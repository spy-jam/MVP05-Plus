// GameCube controllers, controlling like the GameCube release of MVP Baseball 2005.
//
// Two layers, both per controller port:
//  1. Report: a GameCube controller's buttons go into the Xbox report by name (A is A, B is B, Z the white
//     button, L and R the triggers with their analog travel, the trigger clicks the thumbstick clicks), not by
//     position as SDL's gamepad mapping would put them.
//  2. Game: the game's pad object holds a table of 0x10B actions (accept, cancel, swing, pitch select, throw to
//     base, ...), each bound to one or two "virtual buttons" with a mode and a combine rule (or, and, a without
//     b, a - b, b while a held, b while a not held). The Xbox build's layout function (0x2BF960, the pad's
//     vtable slot 39) fills it for the Xbox pad; the GameCube build has its own (fn_80008664) with its combos
//     for the buttons the GameCube pad lacks. For a GameCube controller the pad object's table is replaced
//     by the GameCube release's, its button numbers translated to where layer 1 puts each GameCube button.
//
// Table layout (Xbox, the pad object at `self`): self+0 vtable, self+4 + 16 * i action i
//   {int16 a, b, mode_a, mode_b, op, pad; float scale}; self+0x1468 the controller port.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <thread>
#include <mutex>
#include <unordered_map>

#include "app/app.h"
#include "core/input.h"
#include "core/log.h"
#include "gc_controls.h"
#include "gc_layout_table.h"
#include "ps2_layout_table.h"
#include "xdk/hle.h"

using namespace kernel;

