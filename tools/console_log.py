#!/usr/bin/env python3
"""console_log.py - the laptop's side of a recording: the host's console, kept whole, with marks.

    python tools/console_log.py [--port COMn | /dev/cu.usbserial-...] [--auto-mark SECONDS] [--logs DIR]

The laptop goes on M2's USB port (the ESP32-DevKitC's own; the FPGA module's is not used). Its
console carries everything a recording needs: every telegram decoded (the trace), a status line
every 10 s with the loss counters, the host's messages and a capture's dump (listener_fw/README.md,
Trace and Capture). trace_decode.py reads the files at home.

Windows 10 or 11, or macOS (Apple silicon too), Python 3.8 or later, pyserial. The files go to
logs/ at the repository's root, or beside this file in kit/3_laptop.

The port is opened with DTR and RTS off and they are never changed: on the DevKitC they reset the
ESP32 or hold it in its bootloader. Some drivers still pulse them while a port opens, so the ESP32
may start anew when the laptop is plugged in; the recording shows it (a start, below).

Threads, so that nothing the screen or the keyboard does can cost a byte:
  reader   only reads the port (921600 baud, a 1 MB driver buffer on Windows) and queues each chunk
           with the PC's time; an error closes the port, and the bridge is looked for again every
           0.5 s by its USB ID (CP2102N or CH9102, as DevKitC boards carry), never by a fixed COM. A
           quiet console is normal (the status line comes every 10 s): it never closes the port
  writer   appends the bytes alone to logs/<date>-<time>-<n>.log, with a .idx of (byte offset, PC
           time in ns) per chunk; flushed every 0.5 s, synced to the disk every 5 s (macOS:
           F_FULLFSYNC) and when the window is closed; a new pair of files on every reconnect; a disk
           error raises the alarm and tries a new pair once a second, the bytes meanwhile lost
  beeper   the beeps, from a queue
  main     reads a copy line by line (console_format.py), shows one status line at most 4 times a
           second, takes the keys
It beeps on: the port lost (again every 10 s until it is back), the ESP32 starting anew, a loss
counter rising in the status line (a packet the ESP32 could not read, a block the FPGA had no room
for, a long telegram's segments not kept, a telegram the console had no time for), no line for
25 s, a key the host did not answer, a disk error. The laptop and its screen are kept awake while
it runs (Windows needs "lid: do nothing" for a closed lid; a MacBook must stay open).

Keys:  m  a mark (one keystroke: a beep and a big number; say what you did with the number into a
          phone memo, or add a note)
       n  a note to the last mark (typed on the status line, Enter ends it, Esc drops it; it goes to
          the .marks.txt, nothing stops while it is typed)
       d  the host dumps what the FPGA captured (after a power-up: the ring's start-up)
       c  the FPGA captures anew, and the host dumps it when full (asks: an undumped start-up
          capture is lost)
       q  quit (asks)
The keys work in a Ukrainian or Russian layout as well (m = ь, n = т, d = в, c = с, q = й, y = н)
and with Caps Lock on. Nothing else is ever sent to the ESP32: 'i' (AUX injection) stays a
terminal's key, outside a recording. --auto-mark N makes a mark every N seconds by itself.
"""
from __future__ import annotations

import argparse
import ctypes
import os
import queue
import shutil
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import console_format as CF                                                # noqa: E402

try:
    import serial                                                          # pyserial
    import serial.tools.list_ports
except ImportError:                                                        # pragma: no cover
    sys.exit("pyserial is needed: pip install pyserial")

BAUD = CF.BAUD
# the DevKitC's USB-UART bridge: CP2102N on most, CH9102 on later ones, CH340 on some copies
BRIDGES = {(0x10C4, 0xEA60): "CP2102N", (0x1A86, 0x55D4): "CH9102", (0x1A86, 0x7523): "CH340"}
# the recording's files: logs/ at the repository's root, or beside this file in kit/3_laptop
LOGS = HERE.parent / "logs" if (HERE.parent / "listener_fw").is_dir() else HERE / "logs"
# the command keys as a Ukrainian or Russian layout gives them (a note's text is kept as typed)
LAYOUT = {"ь": "m", "т": "n", "в": "d", "с": "c", "й": "q", "н": "y"}
TONES = {"port": (300, 600), "restart": (400, 400), "loss": (600, 300), "silent": (800, 200),
         "unanswered": (500, 300), "disk": (300, 800), "mark": (2000, 80)}

