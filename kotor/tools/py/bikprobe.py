"""Probe every Bink movie in the install: header, frame index, per-frame packets, audio bitstream.

    python kotor/tools/py/bikprobe.py                     every movies/*.bik, per-file table + totals
    python kotor/tools/py/bikprobe.py FILE.bik ...        just these files
    python kotor/tools/py/bikprobe.py --no-audio-bits     skip the (slow) audio bitstream walk
    python kotor/tools/py/bikprobe.py --frames FILE.bik   also list every frame of FILE
    python kotor/tools/py/bikprobe.py --decode-audio FILE.bik OUT.wav
                                   decode track 0 to 16-bit PCM (needs numpy): a reference to
                                   compare a decoder's output with
    python kotor/tools/py/bikprobe.py --dll [binkw32.dll] check the codec tables in the install's
                                   binkw32.dll (offsets and CRCs in docs/formats/bink.md)

What it checks (see kotor/docs/formats/bink.md):

- the header: signature, revision, file size field, frame counts, size, rate, flags, audio tables;
- the frame index: frame_count + 1 offsets, bit 0 = keyframe, strictly increasing, the first at
  the end of the index, the last equal to the file size;
- each frame: one u32-sized packet per audio track (whose first u32 is the decoded size in bytes),
  then video taking the rest, all within the frame;
- each audio packet's bitstream: walked block by block (2 bits, then per channel two 29-bit
  floats, the band quantizers and run/width-coded coefficients, then 32-bit alignment) without
  running the transform; it must end exactly at the packet end and the block count must match the
  packet's decoded size;
- each video packet (revision 'i' and later): the leading u32 (where the chroma planes start)
  lies within the packet and is 32-bit aligned.

The audio decoder (--decode-audio) was checked against FFmpeg's output for 01c.bik (44.1 kHz) and
56b.bik (48 kHz): largest difference 0.02 of an int16 step before rounding.

Exit status is 1 when any file fails.
"""

import glob
import os
import struct
import sys
import time
from collections import Counter, namedtuple

DEFAULT_DIR = r'F:\Steam\steamapps\common\swkotor'

FLAG_ALPHA = 0x00100000
FLAG_GRAY = 0x00020000
FLAG_SCALE_MASK = 0xF0000000

AUD_16BIT = 0x4000
AUD_STEREO = 0x2000
AUD_DCT = 0x1000

# Upper edges (Hz) of the critical bands Bink audio splits the spectrum into (public: MultimediaWiki
# "Bink Audio"). Only their count matters for walking the bitstream.
CRITICAL_FREQS = (100, 200, 300, 400, 510, 630, 770, 920, 1080, 1270, 1480, 1720, 2000, 2320,
                  2700, 3150, 3700, 4400, 5300, 6400, 7700, 9500, 12000, 15500, 24500)
# Run lengths, in groups of 8 coefficients, for the escape in the coefficient stream.
RUN_GROUPS = (2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 32, 64)

Track = namedtuple('Track', 'max_decoded sample_rate flags track_id')
Header = namedtuple('Header', 'signature revision file_size frames largest_frame frames2 width '
                              'height rate_num rate_den video_flags tracks index_offset')


class BikError(Exception):
    pass


def read_header(d):
    if len(d) < 44:
        raise BikError('shorter than the 44-byte header')
    sig = d[:3]
    if sig != b'BIK':
        raise BikError(f'signature {sig!r}, not BIK')
    rev = chr(d[3])
    fields = struct.unpack_from('<10I', d, 4)
    (size, frames, largest, frames2, width, height, num, den, vflags, ntracks) = fields
    if ntracks > 256:
        raise BikError(f'{ntracks} audio tracks')
    o = 44
    if rev == 'k':
        o += 4      # later revisions add a field here; none in KOTOR
    if len(d) < o + 12 * ntracks:
        raise BikError('truncated audio track tables')
    max_dec = struct.unpack_from(f'<{ntracks}I', d, o)
    o += 4 * ntracks
    rate_flags = struct.unpack_from(f'<{2 * ntracks}H', d, o)
    o += 4 * ntracks
    ids = struct.unpack_from(f'<{ntracks}I', d, o)
    o += 4 * ntracks
    tracks = [Track(max_dec[i], rate_flags[2 * i], rate_flags[2 * i + 1], ids[i])
              for i in range(ntracks)]
    return Header('BIK', rev, size, frames, largest, frames2, width, height, num, den, vflags,
                  tracks, o)


