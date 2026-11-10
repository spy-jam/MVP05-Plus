#include "app/app.h"
#include "../game/gc_controls.h"
#include "save_backup.h"
#include "tools_overlay.h"

// what the runtime asks of the game; strings must be set, hooks may stay null
const app::GameInfo app::kGame = {
    .title = L"MVP Baseball 2005",               // window and splash
    .short_title = L"MVP05",               // message boxes
    .name = L"MVP05",                      // window classes, crash dumps, handover event
    .log = "mvp05",                        // log file prefix
    .settings = "mvp05-settings.toml",          // settings file beside the exe
    .splash = L"splash",                  // optional splash.png or splash.bmp beside the exe
    .missing = L"The game isn't installed yet.\n\nOpen MVP05-Plus-Launcher.exe in this folder and choose your Xbox disc. "
                L"Then start the game with Launch MVP 05 there.\n\n(Or put your extracted Xbox files in the assets folder by "
                L"hand, with default.xbe directly inside it.)",
    .images = {{"default.xbe", "MVP05"}},  // each recompiled xbe and its exe, for title launches
    .options = {{"gamecube_layout", &gc::g_enabled, nullptr}, {"gamecube_icons", &gc::g_icons, nullptr},  // GameCube controllers play as on GameCube
                {"playstation_layout", &gc::g_ps_enabled, nullptr}, {"playstation_icons", &gc::g_ps_icons, nullptr},  // and PlayStation pads as on PS2
                {"save_backups", nullptr, &saves::g_keep},  // the newest saves backups kept in "save backups" (0: off)
                {"season_games", nullptr, &tools::g_season_games}},  // the schedule's length, for the Tools' short season
    .load = nullptr,                      // reads more from the settings file's toml::table
    .save = nullptr,                      // writes more into it
    .init = [] {                           // after the settings load, before the window and boot
        saves::Backup();                   // the saves as they were, before this session touches them
        gc::Init();
    },
    .loaded = nullptr,                    // image in memory, before its entry point runs
    .window = gc::Window,                  // the game window is up: the button art for the controllers connected
    .message = tools::Message,             // F10: the Tools menu
    .ui = tools::Ui,                       // the Tools menu, when open
    .pad = [](int port, input::Pad& p) {   // GameCube controllers: buttons by name; then the Tools menu's combo
        gc::Pad(port, p);
        tools::Pad(port, p);
    },
    .rumble = gc::Rumble,                  // PlayStation pads: the PS2's motor
};
