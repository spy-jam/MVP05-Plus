# MVP Baseball save conversion: handoff guide

This bundle documents and contains everything built so far to convert dynasty saves between platforms:

| Game | Directions | Status |
|---|---|---|
| MVP Baseball 2005 | GameCube `.gci` (Dolphin) <-> Xbox `data.dat` (recomp) | Both directions loaded and played in game (mid-season saves) |
| MVP 06 NCAA Baseball | PS2 `.psu` (PCSX2) <-> Xbox `data.dat` (recomp) | Both directions load in game; checked on fresh dynasties only |

It is written for whoever builds these converters into the recomp fork as a utility (you, or another Claude
chat). It explains the file formats, every conversion rule and why it exists, how the Python reference code is
organized, how to port and test it, and the mistakes that cost the most time. The Python code is the
**reference implementation**: a port is correct when it gives byte-identical output on the test vectors.

## Contents

| Path | What |
|---|---|
| `README.md` | this guide |
| `mvp05/` | MVP 2005 converter (both directions): `mvp_gc2xb.py`, `mvp_xb2gc.py`, `lib/`, `FORMAT_NOTES.md` |
| `mvp06/` | MVP 06 converter (both directions): `mvp06_convert.py`, `lib/`, `NOTES.md` |
| `tables/record_bitmaps.json` | exact GameCube->Xbox bit map of every fixed-size MVP 2005 record (for ports) |
| `tables/gen_bitmaps.py` | regenerates the JSON from the Python converters |
| `tests/test_vectors.json`, `tests/run_tests.py` | reference inputs (SHA-1) and expected outputs (file + payload SHA-1) |
| `tools/standings_patcher/` | MVP 2005 recomp memory patcher for short-season standings (related utility) |

Requirements of the Python reference: Python 3.8+, numpy (MVP 2005 only, for the bulk bit permutations).

---

## 1. Concepts that apply to both games

**Save = container + payload.** Each platform wraps the game's data (the *payload*) in its own file format with
names, sizes and checksums. The payload is one continuous **stream** written field by field by the game. It has
fixed total length per platform; the used part ends with an end marker and the rest is filler.

**Stream markers.** The value `0xBEEFF00D` appears 7 times in every payload and splits it into sections
(little-endian bytes `0D F0 EF BE`, big-endian `BE EF F0 0D`). Each marker is followed by a u32:

| Marker | Followed by | Section after it |
|---|---|---|
| 0, 1 | small values | settings header; then org/team/roster data and the tagged tables |
| 2 | MVP05: count of the first (MLB) schedule table | schedules |
| 3 | u32 | user section part 1 |
| 4 | u32 count (= 1) | user team key + profile name |
| 5 | u32 group count | player history |
| 6 | **its own offset + 4** | end of stream. Recompute after any length change |

**Tagged tables.** Many tables start with the 4-byte key `F58F3C1B` ("Default"). Searching for it finds the table
boundaries (MVP05: 25 hits after 0x5000; MVP06: 22). Two of the hits are not table starts but the Default key
inside a sorted key list; they move with content.

**Templates.** Both converters take an existing save of the *target* platform as a template. It supplies the
container (header constants, icons, file names) and the few payload blocks that cannot be converted or are
the same in every dynasty. Use a fresh dynasty as template where possible.

**Converting a field depends only on its type:**

| Field type | GameCube (BE) <-> Xbox/PS2 (LE) |
|---|---|
| u32 / s32 / keys | swap 4 bytes |
| u16 / UTF-16 text | swap 2 bytes |
| u8 / ASCII text / byte arrays | copy |
| bitfields | read every field's value MSB-first (GC), write LSB-first (Xbox), same field order |
| padding the compilers insert | add/drop (GC and PS2 pad where the Xbox stream is packed) |

Every bug found in testing was a field converted with the wrong rule from this table.

---

## 2. Containers and checksums

