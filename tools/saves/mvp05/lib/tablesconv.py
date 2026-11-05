"""Whole-table converters for the 3250-slot per-player DB tables (tables #8..#15, tag-delimited)."""
import re,sys
import numpy as np
sys.path.insert(0,'.'); sys.path.insert(0,'tools/out')
import bitconv as B, player_conv
TG=b'\xf5\x8f\x3c\x1b'; TX=b'\x1b\x3c\x8f\xf5'
def tags(d,t):
    return [m.start() for m in re.finditer(t,d[:0x150000]) if m.start()>0x5000]
# 4 B table #11: x bit -> g bit (learned, 100% on MATCHED)
_X2G={**{x:7-x for x in range(8)},**{x:23-x for x in range(8,16)},**{16+k:22-k for k in range(5)},**{23+k:30-k for k in range(8)}}
def _pm4():
    pm=np.full(32,-1)
    for x,g in _X2G.items(): pm[g]=x
    return pm
import json as _j
_A=_j.load(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'allbitstructs.json')))
import fitstruct as _F
PM={'F':B.perm('Unk8008CE64_PackF'),'R':B.perm('Unk80070004_Rec'),'4':_pm4(),
    'P':_F.perm_from_words(_A['Unk80089894_Pack']['words']),'PB':_F.perm_from_words(_A['Unk80089894_PackB']['words']),'PC':_F.perm_from_words(_A['Unk80089894_PackC']['words'])}
