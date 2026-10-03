# Character generation (`lib/chargen`)

How New Game makes the player: the original's class selection, quick or custom character, portrait,
attributes, skills, feats and name panels, built over `lib/gui` and `lib/rules`, and the creature
they hand to the engine. What the original does is in [re/chargen.md](../re/chargen.md) (the
screens), [re/chargen-creature.md](../re/chargen-creature.md) (the creature that Play produces and
the saved player it matches) and [re/chargen-3d.md](../re/chargen-3d.md) (the 3D previews); the
rules numbers are lib/rules ([rules.md](rules.md)); the panels are the `.gui` files of
[gui.md](gui.md).

| File | What |
|---|---|
| `chargen.ctx`, `types.ctx` | `State` (everything one run holds), `begin`, `free`, the screens' ids, `Choices` |
| `screens.ctx`, `events.ctx` | the panel stack (`open_screen`, `bind_screen`) and every panel's events |
| `summary.ctx`, `portrait.ctx`, `name.ctx`, `abilities.ctx`, `skills.ctx`, `feats.ctx` | one file per screen's logic |
| `create.ctx`, `write.ctx` | the choices to a `rules::Creature`, and that to the bytes of a UTC-shaped GFF |
| `names.ctx` | the Random Name button: `lib/formats/ltr` and `namefilter.2da` |
| `data.ctx`, `util.ctx` | the 2DAs rules does not keep (classes' scores, portraits, appearance, heads, feat), small helpers |
| `preview.ctx` (`preview3d`), `views.ctx` | a player appearance in a GUI rectangle; the six class previews, the summary's and the portrait step's |
| `tools/chargentest` | the front end driven by a script of clicks, PNGs, and `verify:` of the finished player |
| `tools/chargenview` | one preview rendered to a PNG |

A program that links `lib/frontend` also links `lib/rules` and `lib/chargen` (the front end opens
character generation); `kotor/build.ctx`, `menutest`, `menurun` and `chargentest` do.

## The flow

```
main menu --New Game--> classsel (6 models) --pick--> maincg + qorcpnl (quick or custom)
    quick:  quickpnl  Portrait -> Name -> Play
    custom: custpnl   Portrait -> Attributes -> Skills -> Feats -> Name -> Play
```

`frontend::on_event` hands every GUI event to `chargen::on_event` while `Front.cg` is set;
`chargen::on_event` returns `running`, `finished` (the front end then returns
`Outcome::new_game{ module, player }`) or `cancelled` (the front end frees chargen and the main menu
is as it was). Each screen is a `.gui` panel opened with `open_screen`; the stack mirrors the GUI's.
`maincg` stays under the step panels; the three lists (`qorcpnl`, `quickpnl`, `custpnl`) are opened
in the new `gui::Mode::framed` (their file position inside the centred 640x480 frame, nothing
hidden below), the five steps full screen.

The screens follow the original's behaviour (re/chargen.md has the addresses):

- **Class selection.** Six buttons, left to right: male Scoundrel, Scout, Soldier, female Soldier,
  Scout, Scoundrel (`g_aClassSelSlots`, filled at start-up by the exe). Each model is a random
  `ForPC` portrait of the slot's gender, none twice in a gender, with the body of the class (Soldier
  large, Scout medium, Scoundrel small build, the portrait's three appearance columns). Hovering
  writes "Male Scout" and the description; the first button starts with the focus, so the screen
  opens with "Male Scoundrel". Clicking a button makes it the character.
- **Summary** (`maincg`): name and class, the portrait, the 3D character, the six base scores, defense
  (10 + DEX + class bonus), vitality (hit die + CON) and the three saves of the first level. The value
  labels are blank until Quick builds the character or Attributes is accepted. The level-up panel's
  old/new columns are hidden.
- **Quick or custom.** Only the current step's button is enabled. Back goes one step down (the custom
  list resets the character when it falls to Attributes); Cancel after the first step asks "Are you
  sure you want to cancel?". Play is enabled after the name. **Quick** applies the class's
  recommended build the moment its list appears: the six scores of `classes.2da`, the skills of
  `skills.2da`'s `<class>_reco` order bought to their cap, the first feat of `feat.2da`'s
  `<class>_recom` order that qualifies. We get that from `rules::prepare_auto_level` (the
  auto-leveller's record), which equals the original's by construction and by the numbers in
  re/chargen.md C.4 (Soldier: Treat Injury 4 and Rapid Shot; Scout: Computer Use, Demolitions,
  Repair, Awareness, Treat Injury 4 and Critical Strike; Scoundrel: Stealth, Demolitions, Security,
  Awareness 4, Treat Injury and Repair 2 and Dueling).
- **Portrait.** The 15 portraits of the gender in table order, arrows wrap, each press changes the
  body and the head at once; Back restores the portrait the panel opened with.
- **Attributes.** 30 points over scores of 8 to 18; a step costs 1 below 14, 2 for 14 and 15, 3 from
  16 (6, 8, 10, 13, 16 points for 14 to 18); lowering gives back what the step cost. Recommended (while
  points remain) sets the class's scores, which cost exactly 30 for all three classes. Accept with
  points left shows "You must spend all of your points."
- **Skills.** Points = max(4, 4 x (INT modifier + skillpointbase / 2)) (`rules::skill_points_for_level`);
  class skills cost 1, others 2; cap 4 and 2 at level 1. Accept with points left asks whether to keep
  them for the next level (the first level may end with some unspent).
- **Feats.** One regular feat at level 1 for every class. The list shows the feats the class grants at
  level 1 (dim), then the class's regular feats in chains by `successor`; ones failing a prerequisite
  are dim; Add/Remove toggles (`rules::meets_feat_requirements` decides); Accept needs all picks used
  unless nothing can be picked.
- **Name.** One edit box (18 characters), starting with a random name; Random Name draws a first and
  last name from `humanm`/`humanf` and `humanl`.ltr (the engine's Markov generator, `lib/formats/ltr`),
  refused when `namefilter.2da` lists it. The whole text goes in the first name; an empty name is
  refused ("You must specify a name.").
- **Force powers** are never chosen at creation (the powers panel has one caller, the level-up
  screen); no Jedi class is offered.

## The player it makes

`make_player` takes the choices, builds a `rules::Creature` the way the level-up screen applies a
record (`assemble`: a blank human with the chosen scores, then `rules::apply_level_up` with a record
of the class's full hit die, the chosen skill ranks and unspent points, the picked feats; the class's
level-1 grants come with it), and `write_player` writes it as a GFF (type `UTC `) with the fields the
original's character file has (re/chargen-creature.md 4.1), which are those of a saved game's
`Mod_PlayerList` entry: names, `Gender`, `Race` 6, `Appearance_Type`, `PortraitId` and `Portrait`,
`SoundSetFile` (85 male, 83 female), `ClassList`, scores, `SkillList` and `SkillPoints`, `FeatList`
(granted and picked), `LvlStatList` (one record: hit die, class, skill ranks, feats), hit points,
`GoodEvil` 50, `Experience` 0, `IsPC` 1, `FactionID` 0, head and colour fields, the 14 henchman
scripts. Hit points are written absolute (the original's are relative to the base and ignored for a
new player, who starts at full health); `rules::read_creature` and the engine's template reader both
read it. The creature has no items, no Force powers, no gold and no XP: **the exe gives none**. The
class kit (Soldier: blaster rifle and adrenal; Scout: pistol, adrenal, implant; Scoundrel: pistol and
the two spikes; a belt if Stealth was bought) is created into the footlocker `end_locker01` by the
module's own area script `k_pend_area01` when the player first enters, as is Min1HP; that is the
script VM's work.

The hand-off is the bytes: `Outcome::new_game{ module, player }` -> `modload::set_player_blueprint`
(game/play.ctx) -> `make_default_player` builds the PC from the blueprint when the first module
places the player. `Outcome.player` is owned by the front end's chargen state and valid until
`frontend::leave`; the engine copies it. Without chargen data (or on an error opening it) New Game
still starts, with the engine's default soldier.

## Decisions

- **The plus and minus buttons act on their own row.** The original's handlers act on the focused row
  and the code that moves the focus on hover is unsettled (re/chargen.md Open); a click on a row's
  button focuses and changes that row, which is what a player expects either way.
- **Message boxes hide the 3D previews.** They are drawn over the GUI (the labels have no fill); a
  box would be under them. The original draws a model inside its panel, in order.
- **No rotation.** The previews idle; the original's three previews do not turn either (re/chargen-3d.md).
- **No "feats granted" popup, no skills tutorial popup**; both are `skillinfo`/tutorial panels the
  front end cannot open yet.
- **A picked feat is yellow** in the list; the original's mark for state "chosen" is not in the data.
- **The random portraits come from `g.time`** (the front end's clock) as a seed, so scripted runs
  repeat and real runs differ.
- **`LevelRecord.feats` holds 8**, so `rules::read_creature` keeps the first 8 feats of the history
  record; the top-level `FeatList` is complete, and a new Soldier has ten feats (nine granted, one picked).
- **A new player is level 1 with 0 XP**; the HUD, levelling (an XP threshold) and the level-up panel
  are other leads'.

## Verification

```
kotor/tools/ctxc exe kotor/tools/chargentest -o kotor/out/chargentest.exe
sh kotor/tools/chargentest/selftest.sh             # every creation, a picture of every screen
kotor/out/chargentest.exe click:BTN_NEWGAME click:BTN_SEL3 ... verify:kotor/out/chargen/player.utc
```

`selftest.sh` makes the six quick characters (every class and gender), three custom ones (the
Soldier's scores bought by hand, two with the Recommended buttons) and a run that backs out and
cancels; PNGs of class selection, the quick-or-custom list, both step lists, portrait, summary, name,
attributes (with the "spend all your points" box), skills, feats, ready-to-play go to
`kotor/out/chargen/` (`menu_<name>.png`). After Play, `verify:` reads the written file back with
`lib/rules` and checks 32 things against numbers worked out from the 2DAs in the tool itself: race,
class and level, one history record, the portrait's sex and the body for the class, the sound set,
scores within 8..18 costing 30 points, maximum hit points (hit die + CON + Toughness), attack bonus,
the three saves, defense, the skill pool spent plus kept, the granted feats all present, one regular
feat picked from the class's list, no Force points. `verifyquick:` adds 15: the class's recommended
scores, skill ranks and feat for the quick character. All 10 runs pass (47 and 32 checks).
`game --input` with `FRAME newgame FILE` starts the engine with a created player: a female Scout
plays `end_m01aa` with her portrait's head (kotor/out/chargen/game.png).

## Not done

- The dark-side head textures and the idle fidgets (re/chargen-3d.md).
- The "feats granted" and the skills tutorial popups.
- Gamepad events (0x2d accept, 0x2e back) are not produced by the PC input layer.
- A saved player in the Load Game list is the save lead's; a new player's `Mod_PlayerList` entry is
  the `UTC` above plus what play adds.
