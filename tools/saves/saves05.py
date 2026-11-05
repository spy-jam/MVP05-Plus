"""MVP Baseball 2005 dynasty saves: the game's own (Xbox, in hdd beside MVP05.exe) and GameCube conversions.

Experimental. The converters (mvp05/, see docs/SAVE-CONVERSION.md) were tested on mid-season dynasties, loaded
and played in the recomp and in Dolphin; playoff saves are untested.

  hdd/E/UDATA/45410056/<12-hex folder>/   data.dat, SaveMeta.xbx (UTF-16LE with BOM: "Name=<name> (<type>)"),
                                          saveimage.xbx

GameCube -> Xbox overwrites a dynasty you already have (it's the template: creating a new save folder hasn't been
tested), after copying that folder into "save backups". Xbox -> GameCube writes a .gci beside the GameCube
template you pick (another GameCube dynasty .gci), for Dolphin's Memory Card Manager to import.
"""
import datetime
import struct
import os
import shutil
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "mvp05", "lib")  # (in the Tools exe the modules and their .json tables are bundled)
TITLE = "45410056"
GC_PAYLOAD_OFF, GC_PAYLOAD_LEN = 0x2138, 0x186C00
XB_PAYLOAD_OFF, XB_PAYLOAD_LEN = 0x108, 0x222C00
_lock = threading.Lock()


class SaveError(Exception):
    pass


def _lib():
    if LIB not in sys.path:
        sys.path.insert(0, LIB)
    import containers
    import gc_checksums
    return containers, gc_checksums


def udata(root):
    return os.path.join(root, "hdd", "E", "UDATA", TITLE)


def game_running():
    if os.name != "nt":
        return False
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq MVP05.exe", "/NH"], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return "mvp05.exe" in r.stdout.lower()
    except OSError:
        return False


def savemeta_name(folder):
    try:
        with open(os.path.join(folder, "SaveMeta.xbx"), "rb") as f:
            b = f.read()
        t = b.decode("utf-16-le" if b[:2] == b"\xff\xfe" else "latin-1").lstrip("﻿")
        for line in t.splitlines():
            if line.startswith("Name="):
                return line[5:].strip()
    except OSError:
        pass
    return ""


def list_saves(root):
    """[{folder, id, name, type, when}] newest first; type is the game's ("Dynasty", "Season", ...)."""
    C, _ = _lib()
    out = []
    base = udata(root)
    if not os.path.isdir(base):
        return out
    for d in os.listdir(base):
        folder = os.path.join(base, d)
        dat = os.path.join(folder, "data.dat")
        if not os.path.isfile(dat):
            continue
        name, typ = savemeta_name(folder), ""
        try:
            with open(dat, "rb") as f:
                m = C.parse_xbox(f.read(XB_PAYLOAD_OFF))
            name, typ = m["name"] or name, m["typ"]
        except Exception:
            pass
        out.append(dict(folder=folder, id=d, name=name or d, type=typ or "?",
                        when=datetime.datetime.fromtimestamp(os.path.getmtime(dat))))
    return sorted(out, key=lambda s: s["when"], reverse=True)


def backup_folder(root, folder, why):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H.%M.%S")
    dest = os.path.join(root, "save backups", f"{stamp} before {why}", os.path.basename(folder))
    shutil.copytree(folder, dest)
    return dest


def _check_not_running():
    if game_running():
        raise SaveError("close MVP05.exe first: the game keeps its saves open while it runs")


