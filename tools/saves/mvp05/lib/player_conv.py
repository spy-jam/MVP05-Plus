"""Exact GC <-> Xbox converter for the 0x3C player (PackE) record. Layout derived from the decomp's PackE + verified against saves."""
import struct
from packe_decomp_layout import WORDS
# per word: (xb_offset, gc source) ; GC words 0-4 at 37,41,45,49,53 ; w5 = bytes 57..59 + byte0 ; w6 at 1 ; w7 = bytes 5..7 (upper 24 bits)
XB_OFF=[36,40,44,48,52,56,0,4]
def _gc_word(rec,wi):
    if wi<=4: return struct.unpack_from('>I',rec,37+4*wi)[0]
    if wi==5: return (int.from_bytes(rec[57:60],'big')<<8)|rec[0]
    if wi==6: return struct.unpack_from('>I',rec,1)[0]
    if wi==7: return int.from_bytes(rec[5:8],'big')<<8
def _put_gc_word(rec,wi,v):
    if wi<=4: struct.pack_into('>I',rec,37+4*wi,v)
    elif wi==5: rec[57:60]=(v>>8).to_bytes(3,'big'); rec[0]=v&0xFF
    elif wi==6: struct.pack_into('>I',rec,1,v)
    elif wi==7: rec[5:8]=((v>>8)&0xFFFFFF).to_bytes(3,'big')
def _split_gc(w,v):
    out=[];pos=32
    for n,wd in w:
        pos-=wd;out.append((v>>pos)&((1<<wd)-1))
    return out
def _join_gc(w,vals):
    v=0;pos=32
    for (n,wd),x in zip(w,vals):
        pos-=wd;v|=(x&((1<<wd)-1))<<pos
    return v
def _split_xb(w,v):
    out=[];pos=0
    for n,wd in w:
        out.append((v>>pos)&((1<<wd)-1));pos+=wd
    return out
def _join_xb(w,vals):
    v=0;pos=0
    for (n,wd),x in zip(w,vals):
        v|=(x&((1<<wd)-1))<<pos;pos+=wd
    return v
W=[ [('h0',16),('h2',16)] ]+WORDS[1:]
def gc_to_xb(rec):
    out=bytearray(60);out[8:36]=rec[8:36]
    for wi,w in enumerate(W):
        v=_gc_word(rec,wi)
        if wi==0: vals=[v>>16,v&0xFFFF]
        else: vals=_split_gc(w,v)
        if wi==0: xv=(vals[0])|(vals[1]<<16)
        else: xv=_join_xb(w,vals)
        struct.pack_into('<I',out,XB_OFF[wi],xv)
    return bytes(out)
def xb_to_gc(rec):
    out=bytearray(60);out[8:36]=rec[8:36]
    for wi,w in enumerate(W):
        xv=struct.unpack_from('<I',rec,XB_OFF[wi])[0]
        if wi==0: gv=((xv&0xFFFF)<<16)|(xv>>16)   # h0 high half, h2 low half in BE word
        else: gv=_join_gc(w,_split_xb(w,xv))
        _put_gc_word(out,wi,gv)
    return bytes(out)
