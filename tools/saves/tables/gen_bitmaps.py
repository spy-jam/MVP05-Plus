#!/usr/bin/env python3
"""Generate record_bitmaps.json: the exact GameCube -> Xbox bit mapping of every fixed-size MVP 2005 record type,
taken from the working Python converters in ../mvp05/lib by feeding them records with a single bit set.

Bit numbering (both sides): bit index = byte_offset * 8 + bit, bit 0 = least significant bit of that byte.
map[g] = the Xbox bit that GameCube bit g lands on, or -1 if it is dropped (padding / unlearned).
The mapping is a pure bit permutation for every record listed (checked below: each probe sets at most one bit),
so Xbox -> GameCube is its inverse.

usage: python gen_bitmaps.py            (writes record_bitmaps.json next to this file)"""
import os, sys, json, struct

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, '..', 'mvp05', 'lib')
os.chdir(LIB); sys.path.insert(0, LIB)
import tablesconv as T, teamconv, structconv as SC, mgrconv, player_conv, sched_conv, histrow, postconv as P


def probe(fn, gc_len, base=None, skip=()):
    base = bytearray(base or bytes(gc_len))
    out0 = fn(bytes(base)); xb_len = len(out0)
    m = []
    for g in range(gc_len * 8):
        if g in skip:
            m.append(None); continue
        r = bytearray(base); r[g >> 3] ^= 1 << (g & 7)
        o = fn(bytes(r))
        diff = [i * 8 + b for i in range(xb_len) for b in range(8) if ((o[i] ^ out0[i]) >> b) & 1]
        assert len(diff) <= 1, (fn, g, diff)
        m.append(diff[0] if diff else -1)
    return dict(gc_len=gc_len, xb_len=xb_len, map=m)


def trade(e):          # 42 B: 2 x (3 player keys, u8 count + 3 pad, team key) + u16 date
    r = bytearray()
    for s in (0, 20):
        r += P._sw32(e[s:s + 12]) + e[s + 12:s + 16] + P._sw32(e[s + 16:s + 20])
    return bytes(r + e[40:42][::-1])

def move(e):           # 10 B: player key, team key, u16 date
    return P._sw32(e[:8]) + e[8:10][::-1]

def injury(e):         # 20 B
    return P._sw32(e[:12]) + struct.pack('<I', P._injbits(struct.unpack_from('>I', e, 12)[0])) + e[16:18][::-1] + e[18:20][::-1]

def roster_tail(t):    # 45 B: u8, 3 x u32, 4 x (player key, return date)
    return t[:1] + P._sw32(t[1:])

maps = teamconv.load()
R = {}
R['player_row_60 (frame form, see guide 4.6)'] = probe(player_conv.gc_to_xb, 60)
R['team_row_60'] = probe(lambda r: teamconv.gc_to_xb(r, maps), 60)
R['org_record_84'] = probe(lambda r: SC.gc_to_xb(r, SC.ORG54), 84)
R['team_season_record_16 (F5CC)'] = probe(T.f5cc_conv, 16)
R['manager_record_48_to_44'] = probe(mgrconv.gc_rec_to_xb, 48)
R['schedule_entry_28'] = probe(sched_conv.gc_to_xb, 28)
for t in (0, 1, 2, 3):
    base = bytearray(20); base[7] = t << 6
    R['history_row_20_type%d' % t] = probe(histrow.gc2xb, 20, base, skip={7 * 8 + 6, 7 * 8 + 7})
    # bits 0..31 (link) are written as 0 by the converter (the loader clears them anyway)
R['trade_42'] = probe(trade, 42)
R['roster_move_10'] = probe(move, 10)
R['injury_20'] = probe(injury, 20)
R['roster_block_tail_45'] = probe(roster_tail, 45)
for kind, rb in T.RB.items():
    R['table_row_kind_%s_%dbits' % (kind, rb)] = probe(lambda b, k=kind: T.rowconv(b, k, 1), rb // 8)

json.dump(dict(
    about=__doc__.split('usage:')[0].strip(),
    tables_using_kind=dict((str(k), v) for k, v in T.KIND.items()),
    rows=dict((str(k), v) for k, v in T.ROWS.items()),
    records=R), open(os.path.join(HERE, 'record_bitmaps.json'), 'w'), indent=None)
print('wrote', len(R), 'record maps')
for k, v in R.items():
    print('  %-46s %3d -> %3d bytes, %d bits mapped, %d dropped' % (k, v['gc_len'], v['xb_len'],
          sum(1 for x in v['map'] if x is not None and x >= 0), sum(1 for x in v['map'] if x == -1)))