namespace gc {

bool g_enabled = true;     // settings file: gamecube_layout
bool g_icons = true;       // settings file: gamecube_icons
bool g_ps_enabled = true;  // settings file: playstation_layout
bool g_ps_icons = true;    // settings file: playstation_icons

void Init() {}

// Button art. gc_icons and ps2_icons beside the exe hold the game's own files rebuilt with the GameCube or PS2
// release's button icons (tools/gc_layout/make_icons.py, tools/ps2_layout/make_ps2_icons.py); the chosen folder's
// files replace the disc's at the same paths. The art is read as the game loads it, so it follows the controllers
// connected at start: a GameCube controller gives the GameCube's, else a PlayStation pad the PS2's.
std::atomic<bool> g_booting{false};  // Window's polls, before the game is in memory

void Window(void*) {
    bool gamecube = false, playstation = false;
    g_booting = true;
    // the adapter's thread finds its controllers within a few of its reports
    for (int tries = 0; tries < 40 && !gamecube; tries++) {
        for (int port = 0; port < 4; port++) {
            input::Pad p = input::Poll(port);
            gamecube |= p.connected && p.gc.present;
            playstation |= p.connected && p.playstation;
        }
        if (!gamecube) std::this_thread::sleep_for(std::chrono::milliseconds(25));
    }
    g_booting = false;
    const char* folder = gamecube && g_enabled && g_icons             ? "gc_icons"
                         : playstation && g_ps_enabled && g_ps_icons ? "ps2_icons"
                                                                      : nullptr;
    std::error_code ec;
    if (folder) {
        auto dir = app::ExeDir() / folder;
        if (std::filesystem::is_directory(dir, ec)) kernel::SetDiscOverlay(dir);
        else LOGR("gc: no %s folder beside the exe, the button icons stay the Xbox ones", folder);
    }
}

namespace {

constexpr uint32_t kPadVtable = 0x5ECEC0;  // the local controller's pad class (0x5ECE00 is the remote/replay pad)
constexpr uint32_t kTable = 0x4;
constexpr uint32_t kEntries = 0x10B;
constexpr uint32_t kPortField = 0x1468;

std::atomic<bool> g_port_gc[4];
std::atomic<bool> g_port_ps[4];  // a PlayStation pad, with the PS2 layout on
std::atomic<bool> g_z_held[4];  // the GameCube Z button on each port, as last polled

enum class Layout { Xbox, GameCube, PlayStation };
struct PadObject {
    std::array<uint8_t, kEntries * 16> xbox{};  // the table as the Xbox layout left it
    bool have_xbox = false;
    Layout layout = Layout::Xbox;  // the table in place
};
std::mutex g_lock;
std::unordered_map<uint32_t, PadObject> g_pads;

Layout Wanted(uint32_t self) {
    uint32_t port = R32(self + kPortField);
    if (port >= 4) return Layout::Xbox;
    if (g_enabled && kHaveGcTable && g_port_gc[port]) return Layout::GameCube;
    if (g_port_ps[port]) return Layout::PlayStation;
    return Layout::Xbox;
}

void WriteTable(uint32_t self, const Entry* table, uint32_t count) {
    static_assert(kGcEntries <= kEntries && ps::kPsEntries <= kEntries);
    for (uint32_t i = 0; i < count; i++) {  // 0x10A, the last entry, is set by no release
        const Entry& e = table[i];
        uint32_t at = self + kTable + 16 * i;
        W16(at + 0, uint16_t(e.a));
        W16(at + 2, uint16_t(e.b));
        W16(at + 4, uint16_t(e.mode_a));
        W16(at + 6, uint16_t(e.mode_b));
        W16(at + 8, uint16_t(e.op));
        float s = e.scale;
        std::memcpy(HostPtr(at + 12), &s, 4);
    }
}

// the table to match the controller now on the object's port
void Sync(uint32_t self, PadObject& o) {
    Layout want = Wanted(self);
    if (want == o.layout || !o.have_xbox) return;
    if (want == Layout::GameCube) WriteTable(self, kGcTable, kGcEntries);
    else if (want == Layout::PlayStation) WriteTable(self, ps::kPsTable, ps::kPsEntries);
    else std::memcpy(HostPtr(self + kTable), o.xbox.data(), o.xbox.size());
    o.layout = want;
    LOGR("gc: port %u now has the %s layout", R32(self + kPortField) + 1,
         want == Layout::GameCube ? "GameCube" : want == Layout::PlayStation ? "PS2" : "Xbox");
}

// Stick response. Both releases shape the sticks in the pad poll with the same code, in one of two modes set by the
// screen (Xbox 0x635394, GameCube 0x8061F678; 0x1953C0/0x1953D0 on Xbox):
//  - 0, the menus: each of a stick's four directions on its own, nothing below 0.7, then (v - 0.7) * 3.33; the same
//    constants on both releases, so the stick goes to the Xbox poll as it is;
//  - 1, play and replay: the stick's tilt m (capped at 1) gives a factor s = (m - dz) / (1 - dz), each axis becomes
//    clamp(axis * s, -1, 1), and below m = dz the stick reads 0. The Xbox poll (0x2BF696) has dz = 0.4. The
//    GameCube's dz comes from a static initializer (fn_8000B384 at 0x8000C164) that reads the variable before it
//    is set: dz = 0 - 0.2, 1 / (1 - dz) = 1 and the dead zone squared 0. So the GameCube stick has no dead zone at
//    all and the factor is m + 0.2; the stick handed to the Xbox poll is chosen so that its curve comes out at the
//    GameCube's.
// The triggers need nothing: the GameCube poll takes (t - 0.4) * 1.67 of their travel, and the Xbox poll does the same
// through its per-channel table (0x63EDAC, filled by 0x4405B0: triggers 0.4 / 1.67, face buttons 0.3 / 1.43).
constexpr uint32_t kStickMode = 0x635394;
// the stick to hand the Xbox poll (play mode) for it to come out as (ox, oy)
void XboxStickFor(float ox, float oy, int16_t& ix, int16_t& iy) {
    float n = std::sqrt(ox * ox + oy * oy);
    if (n == 0.0f) {
        ix = iy = 0;
        return;
    }
    if (n <= 1.0f) {
        // Xbox output length for an input of length k (0.4 <= k <= 1) is k (k - 0.4) / 0.6: solve it for n
        float k = 0.2f + std::sqrt(0.04f + 0.6f * n);
        ox = ox / n * k;
        oy = oy / n * k;
    }
    // past length 1 the Xbox caps the factor at 1 and passes each axis through as it is
    auto i16 = [](float v) { return int16_t(std::clamp(v * 32768.0f, -32767.0f, 32767.0f)); };
    ix = i16(ox);
    iy = i16(oy);
}

void GameCubeStick(int16_t& ix, int16_t& iy) {
    float x = ix / 32768.0f, y = iy / 32768.0f;
    float m = std::sqrt(x * x + y * y);
    if (m == 0.0f) return;
    float s = std::min(m, 1.0f) + 0.2f;  // the GameCube's factor
    XboxStickFor(std::clamp(x * s, -1.0f, 1.0f), std::clamp(y * s, -1.0f, 1.0f), ix, iy);
}

// The PS2's play-mode curve (ps2pad poll fn_00103670, mode 1): the stick's byte report less 127 (x right, y down),
// nothing inside radius 51 (51 / 127 = 0.402 of the throw, the Xbox's 0.4), the tilt m capped at 127, each
// direction (m - 51) / 38 times the axis, capped at 255 (so full at 0.996 on an axis, the Xbox 1.0). SDL's PlayStation
// drivers give the pad's bytes as b * 257 - 32768. The menus' mode is the same on both, as for the GameCube.
void PlayStationStick(int16_t& ix, int16_t& iy) {
    float x = (int(ix) + 32768) / 257.0f - 127.0f;   // right
    float y = (32767 - int(iy)) / 257.0f - 127.0f;   // down (iy is y up, SDL's axis -1 - iy)
    float m2 = x * x + y * y;
    if (m2 < 2601.0f) {
        ix = iy = 0;
        return;
    }
    float s = (std::min(std::sqrt(m2), 127.0f) - 51.0f) * 2.0f / 76.0f;
    float ox = std::clamp(x * s, -255.0f, 255.0f) / 255.0f, oy = std::clamp(-y * s, -255.0f, 255.0f) / 255.0f;
    XboxStickFor(ox, oy, ix, iy);
}

// the controller port behind the game's player index, as the action reader 0x1990A0 finds the pad object
int PortOfPlayer(uint32_t player) {
    if (player > 3) return -1;
    uint32_t idx = R32(0x657084 + 4 * player);
    uint32_t pads = R32(0x6570A0);
    if (!pads || idx > 3) return -1;
    uint32_t pad = R32(pads + 4 * idx + 0xC);
    if (!pad || R32(pad) != kPadVtable) return -1;
    uint32_t port = R32(pad + kPortField);
    return port < 4 ? int(port) : -1;
}

}  // namespace

bool PlayerZHeld(uint32_t player, bool* gamecube) {
    int port = PortOfPlayer(player);
    *gamecube = port >= 0 && g_port_gc[port];
    return port >= 0 && g_z_held[port];
}

std::array<bool, 4> g_port_gc_view() { return {g_port_gc[0], g_port_gc[1], g_port_gc[2], g_port_gc[3]}; }

// A PlayStation pad, as the PS2 release lays it out: every button where the Xbox has the one in the same place,
// but its shoulders the other way round from SDL's Xbox-style mapping: L1 and R1 (SDL's shoulders) go on the
// Xbox triggers' channels, L2 and R2 (SDL's triggers, with their travel) on White and Black. With the PS2's own
// action table (ps2_layout_table.h) on top, each button does what it does on the PS2.
// Pressure: the PS2 game turns on the DualShock 2's pressure sensing and reads Cross, Circle, Square, Triangle and
// the four shoulders as 0-255 with nothing taken off (fn_00103670, then fn_00107E10: byte / 255). The Xbox poll
// takes a dead zone off its analog channels (0x4405B0: face buttons and White/Black (v - 0.3) x 1.43, the triggers
// (v - 0.4) x 1.67), so a pressure p goes in as t + p / k to come out of it as p. (The D-pad stays digital: the
// Xbox pad's is.)
uint8_t Through(uint8_t p, float t, float k) {
    if (!p) return 0;
    return uint8_t(std::min(255L, std::lround(255.0f * t + float(p) / k)));
}

// A pressed button whose pressure reads 0 is on a pad or adapter that reports the pressure channels without filling
// them: it counts as fully pressed.
uint8_t Pressure(uint8_t pressure, uint8_t digital) { return pressure ? pressure : digital ? 0xFF : 0; }

void PlayStation(input::Pad& p) {
    uint8_t l1 = p.analog[5], r1 = p.analog[4];  // SDL's left and right shoulder, as input.cpp puts them
    uint8_t l2 = p.analog[6], r2 = p.analog[7];  // and its triggers, with their travel
    if (p.has_pressure) {
        for (int i = 0; i < 4; i++) p.analog[i] = Through(Pressure(p.pressure[i], p.analog[i]), 0.3f, 1.0f / 0.7f);
        l1 = Through(Pressure(p.pressure[4], l1), 0.4f, 1.0f / 0.6f);
        r1 = Through(Pressure(p.pressure[5], r1), 0.4f, 1.0f / 0.6f);
    }
    // L2 and R2 read from their first touch, as the PS2 reads them (a DualShock 3's pressure, a DualShock 4's or
    // DualSense's trigger travel)
    p.analog[5] = Through(l2, 0.3f, 1.0f / 0.7f);  // White: L2
    p.analog[4] = Through(r2, 0.3f, 1.0f / 0.7f);  // Black: R2
    p.analog[6] = l1;                                                      // the triggers: L1 and R1
    p.analog[7] = r1;
    if (R32(kStickMode) != 0) {  // play: the PS2's curve; menus: as it is (see PlayStationStick)
        PlayStationStick(p.lx, p.ly);
        PlayStationStick(p.rx, p.ry);
    }
}

void Pad(int port, input::Pad& p) {
    if (port < 0 || port > 3) return;
    g_port_gc[port] = p.connected && p.gc.present && g_enabled;
    g_port_ps[port] = p.connected && !p.gc.present && p.playstation && g_ps_enabled;
    if (g_booting) return;  // the stick mode below is the game's memory, not there yet
    if (g_port_ps[port]) PlayStation(p);
    if (!g_port_gc[port]) return;
    using G = input::GameCube;
    const input::GameCube& c = p.gc;
    auto on = [&](uint16_t b) { return (c.buttons & b) != 0; };
    // the GameCube poll never reads L and R's digital clicks (only their travel), so they stay off the stick clicks
    p.buttons = uint16_t(on(G::Up) << 0 | on(G::Down) << 1 | on(G::Left) << 2 | on(G::Right) << 3 | on(G::Start) << 4);
    p.analog[0] = on(G::A) ? 0xFF : 0;
    p.analog[1] = on(G::B) ? 0xFF : 0;
    p.analog[2] = on(G::X) ? 0xFF : 0;
    p.analog[3] = on(G::Y) ? 0xFF : 0;
    p.analog[4] = 0;                      // black: no GameCube button
    p.analog[5] = on(G::Z) ? 0xFF : 0;    // white
    g_z_held[port] = on(G::Z);
    p.analog[6] = c.l;
    p.analog[7] = c.r;
    p.lx = c.lx;
    p.ly = c.ly;
    p.rx = c.cx;
    p.ry = c.cy;
    if (R32(kStickMode) != 0) {  // play: the GameCube's curve; menus: as it is (see GameCubeStick)
        GameCubeStick(p.lx, p.ly);
        GameCubeStick(p.rx, p.ry);
    }
}

// after the Xbox layout function: keep its table, then put the GameCube one in when that port wants it
void AfterLayout(uint32_t self) {
    if (R32(self) != kPadVtable) return;
    std::lock_guard lock(g_lock);
    PadObject& o = g_pads[self];
    std::memcpy(o.xbox.data(), HostPtr(self + kTable), o.xbox.size());
    o.have_xbox = true;
    o.layout = Layout::Xbox;
    Sync(self, o);
}

// Screens take menu button events through their vtable: slot 3 + n handles menu action n (0x001 A in slot 4, 0x002 B
// in slot 5, 0x003 X/GameCube Y in slot 6, 0x005 Start in slot 8 ... 0x014 Black, repeating, in slot 23); 0x2BF340
// is "not handled", 0x24C950 "handled, nothing to do". Where the GameCube release handles a screen's buttons
// differently, its slots trade places while a GameCube controller is in use.
constexpr uint32_t kNotHandled = 0x2BF340, kIgnore = 0x24C950;
struct SlotSwap {
    uint32_t vtable;
    uint8_t slot;
    uint32_t xbox, gamecube;
};
constexpr SlotSwap kSlotSwaps[] = {
    // Replay (0x5BEDE8): the Xbox hides and shows the panel (0x21C480) from Black, which the GameCube table puts on
    // C right, so the C stick hid it; the GameCube hides with Y
    {0x5BEDE8, 3 + 0x003, kNotHandled, 0x21C480},
    {0x5BEDE8, 3 + 0x014, 0x21C480, kIgnore},
    // Attract demo (cFEDemoMovie, 0x5D0990): the Xbox skips on A or B (0x4EABD0), the GameCube on Start
    {0x5D0990, 3 + 0x001, 0x4EABD0, kIgnore},
    {0x5D0990, 3 + 0x002, 0x4EABD0, kIgnore},
    {0x5D0990, 3 + 0x005, kNotHandled, 0x4EABD0},
    // Startup movies (the screen at 0x5D1960 that plays the EA Sports and intro movies, 0x4ED210): Start skips them
    // (0x50C690) on both; the Xbox also skips on A, pressed or released (0x4BE0F0, menu actions 0x001 and 0x021)
    {0x5D1960, 3 + 0x001, 0x4BE0F0, kIgnore},
    {0x5D1960, 3 + 0x021, 0x4BE0F0, kIgnore},
};

static void SwapScreenSlots(bool gamecube) {
    for (const SlotSwap& s : kSlotSwaps) {
        uint32_t at = s.vtable + 4 * s.slot, want = gamecube ? s.gamecube : s.xbox;
        if (R32(at) != want) W32(at, want);
    }
}

// Rumble. The game asks through two wrappers, (player, mode, strength, frames): 0x198A10 for the left motor (pad
// vtable slot 21, 0x2BF090) and 0x198990 for the right (slot 22, 0x2BF0E0); the pad runs the requests in its
// per-frame update (0x2BEEA0). The GameCube release (wrapper fn_802D7B88, pad fn_8000B1A8, update fn_8000AEB4) differs:
//  - every request goes to the one motor path (the right one's), the motor only on or off;
//  - a request is dropped while the motor runs or for 5 frames after the last request or the motor stopping (each
//    request, taken or dropped, restarts those 5 frames), and the motor stops after 120 frames on;
//  - the strengths (left x65535, right x8192 + 16348), the length multiplier (1, or 2 when the game steps two
//    frames), the per-poll update and the on/off switch before every request are the same on both;
//  - some events ask for other lengths: the pitch cursor off the plate (asked every frame) 20 frames, not 1, so it
//    gives one burst each time the cursor leaves the plate; an impact (0x584CA) 8 frames, not 5.
// For a GameCube controller the Xbox pad takes the requests by those rules. Xbox controllers are left as they are.
// Pad fields: +0x14D0 rumble on in options, +0x14D1 rumble possible, +0x14D4/+0x14D8 left frames/strength,
// +0x14DC/+0x14E0 right, +0x14E4 frames the motor has been on (0 off), +0x14CF requests changed.
constexpr int kRumbleMaxFrames = 120, kRumbleGap = 5;
std::mutex g_rumble_lock;
std::unordered_map<uint32_t, int> g_rumble_gap;  // pad object -> frames before a request is taken

bool GameCubePlayer(uint32_t player) {
    int port = PortOfPlayer(player);
    return port >= 0 && g_port_gc[port].load();
}

bool PlayStationPlayer(uint32_t player) {
    int port = PortOfPlayer(player);
    return port >= 0 && g_port_ps[port].load();
}

// PS2 rumble (SLUS_211.35). Its one wrapper (fn_004428A8: player, on, frames, strength) drives the DualShock's
// big motor only (pad vtable slot 23, fn_00107C18: strength x 255); the same five events ask for it, some harder:
//  - pitch cursor off the plate: clamp(0.25 v + 0.35, 0.35, 0.6) for 2 frames (Xbox clamp(0.27 v + 0.13, 0.13, 0.4),
//    1 frame, so v = (s - 0.13) / 0.27);
//  - the two fielding events that ask both Xbox motors (0x118A5, 0x1D5287): 0.6 + 0.3 x (Xbox 0.4 + 0.6 x), the
//    same lengths;
//  - the impact and the 0.3 event: as on the Xbox.
// The per-frame update, the 10 s cutoff and taking every request are the same. For a PlayStation player each
// request goes to the right motor's path (its left twin is dropped) with the PS2's strength and length, and the
// motor output (Rumble below) puts that strength on the pad's big motor.
// false: drop the request
bool PlayStationRumble(uint32_t ret, float& strength, uint32_t& frames) {
    switch (ret) {
    case 0x11925: case 0x1D52E8: return false;  // the left motor's half of a two-motor request
    case 0x1192F: case 0x1D52DE: strength = 0.4f + 0.5f * strength; return true;
    case 0x25E28B: {
        float v = (strength - 0.13f) / 0.27f;
        strength = std::clamp(0.25f * v + 0.35f, 0.35f, 0.6f);
        frames = 2;
        return true;
    }
    default: return true;
    }
}

bool GameCubePad(uint32_t self) {
    if (R32(self) != kPadVtable) return false;
    uint32_t port = R32(self + kPortField);
    return port < 4 && g_port_gc[port].load();
}

// the GameCube's length for the request whose wrapper returns to `ret`, or the Xbox's
uint32_t RumbleFrames(uint32_t ret, uint32_t frames) {
    switch (ret) {
    case 0x25E28B: return 20;  // pitch cursor off the plate (GameCube fn at 0x802F99B8: 20)
    case 0x584CF: return 8;    // impact (GameCube 0x801E1744: 8)
    default: return frames;
    }
}

// a request reaching the pad: true to let the Xbox setter take it
bool RumbleRequest(uint32_t self) {
    if (!GameCubePad(self)) return true;
    if (!G<uint8_t>(self + 0x14D0) || !G<uint8_t>(self + 0x14D1)) return true;  // rumble off: the setter ignores it too
    std::lock_guard lock(g_rumble_lock);
    int& gap = g_rumble_gap[self];
    bool take = R32(self + 0x14E4) == 0 && gap <= 0;
    gap = kRumbleGap;
    return take;
}

// before the pad's per-frame update (fn_8000AEB4's start: the wait counts down, the motor stops after 120 frames)
void RumbleFrame(uint32_t self) {
    if (!GameCubePad(self)) return;
    std::lock_guard lock(g_rumble_lock);
    int& gap = g_rumble_gap[self];
    if (gap > 0) gap--;
    if (R32(self + 0x14E4) > uint32_t(kRumbleMaxFrames)) {
        // end both requests: the update turns the motor off and clears the count
        W32(self + 0x14D4, 0);
        W32(self + 0x14DC, 0);
        W32(self + 0x14D8, 0);
        W32(self + 0x14E0, 0);
        G<uint8_t>(self + 0x14CF) = 1;
    }
}

// after it: a motor that stopped (its requests ran out, or the cap) starts the 5 frames as well, as on the GameCube
void RumbleFrameDone(uint32_t self, uint32_t frames_on_before) {
    if (!GameCubePad(self) || !frames_on_before || R32(self + 0x14E4)) return;
    std::lock_guard lock(g_rumble_lock);
    g_rumble_gap[self] = kRumbleGap;
}

// The motor output for a PlayStation pad: the Xbox update (0x2BEEA0) sets both motors to one speed, right requests
// as 16348 + 8192 s; that s goes on the pad's big (low-frequency) motor at full scale, as the PS2 drives it.
void Rumble(int port, uint16_t& left, uint16_t& right) {
    if (port < 0 || port > 3 || !g_port_ps[port]) return;
    float s = left ? std::clamp((float(left) - 16348.0f) / 8192.0f, 0.0f, 1.0f) : 0.0f;
    left = uint16_t(std::lround(s * 65535.0f));
    right = 0;
}

// after each poll: a controller plugged into or pulled from the port changes the table with it
void AfterPoll(uint32_t self) {
    if (R32(self) != kPadVtable) return;
    bool any = false;
    for (auto& p : g_port_gc) any |= p.load();
    SwapScreenSlots(any);
    std::lock_guard lock(g_lock);
    auto it = g_pads.find(self);
    if (it != g_pads.end()) Sync(self, it->second);
}

}  // namespace gc

