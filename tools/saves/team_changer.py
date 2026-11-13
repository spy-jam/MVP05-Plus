"""Team Changer, from the Launcher: the organization a dynasty's player controls, changed in the running MVP05.exe.

A port of tywiggins' MVP2005TeamChanger (2006, for the PC game). It finds the loaded database file "attrib.dat" in
the game's memory (its name, its 0, then the database's 0xBB filler) and the controlled organization's id
0xC5B1C bytes on: on the PC. The Xbox game lays the database out the same, with its memory blocks 16 bytes
further on past the database files, so here it's 0xC5B2C (checked in memory captures; the Tools menu in the game
does the same, src/common/dbtools.cpp). Windows only.
"""
import os
import struct

import standings_patcher as P

ORGS = ("Angels", "Astros", "Athletics", "Blue Jays", "Braves", "Brewers", "Cardinals", "Cubs", "Devil Rays",
        "Diamondbacks", "Dodgers", "Giants", "Indians", "Mariners", "Marlins", "Mets", "Nationals", "Orioles",
        "Padres", "Phillies", "Pirates", "Rangers", "Reds", "Red Sox", "Rockies", "Royals", "Tigers", "Twins",
        "White Sox", "Yankees")
IDS = (0xb87d5f5, 0xb87f3f1, 0xb880fe0, 0xb8826fa, 0xb87d6c6, 0xb880867, 0xb882338, 0xb87dd93, 0x59755b, 0xb87d681,
       0x597452, 0x59753e, 0xb87de39, 0xb88215e, 0xb87eaf8, 0xb880a79, 0xb8831f0, 0xb87d894, 0x59753c, 0xb881506,
       0xb881532, 0xb8825b6, 0xb87dddf, 0xb87da69, 0xb87dea3, 0x597433, 0xb87e1a2, 0xb880869, 0xb87db72, 0xb880a85)
NAME = b"attrib.dat\x00\xbb"
SPOT = 0xC5B1C + 0x10


class TeamError(Exception):
    pass


def find_in(ram):
    """(offset of the controlled organization's id in ram, its index in ORGS) or None: pure, for tests."""
    i = ram.find(NAME)
    while i >= 0:
        o = i + SPOT
        if o + 4 <= len(ram):
            org = struct.unpack_from("<I", ram, o)[0]
            if org in IDS:
                return o, IDS.index(org)
        i = ram.find(NAME, i + 1)
    return None


def find():
    """(process handle, host address, index in ORGS) in the running game."""
    if os.name != "nt":
        raise TeamError("changing the running game works on Windows only")
    import ctypes
    k = ctypes.windll.kernel32
    P._rpm_types(k)
    pid = P.find_dolphin_pid()
    if not pid:
        raise TeamError("MVP05.exe isn't running: start it and load your dynasty or owner mode save first")
    h = k.OpenProcess(0x0030 | 0x0400, False, pid)
    if not h:
        raise TeamError("can't open MVP05.exe's memory (try running the Launcher as administrator)")
    for base, size in P.find_all_gc_ram(h):
        got = find_in(P.read_full_ram(h, base, size))
        if got:
            return h, base + got[0], got[1]
    k.CloseHandle(h)
    raise TeamError("no dynasty or owner mode save found in the game: load one first")


def change(h, addr, org):
    """Control given to ORGS[org], after checking the spot still holds an organization's id."""
    import ctypes
    try:
        now = struct.unpack("<I", P.read_small(h, addr, 4))[0]
        if now not in IDS:
            raise TeamError("the dynasty changed since it was found: look again")
        if not P.write_bytes(h, addr, struct.pack("<I", IDS[org])):
            raise TeamError("couldn't write to the game's memory")
    finally:
        ctypes.windll.kernel32.CloseHandle(h)
