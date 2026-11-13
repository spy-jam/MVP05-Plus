#include "tools_overlay.h"

#include <algorithm>
#include <atomic>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <cstdio>
#include <mutex>
#include <string>
#include <thread>

#include "core/log.h"
#include "imgui.h"
#include "dbtools.h"
#include "standings.h"

namespace tools {

uint32_t g_season_games = standings::kFullSeason;

namespace {

constexpr uint32_t kVkF10 = 0x79, kVkEscape = 0x1B, kWmKeyDown = 0x0100, kWmSysKeyDown = 0x0104;
constexpr uint16_t kStart = 1u << 4, kBack = 1u << 5;
constexpr auto kHold = std::chrono::milliseconds(1000);

std::atomic<bool> g_open{false};
std::atomic<bool> g_focus{false};  // the menu just opened: focus it
float g_scale = 1.0f;  // the menu's size for this screen, set each frame
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
    std::atomic<int> state{0};  // 0 idle, 1 searching, 2 found, 3 not found, 4 written, 5 gone
    standings::Table table;
    std::thread worker;
} g_season;

// Team Changer (tywiggins' MVP2005TeamChanger, ported): control of another organization in the dynasty
struct TeamChange {
    int current = -2;  // -2 not looked yet, -1 not found
    int pick = 0;
    int done = -1;     // the organization just given control, for the message
} g_team;

void Toggle() {
    bool open = !g_open.load();
    g_open = open;
    ImGuiIO& io = ImGui::GetIO();
    io.MouseDrawCursor = open;  // the game hides the system cursor in fullscreen
    if (open && g_season.state != 1 && g_season.state != 2) g_season.state = 0;
    if (open) g_team = {};  // the Team Changer looks again
    g_focus = open;
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

// the season's length: the schedule picked on the Launcher's Schedule tab (season_games in mvp05-settings.toml)
int SeasonGames() {
    return g_season_games >= 1 && g_season_games <= uint32_t(standings::kFullSeason) ? int(g_season_games)
                                                                                     : standings::kFullSeason;
}

void ShortSeason() {
    Help("For seasons shorter than 162 games. After the last regular season game: save the dynasty and stay on "
         "the season screen. Find the standings here, check them, and write them projected to 162 games. Then "
         "advance to the playoffs and save again.");
    ImGui::Spacing();
    int games = SeasonGames();
    ImGui::Text("This season: %d games (your Schedule tab's)", games);
    if (games == standings::kFullSeason) {
        Help("A 162-game season needs nothing projected. If this season plays a shorter schedule, pick it on the "
             "Launcher's Schedule tab, then restart the game.");
        return;
    }
    int state = g_season.state;
    bool busy = state == 1;
    ImGui::BeginDisabled(busy);
    if (ImGui::Button("Find the standings")) {
        if (g_season.worker.joinable()) g_season.worker.join();
        g_season.state = 1;
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
            ImGui::TextColored({1, 0.45f, 0.4f, 1}, "No %d-game standings found.", games);
            Help("Be on the dynasty's season screen after the last regular season game.");
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
            g_season.state = standings::Write(games, g_season.table) ? 4 : 5;
            LOGR("tools: projected standings %s", g_season.state == 4 ? "written" : "not written, they moved");
        }
        ImGui::SameLine();
        if (ImGui::Button("Cancel")) g_season.state = 0;
    }
    // the table scrolls, in what's left of 90% of the screen's height
    float top = ImGui::GetCursorScreenPos().y - ImGui::GetWindowPos().y;
    float room = ImGui::GetIO().DisplaySize.y * 0.9f - top - ImGui::GetStyle().WindowPadding.y * 2;
    float height = std::clamp(room, 120.0f, 400.0f * g_scale);
    if (ImGui::BeginTable("standings", 6, ImGuiTableFlags_Borders | ImGuiTableFlags_SizingFixedFit |
                                              ImGuiTableFlags_ScrollY, ImVec2(0, height))) {
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

void TeamChanger() {
    Help("Take over another organization in your dynasty or owner mode. Load the save first. After changing, save it "
         "to keep it. Based on tywiggins' Team Changer.");
    ImGui::Spacing();
    if (g_team.current == -2 || ImGui::Button("Look again")) {
        g_team.current = dbtools::ControlledOrg();
        if (g_team.current >= 0 && g_team.done < 0) g_team.pick = g_team.current;
    }
    if (g_team.current < 0) {
        ImGui::TextColored({1, 0.45f, 0.4f, 1}, "No dynasty or owner mode save found: load one, then Look again.");
        return;
    }
    ImGui::Text("You control: the %s", dbtools::kOrgNames[g_team.current]);
    ImGui::SetNextItemWidth(260 * g_scale);
    if (ImGui::BeginCombo("##org", dbtools::kOrgNames[g_team.pick], ImGuiComboFlags_HeightLarge)) {
        ImGui::SetWindowFontScale(g_scale);  // the list is a window of its own: scaled like the menu
        for (int k = 0; k < dbtools::kOrgCount; k++)
            if (ImGui::Selectable(dbtools::kOrgNames[k], k == g_team.pick)) g_team.pick = k;
        ImGui::EndCombo();
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(g_team.pick == g_team.current);
    if (ImGui::Button("Take control")) {
        if (dbtools::SetControlledOrg(g_team.pick)) {
            g_team.done = g_team.pick;
            g_team.current = dbtools::ControlledOrg();
        } else {
            g_team.current = -1;
        }
    }
    ImGui::EndDisabled();
    if (g_team.done >= 0 && g_team.done == g_team.current)
        ImGui::TextColored({0.4f, 0.9f, 0.5f, 1}, "Done: you control the %s. Save the dynasty to keep it.",
                           dbtools::kOrgNames[g_team.done]);
}

// the dynasty tools test: whether tywiggins' PC tools' distances hold in this game
struct DbTest {
    std::atomic<int> state{0};  // 0 idle, 1 working, 2 done
    std::mutex lock;
    std::string text;
    std::thread worker;
} g_db;

void DbTools() {
    Help("A test for the next tools (Team Changer, ChangeMoney, Stamina Changer, Playoffs Creator, by tywiggins): "
         "load a dynasty, stay on its season screen, then Check. It only reads, and writes what it finds to the log. "
         "Send the log, or a memory capture if asked for one.");
    ImGui::Spacing();
    bool busy = g_db.state == 1;
    ImGui::BeginDisabled(busy);
    auto run = [](bool capture) {
        if (g_db.worker.joinable()) g_db.worker.join();
        g_db.state = 1;
        g_db.worker = std::thread([capture] {
            std::string t = capture ? dbtools::Capture() : dbtools::Check();
            if (capture) t = t.empty() ? "The capture couldn't be written." : "Saved: " + t;
            std::lock_guard l(g_db.lock);
            g_db.text = t;
            g_db.state = 2;
        });
    };
    if (ImGui::Button("Check")) run(false);
    ImGui::SameLine();
    if (ImGui::Button("Save a memory capture")) run(true);
    ImGui::EndDisabled();
    if (busy) ImGui::Text("Working...");
    if (g_db.state == 2) {
        std::lock_guard l(g_db.lock);
        ImGui::PushTextWrapPos(ImGui::GetContentRegionAvail().x + ImGui::GetCursorPosX());
        ImGui::TextUnformatted(g_db.text.c_str());
        ImGui::PopTextWrapPos();
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
    // sized for the screen: as big on a 4K screen as on a 720p one
    float s = std::clamp(io.DisplaySize.y / 900.0f, 1.0f, 4.0f);
    g_scale = s;
    const ImGuiStyle& st = ImGui::GetStyle();
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(st.WindowPadding.x * s, st.WindowPadding.y * s));
    ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(st.FramePadding.x * s, st.FramePadding.y * s));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(st.ItemSpacing.x * s, st.ItemSpacing.y * s));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemInnerSpacing, ImVec2(st.ItemInnerSpacing.x * s, st.ItemInnerSpacing.y * s));
    ImGui::PushStyleVar(ImGuiStyleVar_CellPadding, ImVec2(st.CellPadding.x * s, st.CellPadding.y * s));
    ImGui::SetNextWindowPos(ImVec2(io.DisplaySize.x * 0.5f, io.DisplaySize.y * 0.5f), ImGuiCond_Always,
                            ImVec2(0.5f, 0.5f));  // centred as it grows, so it stays on the screen
    ImGui::SetNextWindowSize(ImVec2(620 * s, 0), ImGuiCond_Always);
    // kept in front (for the controller), but not while one of its dropdowns is open: focusing it closes them
    if (g_focus.exchange(false) || !ImGui::IsPopupOpen("", ImGuiPopupFlags_AnyPopupId | ImGuiPopupFlags_AnyPopupLevel))
        ImGui::SetNextWindowFocus();
    bool open = true;
    if (ImGui::Begin("MVP05-Plus Tools", &open, ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::SetWindowFontScale(s);
        Help("F10 or Esc closes this, or hold Back + Start (Z + Start on a GameCube controller) for a second. The game "
             "gets no controller input while it's open.");
        if (ImGui::BeginTabBar("tools")) {
            if (ImGui::BeginTabItem("Short Season Advancer")) {
                ShortSeason();
                ImGui::EndTabItem();
            }
            if (ImGui::BeginTabItem("Team Changer")) {
                TeamChanger();
                ImGui::EndTabItem();
            }
            if (ImGui::BeginTabItem("Dynasty tools (test)")) {
                DbTools();
                ImGui::EndTabItem();
            }
            ImGui::EndTabBar();
        }
    }
    ImGui::End();
    ImGui::PopStyleVar(5);
    if (!open) Toggle();
}

void Pad(int port, input::Pad& p) {
    using clock = std::chrono::steady_clock;
    static clock::time_point held[4];
    static bool fired[4] = {};
    if (port < 0 || port > 3) return;
    // Back + Start; a GameCube controller has no Back: Z + Start
    // either controller on this port: an Xbox one's Back + Start, or (a GameCube one has no Back) Z + Start.
    // Both are checked, since a GameCube adapter can share a port with an Xbox controller
    using G = input::GameCube;
    bool combo = p.connected && ((p.buttons & (kStart | kBack)) == (kStart | kBack) ||
                                 (p.gc.present && (p.gc.buttons & (G::Start | G::Z)) == (G::Start | G::Z)));
    // what reaches here, for the log: Start or Back pressed (the first few times), and the shortcut held
    static int noted = 0;
    static uint16_t last[4] = {};
    uint16_t sb = p.connected ? uint16_t(p.buttons & (kStart | kBack)) : 0;
    if (sb != last[port] && sb && noted < 12) {
        noted++;
        LOGR("tools: port %d: %s%s pressed (buttons %04X%s)", port, sb & kStart ? "Start " : "", sb & kBack ? "Back" : "",
             p.buttons, p.gc.present ? ", a GameCube controller" : "");
    }
    last[port] = sb;
    if (!combo) {
        held[port] = {};
        fired[port] = false;
    } else if (held[port] == clock::time_point{}) {
        LOGR("tools: port %d: the shortcut held", port);
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
