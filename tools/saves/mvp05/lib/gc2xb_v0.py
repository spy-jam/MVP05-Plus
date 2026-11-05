"""GameCube (.gci payload) -> Xbox (data.dat payload) dynasty converter for MVP Baseball 2005: the driver.
convert() collects one replacement per section (in Xbox template coordinates), applies them back to front,
then fixes the stream-end marker and filler. See ../FORMAT_NOTES.md and ../../README.md."""
import struct,sys,re,glob
sys.path.insert(0,'.'); sys.path.insert(0,'tools/out')
import teamconv,rosterblock,mgrconv,player_conv,containers
def s32(b): return b''.join(b[i:i+4][::-1] for i in range(0,len(b),4))
SIG=re.compile(rb'(?s).{10}\xbb\x55\x00\x00\x00[\x00-\x40]')
KEYG=b'\x69\x3d\xbc\x6a'; KEYX=b'\x6a\xbc\x3d\x69'
PAT=re.compile(rb"^[A-Za-z][A-Za-z .'\-]{0,11}$")
def _okrow(d,o):
    r=d[o:o+60]
    if len(r)<60: return False
    fn=r[8:20].split(b'\0')[0]; ln=r[20:32].split(b'\0')[0]
    return bool(PAT.match(fn)) and bool(PAT.match(ln))
def _tables(d,lo=0x1e000,hi=0x122000,minrows=30):
    out=[];i=lo
    while i<hi:
        if _okrow(d,i):
            j=i;n=0
            while _okrow(d,j): j+=60;n+=1
            if n>=minrows: out.append((i,n)); i=j; continue
        i+=1
    return out
def convert(gc,xb_tpl,sched=True,hist=True,shift=0):
    """gc: GC payload (0x186C00). xb_tpl: Xbox payload (0x222C00) used as base. Returns new Xbox payload."""
    reps=[]  # (xb_start, xb_end, new_bytes)  in template coordinates
    # 1 team table (126 x 60)
    maps=teamconv.load()
    t=b''.join(teamconv.gc_to_xb(gc[0x1b42+60*i:0x1b42+60*i+60],maps) for i in range(126))
    reps.append((0x1b3f,0x1b3f+7560,t))
    # 2 roster blocks
    P=gc.find(KEYG,0x12000)
    pos=[];i=0x38ce
    while i<P:
        if SIG.match(gc,i): pos.append(i); i+=48
        else: i+=1
    st=[pos[k] for k in range(0,len(pos),4)]; assert len(st)==126,len(st)
    st.append(P)
    ros=b''.join(rosterblock.conv(gc[st[k]:st[k+1]]) for k in range(126))
    Q=xb_tpl.find(KEYX,0x12000)
    # 3 post-roster: 3 tables, keylist, managers
    out=bytearray()
    p=P
    for tno in range(3):
        out+=s32(gc[p:p+4]); d=gc[p+4:p+4+504]
        # 0: current W-L (4 bytes/team: W,L,0,0) and 1: byte pairs -> copy; 2: last season W-L as two u16 -> swap16
        out+= b''.join(d[i:i+2][::-1] for i in range(0,len(d),2)) if tno==2 else d
        p+=508
    hdr,n=struct.unpack('>II',gc[p:p+8]); out+=s32(gc[p:p+8]); p+=8
    out+=s32(gc[p:p+12*n]); p+=12*n
    out+=s32(gc[p:p+28]); p+=28           # 24 zero bytes + key f58f3c1b
    out+=mgrconv.gc_table_to_xb(gc[p:p+48*n],n); p+=48*n
    # template extent of the same block (template has its own count)
    q=Q+1524; hx,nx=struct.unpack('<II',xb_tpl[q:q+8]); qe=q+8+12*nx+28+44*nx
    reps.append((0x38cb,Q+1524+0,ros+bytes(out)[:1524]))   # roster section + 3 tables
    reps.append((Q+1524,qe,bytes(out)[1524:]))
    # 4 per-player DB tables #8..#15 (60 B players, PackF x2, 4 B x2, Rec70004 x3) by tag ordinal
    import tablesconv
    reps+=tablesconv.table_reps(gc,xb_tpl); n=3250
    import postconv
    if sched: reps.append(postconv.sched_rep_all(gc,xb_tpl))
    reps.append(postconv.user_rep(gc,xb_tpl))
    if sched: reps.append(postconv.tail_rep(gc,xb_tpl))
    if hist:
        hr,ng=postconv.hist_rep(gc,xb_tpl); reps.append(hr)
    global DBG; DBG=dict(reps=reps,P=P,Q=Q,st=st)
    # apply back to front
    new=bytearray(xb_tpl); delta=0
    for a,b,c in sorted(reps,key=lambda r:-r[0]):
        new[a:b]=c; delta+=len(c)-(b-a)
    # marker 7 = stream end: shifts with delta; keep payload length constant
    m7=bytes.fromhex('0df0efbe')
    j=new.rfind(m7,0,len(new)); old=struct.unpack_from('<I',new,j+4)[0]
    struct.pack_into('<I',new,j+4,old+delta)
    if delta>0:
        # trailing 0x55bb pad absorbs growth
        new=new[:len(xb_tpl)]
    else:
        new+=bytes([0x55,0xbb])*((len(xb_tpl)-len(new))//2+1); new=new[:len(xb_tpl)]
    return bytes(new),delta,n
