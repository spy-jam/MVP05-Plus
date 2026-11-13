"""MVP Baseball 2005 PS2 dynasty saves to Xbox dynasty saves (dynasty mode; owner mode saves are refused).

  read(data)                    a PS2 dynasty, checked: a .psu, the .sav taken out of one, or (with ps2card) a save
                                on a PCSX2 memory card. {name, body}
  to_xbox(data, xbox_dynasty)   the PS2 dynasty as an Xbox data.dat, built on one of your own Xbox dynasty saves (it
                                keeps that save's name, gives the Xbox's own platform words and the older real-life
                                history seasons: the PS2 keeps 6 per player, the Xbox 16)

Learned on a matched pair (a new Yankees dynasty saved straight away on each platform). The PS2 stores the dynasty
the way the Xbox does (little-endian, the same bitfield order), in the same stream of sections as the GameCube
(spy_jam's converter's notes, mvp05/FORMAT_NOTES.md). What's different:
  - the settings header: 70 option ints, not 72 (the 2 the PS2 doesn't have come from your Xbox save), and the
    GameCube's 3 pad bytes between its 2 flag bytes
  - the 34 manager records: 48 bytes, not 44, and 8 more zero bytes after them (Mad Dog's PS2 roster rule)
  - the 3250 player records: their pad byte at the end, not at byte 31 (Mad Dog's PS2 roster rule)
  - a few words that are the same in every PS2 dynasty and the same in every Xbox one (in the org records and at the
    start of the tables after the managers): the Xbox's are kept
  - the object records after the schedules (72 bytes longer: platform pointers): kept from your Xbox save, as the
    GameCube converter does
  - the player history: the last 6 seasons per player, not 16; the older ones come from your Xbox save
Everything else is the same bytes on both: rosters, players' tables, schedules, trades, injuries, the user's team.
"""
import struct

import dynasty05 as DY
import rosters05 as RO

SIZE = 0x186C00  # a PS2 dynasty's body (the GameCube's is the same size); the Xbox's is DY.XB_LEN
HEAD = 200
MARKER = b"\x0d\xf0\xef\xbe"
TAG = struct.pack("<I", 0xF58F3C1B)
KEYLIST = b"\x6a\xbc\x3d\x69"
SCHED_BYTES = 4 * 4 + 28 * (2442 + 2172 + 2140 + 2112)
TAIL_PS2, TAIL_XB, OBJECTS = 2870, 2798, 2516
PLAYERS, ROW = 3250, 60
HISTORY = 16


class Ps2DynastyError(Exception):
    pass


def _check(ok, why):
    if not ok:
        raise Ps2DynastyError(why)


def _u32(b, p):
    return struct.unpack_from("<I", b, p)[0]


def _markers(d):
    out, i = [], d.find(MARKER)
    while i >= 0:
        out.append(i)
        i = d.find(MARKER, i + 1)
    return out


def _sections(d):
    """The 7 stream markers (the last one the stream end: its value is its own offset + 4)."""
    m = _markers(d)
    _check(len(m) == 7, "not an MVP 2005 dynasty this reads (its sections aren't there)")
    _check(_u32(d, m[6] + 4) == m[6] + 4, "not an MVP 2005 dynasty this reads (no stream end)")
    return m


def _tags(d, lo, hi):
    out, i = [], d.find(TAG, lo)
    while 0 <= i < hi:
        out.append(i)
        i = d.find(TAG, i + 1)
    return out


def _layout(d, ps2):
    """Where the sections this converts are, in d (a PS2 or an Xbox dynasty body)."""
    m = _sections(d)
    head = 0x2CA if ps2 else 0x2CF
    _check(d[head:head + 4] == MARKER and m[1] == head, "the dynasty's settings aren't the size this reads")
    q = d.find(KEYLIST, 0x12000)
    _check(q > 0, "the dynasty's rosters aren't where they should be")
    q += 1524
    _, n = struct.unpack_from("<II", d, q)
    _check(20 <= n <= 40, "the dynasty's managers aren't where they should be")
    mgr = q + 8 + 12 * n + 28
    _check(d[mgr - 4:mgr] == TAG, "the dynasty's managers aren't where they should be")
    after = mgr + (48 if ps2 else 44) * n
    tags = [mgr - 4] + _tags(d, after, m[2])
    _check(len(tags) == 24, f"the dynasty's tables aren't where they should be ({len(tags)} found)")
    k = d.find(struct.pack("<II", PLAYERS, PLAYERS), tags[5], tags[7])
    _check(k > 0, "the dynasty's player list isn't where it should be")
    keys = [struct.unpack_from("<Iii", d, k + 8 + 12 * i) for i in range(PLAYERS)]
    _check(all(0 <= a < PLAYERS for _, a, _ in keys), "the dynasty's player list isn't one this reads")
    players = tags[7] + 4
    _check(tags[8] - players == PLAYERS * ROW, "the dynasty's player table isn't the size this reads")
    tail = m[2] + 4 + SCHED_BYTES
    _check(m[3] - tail == (TAIL_PS2 if ps2 else TAIL_XB), "the dynasty's season sections aren't the size this reads")
    _check(m[5] - m[3] == 420, "the dynasty's user section isn't the size this reads")
    return dict(m=m, n=n, mgr=mgr, after=after, tags=tags, players=players, keys={k for k, _, _ in keys}, tail=tail)


