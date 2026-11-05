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
