# Audio: decoding, mixing, and how the engine uses it

`kotor/lib/audio` plays every sound the game has: it decodes KOTOR's `.wav` files (PCM, IMA ADPCM
and MP3 behind two KOTOR-specific wrappers, [formats/audio.md](../formats/audio.md)), mixes the
sounds playing at once into 16-bit stereo, and keeps SDL's audio queue topped up. Everything is
ctxlang; SDL only takes the finished samples.

| File | Namespace | What |
|---|---|---|
| `wav.ctx` | `wav` | `probe`: what a sound file holds (codec, channels, rate, where the samples are); a WAV header writer for tools |
| `ima.ctx` | `ima` | Microsoft IMA ADPCM blocks |
| `mp3.ctx` | `mp3` | MPEG-1 Layer III: frame headers, the Xing/Info/LAME tag, the decoder |
| `mp3_tab.ctx` | `mp3_tab` | generated (`tools/py/mp3tab.py`): the Huffman lookup tables and the synthesis window |
| `snd.ctx` | `snd` | `Stream`: any sound file, decoded a block or frame at a time |
| `mix.ctx` | `mix` | the mixer: voices, resampling, volumes and groups, 2D pan, 3D sound, feeds |
| `audio.ctx` | `audio` | the device: SDL's queue, filled once a frame; `heard` for lip sync |

Only `audio.ctx` names SDL; the rest is platform-neutral. Programs that use `lib/audio` add
`lib/base` (for `math::Vec3`) and `lib/platform`, and link SDL2.

## The per-frame model

ctxlang has no threads, so nothing pulls samples from us the way an audio callback would. SDL's
queued audio (`SDL_QueueAudio`) plays what it is given; the game gives it more once a frame:

```
let mut dev = try audio::open{ &sdl, rate = 44100, latency_ms = 60 }      // the device may pick another rate
let m = try mix::make{ realloc = heap::alloc, heap = &h, rate = dev.rate, voices_2d = 24, voices_3d = 16 }

while running {
    // ... the game's update: start and stop sounds, move them ...
    mix::set_listener{ m, position = camera.position, forward = camera.forward, up = camera.up }
    try audio::update{ &sdl, &dev, m }           // mixes what the queue lacks, queues it
    // ... render ...
}
```

`audio::update` measures what is still queued and renders just enough to have `latency_ms` of
sound queued again (in blocks of up to 1,024 frames). A frame that takes longer than the latency
empties the queue and the sound stutters (`dev.underruns` counts it). 60 ms covers a 30 fps frame
with a margin. Before work known to stall the loop for longer, such as loading a module, call
`audio::fill{ &sdl, &dev, m, frames = rate / 2 }` to queue half a second, and call
`audio::update` between loading steps as the original's `RenderLoadingFrame` updates its sound
(docs/re/app.md). Changes made to the mixer are heard after the queued latency, which is why it
should stay small.

The original opens Miles at 44.1 kHz, 16-bit stereo ([re/app.md](../re/app.md)); so do we by
default.

## The API

### Streams (`snd`)

```
let s = try snd::make{ realloc, &heap }       // a Stream is ~40 KB with an MP3 decoder in it
try snd::open{ s, bytes }                     // a whole sound file in memory; bytes must outlive s
let n = try snd::read{ s, into = buf[..] }    // interleaved i16 frames at s.info.rate / s.info.channels; 0 at the end
snd::rewind{ s }
snd::count_frames{ s }                        // exact length without decoding (MP3: walks the frame headers)
snd::read_xing{ s }                           // MP3: the LAME tag's frame count, encoder delay and padding
```

A stream decodes from the compressed bytes in memory, one IMA block (2,041 frames) or one MP3
frame (1,152) at a time, so a 7-minute track never exists as 80 MB of PCM. The compressed bytes
themselves are read whole (music is at most 7.5 MB); reading them in pieces from disk would add
an `Fs` to every render and gain nothing at this data's size. Errors are values: a file that
isn't a sound fails `open` with `wav::not_audio` and the like, an MP3 using a feature KOTOR never
uses (Layers I/II, MPEG-2 LSF, intensity stereo, mixed blocks, free format) fails with
`mp3::not_layer3` and so on.

### The mixer (`mix`)

