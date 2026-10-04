#!/usr/bin/env python3
"""trace_decode.py - a recording (console_log.py's files) into files a person can read.

    python tools/trace_decode.py logs/20261010-183000-1.log [logs/20261010-183000-2.log ...]
    python tools/trace_decode.py logs/20261010-183000          (every segment of that recording, in order)
    python tools/trace_decode.py                               (the newest recording in logs/, every segment)

The segments of one recording (console_log starts a new one on every reconnect; the ESP32 runs on)
are read as one stream, a chunk at a time. Into <recording>.d/:
  summary.txt    the segments and the time they cover; lines by kind; every start of the ESP32 (its
                 boot banner, or its milliseconds going back); the status line's counters at each
                 start and at the end and every rise of a counter that means a loss or a gap; the
                 silences (no line for 25 s); the marks with their notes; the dumps; the functions
                 by count
  telegrams.csv  every telegram: PC time, seconds from the start, the ESP32's ms, segment, frame,
                 source, target, FBlock, Inst, FktID, name, OPType, length, data, the last mark
  sound.txt      what the host takes for J3's sound (sound.c): each value's lowest and highest, then
                 every change with its time and the marks between them - a car's scales are fixed
                 from these (listener_fw/README.md)
  functions.txt  every function (FBlock.Inst.FktID): its OPTypes and senders with counts, first and
                 last time, its payloads by count
  marks.txt      every mark: its time, its note and the telegrams from 5 s before it to 3 s after,
                 each with how often its function came in the whole recording (a rare one beside a
                 mark is what the key or the knob sent)
  console.txt    every other line (the host's messages, warnings, errors, the boot) with its time
  dump_<n>.txt, dump_<n>_analysis.txt   each capture's dump, and what capture_analyse.py reads from it
Telegrams the console had no time for are not in the files: the status line counts them (trace
lost), and summary.txt says how many.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import capture_analyse as CA                                               # noqa: E402
import console_format as CF                                                # noqa: E402

# console_log.py's folder: logs/ at the repository's root, or beside this file in kit/3_laptop
LOGS = ROOT / "logs" if (ROOT / "listener_fw").is_dir() else HERE / "logs"
CHUNK = 1 << 20
SILENT_S = 2.5 * CF.STATUS_S
BEFORE_S, AFTER_S = 5.0, 3.0              # a mark's window
NEAR_S = 30.0                             # sound.txt: the marks this near a value's first or last change
PAYLOADS = 40                            # a function's payloads kept by count; the rest counted
# the status line's counters that should stay where they are: losses on our side, a gap in the
# control blocks, a block dropped by its parity, a telegram refused, a capture packet bad
WATCH = ("bad", "fpga_lost", "gaps", "parity_dropped", "refused", "seg_dropped", "trace_lost", "cap_bad")
SEG = re.compile(r"^(.*)-(\d+)\.log$")


def hms(t_ns):
    return "--:--:--.---" if t_ns is None else datetime.fromtimestamp(t_ns / 1e9).strftime("%H:%M:%S.%f")[:-3]


def printable(s: str, n=200) -> str:
    """A console line as text: what is not printable, or came as no character at all (the ROM's
    output at 115200 baud), is a ?"""
    return "".join(c if c.isprintable() and c != "�" else "?" for c in s)[:n]


def segments(args) -> tuple[Path, list[Path]]:
    """The recording's base (logs/<stamp>) and its .log files in order."""
    if not args:
        stamps = sorted({SEG.match(p.name).group(1) for p in LOGS.glob("*-*.log") if SEG.match(p.name)})
        if not stamps:
            sys.exit(f"trace_decode: no recording in {LOGS}")
        args = [str(LOGS / stamps[-1])]
    files = []
    for a in args:
        p = Path(a)
        if p.suffix == ".log":
            files.append(p)
        else:
            files += sorted(p.parent.glob(p.name + "-*.log"),
                            key=lambda q: int(SEG.match(q.name).group(2)) if SEG.match(q.name) else 0)
    files = [f for f in files if f.is_file()]
    if not files:
        sys.exit(f"trace_decode: no .log among {args}")
    m = SEG.match(files[0].name)
    base = files[0].parent / (m.group(1) if m else files[0].stem)
    return base, files


