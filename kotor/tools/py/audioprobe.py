"""Classify every audio file and WAV/MP3 resource in the KOTOR install, and report what the
decoders (PCM WAV, IMA ADPCM, MP3) must handle. Exploration only; see docs/formats/audio.md.

    python kotor/tools/py/audioprobe.py [--jobs N] [--examples N] [--list CLASS]
    python kotor/tools/py/audioprobe.py --refs

Inputs: every *.wav and *.mp3 file anywhere under the install (streamwaves/, streamsounds/,
streammusic/, launcher/, Override/, ...) and every wav/mp3 resource in every container
(chitin.key's BIFs, modules/, rims/, lips/, texture packs, patch.erf, saves), through
kres.Game.every_entry.

Every input gets a class WRAPPER/PAYLOAD:

    wrapper   none      the bytes are what they look like
              mp3pad    whole MPEG audio frames (470 bytes in KOTOR) glued in front of a real
                        RIFF/WAVE file
              riffstub  a RIFF/WAVE header whose data chunk is empty, followed by an MP3 stream
    payload   pcm, ima-adpcm, ms-adpcm, riff-mp3 (format tag 0x55), tag-0xNNNN, mp3, unknown

Each MPEG stream is walked frame by frame to its end (sync, header, frame length), and the
Layer III side information of every frame is parsed (block types, Huffman table selects,
scalefactor flags, the bit reservoir). IMA ADPCM block headers are checked in every block, and a
sample of blocks is decoded to confirm the nibble order and the stereo interleave from the data.

--list CLASS prints the name of every input of that class (e.g. --list none/pcm).
--refs prints where the audio is referenced from: dialog.tlk sound resrefs, the .ssf soundsets,
ambientmusic/ambientsound/loadscreens.2da, and ResRefs found in .dlg/.uts/.git/.utp/.utc files,
resolved against streamwaves/, streamsounds/, streammusic/ and WAV resources.
"""

import hashlib
import os
import re
import statistics
import struct
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402

# --- MPEG audio header tables (ISO 11172-3 / 13818-3) ------------------------------------------

