#!/usr/bin/env python3
"""run_rx.py - the receiver regression: stimulus corners x decoder, all must PASS.

Corners come from the MOST Specification of Physical Layer Rev 1.1:
  fs     44.1 and 48 kHz (both occur in cars: Audi/BMW vs JLR)
  pre    the preamble's run pattern: the placeholder (one 3-UI run) and an
         S/PDIF-like set (two 3-UI runs in one preamble) - the specs give none
  pwd    average pulse-width distortion tapwd4, -0.15 .. +0.316 UI (SP4)
  jit    tDDJ4 + tUJ4 = 0.15 + 0.045 = 0.195 UI peak-to-peak (SP4)
  ppm    FS tolerance +/- 0.1 % (section 2.1, "normal accuracy mode")
With pwd at a limit plus half the jitter, a pulse reaches the SP4 tpwv4 bounds
(0.743 .. 1.40 UI for a 1-UI pulse).

Noise-burst corners: 5 us of noise (runs of 9..12 samples, 0.56..0.75 UI) over
frame 16 of a line at pwd -0.15 UI. Unguarded, rx_classify's loops ended at
ui 0.72 UI, a point the real line then held: the receiver never locked again.
Every decoded frame after the burst must be right and in order, and decoding
must resume:
  burst          ui/b bounds and relearning, as built: back at once
  burst_relearn  bounds off (CLAMP=0), relearning after 0.25 ms: back after it
  burst_noguard  both off: must stay lost - proof that the corner sees the trap

Usage: python run_rx.py [--frames N]      needs oss-cad-suite on PATH
"""
import argparse
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RTL = HERE.parent / "rtl"
SRC = ["tb_rx.v", str(RTL / "rx_runlen.v"), str(RTL / "rx_classify.v"), str(RTL / "rx_framer.v")]

CORNERS = [
    # name              fs     pwd     jit    ppm    preamble set (make_stim --preamble)
    ("48k_ideal",       48000, 0.0,    0.0,   0,     "default"),
    ("44k1_ideal",      44100, 0.0,    0.0,   0,     "default"),
    ("48k_pwd+",        48000, 0.316,  0.195, 0,     "default"),
    ("48k_pwd-",        48000, -0.15,  0.195, 0,     "default"),
    ("44k1_pwd+",       44100, 0.316,  0.195, 0,     "default"),
    ("44k1_pwd-",       44100, -0.15,  0.195, 0,     "default"),
    ("48k_fast_pwd+",   48000, 0.316,  0.195, 1000,  "default"),
    ("44k1_slow_pwd-",  44100, -0.15,  0.195, -1000, "default"),
    # S/PDIF-like preambles: two 3-UI runs in one preamble (3-3-1-1 / 3-1-1-3)
    ("48k_spdif_pwd+",  48000, 0.316,  0.195, 0,     "spdif"),
    ("44k1_spdif_pwd-", 44100, -0.15,  0.195, -1000, "spdif"),
]


BURSTS = [
    # name                 fs     pwd    frames at  us   lo  hi  RELEARN  CLAMP  frames lost at most
    ("48k_burst",          48000, -0.15, 96,    16, 5.0, 9,  12, 495000,  1,     6),
    ("44k1_burst",         44100, -0.15, 96,    16, 5.0, 9,  12, 495000,  1,     6),
    ("48k_burst_relearn",  48000, -0.15, 96,    16, 5.0, 9,  12, 24750,   0,     20),
    ("48k_burst_noguard",  48000, -0.15, 96,    16, 5.0, 9,  12, 1000000, 0,     None),
]


def add_burst(d, fs, at, us, lo, hi, seed):
    """Noise over the samples from frame `at` on: runs of lo..hi samples, alternating."""
    words = [int(l, 16) for l in (d / "samples.hex").read_text().split()]
    bits = [(w >> k) & 1 for w in words for k in range(8)]
    start, n = int(at / fs * 792e6), int(us * 1e-6 * 792e6)
    rnd = random.Random(seed)
    i, lvl = start, bits[start]
    while i < start + n:
        lvl ^= 1
        L = rnd.randint(lo, hi)
        for k in range(i, min(i + L, start + n)):
            bits[k] = lvl
        i += L
    out = [sum(bits[k + j] << j for j in range(8)) for k in range(0, len(bits), 8)]
    (d / "samples.hex").write_text("\n".join("%02x" % v for v in out) + "\n")


