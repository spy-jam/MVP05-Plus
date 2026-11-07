# MVP05-Plus Beta 1

First release of MVP05-Plus by spy_jam, built on Mad Dog's MVP05 Public Beta 3 recompilation.

## New
- **GameCube controllers** through a Wii U / Switch GameCube adapter (official or compatible, in Wii U mode), all 4 ports, with rumble. Stick, C-stick and triggers handled as the GameCube release does. Hold X + Y + Start for 3 seconds to recentre.
- **PlayStation pads** with the PS2 release's stick handling, analog button pressure and rumble.
- **Native control layouts:** GameCube controllers use the GameCube release's layout, PlayStation pads the PS2 release's.
- **Button art:** GameCube or PS2 button pictures in menus, help bars and in-game, picked from the controller connected at start. Built by the installer from your own discs (optional).
- **MVP05-Plus Tools** (`MVP05-Plus-Tools.exe`), the installer: copies your Xbox game into `assets/` and builds the button art from only the files it needs on your GameCube and PS2 discs. Portable: everything stays in the game folder. Once installed, it opens on what's installed (checked each time) with a Launch button.
- **Shader cache** in `shader_cache/`, so shaders compile once instead of every run.
- **Save backups** at startup, in `save backups/` (15 kept by default), listed in the Tools' *Saves* tab, where you can restore single saves or a whole date.

## Fixed
- The stolen-base (baserunner) crash.
- SteamOS / Proton: the black screen; the GameCube adapter through `gcbridge` (see the README for the launch option).

## Known issues
- Under Proton, the GameCube adapter needs the Steam launch option; the game can't start `gcbridge` by itself yet.
- Display issues from the base recompilation (for example 720p fonts) are unchanged.

## Requirements
Windows 10/11 x64 (or SteamOS with Proton), a D3D12 GPU, and your own MVP Baseball 2005 Xbox disc image. GameCube and PS2 discs are optional, for button art.