if os.name == "nt":                                                        # Windows 10 and 11
    import msvcrt
    import winsound

    def _beep(f, ms):
        try:
            winsound.Beep(f, ms)
        except RuntimeError:
            pass

    def keep_awake(on: bool):
        # the system and the screen: the counters stay in sight
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ((ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED) if on else 0))

    def high_priority():
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00000080)

    _con = None

    def console_setup():
        """QuickEdit off: a click in the window would stop the program until a key is pressed."""
        global _con
        h = ctypes.windll.kernel32.GetStdHandle(-10)
        mode = ctypes.c_uint32()
        if ctypes.windll.kernel32.GetConsoleMode(h, ctypes.byref(mode)):
            _con = mode.value
            ctypes.windll.kernel32.SetConsoleMode(h, (mode.value & ~0x0040) | 0x0080)

    def console_restore():
        if _con is not None:
            ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-10), _con)

    def key():
        if not msvcrt.kbhit():
            return None
        k = msvcrt.getwch()
        if k in ("\x00", "\xe0"):            # an arrow or a function key: its second half, dropped
            msvcrt.getwch()
            return None
        return k

    def has_keys():
        return True

    def sync(f):
        f.flush()
        os.fsync(f.fileno())

    _close_handler = None

    def on_close(fn):
        """The console's close button kills the process when the handler returns, about 5 s
        later at most: fn closes the files first."""
        global _close_handler

        @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
        def handler(ev):
            if ev in (2, 5, 6):               # CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT
                fn()
                return 1
            return 0
        _close_handler = handler              # kept: a collected callback would crash the process
        ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, True)
