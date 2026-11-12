#include "dbtools.h"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <filesystem>
#include <utility>

#include "app/app.h"
#include "core/log.h"
#include "kernel/kernel.h"
#include "kernel/memory.h"

namespace dbtools {
namespace {

// tywiggins' Team Changer: each organization's id, in its menu's order (Angels ... Yankees, alphabetical by name)
constexpr const char* kOrgs[30] = {"Angels",    "Astros",       "Athletics", "Blue Jays", "Braves",    "Brewers",
                                   "Cardinals", "Cubs",         "Devil Rays", "Diamondbacks", "Dodgers", "Giants",
                                   "Indians",   "Mariners",     "Marlins",   "Mets",      "Nationals", "Orioles",
                                   "Padres",    "Phillies",     "Pirates",   "Rangers",   "Reds",      "Red Sox",
                                   "Rockies",   "Royals",       "Tigers",    "Twins",     "White Sox", "Yankees"};
constexpr uint32_t kOrgIds[30] = {0xb87d5f5, 0xb87f3f1, 0xb880fe0, 0xb8826fa, 0xb87d6c6, 0xb880867, 0xb882338,
                                  0xb87dd93, 0x59755b,  0xb87d681, 0x597452,  0x59753e,  0xb87de39, 0xb88215e,
                                  0xb87eaf8, 0xb880a79, 0xb8831f0, 0xb87d894, 0x59753c,  0xb881506, 0xb881532,
                                  0xb8825b6, 0xb87dddf, 0xb87da69, 0xb87dea3, 0x597433,  0xb87e1a2, 0xb880869,
                                  0xb87db72, 0xb880a85};
// distances in the PC programs
constexpr uint32_t kTeamChanger = 0xC5B1C;           // from the name: the controlled organization's id (PC)
// the database files sit at the PC's distances here too, but past the last of them (careerp.dat) the Xbox game's
// memory blocks are 16 bytes further on: the controlled organization is at +0xC5B2C, after the dynasty's name
constexpr uint32_t kXboxShift = 0x10;
constexpr uint32_t kDataFromName = 60;               // the others: from the data, 60 bytes after the name
constexpr uint32_t kMoney = 0x11802C;                // ChangeMoney: the balance, a float
constexpr uint32_t kGame = 0x231420;                 // Stamina Changer, Box Score Extractor: the game in play
constexpr uint32_t kPitchers[2] = {0x18C90, 0x1B120};  // from kGame: 25 pitchers of 20 bytes, each team

std::vector<std::pair<uint32_t, uint32_t>> Regions() {
    std::vector<std::pair<uint32_t, uint32_t>> out;
    constexpr uint32_t kCommit = 0x1000;
    for (uint32_t a = mem::kUserLow; a < mem::kUserHigh;) {
        mem::RegionInfo r{};
        if (!mem::QueryVirtual(a, r) || !r.size) break;
        if (r.state == kCommit) out.push_back({r.base, r.size});
        if (r.base + r.size <= a) break;
        a = r.base + r.size;
    }
    out.push_back({mem::kContiguousBase, mem::kPhysicalSize});
    return out;
}

bool Readable(uint32_t va, uint32_t n) {
    for (auto [base, size] : Regions())
        if (va >= base && uint64_t(va) + n <= uint64_t(base) + size) return true;
    return false;
}

template <class T>
bool Read(uint32_t va, T& out) {
    if (!Readable(va, sizeof(T))) return false;
    std::memcpy(&out, kernel::HostPtr(va), sizeof(T));
    return true;
}

}  // namespace

std::vector<Found> FindAttrib() {
    static const char kName[] = "attrib.dat";  // with its 0 after it
    std::vector<Found> out;
    for (auto [base, size] : Regions()) {
        const uint8_t* p = static_cast<const uint8_t*>(kernel::HostPtr(base));
        for (uint32_t o = 0; o + sizeof kName <= size; o++)
            if (p[o] == 'a' && std::memcmp(p + o, kName, sizeof kName) == 0) out.push_back({base + o});
    }
    return out;
}

std::string Check() {
    std::string text;
    auto say = [&](const char* fmt, auto... a) {
        char line[256];
        std::snprintf(line, sizeof line, fmt, a...);
        LOGR("dbtools: %s", line);
        text += line;
        text += "\n";
    };
    auto found = FindAttrib();
    say("\"attrib.dat\" in memory: %d time(s)", int(found.size()));
    for (size_t i = 0; i < found.size() && i < 12; i++) {
        uint32_t n = found[i].name_va, data = n + kDataFromName;
        uint8_t after[16] = {};
        for (int k = 0; k < 16; k++) Read(n + 11 + k, after[k]);
        say("#%d at %08X; bytes after the name: %02X %02X %02X %02X %02X %02X %02X %02X", int(i), n, after[0],
            after[1], after[2], after[3], after[4], after[5], after[6], after[7]);
        uint32_t org = 0;
        if (Read(n + kTeamChanger + kXboxShift, org)) {
            const char* who = nullptr;
            for (int k = 0; k < 30; k++)
                if (kOrgIds[k] == org) who = kOrgs[k];
            say("   Your organization (Team Changer's spot): %08X%s%s", org, who ? " = " : " (not an organization id)",
                who ? who : "");
        } else {
            say("   Team Changer's spot: past the end of memory");
        }
        float money = 0, money2 = 0;
        if (Read(data + kMoney, money) && Read(data + kMoney + kXboxShift, money2))
            say("   ChangeMoney's balance: %.0f (or %.0f)", double(money), double(money2));
        for (int sh = 0; sh <= int(kXboxShift); sh += int(kXboxShift))
        for (int t = 0; t < 2; t++) {
            std::string row;
            int plausible = 0;
            for (int k = 0; k < 25; k++) {
                uint8_t r[20] = {};
                bool ok = true;
                for (int q = 0; q < 20 && ok; q++) ok = Read(data + kGame + sh + kPitchers[t] + k * 20 + q, r[q]);
                if (!ok) break;
                int max = r[0] % 128, cur = (r[16] >> 7) + (r[17] % 64) * 2;
                if (max > 0 && max <= 99 && cur <= 127) plausible++;
                if (k < 8) {
                    char s[16];
                    std::snprintf(s, sizeof s, " %d/%d", cur, max);
                    row += s;
                }
            }
            say("   Stamina Changer (+%d), team %d: %d of 25 look like pitchers; first (current/max):%s", sh, t + 1,
                plausible, row.c_str());
        }
    }
    return text;
}

std::string Capture() {
    auto t = std::time(nullptr);
    std::tm tm{};
#ifdef _WIN32
    localtime_s(&tm, &t);
#else
    localtime_r(&t, &tm);
#endif
    char name[64];
    std::strftime(name, sizeof name, "memory-%Y%m%d-%H%M%S.bin", &tm);
    auto path = app::ExeDir() / "logs" / name;
    std::error_code ec;
    std::filesystem::create_directories(path.parent_path(), ec);
    std::FILE* f = nullptr;
#ifdef _WIN32
    f = _wfopen(path.c_str(), L"wb");
#else
    f = std::fopen(path.c_str(), "wb");
#endif
    if (!f) return "";
    // "MVP5MEM1", the number of regions, each one's (base, size), then their bytes in that order
    auto regions = Regions();
    std::fwrite("MVP5MEM1", 1, 8, f);
    uint32_t n = uint32_t(regions.size());
    std::fwrite(&n, 4, 1, f);
    for (auto [base, size] : regions) {
        std::fwrite(&base, 4, 1, f);
        std::fwrite(&size, 4, 1, f);
    }
    bool ok = true;
    for (auto [base, size] : regions)
        ok &= std::fwrite(kernel::HostPtr(base), 1, size, f) == size;
    ok &= std::fclose(f) == 0;
    LOGR("dbtools: memory capture %s: %s", ok ? "saved" : "failed", path.string().c_str());
    return ok ? path.string() : "";
}

}  // namespace dbtools
