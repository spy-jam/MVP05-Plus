# MVP05-Plus

MVP Baseball 2005 on Windows and SteamOS, from [Mad Dog's](#credits) static recompilation of the Xbox game, with GameCube and PlayStation controllers played the way their own releases played them.

*MVP05-Plus is a working name.*

> **You need your own copy of the Xbox game.** No game files, game code or game art are included here or in any release. The installer builds everything it needs from your own discs, on your PC.

## What Plus adds

**Controllers**
- **GameCube controllers** through a Wii U / Switch GameCube adapter (official or compatible), all 4 ports, with rumble.
- GameCube stick, C-stick and trigger handling as the GameCube release does it. Hold X + Y + Start for 3 seconds to recentre.
- **PlayStation pads** with the PS2 release's stick handling, analog button pressure and rumble.

**Control layouts**
- GameCube controllers use the GameCube release's own control layout (for example, bunt is Z + A).
- PlayStation pads use the PS2 release's control layout.

**Button art**
- GameCube or PlayStation button pictures in the menus, help bars and in-game displays, picked from the controller connected when the game starts.
- Built by the installer from your own GameCube or PS2 disc. Optional: without them the game shows Xbox buttons.

**Fixes and extras**
- A fix for the stolen-base (baserunner) crash.
- **SteamOS / Proton:** a fix for the black screen, and the GameCube adapter through a small helper (`gcbridge`).
- A shader cache, so later runs don't stutter compiling shaders mid-game.
- Automatic save backups at startup.

## Install

1. Download `MVP05-Plus-Beta-1.zip` from [Releases](../../releases) and unzip it wherever you like. The game stays in that folder: nothing goes into Program Files, the registry or the Start menu, and deleting the folder removes it.
2. Run `MVP05-Plus-Tools.exe` and, on its *Install* tab, point it at:
   - **your Xbox disc image** (required): `.iso` (Redump), `.xiso`, or a folder of already extracted files (the one with `default.xbe`, or the folder just above it);
   - **your GameCube disc image** (optional, for GameCube button art): `.iso` / `.gcm`, or `.rvz` / `.gcz` / `.ciso` if Dolphin is installed;
   - **your PS2 disc image** (optional, for PS2 button art): `.iso`, or `.chd` if `chdman` is installed.

   The installer checks each disc is MVP Baseball 2005. It copies the Xbox game into `assets/`, and reads only the files the art needs from the GameCube and PS2 discs (it never copies those discs).
3. Run `MVP05.exe`.

**By hand, without the installer:** copy your extracted Xbox game files into `assets/`, with `default.xbe` directly inside it. To build button art by hand, see [Button art](#button-art-by-hand).

## Saves (experimental)

The *Saves* tab of `MVP05-Plus-Tools.exe` converts **dynasty saves** between the GameCube release and this game:

- **Import GameCube dynasty:** your `.gci` (exported from Dolphin's *Memory Card Manager*) replaces one of your dynasties here. The one it replaces is copied into `save backups` first. Start a dynasty in the game and save it once if you don't have one yet.
- **Export to GameCube:** one of your dynasties as a `.gci` for Dolphin to import. It needs any GameCube MVP 2005 dynasty `.gci` as a template, and a memory card with no other dynasty on it (a dynasty takes 197 of 251 blocks).

Tested on mid-season dynasties, loaded and played both ways. Playoff saves are untested. Close the game before converting. How it works: [`docs/SAVE-CONVERSION.md`](docs/SAVE-CONVERSION.md).

`tools/saves/standings_patcher.py` (Windows, Python) projects a short season's standings to 162 games in the running game's memory, for dynasties played with short schedules.

## Controllers

- **GameCube adapter (Wii U / Switch):** the official adapter, or a compatible one set to its *Wii U* mode if it has a switch (not *PC*). On Windows, give the adapter the WinUSB driver with [Zadig](https://zadig.akeo.ie/), the same as for Dolphin (select *WUP-028*, choose *WinUSB*, *Replace Driver*). Plug controllers into any port.
- **PlayStation pads:** connect them as usual (USB or Bluetooth).
- **Xbox-style pads:** work as in Mad Dog's original.

### SteamOS (Proton)

1. Copy the whole game folder to SteamOS and add `MVP05.exe` to Steam as a non-Steam game, run with Proton.
2. For the GameCube adapter: turn off Steam's own GameCube adapter support, and set the game's launch options to (with your folder's path):

   ```
   sh -c 'B="/home/deck/Games/MVP05-Plus/gcbridge"; chmod +x "$B"; "$B" & exec "$@"' sh %command%
   ```

   `gcbridge` reads the adapter on SteamOS itself, the way Dolphin does, and passes it to the game.

## Settings

`mvp05-settings.toml` beside the exe. Plus adds:

| Setting | Default | Meaning |
| --- | --- | --- |
| `gamecube_layout` | `true` | GameCube controllers use the GameCube release's control layout |
| `gamecube_icons` | `true` | Show GameCube button art when a GameCube controller is connected at start (needs `gc_icons/`) |
| `playstation_layout` | `true` | PlayStation pads use the PS2 release's control layout |
| `playstation_icons` | `true` | Show PS2 button art when a PlayStation pad is connected at start (needs `ps2_icons/`) |
| `save_backups` | `10` | How many save backups to keep in `save backups/` (0: off) |

## Building from source

Requires Windows x64, the Visual Studio C++ tools and Windows SDK, LLVM Clang/lld, CMake 3.25+ and Ninja (as Mad Dog's original). Put your extracted Xbox files in `assets/`, open an x64 developer prompt with `clang`, `clang++`, `cmake` and `ninja` on PATH, and run `Build-Source.cmd`. It builds `MVP05.exe` and copies Microsoft's `d3dcompiler_47.dll` from the Windows SDK beside it as `d3dcompiler_ms.dll` (needed under Proton).

### Button art by hand

Python 3 with Pillow and numpy (`pip install pillow numpy`):

```
python tools/gc_layout/make_icons.py assets/data <GameCube disc's data folder> gc_icons
python tools/ps2_layout/make_ps2_icons.py assets/data <PS2 disc's DATA folder> ps2_icons
```

Put `gc_icons/` and `ps2_icons/` beside the exe. Never commit them: they're made from game art.

## Documentation

- [`docs/MVP05-HANDOFF.md`](docs/MVP05-HANDOFF.md): how everything works, with code references and the full change history.
- [`docs/RELEASING.md`](docs/RELEASING.md): putting a release together on GitHub.
- `START-HERE.txt`, `SOURCE-MAP.txt`: Mad Dog's guides to the base project.

## Credits

- **Mad Dog (TGP482)**: the static recompiler SDK and the MVP Baseball 2005 recompilation this is built on.
- **MVP05-Plus**: James, with Claude (Anthropic).
- Third-party libraries: see `THIRD_PARTY.txt`.

## Legal

The SDK and this fork's code are MIT licensed (`SDK-LICENSE.txt`). MVP Baseball 2005 and its art belong to their owners; none of it is included. This project isn't affiliated with or endorsed by EA, Nintendo, Sony or Microsoft. Microsoft's runtime DLLs and shader compiler in releases are Microsoft's redistributable components, under their own terms.
