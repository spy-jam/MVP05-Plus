"""Schedule/game list entries: 0x1C bytes, from decomp Unk8052B5C4_Ent.
 +0  u16 m0 (key)                       swap16
 +2  16-bit bitfield: f2:10 f3:1 f4:5   GC MSB-first / Xbox LSB-first
 +4  Sub[0]: u32 key (+4), 8 payload bytes (+8..+15)   key swap32, payload bytes copied as-is (decomp: unsigned char m4; char pad5[7])
 +16 Sub[1]: u32 key, 8 payload bytes
List header: 0xBEEFF00D marker, u32 count, then count entries."""
import struct
def _bf_gc_to_xb(h):
    f2=(h>>6)&0x3FF; f3=(h>>5)&1; f4=h&0x1F
    return f2|(f3<<10)|(f4<<11)
def _bf_xb_to_gc(h):
    f2=h&0x3FF; f3=(h>>10)&1; f4=(h>>11)&0x1F
    return (f2<<6)|(f3<<5)|f4
def gc_to_xb(rec):
    out=bytearray(28)
    m0,h=struct.unpack_from('>HH',rec,0)
    struct.pack_into('<HH',out,0,m0,_bf_gc_to_xb(h))
    for off in (4,16):
        struct.pack_into('<I',out,off,struct.unpack_from('>I',rec,off)[0])
        out[off+4:off+12]=_nib(rec[off+4:off+12])
    return bytes(out)
def _nib(p):
    # w1 = b0 runs, b1 hits, then 4 nibbles; w2 = 6 nibbles + 8-bit field. Nibbles swap within each byte (MSB-first vs LSB-first).
    sw=lambda b:((b&15)<<4)|(b>>4)
    return bytes([p[0],p[1],sw(p[2]),sw(p[3]),sw(p[4]),sw(p[5]),sw(p[6]),p[7]])
def xb_to_gc(rec):
    out=bytearray(28)
    m0,h=struct.unpack_from('<HH',rec,0)
    struct.pack_into('>HH',out,0,m0,_bf_xb_to_gc(h))
    for off in (4,16):
        struct.pack_into('>I',out,off,struct.unpack_from('<I',rec,off)[0])
        out[off+4:off+12]=_nib(rec[off+4:off+12])
    return bytes(out)
