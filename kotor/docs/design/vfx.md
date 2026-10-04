# Visual effects and the look of a fight (lib/vfx)

What the player sees of a fight beyond the creatures' own animations: blaster bolts, muzzle
flashes, impact sparks, a lightsaber's blade, the power and grenade effects that come later. The
rules are in [rules.md](rules.md) and `lib/engine/fight.ctx`; how the original runs a round is in
[../re/combat.md](../re/combat.md). This page is the presentation: where each piece comes from in
the game's data, how the engine tells the screen, and how to add an effect.

| Where | What |
|---|---|
| `lib/vfx/vfx.ctx` | `vfx::Vfx`, a pool of 128 effects: making them, placing them, stepping them |
| `lib/vfx/draw.ctx` | the live effects' lights, meshes and particles into a `render::Frame` |
| `lib/vfx/notes.ctx` | outbox notes into effects: shots, `visual` rows, effect models |
| `lib/engine/fight_fx.ctx` | the fight's side: when a bolt leaves and lands, the sounds, `fight::visual_effect`, power visuals |
| `lib/engine/fight_voice.ctx` | creatures' battle cries, grunts and death cries |
| `lib/engine/fight_trace.ctx` | `--log trace`: one line per fighting creature every 6 frames |
| `lib/scene/visual.ctx`, `scene.ctx` | `scene::hook_of` (any node of an object's visual in world space), lightsaber blades, animation events |

## An effect is a model

The game makes every combat effect from an MDL: `w_laserfire_r` (a bolt), `v_muzflash_01` (a
muzzle flash), `v_blaster_imp` (a blaster hit), `v_grnfrag_fnf` (a grenade blast). Such a model
has emitters (particles), sometimes a light, sometimes meshes, and one animation (`impact`,
`travel01`, `default`) that keys the emitters' birth rates, colours and sizes. An emitter of
update type `Explosion` waits for the animation's `detonate` event and then bursts `birthrate`
particles at once; a `Fountain` or `Single` emitter gives birth continuously.

`vfx::Fx` puts such a model into the world: a scene part for its pose and animation (the scene
loads the model once; slots are reused for the same model), one `gui3d::Emitting` per emitter
(the same CPU particle simulation as the main menu and the minigames), and a placement:

| Kind | Placed | Used for |
|---|---|---|
| `still` | at a point, optionally turned so its +Y points along `facing` | an impact on the wall, a blast at a location |
| `follow` | riding a node of an object's visual (`scene::hook_of`), every frame | a muzzle flash on the weapon, an impact on a creature, a power's glow on a hand |
| `bolt` | flying from a point to a point over a time (`flight`), +Y along the way | a blaster bolt; later a grenade (add an arc) or a Force lightning bolt |

An effect lives for `life` seconds (its animation's length unless told) and then the particles
die out; a bolt ends on arrival and may play a `visualeffects.2da` row where it ends.

Particles are drawn as the seam's `render::Emitter`s: `Motion_Blur` and `Aligned_to_Particle_Dir`
stretch along `Particle.dir`. A bolt's emitter is turned to the direction of flight and its
quad made `speed * blurlength * 2.4` long and 1.6 times as wide as its `sizeStart` (ours: the
original's Motion_Blur rule was not read; the factors make a bolt read at fight distances).
Model lights (a bolt's red one, radius 2.5) are added as frame lights, so a bolt lights the
creatures it passes.

## The outbox notes

`lib/engine` never calls the scene. It posts notes (engine.md, "The outbox"), the game loop gives
them to `vfx::take` each tick, and `vfx::update` / `vfx::draw` run with the scene's sync and draw:

| Note | Meaning |
|---|---|
| `shot{ attacker, target, ammo, power, hand, flight_ms, result }` | a ranged attack fires one bolt from the weapon in `hand` (0 right, 1 left), arriving `flight_ms` later; `ammo` is the `ammunitiontypes.2da` row, `power` the power-blast model, `result` a `rules::outcome` |
| `visual{ effect, target, source, position }` | `visualeffects.2da` row `effect` on `target` at its hook, or at `position` when `target` is OBJECT_INVALID |
| `effect_model{ model, object, hook, position, life }` | a model by name (spells.2da's cast visuals) riding `hook` of `object`, or standing at `position` |
| `area_effect` | PlayVisualAreaEffect: a `visualeffects.2da` row at a point |
| `lightsaber{ id, forced, powered, transition }` | SetLightsaberPowered: `forced` fixes the blade lit or dark, else it follows combat |
| `play_sound` | a sound at a place; every effect's sound is one of these, made by the engine |

Sounds are not vfx's: the engine knows the weapon, the target's material and the table rows, so
`fight_fx.ctx` posts `play_sound` notes for them (shot sound at the shot, impact sound at the
hit, swing sounds from the animation's events, falls, voices). `fight::visual_effect{ effect,
target, source, position }` is the single call for a script-driven effect: the note plus the
row's `soundimpact`. Script `EffectVisualEffect` on an object (rules event `VISUAL_ON`) and on a
location (`ApplyEffectAtLocation`) both go through it.

## A ranged attack, as it plays

1. `fight::start_round` resolves all attacks of the round and the shots (weapondischarge.2da
   `shotN` times, `switchmask` digit per shot: `0` the left hand). Each impact keeps two times:
   `fire_ms` (the shot) and `at_ms` = `fire_ms` + the bolt's flight, 23.8 ms per metre
   (combat.md 3.3; clamped to 40 ms .. 1.5 s).
2. At `fire_ms`: `fight::fire_shot` posts `shot` and the weapon's firing sound
   (`ammunitiontypes.shotsound0`, `1` for power blasts). A shot that carries no attack of the
   round is a bolt that misses.
3. vfx makes the muzzle flash (`ammunitiontypes.muzzleflash`, riding the weapon's `bullethook`)
   and the bolt (`model0`, `model1` for power) from the `bullethook` to the target's
   `impact_bolt` node (the front of the chest). A miss flies on, aimed 0.4 to 1.0 m to one side
   and up or down, to the wall it hits (`scene::ray_hit`, at most 30 m), where
   `VFX_COM_BLASTER_IMPACT_GROUND` (4032) throws sparks.
4. At `at_ms`: the damage and the target's reaction, as before, and `land_ranged_fx`: the hit's
   `damagehitvisual.2da` ranged effect (Blaster: `VFX_COM_BLASTER_IMPACT`, 4024) on the target
   with `ammunitiontypes.impactsound0`; a deflected bolt `VFX_COM_BLASTER_DEFLECTION` (4023).

Blaster rifles shoot red bolts, ion weapons blue, disruptors white (ammunitiontypes.2da).

## Melee, sabers and sounds

- **Swings and falls** are the body animation's events: `Swingshort`/`Swinglong`/`Swingtwirl`
  play `weaponsounds.2da` `swingshort0..2` (etc.) of the weapon's row (`baseitems.weaponmattype`;
  a creature without a weapon uses its `appearancesndset.2da` weapon row), `snd_hitground` plays
  the appearancesndset `fall*` sound for the surface under the body. Footsteps (`snd_footstep`) are
  not played yet.
- **Hits** at the combatanimations hit time play the weapon's hit sound for the target's material
  (worn armour's `armortype`, else the creature's, else leather). A blow that was turned plays
  `parry0`, two lightsabers `clash0`, and throws sparks where the blades meet:
  `VFX_COM_SPARKS_LIGHTSABER` (4004) when a lightsaber is in it, else
  `VFX_COM_SPARKS_PARRY_METAL` (4011). There is no visual for a melee hit (damagehitvisual.2da has
  none), as in the original.
- **Lightsaber blades.** A weapon model with a `powered` animation is lit while its wielder is
  in combat or in a round (`powerup` then `powered`; `powerdown` then `off`, with the item's
  powerup/powerdown sound), lit at once for a creature met mid-fight; SetLightsaberPowered
  overrides. The blade itself is `lib/mdl_render`'s saber geometry scaled by those animations.
- **Voices.** `fight::bark` plays a slot of the creature's sound set (soundset.2da row, SSF of
  dialog.tlk strings, the string's voice-over file): a battle cry as the creature joins a fight,
  an attack grunt (half the rounds), a pain grunt (half the hits that do not kill), a shout at a
  critical hit, the death cry. A creature does not grunt twice within 1.5 s. Which slot sounds
  when is ours (ssf.md lists the slots). Sound uses no dice of the world (`fight::voice_hash`
  hashes the creature and frame) so what it plays cannot change the game at any `--speed`.
- A creature that made a **cutscene attack** keeps its weapon up for 6 s (the ready stance),
  and a killed creature plays its `die` animation to the end before `dead` (3 s).

## Adding an effect later

- A Force power or item ability: its `spells.2da` row names models (`conjheadvisual`,
  `casthandvisual`, `castgrndvisual`, `projmodel`). `fight::spell_visuals` already posts the
  conjure and cast visuals as `effect_model` notes at the caster's `headhook` / `handconjure` /
  feet. The impact script's own `EffectVisualEffect`s already play. What is missing is the
  projectile: the engine runs `fight::impact` at the end of the cast time, but the original
  delays it by the flight (actions.md, CASTSPELL: delay = d / v, v = 3 ln d + 2). To add it,
  post a note when the cast animation starts, let `vfx::spawn_bolt` fly the `projmodel` from the
  `projspwnpoint` hook (add an `arc` height to `Fx` for a grenade: `z += arc * 4 t (1 - t)`),
  and run the impact script when it arrives.
- A beam (`EffectBeam`, lightning): `vfx` has no beam kind; `Lightning` emitters are skipped by
  `gui3d::step_emitting`.
- A duration effect (`type_fd` D, a Force shield): one `follow` effect kept until the effect
  leaves the creature. `visual_on` plays every row once for now.
- A new placement is a `Kind`, a case in `vfx::step`, and a constructor like `spawn_follow`.

## Looking at it

`--log trace` prints the fight (every 6 frames: id, tag, position, animation asked for, hit points,
target, action, round timer, shots fired of the round, dead/dying/down), every sound the fight
makes (`sound NAME for ID`), every effect started (`vfx MODEL (slot) life L at X Y Z`) and each
animation a model lacks (`scene: no animation NAME on MODEL`; the creature then plays `pause1`).
Test input (`--input`, docs/playthrough.md): `FRAME cam duel TAGA TAGB [DISTANCE]` puts the camera
at the side of two objects (`pc` for the player), `cam at X,Y,Z X,Y,Z`; `FRAME fx visual ROW TAG`,
`fx at ROW X,Y,Z`, `fx model MODEL TAG [HOOK]`, `fx cast SPELL TAG` play an effect on the spot;
`kotor/tools/py/sheet.py` and `crop.py` tile and crop the screenshots for a frame strip.

```
sh kotor/tools/checkpoints/make.sh                      # once: kotor/out/checkpoints/bunk, bridge, ...
printf '8 ui giveitem g_w_blstrrfl001 1 equip\n10 warpxy 45.5,24.5\n12 cam duel pc end_sith3\n14 attack end_sith3\n' > shoot.txt
EXE=kotor/out/kotor_combat.exe FAST=1 SPEED=1 LOG=combat,trace LOAD=kotor/out/checkpoints/bunk \
  sh kotor/tools/playthrough/run.sh s1 shoot.txt 100 20:20 22:22 24:24 26:26
```

(`SPEED=1` so each screenshot is of its own tick; up to 16 screenshots per run, and none after
`--frames`.)

## Decisions (ours) and open items

- Bolt speed is the engine's 23.8 ms/m (42 m/s); the streak's length and width factors are ours.
- A shot of the round's animation that carries no attack is drawn as a bolt that misses.
- `switchmask` digit `1` is the right (on-hand) weapon and `0` the left: unconfirmed.
- Impact effects attach to `impact_bolt` (blasters), `DeflectHook` (deflection) or `Impact`
  (others); `imp_impact_node` is the model, falling back to the root nodes' models.
- The pool holds 128 effects; a spawn that finds it full is dropped and counted (`vfx:` line at
  the end of a run). A slot reused for a different model keeps its old part in the scene's
  arena until the area is left.
- Animations a model lacks fall back to `pause1` silently (the trace says which): `g2r2` on the
  humanoid skeleton and `cdodgeg` on the humans' (their reaction rows in combatanimations.2da).
- Not done: footsteps, melee blood (the game has none), beams, duration effects, thrown grenades
  and Force projectiles in flight (above), the Jedi's blade colours by crystal (blades show the
  model's own).
