# Movies: the Bink decoder and how the game plays it

KOTOR's 61 cutscenes, logos and legal screen are Bink 1 files (`movies/*.bik`, all revision
`i`, 640 wide, 29.97 fps, DCT audio). `lib/video` decodes them in ctxlang: pictures as YUV 4:2:0
planes and sound as 16-bit PCM. The format itself is in
[docs/formats/bink.md](../formats/bink.md); this note is about our code: its API, where the
codec's tables come from, how it was checked, how fast it is, and how the game should play a
movie.

## Files

| File | Namespace | What |
|---|---|---|
| `lib/video/bink.ctx` | `bink` | the container (header, track tables, frame index, frame packets) and the API below |
| `lib/video/bink_video.ctx` | `bink_video` | the video decoder: bundles, prefix codes, the ten block types, DCT and residue coding, IDCT, motion compensation, two pictures |
| `lib/video/bink_audio.ctx` | `bink_audio` | the DCT audio decoder: bands, coefficients, an FFT-based DCT-III, overlap |
| `lib/video/bink_bits.ctx` | `bink_bits` | the LSB-first 32-bit-word bit reader both share |
| `lib/video/bink_tables.ctx` | `bink_tables` | finds the codec's tables in the install's `binkw32.dll` |
| `tools/bink2png` | | decodes frames N..M of a movie to PNGs, or to raw yuv420p |
| `tools/binkcheck` | | decodes every movie, times it, and with `--ref` compares with FFmpeg |

