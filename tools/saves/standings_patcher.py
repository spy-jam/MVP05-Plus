#!/usr/bin/env python3
"""
MVP Baseball 2005 - RAM Patcher v13, Xbox recomp (MVP05.exe) port
================================================================
Same detection, projection and write logic as the Dolphin v13 patcher.
Only the process/memory access is changed to target MVP05.exe, plus one
extra check: a block where no team has a loss is not accepted as standings.
You enter your season length at startup.
The scanner uses that to find the correct standings table.
First run scans and saves the address. Future runs are instant.

Run while MVP05.exe has the dynasty loaded on the season screen.
Then save the dynasty from within the game normally.

Delete mvp_recomp_config.txt to force a re-scan.
"""

import sys, ctypes, ctypes.wintypes, os, json

TARGET_GAMES = 162
CONFIG_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mvp_recomp_config.txt")

TEAMS = [
    "ANA","OAK","SEA","TEX","CWS","CLE","DET","KC ",
    "MIN","BAL","BOS","NYY","TB ","TOR","ARI","COL",
    "LAD","SD ","SF ","CHC","CIN","HOU","MIL","PIT",
    "STL","ATL","FLA","WAS","NYM","PHI"
]

PROCESS_NAME = "mvp05.exe"
GUEST_LO, GUEST_HI = 0x100000000, 0x200000000   # where the recomp maps the emulated Xbox RAM


# ── Recomp access ─────────────────────────────────────────────────────────────

def find_dolphin_pid():   # name kept from the Dolphin version; finds MVP05.exe
    k = ctypes.windll.kernel32
    class PE32(ctypes.Structure):
        _fields_ = [
            ("dwSize",              ctypes.wintypes.DWORD),
            ("cntUsage",            ctypes.wintypes.DWORD),
            ("th32ProcessID",       ctypes.wintypes.DWORD),
            ("th32DefaultHeapID",   ctypes.c_size_t),
            ("th32ModuleID",        ctypes.wintypes.DWORD),
            ("cntThreads",          ctypes.wintypes.DWORD),
            ("th32ParentProcessID", ctypes.wintypes.DWORD),
            ("pcPriClassBase",      ctypes.c_long),
            ("dwFlags",             ctypes.wintypes.DWORD),
            ("szExeFile",           ctypes.c_char * 260),
        ]
    snap = k.CreateToolhelp32Snapshot(2, 0)
    e = PE32(); e.dwSize = ctypes.sizeof(PE32)
    pid = None
    if k.Process32First(snap, ctypes.byref(e)):
        while True:
            if e.szExeFile.lower() == PROCESS_NAME.encode():
                pid = e.th32ProcessID; break
            if not k.Process32Next(snap, ctypes.byref(e)): break
    k.CloseHandle(snap)
    return pid


def find_gc_ram(h):
    regions = find_all_gc_ram(h)
    return regions[0] if regions else (None, None)

def find_all_gc_ram(h):
    k = ctypes.windll.kernel32
    class MBI(ctypes.Structure):
        _fields_ = [
            ("BaseAddress",       ctypes.c_void_p),
            ("AllocationBase",    ctypes.c_void_p),
            ("AllocationProtect", ctypes.wintypes.DWORD),
            ("PartitionId",       ctypes.wintypes.WORD),
            ("RegionSize",        ctypes.c_size_t),
            ("State",             ctypes.wintypes.DWORD),
            ("Protect",           ctypes.wintypes.DWORD),
            ("Type",              ctypes.wintypes.DWORD),
        ]
    k.VirtualQueryEx.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    addr = 0; mbi = MBI(); guest = []; other = []
    while addr < 0x7FFFFFFFFFFF:
        if not k.VirtualQueryEx(h, ctypes.c_void_p(addr),
                                ctypes.byref(mbi), ctypes.sizeof(mbi)): break
        base = mbi.BaseAddress or 0
        # committed, writable (RW / RWX / WC), not guard/no-access, 1 MB or more
        if (mbi.State == 0x1000 and (mbi.Protect & 0xCC) and not (mbi.Protect & 0x101)
                and mbi.RegionSize >= 0x100000):
            (guest if GUEST_LO <= base < GUEST_HI else other).append((base, mbi.RegionSize))
        addr = base + (mbi.RegionSize or 0x1000)
    return guest or other     # the emulated Xbox RAM; everything else only if it was not found


