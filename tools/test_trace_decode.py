#!/usr/bin/env python3
"""test_trace_decode.py - trace_decode.py over a made-up recording with every case a car brings.

    python tools/test_trace_decode.py

Two segments written by console_log.py's Writer (.log, .idx; the .marks.txt as its main() writes
it), the port away 3.5 s between them: the ROM's noise and the boot banner; the volume stepped
10..15 with the amplifier's echo of each and a mark between 12 and 13; a status line with "trace
lost" rising; a wheel key and a bass step beside the second mark; a capture's dump built from known
frames (listener_gw/sim/make_stim.py at 48 kHz); a line cut by the segment's end; the ESP32 started
anew in the second segment, its counters from zero, the volume at 16, then 35 s without a line.
Every output file is checked against what went in.
"""
from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import console_log as CL                                                   # noqa: E402
import test_capture_analyse as TCA                                         # noqa: E402
import trace_decode as TD                                                  # noqa: E402

BAD = 0
T0 = int(datetime(2026, 10, 4, 12, 0, 0).timestamp()) * 10**9


def check(cond, msg):
    global BAD
    if not cond:
        BAD += 1
        print("  BAD ", msg)
    return cond


def tel(ms, src, dst, fb, fkt, op, data, inst=1):
    return (f"I ({ms}) tel: {0x1000 + ms:08X} {src:04X}>{dst:04X} {fb:02X}.{inst:02X}.{fkt:03X} {op} "
            f"[{len(data)}]" + "".join(f" {b:02X}" for b in data) + "\r\n").encode()


def status(ms, **kw):
    v = dict(packets=0, bad=0, fpga_lost=0, gaps=0, parity_dropped=0, telegrams=0, refused=0, seg_dropped=0,
             trace_lost=0, cap_packets=0, cap_bad=0, dumps=0)
    v.update(kw)
    return (f"I ({ms}) host: packets {v['packets']} (bad {v['bad']}, lost in the FPGA {v['fpga_lost']}, gaps "
            f"{v['gaps']}, parity dropped {v['parity_dropped']}), telegrams {v['telegrams']}, refused {v['refused']}, "
            f"segments dropped {v['seg_dropped']}, trace lost {v['trace_lost']}, capture packets {v['cap_packets']} "
            f"(bad {v['cap_bad']}), dumps {v['dumps']}, audio in none (phone idle, TOSLINK no signal)\r\n").encode()


def write_segment(wr: CL.Writer, chunks, note: str):
    """chunks: [(seconds from T0, bytes)], in order, each one of the port's reads - written by the
    recorder's own Writer, so the decoder reads the files the recorder makes."""
    wr.segment(note)
    for s, b in chunks:
        wr.put(T0 + int(s * 1e9), b)


def recording(tmp: Path):
    stim = tmp / "stim"
    subprocess.run([sys.executable, str(ROOT / "listener_gw" / "sim" / "make_stim.py"), "--fs", "48000",
                    "--frames", "48", "--pwd", "0.2", "--jit", "0.1", "--ppm", "100", "--seed", "5",
                    "--out", str(stim)], check=True, capture_output=True)
    dump = TCA.dump_text(TCA.runs_of(stim / "samples.hex")).replace("\n", "\r\n").encode()
    base = tmp / "logs" / "20261004-120000"
    base.parent.mkdir()
    wr = CL.Writer(base.parent, base.name)
    s1 = [(0.00, b"\x00\xff\x8aets Jul 29 2019 12:21:46\r\n"),
          (0.05, b"I (29) boot: ESP-IDF v6.1 2nd stage bootloader\r\n"),
          (0.30, b"I (310) main: listener host\r\n"),
          (10.0, status(10000, packets=100, telegrams=10))]
    ev = []
    for k in range(31):                                   # a telegram every second, the whole time
        s = 10.5 + k
        ev.append((s, tel(int(s * 1000), 0x110, 0x100, 0x01, 0xC00, "Status/Result", b"\x00\x01")))
    for k, v in enumerate(range(10, 16)):                 # the volume stepped, the amplifier echoing
        s = 15.0 + 0.5 * k
        ev.append((s, tel(int(s * 1000), 0x100, 0x180, 0x22, 0x400, "Set/Start", bytes([v]))))
        ev.append((s + 0.05, tel(int(s * 1000) + 50, 0x180, 0x100, 0x22, 0x400, "Status/Result", bytes([v]))))
    ev.append((20.0, status(20000, packets=200, telegrams=30, trace_lost=2)))
    ev.append((25.0, tel(25000, 0x161, 0x16E, 0x01, 0xCA1, "Set/Start", b"\x03\x01\x00")))
    ev.append((27.0, tel(27000, 0x100, 0x180, 0x22, 0x202, "Set/Start", b"\xfd")))
    lines = dump.split(b"\r\n")[:-1]
    for k in range(0, len(lines), 200):                   # the dump in chunks, as the port reads it
        ev.append((30.0 + k / 20000, b"".join(x + b"\r\n" for x in lines[k:k + 200])))
    ev.append((30.5, status(30500, packets=300, telegrams=40, trace_lost=2, dumps=1)))
    s1 += sorted(ev, key=lambda e: e[0])
    s1.append((41.0, b"I (41000) tel: 0001F2A0 0100>01"))   # the port went mid-line
    write_segment(wr, s1, f"open COM5 {T0}")
    s2 = [(44.0, b"I (29) boot: ESP-IDF v6.1 2nd stage bootloader\r\n"),
          (54.0, status(10000, packets=50)),
          (55.0, tel(11000, 0x100, 0x180, 0x22, 0x400, "Set/Start", bytes([16]))),
          (90.0, b"W (46000) host: no locked ring for 600 ms: every allocation is void, starting over\r\n")]
    write_segment(wr, s2, f"open COM5 {T0 + 44 * 10**9}")
    wr.close()
    (base.parent / (base.name + ".marks.txt")).write_text(
        f"1 {T0 + int(16.2e9)} 2026-10-04T12:00:16.200\n1 note volume up\n"
        f"2 {T0 + int(26.0e9)} 2026-10-04T12:00:26.000\n2 note next track on the wheel\n", encoding="utf-8")
    return base


