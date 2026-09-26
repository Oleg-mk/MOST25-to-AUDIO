#!/usr/bin/env python3
"""test_capture_analyse.py - the analysis against a dump built from known frames.

    python tools/test_capture_analyse.py

make_stim.py builds frames of a known preamble set, parity rule and frame
control, distorts the line to the SP4 limits and samples it at 792 Msps. The
run lengths of those samples, as rx_runlen measures them, are written in the
host's dump format (one packet lost on purpose); capture_analyse must read
back the UI and the rate, every frame, the two preamble patterns and their
16-frame period, the parity rule, the frame control bits and the boundary
descriptor - for both preamble sets and both rates.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import capture_analyse as ca                                        # noqa: E402
from virtual_most_source.config import PREAMBLE_SETS                # noqa: E402

PASS = FAIL = 0


def check(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL:", msg)


def runs_of(samples_hex: Path):
    words = [int(x, 16) for x in samples_hex.read_text().split()]
    bits = [(w >> k) & 1 for w in words for k in range(8)]
    runs, n = [], 0
    for k in range(1, len(bits)):
        n += 1
        if bits[k] != bits[k - 1]:
            runs.append(min(n, 255))
            n = 0
    return runs


def dump_text(runs, lose=None):
    lines = [f"CAP BEGIN runs={len(runs)} packets={(len(runs) + 31) // 32} missing={1 if lose is not None else 0}"]
    for p in range(0, len(runs), 32):
        seq = p // 32
        if seq == lose:
            lines.append(f"CAP {seq} -")
            continue
        chunk = runs[p:p + 32] + [0] * (32 - len(runs[p:p + 32]))
        lines.append(f"CAP {seq} {bytes(chunk).hex()} 00000000")
    lines.append("CAP END")
    return "\n".join(lines) + "\n"


def one(fs, pre, pwd, tmp):
    d = tmp / f"{fs}_{pre}"
    subprocess.run([sys.executable, str(ROOT / "listener_gw" / "sim" / "make_stim.py"), "--fs", str(fs),
                    "--frames", "120", "--pwd", str(pwd), "--jit", "0.195", "--ppm", "300", "--preamble", pre,
                    "--seed", "3", "--out", str(d)], check=True, capture_output=True)
    meta = json.loads((d / "meta.json").read_text())
    runs = runs_of(d / "samples.hex")
    text = "noise before\n" + dump_text(runs, lose=7) + "noise after\n"
    r, g, hdr = ca.parse_dump(text)
    a = ca.analyse(r, g)
    print(f"-- {fs} Hz, {pre}, PWD {pwd:+.3f} UI:")
    print("  " + ca.report(a).replace("\n", "\n  "))
    check(abs(a["ui_samples"] - meta["ui_samples"]) < 0.02 * meta["ui_samples"],
          f"UI {a['ui_samples']:.3f} vs {meta['ui_samples']:.3f}")
    check(a["rate"] == fs, f"rate {a['rate']} vs {fs}")
    check(abs(a["frame_rate_hz"] / (fs * 1.0003) - 1) < 3e-5, f"frame rate {a['frame_rate_hz']:.2f} vs {fs * 1.0003:.2f}")
    check(a["unclassified"] == 0, f"{a['unclassified']} unclassified runs")
    check(a["frames"] >= 110, f"only {a['frames']} frames of 120 (one packet lost)")
    pf, pb = PREAMBLE_SETS[pre]
    want_f, want_b = " ".join(map(str, pf)), " ".join(map(str, pb))
    check(a["common_preamble"] == want_f, f"common preamble {a['common_preamble']} vs {want_f}")
    check(want_b in a["preambles"] and a["preambles"][want_b] >= 6, f"block preamble {want_b}: {a['preambles']}")
    check(set(a["rare_preamble_period"]) <= {16, 32}, f"rare preamble period {a['rare_preamble_period']}")
    check(a["parity_odd"] == 0 and a["parity_even"] == a["frames"], f"parity {a['parity_even']} even / {a['parity_odd']} odd")
    check(a["frame_control"] == {0: a["frames"]}, f"frame control {a['frame_control']}")
    check(a["boundary_descriptor"] == {15: a["frames"]}, f"BD {a['boundary_descriptor']}")
    check(set(a["frame_distance_ui"]) <= {1024, 2048}, f"frame distance {a['frame_distance_ui']}")
    if abs(pwd) > 0.05:
        check(a["pwd_ui"] is not None and abs(abs(a["pwd_ui"]) - abs(pwd)) < 0.03,
              f"PWD {abs(a['pwd_ui']):.3f} vs {abs(pwd):.3f}")


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        one(48000, "default", 0.316, tmp)
        one(44100, "spdif", -0.15, tmp)
    print(f"\nTESTS: {PASS}/{PASS + FAIL} passed" + (f"  ({FAIL} FAILED)" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