def _rpm_types(k):
    k.ReadProcessMemory.argtypes  = [ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    k.WriteProcessMemory.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    k.OpenProcess.restype = ctypes.wintypes.HANDLE
    k.CreateToolhelp32Snapshot.restype = ctypes.wintypes.HANDLE

def read_full_ram(h, host_base, ram_size):
    k   = ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(ram_size)
    n   = ctypes.c_size_t(0)
    k.ReadProcessMemory(h, ctypes.c_void_p(host_base), buf, ram_size, ctypes.byref(n))
    return bytearray(buf.raw[:n.value])


def read_small(h, host_addr, size):
    k   = ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(size)
    n   = ctypes.c_size_t(0)
    k.ReadProcessMemory(h, ctypes.c_void_p(host_addr), buf, size, ctypes.byref(n))
    return bytearray(buf.raw[:n.value])


def write_bytes(h, host_addr, data):
    k   = ctypes.windll.kernel32
    buf = (ctypes.c_char * len(data))(*data)
    n   = ctypes.c_size_t(0)
    ok  = k.WriteProcessMemory(h, ctypes.c_void_p(host_addr), buf, len(data), ctypes.byref(n))
    return ok and n.value == len(data)


# ── Standings detection ───────────────────────────────────────────────────────

def score_block(data, offset, season_games):
    """
    Score a 120-byte block as standings for a season of `season_games` length.
    season_games is the TOTAL games in the schedule (e.g. 30, 60, 82, 162).
    We expect each team to have played between 70-110% of season_games.
    """
    if len(data) - offset < 120:
        return 0, None, None

    # Wider GP window to handle scheduling variance across longer seasons
    min_gp = max(1,   int(season_games * 0.50))
    max_gp = min(162, int(season_games * 1.25) + 5)

    # Allow wider spread for longer seasons (more scheduling variance between teams)
    max_spread = max(20, season_games // 3)

    # Format A: [W][L][00][00]
    recs_a = []; ok_a = True
    for i in range(30):
        o = offset + i*4
        w,l,p2,p3 = data[o],data[o+1],data[o+2],data[o+3]
        if p2!=0 or p3!=0 or w>162 or l>162:
            ok_a = False; break
        gp = w+l
        if gp != 0 and not (min_gp <= gp <= max_gp):
            ok_a = False; break
        recs_a.append((w,l))
    if ok_a:
        active = [w+l for w,l in recs_a if w+l > 0]
        if len(active) >= 25:
            spread = max(active)-min(active)
            unique = len(set(recs_a))
            if spread <= max_spread and unique >= 6:
                return unique*10 - spread + len(active), 'A', recs_a

    # Format B: [W1][L1][W2][L2] split halves
    # Each half should be ~season_games/2
    half     = season_games / 2
    min_half = max(1,   int(half * 0.65))
    max_half = min(100, int(half * 1.35) + 3)

    recs_b = []; ok_b = True; hgps = []
    for i in range(30):
        o = offset + i*4
        w1,l1,w2,l2 = data[o],data[o+1],data[o+2],data[o+3]
        gp1,gp2 = w1+l1, w2+l2
        if gp1==0 or gp2==0:
            ok_b = False; break
        if not (min_half <= gp1 <= max_half) or not (min_half <= gp2 <= max_half):
            ok_b = False; break
        hgps.extend([gp1,gp2]); recs_b.append((w1+w2,l1+l2))
    if ok_b and hgps and max(hgps)-min(hgps) <= max_spread and len(set(recs_b)) >= 6:
        return len(set(recs_b))*10-(max(hgps)-min(hgps))+30, 'B', recs_b

    return 0, None, None


def checked_block(data, offset, season_games):
    """score_block, plus: real standings always have at least one loss and one win."""
    score, fmt, recs = score_block(data, offset, season_games)
    if score and not (any(l > 0 for w, l in recs) and any(w > 0 for w, l in recs)):
        return 0, None, None
    return score, fmt, recs


import re as _re, bisect as _bisect
# Positions that score_block can accept, found with a fast byte search instead of calling it
# at every 4th byte (the recomp's memory is much bigger than the GameCube's). Same result.
_ACT_A = _re.compile(rb"(?=(?:[\x01-\xa2][\x00-\xa2]|\x00[\x01-\xa2])\x00\x00)", _re.S)
_HALF  = rb"(?:[\x01-\x64][\x00-\x64]|\x00[\x01-\x64])"
_ACT_B = _re.compile(rb"(?=" + _HALF + _HALF + rb")", _re.S)

def _candidates(ram):
    def words(p): return [m.start() >> 2 for m in p.finditer(ram) if not (m.start() & 3)]
    cands = set()
    acts = words(_ACT_A)                       # format A needs >= 25 played entries in the 30
    for a in acts:
        for s in range(a - 5, a + 1):
            if s >= 0 and s not in cands and \
               _bisect.bisect_left(acts, s + 30) - _bisect.bisect_left(acts, s) >= 25:
                cands.add(s)
    run = prev = None                          # format B needs 30 played entries in a row
    for w in words(_ACT_B):
        if prev is None or w != prev + 1: run = w
        prev = w
        if w - run + 1 >= 30: cands.add(w - 29)
    return sorted(s * 4 for s in cands)


def scan_ram(ram, season_games):
    best_score = 0
    best = (None, None, None)
    print("  searching...", end="  ", flush=True)

    for pos in _candidates(ram):               # ascending, like the original loop
        score, fmt, recs = checked_block(ram, pos, season_games)
        if score > best_score:
            best_score = score
            best = (pos, fmt, recs)

    print(f"100%  (best score: {best_score})")
    return best


# ── Config ────────────────────────────────────────────────────────────────────

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def save_config(gc_offset, fmt, season_games):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"gc_offset": gc_offset, "fmt": fmt,
                       "season_games": season_games}, f, indent=2)
        print(f"  Address saved to {os.path.basename(CONFIG_FILE)}")
        print("  Future runs will skip the scan entirely.")
    except Exception as e:
        print(f"  Note: could not save config ({e})")


