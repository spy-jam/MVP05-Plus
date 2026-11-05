"""Reading the three discs' file systems, with nothing but Python.

Xbox:      XDVDFS, in a Redump image (game partition after the video one), an xiso, or an extracted folder.
GameCube:  GCM with its FST (.iso / .gcm); .rvz / .gcz / .ciso / .wia are converted first by DolphinTool.
PS2:       ISO 9660 (.iso); .chd is converted first by chdman.

Each reader gives `files()` (path -> (offset, size), paths lower case with '/') and `read(path)` / `copy(path, dest)`,
so only the files that are asked for are read from a disc.
"""
import os
import shutil
import struct
import subprocess
import tempfile

XBOX_TITLE = 0x45410056   # MVP Baseball 2005 (EA, 0x56)
GC_GAME_ID = b"GV4E69"
PS2_SERIAL = "SLUS_211.35"

SECTOR = 2048
CHUNK = 1 << 20


class DiscError(Exception):
    pass


class Image:
    """A disc image file; subclasses fill self.entries {path: (offset, size)}."""

    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        self.size = os.fstat(self.f.fileno()).st_size
        self.entries = {}

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def at(self, off, n):
        self.f.seek(off)
        b = self.f.read(n)
        if len(b) != n:
            raise DiscError(f"{os.path.basename(self.path)} ends early (wanted {n} bytes at {off:#x}): incomplete image?")
        return b

    def files(self):
        return self.entries

    def find(self, path):
        e = self.entries.get(path.replace("\\", "/").lower().strip("/"))
        if e is None:
            raise DiscError(f"{path} isn't on {os.path.basename(self.path)}")
        return e

    def read(self, path):
        off, n = self.find(path)
        return self.at(off, n)

    def copy(self, path, dest, progress=None):
        off, n = self.find(path)
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        self.f.seek(off)
        left = n
        with open(dest + ".part", "wb") as o:
            while left:
                b = self.f.read(min(CHUNK, left))
                if not b:
                    raise DiscError(f"{os.path.basename(self.path)} ends inside {path}: incomplete image?")
                o.write(b)
                left -= len(b)
                if progress:
                    progress(len(b))
        os.replace(dest + ".part", dest)


# ---------------------------------------------------------------- Xbox (XDVDFS)

XDVDFS_MAGIC = b"MICROSOFT*XBOX*MEDIA"
# where the game partition starts: an xiso, then Redump images of XGD1, XGD2, XGD3 discs
XBOX_PARTITIONS = (0, 0x18300000, 0xFD90000, 0x2080000)


class XboxImage(Image):
    def __init__(self, path):
        super().__init__(path)
        for base in XBOX_PARTITIONS:
            vd = base + 32 * SECTOR
            if vd + SECTOR > self.size:
                continue
            h = self.at(vd, SECTOR)
            if h[:20] == XDVDFS_MAGIC and h[0x7EC:0x800] == XDVDFS_MAGIC:
                self.base = base
                root, rsize = struct.unpack_from("<II", h, 20)
                self._walk(root, rsize, "", set())
                break
        else:
            raise DiscError(f"{os.path.basename(path)} isn't an Xbox disc image (no XDVDFS volume found)")

    def _walk(self, sector, size, prefix, seen):
        if size == 0 or sector in seen:
            return
        seen.add(sector)
        table = self.at(self.base + sector * SECTOR, size)
        todo = [0]
        while todo:
            o = todo.pop()
            if o + 14 > len(table):
                continue
            left, right, start, length, attr, nlen = struct.unpack_from("<HHIIBB", table, o)
            if left == 0xFFFF and right == 0xFFFF:  # padding at a sector's end
                continue
            name = table[o + 14:o + 14 + nlen].decode("latin-1")
            if left:
                todo.append(left * 4)
            if right:
                todo.append(right * 4)
            path = (prefix + name).lower()
            if attr & 0x10:
                self._walk(start, length, path + "/", seen)
            else:
                self.entries[path] = (self.base + start * SECTOR, length)