def main() -> int:
    sys.stdout.reconfigure(errors="backslashreplace")       # a console in cp1251 still shows a failure
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        base = recording(tmp)
        TD.main([str(base)])
        out = base.parent / (base.name + ".d")
        rows = list(csv.DictReader(open(out / "telegrams.csv", encoding="utf-8")))
        check(len(rows) == 31 + 12 + 1 + 1 + 1, f"{len(rows)} telegrams, want 46")
        vol = [r for r in rows if r["fktid"] == "400" and r["optype"] == "Set/Start"]
        check([int(r["data"], 16) for r in vol] == list(range(10, 17)), f"volume steps {[r['data'] for r in vol]}")
        check(vol[2]["mark"] == "" and vol[3]["mark"] == "1" and vol[3]["name"] == "Volume" and vol[3]["t_s"] == "16.500",
              f"the mark and time of the volume rows: {vol[2]}, {vol[3]}")
        check(vol[-1]["segment"] == "2" and vol[-1]["mark"] == "2", f"the second segment's row: {vol[-1]}")
        snd = (out / "sound.txt").read_text(encoding="utf-8")
        check("22.400 Volume: 7 value(s), lowest 10, highest 16" in snd, "sound.txt's volume line:\n" + snd)
        check("22.202 Bass: 1 value(s), lowest -3, highest -3" in snd, "sound.txt's bass line")
        bs = snd[snd.index("22.202 Bass"):snd.index("22.400 Volume")]
        check("mark 1 at" in bs and "mark 2 at" in bs, "the marks within 30 s before the bass's change:\n" + bs)
        vs = snd[snd.index("22.400 Volume"):]
        i12, im, i13 = vs.find("volume 12 "), vs.find("-- mark 1 at 12:00:16.200: volume up"), vs.find("volume 13 ")
        check(0 < i12 < im < i13, "mark 1 between the volume's 12 and 13 in sound.txt")
        summ = (out / "summary.txt").read_text(encoding="utf-8")
        check("the ESP32 started 2 time(s)" in summ and "(the recording's first line)" in summ,
              "the two starts in summary.txt")
        check("trace_lost 0 -> 2" in summ and "rises of the counters that should stay put" in summ and
              "no time for 2 telegram(s)" in summ, "trace lost rising in summary.txt")
        check(summ.count(" -> ") == 1, "one rise only: the second start's counters are not a rise")
        check("12:00:55.000 .. 12:01:30.000 (35.0 s)" in summ, "the silence in summary.txt")
        check("3.5 s after the one before" in summ and "the last line cut" in summ, "the segments in summary.txt")
        check("1  12:00:16.200" in summ and "next track on the wheel" in summ, "the marks in summary.txt")
        mk = (out / "marks.txt").read_text(encoding="utf-8")
        part = mk[mk.index("mark 2"):]
        check("01.01.CA1 wheel keys Set/Start [3] 03 01 00" in part and "0161>016E  x1" in part,
              "the wheel key beside mark 2:\n" + part)
        check(part.count("01.01.C00") == 8, f"mark 2's window: {part.count('01.01.C00')} periodic telegrams, want 8")
        fn = (out / "functions.txt").read_text(encoding="utf-8")
        check("22.01.400 Volume: 13 telegrams" in fn and "Set/Start 0100>0180" in fn, "functions.txt's volume")
        con = (out / "console.txt").read_text(encoding="utf-8")
        check("I (310) main: listener host" in con and "segment 1 ends inside a line" in con and
              "W (46000) host: no locked ring" in con and "?ets Jul 29" in con, "console.txt:\n" + con[:600])
        an = (out / "dump_1_analysis.txt").read_text(encoding="utf-8")
        check("a 48000 Hz ring" in an and "EVEN" in an, "the dump's analysis:\n" + an)
        check((out / "dump_1.txt").read_text(encoding="utf-8").startswith("CAP BEGIN"), "dump_1.txt")
        # a recording named by one of its .log files, and the newest in a logs folder
        TD.LOGS = base.parent
        b2, files = TD.segments([])
        check(b2 == base and [f.name for f in files] == ["20261004-120000-1.log", "20261004-120000-2.log"],
              f"the newest recording: {b2}, {files}")
        b3, files = TD.segments([str(base.parent / "20261004-120000-2.log")])
        check(b3 == base and len(files) == 1, f"one segment by name: {b3}, {files}")
    print("TRACE_DECODE: " + ("PASS" if not BAD else f"FAIL, {BAD}"))
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