VERSIONS = {0: '2.5', 2: '2', 3: '1'}          # header bits 20..19; 1 is reserved
LAYERS = {1: 3, 2: 2, 3: 1}                     # header bits 18..17; 0 is reserved
BITRATES = {                                    # kbit/s by (version family, layer); index 0 = free
    ('1', 1): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
    ('1', 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
    ('1', 3): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    ('2', 1): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
    ('2', 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
    ('2', 3): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
RATES = {'1': [44100, 48000, 32000], '2': [22050, 24000, 16000], '2.5': [11025, 12000, 8000]}
MODES = ['stereo', 'joint', 'dual', 'mono']

# Long-block scalefactor band boundaries (in spectral lines), used only to tell which big_values
# regions are non-empty so that the Huffman-table histogram counts tables actually exercised.
SFB_LONG = {
    44100: [0, 4, 8, 12, 16, 20, 24, 30, 36, 44, 52, 62, 74, 90, 110, 134, 162, 196, 238, 288, 342, 418, 576],
    48000: [0, 4, 8, 12, 16, 20, 24, 30, 36, 42, 50, 60, 72, 88, 106, 128, 156, 190, 230, 276, 330, 384, 576],
    32000: [0, 4, 8, 12, 16, 20, 24, 30, 36, 44, 54, 66, 82, 102, 126, 156, 194, 240, 296, 364, 448, 550, 576],
    22050: [0, 6, 12, 18, 24, 30, 36, 44, 54, 66, 80, 96, 116, 140, 168, 200, 238, 284, 336, 396, 464, 522, 576],
    24000: [0, 6, 12, 18, 24, 30, 36, 44, 54, 66, 80, 96, 114, 136, 162, 194, 232, 278, 332, 394, 464, 540, 576],
    16000: [0, 6, 12, 18, 24, 30, 36, 44, 54, 66, 80, 96, 116, 140, 168, 200, 238, 284, 336, 396, 464, 522, 576],
    11025: [0, 6, 12, 18, 24, 30, 36, 44, 54, 66, 80, 96, 116, 140, 168, 200, 238, 284, 336, 396, 464, 522, 576],
    12000: [0, 6, 12, 18, 24, 30, 36, 44, 54, 66, 80, 96, 116, 140, 168, 200, 238, 284, 336, 396, 464, 522, 576],
    8000: [0, 12, 24, 36, 48, 60, 72, 88, 108, 132, 160, 192, 232, 280, 336, 400, 476, 566, 568, 570, 572, 574, 576],
}

# --- IMA ADPCM tables (IMA / Microsoft WAVE_FORMAT_IMA_ADPCM) -------------------------------------

IMA_STEP = [
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66,
    73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408,
    449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
    2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630,
    9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794,
    32767,
]
IMA_INDEX = [-1, -1, -1, -1, 2, 4, 6, 8]

FORMAT_TAGS = {1: 'pcm', 2: 'ms-adpcm', 0x11: 'ima-adpcm', 0x55: 'riff-mp3'}


def u16(d, p):
    return d[p] | d[p + 1] << 8


def u32(d, p):
    return d[p] | d[p + 1] << 8 | d[p + 2] << 16 | d[p + 3] << 24


# --- MPEG frame headers --------------------------------------------------------------------------

def parse_header(d, p):
    """The MPEG audio frame header at d[p:p+4] as a tuple, or None if it is not one.
    (version, layer, crc, bitrate_kbps, rate, padding, private, mode, mode_ext, copyright,
     original, emphasis, frame_len, samples_per_frame, side_info_len, raw_bitrate_index)
    frame_len is 0 for a free-format frame."""
    if p + 4 > len(d):
        return None
    b0, b1, b2, b3 = d[p], d[p + 1], d[p + 2], d[p + 3]
    if b0 != 0xFF or b1 & 0xE0 != 0xE0:
        return None
    vbits = (b1 >> 3) & 3
    lbits = (b1 >> 1) & 3
    bri = b2 >> 4
    sri = (b2 >> 2) & 3
    if vbits == 1 or lbits == 0 or bri == 15 or sri == 3:
        return None
    version = VERSIONS[vbits]
    layer = LAYERS[lbits]
    fam = '1' if version == '1' else '2'
    kbps = BITRATES[(fam, layer)][bri]
    rate = RATES[version][sri]
    pad = (b2 >> 1) & 1
    mode = b3 >> 6
    if layer == 1:
        spf = 384
        flen = (12 * kbps * 1000 // rate + pad) * 4 if kbps else 0
    elif layer == 2 or version == '1':
        spf = 1152
        flen = 144 * kbps * 1000 // rate + pad if kbps else 0
    else:
        spf = 576
        flen = 72 * kbps * 1000 // rate + pad if kbps else 0
    if layer == 3:
        if version == '1':
            si = 17 if mode == 3 else 32
        else:
            si = 9 if mode == 3 else 17
    else:
        si = 0
    return (version, layer, not (b1 & 1), kbps, rate, pad, b2 & 1, mode, (b3 >> 4) & 3,
            (b3 >> 3) & 1, (b3 >> 2) & 1, b3 & 3, flen, spf, si, bri)


def mp3_prefix_len(d):
    """If d starts with whole MPEG frames that are followed, at a frame boundary, by a RIFF/WAVE
    header, the byte length of those frames; else 0."""
    p = 0
    for _ in range(64):
        h = parse_header(d, p)
        if h is None or h[12] == 0:
            return 0
        p += h[12]
        if d[p:p + 4] == b'RIFF' and d[p + 8:p + 12] == b'WAVE':
            return p
    return 0


def find_free_len(d, p, end, h):
    """Length of a free-format frame: distance to the next header with the same fixed fields."""
    key = (d[p + 1], d[p + 2] & 0xFC)
    q = p + 4 + h[14]
    while True:
        q = d.find(b'\xff', q, end)
        if q < 0 or q + 4 > end:
            return 0
        if (d[q + 1], d[q + 2] & 0xFC) == key:
            return q - p
        q += 1


def compatible(h, ref):
    return h[0] == ref[0] and h[1] == ref[1] and h[4] == ref[4]


def resync(d, p, end, ref):
    """Next position >= p holding a header compatible with ref whose successor is also a
    compatible header (or the end of the stream)."""
    while True:
        p = d.find(b'\xff', p, end)
        if p < 0 or p + 4 > end:
            return None
        h = parse_header(d, p)
        if h and h[12] and (ref is None or compatible(h, ref)):
            q = p + h[12]
            if q == end:
                return p
            h2 = parse_header(d, q)
            if h2 and (ref is None or compatible(h2, ref)):
                return p
        p += 1


def parse_side_info(d, p, h):
    """Layer III side info of the frame at p: (main_data_begin, scfsi list, granules) where
    granules is a list of (gr, ch, fields dict)."""
    version, mode, crc, si = h[0], h[7], h[2], h[14]
    q = p + 4 + (2 if crc else 0)
    v = int.from_bytes(d[q:q + si], 'big')
    left = si * 8
    nch = 1 if mode == 3 else 2

    def take(n):
        nonlocal left
        left -= n
        return (v >> left) & ((1 << n) - 1)

    mpeg1 = version == '1'
    if mpeg1:
        mdb = take(9)
        take(5 if nch == 1 else 3)
        scfsi = [take(4) for _ in range(nch)]
        ngr = 2
    else:
        mdb = take(8)
        take(1 if nch == 1 else 2)
        scfsi = []
        ngr = 1
    grs = []
    for gr in range(ngr):
        for ch in range(nch):
            g = {'p23': take(12), 'bv': take(9), 'gg': take(8), 'sfc': take(4 if mpeg1 else 9)}
            g['wsf'] = take(1)
            if g['wsf']:
                g['bt'] = take(2)
                g['mixed'] = take(1)
                g['ts'] = [take(5), take(5)]
                g['sbg'] = [take(3), take(3), take(3)]
                g['r0'] = g['r1'] = None
            else:
                g['bt'] = 0
                g['mixed'] = 0
                g['ts'] = [take(5), take(5), take(5)]
                g['sbg'] = [0, 0, 0]
                g['r0'] = take(4)
                g['r1'] = take(3)
            g['preflag'] = take(1) if mpeg1 else None
            g['sfs'] = take(1)
            g['c1'] = take(1)
            grs.append((gr, ch, g))
    return mdb, scfsi, grs


def block_kind(g):
    if not g['wsf']:
        return 'long'
    bt, mixed = g['bt'], g['mixed']
    if bt == 0:
        return 'INVALID(wsf with block_type 0)'
    if bt == 2:
        return 'short+mixed' if mixed else 'short'
    name = 'start' if bt == 1 else 'stop'
    return name + ('+mixed-flag' if mixed else '')


def region_ends(g, rate):
    """Spectral-line ends of the big_values regions 0, 1, 2 (empty regions have end <= start)."""
    bv2 = min(g['bv'] * 2, 576)
    if g['wsf']:
        r0 = 36 if g['bt'] == 2 else SFB_LONG[rate][8]
        return [min(r0, bv2), bv2]
    sfb = SFB_LONG[rate]
    i0 = min(g['r0'] + 1, 22)
    i1 = min(g['r0'] + g['r1'] + 2, 22)
    return [min(sfb[i0], bv2), min(sfb[i1], bv2), bv2]


def read_xing(d, p, h):
    """(tag name, fields) for a Xing/Info/VBRI header in the frame at p, or None."""
    off = p + 4 + (2 if h[2] else 0) + h[14]
    tag = d[off:off + 4]
    if tag in (b'Xing', b'Info'):
        flags = struct.unpack_from('>I', d, off + 4)[0]
        q = off + 8
        f = {'flags': flags}
        if flags & 1:
            f['frames'] = struct.unpack_from('>I', d, q)[0]
            q += 4
        if flags & 2:
            f['bytes'] = struct.unpack_from('>I', d, q)[0]
            q += 4
        if flags & 4:
            q += 100
        if flags & 8:
            q += 4
        enc = d[q:q + 9]
        if enc[:4] in (b'LAME', b'Lavf', b'Lavc', b'GOGO'):
            f['encoder'] = enc.rstrip(b'\0 ').decode('latin-1')
            dp = q + 21
            if dp + 3 <= len(d):
                x = int.from_bytes(d[dp:dp + 3], 'big')
                f['delay'] = x >> 12
                f['padding'] = x & 0xFFF
        return tag.decode(), f
    voff = p + 4 + 32
    if d[voff:voff + 4] == b'VBRI':
        return 'VBRI', {}
    return None


class Mp3Stats:
    """Histograms and counts over MPEG streams; merges by adding."""

    def __init__(self):
        self.c = Counter()      # (field, value) -> frames or granules or streams
        self.mx = {}            # field -> max
        self.mn = {}            # field -> min

    def hi(self, k, v):
        if v > self.mx.get(k, -1):
            self.mx[k] = v

    def lo(self, k, v):
        if k not in self.mn or v < self.mn[k]:
            self.mn[k] = v

    def merge(self, o):
        self.c.update(o.c)
        for k, v in o.mx.items():
            self.hi(k, v)
        for k, v in o.mn.items():
            self.lo(k, v)


def scan_mp3(d, start, end, st):
    """Walk the MPEG stream d[start:end] frame by frame, adding to Mp3Stats st. Returns a dict
    with per-stream facts (frames, samples, rate, channels, issues)."""
    info = {'frames': 0, 'samples': 0, 'rate': None, 'nch': None, 'issues': [], 'bitrates': set()}
    c = st.c
    p = start
    if d[p:p + 3] == b'ID3':
        size = (d[p + 6] & 0x7F) << 21 | (d[p + 7] & 0x7F) << 14 | (d[p + 8] & 0x7F) << 7 | d[p + 9] & 0x7F
        c[('stream.id3v2-version', f'2.{d[p + 3]}.{d[p + 4]} flags=0x{d[p + 5]:02x}')] += 1
        st.hi('id3v2 total bytes', 10 + size)
        st.lo('id3v2 total bytes', 10 + size)
        p += 10 + size + (10 if d[p + 5] & 0x10 else 0)
        c['stream.id3v2'] += 1
        if parse_header(d, p) is None:
            c['stream.id3v2-not-followed-by-a-frame'] += 1
    tail = end
    if tail - p >= 128 and d[tail - 128:tail - 125] == b'TAG':
        c['stream.id3v1'] += 1
        tail -= 128
    if tail - p >= 32 and d[tail - 32:tail - 24] == b'APETAGEX':
        c['stream.ape'] += 1
        tail -= 32
    if d.find(b'LYRICS', p, tail) >= 0 and d.find(b'LYRICS200', p, tail) >= 0:
        c['stream.lyrics3'] += 1
    lame = d.find(b'LAME', p, tail)
    if lame >= 0:
        c[('stream.lame-string', d[lame:lame + 8].decode('latin-1'))] += 1
    ref = None
    first = True
    junk = 0
    resyncs = 0
    reservoir = 0           # main-data bytes of earlier frames (the virtual main-data stream)
    prev_end_bits = 0       # end (in bits) of the previous frame's main data in that stream
    mode_seen = set()
    while p + 4 <= tail:
        h = parse_header(d, p)
        if h is None or (ref is not None and not compatible(h, ref)):
            q = resync(d, p + 1, tail, ref)
            if q is None:
                info['issues'].append(f'{tail - p} bytes after the last frame')
                c['stream.trailing-bytes'] += 1
                st.hi('trailing bytes', tail - p)
                break
            junk += q - p
            resyncs += 1
            p = q
            continue
        (version, layer, crc, kbps, rate, pad, priv, mode, mext, copy, orig, emph,
         flen, spf, si, bri) = h
        if flen == 0:
            flen = find_free_len(d, p, tail, h)
            c['frame.free-format'] += 1
            if flen == 0:
                info['issues'].append('free-format frame with no following sync')
                break
        if p + flen > tail:
            info['issues'].append(f'last frame truncated: {tail - p} of {flen} bytes')
            c['stream.truncated-last-frame'] += 1
            break
        if ref is None:
            ref = h
        info['frames'] += 1
        info['samples'] += spf
        info['rate'] = rate
        info['nch'] = 1 if mode == 3 else 2
        mode_seen.add(mode)
        c[('version', version)] += 1
        c[('layer', layer)] += 1
        c[('rate', rate)] += 1
        c[('mode', MODES[mode])] += 1
        if mode == 1:
            c[('mode_ext', ('MS' if mext & 2 else '') + ('+' if mext == 3 else '')
               + ('IS' if mext & 1 else '') or 'none')] += 1
        c[('crc', crc)] += 1
        c[('padding', pad)] += 1
        c[('frame-bytes', flen)] += 1
        c[('private', priv)] += 1
        c[('copyright', copy)] += 1
        c[('original', orig)] += 1
        c[('emphasis', emph)] += 1
        tagframe = None
        if first:
            first = False
            tagframe = read_xing(d, p, h) if layer == 3 else None
            if tagframe:
                name, f = tagframe
                c[('stream.tag', name)] += 1
                c[('stream.tag-flags', f.get('flags'))] += 1
                if 'encoder' in f:
                    c[('stream.lame-tag', f['encoder'])] += 1
                    c[('stream.lame-delay', f['delay'])] += 1
                    st.hi('lame end padding', f['padding'])
                    st.lo('lame end padding', f['padding'])
                if 'frames' in f:
                    info['xing_frames'] = f['frames']
                if 'bytes' in f and f['bytes'] != tail - p:
                    c['stream.xing-byte-count-mismatch'] += 1
            else:
                c[('stream.tag', 'none')] += 1
        if tagframe is None:
            c[('bitrate', kbps)] += 1
            info['bitrates'].add(kbps)
        else:
            c[('bitrate.tagframe', kbps)] += 1
        if layer == 3:
            main_avail = flen - 4 - (2 if crc else 0) - si
            mdb, scfsi, grs = parse_side_info(d, p, h)
            st.hi('main_data_begin', mdb)
            used = sum(g['p23'] for _, _, g in grs)
            start_bits = (reservoir - mdb) * 8
            if reservoir - mdb < 0:
                c['res.begins-before-stream'] += 1
                info['issues'].append(f'frame {info["frames"] - 1}: main_data_begin {mdb} > reservoir {reservoir}')
            if start_bits < prev_end_bits:
                c['res.overlaps-previous-frame'] += 1
            end_bits = start_bits + used
            if end_bits > (reservoir + main_avail) * 8:
                c['res.overruns-frame'] += 1
            prev_end_bits = max(prev_end_bits, end_bits)
            reservoir += main_avail
            st.hi('part2_3_length', max(g['p23'] for _, _, g in grs))
            if tagframe is None:
                for s in scfsi:
                    c[('scfsi', 'used' if s else 'zero')] += 1
                kinds = {}
                for gr, ch, g in grs:
                    k = block_kind(g)
                    c[('block', k)] += 1
                    kinds[(gr, ch)] = g['bt'] if g['wsf'] else 0
                    if g['bv'] > 288:
                        c['granule.big_values>288'] += 1
                    st.hi('big_values', g['bv'])
                    st.hi('global_gain', g['gg'])
                    st.lo('global_gain', g['gg'])
                    if g['p23'] == 0:
                        c['granule.empty(part2_3_length=0)'] += 1
                    c[('scalefac_scale', g['sfs'])] += 1
                    if g['preflag'] is not None:
                        c[('preflag', g['preflag'])] += 1
                    if any(g['sbg']):
                        c['granule.subblock_gain-nonzero'] += 1
                    if g['wsf']:
                        st.hi('subblock_gain', max(g['sbg']))
                    lo = 0
                    for t, e in zip(g['ts'], region_ends(g, rate)):
                        if e > lo:
                            c[('huffman-table', t)] += 1
                        lo = max(lo, e)
                    if g['bv'] * 2 < 576 and g['p23'] > 0:
                        c[('count1-table', 'B' if g['c1'] else 'A')] += 1
                    if version != '1':
                        st.hi('lsf scalefac_compress', g['sfc'])
                if mode == 1:
                    for gr in range(2 if version == '1' else 1):
                        if kinds.get((gr, 0)) != kinds.get((gr, 1)):
                            c['joint.granule-block-types-differ' + ('(MS on)' if mext & 2 else '(MS off)')] += 1
                    if mext & 1 and version != '1':
                        c['joint.lsf-intensity'] += 1
        p += flen
    if junk:
        info['issues'].append(f'{resyncs} lost syncs, {junk} junk bytes between frames')
        c['stream.junk'] += 1
        st.hi('junk bytes', junk)
    c[('stream.modes', '+'.join(sorted(MODES[m] for m in mode_seen)))] += 1
    st.hi('frames per stream', info['frames'])
    st.lo('frames per stream', info['frames'])
    br = info['bitrates']
    c[('stream.bitrate', 'CBR' if len(br) == 1 else ('VBR' if br else 'no audio frames'))] += 1
    if 'xing_frames' in info and info['xing_frames'] + 1 != info['frames']:
        c['stream.xing-frame-count-mismatch'] += 1
    del info['bitrates']
    return info


# --- RIFF / WAVE -----------------------------------------------------------------------------------

def parse_fmt(b):
    f = {'tag': u16(b, 0), 'ch': u16(b, 2), 'rate': u32(b, 4), 'byterate': u32(b, 8),
         'align': u16(b, 12), 'bits': u16(b, 14) if len(b) >= 16 else None,
         'cbsize': u16(b, 16) if len(b) >= 18 else None, 'fmtlen': len(b)}
    if f['tag'] == 0x11 and len(b) >= 20:
        f['spb'] = u16(b, 18)
    if f['tag'] == 2 and len(b) >= 22:
        f['spb'] = u16(b, 18)
        n = u16(b, 20)
        f['coefs'] = tuple(struct.unpack_from('<%dh' % (2 * n), b, 22)) if len(b) >= 22 + 4 * n else None
    if f['tag'] == 0x55 and len(b) >= 30:
        f['mp3'] = struct.unpack_from('<HIHHH', b, 18)
    if f['tag'] == 0xFFFE and len(b) >= 40:
        f['subformat'] = b[24:40].hex()
    return f


def fmt_key(f):
    k = f"tag=0x{f['tag']:04x} ch={f['ch']} rate={f['rate']} bits={f['bits']} align={f['align']}"
    if f['tag'] in (2, 0x11):
        k += f" spb={f.get('spb')}"
    return k


def read_riff(d, base, r):
    """Fill r with the RIFF/WAVE file at d[base:]. Returns (fmt, data_offset, data_size) or None."""
    riff_size = u32(d, base + 4)
    declared_end = base + 8 + riff_size
    r['riff_end'] = 'exact' if declared_end == len(d) else (
        'ends before the file' if declared_end < len(d) else 'ends past the file')
    p = base + 12
    chunks = []
    fmt = data = None
    fact = None
    while p + 8 <= len(d) and p < declared_end:
        cid = d[p:p + 4]
        if not all(32 <= x < 127 for x in cid):
            r['issues'].append(f'non-ASCII chunk id {cid!r} at {p - base}')
            break
        size = u32(d, p + 4)
        chunks.append(cid.decode('latin-1').strip())
        if size & 1:
            r['odd_chunks'] = r.get('odd_chunks', 0) + 1
        body = p + 8
        if cid == b'fmt ':
            fmt = parse_fmt(d[body:body + size])
        elif cid == b'data':
            data = (body, size)
        elif cid == b'fact':
            fact = u32(d, body)
        nxt = body + size + (size & 1)
        if body + size > len(d):
            r['issues'].append(f'chunk {cid.decode("latin-1")} runs {body + size - len(d)} bytes past the end of the file')
            break
        p = nxt
    r['chunks'] = ','.join(chunks)
    r['fact'] = fact
    r['after_riff'] = len(d) - min(p, len(d)) if p >= declared_end else 0
    if fmt is None or data is None:
        r['issues'].append('no fmt or no data chunk')
        return None
    r['fmt'] = fmt
    r['data_size'] = data[1]
    r['data_vs_file'] = len(d) - (data[0] + data[1])
    return fmt, data[0], data[1]


# --- IMA ADPCM -----------------------------------------------------------------------------------

def ima_decode_block(blk, nch, high_first, group):
    """Decode one block; returns [(second-to-last, last) sample] per channel. `group` is the
    number of data bytes per channel before switching channel (4 per Microsoft; 1 is the
    alternative tried)."""
    pred = []
    idx = []
    for ch in range(nch):
        pv = struct.unpack_from('<h', blk, 4 * ch)[0]
        pred.append(pv)
        idx.append(min(blk[4 * ch + 2], 88))
    data = blk[4 * nch:]
    per = len(data) // nch
    for ch in range(nch):
        # Gather this channel's bytes in stream order.
        if nch == 1:
            mine = data
        else:
            mine = bytearray()
            for g in range(0, per, group):
                o = (g // group) * group * nch + ch * group
                mine += data[o:o + group]
        pv, ix = pred[ch], idx[ch]
        before = pv
        for byte in mine:
            for n in ((byte >> 4, byte & 15) if high_first else (byte & 15, byte >> 4)):
                step = IMA_STEP[ix]
                diff = step >> 3
                if n & 4:
                    diff += step
                if n & 2:
                    diff += step >> 1
                if n & 1:
                    diff += step >> 2
                before = pv
                pv = pv - diff if n & 8 else pv + diff
                pv = -32768 if pv < -32768 else 32767 if pv > 32767 else pv
                ix += IMA_INDEX[n & 7]
                ix = 0 if ix < 0 else 88 if ix > 88 else ix
        pred[ch] = (before, pv)
    return pred


def check_ima(d, off, size, fmt, r, st):
    nch, align = fmt['ch'], fmt['align']
    c = st['c']
    want_spb = (align - 4 * nch) * 2 // nch + 1 if nch else 0
    c[('ima.spb-matches-formula', fmt.get('spb') == want_spb)] += 1
    c[('ima.bits', fmt['bits'])] += 1
    c[('ima.cbsize', fmt['cbsize'])] += 1
    if want_spb:
        exact = fmt['rate'] * align / want_spb
        c[('ima.byterate-minus-rate*align/spb', round(fmt['byterate'] - exact, 2))] += 1
    nfull, rem = divmod(size, align)
    c[('ima.partial-last-block', rem != 0)] += 1
    samples = nfull * want_spb + ((rem - 4 * nch) * 2 // nch + 1 if rem > 4 * nch else 0)
    r['samples'] = samples
    if r.get('fact') is not None:
        short = samples - r['fact']
        c[('ima.fact-vs-blocks', 'equal' if short == 0 else
           'fact smaller by less than one block' if 0 < short < want_spb else 'other')] += 1
        st['short'].append(short)
    nblocks = nfull + (1 if rem > 4 * nch else 0)
    bad_idx = bad_res = 0
    for b in range(nblocks):
        for ch in range(nch):
            q = off + b * align + 4 * ch
            if d[q + 2] > 88:
                bad_idx += 1
            if d[q + 3] != 0:
                bad_res += 1
    c['ima.blocks'] += nblocks
    c['ima.headers-step-index>88'] += bad_idx
    c['ima.headers-reserved-nonzero'] += bad_res
    if bad_idx or bad_res:
        r['issues'].append(f'IMA block headers: {bad_idx} step index > 88, {bad_res} reserved byte != 0')
    # Continuity test: the next block's header sample should be close to this block's last
    # decoded sample when decoding is right.
    variants = [(False, 4), (True, 4)] + ([(False, 1)] if nch == 2 else [])
    picks = list(range(0, max(nfull - 1, 0), max(1, (nfull - 1) // 24)))[:24]
    for hf, grp in variants:
        err = 0
        n = 0
        for b in picks:
            blk = d[off + b * align: off + (b + 1) * align]
            last = ima_decode_block(blk, nch, hf, grp)
            for ch in range(nch):
                nxt = struct.unpack_from('<h', d, off + (b + 1) * align + 4 * ch)[0]
                err += abs(last[ch][1] - nxt)
                n += 1
                if (hf, grp) == (False, 4):
                    # Baseline: how far apart two neighbouring decoded samples are anyway.
                    st['ima_cont']['(baseline) |last - second-to-last| sample, low nibble first, 4-byte groups'][0] += abs(last[ch][1] - last[ch][0])
                    st['ima_cont']['(baseline) |last - second-to-last| sample, low nibble first, 4-byte groups'][1] += 1
        if n:
            key = f"{'high' if hf else 'low'} nibble first, {grp}-byte channel groups"
            st['ima_cont'][key][0] += err
            st['ima_cont'][key][1] += n


# --- Classification ------------------------------------------------------------------------------

def classify(d, r):
    """Sets r['wrapper'], r['payload'], r['class'] and details. Returns per-file MPEG stats."""
    st = Mp3Stats()
    pst = Mp3Stats()
    ist = {'c': Counter(), 'ima_cont': defaultdict(lambda: [0, 0]), 'short': []}
    r['wrapper'] = 'none'
    base = 0
    pre = mp3_prefix_len(d)
    if pre:
        r['wrapper'] = 'mp3pad'
        r['prefix_len'] = pre
        r['prefix_sha'] = hashlib.sha1(d[:pre]).hexdigest()[:12]
        r['prefix_head'] = d[:4].hex()
        r['prefix_info'] = scan_mp3(d, 0, pre, pst)
        base = pre
    if d[base:base + 4] == b'RIFF' and d[base + 8:base + 12] == b'WAVE':
        got = read_riff(d, base, r)
        if got is None:
            r['payload'] = 'unknown'
        else:
            fmt, off, size = got
            tail = len(d) - (off + size)
            h = parse_header(d, off + size)
            if size == 0 and tail > 0 and (h is not None or d[off + size:off + size + 3] == b'ID3'):
                # An empty data chunk followed by an MPEG stream: the stub header.
                r['wrapper'] = 'riffstub'
                r['payload'] = 'mp3'
                r['stub_len'] = off
                r['stub_sha'] = hashlib.sha1(d[:off]).hexdigest()[:12]
                r['stub_fmt'] = fmt_key(fmt)
                r['stub_riff_size'] = u32(d, 4)
                info = scan_mp3(d, off, len(d), st)
                r['mp3'] = info
                r['duration'] = info['samples'] / info['rate'] if info['rate'] else 0
                r['issues'] += info['issues']
            else:
                r['payload'] = FORMAT_TAGS.get(fmt['tag'], f"tag-0x{fmt['tag']:04x}")
                if fmt['tag'] == 1:
                    ba = fmt['align'] or 1
                    r['duration'] = size / ba / fmt['rate'] if fmt['rate'] else 0
                    if fmt['align'] != fmt['ch'] * fmt['bits'] // 8:
                        r['issues'].append('PCM block align != channels * bits / 8')
                    if fmt['byterate'] != fmt['rate'] * fmt['align']:
                        r['issues'].append('PCM byte rate != rate * block align')
                    if size % ba:
                        r['issues'].append(f'PCM data size {size} not a multiple of block align {ba}')
                elif fmt['tag'] == 0x11:
                    check_ima(d, off, min(size, len(d) - off), fmt, r, ist)
                    r['duration'] = r['samples'] / fmt['rate']
                elif fmt['tag'] == 0x55:
                    info = scan_mp3(d, off, min(off + size, len(d)), st)
                    r['mp3'] = info
                    r['duration'] = info['samples'] / info['rate'] if info['rate'] else 0
                    r['issues'] += info['issues']
                else:
                    r['issues'].append(f"payload format tag 0x{fmt['tag']:04x} not analysed")
                if r['data_vs_file'] < 0:
                    r['issues'].append(f"data chunk claims {-r['data_vs_file']} bytes more than the file holds")
    elif pre:
        r['payload'] = 'unknown'
    elif d[:3] == b'ID3' or resync(d, 0, min(len(d), 4096), None) == 0:
        r['payload'] = 'mp3'
        info = scan_mp3(d, 0, len(d), st)
        r['mp3'] = info
        r['duration'] = info['samples'] / info['rate'] if info['rate'] else 0
        r['issues'] += info['issues']
    else:
        r['payload'] = 'unknown'
        r['head'] = d[:16].hex()
    r['class'] = f"{r['wrapper']}/{r['payload']}"
    r['payload_sha'] = hashlib.sha1(d[r.get('stub_len', base):]).hexdigest()[:16]
    return st, pst, ist


def analyze(task):
    name, group, path, off, size = task
    with open(path, 'rb') as f:
        f.seek(off)
        d = f.read(size) if size is not None else f.read()
    r = {'name': name, 'group': group, 'size': len(d), 'issues': [],
         'resref': os.path.splitext(os.path.basename(name.split(':')[-1]))[0].lower()}
    try:
        st, pst, ist = classify(d, r)
    except Exception as ex:  # a probe reports, it does not stop
        r['class'] = 'error'
        r['issues'].append(f'exception: {ex!r}')
        st, pst, ist = Mp3Stats(), Mp3Stats(), {'c': Counter(), 'ima_cont': {}, 'short': []}
    ist['ima_cont'] = dict(ist['ima_cont'])
    return r, st, pst, ist


# --- Inputs --------------------------------------------------------------------------------------

def gather(g):
    tasks = []
    for dp, dn, fn in os.walk(g.dir):
        for n in fn:
            if n.lower().endswith(('.wav', '.mp3')):
                p = os.path.join(dp, n)
                rel = os.path.relpath(p, g.dir)
                top = rel.split(os.sep)[0] if os.sep in rel else '(install root)'
                tasks.append((rel, top, p, 0, None))
    for ext in ('wav', 'mp3'):
        for e in g.every_entry(ext):
            cont = os.path.relpath(e.container, g.dir)
            if e.container.lower().startswith(os.path.join(g.dir, 'override').lower()):
                continue  # loose Override files are already in the walk above
            tasks.append((f'{cont}:{e.resref}.{e.ext}', cont, e.container, e.offset, e.size))
    return tasks


# --- Report --------------------------------------------------------------------------------------

# Counts printed even when zero, so that "never happens" is visible in the output.
MP3_FLAGS = [
    'frame.free-format', 'stream.id3v1', 'stream.id3v2', 'stream.id3v2-not-followed-by-a-frame',
    'stream.ape', 'stream.lyrics3', 'stream.junk', 'stream.trailing-bytes',
    'stream.truncated-last-frame', 'stream.xing-frame-count-mismatch',
    'stream.xing-byte-count-mismatch', 'granule.big_values>288',
    'granule.empty(part2_3_length=0)', 'granule.subblock_gain-nonzero',
    'joint.granule-block-types-differ(MS on)', 'joint.granule-block-types-differ(MS off)',
    'joint.lsf-intensity', 'res.begins-before-stream', 'res.overlaps-previous-frame',
    'res.overruns-frame',
]


def hist(counter, field, top=40):
    items = [(k[1], v) for k, v in counter.items() if isinstance(k, tuple) and k[0] == field]
    items.sort(key=lambda kv: (-kv[1], str(kv[0])))
    return ', '.join(f'{k}: {v}' for k, v in items[:top]) + (' ...' if len(items) > top else '')


def plain(counter, prefix):
    items = sorted((k, v) for k, v in counter.items() if isinstance(k, str) and k.startswith(prefix))
    return ', '.join(f'{k}: {v}' for k, v in items)


def dur_line(ds):
    if not ds:
        return 'n/a'
    return (f'n {len(ds)}, min {min(ds):.2f}s, median {statistics.median(ds):.2f}s, '
            f'max {max(ds):.2f}s, total {sum(ds) / 3600:.2f}h')


def print_mp3(st, indent='  '):
    c = st.c
    frames = sum(v for k, v in c.items() if isinstance(k, tuple) and k[0] == 'version')
    print(f'{indent}frames: {frames}')
    for f in ('version', 'layer', 'rate', 'bitrate', 'bitrate.tagframe', 'mode', 'mode_ext', 'crc',
              'padding', 'frame-bytes', 'private', 'copyright', 'original', 'emphasis'):
        print(f'{indent}{f}: {hist(c, f) or "-"}')
    for f in ('stream.tag', 'stream.tag-flags', 'stream.lame-tag', 'stream.lame-string',
              'stream.lame-delay', 'stream.id3v2-version', 'stream.bitrate', 'stream.modes'):
        print(f'{indent}{f}: {hist(c, f) or "-"}')
    print(f'{indent}counts: ' + ', '.join(f'{k} {c[k]}' for k in MP3_FLAGS))
    print(f'{indent}block types (granule x channel): {hist(c, "block") or "-"}')
    print(f'{indent}huffman tables used (non-empty big_values regions): {hist(c, "huffman-table", 40) or "-"}')
    print(f'{indent}count1 tables: {hist(c, "count1-table") or "-"}')
    print(f'{indent}scfsi (per frame x channel, MPEG-1): {hist(c, "scfsi") or "-"}')
    print(f'{indent}preflag: {hist(c, "preflag") or "-"}   scalefac_scale: {hist(c, "scalefac_scale") or "-"}')
    print(f'{indent}maxima: {", ".join(f"{k} {v}" for k, v in sorted(st.mx.items()))}')
    print(f'{indent}minima: {", ".join(f"{k} {v}" for k, v in sorted(st.mn.items()))}')


def name_prefix(resref):
    """The leading letters of a resref, plus '_' when an underscore follows them: 'p_' for
    p_carth_atk1, 'ba' for ba02cs001, '(digits)' for 01b."""
    n = 0
    while n < len(resref) and resref[n].isalpha():
        n += 1
    if n == 0:
        return '(digits)'
    return resref[:n] + ('_' if resref[n:n + 1] == '_' else '')


def read_2da(d):
    """Rows of a binary 2DA (V2.b) as dicts."""
    if d[:9] != b'2DA V2.b\n':
        raise ValueError('not a 2DA V2.b')
    p = 9
    e = d.index(b'\0', p)
    cols = d[p:e].decode('latin-1').split('\t')[:-1]
    p = e + 1
    n = u32(d, p)
    p += 4
    for _ in range(n):
        p = d.index(b'\t', p) + 1
    offs = struct.unpack_from('<%dH' % (n * len(cols)), d, p)
    p += 2 * n * len(cols) + 2
    rows = []
    for r in range(n):
        row = {}
        for c, col in enumerate(cols):
            o = p + offs[r * len(cols) + c]
            row[col] = d[o:d.index(b'\0', o)].decode('latin-1').lower()
        rows.append(row)
    return rows


def refs(g):
    """Where the audio pools are referenced: dialog.tlk sound resrefs and the two music 2DAs."""
    pools = defaultdict(set)
    root = os.path.join(g.dir, 'streamwaves')
    for dp, dn, fn in os.walk(root):
        for n in fn:
            pools[os.path.splitext(n)[0].lower()].add('streamwaves/' + ('top' if dp == root else 'a/b'))
    for sub in ('streamsounds', 'streammusic'):
        for n in os.listdir(os.path.join(g.dir, sub)):
            pools[os.path.splitext(n)[0].lower()].add(sub)
    for e in g.entries('wav'):
        pools[e.resref].add('wav resource')
    d = open(os.path.join(g.dir, 'dialog.tlk'), 'rb').read()
    count = u32(d, 12)
    tlk = []
    for i in range(count):
        o = 20 + 40 * i
        snd = d[o + 4:o + 20].split(b'\0')[0].decode('latin-1').lower()
        if u32(d, o) & 2 and snd:
            tlk.append(snd)
    print(f'dialog.tlk: {count} entries, {len(tlk)} with a sound resref ({len(set(tlk))} distinct)')
    c = Counter('+'.join(sorted(pools.get(r, {'(nowhere)'}))) for r in set(tlk))
    for k, v in c.most_common():
        print(f'  resolves to {k}: {v}')
    for pool in ('streamwaves/top', 'streamwaves/a/b', 'streamsounds', 'streammusic', 'wav resource'):
        names = [n for n, ps in pools.items() if pool in ps]
        print(f'  {pool}: {len(names)} names, {sum(1 for n in names if n in set(tlk))} named by dialog.tlk')
    # Soundsets: .ssf files are lists of strrefs; the sound is the TLK entry's sound resref.
    tlk_sound = {}
    for i in range(count):
        o = 20 + 40 * i
        if u32(d, o) & 2:
            tlk_sound[i] = d[o + 4:o + 20].split(b'\0')[0].decode('latin-1').lower()
    ssf_names = set()
    ssfs = g.entries('ssf')
    for e in ssfs:
        b = kres.read_entry(e)
        off = u32(b, 8)
        for j in range(off, len(b) - 3, 4):
            s = tlk_sound.get(u32(b, j))
            if s:
                ssf_names.add(s)
    c = Counter('+'.join(sorted(pools.get(n, {'(nowhere)'}))) for n in ssf_names)
    print(f'.ssf soundsets: {len(ssfs)} files, {len(ssf_names)} distinct sound resrefs through '
          f'dialog.tlk: ' + ', '.join(f'{k} {v}' for k, v in c.most_common()))
    for table, columns in (('ambientmusic', ('resource', 'stinger1', 'stinger2', 'stinger3')),
                           ('ambientsound', ('resource',)), ('loadscreens', ('musicresref',))):
        rows = read_2da(g.get(table, '2da'))
        names = [row[col] for row in rows for col in columns if row.get(col) and row[col] != '****']
        c = Counter('+'.join(sorted(pools.get(n, {'(nowhere)'}))) for n in set(names))
        print(f'{table}.2da: {len(rows)} rows, {len(set(names))} distinct names: '
              + ', '.join(f'{k} {v}' for k, v in c.most_common()))
        missing = sorted(n for n in set(names) if n not in pools)
        if missing:
            print(f'  not found anywhere: {", ".join(missing)}')
    # GFF files store a ResRef as a length byte and that many characters. Scanning the raw bytes
    # for that shape (no GFF parser needed) and keeping only names of existing audio finds which
    # resource types point at which pool; a stray match could only overcount by a name or two.
    pool_names = defaultdict(set)
    for n, ps in pools.items():
        for p in ps:
            pool_names[p].add(n)
    for ext in ('dlg', 'uts', 'git', 'utp', 'utc'):
        found = set()
        es = g.entries(ext)
        for e in es:
            b = kres.read_entry(e)
            i = 0
            while True:
                m = RESREF_RE.search(b, i)
                if not m:
                    break
                ln = b[m.start()]
                if ln <= len(m.group(1)):
                    found.add(m.group(1)[:ln].decode('latin-1').lower())
                i = m.start() + 1
        line = ', '.join(f'{p} {len(found & pool_names[p])} of {len(pool_names[p])}'
                         for p in ('streamwaves/a/b', 'streamwaves/top', 'streamsounds', 'streammusic', 'wav resource'))
        print(f'.{ext} ({len(es)} files) name audio as ResRefs: {line}')
        if ext == 'dlg':
            nums = sorted(n for n in found & pool_names['streammusic'])
            print(f'  streammusic names in .dlg: {", ".join(nums)}')


RESREF_RE = re.compile(rb'[\x01-\x10]([0-9A-Za-z_]{1,16})')


def main(argv):
    if '--refs' in argv:
        refs(kres.Game())
        return 0
    jobs = int(argv[argv.index('--jobs') + 1]) if '--jobs' in argv else os.cpu_count()
    nex = int(argv[argv.index('--examples') + 1]) if '--examples' in argv else 3
    want = argv[argv.index('--list') + 1] if '--list' in argv else None
    g = kres.Game()
    tasks = gather(g)
    results = []
    by_class = defaultdict(Mp3Stats)
    by_class_group = defaultdict(Mp3Stats)
    prefix_st = Mp3Stats()
    ima_c = Counter()
    ima_cont = defaultdict(lambda: [0, 0])
    ima_short = []
    with Pool(jobs) as pool:
        for r, st, pst, ist in pool.imap_unordered(analyze, tasks, chunksize=16):
            results.append(r)
            by_class[r['class']].merge(st)
            by_class_group[(r['class'], r['group'])].merge(st)
            prefix_st.merge(pst)
            ima_c.update(ist['c'])
            ima_short += ist['short']
            for k, (e, n) in ist['ima_cont'].items():
                ima_cont[k][0] += e
                ima_cont[k][1] += n
    results.sort(key=lambda r: r['name'].lower())

    if want:
        for r in results:
            if r['class'] == want:
                print(r['name'])
        return 0

    print('== Inputs')
    groups = Counter(r['group'] for r in results)
    print(f'{len(results)} inputs: ' + ', '.join(f'{k} {v}' for k, v in sorted(groups.items())))

    print('\n== Classes (wrapper/payload)')
    classes = defaultdict(list)
    for r in results:
        classes[r['class']].append(r)
    for cl, rs in sorted(classes.items(), key=lambda kv: -len(kv[1])):
        per = Counter(r['group'] for r in rs)
        print(f'{cl}: {len(rs)}   [' + ', '.join(f'{k} {v}' for k, v in sorted(per.items())) + ']')
        print('    e.g. ' + ', '.join(r['name'] for r in rs[:nex]))

    print('\n== Per class details')
    for cl, rs in sorted(classes.items(), key=lambda kv: -len(kv[1])):
        print(f'\n-- {cl} ({len(rs)})')
        print('  sizes: min %d, max %d bytes' % (min(r['size'] for r in rs), max(r['size'] for r in rs)))
        if any('prefix_len' in r for r in rs):
            print('  mp3pad prefix length:', dict(Counter(r.get('prefix_len') for r in rs)))
            print('  mp3pad prefix distinct byte strings (sha1/12):', dict(Counter(r.get('prefix_sha') for r in rs)))
            print('  mp3pad first 4 bytes:', dict(Counter(r.get('prefix_head') for r in rs)))
            print('  mp3pad frames in prefix:', dict(Counter(r['prefix_info']['frames'] for r in rs)))
        if any('stub_len' in r for r in rs):
            print('  riffstub header length (offset of the MPEG stream):', dict(Counter(r.get('stub_len') for r in rs)))
            print('  riffstub distinct header byte strings (sha1/12):', dict(Counter(r.get('stub_sha') for r in rs)))
            print('  riffstub RIFF size field:', dict(Counter(r.get('stub_riff_size') for r in rs)))
            print('  riffstub fmt:', dict(Counter(r.get('stub_fmt') for r in rs)))
        if any('fmt' in r for r in rs):
            print('  chunk lists:', dict(Counter(r.get('chunks') for r in rs)))
            if 'stub_len' not in rs[0]:
                fk = Counter(fmt_key(r['fmt']) for r in rs if 'fmt' in r)
                for k, v in fk.most_common():
                    per = Counter(r['group'] for r in rs if 'fmt' in r and fmt_key(r['fmt']) == k)
                    print(f'  fmt {k}: {v}   [' + ', '.join(f'{a} {b}' for a, b in sorted(per.items())) + ']')
                print('  fmt chunk length / cbSize:', dict(Counter((r['fmt']['fmtlen'], r['fmt']['cbsize']) for r in rs if 'fmt' in r)))
                print('  byte rate:', dict(Counter(r['fmt']['byterate'] for r in rs if 'fmt' in r)))
                print('  fact chunk value:', dict(Counter('none' if r.get('fact') is None else ('0' if r['fact'] == 0 else 'nonzero') for r in rs)))
                print('  data size odd:', sum(1 for r in rs if r.get('data_size', 0) & 1),
                      ' data size 0:', sum(1 for r in rs if r.get('data_size') == 0))
            print('  chunks with an odd size (followed by a pad byte):', sum(r.get('odd_chunks', 0) for r in rs))
            print('  RIFF size field (+8) vs file length:', dict(Counter(r.get('riff_end') for r in rs)))
            print('  bytes after the data chunk to EOF (top 8):', dict(Counter(r.get('data_vs_file', 0) for r in rs).most_common(8)))
        if any('mp3' in r for r in rs):
            sub = defaultdict(Counter)
            for r in rs:
                if 'mp3' in r:
                    sub[r['group']][(r['mp3']['rate'], r['mp3']['nch'])] += 1
            print('  MPEG (rate, channels) per group:')
            for k, v in sorted(sub.items()):
                print(f'    {k}: ' + ', '.join(f'{a}: {b}' for a, b in v.most_common()))
            print_mp3(by_class[cl])
            print('  per group:')
            for grp in sorted({r['group'] for r in rs if 'mp3' in r}):
                c = by_class_group[(cl, grp)].c
                print(f'    {grp}: bitrate {hist(c, "bitrate")}; mode {hist(c, "mode")}; '
                      f'mode_ext {hist(c, "mode_ext") or "-"}; blocks {hist(c, "block")}; '
                      f'scfsi {hist(c, "scfsi")}; preflag {hist(c, "preflag")}; '
                      f'scalefac_scale {hist(c, "scalefac_scale")}; '
                      f'subblock_gain-nonzero {c["granule.subblock_gain-nonzero"]}; '
                      f'tag {hist(c, "stream.tag")}; id3v2 {c["stream.id3v2"]}; id3v1 {c["stream.id3v1"]}; '
                      f'frame bytes {hist(c, "frame-bytes")}; '
                      f'huffman tables never used: '
                      f'{sorted(set(range(32)) - {k[1] for k in c if isinstance(k, tuple) and k[0] == "huffman-table"})}')
        print('  duration per group:')
        for grp in sorted({r['group'] for r in rs}):
            ds = [r['duration'] for r in rs if r['group'] == grp and r.get('duration') is not None]
            print(f'    {grp}: {dur_line(ds)}')
        bad = [r for r in rs if r['issues']]
        print(f'  inputs with issues: {len(bad)}')
        issues = Counter(i.split(':')[0] if i.startswith('frame') else i for r in bad for i in r['issues'])
        for i, n in issues.most_common(12):
            print(f'    {n}x {i}')
        for r in bad[:nex]:
            print(f'    e.g. {r["name"]}: {r["issues"][:3]}')

    if ima_c:
        print('\n== IMA ADPCM (all IMA inputs together)')
        for k in sorted({k[0] for k in ima_c if isinstance(k, tuple)}):
            print(f'  {k}: {hist(ima_c, k)}')
        print(f'  {plain(ima_c, "ima.")}')
        if ima_short:
            print(f'  blocks*samples_per_block - fact: min {min(ima_short)}, max {max(ima_short)}')
        print('  continuity test (mean |last decoded sample of block n - header sample of block n+1|):')
        for k, (e, n) in sorted(ima_cont.items(), key=lambda kv: kv[1][0] / max(kv[1][1], 1)):
            print(f'    {k}: {e / max(n, 1):.1f} over {n} samples')

    print('\n== The MPEG frames inside mp3pad prefixes (all files together)')
    print_mp3(prefix_st)

    print('\n== Names')
    sw = [r for r in results if r['group'] == 'streamwaves']
    nested = [r for r in sw if r['name'].count(os.sep) == 3]
    for grp in sorted(groups):
        pc = Counter(name_prefix(r['resref']) for r in results if r['group'] == grp
                     and not (grp == 'streamwaves' and r['name'].count(os.sep) == 3))
        print(f'  {grp}{" (top level only)" if grp == "streamwaves" else ""}: '
              + ', '.join(f'{k} {v}' for k, v in pc.most_common(25)))
    ok = sum(1 for r in nested if r['resref'][0] == 'n'
             and r['name'].split(os.sep)[1].lower() == r['resref'][1:6]
             and r['name'].split(os.sep)[2].lower() == r['resref'][6:12])
    print(f'  streamwaves: {len(sw) - len(nested)} at top level, {len(nested)} in <a>/<b>/ subdirectories, '
          f'{ok} of which are named n + a (5 chars) + b (6 chars) + ...; '
          f'resref lengths there {dict(Counter(len(r["resref"]) for r in nested))}')

    print('\n== Same resref in more than one input')
    byname = defaultdict(list)
    for r in results:
        byname[r['resref']].append(r)
    combos = Counter()
    differ = []
    for n, rs in byname.items():
        if len(rs) > 1:
            same = len({r['payload_sha'] for r in rs}) == 1
            combos[(' + '.join(sorted(r['group'] for r in rs)), 'payload identical' if same else 'payload differs')] += 1
            if not same:
                differ.append(n)
    print('  (payload = the bytes after any mp3pad prefix, so a streamsounds file can equal a BIF WAV)')
    for (k, s2), v in sorted(combos.items(), key=lambda kv: -kv[1]):
        print(f'  {k}: {v} ({s2})')
    if differ:
        print('  differing: ' + ', '.join(sorted(differ)))

    print('\n== Failures')
    fails = [r for r in results if r['class'] == 'error' or r.get('payload') == 'unknown' or r['issues']]
    print(f'unclassified, crashed or with issues: {len(fails)}')
    for r in fails[:20]:
        print(f'  {r["name"]}: {r.get("head", "")} {r["issues"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
