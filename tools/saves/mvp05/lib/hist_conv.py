"""History-table (section after marker #6) converter. Row/group format and bit maps learned from matched pairs.
Group  = key u32 | count u8 | count x row.   Row (20 bytes) = link u32 | year u16 | 14 data bytes.
GC: BE key/link/year, data bits MSB-first (per-type permutation). Xbox: LE, LSB-first. Type = 2-bit field (1 batter, 2 pitcher).
GC keeps the LAST 6 rows per player, Xbox up to 16.  Links are runtime heap pointers (NOT solved - see regen_links).
usage as a tool: python3 hist_conv.py learn GC XB [GC XB...]   -> writes hist_maps.json
                 python3 hist_conv.py test  GC XB            -> Xbox->GC rebuild vs real GC, GC->Xbox row check
"""
import sys,json,struct,collections; sys.path.insert(0,'.')
from sections import load,markers
GC_CAP,XB_CAP=6,16
def parse(pl,t):
    f='>I' if pl=='GC' else '<I'; i=0; out=[]
    while i+5<=len(t):
        n=t[i+4]
        if n==0 or n>XB_CAP or i+5+20*n>len(t): raise ValueError('bad group at %d'%i)
        out.append((struct.unpack(f,t[i:i+4])[0],[t[i+5+20*k:i+25+20*k] for k in range(n)])); i+=5+20*n
    return out
def gbits(b): return [(v>>(7-j))&1 for v in b for j in range(8)]
def xbits(b): return [(v>>j)&1 for v in b for j in range(8)]
def gpack(bits): return bytes(sum(bits[k*8+j]<<(7-j) for j in range(8)) for k in range(len(bits)//8))
def xpack(bits): return bytes(sum(bits[k*8+j]<<j for j in range(8)) for k in range(len(bits)//8))
def gtype(d): return d[3]>>6          # GC byte 3 of data (after year+team): top 2 bits
def xtype(d): return d[3]&3
def learn(pairs):
    import numpy as np
    by=collections.defaultdict(list)
    for gr,xr in pairs: by[xtype(xr)].append((gr,xr))
    M={}
    for t,L in by.items():
        GB=np.array([gbits(g) for g,x in L],dtype=np.float32); XB=np.array([xbits(x) for g,x in L],dtype=np.float32)
        A=(GB.T@XB+(1-GB).T@(1-XB))/len(L)
        g2x={}
        for g in range(GB.shape[1]):
            if GB[:,g].std()>0:
                j=int(A[g].argmax()); 
                if A[g,j]>0.999: g2x[g]=j
        gc={g:int(GB[0,g]) for g in range(GB.shape[1]) if GB[:,g].std()==0}
        xc={x:int(XB[0,x]) for x in range(XB.shape[1]) if XB[:,x].std()==0}
        M[str(t)]={'g2x':{str(k):v for k,v in g2x.items()},'gconst':{str(k):v for k,v in gc.items()},'xconst':{str(k):v for k,v in xc.items()},'rows':len(L)}
    return M
def load_maps(p='hist_maps.json'):
    import os
    if not os.path.isabs(p): p=os.path.join(os.path.dirname(os.path.abspath(__file__)),p)
    M=json.load(open(p)); out={}
    for t,m in M.items():
        g2x={int(k):v for k,v in m['g2x'].items()}; x2g={v:k for k,v in g2x.items()}
        out[int(t)]=(g2x,x2g,{int(k):v for k,v in m['gconst'].items()},{int(k):v for k,v in m['xconst'].items()})
    return out
def row_xb2gc(xd,maps):   # xd = 16 bytes after link (year + 14)
    g2x,x2g,gconst,xconst=maps[xtype(xd)]
    xb=xbits(xd); gb=[0]*128
    for g,v in gconst.items(): gb[g]=v
    for x,g in x2g.items(): gb[g]=xb[x]
    return gpack(gb)
def row_gc2xb(gd,maps):
    g2x,x2g,gconst,xconst=maps[gtype(gd)]
    gb=gbits(gd); xb=[0]*128
    for x,v in xconst.items(): xb[x]=v
    for g,x in g2x.items(): xb[x]=gb[g]
    return xpack(xb)
def regen_links(rows,base):   # placeholder: sequential 0x14 stepping, last row 0. NOT verified against the game.
    out=[]; 
    for i,r in enumerate(rows): out.append(r)
    return out
def xb_to_gc(xt,maps,link_base=0x80DB00C4):
    res=bytearray(); addr=link_base
    for key,rows in parse('XB',xt):
        rows=rows[-GC_CAP:]; res+=struct.pack('>I',key)+bytes([len(rows)])
        for i,r in enumerate(rows):
            link=0 if i==len(rows)-1 else addr+0x14*(i+1)
            res+=struct.pack('>I',link)+row_xb2gc(r[4:],maps)
        addr+=0x14*len(rows)+0x100
    return bytes(res)
def gc_to_xb(gt,maps,link_base=0x81CB004C):
    res=bytearray(); addr=link_base
    for key,rows in parse('GC',gt):
        res+=struct.pack('<I',key)+bytes([len(rows)])
        for i,r in enumerate(rows):
            link=0 if i==len(rows)-1 else addr+0x14*(i+1)
            res+=struct.pack('<I',link)+row_gc2xb(r[4:],maps)
        addr+=0x14*len(rows)+0x100
    return bytes(res)
def tails(gp,xp):
    _,g=load(gp); _,x=load(xp); mg=markers('GC',g); mx=markers('XB',x)
    return g[mg[5][0]+8:mg[6][0]], x[mx[5][0]+8:mx[6][0]]
def pairs_of(gt,xt):
    G=parse('GC',gt); X=parse('XB',xt); out=[]
    for (kg,gr),(kx,xr) in zip(G,X):
        assert kg==kx
        for a,b in zip(gr,xr[-len(gr):]): out.append((a[4:],b[4:]))
    return out
if __name__=='__main__':
    cmd=sys.argv[1]; a=sys.argv[2:]
    if cmd=='learn':
        P=[]
        for i in range(0,len(a),2): P+=pairs_of(*tails(a[i],a[i+1]))
        M=learn(P); json.dump(M,open('hist_maps.json','w')); print('rows used',len(P),{t:(len(m['g2x']),m['rows']) for t,m in M.items()})
    if cmd=='test':
        maps=load_maps(); gt,xt=tails(a[0],a[1])
        built=xb_to_gc(xt,maps); 
        def strip(t,pl):  # drop link fields
            out=bytearray()
            for key,rows in parse(pl,t):
                out+=struct.pack('>I',key)+bytes([len(rows)])
                for r in rows: out+=r[4:]
            return bytes(out)
        print('GC history from Xbox: length ok',len(built)==len(gt),'| identical ignoring links:',strip(built,'GC')==strip(gt,'GC'))
        back=gc_to_xb(gt,maps); xs=strip(back,'XB')
        # GC->XB can only restore the last 6 rows; compare those
        ok=True
        for (k,gr),(k2,xr) in zip(parse('GC',gt),parse('XB',xt)):
            for a_,b_ in zip(parse('XB',back)[0][1][:0],[]): pass
        B=parse('XB',back); X=parse('XB',xt)
        good=sum(1 for (k,br),(k2,xr) in zip(B,X) for a_,b_ in zip(br,xr[-len(br):]) if a_[4:]==b_[4:]); tot=sum(len(br) for k,br in B)
        print('GC->Xbox rows equal to real Xbox rows: %d/%d'%(good,tot))
