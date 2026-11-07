"""MVP05-Plus Tools. Install: puts your own discs' game files where the game looks for them, in the folder the installer is in.

  Xbox disc (required)        every file, into assets/ (as Mad Dog's original asks for by hand)
  GameCube disc (optional)    only the 11 files the button art needs, read into a temporary folder, made into
                              gc_icons/ (tools/gc_layout/make_icons.py), then deleted
  PS2 disc (optional)         the same for ps2_icons/ (tools/ps2_layout/make_ps2_icons.py)

Nothing is written anywhere else: no registry, no shortcuts, no Program Files. Deleting the folder removes it all.

Save backups: the game's own backups of your saves (save backups/), listed and restored.

  MVP05-Plus-Tools.exe                       the window
  MVP05-Plus-Tools.exe --xbox X [--gamecube G] [--ps2 P] [--dir D]   installing without it
"""
import argparse
import contextlib
import io
import os
import shutil
import sys
import tempfile
import threading
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("gc_layout", "ps2_layout"):  # the art builders (bundled beside this when frozen)
    for base in (os.path.join(HERE, "..", sub), os.path.join(getattr(sys, "_MEIPASS", HERE), sub)):
        if os.path.isdir(base) and base not in sys.path:
            sys.path.insert(0, base)

import discs  # noqa: E402

VERSION = "Beta 1"
GAME = "MVP05-Plus"


