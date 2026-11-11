import json,struct
PS=json.load(open('packstructs.json'))
def words_of(name):
    return [[(f[0],f[1]) for f in w] for w in PS[name]['words']]
def gc_to_xb_record(words,rec):
    out=bytearray()
    for wi,w in enumerate(words):
        v=struct.unpack_from('>I',rec,4*wi)[0];pos=32;x=0;p=0
        for n,wd in w:
            pos-=wd;val=(v>>pos)&((1<<wd)-1);x|=val<<p;p+=wd
        out+=struct.pack('<I',x)
    return bytes(out)
def xb_to_gc_record(words,rec):
    out=bytearray()
    for wi,w in enumerate(words):
        x=struct.unpack_from('<I',rec,4*wi)[0];p=0;v=0;pos=32
        for n,wd in w:
            val=(x>>p)&((1<<wd)-1);p+=wd;pos-=wd;v|=val<<pos
        out+=struct.pack('>I',v)
    return bytes(out)