### 2.1 Xbox `data.dat` (both games)
```
0x00  20 B  HMAC-SHA1(key, file[0x50:0x108])        header signature
0x14  20 B  HMAC-SHA1(key, payload)                 payload signature
0x28  zero
0x50  header (0xB8 B): u32 header_end (=0x108), u32 payload_len, ..., u32 flags @+0x14,
      UTF-16LE name @+0x18 (32 B), UTF-16LE type @+0x38 (32 B), "name (type)" @+0x58 (64 B)
0x108 payload: 0x222C00 B (MVP05) / 0x212800 B (MVP06)
```
`key` is 16 zero bytes: the recomps use a zero `XboxSignatureKey`. A real console would need the title's key.
Code: `mvp05/lib/containers.py` (`build_xbox`, `verify_xbox`), `mvp06/lib/m06files.py` (`xb_build`, `xb_check`).

Save folder: `hdd/E/UDATA/<title id>/<12-hex folder>/` containing `data.dat`, `SaveMeta.xbx`, `saveimage.xbx`.
Title IDs: **MVP 2005 `45410056`**, **MVP 06 `4541008D`** (read from `default.xbe`).
`SaveMeta.xbx` is **UTF-16LE with a BOM**: `﻿Name=<name> (Dynasty)\r\n` (`containers.xbox_savemeta`). If it
is plain ASCII the game silently skips the save. Whether the recomp accepts a newly created folder name (rather
than an existing one) has not been tested.

### 2.2 GameCube `.gci` (MVP 2005)
```
0x0000  64 B   GCI directory entry: game id "GV4E", file name "Dynasty_<name>.dat" @0x08, block count @0x38 (u16 BE),
               comment line 2 "Dynasty-<name>" @0x64 ...
0x0040         card data: comment, banner and icon art
0x2084  s32 BE = sum of the SIGNED bytes 0x40..0x2083           <- changes when the name changes
0x2088  save header (0xB0 B):
        +0x00 4 x u32 BE checksums: [0] header body (+0x10..+0xB0), [1] payload, [2] icon, [3] banner
        +0x10 4 x u32 sizes (0xB0, payload_len, 0x840, 0x1840), +0x20 blocks, +0x24 flags (0x01101311)
        +0x28 UTF-16BE name (22 B), +0x3E UTF-16BE type, +0x94 ASCII file name
0x2138  payload 0x186C00 B; file padded to 0x40 + n x 0x2000
```
Checksums [2]/[3] are the same in every save (kept from the template). Recompute [0], [1] and the 0x2084 sum.
Without the 0x2084 sum, a renamed save shows as *corrupt*. Dynasty names are at most 10 characters.
A dynasty takes 197 blocks, so a standard 251-block card holds one.
Code: `containers.build_gc` / `parse_gc`, `gc_checksums.py`.

**EA checksum** (used by GameCube MVP 2005 and PS2 MVP 06; from the decomp, `fn_80400560`):
```c
uint32_t T[256];  // standard MSB-first CRC-32 table, poly 0x04C11DB7: T[i] = crc of (i << 24), shift left
uint32_t ea_crc(const uint8_t *p, size_t n) {
    if (n <= 3) return 0;
    uint32_t crc = ~((p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3]);   // first 4 bytes, big-endian
    for (size_t i = 4; i < n; i++) crc = ((crc << 8) | p[i]) ^ T[crc >> 24];
    return ~crc;
}
```

### 2.3 PS2 `.psu` (MVP 06)
A `.psu` export holds 512-byte entry headers (u16 mode, u16 attr, u32 size, ..., name at +0x40); file data
follows each file header, padded to 1024. The save folder `BASLUS-21367D...` contains `icon.sys`, `title.ico`, an
8-byte marker file and `<name>.sav`:
```
.sav: 0x00 4 x u32 LE EA checksums [header 0x10..0xC8, payload, title.ico, icon.sys]
      0x10 4 x u32 sizes (0xC8, 0x176800, len(title.ico), len(icon.sys)); then UTF-16 name/type, folder name
      0xC8 payload 0x176800 B
```
Code: `mvp06/lib/m06files.py` (`psu_parse`, `ps2_payload`, `ps2_build`, `ps2_check`). The converter keeps the
template's names. Renaming would also mean renaming the `.sav` entry and probably the folder, which is untested.

---

## 3. MVP 2005: GameCube <-> Xbox

Full detail with evidence: `mvp05/FORMAT_NOTES.md`. Summary in stream order, with the code that does it.
Offsets are payload offsets for the fresh Dodgers pair (GC / Xbox); later sections move with roster size and
are found by search.

