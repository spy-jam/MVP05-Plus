"""Player of the Day for the Launcher's Play tab: one MLB player a day, the same one for everyone, with his picture,
read from the player's own installed game (nothing of EA's is shipped).

  assets/data/database/database.big   the disc's default database: EA BIGF of RefPack'd text tables
                                      ("<id>,0 <value>,1 <value>,...;\\r\\n" rows under a header row)
  assets/data/frontend/portrait.big   the headshots: one <audioid>.xsh per player (a RefPack'd SHPX holding one
                                      128 x 128 swizzled 32-bit Xbox texture), named by attrib.dat's
                                      playerattrib_audioid as 4 digits

The players are the 30 MLB franchises' default 25-man rosters (org.dat's org_is_franchise; the All-Star, Legends and
Heroes teams aren't franchises), only those with a picture, sorted by player id. The day picks one by SHA-256 of
the local date (YYYY-MM-DD), so everyone sees the same player on the same date, whatever their saves hold.
"""
import datetime
import hashlib
import os
import struct

from schedules import ScheduleError, refpack_decompress

DB = ("assets", "data", "database", "database.big")
PORTRAITS = ("assets", "data", "frontend", "portrait.big")
POS = {0: "SP", 10: "RP", 1: "C", 2: "1B", 3: "2B", 4: "3B", 5: "SS", 6: "LF", 7: "CF", 8: "RF", 9: "DH"}
TABLES = ("attrib.dat", "roster.dat", "team.dat", "org.dat", "lhbstats.dat", "rhbstats.dat", "pstats.dat",
          "lhpstats.dat", "rhpstats.dat")


class PotdError(Exception):
    pass


def _big_dir(f):
    """{name: (offset, size)} of an open EA BIGF archive, reading only its header."""
    head = f.read(16)
    if head[:4] not in (b"BIGF", b"BIG4"):
        raise PotdError("not a BIG archive")
    n, hlen = struct.unpack(">II", head[8:16])
    d = head + f.read(max(0, hlen - 16))
    out, p = {}, 16
    for _ in range(n):
        off, size = struct.unpack_from(">II", d, p)
        e = d.index(b"\0", p + 8)
        out[d[p + 8:e].decode("latin-1").lower()] = (off, size)
        p = e + 1
    return out


def _unpack(b):
    return refpack_decompress(b) if b[1:2] == b"\xfb" else b


def _rows(text):
    """id -> {column number: value} for one table."""
    out = {}
    for r in text.split(";\r\n")[1:]:
        r = r.strip()
        if not r:
            continue
        parts = r.rstrip(",").split(",")
        d = {}
        for q in parts[1:]:
            k, _, v = q.partition(" ")
            if k.isdigit():
                d[int(k)] = v
        out[parts[0]] = d
    return out


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def load(root):
    """The players to pick from: [{id, name, number, pos, team, photo, line}], sorted by id."""
    try:
        with open(os.path.join(root, *DB), "rb") as f:
            ents = _big_dir(f)
            t = {}
            for name in TABLES:
                off, size = ents[name]
                f.seek(off)
                t[name] = _rows(_unpack(f.read(size)).decode("latin-1"))
        with open(os.path.join(root, *PORTRAITS), "rb") as f:
            pics = _big_dir(f)
    except (OSError, KeyError, IndexError, ValueError, struct.error, ScheduleError) as e:
        raise PotdError(f"the game's player data can't be read ({e})")
    attrib, teams = t["attrib.dat"], t["team.dat"]
    team_of = {}
    for r in t["roster.dat"].values():
        team_of.setdefault(r.get(1), r.get(0))
    franchises = {format(_int(o.get(1)) & 0xFFFFFFFF, "09x") for o in t["org.dat"].values() if o.get(5) == "1"}
    out = []
    for pid, a in attrib.items():
        tid = team_of.get(pid)
        photo = "%04d.xsh" % _int(a.get(17), -1)
        if tid not in franchises or photo not in pics:
            continue
        tm = teams.get(tid, {})
        name = " ".join(x for x in (a.get(0, "").strip(), a.get(1, "").strip()) if x)
        out.append(dict(id=pid, name=name, number=a.get(2, ""), pos=POS.get(_int(a.get(5), -1), ""),
                        team=f"{tm.get(1, '')} {tm.get(2, '')}".strip(), photo=photo, line=_line(pid, a, t)))
    if not out:
        raise PotdError("no players found in the game's data")
    return sorted(out, key=lambda p: p["id"])


