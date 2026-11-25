# A console that presses Ctrl-Break, for the cases of std's stop (cases/Stop), on Windows only:
# `python console_break.py WAITER PLAIN`, the paths of the two programs it runs.
#
# Each program runs in a process group of its own (CREATE_NEW_PROCESS_GROUP), on this process's
# console, so that GenerateConsoleCtrlEvent's Ctrl-Break reaches it and nothing else: not this
# process, nor what ran it. Ctrl-C can't be aimed at one group, and is off in a new one, so
# Ctrl-Break, which goes the same way in a program, stands for both. Whenever a program prints
# `ready`, a Ctrl-Break is sent to it. Each line it prints is printed here, indented, and then
# how it ended: its exit code, or Windows' own handler's 0xC000013A, STATUS_CONTROL_C_EXIT.
#
# Without a console (a run from a service), it makes one, hidden, for the programs to share.
# A program that prints nothing for 30 seconds is ended, and said to have timed out.

import ctypes
import os
import queue
import signal
import subprocess
import sys
import threading

STATUS_CONTROL_C_EXIT = 0xC000013A


def ensure_console():
    kernel32 = ctypes.windll.kernel32
    ids = (ctypes.c_uint32 * 1)()
    if kernel32.GetConsoleProcessList(ids, 1) != 0:
        return
    kernel32.AllocConsole()
    window = kernel32.GetConsoleWindow()
    if window:
        ctypes.windll.user32.ShowWindow(window, 0)


# A line of standard output, ended by a line feed alone, as the case expects it.
def say(text):
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def read_lines(stream, lines):
    for raw in stream:
        lines.put(raw.decode("utf-8", "replace").rstrip("\r\n"))
    lines.put(None)


def run(name, argv):
    say(name + ":")
    child = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    lines = queue.Queue()
    threading.Thread(target=read_lines, args=(child.stdout, lines), daemon=True).start()
    while True:
        try:
            line = lines.get(timeout=30)
        except queue.Empty:
            child.kill()
            say("  timed out")
            break
        if line is None:
            break
        say("  " + line)
        if line == "ready":
            os.kill(child.pid, signal.CTRL_BREAK_EVENT)
    try:
        code = child.wait(timeout=30) & 0xFFFFFFFF
    except subprocess.TimeoutExpired:
        child.kill()
        code = child.wait()
        say("  did not end")
    if code == STATUS_CONTROL_C_EXIT:
        say(name + ": ended by Ctrl-Break (0xC000013A)")
    else:
        say(name + ": exit code " + str(code))


if __name__ == "__main__":
    ensure_console()
    waiter, plain = sys.argv[1], sys.argv[2]
    run("plain", [plain])
    run("once", [waiter, "once"])
    run("twice", [waiter, "twice"])
    run("tasks", [waiter, "tasks"])