def xbe_title(xbe):
    if xbe[:4] != b"XBEH":
        raise DiscError("default.xbe isn't an Xbox program")
    base, cert = struct.unpack_from("<I", xbe, 0x104)[0], struct.unpack_from("<I", xbe, 0x118)[0]
    o = cert - base
    title_id = struct.unpack_from("<I", xbe, o + 8)[0]
    name = xbe[o + 12:o + 12 + 80].decode("utf-16le", "replace").split("\0")[0]
    return title_id, name


class XboxFolder:
    """Already extracted files, with default.xbe directly inside the folder."""

    def __init__(self, path):
        self.path = path
        self.entries = {}
        for d, _, fs in os.walk(path):
            for f in fs:
                full = os.path.join(d, f)
                self.entries[os.path.relpath(full, path).replace(os.sep, "/").lower()] = (full, os.path.getsize(full))
        if "default.xbe" not in self.entries:
            raise DiscError(f"there's no default.xbe directly in {path}")

    def files(self):
        return self.entries

    def read(self, p):
        with open(self.entries[p][0], "rb") as f:
            return f.read()

    def copy(self, p, dest, progress=None):
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        shutil.copyfile(self.entries[p][0], dest)
        if progress:
            progress(self.entries[p][1])

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def open_xbox(path):
    d = XboxFolder(path) if os.path.isdir(path) else XboxImage(path)
    try:
        title_id, name = xbe_title(d.read("default.xbe"))
    except KeyError:
        d.close()
        raise DiscError("there's no default.xbe on that disc")
    if title_id != XBOX_TITLE:
        d.close()
        raise DiscError(f"that's {name or 'another game'} ({title_id:08X}), not MVP Baseball 2005 for Xbox")
    return d


# ---------------------------------------------------------------- GameCube (GCM / FST)

class GameCubeImage(Image):
    def __init__(self, path):
        super().__init__(path)
        h = self.at(0, 0x440)
        if struct.unpack_from(">I", h, 0x1C)[0] != 0xC2339F3D:
            raise DiscError(f"{os.path.basename(path)} isn't a GameCube disc image")
        self.game_id = h[:6]
        self.name = h[0x20:0x60].split(b"\0")[0].decode("latin-1")
        fst, fst_size = struct.unpack_from(">II", h, 0x424)
        t = self.at(fst, fst_size)
        count = struct.unpack_from(">I", t, 8)[0]
        names = 12 * count

        def name_at(o):
            return t[names + o:t.index(b"\0", names + o)].decode("latin-1")

        # directories end at their "next" index: a stack of (end, prefix)
        stack = [(count, "")]
        for i in range(1, count):
            while i >= stack[-1][0]:
                stack.pop()
            w, a, b = struct.unpack_from(">III", t, 12 * i)
            nm = name_at(w & 0xFFFFFF)
            if w >> 24:
                stack.append((b, stack[-1][1] + nm.lower() + "/"))
            else:
                self.entries[stack[-1][1] + nm.lower()] = (a, b)


