#!/usr/bin/env python3
"""
MVP Baseball 2005 - GameCube dynasty -> Xbox dynasty converter (one way, mid-season saves)
=========================================================================================

    python mvp_gc2xb.py  <GameCube .gci>  <Xbox template data.dat>  <output folder>  [--name NAME]

or run it with no arguments and it asks for the three paths (you can drag files into the window).

  GameCube .gci       your dynasty, exported from Dolphin's memory card manager (e.g. 69-GV4E-Dynasty_XXX.dat.gci)
  Xbox template       any Xbox MVP 2005 dynasty data.dat (supplies a few blocks that are the same in every
                      dynasty, the pre-2005 career history, and the save signature layout)
  output folder       gets data.dat (plus SaveMeta.xbx / saveimage.xbx copied from the template's folder,
                      if they are there). Put the files in your Xbox save folder (UDATA/45410056/<folder>/).

--name NAME sets the dynasty name stored inside data.dat (default: the template's).

What is converted: settings header, user team + profile, team (org) records incl. budgets, team table,
rosters / depth charts / injury lists, standings, managers, all 3250 player rows and per-player tables,
season stats, player history (last 6 seasons per player, as GameCube keeps), the four schedules with
results and line scores (sets the current date), trades, roster moves and injuries.
Not converted (kept from the template): three small blocks that are the same in every dynasty seen so far,
and 9 unidentified values at the end of the trades/injuries section.
Tested on mid-season saves only.
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
        print(__doc__.split("What is converted")[0])
        gc_path = ask("GameCube .gci file: ")
        tpl_path = ask("Xbox template data.dat: ")
        out_dir = ask("Output folder: ")
    else:
        gc_path, tpl_path, out_dir = args[:3]
    gc_path, tpl_path, out_dir = (os.path.abspath(p) for p in (gc_path, tpl_path, out_dir))

    for p in (gc_path, tpl_path):
        if not os.path.isfile(p):
            sys.exit(f"Not found: {p}")
    gci = open(gc_path, "rb").read()
    if len(gci) < GC_PAYLOAD_OFF + GC_PAYLOAD_LEN or gci[:4] != b"GV4E":
        sys.exit("That does not look like an MVP 2005 GameCube dynasty .gci (expected game id GV4E).")
    xf = open(tpl_path, "rb").read()

    try:
        import numpy  # noqa: F401
    except ImportError:
        print("numpy is needed; installing it now (one time)...")
        import subprocess
        r = subprocess.call([sys.executable, "-m", "pip", "install", "numpy"])
        try:
            import numpy  # noqa: F401
        except ImportError:
            sys.exit("Could not install numpy automatically. Run:  python -m pip install numpy")

    os.chdir(LIB)            # the converter modules load their tables relative to lib/
    sys.path.insert(0, LIB)
    import containers as C
    import gc2xb_v0 as G

    try:
        tmeta = C.parse_xbox(xf)
    except Exception as e:
        sys.exit(f"The template is not a valid Xbox MVP 2005 save: {e}")
    if tmeta.get("typ") != "Dynasty":
        sys.exit(f"The template is a '{tmeta.get('typ')}' save; it must be a Dynasty save.")

    gc = gci[GC_PAYLOAD_OFF:GC_PAYLOAD_OFF + GC_PAYLOAD_LEN]
    tpl = xf[XB_PAYLOAD_OFF:XB_PAYLOAD_OFF + XB_PAYLOAD_LEN]
    print("Converting...")
    new, delta, _ = G.convert(gc, tpl, sched=True, hist=True)
    out = C.build_xbox(xf, dict(name=name or tmeta["name"], typ="Dynasty", flags=tmeta["flags"], payload=new))
    if not C.verify_xbox(out):
        sys.exit("Internal error: the built save did not pass the signature check. Nothing written.")

    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, "data.dat")
    if os.path.isfile(dst):
        bak = dst + ".bak"
        n = 1
        while os.path.exists(bak):
            n += 1; bak = dst + f".bak{n}"
        shutil.copyfile(dst, bak)
        print(f"Existing data.dat backed up to {os.path.basename(bak)}")
    open(dst, "wb").write(out)
    src_dir = os.path.dirname(tpl_path)
    for extra in ("SaveMeta.xbx", "saveimage.xbx"):
        s = os.path.join(src_dir, extra)
        if os.path.isfile(s) and os.path.abspath(s) != os.path.join(out_dir, extra):
            shutil.copyfile(s, os.path.join(out_dir, extra))
    print(f"Done: {os.path.join(out_dir, 'data.dat')}")
    print("Copy the output folder's files into your Xbox save folder (back up the old ones first).")


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
