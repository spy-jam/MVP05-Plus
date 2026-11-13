# MVP05-Plus Beta 2

Bring your saves over from the other versions of MVP 2005, pick the season you play, run tywiggins' dynasty tools from inside the game, and update from the Launcher.

## Highlights
- **Import saves from the PS2, GameCube, PC and Xbox** (*Saves → Import a save…*): rosters and dynasties, converted into one of your MVP05-Plus saves so they play here. Your save is backed up first.
- **Season Schedule** (*Schedule* tab): the MVP 2005 disc's 162 games, a 162-game schedule shuffled anew every time you launch, MVP 2004's 60, 30 and 15-game schedules, a 64-game schedule made for MVP05-Plus, or one you import.
- **Tools menu in the game** (F10, or hold Back + Start / Z + Start): the Short Season Advancer, the Team Changer and the Playoffs Editor, without leaving the game.
- **Updates from the Launcher** (*Settings → Updates*): check, install and undo, from this version on.

## Import saves
*Saves → Your saves → Import a save…*: choose the save, pick which of your saves it goes into (it's backed up first, in *Saves → Backups*), and import. Save your rosters, or start a dynasty and save it, in the game once so you have a save of that kind to import into.
- **PS2:** rosters and dynasties, from a `.psu`, a PCSX2 memory card (`.ps2`: you pick the save on it), or the `.sav` from a save.
- **GameCube:** rosters and dynasties, from the `.gci` Dolphin exports.
- **PC:** rosters and dynasties (`.sav`).
- **Xbox:** rosters from another Xbox.
- Owner mode saves aren't imported yet (planned for Beta 3).

Roster conversion is **Mad Dog**'s, from his MVP Roster Toolkit (the same file it makes). GameCube conversion, rosters and dynasties, is **spy_jam**'s. PS2 and PC dynasties use both.

## Season Schedule
The *Schedule* tab sets the schedule new seasons play. Only the three MLB schedules in your game's `schedule.big` change (the minor leagues and spring training stay the game's own), and your original is kept.
- **162 games:** the MVP 2005 disc's, the real 2005 season.
- **162 games, shuffled:** the 2005 schedule with the teams in each division dealt one another's seasons. Every team keeps 81 home games and the same division, league and interleague games, against opponents in a new order; dates and the All-Star break stay put. A new shuffle every time the Launcher starts the game; a season already under way keeps its own.
- **64 games,** made for MVP05-Plus: 6 games against each division rival, 2 or 3 against the rest of the league, every interleague team once (the natural rival twice), even home and away, the All-Star Game in July and a real trade deadline.
- **60, 30 and 15 games:** MVP Baseball 2004's short schedules, brought over to 2005.
- **Import a schedule:** a `schedule.big`, or its `mlb162_1/2/3.dat` files, from any version of MVP 2005 (they're the same on every platform). It's checked (all 30 teams, the same number of games each), joins the list, can be removed again, and updates never touch it.

## Tools
In the game's Tools menu (F10, or hold Back + Start for a second, Z + Start on a GameCube controller; any controller or the mouse moves around it, and the game gets no input while it's open) and in the Launcher's *Tools* tab:
- **Short Season Advancer:** a season shorter than 162 games stops at the end of the regular season until the standings are 162 games long. At its end, it finds the standings and writes them projected to 162 games, every team keeping its winning percentage, so the season goes on to the playoffs. The season's length comes from the *Schedule* tab. In the Launcher it also works on a saved dynasty with the game closed.
- **Team Changer:** take over another organization in your dynasty or owner mode; save to keep it. A port of **tywiggins'** MVP 2005 Team Changer (2006, for the PC game).
- **Playoffs Editor:** choose who plays in the playoffs. When a playoff round has started, before its first game, swap any team in it for another organization; each series keeps its dates and home field. In the running game or on a saved dynasty. Based on **tywiggins'** MVP 2005 Playoffs Creator (2006, for the PC game).

tywiggins' tools were made for the PC game; the Xbox game keeps its database in memory the same way, so they carry over.

## Launcher
- **Updates** (*Settings → Updates*): shows your version, checks GitHub for a newer release (also when the Launcher opens, unless you turn that off), shows what's new and installs it: the program files only, checked against the release's manifest. Your game files, saves, backups, button art, shader cache and imported schedules are never touched, and your settings are kept, with new options added. *Back to …* undoes the last update.
- **A tidier layout:** *Play*, *Saves* (your saves and backups), *Schedule*, *Tools* (a list: open the one you want) and *Settings* (desktop shortcuts and updates side by side).
- **Your game's title art** on the *Play* tab, from your own Xbox disc.
- **Controllers:** an Xbox-style controller, or a GameCube controller on the adapter (with its WinUSB driver), moves around the Launcher: d-pad or stick, A presses, B goes back, LB / RB (L / R) switch tabs, Start launches the game from *Play*.
- **Install progress:** one bar across the whole install ("Step 2 of 3: making the PS2 button art") with the time so far.
- *Launch MVP 05* minimizes the Launcher instead of closing it, so it's an alt-tab away while you play; it closes when the game does, unless you've brought it back up.

## Game
- **Low latency** (*Settings*, off by default): one finished frame waits for the screen instead of up to three, for up to about two frames (~33 ms at 60 Hz) less delay between a button and the screen. It can stutter on a slower PC, so it starts off.
- **Esc** asks "Quit MVP05-Plus?".

## Fixed
- The Launcher's *Settings* no longer drops the note after a text setting (such as `display_mode`) in `mvp05-settings.toml`.

## Updating from Beta 1
Beta 1 has no updater, so this once it's by hand: unzip Beta 2 into your Beta 1 folder and let it replace the files. Your game files (`assets`), saves (`hdd`), backups and button art stay. To keep your settings, don't replace `mvp05-settings.toml`. From Beta 2 on, *Settings → Updates* does it for you.

## Thanks
**Mad Dog** for MVP05 and his MVP Roster Toolkit, **tywiggins** for his MVP 2005 tools, and **TGP482** for XboxXBERecomp.

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
