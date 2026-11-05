# MVP Baseball 2005 PC recomp: GameCube and PlayStation controls, full handoff

This is for starting a new chat. Attach this file, the latest package (`mvp05-controls-v47.zip`) and, if you can, `mvp05-controls.patch`. Everything below describes what's in that package.

---

## 1. The project in one paragraph

The base is a static recompilation of the **Xbox** MVP Baseball 2005 (`default.xbe`, title 0x45410056) that runs natively on Windows. The source lives at `C:\MVP05\MVP05-Source-Build-Title-ID-Update`. Mad Dog is the person behind the recomp, and we're adding a mod for him.

On the input side, the mod lets you play with:
- **real GameCube controllers** on a USB adapter, controlling and looking like the **GameCube release**;
- **any PlayStation pad** (DualShock 3, DualShock 4, DualSense, or a PS2 pad on a PS3-type adapter), controlling and looking like the **PS2 release** (`SLUS_211.35`), including pressure-sensitive buttons where the pad has them.

Xbox-type and other pads are left exactly as the Xbox game has them.

**Scope rule:** this chat is controller-only. Display fixes (720p font sizes, 120 Hz smoothness, audio volume, the substitution popup's black backdrop, SteamOS) are deferred to a community decomp project. A 720p font fix was tried once (v30); it crashed the quick menu and was reverted in v31. Don't retry it.

---

## 2. How you build and install

1. Extract the zip over the source folder (it holds `src/`, `sdk/`, `config/`, `tools/`, the patch, and the two art folders).
2. In the **x64 Native Tools** command prompt:
   ```
   set PATH=C:\Program Files\LLVM\bin;%PATH%
   Build-Source.cmd
   ```
3. Put `gc_icons` and `ps2_icons` beside `MVP05.exe`, replacing old copies.
4. The settings file (`mvp05-settings.toml`) has four switches, all defaulting to true: `gamecube_layout`, `gamecube_icons`, `playstation_layout`, `playstation_icons`. It also has `save_backups` (default 10; 0 turns backups off).
5. The log (`mvp05.log`) is the main diagnostic. It records each controller plugged in, which layout each port got, which art folder loaded, and crashes.

There's no `fixes` folder any more (it came from the v30 font attempt). Delete it if it's still there.

**Mad Dog's package** (`MVP05-GameCube-Mod`, a README, a SUMMARY, the patch and the changed source) is still at **v24**, which is GameCube only. He gets the combined GameCube + PS2 update when the PS2 work is finished. The disc-derived art folders must **never** go into his repo. His README tells people to build the art from their own discs with the Python tools.

---

## 3. Where everything lives in the code

| File | What it does |
|---|---|
| `sdk/runtime/core/gc_adapter.cpp/.h` | Reads the GameCube adapter directly. |
| `sdk/runtime/core/input.cpp/.h` | Turns all controllers (SDL3 pads plus the adapter) into the Xbox controller report, runs rumble output, and keeps the screen awake while a controller is in use (v35). |
| `sdk/runtime/kernel/files.cpp`, `kernel.h` | "Disc overlay": art folders whose files replace the disc's files at the same paths. |
| `src/game/gc_controls.cpp/.h` | The main mod: per-port layout swapping, stick curves, PlayStation button handling, rumble rules, GameCube-only screen fixes. |
| `src/game/gc_layout_table.h` | The GameCube release's action table, generated. |
| `src/game/ps2_layout_table.h` | The PS2 release's action table, generated. |
| `src/common/game_info.cpp` | Wires in the hooks (`init`, `pad`, `window`, `rumble`) and the settings (the four layout/icon switches, plus `save_backups`). |
| `src/common/save_backup.cpp/.h` | Save backups at launch (v36): copies `hdd\E` to `save backups\<date time>\E`. |
| `config/game.toml` | The recompiler config, with the steal-crash fix added (see 4.6). In git the whole file shows as changed because of line endings, but the only real change is 4 lines. |
| `tools/gc_layout/` | The GameCube table extractor and `make_icons.py`, which builds `gc_icons`. |
| `tools/gc_layout/iconlib/` | Shared readers and writers for `.big` archives, refpack compression, Xbox/GameCube/PS2 shape sheets (`.xsh`/`.ssh`), and layout files. |
| `tools/ps2_layout/` | The PS2 table extractor and `make_ps2_icons.py`, which builds `ps2_icons`. |

---

## 4. GameCube work (v1–v24, confirmed working)

### 4.1 The adapter (`gc_adapter.cpp`)
- It supports the official Nintendo Wii U/Switch GameCube adapter (057E:0337) and compatibles.
- The adapter is read **directly over WinUSB**, with the Zadig driver, the same setup Dolphin uses. If WinUSB isn't available it falls back to Windows HID.
  - Endpoints: IN 0x81, OUT 0x02. Writing 0x13 starts reports; each report is 37 bytes.
  - Some adapters need a class request first, which is sent too.
- SDL's own GameCube driver is turned off, so pads don't appear twice.
- Dolphin and the game can't hold the adapter at the same time.
- **Stick processing matches the console:**
  - The resting point (origin) is taken when a controller is plugged in.
  - Holding X+Y+Start for 3 seconds re-centres, like a real GameCube.
  - The stick goes through the SDK's PADClamp (main stick radius 56, dead 15; C-stick 44/15).
  - Values are then scaled the way the GameCube game does it (main stick /55, C-stick /43, triggers clamped 30–180, then /150).
  - The result is that the Xbox game receives exactly the numbers the GameCube game worked with.
- **Rumble** is on/off only, as on the GameCube.
- **Polling rate:** a real GameCube polls about 1,140 Hz (`SISetSamplingRate(1)`). The official adapter runs at 125 Hz unless overclocked. You can't overclock because of Secure Boot, so you ordered an **Input Integrity "Lossless" adapter**. **Pending:** when it arrives, check that its USB endpoint numbers match. If not, read them from the device descriptor instead of assuming 0x81/0x02.

### 4.2 Controls: the action-table swap (`gc_controls.cpp`)
- The game keeps a table of 0x10B "actions" per controller: swing, pitch select, throw to base, menu accept, and so on. Each action is bound to one or two virtual buttons with a mode (press/hold/release/repeat/analog) and a combine rule.
- The Xbox build fills this table in its layout function, **0x2BF960** (pad vtable slot 39).
- We hook that function. After the Xbox layout runs we save the Xbox table. Then, **per port**, we write the **GameCube release's own table** whenever a GameCube controller is on that port.
- That table was pulled from the GameCube `main.dol` (layout function `fn_80008664`) by `tools/gc_layout/gc_extract.py` and `gen_table.py`. It's translated so each GameCube button lands where the report puts it: A=A, B=B, X=X, Y=Y, Z=White, L/R=the triggers with analog travel.
- `tools/gc_layout/gamecube_vs_xbox.txt` lists every action the two releases bind differently. Highlights:
  - B and X swapped in many places;
  - Z combos (Z+A bunt, Z+D-pad quick menu, Z+Start, Z+C);
  - the C-stick does the jobs of White/Black/stick clicks;
  - the fifth pitch is on R.
- Plug or unplug a controller mid-game and that port's table switches on the next poll (`AfterPoll`).

### 4.3 Stick curve
- The game shapes sticks in two modes, set by the current screen (flag at 0x635394):
  - **Mode 0 (menus):** identical on both releases.
  - **Mode 1 (play):** the Xbox uses dead zone 0.4 with the factor (m − 0.4)/0.6.
- The GameCube release, through a static-initializer ordering bug, ends up with **no dead zone** and the factor m + 0.2.
- We hand the Xbox poll a stick value pre-computed so that its output equals the GameCube curve (`XboxStickFor` inverts the Xbox curve).
- Triggers need nothing: both releases take (t − 0.4)·1.67.

### 4.4 GameCube-only behaviour fixes
These are hooks that apply only while a GameCube controller is in use:
- **Title screen ("Press Start"):** A does nothing; only Start continues, as on the GameCube (hook on 0x4BB110).
- **Attract demo and startup movies:** skip on Start only, not A/B (vtable slot swaps).
- **Replay:** Y hides or shows the panel. On the Xbox it's Black, which the GameCube table puts on the C-stick, so the C-stick was hiding it.
- **Sports Trax music box:** the C-stick alone skips songs, and **Z + C-stick moves the box**. That's real GameCube behaviour: the GameCube code throws away the box-move action unless action 0x1A (Z held) is on.

### 4.5 GameCube rumble rules
The GameCube release differs from the Xbox, and we reproduce it for GameCube players:
- every request goes to one motor, on or off only;
- a request is dropped while the motor runs or for 5 frames after the last one;
- the motor stops after 120 frames;
- some events are longer: the pitch cursor off the plate gives a 20-frame burst instead of 1, and an impact is 8 frames instead of 5.

Hooks: wrappers 0x198990/0x198A10, setters 0x2BF090/0x2BF0E0, per-frame update 0x2BEEA0.

### 4.6 Steal crash fix (`config/game.toml`)
- Stealing a base crashed with "indirect call to 000592A0".
- The handler is stored into a table at run time, so the recompiler never found it.
- Added `0x592A0` and `0x6FE40` as extra function entry points.

### 4.7 GameCube button art (`gc_icons`, built by `tools/gc_layout/make_icons.py`)
Usage: `python make_icons.py <Xbox data> <GameCube data> gc_icons` (needs Pillow and numpy). The game looks art up by name, so replacing files with the same names swaps the art. The script changes:
- **`shared.big` → `helpbuts.xsh` (help icons):** each Xbox button's icon becomes the GameCube button that does the same job, and the controller pictures (gpad, gpa2, gpdx) become the GameCube pad.
- **`igonly.big`:**
  - `ingameov.xsh`: the GameCube pitch-select diamond, PICK and STAMINA, with the fifth pitch top-right on R.
  - `replay.xsh`: the GameCube replay panel.
- **`igshapes/igcrsr.xsh`:** base runner and fielder diamonds in the GameCube arrangement (B third, Y second, X first).
- **`frontend.big` and `ingame.big` (screen layouts, `.fel`):** both releases ship the same layout files, with per-platform visibility flags on each element. Where the GameCube's elements sit differently, the Xbox elements take the GameCube ones' place. This covers the help bar, keyboard spacing, team select pads and arrows, Select Controller, the fifth pitch label, the cutoff prompt, argue/charge mound, and the draft Auto Finish box.
- **Loading screens `load0.big`–`load7.big`:** the GameCube controller diagrams.
- Works in 480p and 720p.

---

## 5. PlayStation / PS2 work (v25–v34)

### 5.1 Which pads count
- A pad counts as PlayStation when SDL3 reports its type as **PS3, PS4 or PS5**: a DualShock 3, DualShock 4, DualSense, or a third-party pad or adapter that identifies as one of those.
- All of them get the PS2 layout and the PS2 art.
- A GameCube controller always takes priority on its own port.
- **Not covered:**
  - Pads hidden behind Steam Input or DS4Windows look like Xbox pads, so turn those off for this game.
  - Generic PS2 adapters that report as an unknown joystick (see 6.2).

### 5.2 The PS2 action table
- It was extracted from the PS2 executable `SLUS_211.35`: MIPS, defaults function 0x43CF70, layout function 0x102F70.
- The tools are `tools/ps2_layout/ps2_extract.py` (a small MIPS interpreter) and `gen_ps2_table.py`, giving `ps2_layout_table.h`.
- The PS2 layout function has no option branches, so one table covers every game setting.
- PS2 channel numbers are translated to Xbox positions by place: Cross=A, Circle=B, Square=X, Triangle=Y, Select=Back, L1=LT, R1=RT, L2=White, R2=Black.
- `tools/ps2_layout/ps2_vs_xbox.txt` lists the 23 differences from the Xbox:
  - **Back/cancel is Triangle**, and Circle takes the Xbox Y's job (actions 0x002 and 0x004 swapped);
  - the fifth pitch and some "Black" actions move to **R1**;
  - the White-button combos move to **R2**;
  - the R1 combos move to **L2**;
  - 0x01A (Triangle + Cross held, a PS2 boot check) is read by nothing on the Xbox, so it's harmless.

### 5.3 Button handling (`PlayStation()` in `gc_controls.cpp`)
- **Shoulders:** SDL's mapping is Xbox-style, so the shoulders are swapped. L1/R1 go to the Xbox trigger channels; L2/R2 go to White/Black.
- **Pressure-sensitive buttons (DS3 and PS3-type adapters):**
  - SDL's PS3 driver exposes pressure as extra axes 6–15 (Cross, Circle, Square, Triangle, L1, R1, then the D-pad).
  - The PS2 game reads Cross, Circle, Square, Triangle and the four shoulders as 0–255 with no dead zone.
  - The Xbox poll subtracts a dead zone per channel (face buttons and White/Black (v − 0.3)×1.43, triggers (v − 0.4)×1.67). So a pressure p is sent as t + p/k, which comes out of the Xbox poll as exactly p.
  - The D-pad stays digital, as the Xbox's is.
  - `SDL_HINT_JOYSTICK_HIDAPI_PS3` is on. A real DS3 on Windows needs **DsHidMini in SDL mode**.
- **v32 changes:**
  - **Pressure fallback:** a pressed button whose pressure reads 0 counts as fully pressed, so pads that report empty pressure channels don't lose their buttons.
  - **L2/R2** go through the same no-dead-zone treatment on every PlayStation pad, so a DualSense/DS4 trigger registers from the first touch, as on the PS2. Before, they needed about 30% pull.

### 5.4 PS2 stick curve
- The PS2 play-mode curve: the stick byte minus 127; nothing inside radius 51 (0.40, the same as the Xbox's 0.4); scale (m − 51)·2/76, capped at 255 per axis.
- Applied through the same `XboxStickFor` inversion as the GameCube curve.
- The menu mode is identical, so the stick is left alone there.

### 5.5 PS2 rumble
- The PS2 drives only the DualShock's **big motor**.
- For PlayStation players, every request goes through one path at the PS2's strength:
  - pitch cursor off the plate: clamp(0.25v + 0.35, 0.35, 0.6) for 2 frames;
  - the two fielding events: 0.6 + 0.3x;
  - impact and the 0.3 event: unchanged.
- The output goes to the pad's low-frequency motor only (`gc::Rumble`).

### 5.6 Player lights (v32)
Each pad's player index is set to its port number:
- DS3: LED 1–4;
- DualSense: player lights;
- DS4: light bar colour per player.

### 5.7 Art selection at launch (`gc::Window`)
- At startup the mod waits up to 1 second for a GameCube controller to appear.
- If any GameCube pad is found (and its settings are on), `gc_icons` loads. Otherwise, if any PlayStation pad is found, `ps2_icons` loads. Otherwise the Xbox art stays.
- **The art is chosen once, at launch.** Controls follow each port live, but the art doesn't change mid-game.
- The overlay supports several folders (the first folder that has a file wins).
- There's a `g_booting` guard: the startup poll must not touch game memory. That was the v27 crash.

### 5.8 PS2 art (`ps2_icons`, built by `tools/ps2_layout/make_ps2_icons.py`)
- **Usage:** `python make_ps2_icons.py <Xbox data> <PS2 DATA> ps2_icons`.
- **PS2 decoder:** a new decoder for the PS2 shape format (`iconlib/ps2.py`) handles 8-bit, 4-bit and the GST 2-bit format, with palette ordering and swizzle.
- **Help icons:** these have the same names on both releases. The script copies them across (bu00 Cross, bu01 Circle, bu02 Square, bu03 Triangle, bu04–07 L1/R1/L2/R2, bq00 Select, bq01 Start) and stretches or centres the controller pictures (gpad/gpa2/gpdx).
- **Controller pictures (v34):**
  - **Green dots removed:** the PS2 sheet's gpad, gpa2 and gpdx carry green anchor dots around the pad's silhouette, which showed as green specks beside the pads and the CPU outline. `clean_markers` treats a greenish pixel within 2 px of transparency as a dot (the Triangle button, inside the pad, is kept). On the pads it takes the colour of its neighbours, so the rim stays whole; on the outline it's deleted.
  - **Outline refitted:** the PS2 outline fills its whole picture, while the pad's body covers only about 3–95% across and 2–85% down (the rest is drop shadow). Both are drawn in the same box (`pad_boxes`), so the outline's lower curve showed under the pad. `fit_outline` redraws the outline over the pad's body, 2.5% inside it, so a pad landing on a side now hides that side's outline. The CPU outline alone is a little smaller than before, the size of the pad body.
  - Both apply to every Select Controller screen: team select, in-game and the mini games.
  - The "P1" label still sits on the pad's top edge, where the layout puts it; the PS2's own minigame layout has the same 3 px overlap. Not changed.
  - The builder now needs numpy as well.
- **Pitch select** (ps00–03, PICK, STAMINA) and **replay** come from the PS2 sheets.
- **Base-runner diamonds** (`igcrsr.xsh`): Square, Triangle and Circle pictures from the PS2's `IGCRSR.SSH`.
- **Layouts (frontend.big, ingame.big):** the Xbox groups "adopt" the PS2 groups:
  - nav bars (`NAVGROUPPS2`);
  - keyboard nav bar;
  - HUD left/right shoulder labels;
  - bullpen;
  - overlay;
  - replay;
  - the controller-menu picture;
  - the Select Controller pad boxes (centred so the CPU outline doesn't show behind P1);
  - the draft's AUTOFINISH box.
- **Loading screens 0–7:** PS2 pictures decoded, resized to 1024×512 and re-encoded as DXT1.
- **Mini games (`minigame.big`, v33):** see 6.3.

---

## 6. Status and open items

### 6.1 Confirmed working
- **GameCube:** everything in section 4.
- **PlayStation:**
  - DualSense and DS4 both got the PS2 layout;
  - Select Team, Select Controller, pitch select and base diamonds look right;
  - "feeling great";
  - **Triangle cancels the name-entry keyboard.**

### 6.2 Built into v32 but untested
- Player lights.
- L2/R2 registering from the first touch on the DualSense and DS4.
- New log lines: each controller's type, axis count and GUID; any controller SDL sees **without a button map** ("has no button map, not used"); and `gamecontrollerdb.txt` loaded beside the exe, if present.
  - These are for testing a **PS2-to-USB adapter** and a **real DS3**. A DS3 or PS3-type adapter needs 16 or more axes for pressure.
  - Generic adapters may need a `gamecontrollerdb.txt` line, or may not appear at all (DirectInput is off). A setting to force a named pad to count as PlayStation is a possible follow-up.

### 6.3 Mini games (v33, built but not tested in game)
- **The finding:** all 35 layouts in `minigame.big` are byte-identical on the Xbox and PS2 discs. Like the other layouts, they carry per-platform visibility flags, so no PS2 art is needed: the fix is to show each screen the way the target platform shows it.
- **New function `as_platform(fel, p)`** in `tools/gc_layout/make_icons.py`, with `minigame(xb, p, extra)` around it. It's generic, not a hand-made list:
  - any group the Xbox shows and p hides, with exactly one sibling group that p shows and the Xbox hides, takes that sibling's place and content (as `adopt` does). Inside the copy, each element's Xbox flag becomes p's;
  - boxes and text (`RT`/`TB`/`TX`/`TL`) the Xbox and p show differently are shown as p shows them;
  - pictures (`SH`) are left alone, so the missing `XBOXL1`/`PS2L1` stay off;
  - for GameCube, `bu01`/`bu03` (and `bp01`/`bp03`) are swapped in everything the GameCube shows, the same swap the nav bar and overlay fixes use. The only uses are the nav bars and the fielding mini game's charge-mound button, which becomes B.
  - The build prints every change it makes.
- **Special cases:**
  - PS2 Select Controller (`fes_igminicontrolmenu.fel`): the PS2 group has only 2 rows, so the Xbox group keeps its 4 and gets `pad_boxes(..., 71, 42)`, as in game.
  - GameCube Select Controller: takes the `GCCONTROLLER` group, with gpad changed to gpa2, as in game.
- **What changes (PS2, 11 layouts):**
  - **Nav bar: "Circle Cancel" fixed.** The Xbox list has `bu01` (Circle in the PS2 art) in the Cancel slot; the PS2 list has `bu03` (Triangle).
  - **Pitching HUD (`fes_hudrightpmg`):** the fifth pitch moves to the top right, into the box above R1 (it was in the Xbox Black slot at the bottom, hence the blank box and SPL in the corner). The slot colours become the PS2's: Circle red, Square purple, Cross blue, Triangle green.
  - The same fifth-pitch move in the fielding HUDs (`fes_hudleft/rightfmg`), batting practice (`bpd`) and pitch show.
  - "Press Start" boxes (the PS2's string and box) in the `bmg`/`fmg`/`hrd`/`pmg`/`pshow`/`bpd` screens.
  - The cutoff prompt text in the fielding mini game.
- **What changes (GameCube, 13 layouts):** the same as PS2 with the GameCube groups and colours, plus:
  - the fielding HUD's pitch arrows (`NOTGC` takes `GC`: bu06 boxes);
  - Rumble for Vibration in the mini-game controller options;
  - the GameCube controller line in the mini-game options menu.
- **`iconlib/pack.py`:** `write_big` now puts the first file on a 4-byte boundary, as the discs do. Rebuilding an unchanged `minigame.big` now gives the disc file byte for byte. This also applies to the other archives the builders write; they were accepted before, and are now the same layout as the disc.
- `minigame.big` is optional for both builders: if the Xbox data folder doesn't have it, they say so and skip it.
- **To check in game, with a PS2 pad and a GameCube pad:**
  - every mini game's Select Controller (nav bar, pads);
  - pitching HUD;
  - fielding HUD;
  - home run derby and batting practice;
  - pause, controller and options menus (`igmini*`);
  - the tutorial (`mgtutorial`, no platform groups);
  - **and that Triangle really cancels** on the minigame Select Controller (the PS2 table says so).

### 6.4 Other open items
- In-game screens weren't machine-compared between PS2 and Xbox (only the 200 front-end screens were). Replay, pause, bullpen, pitch select, substitutions and play-select rely on testing.
- The HUD's `XBOXL1`/`PS2L1` shapes point at pictures ("L1", "l1_n") that exist in no file on either release. Dropped.
- Online-tip loading screens 49–58 mention Xbox Live; there's no PS2 equivalent. Low priority.
- Lossless GameCube adapter: verify the endpoints when it arrives (4.1).
- **Release plan (changed):** Mad Dog isn't taking the update, but he has given permission for a fork, which the MIT license (copyright TGP482) allows anyway. Plan: a GitHub fork of his recomp with our changes, released after more play-testing.
  - **His public release** (`MVP05-Public-Beta-3.zip`) ships `MVP05.exe`, the VC++ runtime DLLs (with `MICROSOFT-RUNTIME-NOTICE.txt`), `mvp05-settings.toml`, `SDK-LICENSE.txt`, `THIRD_PARTY.txt`, `START-HERE.txt`, `SHA256-MANIFEST.json`, and an empty `assets` folder for the user's Xbox files. A fork's release can follow the same layout.
  - **Never ship:** game files, or the `gc_icons`/`ps2_icons` art (it's derived from the discs).
  - **Installer idea:** a setup prompt where the user picks their Xbox ISO (required) and, optionally, the GameCube and PS2 ISOs. It extracts the Xbox files into `assets` and runs `make_icons.py` / `make_ps2_icons.py` locally to build the art folders. This needs an ISO reader for each format: Xbox XISO, GameCube GCM/ISO, PS2 ISO9660.
  - **README topics:** credit to Mad Dog's recomp; GameCube adapter setup (Zadig/WinUSB); which PlayStation pads work (turn Steam Input and DS4Windows off for this game); the four settings; asking for `mvp05.log` with bug reports.

---

## 7. Version history (short)
- **v1–v24:** the GameCube mod: adapter, table, stick, rumble, screen fixes, art, steal crash fix. Sent to Mad Dog as v24.
- **v25–v26:** the PS2 table, PlayStation detection, shoulder remap, PS2 rumble, pressure for PS3-type pads, PS2 stick curve (never built by you).
- **v27:** crashed at startup (startup poll read game memory). **v28:** fixed with the `g_booting` guard.
- **v29:** PS2 art complete, plus Select Controller pad-box centring.
- **v30:** a 720p quick-menu font attempt; it crashed. **v31:** reverted it, and kept multi-folder overlays.
- **v32:** player lights, pressure fallback, L2/R2 with no dead zone, controller diagnostics in the log, `gamecontrollerdb.txt` support.
- **v33:** mini games for PS2 and GameCube (`as_platform`, `minigame.big` in both art folders); 4-byte alignment of the first file in written `.big` archives. No C++ changes since v32.
- **v37:** build portability, no behaviour change. `gc_adapter.cpp` compiles to stubs off Windows, so Mad Dog's Linux test harness (`sdk/harness`, which builds every runtime file but `input.cpp`) still builds. The save-backup log lines print paths as UTF-8 text on every platform.
- **v38:** SteamOS / Proton black screen. Under Proton the system `d3dcompiler_47` is Wine's, which stops at the base recomp's `1.#INF` infinity literal, so every vertex shader failed and nothing drew (seen in the Steam Machine log). Two fixes in `sdk/runtime/gpu/d3d12.cpp` (Mad Dog's file) plus one in `Build-Source.cmd`:
  - `Build-Source.cmd` copies Microsoft's `d3dcompiler_47.dll` (Windows SDK redist, else System32) beside the exe as `d3dcompiler_ms.dll`. The game loads that first (`ShaderCompiler()`); Wine has no built-in of that name, so it loads Microsoft's as it is. Copy the folder to the Deck as it is, DLL included.
  - Without it, a compile that fails is retried with `1.#INF` spelled `asfloat(0x7f800000)`, then the largest float.
  - The log says which compiler it used (`d3d12: shader compiler ...`). Windows behaves as before.
- **v36:** save backups.
  - **When:** at every launch, before the game boots (first thing in the `init` hook).
  - **What:** `hdd\E` (UDATA, the saves; TDATA, the game's own data) is copied to `save backups\YYYY-MM-DD HH-MM-SS\E` beside the exe. A second instance (`--instance 2`, `hdd2`) gets `hdd2 <date>` folders.
  - **Unchanged saves:** if the saves match the newest backup, nothing is copied. Each backup holds `backup-contents.txt` (every file's path, size and time); it's written last, so only a complete copy counts.
  - **Pruning:** only the newest `save_backups` backups are kept (default 10; 0 turns it off). Only folders carrying that list are ever deleted, never the user's own folders.
  - **Errors** are logged and never stop the game from starting; a failed copy is removed.
  - **To restore:** close the game, then copy a backup's `E` folder over `hdd\E`.
- **v35:** keep-awake. Windows counts only the keyboard and mouse as activity, so the screen blanked during controller-only play. `NoteActivity` in `input.cpp` calls `SetThreadExecutionState(ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)` when any pad's input changes, at most every 5 s. That's a one-shot reset of the idle timer, the same as a mouse move, with no lasting request: put the controller down and the screen still turns off after the normal timeout. Stick changes under 3000/32767 and trigger or button-pressure changes under 24/255 don't count, so resting-stick jitter doesn't keep the screen on. Works for every pad type, GameCube adapter included.
- **v34:** PS2 controller pictures: green anchor dots removed, CPU outline refitted under the pad (`make_ps2_icons.py`, `ps2_icons/.../shared.big`).

- **v39:** the GameCube adapter search logs how many USB/HID devices it saw when it finds no adapter (for Proton). Under Proton the adapter can only come through as a HID device: launch option `PROTON_ENABLE_HIDRAW=0x057E/0x0337 %command%`, Steam's own GameCube support off, and the `hidraw` device readable by the user.
- **v40:** GameCube adapter under Proton. Wine's HID layer finds the adapter but refuses its 1-byte start report (error 87), so `gc_adapter.cpp` now opens the adapter's Linux hidraw node itself through Wine's Z: drive (`OpenLinuxHidraw`: found by `HID_ID=0003:0000057E:00000337` under `/sys/class/hidraw`), as Dolphin talks to it. Needs Steam's own GameCube support off; `PROTON_ENABLE_HIDRAW` isn't needed. On Windows nothing changes.
- **v41:** the hidraw start report is sent as 2 bytes (`13 00`): Linux's hidraw refuses writes under 2 bytes with EINVAL, which Wine reported as error 87.
- **v42:** diagnostics: the adapter's first 6 reads (and up to 20 odd-sized ones) go in the log as hex. On Proton (v41) it opened and took the start report but no controller ever showed up.
- **v43:** GameCube adapter under Proton through a Linux helper, `gcbridge` (source `tools/gcbridge/gcbridge.c`, a static Linux build beside the exe). v42 showed the hidraw route opens but never gets a report: Linux's hidraw can't send the adapter's 1-byte start report (2 bytes minimum), and the adapter ignores `13 00`. `gcbridge` talks to the adapter over usbfs as Dolphin does (detaches the kernel HID driver, claims interface 0, sends `13` on EP 02) and passes each 37-byte report to the game over UDP on 127.0.0.1:47337 (rumble back the same way). The game starts it by itself under Wine (`OpenBridge`, tried before hidraw); it quits 5 s after the game stops. It must be executable (`chmod +x gcbridge`). Build: `cc -O2 -static -s -o gcbridge gcbridge.c`.
- **v44:** `gcbridge` writes `gcbridge.log` beside the exe (USB devices seen, open/claim/start errors, the game's hello, the first report). With `gcbridge` present the game no longer falls back to hidraw (whose read never returns).
- **v45:** GameCube adapter under Proton, both routes reworked. **hidraw is first again, with the start report fixed:** a hidraw write starting `00` is a report without an id, and the kernel (`usbhid_output_report`) drops the `00` and sends the rest, so `00 13` reaches the adapter as the single `13` Dolphin sends (`13 00`, sent before, went as two bytes and the adapter ignored it; every earlier hidraw log opened and then logged no read at all). The hidraw node is read on its own thread with its own handle, so a silent adapter can't hang the loop: no report within 2 s (start sent twice) and it moves on to `gcbridge` for the session. **gcbridge:** it binds its port before opening its log, so a second copy exits without overwriting the first's log. It sends its log lines to the game (`GCL1` + text, put in the game's log as `gcbridge: ...`, with lines from before the game's hello buffered) and a heartbeat every second (`GCA1`). The game doesn't relaunch it while it's heard from, and deletes the old `gcbridge.log` before a launch. If the game hears nothing, it copies `gcbridge.log` into its own log, or says Wine never ran it and suggests the launch option `./gcbridge & %command%`. The bridge uses `USBDEVFS_DISCONNECT_CLAIM`, with the older disconnect and claim as fallback. Its log lines name the interface's current driver; on a failed open, the node's mode, owner and group against its own uid and groups (or that the node is missing in Steam's container); and on a failed claim, the processes holding the node. If no report arrives it resends the start (at 1, 2, ... s, five times), clears an IN stall, and gives the kernel driver back if the start fails.
- **v46:** v45's test: hidraw took `00 13` but sent nothing, and Wine said gcbridge "started" but it left no log and never answered. Wine starts a Linux program with fork and exec and calls it success once the exec is under way (Wine's `fork_and_exec`; no handles come back), so "started" proved nothing. Now: (1) the game starts gcbridge through `Z:\bin\sh -c '...' <unix path>` (path from `wine_get_unix_file_name`, else Z: stripped). The shell marks it executable when it isn't (no chmod by hand) and writes `gcbridge.out` beside it: that it ran, `ls -l`, the program's own lines (it copies each to stderr) and its exit code. If the game hears nothing in 4 s, `gcbridge.out` and `gcbridge.log` are copied into its log; if neither exists, nothing ran at all. Tested here with the exact command line split by Windows' rules, on a non-executable file in a folder with a space. (2) The game checks that the `gcbridge` beside the exe holds `GCBRIDGE-PROTOCOL-3` and says when it's an older one. (3) The bridge is tried before hidraw: SDL (it marks 057e:0337 as libusb-only) and Dolphin both drive this adapter only through libusb, never hidraw. hidraw is kept as a last resort and now logs what it reads. (4) The bridge finds its interrupt endpoints in sysfs (`ep_*/type`, `direction`), is built `-march=x86-64` (baseline ISA), waits 180 s for the first hello (so it can be started from Steam's launch options before Proton), and falls back to `/tmp/gcbridge.log`. Tested against a fake adapter (an LD_PRELOAD shim over sysfs, usbfs and ioctl): disconnect and claim, control 21/11/1, the 1-byte `13`, about 125 reports a second to the game, rumble out, the start resent when the first is ignored, and the driver given back at exit. Fallback that bypasses Wine and Steam's container: launch options `sh -c 'B="<full path>/gcbridge"; chmod +x "$B"; "$B" & exec "$@"' sh %command%`.
- **v47:** Last build before a long test (**needs a rebuild**). (1) **Shader cache** (`d3d12.cpp`, the SDK's renderer, the same code in 05 and 06): each compiled shader is saved in `shader_cache` beside the exe (`<key>.bin`: a 32-byte header with magic `MVCS`, version 1, the key, a hash of the bytes and their size, then the compiled shader) and loaded on later runs, instead of compiled the first time it's drawn every run (a hitch, slower under Proton). The key is the in-memory cache's hash (source, entry point, profile) salted with the format version and which compiler (`d3dcompiler_ms.dll` or the system's). A file that's missing, truncated, for another key or fails its hash is ignored and compiled and rewritten. Written to `.tmp` and renamed. The log says once that it's loading from the cache. Delete the folder to clear it. Tested here against stand-ins (save, reload, another compiler, a corrupted file, a truncated file, rewrite). (2) **Adapter under Proton, quieter:** the game stops starting gcbridge itself after 3 starts it never heard from (it still listens every second, for one started from Steam's launch options), and "adapter found (HID) but would not start", Wine's HID route refusing the start report every few seconds, is said 3 times, not all session. **Proton setup (works, James 2026-11-03):** Steam's GameCube support off, and in the game's Steam launch options `sh -c 'B="<game folder>/gcbridge"; chmod +x "$B"; "$B" & exec "$@"' sh %command%`. The game's own start of gcbridge under Wine never ran (Wine reports success at the exec; the cause wasn't found), so the launch option is the way.
## 8. Useful facts if the new chat needs to dig into the game code
- **Xbox pad object:** vtable 0x5ECEC0; the table is at +4, 16 bytes per entry: {int16 a, b, mode_a, mode_b, op, pad; float scale}; the port is at +0x1468.
- **Action reader:** 0x1990A0 (per player 0x199170). Player→pad lookup: `[0x657084 + 4·player]`, pads at `[0x6570A0]`.
- **Menu screens:** action n is handled at primary vtable slot 39+n on the Xbox (the code also uses "slot 3+n" from a different base). "Not handled" is 0x2BF340 (or 0x4B3FD0); "handled, nothing to do" is 0x24C950.
  - PS2: the screen factory is 0x1D3270, and the handler for action n is entry 40+n (8-byte entries).
- **PS2 pad poll:** 0x103670; channel = byte/255 (0x107E10); stick mode flag 0x7DD48C; rumble wrapper 0x4428A8.
- **Xbox analog dead-zone table:** 0x63EDAC, filled by 0x4405B0.
- **Layout files (`.fel`)** are refpack-compressed inside `.big` archives. Elements carry per-platform visibility flags, and the "adopt" approach copies a platform group's position and contents onto the Xbox group.

## Release work (Beta 1)

- **MVP05-Plus Tools** (`tools/installer/install.py`, built as `MVP05-Plus-Tools.exe` by `.github/workflows/release-tools.yml`): one window with two tabs.
  - *Install*: `tools/installer/discs.py` reads the discs with plain Python. Xbox XDVDFS (Redump images at the XGD1/2/3 game partition offsets 0x18300000 / 0xFD90000 / 0x2080000, xiso at 0, or a folder, also one level up), title check 0x45410056 from `default.xbe`'s certificate. GameCube GCM/FST, game ID GV4E69 (RVZ/GCZ/CISO/WIA through DolphinTool). PS2 ISO 9660, serial SLUS_211.35 from `SYSTEM.CNF` (CHD through `chdman extractdvd`). Only the 11 art files are read from the GameCube and PS2 discs, into a temporary folder that's deleted; the art builders run in-process (`main()` with `sys.argv` set). Tests on synthetic images: `tools/installer/tests/test_discs.py`.
  - *Saves (experimental)*: `tools/saves/saves05.py` around the GameCube <-> Xbox dynasty converters from the conversion handoff (`tools/saves/mvp05/`, written up in `docs/SAVE-CONVERSION.md`). Saves are in `hdd/E/UDATA/45410056/<12-hex>/` (`data.dat`, `SaveMeta.xbx` UTF-16LE with BOM, `saveimage.xbx`). Import replaces a chosen Xbox dynasty (it's the template; new folders are untested) after copying it into `save backups/<time> before GameCube import/`. Refuses while MVP05.exe runs. The three library files that opened their .json tables from the working folder now open them beside the module. Regression test with the user's reference saves: `python tools/saves/tests/run_tests.py <folder>` (3 MVP 2005 cases).
- `tools/make_release.py` packs the release zip like Mad Dog's Public Beta; `docs/RELEASING.md` has the GitHub steps.
- **Standings for short seasons** (Saves tab, *Standings…*). Two methods, same projection (`round(W / GP * 162)`, L = 162 - W, the 30 MLB teams):
  - *In the save* (`saves05.read_standings` / `patch_standings`, experimental): the standings table is the first post-roster per-team table, found by the key `6ABC3D69` (search from 0x12000 in the Xbox payload), then 126 x `[W][L][0][0]`, MLB teams first in the patcher's order (ANA ... PHI). Only those 120 bytes change; the save is re-signed (HMAC-SHA1, zero key) and backed up first. Season progress comes from the MLB schedule after marker 2 (u32 count, 28-byte entries, played when bits 11-15 of the u16 at +2 are non-zero). Refuses a save already at 162 games, a non-Dynasty save, a save whose signature doesn't check, or a table not shaped `[W][L][0][0]`. Not yet confirmed in game: that loading takes the table as stored (the memory patcher's results suggest it, since the save is the game's own copy of that table).
  - *In the running game* (`standings_mem.py` around the unchanged `standings_patcher.py`): the original scan (season length needed), cached address in `mvp_recomp_config.txt` beside the game, re-read before writing. The script still runs on its own.