def import_gamecube(root, gci_path, folder, name=None, say=print):
    """A GameCube dynasty .gci into this Xbox dynasty's folder (replacing it, after a backup)."""
    _check_not_running()
    with open(gci_path, "rb") as f:
        gci = f.read()
    if len(gci) < GC_PAYLOAD_OFF + GC_PAYLOAD_LEN or gci[:4] != b"GV4E":
        raise SaveError("that isn't an MVP 2005 GameCube dynasty .gci (no GV4E game id)")
    dat = os.path.join(folder, "data.dat")
    with open(dat, "rb") as f:
        xf = f.read()
    with _lock:
        C, _ = _lib()
        import gc2xb_v0 as G
        try:
            tmeta = C.parse_xbox(xf)
        except Exception as e:
            raise SaveError(f"the Xbox save there isn't readable: {e}")
        if tmeta.get("typ") != "Dynasty":
            raise SaveError(f"that Xbox save is a {tmeta.get('typ')} save: pick a Dynasty save to replace")
        gmeta = C.parse_gc(gci)
        name = (name or gmeta["name"] or tmeta["name"])[:16]
        say(f"Converting {os.path.basename(gci_path)} ({gmeta['name']})...")
        try:
            new, _, _ = G.convert(gci[GC_PAYLOAD_OFF:GC_PAYLOAD_OFF + GC_PAYLOAD_LEN],
                                  xf[XB_PAYLOAD_OFF:XB_PAYLOAD_OFF + XB_PAYLOAD_LEN], sched=True, hist=True)
            out = C.build_xbox(xf, dict(name=name, typ="Dynasty", flags=tmeta["flags"], payload=new))
        except Exception as e:
            raise SaveError(f"the converter stopped ({type(e).__name__}: {e}); nothing was written")
        if not C.verify_xbox(out):
            raise SaveError("the converted save didn't pass its signature check; nothing was written")
        meta = C.xbox_savemeta(name, "Dynasty")
    b = backup_folder(root, folder, "GameCube import")
    say(f"Backed up the old save to {os.path.relpath(b, root)}")
    with open(dat + ".part", "wb") as f:
        f.write(out)
    os.replace(dat + ".part", dat)
    with open(os.path.join(folder, "SaveMeta.xbx"), "wb") as f:
        f.write(meta)
    say(f"Done: \"{name}\" is in the game's saves. Load it from Dynasty mode.")


def export_gamecube(root, folder, gc_template, out_dir, name=None, say=print):
    """This Xbox dynasty as a GameCube .gci, built on a GameCube dynasty .gci (for Dolphin)."""
    _check_not_running()
    with open(os.path.join(folder, "data.dat"), "rb") as f:
        xf = f.read()
    with open(gc_template, "rb") as f:
        gtf = f.read()
    if len(gtf) < GC_PAYLOAD_OFF + GC_PAYLOAD_LEN or gtf[:4] != b"GV4E":
        raise SaveError("the GameCube template isn't an MVP 2005 GameCube dynasty .gci (no GV4E game id)")
    with _lock:
        C, GCS = _lib()
        import xb2gc as R
        try:
            meta = C.parse_xbox(xf)
        except Exception as e:
            raise SaveError(f"the Xbox save isn't readable: {e}")
        if meta.get("typ") != "Dynasty":
            raise SaveError(f"that's a {meta.get('typ')} save: only Dynasty saves convert")
        if not C.verify_xbox(xf):
            say("Note: the Xbox save's signature doesn't check out; converting anyway.")
        gmeta = C.parse_gc(gtf)
        name = "".join(c for c in (name or meta["name"] or gmeta["name"] or "DYNASTY") if c.isalnum())[:10] or "DYNASTY"
        say(f"Converting {meta['name']}...")
        try:
            payload = R.convert(meta["payload"], gtf[GC_PAYLOAD_OFF:GC_PAYLOAD_OFF + GC_PAYLOAD_LEN])
            out = C.build_gc(gtf, dict(name=name, typ="Dynasty", flags=gmeta["flags"], payload=payload))
        except Exception as e:
            raise SaveError(f"the converter stopped ({type(e).__name__}: {e}); nothing was written")
        if not GCS.check(bytearray(out)):
            raise SaveError("the converted .gci didn't pass its checksum check; nothing was written")
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, f"69-GV4E-Dynasty_{name}.dat.gci")
    if os.path.exists(dst):
        n = 1
        while os.path.exists(f"{dst}.bak{n}"):
            n += 1
        shutil.copyfile(dst, f"{dst}.bak{n}")
    with open(dst, "wb") as f:
        f.write(out)
    say(f"Done: {dst}\nIn Dolphin: Tools > Memory Card Manager > Import. A dynasty takes 197 of a 251-block card's "
        f"blocks, so it needs a card with no other dynasty on it.")
    return dst


# ---------------------------------------------------------------- standings for short seasons
#
# The standings are the first of the three per-team tables after the rosters (docs/SAVE-CONVERSION.md 3.2): the
# post-roster key 6ABC3D69 (Xbox), then 126 teams x [W][L][0][0], the 30 MLB teams first in the patcher's order.
# The same table the memory patcher writes in the running game; here it's written into the save, so it's done
# with the game closed and the save is backed up first. The game has no stored date: the season is over when the
# MLB schedule (the first of the four after marker 2) has no unplayed game.

