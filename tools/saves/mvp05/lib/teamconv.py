"""Team record (60 B, group 2 table) GC<->Xbox. 4 packed words learned by matching per-bit vectors over 126 teams (GC word BE, Xbox word LE).
Bits constant across all teams (gap fields) cannot be learned and are written as 0 (they are 0 in day-1 saves)."""
import struct,json,os
MAPFILE=os.path.join(os.path.dirname(os.path.abspath(__file__)),'team_bitmap.json')
def learn(gc_recs,xb_recs):
    maps=[]
    for w in range(4):
        gv={b:tuple((struct.unpack_from('>I',r,4*w)[0]>>b)&1 for r in gc_recs) for b in range(32)}
        xv={b:tuple((struct.unpack_from('<I',r,4*w)[0]>>b)&1 for r in xb_recs) for b in range(32)}
        m={}
        for gb,v in gv.items():
            if len(set(v))==1: continue
            c=[xb for xb,u in xv.items() if u==v]
            if len(c)==1: m[gb]=c[0]
            else: print('ambiguous',w,gb,c)
        maps.append(m)
    return maps
def load(): return [{int(k):v for k,v in m.items()} for m in json.load(open(MAPFILE))]
def gc_to_xb(rec,maps=None):
    maps=maps or load(); out=bytearray(rec)
    for w in range(4):
        g=struct.unpack_from('>I',rec,4*w)[0]; x=0
        for gb,xb in maps[w].items(): x|=((g>>gb)&1)<<xb
        struct.pack_into('<I',out,4*w,x)
    return bytes(out)
def xb_to_gc(rec,maps=None):
    maps=maps or load(); out=bytearray(rec)
    for w in range(4):
        x=struct.unpack_from('<I',rec,4*w)[0]; g=0
        for gb,xb in maps[w].items(): g|=((x>>xb)&1)<<gb
        struct.pack_into('>I',out,4*w,g)
    return bytes(out)