def _history(d, m):
    p = m[5] + 4
    n = _u32(d, p)
    p += 4
    out = []
    for _ in range(n):
        _check(p + 5 <= m[6], "the dynasty's player history is cut short")
        k, c = _u32(d, p), d[p + 4]
        p += 5
        out.append((k, [bytes(d[p + 20 * i:p + 20 * i + 20]) for i in range(c)]))
        p += 20 * c
    _check(p == m[6], "the dynasty's player history isn't one this reads")
    return out


def _merge(older, rows):
    """A player's history rows: the PS2's (its last 6), after the ones before them in your Xbox save. A player's
    list isn't always in year order (one can hold two runs of seasons), so the PS2's rows are found where they
    start in the Xbox list; failing that, the Xbox rows from before the PS2's first season are put in front."""
    if not rows:
        return older[-HISTORY:]
    a, b = [r[4:] for r in older], [r[4:] for r in rows]
    for j in range(len(a) + 1):
        if a[j:] == b[:len(a) - j]:
            break
    if j == len(a):  # no overlap
        first = min(struct.unpack_from("<H", r, 4)[0] for r in rows)
        older = [r for r in older if struct.unpack_from("<H", r, 4)[0] < first]
        j = len(older)
    return (older[:j] + rows)[-HISTORY:]


def is_dynasty(data):
    """Whether data is a PS2 MVP 2005 dynasty-sized save (a .sav, or a .psu holding one): then read() it."""
    if len(data) == HEAD + SIZE:
        return _u32(data, 16) == HEAD and _u32(data, 20) == SIZE
    try:
        return any(z == HEAD + SIZE for _, _, z in RO.psu_entries(data))
    except (RO.RosterError, struct.error):
        return False


def read(data):
    """A PS2 dynasty save (a .psu, or the .sav from one), checked: {name, body}."""
    data = bytes(data)
    b, icons = data, None
    if len(b) != HEAD + SIZE:
        try:
            ent = RO.psu_entries(b)
        except RO.RosterError:
            raise Ps2DynastyError("not a PS2 MVP 2005 save (.psu, or a .sav from one)")
        files = {n: data[s:s + z] for n, s, z in ent}
        sav = [n for n, s, z in ent if z == HEAD + SIZE]
        _check(len(sav) == 1, "that PS2 save isn't a dynasty")
        b = files[sav[0]]
        icons = (files.get("title.ico"), files.get("icon.sys"))
    _check(_u32(b, 16) == HEAD and _u32(b, 20) == SIZE, "not a PS2 MVP 2005 dynasty this reads")
    typ = b[0x48:0x88].decode("utf-16-le", "replace").split("\0")[0]
    _check(typ == "Dynasty", f"that's a{'n' if typ[:1] in 'AEIOU' else ''} {typ or 'different'} save: only "
                             "dynasties convert (owner mode is coming later)")
    _check(_u32(b, 0) == RO.crc(b[16:HEAD]) and _u32(b, 4) == RO.crc(b[HEAD:]),
           "the PS2 save's checksums don't match: it's damaged or edited")
    if icons and all(icons):
        _check(_u32(b, 8) == RO.crc(icons[0]) and _u32(b, 12) == RO.crc(icons[1]),
               "the .psu's save icon doesn't match its save")
    body = b[HEAD:]
    try:
        _layout(body, True)
    except (struct.error, IndexError):
        raise Ps2DynastyError("not an MVP 2005 dynasty this reads")
    name = b[0x28:0x48].decode("utf-16-le", "replace").split("\0")[0]
    return dict(name=name, body=body)


# the platform words at the start of the tables after the managers, by table (in _layout's tags) and offset
FIXED = ((1, (4, 8, 652)), (2, (4, 8, 652)), (3, (4, 8, 652)), (4, (4, 8, 972)), (5, (4, 8)))


