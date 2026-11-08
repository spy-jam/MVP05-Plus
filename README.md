# MVP05-Plus

MVP Baseball 2005 on Windows, and on SteamOS through Proton, built on [Mad Dog's](#credits) PC port of the Original Xbox game. spy_jam's MVP05-Plus adds GameCube and PlayStation controller support with full control layouts and button labels. Includes a launcher for easy installation, also providing a save backup menu and display settings.

> **You need your own copy of the Xbox game.** No game files or game art are included. The Launcher builds what's needed from your own discs.

## Features

* **GameCube controllers** through a Wii U / Switch adapter: all 4 ports and rumble, with the GameCube release's full control layout, stick deadzones, C-stick and analog trigger handling.
* **PlayStation controllers** with the PS2 release's full control layout and stick handling, analog button pressure and rumble.
* **Button art to match your controller**: GameCube or PS2 buttons in menus and in-game, made from your own discs (optional).
* **MVP05-Plus Launcher**: install from your discs, launch the game, restore save backups, adjust display settings.
* **Fixes**: a shader cache to prevent mid-game stutter, SteamOS support through Proton, and a fix for a crash during stolen bases, found while testing the original recomp.
* **Save backups**: a full save backup menu in the Launcher. Your saves are backed up automatically when the game starts, keeping the latest 30 backups by default, and you can view and restore them in the Launcher.

## Compatible controllers

* **GameCube controllers** (official adapter, or a third-party adapter in Wii U mode) — GameCube button art and controls
* **DualSense, DualShock 4** — PS2 button art and controls
* **DualShock 3** — PS2 button art and controls, with pressure-sensitive buttons (on Windows, through [DsHidMini](https://github.com/nefarius/DsHidMini) in SDL mode)
* **Xbox 360, Xbox One and Xbox Series controllers** — Xbox button art and controls, as the original
* **Other controllers** (Switch Pro and most others SDL supports) — Xbox button art and controls

Button art follows the controller connected when the game starts. Without the art sets, PlayStation and GameCube controllers still use their own control layouts, with Xbox buttons shown.

## Install

1. Download `MVP05-Plus-Beta-1.zip` from [Releases](../../releases) and unzip it anywhere. Everything stays in that folder: nothing goes into Program Files or the registry, and desktop shortcuts are only made if you ask.
2. Run `MVP05-Plus-Launcher.exe` and choose your discs:

   * **Xbox** (required): a Redump `.iso`, `.xiso`, or a folder of extracted files.
   * **GameCube** (optional, for GameCube art): `.iso`, `.gcm`, `.gcz` or `.ciso`, or `.rvz` with Dolphin (the Launcher finds it, or asks where it is).
   * **PS2** (optional, for PS2 art): `.iso`, or `.chd` with MAME's `chdman` (found or asked for the same way).
   * Already have a `gc_icons` or `ps2_icons` set? Choose its folder or `.zip` instead of the disc.

   Only the files the art needs are read from the GameCube and PS2 discs.

3. Press **Launch MVP 05**. From then on, the Launcher opens on what's installed, with Launch. To quit the game, press **Esc** (it asks first).

Windows may warn that the Launcher is from an unknown publisher: choose *More info → Run anyway*.

## Setting up controllers

* **GameCube adapter on Windows:** give it the WinUSB driver with [Zadig](https://zadig.akeo.ie/), as for Dolphin (select *WUP-028*, *WinUSB*, *Replace Driver*). Third-party adapters: set the switch to *Wii U*.
* **PlayStation and Xbox controllers:** connect by USB or Bluetooth as usual.

### SteamOS (Proton)

Add `MVP05.exe` to Steam as a non-Steam game, run with Proton. For the GameCube adapter, turn off Steam's own GameCube adapter support and set the launch options (with your folder's path):

```
sh -c 'B="/home/deck/Games/MVP05-Plus/gcbridge"; chmod +x "$B"; "$B" & exec "$@"' sh %command%
```

## Adding to Steam (optional)

1. In Steam: *Games → Add a Non-Steam Game to My Library*, and choose `MVP05.exe`.
2. Playing with a PlayStation or Switch controller? In the game's *Properties → Controller*, choose *Disable Steam Input*. Otherwise Steam passes it to the game as an Xbox controller, with the Xbox layout and buttons.
3. On SteamOS, also follow the Proton steps above.

## MVP05-Plus Launcher

* **Install**, which becomes **Play** once the game's installed: your discs in, then what's installed (checked each start), **Launch MVP 05**, and which controllers Windows sees right now, including whether the GameCube adapter has the WinUSB driver it needs.
* **Saves**: *Current saves*, and *Backups* by date. Restore single saves or a whole date; your saves become a backup first, so a restore can be undone.
* **Settings**: display mode, aspect ratio (16:9, or 4:3 with black bars at the sides), resolution (default: fullscreen at your desktop's resolution), render scale, frame rate cap, texture filtering, VSync, Xbox 720p mode; and desktop shortcuts for the game ("MVP 05 Plus") and the Launcher, if you want them.

Everything is also in `mvp05-settings.toml`. Plus adds `gamecube_layout`, `gamecube_icons`, `playstation_layout`, `playstation_icons` (all on) and `save_backups` (30).

## Building from source

Windows x64 with Visual Studio's C++ tools and Windows SDK, LLVM Clang, CMake 3.25+ and Ninja. Put your Xbox files in `assets/` and run `Build-Source.cmd` from an *x64 Native Tools Command Prompt*. Details: [`docs/MVP05-HANDOFF.md`](docs/MVP05-HANDOFF.md); making a release: [`docs/RELEASING.md`](docs/RELEASING.md).

Button art by hand (Python 3 with `pip install pillow numpy`):

```
python tools/gc_layout/make_icons.py assets/data <GameCube disc's data folder> gc_icons
python tools/ps2_layout/make_ps2_icons.py assets/data <PS2 disc's DATA folder> ps2_icons
```

## Credits

* [**Mad Dog**](https://github.com/maddog847): the MVP Baseball 2005 PC port this is built on.
* [**TGP482**](https://github.com/TGP482): [XboxXBERecomp](https://github.com/TGP482/XboxXBERecomp), the static recompiler for original Xbox games that the port is made with.
* **MVP05-Plus**: spy_jam, with Claude (Anthropic).
* Third-party libraries: see `THIRD_PARTY.txt`.

## Special Thanks

* Special thanks to Mad Dog and Kccitystar for their help in the MVP community and consultation on this project.
* Also rip to MVPmods.com and a shout out to all the community members that had done valuable work on there over the years.

## Disclaimer

* This project was entirely vibecoded so take that as you will. But to be clear, everything I added to this project was thoroughly tested and many hours were spent making sure every detail functioned and looked proper.

## Legal

MIT licensed (`SDK-LICENSE.txt`); MVP05-Plus's additions are Copyright 2026 spy_jam under the same license. MVP Baseball 2005 and its art belong to EA; none of it is included. The game's icon is made from your own Xbox disc by the Launcher. Not affiliated with or endorsed by EA, Nintendo, Sony or Microsoft. Microsoft's runtime DLLs and shader compiler are Microsoft's redistributable components, under their own terms.