`lib/video` depends on std only (no `lib/base`, no SDL); the tools add `lib/base` (PNG) and
`lib/platform` (SDL's performance counter).

## API

```
// Once, at start-up: the codec's tables (about 10 KB), from the install.
let tables = bink_tables::load{ &fs, realloc, &heap, path = "<install>/binkw32.dll" } iferr {
    // no usable DLL: play no movies (log it); the game goes on
}

// A movie: header and index read, decoders made. Memory from `realloc` (below).
let mut movie = try bink::open{ &fs, realloc, &heap, path = "<install>/movies/01a.bik", tables = &tables }
movie.header.width, .height, .frames, .rate_num / .rate_den      // 640 x 272, 3606, 2997/100
movie.audio_rate, movie.audio_channels                            // 44100, 2 (0, 0: silent)

while true {
    let frame = try bink::next{ &fs, m = &movie } ifnull { break }   // null after the last frame
    frame.number                                                       // 0, 1, 2, ...
    frame.y, frame.u, frame.v              // bink_video::Plane { pixels, stride, width, height }
    frame.audio                            // []i16, interleaved: this frame's audio packet
    bink::frame_time_us{ header = movie.header, frame = frame.number }  // when to show it
}
bink::close{ &fs, realloc, &heap, m = &movie }
```

- **Streaming.** `open` reads the header and the frame index; `next` reads one frame from the file
  (sequentially, no seeking: every KOTOR movie has one keyframe, frame 0, so playback always starts
  at the beginning) and decodes its audio and video. The frame's planes and samples live in the
  movie until the next call to `next`.
- **Planes.** `y` is `width` x `height`, `u` (Cb) and `v` (Cr) half that each way, 8 bits per
  sample, BT.601 limited range (Y 16..235). Rows are `stride` bytes apart (`stride >= width`:
  the decoder pads planes to whole 16x16 blocks), so a texture upload needs the row length.
- **Audio.** Each frame's `audio` is what that frame's packet decodes to, interleaved, at
  `movie.audio_rate`: the first frame carries 18 blocks (about 0.78 s, a pre-roll), later frames
  one block (1920 samples per channel) or nothing (about one frame in four). The samples are
  trimmed to the file's own count, so a track ends exactly with the video (within 1 ms). A track
  that isn't DCT audio (none in KOTOR) leaves `audio_rate` 0 and sets `audio_unsupported`; the
  movie then plays silent rather than not at all.
- **Timing.** Frame *n* starts at `n * rate_den / rate_num` seconds (`frame_time_us`);
  `duration_us` is the end of the last frame. Audio starts at time 0 with frame 0.
- **Errors.** A malformed file is an error value, never a panic or an out-of-bounds access:
  `bink::not_bink`, `unsupported{ revision, video_flags }`, `bad_frame{ frame }`,
  `truncated{ frame }`, ...; from the decoders `bink_video::overrun`, `starved`, `bad_block`,
  `bad_run`, `bad_motion{ plane, row, col, x, y }`, `bink_audio::bad_packet`, and fs and allocation
  errors. On an error the game should end the movie as if it had finished.
- **Memory**, per open movie, all from the caller's allocator and freed by `close`: two pictures
  (640 x 480: 0.9 MB; 640 x 272: 0.5 MB), the bundles' value buffers (0.3 MB), the frame index
  (4 bytes a frame), one frame of the file (KOTOR's largest is 53 KB), the audio decoder (about
  0.13 MB) and its PCM buffer (0.14 MB).
- **Lower levels**, for other uses (tests, another way of reading files): `bink::read_frame`
  (the next frame's bytes) and `bink::decode_frame` (them decoded), which `next` is made of;
  `bink::parse_header` and `bink::split` (a frame's audio and video packets);
  `bink_video::new/decode/plane/free` (one video packet in, the next picture out) and
  `bink_audio::new/decode_packet/free` (one audio packet in, samples out).

## The tables: read from the install's binkw32.dll

The video decoder needs constant tables: 16 prefix codes (lengths and bits), the coefficient scan
order, the 16 scan patterns of run blocks, and the 16 intra and 16 inter quantizer matrices
(each 64 values). Options:

1. **Embed them as source.** Their only public text form is FFmpeg's `binkdata.h` (LGPL,
   mirrored in GPL projects), which our rules forbid copying. Retyping them from there is
   copying.
2. **Derive them from first principles.** The prefix codes, the scan order and the run patterns
   are arbitrary choices of RAD's: there is nothing to derive them from. The quantizers are
   described (a base matrix times 16 steps, with the IDCT's scale folded in), but an attempt to
   rebuild them came out one too low in about 4% of the entries, and a decoder that is off by
   one in a quantizer is not bit-exact.
3. **Read them at run time from `binkw32.dll`**, RAD's decoder, which every install of the game
   ships next to `swkotor.exe` (the install is required anyway).

**Decision: 3.** `bink_tables::load` reads the DLL and finds each table by its *shape*, without
assuming where the linker put it: prefix-code lengths start with sixteen 4s (code 0 is plain 4-bit
values); the codes with 0..15; a scan order is a permutation of 0..63 starting at 0; the run
patterns start with a permutation; a quantizer set is little-endian i32s whose second matrix is the
first times 4/3 (the documented second step). Each candidate is accepted only if the CRC-32 of the
whole table is the one recorded in [bink.md](../formats/bink.md#tables-where-to-get-them), so
another build of the DLL that holds the same tables anywhere works, and one with different tables
is refused. The prefix codes are then checked to form 16 complete codes of at most 7 bits, and
turned into 7-bit lookup tables. Reading the 375 KB DLL and searching it takes about 7 ms, once.

What is embedded instead is public prose or arithmetic: the block-type repeat counts 4, 8, 12, 32
and the audio decoder's critical-band frequencies and coefficient run lengths (all printed on
MultimediaWiki), the IDCT's four multipliers (the AAN factors in Q11), and the audio quantizer
curve `10^(0.0664 q)`.

Consequences: no table data is in git; without a `binkw32.dll` holding these tables (another
platform's port, say) `load` fails with `bink_tables::no_*` and the game must skip its movies
rather than crash. A port's Bink library (a `.dylib` or `.so`) very likely holds the same tables
in the same layout, and the search is over raw bytes, so pointing `load` at it should work.

## Checked against FFmpeg

`binkcheck --ref` decodes every movie and compares it with FFmpeg 7.1's decoder, run as a
program (a dev-only oracle; nothing of it is linked or copied):

```
kotor/tools/ctxc run kotor/tools/binkcheck -- --ref        # needs ffmpeg on PATH (MSYS2's mingw64)

61 movies, 0 failed; 48752 frames, 143378834 samples
reference: 48752/48752 frames exact; audio: 143378834 samples compared, 113172 differ, max difference 1
```

Video is **bit-exact**: every frame of every movie is byte for byte FFmpeg's yuv420p output.
Audio differs by at most 1, in 0.08% of the samples: both round half to even, but FFmpeg
computes in 32-bit float and we in 64-bit, so values near a half round differently now and then.
Every packet decodes to exactly the sample count its header field gives. The audio decoder was
also fuzzed (145,000 cut, bit-flipped and random packets: errors, no panics), and its FFT-based
DCT-III checked against the direct cosine sum (error under 1e-8).

## Speed

`binkcheck` times `bink::next` per frame (reading the frame from the file, decoding its audio
packet and its video) at `-O2`, on an AMD Ryzen 9 5900X, one thread:

| Movies | Frames | Average | Slowest frame |
|---|---:|---:|---:|
| 53 at 640 x 272 | 38893 | 0.90 ms | 3.33 ms |
| 5 at 640 x 360 | 9185 | 1.05 ms | 3.70 ms |
| 3 at 640 x 480 | 674 | 0.97 ms | 2.55 ms |
| all 61 | 48752 | 0.93 ms | 3.70 ms |

A frame lasts 33.4 ms at 29.97 fps, so decoding takes about 3% of a core while a movie plays
(all 27 minutes of movies decode in 45 s), and the slowest frame is a tenth of the budget. Audio
is a small part of it: about 36 us per stereo block, one block every 1.3 frames.

What helped (and what a reader should keep): the bit reader refills 32 bits at a time and decodes
prefix codes with one 7-bit table lookup; pixel loops write through raw pointers into planes whose
bounds were checked once per block (motion vectors) or hold by construction; the IDCT skips the
column pass for columns with only a DC; the audio's DCT-III is one complex FFT for both channels.
Everything else is plain ctxlang with checked arithmetic.

## Playing a movie in the game

What the original does (from [docs/re/app.md](../re/app.md), "Movies"): movies are queued with a
skippable flag each (the legal movies `leclogo`, `biologo`, `legal` at start-up unless `Disable
Movies`; the script `PlayMovie`; module transitions); while one plays the main loop draws nothing
else, the client's world timers are paused, Esc or a mouse click skips a skippable movie, the
picture is centred (or scaled) in the window over a black background, and the sound goes through
the game's audio system at the movie volume.

Our game loop, with no threads:

1. **Enter movie mode.** Pause world timers and the 3D/GUI drawing; `bink::open` the first queued
   movie. If the tables failed to load or the open fails, skip it.
2. **Video through the render seam.** The renderer keeps three single-channel 8-bit textures (Y at
   `width x height`, U and V at half size) for the movie and a quad drawn with a YUV shader. Each
   new picture is uploaded plane by plane (with GL, `glTexSubImage2D` of `GL_RED` with
   `GL_UNPACK_ROW_LENGTH = stride`). The shader converts BT.601 limited range:
   `r = 1.164 (y - 16/255) + 1.596 (v - 0.5)`, `g = 1.164 (y - 16/255) - 0.392 (u - 0.5) - 0.813 (v - 0.5)`,
   `b = 1.164 (y - 16/255) + 2.017 (u - 0.5)`, sampling U and V bilinearly. The quad keeps the
   movie's aspect (640 x 272 is 2.35:1): scaled to the window's width, centred, black above and
   below. The render seam needs, roughly, "create a video surface of w x h", "update its three
   planes from (pixels, stride)", and "draw it into this rectangle"; a Metal or Vulkan backend
   does the same with its own upload and shader. Converting on the CPU is not needed.
3. **Audio into the mixer.** Open a mixer stream at `movie.audio_rate` (44100, or 48000 for
   `56b.bik`; the mixer resamples to the device rate) with `audio_channels` channels, at the movie
   volume, and append each frame's `frame.audio` as it is decoded. The first frame's 0.78 s
   pre-roll fills the stream's buffer at once.
4. **The clock is the audio.** The frame to show is the one whose start time has passed on the
   audio stream's played-sample count (`played / rate`); the mixer must report how many samples of
   the stream the device has consumed (SDL: queued minus `SDL_GetQueuedAudioSize`). Without audio
   (`legal.bik`) use the wall clock from when the movie started. Each game frame: while the next
   movie frame's start time is due, `bink::next` (about 1 ms each) and push its audio; upload only
   the last picture decoded. Falling behind thus drops pictures, never audio. Before the audio
   starts (the first game frame), show frame 0.
5. **Skip and end.** Esc or a click (if skippable) or `next` returning null or an error ends the
   movie: `bink::close`, drop the stream's unplayed audio, open the next queued movie or leave
   movie mode and resume the timers.

## Open questions

- **RAD's own colour conversion.** The original game lets `binkw32.dll` convert to RGB
  (`BinkCopyToBuffer`); we assume BT.601 limited range, as FFmpeg does. Black bars (Y 16) come out
  black and skin and lightsabers look right (`kotor/out/bink/02_0120.png`), but the DLL's
  matrix wasn't reverse-engineered: a quick search for the usual fixed-point constants in it found
  none, so it may use computed lookup tables. Worth a look in Ghidra if colours ever seem off.
- **Volume and the movie's sound mode.** The original sets the sound mode to 3 while a movie plays
  (docs/re/app.md); what that mutes or ducks is for the audio subsystem to find out.
