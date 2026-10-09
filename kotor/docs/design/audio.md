# Audio: decoding, mixing, and how the engine uses it

`kotor/lib/audio` plays every sound the game has: it decodes KOTOR's `.wav` files (PCM, IMA ADPCM
and MP3 behind two KOTOR-specific wrappers, [formats/audio.md](../formats/audio.md)), mixes the
sounds playing at once into 16-bit stereo, and keeps SDL's audio queue topped up from a thread of
its own. Everything is ctxlang; SDL only takes the finished samples.

| File | Namespace | What |
|---|---|---|
| `wav.ctx` | `wav` | `probe`: what a sound file holds (codec, channels, rate, where the samples are); a WAV header writer for tools |
| `ima.ctx` | `ima` | Microsoft IMA ADPCM blocks |
| `mp3.ctx` | `mp3` | MPEG-1 Layer III: frame headers, the Xing/Info/LAME tag, the decoder |
| `mp3_tab.ctx` | `mp3_tab` | generated (`tools/py/mp3tab.py`): the Huffman lookup tables and the synthesis window |
| `snd.ctx` | `snd` | `Stream`: any sound file, decoded a block or frame at a time |
| `mix.ctx` | `mix` | the mixer: voices, resampling, volumes and groups, 2D pan, 3D sound, feeds |
| `audio.ctx` | `audio` | the device: SDL's queue, kept full by the mixer's thread (or once a frame); `heard` for lip sync |

Only `audio.ctx` names SDL; the rest is platform-neutral. Programs that use `lib/audio` add
`lib/base` (for `math::Vec3`) and `lib/platform`, and link SDL2.

## The mixer's thread

SDL's queued audio (`SDL_QueueAudio`) plays what it is given; something has to give it more before
it runs dry. In the game that is a thread of its own (`audio::start`), as Miles mixed on its own
thread in the original, so the sound no longer depends on how long a frame takes:

```
let mut dev = try audio::open{ &sdl, rate = 44100, latency_ms = 60 }      // the device may pick another rate
let m = try mix::make{ realloc = heap::alloc, heap = &h, rate = dev.rate, voices_2d = 24, voices_3d = 16 }
try audio::start{ &sdl, &threads, &dev, m }    // the mixer's thread: needs Threads, so main takes it
defer audio::close{ &sdl, &dev }
defer audio::stop{ &threads, &dev }            // runs first: the thread is joined before the device closes

while running {
    // ... the game's update: start and stop sounds, move them, set the listener ...
    // ... render ...
}
```

**The thread** (`audio::pump`) looks at the queue every 4 ms and mixes what it lacks to stay
`latency_ms` (60 ms) ahead of the speakers, a `mix::BLOCK` (1,024 frames, 23 ms) at a time, then
sleeps. The device takes its buffer 1,024 frames at a time, so the queue swings between about
37 and 60 ms; a frame of any length leaves it there. Changes to the mixer are heard 40-80 ms
later.

**The lock.** The Mixer is one structure both threads use, guarded by a mutex in it (`m.lock`).
Every public `mix::` fn takes the lock for its own work (so the game's calls change nothing), and
`mix::render` holds it for one block's mixing at a time, never across SDL's calls or a sleep. A
game call waits at most for the block being mixed (well under a millisecond for 40 voices). The
lock isn't recursive: inside mix.ctx only the public fns lock, and what they call (`stop_voice`,
`take_voice`, `voice_of`) doesn't. Windows' slim lock isn't fair: a thread that unlocks and locks
again at once can keep it, so the pump sleeps between top-ups (mixtest's stress check yields
between blocks for the same reason). A command queue (ctxlang/threads.md, "Examples") would avoid
the waiting altogether; it isn't needed while a block is this quick.

