"""Watches what Windows draws over the game's window (dev tooling; Windows only).

    python kotor/tools/py/pointer_probe.py EXE SETTINGS INPUT_SCRIPT SECONDS [game args...]

Starts the game in a real, visible window, parks the real pointer inside it and, every 30 ms, asks Windows which
cursor is in force there. A line prints whenever the picture changes: the window's size, place and style, whether
the OS cursor is shown (one of the system's stock cursors) or hidden (the game hides it: it draws its own), and the
pointer's place. A script of `FRAME gfx mode windowed|borderless|fullscreen` lines in INPUT_SCRIPT switches the
window's mode while it runs; `ACTIONS=9:min,10.5:restore,12:other,13.5:back` adds minimise, restore, and focus
moves to the shell and back at those seconds. `PARK=X,Y` is where the pointer sits (default 600,400: inside the
window in every mode, because SDL moves the pointer to the same window-relative place when the window changes).
`WIGGLE=S` moves it a pixel every S seconds (default never), `STEP=S` is the sampling period.

What it found (docs/mechanics/graphics.md, "The OS pointer"): the front end left the arrow showing in every window
mode; with the pointer hidden from the first display::apply it stays hidden through every mode switch, minimise
and restore. The real game is never touched: use your own settings copy (--settings) and saves directory.
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

user32 = ctypes.windll.user32
ctypes.windll.shcore.SetProcessDpiAwareness(2)   # real pixels, as the game asks of SDL


class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD), ("hCursor", wt.HANDLE), ("ptScreenPos", wt.POINT)]


user32.LoadCursorW.restype = wt.HANDLE
user32.LoadCursorW.argtypes = [wt.HANDLE, ctypes.c_void_p]
# SetCursor(NULL) leaves the system with a cursor handle of its own, so "hidden" is "not one of the stock cursors".
STOCK = {user32.LoadCursorW(None, i) for i in list(range(32512, 32517)) + list(range(32640, 32652))} - {None, 0}


def find_window(pid):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def visit(hwnd, _):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(visit, 0)
    return found[0] if found else None


def thread_cursor(hwnd):
    """The cursor the window's own thread has set: attach to its input queue to read it."""
    pid = wt.DWORD()
    tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    me = ctypes.windll.kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(me, tid, True)
    c = user32.GetCursor()
    user32.AttachThreadInput(me, tid, False)
    return c or 0


def describe(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    style = user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
    kind = "popup" if style & 0x80000000 else ("caption" if style & 0x00C00000 == 0x00C00000 else "other")
    frame = "thickframe" if style & 0x00040000 else "noframe"
    focus = "fg" if user32.GetForegroundWindow() == hwnd else "bg"
    iconic = " ICONIC" if user32.IsIconic(hwnd) else ""
    return f"{r.right - r.left}x{r.bottom - r.top}@{r.left},{r.top} {kind} {frame} {focus}{iconic}"


def main():
    exe, settings, script, seconds = sys.argv[1:5]
    args = [os.path.abspath(exe), "--settings", settings, "--input", script] + sys.argv[5:]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    hwnd = None
    start = time.time()
    while time.time() - start < 30 and hwnd is None:
        hwnd = find_window(proc.pid)
        time.sleep(0.2)
    if hwnd is None:
        print("no window")
        proc.kill()
        return 1
    px, py = map(int, os.environ.get("PARK", "600,400").split(","))
    wiggle = float(os.environ.get("WIGGLE", "1000000"))
    step = float(os.environ.get("STEP", "0.03"))
    actions = sorted((float(a.split(":")[0]), a.split(":")[1]) for a in os.environ.get("ACTIONS", "").split(",") if a)
    print(f"pointer parked at {px},{py}")
    t0 = time.time()
    tick, last = -1, None
    while time.time() - t0 < float(seconds) and proc.poll() is None:
        hwnd = find_window(proc.pid) or hwnd
        while actions and time.time() - t0 >= actions[0][0]:
            _, act = actions.pop(0)
            if act == "min":
                user32.ShowWindow(hwnd, 6)
            elif act == "restore":
                user32.ShowWindow(hwnd, 9)
                user32.SwitchToThisWindow(hwnd, True)
            elif act == "other":
                user32.SwitchToThisWindow(user32.GetShellWindow(), True)
            elif act == "back":
                user32.SwitchToThisWindow(hwnd, True)
            print(f"{time.time() - t0:6.2f}s -- {act}")
        if int((time.time() - t0) / wiggle) != tick:
            tick = int((time.time() - t0) / wiggle)
            user32.SetCursorPos(px + tick % 2, py)
        time.sleep(step)
        cursor = thread_cursor(hwnd)
        where = wt.POINT()
        user32.GetCursorPos(ctypes.byref(where))
        state = (f"ptr={where.x},{where.y}", describe(hwnd), "OS cursor " + ("SHOWN" if cursor in STOCK else "hidden"))
        if state != last:
            print(f"{time.time() - t0:6.2f}s", *state)
            last = state
    proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
