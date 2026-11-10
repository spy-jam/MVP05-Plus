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
import shutil
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
SEASON_FILES = ("mlb162_1.dat", "mlb162_2.dat", "mlb162_3.dat")
ORIGINAL = "162"


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
                s["folder"] = os.path.join(base, s["id"])
            return out
    return [{"id": ORIGINAL, "name": "162 games (the original)", "games": 162, "kind": "original", "about": "",
             "folder": None}]


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
    for s in catalog(root):
        if s["id"] != ORIGINAL and s.get("folder") and os.path.isdir(s["folder"]):
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


def apply(root, schedule_id):
    """The schedule swapped into the game's schedule.big; the game's own kept first. Returns its games per team."""
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
    if schedule_id == ORIGINAL:
        data = open(orig, "rb").read()
    else:
        texts = season_files(entry)
        for t in texts:
            g = set(games_per_team(t).values())
            if g != {entry["games"]}:
                raise ScheduleError(f"{entry['name']}'s files don't give every team {entry['games']} games")
        with open(orig, "rb") as f:
            base = read_big(f.read())
        swap = dict(zip(SEASON_FILES, texts))
        data = write_big([(n, refpack(swap[n]) if n in swap else d) for n, d in base])
        check = dict(read_big(data))
        if [unpacked(check[n]) for n in SEASON_FILES] != texts:
            raise ScheduleError("the new schedule.big didn't read back right; nothing was changed")
    with open(big + ".new", "wb") as f:
        f.write(data)
    os.replace(big + ".new", big)
    return entry["games"]
