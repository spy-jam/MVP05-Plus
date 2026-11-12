#pragma once
// Short seasons: the season's standings found in the running game and projected to 162 games, as the standings
// patcher (tools/saves/standings_patcher.py) does from outside the game, with stricter checks: only a finished
// season's standings are taken, and the season's length is read from them.
#include <array>
#include <cstdint>
#include <string>

namespace standings {

constexpr int kTeams = 30;
constexpr int kFullSeason = 162;
extern const char* const kTeamNames[kTeams];

struct Record {
    int wins = 0, losses = 0;
};

struct Table {
    uint32_t va = 0;  // guest address of the 120 bytes
    char format = 0;  // 'A': W L 0 0 per team; 'B': W L for each half of the season
    int score = 0;
    int games = 0;    // the season's length, read from the standings
    std::array<Record, kTeams> records{};
};

// standings in the game's memory with every team at the same games played and the league's wins equal to its
// losses; out.games is how many. A season stopped on such a day looks the same, so expected (the season's length the
// Launcher set, 0 if unknown) is preferred, and the caller compares them. False when there are none.
bool Find(int expected, Table& out);
// the same 120 bytes read again and checked; false when they changed or moved since Find
bool StillThere(Table& t);
// a record scaled to 162 games, as the patcher does
Record Project(Record r);
// the projection written over the table; false when it wasn't there any more
bool Write(Table& t);

}  // namespace standings
