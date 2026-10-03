"""Check every LIP (lip-sync) resource in the install against what docs/formats/lip.md says.

    python kotor/tools/py/lip_probe.py                 check every LIP and its pairing
    python kotor/tools/py/lip_probe.py talk [MODEL...] print the 16 mouth poses of heads' "talk"
                                                       animation (the shape-id evidence in lip.md)

For each LIP copy (Game.every_entry('lip')): magic "LIP V1.0", size == 16 + 5 * key count, times
non-decreasing and inside [0, length], shape ids 0..15. Then pairs each LIP with its voice-over
in streamwaves/ by resref (and the path rule streamwaves/<r[1:6]>/<r[6:12]>/<r>.wav), compares the
LIP length with the MP3-in-WAV duration, and (when gffpy is present) finds which DLG field names
each LIP and whether the LIP sits in the lips/ container of the DLG's module.
Exit status 1 if any structural check fails.
"""

import os
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kres  # noqa: E402

SHAPES = ['EE', 'EH', 'SCHWA', 'AH', 'OH', 'OOH', 'Y', 'S/TS', 'F/V', 'N/NG', 'TH', 'M/P/B',
          'T/D', 'J/SH', 'L/R', 'K/G']


def parse_lip(d):
    """(length, [(time, shape)]) or raise ValueError."""
    if len(d) < 16:
        raise ValueError('shorter than the 16-byte header')
    if d[:8] != b'LIP V1.0':
        raise ValueError(f'bad magic {d[:8]!r}')
    length, count = struct.unpack_from('<fI', d, 8)
    if len(d) != 16 + 5 * count:
        raise ValueError(f'size {len(d)} != 16 + 5 * {count}')
    keys = [struct.unpack_from('<fB', d, 16 + 5 * i) for i in range(count)]
    return length, keys


# MPEG audio, enough to time the MP3 frames the game wraps in WAV files.
_BITRATES = {  # kbit/s by index, layer III; True = MPEG-1, False = MPEG-2/2.5
    True: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
    False: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
}
_RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def mp3_duration(d, start):
    """Seconds of MPEG layer III audio in d[start:], skipping an ID3v2 tag and a Xing/Info frame."""
    i = start
    if d[i:i + 3] == b'ID3':
        size = 0
        for b in d[i + 6:i + 10]:
            size = (size << 7) | (b & 0x7F)
        i += 10 + size
    samples = 0
    rate = None
    first = True
    while i + 4 <= len(d):
        h = struct.unpack_from('>I', d, i)[0]
        if (h >> 21) & 0x7FF != 0x7FF:
            i += 1
            continue
        ver = (h >> 19) & 3
        layer = (h >> 17) & 3
        bri = (h >> 12) & 15
        sri = (h >> 10) & 3
        pad = (h >> 9) & 1
        if ver == 1 or layer != 1 or bri in (0, 15) or sri == 3:
            i += 1
            continue
        mpeg1 = ver == 3
        rate = _RATES[ver][sri]
        br = _BITRATES[mpeg1][bri] * 1000
        flen = (144 if mpeg1 else 72) * br // rate + pad
        if first and (b'Xing' in d[i:i + flen] or b'Info' in d[i:i + flen]):
            first = False
            i += flen
            continue
        first = False
        samples += 1152 if mpeg1 else 576
        i += flen
    return samples / rate if rate else None


def wav_duration(path):
    with open(path, 'rb') as f:
        d = f.read()
    if d[:4] != b'RIFF' or d[8:12] != b'WAVE':
        return None, 'not RIFF/WAVE'
    i = 12
    fmt = None
    while i + 8 <= len(d):
        cid = d[i:i + 4]
        size = struct.unpack_from('<I', d, i + 4)[0]
        if cid == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', d, i + 8)
        elif cid == b'data':
            tag, ch, rate, _bps, _align, bits = fmt
            if size == 0 or size > len(d) - i - 8:
                # The header claims PCM but the payload is MP3 frames running to end of file.
                return mp3_duration(d, i + 8), 'mp3-in-wav'
            if tag == 1:
                return size / (rate * ch * bits / 8), 'pcm'
            return None, f'format {tag}'
        i += 8 + size + (size & 1)
    return None, 'no data chunk'