// The title screen (Press Start, and the intro movies before it). Its vtable slot 4 (0x4BB110 on Xbox) takes a menu
// button event: the Xbox release passes it on to the generic menu handler (slot 44), which takes A as "accept" and
// moves on; the GameCube release's same method (0x804E0EF4 in its front end overlay) is "return 1", so A does
// nothing there and only Start (slot 8) leaves the screen. With a GameCube controller in use the Xbox one does
// the same.
X86_EXTERN_FUNC(__imp__sub_004BB110);
X86_FUNC(sub_004BB110) {
    bool gamecube = false;
    for (auto& p : gc::g_port_gc_view()) gamecube |= p;
    if (!gamecube) {
        __imp__sub_004BB110(ctx, base);
        return;
    }
    ::kernel::Return(ctx, 1, 1);  // thiscall, one argument: handled
}

// Sports Trax box. The Xbox release moves it with the right stick (actions 0x34 and 0x35, read for each player by
// 0x231EBA / 0x231EC5 through the per-player action reader 0x199170). The GameCube release reads the same actions
// but drops them unless action 0x1A, Z held in its table, is on (0x8014298C-0x801429C8): the C stick alone skips
// songs and Z + C stick moves the box. For a GameCube player the two reads at those call sites ask for an
// unbound action (0x1F, -2 in both tables, reads 0) unless Z is held.
X86_EXTERN_FUNC(__imp__sub_00199170);
X86_FUNC(sub_00199170) {
    uint32_t ret = R32(ctx.esp), player = R32(ctx.esp + 4), action_at = ctx.esp + 8;
    uint32_t action = R32(action_at);
    bool swap = false;
    if ((ret == 0x231EBF || ret == 0x231ECA) && (action == 0x34 || action == 0x35)) {
        bool gamecube = false;
        bool z = gc::PlayerZHeld(player, &gamecube);
        swap = gamecube && !z;
    }
    if (swap) W32(action_at, 0x1F);
    __imp__sub_00199170(ctx, base);
    if (swap) W32(action_at, action);  // cdecl: the caller's argument slot, put back as it was
}

