"""Season schedules: which one the game's schedule.big (in assets) holds, and another swapped in.

The game reads three MLB schedules from data/database/schedule.big, one per dynasty year (mlb162_1/2/3.dat, then
again from 1), when a season goes from spring training to the regular season; a saved season keeps the one it
started with. Only those three files change: the minor league and spring training schedules stay the game's own.

The schedules this offers are in schedules/ beside the Launcher (schedules.json, and each one's three files as
plain text). Your game's own schedule.big is kept in schedules/original/ the first time another is chosen, and
put back for the original 162-game schedule.
"""
import hashlib
import json
import os
import random
import shutil
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
SEASON_FILES = ("mlb162_1.dat", "mlb162_2.dat", "mlb162_3.dat")
ORIGINAL = "162"
SHUFFLED = "162s"  # the game's own, its teams dealt new slates within their divisions: made here, every launch
# 2005's divisions, as the schedules name the teams
DIVISIONS = {"AL East": "Bal Bos NYY TB Tor", "AL Central": "CWS Cle Det KC Min", "AL West": "Ana Oak Sea Tex",
             "NL East": "Atl Fla NYM Phi Was", "NL Central": "ChC Cin Hou Mil Pit StL", "NL West": "Ari Col LA SD SF"}


class ScheduleError(Exception):
    pass


