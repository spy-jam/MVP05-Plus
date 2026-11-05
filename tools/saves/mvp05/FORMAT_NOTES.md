# MVP Baseball 2005 dynasty save: GameCube vs Xbox format notes

Notes behind `mvp_gc2xb.py` (GameCube `.gci` -> Xbox `data.dat`, mid-season dynasty saves). Written so a later
session can pick the work up without redoing the reverse engineering. Offsets are for a fresh Dodgers dynasty
(`MATCHED` GC save / its Xbox template) unless noted; sections after the rosters move with roster size.

Evidence used: the GameCube decomp (`mvp2005-decomp-main`, struct layouts and stream code), three fresh
GC/Xbox dynasty saves (Dodgers, Yankees, Red Sox), the KC dynasty at April 2007 (two copies) and at the start of
2008, and a native Xbox Houston dynasty in its 2006 season (the only Xbox save with game-generated history,
trades and injuries). In-game tests on the recomp: v3-v15 builds, v15/v16 confirmed working mid-season.

## 1. Containers

| | GameCube `.gci` | Xbox `data.dat` |
|---|---|---|
| payload offset / length | 0x2138 / 0x186C00 | 0x108 / 0x222C00 |
| byte order | big-endian | little-endian |
| bitfields | MSB-first | LSB-first, same field order |
| checks | file starts `GV4E`; s32 at file 0x2084 = sum of the signed bytes 0x40..0x2083 (comment/icon area, contains the dynasty name, so it changes on rename); EA CRCs at 0x2088 for header body and payload | header + payload signatures (`containers.build_xbox` / `verify_xbox`) |

The payload is one continuous stream. Seven `0xBEEFF00D` markers (each followed by a u32) split it:
0 and 1 in the header, 2 = schedules, 3/4 = user section, 5 = player history, 6 = stream end (its value is
rewritten when the stream length changes; the trailing `55 BB` filler absorbs the difference).

Conversion rule of thumb: a field converts by its declared type. u32 -> swap 4 bytes, u16 -> swap 2, u8 and
byte arrays -> copy, bitfields -> same field values re-packed LSB-first. Every bug found in testing was a
field converted with the wrong one of these (4-byte swap over bytes or u16 pairs, raw copy over u32 keys).

## 2. Stream layout (GC offset / Xbox offset in the fresh pair)

| Section | GC | Xbox | Contents / conversion | Status |
|---|---|---|---|---|
| Settings header | 0x000-0x2D2 | 0x000-0x2CF | 72 ints (swap32); 2 flag bytes (GC has 3 pad bytes between); UTF-16 name buffer, 19 units (swap16); 2 ints; slider byte arrays (copy); 3 ints + marker 0 + value; 7 bytes (copy) | converted, exact on fresh pair |
| Org keylist | 0x2D2-0x47A | 0x2CF-0x477 | 34 x (key, idx, idx) | identical in every save, kept |
| Org records | 0x47A | 0x477 | 34 x 0x54 `Unk8052E9C4_Rec`: 14 ints, 16-bit bitfield group (1,5,3,1,2,3,1), 11 halfwords, last word (15,15,2) | converted (`structconv.ORG54`) |
| Team season records | 0xFA2 | 0xF9F | tag + 30 x 16 B `Unk8052F5CC_Rec` (7,7,7,7,4 / 7,7,7,7,4 / 7,7,7,11 / 11,21) + plain words + 1 byte-bitfield word + plain words | converted (that one word kept) |
| Team table | 0x1B42 | 0x1B3F | 126 x 60 B, 4 packed words | converted (`teamconv`, bit map learned on the fresh pair) |
| Roster blocks | 0x38CE- | 0x38CB- | 126 variable-length blocks, see 3.1 | converted |
| Post-roster tables | after rosters | | 3 per-team tables [tag][504 B]; keylist; 36 managers (48 B GC / 44 B Xbox) | converted, see 3.2 |
| Tagged tables | 25 tags `F58F3C1B` | | see 3.3 | converted |
| 1 KB block | tag 2 - 1056 | | zeros except: 80, 1, and one u32 that differs per dynasty and never changes during it (seed or creation stamp) | kept from template |
| 704 B block | before marker 2 | | identical in every save | kept |
| Schedules | marker 2 | | see 3.4 | converted |
| Trades / moves / injuries | after schedules (2870 B GC / 2798 B Xbox) | | see 3.5 | converted except 9 values |
| User section | marker 3, 4 | | m3 + u32 + 20 zero bytes; m4 + count (1) + **user team key** + UTF-16 profile name (swap16) | converted |
| Player history | marker 5 | | see 3.6 | converted |

