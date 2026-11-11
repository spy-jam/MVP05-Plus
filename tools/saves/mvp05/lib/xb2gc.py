"""Xbox (data.dat payload) -> GameCube (.gci payload) dynasty converter: the inverse of gc2xb_v0.
Every section uses the same layout knowledge as the GC->Xbox direction (see FORMAT_NOTES.md), applied backwards.
A GameCube dynasty save is needed as the template for the few blocks that are kept (same in every dynasty)."""
import struct, re
import numpy as np
import tablesconv as T, postconv as P, rosterblock, teamconv, mgrconv, player_conv, structconv as SC, histrow, sched_conv
import bitconv as B
import hist_conv as H

KEYG = b'\x69\x3d\xbc\x6a'; KEYX = b'\x6a\xbc\x3d\x69'
SIG_G = re.compile(rb'(?s).{10}\xbb\x55\x00\x00\x00[\x00-\x40]')
SIG_X = re.compile(rb'(?s).{10}\x55\xbb[\x00-\x40]\x00\x00\x00')
def s32(b): return b''.join(b[i:i+4][::-1] for i in range(0, len(b), 4))
def s16(b): return b''.join(b[i:i+2][::-1] for i in range(0, len(b), 2))

# ---------------------------------------------------------------- bit helpers (inverse of the GC->XB packers)
def bf_x2g(v, widths, nbits=32):
    """XB LSB-first value -> GC MSB-first value, same field order."""
    out = 0; pg = nbits; px = 0
    for w in widths:
        pg -= w; out |= ((v >> px) & ((1 << w) - 1)) << pg; px += w
    return out

