#!/usr/bin/env python3
"""run_spdif.py - spdif_tx alone, decoded back (spdif_dec.py), at 48 and 44.1 kHz.

tb_spdif.v drives the encoder with a frame counter like tdm_out's and a known
pair per frame (full scale both ways, zero, +-1 LSB, changing patterns), 600
frames = 3 channel-status blocks and a bit. The decoder must find, in every
frame: X or Z before the left sample and Y before the right, Z exactly every
192 frames, a transition opening every bit cell, even parity, V = U = 0, the
channel status bytes 04 00 00 (00 | 02) 0B and zeros, and the pair itself.

Usage: python run_spdif.py            needs oss-cad-suite on PATH
"""
import subprocess
import sys
from pathlib import Path

import spdif_dec

HERE = Path(__file__).resolve().parent
RTL = HERE.parent / "rtl"
SRC = ["tb_spdif.v", str(RTL / "spdif_tx.v")]
CORNERS = [("spdif48", 1), ("spdif44", 0)]


def run_corner(name, rate48, work):
    d = work / name
    d.mkdir(parents=True, exist_ok=True)
    vvp = d / "tb.vvp"
    subprocess.run(["iverilog", "-g2012", "-o", str(vvp), f"-Ptb_spdif.RATE48={rate48}", "-Ptb_spdif.NFR=600"]
                   + SRC, cwd=HERE, check=True)
    subprocess.run(["vvp", "-n", str(vvp)], cwd=d, check=True, capture_output=True)
    lines = spdif_dec.frames_of((d / "out_spdif.txt").read_text())
    truth = [(int(l, 16), int(r, 16)) for _, l, r in
             (ln.split() for ln in (d / "out_truth.txt").read_text().splitlines() if ln.strip())]
    ok, summary = spdif_dec.check(lines, truth, bool(rate48))
    print(f"  {'PASS' if ok else 'FAIL'}  {summary}")
    return ok


def main():
    work = HERE / "work"
    ok = True
    for name, rate48 in CORNERS:
        print(f"{name}: {'48000' if rate48 else '44100'} Hz")
        ok &= run_corner(name, rate48, work)
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
