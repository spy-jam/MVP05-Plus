"""MVP Baseball 2005 dynasty saves between the GameCube and the Xbox (dynasty mode; owner mode saves are refused).

  read_gc(data)                     a GameCube dynasty .gci (Dolphin) checked: {name, typ, payload}
  gc_to_xbox(gci, xbox_dynasty)     the .gci's dynasty as an Xbox data.dat, built on one of your own Xbox dynasty
                                    saves (it gives the signature layout, the save's name and the older real-life
                                    history seasons: the GameCube keeps 6 per player, the Xbox 16)
  xbox_to_gc(data, gc_dynasty)      an Xbox dynasty as a .gci, built on one of your own GameCube dynasty saves

The conversion is spy_jam's GameCube save converter (mvp05/lib, its notes in mvp05/FORMAT_NOTES.md). Its modules
read their .json tables from their own folder when they're first imported, so they're imported and run from there,
one conversion at a time.
"""
import contextlib
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
# beside this file, or in the Launcher exe, where the modules and their .json tables are bundled
LIB = os.path.join(getattr(sys, "_MEIPASS", HERE), "mvp05", "lib")
GC_OFF, GC_LEN = 0x2138, 0x186C00
XB_OFF, XB_LEN = 0x108, 0x222C00
XB_DYNASTY_SIZE = XB_OFF + XB_LEN  # 2,239,752 bytes
_lock = threading.Lock()


class DynastyError(Exception):
    pass


@contextlib.contextmanager
def _in_lib():
    with _lock:
        old = os.getcwd()
        if LIB not in sys.path:
            sys.path.insert(0, LIB)
        os.chdir(LIB)
        try:
            yield
        finally:
            os.chdir(old)


def _libs():
    import containers
    import gc2xb_v0
    import gc_checksums
    import xb2gc
    return containers, gc2xb_v0, xb2gc, gc_checksums


def read_gc(data):
    if len(data) < GC_OFF + GC_LEN or data[:4] != b"GV4E":
        raise DynastyError("not an MVP 2005 GameCube save (.gci from Dolphin)")
    with _in_lib():
        C, _, _, GCS = _libs()
        try:
            meta = C.parse_gc(data)
        except Exception as e:
            raise DynastyError(f"not a GameCube save this reads ({e})")
        try:
            good = GCS.check(bytearray(data))
        except Exception:
            good = False
        if not good:
            raise DynastyError("the GameCube save's checksums don't match: it's damaged or edited")
    if meta.get("typ") != "Dynasty":
        raise DynastyError(f"that's a {meta.get('typ') or 'different'} save: only dynasties convert")
    return meta


def read_xbox(data):
    with _in_lib():
        C = _libs()[0]
        try:
            meta = C.parse_xbox(data)
        except Exception as e:
            raise DynastyError(f"not an Xbox MVP 2005 save this reads ({e})")
        meta["verified"] = bool(C.verify_xbox(data))
    if meta.get("typ") != "Dynasty":
        raise DynastyError(f"that's a {meta.get('typ') or 'different'} save: only dynasties convert")
    return meta


def gc_to_xbox(gci, xbox_dynasty, name=None):
    """The GameCube dynasty as an Xbox data.dat, built on xbox_dynasty (keeping its name unless name is given)."""
    read_gc(gci)
    t = read_xbox(xbox_dynasty)
    with _in_lib():
        C, G, _, _ = _libs()
        try:
            new, _, _ = G.convert(gci[GC_OFF:GC_OFF + GC_LEN], xbox_dynasty[XB_OFF:XB_OFF + XB_LEN], sched=True,
                                  hist=True)
        except Exception as e:
            raise DynastyError(f"this dynasty couldn't be converted ({e})")
        out = C.build_xbox(xbox_dynasty, dict(name=name or t["name"], typ="Dynasty", flags=t["flags"], payload=new))
        if not C.verify_xbox(out):
            raise DynastyError("the converted save failed its signature check")
    return out


def xbox_to_gc(data, gc_dynasty, name=None):
    """An Xbox dynasty as a GameCube .gci, built on gc_dynasty: (file name, bytes). Names are up to 10 letters."""
    meta = read_xbox(data)
    g = read_gc(gc_dynasty)
    name = (name or g["name"] or "DYNASTY")[:10]
    with _in_lib():
        C, _, R, GCS = _libs()
        try:
            payload = R.convert(meta["payload"], gc_dynasty[GC_OFF:GC_OFF + GC_LEN])
        except Exception as e:
            raise DynastyError(f"this dynasty couldn't be converted ({e})")
        out = C.build_gc(gc_dynasty, dict(name=name, typ="Dynasty", flags=g["flags"], payload=payload))
        if not GCS.check(bytearray(out)):
            raise DynastyError("the converted .gci failed its checksum check")
    return f"69-GV4E-Dynasty_{name}.dat.gci", out