| # | Section | GC | Xbox | Rule | Code |
|---|---|---|---|---|---|
| 1 | Settings header | 0x000-0x2D2 | 0x000-0x2CF | 72 u32; 2 flag bytes (GC: 3 pad bytes between); UTF-16 name (19 units); 2 u32; slider bytes copy; 3 u32 + marker 0 + value; 7 bytes copy | `tablesconv.header_rep` |
| 2 | Org key list | 0x2D2-0x47A | 0x2CF-0x477 | same in every save | kept |
| 3 | Org records 34 x 84 B | 0x47A | 0x477 | 14 u32, bitfield u16 (1,5,3,1,2,3,1), 11 u16, bitfield u32 (15,15,2). Budget = u16 #0 ($100K units) | `structconv.ORG54` |
| 4 | Team season records | 0xFA2 | 0xF9F | tag, 30 x 16 B bitfields (7,7,7,7,4 / 7,7,7,7,4 / 7,7,7,11 / 11,21), plain u32s, one byte-bitfield word kept | `tablesconv.teamflags_rep` |
| 5 | Team table 126 x 60 B | 0x1B42 | 0x1B3F | 4 packed words (learned bit map), 44 B text copy | `teamconv` + `team_bitmap.json` |
| 6 | Roster blocks x 126 | 0x38CE- | 0x38CB- | see 3.1 | `rosterblock.conv` |
| 7 | 3 per-team tables + key list + 34 managers | after rosters (key `693DBC6A`) | | table 0 (W,L,0,0 bytes) copy; table 1 copy; table 2 (u16 W, u16 L) swap16; key list swap32; managers 48 B GC -> 44 B Xbox | `gc2xb_v0`, `mgrconv` |
| 8 | Tagged tables 2-24 | tags | tags | see 3.2 | `tablesconv.table_reps` |
| 9 | 1 KB block before tag 2 | | | values 80, 1, one per-dynasty constant | kept |
| 10 | 704 B block before marker 2 | | | same in every save | kept |
| 11 | Schedules | marker 2 | | see 3.3 | `postconv.sched_rep_all` |
| 12 | Trades / moves / injuries / objects | after schedules (2870 B GC / 2798 B Xbox) | | see 3.4 | `postconv.tail_rep` |
| 13 | User section | marker 3-5 (420 B) | | swap32 up to the profile name, then swap16. Holds the **user team key** | `postconv.user_rep` |
| 14 | Player history | marker 5 | | see 3.5 | `postconv.hist_rep` + `histrow` |
| 15 | End marker + filler | | | value = offset + 4; filler `55`/`BB` | driver |

### 3.1 Roster block (per team; 30 MLB, 2 All-Star, minors, specials)
Blocks are found by a signature: each starts with 4 "lineup units" of 48 B whose bytes 10-11 are the uninitialized
u16 `BB55` (GC) / `55BB` (Xbox), followed by a small u32 (`SIG` regex in `gc2xb_v0.py` / `xb2gc.py`). Every 4th match
is a block start; the post-roster key `693DBC6A` ends the last one.
```
4 x lineup unit (48 B): 10 B copy | u16 | 9 x u32
25 x u32 player keys | u32 n | u32 | n x u32 player keys
5 rings: [cap bytes][u32 count][u32 index]   caps vary per team -> depth-first search (rosterblock._caps)
45 B tail: u8 | 3 x u32 | 4 x (u32 player key, u32 return date)  = injured list
```
The ring caps are not stored. The search tries candidate caps per ring (sets in `rosterblock.SETS`); a ring is
valid when its count/index words have zero high bytes. The block must end in exactly 45 bytes. Where several
chains are valid (All-Star teams in fresh saves, team 125), all give identical output.

### 3.2 Tagged tables
| Tables | Content | Rule |
|---|---|---|
| 2-5 | plain ints | swap32 |
| 6-8 region | 404 B preamble + player key list [n=3250][n][3250 x (key, row, row)] | swap32. Keys sorted as **signed** ints |
| 8 | 3250 player rows x 60 B | `player_conv` (bit map `player_row_60`). Row *frame* starts at +23 (GC) / +24 (Xbox) in the table body, frame byte 0 = GC byte at frame+60, and the last row **wraps** to the body start (`tablesconv.players`) |
| 9-15 | per-player packs (16 B, 4 B, 12 B rows) | bit permutation per row kind (`tablesconv.KIND`, `PM`) |
| 16-18 region (0x34288 B) | 12 B rows, 5 x 4 B tables, 16 B rows, 1800-entry key list, 20 B rows | `tablesconv.region16` |
| 18-24 | 1800 x 12 B season stat packs | bit permutation per kind |

