"""The Launcher moved around with an Xbox-style controller (XInput: Xbox pads, and others Steam or DS4Windows
present as one), while one of its windows is in front. Nothing is opened: the game still gets every controller.

  D-pad / left stick   up and down: the previous / next control (in a list: the previous / next row)
                       left and right: a list box's or number's value, else the previous / next control
  A                    press the button, tick the box, open a row
  B                    back: closes a dialog (Esc)
  LB / RB              the previous / next tab
  Start                Launch, on the Play tab
In Windows' own message boxes, A is Enter, B is Esc and the d-pad moves between their buttons.
"""
import ctypes
import os
import time

POLL_MS = 33
REPEAT_DELAY, REPEAT_EVERY = 0.40, 0.12  # held direction: first repeat, then every

UP, DOWN, LEFT, RIGHT, START, BACK = 0x0001, 0x0002, 0x0004, 0x0008, 0x0010, 0x0020
LB, RB, A, B = 0x0100, 0x0200, 0x1000, 0x2000
STICK = 16000


class _State(ctypes.Structure):
    _fields_ = [("packet", ctypes.c_uint32), ("buttons", ctypes.c_uint16), ("lt", ctypes.c_uint8),
                ("rt", ctypes.c_uint8), ("lx", ctypes.c_int16), ("ly", ctypes.c_int16), ("rx", ctypes.c_int16),
                ("ry", ctypes.c_int16)]


def _xinput():
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            return getattr(ctypes.windll, name).XInputGetState
        except (OSError, AttributeError):
            pass
    return None


def _ours_in_front():
    """The window in front, if it's one of this process's: (hwnd, is Windows' own dialog)."""
    u = ctypes.windll.user32
    h = u.GetForegroundWindow()
    if not h:
        return None, False
    pid = ctypes.c_ulong()
    u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if pid.value != os.getpid():
        return None, False
    cls = ctypes.create_unicode_buffer(64)
    u.GetClassNameW(h, cls, 64)
    return h, cls.value == "#32770"


def _key(vk, shift=False):
    u = ctypes.windll.user32
    if shift:
        u.keybd_event(0x10, 0, 0, 0)
    u.keybd_event(vk, 0, 0, 0)
    u.keybd_event(vk, 0, 2, 0)
    if shift:
        u.keybd_event(0x10, 0, 2, 0)


def attach(w, tabs, on_start=None):
    """Polls the controllers while the Launcher runs; tabs: the main Notebook; on_start: Launch, when it can."""
    if os.name != "nt":
        return
    get = _xinput()
    if not get:
        return
    import tkinter as tk
    from tkinter import ttk
    st = _State()
    last = {"buttons": 0, "dir": 0, "next": 0.0}

    def widget_class(wd):
        try:
            return wd.winfo_class()
        except tk.TclError:
            return ""

    def move_focus(forward):
        wd = w.focus_get()
        if wd is None:
            wd = tabs
        nxt = wd.tk_focusNext() if forward else wd.tk_focusPrev()
        if nxt is not None:
            nxt.focus_set()

    def change_value(wd, step):
        c = widget_class(wd)
        if c == "TCombobox":
            vals = list(wd.cget("values"))
            if vals:
                i = vals.index(wd.get()) if wd.get() in vals else -1
                wd.set(vals[max(0, min(len(vals) - 1, i + step))])
                wd.event_generate("<<ComboboxSelected>>")
            return True
        if c in ("TSpinbox", "Spinbox"):
            wd.invoke("buttonup" if step > 0 else "buttondown")
            return True
        return False

    def tree_move(wd, step):
        items = []

        def walk(parent):
            for it in wd.get_children(parent):
                items.append(it)
                if wd.item(it, "open"):
                    walk(it)
        walk("")
        if not items:
            return
        sel = wd.selection()
        i = items.index(sel[0]) if sel and sel[0] in items else -1
        it = items[max(0, min(len(items) - 1, i + step))]
        wd.selection_set(it)
        wd.focus(it)
        wd.see(it)

    def direction(d):
        h, native = _ours_in_front()
        if not h:
            return
        if native:
            _key(0x09, shift=d in (UP, LEFT))  # Tab / Shift+Tab between the dialog's buttons
            return
        wd = w.focus_get()
        c = widget_class(wd) if wd else ""
        if c == "Treeview" and d in (UP, DOWN):
            tree_move(wd, -1 if d == UP else 1)
        elif d in (LEFT, RIGHT) and wd is not None and change_value(wd, -1 if d == LEFT else 1):
            pass
        else:
            move_focus(d in (DOWN, RIGHT))

    def press(b):
        h, native = _ours_in_front()
        if not h:
            return
        if native:
            if b == A:
                _key(0x0D)
            elif b == B:
                _key(0x1B)
            return
        wd = w.focus_get()
        c = widget_class(wd) if wd else ""
        if b == A and wd is not None:
            if c in ("TButton", "Button", "TCheckbutton", "Checkbutton", "TRadiobutton"):
                wd.invoke()
            elif c == "Treeview":
                sel = wd.selection()
                if sel and wd.get_children(sel[0]):
                    wd.item(sel[0], open=not wd.item(sel[0], "open"))
                elif sel:
                    wd.event_generate("<Double-1>")
            elif c == "TCombobox":
                change_value(wd, 1)
            elif c == "TNotebook":
                move_focus(True)
        elif b == B:
            top = wd.winfo_toplevel() if wd is not None else w
            if top is not w:
                top.destroy()
        elif b in (LB, RB):
            n = len(tabs.tabs())
            if n:
                i = tabs.index(tabs.select())
                tabs.select((i + (1 if b == RB else -1)) % n)
                tabs.focus_set()
        elif b == START and on_start:
            on_start()

    def poll():
        buttons = 0
        lx = ly = 0
        for port in range(4):
            if get(port, ctypes.byref(st)) == 0:
                buttons |= st.buttons
                if abs(st.lx) > abs(lx):
                    lx = st.lx
                if abs(st.ly) > abs(ly):
                    ly = st.ly
        d = 0
        if buttons & UP or ly > STICK:
            d = UP
        elif buttons & DOWN or ly < -STICK:
            d = DOWN
        elif buttons & LEFT or lx < -STICK:
            d = LEFT
        elif buttons & RIGHT or lx > STICK:
            d = RIGHT
        now = time.monotonic()
        try:
            if d and (d != last["dir"] or now >= last["next"]):
                direction(d)
                last["next"] = now + (REPEAT_DELAY if d != last["dir"] else REPEAT_EVERY)
            last["dir"] = d
            pressed = buttons & ~last["buttons"]
            for b in (A, B, LB, RB, START):
                if pressed & b:
                    press(b)
        except tk.TclError:
            pass  # a window closed under it
        last["buttons"] = buttons
        try:
            w.after(POLL_MS, poll)
        except tk.TclError:
            pass

    w.after(POLL_MS, poll)