def check_burst(d, at, lost_max):
    """Decoded frames against the truth around a burst over frame `at`."""
    truth = [l.strip() for l in (d / "frames.hex").read_text().split()]
    tnorm = ["0" + t[1:] for t in truth]
    got = [l.split() for l in (d / "out_frames.txt").read_text().splitlines() if l.strip()]
    idx = []
    for bk, bi, par, hexs in got:
        h = hexs if bk == "1" else "0" + hexs[1:]
        idx.append(next((k for k, t in enumerate(truth if bk == "1" else tnorm) if t == h), None))
    post = [i for i, k in enumerate(idx) if k is not None and k >= at + 2]
    bad = 0
    if post:                    # from the first good frame after the burst on: all right, in order
        for n, i in enumerate(range(post[0], len(idx))):
            if idx[i] != idx[post[0]] + n:
                bad += 1
    resumed = idx[post[0]] if post else None
    if lost_max is None:
        return len(post) <= 2, f"stayed lost ({len(post)} frames after the burst)"
    ok = bad == 0 and resumed is not None and resumed - (at + 1) <= lost_max
    return ok, (f"{len(post)} frames after the burst, decoding again from frame "
                f"{resumed if resumed is not None else '-'} (at most {at + 1 + lost_max}), "
                f"{bad} wrong or out of order")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=48)
    ap.add_argument("--work", type=Path, default=HERE / "work")
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    vvp = a.work / "tb_rx.vvp"
    subprocess.run(["iverilog", "-g2005", "-o", str(vvp)] + SRC, cwd=HERE, check=True)
    fails = 0
    for i, (name, fs, pwd, jit, ppm, pre) in enumerate(CORNERS):
        d = a.work / name
        if d.exists():
            shutil.rmtree(d)
        subprocess.run([sys.executable, str(HERE / "make_stim.py"), "--fs", str(fs),
                        "--frames", str(a.frames), "--pwd", str(pwd), "--jit", str(jit),
                        "--ppm", str(ppm), "--preamble", pre, "--seed", str(i + 1), "--out", str(d)],
                       check=True, capture_output=True)
        sim = subprocess.run(["vvp", "-n", str(vvp)], cwd=d, capture_output=True, text=True)
        stat = next((l for l in sim.stdout.splitlines() if l.startswith("clocks=")), "no status")
        cmp = subprocess.run([sys.executable, str(HERE / "compare.py"), str(d)],
                             capture_output=True, text=True)
        verdict = "PASS" if cmp.returncode == 0 else "FAIL"
        fails += cmp.returncode != 0
        print(f"{verdict}  {name:16s} {stat}")
        for line in cmp.stdout.splitlines():
            if line.startswith(("frames:", "runs:", "FAIL", "frame ")):
                print("        " + line)
    for name, fs, pwd, frames, at, us, lo, hi, relearn, clamp, lost_max in BURSTS:
        d = a.work / name
        if d.exists():
            shutil.rmtree(d)
        subprocess.run([sys.executable, str(HERE / "make_stim.py"), "--fs", str(fs),
                        "--frames", str(frames), "--pwd", str(pwd), "--jit", "0.195",
                        "--seed", "7", "--out", str(d)], check=True, capture_output=True)
        add_burst(d, fs, at, us, lo, hi, 11)
        bvvp = d / "tb_rx.vvp"
        subprocess.run(["iverilog", "-g2005", "-o", str(bvvp),
                        f"-Ptb_rx.MAXCLK={int(frames / fs * 99e6) + 2000}",
                        f"-Ptb_rx.RELEARN={relearn}", f"-Ptb_rx.CLAMP={clamp}"] + SRC, cwd=HERE, check=True)
        sim = subprocess.run(["vvp", "-n", str(bvvp)], cwd=d, capture_output=True, text=True)
        stat = next((l for l in sim.stdout.splitlines() if l.startswith("clocks=")), "no status")
        ok, verdict = check_burst(d, at, lost_max)
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:18s} {stat}")
        print(f"        {verdict}")
    n = len(CORNERS) + len(BURSTS)
    print(f"\n{n - fails}/{n} corners pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