### 3.3 Schedules (marker 2) and the current date
Four tables (MLB + three minor leagues), capacities **2442, 2172, 2140, 2112**. Each is a u32 count followed by
*all* capacity entries; the section never changes size.
```
entry 28 B: u16 day number (days since 1948-01-01, +1) | u16 bitfield (10,1,5; the 5-bit field != 0 = played)
            | 2 x side: u32 team key, u8 runs, u8 hits, 5 bytes of 4-bit inning scores, u8
```
Inning nibbles swap inside each byte. **The game stores no current date.** It is the first unplayed game across
all four tables, so all four must be converted.

### 3.4 After the schedules
```
0     u32 trades, u32 moves, u32 0
12    30 x 42 B trades: 2 x (3 player keys, u8 count + 3 pad, team key) + u16 date
1272  60 x 10 B roster moves: player key, team key, u16 date
1872  u32 n + 32 x 20 B injuries: player key, u32, u32, bitfield (1,1,6,6,6,6,6), u16 date, u16 date
2516  object records with platform-specific sizes and pointers: kept from the template, including the 9 u16 at
      GC +2840 / Xbox +2777 (zero in fresh dynasties, meaning unknown)
```

### 3.5 Player history (marker 5)
Groups: `u32 player key | u8 n | n x 20 B rows`. **GameCube keeps the last 6 rows per player, Xbox up to 16.**
```
row: u32 link (heap pointer; the loader clears it; write 0) | u16 year | u8 team | u8 bitfield (2,2,3,1)
     | 3 packed u32 words. Type = first 2-bit field: 1 batter, 2 pitcher
batter words:  (10,8,7,7) (9,8,8,7) (9,8,8,7)
pitcher words: (8,8,9,7) (9,2,6,6,9) (7,25)
```
Matches all 5757 shared rows of the fresh pair exactly. GC->Xbox also keeps the template's rows older than the
oldest GC row (real pre-2005 history, the same in every dynasty) and appends template-only groups. Xbox->GC
keeps the last 6.

### 3.6 Identifying data (for UI)
- User team: the u32 key in the marker-4 section (org key list maps keys to org index).
- Budget: org record u16 #0, $100K units.
- Standings: post-roster table 0 (current W/L bytes), table 2 (last season W/L).

### 3.7 Xbox -> GameCube
`lib/xb2gc.py` applies each rule backwards, keeps the GC template's pad bytes, the per-dynasty word and the
object block, writes the stream end, fills `BB` at even and `55` at odd payload offsets, and the container
builder recomputes the checksums. Round trip GC -> Xbox -> GC is identical up to the history section, apart from
the template-kept pieces.

---

## 4. MVP 06: PS2 <-> Xbox

Full detail: `mvp06/NOTES.md`. Both platforms are little-endian with LSB-first bitfields, so almost everything
is a byte-for-byte copy. Differences are only where the PS2 stream stores C struct padding and the Xbox stream
is packed:

| Where | PS2 | Xbox | Rule |
|---|---|---|---|
| header 0xF0 | u8 + 3 pad, char[32] roster name | u8, char[32] | copy fields |
| header after the name | 20 x u32 settings | 18 x u32 | which 2 are extra is unknown: keep the target template's |
| marker 1 + 0x12D4 | 16 conference records x 0x98: u8 id, char[13] short, 136 B, 2 pad | u32 id, char[12] short, 136 B | per field |
| marker 1 + 0x1B1C7 | 2 lists: u8 flag, 3 pad, u32 n, n x u32 | u8 flag, u32 n, n x u32 | drop/add pad |
| marker 2 + 0x195A0 | 16 B record (a,b,c,d) | (c,a,b,d) | reorder (c is a heap pointer) |
| end of marker-2 section | 18 B longer | | zero in fresh saves. A log there grows during play: **layout unknown** |
| end marker | offset + 4 | offset + 4 | recompute; filler `55` even / `AA` odd |

