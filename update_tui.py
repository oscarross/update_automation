#!/usr/bin/env python3
"""Terminal UI for managing system updates (macOS, App Store, Homebrew, RubyGems).

Pure standard library (curses) - no dependencies.

Keys:
  ↑/↓ j/k   move          space  toggle group     a / n  select all / none
  Enter / r run selected  c      list outdated    x      stop running update
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
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


@dataclass
class Step:
    label: str
    cmd: list
    sudo: bool = False

    @property
    def available(self):
        return shutil.which(self.cmd[0]) is not None


@dataclass
class Group:
    name: str
    desc: str
    steps: list
    outdated: list  # commands that list outdated items
    selected: bool = False
    status: str = "idle"  # idle | running | ok | failed | skipped | missing
    seconds: float = 0.0
    current: int = -1  # index of running step
    done: int = 0  # steps finished in the current run

    @property
    def runnable(self):
        return [s for s in self.steps if s.available]

    @property
    def available(self):
        return bool(self.runnable)

    def __post_init__(self):
        if not self.available:
            self.status = "missing"


def build_groups():
    return [
        Group("Mac", "App Store + macOS system updates", [
            Step("mas upgrade", ["mas", "upgrade"]),
            Step("softwareupdate", ["softwareupdate", "--install", "--all"], sudo=True),
        ], [["mas", "outdated"], ["softwareupdate", "--list"]]),
        Group("Brew", "Homebrew formulae and casks", [
            Step("update", ["brew", "update"]),
            Step("upgrade", ["brew", "upgrade"]),
            Step("cask upgrade", ["brew", "upgrade", "--cask", "--greedy"]),
            Step("cleanup", ["brew", "cleanup"]),
        ], [["brew", "outdated"], ["brew", "outdated", "--cask", "--greedy"]]),
        Group("Gem", "RubyGems system and gems", [
            Step("update --system", ["gem", "update", "--system"]),
            Step("update", ["gem", "update"]),
            Step("cleanup", ["gem", "cleanup"]),
        ], [["gem", "outdated"]]),
    ]


def demo_groups():
    """Fake groups for trying out the UI without touching the system."""
    def step(label, secs, fail=False):
        script = f"for i in 1 2 3; do echo '{label}: line '$i; sleep {secs}; done" + (
            "; echo boom >&2; exit 1" if fail else "")
        return Step(label, ["sh", "-c", script])
    echo = [["echo", "demo-pkg 1.0 -> 2.0"]]
    return [
        Group("Mac", "Demo group (ok)", [step("one", 0.2), step("two", 0.2)], echo),
        Group("Brew", "Demo group (ok, 4 steps)",
              [step("update", 0.15), step("upgrade", 0.2), step("cask", 0.15), step("cleanup", 0.1)], echo),
        Group("Gem", "Demo group (fails)", [step("update", 0.2), step("broken", 0.2, fail=True)], echo),
    ]


class Runner:
    """Runs commands in a background thread, streaming output lines to a queue."""

    def __init__(self, log):
        self.log = log
        self.proc = None
        self.thread = None
        self.stop_flag = False
        self.sudo_ok = True

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def _stream(self, cmd):
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, text=True, errors="replace",
                                     start_new_session=True)
        for line in self.proc.stdout:
            self.log.put(line.rstrip("\r\n").split("\r")[-1].expandtabs(4))
        return self.proc.wait()

    def run(self, groups):
        def work():
            for g in groups:
                g.status, g.seconds, g.done, g.current = "idle", 0.0, 0, -1
            for g in groups:
                if self.stop_flag:
                    g.status = "skipped"
                    continue
                g.status = "running"
                start = time.time()
                self.log.put(f"\x00head━━ {g.name} ━━")
                ok = True
                for i, s in enumerate(g.steps):
                    if not s.available:
                        self.log.put(f"\x00warn⚠ {s.cmd[0]} not installed, skipping {s.label}")
                        g.done += 1
                        continue
                    if s.sudo and not self.sudo_ok:
                        self.log.put(f"\x00warn⚠ no sudo access, skipping {s.label}")
                        g.done += 1
                        continue
                    if self.stop_flag:
                        ok = False
                        break
                    g.current = i
                    self.log.put(f"\x00step» {s.label}")
                    try:
                        rc = self._stream((SUDO if s.sudo else []) + s.cmd)
                    except OSError as e:
                        self.log.put(f"\x00err✖ {e}")
                        rc = 1
                    g.done += 1
                    if rc != 0:
                        self.log.put(f"\x00err✖ {s.label} exited with code {rc}")
                        ok = False
                        break
                g.current = -1
                g.seconds = time.time() - start
                g.status = "ok" if ok else ("skipped" if self.stop_flag else "failed")
            self.log.put("\x00head• Stopped" if self.stop_flag else "\x00ok✔ All done")
        self.stop_flag = False
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def check(self, group):
        def work():
            self.log.put(f"\x00head━━ Outdated: {group.name} ━━")
            for cmd in group.outdated:
                if shutil.which(cmd[0]) is None:
                    continue
                self.log.put(f"\x00step$ {' '.join(cmd)}")
                try:
                    self._stream(cmd)
                except OSError as e:
                    self.log.put(f"\x00err✖ {e}")
            self.log.put("\x00ok✔ Check finished")
        self.stop_flag = False
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag = True
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, 15)
            except OSError:  # already gone, or a root-owned process we may not signal
                pass


# colour pair ids
C_OK, C_ERR, C_WARN, C_ACCENT, C_TITLE, C_KEY = range(1, 7)
BADGE = {  # status -> (symbol, colour)
    "idle": ("○", 0), "running": ("●", C_WARN), "ok": ("✔", C_OK),
    "failed": ("✖", C_ERR), "skipped": ("–", 0), "missing": ("∅", C_ERR),
}
LOG_STYLES = {"head": (C_ACCENT, curses.A_BOLD), "step": (C_WARN, 0), "err": (C_ERR, curses.A_BOLD),
              "warn": (C_WARN, 0), "ok": (C_OK, curses.A_BOLD)}


class App:
    def __init__(self, scr, groups):
        self.scr = scr
        self.groups = groups
        self.cur = 0
        self.log_q = queue.Queue()
        self.lines = []  # (text, (colour, attr))
        self.scroll = 0  # lines up from the bottom
        self.runner = Runner(self.log_q)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        for pair, fg, bg in ((C_OK, curses.COLOR_GREEN, -1), (C_ERR, curses.COLOR_RED, -1),
                             (C_WARN, curses.COLOR_YELLOW, -1), (C_ACCENT, curses.COLOR_CYAN, -1),
                             (C_TITLE, curses.COLOR_BLACK, curses.COLOR_CYAN),
                             (C_KEY, curses.COLOR_BLACK, curses.COLOR_WHITE)):
            curses.init_pair(pair, fg, bg)
        scr.timeout(100)

    def col(self, c, extra=0):
        return (curses.color_pair(c) if c else 0) | extra

    def drain(self):
        while True:
            try:
                msg = self.log_q.get_nowait()
            except queue.Empty:
                return
            style = (0, 0)
            if msg.startswith("\x00"):
                tag = next(t for t in LOG_STYLES if msg[1:].startswith(t))
                msg, style = msg[1 + len(tag):], LOG_STYLES[tag]
            self.lines.append((msg, style))
            del self.lines[:-5000]

    def put(self, y, x, text, attr=0):
        h, w = self.scr.getmaxyx()
        if 0 <= y < h and 0 <= x < w - 1:
            try:
                self.scr.addnstr(y, x, text, w - x - 1, attr)
            except curses.error:
                pass

    def box(self, y, x, bh, bw, title="", attr=0):
        attr = attr or self.col(C_ACCENT, curses.A_DIM)
        self.put(y, x, "╭" + "─" * (bw - 2) + "╮", attr)
        for r in range(1, bh - 1):
            self.put(y + r, x, "│", attr)
            self.put(y + r, x + bw - 1, "│", attr)
        self.put(y + bh - 1, x, "╰" + "─" * (bw - 2) + "╯", attr)
        if title:
            self.put(y, x + 2, f" {title} ", self.col(C_ACCENT, curses.A_BOLD))

    def progress(self):
        sel = [g for g in self.groups if g.selected and g.available] or \
              [g for g in self.groups if g.status != "missing"]
        total = sum(len(g.runnable) for g in sel) or 1
        done = sum(min(g.done, len(g.runnable)) for g in sel)
        return done, total

    def draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        if h < 14 or w < 50:
            self.put(0, 0, "Terminal too small (min 50x14)", self.col(C_ERR))
            scr.refresh()
            return
        tick = int(time.time() * 10)
        spin = SPINNER[tick % len(SPINNER)]

        # banner
        self.put(0, 0, " ⟳  Update Manager".ljust(w - 1), self.col(C_TITLE, curses.A_BOLD))
        right = "demo mode " if "--demo" in sys.argv else ""
        self.put(0, w - 1 - len(right), right, self.col(C_TITLE))

        # groups panel
        ph = len(self.groups) * 3 + 2
        self.box(2, 1, ph, w - 2, "Updates")
        for i, g in enumerate(self.groups):
            y = 3 + i * 3
            focus = i == self.cur
            sym, colour = BADGE[g.status]
            if g.status == "running":
                sym = spin
            if focus:
                self.put(y, 2, "▌", self.col(C_ACCENT, curses.A_BOLD))
                self.put(y + 1, 2, "▌", self.col(C_ACCENT, curses.A_BOLD))
            box = "◼" if g.selected else "◻"
            dim = curses.A_DIM if not g.available else 0
            self.put(y, 4, box, self.col(C_OK if g.selected else 0, dim))
            self.put(y, 6, g.name, curses.A_BOLD | dim | (curses.A_UNDERLINE if focus else 0))
            self.put(y, 14, g.desc, curses.A_DIM)
            status = g.status if g.status != "running" else \
                f"step {g.done + 1}/{len(g.runnable)}"
            dur = f"  {g.seconds:.0f}s" if g.seconds else ""
            label = f"{sym} {status}{dur}"
            self.put(y, w - 3 - len(label), label, self.col(colour, curses.A_BOLD))
            # step chips
            x = 6
            for j, s in enumerate(g.steps):
                if not s.available:
                    chip, attr = f"∅ {s.label}", self.col(C_ERR, curses.A_DIM)
                elif g.status == "running" and j == g.current:
                    chip, attr = f"{spin} {s.label}", self.col(C_WARN, curses.A_BOLD)
                elif g.status in ("running", "ok", "failed") and j < g.done:
                    chip, attr = f"✔ {s.label}", self.col(C_OK)
                else:
                    chip, attr = f"· {s.label}", curses.A_DIM
                self.put(y + 1, x, chip, attr)
                x += len(chip) + 3

        # progress bar
        py = 3 + ph - 1
        done, total = self.progress()
        bw = max(10, w - 18)
        filled = int(bw * done / total)
        self.put(py, 2, "━" * filled, self.col(C_OK, curses.A_BOLD))
        self.put(py, 2 + filled, "━" * (bw - filled), curses.A_DIM)
        self.put(py, 4 + bw, f"{done}/{total} steps")

        # log panel
        ly = py + 1
        lh = h - ly - 2
        if lh >= 3:
            self.box(ly, 1, lh, w - 2, "Log" + (f"  ↑{self.scroll}" if self.scroll else ""))
            avail = lh - 2
            end = len(self.lines) - self.scroll
            for k, (text, (c, a)) in enumerate(self.lines[max(0, end - avail):end]):
                self.put(ly + 1 + k, 3, text, self.col(c, a))
            if not self.lines:
                self.put(ly + 1, 3, "Select groups with space, then press Enter.", curses.A_DIM)

        # footer
        x = 1
        state = ("RUNNING", C_WARN) if self.runner.busy else ("READY", C_OK)
        self.put(h - 1, x, f" {state[0]} ", self.col(state[1], curses.A_REVERSE | curses.A_BOLD))
        x += len(state[0]) + 4
        for key, text in (("space", "toggle"), ("a/n", "all/none"), ("⏎", "run"), ("c", "outdated"),
                          ("x", "stop"), ("q", "quit")):
            self.put(h - 1, x, f" {key} ", self.col(C_KEY, curses.A_BOLD))
            self.put(h - 1, x + len(key) + 2, f" {text}", curses.A_DIM)
            x += len(key) + len(text) + 5
        scr.refresh()

    def run_selected(self):
        todo = [g for g in self.groups if g.selected and g.available]
        if self.runner.busy or not todo:
            return
        if SUDO and any(s.sudo and s.available for g in todo for s in g.steps):
            curses.def_prog_mode()
            curses.endwin()
            print("sudo is needed for the macOS system update (Ctrl+C or no access = skip it):")
            try:
                self.runner.sudo_ok = subprocess.call(["sudo", "-v"]) == 0
            except KeyboardInterrupt:
                self.runner.sudo_ok = False
            curses.reset_prog_mode()
            self.scr.refresh()
        self.lines.clear()
        self.scroll = 0
        self.runner.run(todo)

    def loop(self):
        while True:
            self.drain()
            self.draw()
            k = self.scr.getch()
            n = len(self.groups)
            if k in (ord("q"), 27):
                if self.runner.busy:
                    self.runner.stop()
                return
            elif k in (curses.KEY_DOWN, ord("j")):
                self.cur = (self.cur + 1) % n
            elif k in (curses.KEY_UP, ord("k")):
                self.cur = (self.cur - 1) % n
            elif k == ord(" "):
                g = self.groups[self.cur]
                if g.available:
                    g.selected = not g.selected
            elif k == ord("a"):
                for g in self.groups:
                    g.selected = g.available
            elif k == ord("n"):
                for g in self.groups:
                    g.selected = False
            elif k in (10, 13, ord("r"), curses.KEY_ENTER):
                self.run_selected()
            elif k == ord("c"):
                g = self.groups[self.cur]
                if not self.runner.busy and g.available:
                    self.lines.clear()
                    self.runner.check(g)
            elif k == ord("x"):
                self.runner.stop()
            elif k == curses.KEY_PPAGE:
                self.scroll = min(self.scroll + 10, max(0, len(self.lines) - 1))
            elif k == curses.KEY_NPAGE:
                self.scroll = max(self.scroll - 10, 0)


def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return
    groups = demo_groups() if "--demo" in sys.argv else build_groups()
    curses.wrapper(lambda scr: App(scr, groups).loop())


if __name__ == "__main__":
    main()