def game_dir():
    """The folder with MVP05.exe: the installer's own (frozen), else the repository's root."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(HERE, "..", ".."))


class Log:
    def __init__(self, say=print, progress=None):
        self.say, self.progress = say, progress


def need_space(folder, nbytes):
    free = shutil.disk_usage(folder).free
    if free < nbytes + (64 << 20):
        raise discs.DiscError(f"not enough room: {nbytes / 2**30:.1f} GB needed, {free / 2**30:.1f} GB free")


def install_xbox(src, root, log):
    assets = os.path.join(root, "assets")
    with discs.open_xbox(src) as d:
        files = d.files()
        todo = {}
        for p, (_, n) in files.items():
            dest = os.path.join(assets, *p.split("/"))
            if not (os.path.isfile(dest) and os.path.getsize(dest) == n):
                todo[p] = (dest, n)
        total = sum(n for _, n in todo.values())
        log.say(f"Xbox disc: MVP Baseball 2005, {len(files)} files"
                + (f", copying {len(todo)} ({total / 2**20:.0f} MB)" if todo else ", already in assets"))
        if not todo:
            return
        need_space(root, total)
        done = [0]

        def step(n):
            done[0] += n
            if log.progress:
                log.progress(done[0] / total)

        for p, (dest, _) in sorted(todo.items()):
            d.copy(p, dest, step)
    log.say("Xbox files are in assets.")


def build_art(kind, src, root, log):
    """gc_icons or ps2_icons from a disc; only the art's files are read, into a temporary folder that's deleted."""
    gc = kind == "gamecube"
    opener, names = (discs.open_gamecube, discs.GC_ART_FILES) if gc else (discs.open_ps2, discs.PS2_ART_FILES)
    out_name = "gc_icons" if gc else "ps2_icons"
    xbox_data = os.path.join(root, "assets", "data")
    if not os.path.isfile(os.path.join(xbox_data, "frontend", "shared.big")):
        raise discs.DiscError("the Xbox files aren't in assets yet: the art is made from them too")
    tmp = tempfile.mkdtemp(prefix="mvp-installer-")
    try:
        with opener(src) as d:
            log.say(f"{'GameCube' if gc else 'PS2'} disc: reading the {len(names)} files the button art needs")
            discs.extract(d, names, tmp, upper=not gc)
        disc_data = os.path.join(tmp, "data" if gc else "DATA")
        built = os.path.join(tmp, out_name)
        if gc:
            import make_icons as builder
        else:
            import make_ps2_icons as builder
        argv, sys.argv = sys.argv, [builder.__file__, xbox_data, disc_data, built]
        words = io.StringIO()
        try:
            with contextlib.redirect_stdout(words):
                builder.main()
        except SystemExit as e:
            raise discs.DiscError(f"making {out_name} stopped: {e}")
        finally:
            sys.argv = argv
        put_icons(built, os.path.join(root, out_name))
        log.say(f"{out_name} made ({count_files(os.path.join(root, out_name))} files).")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def count_files(d):
    return sum(len(f) for _, _, f in os.walk(d))


def put_icons(src, dest):
    """src's set in place of dest's, the old one kept until the new one is all there."""
    old = dest + ".old"
    shutil.rmtree(old, ignore_errors=True)
    if os.path.exists(dest):
        os.replace(dest, old)
    try:
        shutil.copytree(src, dest)
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        if os.path.exists(old):
            os.replace(old, dest)
        raise
    shutil.rmtree(old, ignore_errors=True)


# what a made set has (make_icons.py / make_ps2_icons.py); an older set may lack some, and the game shows Xbox art
# for whatever's missing
ICON_FILES = ["data/frontend/" + n for n in ("shared.big", "frontend.big", "ingame.big", "igonly.big", "minigame.big")
              ] + [f"data/frontend/load{i}.big" for i in range(8)] + ["data/igshapes/igcrsr.xsh"]


def is_icons_source(src):
    """A folder or a .zip: an icons set someone already made, not a disc."""
    return os.path.isdir(src) or src.lower().endswith(".zip")


def find_set(folder, name):
    """The set in folder: folder itself (it has data/frontend), or a name folder in it or one level further down."""
    def has(d):
        return os.path.isfile(os.path.join(d, "data", "frontend", "shared.big"))
    if has(folder) and os.path.basename(folder.rstrip("/\\")).lower() != ("ps2_icons" if name == "gc_icons" else
                                                                               "gc_icons"):
        return folder
    for d in [os.path.join(folder, name)] + [os.path.join(folder, s, name) for s in sorted(os.listdir(folder))
                                             if os.path.isdir(os.path.join(folder, s))]:
        if has(d):
            return d
    return None


def import_icons(kind, src, root, log):
    """gc_icons or ps2_icons someone already made (a folder, or a .zip with it), copied beside the game."""
    name = "gc_icons" if kind == "gamecube" else "ps2_icons"
    tmp = None
    try:
        if not os.path.isdir(src):
            import zipfile
            tmp = tempfile.mkdtemp(prefix="mvp-installer-")
            try:
                with zipfile.ZipFile(src) as z:
                    for m in z.infolist():
                        target = os.path.realpath(os.path.join(tmp, m.filename))
                        if not target.startswith(os.path.realpath(tmp) + os.sep):
                            raise discs.DiscError(f"{os.path.basename(src)} has a file outside its own folders")
                    z.extractall(tmp)
            except zipfile.BadZipFile:
                raise discs.DiscError(f"{os.path.basename(src)} isn't a zip that can be read")
            folder = tmp
        else:
            folder = src
        found = find_set(folder, name)
        if not found:
            raise discs.DiscError(f"no {name} in {os.path.basename(src) or src} (it should hold data/frontend/shared.big)")
        dest = os.path.join(root, name)
        if os.path.realpath(found) == os.path.realpath(dest):
            log.say(f"{name} is already in place.")
            return
        have = {os.path.relpath(os.path.join(d, f), found).replace(os.sep, "/").lower()
                for d, _, fs in os.walk(found) for f in fs}
        missing = [f for f in ICON_FILES if f not in have]
        put_icons(found, dest)
        log.say(f"{name} copied ({count_files(dest)} files).")
        if missing:
            log.say(f"  It's an older set without {', '.join(os.path.basename(m) for m in missing)}: the game shows "
                    f"Xbox art there. Make a new set from the disc for all of it.")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def run(root, xbox=None, gamecube=None, ps2=None, log=None):
    """gamecube / ps2: a disc image (the art is made from it), or a gc_icons / ps2_icons folder or .zip (copied)."""
    log = log or Log()
    if not (xbox or gamecube or ps2):
        raise discs.DiscError("choose your Xbox disc, and any GameCube or PS2 disc or icons")
    if xbox:
        install_xbox(xbox, root, log)
    for kind, src in (("gamecube", gamecube), ("ps2", ps2)):
        if src and is_icons_source(src):
            import_icons(kind, src, root, log)
        elif src:
            build_art(kind, src, root, log)
    if not os.path.isfile(os.path.join(root, "assets", "default.xbe")):
        log.say("The Xbox files aren't in assets yet: choose your Xbox disc too, the game needs it.")
    else:
        log.say("Done. Run MVP05.exe.")


# ---------------------------------------------------------------- the window

def gui(root):
    import tkinter as tk
    from tkinter import filedialog, ttk

    w = tk.Tk()
    w.title(f"{GAME} Tools ({VERSION}) by spy_jam")
    w.resizable(False, False)
    tabs = ttk.Notebook(w)
    tabs.grid(padx=8, pady=8)
    frm = ttk.Frame(tabs, padding=12)
    tabs.add(frm, text="Install")
    backups_tab(tabs, root, tk, ttk)
    ttk.Label(frm, text=f"{GAME} installs into this folder:", font=("Segoe UI", 10, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w")
    ttk.Label(frm, text=root, foreground="#555").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

    kinds = [
        ("xbox", "Xbox disc (required)", [("Xbox image", "*.iso *.xiso"), ("All files", "*.*")], True),
        ("gamecube", "GameCube disc, or a gc_icons folder or .zip someone made (optional, button art)",
         [("GameCube image or icons zip", "*.iso *.gcm *.rvz *.gcz *.ciso *.wia *.zip"), ("All files", "*.*")],
         "gc_icons"),
        ("ps2", "PS2 disc, or a ps2_icons folder or .zip someone made (optional, button art)",
         [("PS2 image or icons zip", "*.iso *.chd *.zip"), ("All files", "*.*")], "ps2_icons"),
    ]
    vars_ = {}
    for i, (k, label, types, folder_ok) in enumerate(kinds):
        v = tk.StringVar()
        vars_[k] = v
        ttk.Label(frm, text=label).grid(row=2 + 2 * i, column=0, columnspan=3, sticky="w")
        ttk.Entry(frm, textvariable=v, width=60).grid(row=3 + 2 * i, column=0, sticky="we", pady=(0, 6))

        def pick(v=v, types=types):
            p = filedialog.askopenfilename(filetypes=types)
            if p:
                v.set(os.path.normpath(p))

        ttk.Button(frm, text="Image…" if folder_ok is True else "File…", command=pick).grid(
            row=3 + 2 * i, column=1, padx=(6, 0), pady=(0, 6))

        def pickdir(v=v, what=folder_ok):
            p = filedialog.askdirectory(title="The folder with default.xbe" if what is True else f"The {what} folder")
            if p:
                v.set(os.path.normpath(p))
        ttk.Button(frm, text="Folder…", command=pickdir).grid(row=3 + 2 * i, column=2, padx=(6, 0), pady=(0, 6))

    bar = ttk.Progressbar(frm, length=440, mode="determinate", maximum=1.0)
    bar.grid(row=8, column=0, columnspan=3, sticky="we", pady=(8, 4))
    out = tk.Text(frm, width=72, height=9, state="disabled", wrap="word", relief="flat", background="#f4f4f4")
    out.grid(row=9, column=0, columnspan=3, **{"pady": 4})
    go = ttk.Button(frm, text="Install")
    go.grid(row=10, column=2, sticky="e", pady=(6, 0))

    def say(t):
        def f():
            out.configure(state="normal")
            out.insert("end", t + "\n")
            out.see("end")
            out.configure(state="disabled")
        w.after(0, f)

    def progress(x):
        w.after(0, lambda: bar.configure(value=x))

    def work():
        try:
            run(root, **{k: (v.get().strip() or None) for k, v in vars_.items()}, log=Log(say, progress))
            w.after(0, lambda: bar.configure(value=1.0))
        except discs.DiscError as e:
            say(f"Stopped: {e}")
        except Exception:
            say("Something went wrong:\n" + traceback.format_exc(limit=4))
        finally:
            w.after(0, lambda: go.configure(state="normal"))

    def start():
        go.configure(state="disabled")
        bar.configure(value=0)
        threading.Thread(target=work, daemon=True).start()

    go.configure(command=start)
    if os.path.isfile(os.path.join(root, "assets", "default.xbe")):
        say("The Xbox files are already in assets: choose only the discs you want button art from.")
    if not os.path.isfile(os.path.join(root, "MVP05.exe")):
        say("Note: MVP05.exe isn't in this folder. Put the installer in the game's folder first.")
    w.mainloop()


def backups_tab(tabs, root, tk, ttk):
    from tkinter import messagebox
    import backups as B

    frm = ttk.Frame(tabs, padding=12)
    tabs.add(frm, text="Save backups")
    ttk.Label(frm, text="Save backups", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(frm, wraplength=520, justify="left", text=(
        "The game backs up your saves each time it starts, when they've changed (save_backups in "
        "mvp05-settings.toml says how many to keep). Restoring puts all of a backup's saves back; your saves "
        "as they are now become a backup first, so you can undo it. Close the game first.")).grid(
        row=1, column=0, sticky="w", pady=(2, 8))
    tree = ttk.Treeview(frm, columns=("when", "saves"), show="headings", height=9, selectmode="browse")
    tree.heading("when", text="Backed up")
    tree.heading("saves", text="Saves in it")
    tree.column("when", width=220, anchor="w")
    tree.column("saves", width=300, anchor="w")
    tree.grid(row=2, column=0, sticky="we")
    out = tk.Text(frm, width=72, height=4, state="disabled", wrap="word", relief="flat", background="#f4f4f4")
    out.grid(row=4, column=0, pady=(8, 0))
    rows = {}

    def say(t):
        out.configure(state="normal")
        out.insert("end", t + "\n")
        out.see("end")
        out.configure(state="disabled")

    def refresh():
        tree.delete(*tree.get_children())
        rows.clear()
        for b in B.list_backups(root):
            when = b["when"].strftime("%Y-%m-%d %H:%M:%S") + (" (before restore)" if "before restore" in b["name"] else "")
            iid = tree.insert("", "end", values=(when,
                                                 ", ".join(b["saves"]) or "(no saves)"))
            rows[iid] = b
        if not rows:
            say("No backups yet: the game makes one when it starts, once you have saves.")

    def do_restore():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Save backups", "Pick a backup in the list first.")
            return
        b = rows[sel[0]]
        now = B.saves_in(os.path.join(root, "hdd"))
        if not messagebox.askyesno("Restore this backup?", (
                f"Your saves will be replaced by the ones backed up {b['when'].strftime('%Y-%m-%d %H:%M')}:\n"
                f"{', '.join(b['saves']) or '(none)'}\n\nYour saves now ({', '.join(now) or 'none'}) are kept as a "
                f"backup first.\n\nGo ahead?")):
            return
        try:
            B.restore(root, b["path"], say=say)
        except B.BackupError as e:
            say(f"Stopped: {e}")
        except Exception as e:
            say(f"Something went wrong: {e}")
        refresh()

    def open_folder():
        d = os.path.join(root, "save backups")
        if os.name == "nt" and os.path.isdir(d):
            os.startfile(d)

    bar = ttk.Frame(frm)
    bar.grid(row=3, column=0, sticky="we", pady=(8, 0))
    ttk.Button(bar, text="Restore…", command=do_restore).pack(side="left")
    ttk.Button(bar, text="Backups folder", command=open_folder).pack(side="right")
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="right", padx=6)
    refresh()


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--xbox")
    a.add_argument("--gamecube")
    a.add_argument("--ps2")
    a.add_argument("--dir", default=game_dir())
    o = a.parse_args()
    if not (o.xbox or o.gamecube or o.ps2):
        return gui(o.dir)
    try:
        run(o.dir, o.xbox, o.gamecube, o.ps2)
    except discs.DiscError as e:
        raise SystemExit(f"stopped: {e}")


if __name__ == "__main__":
    main()