**Memory.** The voices read their sounds' bytes, which belong to the game (the ambience's
streams, the dialogue's voice-over, the GUI's and pazaak's clicks, cached effect waves). The rule:
bytes may be freed only once no voice reads them, which is when `mix::stop{ fade = 0 }` or
`mix::release{ m, bytes }` has returned, or `is_playing` said false. A stopped voice that is
fading out still reads its bytes until the fade ends. Since every one of these takes the lock,
once it returns no block being mixed can still be reading them. `release` ends every voice
reading a buffer whether or not its handle was kept: the ambience's `stop_bytes` and pazaak's
`end_session` call it before they free. Area changes run `ambience::stop_area` (every voice
stopped at once) before the scene and module memory go. Sounds that are never freed (the GUI's,
the front end's theme, the cached effect waves, the credits song) need nothing. A feed's samples
(movies) are copied into the mixer's own ring, so a movie's memory isn't the mixer's concern.

**Output and counters.** The thread prints nothing (standard output is per thread in a threaded
program). It counts underruns (the queue found empty) in `dev.underruns` with atomics;
`audio::underruns` reads them, and with `--log sound` the game reports each new one at the frame
it sees it, and the total at the end.

**Shutdown.** `audio::stop` clears an atomic `running` flag and joins the thread; the game's play
loop does it, and closes the device, as it returns (`play::close_sound`, deferred right after the
mixer starts, so it runs before anything set up earlier is undone).

**Without the thread.** A program that doesn't take `Threads` (the tools: sndplay, menurun,
movietest, pazaakplay), or a game whose thread failed to start, calls `audio::update` once a frame
instead, which mixes what the queue lacks to cover the next frame (`update`, `brace` and `fill` do
nothing while the thread runs). A frame that takes longer than what is queued then empties the
queue and the sound stutters. What it keeps queued adapts: at least `latency_ms`, else the longest
gap between updates lately (falling by 5 % of each frame's time, a stall counted as at most
250 ms) plus 50 ms, at most 250 ms. `audio::brace` queues the most at once before a known stall
(a new area's first frames), and `audio::fill{ &sdl, &dev, m, frames }` a given amount. Measured
before the thread at real pace: on the escape pod and the Taris arrival with the machine busy
(frames of 60-100 ms), a fixed 60 ms ran dry 144 times in 90 s; adapting, 3 times.

**Headless runs** without `--sound-device` open no device and start no thread: the game renders
into a scratch buffer for each tick's time (as before), so replays and tests stay deterministic.

**What a threaded program costs.** `main` taking `Threads` makes the whole game a threaded program
(spec §15, Entry point, rule 8): the stack check reads its limit from a thread-local slot, about a
fifth more time on a program that does nothing but call. On the game it is about 2-3 %: the Upper
City fight (`--headless --load uppercity`, fight6.txt, 1,800 frames, no sound device, three runs
each, the mixer's lock included) took 3.05 ms a frame drawn before and 3.11 after, and 1.17 ms
with `--no-render` before and 1.21 after.

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
mix::render{ m, into }                        // what the mixer's thread (or audio::update) calls
mix::release{ m, bytes }                      // ends at once every voice reading `bytes`, before they are freed
mix::stats{ m }                               // the counts (Stats), read under the lock
```

Each of these takes the mixer's lock for its work (above, "The mixer's thread").

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
of the lowest-priority sound of that kind if its priority is *lower* than the new one's, and
fails with `no_voice` otherwise: as in the original ([re/app.md](../re/app.md), "Voices"), a sound
never cuts off one as important as itself. A 3D sound at or past its `max_distance` from the
listener fails with `out_of_range` and takes no voice. `m.stats` counts steals, refusals, cuts
(audible voices ended without a fade), clipped output samples, the peak and the most voices busy;
`take_events` hands over the latest steals and refusals with the sounds' `tag`s, for
`--log sound`, which also names every one-shot the presentation starts (`sound play NAME row
GROUP`, `(missing)` when the wave isn't found).

**Voices and loudness: what the engine layer does** (lib/scene/ambience.ctx). Every sound effect
carries its `prioritygroups.2da` row: a sound object its UTS `Priority`, a `play_sound` note a
row chosen by kind (`outbox::GROUP_*`: combat 15, scripted `PlaySound` 10, GUI 11, traps 22), the
music 2, stingers 1, the ambient bed 4. Its mixer priority is `255 - Priority`, so ambients (4, 5)
keep their voices over combat (15) and footsteps (19, 20). Its volume is the original's: its own
times the row's `Volume` (both /127), squared for a 3D sound, and for a 2D one times `2 - 2D3D
Bias` (the settings' `2D3D Bias`, 1.5 as installed: half). A continuous positional sound object
gives its voice back 6 m past its max distance and starts again within 2 m of it.

Measured on the first 9,000 frames of the Endar Spire replay at real pace (below, "Checked"),
before these rules: 936 voices stolen in 5 minutes (353 of them looping ambients, which then
restarted and stole another; every sound had priority 128 and the first busy slot was taken, so
one slot was often stolen several times in a frame), 295 audible cuts, 1.4 % of output samples
clipped (peak 2.5 times full scale, from the bunk room's 2D loops at their full level on); after:
none stolen or refused, 12 cuts, 118 samples clipped (the limiter, below, turns the rest down).

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

**Limiter** (ours: Miles' output stage wasn't read). When the voices sum past full scale, the
block about to be handed over turns the whole mix down to 0.97 of full scale within 64 frames (a
ramp, not a step), and the gain comes back by 0.025 a block (about half a second from half to
full) once the sum fits. Hard clipping a loud fight made it crackle: the Upper City fight against
six troopers clipped 1.6 % of its samples (peak 2.8 times full scale) before; with the original's
volumes (below) and the limiter, 20 samples in a minute.

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
doesn't own its file's bytes: the caller keeps them until `is_playing` is false (or until `stop`
with no fade or `release` returns: "The mixer's thread", Memory). Streams and
the mixer are big, so they are only ever passed by pointer.

### The device (`audio`)

```
audio::open{ &sdl, rate, latency_ms } -> !Device     // initialises SDL's audio subsystem
audio::start{ &sdl, &threads, &dev, m }              // the mixer's thread keeps the queue latency_ms ahead
audio::stop{ &threads, &dev }                        // ends and joins it (before close)
audio::underruns{ &dev } -> u32                      // times the queue ran dry, from any thread
audio::update{ &sdl, &dev, m }                       // once a frame, without the thread (nothing with it)
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

**Doors and placeables** (lib/engine/objsound.ctx; [re/actions.md](../re/actions.md) 3.15): their
`placeableobjsnds.2da` row (genericdoors/placeables `SoundAppType`) names the waves. A door's open
state changing plays `Opened` (from closed), `Closed` (to closed) or `Destroyed`
(`doors::set_door_state`, so a bashed door, which opens, sounds `Opened`); USEOBJECT opening a
container plays `Opened`; a placeable's state animation plays `Closed` (leaving open), `Used` (to
or from on/off) or `Destroyed` (its DEATH event); "This object is locked." to the player plays
`Locked`. All as `play_sound` notes, 3D at the object (a door's 1.5 m up), group 22
(`Single_Shot_Positional`). Not done yet: a hit on a door or placeable should take its row's
`ArmorType` as the weaponsounds.2da column (lib/engine/fight_fx.ctx `hit_column` still uses
`leather`), and a creature's body bag uses row 53 `Corpse` for its close sound.

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
- **mixtest**: 34 checks pass: 33 of exact sample values (gains, pans, groups, ends, loops,
  fades, stealing and its equal-priority rule, the stats, out-of-range 3D, the limiter, stale
  handles, 3D, feeds, `release`), and the lock: a thread renders 3,000 blocks while the test plays,
  stops, fades and releases sounds, and a sound stopped at once or released is never seen playing
  after the call.
- **At real pace** (`sh kotor/tools/sndrun/run.sh`, testing.md): the game runs headless with
  `--sound-device` on SDL's `disk` driver, which takes the samples at the speakers' pace and
  writes them to a file, and `kotor/tools/py/sndscan.py` reads that file for dropouts (digital
  silence between sounds), clicks (a step far larger than the signal's motion around it; real
  sounds' sharp attacks count too, so it is a relative measure) and clipping; `--log sound`
  gives the mixer's side. Before and after the fixes of 2026-10 (steals, the original's volumes,
  out-of-range voices, the limiter, the adaptive latency):

  | Scenario | Steals | Clipped samples | Underruns (dropouts, silence) | Clicks |
  |---|---|---|---|---|
  | Endar Spire, 9,000 frames (5 min) | 936 → 0 | 390,786 (1.4 %) → 118 | 3 (2, 43 ms) → 21 on a busy machine, all after frames of 61-708 ms | 417 → 363 |
  | Upper City, six troopers (1 min) | 2 → 0 | 83,911 (1.6 %) → 20 | 1 → 1 (the first frames) | 5 → 8 |
  | Escape pod to Taris, busy machine (90 s) | 0 | 52,900 → 18 | 144 (150, 2.7 s) → 3 (1, 140 ms) | 218 → 52 |
  | the same, quiet machine, run in turn | 0 | 47,584 → 0 | 3 (4, 62 ms) → 0 | 56 → 51 |

  So of what was heard as cut-offs and weirdness, the voice stealing and the clipping were the
  mixer's own bugs on any machine; the underruns (no threads) only bite when frames run past the
  latency, which a busy machine or a heavy scene makes common and the adaptive latency now
  absorbs up to 250 ms frames.

  The mixer's thread (2026-10), against the frame-driven queue with its adaptive latency, the same
  runs (`sndrun`; `STALL=250` sleeps 250 ms more every 15th frame, as a heavy scene or a busy
  machine would):

  | Scenario | Frame-driven: underruns (silence) | Thread: underruns |
  |---|---|---|
  | Upper City, six troopers (1 min) | 0 | 0 |
  | Endar Spire, 6,000 frames (4 min) | 1 (9 ms) | 0 |
  | the fight, `STALL=250` | 34 (193 ms) | 0 |
  | the Endar Spire, `STALL=250` | 134 (852 ms) | 0 |

  The adaptive latency can't help a stall that comes now and then: it falls back between them, and
  each stall runs the queue dry again. The thread plays through them at its steady 60 ms. A third
  pass with `STALL=300` gave 0 underruns and 0 dropouts in both runs too.

## Open questions

- Whether Miles trimmed the MP3s' encoder delay (LIP timing would say, by 18 ms).
- The original's 3D rolloff and pan law (Miles with a 3D provider, or EAX), and how
  `Environment Effects Level` applies; ours are chosen, not measured. (`2D3D Bias` is read:
  re/app.md, "Voices".)
- `MaxPlaying` and `Interrupt` of `prioritygroups.2da` (re/app.md, "Voices") aren't enforced yet,
  nor `FadeTime`; the player's Sound Effects volume, which the original squares for 3D sounds,
  stays linear here.
- Whether Miles clipped or scaled a mix past full scale (ours limits it).
- The streams' loudness (music, the ambient bed, voice-over): whether `prioritygroups.2da`'s
  volume applies to them as to sound effects (0x005dc930 wasn't read that far).
- Which volume `prioritygroups.2da`'s distances override (they differ from the UTS's own).
