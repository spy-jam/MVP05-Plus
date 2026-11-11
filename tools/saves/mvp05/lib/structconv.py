"""Generic struct-driven GC<->Xbox record converter.
Spec = list of items: ('i',) 4-byte int | ('h',) 2-byte | ('b',) 1-byte | ('bits',unit_bytes,[widths..]) bitfield unit, fields in declaration order.
GC (MWCC, big-endian): bitfields fill from MSB; Xbox (MSVC, little-endian): fill from LSB. Values are preserved."""
import struct
def spec_size(spec): return sum(it[1] if it[0]=='bits' else {'i':4,'h':2,'b':1}[it[0]] for it in spec)
def _conv(rec,spec,to_xb):
    out=bytearray(len(rec)); o=0
    for it in spec:
        if it[0]=='bits':
            n,w=it[1],it[2]; f={2:'H',4:'I'}[n]
            src,dst=('>','<') if to_xb else ('<','>')
            v=struct.unpack_from(src+f,rec,o)[0]; vals=[]
            tot=n*8; pos=tot if to_xb else 0
            for x in w:
                if to_xb: pos-=x; vals.append((v>>pos)&((1<<x)-1))
                else: vals.append((v>>pos)&((1<<x)-1)); pos+=x
            nv=0; pos=0 if to_xb else tot
            for x,val in zip(w,vals):
                if to_xb: nv|=val<<pos; pos+=x
                else: pos-=x; nv|=val<<pos
            struct.pack_into(dst+f,out,o,nv); o+=n
        else:
            n={'i':4,'h':2,'b':1}[it[0]]
            out[o:o+n]=rec[o:o+n][::-1]; o+=n
    return bytes(out)
def gc_to_xb(rec,spec): return _conv(rec,spec,True)
def xb_to_gc(rec,spec): return _conv(rec,spec,False)
# Specs taken from include/game/tu_8052A220.h
ORG54=[('i',)]*14+[('bits',2,[1,5,3,1,2,3,1])]+[('h',)]*11+[('bits',4,[15,15,2])]   # Unk8052E9C4_Rec, 0x54
REC16=[('bits',4,[7,7,7,7,4]),('bits',4,[7,7,7,7,4]),('bits',4,[7,7,7,11]),('bits',4,[11,21])]  # Unk8052F5CC_Rec, 16 B (GC order; last word f12:11,p3:21)
if __name__=='__main__': print(spec_size(ORG54),spec_size(REC16))
# --- team record (roster/team table of group 2, 60 B): 4 packed words (widths in declaration order = XB LSB-first) + 44 B of strings. Learned from team.dat.
_W2=[2]*16
TEAM60=[('bits',4,[4,5,7,2,1,2,8,2,1]),
        ('bits',4,[2]*13+[2,2,2]),      # pinchrunner..suicidesqueeze (13) + vs_ana, vs_oak, vs_sea
        ('bits',4,_W2),
        ('bits',4,[2]*13+[3,3])]+[('b',)]*44
