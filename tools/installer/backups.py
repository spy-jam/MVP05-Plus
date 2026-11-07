"""The save backups the game makes when it starts (src/common/save_backup.cpp), listed and restored.

  save backups/<YYYY-MM-DD HH-MM-SS>/E/...           a copy of hdd/E, the game's saves drive
  save backups/<...>/backup-contents.txt             written last: only a complete copy has it

Restoring puts a backup's E in place of hdd/E. The saves there first become a backup of their own
("<time> before restore"), which the game counts and prunes with the others, so a restore can be undone.
"""
import datetime
import os
import shutil
import subprocess

LIST = "backup-contents.txt"
TITLE_UDATA = os.path.join("E", "UDATA", "45410056")


class BackupError(Exception):
    pass


def game_running():
    if os.name != "nt":
        return False
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq MVP05.exe", "/NH"], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return "mvp05.exe" in r.stdout.lower()
    except OSError:
        return False


def save_name(folder):
    """A save's name as the game shows it, from its SaveMeta.xbx (UTF-16LE: "Name=<name>")."""
    try:
        with open(os.path.join(folder, "SaveMeta.xbx"), "rb") as f:
            b = f.read()
        t = b.decode("utf-16-le" if b[:2] == b"\xff\xfe" else "latin-1").lstrip("﻿")
        for line in t.splitlines():
            if line.startswith("Name="):
                return line[5:].strip()
    except OSError:
        pass
    return os.path.basename(folder)


def saves_in(drive_parent):
    """The game's saves under <drive_parent>/E, by name."""
    base = os.path.join(drive_parent, TITLE_UDATA)
    if not os.path.isdir(base):
        return []
    return sorted(save_name(os.path.join(base, d)) for d in os.listdir(base)
                  if os.path.isdir(os.path.join(base, d)))


def list_backups(root):
    """[{path, when, saves}] newest first: complete backups of this game's hdd (named by date)."""
    top = os.path.join(root, "save backups")
    out = []
    if not os.path.isdir(top):
        return out
    for d in os.listdir(top):
        p = os.path.join(top, d)
        if not d[:1].isdigit() or not os.path.isfile(os.path.join(p, LIST)) or not os.path.isdir(os.path.join(p, "E")):
            continue
        try:
            when = datetime.datetime.strptime(d[:19], "%Y-%m-%d %H-%M-%S")
        except ValueError:
            when = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(p, LIST)))
        out.append(dict(path=p, name=d, when=when, saves=saves_in(p)))
    return sorted(out, key=lambda b: b["when"], reverse=True)


def restore(root, backup, say=print):
    """backup's saves in place of the game's, after making a backup of the game's own."""
    if game_running():
        raise BackupError("close MVP05.exe first: the game keeps its saves open while it runs")
    src = os.path.join(backup, "E")
    if not os.path.isfile(os.path.join(backup, LIST)) or not os.path.isdir(src):
        raise BackupError("that backup isn't complete")
    hdd = os.path.join(root, "hdd")
    drive = os.path.join(hdd, "E")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    if os.path.isdir(drive) and os.listdir(drive):
        keep = os.path.join(root, "save backups", f"{stamp} before restore")
        shutil.copytree(drive, os.path.join(keep, "E"))
        with open(os.path.join(keep, LIST), "w") as f:
            f.write("the saves before a restore with MVP05-Plus Tools\n")
        say(f"Your current saves are kept as the backup \"{os.path.basename(keep)}\".")
    new, old = drive + ".restoring", drive + ".old"
    for p in (new, old):
        shutil.rmtree(p, ignore_errors=True)
    shutil.copytree(src, new)
    if os.path.isdir(drive):
        os.replace(drive, old)
    os.makedirs(hdd, exist_ok=True)
    os.replace(new, drive)
    shutil.rmtree(old, ignore_errors=True)
    say(f"Restored the saves from {os.path.basename(backup)}.")
