# The data layer: resources and file formats

How the game turns the install's files into data: the resource manager that finds a resource by
name and type, and the readers (and writers) of the formats every subsystem loads through. Three
library directories, in dependency order:

| Directory | Namespaces | What |
|---|---|---|
| `lib/base` | `heap`, `le`, `resref`, `ci`, `text`, `path`, `lists` (and the render agent's `math`, `png`) | a general allocator, bounds-checked little-endian reads and writes, resource names, case-insensitive compares, the C-style text scanning the formats need, paths |
| `lib/formats` | `gff`, `gffw`, `twoda`, `tlk`, `ssf`, `lip`, `ltr`, `lyt`, `vis`, `txi`, `pth`, `ini` | parsers of bytes, and the GFF writer; no IO |
| `lib/res` | `restype`, `key`, `erf`, `rim`, `res`, `corpus` | resource types, the archive formats, the resource manager, the corpus walk for tests |

`lib/res` uses `lib/formats` (texpacks.2da and swkotor.ini choose the texture packs), so a program
that loads resources adds all three:

```
let exe = build::exe{ &b, name = "mdlview", root = "." }
build::add_sources{ &b, exe, dir = "../../lib/base" }
build::add_sources{ &b, exe, dir = "../../lib/formats" }
build::add_sources{ &b, exe, dir = "../../lib/res" }
```

The format docs these implement are `docs/formats/*.md`; every reader is run over every copy of
its format in the install by `tools/fmtcheck` (see [Verification](#verification)).

## Memory and ownership

Two allocators cover the game's lifetimes, both std `alloc::Fn`s:

- **`heap::Heap`** (`lib/base/heap.ctx`): the C library's malloc, realloc and free, holding the
  `Mem` capability. For memory whose lifetime isn't one arena's: the resource manager's index,
  tables loaded at start-up and kept, a module's data that lives until the module is left. It
  counts live bytes and blocks (`h.live`, `h.blocks`, `h.peak`), so a leak shows as a number that
  grows; fmtcheck mounts and unmounts every module and checks it comes back to the same count.
  Alignment up to 16 bytes (malloc's); more fails.

  ```
  let mut h = heap::new{ &mem }
  let bytes = try alloc::resize(u8, heap::Heap){ realloc = heap::alloc, heap = &h, mem = slice::empty(u8){}, count = n }
  ```

- **`arena::Arena`** (std): for anything parsed, used and dropped together: one resource load,
  one frame. Reset instead of freeing.

The rules every reader here follows:

- **Parsers take bytes and an allocator, and never trust the bytes.** Malformed or truncated data
  is an error value (`!T`), never a panic and never a read outside the buffer. Errors are each
  format's own (`gff::bad_value{ field }`, `le::truncated{ at, want }`, ...) and are printed with
  `@fmt` as their name and payload.
- **Parsed results are views into the bytes where they can be.** A `gff::Doc`'s strings and
  resrefs, a binary 2DA's cells and names, a TLK's texts are slices of the data you parsed, so
  the bytes must outlive the result. The arrays a parser builds come from the allocator you pass,
  and each format with arrays has a `free(S)` that gives them back (`gff::free`, `twoda::free`,
  `pth::free`); with an arena, just reset it.
- **Everything that is handed out to be freed is allocated at its exact size**, so
  `alloc::resize(T, S){ ..., mem = x, count = 0 }` (or `res::free_bytes` for heap bytes) frees it.

## lib/base

| Namespace | API |
|---|---|
| `heap` | `Heap { mem, live, blocks, peak }`, `new{ &mem }`, `alloc` (an `alloc::Fn(Heap)`), `MAX_ALIGN` |
| `le` | reading at an offset: `get_u8/u16/u32/u64/i16/i32/i64/f32/f64{ data, at } -> !T`, `get_bytes{ data, at, len }`, `fits`; in sequence: `Reader`, `reader{ data }`, `read_u8/.../f32{ &r }`, `read_bytes`, `skip`, `remaining`; error `truncated{ at, want }`; bits: `f32_of_bits`, `bits_of_f32`, ...; writing into a `list::List(u8, S)`: `put_u8/u16/u32/u64/i32/f32/bytes/zeros/padded`, and patching: `set_u16/u32` |
| `resref` | `ResRef { len, chars: [16]u8 }`, lower-cased, a value usable as a map key: `from{ name } -> !ResRef` (error `too_long`), `truncate` (directory names: the first 16), `from_field{ raw }` (a NUL-padded 16-byte archive field), `bytes{ r = &r }`, `eq`, `hash`, `matches{ r, name }`, `empty`, `is_empty` |
| `ci` | ASCII case-insensitive: `eq`, `starts_with`, `ends_with`, `find`, `compare`, `hash`, `lower` |
| `text` | `Lines`/`next_line` (CR LF, LF or CR), `Words`/`next_word`/`rest`/`count_words` (spaces and tabs), `trim`, `find_byte`; numbers as the engine's C reads them: `scan_int` (sscanf `%i`: `0x` hex, leading-0 octal, stops at the first bad character, wraps), `scan_decimal` (atol), `scan_f32`/`scan_f64` (`%f`, `.5`, `1e-007`), `float_prefix`, `is_float`, `is_integer` |
| `path` | `join(S)` (into memory from an allocator), `join_into` (into a buffer), `base_name`, `stem` and `extension` (by the first `.`, as the engine names directory files) |
| `lists` | `take{ list = &l }`: a list's items at their exact size, so the slice can be freed, the list left empty |

## lib/res: the resource manager

```
let mut h = heap::new{ &mem }
let mut rm = try res::open{ &fs, heap = &h, game = "F:/Steam/steamapps/common/swkotor" }
defer res::close{ &fs, &rm }

try res::mount_module{ &fs, &rm, name = "end_m01aa", save = "" }      // or a SAVEGAME.sav path
let git = try res::load{ &fs, rm, name = "m01aa", kind = restype::Type::git, realloc = arena::alloc, heap = &frame } ifnull {
    return no_area                                                     // null: no source has it
}
```

### Opening and mounting

- `res::open{ &fs, heap: *mut heap::Heap, game }` mounts, in the engine's start-up order:
  `Override/`; `chitin.key` with its 26 BIFs; `Override/textures.*` and `patch.erf`; the top level
  of `movies/`, `streamwaves/` and `streammusic/`; the texture packs that `texpacks.2da`'s row for
  `swkotor.ini`'s `[Graphics Options] Texture Quality` names (row 2, `swpc_tex_tpa`, in this
  install) and `swpc_tex_gui`. Directories and files are found ignoring case, so a case-sensitive
  file system works too. The heap must outlive the manager; `close` gives everything back.
- `res::mount_module{ &fs, &rm, name, save }` mounts a module as the engine does on entering it:
  `lips/<m>_loc` and `lips/localization`; `modules/<m>.mod` if there is one, else `<m>_s.rim`;
  then the module's own state: `<m>.sav` from the saved game at `save` if it holds one, else
  `<m>.rim` (none after a `.mod`). The module mounted before is unmounted first.
  `unmount_module` takes them all away. Fails with `res::no_module` if there is neither a `.mod`
  nor a `.rim`.
- `res::mount_texture_packs{ &fs, &rm, quality }` switches the packs (a Texture Quality change).
- `rims/` is never mounted: everything in it is in chitin too (resources.md, "Our engine").

### Finding and reading

The search walks five classes of source in order, each newest first, the first hit winning
(resources.md): **dir** (stream folders, then Override), **erf1** (patch.erf), **rim** (the
module's `.rim`, then `_s.rim`), **erf2** (a saved module state or `.mod`, lips, the GUI pack, the
texture pack), **key** (chitin's BIFs). `resls --sources` prints the order.

| Function | What |
|---|---|
| `find{ rm, name, kind } -> ?Loc` | where the search finds `name` (at most 16 bytes, any case) of type `kind`. A `Loc` is `{ source, member, size, class }`, valid while its source stays mounted (a stale one makes `read` fail with `res::stale`) |
| `find_ref{ rm, name: ResRef, kind }` | the same with a ResRef |
| `read(S){ &fs, rm, loc, realloc, &heap } -> !alloc::Bytes` | the resource's bytes, in memory from your allocator, yours to free. Only that member is read from its archive |
| `read_part{ &fs, rm, loc, offset, into } -> !usize` | part of a resource, for streaming |
| `load(S){ &fs, rm, name, kind, realloc, &heap } -> !?alloc::Bytes` | find and read; null when no source has it, an error when reading fails |
| `find_texture{ rm, name } -> ?Texture` | which form of a texture the engine loads, `{ kind, loc }`: the TPC if its source class ranks at least as high as the best TGA/DDS/4PC's, with directory > RIM > ERF > KEY, else the TGA |
| `list_type(S){ rm, kind, realloc, &heap } -> ![]mut Found` | every resource of a type the search can find, once each, with where it is found |
| `voice_path`, `music_path`, `sound_path` | the paths of stream files, which the engine opens by path, not through the search (voice-over in `streamwaves/<2-6>/<7-12>/` for 16-character `n...` names) |
| `source_path`, `member_file`, `member_of`, `class_name` | where a Loc is, for tools |

`restype::Type` is the engine's table of 87 types (`restype::Type::utc`, `twoda` for `2da`,
`fourpc` for `4pc`), with `of_id`, `of_ext` (ignoring case), `ext`, `is_gff`.

### Archives

The archive formats are their own namespaces, used by the manager and usable alone:
`key::parse` (chitin.key) and `key::parse_bif_header`/`bif_entry`; `erf::parse_header`,
`erf::parse_members`, `erf::parse` (an ERF in memory); `rim::...` the same. Each yields
`res::Member { name, kind, file, offset, size }`. `corpus::each` walks every copy of every resource
in the install (all texture packs, rims/, the saves and the module states nested in them) for
corpus tests.

**Writing an ERF** (saves): `erf::write(S){ realloc, &heap, sig = erf::Sig::mod, members:
[]erf::NewMember{ name, kind, data }, year, day }` lays it out as the engine writes saves (keys
with ResID = index, data packed in key order, DescriptionStrRef 0); names keep the case you give
(the engine writes `AVAILNPC0`, `END_M01AA` at a save's top level). `erf::write_index` gives just
the header and tables for members of given sizes, for an archive streamed to disk. Rebuilt from
their own members, the install's save and the module state inside it come out byte-identical.

## lib/formats

### GFF (`gff`, `gffw`)

```
let doc = try gff::parse{ data, realloc, &heap }          // validates everything once
let tag = gff::get_string{ doc, s = gff::ROOT, label = "Tag" } ifnull ""
let items = gff::get_list{ doc, s = gff::ROOT, label = "ItemList" } ifnull slice::empty(u32){}
let mut i: usize = 0
while i < items.len {
    let item = gff::get_resref{ doc, s = items[i], label = "InventoryRes" } ifnull ""
    i = i + 1
}
```

- Structs and fields are numbered as in the file; `gff::ROOT` is struct 0. Labels compare exactly
  (case matters); a struct may repeat a label (29 shipped dialogues do) and lookups take the
  first.
- Getters return null when the struct has no such label or the field has another type:
  `get_byte`, `get_char`, `get_word`, `get_short`, `get_dword`, `get_int`, `get_dword64`,
  `get_int64`, `get_float`, `get_double`, `get_string` (CExoString bytes), `get_resref`,
  `get_locstring` (`LocString { strref, count, body }`, with `loc_text{ ls, language, gender }`
  and `loc_substring`), `get_void`, `get_struct` (child struct), `get_list` (`[]u32` of element
  structs), `get_orientation` (w, x, y, z), `get_vector`; `get_number` takes any integer type.
- Generic walking: `fields_of{ doc, s }`, `label_of`, `kind_of`, `struct_id`, `find`, and
  `value{ doc, f } -> gff::Value`, a union with a variant per field type.
- Because `parse` checked every offset, getters can't fail or read outside the data.

Writing: `gffw::Builder(S)` records the order structs and fields are created in; `finish` lays out
the file. To write a GFF the way the engine writes its saves, create it depth first, each struct's
fields in the engine's order (the schema docs give it), and finish with `gffw::ENGINE`:

```
let mut b = try gffw::new{ realloc, heap = &heap, tag = "UTC " }
_ = try gffw::add_value{ &b, owner = gffw::ROOT, label = "Race", value = gff::Value::byte{ v = 6 } }
let items = try gffw::put_list{ &b, owner = gffw::ROOT, label = "ItemList" }
let e = try gffw::add_element{ &b, list = items, id = 0 }
_ = try gffw::add_value{ &b, owner = e, label = "InventoryRes", value = gff::Value::resref{ v = name } }
let child = try gffw::put_struct{ &b, owner = gffw::ROOT, label = "CombatInfo", id = 51882 }
let bytes = try gffw::finish{ &b, layout = gffw::ENGINE }
```

`gffw::copy_doc{ &b, doc, order }` replays a parsed file in the `dfs`, `elements` or `keep` order;
with the right `Layout { fi, li, late }` that gives back every GFF in the install byte for byte
(gff.md, "Writing files the way the game does").

### 2DA (`twoda`)

`twoda::parse{ data, realloc, &heap } -> !Table` reads the binary `2DA V2.b` form (with the NUL
separators of the rims/ copies) and the text `2DA V2.0` form an Override may hold.
`find_column{ t, name }` and `find_row{ t, label }` ignore case. `get_string`, `get_int`,
`get_float` (by column name) and their `_at` forms (by index) return null for a blank cell, a row
out of range or an unknown column; integers read as the engine reads them (`%i` in binary tables:
`0x1F` hex, `010` octal, a non-number 0; `atol` in text ones), so exptable's `0xFFFFFFFF` is -1.
`cell{ t, row, col }` is the raw text. Load the tables a subsystem needs once and keep them in the
heap; a binary table's cells are views into its bytes, so keep those too.

### PTH (`pth`), INI (`ini`)

`pth::read{ doc, realloc, &heap } -> !Graph { points: []Point { x, y, first, count }, links }` on a
parsed PTH; `links_of{ g, point }`. `ini::get{ data, section, key } -> ?[]u8` for swkotor.ini.

### TLK (`tlk`)

`tlk::load(S){ &fs, realloc, &heap, path } -> !Table` reads `dialog.tlk` (a file, opened by path:
`res::open` doesn't), `tlk::parse{ data }` makes a Table over bytes you hold; `free` gives back
what `load` read. Entries are read when asked for, not decoded up front:
`tlk::get{ t, strref } -> !?Entry { flags, text, sound, length }` follows the engine's StrRef
rules (0xFFFFFFFF is an empty entry; the top byte is dropped; past the end or on a 0x8000 hole is
null) and fails only for an entry whose text lies outside the file. `get_text` is just the text.
Text is raw bytes in the table's code page (`t.language`: 0-4 cp1252, 5 cp1250); `<token>`
replacement is the text layer's. `length` is 0 in every entry: take sound lengths from the WAVs.

### The small formats

| Namespace | Read | Result |
|---|---|---|
| `ssf` | `parse{ data } -> !SoundSet` | a value: the 28 StrRefs the engine reads; `get{ set, k }` (1..28) and `get_slot{ set, slot = ssf::Slot::dead }` give `?u32`, null for no bark |
| `lip` | `parse{ data } -> !Lip` | a view of the bytes, every key checked; `get_key{ l, i } -> Key { time, shape: lip::Shape }` |
| `ltr` | `parse{ data } -> !Table` | a view; `get_singles`/`get_doubles`/`get_triples` blocks, `get_value`, `pick`, and the engine's name generator `generate{ t, &rng, max_len, into }` with `seed_rng`/`roll_rand` (MSVC's rand) |
| `lyt` | `parse(S){ data, realloc, &heap } -> !Layout` | `rooms`, `tracks`, `obstacles` (`Placement { model: ResRef, x, y, z }`), `doorhooks` (quaternion w, x, y, z), `blanked` (`****` rooms skipped); `find_room`; `free` |
| `vis` | `parse(S){ ... } -> !Vis` | entries (`room`, its names) by indentation, `mismatches` (wrong or missing counts); `find`, `get_names`, `sees{ v, from, to }` (a room with no entry sees everything, vis.md's decision); `free` |
| `txi` | `parse(S){ ... } -> !Txi` | every keyword the engine reads as a value with the no-TXI defaults (`blending`, `mipmap`, `filter`, `clamp`, `cube`, `envmaptexture`, `bumpmaptexture`, `proceduretype`, `numx`/`numy`/`fps`, font metrics, glyph `upperleftcoords`/`lowerrightcoords`, ...); unknown keywords ignored, later repeats win; `defaults{}`; `free`. `txi::find_in_tpc{ data }` is the TXI text after a TPC's pixel data (`size_tpc_pixels` sizes that data, cube maps and flipbooks included) |

lyt, vis and txi copy what they keep (names become lower-case ResRefs), so their bytes can go;
lip and ltr are views of their bytes.

## How subsystems load resources

- **Open one manager for the program**, in `main` or the engine's start-up, with the heap, and
  pass it down read-only (`rm: res::Manager`) with `mut fs: Fs` where reads happen. Mount the
  module when entering it and unmount it when leaving.
- **A resource that becomes game data** (a blueprint, an area, a dialogue): `res::load` into an
  arena, parse, copy what the game keeps into its own structures, reset the arena.
- **A resource whose bytes stay** (a 2DA, a model's MDX, the TLK): load into the heap; free it
  when the owner (the game, the module) goes.
- **Textures**: `res::find_texture` gives the form and place; `res::read` the bytes; the TXI is
  `txi.md`'s rule: a `.txi` resource of the same name if `res::find` finds one, else the text after
  the TPC's pixel data (`txi::tpc_text`). TGA lightmaps come with standalone TXIs.
- **Models**: `mdl` and `mdx` of the same resref, both through `res::find`/`read`.
- **Sound**: `wav` resources through the search; voice-over, music and ambient streams by path
  (`res::voice_path`, `music_path`, `sound_path`), opened with `fs` directly. LIPs are in the lips
  archives mounted with the module.
- **Names**: keep resrefs as `resref::ResRef` (lower case, a value); GFF and 2DA give names as
  bytes in any case, and `res::find` folds them.

## Tools

| Tool | Run | What |
|---|---|---|
| `tools/resls` | `kotor/tools/ctxc run kotor/tools/resls -- [--module M] [--type EXT] [PATTERN]` | list what the search finds (`name.ext size class source`); `get NAME.EXT...` extracts; `--sources`; `--texture NAME`; `--crc` |
| `tools/gffdump` | `... gffdump -- [--module M] NAME.EXT\|FILE...` | a GFF as an indented tree |
| `tools/fmtcheck` | `... fmtcheck -- [--only census\|2da\|gff\|small\|erf\|res] [-v]` | the corpus test (below) |
| `tools/fmttest` | `... fmttest` | what the corpus can't test: the text 2DA form, building a GFF, writing an ERF, malformed input |
| `tools/basetest` | `... basetest` | lib/base on hand-made input |
| `tools/py/rescheck.py` | `python kotor/tools/py/rescheck.py LISTING [--module M]` | checks `resls --crc`'s listing against an independent Python model of the search |

Every tool takes `--game DIR` (default `F:/Steam/steamapps/common/swkotor`).

## Verification

`kotor/tools/ctxc exe kotor/tools/fmtcheck -o kotor/out/fmtcheck.exe` then `kotor/out/fmtcheck.exe`
walks every copy of every resource (the probes' `every_entry`) and reports, against the numbers
the Python probes give in `docs/formats/*.md` (all equal; about 3 seconds with a warm disk cache):

| Check | Result |
|---|---|
| corpus | 402 archives, 78,114 resource copies of 40 types |
| 2DA | 519 copies parsed, 0 failures, 317,162 cells, 26 NUL-separated; every cell equal to twodapy's (`tools/py/twodasum.py`: content sum fa6d6d65e5) |
| GFF | 11,152 files, 0 parse and 0 round-trip failures; 9,913 byte-identical in the engine layout, **11,152 byte-identical** with some setting, split by setting and file type exactly as gff.md's table |
| PTH | 132 files, 7,014 points, 15,134 links, 18 self links, 1 isolated point, 3 split graphs, 38 empty |
| TLK | 49,265 entries, 0 failures; flags 0x0007 48,560, 0x0006 398, holes 307; 32,853 sound resrefs |
| SSF / LIP / LTR | 316 / 18,206 / 3 copies, 0 failures; every LIP starts and ends at rest |
| LYT / VIS | 124 / 112 files, 0 failures; 1,401 room lines (134 `****`), 897 door hooks; 1,250 VIS entries, 8,905 room lines, 4 count mismatches |
| TXI | 5,616 standalone and 6,207 TPC-appended texts, 0 failures; 189 cube maps, 121 flipbooks |
| ERF | 130 archives rebuilt from their members: the save and its module state identical whole, every shipped one identical but for the DescriptionStrRef |
| res | all 117 modules mounted and unmounted, each finding its module.ifo, the heap back to the same live bytes every time |

And `tools/py/rescheck.py` checks the search itself: with no module, `end_m01aa` and `danm13`
mounted, every resource `resls --crc` lists (31,381, 34,429 and 35,146) has the source, size and
CRC an independent Python model of the engine's order gives.

## Not done yet

- Writing the module state of a save (CURRENTGAME, GAMEINPROGRESS) is stage 6; the pieces it
  needs (the GFF builder in the engine layout, the ERF writer) are here and checked.
- The TLK's token replacement (`<CUSTOMn>`, `<FullName>`) belongs to the text layer.
- `res` resolves the install's own directory names ignoring case, but not stream paths below
  `streamwaves/` (Windows doesn't need it).
