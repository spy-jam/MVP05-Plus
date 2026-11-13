#include "dbtools.h"

#include <array>
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

// tywiggins' Team Changer: each organization's id, in its menu's order (kOrgNames: Angels ... Yankees)
constexpr const char* const* kOrgs = kOrgNames;
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

// the loaded attrib.dat's name: followed by its 0 and the database's 0xBB filler, as the Team Changer checks
uint32_t AttribName() {
    for (const Found& f : FindAttrib()) {
        uint8_t b = 0;
        if (Read(f.name_va + 11, b) && b == 0xBB) return f.name_va;
    }
    return 0;
}

}  // namespace

const char* const kOrgNames[kOrgCount] = {
    "Angels", "Astros", "Athletics", "Blue Jays", "Braves", "Brewers", "Cardinals", "Cubs", "Devil Rays", "Diamondbacks",
    "Dodgers", "Giants", "Indians", "Mariners", "Marlins", "Mets", "Nationals", "Orioles", "Padres", "Phillies",
    "Pirates", "Rangers", "Reds", "Red Sox", "Rockies", "Royals", "Tigers", "Twins", "White Sox", "Yankees"};

int ControlledOrg(uint32_t* where) {
    uint32_t n = AttribName(), id = 0;
    if (!n || !Read(n + kTeamChanger + kXboxShift, id)) return -1;
    for (int k = 0; k < kOrgCount; k++)
        if (kOrgIds[k] == id) {
            if (where) *where = n + kTeamChanger + kXboxShift;
            return k;
        }
    return -1;
}

bool SetControlledOrg(int org) {
    uint32_t va = 0;
    if (org < 0 || org >= kOrgCount || ControlledOrg(&va) < 0) return false;
    std::memcpy(kernel::HostPtr(va), &kOrgIds[org], 4);
    LOGR("dbtools: Team Changer: control given to the %s", kOrgNames[org]);
    return true;
}

namespace {
constexpr uint32_t kSchedule = 0xC78B0;  // from the data: the MLB schedule (PC; the Xbox's is kXboxShift on)
constexpr uint32_t kEntry = 28;
constexpr int kRoundMax = 7 * 4;          // a round's games: up to four best-of-7 series

int OrgOf(uint32_t id) {
    for (int k = 0; k < kOrgCount; k++)
        if (kOrgIds[k] == id) return k;
    return -1;
}

// the round's games (va: the first), read up to the first empty entry
std::vector<std::array<uint8_t, kEntry>> RoundGames(uint32_t& va) {
    std::vector<std::array<uint8_t, kEntry>> out;
    uint32_t n = AttribName();
    if (!n) return out;
    va = n + kDataFromName + kSchedule + kXboxShift;
    for (int i = 0; i <= kRoundMax; i++) {
        std::array<uint8_t, kEntry> e{};
        if (!Read(va + i * kEntry, e)) break;
        uint16_t day = 0;
        std::memcpy(&day, e.data(), 2);
        if (!day) break;
        out.push_back(e);
    }
    return out;
}

std::vector<Series> Parse(const std::vector<std::array<uint8_t, kEntry>>& games, std::string& why) {
    std::vector<Series> out;
    auto fail = [&](const char* t) {
        why = t;
        out.clear();
        return out;
    };
    if (games.empty()) return fail("No playoffs found: load your dynasty and advance to the playoffs.");
    if (int(games.size()) > kRoundMax)
        return fail("That's the regular season's schedule: advance to the playoffs first.");
    for (const auto& e : games) {
        uint16_t bits = 0;
        uint32_t h = 0, a = 0;
        std::memcpy(&bits, e.data() + 2, 2);
        std::memcpy(&h, e.data() + 4, 4);
        std::memcpy(&a, e.data() + 16, 4);
        int home = OrgOf(h), away = OrgOf(a);
        if (home < 0 || away < 0 || home == away) return fail("The schedule doesn't look like a playoff round.");
        if ((bits >> 11) & 31)
            return fail("A game of this round has been played: teams can only be changed before its first game.");
        Series* s = nullptr;
        for (Series& x : out)
            if (x.slot == (bits & 0x3FF)) s = &x;
        if (!s) {
            out.push_back({bits & 0x3FF, home, away, 0});
            s = &out.back();
        } else if (!((s->home == home && s->away == away) || (s->home == away && s->away == home))) {
            return fail("The schedule doesn't look like a playoff round.");
        }
        s->games++;
    }
    for (size_t i = 0; i < out.size(); i++)
        for (size_t j = 0; j < out.size(); j++)
            for (int t : {out[i].home, out[i].away})
                if ((i != j && (t == out[j].home || t == out[j].away)))
                    return fail("The schedule doesn't look like a playoff round.");
    return out;
}
}  // namespace

std::vector<Series> Playoffs(std::string& why) {
    uint32_t va = 0;
    why.clear();
    return Parse(RoundGames(va), why);
}

bool SetPlayoffTeams(const int (&to)[kOrgCount], std::string& why) {
    uint32_t va = 0;
    auto games = RoundGames(va);
    auto round = Parse(games, why);
    if (round.empty()) return false;
    int count[kOrgCount] = {};
    for (const Series& s : round)
        for (int t : {s.home, s.away}) {
            int n = to[t];
            if (n < 0 || n >= kOrgCount) {
                why = "Pick organizations from the list.";
                return false;
            }
            if (++count[n] > 1) {
                why = std::string("The ") + kOrgNames[n] + " would be in the playoffs twice.";
                return false;
            }
        }
    for (size_t i = 0; i < games.size(); i++)
        for (uint32_t at : {4u, 16u}) {
            uint32_t id = 0;
            std::memcpy(&id, games[i].data() + at, 4);
            int k = OrgOf(id);
            if (k >= 0 && to[k] != k) {
                std::memcpy(kernel::HostPtr(va + uint32_t(i) * kEntry + at), &kOrgIds[to[k]], 4);
            }
        }
    for (int k = 0; k < kOrgCount; k++)
        if (to[k] != k && count[to[k]]) LOGR("dbtools: Playoffs Creator: the %s in place of the %s", kOrgNames[to[k]],
                                             kOrgNames[k]);
    return true;
}

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
