"""Split a dynasty payload (GC .gci or Xbox data.dat) at its 0xBEEFF00D markers.
usage: python3 sections.py save1 [save2 ...]   (platform detected from file name/extension)
Each marker is followed by a u32 (count/size/length). The LAST marker's u32 is the total stream length;
everything after it is 0xBB55 fill. Section 0x200 'hist' tail follows the 4th data marker."""
import sys,re,struct
def load(p):
    b=open(p,'rb').read()
    if p.lower().endswith('.gci'): return 'GC',b[0x2138:0x2138+0x186C00]
    return 'XB',b[0x108:]
def markers(plat,d):
    pat=b'\xBE\xEF\xF0\x0D' if plat=='GC' else b'\x0D\xF0\xEF\xBE'
    out=[]
    for m in re.finditer(pat,d):
        o=m.start(); v=struct.unpack('>I' if plat=='GC' else '<I',d[o+4:o+8])[0]
        out.append((o,v))
    return out
if __name__=='__main__':
    for p in sys.argv[1:]:
        plat,d=load(p); ms=markers(plat,d)
        print(p.split('/')[-1],plat,'markers:',len(ms))
        prev=0
        for o,v in ms:
            print('  @0x%06x value=0x%08x  (+0x%x from previous)'%(o,v,o-prev)); prev=o