def streamwaves(game_dir):
    """resref -> [path] for every .wav under streamwaves/."""
    out = defaultdict(list)
    root = os.path.join(game_dir, 'streamwaves')
    for dp, _dn, fn in os.walk(root):
        for n in fn:
            stem, _, ext = n.rpartition('.')
            if ext.lower() == 'wav':
                out[stem.lower()].append(os.path.join(dp, n))
    return out


def talk_poses(data, anim='talk'):
    """For a binary MDL: (length, {node: [(time, value)]}) of its `anim` animation, orientation
    controllers only (type 20), as x y z of the quaternion. Just enough MDL for lip.md's evidence;
    the layout is the public one (xoreos-docs specs/kotor_mdl.html)."""
    base = 12

    def u32(o):
        return struct.unpack_from('<I', data, base + o)[0]

    def name32(o):
        return data[base + o:base + o + 32].split(b'\0')[0].decode('latin-1')

    anim_off, anim_cnt = u32(80 + 8), u32(80 + 12)
    names_off, names_cnt = u32(80 + 88 + 16), u32(80 + 88 + 20)
    names = [data[base + u32(names_off + 4 * i):].split(b'\0')[0].decode('latin-1')
             for i in range(names_cnt)]
    for a in (u32(anim_off + 4 * i) for i in range(anim_cnt)):
        if name32(a + 8).lower() != anim:
            continue
        length = struct.unpack_from('<f', data, base + a + 80)[0]
        out = {}
        stack = [u32(a + 40)]
        while stack:
            node = stack.pop()
            stack.extend(u32(u32(node + 44) + 4 * i) for i in range(u32(node + 48)))
            nidx = struct.unpack_from('<H', data, base + node + 4)[0]
            ctl, n_ctl, dat = u32(node + 56), u32(node + 60), u32(node + 68)
            for c in range(n_ctl):
                ctype, _u, rows, ti, di, cols = struct.unpack_from('<IHHHHB', data,
                                                                     base + ctl + 16 * c)
                if ctype != 20:
                    continue
                keys = []
                for r in range(rows):
                    t = struct.unpack_from('<f', data, base + dat + 4 * (ti + r))[0]
                    if cols == 2:
                        # Compressed quaternion: 11, 11 and 10 bits of x, y, z.
                        v = struct.unpack_from('<I', data, base + dat + 4 * (di + r))[0]
                        q = ((v & 0x7FF) / 1023 - 1, ((v >> 11) & 0x7FF) / 1023 - 1,
                             (v >> 22) / 511 - 1)
                    else:
                        q = struct.unpack_from('<3f', data, base + dat + 4 * (di + 4 * r))
                    keys.append((t, q))
                out[names[nidx].lower()] = keys
        return length, out
    return None, {}


def show_talk(models):
    g = kres.Game()
    for m in models:
        data = g.get(m, 'mdl')
        if data is None:
            print(f'{m}: no MDL')
            continue
        length, nodes = talk_poses(data)
        if length is None:
            print(f'{m}: no talk animation')
            continue
        print(f'{m}: talk length {length:.3f}s')
        for node in ('f_jaw_g', 'f_um_g', 'f_lmc_g'):
            keys = nodes.get(node)
            if not keys:
                continue
            note = ' (x < 0 opens the jaw)' if node == 'f_jaw_g' else ''
            print(f'  {node} orientation key, quaternion x y z{note}, by shape:')
            for t, q in keys:
                s = round(t * 30)
                label = SHAPES[s] if s < 16 and abs(t * 30 - s) < 0.05 else '?'
                print(f'    t={t:.3f} shape {s:2} {label:6} x={q[0]:+.3f} y={q[1]:+.3f} z={q[2]:+.3f}')


