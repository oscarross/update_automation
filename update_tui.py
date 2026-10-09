#!/usr/bin/env python3
"""Terminal UI for managing system updates (macOS, App Store, Homebrew, RubyGems).

Pure standard library (curses) - no dependencies.

Keys:
  ↑/↓ j/k   move          space  toggle task      a / n  select all / none
  Enter / r run selected  c      check outdated   x      stop running task
  PgUp/PgDn scroll log    q      quit
"""
import curses
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

SUDO = [] if os.geteuid() == 0 else ["sudo"]


@dataclass
class Task:
    group: str
    label: str
    cmd: list
    binary: str
    check: list = None  # command listing outdated items
    sudo: bool = False
    selected: bool = False
    status: str = "idle"  # idle | running | ok | failed | skipped | missing
    seconds: float = 0.0
    available: bool = field(init=False, default=True)

    def __post_init__(self):
        self.available = shutil.which(self.binary) is not None
        if not self.available:
            self.status = "missing"


def build_tasks():
    return [
        Task("Mac", "App Store upgrade (mas)", ["mas", "upgrade"], "mas", ["mas", "outdated"]),
        Task("Mac", "macOS softwareupdate", ["softwareupdate", "--install", "--all"],
             "softwareupdate", ["softwareupdate", "--list"], sudo=True),
        Task("Brew", "brew update", ["brew", "update"], "brew"),
        Task("Brew", "brew upgrade", ["brew", "upgrade"], "brew", ["brew", "outdated"]),
        Task("Brew", "brew upgrade --cask --greedy", ["brew", "upgrade", "--cask", "--greedy"],
             "brew", ["brew", "outdated", "--cask", "--greedy"]),
        Task("Brew", "brew cleanup", ["brew", "cleanup"], "brew"),
        Task("Gem", "gem update --system", ["gem", "update", "--system"], "gem"),
        Task("Gem", "gem update", ["gem", "update"], "gem", ["gem", "outdated"]),
        Task("Gem", "gem cleanup", ["gem", "cleanup"], "gem"),
    ]


def demo_tasks():
    """Fake tasks for trying out the UI without touching the system."""
    def t(group, label, secs, fail=False):
        script = f"for i in 1 2 3; do echo '{label}: step '$i; sleep {secs}; done" + (
            "; echo boom >&2; exit 1" if fail else "")
        return Task(group, label, ["sh", "-c", script], "sh", ["echo", "demo-pkg 1.0 -> 2.0"])
    return [t("Mac", "demo mas", 0.3), t("Brew", "demo brew upgrade", 0.4),
            t("Brew", "demo failing task", 0.2, fail=True), t("Gem", "demo gem update", 0.3)]


class Runner:
    """Runs commands in a background thread, streaming output lines to a queue."""

    def __init__(self, log):
        self.log = log
        self.proc = None
        self.thread = None
        self.stop_flag = False

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def _stream(self, cmd):
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, text=True, errors="replace",
                                     start_new_session=True)
        for line in self.proc.stdout:
            self.log.put(line.rstrip("\n"))
        return self.proc.wait()

    def run(self, tasks):
        def work():
            for t in tasks:
                if self.stop_flag:
                    t.status = "skipped"
                    continue
                t.status = "running"
                start = time.time()
                self.log.put(f"\x00head▶ {t.label}")
                try:
                    cmd = (SUDO if t.sudo else []) + t.cmd
                    rc = self._stream(cmd)
                    t.status = "ok" if rc == 0 else "failed"
                    if rc != 0:
                        self.log.put(f"\x00err✖ exit code {rc}")
                except OSError as e:
                    t.status = "failed"
                    self.log.put(f"\x00err✖ {e}")
                t.seconds = time.time() - start
            self.log.put("\x00head■ Done" if not self.stop_flag else "\x00err■ Stopped")
        self.stop_flag = False
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def check(self, task):
        def work():
            self.log.put(f"\x00head? Outdated: {task.label}")
            try:
                rc = self._stream(task.check)
                if rc == 0:
                    self.log.put("(nothing printed above = up to date)")
            except OSError as e:
                self.log.put(f"\x00err✖ {e}")
        self.stop_flag = False
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag = True
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, 15)
            except ProcessLookupError:
                pass


ICONS = {"idle": " ", "running": "…", "ok": "✔", "failed": "✖", "skipped": "-", "missing": "∅"}


