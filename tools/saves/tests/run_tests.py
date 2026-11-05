#!/usr/bin/env python3
"""Regression test for the save converters (Python reference, or a port).

Put the reference saves in a folder using the names listed in test_vectors.json (inputs), e.g.
    refsaves/mvp05/69-GV4E-Dynasty_KCR.dat.gci
    refsaves/mvp06/CF56F1B2E6CF/data.dat   (+ SaveMeta.xbx, saveimage.xbx in the same folder)
then run
    python run_tests.py refsaves

Each input is checked against its SHA-1 first (a different save cannot be tested against these hashes).
Each case runs the Python reference tool and compares the output file's SHA-1 and its payload SHA-1.

To test a port, compare your own output for the same inputs with `payload_sha1` (game data only) and
`file_sha1` (whole file: also covers names, header fields and checksums)."""
import os, sys, json, hashlib, subprocess, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
V = json.load(open(os.path.join(HERE, 'test_vectors.json')))
sha1 = lambda p: hashlib.sha1(open(p, 'rb').read()).hexdigest()


def main(refdir):
    ok = True
    for rel, info in V['inputs'].items():
        p = os.path.join(refdir, rel)
        if not os.path.isfile(p):
            print('missing input:', rel); ok = False; continue
        if sha1(p) != info['sha1']:
            print('input differs from the reference save:', rel); ok = False
    if not ok:
        sys.exit('fix the inputs first')
    tmp = tempfile.mkdtemp(); outs = {}
    for c in V['cases']:
        args = [outs['t1'] if a == '<t1 output data.dat>' else os.path.join(refdir, a) if not a.startswith('--') and a not in ('STROS', 'KCR') else a
                for a in c['args']]
        od = os.path.join(tmp, c['id'])
        if c['game'] == 'mvp05':
            tool = os.path.join(ROOT, 'mvp05', 'mvp_gc2xb.py' if c['direction'] == 'gc-to-xbox' else 'mvp_xb2gc.py')
            cmd = [sys.executable, '-I', tool, args[0], args[1], od] + args[2:]
        else:
            tool = os.path.join(ROOT, 'mvp06', 'mvp06_convert.py')
            cmd = [sys.executable, '-I', tool, c['direction'], args[0], args[1], od]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        out = os.path.join(od, c['output']); outs[c['id']] = out
        good = sha1(out) == c['file_sha1']
        print('%s %-12s %-5s %s' % (c['id'], c['direction'], 'OK' if good else 'DIFF', c['tested_in_game']))
        ok &= good
    shutil.rmtree(tmp, ignore_errors=True)
    print('ALL OK' if ok else 'FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
