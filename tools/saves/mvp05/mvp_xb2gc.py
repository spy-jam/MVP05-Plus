#!/usr/bin/env python3
"""
MVP Baseball 2005 - Xbox dynasty -> GameCube dynasty converter (mid-season saves)
=================================================================================

    python mvp_xb2gc.py  <Xbox data.dat>  <GameCube template .gci>  <output folder>  [--name NAME]

or run it with no arguments and it asks for the three paths (you can drag files into the window).

  Xbox data.dat        your dynasty (UDATA/45410056/<folder>/data.dat)
  GameCube template    any MVP 2005 GameCube dynasty .gci (supplies the few blocks that are the same in every
                       dynasty, and the memory card file header/icon)
  output folder        gets 69-GV4E-Dynasty_<NAME>.dat.gci. Import it with Dolphin's memory card manager.

--name NAME sets the dynasty name (max 10 characters; default: the template's).

GameCube keeps at most 6 history rows per player (Xbox up to 16), so older seasons are dropped, as the
GameCube game does itself. Everything else converts as in mvp_gc2xb.py (see FORMAT_NOTES.md).
"""
import os, sys, shutil


HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "lib")

GC_PAYLOAD_OFF, GC_PAYLOAD_LEN = 0x2138, 0x186C00
XB_PAYLOAD_OFF, XB_PAYLOAD_LEN = 0x108, 0x222C00


def ask(prompt):
    v = input(prompt).strip().strip('"').strip("'")
    return v


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    name = None
    if "--name" in argv:
        i = argv.index("--name")
        if i + 1 < len(argv):
            name = argv[i + 1]
            if name in args: args.remove(name)
    if len(args) < 3:
        print(__doc__.split("GameCube keeps")[0])
        xb_path = ask("Xbox data.dat: ")
        tpl_path = ask("GameCube template .gci: ")
        out_dir = ask("Output folder: ")
    else:
        xb_path, tpl_path, out_dir = args[:3]
    xb_path, tpl_path, out_dir = (os.path.abspath(p) for p in (xb_path, tpl_path, out_dir))
    for p in (xb_path, tpl_path):
        if not os.path.isfile(p):
            sys.exit(f"Not found: {p}")
    gtf = open(tpl_path, "rb").read()
    if len(gtf) < GC_PAYLOAD_OFF + GC_PAYLOAD_LEN or gtf[:4] != b"GV4E":
        sys.exit("The template does not look like an MVP 2005 GameCube dynasty .gci (expected game id GV4E).")
    xf = open(xb_path, "rb").read()

    try:
        import numpy  # noqa: F401
    except ImportError:
        print("numpy is needed; installing it now (one time)...")
        import subprocess
        subprocess.call([sys.executable, "-m", "pip", "install", "numpy"])
        try:
            import numpy  # noqa: F401
        except ImportError:
            sys.exit("Could not install numpy automatically. Run:  python -m pip install numpy")

    os.chdir(LIB)
    sys.path.insert(0, LIB)
    import containers as C
    import xb2gc as R
    import gc_checksums as GCS

    try:
        meta = C.parse_xbox(xf)
    except Exception as e:
        sys.exit(f"Not a valid Xbox MVP 2005 save: {e}")
    if meta.get("typ") != "Dynasty":
        sys.exit(f"That is a '{meta.get('typ')}' save; it must be a Dynasty save.")
    if not C.verify_xbox(xf):
        print("Note: the Xbox save's signature does not verify; converting anyway.")
    gmeta = C.parse_gc(gtf)
    name = (name or gmeta["name"] or "DYNASTY")[:10]

    print("Converting...")
    payload = R.convert(meta["payload"], gtf[GC_PAYLOAD_OFF:GC_PAYLOAD_OFF + GC_PAYLOAD_LEN])
    out = C.build_gc(gtf, dict(name=name, typ="Dynasty", flags=gmeta["flags"], payload=payload))
    if not GCS.check(bytearray(out)):
        sys.exit("Internal error: the built .gci failed its checksum check. Nothing written.")

    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, f"69-GV4E-Dynasty_{name}.dat.gci")
    if os.path.isfile(dst):
        bak = dst + ".bak"; n = 1
        while os.path.exists(bak):
            n += 1; bak = dst + f".bak{n}"
        shutil.copyfile(dst, bak)
        print(f"Existing file backed up to {os.path.basename(bak)}")
    open(dst, "wb").write(out)
    print(f"Done: {dst}")
    print("Import it in Dolphin: Tools > Memory Card Manager > Import.")


if __name__ == "__main__":
    import traceback
    interactive = len(sys.argv) < 2
    try:
        main(sys.argv[1:])
    except SystemExit as e:
        if e.code not in (None, 0):
            print("\nSTOPPED:", e.code)
    except Exception:
        print("\nSTOPPED: the converter hit an error. Nothing was written.")
        print("Please send this whole message:\n")
        traceback.print_exc()
    if interactive:
        try: input("\nPress Enter to exit...")
        except EOFError: pass
