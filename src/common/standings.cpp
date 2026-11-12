// The standings patcher's search and projection, run inside the game: its memory is read directly instead of
// through another process, so nothing has to be scanned for the game itself or opened as administrator.
#include "standings.h"

#include <algorithm>
#include <cstring>
#include <cmath>
#include <set>
#include <utility>
#include <vector>

#include "kernel/kernel.h"
#include "kernel/memory.h"

namespace standings {

const char* const kTeamNames[kTeams] = {"ANA", "OAK", "SEA", "TEX", "CWS", "CLE", "DET", "KC",  "MIN", "BAL",
                                        "BOS", "NYY", "TB",  "TOR", "ARI", "COL", "LAD", "SD",  "SF",  "CHC",
                                        "CIN", "HOU", "MIL", "PIT", "STL", "ATL", "FLA", "WAS", "NYM", "PHI"};

namespace {

constexpr uint32_t kBytes = kTeams * 4;

// A finished regular season's standings, the season's length read from them: every team has played the same number
// of games (any schedule the Launcher offers gives every team the same), and the league's wins equal its losses,
// since every game has one of each. A table that's only near those numbers (a table of other things, or a season
// still being played) isn't taken: writing the projection over it would damage the dynasty. 0: it isn't one.
int Finished(const uint8_t* d, char& format, int& games, std::array<Record, kTeams>& recs) {
    // format A: [W][L][00][00]
    {
        bool ok = true;
        int g = d[0] + d[1], wins = 0, losses = 0;
        std::set<std::pair<int, int>> unique;
        for (int i = 0; i < kTeams && ok; i++) {
            int w = d[i * 4], l = d[i * 4 + 1];
            if (d[i * 4 + 2] || d[i * 4 + 3] || w + l != g) ok = false;
            wins += w, losses += l;
            recs[i] = {w, l};
            unique.insert({w, l});
        }
        if (ok && g >= 1 && g <= kFullSeason && wins == losses && unique.size() >= 4) {
            format = 'A';
            games = g;
            return int(unique.size()) * 10 + 30;
        }
    }
    // format B: [W1][L1][W2][L2], the season's two halves, each with as many wins as losses across the league
    int g = d[0] + d[1] + d[2] + d[3], w1s = 0, l1s = 0, w2s = 0, l2s = 0;
    std::set<std::pair<int, int>> unique;
    for (int i = 0; i < kTeams; i++) {
        int w1 = d[i * 4], l1 = d[i * 4 + 1], w2 = d[i * 4 + 2], l2 = d[i * 4 + 3];
        if (!(w1 + l1) || !(w2 + l2) || w1 + l1 + w2 + l2 != g) return 0;
        w1s += w1, l1s += l1, w2s += w2, l2s += l2;
        recs[i] = {w1 + w2, l1 + l2};
        unique.insert({w1 + w2, l1 + l2});
    }
    if (g < 2 || g > kFullSeason || w1s != l1s || w2s != l2s || unique.size() < 4) return 0;
    format = 'B';
    games = g;
    return int(unique.size()) * 10 + 30;
}

// the guest memory the game's data can be in: its committed user space and the 64 MB of physical memory
std::vector<std::pair<uint32_t, uint32_t>> Regions() {
    std::vector<std::pair<uint32_t, uint32_t>> out;
    constexpr uint32_t kCommit = 0x1000;
    for (uint32_t a = mem::kUserLow; a < mem::kUserHigh;) {
        mem::RegionInfo r{};
        if (!mem::QueryVirtual(a, r) || !r.size) break;
        if (r.state == kCommit && r.size >= kBytes) out.push_back({r.base, r.size});
        if (r.base + r.size <= a) break;
        a = r.base + r.size;
    }
    out.push_back({mem::kContiguousBase, mem::kPhysicalSize});
    return out;
}

}  // namespace

bool Find(int expected, Table& out) {
    // first, a table as long as the season the Launcher set (expected, 0 if unknown); then any shorter than 162
    // games: last season's standings stay in memory too, and once projected they're 162 games long; then 162
    Table exact, best, full;
    for (auto [base, size] : Regions()) {
        const uint8_t* p = static_cast<const uint8_t*>(kernel::HostPtr(base));
        for (uint32_t o = 0; o + kBytes <= size; o += 4) {
            const uint8_t* d = p + o;
            // a quick no: the first team has played a game, and every team's numbers fit a season
            if (!(d[0] + d[1] + d[2] + d[3])) continue;
            char f = 0;
            int g = 0;
            std::array<Record, kTeams> recs;
            int s = Finished(d, f, g, recs);
            Table& slot = expected && g == expected ? exact : g < kFullSeason ? best : full;
            if (s > slot.score) slot = {base + o, f, s, g, recs};
        }
    }
    if (exact.score) best = exact;
    if (!best.score) best = full;
    if (!best.score) return false;
    out = best;
    return true;
}

bool StillThere(Table& t) {
    char f = 0;
    int g = 0;
    std::array<Record, kTeams> recs;
    if (!t.va || !Finished(static_cast<const uint8_t*>(kernel::HostPtr(t.va)), f, g, recs) || f != t.format ||
        g != t.games)
        return false;
    t.records = recs;
    return true;
}

Record Project(Record r) {
    int gp = r.wins + r.losses;
    if (!gp) return {kFullSeason / 2, kFullSeason / 2};
    // Python's round: halves to even
    int w = int(std::nearbyint(double(r.wins) / gp * kFullSeason));
    w = std::clamp(w, 0, kFullSeason);
    return {w, kFullSeason - w};
}

bool Write(Table& t) {
    if (!StillThere(t)) return false;
    uint8_t out[kBytes] = {};
    for (int i = 0; i < kTeams; i++) {
        Record p = Project(t.records[i]);
        if (t.format == 'B') {
            int w1 = p.wins / 2, l1 = p.losses / 2;
            out[i * 4] = uint8_t(w1);
            out[i * 4 + 1] = uint8_t(l1);
            out[i * 4 + 2] = uint8_t(p.wins - w1);
            out[i * 4 + 3] = uint8_t(p.losses - l1);
        } else {
            out[i * 4] = uint8_t(p.wins);
            out[i * 4 + 1] = uint8_t(p.losses);
        }
    }
    std::memcpy(kernel::HostPtr(t.va), out, kBytes);
    return true;
}

}  // namespace standings