def read_index(d, h):
    """[(offset, keyframe)] for frame_count + 1 entries; the last is the end of the last frame."""
    n = h.frames + 1
    if len(d) < h.index_offset + 4 * n:
        raise BikError('truncated frame index')
    raw = struct.unpack_from(f'<{n}I', d, h.index_offset)
    return [(v & ~1, v & 1) for v in raw]


class AudioFormat:
    """What the bitstream walk needs from a track's header entry (block length, bands, layout)."""

    def __init__(self, track):
        self.rate = track.sample_rate
        self.channels = 2 if track.flags & AUD_STEREO else 1
        self.dct = bool(track.flags & AUD_DCT)
        bits = 9 if self.rate < 22050 else 10 if self.rate < 44100 else 11
        if self.dct:
            self.coded_channels = self.channels    # each channel is its own transform
            rate = self.rate
        else:
            bits += self.channels - 1              # RDFT codes interleaved channels as one signal
            self.coded_channels = 1
            rate = self.rate * self.channels
        self.block_len = 1 << bits                 # coefficients per coded channel
        self.overlap = self.block_len >> 4
        half = (rate + 1) // 2
        nb = 1
        while nb < 25 and half > CRITICAL_FREQS[nb - 1]:
            nb += 1
        self.bands = nb
        # Output samples per channel per block: the block minus the part kept for the overlap.
        self.samples_per_block = (self.block_len - self.overlap) * self.coded_channels // self.channels
        self.block_bytes = self.samples_per_block * self.channels * 2

    def describe(self):
        kind = 'DCT' if self.dct else 'RDFT'
        return (f'{kind} {self.rate} Hz {self.channels}ch, block {self.block_len} coefs/coded ch, '
                f'overlap {self.overlap}, {self.bands} bands, {self.samples_per_block} samples/ch/block')


class Bits:
    """LSB-first reader over 32-bit little-endian words, the order Bink packs its bitstreams."""

    def __init__(self, data, start_bit=0):
        n = len(data) // 4
        self.words = list(struct.unpack_from(f'<{n}I', data)) + [0, 0]
        self.end = 32 * n
        self.pos = start_bit

    def read(self, n):
        p = self.pos
        w = p >> 5
        v = (self.words[w] | (self.words[w + 1] << 32)) >> (p & 31)
        self.pos = p + n
        return v & ((1 << n) - 1)

    def align32(self):
        self.pos = (self.pos + 31) & ~31


def read_audio_block(b, fmt, keep=False):
    """Read one audio block at b.pos (32-bit aligned). Returns the 2 leading bits of a DCT block
    and, when keep, per coded channel (first two coefficients, band quantizer indices, the
    integer coefficients); without keep the values are only skipped, which is much faster."""
    lead = b.read(2) if fmt.dct else 0
    rd = b.read
    n = fmt.block_len
    chans = []
    for _ in range(fmt.coded_channels):
        if keep:
            first = (read_float(b), read_float(b))
            quant = [rd(8) for _ in range(fmt.bands)]
            ints = [0] * n
        else:
            b.pos += 2 * 29 + 8 * fmt.bands
        i = 2
        while i < n:
            j = i + (RUN_GROUPS[rd(4)] * 8 if rd(1) else 8)
            if j > n:
                j = n
            width = rd(4)
            if width:
                if keep:
                    for k in range(i, j):
                        v = rd(width)
                        if v and rd(1):
                            v = -v
                        ints[k] = v
                else:
                    for _ in range(j - i):
                        if rd(width):
                            b.pos += 1   # sign
            i = j
        if b.pos > b.end:
            raise BikError(f'audio block overruns its packet by {b.pos - b.end} bits')
        if keep:
            chans.append((first, quant, ints))
    b.align32()
    return lead, chans