`m06.p2x` / `m06.x2p` assemble the target stream piece by piece; `Unsupported` is raised instead of writing a
bad file. Xbox dynasties with entries in the post-schedule log (Dyna1, Coyote06) are rejected until a progressed
PS2 save is available to compare.

---

## 5. Code walkthrough (Python reference)

### MVP 2005, GameCube -> Xbox (`mvp05/mvp_gc2xb.py`, `lib/gc2xb_v0.convert`)
1. Read the GC payload (0x186C00 at file 0x2138) and the Xbox template payload (0x222C00 at 0x108).
2. Build a list of **replacements** `(xbox_start, xbox_end, new_bytes)` in *template coordinates*, one per section
   (team table, rosters + post-roster tables, `tablesconv.table_reps`, schedules, user, after-schedules, history).
   Each section converter locates its source by markers/tags/signatures in the GC payload and its destination
   in the template.
3. Apply the replacements **back to front** (so earlier offsets stay valid while later sections change length).
4. Patch the end marker value by the total length change; trim/extend with filler to the fixed payload length.
5. `containers.build_xbox` writes header fields and both HMACs.

### MVP 2005, Xbox -> GameCube (`mvp05/mvp_xb2gc.py`, `lib/xb2gc.convert`)
Same replacement idea in GC template coordinates. History is built separately and appended, then the end marker
and filler. `containers.build_gc` sets names/sizes, the 0x2084 sum and checksums.

### MVP 06 (`mvp06/mvp06_convert.py`, `lib/m06.py`, `lib/m06files.py`)
Sequential assembly: copy ranges, transform the known records, finish with end marker + filler.

### Module map (MVP 2005 `lib/`)
| Module | Role | Port note |
|---|---|---|
| `containers.py`, `gc_checksums.py` | file wrappers, checksums | straightforward |
| `gc2xb_v0.py`, `xb2gc.py` | drivers | port the section order and the back-to-front apply |
| `tablesconv.py` | header, org, team-season, tagged tables, region 16 | row kinds -> use `record_bitmaps.json` |
| `player_conv.py`, `packe_decomp_layout.py` | 60 B player row | bitmap `player_row_60`, plus the frame/wrap logic |
| `teamconv.py` + `team_bitmap.json` | team row | bitmap `team_row_60` |
| `structconv.py` | generic struct spec (org) | bitmap `org_record_84` |
| `mgrconv.py`, `manager_conv.py` | manager 48 <-> 44 B | bitmap `manager_record_48_to_44` |
| `rosterblock.py` | roster blocks | port the ring search as is (small DFS) |
| `sched_conv.py`, `postconv.py` | schedules, user, after-schedules, history | bitmaps `schedule_entry_28`, `trade_42`, `roster_move_10`, `injury_20`, `history_row_20_type*` |
| `histrow.py`, `hist_conv.py` | history rows / group parser | `hist_maps.json` is obsolete (replaced by `histrow`) |
| `bitconv.py`, `fitstruct.py`, `packstructs.json`, `allbitstructs.json` | build bit permutations from decomp structs | not needed in a port: use `record_bitmaps.json` |
| `pconv.py`, `sections.py` | older helpers | not needed |

### Using `record_bitmaps.json` in a port
Bit numbering on both sides: `bit = byte * 8 + b`, `b = 0` is the least significant bit of the byte.
`map[g]` is the Xbox bit for GameCube bit `g`, or `-1` (dropped: padding, or team-table bits never learned).
```c
void convert_record(const uint8_t *gc, uint8_t *xb, const int16_t *map, int gc_len, int xb_len) {
    memset(xb, 0, xb_len);
    for (int g = 0; g < gc_len * 8; g++)
        if (map[g] >= 0 && (gc[g >> 3] >> (g & 7) & 1)) xb[map[g] >> 3] |= 1 << (map[g] & 7);
}
```
Xbox -> GameCube uses the inverse map. The history maps exclude the 2 type bits: GC byte 7 bits 6-7 go to Xbox
byte 7 bits 0-1 (choose the map by the type value first), and the link (bytes 0-3) is written as 0.
The maps were checked against the converters on real data: 126 team rows, 3250 player rows, 2442 schedule entries
and 12375 history rows from the KC save, 0 mismatches.

