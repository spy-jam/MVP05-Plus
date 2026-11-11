"""Per-team roster block (group 2, 512 B, GC payload 0x38ce + 512*i; Xbox = GC-3). Grammar learned from team 0 and verified vs Xbox for all teams.
4 lineup units | 25 ints + 2 u32 | 25 ints | 5 byte rings [cap bytes][u32][u32] caps 5,8,6,4,2 | 47 B tail (copy)."""
import struct
def _s32(b): return b''.join(b[i:i+4][::-1] for i in range(0,len(b),4))
import struct as _st
SETS=((5,),(8,),(4,5,6,7),(3,4,5,6,7),(2,3,7))
def _ok(blk,o,c,be):
    t=blk[o+c:o+c+8]
    if len(t)<8: return False
    if be: z=t[0:3]==b'\0\0\0' and t[4:7]==b'\0\0\0'; cnt,x=t[3],t[7]
    else:  z=t[1:4]==b'\0\0\0' and t[5:8]==b'\0\0\0'; cnt,x=t[0],t[4]
    return z and cnt<=c and x<=8
def _caps(blk,o,be):
    """DFS over plausible ring caps; prefer the chain whose remainder after ring 5 is mostly zero.
    Checked on 6 GC saves: every block has a 45-byte tail; the only blocks with more than one valid chain
    (All-Star teams 30/31 in fresh saves, special team 125) give byte-identical output for every chain."""
    best=[None,10**9]
    def rec(k,pos,acc):
        if k==5:
            rem=blk[pos:]
            score=sum(1 for b in rem[:-12] if b)      # nonzero bytes left over (ignore next unit's first bytes)
            if score<best[1]: best[0]=list(acc);best[1]=score
            return
        for c in SETS[k]:
            if _ok(blk,pos,c,be): rec(k+1,pos+c+8,acc+[c])
    rec(0,o,[])
    assert best[0] is not None,'no ring chain'
    return best[0]
def conv(blk,be=True):
    """be=True: GC->XB. be=False: XB->GC (same swaps). Array B length = count n in array A trailer; ring caps detected."""
    o=0; out=bytearray()
    for _ in range(4):
        out+=blk[o:o+10]+blk[o+10:o+12][::-1]+_s32(blk[o+12:o+48]); o+=48
    A=blk[o:o+100]; out+=_s32(A); o+=100
    n=_st.unpack('>I' if be else '<I',blk[o:o+4])[0]
    out+=_s32(blk[o:o+8]); o+=8
    out+=_s32(blk[o:o+4*n]); o+=4*n
    for cap in _caps(blk,o,be):
        out+=blk[o:o+cap]+_s32(blk[o+cap:o+cap+8]); o+=cap+8
    tl=blk[o:]; assert len(tl)==45,len(tl)
    out+=tl[:1]+_s32(tl[1:])          # u8, 3 x u32, 4 x (player key, return date) injury list
    return bytes(out)