class App:
    def __init__(self, scr, tasks):
        self.scr = scr
        self.tasks = tasks
        self.cur = 0
        self.log_q = queue.Queue()
        self.lines = []  # (text, style)
        self.scroll = 0  # lines up from the bottom
        self.runner = Runner(self.log_q)
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        for i, c in enumerate((curses.COLOR_GREEN, curses.COLOR_RED, curses.COLOR_YELLOW,
                               curses.COLOR_CYAN), 1):
            curses.init_pair(i, c, -1)
        scr.timeout(100)

    def drain(self):
        while True:
            try:
                msg = self.log_q.get_nowait()
            except queue.Empty:
                return
            style = 0
            if msg.startswith("\x00head"):
                msg, style = msg[5:], curses.color_pair(4) | curses.A_BOLD
            elif msg.startswith("\x00err"):
                msg, style = msg[4:], curses.color_pair(2) | curses.A_BOLD
            self.lines.append((msg, style))
            del self.lines[:-5000]

    def put(self, y, x, text, attr=0):
        h, w = self.scr.getmaxyx()
        if 0 <= y < h and x < w:
            try:
                self.scr.addnstr(y, x, text, w - x - 1, attr)
            except curses.error:
                pass

    def draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        self.put(0, 0, " Update Manager ".ljust(w - 1), curses.A_REVERSE | curses.A_BOLD)
        row, last_group = 2, None
        for i, t in enumerate(self.tasks):
            if t.group != last_group:
                last_group = t.group
                self.put(row, 1, t.group.upper(), curses.A_BOLD | curses.A_UNDERLINE)
                row += 1
            box = "[x]" if t.selected else "[ ]"
            color = {"ok": 1, "failed": 2, "running": 3, "missing": 2}.get(t.status, 0)
            attr = curses.A_REVERSE if i == self.cur else 0
            dur = f" {t.seconds:.0f}s" if t.seconds else ""
            self.put(row, 2, f" {box} {t.label}".ljust(38), attr | (curses.A_DIM if not t.available else 0))
            self.put(row, 40, f"{ICONS[t.status]} {t.status}{dur}", curses.color_pair(color) if color else 0)
            row += 1
        log_top = row + 1
        self.put(log_top - 1, 0, "─" * (w - 1) + "", curses.A_DIM)
        self.put(log_top - 1, 2, " Log ", curses.A_BOLD)
        avail = h - log_top - 2
        if avail > 0:
            end = len(self.lines) - self.scroll
            for k, (text, style) in enumerate(self.lines[max(0, end - avail):end]):
                self.put(log_top + k, 1, text, style)
        state = "RUNNING" if self.runner.busy else "ready"
        keys = "↑↓ move  space toggle  a/n all/none  ⏎ run  c check  x stop  PgUp/Dn scroll  q quit"
        self.put(h - 1, 0, f" [{state}] {keys}".ljust(w - 1), curses.A_REVERSE)
        scr.refresh()

    def selected(self):
        return [t for t in self.tasks if t.selected and t.available]

    def run_selected(self):
        todo = self.selected()
        if self.runner.busy or not todo:
            return
        if SUDO and any(t.sudo for t in todo):
            curses.def_prog_mode()
            curses.endwin()
            print("sudo password needed for macOS softwareupdate:")
            subprocess.call(["sudo", "-v"])
            curses.reset_prog_mode()
            self.scr.refresh()
        for t in todo:
            t.status, t.seconds = "idle", 0.0
        self.lines.clear()
        self.scroll = 0
        self.runner.run(todo)

    def check_current(self):
        t = self.tasks[self.cur]
        if self.runner.busy or not t.available or not t.check:
            return
        self.runner.check(t)

    def loop(self):
        while True:
            self.drain()
            self.draw()
            k = self.scr.getch()
            n = len(self.tasks)
            if k in (ord("q"), 27):
                if self.runner.busy:
                    self.runner.stop()
                return
            elif k in (curses.KEY_DOWN, ord("j")):
                self.cur = (self.cur + 1) % n
            elif k in (curses.KEY_UP, ord("k")):
                self.cur = (self.cur - 1) % n
            elif k == ord(" "):
                t = self.tasks[self.cur]
                if t.available:
                    t.selected = not t.selected
            elif k == ord("a"):
                for t in self.tasks:
                    t.selected = t.available
            elif k == ord("n"):
                for t in self.tasks:
                    t.selected = False
            elif k in (10, 13, ord("r"), curses.KEY_ENTER):
                self.run_selected()
            elif k == ord("c"):
                self.check_current()
            elif k == ord("x"):
                self.runner.stop()
            elif k == curses.KEY_PPAGE:
                self.scroll = min(self.scroll + 10, max(0, len(self.lines) - 1))
            elif k == curses.KEY_NPAGE:
                self.scroll = max(self.scroll - 10, 0)


def main():
    tasks = demo_tasks() if "--demo" in sys.argv else build_tasks()
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return
    curses.wrapper(lambda scr: App(scr, tasks).loop())


if __name__ == "__main__":
    main()
