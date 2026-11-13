"""MVP Baseball 2005 GameCube roster saves (.gci) to Xbox roster data, with spy_jam's dynasty converter's tables.

A roster save is a dynasty save without its settings header and its season sections: the roster's payload is the
dynasty stream from 0x2D6 on (its settings header ends at GC 0x2D2 / Xbox 0x2CF) through the 25 tagged tables, then the
stream-end marker and filler. So the dynasty converter's roster steps (org records, team season records, team
table, roster blocks, post-roster tables and managers, the tagged per-player tables) convert it, run on the roster
with a blank header put in front, in its own coordinates. The dynasty-only steps (settings, schedules, user section,
history) are left out. The Xbox side is built on your own Xbox roster save, as the dynasty converter builds on a
dynasty: the result goes through rosters05.to_xbox's header and checks.
"""
import os
import struct

import dynasty05 as DY
import rosters05 as RO

# what a dynasty has before a roster's first byte: its settings header (GC 0x2D2, Xbox 0x2CF: the GameCube keeps 3
# pad bytes in it) and 4 bytes. The roster itself starts the same on both
GC_HEAD, XB_HEAD = 0x2D6, 0x2D3
MARKER = b"\x0d\xf0\xef\xbe"


class GcRosterError(Exception):
    pass


def read_gc(data):
    """The roster payload of a GameCube roster .gci (checked), as bytes."""
    if len(data) < 0x40 or data[:4] != b"GV4E":
        raise GcRosterError("not an MVP 2005 GameCube save (.gci from Dolphin)")
    with DY._in_lib():
        C, _, _, GCS = DY._libs()
        try:
            meta = C.parse_gc(data)
        except Exception as e:
            raise GcRosterError(f"not a GameCube save this reads ({e})")
        try:
            good = GCS.check(bytearray(data))
        except Exception:
            good = False
    if meta.get("typ") != "Rosters":
        raise GcRosterError(f"that's a {meta.get('typ') or 'different'} save, not rosters")
    if not good:
        raise GcRosterError("the GameCube save's checksums don't match: it's damaged or edited")
    p = bytes(meta["payload"])
    if len(p) != RO.SIZE:
        raise GcRosterError("that GameCube roster save isn't the size MVP 2005's are")
    return p, meta


def convert_body(gc_body, xb_body):
    """GameCube roster payload -> Xbox roster body (RO.SIZE bytes), built on xb_body (an Xbox roster's)."""
    with DY._in_lib():
        import gc2xb_v0 as G
        import mgrconv
        import rosterblock
        import struct as st
        import tablesconv
        import teamconv
        gc = bytes(GC_HEAD) + gc_body
        xb = bytes(XB_HEAD) + xb_body
        reps = []
        try:
            # the dynasty converter's steps 1-4, as gc2xb_v0.convert runs them
            maps = teamconv.load()
            t = b"".join(teamconv.gc_to_xb(gc[0x1b42 + 60 * i:0x1b42 + 60 * i + 60], maps) for i in range(126))
            reps.append((0x1b3f, 0x1b3f + 7560, t))
            P = gc.find(G.KEYG, 0x12000)
            pos, i = [], 0x38ce
            while i < P:
                if G.SIG.match(gc, i):
                    pos.append(i)
                    i += 48
                else:
                    i += 1
            st_ = [pos[k] for k in range(0, len(pos), 4)]
            if len(st_) != 126:
                raise GcRosterError(f"the roster blocks aren't where they should be ({len(st_)} teams found)")
            st_.append(P)
            ros = b"".join(rosterblock.conv(gc[st_[k]:st_[k + 1]]) for k in range(126))
            Q = xb.find(G.KEYX, 0x12000)
            out = bytearray()
            p = P
            for tno in range(3):
                out += G.s32(gc[p:p + 4])
                d = gc[p + 4:p + 4 + 504]
                out += b"".join(d[i:i + 2][::-1] for i in range(0, len(d), 2)) if tno == 2 else d
                p += 508
            hdr, n = st.unpack(">II", gc[p:p + 8])
            out += G.s32(gc[p:p + 8])
            p += 8
            out += G.s32(gc[p:p + 12 * n])
            p += 12 * n
            out += G.s32(gc[p:p + 28])
            p += 28
            out += mgrconv.gc_table_to_xb(gc[p:p + 48 * n], n)
            p += 48 * n
            q = Q + 1524
            hx, nx = st.unpack("<II", xb[q:q + 8])
            qe = q + 8 + 12 * nx + 28 + 44 * nx
            reps.append((0x38cb, Q + 1524, ros + bytes(out)[:1524]))
            reps.append((Q + 1524, qe, bytes(out)[1524:]))
            # the tagged tables, the org records and the team season records (not the dynasty settings header)
            tr = [r for r in tablesconv.table_reps(gc, xb) if not (r[0] == 0 and r[1] == 0x2cf)]
            reps += tr
        except GcRosterError:
            raise
        except Exception as e:
            raise GcRosterError(f"this roster couldn't be converted ({e})")
    new = bytearray(xb)
    delta = 0
    for a, b, c in sorted(reps, key=lambda r: -r[0]):
        new[a:b] = c
        delta += len(c) - (b - a)
    body = new[XB_HEAD:]
    # the stream end: its marker and offset moved with the tables; then the filler, the 16-bit value 0xBB55 at every
    # even offset (55 BB in Xbox byte order), as in every MVP 2005 save
    j = body.rfind(MARKER, 0, RO.SIZE + max(delta, 0))
    if j < 0:
        raise GcRosterError("the converted roster has no end marker")
    f = j + 4
    struct.pack_into("<I", body, f, f)
    body = body[:f + 4]
    if len(body) > RO.SIZE - 144:
        raise GcRosterError("the converted roster doesn't fit an Xbox roster save")
    body += bytes(0x55 if k % 2 == 0 else 0xBB for k in range(len(body), RO.SIZE))
    return bytes(body)


def to_xbox(gci, xbox_save):
    """A GameCube roster .gci as an Xbox data.dat, with xbox_save's header (one of your Xbox roster saves)."""
    gc_body, _ = read_gc(gci)
    try:
        target = RO.read(xbox_save)
    except RO.RosterError as e:
        raise GcRosterError(f"your roster save it goes into can't be read ({e})")
    if target.platform != RO.XBOX:
        raise GcRosterError("the save to write into isn't an Xbox roster save")
    body = convert_body(gc_body, target.body)
    save = RO.Save(RO.XBOX, None, body)
    try:
        RO.locate(body, RO.XBOX)
    except RO.RosterError as e:
        raise GcRosterError(f"the converted roster didn't come out right, built on that save ({e})")
    try:
        return RO.to_xbox(save, xbox_save)
    except RO.RosterError as e:
        raise GcRosterError(f"the converted roster didn't pass the Xbox roster checks ({e})")