```
let h = try mix::play{ m, bytes, p }          // -> mix::Handle; fails with the file's error or mix::no_voice
mix::stop{ m, h, fade = 0.2 }                 // fade out over 0.2 s (0: at once)
mix::stop_all{ m, group = mix::Group::sfx, fade }   // null group: everything
mix::is_playing{ m, h }
mix::played{ m, h }                           // ?f64: seconds of the sound mixed so far
mix::set_volume / set_pan / set_pitch / set_position / set_looping / set_paused { m, h, ... }
mix::set_group_volume{ m, group, volume }     // swkotor.ini's 0..100 / 100
mix::set_group_paused{ m, group, paused }
mix::set_master{ m, volume }
mix::set_listener{ m, position, forward, up }
mix::render{ m, into }                        // what audio::update calls
```

`Params` say how a sound plays: `group`, `volume` (linear, 0..1), `pan` (2D, -1..1), `pitch`
(rate multiplier), `looping`, `priority` (0..255, higher keeps its voice), `positional`,
`position`, `min_distance`, `max_distance`. `mix::sound_2d{ group, volume }` and
`mix::sound_3d{ group, volume, position, min_distance, max_distance }` fill in the rest (priority
128, pitch 1, not looping) and the fields can be changed after.

A `Handle` is a slot and a generation: once its sound ends, or its voice is taken by another
sound, every call with it does nothing and `is_playing` is false. The zero handle is "no sound",
so a game object can keep one in a field from the start.

**Groups** are swkotor.ini's four volumes: `music` (Music Volume), `voice` (Voiceover Volume),
`sfx` (Sound Effects Volume), `movie` (Movie Volume). A voice's gain is its volume times its
group's times the master volume. Groups can be paused (the game pauses effects and voice-over
while it is paused, music plays on).

