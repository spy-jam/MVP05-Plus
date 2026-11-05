"""Manager row table (34 x 48B GC / 44B Xbox). True record = stream + 2x14-char names + pad.
GC record (48): stream 19B (MSB-first, 160-bit PackA minus last byte) | names 28 | pad 1.
XB record (44): POST 8B (a00..a07, LSB-first) | PRE 8B (a08..a15) | names 28.   (POST of record i sits at XB record start; PRE follows.)"""
import sys
sys.path.insert(0,'tools/out')
import manager_conv as M
FIELDS=M.FIELDS
def gc_rec_to_xb(r):
    v=int.from_bytes(r[:19]+b'\0',  'big'); pos=160; vals={}
    for n,w in FIELDS:
        pos-=w; vals[n]=(v>>pos)&((1<<w)-1)
    def pack(fs):
        x=0;p=0
        for n,w in fs: x|=vals[n]<<p;p+=w
        return x.to_bytes(8,'little')
    return pack(M.POST)+pack(M.PRE)+r[19:47]
def xb_rec_to_gc(r):
    vals={}
    for fs,off in ((M.POST,0),(M.PRE,8)):
        x=int.from_bytes(r[off:off+8],'little');p=0
        for n,w in fs: vals[n]=(x>>p)&((1<<w)-1);p+=w
    v=0;pos=160
    for n,w in FIELDS:
        pos-=w; v|=vals.get(n,0)<<pos
    s=v.to_bytes(20,'big')[:19]
    return s+r[16:44]+b'\0'
def gc_table_to_xb(b,n=34): return b''.join(gc_rec_to_xb(b[48*i:48*i+48]) for i in range(n))
def xb_table_to_gc(b,n=34): return b''.join(xb_rec_to_gc(b[44*i:44*i+44]) for i in range(n))
