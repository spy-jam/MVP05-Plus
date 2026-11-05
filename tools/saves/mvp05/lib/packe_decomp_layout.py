import struct
# PackE (player/attrib record, 0x3C bytes) from the decomp: words of bitfields, widths in declaration order (MSB-first on GC, LSB-first on Xbox)
# ('u16',) entries are plain 16-bit values; names are None for padding
WORDS=[
 [('h0','u16'),('h2','u16')],
 [('f02',6),('f03',8),('f04',7),('f05',4),('f06',5),('f07',2)],
 [('f08',2),('f09',1),('f0A',3),('f0B',1),('f0C',4),('f0D',7),('f0E',4),('f0F',4),('f10',4),(None,2)],
 [('f11',4),('f12',4),('f13',4),('f14',4),('f15',4),('f16',3),('f17',1),('f18',8)],
 [('f19',3),('f1A',2),('f1B',2),('f1C',8),('f1D',7),('f1E',7),(None,3)],
 [('f1F',8),('f20',1),('f21',7),('f22',1),('f23',4),('f24',4),('f25',3),('f26',3),(None,1)],
 [('f27',3),('f28',3),('f29',2),('f2A',2),('f2B',3),('f2C',10),('f2D',1),('f2E',2),('f2F',2),('f30',1),(None,3)],
 [('f31',7),('f32',5),('f33',1),('f34',2),('f35',2),('f36',3),(None,12)],
]
for w in WORDS:
    if w[0][1]=='u16': continue
    assert sum(x[1] for x in w)==32, w
# byte offsets of each word within the SAVED 0x3C record: words 0,1 at 0..7 ; words 2..7 at 36..59
WOFF=[36,40,44,48,52,56,0,4]   # XB offsets of words 0..7 in the saved record (verified)
NAMES=(8,36)
def gc_fields(rec):
    out={}
    for wi,w in enumerate(WORDS):
        o=WOFF[wi]
        if w[0][1]=='u16':
            out['h0']=struct.unpack_from('>H',rec,o)[0];out['h2']=struct.unpack_from('>H',rec,o+2)[0];continue
        v=struct.unpack_from('>I',rec,o)[0];pos=32
        for n,wd in w:
            pos-=wd
            if n: out[n]=(v>>pos)&((1<<wd)-1)
    return out
def xb_fields(rec):
    out={}
    for wi,w in enumerate(WORDS):
        o=WOFF[wi]
        if w[0][1]=='u16':
            out['h0']=struct.unpack_from('<H',rec,o)[0];out['h2']=struct.unpack_from('<H',rec,o+2)[0];continue
        v=struct.unpack_from('<I',rec,o)[0];pos=0
        for n,wd in w:
            if n: out[n]=(v>>pos)&((1<<wd)-1)
            pos+=wd
    return out
def pack_xb(fields,names):
    rec=bytearray(60);rec[NAMES[0]:NAMES[1]]=names
    for wi,w in enumerate(WORDS):
        o=WOFF[wi]
        if w[0][1]=='u16':
            struct.pack_into('<HH',rec,o,fields['h0'],fields['h2']);continue
        v=0;pos=0
        for n,wd in w:
            if n: v|=fields[n]<<pos
            pos+=wd
        struct.pack_into('<I',rec,o,v)
    return bytes(rec)
def pack_gc(fields,names):
    rec=bytearray(60);rec[NAMES[0]:NAMES[1]]=names
    for wi,w in enumerate(WORDS):
        o=WOFF[wi]
        if w[0][1]=='u16':
            struct.pack_into('>HH',rec,o,fields['h0'],fields['h2']);continue
        v=0;pos=32
        for n,wd in w:
            pos-=wd
            if n: v|=fields[n]<<pos
        struct.pack_into('>I',rec,o,v)
    return bytes(rec)