# ── Projection ────────────────────────────────────────────────────────────────

def project(w, l):
    gp = w+l
    if gp == 0: return 81, 81
    pw = max(0, min(TARGET_GAMES, round(w/gp*TARGET_GAMES)))
    return pw, TARGET_GAMES-pw


def build_patch(fmt, data, offset, records):
    out = bytearray(120)
    for i,(w,l) in enumerate(records):
        pw,pl = project(w,l)
        if fmt == 'B':
            pw1=pw//2; pw2=pw-pw1; pl1=pl//2; pl2=pl-pl1
            out[i*4]=pw1; out[i*4+1]=pl1; out[i*4+2]=pw2; out[i*4+3]=pl2
        else:
            out[i*4]=pw; out[i*4+1]=pl; out[i*4+2]=0; out[i*4+3]=0
    return out


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if sys.platform != 'win32':
        print("Requires Windows."); sys.exit(1)

    print("=" * 55)
    print("  MVP Baseball 2005 - RAM Patcher v13 (Xbox recomp)")
    print("=" * 55)
    print()
    print("STEP 1: Simulate to end of season")
    print("STEP 2: SAVE THE DYNASTY to memory card")
    print("STEP 3: Run this patcher immediately after saving")
    print()
    print()

    # Ask for season length
    while True:
        try:
            val = input("How many games is your season schedule? (e.g. 30, 60, 82, 162): ").strip()
            season_games = int(val)
            if 1 <= season_games <= 162:
                break
            print("Please enter a number between 1 and 162.")
        except ValueError:
            print("Please enter a number.")

    print()

    # Connect
    _rpm_types(ctypes.windll.kernel32)
    print("Connecting to MVP05.exe...", end=" ", flush=True)
    pid = find_dolphin_pid()
    if not pid:
        print("\nERROR: MVP05.exe not found. Start the game first.")
        input("\nPress Enter to exit..."); sys.exit(1)

    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x0030|0x0400, False, pid)
    if not h:
        print("\nERROR: Can't open MVP05.exe (try as Administrator)")
        input("\nPress Enter to exit..."); sys.exit(1)

    all_regions = find_all_gc_ram(h)
    if not all_regions:
        print("\nERROR: game memory not found. Is the game loaded?")
        k.CloseHandle(h); input("\nPress Enter to exit..."); sys.exit(1)

    host_base = all_regions[0][0]
    print(f"Connected. ({len(all_regions)} regions)\n")

    cfg         = load_config()
    gc_offset   = None
    fmt         = None
    records     = None
    active_base = host_base

    if cfg and cfg.get("season_games") == season_games:
        ridx  = cfg.get("region_idx", 0)
        rb    = all_regions[ridx][0] if ridx < len(all_regions) else host_base
        block = read_small(h, rb + cfg["gc_offset"], 120)
        score, found_fmt, found_recs = checked_block(block, 0, season_games)
        if score > 0:
            gc_offset   = cfg["gc_offset"]
            fmt         = found_fmt
            records     = found_recs
            active_base = rb
            print(f"Using saved address: {hex(active_base+gc_offset)}\n")
        else:
            print("Saved address invalid - re-scanning.\n")
    elif cfg and cfg.get("season_games") != season_games:
        print(f"Season length changed ({cfg.get('season_games')} -> {season_games}) - re-scanning.\n")

    if gc_offset is None:
        print(f"Scanning RAM for {season_games}-game season standings...")
        for ridx, (rb, rs) in enumerate(all_regions):
            print(f"  Region {ridx+1}/{len(all_regions)} ", end="", flush=True)
            print("Progress: ", end="", flush=True)
            ram = read_full_ram(h, rb, rs)
            off, f, recs = scan_ram(ram, season_games)
            if off is not None:
                sc, _, _ = checked_block(ram, off, season_games)
                if sc > 0:
                    gc_offset = off; fmt = f; records = recs; active_base = rb
                    print(f"  Found! {hex(rb+off)}")
                    try:
                        with open(CONFIG_FILE,'w') as cf:
                            json.dump({"gc_offset":gc_offset,"fmt":fmt,
                                       "season_games":season_games,
                                       "region_idx":ridx},cf,indent=2)
                        print(f"  Saved to {os.path.basename(CONFIG_FILE)}")
                        print("  Future runs will be instant.")
                    except Exception as e:
                        print(f"  Note: could not save config ({e})")
                    print()
                    break
            else:
                print("  no match")

        if gc_offset is None:
            print("\nERROR: Could not find standings.")
            print("Make sure you are on the dynasty SEASON screen.")
            k.CloseHandle(h); input("\nPress Enter to exit..."); sys.exit(1)

    host_base = active_base

    # Show standings
    fmt_name = {'A':'[W][L][00][00]', 'B':'[W1][L1][W2][L2] split'}
    print(f"Format: {fmt_name.get(fmt,'unknown')}\n")
    print(f"{'Team':>5}  {'W':>3}  {'L':>3}  {'GP':>3}  ->  {'Proj W':>6}  {'Proj L':>6}")
    print("-" * 48)
    for team,(w,l) in zip(TEAMS, records):
        pw,pl = project(w,l)
        print(f"  {team}  {w:3d}  {l:3d}  {w+l:3d}  ->  {pw:6d}  {pl:6d}")

    print()
    if input("Apply projection? (yes/no): ").strip().lower() not in ('yes','y'):
        print("Cancelled.")
        k.CloseHandle(h); input("\nPress Enter to exit..."); sys.exit(0)

    # Re-read fresh before writing
    fresh = read_small(h, host_base + gc_offset, 120)
    _, fmt, records = checked_block(fresh, 0, season_games)
    if not fmt:
        # Fall back to whatever format was detected during scan
        fmt = cfg["fmt"] if cfg else 'A'
        _, _, records = score_block(fresh, 0, 162)  # broad search
    patch = build_patch(fmt, fresh, 0, records)

    print()
    print("Writing standings...")
    ok = write_bytes(h, host_base + gc_offset, patch)
    print(f"  {'OK' if ok else 'FAILED'} -> {hex(active_base+gc_offset)}")
    k.CloseHandle(h)

    print()
    if ok:
        print("=" * 55)
        print("  SUCCESS!")
        print("=" * 55)
        print()
        print("In the game:")
        print("  1. Advance season to trigger playoffs")
        print("  2. Save dynasty normally from within the game")
    else:
        print("Write failed - try running as Administrator.")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