## 3. Details

### 3.1 Roster block (per team, 126 teams: 30 MLB, 2 All-Star, minors, specials)
- 4 lineup units x 48 B: 10 bytes copy, u16, 9 x u32.
- 25 u32 player keys, u32 n, u32, then n u32 player keys.
- 5 "rings": [cap bytes of roster-slot indices][u32 count][u32 index]. The caps vary per team and are found by
  search; the block always ends in a 45-byte tail, which fixes the chain. All-Star teams 30/31 (fresh saves)
  and team 125 allow several chains, and all of them give byte-identical output.
- 45-byte tail: u8, 3 x u32, then 4 x (player key u32, return date u16 day number in a u32). This is the
  injured list. Copying it raw broke 21 players (they turned into free agents, with "D. Default" in their slots).

### 3.2 Per-team tables after the rosters (126 x 4 B each)
- Table 0: current record, bytes [W][L][0][0], same byte order on both platforms -> copy. (A 4-byte swap
  showed 10-0 as 0-10.) This is also the table the standings patcher edits in memory.
- Table 1: byte pairs -> copy.
- Table 2: last season's record as u16 W, u16 L -> swap16 each.

### 3.3 Tagged tables (tag `F58F3C1B` / Xbox `1B3C8FF5`, 25 of them)
- Tables 2-5: plain ints. Region 6-8: 404 B preamble + player keylist [n=3250][n][3250 x (key, row, row)];
  keys are sorted as signed ints.
- Table 8: 3250 player rows of 60 B (`Unk8008CE64_PackE`, `player_conv`). The row frame starts 23 bytes (GC) /
  24 bytes (Xbox) into the table and the last row wraps to the table start.
- Tables 9-15: per-player packs (PackF 16 B, 4 B words, `Unk80070004_Rec` 12 B), bit-permuted from the decomp
  structs (`bitconv`, `tablesconv.PM`).
- Region 16-18 (fixed 0x34288 B): Rec70004 table, 5 x 4 B word tables, 16 B `Unk80071170_Rec` table, an
  1800-entry stats keylist, PackD table (20 B).
- Tables 18-24: 1800 x 12 B season-stat packs (PackC/PackB/Pack). Player stats show correctly in game.

### 3.4 Schedules (marker 2) and the current date
- Four tables, MLB + three minor leagues, with fixed capacities 2442, 2172, 2140, 2112. Each is a u32 count
  followed by **all** capacity entries (the game streams the whole array, so the section size never changes;
  shortening it crashed the game).
- Entry 28 B: u16 day number (days since 1948-01-01, +1); 16-bit bitfield (10, 1, 5: the 5-bit field is
  non-zero once the game is played); 2 x side: team key u32, runs u8, hits u8, then 4 + 6 four-bit inning
  scores and a u8. The inning nibbles swap within each byte (MSB-first vs LSB-first).
- **The game has no stored "current date".** It uses the first unplayed game across the four tables. Converting
  only the MLB table left the minors at 2005, so the game showed April 7, 2005 and crashed on game start.

### 3.5 After the schedules (2870 B GC / 2798 B Xbox)
- 0: u32 trade count, u32 roster-move count, u32 0.
- 12: 30 x 42 B trades: 2 x (3 player keys, u8 count + 3 pad bytes, team key) + u16 date.
- 1272: 60 x 10 B roster moves: player key, team key, u16 date.
- 1872: u32 count + 32 x 20 B injuries: player key, u32, u32, packed word (1,1,6,6,6,6,6), u16 date, u16 date.
- 2516: object records whose sizes differ per platform (GC entries hold GC pointers 0x8068xxxx), kept from
  the template, ending in 9 x u16 (GC +2840, Xbox +2777). Those 9 are zero in fresh dynasties and filled after a
  season (KC: 38,66,26,99,22,8,93,11,24; Houston 2006: 40,156,60,220,48,16,205,17,44). Meaning unknown; kept as
  the template's zeros at the user's request.

