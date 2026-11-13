#pragma once
// The game's database in memory, for tools ported from tywiggins' MVP 2005 (PC) programs: Team Changer, ChangeMoney,
// Stamina Changer, Playoffs Creator. They find the loaded file "attrib.dat" and read and write at fixed distances
// from it. Whether the Xbox game keeps it the same way is what Check() is for.
#include <cstdint>
#include <string>
#include <vector>

namespace dbtools {

struct Found {
    uint32_t name_va = 0;  // where "attrib.dat" is; the PC tools' data starts 60 bytes after it
};

std::vector<Found> FindAttrib();

// Team Changer (tywiggins): the organization a dynasty's player controls, one of 30 ids, in the database's memory
constexpr int kOrgCount = 30;
extern const char* const kOrgNames[kOrgCount];  // Angels ... Yankees, alphabetical by nickname
// the controlled organization's place in kOrgNames, or -1 (no dynasty loaded, or not found); va: where it is
int ControlledOrg(uint32_t* va = nullptr);
// control given to that organization; false if the spot wasn't found or isn't an organization any more
bool SetControlledOrg(int org);
// Playoffs Editor (from tywiggins' Playoffs Creator): when a playoff round starts, the game puts its games in the MLB schedule (28-byte
// entries: day, a bitfield with the series' slot and a played count, the home id at +4, the visitors' at +16); the
// next round is made from their results. A team swapped in every game of its series changes who's in the playoffs.
struct Series {
    int slot = 0;            // the game's number for the series
    int home = -1, away = -1;  // places in kOrgNames; home: at home in the series' first game
    int games = 0;
};
// the round's series, before its first game; empty, with the reason in why, if there isn't one
std::vector<Series> Playoffs(std::string& why);
// to[k]: the organization in place of organization k in this round (k itself to keep it); false, with why, if the
// round isn't there any more, has started, or a team would be in it twice
bool SetPlayoffTeams(const int (&to)[kOrgCount], std::string& why);
// what the ported tools would read, written to the log and returned as text for the Tools menu; changes nothing
std::string Check();
// a copy of the game's memory (committed user space and the 64 MB of physical memory) into logs/, for the tools
// work: returns the file's path, or "" if it couldn't be written
std::string Capture();

}  // namespace dbtools
