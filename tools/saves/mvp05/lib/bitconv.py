import numpy as np, sys
sys.path.insert(0,'.')
import pconv
def perm(name):
    """returns array g2x: GC row bit idx (MSB-first stream order) -> XB row bit idx (LSB-first stream)"""
    words=pconv.words_of(name); g2x=[]
    for wi,w in enumerate(words):
        pos=0; p=0
        for n,wd in w:
            for b in range(wd):          # b: val bit from msb
                g=32*wi+pos+b; xb=32*wi+p+(wd-1-b)
                g2x.append((g,xb))
            pos+=wd; p+=wd
        # unused bits (none expected)
    a=np.full(32*len(words),-1)
    for g,x in g2x:a[g]=x
    return a
def gbits(b): return np.unpackbits(np.frombuffer(b,np.uint8))            # MSB first
def xbits(b): return np.unpackbits(np.frombuffer(b,np.uint8),bitorder='little')
def g2x_stream(gb,sg,sx,nrows,pm,xlen):
    """gb: GC bit array of body; build XB bit array of xlen bits"""
    out=np.zeros(xlen,np.uint8); R=len(pm); ok=pm>=0
    for i in range(nrows):
        s=sg+R*i
        if s+R>len(gb):break
        row=gb[s:s+R]
        idx=sx+R*i+pm[ok]
        if idx.max()>=xlen:continue
        out[idx]=row[ok]
    return out
