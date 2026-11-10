"""The memory patcher (standings_patcher.py, the current method) for the Tools window: the same scan, projection
and write into the running MVP05.exe, with its messages in the window instead of a console. Windows only.

In the game: play or simulate to the end of the regular season, save the dynasty, stay on the season screen, then
patch; then advance to the playoffs and save again.
"""
import contextlib
import ctypes
import io
import os

import standings_patcher as P


class MemError(Exception):
    pass


def find(season_games, game_dir, say):
    """(handle, address, fmt, records) of the standings in the running game, by the patcher's own search."""
    if os.name != "nt":
        raise MemError("patching the running game works on Windows only")
    P.CONFIG_FILE = os.path.join(game_dir, "mvp_recomp_config.txt")  # beside the game, as the script keeps it
    k = ctypes.windll.kernel32
    P._rpm_types(k)
    pid = P.find_dolphin_pid()
    if not pid:
        raise MemError("MVP05.exe isn't running: start it and load the dynasty first")
    h = k.OpenProcess(0x0030 | 0x0400, False, pid)
    if not h:
        raise MemError("can't open MVP05.exe's memory (try running the Tools as administrator)")
    regions = P.find_all_gc_ram(h)
    if not regions:
        k.CloseHandle(h)
        raise MemError("the game's memory wasn't found: is the dynasty loaded?")
    cfg = P.load_config()
    if cfg and cfg.get("season_games") == season_games:
        ridx = cfg.get("region_idx", 0)
        base = regions[ridx][0] if ridx < len(regions) else regions[0][0]
        score, fmt, recs = P.checked_block(P.read_small(h, base + cfg["gc_offset"], 120), 0, season_games)
        if score:
            say("Using the address found last time.")
            return h, base + cfg["gc_offset"], fmt, recs
    say(f"Searching the game's memory for {season_games}-game standings...")
    for ridx, (base, size) in enumerate(regions):
        with contextlib.redirect_stdout(io.StringIO()):
            off, fmt, recs = P.scan_ram(P.read_full_ram(h, base, size), season_games)
        if off is not None:
            try:
                with open(P.CONFIG_FILE, "w") as f:
                    import json
                    json.dump({"gc_offset": off, "fmt": fmt, "season_games": season_games, "region_idx": ridx}, f,
                              indent=2)
            except OSError:
                pass
            return h, base + off, fmt, recs
    k.CloseHandle(h)
    raise MemError("couldn't find the standings: be on the dynasty's season screen, with the season length right")


def apply(h, addr, fmt, season_games):
    """Re-read and write the projection, as the patcher does; True when written."""
    k = ctypes.windll.kernel32
    try:
        fresh = P.read_small(h, addr, 120)
        _, f2, recs = P.checked_block(fresh, 0, season_games)
        if not f2:
            raise MemError("the standings changed or moved since they were found; nothing written")
        return P.write_bytes(h, addr, P.build_patch(f2, fresh, 0, recs))
    finally:
        k.CloseHandle(h)


def close(h):
    ctypes.windll.kernel32.CloseHandle(h)
