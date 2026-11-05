#!/usr/bin/env python3
"""Pull MVP Baseball 2005 (GameCube GV4E69) control tables out of main.dol or the disc image.

The pad base class keeps 0x10B 16-byte entries {short a, b, modeA, modeB, op, pad; float scale}.
fn_802DD224 (common defaults, if that is what it is) and fn_80008664 (the gcpad vslot39 layout)
write them with straight-line stores; this runs both with a tiny PowerPC interpreter on
llvm-objdump's text and prints the resulting table as JSON.
usage: gc_extract.py <main.dol | disc.iso> out.json
"""
import json, re, struct, subprocess, sys, tempfile, os

FUNCS = {'defaults': (0x802D8B64, 0x3134), 'gc_layout': (0x80008664, 0x1DE8), 'gc_poll': (0x8000A44C, 0xA68)}

def load_dol(path):
    d = open(path, 'rb').read()
    if d[:6] == b'GV4E69' or d[0x1c:0x20] == b'\xc2\x33\x9f\x3d':
        off, = struct.unpack_from('>I', d, 0x420)
        d = d[off:]
    offs = struct.unpack_from('>18I', d, 0); addrs = struct.unpack_from('>18I', d, 0x48); sizes = struct.unpack_from('>18I', d, 0x90)
    secs = [(addrs[i], offs[i], sizes[i]) for i in range(18) if sizes[i]]
    end = max(o + s for a, o, s in secs)
    return d[:end], secs

class Mem:
    def __init__(s, dol, secs): s.dol, s.secs, s.w = dol, secs, {}
    def rd(s, a, n):
        v = 0
        for i in range(n):
            b = s.w.get(a + i)
            if b is None:
                b = 0
                for va, o, sz in s.secs:
                    if va <= a + i < va + sz: b = s.dol[o + a + i - va]; break
            v = (v << 8) | b
        return v
    def wr(s, a, n, v, log):
        for i in range(n): s.w[a + i] = (v >> (8 * (n - 1 - i))) & 0xff
        log.append((a, n, v))

def disasm(dol, secs, va, size):
    for a, o, s in secs:
        if a <= va < a + s:
            blob = dol[o + va - a:o + va - a + size]; break
    with tempfile.TemporaryDirectory() as t:
        b, e = os.path.join(t, 'f.bin'), os.path.join(t, 'f.o')
        open(b, 'wb').write(blob)
        subprocess.run(['llvm-objcopy', '-I', 'binary', '-O', 'elf32-powerpc', '--rename-section', '.data=.text,code', b, e], check=True)
        out = subprocess.run(['llvm-objdump', '-d', '--triple=powerpc-unknown-unknown', '--adjust-vma=0x%x' % va, e], capture_output=True, text=True, check=True).stdout
    ins = []
    for line in out.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} ){4}\s*(.*)', line)
        if m:
            t = re.sub(r'\s*<[^>]*>', '', m.group(2)).strip()
            bm = re.match(r'(b\w*)\s+(?:(\d+),\s*)?(0x[0-9a-f]+)$', t)
            if bm and int(bm.group(3), 16) < size:
                t = '%s %s0x%x' % (bm.group(1), (bm.group(2) + ', ') if bm.group(2) else '', int(bm.group(3), 16) + va)
            a = int(m.group(1), 16)
            ins.append((a + va if a < size else a, t))
    return ins

def sx16(v): return v - 0x10000 if v & 0x8000 else v

