#pragma once
// Short seasons: the season's standings found in the running game and projected to 162 games, as the standings
// patcher (tools/saves/standings_patcher.py on the experimental-saves branch) does from outside the game.
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
    std::array<Record, kTeams> records{};
};

// the standings of a season of season_games, by the patcher's search over the game's memory; false when not found
bool Find(int season_games, Table& out);
// the same 120 bytes read again and checked; false when they changed or moved since Find
bool StillThere(int season_games, Table& t);
// a record scaled to 162 games, as the patcher does
Record Project(Record r);
// the projection written over the table; false when it wasn't there any more
bool Write(int season_games, Table& t);

}  // namespace standings
