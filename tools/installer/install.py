"""MVP05-Plus Tools. Install: puts your own discs' game files where the game looks for them, in the folder the installer is in.

  Xbox disc (required)        every file, into assets/ (as Mad Dog's original asks for by hand)
  GameCube disc (optional)    only the 11 files the button art needs, read into a temporary folder, made into
                              gc_icons/ (tools/gc_layout/make_icons.py), then deleted
  PS2 disc (optional)         the same for ps2_icons/ (tools/ps2_layout/make_ps2_icons.py)

Nothing is written anywhere else: no registry, no shortcuts, no Program Files. Deleting the folder removes it all.

Saves (experimental): dynasty saves between the GameCube release (Dolphin .gci) and this game (tools/saves).

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
for sub in ("gc_layout", "ps2_layout", "saves"):  # the art builders (bundled beside this when frozen)
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
        dest = os.path.join(root, out_name)
        old = dest + ".old"
        shutil.rmtree(old, ignore_errors=True)
        if os.path.exists(dest):
            os.replace(dest, old)
        shutil.copytree(built, dest)
        shutil.rmtree(old, ignore_errors=True)
        log.say(f"{out_name} made ({sum(len(f) for _, _, f in os.walk(dest))} files).")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run(root, xbox=None, gamecube=None, ps2=None, log=None):
    log = log or Log()
    if xbox:
        install_xbox(xbox, root, log)
    elif not os.path.isfile(os.path.join(root, "assets", "default.xbe")):
        raise discs.DiscError("choose your Xbox disc: the game needs it")
    for kind, src in (("gamecube", gamecube), ("ps2", ps2)):
        if src:
            build_art(kind, src, root, log)
    log.say("Done. Run MVP05.exe.")


# ---------------------------------------------------------------- the window

def gui(root):
    import tkinter as tk
    from tkinter import filedialog, ttk

    w = tk.Tk()
    w.title(f"{GAME} Tools ({VERSION})")
    w.resizable(False, False)
    tabs = ttk.Notebook(w)
    tabs.grid(padx=8, pady=8)
    frm = ttk.Frame(tabs, padding=12)
    tabs.add(frm, text="Install")
    saves_tab(tabs, root, tk, ttk, filedialog)
    ttk.Label(frm, text=f"{GAME} installs into this folder:", font=("Segoe UI", 10, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w")
    ttk.Label(frm, text=root, foreground="#555").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

    kinds = [
        ("xbox", "Xbox disc (required)", [("Xbox image", "*.iso *.xiso"), ("All files", "*.*")], True),
        ("gamecube", "GameCube disc (optional, button art)",
         [("GameCube image", "*.iso *.gcm *.rvz *.gcz *.ciso *.wia"), ("All files", "*.*")], False),
        ("ps2", "PS2 disc (optional, button art)", [("PS2 image", "*.iso *.chd"), ("All files", "*.*")], False),
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

        ttk.Button(frm, text="Image…", command=pick).grid(row=3 + 2 * i, column=1, padx=(6, 0), pady=(0, 6))
        if folder_ok:
            def pickdir(v=v):
                p = filedialog.askdirectory(title="The folder with default.xbe")
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


def saves_tab(tabs, root, tk, ttk, filedialog):
    from tkinter import messagebox, simpledialog
    import saves05 as S

    frm = ttk.Frame(tabs, padding=12)
    tabs.add(frm, text="Saves (experimental)")
    ttk.Label(frm, text="Dynasty saves between the GameCube release (Dolphin) and this game",
              font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
    ttk.Label(frm, foreground="#8a5a00", wraplength=520, justify="left", text=(
        "Experimental: tested on mid-season dynasties; playoff saves untested. A GameCube dynasty replaces one of "
        "your dynasties here, which is copied into \"save backups\" first. Close the game before converting.")).grid(
        row=1, column=0, columnspan=3, sticky="w", pady=(2, 8))
    cols = ("name", "type", "when")
    tree = ttk.Treeview(frm, columns=cols, show="headings", height=7, selectmode="browse")
    for c, t, wd in zip(cols, ("Save", "Type", "Saved"), (250, 90, 150)):
        tree.heading(c, text=t)
        tree.column(c, width=wd, anchor="w")
    tree.grid(row=2, column=0, columnspan=3, sticky="we")
    out = tk.Text(frm, width=72, height=6, state="disabled", wrap="word", relief="flat", background="#f4f4f4")
    out.grid(row=4, column=0, columnspan=3, pady=(8, 0))
    saves = {}

    def say(t):
        def f():
            out.configure(state="normal")
            out.insert("end", t + "\n")
            out.see("end")
            out.configure(state="disabled")
        frm.after(0, f)

    def refresh():
        tree.delete(*tree.get_children())
        saves.clear()
        try:
            for s in S.list_saves(root):
                iid = tree.insert("", "end", values=(s["name"], s["type"], s["when"].strftime("%Y-%m-%d %H:%M")))
                saves[iid] = s
        except Exception as e:
            say(f"Couldn't read the saves: {e}")
        if not saves:
            say(f"No saves in {os.path.relpath(S.udata(root), root)} yet. Start a dynasty in the game and save "
                f"it once: a GameCube dynasty is converted over one of yours.")

    def chosen(dynasty=True):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Saves", "Pick one of your saves in the list first.")
            return None
        s = saves[sel[0]]
        if dynasty and s["type"] != "Dynasty":
            messagebox.showinfo("Saves", f"\"{s['name']}\" is a {s['type']} save: pick a Dynasty save.")
            return None
        return s

    def background(fn):
        def work():
            try:
                fn()
            except S.SaveError as e:
                say(f"Stopped: {e}")
            except Exception:
                say("Something went wrong (nothing was written):\n" + traceback.format_exc(limit=4))
            frm.after(0, refresh)
        threading.Thread(target=work, daemon=True).start()

    def do_import():
        s = chosen()
        if not s:
            return
        gci = filedialog.askopenfilename(title="Your GameCube dynasty (.gci from Dolphin's Memory Card Manager)",
                                         filetypes=[("GameCube save", "*.gci"), ("All files", "*.*")])
        if not gci:
            return
        if not messagebox.askyesno("Replace this dynasty?", (
                f"\"{s['name']}\" will be replaced by the GameCube dynasty.\n\nIt's copied into \"save backups\" "
                f"first, so you can put it back.\n\nGo ahead?")):
            return
        background(lambda: S.import_gamecube(root, gci, s["folder"], say=say))

    def do_export():
        s = chosen()
        if not s:
            return
        tpl = filedialog.askopenfilename(title="Any GameCube MVP 2005 dynasty .gci (a template for the card's "
                                               "header and icons)",
                                         filetypes=[("GameCube save", "*.gci"), ("All files", "*.*")])
        if not tpl:
            return
        dest = filedialog.askdirectory(title="Where to put the GameCube save")
        if not dest:
            return
        name = simpledialog.askstring("Name", "Dynasty name on the GameCube (up to 10 letters or digits):",
                                      initialvalue="".join(c for c in s["name"] if c.isalnum())[:10])
        if name is None:
            return
        background(lambda: S.export_gamecube(root, s["folder"], tpl, dest, name or None, say=say))

    def open_folder():
        d = S.udata(root)
        os.makedirs(d, exist_ok=True)
        if os.name == "nt":
            os.startfile(d)

    bar = ttk.Frame(frm)
    bar.grid(row=3, column=0, columnspan=3, sticky="we", pady=(8, 0))
    ttk.Button(bar, text="Import GameCube dynasty…", command=do_import).pack(side="left")
    ttk.Button(bar, text="Export to GameCube…", command=do_export).pack(side="left", padx=6)
    ttk.Button(bar, text="Standings…", command=lambda: standings_window(frm, root, S, chosen, say, refresh)).pack(
        side="left")
    ttk.Button(bar, text="Saves folder", command=open_folder).pack(side="right")
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="right", padx=6)
    refresh()


def standings_window(parent, root, S, chosen, say, refresh):
    """Short seasons: every MLB team's record projected to 162 games, in the save file or in the running game."""
    import tkinter as tk
    from tkinter import messagebox, ttk

    w = tk.Toplevel(parent)
    w.title("Standings for short seasons")
    w.resizable(False, False)
    f = ttk.Frame(w, padding=12)
    f.grid()
    ttk.Label(f, wraplength=470, justify="left", text=(
        "Projects every MLB team's record to a 162-game season (the same winning percentage), for dynasties "
        "played with a short schedule. Do it after the last regular-season game, before the playoffs.")).grid(
        row=0, column=0, columnspan=2, sticky="w")
    how = tk.StringVar(value="file")
    ttk.Radiobutton(f, variable=how, value="file", text=(
        "In the save file (experimental): save the dynasty, close the game, patch the save picked in the list, "
        "load it again")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
    ttk.Radiobutton(f, variable=how, value="memory", text=(
        "In the running game (the patcher's method): save the dynasty and stay on the season screen")).grid(
        row=2, column=0, columnspan=2, sticky="w")
    row = ttk.Frame(f)
    row.grid(row=3, column=0, columnspan=2, sticky="w", pady=6)
    ttk.Label(row, text="Games in your season schedule:").pack(side="left")
    games = tk.StringVar(value="")
    ttk.Entry(row, textvariable=games, width=6).pack(side="left", padx=6)
    ttk.Label(row, text="(the running game's search needs it)", foreground="#666").pack(side="left")
    tree = ttk.Treeview(f, columns=("t", "w", "l", "pw", "pl"), show="headings", height=10)
    for c, t in zip(("t", "w", "l", "pw", "pl"), ("Team", "W", "L", "162: W", "162: L")):
        tree.heading(c, text=t)
        tree.column(c, width=80, anchor="center")
    tree.grid(row=4, column=0, columnspan=2)
    note = ttk.Label(f, text="", wraplength=470, justify="left")
    note.grid(row=5, column=0, columnspan=2, sticky="w", pady=4)
    state = {}

    def show(recs, text):
        tree.delete(*tree.get_children())
        for t, wn, ls in recs:
            pw, pl = S.project(wn, ls)
            tree.insert("", "end", values=(t, wn, ls, pw, pl))
        note.configure(text=text)

    def season_games():
        try:
            n = int(games.get())
            assert 1 <= n <= 162
            return n
        except (ValueError, AssertionError):
            messagebox.showinfo("Standings", "Enter how many games your season schedule has (1-162).", parent=w)
            return None

    def find():
        state.clear()
        try:
            if how.get() == "file":
                s = chosen()
                if not s:
                    return
                r = S.read_standings(s["folder"])
                text = f"{r['name']}"
                if r["scheduled"]:
                    left = r["scheduled"] - r["played"]
                    text += (f": all {r['scheduled']} scheduled games played." if not left else
                             f": {left} of {r['scheduled']} scheduled games not played yet. Patch after the last one.")
                state.update(kind="file", save=s)
                show(r["records"], text)
            else:
                n = season_games()
                if not n:
                    return
                import standings_mem as M
                h, addr, fmt, recs = M.find(n, root, lambda t: note.configure(text=t))
                state.update(kind="memory", h=h, addr=addr, fmt=fmt, n=n)
                show([(t, a, b) for t, (a, b) in zip(S.MLB_TEAMS, recs)],
                     f"Found in the running game at {addr:#x} ({'[W][L]' if fmt == 'A' else 'split halves'}).")
        except Exception as e:
            show([], f"Stopped: {e}")

    def apply():
        if not state:
            messagebox.showinfo("Standings", "Press Find first and check the records.", parent=w)
            return
        try:
            if state["kind"] == "file":
                S.patch_standings(root, state["save"]["folder"], say=say)
                note.configure(text="Patched. Load the dynasty and advance to the playoffs, then save.")
                refresh()
            else:
                import standings_mem as M
                ok = M.apply(state["h"], state["addr"], state["fmt"], state["n"])
                note.configure(text="Written. In the game: advance to the playoffs, then save the dynasty." if ok else
                               "The write failed: try running the Tools as administrator.")
        except Exception as e:
            note.configure(text=f"Stopped: {e}")
        state.clear()

    def closing():
        if state.get("kind") == "memory":
            import standings_mem as M
            M.close(state["h"])
        w.destroy()

    b = ttk.Frame(f)
    b.grid(row=6, column=0, columnspan=2, sticky="e")
    ttk.Button(b, text="Find", command=find).pack(side="left")
    ttk.Button(b, text="Patch", command=apply).pack(side="left", padx=6)
    w.protocol("WM_DELETE_WINDOW", closing)


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
