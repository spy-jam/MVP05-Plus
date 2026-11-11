"""The updater on a pretend game folder: python tests/test_updater.py <tools/installer>"""
import hashlib, io, json, os, sys, tempfile, zipfile
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
import updater as U


def release_zip(path, files):
    man = {n: hashlib.sha256(d).hexdigest() for n, d in files.items()}
    with zipfile.ZipFile(path, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
        z.writestr(U.MANIFEST, json.dumps(man))


def put(root, name, data):
    p = os.path.join(root, *name.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def get(root, name):
    with open(os.path.join(root, *name.split("/")), "rb") as f:
        return f.read()


assert U.newer("Beta 2", "Beta 1") and not U.newer("Beta 1", "Beta 1") and U.newer("1.0", "Beta 9")
assert U.newer("v1.0.1", "1.0") and not U.newer("Beta 3", "1.0") and U.newer("RC 1", "Beta 4")

root = tempfile.mkdtemp()
old = {"MVP05.exe": b"old game", U.LAUNCHER_EXE: b"old launcher", "README.md": b"old readme",
       U.SETTINGS: b"# display\r\ndisplay_mode = \"fullscreen\"  # how\r\nwidth = 0\r\nsave_backups = 30\r\n"}
for n, d in old.items():
    put(root, n, d)
put(root, U.SETTINGS, b"# display\r\ndisplay_mode = \"windowed\"  # how\r\nwidth = 1920\r\nsave_backups = 100\r\nmine = true\r\n")
put(root, "assets/default.xbe", b"game")
put(root, "hdd/E/UDATA/x/save", b"save")

new = {"MVP05.exe": b"new game", U.LAUNCHER_EXE: b"new launcher", "README.md": b"new readme",
       "NEW-FILE.txt": b"added", U.SETTINGS: b"# display\r\ndisplay_mode = \"fullscreen\"  # how\r\nwidth = 0\r\n"
       b"save_backups = 30\r\nnew_option = true  # new\r\n",
       "assets/PUT-GAME-FILES-HERE.txt": b"in every release zip"}
z = os.path.join(root, "rel.zip")
release_zip(z, new)
files = U.verify(z)
assert "assets/PUT-GAME-FILES-HERE.txt" not in files  # checked, then left out: nothing goes into assets
U.apply(root, files, "Beta 1")
assert not os.path.exists(os.path.join(root, "assets", "PUT-GAME-FILES-HERE.txt"))
assert get(root, "MVP05.exe") == b"new game" and get(root, "NEW-FILE.txt") == b"added"
s = get(root, U.SETTINGS).decode()
assert 'display_mode = "windowed"  # how' in s and "width = 1920" in s and "save_backups = 100" in s, s
assert "new_option = true  # new" in s and "mine = true" in s and "\r\n" in s, s
assert get(root, "assets/default.xbe") == b"game" and get(root, "hdd/E/UDATA/x/save") == b"save"
assert U.last_update(root)["from"] == "Beta 1"
assert U.undo(root) == "Beta 1"
assert get(root, "MVP05.exe") == b"old game" and get(root, "README.md") == b"old readme"
assert not os.path.exists(os.path.join(root, "NEW-FILE.txt"))
assert "save_backups = 100" in get(root, U.SETTINGS).decode()  # undo keeps your settings
assert U.last_update(root) is None

# refused: a damaged file, a file into your game files, a zip without the game
release_zip(z, new)
with zipfile.ZipFile(z, "a") as zz:
    zz.writestr("extra.txt", b"x")  # not in the manifest
try:
    U.verify(z); raise SystemExit("file outside the manifest accepted")
except U.UpdateError:
    pass
release_zip(z, dict(new, **{"assets/default.xbe": b"evil"}))
try:
    U.verify(z); raise SystemExit("protected file accepted")
except U.UpdateError as e:
    assert "mustn't" in str(e)
release_zip(z, dict(new, **{"schedules/original/schedule.big": b"evil"}))
try:
    U.verify(z); raise SystemExit("the player's original schedule accepted")
except U.UpdateError:
    pass
release_zip(z, dict(new, **{"schedules/64/mlb162_1.dat": b"ok"}))
U.verify(z)  # the shipped schedules are program files
release_zip(z, {"README.md": b"x"})
try:
    U.verify(z); raise SystemExit("zip without the game accepted")
except U.UpdateError:
    pass
man = {n: hashlib.sha256(d).hexdigest() for n, d in new.items()}
man["MVP05.exe"] = "0" * 64
with zipfile.ZipFile(z, "w") as zz:
    for n, d in new.items():
        zz.writestr(n, d)
    zz.writestr(U.MANIFEST, json.dumps(man))
try:
    U.verify(z); raise SystemExit("damaged file accepted")
except U.UpdateError as e:
    assert "damaged" in str(e)

# the running Launcher: renamed out of the way, its name back on a failed write
U.own_exe = lambda: os.path.join(root, U.LAUNCHER_EXE)
release_zip(z, new)
U.apply(root, U.verify(z), "Beta 1")
assert get(root, U.LAUNCHER_EXE) == b"new launcher" and get(root, U.LAUNCHER_EXE + ".old") == b"old launcher"
U.tidy(root)
assert not os.path.exists(os.path.join(root, U.LAUNCHER_EXE + ".old"))

# check(): GitHub's answer read
class R(io.BytesIO):
    headers = {}
    def __enter__(self): return self
    def __exit__(self, *a): pass
U._get = lambda url, timeout=15: R(json.dumps([
    {"name": "MVP05-Plus Beta 4", "tag_name": "beta-4", "draft": True, "assets": []},
    {"name": "MVP05-Plus Beta 3", "tag_name": "beta-3", "prerelease": True, "body": "## New\n- x", "html_url": "h",
     "assets": [{"name": "MVP05-Plus-Beta-3.zip", "browser_download_url": "u", "size": 5}]},
    {"name": "MVP05-Plus Beta 1", "tag_name": "beta-1", "assets": []}]).encode())
i = U.check("Beta 2")
assert i["version"] == "Beta 3" and i["url"] == "u" and i["name"] == "MVP05-Plus-Beta-3.zip", i
assert U.check("Beta 3") is None
print("updater tests passed")
