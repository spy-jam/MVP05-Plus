import json,re,sys
import numpy as np
U='/mnt/user-data/uploads/'
def gbits(b): return np.unpackbits(np.frombuffer(b,np.uint8))
def xbits(b): return np.unpackbits(np.frombuffer(b,np.uint8),bitorder='little')
def perm_from_words(words):
    """returns pm: GC row-bit idx -> XB row-bit idx (or -1) ; row bits = sum of word sizes"""
    pm=[];base=0
    for w in words:
        # word kinds
        if len(w)==1 and w[0][2] in('plain','arr'):
            n=w[0][1]; nb=n//8
            if w[0][2]=='arr':
                for k in range(nb):
                    for b in range(8): pm.append((base+8*k+(7-b),base+8*k+b))
            else:
                for v in range(n):
                    pm.append((base+8*(nb-1-v//8)+(7-v%8),base+v))
            base+=n; continue
        tot=sum(f[1] for f in w); size=32 if tot>16 else (16 if tot>8 else 8)
        if tot not in(8,16,32): size=32 if tot>16 else 16 if tot>8 else 8
        pos=0;p=0
        for f in w:
            wd=f[1]
            for b in range(wd):
                # GC: word stored BE; fields MSB-first. stream pos of value-bit (wd-1-b) ... use msb-first index
                pm.append((base+pos+b, base+p+(wd-1-b)))   # NOTE: valid when size==32 BE word (stream order==MSB-first)
            pos+=wd;p+=wd
        base+=size
    a=np.full(base,-1)
    for g,x in pm:
        if g<base:a[g]=x
    return a
def fit(body_g,body_x,pm,rows_lo=100,nr=40,maxoff=None):
    R=len(pm); ok=pm>=0
    best=(10**9,None)
    gb=gbits(body_g[:R//8*(rows_lo+nr+3)+8]); xb=xbits(body_x[:R//8*(rows_lo+nr+3)+8])
    for sg in range(0,(maxoff or R)):
        for sx in (sg,):
            bad=0
            for i in range(rows_lo,rows_lo+nr):
                r=gb[sg+R*i:sg+R*i+R]
                if len(r)<R: bad+=R;break
                t=np.zeros(R,np.uint8); t[pm[ok]]=r[ok]
                bad+=int((xb[sx+R*i:sx+R*i+R][ok.nonzero()[0]*0+np.arange(R)][pm[ok]] != r[ok]).sum()) if False else int((xb[sx+R*i:sx+R*i+R][pm[ok]]!=r[ok]).sum())
            if bad<best[0]: best=(bad,sg)
    return best
