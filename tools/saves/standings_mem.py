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


def finished_games(d):
    """The season's length if these 120 bytes are a finished season's standings, else 0: every team at the same
    games played and the league's wins equal to its losses (each game has one of each). The patcher's search alone
    also takes tables that are only near a season's numbers, and writing over one of those damages the dynasty.
    The same checks as the Tools menu in the game (src/common/standings.cpp)."""
    if len(d) < 120:
        return 0
    g = d[0] + d[1]
    if all(d[i * 4 + 2] == 0 and d[i * 4 + 3] == 0 and d[i * 4] + d[i * 4 + 1] == g for i in range(30)):
        if 1 <= g <= 162 and sum(d[i * 4] for i in range(30)) == sum(d[i * 4 + 1] for i in range(30)):
            return g
    g = sum(d[0:4])
    for i in range(30):
        w1, l1, w2, l2 = d[i * 4:i * 4 + 4]
        if not (w1 + l1) or not (w2 + l2) or w1 + l1 + w2 + l2 != g:
            return 0
    halves = [sum(d[i * 4 + k] for i in range(30)) for k in range(4)]
    return g if 2 <= g <= 162 and halves[0] == halves[1] and halves[2] == halves[3] else 0


def _check_finished(h, addr, season_games):
    g = finished_games(P.read_small(h, addr, 120))
    if g != season_games:
        raise MemError(f"the standings found aren't a finished {season_games}-game season's" +
                       (f" (every team is at {g} games)" if g else "") +
                       ": be on the season screen after the last regular season game, with the season length right")


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
        if score and finished_games(P.read_small(h, base + cfg["gc_offset"], 120)) == season_games:
            say("Using the address found last time.")
            return h, base + cfg["gc_offset"], fmt, recs
    say(f"Searching the game's memory for {season_games}-game standings...")
    for ridx, (base, size) in enumerate(regions):
        with contextlib.redirect_stdout(io.StringIO()):
            off, fmt, recs = P.scan_ram(P.read_full_ram(h, base, size), season_games)
        if off is not None:
            try:
                _check_finished(h, base + off, season_games)
            except MemError:
                k.CloseHandle(h)
                raise
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
        _check_finished(h, addr, season_games)
        _, f2, recs = P.checked_block(fresh, 0, season_games)
        if not f2:
            raise MemError("the standings changed or moved since they were found; nothing written")
        return P.write_bytes(h, addr, P.build_patch(f2, fresh, 0, recs))
    finally:
        k.CloseHandle(h)


def close(h):
    ctypes.windll.kernel32.CloseHandle(h)
