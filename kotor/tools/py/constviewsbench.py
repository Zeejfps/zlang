"""Compare an earlier MP3 decoder with the working tree, using the current ctxc for both.

    python3 kotor/tools/py/constviewsbench.py --before 5ae1c76

Requires ffmpeg with libmp3lame. Generates deterministic synthetic stereo audio, checks all
decoded PCM bytes for equality, and measures the long IMDCT and complete MP3 decoding at -O2.
One warmup, then alternating run order; reports individual wall times and medians. Timing
includes process startup (and one input read for decode), but excludes compilation and PCM
verification. Sources, emitted C, assembly, executables and JSON results stay in kotor/out.
This is a performance experiment, not validation against the purchased game's audio corpus.
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'ctxlang' / 'tools'))
import toolchain as tc


KERNEL = '''
fn main { mut io: Io } {
    let mut x: [18]f32
    let mut prev: [18]f32
    let mut out: [18]f32
    let mut checksum: f64 = 0.0
    let mut i: usize = 0
    while i < ITERATIONS {
        x[i % 18] = @as(f32, i % 1024) / 1024.0
        mp3::transform_long{ x = x[..], block_type = @as(u32, (i % 2) * 3), prev = prev[..], out = out[..] }
        checksum = checksum + @as(f64, out[i % 18])
        i = i + 1
    }
    io::println_f64{ &io, n = checksum }
}
'''

DECODE = '''
fn main { mut io: Io, mut fs: Fs, args: Args } -> i32 {
    let mut memory: [1048576]u8
    let mut heap = arena::new{ buf = memory[..] }
    let bytes = try! fs::read_all{ &fs, &heap, realloc = arena::alloc, path = args[0] }
    let mut d: mp3::Decoder
    let mut pcm: [2304]i16
    let mut checksum: i64 = 0
    let mut frames: u64 = 0
    let mut repeat = 0
    while repeat < REPEATS {
        mp3::reset{ d = &d }
        let mut pos: usize = 0
        while pos < bytes.len {
            let h = mp3::read_header{ b = bytes[pos..] } ifnull { return 2 }
            let n = try! mp3::decode{ d = &d, f = bytes[pos..pos + h.size], into = pcm[..] }
            frames = frames + n
            if n > 0 { checksum = checksum + pcm[0] }
            VERIFY_PCM
            pos = pos + h.size
        }
        repeat = repeat + 1
    }
    io::println_i64{ &io, n = checksum }
    io::println_u64{ &io, n = frames }
    return 0
}
'''

VERIFY_PCM = '''
            if n > 0 {
                let data = @slice(@cast(*u8, &pcm[0]), @as(usize, n) * h.channels * 2)
                io::write{ &io, to = io::Stream::out, bytes = data }
            }
'''


def build(out, label, decoder, main, kind):
    folder = out / label / kind
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'mp3.ctx').write_text(decoder)
    (folder / 'mp3_tab.ctx').write_text((ROOT / 'kotor/lib/audio/mp3_tab.ctx').read_text())
    (folder / 'main.ctx').write_text(main)
    emitted = folder / 'program.c'
    code, error = tc.ctxc_build(tc.native_ctxc(), str(emitted),
                              ['mp3.ctx', 'mp3_tab.ctx', 'main.ctx'], cwd=str(folder))
    if code:
        raise RuntimeError(error)
    cc, env = tc.compiler()
    flags = [flag for flag in tc.CFLAGS if flag != '-O1'] + ['-O2']
    common = cc + flags + ['-I', tc.RT]
    exe = folder / ('bench' + tc.EXE)
    subprocess.run(common + [str(emitted), tc.runtime_object(cc, env), '-lm', '-o', str(exe)]
                   + tc.stack_flags(), check=True, capture_output=True, env=env)
    if kind == 'kernel':
        subprocess.run(common + ['-S', str(emitted), '-o', str(folder / 'program.s')],
                       check=True, capture_output=True, env=env)
    return str(exe)


def measure(exes, args, runs):
    outputs, timings = {}, {label: [] for label in exes}
    for label, exe in exes.items():
        outputs[label] = subprocess.check_output([exe, *args])  # warmup
    if outputs['before'] != outputs['after']:
        raise RuntimeError(f'Output mismatch: {outputs!r}')
    for i in range(runs):
        for label in (['before', 'after'] if i % 2 == 0 else ['after', 'before']):
            start = time.perf_counter()
            result = subprocess.check_output([exes[label], *args])
            elapsed = time.perf_counter() - start
            if result != outputs[label]:
                raise RuntimeError('Output changed between repetitions')
            timings[label].append(elapsed)
    medians = {label: statistics.median(times) for label, times in timings.items()}
    return {'seconds': timings, 'median_seconds': medians,
            'speedup': medians['before'] / medians['after'],
            'output': outputs['after'].decode()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, help='git revision with the baseline decoder')
    parser.add_argument('--runs', type=int, default=7)
    parser.add_argument('--iterations', type=int, default=20000000)
    parser.add_argument('--decode-repeats', type=int, default=128)
    parser.add_argument('--duration', type=int, default=6)
    parser.add_argument('--out', type=Path, default=ROOT / 'kotor/out/constviewsbench')
    opts = parser.parse_args()
    if min(opts.runs, opts.iterations, opts.decode_repeats, opts.duration) < 1:
        parser.error('counts and duration must be positive')
    out = opts.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    decoders = {
        'before': subprocess.check_output(['git', 'show', f'{opts.before}:kotor/lib/audio/mp3.ctx'],
                                          cwd=ROOT, text=True),
        'after': (ROOT / 'kotor/lib/audio/mp3.ctx').read_text(),
    }
    if decoders['before'] == decoders['after']:
        parser.error('baseline and working-tree decoders are identical')
    audio = out / 'synthetic.mp3'
    # Different tones per channel plus periodic transients exercise joint stereo and windows.
    wave = ('aevalsrc=0.12*sin(2*PI*440*t)+0.08*sin(2*PI*1760*t)'
            r'+if(lt(mod(t\,0.2)\,0.008)\,0.25*sin(2*PI*6000*t)\,0)'
            '|0.15*sin(2*PI*659*t)+0.07*sin(2*PI*2200*t):s=44100')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
                    '-i', wave, '-t', str(opts.duration), '-c:a', 'libmp3lame', '-b:a', '192k',
                    '-write_xing', '0', '-id3v2_version', '0', '-write_id3v1', '0', str(audio)],
                   check=True)
    report = {'platform': platform.platform(), 'compiler': tc.compiler()[0],
              'flags': '-O2 (runtime -O1)', 'before_revision': opts.before,
              'parameters': {k: str(v) if isinstance(v, Path) else v for k, v in vars(opts).items()}}
    pcm = {}
    for label, decoder in decoders.items():
        exe = build(out, label, decoder, DECODE.replace('REPEATS', '1')
                    .replace('VERIFY_PCM', VERIFY_PCM), 'verify')
        pcm[label] = subprocess.check_output([exe, str(audio)])
    if pcm['before'] != pcm['after']:
        raise RuntimeError('Decoded PCM differs')
    report['pcm_equal'] = True
    report['pcm_and_summary_sha256'] = hashlib.sha256(pcm['after']).hexdigest()
    for kind, source, args in [
        ('kernel', KERNEL.replace('ITERATIONS', str(opts.iterations)), []),
        ('decode', DECODE.replace('REPEATS', str(opts.decode_repeats)).replace('VERIFY_PCM', ''), [str(audio)]),
    ]:
        exes = {label: build(out, label, decoder, source, kind) for label, decoder in decoders.items()}
        report[kind] = measure(exes, args, opts.runs)
        print(kind, json.dumps(report[kind]), flush=True)
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PCM identical; results:', out / 'results.json')


if __name__ == '__main__':
    main()
