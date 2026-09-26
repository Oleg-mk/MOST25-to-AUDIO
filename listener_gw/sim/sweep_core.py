#!/usr/bin/env python3
"""sweep_core.py - the whole-core test over many random rings, not two.

A test proves only the case it runs; a bug that needs an unlucky coincidence
(the FIFO restart found in the Si514 block needed the write pointer in one
range when the read side came back) slips past two fixed stimuli. So each run
here draws its own case:
  rate 48 or 44.1 kHz (alternating), pulse-width distortion -0.15..+0.316 UI
  (the SP4 limits), edge jitter 0.1..0.195 UI, ring offset -1000..+1000 ppm,
  the Si514's own crystal error -100..+100 ppm (the widest stability grade
  on the shelf), its I2C address 0x08..0x77,
  whether "inject" is sent before the Si514 is centred, and a fresh seed.
Every third run also kills the line for 5..50 us, 2 ms after LOCK.

  clean run  every check of check_core.py must pass (SI, TX, TDM, UART, MCLK,
             I2S, INJ, FS)
  gap run    check_core.check_gap: LOCK down within 5 us of the dead line, back
             after it; the Si514 centred once, no small change outside its
             window, nothing addressed wrongly
720 frames per run (840 with a dead line): the simulation loop (8-frame rate
measurement, fn 150 Hz) takes ~7 ms to lock when the Si514's crystal is 50 ppm
off - the centring cannot see that error - and the host's commands and the
dead line come after LOCK.

Runs go in parallel; a failing run's directory is kept whole under work/sweep/.
Usage: python sweep_core.py [--runs 32] [--jobs 16] [--base 1000]
                            needs oss-cad-suite on PATH
"""
import argparse
import contextlib
import io
import random
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import check_core as cc
from run_core import RTL, SRC, full_checks

HERE = Path(__file__).resolve().parent


def case(i, base):
    r = random.Random(base + i)
    c = dict(
        i=i,
        fs=48000 if i % 2 == 0 else 44100,
        pwd=round(r.uniform(-0.15, 0.316), 3),
        jit=round(r.uniform(0.1, 0.195), 3),
        ppm=round(r.uniform(-1000.0, 1000.0), 1),
        si_ppm=round(r.uniform(-100.0, 100.0), 1),
        addr=r.randrange(0x08, 0x78),
        early=r.random() < 0.3,
        seed=r.randrange(1, 10 ** 6),
        gap_us=round(r.uniform(5.0, 50.0), 1) if i % 3 == 2 else 0.0,
    )
    c["frames"] = 840 if c["gap_us"] else 720
    return c


def run(c, work):
    d = work / f"run{c['i']:03d}"
    if d.exists():
        shutil.rmtree(d)
    subprocess.run([sys.executable, "make_stim.py", "--fs", str(c["fs"]), "--frames", str(c["frames"]),
                    "--pwd", str(c["pwd"]), "--jit", str(c["jit"]), "--ppm", str(c["ppm"]),
                    "--seed", str(c["seed"]), "--out", str(d)],
                   cwd=HERE, check=True, capture_output=True)
    nclk = len((d / "samples.hex").read_text().split())
    opts = [f"-Ptb_core.MAXCLK={nclk + 1000}", f"-Ptb_core.SI_ADDR={c['addr']}",
            f"-Ptb_core.SI_PPM={c['si_ppm']}", f"-Ptb_core.INJ_EARLY={int(c['early'])}"]
    if c["gap_us"]:
        opts += ["-Ptb_core.GAP_AFTER_LOCK_US=2000", f"-Ptb_core.GAP_US={c['gap_us']}"]
    subprocess.run(["iverilog", "-g2012", "-o", str(d / "tb.vvp"), "-s", "tb_core", f"-I{RTL}"] + opts + SRC,
                   cwd=HERE, check=True, capture_output=True)
    subprocess.run(["vvp", "-n", "tb.vvp"], cwd=d, check=True, capture_output=True)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=32)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--base", type=int, default=1000)
    ap.add_argument("--only", type=int, nargs="*", help="run numbers to repeat")
    ap.add_argument("--work", type=Path, default=HERE / "work" / "sweep")
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    cases = [case(i, a.base) for i in range(a.runs) if a.only is None or i in a.only]
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        dirs = list(ex.map(lambda c: run(c, a.work), cases))
    fails = 0
    print(f"{'run':>4} {'Fs':>6} {'PWD':>7} {'jit':>6} {'ring':>8} {'Si514':>6} {'addr':>5} "
          f"{'early':>5} {'gap':>6}  result")
    for c, d in zip(cases, dirs):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            res = {"GAP": cc.check_gap(d, c["fs"])} if c["gap_us"] else full_checks(d)
        bad = [k for k, v in res.items() if not v]
        fails += bool(bad)
        lock = next((l.split()[0] for l in (d / "out_lock.txt").read_text().splitlines()
                     if l.split()[1] == "lock=1"), None)
        note = f"LOCK {int(lock) / 1e9:.2f} ms" if lock else "no LOCK"
        print(f"{c['i']:>4} {c['fs']:>6} {c['pwd']:>+7.3f} {c['jit']:>6.3f} {c['ppm']:>+8.1f} "
              f"{c['si_ppm']:>+6.1f} {c['addr']:>#5x} {'yes' if c['early'] else '-':>5} "
              f"{c['gap_us']:>6.1f}  {'PASS' if not bad else 'FAIL ' + ','.join(bad)}  {note}", flush=True)
        if bad or c["gap_us"]:
            print("      " + buf.getvalue().strip().replace("\n", "\n      "))
        if not bad:
            for f in d.glob("*.hex"):                         # keep failures whole, trim passes
                f.unlink()
            (d / "tb.vvp").unlink(missing_ok=True)
    print(f"\n{len(cases) - fails} of {len(cases)} runs pass"
          + (f", {fails} FAIL (kept in {a.work})" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