def check_dlg(g, by_resref):
    """Which DLG fields name each LIP, and is the LIP in its DLG's module container."""
    try:
        import gffpy
    except ImportError:
        print('DLG pairing: skipped (gffpy not available)')
        return
    lip_conts = {r: {os.path.basename(e.container).lower() for e, _ in v}
                 for r, v in by_resref.items()}
    referenced = defaultdict(set)
    where = Counter()
    odd = []
    for e in g.every_entry('dlg'):
        base = os.path.basename(e.container).lower()
        module = base[:-len('_s.rim')] if base.endswith('_s.rim') else None
        try:
            root = gffpy.read(kres.read_entry(e))
        except Exception:
            continue
        for lst in ('EntryList', 'ReplyList'):
            for node in root.get(lst, []):
                for field in ('VO_ResRef', 'Sound'):
                    r = (node.get(field, '') or '').lower()
                    if r not in lip_conts:
                        continue
                    referenced[r].add(field)
                    if module is None:
                        inloc = 'localization.mod' in lip_conts[r]
                        where[f'{field} in a DLG outside modules ({base}), LIP '
                              + ('in' if inloc else 'not in') + ' lips/localization.mod'] += 1
                    elif module + '_loc.mod' in lip_conts[r]:
                        where[f'{field} in a module DLG, LIP in lips/<module>_loc.mod'] += 1
                    elif 'localization.mod' in lip_conts[r]:
                        where[f'{field} in a module DLG, LIP only in lips/localization.mod'] += 1
                    else:
                        where[f'{field} in a module DLG, LIP in another module'] += 1
                        odd.append(f'{e.resref}.dlg ({module}) -> {r} in {sorted(lip_conts[r])}')
    kinds = Counter('+'.join(sorted(v)) for v in referenced.values())
    print(f'LIP resrefs named by a DLG node: {len(referenced)} of {len(lip_conts)} {dict(kinds)}')
    for k, n in sorted(where.items()):
        print(f'  {n:6}  {k}')
    for o in odd[:5]:
        print('   ', o)


