"""MVP Baseball 2005 PC dynasty saves (<name>_Dynasty.sav) to Xbox dynasty saves (owner mode saves are refused).

  is_dynasty(data)              whether data is a PC dynasty save (then read() it)
  read(data)                    a PC dynasty, checked: {name, body}
  to_xbox(data, xbox_dynasty)   the PC dynasty as an Xbox data.dat, built on one of your own Xbox dynasty saves (it
                                keeps that save's name and gives the Xbox's own platform words)

The PC stores a dynasty the way the Xbox does: the same body size, 44-byte managers, the same player records, 16
history seasons per player, the same object records after the schedules (as its rosters are the Xbox's, in Mad Dog's
notes). Only the settings header differs: 70 option ints, as on the PS2 (your Xbox save gives the 2 more), and 14
PC-only ints after marker 0 (48 bytes in all, left out). The platform words that differ between the PS2 and the Xbox
have PC values of their own too: the Xbox's are kept, as for the PS2 (ps2dynasty05).
"""
import struct

import dynasty05 as DY
import ps2dynasty05 as PD
import rosters05 as RO

HEAD = 200
SIZE = DY.XB_LEN  # the PC's body is the Xbox's size
PC_HEAD = 0x2FF   # marker 1 (the Xbox's is at 0x2CF)
SHIFT = 0x2CF - PC_HEAD
OBJECTS = PD.OBJECTS


class PcDynastyError(Exception):
    pass


def _check(ok, why):
    if not ok:
        raise PcDynastyError(why)


def _u32(b, p):
    return struct.unpack_from("<I", b, p)[0]


def is_dynasty(data):
    return len(data) == HEAD + SIZE and _u32(data, 16) == HEAD and _u32(data, 20) == SIZE


def _layout(d):
    """Where this converts things, in a PC dynasty body: the Xbox layout from marker 1 on, 48 bytes later."""
    m = PD._markers(d)
    _check(len(m) == 7 and m[1] == PC_HEAD and _u32(d, m[6] + 4) == m[6] + 4,
           "not an MVP 2005 dynasty this reads (its sections aren't there)")
    q = d.find(PD.KEYLIST, 0x12000)
    _check(q > 0, "the dynasty's rosters aren't where they should be")
    q += 1524
    _, n = struct.unpack_from("<II", d, q)
    _check(20 <= n <= 40, "the dynasty's managers aren't where they should be")
    mgr = q + 8 + 12 * n + 28
    _check(d[mgr - 4:mgr] == PD.TAG, "the dynasty's managers aren't where they should be")
    after = mgr + 44 * n
    tags = [mgr - 4] + PD._tags(d, after, m[2])
    _check(len(tags) == 24, f"the dynasty's tables aren't where they should be ({len(tags)} found)")
    _check(tags[8] - tags[7] - 4 == PD.PLAYERS * PD.ROW, "the dynasty's player table isn't the size this reads")
    tail = m[2] + 4 + PD.SCHED_BYTES
    _check(m[3] - tail == PD.TAIL_XB, "the dynasty's season sections aren't the size this reads")
    _check(m[5] - m[3] == 420, "the dynasty's user section isn't the size this reads")
    PD._history(d, m)  # checks it reads
    return dict(m=m, n=n, mgr=mgr, after=after, tags=tags, tail=tail)


def read(data):
    """A PC dynasty save, checked: {name, body}."""
    data = bytes(data)
    _check(is_dynasty(data), "not a PC MVP 2005 dynasty save")
    typ = data[0x48:0x88].decode("utf-16-le", "replace").split("\0")[0]
    _check(typ == "Dynasty", f"that's a{'n' if typ[:1] in 'AEIOU' else ''} {typ or 'different'} save: only "
                             "dynasties convert (owner mode is coming later)")
    _check(_u32(data, 0) == RO.crc(data[16:HEAD]) and _u32(data, 4) == RO.crc(data[HEAD:]),
           "the PC save's checksums don't match: it's damaged or edited")
    body = data[HEAD:]
    try:
        _layout(body)
    except (struct.error, IndexError, PD.Ps2DynastyError):
        raise PcDynastyError("not an MVP 2005 dynasty this reads")
    return dict(name=data[0x28:0x48].decode("utf-16-le", "replace").split("\0")[0], body=body)


def convert_body(pc, xb):
    """A PC dynasty body -> an Xbox dynasty body, built on xb (one of your Xbox dynasties')."""
    _check(len(pc) == SIZE and len(xb) == DY.XB_LEN, "the saves aren't the size MVP 2005 dynasties are")
    try:
        L, T = _layout(pc), PD._layout(xb, False)
    except (struct.error, IndexError, PD.Ps2DynastyError) as e:
        raise PcDynastyError(f"the dynasty isn't one this reads ({e})")
    _check(L["n"] == T["n"], "the two dynasties don't have the same number of managers")
    # settings header: 70 option ints (your Xbox save's 2 more after the 21st), the 2 flag bytes, the name buffer,
    # ints and sliders, marker 0 and its value, then 7 bytes (5 unset, 2 kept); the PC's own 14 ints are left out
    out = bytearray(pc[0:84] + xb[84:92] + pc[84:0x11A] + pc[0x11A:0x2C0] + xb[0x2C8:0x2CD] + pc[0x2C5:0x2C7])
    _check(len(out) == 0x2CF, "the settings header came out the wrong size")
    end = L["m"][6]
    out += pc[PC_HEAD:end]
    # the org records' 8 platform words (6-13) and the ones at the start of the tables after the managers: the
    # Xbox's
    for i in range(34):
        o = 0x477 + 0x54 * i + 24
        out[o:o + 32] = xb[o:o + 32]
    at = L["after"] + SHIFT + 96
    out[at:at + 4] = xb[T["after"] + 96:T["after"] + 100]
    for k, offs in PD.FIXED:
        for o in offs:
            at = L["tags"][k] + SHIFT + o
            out[at:at + 4] = xb[T["tags"][k] + o:T["tags"][k] + o + 4]
    # the object records after the schedules: your Xbox save's (they hold the platform's pointers)
    a = L["tail"] + SHIFT + OBJECTS
    out[a:L["m"][3] + SHIFT] = xb[T["tail"] + OBJECTS:T["m"][3]]
    # the stream end: its marker and offset, then the filler (0xBB55 at even offsets)
    f = len(out) + 4
    out += PD.MARKER + struct.pack("<I", f)
    out += bytes(0x55 if k % 2 == 0 else 0xBB for k in range(len(out), DY.XB_LEN))
    _check(len(out) == DY.XB_LEN, "the converted dynasty came out the wrong size")
    return bytes(out)


def to_xbox(data, xbox_dynasty, name=None):
    """A PC dynasty (.sav) as an Xbox data.dat, built on xbox_dynasty (keeping its name unless name is given)."""
    src = read(data) if not isinstance(data, dict) else data
    try:
        t = DY.read_xbox(xbox_dynasty)
    except DY.DynastyError as e:
        raise PcDynastyError(str(e))
    new = convert_body(src["body"], t["payload"])
    with DY._in_lib():
        C = DY._containers()
        out = C.build_xbox(xbox_dynasty, dict(name=name or t["name"], typ="Dynasty", flags=t["flags"], payload=new))
        _check(C.verify_xbox(out), "the converted save failed its signature check")
    return out
