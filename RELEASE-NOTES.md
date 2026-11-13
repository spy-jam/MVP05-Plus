# MVP05-Plus Beta 2

Work in progress: more is coming before this is released.

## New
- **Updates from the Launcher:** *Settings → Updates* shows your version, checks GitHub for a newer release (also when the Launcher opens, unless you turn that off), shows what's new, and installs it: the program files only, checked against the release's manifest. Your game files, saves, backups, button art and shader cache are never touched; your settings are kept, with any new options added. *Back to* undoes the last update. From Beta 2 on: going from Beta 1 to Beta 2 is still by hand.
- **Tools menu in the game:** F10, or hold Back + Start (Z + Start on a GameCube controller) for a second. Any controller or the mouse moves around it, and the game gets no controller input while it's open. Esc closes it.
  - *Short Season Advancer:* at the end of a season shorter than 162 games, it finds the standings in the game and writes them projected to 162 games, as the standings patcher does, so the season can go on to the playoffs. The season's length is taken from the schedule picked on the Schedule tab (in the Launcher it starts there and can be changed).
- **Team Changer** (*Tools* tab, and the Tools menu in the game): take over another organization in your dynasty or owner mode, in the running game; save to keep it. A port of **tywiggins'** MVP 2005 Team Changer (2006, for the PC game): the Xbox game keeps its database in memory the way the PC game does, so his tools' places carry over.
- **Playoffs Creator** (*Tools* tab, and the Tools menu in the game): choose who plays in the playoffs. When a playoff round has started, before its first game, swap any team in it for another organization, in the running game or in a saved dynasty; each series keeps its dates and home field. Based on **tywiggins'** MVP 2005 Playoffs Creator (2006, for the PC game), which finds the round in the same place.
- **Schedule tab:** the season schedule new seasons play, picked from: the game's own 162 games; MVP Baseball 2004's 60, 30 and 15-game schedules brought over to 2005; and a 64-game one made for MVP05-Plus. Only the three MLB schedules in your game's `schedule.big` change (the minor leagues and spring training stay the game's own); your original is kept and goes back with *162 games*. It also sets the season length the Short Season Advancer uses.
- **Tools tab in the Launcher**, with the same *Short Season Advancer*: in the running game (alt-tab to the Launcher), or in a saved dynasty with the game closed (it reads the season's length from the save, backs the save up, then writes it).
- **Import a schedule** (*Schedule* tab): a `schedule.big`, or its `mlb162_1/2/3.dat` files, from any version of MVP 2005 (Xbox, PS2, GameCube or PC: the schedules are the same everywhere). It's checked (all 30 teams, the same number of games each) and joins the list, where it can be removed again; updates never touch it.
- **162 games, shuffled** (*Schedule* tab): the MVP 2005 disc's schedule with the teams in each division dealt one another's seasons at random. Dates, start times and the All-Star break stay put; every team keeps 81 home games and the same division, league and interleague games, against opponents in a new order. The Launcher deals a new shuffle every time it starts the game, so each new season is different; a season already under way keeps its own.
- **Import saves** (*Saves → Import a save…*), so saves from other versions of MVP 2005 play in MVP05-Plus: rosters and dynasties from the PS2 (a `.psu`, a PCSX2 memory card `.ps2`, or the `.sav` from a save), the GameCube (the `.gci` Dolphin exports) and the PC (`.sav`), and rosters from another Xbox. Each goes into one of your saves of the same kind, backed up first: save your rosters, or start a dynasty and save it, in the game once to have one. Roster conversion by Mad Dog (from his MVP Roster Toolkit, giving the same file it does); GameCube conversion, rosters and dynasties, by spy_jam (a GameCube roster goes to Xbox and back unchanged, byte for byte). PS2 and PC dynasties use both: Mad Dog's record layouts with spy_jam's dynasty sections (a new PS2 dynasty comes out the same as the Xbox's, apart from what each game picks at random when it starts one; the PC keeps a dynasty the Xbox way, apart from its settings).
- **The Launcher by controller:** an Xbox-style controller, or a GameCube controller on the adapter (with its WinUSB driver), moves around it (d-pad or stick), A presses, B goes back, LB / RB (L / R) switch tabs, Start launches the game from *Play*.
- **Low latency** (off by default; *Settings* or `low_latency` in `mvp05-settings.toml`): at most one finished frame waits for the screen instead of up to three, for up to about two frames (~33 ms at 60 Hz) less delay between a button and the screen. It can stutter on a slower PC, so it starts off.
- **Install progress:** one bar across the whole install, with "Step 2 of 3: making the PS2 button art" and the time so far.

## Changed
- Esc asks "Quit MVP05-Plus?".
- *Launch MVP 05* minimizes the Launcher instead of closing it, so it's an alt-tab away while you play. It closes when the game does, unless you've brought it back up.

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