def rowconv_x2g(body, kind, rows):
    rows = min(rows, len(body) * 8 // T.RB[kind])
    pm = T.PM[kind]; R = T.RB[kind]; ok = pm >= 0
    xb = B.xbits(body[:R * rows // 8]).reshape(rows, R)
    out = np.zeros((rows, R), np.uint8)
    out[:, ok] = xb[:, pm[ok]]
    return np.packbits(out.reshape(-1)).tobytes()

def players_x2g(xbody, gbody_tpl):
    n = len(xbody); assert n == len(gbody_tpl) == 60 * 3250
    xw = xbody + xbody; out = bytearray(gbody_tpl)
    for i in range(3250):
        c = player_conv.xb_to_gc(bytes(xw[24 + 60 * i:84 + 60 * i]))
        gi = 23 + 60 * i
        for j in range(1, 60): out[(gi + j) % n] = c[j]
        out[(gi + 60) % n] = c[0]
    return bytes(out)

# ---------------------------------------------------------------- sections
def header(xb, gt):
    o = bytearray(gt[0:0x2d2])
    o[0:0x120] = s32(xb[0:0x120])
    o[0x120] = xb[0x120]; o[0x124] = xb[0x121]           # 2 flags; GC pad bytes 0x121..0x123 kept
    o[0x125:0x14b] = s16(xb[0x122:0x148])
    o[0x14b:0x153] = s32(xb[0x148:0x150])
    o[0x153:0x2b7] = xb[0x150:0x2b4]
    o[0x2b7:0x2cb] = s32(xb[0x2b4:0x2c8])
    o[0x2cb:0x2d2] = xb[0x2c8:0x2cf]
    return (0, 0x2d2, bytes(o))

def orgs(xb, gt):
    return (0x47a, 0x47a + 84 * 34, b''.join(SC.xb_to_gc(xb[0x477 + 84 * i:0x477 + 84 * i + 84], SC.ORG54) for i in range(34)))

def teamflags(xb, gt):
    x = xb[0xf9f:0x1b3f]; g = gt[0xfa2:0x1b42]
    o = bytearray(s32(x[0:4]))
    for i in range(30):
        r = x[4 + 16 * i:20 + 16 * i]
        o += b''.join(struct.pack('>I', bf_x2g(struct.unpack_from('<I', r, 4 * j)[0], T.F5CC[j])) for j in range(4))
    o += s32(x[0x1e4:0x5a8]); o += g[0x5a8:0x5ac]; o += s32(x[0x5ac:])
    assert len(o) == len(g)
    return (0xfa2, 0x1b42, bytes(o))

def teamtable(xb, gt):
    maps = teamconv.load()
    return (0x1b42, 0x1b42 + 7560, b''.join(teamconv.xb_to_gc(xb[0x1b3f + 60 * i:0x1b3f + 60 * i + 60], maps) for i in range(126)))

def _blocks(d, key, sig, start):
    Pp = d.find(key, 0x12000); pos = []; i = start
    while i < Pp:
        if sig.match(d, i): pos.append(i); i += 48
        else: i += 1
    st = [pos[k] for k in range(0, len(pos), 4)]; assert len(st) == 126, len(st)
    return st + [Pp]

def rosters_and_post(xb, gt):
    stx = _blocks(xb, KEYX, SIG_X, 0x38cb); Q = stx[-1]
    ros = b''.join(rosterblock.conv(xb[stx[k]:stx[k + 1]], be=False) for k in range(126))
    out = bytearray(); p = Q
    for tno in range(3):
        out += s32(xb[p:p + 4]); d = xb[p + 4:p + 508]
        out += s16(d) if tno == 2 else d
        p += 508
    hdr, n = struct.unpack('<II', xb[p:p + 8]); out += s32(xb[p:p + 8]); p += 8
    out += s32(xb[p:p + 12 * n]); p += 12 * n
    out += s32(xb[p:p + 28]); p += 28
    out += mgrconv.xb_table_to_gc(xb[p:p + 44 * n], n); p += 44 * n
    # template extent
    Pg = gt.find(KEYG, 0x12000); q = Pg + 1524
    hg, ng = struct.unpack('>II', gt[q:q + 8]); qe = q + 8 + 12 * ng + 28 + 48 * ng
    return (0x38ce, qe, ros + bytes(out))

def tagged(xb, gt):
    tg = T.tags(gt, T.TG); tx = T.tags(xb, T.TX); reps = []
    for k in list(range(8, 16)) + list(range(18, 25)):
        xs = tx[k] + 4; xe = tx[k + 1] if k < 24 else tx[k] + 4 + 21600
        gs = tg[k] + 4; ge = tg[k + 1] if k < 24 else tg[k] + 4 + 21600
        xbd = xb[xs:xe]; assert len(xbd) == ge - gs, (k, len(xbd), ge - gs)
        if k == 8: new = players_x2g(xbd, gt[gs:ge])
        else:
            kind = T.KIND[k]; rows = T.ROWS[k]
            new = rowconv_x2g(xbd, kind, rows) + xbd[(T.RB[kind] * rows) // 8:]
        reps.append((gs, ge, new))
    # region 16..18
    x = xb[tx[16]:tx[18]]; assert len(x) == T.REGION16_LEN
    o = bytearray(); p = 0
    def sub(kind, rows, size):
        nonlocal p
        o.extend(s32(x[p:p + 4])); o.extend(rowconv_x2g(x[p + 4:p + size], kind, rows)); p += size
    sub('R', 3250, 39004)
    for _ in range(5): sub('W', 3250, 13004)
    sub('V', 3250, 52004)
    n = struct.unpack_from('<I', x, p)[0]; assert n == 1800, n
    o.extend(s32(x[p:p + 8 + 12 * n])); p += 8 + 12 * n
    sub('D', 1800, 36004)
    reps.append((tg[16], tg[18], bytes(o)))
    for a, b in ((2, 6), (6, 8)):
        xx = xb[tx[a]:tx[b]]; assert len(xx) == tg[b] - tg[a]
        reps.append((tg[a], tg[b], s32(xx)))
    return reps

def schedules(xb, gt):
    g = P._markers(gt, False); x = P._markers(xb, True)
    px = x[2] + 4; out = bytearray()
    for cap in P.SCHED_CAPS:
        n = struct.unpack_from('<I', xb, px)[0]; assert n <= cap
        out += struct.pack('>I', n)
        out += b''.join(sched_conv.xb_to_gc(xb[px + 4 + 28 * i:px + 32 + 28 * i]) for i in range(cap))
        px += 4 + 28 * cap
    return (g[2] + 4, g[2] + 4 + len(out), bytes(out))

def after_schedules(xb, gt):
    g = P._markers(gt, False); x = P._markers(xb, True)
    ga = g[2] + 4 + P.SCHED_BYTES; xa = x[2] + 4 + P.SCHED_BYTES
    X = xb[xa:x[3]]; Gt = gt[ga:g[3]]
    assert len(X) == 2798 and len(Gt) == 2870
    o = bytearray(Gt)
    nt, nm = struct.unpack_from('<II', X, 0); assert nt <= 30 and nm <= 60
    o[0:12] = s32(X[0:12]); o[12:1272] = bytes(1260)
    for i in range(nt):
        e = X[12 + 42 * i:54 + 42 * i]; r = bytearray()
        for s in (0, 20): r += s32(e[s:s + 12]) + e[s + 12:s + 16] + s32(e[s + 16:s + 20])
        r += e[40:42][::-1]; o[12 + 42 * i:54 + 42 * i] = r
    o[1272:1872] = bytes(600)
    for i in range(nm):
        e = X[1272 + 10 * i:1282 + 10 * i]; o[1272 + 10 * i:1282 + 10 * i] = s32(e[:8]) + e[8:10][::-1]
    n = struct.unpack_from('<I', X, 1872)[0]; assert n <= 32
    o[1872:2516] = bytes(644); o[1872:1876] = X[1872:1876][::-1]
    for i in range(n):
        e = X[1876 + 20 * i:1896 + 20 * i]
        r = s32(e[:12]) + struct.pack('>I', bf_x2g(struct.unpack_from('<I', e, 12)[0], (1, 1, 6, 6, 6, 6, 6))) + e[16:18][::-1] + e[18:20][::-1]
        o[1876 + 20 * i:1896 + 20 * i] = r
    return (ga, g[3], bytes(o))           # object block (2516..) kept from the GC template

def user(xb, gt):
    g = P._markers(gt, False); x = P._markers(xb, True)
    s = xb[x[3]:x[5]]; assert len(s) == 420 and g[5] - g[3] == 420
    k = x[4] - x[3] + 12
    return (g[3], g[5], s32(s[:k]) + s16(s[k:]))

def hist_row_x2g(r):
    t = r[7] & 3
    out = bytearray(20)
    struct.pack_into('>H', out, 4, struct.unpack_from('<H', r, 4)[0])
    out[6] = r[6]; out[7] = bf_x2g(r[7], [2, 2, 3, 1], 8)
    ws = histrow.WORDS.get(t)
    for i in range(3):
        v = struct.unpack_from('<I', r, 8 + 4 * i)[0]
        struct.pack_into('>I', out, 8 + 4 * i, bf_x2g(v, ws[i]) if ws else v)
    return bytes(out)

def history(xb, gt):
    g = P._markers(gt, False); x = P._markers(xb, True)
    groups = H.parse('XB', xb[x[5] + 8:x[6]])
    body = bytearray()
    for key, rows in groups:
        rows = rows[-H.GC_CAP:]                         # GameCube keeps the last 6 rows per player
        body += struct.pack('>I', key) + bytes([len(rows)]) + b''.join(hist_row_x2g(r) for r in rows)
    return (g[5], None, b'\xbe\xef\xf0\x0d' + struct.pack('>I', len(groups)) + bytes(body))

# ---------------------------------------------------------------- driver
def convert(xb, gt):
    """xb: Xbox payload (0x222C00). gt: GameCube template payload (0x186C00). Returns new GC payload."""
    g = P._markers(gt, False)
    reps = [header(xb, gt), orgs(xb, gt), teamflags(xb, gt), teamtable(xb, gt), rosters_and_post(xb, gt)]
    reps += tagged(xb, gt)
    reps += [schedules(xb, gt), after_schedules(xb, gt), user(xb, gt)]
    hs, _, hbody = history(xb, gt)
    reps.sort(key=lambda r: r[0])
    for (a, b, _), (c, d, _) in zip(reps, reps[1:]): assert c >= b, ('overlap', hex(a), hex(c))
    out = bytearray(); p = 0
    for a, b, c in reps:
        out += gt[p:a]; out += c; p = b
    out += gt[p:hs]                                    # up to marker 5 (template coordinates)
    out += hbody
    end = len(out)
    out += b'\xbe\xef\xf0\x0d' + struct.pack('>I', end + 4)   # stream end marker: value = its offset + 4
    if len(out) > len(gt):
        raise ValueError('converted dynasty is %d bytes too large for a GameCube save' % (len(out) - len(gt)))
    fill = bytes(0xBB if (i & 1) == 0 else 0x55 for i in range(len(out), len(gt)))
    out += fill
    return bytes(out)
