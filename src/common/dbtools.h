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
// what the ported tools would read, written to the log and returned as text for the Tools menu; changes nothing
std::string Check();
// a copy of the game's memory (committed user space and the 64 MB of physical memory) into logs/, for the tools
// work: returns the file's path, or "" if it couldn't be written
std::string Capture();

}  // namespace dbtools
