#!/usr/bin/env python3
"""Container layer for MVP Baseball 2005 dynasty saves (GameCube .gci and Xbox data.dat).

Handles everything AROUND the payload: headers, names, sizes, checksums / signatures.
The payload itself (0x186C00 bytes on GC, 0x222C00 on Xbox) is passed through untouched - converting its
contents between the two platforms is a separate step (see FORMAT_NOTES.md).

Both builders take a TEMPLATE save of the target platform (any existing save) to supply the constant parts
(banner/icon art, GCI directory fields, Xbox header constants).
"""
import hashlib, hmac, struct
from gc_checksums import ea_crc

GC_HDR, GC_HDR_LEN = 0x2088, 0xB0          # save header inside the .gci
GC_PAYLOAD = GC_HDR + GC_HDR_LEN            # 0x2138
GC_PAYLOAD_LEN = 0x186C00
GC_BLOCK = 0x2000

XB_SIG_LEN = 0x14
XB_HDR, XB_HDR_LEN = 0x50, 0xB8             # header covered by signature 0
XB_PAYLOAD = XB_HDR + XB_HDR_LEN            # 0x108
XB_PAYLOAD_LEN = 0x222C00
XB_SIG_KEY = b'\0' * 16                     # XboxSignatureKey in the MVP05 recomp. A real console uses the
                                            # title certificate's key instead (pass key=... to build_xbox).

def _wstr(b, enc):  return b.decode(enc).split('\0')[0]
def _pack_w(s, n, enc):  return s.encode(enc).ljust(n, b'\0')[:n]

# --------------------------------------------------------------------------------------------- GameCube
def parse_gc(buf: bytes) -> dict:
    h = buf[GC_HDR:GC_HDR + GC_HDR_LEN]
    cs = struct.unpack('>4I', h[:16]); sizes = struct.unpack('>4I', h[16:32])
    assert sizes[0] == GC_HDR_LEN, 'unexpected header size'
    psz = sizes[1]
    return dict(
        name=_wstr(h[0x28:0x3E], 'utf-16-be'), typ=_wstr(h[0x3E:0x5E], 'utf-16-be'),
        flags=struct.unpack('>I', h[0x24:0x28])[0], payload=buf[GC_PAYLOAD:GC_PAYLOAD + psz],
        checksums=cs, sizes=sizes, blocks=struct.unpack('>I', h[0x20:0x24])[0])

def build_gc(template: bytes, d: dict) -> bytes:
    name, typ, payload = d['name'], d['typ'], d['payload']
    assert len(payload) == GC_PAYLOAD_LEN, 'GC payload must be 0x%X bytes' % GC_PAYLOAD_LEN
    if len(name) > 10:
        print('warning: dynasty name truncated to 10 characters for the GameCube header'); name = name[:10]
    fname = ('Dynasty_%s.dat' % name)
    out = bytearray(template)
    # data size + total length in 8 KB blocks
    data_end = GC_PAYLOAD + len(payload)
    blocks = -(-(data_end - 0x40) // GC_BLOCK)
    out = out[:0x40 + blocks * GC_BLOCK].ljust(0x40 + blocks * GC_BLOCK, b'\0')
    out[GC_PAYLOAD:GC_PAYLOAD + len(payload)] = payload
    out[GC_PAYLOAD + len(payload):] = b'\0' * (len(out) - GC_PAYLOAD - len(payload))
    struct.pack_into('>I', out, 0x40, len(payload) + GC_HDR_LEN)             # first u32 of card data
    out[0x08:0x28] = fname.encode('ascii').ljust(0x20, b'\0')                  # GCI directory file name
    struct.pack_into('>H', out, 0x38, blocks)                                   # GCI block count
    out[0x64:0x84] = ('Dynasty-%s' % name).encode('latin1').ljust(0x20, b'\0')  # comment line 2
    h = bytearray(out[GC_HDR:GC_HDR + GC_HDR_LEN])
    struct.pack_into('>I', h, 0x10, GC_HDR_LEN); struct.pack_into('>I', h, 0x14, len(payload))
    struct.pack_into('>I', h, 0x20, blocks); struct.pack_into('>I', h, 0x24, d['flags'])
    h[0x28:0x3E] = _pack_w(name, 0x16, 'utf-16-be'); h[0x3E:0x5E] = _pack_w(typ, 0x20, 'utf-16-be')
    h[0x94:0xAF] = fname.encode('ascii').ljust(0x1B, b'\0')
    out[GC_HDR:GC_HDR + GC_HDR_LEN] = h
    # comment/icon block checksum: s32 at 0x2084 = sum of the signed bytes 0x40..0x2083 (name is in the comment)
    struct.pack_into('>i', out, 0x2084, sum(b - 256 if b > 127 else b for b in out[0x40:0x2084]))
    # checksums: [0] header body, [1] payload; [2]/[3] (icon/banner) kept from the template
    c0 = ea_crc(bytes(h[0x10:])); c1 = ea_crc(bytes(payload))
    struct.pack_into('>II', out, GC_HDR, c0, c1)
    return bytes(out)

# --------------------------------------------------------------------------------------------- Xbox
def parse_xbox(buf: bytes) -> dict:
    h = buf[XB_HDR:XB_HDR + XB_HDR_LEN]
    hdr_end, psz = struct.unpack('<II', h[:8])
    assert hdr_end == XB_PAYLOAD, 'unexpected header end'
    return dict(
        name=_wstr(h[0x18:0x38], 'utf-16-le'), typ=_wstr(h[0x38:0x58], 'utf-16-le'),
        flags=struct.unpack('<I', h[0x14:0x18])[0], payload=buf[XB_PAYLOAD:XB_PAYLOAD + psz],
        sig_header=buf[:0x14], sig_payload=buf[0x14:0x28])

def xbox_sigs(hdr: bytes, payload: bytes, key=XB_SIG_KEY):
    return (hmac.new(key, hdr, hashlib.sha1).digest(), hmac.new(key, payload, hashlib.sha1).digest())

def build_xbox(template: bytes, d: dict, key=XB_SIG_KEY) -> bytes:
    name, typ, payload = d['name'], d['typ'], d['payload']
    assert len(payload) == XB_PAYLOAD_LEN, 'Xbox payload must be 0x%X bytes' % XB_PAYLOAD_LEN
    h = bytearray(template[XB_HDR:XB_HDR + XB_HDR_LEN])
    struct.pack_into('<II', h, 0, XB_PAYLOAD, len(payload)); struct.pack_into('<I', h, 0x14, d['flags'])
    h[0x18:0x38] = _pack_w(name, 0x20, 'utf-16-le'); h[0x38:0x58] = _pack_w(typ, 0x20, 'utf-16-le')
    h[0x58:0x98] = _pack_w('%s (%s)' % (name, typ), 0x40, 'utf-16-le')
    out = bytearray(0x50) + h + payload
    s0, s1 = xbox_sigs(bytes(h), bytes(payload), key)
    out[0:0x14], out[0x14:0x28] = s0, s1
    return bytes(out)

def xbox_savemeta(name: str, typ: str) -> bytes:
    return ('\ufeffName=%s (%s)\r\n' % (name, typ)).encode('utf-16-le')

def verify_xbox(buf: bytes, key=XB_SIG_KEY) -> bool:
    d = parse_xbox(buf)
    s0, s1 = xbox_sigs(buf[XB_HDR:XB_HDR + XB_HDR_LEN], buf[XB_PAYLOAD:], key)
    return s0 == buf[:0x14] and s1 == buf[0x14:0x28]
