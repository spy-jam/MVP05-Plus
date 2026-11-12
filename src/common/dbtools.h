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
// what the ported tools would read, written to the log and returned as text for the Tools menu; changes nothing
std::string Check();
// a copy of the game's memory (committed user space and the 64 MB of physical memory) into logs/, for the tools
// work: returns the file's path, or "" if it couldn't be written
std::string Capture();

}  // namespace dbtools
