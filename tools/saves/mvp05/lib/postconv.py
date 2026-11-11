"""Sections after marker 3: schedule list (verified converter) and yearly-history list (lossy: learned bit maps only)."""
import sys,struct,re
sys.path.insert(0,'.'); sys.path.insert(0,'tools/out')
import sched_conv, hist_conv as H
MAPS=H.load_maps('hist_maps.json')
def _markers(d,le):
    pat=b'\x0d\xf0\xef\xbe' if le else b'\xbe\xef\xf0\x0d'
    return [m.start() for m in re.finditer(pat,d)]
def sched_rep(gc,xb,shift=0):
    g=_markers(gc,False); x=_markers(xb,True); assert len(g)==len(x)==7,(len(g),len(x))
    n=struct.unpack_from('>I',gc,g[2]+4)[0]; nx=struct.unpack_from('<I',xb,x[2]+4)[0]
    rows=bytearray(b''.join(sched_conv.gc_to_xb(gc[g[2]+8+28*i:g[2]+36+28*i]) for i in range(n)))
    if shift:
        for i in range(n):
            v=struct.unpack_from('<H',rows,28*i)[0]; struct.pack_into('<H',rows,28*i,v+shift)
    rows=bytes(rows)
    rows=rows.ljust(28*nx,b'\0')   # GC keeps the section a fixed size: count shrinks, zero fill stays
    return (x[2],x[2]+8+28*nx,b'\x0d\xf0\xef\xbe'+struct.pack('<I',n)+rows)
import histrow as _HR
def hist_rep(gc,xb):
    g=_markers(gc,False); x=_markers(xb,True)
    gg=H.parse('GC',gc[g[5]+8:g[6]]); xg=H.parse('XB',xb[x[5]+8:x[6]])
    xd=dict(xg); out=[]; seen=set()
    yG=lambda r:struct.unpack_from('>H',r,0)[0]    # r = 16 bytes after link
    for k,rs in gg:
        seen.add(k); drs=[r[4:] for r in rs]
        miny=min(yG(d) for d in drs)
        old=[r for r in xd.get(k,[]) if struct.unpack_from('<H',r,4)[0]<miny]
        new=[_HR.gc2xb(r) for r in rs]          # exact struct layout (histrow.py)
        rows=(old+new)[-16:]
        out.append((k,rows))
    for k,rs in xg:
        if k not in seen: out.append((k,rs))
    b=bytearray(b'\x0d\xf0\xef\xbe'+struct.pack('<I',len(out)))
    for k,rows in out:
        b+=struct.pack('<I',k)+bytes([len(rows)])
        for r in rows: b+=b'\0\0\0\0'+r[4:]
    return (x[5],x[6],bytes(b)),len(out)

SCHED_CAPS=(2442,2172,2140,2112)   # MLB + 3 minor-league schedules (Unk8052B978_Tbl::m0); fn_8052C494 streams count + all cap entries
def sched_rep_all(gc,xb):
    """All four schedule tables after marker 2. The game's current date = first unplayed entry (f4==0) across them."""
    g=_markers(gc,False); x=_markers(xb,True)
    pg=g[2]+4; px=x[2]+4; out=bytearray()
    for cap in SCHED_CAPS:
        n=struct.unpack_from('>I',gc,pg)[0]; assert n<=cap
        out+=struct.pack('<I',n)
        out+=b''.join(sched_conv.gc_to_xb(gc[pg+4+28*i:pg+32+28*i]) for i in range(cap))
        pg+=4+28*cap
    end=px+len(out)
    assert end<x[3] and struct.unpack_from('<I',xb,end)[0]<=30 and struct.unpack_from('<I',xb,end+4)[0]<=60 and struct.unpack_from('>I',gc,pg)[0]<=30 and struct.unpack_from('>I',gc,pg+4)[0]<=60, (xb[end:end+8].hex(),gc[pg:pg+8].hex())   # next section: trades / moves counts
    return (px,end,bytes(out))

def user_rep(gc,xb):
    """Markers 3..5: [m3][u32][20 zero] [m4][u32][u32 n=1][u32 user team key][UTF-16 profile name buffer ...]"""
    g=_markers(gc,False); x=_markers(xb,True)
    a,b=g[3],g[5]; assert b-a==x[5]-x[3]==420
    s=gc[a:b]; o=bytearray()
    o+=b''.join(s[i:i+4][::-1] for i in range(0,g[4]-a+12,4))
    o+=b''.join(s[i:i+2][::-1] for i in range(g[4]-a+12,b-a,2))
    return (x[3],x[5],bytes(o))

SCHED_BYTES=4*4+28*sum(SCHED_CAPS)
def _sw32(b): return b''.join(b[i:i+4][::-1] for i in range(0,len(b),4))
def _injbits(v,W=(1,1,6,6,6,6,6)):
    out=0;pg=32;px=0
    for w in W: pg-=w; out|=((v>>pg)&((1<<w)-1))<<px; px+=w
    return out
def tail_rep(gc,xb):
    """Section between the four schedules and marker 3.
    0:    u32 trades, u32 moves, u32 0
    12:   30 x 42 B trades: 2 x (3 player keys, u8 count + 3 pad, team key) + u16 date
    1272: 60 x 10 B roster moves: player key, team key, u16 date
    1872: u32 n + 32 x 20 B injuries: player key, u32, u32, packed word (1/1/6/6/6/6/6), u16 date, u16 date
    2516: object records (platform-specific sizes; kept from the template) ending in 9 x u16 (GC +324 / XB +261)"""
    g=_markers(gc,False); x=_markers(xb,True)
    ga=g[2]+4+SCHED_BYTES; xa=x[2]+4+SCHED_BYTES
    G=gc[ga:g[3]]; X=xb[xa:x[3]]
    assert len(G)==2870 and len(X)==2798,(len(G),len(X))
    o=bytearray(X)
    nt,nm=struct.unpack_from('>II',G,0); assert nt<=30 and nm<=60
    o[0:12]=_sw32(G[0:12])
    o[12:1272]=bytes(1260)
    for i in range(nt):
        e=G[12+42*i:54+42*i]; r=bytearray()
        for s in (0,20):
            r+=_sw32(e[s:s+12])+e[s+12:s+16]+_sw32(e[s+16:s+20])
        r+=e[40:42][::-1]; o[12+42*i:54+42*i]=r
    o[1272:1872]=bytes(600)
    for i in range(nm):
        e=G[1272+10*i:1282+10*i]; o[1272+10*i:1282+10*i]=_sw32(e[:8])+e[8:10][::-1]
    n=struct.unpack_from('>I',G,1872)[0]; assert n<=32
    o[1872:2516]=bytes(644); o[1872:1876]=G[1872:1876][::-1]
    for i in range(n):
        e=G[1876+20*i:1896+20*i]
        r=_sw32(e[:12])+struct.pack('<I',_injbits(struct.unpack_from('>I',e,12)[0]))+e[16:18][::-1]+e[18:20][::-1]
        o[1876+20*i:1896+20*i]=r
    # the 9 u16 at the end of the object block are left as the template's (reverted: unidentified, possibly goals)
    return (xa,x[3],bytes(o))