else:                                                                      # macOS (and Linux)
    import codecs
    import math
    import select
    import struct
    import subprocess
    import tempfile
    import termios
    import tty
    import wave

    _tones = {}

    def _tone(f, ms) -> Path:
        """Each alarm's own tone, as Windows plays it: a sine of f Hz for ms, written once."""
        if (f, ms) not in _tones:
            d = Path(tempfile.gettempdir()) / "console_log_tones"
            d.mkdir(exist_ok=True)
            path = d / f"{f}_{ms}.wav"
            n = 44100 * ms // 1000
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * f * i / 44100)))
                                       for i in range(n)))
            _tones[(f, ms)] = path
        return _tones[(f, ms)]

    def _beep(f, ms):
        # afplay waits for the tone to end; the beeper is a thread of its own
        try:
            subprocess.run(["afplay", str(_tone(f, ms))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            print("\a", end="", flush=True)

    _caff = None

    def keep_awake(on: bool):
        # caffeinate holds off idle, display and disk sleep while this process lives, in a session
        # of its own so that Ctrl+C does not stop it; started again if it has gone
        global _caff
        if on and (_caff is None or _caff.poll() is not None) and sys.platform == "darwin":
            try:
                _caff = subprocess.Popen(["caffeinate", "-dims", "-w", str(os.getpid())], start_new_session=True)
            except OSError:
                _caff = None
        elif not on and _caff is not None:
            _caff.terminate()
            _caff = None

    def high_priority():
        pass                                 # only root may raise a process's priority here

    _tty = None
    _dec = codecs.getincrementaldecoder("utf-8")(errors="ignore")

    def console_setup():
        """Keys one at a time, without Enter and without echo (Ctrl+C still stops)."""
        global _tty
        if sys.stdin.isatty():
            _tty = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        else:
            print("console_log: no keyboard here (not a terminal): no marks; Ctrl+C quits")
        if sys.platform == "darwin":
            print("console_log: MacBook: keep the lid open, a closed lid sleeps it and ends the recording")

    def console_restore():
        if _tty is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _tty)

    def key():
        if _tty is None:
            return None
        fd = sys.stdin.fileno()
        while select.select([fd], [], [], 0)[0]:
            b = os.read(fd, 1)
            if not b:
                return None
            k = _dec.decode(b)               # a letter of a note may take several bytes
            if k:
                return k
        return None

    def has_keys():
        return _tty is not None

    def sync(f):
        f.flush()
        try:
            import fcntl
            fcntl.fcntl(f.fileno(), fcntl.F_FULLFSYNC)   # macOS: through the drive's own cache
        except (ImportError, AttributeError, OSError):
            os.fsync(f.fileno())

    def on_close(fn):
        """The terminal window closed (SIGHUP) or the process asked to end (SIGTERM): the files
        are closed by main's finally."""
        for sig in (signal.SIGHUP, signal.SIGTERM):
            signal.signal(sig, lambda *_: sys.exit(0))

_beeps: queue.Queue = queue.Queue()


def beep(f=1500, ms=120):
    if _beeps.qsize() < 8:
        _beeps.put((f, ms))


def _beeper():
    while True:
        f, ms = _beeps.get()
        _beep(f, ms)


PORT_NOTE = []                             # a hint for the screen while no port is open


def find_port(name: str | None) -> str | None:
    """The DevKitC's bridge by its USB ID; none if there are two (a wrong guess records nothing)."""
    PORT_NOTE.clear()
    if name:
        return name
    cands = [p for p in serial.tools.list_ports.comports() if (p.vid, p.pid) in BRIDGES]
    cu = [p for p in cands if p.device.startswith("/dev/cu.")]
    if cu:                                   # macOS: the call-out node, not the tty twin
        cands = cu
    if len(cands) > 1:
        PORT_NOTE.append("several bridges (" + ", ".join(sorted(p.device for p in cands)) + "): give --port")
        return None
    if not cands:
        PORT_NOTE.append("no ESP32 bridge (CP2102N / CH9102) on USB")
        return None
    return cands[0].device


class Link:
    """The port with its reader thread; reconnects by itself after an error."""

    def __init__(self, port_name, chunks: queue.Queue):
        self.port_name = port_name
        self.chunks = chunks
        self.ser = None
        self.lock = threading.Lock()
        self.alive = threading.Event()
        self.stop = threading.Event()
        self.lost = 0
        self.ever = False
        threading.Thread(target=self._run, daemon=True).start()

    def _open(self):
        dev = find_port(self.port_name)
        if not dev:
            return False
        try:
            s = serial.Serial()
            s.port, s.baudrate, s.timeout = dev, BAUD, 0.02
            s.dtr = s.rts = False                # before open: the DevKitC's reset and boot lines
            s.open()
            if hasattr(s, "set_buffer_size"):
                s.set_buffer_size(rx_size=1 << 20, tx_size=4096)
        except (serial.SerialException, OSError, ValueError):
            return False
        with self.lock:
            self.ser = s
        self.chunks.put(("open", time.time_ns(), dev.encode()))
        self.ever = True
        self.alive.set()
        return True

    def _close(self, why: str):
        with self.lock:
            s, self.ser = self.ser, None
        if s:
            try:
                s.close()
            except Exception:
                pass
        if self.alive.is_set():
            self.lost += 1
            self.chunks.put(("lost", time.time_ns(), why.encode()))
        self.alive.clear()

    def _run(self):
        while not self.stop.is_set():
            if not self.alive.is_set():
                if not self._open():
                    time.sleep(0.5)
                continue
            try:
                b = self.ser.read(65536)
            except (serial.SerialException, OSError, TypeError, AttributeError) as e:
                self._close(f"error {e}")
                continue
            if b:
                self.chunks.put(("data", time.time_ns(), b))
        self._close("stopped")

    def send(self, data: bytes) -> bool:
        with self.lock:
            s = self.ser
        if not s:
            return False
        try:
            s.write(data)
            return True
        except (serial.SerialException, OSError):
            return False


class Writer:
    """The files: the console's bytes alone, and where each chunk came at the PC's time."""

    def __init__(self, logdir: Path, stamp: str):
        self.dir, self.stamp, self.n = logdir, stamp, 0
        self.log = self.idx = None
        self.off = 0
        self.t_flush = self.t_sync = time.monotonic()
        self.error = None

    def segment(self, note: str):
        self.close()
        self.n += 1
        base = self.dir / f"{self.stamp}-{self.n}"
        self.log = open(base.with_suffix(".log"), "ab")
        self.idx = open(base.with_suffix(".idx"), "a", encoding="ascii")
        self.idx.write(f"# {note}\n")
        self.off = 0
        return base

    def put(self, t_ns: int, b: bytes):
        if self.log is None:
            self.segment("start")
        self.idx.write(f"{self.off} {t_ns}\n")
        self.log.write(b)
        self.off += len(b)
        now = time.monotonic()
        if now - self.t_flush > 0.5:
            self.log.flush(); self.idx.flush(); self.t_flush = now
        if now - self.t_sync > 5:
            sync(self.log); sync(self.idx); self.t_sync = now

    def close(self):
        """Never raises: after a disk error the files are let go whatever they say."""
        for f in (self.log, self.idx):
            if f:
                try:
                    sync(f)
                except (OSError, ValueError):
                    pass
                try:
                    f.close()
                except (OSError, ValueError):
                    pass
        self.log = self.idx = None


class Monitor:
    """What the screen shows and what raises an alarm, from the console's bytes (test_console_log.py
    runs it without a port). Times are time.monotonic()'s."""

    SILENT_S = 2.5 * CF.STATUS_S          # the status line comes every 10 s
    ANSWER_S = 1.5                        # the host answers a key within its 20 ms loop

    def __init__(self, alarm):
        self.alarm = alarm                # alarm(kind): a beep, counted
        self.lines = CF.Lines()
        self.tels = self.starts = self.dumps = self.warnings = 0
        self.last_tel = self.last_sound = None
        self.last_warn = ""
        self.status = None                # the last status line's counters (since the ESP32 started)
        self.rose = dict.fromkeys(CF.LOSSES, 0)      # what rose while recording
        self.last_ms = None
        self.t_line = None
        self.t_silent = None              # the silence alarm's last time, while it lasts
        self.open = False                 # silence counts only while the port is open
        self.waiting = None              # (key, deadline): a key sent, its answer not seen yet

    def port(self, kind: str, t: float):
        self.lines = CF.Lines()           # a new stream: a line cut by the old one is dropped here
        self.t_line, self.t_silent = t, None
        self.open = kind == "open"
        if kind == "lost":
            self.alarm("port")

    def feed(self, t: float, data: bytes):
        for _, raw in self.lines.feed(data):
            self.line(t, CF.classify(raw))

    def line(self, t: float, ln: CF.Line):
        first = self.last_ms is None      # no line of the ESP32's yet: its first start, not a restart
        self.t_line, self.t_silent = t, None
        if ln.ms is not None:
            if ln.boot_banner or (self.last_ms is not None and ln.ms + 1000 < self.last_ms):
                self.starts += 1
                self.status = None        # its counters start anew
                if not first:
                    self.alarm("restart")
            self.last_ms = ln.ms
        if ln.kind == "tel":
            self.tels += 1
            self.last_tel = ln.tel
            v = CF.sound_value(ln.tel)
            if v is not None:
                self.last_sound = v
        elif ln.kind == "status":
            s = ln.status
            if self.status is not None:
                up = [k for k in CF.LOSSES if s[k] > self.status[k]]
                for k in up:
                    self.rose[k] += s[k] - self.status[k]
                if up:
                    self.alarm("loss")
            self.status = s
        elif ln.kind == "cap":
            if ln.text.startswith("CAP END"):
                self.dumps += 1
        elif ln.kind == "log":
            if ln.level in ("E", "W"):
                self.warnings += 1
                self.last_warn = f"{ln.level} {ln.tag}: {ln.msg}"
            if ln.tag == "host" and ln.msg.startswith("capture:") and self.waiting:
                self.waiting = None

    def sent(self, k: str, t: float):
        self.waiting = (k, t + self.ANSWER_S)

    def tick(self, t: float):
        if self.waiting and t > self.waiting[1]:
            self.waiting = None
            self.alarm("unanswered")
        if self.open and self.t_line is not None and t - self.t_line > self.SILENT_S and \
                (self.t_silent is None or t - self.t_silent > self.SILENT_S):
            self.t_silent = t
            self.alarm("silent")

    def screen(self, t: float) -> str:
        line = ""
        if self.open and self.t_line is not None and t - self.t_line > self.SILENT_S:
            line += f"NO LINE FOR {t - self.t_line:.0f} s | "
        s = self.status
        line += (f"lost: bad {s['bad']} fpga {s['fpga_lost']} seg {s['seg_dropped']} trace {s['trace_lost']}"
                 f" | gaps {s['gaps']} parity {s['parity_dropped']}" if s else "no status line yet")
        line += f" | tel {self.tels} | starts {self.starts} | W/E {self.warnings} | dumps {self.dumps}"
        if self.last_sound:
            line += f" | {self.last_sound}"
        elif self.last_tel:
            line += f" | {self.last_tel.short()}"
        return line


def arg_range(lo, hi):
    def parse(v):
        n = int(v)
        if not lo <= n <= hi:
            raise argparse.ArgumentTypeError(f"{n} is not within {lo}..{hi}")
        return n
    return parse


def command_key(k):
    return LAYOUT.get(k.lower(), k.lower()) if k else k


def ask(question: str) -> bool:
    print(f"\n{question} y/n ", end="", flush=True)
    if not has_keys():
        return True                           # no keyboard: Ctrl+C quits
    while (c := key()) is None:
        time.sleep(0.02)
    return command_key(c) == "y"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="the DevKitC's port, COMn or /dev/cu.usbserial-... (default: found by its USB ID)")
    ap.add_argument("--auto-mark", type=arg_range(0, 3600), default=0, help="a mark every so many seconds (0: none)")
    ap.add_argument("--logs", default=str(LOGS), help="the folder for the recording's files (default: %(default)s)")
    a = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")  # a console's code page never stops the screen
    sys.setswitchinterval(0.001)              # the reader thread gets the interpreter back within 1 ms

    logdir = Path(a.logs)
    logdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    marks = open(logdir / f"{stamp}.marks.txt", "a", encoding="utf-8")
    chunks: queue.Queue = queue.Queue()
    work: queue.Queue = queue.Queue()
    keep_awake(True); high_priority(); console_setup()
    threading.Thread(target=_beeper, daemon=True).start()
    alarms = dict.fromkeys(TONES, 0)

    def alarm(kind):
        alarms[kind] += 1
        beep(*TONES[kind])

    wr = Writer(logdir, stamp)
    t_err = [0.0]

    def writer():
        while True:
            item = chunks.get()
            if item is None:
                break
            kind, t, b = item
            try:
                if kind == "data":
                    wr.put(t, b)
                    work.put((t, b))
                elif kind == "open":
                    base = wr.segment(f"open {b.decode(errors='replace')} {t}")
                    work.put((kind, base.name))
                else:
                    wr.close()
                    work.put((kind, b.decode(errors="replace")))
            except Exception as e:           # a disk error: the alarm, a new pair once a second
                wr.error = str(e) or type(e).__name__
                alarm("disk")
                wr.close()
                if time.monotonic() - t_err[0] > 1:
                    t_err[0] = time.monotonic()
                    try:
                        wr.segment(f"after a disk error: {e}")
                    except Exception:
                        wr.close()
        wr.close()

    wt = threading.Thread(target=writer, daemon=True)
    wt.start()
    link = Link(a.port, chunks)
    closed = threading.Event()

    def shutdown():
        """The files closed and synced: on quit, and when the window is closed."""
        if closed.is_set():
            return
        closed.set()
        link.stop.set()
        chunks.put(None)
        wt.join(timeout=3)
        marks.close()
        keep_awake(False)
        console_restore()
    on_close(shutdown)

    mon = Monitor(alarm)
    st = dict(mark=0, note=None, port="-")

    def mark():
        st["mark"] += 1
        m = st["mark"]
        marks.write(f"{m} {time.time_ns()} {datetime.now().isoformat(timespec='milliseconds')}\n")
        marks.flush()
        beep(*TONES["mark"])
        print(f"\n\n    MARK {m}\n")

    def send_key(k):
        if link.send(k.encode()):
            mon.sent(k, time.monotonic())
        else:
            alarm("unanswered")

    t_show = t_awake = t_auto = t_port = time.monotonic()
    print(f"console_log: files in {logdir.resolve()}  ({stamp}-n.log / .idx / .marks.txt)")
    print("console_log: m mark, n note, d dump the capture, c capture anew, q quit")
    try:
        while True:
            try:
                for _ in range(work.qsize()):
                    item = work.get_nowait()
                    if isinstance(item[0], str):
                        kind, name = item
                        mon.port(kind, time.monotonic())
                        st["port"] = f"{kind} ({name})"
                        continue
                    mon.feed(time.monotonic(), item[1])
                # the keys; a note is typed on the status line, nothing waits for it
                k = key()
                if st["note"] is None:
                    k = command_key(k)
                if st["note"] is not None and k is not None:
                    if k in ("\r", "\n"):
                        marks.write(f"{st['mark']} note {st['note']}\n"); marks.flush(); st["note"] = None
                    elif k in ("\b", "\x7f"):
                        st["note"] = st["note"][:-1]
                    elif k == "\x1b":
                        st["note"] = None
                    else:
                        st["note"] += k
                elif k == "m":
                    mark()
                elif k == "n":
                    st["note"] = ""
                elif k == "d":
                    send_key("d")
                elif k == "c":
                    if ask("capture anew? a start-up capture not dumped yet is lost"):
                        send_key("c")
                elif k == "q":
                    if ask("quit?"):
                        break
                now = time.monotonic()
                mon.tick(now)
                if a.auto_mark and now - t_auto >= a.auto_mark:
                    t_auto = now
                    mark()
                if link.ever and not link.alive.is_set() and now - t_port > 10:
                    t_port = now
                    alarm("port")                    # again while it is gone
                elif link.alive.is_set():
                    t_port = now
                if now - t_awake > 30:
                    t_awake = now
                    keep_awake(True)                 # macOS: caffeinate again if it has gone
                if now - t_show > 0.25:              # the screen, 4 times a second at most
                    t_show = now
                    cols = max(40, shutil.get_terminal_size((160, 24)).columns - 1)
                    if st["note"] is not None:
                        print("\r" + f"note for mark {st['mark']}: {st['note']}"[-cols:].ljust(cols), end="", flush=True)
                    else:
                        # one line, cut to the window (a wrapped line would scroll the screen): the
                        # alarms while they last, then the counters and the last sound value
                        line = ""
                        if wr.error:
                            line += f"DISK ERROR {wr.error[:40]} | "
                        if not link.alive.is_set():
                            line += "PORT " + (PORT_NOTE[0] if PORT_NOTE else f"{a.port or ''} not open".lstrip()) + " | "
                        line += f"mark {st['mark']} | " + mon.screen(now)
                        print("\r" + line[:cols].ljust(cols), end="", flush=True)
                time.sleep(0.01)
            except KeyboardInterrupt:
                if ask("quit?"):
                    break
    finally:
        shutdown()
    print("\nconsole_log: closed; alarms " + ", ".join(f"{k} {v}" for k, v in alarms.items() if v and k != "mark"))


if __name__ == "__main__":
    main()
