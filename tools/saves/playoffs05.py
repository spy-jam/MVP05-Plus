"""Playoffs Editor: who plays in a playoff round, changed before its first game, in the running MVP05.exe or in a
dynasty save. Based on tywiggins' MVP2005PlayoffsCreator (2006, for the PC game).

When a playoff round starts, the game replaces the MLB schedule with that round's games (the first round: 20, four
best-of-5 series), each a 28-byte schedule entry: day, a bitfield (a slot number for the series, a played flag), the
home team's id at +4 and the visitors' at +16. Nothing else holds the bracket: the next round is made from these
games' results. tywiggins' tool writes new entries over them; this one keeps the game's (its dates, home field and
series slots) and swaps teams in them: every game of a series gets the new organization in place of the old one.

In memory, the MLB schedule is where his tool reads it, 0xC78B0 bytes after the database's data (the "attrib.dat"
name + 60), 16 bytes further on in the Xbox game (as for the Team Changer). In a save, it's the first schedule
table after marker 2 (ps2dynasty05's layout).
"""
import os
import struct

import team_changer as TC

ENTRY = 28
MAX_GAMES = 7 * 4         # a round's games: up to four best-of-7 series
SCHEDULE = 60 + 0xC78B0 + 0x10  # from the "attrib.dat" name, in the Xbox game's memory
ORGS, IDS = TC.ORGS, TC.IDS


class PlayoffsError(Exception):
    pass


def _check(ok, why):
    if not ok:
        raise PlayoffsError(why)


def name(key):
    return ORGS[IDS.index(key)] if key in IDS else f"team {key:#x}"


def games(raw):
    """The round's games, from the start of the MLB schedule: entries up to the first empty one."""
    out = []
    for i in range(MAX_GAMES + 1):
        e = raw[ENTRY * i:ENTRY * (i + 1)]
        if len(e) < ENTRY or struct.unpack_from("<H", e, 0)[0] == 0:
            break
        out.append(bytes(e))
    return out


def series(gs):
    """[{slot, home, away, games}] of a playoff round (home: the team at home in its first game), checked."""
    _check(gs, "no playoff games found: this works when the playoffs have started (the season screen of a round)")
    _check(len(gs) <= MAX_GAMES, "that's the regular season's schedule, not a playoff round's: advance to the "
                                 "playoffs first")
    out = {}
    for e in gs:
        h = struct.unpack_from("<H", e, 2)[0]
        home, away = struct.unpack_from("<I", e, 4)[0], struct.unpack_from("<I", e, 16)[0]
        _check(home in IDS and away in IDS and home != away, "the schedule doesn't look like a playoff round")
        _check((h >> 11) & 31 == 0, "a game of this round has been played: teams can only be changed before its "
                                    "first game")
        s = out.setdefault(h & 0x3FF, dict(slot=h & 0x3FF, home=home, away=away, games=0))
        _check({home, away} == {s["home"], s["away"]}, "the schedule doesn't look like a playoff round")
        s["games"] += 1
    out = list(out.values())
    teams = [t for s in out for t in (s["home"], s["away"])]
    _check(len(set(teams)) == len(teams), "the schedule doesn't look like a playoff round")
    return out


def swap(gs, changes):
    """The games with teams replaced: changes {old id: new id}."""
    out = []
    for e in gs:
        e = bytearray(e)
        for at in (4, 16):
            k = struct.unpack_from("<I", e, at)[0]
            struct.pack_into("<I", e, at, changes.get(k, k))
        out.append(bytes(e))
    return out


def check_changes(ss, changes):
    teams = [t for s in ss for t in (s["home"], s["away"])]
    after = [changes.get(t, t) for t in teams]
    _check(all(t in IDS for t in after), "pick organizations from the list")
    dup = sorted({name(t) for t in after if after.count(t) > 1})
    _check(not dup, f"the {', the '.join(dup)} would be in the playoffs twice")


# --- a dynasty save (data.dat), with the game closed

def _save_parts(data):
    import dynasty05 as DY
    import ps2dynasty05 as PD
    try:
        t = DY.read_xbox(data)
    except DY.DynastyError as e:
        raise PlayoffsError(str(e))
    body = t["payload"]
    try:
        L = PD._layout(body, False)
    except PD.Ps2DynastyError as e:
        raise PlayoffsError(str(e))
    p = L["m"][2] + 4  # the MLB table: its count, then its entries
    n = struct.unpack_from("<I", body, p)[0]
    return t, body, p + 4, n


def read_save(data):
    """The playoff round in a dynasty save: [{slot, home, away, games}]."""
    _, body, at, n = _save_parts(data)
    _check(0 < n <= MAX_GAMES, "that dynasty isn't at the start of a playoff round: save it in the game when the "
                               "playoffs have started")
    return series(games(body[at:at + ENTRY * n]))


def write_save(data, changes):
    """The dynasty save with the round's teams changed (re-signed), as bytes."""
    import dynasty05 as DY
    t, body, at, n = _save_parts(data)
    gs = games(body[at:at + ENTRY * n])
    check_changes(series(gs), changes)
    body = bytearray(body)
    body[at:at + ENTRY * len(gs)] = b"".join(swap(gs, changes))
    with DY._in_lib():
        C = DY._containers()
        out = C.build_xbox(data, dict(name=t["name"], typ=t["typ"], flags=t["flags"], payload=bytes(body)))
        _check(C.verify_xbox(out), "the changed save failed its signature check")
    return out


# --- the running game (Windows)

def find_in(ram):
    """(offset of the MLB schedule in ram, the round's series) or None: pure, for tests. A playoff round found
    after a game of it was played raises, saying so."""
    i, why = ram.find(TC.NAME), None
    while i >= 0:
        o = i + SCHEDULE
        gs = games(ram[o:o + ENTRY * (MAX_GAMES + 1)])
        try:
            return o, series(gs)
        except PlayoffsError as e:
            if "played" in str(e):
                why = e
        i = ram.find(TC.NAME, i + 1)
    if why:
        raise why
    return None


def find():
    """(process handle, host address of the MLB schedule, the round's series) in the running game."""
    if os.name != "nt":
        raise PlayoffsError("changing the running game works on Windows only")
    import ctypes
    import standings_patcher as P
    k = ctypes.windll.kernel32
    P._rpm_types(k)
    pid = P.find_dolphin_pid()
    if not pid:
        raise PlayoffsError("MVP05.exe isn't running: start it and load your dynasty first")
    h = k.OpenProcess(0x0030 | 0x0400, False, pid)
    if not h:
        raise PlayoffsError("can't open MVP05.exe's memory (try running the Launcher as administrator)")
    try:
        for base, size in P.find_all_gc_ram(h):
            got = find_in(P.read_full_ram(h, base, size))
            if got:
                return h, base + got[0], got[1]
    except PlayoffsError:
        k.CloseHandle(h)
        raise
    k.CloseHandle(h)
    raise PlayoffsError("no playoffs found in the game: load your dynasty and advance to the playoffs first")


def change(h, addr, changes):
    """The round's teams changed in the running game, after checking it's still the round that was found."""
    import ctypes
    import standings_patcher as P
    try:
        gs = games(P.read_small(h, addr, ENTRY * (MAX_GAMES + 1)))
        check_changes(series(gs), changes)
        if not P.write_bytes(h, addr, b"".join(swap(gs, changes))):
            raise PlayoffsError("couldn't write to the game's memory")
    finally:
        ctypes.windll.kernel32.CloseHandle(h)