---

## 6. Integrating into the recomp fork

Suggested shape (adapt to the fork's code):
1. **Entry point:** a host-side utility in the recomp (menu item or command-line option such as
   `--import-gci <file>` / `--export-gci <folder>`) that runs while no game is running.
2. **Paths:** the recomp already knows its emulated drive. Write to `hdd/E/UDATA/<title id>/<folder>/`. Safest is
   to overwrite a chosen existing dynasty folder; creating a new 12-hex folder needs a test first.
3. **Template:** pick an existing dynasty in the same `UDATA/<title id>` (scan `SaveMeta.xbx` for "(Dynasty)"), or
   ship a fresh dynasty save with the fork. Copy its `saveimage.xbx`; write `SaveMeta.xbx` as UTF-16LE with BOM.
4. **Back up** anything overwritten (`.bak`), as the Python tools do.
5. **Port vs embed:** porting to C++ with the bitmaps is about 1-2k lines. Alternatively, ship the Python tools and
   call them. Either way, check the result with the test vectors (section 7).
6. **Report errors, never write partial files:** every converter asserts its assumptions (section sizes, counts,
   capacities). Keep those checks in a port and show the message to the user.

---

## 7. Testing

`python tests/run_tests.py <folder with the reference saves>` runs six cases:
- 3 MVP 2005: GC->Xbox KC, Xbox->GC round trip, native Xbox Astros->GC.
- 3 MVP 06: PS2->Xbox, Xbox->PS2, Xbox Dyna2->PS2.

Each case is compared with a file that was loaded in the real game: either byte-identical, or with identical game
data and only the save name differing. Input SHA-1s are checked first. A port should produce the same
`payload_sha1` (and `file_sha1` when names match). The reference saves are the user's own files listed in
`test_vectors.json`.

In-game checks that found real bugs (do these after any change): load the save; date and next game; user team;
budget; standings; free agent list (no "Default" players); injured players on rosters; a game started and played.

---

## 8. Lessons and pitfalls (what each one cost)

| Symptom seen in game | Cause | Fix |
|---|---|---|
| Game crashed on load (schedule-only build) | schedule section shortened | streams always hold full capacity |
| Date showed April 7 2005, crash at game start | only the MLB schedule converted | convert all four schedules (date = first unplayed game) |
| Crash entering a game | header settings written 3 bytes off | header field map (`header_rep`) |
| Real players became free agents, "D. Default" in slots | 45 B roster tail copied raw (player keys unswapped) | tail = u8 + u32s |
| Standings 10-0 shown as 0-10 | byte table converted with a 4-byte swap | copy bytes; u16 pairs swap16 |
| Wrong inning scores | nibbles not swapped within bytes | nibble swap |
| -$20M budget | org records kept from the template | convert org records |
| Still the template's team | user key in the marker-4 section kept from template | convert user section |
| Renamed GC save "corrupt" | 0x2084 byte sum not updated | recompute it |
| Xbox save missing from the load list | SaveMeta.xbx not UTF-16 | write UTF-16LE with BOM |
| GC "no dynasty detected" | a test file was left on the full card | one dynasty per 251-block card |
| MVP06 PS2 progressed saves rejected | unknown log layout | needs a progressed PS2 save |

Other things learned:
- "Matched" saves made separately on two platforms do not have identical content (random seeds, generated
  players). Compare layouts by structure, not by expecting equal bytes.
- Fresh saves leave many sections empty. A conversion that works on fresh saves can still be wrong mid-season, so
  test with progressed saves.
- Heap garbage after the stream end (MVP06) and uninitialized pad bytes (`BB55`, `CDCD`) are normal and harmless.

## 9. Open items
- MVP 2005: 9 unidentified u16 values (kept as template zeros); org fields s27/s28/f15 converted but unidentified;
  team table bits never learned are written as 0; playoff saves untested.
- MVP 06: needs a progressed PS2 dynasty to finish the post-schedule log and to confirm history/stat sections;
  2 PS2 settings values unmapped; save renaming not supported.
- Both: creating new Xbox save folders untested.