### 3.6 Player history (marker 5)
- Groups: player key u32, u8 n, n x 20 B rows. GC keeps the last 6 rows per player, Xbox up to 16.
- Row (`Unk80082248_Rec`): link u32 (zeroed by the loader), u16 year, u8 team, byte bitfield (2,2,3,1), then
  3 packed words. The packing is not in the decomp; it was read off game-generated rows by bit frequency on both
  platforms, and matches all 5757 shared rows in the fresh pair exactly:
  - batter: (10,8,7,7) (9,8,8,7) (9,8,8,7)
  - pitcher: (8,8,9,7) (9,2,6,6,9) (7,25). The last 25 bits look like filler on both platforms.
- The converter keeps template rows older than the oldest GC row (pre-2005 real history is the same in every
  dynasty) and appends template-only groups.

### 3.7 Team / budget / user identification
- User team: the key in the marker-4 section (only place that differs between fresh saves of different teams).
- Budget: org record halfword s21, in $100K units (KC 877 = $87.7M). CPU teams change by fixed or small steps,
  the user team by performance. Using the template's 2005 budget against a 2007 payroll showed -$20M.
- Org bitfield f15 (5 bits) is set only on the user org (KC: 2 in April 2007, 3 at the start of 2008; Houston 1
  in 2006); probably contract year. Halfwords s27/s28 are set only on the user org (KC 52/276, Houston 1/160;
  0 at the start of 2008), meaning unknown. All of these are converted as plain fields.

## 4. Converter files (`lib/`)
`gc2xb_v0.py` (driver: replacement list applied back to front), `tablesconv.py` (tagged tables, header,
org/team-season records), `postconv.py` (schedules, user section, after-schedules section, history merge),
`histrow.py` (history row layout), `rosterblock.py`, `teamconv.py` + `team_bitmap.json`, `mgrconv.py` /
`manager_conv.py`, `player_conv.py` / `packe_decomp_layout.py`, `bitconv.py` / `fitstruct.py` +
`packstructs.json` / `allbitstructs.json`, `structconv.py`, `sched_conv.py`, `containers.py` /
`gc_checksums.py`. `hist_conv.py` is used only to parse history groups. Its learned bit map (`hist_maps.json`)
is superseded by `histrow.py`.

## 5. Xbox -> GameCube (`mvp_xb2gc.py`, `lib/xb2gc.py`)
Every section is converted with the inverse of the GC->Xbox rule. A GC dynasty `.gci` is the template for
the kept pieces (GC pad bytes, the per-dynasty word, the object block in 3.5) and for the memory card header.
History keeps the last 6 rows per player, as GameCube does. The stream-end marker value is its own offset + 4,
and the filler after it is `BB` at even and `55` at odd payload offsets. Checksums [0]/[1] are recomputed
(`gc_checksums`). Checks:
- Round trip GC -> Xbox -> GC on the three KC saves: identical up to the history section, except the
  template-kept pieces.
- History differs because GC->Xbox fills in older real-life seasons from the Xbox template. The GameCube save
  had already dropped them; KC had dropped them for 828 players.
- The fresh Xbox template, the native Houston 2006 dynasty and a converted save all built valid .gci files,
  and the GC->Xbox converter reads each one back.
- In-game test in Dolphin: works. The KC round trip, the Astros (native Xbox, 2006) dynasty and a renamed fresh save all load.
  Renaming needs the s32 at 0x2084 recomputed: without it the game says the file is corrupt.

## 6. Open items
- The 9 values in 3.5, s27/s28 and f15 in 3.7, and the per-dynasty word in the 1 KB block are unidentified.
- Only mid-season saves are tested. The game does not save in the offseason; playoff saves are untested.
- The team table map (`teamconv`) is learned, not from a struct: bits that were constant in the fresh pair
  are written as 0. No visible problem so far.
