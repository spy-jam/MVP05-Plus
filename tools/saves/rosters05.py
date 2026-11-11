"""MVP Baseball 2005 roster saves (not dynasties): a PC .sav, a PS2 .psu (or the Ps2.sav taken out of one) or an
Xbox data.dat read, and converted into one of your Xbox roster saves in hdd beside MVP05.exe.

A port of the save conversion in Mad Dog's MVP-Roster-Toolkit-Native (madddog), checked byte for byte against it.
All three platforms store the same 0xE4C00-byte roster after a header (200 bytes on PC and PS2, 264 on Xbox). PS2
differs in two records: its 36 manager records are 48 bytes (PC and Xbox: 44) and its 60-byte player records keep
their padding byte at the end (PC and Xbox: at byte 31). Nothing else changes.

Nothing here comes from the game's discs: the Xbox header is the one already in your roster save, signed again.
"""
import hashlib
import hmac as _hmac
import struct

SIZE = 0xE4C00
PC, PS2, XBOX = "PC", "PS2", "Xbox"
XBOX_HEAD, PC_HEAD = 264, 200
XBOX_SAVE_SIZE = SIZE + XBOX_HEAD  # 937,224 bytes; an MVP 2005 dynasty's data.dat is 2,239,752
MANAGER = 0x13619
MANAGERS, PLAYERS = 36, 3250
TABLE = 0xF58F3C1B
MARKER = b"\x0d\xf0\xef\xbe"
ANCHORS = (0x1371D, 0x14119, 0x14765, 0x14DB1, 0x155DD, 0x15C01, 0x1F5F5, 0x4EFB1, 0x5BAD5, 0x685F9, 0x6B8C5,
           0x75121, 0x7E97D, 0x81C49, 0x8B4A5, 0xBF72D, 0xC4B91, 0xC9FF5, 0xCF459, 0xD48BD, 0xD9D21, 0xDF185)


class RosterError(Exception):
    pass


def _check(ok, why):
    if not ok:
        raise RosterError(why)


def u32(b, p):
    _check(0 <= p and p + 4 <= len(b), "the save is cut short")
    return struct.unpack_from("<I", b, p)[0]


def player_at(p):
    return 0x1F581 if p == PS2 else 0x1F4F1


def footer_at(p):
    return 0xE4831 if p == PS2 else 0xE47A1


def _crc_table():
    t = []
    for i in range(256):
        v = i << 24
        for _ in range(8):
            v = ((v << 1) ^ (0x04C11DB7 if v & 0x80000000 else 0)) & 0xFFFFFFFF
        t.append(v)
    return t


_CRC = _crc_table()


def crc(b):
    """EA's CRC: the first four bytes taken big-endian and inverted, the rest shifted through."""
    if len(b) < 4:
        return 0
    v = int.from_bytes(b[:4], "big") ^ 0xFFFFFFFF
    t = _CRC
    for c in memoryview(b)[4:]:
        v = (((v << 8) & 0xFFFFFFFF) | c) ^ t[v >> 24]
    return v ^ 0xFFFFFFFF


def signatures(b):
    """The Xbox save's two HMAC-SHA1s (the recomp signs with a zero key): its header, then its roster."""
    key = bytes(16)
    return (_hmac.new(key, bytes(b[80:264]), hashlib.sha1).digest() +
            _hmac.new(key, bytes(b[264:]), hashlib.sha1).digest())