def read_float(b):
    """Bink audio's 29-bit float: 5-bit exponent, 23-bit mantissa, sign; value m * 2^(e - 23)."""
    e = b.read(5)
    m = b.read(23)
    f = m * 2.0 ** (e - 23)
    return -f if b.read(1) else f


def walk_audio_packet(pkt, fmt):
    """(blocks, nonzero leading bit pairs) of one audio packet; raises if the blocks don't fit."""
    if len(pkt) % 4:
        raise BikError(f'audio packet of {len(pkt)} bytes is not whole 32-bit words')
    b = Bits(pkt, 32)
    blocks = 0
    odd_leads = 0
    while b.pos < b.end:
        lead, _ = read_audio_block(b, fmt)
        odd_leads += lead != 0
        blocks += 1
    if b.pos != b.end:
        raise BikError(f'audio packet ends {b.pos - b.end} bits past its data')
    return blocks, odd_leads


def band_starts(fmt):
    """First coefficient of each band, plus block_len at the end (bands + 1 entries)."""
    rate = fmt.rate if fmt.dct else fmt.rate * fmt.channels
    half = (rate + 1) // 2
    n = fmt.block_len
    return [2] + [(CRITICAL_FREQS[i - 1] * n // half) & ~1 for i in range(1, fmt.bands)] + [n]


def decode_audio(path, track=0):
    """Track `track` of a DCT-coded file as an int16 array of shape (samples, channels).

    Written from the description in docs/formats/bink.md, as a reference for checking a real
    decoder; slow (pure Python bit reading, numpy for the transform)."""
    import numpy as np
    with open(path, 'rb') as f:
        d = f.read()
    h = read_header(d)
    fmt = AudioFormat(h.tracks[track])
    if not fmt.dct:
        raise BikError('only the DCT variant is implemented (all KOTOR movies use it)')
    n, ov, ch = fmt.block_len, fmt.overlap, fmt.channels
    starts = band_starts(fmt)
    k = np.arange(n)
    basis = np.cos(np.pi * np.outer(k + 0.5, k) / n)       # basis[t, f] = cos(pi f (t + 1/2) / n)
    gain = 2.0 / np.sqrt(n)
    idx = read_index(d, h)
    out = []
    tail = None
    total = 0
    for fi in range(h.frames):
        o = idx[fi][0]
        for t in range(len(h.tracks)):
            size = struct.unpack_from('<I', d, o)[0]
            o += 4
            if t == track and size:
                total += struct.unpack_from('<I', d, o)[0]
                b = Bits(d[o:o + size], 32)
                while b.pos < b.end:
                    _, chans = read_audio_block(b, fmt, keep=True)
                    block = np.empty((n, ch))
                    for c, (first, quant, ints) in enumerate(chans):
                        x = np.array(ints, dtype=np.float64)
                        x[0], x[1] = first
                        for q in range(fmt.bands):
                            x[starts[q]:starts[q + 1]] *= 10.0 ** (min(quant[q], 95) * 0.0664)
                        block[:, c] = gain * (basis @ x)
                    if tail is not None:
                        # Cross-fade over the interleaved samples: channel c of sample i weighs
                        # (i * ch + c) / (ov * ch), so the channels' ramps are offset slightly.
                        w = (np.arange(ov)[:, None] * ch + np.arange(ch)[None, :]) / (ov * ch)
                        block[:ov] = tail * (1 - w) + block[:ov] * w
                    tail = block[n - ov:].copy()
                    out.append(block[:n - ov])
            o += size
    pcm = np.concatenate(out)[:total // (2 * ch)]   # the decoded-size fields trim the last block
    return np.clip(np.floor(pcm + 0.5), -32768, 32767).astype('<i2'), fmt.rate


def write_wav(path, pcm, rate):
    import wave
    with wave.open(path, 'wb') as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


# Bink's constant tables as binkw32.dll 1.5v (KOTOR's Steam install) holds them: name, file offset,
# size, CRC-32. The video decoder needs them; see docs/formats/bink.md, "Tables".
DLL_TABLES = (
    ('Huffman code lengths, 16 trees x 16 u8', 0x39A48, 256, 0xf2c3ec57),
    ('Huffman codes (LSB-first), 16 x 16 u8', 0x39B50, 256, 0xa2739da1),
    ('DCT coefficient scan, 64 u8', 0x39C60, 64, 0x8fbdd9f2),
    ('run-block scan patterns, 16 x 64 u8', 0x39CA8, 1024, 0xf9e3218a),
    ('intra quantizers, 16 x 64 i32, raster order', 0x3A0C0, 4096, 0xd53c4639),
    ('inter quantizers, 16 x 64 i32, raster order', 0x3C100, 4096, 0xc4f4dcd3),
    ('block-type run lengths, 4 u8', 0x3E648, 4, 0x37ee7637),
    ('audio run lengths (x8 coefs), 16 u8', 0x44840, 16, 0x7c59d03f),
    ('audio band edges in Hz, 26 u32', 0x44850, 104, 0x67e0ebbd),
)


def check_dll(path):
    import zlib
    with open(path, 'rb') as f:
        d = f.read()
    marker = 'FileVersion'.encode('utf-16-le')
    i = d.find(marker)
    version = '?'
    if i >= 0:
        j = i + len(marker)
        while j < len(d) and d[j] == 0:
            j += 1
        version = d[j:j + 32].decode('utf-16-le', 'replace').split('\0', 1)[0]
    print(f'{path}: FileVersion {version}')
    bad = 0
    for name, off, size, crc in DLL_TABLES:
        got = zlib.crc32(d[off:off + size])
        ok = got == crc
        bad += not ok
        print(f'  0x{off:05X} {size:5d}  {"ok " if ok else "BAD"} {name}')
    lens = d[0x39A48:0x39A48 + 256]
    codes = d[0x39B50:0x39B50 + 256]
    for t in range(16):
        ls, cs = lens[16 * t:16 * t + 16], codes[16 * t:16 * t + 16]
        kraft = sum(2.0 ** -n for n in ls)
        clash = any(i != j and ls[i] <= ls[j] and cs[j] & ((1 << ls[i]) - 1) == cs[i]
                    for i in range(16) for j in range(16))
        if kraft != 1.0 or clash:
            bad += 1
            print(f'  tree {t}: not a complete LSB-first prefix code')
    print('tables:', 'all match' if not bad else f'{bad} mismatches')
    return 1 if bad else 0


FileReport = namedtuple('FileReport', 'name size header keyframes largest_seen video_bytes '
                                      'audio_bytes audio_packets empty_audio decoded_bytes blocks '
                                      'first_decoded max_decoded_seen trimmed odd_leads per_packet '
                                      'chroma_offsets errors')


def probe_file(path, audio_bits=True, list_frames=False):
    name = os.path.basename(path)
    with open(path, 'rb') as f:
        d = f.read()
    errors = []
    h = read_header(d)
    if h.revision not in 'bdfghi':
        errors.append(f'unexpected revision {h.revision!r}')
    if h.file_size + 8 != len(d):
        errors.append(f'file size field {h.file_size} + 8 != {len(d)}')
    if h.frames2 != h.frames:
        errors.append(f'second frame count {h.frames2} != {h.frames}')
    if h.rate_num == 0 or h.rate_den == 0:
        errors.append(f'frame rate {h.rate_num}/{h.rate_den}')
    idx = read_index(d, h)
    first = h.index_offset + 4 * (h.frames + 1)
    if idx[0][0] != first:
        errors.append(f'first frame at {idx[0][0]}, index ends at {first}')
    if not idx[0][1]:
        errors.append('frame 0 is not marked as a keyframe')
    if idx[-1][0] != len(d):
        errors.append(f'last index entry {idx[-1][0]} != file size {len(d)}')
    fmts = [AudioFormat(t) for t in h.tracks]
    nt = len(h.tracks)
    keyframes = 0
    largest = 0
    video_bytes = 0
    audio_bytes = [0] * nt
    audio_packets = [0] * nt
    empty = [0] * nt
    decoded = [0] * nt
    blocks = [0] * nt
    first_decoded = [None] * nt
    max_decoded = [0] * nt
    chroma = []
    short = [[] for _ in range(nt)]
    odd_leads = [0] * nt
    per_packet = Counter()
    last_packet = [None] * nt
    for fi in range(h.frames):
        start, key = idx[fi]
        end = idx[fi + 1][0]
        if end <= start:
            errors.append(f'frame {fi}: offsets not increasing ({start} -> {end})')
            break
        keyframes += key
        size = end - start
        largest = max(largest, size)
        o = start
        line = [f'{fi:5d} {"K" if key else " "} {size:6d}']
        for t in range(nt):
            if o + 4 > end:
                errors.append(f'frame {fi}: no room for track {t} packet size')
                break
            asz = struct.unpack_from('<I', d, o)[0]
            o += 4
            if o + asz > end:
                errors.append(f'frame {fi}: track {t} packet of {asz} bytes overruns the frame')
                break
            if asz:
                if asz < 4:
                    errors.append(f'frame {fi}: track {t} packet of {asz} bytes has no decoded size')
                    break
                dec = struct.unpack_from('<I', d, o)[0]
                if first_decoded[t] is None:
                    first_decoded[t] = dec
                audio_packets[t] += 1
                last_packet[t] = fi
                audio_bytes[t] += asz
                decoded[t] += dec
                max_decoded[t] = max(max_decoded[t], dec)
                line.append(f'a{t} {asz:5d}B dec {dec:6d}')
                if audio_bits:
                    try:
                        nb, odd = walk_audio_packet(d[o:o + asz], fmts[t])
                    except BikError as e:
                        errors.append(f'frame {fi}: track {t}: {e}')
                        nb = None
                    if nb is not None:
                        odd_leads[t] += odd
                        per_packet[nb] += 1
                        blocks[t] += nb
                        full = nb * fmts[t].block_bytes
                        if dec != full:
                            # Only the file's last packet may stop short inside its last block.
                            short[t].append((fi, nb, dec))
                        line.append(f'({nb} blk)')
            else:
                empty[t] += 1
                line.append(f'a{t}     -')
            o += asz
        vsz = end - o
        video_bytes += vsz
        if h.revision >= 'i':
            if vsz < 4:
                errors.append(f'frame {fi}: video packet of {vsz} bytes')
            else:
                c = struct.unpack_from('<I', d, o)[0]
                if c % 4 or c < 4 or c > vsz:
                    errors.append(f'frame {fi}: chroma offset {c} outside the {vsz}-byte video packet')
                chroma.append((c, vsz))
                line.append(f'video {vsz:6d}B (luma ends {c})')
        else:
            line.append(f'video {vsz:6d}B')
        if list_frames:
            print('  '.join(line))
    trimmed = [0] * nt
    for t in range(nt):
        bb = fmts[t].block_bytes
        for fi, nb, dec in short[t]:
            if fi == last_packet[t] and (nb - 1) * bb < dec < nb * bb:
                trimmed[t] = nb * bb - dec
            else:
                errors.append(f'frame {fi}: track {t}: {nb} blocks but decoded size '
                              f'{dec} != {nb} x {bb}')
    if largest != h.largest_frame:
        errors.append(f'largest frame {largest} != header {h.largest_frame}')
    for t, tr in enumerate(h.tracks):
        if first_decoded[t] is not None and tr.max_decoded != first_decoded[t]:
            errors.append(f'track {t}: header buffer size {tr.max_decoded} != first packet\'s '
                          f'decoded size {first_decoded[t]}')
        if max_decoded[t] > tr.max_decoded:
            errors.append(f'track {t}: a packet decodes to {max_decoded[t]} > header {tr.max_decoded}')
    return FileReport(name, len(d), h, keyframes, largest, video_bytes, audio_bytes,
                      audio_packets, empty, decoded, blocks, first_decoded, max_decoded, trimmed,
                      odd_leads, per_packet, chroma, errors)


def flag_names(vflags):
    out = []
    if vflags & FLAG_ALPHA:
        out.append('alpha')
    if vflags & FLAG_GRAY:
        out.append('gray')
    if vflags & FLAG_SCALE_MASK:
        out.append(f'scale{vflags >> 28}')
    rest = vflags & ~(FLAG_ALPHA | FLAG_GRAY | FLAG_SCALE_MASK)
    if rest:
        out.append(f'0x{rest:x}')
    return ','.join(out) or '-'


def track_desc(tr):
    kind = 'DCT' if tr.flags & AUD_DCT else 'RDFT'
    ch = 2 if tr.flags & AUD_STEREO else 1
    bits = 16 if tr.flags & AUD_16BIT else 8
    return f'{tr.sample_rate}/{ch}ch/{kind}/{bits}bit'


def main(argv):
    if argv[:1] == ['--dll']:
        game = os.environ.get('KOTOR_DIR', DEFAULT_DIR)
        return check_dll(argv[1] if len(argv) > 1 else os.path.join(game, 'binkw32.dll'))
    if argv[:1] == ['--decode-audio']:
        if len(argv) != 3:
            print('usage: bikprobe.py --decode-audio FILE.bik OUT.wav')
            return 2
        pcm, rate = decode_audio(argv[1])
        write_wav(argv[2], pcm, rate)
        print(f'{argv[2]}: {pcm.shape[0]} samples x {pcm.shape[1]} ch at {rate} Hz')
        return 0
    audio_bits = '--no-audio-bits' not in argv
    list_frames = '--frames' in argv
    files = [a for a in argv if not a.startswith('--')]
    if not files:
        game = os.environ.get('KOTOR_DIR', DEFAULT_DIR)
        files = sorted(glob.glob(os.path.join(game, 'movies', '*.bik')), key=str.lower)
    t0 = time.time()
    reports = []
    failed = 0
    print(f'{"file":13} {"rev":3} {"WxH":8} {"fps":>6} {"frames":>6} {"keys":>4} {"secs":>7} '
          f'{"vflags":6} {"audio":22} {"apkts":>5} {"empty":>5} {"blocks":>6} {"audio s":>7} '
          f'{"largest":>7} {"MB":>6}')
    for p in files:
        try:
            r = probe_file(p, audio_bits, list_frames)
        except BikError as e:
            print(f'{os.path.basename(p)}: FAIL {e}')
            failed += 1
            continue
        reports.append(r)
        h = r.header
        fps = h.rate_num / h.rate_den
        secs = h.frames / fps
        audio = ' '.join(track_desc(t) for t in h.tracks) or 'none'
        if h.tracks:
            ch = 2 if h.tracks[0].flags & AUD_STEREO else 1
            asecs = r.decoded_bytes[0] / (2 * ch) / h.tracks[0].sample_rate
            apk, emp, blk = r.audio_packets[0], r.empty_audio[0], r.blocks[0]
        else:
            asecs, apk, emp, blk = 0.0, 0, 0, 0
        print(f'{r.name:13} BIK{h.revision} {h.width}x{h.height} {fps:6.3f} {h.frames:6d} '
              f'{r.keyframes:4d} {secs:7.2f} {flag_names(h.video_flags):6} {audio:22} '
              f'{apk:5d} {emp:5d} {blk:6d} {asecs:7.2f} {r.largest_seen:7d} {r.size / 1e6:6.2f}')
        for e in r.errors[:10]:
            print(f'    FAIL {e}')
        if len(r.errors) > 10:
            print(f'    ... {len(r.errors) - 10} more')
        if r.errors:
            failed += 1

    print()
    print(f'files: {len(files)}, failed: {failed}' + ('' if audio_bits else ' (audio bitstream not walked)'))
    if not reports:
        return 1 if failed else 0
    hs = [r.header for r in reports]
    print('revisions:', dict(Counter('BIK' + h.revision for h in hs)))
    print('sizes:', dict(Counter(f'{h.width}x{h.height}' for h in hs)))
    print('frame rates:', dict(Counter(f'{h.rate_num}/{h.rate_den}' for h in hs)))
    print('video flags:', dict(Counter(flag_names(h.video_flags) for h in hs)))
    print('audio tracks per file:', dict(Counter(len(h.tracks) for h in hs)))
    tracks = [t for h in hs for t in h.tracks]
    print('track formats:', dict(Counter(track_desc(t) for t in tracks)))
    print('track flags:', dict(Counter(f'0x{t.flags:04x}' for t in tracks)))
    print('track ids:', dict(Counter(t.track_id for t in tracks)))
    print('track buffer sizes:', dict(Counter(t.max_decoded for t in tracks)))
    for t in sorted({(t.sample_rate, t.flags) for t in tracks}):
        print('  layout', AudioFormat(Track(0, t[0], t[1], 0)).describe())
    frames = sum(h.frames for h in hs)
    secs = sum(h.frames * h.rate_den / h.rate_num for h in hs)
    keys = sum(r.keyframes for r in reports)
    print(f'frames: {frames}, keyframes: {keys}, duration: {secs:.1f} s ({secs / 60:.1f} min)')
    print('keyframes per file:', dict(Counter(r.keyframes for r in reports)))
    vbytes = sum(r.video_bytes for r in reports)
    abytes = sum(sum(r.audio_bytes) for r in reports)
    apk = sum(sum(r.audio_packets) for r in reports)
    emp = sum(sum(r.empty_audio) for r in reports)
    print(f'bytes: video {vbytes}, audio {abytes} '
          f'({8 * vbytes / secs / 1000:.0f} + {8 * abytes / secs / 1000:.0f} kbit/s on average)')
    print(f'audio packets: {apk} non-empty, {emp} empty (size 0)')
    if audio_bits:
        firsts = Counter()
        later = Counter()
        for r in reports:
            for t, tr in enumerate(r.header.tracks):
                firsts[r.first_decoded[t] // AudioFormat(tr).block_bytes] += 1
        print('blocks in each file\'s first audio packet:', dict(sorted(firsts.items())))
        blk = sum(sum(r.blocks) for r in reports)
        print(f'audio blocks walked: {blk}')
        tr = [r.trimmed[t] for r in reports for t in range(len(r.header.tracks))]
        print(f'tracks whose last packet decodes to less than its blocks: '
              f'{sum(x > 0 for x in tr)} of {len(tr)} (bytes dropped: {min(tr)}..{max(tr)})')
        pp = Counter()
        for r in reports:
            pp.update(r.per_packet)
        print('blocks per non-empty audio packet:', dict(sorted(pp.items())))
        print('DCT blocks whose 2 leading bits are not 0:', sum(sum(r.odd_leads) for r in reports))
    drift = []
    for r in reports:
        h = r.header
        if h.tracks:
            tr = h.tracks[0]
            ch = 2 if tr.flags & AUD_STEREO else 1
            a = r.decoded_bytes[0] / (2 * ch) / tr.sample_rate
            v = h.frames * h.rate_den / h.rate_num
            drift.append((a - v, r.name))
    if drift:
        drift.sort()
        print(f'audio minus video duration: min {drift[0][0]:+.3f} s ({drift[0][1]}), '
              f'max {drift[-1][0]:+.3f} s ({drift[-1][1]})')
    if any(r.chroma_offsets for r in reports):
        share = [c / v for r in reports for c, v in r.chroma_offsets]
        print(f'video: luma share of the packet (from the leading u32): min {min(share):.2f}, '
              f'mean {sum(share) / len(share):.2f}, max {max(share):.2f}')
    print(f'time: {time.time() - t0:.1f} s')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