PM['W']=_F.perm_from_words(_A['Unk8007FF8C_W']['words']); PM['V']=_F.perm_from_words(_A['Unk80071170_Rec']['words']); PM['D']=_F.perm_from_words(_A['Unk80089894_PackD']['words'])
RB={'F':128,'R':96,'4':32,'P':96,'PB':96,'PC':96,'W':32,'V':128,'D':160}
def rowconv(body,kind,rows=3250):
    rows=min(rows,len(body)*8//RB[kind])
    pm=PM[kind];R=RB[kind];ok=pm>=0
    gb=B.gbits(body[:R*rows//8]).reshape(rows,R)
    out=np.zeros((rows,R),np.uint8)
    out[:,pm[ok]]=gb[:,ok]
    return np.packbits(out.reshape(-1),bitorder='little').tobytes()
KIND={9:'F',10:'F',11:'4',14:'4',12:'R',13:'R',15:'R',18:'PC',19:'PB',20:'PB',21:'PC',22:'PB',23:'PB',24:'P'}
ROWS={k:3250 for k in (9,10,11,12,13,14,15)}
ROWS.update({k:1800 for k in range(18,25)})
def players(gbody,xbody_tpl):
    # rows are framed at +23 (GC) / +24 (XB); the last row wraps around to the start of the table body
    n=len(gbody); assert n==len(xbody_tpl)==60*3250
    gw=gbody+gbody; out=bytearray(xbody_tpl)
    for i in range(3250):
        gi=23+60*i
        rec=bytearray(gw[gi:gi+60]); rec[0]=gw[gi+60]
        c=player_conv.gc_to_xb(bytes(rec))
        for j in range(60): out[(24+60*i+j)%n]=c[j]
    return bytes(out)
def table_reps(gc,xb_tpl):
    """-> list of (xb_start,xb_end,new_bytes) in template coords; table body = after 4 B tag."""
    tg=tags(gc,TG); tx=tags(xb_tpl,TX); assert len(tg)==len(tx)==25,(len(tg),len(tx))
    reps=[]
    for k in list(range(8,16))+list(range(18,25)):
        gb=gc[tg[k]+4:(tg[k+1] if k<24 else tg[k]+4+21600)]; xs=tx[k]+4; xe=(tx[k+1] if k<24 else tx[k]+4+21600)
        assert len(gb)==xe-xs,(k,len(gb),xe-xs)
        if k==8: new=players(gb,xb_tpl[xs:xe])
        else: new=rowconv(gb,KIND[k],ROWS[k])+gb[(RB[KIND[k]]*ROWS[k])//8:]
        reps.append((xs,xe,new))
    reps.append(region16_rep(gc,xb_tpl))
    reps+=small_reps(gc,xb_tpl)
    reps+=early_reps(gc,xb_tpl)
    return reps

import struct as _st
def _swap32(b): return b''.join(b[i:i+4][::-1] for i in range(0,len(b),4))
REGION16_LEN=0x34288
def region16(g):
    """GC bytes of [tag16, tag18) -> XB bytes (same length). Layout verified on the fresh pair."""
    assert len(g)==REGION16_LEN
    out=bytearray(); p=0
    def sub(kind,rows,size):
        nonlocal p
        out.extend(_swap32(g[p:p+4])); out.extend(rowconv(g[p+4:p+size],kind,rows)); p+=size
    sub('R',3250,39004)
    for _ in range(5): sub('W',3250,13004)
    sub('V',3250,52004)
    n=_st.unpack_from('>I',g,p)[0]; assert n==1800,n
    out.extend(_swap32(g[p:p+8+12*n])); p+=8+12*n
    sub('D',1800,36004)
    assert p==REGION16_LEN,(p,)
    return bytes(out)
def region16_rep(gc,xb_tpl):
    tg=tags(gc,TG); tx=tags(xb_tpl,TX)
    return (tx[16],tx[18],region16(gc[tg[16]:tg[18]]))

def small_reps(gc,xb_tpl):
    """tables #2..#5 (plain int arrays) and region #6..#8 (404 B preamble + 3250-entry player keylist): all plain swap32."""
    tg=tags(gc,TG); tx=tags(xb_tpl,TX); reps=[]
    for a,b in ((2,6),(6,8)):
        g=gc[tg[a]:tg[b]]; xl=tx[b]-tx[a]
        assert len(g)==xl,(a,b,len(g),xl)
        reps.append((tx[a],tx[b],_swap32(g)))
    return reps

import structconv as _SC
def early_reps(gc,xb_tpl):
    """(a) 34 org records (0x54 B, Unk8052E9C4_Rec: ints swap32, bitfield group, halfwords, last bitfield word) GC 0x47a -> XB 0x477
       (b) user-visible settings words 2,3,8,45 of the header (plain ints) GC 0x4*i -> XB 3+4*i"""
    reps=[]
    org=b''.join(_SC.gc_to_xb(gc[0x47a+84*i:0x47a+84*i+84],_SC.ORG54) for i in range(34))
    reps.append((0x477,0x477+84*34,org))
    reps.append(header_rep(gc,None))
    reps.append(teamflags_rep(gc,xb_tpl))
    return reps

def header_rep(gc,_):
    """Settings header up to marker 1 (GC 0x2d2 / XB 0x2cf). Layout checked byte-for-byte against the fresh pair."""
    o=bytearray()
    o+=_swap32(gc[0:0x120])                      # 72 ints (option settings)
    o+=bytes([gc[0x120],gc[0x124]])              # 2 flags (GC stores them with 3 pad bytes between)
    o+=b''.join(gc[i:i+2][::-1] for i in range(0x125,0x14b,2))   # UTF-16 name buffer (19 units)
    o+=_swap32(gc[0x14b:0x153])                  # 2 ints
    o+=gc[0x153:0x2b7]                           # byte arrays (sliders)
    o+=_swap32(gc[0x2b7:0x2cb])                  # 3 ints, marker 0, its value
    o+=gc[0x2cb:0x2d2]                           # 7 bytes
    assert len(o)==0x2cf,len(o)
    return (0,0x2cf,bytes(o))

# Unk8052F5CC_Rec (decomp include/game/tu_8052A220.h): 4 words of bitfields, 30 MLB teams, after the org table
F5CC=[[7,7,7,7,4],[7,7,7,7,4],[7,7,7,11],[11,21]]
def _bfword(v,widths):
    """GC MSB-first word value -> XB LSB-first word value, same field order."""
    out=0;pg=32;px=0
    for w in widths:
        pg-=w; f=(v>>pg)&((1<<w)-1); out|=f<<px; px+=w
    return out
def f5cc_conv(rec):
    return b''.join(_st.pack('<I',_bfword(_st.unpack_from('>I',rec,4*i)[0],F5CC[i])) for i in range(4))
def teamflags_rep(gc,xb_tpl):
    """GC [0xfa2,0x1b42) -> XB [0xf9f,0x1b3f): tag | 30 x F5CC | plain words | 1 byte-bitfield word (kept) | plain words."""
    g=gc[0xfa2:0x1b42]; x=xb_tpl[0xf9f:0x1b3f]
    o=bytearray(_swap32(g[0:4]))
    for i in range(30): o+=f5cc_conv(g[4+16*i:20+16*i])
    o+=_swap32(g[0x1e4:0x5a8]); o+=x[0x5a8:0x5ac]; o+=_swap32(g[0x5ac:])
    assert len(o)==len(x)
    return (0xf9f,0x1b3f,bytes(o))