def catalog(root):
    """[{id, name, games, kind, about, folder}] from schedules/schedules.json (beside the exe, or in the source)."""
    for base in (os.path.join(root, "schedules"), os.path.join(HERE, "..", "schedules")):
        p = os.path.join(base, "schedules.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                out = json.load(f)
            for s in out:
                s["folder"] = None if s.get("shuffle") else os.path.join(base, s["id"])
            return out + imported(root)
    return [{"id": ORIGINAL, "name": "162 games (the original)", "games": 162, "kind": "original", "about": "",
             "folder": None}] + imported(root)


# --- schedules you bring in: the season files of any MVP 2005's schedule.big (Xbox, PS2, GameCube, PC: they're the
# same text everywhere), or the .dat files themselves. Kept in schedules/imported/, which updates never touch.

def _imported_dir(root):
    return os.path.join(root, "schedules", "imported")


def imported(root):
    try:
        with open(os.path.join(_imported_dir(root), "imported.json"), encoding="utf-8") as f:
            out = json.load(f)
    except (OSError, ValueError):
        return []
    for s in out:
        s["folder"] = os.path.join(_imported_dir(root), s["id"])
    return [s for s in out if os.path.isdir(s["folder"])]


def read_schedule_files(paths):
    """The three season files from a schedule.big, or from one to three .dat files (one: every year the same)."""
    if len(paths) == 1 and paths[0].lower().endswith(".big"):
        with open(paths[0], "rb") as f:
            have = {n.replace("\\", "/").split("/")[-1].lower(): d for n, d in read_big(f.read())}
        missing = [n for n in SEASON_FILES if n not in have]
        if missing:
            raise ScheduleError("that schedule.big has no " + ", ".join(missing))
        return [unpacked(have[n]) for n in SEASON_FILES]
    if not 1 <= len(paths) <= 3:
        raise ScheduleError("pick a schedule.big, or one to three mlb162 .dat files")
    texts = {}
    for p in paths:
        with open(p, "rb") as f:
            data = f.read()
        if data[1:2] == b"\xfb":
            data = unpacked(data)
        year = next((y for y in (1, 2, 3) if f"_{y}" in os.path.basename(p)), None)
        texts[year or len(texts) + 1] = data
    if len(texts) == 1:
        return [next(iter(texts.values()))] * 3
    if sorted(texts) != [1, 2, 3]:
        raise ScheduleError("pick the three files mlb162_1, _2 and _3 (or just one, for every year)")
    return [texts[1], texts[2], texts[3]]


def check_season(texts):
    """Games per team, the same for every team and year, every team known, or ScheduleError."""
    known = {t for ts in DIVISIONS.values() for t in ts.split()}
    games = set()
    for i, text in enumerate(texts, 1):
        g = games_per_team(text)
        if not g:
            raise ScheduleError(f"year {i} has no games in it (not a schedule file?)")
        odd = sorted(set(g) - known)
        if odd:
            raise ScheduleError(f"year {i} has teams the game doesn't: {', '.join(odd[:3])}")
        if set(g) != known:
            raise ScheduleError(f"year {i} doesn't have all 30 teams")
        if len(set(g.values())) != 1:
            raise ScheduleError(f"in year {i} the teams play different numbers of games "
                                f"({min(g.values())} to {max(g.values())})")
        games |= set(g.values())
    if len(games) != 1:
        raise ScheduleError("the years have different season lengths")
    n = games.pop()
    if not 1 <= n <= 162:
        raise ScheduleError(f"{n} games is more than a season can have")
    return n


def import_schedule(root, paths, name):
    """A schedule brought in under name: checked, then kept in schedules/imported/. Returns its catalog entry."""
    texts = read_schedule_files(paths)
    games = check_season(texts)
    name = " ".join(name.split())[:40] or f"{games} games"
    have = imported(root)
    d = _digest(texts)
    for s in have:
        if s.get("digest") == d:
            raise ScheduleError(f"that schedule is already here, as \"{s['name']}\"")
    n = 1
    while any(s["id"] == f"imported-{n}" for s in have):
        n += 1
    sid = f"imported-{n}"
    folder = os.path.join(_imported_dir(root), sid)
    os.makedirs(folder, exist_ok=True)
    for fn, text in zip(SEASON_FILES, texts):
        with open(os.path.join(folder, fn), "wb") as f:
            f.write(text)
    same = texts[0] == texts[1] == texts[2]
    entry = {"id": sid, "name": name, "games": games, "kind": "imported", "digest": d,
             "short": f"Imported from {', '.join(os.path.basename(p) for p in paths)}: {games} games a team" +
                      (", the same schedule every year." if same else ", a schedule for each of the three years.")}
    _save_imported(root, [{k: v for k, v in s.items() if k != "folder"} for s in have] + [entry])
    entry["folder"] = folder
    return entry


def remove_imported(root, sid):
    have = [{k: v for k, v in s.items() if k != "folder"} for s in imported(root) if s["id"] != sid]
    _save_imported(root, have)
    shutil.rmtree(os.path.join(_imported_dir(root), sid), ignore_errors=True)


def _save_imported(root, entries):
    os.makedirs(_imported_dir(root), exist_ok=True)
    p = os.path.join(_imported_dir(root), "imported.json")
    with open(p + ".new", "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    os.replace(p + ".new", p)


def find_big(root):
    """The installed game's schedule.big, whatever the case of its folders."""
    data = os.path.join(root, "assets", "data")
    for dp, dirs, files in os.walk(data):
        for f in files:
            if f.lower() == "schedule.big":
                return os.path.join(dp, f)
    return None


def original_copy(root):
    return os.path.join(root, "schedules", "original", "schedule.big")


def _marker(root):
    return os.path.join(root, "schedules", "current.json")  # which schedule the Launcher last wrote, by digest


# --- the BIG archive and EA's RefPack compression its files are in

def refpack_decompress(d):
    if len(d) < 5 or d[1] != 0xFB:
        raise ScheduleError("not RefPack data")
    n = 4 if d[0] & 0x80 else 3
    size = int.from_bytes(d[2:2 + n], "big")
    p = 2 + n + (n if d[0] & 0x01 else 0)
    out = bytearray()
    while p < len(d):
        b0 = d[p]
        if b0 < 0x80:
            b1 = d[p + 1]
            p += 2
            lit = b0 & 3
            ln, off = ((b0 >> 2) & 7) + 3, ((b0 & 0x60) << 3) + b1 + 1
        elif b0 < 0xC0:
            b1, b2 = d[p + 1], d[p + 2]
            p += 3
            lit = b1 >> 6
            ln, off = (b0 & 0x3F) + 4, ((b1 & 0x3F) << 8) + b2 + 1
        elif b0 < 0xE0:
            b1, b2, b3 = d[p + 1], d[p + 2], d[p + 3]
            p += 4
            lit = b0 & 3
            ln, off = ((b0 & 0x0C) << 6) + b3 + 5, ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
        elif b0 < 0xFC:
            lit = ((b0 & 0x1F) << 2) + 4
            out += d[p + 1:p + 1 + lit]
            p += 1 + lit
            continue
        else:
            lit = b0 & 3
            out += d[p + 1:p + 1 + lit]
            break
        out += d[p:p + lit]
        p += lit
        if off > len(out):
            raise ScheduleError("damaged RefPack data")
        for _ in range(ln):
            out.append(out[-off])
    if len(out) != size:
        raise ScheduleError("damaged RefPack data")
    return bytes(out)


def read_big(data):
    """[(name, stored bytes)] of a BIGF archive, in its directory's order."""
    if data[:4] != b"BIGF":
        raise ScheduleError("schedule.big isn't a BIG archive")
    n = struct.unpack(">I", data[8:12])[0]
    p, out = 16, []
    for _ in range(n):
        off, size = struct.unpack(">II", data[p:p + 8])
        e = data.index(b"\0", p + 8)
        out.append((data[p + 8:e].decode("latin-1"), data[off:off + size]))
        p = e + 1
    return out


def unpacked(stored):
    return refpack_decompress(stored) if stored[1:2] == b"\xfb" and stored[0] in (0x10, 0x11, 0x90, 0x91) else stored


def write_big(entries):
    """A BIGF archive of [(name, stored bytes)], files after the directory in its order."""
    names = [n.encode("latin-1") + b"\0" for n, _ in entries]
    start = 16 + sum(8 + len(n) for n in names)
    start = (start + 15) & ~15
    head, body, off = bytearray(), bytearray(), start
    for (n, data), nb in zip(entries, names):
        head += struct.pack(">II", off, len(data)) + nb
        body += data
        off += len(data)
    out = bytearray(b"BIGF" + struct.pack("<I", start + len(body)) + struct.pack(">II", len(entries), start))
    out += head
    out += b"\0" * (start - len(out))
    out += body
    return bytes(out)


def refpack(data):
    import sys
    gc = os.path.join(HERE, "..", "gc_layout")
    if os.path.isdir(gc) and gc not in sys.path:
        sys.path.insert(0, gc)
    from iconlib import pack
    out = pack.refpack(data)
    if refpack_decompress(out) != data:  # checked: the game must get exactly these schedules
        raise ScheduleError("compressing the schedule went wrong; nothing was changed")
    return out


# --- schedules

def games_per_team(text):
    """Games each team plays in a season file ({team: n}), the All-Star Game left out."""
    out = {}
    for line in text.decode("latin-1").splitlines()[1:]:
        f = [x.strip() for x in line.split(",")]
        if len(f) < 5 or not f[0] or f[2] in ("AL", "NL"):
            continue
        for t in f[2:4]:
            out[t] = out.get(t, 0) + 1
    return out


def season_files(entry):
    out = []
    for name in SEASON_FILES:
        with open(os.path.join(entry["folder"], name), "rb") as f:
            out.append(f.read())
    return out


def _digest(texts):
    return hashlib.sha1(b"".join(texts)).hexdigest()


def shuffled(text, rng):
    """A season file with the teams of each division dealt one another's slates at random: every game, date, start
    time and half stays where it is, only the team names move. Each team ends up with a division rival's 81 home
    games and its division, league and interleague games; the order of who it plays when is new."""
    lines = text.decode("latin-1").split("\n")
    deal = {}
    for teams in DIVISIONS.values():
        teams = teams.split()
        dealt = teams[:]
        rng.shuffle(dealt)
        deal.update(zip(teams, dealt))
    seen = set()
    for i, line in enumerate(lines[1:], 1):
        f = line.split(",")
        if len(f) < 5 or not f[0].strip() or f[2].strip() in ("AL", "NL"):
            continue
        for c in (2, 3):
            name = f[c].strip()
            if name not in deal:
                raise ScheduleError(f"the schedule has a team this doesn't know ({name})")
            seen.add(name)
            f[c] = f[c].replace(name, deal[name])
        lines[i] = ",".join(f)
    if len(seen) != len(deal):
        raise ScheduleError("the schedule doesn't have all 30 teams")
    return "\n".join(lines).encode("latin-1")


def current(root):
    """The schedule the installed game has: a catalog id, ORIGINAL, or None (another one, or not installed)."""
    big = find_big(root)
    if not big:
        return None
    try:
        with open(big, "rb") as f:
            have = dict(read_big(f.read()))
        texts = [unpacked(have[n]) for n in SEASON_FILES]
    except (OSError, KeyError, ScheduleError):
        return None
    d = _digest(texts)
    try:
        with open(_marker(root)) as f:
            m = json.load(f)
        if m.get("digest") == d and m.get("id"):
            return m["id"]
    except (OSError, ValueError):
        pass
    for s in catalog(root):
        if s["id"] != ORIGINAL and not s.get("shuffle") and s.get("folder") and os.path.isdir(s["folder"]):
            try:
                if _digest(season_files(s)) == d:
                    return s["id"]
            except OSError:
                pass
    orig = original_copy(root)
    if os.path.isfile(orig):
        with open(orig, "rb") as f:
            o = dict(read_big(f.read()))
        if _digest([unpacked(o[n]) for n in SEASON_FILES]) == d:
            return ORIGINAL
        return None
    # never changed by the Launcher: the game's own, if every team plays 162
    return ORIGINAL if set(games_per_team(texts[0]).values()) == {162} else None


def apply(root, schedule_id, seed=None):
    """The schedule swapped into the game's schedule.big; the game's own kept first. Returns its games per team.
    The shuffled one is dealt anew each time (seed: the same deal again, for tests)."""
    big = find_big(root)
    if not big:
        raise ScheduleError("the game isn't installed yet (no schedule.big in assets)")
    orig = original_copy(root)
    if not os.path.isfile(orig):
        if current(root) != ORIGINAL:
            raise ScheduleError("the installed schedule.big isn't the game's own, so it can't be kept as the "
                                "original: install the Xbox game again first")
        os.makedirs(os.path.dirname(orig), exist_ok=True)
        shutil.copy2(big, orig)
    entry = next((s for s in catalog(root) if s["id"] == schedule_id), None)
    if entry is None:
        raise ScheduleError(f"there's no schedule {schedule_id}")
    with open(orig, "rb") as f:
        base = read_big(f.read())
    if schedule_id == ORIGINAL:
        data = open(orig, "rb").read()
        texts = None
    else:
        if entry.get("shuffle"):
            have = dict(base)
            rng = random.Random(seed)
            texts = [shuffled(unpacked(have[n]), rng) for n in SEASON_FILES]
        else:
            texts = season_files(entry)
        for t in texts:
            g = set(games_per_team(t).values())
            if g != {entry["games"]}:
                raise ScheduleError(f"{entry['name']}'s files don't give every team {entry['games']} games")
        swap = dict(zip(SEASON_FILES, texts))
        data = write_big([(n, refpack(swap[n]) if n in swap else d) for n, d in base])
        check = dict(read_big(data))
        if [unpacked(check[n]) for n in SEASON_FILES] != texts:
            raise ScheduleError("the new schedule.big didn't read back right; nothing was changed")
    with open(big + ".new", "wb") as f:
        f.write(data)
    os.replace(big + ".new", big)
    try:
        if texts is None:
            os.remove(_marker(root))
        else:
            with open(_marker(root), "w") as f:
                json.dump({"id": schedule_id, "digest": _digest(texts)}, f)
    except OSError:
        pass
    return entry["games"]
