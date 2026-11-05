"""History row (0x14 B, Unk80082248_Rec) GC -> Xbox, field layout from the decomp header + bit-frequency analysis
of game-generated rows on both platforms (KC GC saves and a native Xbox 2006 dynasty).
row: link u32 (runtime, zeroed by loader) | year u16 | team u8 | bits c:2 d:2 e:3 used:1 | 3 packed stat words."""
import struct
WORDS={1:[[10,8,7,7],[9,8,8,7],[9,8,8,7]],      # batter
       2:[[8,8,9,7],[9,2,6,6,9],[7,25]]}        # pitcher (last 25 bits look like filler on both platforms)
def _w(v,widths):
    out=0;pg=32;px=0
    for w in widths:
        pg-=w; out|=((v>>pg)&((1<<w)-1))<<px; px+=w
    return out
def _b(v,widths):   # same for one byte
    out=0;pg=8;px=0
    for w in widths:
        pg-=w; out|=((v>>pg)&((1<<w)-1))<<px; px+=w
    return out
def gc2xb(r):
    """r = full 20-byte GC row. Returns 20-byte Xbox row (link zeroed)."""
    t=r[7]>>6
    out=bytearray(20)
    struct.pack_into('<H',out,4,struct.unpack_from('>H',r,4)[0])
    out[6]=r[6]; out[7]=_b(r[7],[2,2,3,1])
    ws=WORDS.get(t)
    for i in range(3):
        v=struct.unpack_from('>I',r,8+4*i)[0]
        struct.pack_into('<I',out,8+4*i,_w(v,ws[i]) if ws else v)
    return bytes(out)