**Voices.** `make` takes how many 2D and 3D voices there are, as swkotor.ini's `Number 2D
Voices=24` and `Number 3D Voices=16` say for Miles. When a kind runs out, `play` takes the voice
of the lowest-priority sound of that kind if its priority is no higher than the new one's, and
fails with `no_voice` otherwise.

**Resampling.** Each voice is resampled from its file's rate (11,025, 22,050, 32,000 or 44,100 Hz
in KOTOR) times its pitch to the output rate by cubic (Catmull-Rom) interpolation, from 32.32
fixed-point positions. At the output's own rate and pitch 1 the samples pass through unchanged;
against an ideal band-limited resampler, 32 kHz voice-over to 44.1 kHz comes out about 43 dB
cleaner than the error. Looping is sample-exact.

**2D panning** is a balance: `pan` lowers the far side (left gain `1 - pan` for pan > 0, right
gain `1 + pan` for pan < 0), so a centred sound is at full volume on both sides. A stereo file
keeps its channels.

**3D sound.** A positional voice is mixed in mono (a stereo file is downmixed). Its gain is
attenuated by distance from the listener: 1 within `min_distance`, 0 from `max_distance`, and
between them `min / d` faded linearly to 0 at the max, so nothing pops off at the edge. Its pan
is 0.7 times the cosine between the direction to it and the listener's right (`forward x up`;
KOTOR is right-handed with Z up): a sound to one side is at 0.3 in the far ear, never gone. There
is no Doppler, HRTF, occlusion or reverb (the original's EAX rooms are not reproduced).

**Smoothness.** Gains move linearly from where they were to the new target across each block of
up to 1,024 frames (23 ms), so volume, pan and position changes and moving sounds don't click.
A new voice starts at its target gain; `stop` fades over the time given.

**Feeds** play samples the caller makes as it goes, such as a Bink movie's sound:

```
let h = try mix::play_feed{ m, rate = 22050, channels = 2, p = mix::sound_2d{ group = mix::Group::movie, volume = 1.0 } }
let took = mix::feed{ m, h, samples }         // whole frames taken; keep the rest for later
mix::feed_room{ m, h }                        // frames of room in its 2 s (at 48 kHz) ring
mix::end_feed{ m, h }                         // it ends once it has played what it has
```

A feed that runs dry plays silence and keeps its voice; there are two feeds. The ring holds 2 s
at 48 kHz stereo, so a Bink movie's first packet (a 0.78 s pre-roll, docs/design/video.md) goes
in whole, and later frames (one 1,920-sample block each) always fit. For the movie's clock,
`audio::heard` on the feed's handle is how much of its sound has been heard; `mix::stop{ m, h,
fade = 0.0 }` drops what is left when the movie is skipped.

**Memory.** `mix::make` allocates the mixer and its voices (about 3 MB for 40 voices: each holds
its own stream and decoder) from the allocator it is given; `mix::free` gives it back. A voice
doesn't own its file's bytes: the caller keeps them until `is_playing` is false. Streams and
the mixer are big, so they are only ever passed by pointer.

### The device (`audio`)

```
audio::open{ &sdl, rate, latency_ms } -> !Device     // initialises SDL's audio subsystem
audio::update{ &sdl, &dev, m }                       // once a frame
audio::fill{ &sdl, &dev, m, frames }                 // queue more before a stall
audio::set_latency{ &dev, latency_ms }
audio::heard{ &sdl, dev, m, h } -> ?f64              // seconds into voice h as heard now
audio::flush{ &sdl, dev }                            // drop what is queued
audio::close{ &sdl, &dev }
```

## How the engine should use it

The engine layer above `mix` (planned, stage 3-4) owns the policy: which sound a game event
means, where its bytes come from, and how long they stay. The pieces, with the data that drives
them:

**Finding the bytes.** Sounds in archives (sound effects in `sounds.bif`, GUI sounds) come from
the resource manager: `res::load{ ..., kind = restype::Type::wav }`. Streamed sounds are files:
`res::voice_path` (voice-over: `streamwaves/<module>/<dialogue>/<name>.wav` for the 16-character
names, else the top level), `res::music_path` (`streammusic/`), `res::sound_path`
(`streamsounds/`). A sound that exists nowhere is silence, not an error: `dialog.tlk` and
`ambientmusic.2da` name hundreds of missing files ([formats/audio.md](../formats/audio.md)). A
small cache keyed by resref keeps effect sounds loaded (they are reused constantly); streamed
files are read when their sound starts and freed when it stops.

**Music.** The area's `MusicDay`/`MusicNight`/`MusicBattle` (GIT `AreaProperties`) are rows of
`ambientmusic.2da`, whose `resource` names a track in `streammusic/`. Play it in the `music` group;
when it ends, wait `MusicDelay` milliseconds and play it again (the original repeats it with a
pause, not as a seamless loop). When combat starts, `stop` the area track with a fade and play
the battle track (looping); when combat ends, fade it out and play its `stinger1`, then return to
the area track. Cutscene music (`streammusic/<number>.wav`, named by `.dlg` files) replaces the
area track for the scene. `prioritygroups.2da`'s `Streams_Music` row gives music its volume (64
of 127) and fade time (1,000 ms).

**Ambient beds.** `AmbientSndDay`/`AmbientSndNight` are rows of `ambientsound.2da` whose
`resource` is a long loop in `streammusic/` (IMA ADPCM or PCM, `al_*`); play it looping in the
`sfx` group at `AmbientSndDayVol / 127`, scaled by the listener's room's `AmbientScale` (ARE
`Rooms`).

**Placed sound objects** (GIT `SoundList`, from `.uts` blueprints;
[formats/gff-templates.md](../formats/gff-templates.md)): each needs a small scheduler in the
engine. `Continuous` plays one wave looping. Otherwise it plays a wave from `Sounds` (in order, or
at random with `Random`), waits `Interval` +/- `IntervalVrtn` ms, and plays the next, forever with
`Looping` or once without. `Positional` makes it `mix::sound_3d` at the object's position (plus
`Elevation`, plus a random offset within `RandomRangeX/Y` with `RandomPosition`) with its
`MinDistance`/`MaxDistance`; otherwise `sound_2d`. `Volume` is 0..127 (divide by 127), varied by
`VolumeVrtn`; `PitchVariation` is in octaves, so `pitch = 2^(random(-v, v))`. `Priority` is a row
of `prioritygroups.2da`.

**Priorities.** `prioritygroups.2da` gives each class of sound a `priority` (0 is the most
important, 255 the least), a `volume` (0..127), `maxplaying`, `interrupt`, `fadetime`, distances
and a `playbackvariance` (pitch). Map its priority to the mixer's as `255 - priority`, multiply
its volume into the sound's, and enforce `maxplaying` in the engine: keep the handles of each
class, and when one more would exceed it, stop the oldest if `interrupt` is 1, or don't play the
new one if it is 0.

**Voice-over and lip sync.** A dialogue line names its VO (`.dlg` `VO_ResRef`, or the sound of
its `dialog.tlk` string); play it with `sound_2d{ group = voice }` (party and NPC barks too). The
line's `.lip` (same resref; [formats/lip.md](../formats/lip.md)) times the mouth: each frame, take
`t = audio::heard{ &sdl, dev, m, h }` (what the mixer has played less what is queued and in the
device's buffer) and pick the keyframes around `t`. When `is_playing` turns false the line is
over (or use the LIP's length for lines with no sound). The MP3s carry 576 samples of encoder
delay (18 ms at 32 kHz, in the LAME tag) that we play as Miles probably did, without trimming;
`snd::read_xing` has the number should lip sync turn out to want it.

**Sound effects.** Footsteps (`footstepsounds.2da`), weapons, impacts, spells, creature sounds
(soundsets: `.ssf` strrefs into `dialog.tlk`, whose sound resrefs name the waves), GUI clicks
(`guisounds.2da`) and scripted `PlaySound`: load (cached), then `mix::play` 3D at the source for
anything in the world, 2D for the GUI, with the class's priority. Moving sources (a creature's
looping sound) get `set_position` each frame. The listener is the camera
(`UpdateSoundListener` in the original follows the camera/player each frame).

**Movies.** The Bink decoder (lib/video) decodes a movie's audio and pushes it into a feed
(`play_feed` in the `movie` group, `feed` as frames decode, `end_feed` at the end); the picture
can be timed from `audio::heard` on the feed's handle. While a movie plays, pause the `sfx` and
`voice` groups.

**Options.** At start, read `[Sound Options]` from swkotor.ini: `Music Volume`, `Voiceover
Volume`, `Sound Effects Volume`, `Movie Volume` (0..100) go to `set_group_volume` divided by
100; `Number 2D Voices` and `Number 3D Voices` to `mix::make`; `Disable Sound=1` means don't open
a device and drop every sound.

**No device.** If `audio::open` fails (no output, as the original sets `g_bDisableSound` when
Miles fails), the game plays on silently: it still makes the mixer and calls `mix::render` into a
scratch buffer for the frame's elapsed time instead of `audio::update`, so voices advance and end
as they would and dialogue, lip sync and movies keep their clocks.

## Checked

```
kotor/tools/ctxc run kotor/tools/sndcheck              # every sound in the install, decoded
kotor/tools/ctxc run kotor/tools/sndcheck -- --ref 40  # ... and every 40th MP3 and all music against ffmpeg
kotor/tools/ctxc run kotor/tools/mixtest               # the mixer, on sounds with known answers
kotor/tools/ctxc run kotor/tools/sndplay -- FILE       # play one (or --wav / --mixed OUT to write it)
```

- **The whole install decodes**: 16,818 sounds (13,867 MP3, 2,900 PCM, 51 IMA ADPCM; the loose
  files under the stream folders and launcher, and every WAV the resource manager finds in an
  archive), no failure, every decoded length equal to what the headers say (data size, `fact`,
  MP3 frames walked, and the Info frame's count in all 13,799 voice-over files).
- **Against ffmpeg** (its float MP3 decoder, a dev-only reference): 412 files (344 voice-over
  lines and all 68 music tracks), 592 million samples. No sample differs by more than 1 (in 16-bit
  steps), 0.17 % of them differ at all, RMS difference 0.04. ffmpeg's IMA ADPCM decoder rounds
  each step from `(2 * code + 1) * step / 8` rather than the IMA reference's shifts, which we use,
  so IMA isn't compared; 8- and 16-bit PCM decode identically.
- **Speed** at -O2 (one core; a busy machine reads lower): voice-over MP3 (32 kHz mono) about
  1,000x real time, music MP3 (44.1 kHz stereo) about 340x, IMA ADPCM stereo about 700x, PCM
  thousands. Mixing 40 PCM voices with resampling, 3D and ramps runs about 90x real time; 40 voices
  each decoding its own stereo MP3 about 5x.
- **mixtest**: 27 checks of exact sample values (gains, pans, groups, ends, loops, fades,
  stealing, stale handles, 3D, feeds) pass.

## Open questions

- Whether Miles trimmed the MP3s' encoder delay (LIP timing would say, by 18 ms).
- The original's 3D rolloff and pan law (Miles with a 3D provider, or EAX), and how `2D3D Bias`
  and `Environment Effects Level` apply; ours are chosen, not measured.
- Which volume `prioritygroups.2da`'s distances override (they differ from the UTS's own).
