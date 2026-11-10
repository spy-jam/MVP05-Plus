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

// score_block: a 120 byte block scored as the standings of a season of season_games (0: it isn't)
int Score(const uint8_t* d, int season_games, char& format, std::array<Record, kTeams>& recs) {
    const int min_gp = std::max(1, int(season_games * 0.50));
    const int max_gp = std::min(162, int(season_games * 1.25) + 5);
    const int max_spread = std::max(20, season_games / 3);
    // format A: [W][L][00][00]
    bool ok = true;
    for (int i = 0; i < kTeams && ok; i++) {
        int w = d[i * 4], l = d[i * 4 + 1];
        if (d[i * 4 + 2] || d[i * 4 + 3] || w > 162 || l > 162) ok = false;
        int gp = w + l;
        if (gp && (gp < min_gp || gp > max_gp)) ok = false;
        recs[i] = {w, l};
    }
    if (ok) {
        int active = 0, lo = 1000, hi = 0;
        std::set<std::pair<int, int>> unique;
        for (auto& r : recs) {
            unique.insert({r.wins, r.losses});
            int gp = r.wins + r.losses;
            if (gp) active++, lo = std::min(lo, gp), hi = std::max(hi, gp);
        }
        if (active >= 25 && hi - lo <= max_spread && unique.size() >= 6) {
            format = 'A';
            return int(unique.size()) * 10 - (hi - lo) + active;
        }
    }
    // format B: [W1][L1][W2][L2], the season's two halves
    const double half = season_games / 2.0;
    const int min_half = std::max(1, int(half * 0.65)), max_half = std::min(100, int(half * 1.35) + 3);
    int lo = 1000, hi = 0;
    std::set<std::pair<int, int>> unique;
    for (int i = 0; i < kTeams; i++) {
        int w1 = d[i * 4], l1 = d[i * 4 + 1], w2 = d[i * 4 + 2], l2 = d[i * 4 + 3];
        int g1 = w1 + l1, g2 = w2 + l2;
        if (!g1 || !g2 || g1 < min_half || g1 > max_half || g2 < min_half || g2 > max_half) return 0;
        lo = std::min({lo, g1, g2});
        hi = std::max({hi, g1, g2});
        recs[i] = {w1 + w2, l1 + l2};
        unique.insert({w1 + w2, l1 + l2});
    }
    if (hi - lo <= max_spread && unique.size() >= 6) {
        format = 'B';
        return int(unique.size()) * 10 - (hi - lo) + 30;
    }
    return 0;
}

// checked_block: real standings always have a win and a loss somewhere
int Checked(const uint8_t* d, int season_games, char& format, std::array<Record, kTeams>& recs) {
    int s = Score(d, season_games, format, recs);
    if (!s) return 0;
    bool win = false, loss = false;
    for (auto& r : recs) win |= r.wins > 0, loss |= r.losses > 0;
    return win && loss ? s : 0;
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

bool Find(int season_games, Table& out) {
    Table best;
    for (auto [base, size] : Regions()) {
        const uint8_t* p = static_cast<const uint8_t*>(kernel::HostPtr(base));
        for (uint32_t o = 0; o + kBytes <= size; o += 4) {
            // a quick no: format A's first team needs zero bytes 2 and 3, format B's a played first half
            const uint8_t* d = p + o;
            if ((d[2] || d[3]) && !(d[0] + d[1])) continue;
            char f = 0;
            std::array<Record, kTeams> recs;
            int s = Checked(d, season_games, f, recs);
            if (s > best.score) best = {base + o, f, s, recs};
        }
    }
    if (!best.score) return false;
    out = best;
    return true;
}

bool StillThere(int season_games, Table& t) {
    char f = 0;
    std::array<Record, kTeams> recs;
    if (!t.va || !Checked(static_cast<const uint8_t*>(kernel::HostPtr(t.va)), season_games, f, recs) || f != t.format)
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

bool Write(int season_games, Table& t) {
    if (!StillThere(season_games, t)) return false;
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