MLB_TEAMS = ["ANA", "OAK", "SEA", "TEX", "CWS", "CLE", "DET", "KC", "MIN", "BAL", "BOS", "NYY", "TB", "TOR", "ARI",
             "COL", "LAD", "SD", "SF", "CHC", "CIN", "HOU", "MIL", "PIT", "STL", "ATL", "FLA", "WAS", "NYM", "PHI"]
POST_ROSTER_KEY = b"\x6a\xbc\x3d\x69"
MARKER = b"\x0d\xf0\xef\xbe"
MLB_SCHEDULE_CAP = 2442


def project(w, l, games=162):
    """The memory patcher's projection: the same winning percentage over a full season."""
    gp = w + l
    if gp == 0:
        return games // 2, games - games // 2
    pw = max(0, min(games, round(w / gp * games)))
    return pw, games - pw


def _standings_at(payload):
    q = payload.find(POST_ROSTER_KEY, 0x12000)
    if q < 0:
        raise SaveError("couldn't find the standings in this save (no post-roster table)")
    t = q + 4
    recs = [(payload[t + 4 * i], payload[t + 4 * i + 1]) for i in range(30)]
    if any(payload[t + 4 * i + 2] or payload[t + 4 * i + 3] for i in range(30)):
        raise SaveError("the standings table isn't laid out as expected ([W][L][0][0] per team); nothing written")
    return t, recs


def _schedule_progress(payload):
    """(played, scheduled) games in the MLB schedule."""
    marks = []
    i = payload.find(MARKER)
    while i >= 0 and len(marks) < 7:
        marks.append(i)
        i = payload.find(MARKER, i + 4)
    if len(marks) < 4:
        return None
    p = marks[2] + 4
    n = struct.unpack_from("<I", payload, p)[0]
    if n > MLB_SCHEDULE_CAP:
        return None
    played = sum(1 for k in range(n) if (struct.unpack_from("<H", payload, p + 4 + 28 * k + 2)[0] >> 11) & 0x1F)
    return played, n


def read_standings(folder):
    """{name, records [(team, W, L)], played, scheduled} of a dynasty save."""
    C, _ = _lib()
    with open(os.path.join(folder, "data.dat"), "rb") as f:
        xf = f.read()
    m = C.parse_xbox(xf)
    if m.get("typ") != "Dynasty":
        raise SaveError(f"that's a {m.get('typ')} save: standings are in Dynasty saves")
    _, recs = _standings_at(m["payload"])
    prog = _schedule_progress(m["payload"]) or (None, None)
    return dict(name=m["name"], records=[(t, w, l) for t, (w, l) in zip(MLB_TEAMS, recs)],
                played=prog[0], scheduled=prog[1])


def patch_standings(root, folder, games=162, say=print):
    """Every MLB team's record projected to `games` games in the save (backed up first)."""
    _check_not_running()
    C, _ = _lib()
    dat = os.path.join(folder, "data.dat")
    with open(dat, "rb") as f:
        xf = f.read()
    m = C.parse_xbox(xf)
    if m.get("typ") != "Dynasty":
        raise SaveError(f"that's a {m.get('typ')} save: pick a Dynasty save")
    if not C.verify_xbox(xf):
        raise SaveError("that save's signature doesn't check out; it's left as it is")
    payload = bytearray(m["payload"])
    t, recs = _standings_at(payload)
    if not any(w + l for w, l in recs):
        raise SaveError("no MLB team has played a game in this save yet")
    if all(w + l == games for w, l in recs):
        raise SaveError(f"every team already has {games} games: this save's standings are already projected")
    for i, (w, l) in enumerate(recs):
        pw, pl = project(w, l, games)
        payload[t + 4 * i], payload[t + 4 * i + 1] = pw, pl
    out = C.build_xbox(xf, dict(name=m["name"], typ="Dynasty", flags=m["flags"], payload=bytes(payload)))
    if not C.verify_xbox(out):
        raise SaveError("the patched save didn't pass its signature check; nothing written")
    b = backup_folder(root, folder, "standings patch")
    say(f"Backed up the save to {os.path.relpath(b, root)}")
    with open(dat + ".part", "wb") as f:
        f.write(out)
    os.replace(dat + ".part", dat)
    say(f"Done: {m['name']}'s standings are projected to {games} games. Load it in the game and advance to the "
        f"playoffs, then save.")