def read_idx(path: Path):
    offs, times, notes = [], [], []
    if path.is_file():
        for line in path.read_text(encoding="ascii", errors="replace").splitlines():
            if line.startswith("#"):
                notes.append(line[1:].strip())
                continue
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                offs.append(int(parts[0]))
                times.append(int(parts[1]))
    return offs, times, notes


def read_marks(path: Path):
    marks, notes = {}, defaultdict(list)
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split(" ", 2)
            if len(parts) >= 3 and parts[0].isdigit() and parts[1] == "note":
                notes[int(parts[0])].append(parts[2])
            elif len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                marks[int(parts[0])] = int(parts[1])
    return [(n, t, " / ".join(notes.get(n, []))) for n, t in sorted(marks.items(), key=lambda x: x[1])]


class Decode:
    def __init__(self, out: Path, marks):
        self.out = out
        self.marks = marks                         # [(n, t_ns, note)] by time
        self.mark_t = [t for _, t, _ in marks]
        self.kinds = Counter()
        self.t0 = self.t_end = None
        self.segs = []                             # (name, bytes, first t, last t, notes, cut lines)
        self.starts = []                           # (t, why, the line)
        self.rises = []                            # (t, counter, from, to)
        self.status_at = []                        # (t, "start" / "end", the counters)
        self.status = None
        self.silences = []                         # (from t, to t)
        self.last_ms = None
        self.t_last_line = None
        self.funcs = {}                            # (fblock, inst, fkt) -> dict
        self.func_n = Counter()                    # (fblock, fkt) -> count
        self.sound = defaultdict(list)             # what -> [(t, number, text, op, src>dst)] on change
        self.near = {n: [] for n, _, _ in marks}   # mark -> [(t, Tel)]
        self.dumps = []                            # (t, [lines], whole)
        self.dump = None
        self.console = open(out / "console.txt", "w", encoding="utf-8", newline="\n")
        self.csvf = open(out / "telegrams.csv", "w", encoding="utf-8", newline="")
        self.csv = csv.writer(self.csvf)
        self.csv.writerow(["pc_time", "t_s", "esp_ms", "segment", "frame", "source", "target", "fblock", "inst",
                           "fktid", "name", "optype", "length", "data", "truncated", "mark"])

    def last_mark(self, t):
        if t is None:
            return ""
        i = bisect.bisect_right(self.mark_t, t)
        return str(self.marks[i - 1][0]) if i else ""

    def line(self, seg: int, t, ln: CF.Line):
        self.kinds[ln.kind] += 1
        if t is not None:
            if self.t0 is None:
                self.t0 = t
            if self.t_last_line is not None and (t - self.t_last_line) / 1e9 > SILENT_S:
                self.silences.append((self.t_last_line, t))
            self.t_last_line = self.t_end = t
        first = self.last_ms is None      # no line of the ESP32's yet
        if ln.ms is not None:
            back = self.last_ms is not None and ln.ms + 1000 < self.last_ms
            if ln.boot_banner or back:
                why = "the boot banner" if ln.boot_banner else f"its ms went back from {self.last_ms} to {ln.ms}"
                self.starts.append((t, why if not first else why + " (the recording's first line)",
                                    printable(ln.text, 120)))
                if self.status is not None:
                    self.status_at.append((t, "before this start", self.status))
                self.status = None
            self.last_ms = ln.ms
        if ln.kind == "tel":
            self.tel(seg, t, ln)
        elif ln.kind == "status":
            s = ln.status
            if self.status is None:
                self.status_at.append((t, "first after a start" if self.starts else "first", s))
            else:
                for k in WATCH:
                    if s[k] > self.status[k]:
                        self.rises.append((t, k, self.status[k], s[k]))
            self.status = s
        elif ln.kind == "cap":
            if ln.text.startswith("CAP BEGIN"):
                if self.dump:
                    self.dumps.append((self.dump[0], self.dump[1], False))
                self.dump = (t, [ln.text])
            elif self.dump:
                self.dump[1].append(ln.text)
                if ln.text.startswith("CAP END"):
                    self.dumps.append((self.dump[0], self.dump[1], True))
                    self.dump = None
        else:
            self.console.write(f"{hms(t)}  {printable(ln.text)}\n")

    def tel(self, seg, t, ln):
        x = ln.tel
        self.csv.writerow([hms(t), "" if t is None or self.t0 is None else f"{(t - self.t0) / 1e9:.3f}", ln.ms, seg,
                           f"{x.frame:08X}", f"{x.source:04X}", f"{x.target:04X}", f"{x.fblock:02X}", f"{x.inst:02X}",
                           f"{x.fkt:03X}", CF.name(x.fblock, x.fkt), x.op, x.length, x.data.hex(" ").upper(),
                           int(x.truncated), self.last_mark(t)])
        key = (x.fblock, x.inst, x.fkt)
        f = self.funcs.get(key)
        if f is None:
            f = self.funcs[key] = dict(n=0, first=t, last=t, how=Counter(), pay=Counter(), more=0)
        f["n"] += 1
        f["last"] = t
        f["how"][(x.op, f"{x.source:04X}>{x.target:04X}")] += 1
        p = f"[{x.length}] " + x.data.hex(" ").upper() + (" ..." if x.truncated else "")
        if p in f["pay"] or len(f["pay"]) < PAYLOADS:
            f["pay"][p] += 1
        else:
            f["more"] += 1
        self.func_n[(x.fblock, x.fkt)] += 1
        for what, num, text in CF.sound_values(x):
            hist = self.sound[what]
            if not hist or hist[-1][2] != text:
                hist.append((t, num, text, x.op, f"{x.source:04X}>{x.target:04X}"))
        if t is not None:
            lo = bisect.bisect_left(self.mark_t, t - AFTER_S * 1e9)
            hi = bisect.bisect_right(self.mark_t, t + BEFORE_S * 1e9)
            for i in range(lo, hi):
                self.near[self.marks[i][0]].append((t, x))

    def segment(self, k: int, path: Path):
        offs, times, notes = read_idx(path.with_suffix(".idx"))
        lines = CF.Lines()
        size = cut = 0
        first = last = None

        def at(off):
            i = bisect.bisect_right(offs, off) - 1
            return times[i] if i >= 0 else (times[0] if times else None)

        with open(path, "rb") as fh:
            while True:
                b = fh.read(CHUNK)
                if not b:
                    break
                size += len(b)
                for off, raw in lines.feed(b):
                    t = at(off)
                    first = first if first is not None else t
                    last = t
                    self.line(k, t, CF.classify(raw))
        r = lines.rest()
        if r:
            cut += 1
            self.console.write(f"{hms(at(r[0]))}  (segment {k} ends inside a line) {printable(r[1].decode('utf-8', 'replace'))}\n")
        self.segs.append((path.name, size, first, last, notes, cut))

    def finish(self):
        if self.dump:
            self.dumps.append((self.dump[0], self.dump[1], False))
            self.dump = None
        if self.status is not None:
            self.status_at.append((self.t_end, "last", self.status))
        self.console.close()
        self.csvf.close()
        self.write_sound()
        self.write_functions()
        self.write_marks()
        dump_lines = self.write_dumps()
        self.write_summary(dump_lines)

    def rel(self, t):
        return "" if t is None or self.t0 is None else f"{(t - self.t0) / 1e9:+.3f} s"

    def marks_between(self, a, b):
        return [m for m in self.marks if (a is None or m[1] > a) and (b is None or m[1] <= b)]

    def write_sound(self):
        with open(self.out / "sound.txt", "w", encoding="utf-8", newline="\n") as f:
            f.write("What the host takes for J3's sound (listener_fw/components/mostctl/sound.c), from Set,\n"
                    "SetGet and Status telegrams: each value's lowest and highest, then every change with\n"
                    "its time, the OPType and who sent it; the marks between the changes, and those up to\n"
                    f"{NEAR_S:.0f} s before the first change and after the last.\n")
            if not self.sound:
                f.write("\nnothing: no telegram the host takes a sound value from\n")
            for what in sorted(self.sound):
                hist = self.sound[what]
                nums = [h[1] for h in hist if h[1] is not None]
                rng = f"lowest {min(nums)}, highest {max(nums)}" if nums else "no number"
                f.write(f"\n{what}: {len(hist)} value(s), {rng}\n")
                # the marks between the changes, and those within NEAR_S before the first change and
                # after the last (a mark set at an end of the knob's travel)
                prev = None if hist[0][0] is None else hist[0][0] - int(NEAR_S * 1e9)
                for t, num, text, op, who in hist:
                    for n, tm, note in self.marks_between(prev, t):
                        f.write(f"    -- mark {n} at {hms(tm)}{': ' + note if note else ''}\n")
                    f.write(f"  {hms(t)}  {self.rel(t):>12}  {text:<14} {op} {who}\n")
                    prev = t
                if prev is not None:
                    for n, tm, note in self.marks_between(prev, prev + int(NEAR_S * 1e9)):
                        f.write(f"    -- mark {n} at {hms(tm)}{': ' + note if note else ''}\n")

    def write_functions(self):
        with open(self.out / "functions.txt", "w", encoding="utf-8", newline="\n") as f:
            f.write("Every function the trace showed (FBlock.Inst.FktID), by FBlock and FktID: how often, the\n"
                    "OPTypes and senders, the first and last time, the payloads by count.\n")
            for (fb, inst, fkt), d in sorted(self.funcs.items(), key=lambda x: (x[0][0], x[0][2], x[0][1])):
                n = CF.name(fb, fkt)
                f.write(f"\n{fb:02X}.{inst:02X}.{fkt:03X}{' ' + n if n else ''}: {d['n']} telegrams, "
                        f"{hms(d['first'])} .. {hms(d['last'])}\n")
                for (op, who), c in d["how"].most_common():
                    f.write(f"    {c:7d}  {op} {who}\n")
                for p, c in d["pay"].most_common():
                    f.write(f"    {c:7d}  {p}\n")
                if d["more"]:
                    f.write(f"    {d['more']:7d}  in other payloads (only the first {PAYLOADS} kept)\n")

    def write_marks(self):
        with open(self.out / "marks.txt", "w", encoding="utf-8", newline="\n") as f:
            f.write(f"Every mark with the telegrams {BEFORE_S:g} s before it to {AFTER_S:g} s after it; the last\n"
                    "column is how often that function came in the whole recording.\n")
            if not self.marks:
                f.write("\nno marks\n")
            for n, tm, note in self.marks:
                f.write(f"\nmark {n} at {hms(tm)} ({self.rel(tm)}){': ' + note if note else ''}\n")
                for t, x in self.near[n]:
                    f.write(f"  {(t - tm) / 1e9:+7.3f} s  {x.short():<60}  {x.source:04X}>{x.target:04X}  "
                            f"x{self.func_n[(x.fblock, x.fkt)]}\n")
                if not self.near[n]:
                    f.write("  no telegram\n")

    def write_dumps(self):
        out = []
        for k, (t, lines, whole) in enumerate(self.dumps, 1):
            text = "\n".join(lines) + "\n"
            (self.out / f"dump_{k}.txt").write_text(text, encoding="utf-8", newline="\n")
            try:
                runs, glitch, hdr = CA.parse_dump(text)
                rep = CA.report(CA.analyse(runs, glitch)) if runs else "no runs in this dump"
            except Exception as e:                 # a broken dump must not stop the rest
                rep = f"capture_analyse could not read it: {type(e).__name__}: {e}"
            (self.out / f"dump_{k}_analysis.txt").write_text(rep + "\n", encoding="utf-8", newline="\n")
            out.append(f"  dump {k} at {hms(t)}: {lines[0]}" + ("" if whole else " - NO 'CAP END': cut") +
                       f"\n    {rep.splitlines()[0] if rep else ''}")
        return out

    def write_summary(self, dump_lines):
        t0 = self.t0
        with open(self.out / "summary.txt", "w", encoding="utf-8", newline="\n") as f:
            day = datetime.fromtimestamp(t0 / 1e9).strftime("%Y-%m-%d") if t0 else "unknown day"
            dur = (self.t_end - t0) / 1e9 if t0 and self.t_end else 0
            f.write(f"Recording of {day}, {hms(t0)} .. {hms(self.t_end)} ({dur:.0f} s), {len(self.segs)} segment(s)\n")
            prev_last = None
            for name, size, first, last, notes, cut in self.segs:
                gap = f", {(first - prev_last) / 1e9:.1f} s after the one before (the port was away)" \
                    if prev_last and first else ""
                f.write(f"  {name}: {size} bytes, {hms(first)} .. {hms(last)}{gap}"
                        f"{'; the last line cut' if cut else ''}; {'; '.join(notes)}\n")
                prev_last = last or prev_last
            f.write("\nlines: " + ", ".join(f"{k} {v}" for k, v in self.kinds.most_common()) + "\n")
            f.write(f"\nthe ESP32 started {len(self.starts)} time(s):\n")
            for t, why, text in self.starts:
                f.write(f"  {hms(t)}  {why}: {text}\n")
            f.write("\nthe status line's counters (since the ESP32's start):\n")
            for t, what, s in self.status_at:
                f.write(f"  {hms(t)}  {what}: " + ", ".join(f"{k} {s[k]}" for k in CF.COUNTERS) +
                        f"; audio in {s['audio_in']} (phone {s['phone']}, TOSLINK {s['toslink']})\n")
            lost = sum(b - a for _, k, a, b in self.rises if k == "trace_lost")
            f.write(f"\nrises of the counters that should stay put ({', '.join(WATCH)}): {len(self.rises)}\n")
            for t, k, a, b in self.rises:
                f.write(f"  {hms(t)}  {k} {a} -> {b}\n")
            if lost:
                f.write(f"  the console had no time for {lost} telegram(s): they are not in telegrams.csv\n")
            f.write(f"\nsilences (no line for {SILENT_S:.0f} s): {len(self.silences)}\n")
            for a, b in self.silences:
                f.write(f"  {hms(a)} .. {hms(b)} ({(b - a) / 1e9:.1f} s)\n")
            f.write(f"\nmarks: {len(self.marks)}\n")
            for n, t, note in self.marks:
                f.write(f"  {n}  {hms(t)}  {self.rel(t)}{'  ' + note if note else ''}\n")
            f.write(f"\ndumps: {len(self.dumps)}\n" + "".join(x + "\n" for x in dump_lines))
            f.write(f"\nfunctions by count ({len(self.funcs)} in all):\n")
            for (fb, inst, fkt), d in sorted(self.funcs.items(), key=lambda x: -x[1]["n"])[:40]:
                n = CF.name(fb, fkt)
                f.write(f"  {d['n']:8d}  {fb:02X}.{inst:02X}.{fkt:03X}{' ' + n if n else ''}\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help=".log segments, or logs/<stamp> for every segment of it")
    a = ap.parse_args(argv)
    base, files = segments(a.files)
    out = base.parent / (base.name + ".d")
    out.mkdir(exist_ok=True)
    d = Decode(out, read_marks(base.parent / (base.name + ".marks.txt")))
    for k, p in enumerate(files, 1):
        m = SEG.match(p.name)
        d.segment(int(m.group(2)) if m else k, p)
    d.finish()
    print(f"trace_decode: {len(files)} segment(s), {d.kinds['tel']} telegrams, {len(d.starts)} start(s), "
          f"{len(d.rises)} counter rise(s), {len(d.marks)} mark(s), {len(d.dumps)} dump(s) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
