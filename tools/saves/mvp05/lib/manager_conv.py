"""GC <-> Xbox converter for the manager table (PackA, 22 fields). GC row 0x30 bytes, Xbox row 0x2C bytes."""
import struct
# decomp PackA, declaration order. GC words are 32 bits with explicit pads; Xbox omits pads and packs LSB-first contiguously.
PACKA=[
 [('top0',8),('a00',16),('pad0',8)],
 [('a01',15),('a02',1),('a03',6),('a04',8),('pad1',2)],
 [('a05',7),('a06',10),('a07',1),('a08',7),('a09',4),('a0A',2),('pad2',1)],
 [('a0B',4),('a0C',3),('a0D',4),('a0E',1),('a0F',7),('a10',3),('a11',1),('a12',7),('pad3',2)],
 [('a13',7),('a14',7),('a15',7),('pad4',11)]]
# NOTE: the decomp lists a08..a0A inside word 2 with a05..a07 (7+10+1+7+4+2+1 = 32).
FIELDS=[(n,w) for word in PACKA for n,w in word]
REAL=[(n,w) for n,w in FIELDS if not n.startswith(('pad','top'))]
POST=[f for f in REAL if f[0]<='a07']   # a00..a07  (64 bits) -> Xbox bytes 36..43
PRE =[f for f in REAL if f[0]>'a07']    # a08..a15  (64 bits) -> Xbox bytes 0..7
assert sum(w for _,w in POST)==64 and sum(w for _,w in PRE)==64
def _gc_stream(rec):
    # bytes 37..47 then 0..7 (stream starts after the leading pad byte 36); 20 bytes; last word keeps only its top 3 bytes
    s=rec[37:48]+rec[0:8]+b'\0'
    return int.from_bytes(s,'big')   # 20 bytes = 160 bits, MSB-first
def gc_to_xb(rec):
    v=_gc_stream(rec);pos=160;vals={}
    for n,w in FIELDS:
        pos-=w;vals[n]=(v>>pos)&((1<<w)-1)
    out=bytearray(44);out[8:36]=rec[8:36]
    def pack(fs):
        x=0;p=0
        for n,w in fs: x|=vals[n]<<p;p+=w
        return x.to_bytes(8,'little')
    out[36:44]=pack(POST);out[0:8]=pack(PRE)
    return bytes(out)
def xb_to_gc(rec):
    vals={}
    for fs,off in ((POST,36),(PRE,0)):
        x=int.from_bytes(rec[off:off+8],'little');p=0
        for n,w in fs: vals[n]=(x>>p)&((1<<w)-1);p+=w
    v=0;pos=160
    for n,w in FIELDS:
        pos-=w;v|=vals.get(n,0)<<pos
    s=v.to_bytes(20,'big')           # 160-bit stream
    out=bytearray(48);out[8:36]=rec[8:36]
    out[37:48]=s[0:11];out[0:8]=s[11:19]
    return bytes(out)
