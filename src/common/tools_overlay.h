#pragma once
// MVP05-Plus Tools inside the game: F10, or Back + Start held for a second on a controller, opens and closes it.
// While it's open the game gets no controller input, and the controllers move around the menu instead.
#include <cstdint>

#include "core/input.h"

namespace tools {

extern uint32_t g_season_games;  // mvp05-settings.toml season_games: the schedule's length, set by the Launcher

bool Open();
// window messages: F10, and Esc closing the menu instead of asking to quit
bool Message(void* hwnd, uint32_t msg, uintptr_t wp, intptr_t lp, intptr_t* result);
void Ui(double fps);
// every polled pad: the open combo, and while open the pad goes to the menu instead of the game
void Pad(int port, input::Pad& p);

}  // namespace tools