def _line(pid, a, t):
    """His 2004 season, from the disc's stats: AVG / HR / RBI, or W-L / ERA (and saves)."""
    if _int(a.get(5), -1) in (0, 10):
        p = t["pstats.dat"].get(pid, {})
        outs = _int(p.get(13)) * 3 + _int(p.get(14))
        if not _int(p.get(2)) or not outs:
            return ""
        era = _int(p.get(5)) * 27 / outs
        so = sum(_int(t[k].get(pid, {}).get(2)) for k in ("lhpstats.dat", "rhpstats.dat"))
        line = f"{_int(p.get(6))}-{_int(p.get(7))}, {era:.2f} ERA"
        sv = _int(p.get(8))
        return f"2004: {line}, {sv} SV" if sv else f"2004: {line}, {so} K"
    h = ab = hr = rbi = 0
    for k in ("lhbstats.dat", "rhbstats.dat"):
        s = {i: _int(v) for i, v in t[k].get(pid, {}).items()}
        hits = s.get(2, 0) + s.get(3, 0) + s.get(4, 0) + s.get(5, 0)
        h += hits
        hr += s.get(5, 0)
        rbi += s.get(6, 0)
        ab += s.get(13, 0) - s.get(8, 0) - s.get(10, 0) - s.get(11, 0) - s.get(12, 0)
    if ab <= 0:
        return ""
    avg = f"{h / ab:.3f}".lstrip("0")
    return f"2004: {avg} AVG, {hr} HR, {rbi} RBI"


def pick(players, day=None):
    """The day's player: the same for everyone on the same (local) date."""
    day = day or datetime.date.today()
    h = int.from_bytes(hashlib.sha256(day.isoformat().encode()).digest()[:8], "big")
    return players[h % len(players)]


def _morton(w, h):
    idx = []
    for y in range(h):
        for x in range(w):
            o = i = 0
            sx, sy, mw, mh = x, y, w, h
            while mw > 1 or mh > 1:
                if mw > 1:
                    o |= (sx & 1) << i
                    sx >>= 1
                    i += 1
                    mw >>= 1
                if mh > 1:
                    o |= (sy & 1) << i
                    sy >>= 1
                    i += 1
                    mh >>= 1
            idx.append(o)
    return idx


def picture(root, player):
    """His headshot as a PIL image (RGBA)."""
    from PIL import Image
    try:
        with open(os.path.join(root, *PORTRAITS), "rb") as f:
            off, size = _big_dir(f)[player["photo"]]
            f.seek(off)
            u = _unpack(f.read(size))
    except (OSError, KeyError, IndexError, ValueError, struct.error, ScheduleError) as e:
        raise PotdError(f"his picture can't be read ({e})")
    if u[:4] != b"SHPX":
        raise PotdError("his picture isn't an Xbox texture")
    o = struct.unpack_from("<I", u, 20)[0]
    kind = u[o]
    w, h = struct.unpack_from("<HH", u, o + 4)
    if kind != 0x7D or w * h * 4 > len(u) - o - 16:
        raise PotdError(f"his picture is in a format this doesn't read ({kind:#x})")
    data = u[o + 16:o + 16 + w * h * 4]
    px = bytearray(w * h * 4)
    for n, i in enumerate(_morton(w, h)):
        b, g, r, al = data[i * 4:i * 4 + 4]
        px[n * 4:n * 4 + 4] = bytes((r, g, b, al))
    return Image.frombytes("RGBA", (w, h), bytes(px))


def today(root, day=None):
    """(player, picture or None) for the day."""
    p = pick(load(root), day)
    try:
        return p, picture(root, p)
    except PotdError:
        return p, None