def convert_body(ps2, xb):
    """A PS2 dynasty body -> an Xbox dynasty body (DY.XB_LEN bytes), built on xb (one of your Xbox dynasties')."""
    _check(len(ps2) == SIZE and len(xb) == DY.XB_LEN, "the saves aren't the size MVP 2005 dynasties are")
    try:
        L, T = _layout(ps2, True), _layout(xb, False)
    except (struct.error, IndexError):
        raise Ps2DynastyError("the dynasty isn't one this reads")
    _check(L["n"] == T["n"], "the two dynasties don't have the same number of managers")
    out = bytearray()
    # settings header: 70 option ints (your Xbox save's 2 more after the 21st), the 2 flag bytes (3 pad bytes
    # between on PS2), the name buffer, ints and sliders, marker 0 and its value, then 7 bytes (5 unset, 2 kept)
    out += ps2[0:84] + xb[84:92] + ps2[84:0x118]
    out += bytes([ps2[0x118], ps2[0x11C]])
    out += ps2[0x11D:0x2C3]
    out += xb[0x2C8:0x2CD] + ps2[0x2C8:0x2CA]
    _check(len(out) == 0x2CF, "the settings header came out the wrong size")
    # org keylist, org records, team season records, team table, roster blocks, the per-team tables, the manager
    # keylist: the same bytes; but the org records' 8 platform words (6-13), the Xbox's
    roster = bytearray(ps2[0x2CA:L["mgr"]])
    for i in range(34):
        o = 0x472 + 0x54 * i + 24 - 0x2CA
        roster[o:o + 32] = xb[0x477 + 0x54 * i + 24:0x477 + 0x54 * i + 56]
    out += roster
    _check(len(out) == L["mgr"] + 5, "the rosters came out the wrong size")
    # managers: Mad Dog's PS2 record layout
    for i in range(L["n"]):
        rec = ps2[L["mgr"] + 48 * i:L["mgr"] + 48 * (i + 1)]
        new = RO.manager(rec, RO.PS2, RO.XBOX)
        _check(RO.manager(new, RO.XBOX, RO.PS2) == rec, "a PS2 manager record holds something this can't carry over")
        out += new
    # the rest of that table: 8 zero bytes fewer on the Xbox
    a = L["after"]
    _check(ps2[a:a + 96] == bytes(96), "the table after the managers isn't one this reads")
    shift = 5 - 4 * L["n"] - 8  # where a PS2 offset from here on is in the Xbox dynasty
    _check(len(out) == a + 5 - 4 * L["n"], "the managers came out the wrong size")
    out += ps2[a + 8:L["m"][2]]
    _check(len(out) == L["m"][2] + shift, "the dynasty's tables came out the wrong size")
    # the platform words: your Xbox save's
    at = a + 5 - 4 * L["n"] + 96
    out[at:at + 4] = xb[T["after"] + 96:T["after"] + 100]
    for k, offs in FIXED:
        for o in offs:
            at = L["tags"][k] + shift + o
            out[at:at + 4] = xb[T["tags"][k] + o:T["tags"][k] + o + 4]
    # the player records: the pad byte moved from the end to byte 31
    p = L["players"] + shift
    for i in range(PLAYERS):
        rec = out[p + ROW * i:p + ROW * (i + 1)]
        _check(rec[59] == 0, "a PS2 player record holds something this can't carry over")
        out[p + ROW * i:p + ROW * (i + 1)] = rec[:31] + b"\0" + rec[31:59]
    # schedules, trades, roster moves, injuries: the same; the object records after them: your Xbox save's
    m, x = L["m"], T["m"]
    out += ps2[m[2]:L["tail"] + OBJECTS]
    out += xb[T["tail"] + OBJECTS:x[3]]
    # the user section (markers 3 and 4): the same
    out += ps2[m[3]:m[5]]
    _check(len(out) == m[5] + shift - (TAIL_PS2 - TAIL_XB), "the season sections came out the wrong size")
    # player history: the PS2's seasons, after the older ones in your Xbox save; then players only it has
    mine = dict(_history(xb, x))
    groups, seen = [], set()
    for k, rows in _history(ps2, m):
        seen.add(k)
        groups.append((k, _merge(mine.get(k, []), rows)))
    for k, rows in _history(xb, x):
        if k not in seen and k in L["keys"]:
            groups.append((k, rows))
    out += MARKER + struct.pack("<I", len(groups))
    for k, rows in groups:
        out += struct.pack("<I", k) + bytes([len(rows)])
        for r in rows:
            out += bytes(4) + r[4:]
    # the stream end: its marker and its offset, then the filler (0xBB55 at even offsets)
    f = len(out) + 4
    out += MARKER + struct.pack("<I", f)
    _check(len(out) <= DY.XB_LEN, "the converted dynasty doesn't fit an Xbox dynasty save")
    out += bytes(0x55 if k % 2 == 0 else 0xBB for k in range(len(out), DY.XB_LEN))
    return bytes(out)


def to_xbox(data, xbox_dynasty, name=None):
    """A PS2 dynasty (.psu or .sav) as an Xbox data.dat, built on xbox_dynasty (keeping its name unless name is
    given)."""
    src = read(data) if not isinstance(data, dict) else data
    try:
        t = DY.read_xbox(xbox_dynasty)
    except DY.DynastyError as e:
        raise Ps2DynastyError(str(e))
    new = convert_body(src["body"], t["payload"])
    with DY._in_lib():
        C = DY._containers()
        out = C.build_xbox(xbox_dynasty, dict(name=name or t["name"], typ="Dynasty", flags=t["flags"], payload=new))
        _check(C.verify_xbox(out), "the converted save failed its signature check")
    return out