def main(argv):
    if argv and argv[0] == 'talk':
        show_talk(argv[1:] or ['s_male02', 's_female03', 'p_bastilah', 'p_missionh'])
        return 0
    g = kres.Game()
    es = g.every_entry('lip')
    fails = []
    shapes = Counter()
    first_shape = Counter()
    last_shape = Counter()
    counts = Counter()
    strict = 0           # files whose times strictly increase
    repeats = Counter()  # repeated times: same shape or not
    first_at_zero = 0
    last_at_length = 0
    ms_grid = 0          # every time a whole millisecond (to float precision)
    gaps = []
    containers = Counter()
    by_resref = defaultdict(list)
    lengths = {}
    for e in es:
        d = kres.read_entry(e)
        name = f'{e.resref}.lip in {os.path.relpath(e.container, g.dir)}'
        try:
            length, keys = parse_lip(d)
        except ValueError as ex:
            fails.append(f'{name}: {ex}')
            continue
        containers[os.path.basename(e.container).lower()] += 1
        by_resref[e.resref].append((e, d))
        lengths[e.resref] = length
        counts[len(keys)] += 1
        times = [t for t, _ in keys]
        errs = []
        if length != length or length < 0:
            errs.append(f'bad length {length}')
        if any(b < a for a, b in zip(times, times[1:])):
            errs.append('times not sorted')
        if any(t < 0 or t > length + 1e-6 for t in times):
            errs.append(f'time outside [0, {length}]')
        bad = [s for _, s in keys if s > 15]
        if bad:
            errs.append(f'shape ids out of range {sorted(set(bad))}')
        if errs:
            fails.append(f'{name}: ' + '; '.join(errs))
        if all(b > a for a, b in zip(times, times[1:])):
            strict += 1
        for (ta, sa), (tb, sb) in zip(keys, keys[1:]):
            # Same millisecond, sometimes one float step apart: a repeated key.
            if tb - ta < 0.0005:
                repeats[('exactly equal, ' if ta == tb else 'one float step apart, ')
                        + ('same shape' if sa == sb else 'different shape')] += 1
            else:
                gaps.append(tb - ta)
        if keys:
            first_shape[keys[0][1]] += 1
            last_shape[keys[-1][1]] += 1
            if keys[0][0] == 0:
                first_at_zero += 1
            if abs(keys[-1][0] - length) < 1e-6:
                last_at_length += 1
        if all(abs(t * 1000 - round(t * 1000)) <= max(1e-3, t * 1e-4) for t in times):
            ms_grid += 1
        for _, s in keys:
            shapes[s] += 1

    print(f'LIP copies: {len(es)}, unique resrefs: {len(by_resref)}, failures: {len(fails)}')
    for f in fails[:50]:
        print('  FAIL', f)
    print(f'containers: {len(containers)} (lips/*.mod); localization.mod holds '
          f'{containers["localization.mod"]}')
    print(f'key counts: min {min(counts)}, max {max(counts)}')
    print(f'files whose times strictly increase: {strict}; repeated keys: {dict(repeats)}')
    gaps.sort()
    print(f'gap between distinct key times: min {gaps[0]:.4f}s, median {gaps[len(gaps) // 2]:.4f}s, '
          f'max {gaps[-1]:.3f}s')
    print(f'first key at t=0: {first_at_zero}; last key at t=length: {last_at_length}')
    print(f'all times whole milliseconds: {ms_grid}')
    print('shape histogram:')
    total = sum(shapes.values())
    for s in range(16):
        print(f'  {s:2} {SHAPES[s]:6} {shapes[s]:7} {100 * shapes[s] / total:5.1f}%'
              f'  first key {first_shape[s]:5}  last key {last_shape[s]:5}')
    diff_dupes = sum(1 for v in by_resref.values() if len({d for _, d in v}) > 1)
    multi = sum(1 for v in by_resref.values() if len(v) > 1)
    print(f'resrefs in more than one container: {multi}; of those with differing bytes: {diff_dupes}')

    # Pair with voice-over.
    waves = streamwaves(g.dir)
    sounds = {e.resref for e in g.every_entry('wav')}
    have = [r for r in by_resref if r in waves]
    only_res = [r for r in by_resref if r not in waves and r in sounds]
    none = [r for r in by_resref if r not in waves and r not in sounds]
    print(f'LIP resrefs with a streamwaves/ WAV of the same name: {len(have)}; '
          f'only a WAV resource (BIF/RIM): {len(only_res)}; no WAV anywhere: {len(none)}')
    if none:
        print('  e.g.', ', '.join(sorted(none)[:10]))
    print(f'streamwaves/ WAVs without a LIP: {len([r for r in waves if r not in by_resref])} '
          f'of {len(waves)}')
    rule = Counter()
    root = os.path.join(g.dir, 'streamwaves')
    for r, paths in waves.items():
        for p in paths:
            parts = os.path.relpath(p, root).lower().split(os.sep)
            if len(parts) == 1:
                rule['streamwaves/<r>.wav'] += 1
            elif len(parts) == 3 and parts[0] == r[1:6] and parts[1] == r[6:12]:
                rule['streamwaves/<r[1:6]>/<r[6:12]>/<r>.wav'] += 1
            else:
                rule['other path'] += 1
    print('streamwaves/ path rule over every WAV:', dict(rule))
    deltas = []
    kinds = Counter()
    for r in have:
        dur, kind = wav_duration(waves[r][0])
        kinds[kind] += 1
        if dur is not None:
            deltas.append((lengths[r] - dur, r, lengths[r], dur))
    deltas.sort()
    if deltas:
        n = len(deltas)
        absd = sorted(abs(x[0]) for x in deltas)
        print(f'LIP length - WAV duration over {n} pairs ({dict(kinds)}): '
              f'median |d| {absd[n // 2]:.3f}s, 99% {absd[int(n * 0.99)]:.3f}s, '
              f'max {absd[-1]:.3f}s; LIP shorter in {sum(1 for x in deltas if x[0] < 0)}')
    check_dlg(g, by_resref)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
