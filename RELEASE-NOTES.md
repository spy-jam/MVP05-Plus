# MVP05-Plus Beta 2

Work in progress: more is coming before this is released.

## New
- **Updates from the Launcher:** *Settings → Updates* shows your version, checks GitHub for a newer release (also when the Launcher opens, unless you turn that off), shows what's new, and installs it: the program files only, checked against the release's manifest. Your game files, saves, backups, button art and shader cache are never touched; your settings are kept, with any new options added. *Back to* undoes the last update. From Beta 2 on: going from Beta 1 to Beta 2 is still by hand.
- **Tools menu in the game:** F10, or hold Back + Start (Z + Start on a GameCube controller) for a second. Any controller or the mouse moves around it, and the game gets no controller input while it's open. Esc closes it.
  - *Short season:* at the end of a season shorter than 162 games, it finds the standings in the game and writes them projected to 162 games, as the standings patcher does, so the season can go on to the playoffs. The season length comes from `season_games` in `mvp05-settings.toml` (162 by default) and can be changed in the menu.
- **Install progress:** one bar across the whole install, with "Step 2 of 3: making the PS2 button art" and the time so far.

## Changed
- Esc asks "Quit MVP05-Plus?".

## Fixed
- The Launcher's *Settings* no longer drops the note after a text setting (such as `display_mode`) in `mvp05-settings.toml`.

# MVP05-Plus Beta 1

First release of MVP05-Plus by spy_jam, built on Mad Dog's MVP05 Public Beta 3 (made with TGP482's XboxXBERecomp).

## New
- **GameCube controllers** through a Wii U / Switch GameCube adapter (official or compatible, in Wii U mode), all 4 ports, with rumble. Stick, C-stick and triggers handled as the GameCube release does. Hold X + Y + Start for 3 seconds to recentre.
- **PlayStation controllers** with the PS2 release's stick handling, analog button pressure and rumble.
- **Native control layouts:** GameCube controllers use the GameCube release's layout, PlayStation controllers the PS2 release's.
- **Button art:** GameCube or PS2 button pictures in menus, help bars and in-game, picked from the controller connected at start. Built by the Launcher from your own discs (optional).
- **MVP05-Plus Launcher** (`MVP05-Plus-Launcher.exe`): installs from your discs (the Xbox game into `assets/`, and the button art from only the files it needs on your GameCube and PS2 discs), then opens on *Play*, with Launch and which controllers Windows sees, including whether the GameCube adapter has its WinUSB driver. Also *Saves* and *Settings* (display mode, aspect ratio, resolution and more, and desktop shortcuts if you want them). Portable: everything stays in the game folder.
- **Shader cache** in `shader_cache/`, so shaders compile once instead of every run.
- **The game's icon**, made from your own Xbox disc by the Launcher.
- **Save backups** at startup, in `save backups/` (30 kept by default), listed in the Launcher's *Saves* tab, where you can restore single saves or a whole date.
- **Esc quits** after asking (Alt+F4 still works). Don't quit while the game is saving.
- **Fullscreen by default**, at your desktop's own resolution (Mad Dog's release starts windowed at 1920 x 1080); change it in the Launcher's *Settings* tab.

## Fixed
- A crash during stolen bases, found in testing.
- SteamOS (through Proton): the black screen; the GameCube adapter through `gcbridge` (see the README for the launch option).

## Known issues
- Under Proton, the GameCube adapter needs the Steam launch option; the game can't start `gcbridge` by itself yet.
- Display issues from the base recompilation (for example 720p fonts) are unchanged.

## Requirements
Windows 10/11 x64 (or SteamOS with Proton), a DirectX 12 graphics card, about 4 GB free, and your own MVP Baseball 2005 Xbox disc image. GameCube and PS2 discs are optional, for button art. Nothing else to install.