def convert(tool_names, args_for, src, what):
    """A compressed image converted to a plain one in a temporary folder by an outside tool; (path, folder)."""
    tool = next((shutil.which(t) for t in tool_names if shutil.which(t)), None)
    if not tool:
        raise DiscError(f"reading a {os.path.splitext(src)[1]} image needs {tool_names[0]} ({what}); "
                        f"or give the installer a plain .iso")
    tmp = tempfile.mkdtemp(prefix="mvp-installer-")
    out = os.path.join(tmp, "disc.iso")
    r = subprocess.run([tool] + args_for(src, out), capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode or not os.path.exists(out):
        shutil.rmtree(tmp, ignore_errors=True)
        raise DiscError(f"{os.path.basename(tool)} couldn't convert {os.path.basename(src)}:\n{(r.stderr or r.stdout)[-600:]}")
    return out, tmp


class Converted:
    """An image read from a converted copy, which goes when it's closed."""

    def __init__(self, image, tmp):
        self.image, self.tmp = image, tmp

    def __getattr__(self, k):
        return getattr(self.image, k)

    def close(self):
        self.image.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def open_gamecube(path):
    ext = os.path.splitext(path)[1].lower()
    tmp = None
    if ext in (".rvz", ".gcz", ".ciso", ".wia"):
        path, tmp = convert(["DolphinTool", "dolphin-tool"],
                            lambda s, o: ["convert", "-i", s, "-o", o, "-f", "iso"], path, "it comes with Dolphin")
    try:
        d = GameCubeImage(path)
    except Exception:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        raise
    if d.game_id != GC_GAME_ID:
        d.close()
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        raise DiscError(f"that's {d.name or 'another game'} ({d.game_id.decode('latin-1')}), "
                        f"not MVP Baseball 2005 for GameCube ({GC_GAME_ID.decode()})")
    return Converted(d, tmp) if tmp else d


# ---------------------------------------------------------------- PS2 (ISO 9660)

class Iso9660Image(Image):
    def __init__(self, path):
        super().__init__(path)
        pvd = self.at(16 * SECTOR, SECTOR)
        if pvd[1:6] != b"CD001" or pvd[0] != 1:
            raise DiscError(f"{os.path.basename(path)} isn't a PS2 DVD image (no ISO 9660 volume)")
        self._walk(pvd[156:156 + 34], "", set())

    def _walk(self, rec, prefix, seen):
        extent, size = struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0]
        if extent in seen:
            return
        seen.add(extent)
        data = self.at(extent * SECTOR, size)
        o = 0
        while o < len(data):
            n = data[o]
            if n == 0:  # rest of this sector unused
                o = (o // SECTOR + 1) * SECTOR
                continue
            r = data[o:o + n]
            o += n
            nlen = r[32]
            raw = r[33:33 + nlen]
            if raw in (b"\0", b"\1"):
                continue
            name = raw.decode("latin-1").split(";")[0].rstrip(".").lower()
            if r[25] & 2:
                self._walk(r, prefix + name + "/", seen)
            else:
                ext, ln = struct.unpack_from("<I", r, 2)[0], struct.unpack_from("<I", r, 10)[0]
                self.entries[prefix + name] = (ext * SECTOR, ln)


def ps2_serial(cnf):
    for line in cnf.decode("latin-1").splitlines():
        if line.replace(" ", "").upper().startswith("BOOT2="):
            return line.split("\\")[-1].split(";")[0].strip().upper()
    return ""


def open_ps2(path):
    tmp = None
    if os.path.splitext(path)[1].lower() == ".chd":
        path, tmp = convert(["chdman"], lambda s, o: ["extractdvd", "-i", s, "-o", o, "-f"], path,
                            "from MAME's tools")
    try:
        d = Iso9660Image(path)
        serial = ps2_serial(d.read("system.cnf")) if "system.cnf" in d.entries else ""
    except Exception:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        raise
    if serial != PS2_SERIAL:
        d.close()
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        raise DiscError(f"that's {serial or 'not a PS2 game'}, not MVP Baseball 2005 for PS2 ({PS2_SERIAL})")
    return Converted(d, tmp) if tmp else d


# ---------------------------------------------------------------- what the art needs from each

ART_FILES = ["data/frontend/shared.big", "data/frontend/igonly.big"] + \
            [f"data/frontend/load{i}.big" for i in range(8)]
GC_ART_FILES = ART_FILES + ["data/igshapes/igcrsr.gsh"]
PS2_ART_FILES = ART_FILES + ["data/igshapes/igcrsr.ssh"]


def extract(disc, names, dest, upper=False, progress=None):
    """Only these files from the disc, into dest (keeping their folders); upper-case names as the PS2 disc has them."""
    missing = [n for n in names if n not in disc.files()]
    if missing:
        raise DiscError("the disc is missing " + ", ".join(missing) + ": incomplete or modified image?")
    for n in names:
        disc.copy(n, os.path.join(dest, *(n.upper() if upper else n).split("/")), progress)
