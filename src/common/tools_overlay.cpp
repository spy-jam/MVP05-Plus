#include "tools_overlay.h"

#include <algorithm>
#include <atomic>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <cstdio>
#include <mutex>
#include <thread>

#include "core/log.h"
#include "imgui.h"
#include "standings.h"

namespace tools {

uint32_t g_season_games = standings::kFullSeason;

namespace {

constexpr uint32_t kVkF10 = 0x79, kVkEscape = 0x1B, kWmKeyDown = 0x0100, kWmSysKeyDown = 0x0104;
constexpr uint16_t kStart = 1u << 4, kBack = 1u << 5;
constexpr auto kHold = std::chrono::milliseconds(1000);

std::atomic<bool> g_open{false};
std::atomic<bool> g_toggle{false};  // asked for from the pad thread, done in Ui

// the pads while the menu is open, for ImGui's gamepad navigation: any controller moves it
struct Seen {
    uint16_t buttons = 0;
    uint8_t analog[8] = {};
    int16_t lx = 0, ly = 0;
};
std::mutex g_pad_lock;
Seen g_ports[4];

// the short season tool's state, kept between frames
struct Season {
    int games = standings::kFullSeason;
    std::atomic<int> state{0};  // 0 idle, 1 searching, 2 found, 3 not found, 4 written, 5 gone
    standings::Table table;
    std::thread worker;
} g_season;

void Toggle() {
    bool open = !g_open.load();
    g_open = open;
    ImGuiIO& io = ImGui::GetIO();
    io.MouseDrawCursor = open;  // the game hides the system cursor in fullscreen
    if (open && g_season.state != 1) {
        g_season.games = int(g_season_games ? g_season_games : standings::kFullSeason);
        if (g_season.state != 2) g_season.state = 0;
    }
    LOGR("tools: menu %s", open ? "opened" : "closed");
}

void FeedPad() {
    ImGuiIO& io = ImGui::GetIO();
    uint16_t b = 0;
    uint8_t an[8] = {};
    int lx = 0, ly = 0;
    {
        std::lock_guard lock(g_pad_lock);
        for (auto& s : g_ports) {
            b |= s.buttons;
            for (int i = 0; i < 8; i++) an[i] = std::max(an[i], s.analog[i]);
            if (std::abs(s.lx) > std::abs(lx)) lx = s.lx;
            if (std::abs(s.ly) > std::abs(ly)) ly = s.ly;
        }
    }
    io.BackendFlags |= ImGuiBackendFlags_HasGamepad;
    io.AddKeyEvent(ImGuiKey_GamepadDpadUp, (b & 1) || ly > 16000);
    io.AddKeyEvent(ImGuiKey_GamepadDpadDown, (b & 2) || ly < -16000);
    io.AddKeyEvent(ImGuiKey_GamepadDpadLeft, (b & 4) || lx < -16000);
    io.AddKeyEvent(ImGuiKey_GamepadDpadRight, (b & 8) || lx > 16000);
    io.AddKeyEvent(ImGuiKey_GamepadFaceDown, an[0] > 64);   // A: activate
    io.AddKeyEvent(ImGuiKey_GamepadFaceRight, an[1] > 64);  // B: back
    io.AddKeyEvent(ImGuiKey_GamepadL1, an[6] > 64);         // triggers: switch sections
    io.AddKeyEvent(ImGuiKey_GamepadR1, an[7] > 64);
}

void Help(const char* text) {
    ImGui::PushTextWrapPos(ImGui::GetContentRegionAvail().x + ImGui::GetCursorPosX());
    ImGui::TextDisabled("%s", text);
    ImGui::PopTextWrapPos();
}

void ShortSeason() {
    Help("For seasons shorter than 162 games. At the end of the regular season: save the dynasty and stay on the "
         "season screen. Find the standings here, check them, and write them projected to 162 games. Then advance "
         "to the playoffs and save again.");
    ImGui::Spacing();
    int state = g_season.state;
    bool busy = state == 1;
    ImGui::BeginDisabled(busy);
    ImGui::SetNextItemWidth(160);
    if (ImGui::InputInt("games in this season", &g_season.games, 1, 10)) {
        g_season.games = std::clamp(g_season.games, 1, standings::kFullSeason);
        g_season.state = 0;
    }
    if (ImGui::Button("Find the standings")) {
        if (g_season.worker.joinable()) g_season.worker.join();
        g_season.state = 1;
        int games = g_season.games;
        g_season.worker = std::thread([games] {
            standings::Table t;
            bool ok = standings::Find(games, t);
            if (ok) g_season.table = t;
            if (ok) LOGR("tools: standings for %d games found at %08X, format %c", games, t.va, t.format);
            else LOGR("tools: standings for %d games not found", games);
            g_season.state = ok ? 2 : 3;
        });
    }
    ImGui::EndDisabled();
    switch (state) {
        case 1: ImGui::Text("Searching the game's memory..."); break;
        case 3:
            ImGui::TextColored({1, 0.45f, 0.4f, 1}, "No %d-game standings found.", g_season.games);
            Help("Be on the dynasty's season screen after the last regular season game, with the season length "
                 "right.");
            break;
        case 4: ImGui::TextColored({0.4f, 0.9f, 0.5f, 1}, "Written. Now advance to the playoffs, then save."); break;
        case 5:
            ImGui::TextColored({1, 0.45f, 0.4f, 1}, "The standings changed or moved: nothing written. Find them again.");
            break;
        default: break;
    }
    if (state != 2 && state != 4) return;
    ImGui::Spacing();
    if (state == 2) {
        if (ImGui::Button("Write the standings, projected to 162 games")) {
            g_season.state = standings::Write(g_season.games, g_season.table) ? 4 : 5;
            LOGR("tools: projected standings %s", g_season.state == 4 ? "written" : "not written, they moved");
        }
        ImGui::SameLine();
        if (ImGui::Button("Cancel")) g_season.state = 0;
    }
    if (ImGui::BeginTable("standings", 6, ImGuiTableFlags_Borders | ImGuiTableFlags_SizingFixedFit |
                                              ImGuiTableFlags_ScrollY, ImVec2(0, 260))) {
        for (int c = 0; c < 2; c++) {
            ImGui::TableSetupColumn("Team");
            ImGui::TableSetupColumn("Now");
            ImGui::TableSetupColumn("162 games");
        }
        ImGui::TableHeadersRow();
        for (int i = 0; i < standings::kTeams / 2; i++) {
            ImGui::TableNextRow();
            for (int j : {i, i + standings::kTeams / 2}) {
                auto r = g_season.table.records[size_t(j)];
                auto p = standings::Project(r);
                ImGui::TableNextColumn();
                ImGui::TextUnformatted(standings::kTeamNames[j]);
                ImGui::TableNextColumn();
                ImGui::Text("%d-%d", r.wins, r.losses);
                ImGui::TableNextColumn();
                ImGui::Text("%d-%d", p.wins, p.losses);
            }
        }
        ImGui::EndTable();
    }
}

}  // namespace

bool Open() { return g_open; }

bool Message(void*, uint32_t msg, uintptr_t wp, intptr_t lp, intptr_t* result) {
    if (msg != kWmKeyDown && msg != kWmSysKeyDown) return false;
    bool repeated = (lp & (1LL << 30)) != 0;
    if (wp == kVkF10 || (wp == kVkEscape && g_open)) {
        if (!repeated) g_toggle = true;
        *result = 0;
        return true;
    }
    return false;
}

void Ui(double) {
    if (g_toggle.exchange(false)) Toggle();
    if (!g_open) return;
    FeedPad();
    ImGuiIO& io = ImGui::GetIO();
    ImGui::SetNextWindowPos(ImVec2(io.DisplaySize.x * 0.5f, io.DisplaySize.y * 0.5f), ImGuiCond_Appearing,
                            ImVec2(0.5f, 0.5f));
    ImGui::SetNextWindowSize(ImVec2(620, 0), ImGuiCond_Appearing);
    ImGui::SetNextWindowFocus();
    bool open = true;
    if (ImGui::Begin("MVP05-Plus Tools", &open, ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_AlwaysAutoResize)) {
        Help("F10 or Esc closes this, or hold Back + Start (Z + Start on a GameCube controller) for a second. The game "
             "gets no controller input while it's open.");
        if (ImGui::BeginTabBar("tools")) {
            if (ImGui::BeginTabItem("Short Season Advancer")) {
                ShortSeason();
                ImGui::EndTabItem();
            }
            ImGui::EndTabBar();
        }
    }
    ImGui::End();
    if (!open) Toggle();
}

void Pad(int port, input::Pad& p) {
    using clock = std::chrono::steady_clock;
    static clock::time_point held[4];
    static bool fired[4] = {};
    if (port < 0 || port > 3) return;
    // Back + Start; a GameCube controller has no Back: Z + Start
    using G = input::GameCube;
    bool combo = p.connected && (p.gc.present ? (p.gc.buttons & (G::Start | G::Z)) == (G::Start | G::Z)
                                              : (p.buttons & (kStart | kBack)) == (kStart | kBack));
    if (!combo) {
        held[port] = {};
        fired[port] = false;
    } else if (held[port] == clock::time_point{}) {
        held[port] = clock::now();
    } else if (!fired[port] && clock::now() - held[port] >= kHold) {
        fired[port] = true;
        g_toggle = true;
    }
    if (!g_open && !combo) return;
    {
        std::lock_guard lock(g_pad_lock);
        Seen& s = g_ports[port];
        s = {};
        if (g_open && p.connected && !combo) {
            s.buttons = p.buttons;
            std::memcpy(s.analog, p.analog, sizeof s.analog);
            s.lx = p.lx;
            s.ly = p.ly;
        }
    }
    // the game sees an idle controller while the menu is open, and while the combo is held (no pause menu)
    bool connected = p.connected;
    p = input::Pad{};
    p.connected = connected;
}

}  // namespace tools