def psu_entries(b):
    """[(name, start, size)] of the files in a PS2 .psu."""
    _check(len(b) >= 1536, "not a PS2 .psu")
    count = u32(b, 4)
    _check(2 <= count <= 100, "not a PS2 .psu this reads")
    o, out = 1536, []
    for _ in range(count - 2):
        _check(o + 512 <= len(b), "the .psu is cut short")
        n = u32(b, o + 4)
        start = o + 512
        _check(n <= len(b) - start, "the .psu is cut short")
        out.append((bytes(b[o + 64:o + 96]).split(b"\0")[0].decode("latin-1"), start, n))
        o = start + ((n + 1023) // 1024) * 1024
    return out


def locate(body, p):
    """(delta, manager, player, footer): where the tables sit in this roster (they move with what's in it)."""
    _check(len(body) == SIZE, "not an MVP 2005 roster")
    found = []
    m = body.find(MARKER)
    while m >= 0:
        f = m + 4
        if f + 4 <= len(body) and u32(body, f) == f:
            d = f - footer_at(p)
            ma, pl = MANAGER + d, player_at(p) + d
            if ma >= 4 and pl >= ma and f + 4 <= SIZE - 144 and _anchored(body, p, d) and _filled(body, f + 4):
                found.append((d, ma, pl, f))
        m = body.find(MARKER, m + 1)
    _check(len(found) == 1, "the roster's tables aren't where an MVP 2005 roster keeps them")
    return found[0]


def _anchored(body, p, d):
    for i, a in enumerate(ANCHORS):
        a = a - 264 + d + (144 if p == PS2 and i > 0 else 0)
        if a < 0 or a + 4 > len(body) or u32(body, a) != TABLE:
            return False
    return True


def _filled(body, start):
    n = len(body) - start
    want = (b"\xbb\x55" * (n // 2 + 1))[:n]
    return bytes(body[start:]) == want


class Save:
    def __init__(self, platform, raw, body):
        self.platform, self.raw, self.body = platform, raw, body


def read(data):
    """A roster save of any of the three platforms, its checksums or signatures verified."""
    data = bytes(data)
    b, archive, ent = data, False, []
    if len(b) not in (SIZE + PC_HEAD, SIZE + XBOX_HEAD):
        archive = True
        try:
            ent = psu_entries(b)
        except RosterError:
            raise RosterError("this isn't an MVP 2005 roster save (PC .sav, PS2 .psu or Ps2.sav, Xbox data.dat)")
        rosters = [e for e in ent if e[2] == SIZE + PC_HEAD and u32(b, e[1] + 16) == PC_HEAD]
        _check(len(rosters) == 1, "this isn't an MVP 2005 roster save (or a .psu holding one)")
        b = b[rosters[0][1]:rosters[0][1] + rosters[0][2]]
    if len(b) == SIZE + XBOX_HEAD:
        p, h = XBOX, XBOX_HEAD
        _check(u32(b, 80) == XBOX_HEAD and u32(b, 84) == SIZE, "not an Xbox roster save this reads")
        _check(b[40:80] == bytes(40), "not an Xbox roster save this reads")
        _check(b[:40] == signatures(b), "the Xbox save's signatures don't match: it's damaged or edited")
    else:
        _check(len(b) == SIZE + PC_HEAD and u32(b, 16) == PC_HEAD and u32(b, 20) == SIZE,
               "not a PC or PS2 roster save this reads")
        body = b[PC_HEAD:]
        kinds = []
        for test in (PC, PS2):
            try:
                locate(body, test)
                kinds.append(test)
            except RosterError:
                pass
        _check(len(kinds) == 1, "can't tell whether this is a PC or a PS2 roster")
        p, h = kinds[0], PC_HEAD
        _check(u32(b, 0) == crc(b[16:200]) and u32(b, 4) == crc(body), "the save's checksums don't match: "
                                                                        "it's damaged or edited")
        if p == PC:
            _check(b[8:16] == bytes(8), "not a PC roster save this reads")
    _check(not archive or p == PS2, "the .psu doesn't hold a PS2 roster")
    if archive:
        files = {n: data[s:s + z] for n, s, z in ent}
        _check("title.ico" in files and "icon.sys" in files, "the .psu has no PS2 save icon")
        _check(u32(b, 8) == crc(files["title.ico"]) and u32(b, 12) == crc(files["icon.sys"]),
               "the .psu's save icon doesn't match its save")
    body = b[h:h + SIZE]
    _, ma, pl, _ = locate(body, p)
    _check(u32(body, ma - 4) == TABLE and u32(body, pl + PLAYERS * 60) == TABLE, "the roster's tables aren't "
                                                                                  "the size this reads")
    tail = bytes(body[SIZE - 144:])
    _check(tail == b"\x55\xbb" * 72, "the roster doesn't end the way an MVP 2005 roster does")
    return Save(p, b, body)


def manager(rec, frm, to):
    """A manager record moved between the PS2 layout and the PC/Xbox one: its fields by MANAGER_MAP, then its last
    28 bytes (from byte 16, PS2 19) as they are."""
    n = 48 if to == PS2 else 44
    v = 0
    src = int.from_bytes(rec, "little")
    for pc, ps2, width in MANAGER_MAP:
        val = (src >> (ps2 if frm == PS2 else pc)) & ((1 << width) - 1)
        at = ps2 if to == PS2 else pc
        v = (v & ~(((1 << width) - 1) << at)) | (val << at)
    out = bytearray(v.to_bytes(n, "little"))
    a, z = (19 if frm == PS2 else 16), (19 if to == PS2 else 16)
    out[z:z + 28] = rec[a:a + 28]
    return bytes(out)


def convert_body(body, frm, to):
    d, ma, pl, f = locate(body, frm)
    if (frm == PS2) == (to == PS2):
        return bytes(body)
    old = 48 if frm == PS2 else 44
    managers = bytearray()
    for i in range(MANAGERS):
        rec = body[ma + i * old:ma + (i + 1) * old]
        res = manager(rec, frm, to)
        if frm == PS2:
            _check(manager(res, to, frm) == rec, "a PS2 manager record holds something this can't carry over")
        managers += res
    target_footer = footer_at(to) + d
    _check(target_footer + 4 <= SIZE - 144, "the roster won't fit in the other platform's save")
    out = bytearray(body[:ma]) + managers + bytearray(body[ma + MANAGERS * old:])
    if frm == PS2:
        out += b"\x55\xbb" * 72
    else:
        del out[SIZE:]
    for i in range(PLAYERS):
        o = player_at(to) + d + i * 60
        rec = out[o:o + 60]
        if frm == PS2:
            _check(rec[59] == 0, "a PS2 player record holds something this can't carry over")
            r = rec[:31] + b"\0" + rec[31:59]
        else:
            _check(rec[31] == 0, "a player record holds something this can't carry over")
            r = rec[:31] + rec[32:60] + b"\0"
        out[o:o + 60] = r
    struct.pack_into("<I", out, target_footer, target_footer)
    _check(len(out) == SIZE, "the converted roster came out the wrong size")
    return bytes(out)


def to_xbox(save, xbox_save):
    """save's roster as an Xbox data.dat, with xbox_save's header (one of your own Xbox roster saves)."""
    target = read(xbox_save)
    _check(target.platform == XBOX, "the save to write into isn't an Xbox roster save")
    body = convert_body(save.body, save.platform, XBOX)
    out = bytearray(target.raw[:XBOX_HEAD]) + body
    out[:40] = signatures(out)
    check = read(out)
    _check(check.platform == XBOX and check.body == body, "the converted save didn't read back right")
    return bytes(out)


# (PC/Xbox bit, PS2 bit, width) of each manager field, from the toolkit's schema
MANAGER_MAP = ((0, 8, 16), (16, 32, 15), (31, 47, 1), (32, 48, 6), (38, 54, 8), (46, 64, 7), (53, 71, 10),
               (63, 81, 1), (64, 82, 7), (71, 89, 4), (75, 93, 2), (77, 96, 4), (81, 100, 3), (84, 103, 4),
               (88, 107, 1), (89, 108, 7), (96, 115, 3), (99, 118, 1), (100, 119, 7), (107, 128, 7), (114, 135, 7),
               (121, 142, 7))