def run(ins, mem, regs, log, warn):
    r = dict(regs); f = {}
    idx = {a: i for i, (a, _) in enumerate(ins)}
    i = 0; steps = 0
    while i < len(ins) and steps < 200000:
        steps += 1
        a, t = ins[i]; i += 1
        parts = t.split(None, 1); op = parts[0]; rest = parts[1] if len(parts) > 1 else ''
        args = [x.strip() for x in rest.split(',')] if rest else []
        def R(x): return r.get(int(x), 0) & 0xffffffff
        def EA(x):
            m = re.match(r'(-?\d+)\((\d+)\)', x); d, b = int(m.group(1)), int(m.group(2))
            return ((R(b) if b else 0) + d) & 0xffffffff
        if op == 'li': r[int(args[0])] = int(args[1], 0) & 0xffffffff
        elif op == 'lis': r[int(args[0])] = (int(args[1], 0) << 16) & 0xffffffff
        elif op == 'addi': r[int(args[0])] = (R(args[1]) + int(args[2], 0)) & 0xffffffff
        elif op == 'addis': r[int(args[0])] = (R(args[1]) + (int(args[2], 0) << 16)) & 0xffffffff
        elif op in ('ori', 'oris'): r[int(args[0])] = R(args[1]) | (int(args[2], 0) << (16 if op == 'oris' else 0))
        elif op == 'mr': r[int(args[0])] = R(args[1])
        elif op == 'or': r[int(args[0])] = R(args[1]) | R(args[2])
        elif op == 'add': r[int(args[0])] = (R(args[1]) + R(args[2])) & 0xffffffff
        elif op == 'subi': r[int(args[0])] = (R(args[1]) - int(args[2], 0)) & 0xffffffff
        elif op == 'slwi': r[int(args[0])] = (R(args[1]) << int(args[2])) & 0xffffffff
        elif op == 'mulli': r[int(args[0])] = (R(args[1]) * int(args[2], 0)) & 0xffffffff
        elif op in ('stw', 'stwu'):
            ea = EA(args[1]); mem.wr(ea, 4, R(args[0]), log)
            if op == 'stwu': r[int(re.search(r'\((\d+)\)', args[1]).group(1))] = ea
        elif op == 'sth': mem.wr(EA(args[1]), 2, R(args[0]) & 0xffff, log)
        elif op == 'mtctr': r['ctr'] = R(args[0])
        elif op == 'mtlr': r['lr'] = R(args[0])
        elif op == 'mflr': r[int(args[0])] = r.get('lr', 0)
        elif op == 'mfctr': r[int(args[0])] = r.get('ctr', 0)
        elif op == 'sthx': mem.wr((R(args[1]) + R(args[2])) & 0xffffffff, 2, R(args[0]) & 0xffff, log)
        elif op == 'stwx': mem.wr((R(args[1]) + R(args[2])) & 0xffffffff, 4, R(args[0]), log)
        elif op == 'stfsx': mem.wr((R(args[1]) + R(args[2])) & 0xffffffff, 4, f.get(int(args[0]), 0), log)
        elif op == 'blrl': warn.append('%08x indirect call (end)' % a); return r
        elif op == 'stb': mem.wr(EA(args[1]), 1, R(args[0]) & 0xff, log)
        elif op == 'stfs': mem.wr(EA(args[1]), 4, f.get(int(args[0]), 0), log)
        elif op == 'lfs': f[int(args[0])] = mem.rd(EA(args[1]), 4)
        elif op == 'fmr': f[int(args[0])] = f.get(int(args[1]), 0)
        elif op == 'lwz': r[int(args[0])] = mem.rd(EA(args[1]), 4)
        elif op == 'lhz': r[int(args[0])] = mem.rd(EA(args[1]), 2)
        elif op == 'lha': r[int(args[0])] = sx16(mem.rd(EA(args[1]), 2)) & 0xffffffff
        elif op == 'stmw':
            ea = EA(args[1])
            for k in range(int(args[0]), 32): mem.wr(ea + 4 * (k - int(args[0])), 4, R(k), log)
        elif op in ('lmw', 'mfcr', 'mtcrf', 'nop', 'extsh', 'clrlwi', 'rlwinm', 'lbz', 'lfd', 'stfd', 'psq_st', 'psq_l', 'cmpwi', 'cmplwi', 'cmpw', 'cmplw', 'fcmpu', 'fcmpo', 'crclr', 'crset', 'neg', 'bctrl', 'mullw', 'fmuls', 'fadds', 'fsubs', 'xoris', 'frsp', 'fctiwz'):
            if op in ('bctrl',): warn.append('%08x virtual call' % a)
            if op in ('extsh',): r[int(args[0])] = sx16(R(args[1]) & 0xffff) & 0xffffffff
            if op == 'lmw': pass
            if op.startswith('cmp') or op.startswith('fcmp'): warn.append('%08x compare %s' % (a, t))
        elif op == 'bl': warn.append('%08x call %s' % (a, args[0]))
        elif op == 'blr': return r
        elif op == 'b':
            tgt = int(args[0], 0)
            if tgt in idx: i = idx[tgt]
            else: warn.append('%08x tail branch %x' % (a, tgt)); return r
        elif op.startswith('b'):
            warn.append('%08x conditional %s (fell through)' % (a, t))
        else:
            warn.append('%08x UNHANDLED %s' % (a, t))
    return r

def table(log, this):
    ent = {}
    for a, n, v in log:
        o = a - this
        if 0 <= o < 0x10B * 16:
            e = ent.setdefault(o // 16, bytearray(b'\xee' * 16))
            for k in range(n): e[o % 16 + k] = (v >> (8 * (n - 1 - k))) & 0xff
    out = {}
    for i, b in sorted(ent.items()):
        sh = list(struct.unpack_from('>6h', b, 0)); sc = struct.unpack_from('>f', b, 12)[0]
        out[i] = {'shorts': sh, 'scale': sc, 'raw': b.hex()}
    return out

def main():
    dol, secs = load_dol(sys.argv[1])
    mem = Mem(dol, secs)
    # r2/r13 from __start
    entry = None
    res = {}
    ep, = struct.unpack_from('>I', dol, 0xE0)
    boot = disasm(dol, secs, ep, 0x200)
    sda = {}
    for k in (2, 13):
        hi = lo = None
        for a, t in boot:
            if t.startswith('lis %d,' % k): hi = int(t.split(',')[1], 0) & 0xffff
            if t.startswith('ori %d, %d,' % (k, k)) or t.startswith('addi %d, %d,' % (k, k)): lo = int(t.split(',')[2], 0)
        sda[k] = ((hi or 0) << 16) + (lo or 0)
    print('r2 %08x r13 %08x' % (sda[2], sda[13]))
    THIS = 0x90000000
    for name in ('defaults', 'gc_layout'):
        va, sz = FUNCS[name]
        ins = disasm(dol, secs, va, sz)
        open(sys.argv[2] + '.%s.s' % name, 'w').write('\n'.join('%08x  %s' % x for x in ins))
        log, warn = [], []
        regs = {1: 0x81000000, 3: THIS, 2: sda[2], 13: sda[13]}
        run(ins, mem, regs, log, warn)
        res[name] = {'table': table(log, THIS), 'warnings': warn}
    va, sz = FUNCS['gc_poll']
    open(sys.argv[2] + '.gc_poll.s', 'w').write('\n'.join('%08x  %s' % x for x in disasm(dol, secs, va, sz)))
    json.dump(res, open(sys.argv[2], 'w'), indent=1)
    for k, v in res.items(): print(k, len(v['table']), 'entries,', len(v['warnings']), 'warnings')

if __name__ == '__main__': main()