// rumble requests (cdecl: player, mode, strength, frames), the pad's setters (thiscall: strength, frames) and its
// per-frame update; see gc::RumbleRequest
X86_EXTERN_FUNC(__imp__sub_00198990);
X86_EXTERN_FUNC(__imp__sub_00198A10);
static void RumbleWrapper(X86Context& ctx, uint8_t* base, bool left) {
    uint32_t ret = R32(ctx.esp), player = R32(ctx.esp + 4), frames_at = ctx.esp + 16, frames = R32(frames_at);
    uint32_t strength_at = ctx.esp + 12;
    if (gc::PlayStationPlayer(player)) {
        uint32_t bits = R32(strength_at), f = frames;
        float s;
        std::memcpy(&s, &bits, 4);
        if (!gc::PlayStationRumble(ret, s, f)) {
            ::kernel::Return(ctx, 0, 0);
            return;
        }
        uint32_t nb;
        std::memcpy(&nb, &s, 4);
        W32(strength_at, nb);
        W32(frames_at, f);
        __imp__sub_00198990(ctx, base);  // the right motor's path
        W32(strength_at, bits);          // cdecl: the caller's arguments, put back
        W32(frames_at, frames);
        return;
    }
    if (!gc::GameCubePlayer(player)) {
        left ? __imp__sub_00198A10(ctx, base) : __imp__sub_00198990(ctx, base);
        return;
    }
    W32(frames_at, gc::RumbleFrames(ret, frames));
    __imp__sub_00198990(ctx, base);  // the GameCube's one motor path
    W32(frames_at, frames);          // cdecl: the caller's argument, put back
}
X86_FUNC(sub_00198990) { RumbleWrapper(ctx, base, false); }
X86_FUNC(sub_00198A10) { RumbleWrapper(ctx, base, true); }
X86_EXTERN_FUNC(__imp__sub_002BF090);
X86_FUNC(sub_002BF090) {
    if (gc::RumbleRequest(ctx.ecx)) __imp__sub_002BF090(ctx, base);
    else ::kernel::Return(ctx, 0, 2);
}
X86_EXTERN_FUNC(__imp__sub_002BF0E0);
X86_FUNC(sub_002BF0E0) {
    if (gc::RumbleRequest(ctx.ecx)) __imp__sub_002BF0E0(ctx, base);
    else ::kernel::Return(ctx, 0, 2);
}
X86_EXTERN_FUNC(__imp__sub_002BEEA0);
X86_FUNC(sub_002BEEA0) {
    uint32_t self = ctx.ecx, before = ::kernel::R32(self + 0x14E4);
    gc::RumbleFrame(self);
    __imp__sub_002BEEA0(ctx, base);
    gc::RumbleFrameDone(self, before);
}

// the pad's layout (vtable slot 39), called at the end of the game's default action table
X86_EXTERN_FUNC(__imp__sub_002BF960);
X86_FUNC(sub_002BF960) {
    uint32_t self = ctx.ecx;
    __imp__sub_002BF960(ctx, base);
    gc::AfterLayout(self);
}

// the pad's poll (vtable slot 42): XInputGetState into the 25 channels
X86_EXTERN_FUNC(__imp__sub_002BF350);
X86_FUNC(sub_002BF350) {
    uint32_t self = ctx.ecx;
    __imp__sub_002BF350(ctx, base);
    gc::AfterPoll(self);
}
