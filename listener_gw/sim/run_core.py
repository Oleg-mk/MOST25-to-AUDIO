#!/usr/bin/env python3
"""run_core.py - the whole listener_core, corner by corner: stimulus, simulation, checks.

Corners (stimulus from make_stim.py, simulation tb_core.v, checks check_core.py):
  core48     48 kHz ring, PWD +0.316 UI, jitter 0.195 UI, 0 ppm, 240 frames:
             every check in check_core.py must pass
  core44     44.1 kHz ring, PWD -0.15 UI, jitter 0.195 UI, -1000 ppm, 240 frames:
             every check must pass
  pre2       core48 with S/PDIF-like preambles (3-3-1-1, block start 3-1-1-3: two
             3-UI runs in one preamble): every check must pass. The design as
             first written took the second 3-UI run for a lost frame and never
             injected; the clock loop saw two events per frame
  mut_nofix  core48 with the injector's parity fix turned off (NOFIX): INJ must
             FAIL and nothing else - proof that the injection check sees parity
  inj_early  core48 with "inject" sent before the Si514 is centred: the ring
             domain is reset under the command, which must survive it (every
             check must pass; the injector as first written lost the command)
  gap        48 kHz ring, PWD +0.2 UI, 480 frames, the line dead for 20 us 2 ms
             after LOCK (placed by the tb, wherever LOCK comes): LOCK must drop
             within 5 us, come back after the line returns, and the Si514 must
             not be centred a second time
  fb_dead    core48, but TX_FB dies 200 us after LOCK and stays dead (U9's
             output stuck): LOCK must drop within 4 ring frames and stay off
  clk_stop   core48, but clk_s stops 300 us after LOCK (PLL or crystal dead):
             LOCK stays on - no clk_s logic can help - and the board's watchdog
             (U11, modelled in tb_core.v) must take the ring to bypass: TX
             stops toggling within 3 us, TX_SEL falls within 13 us
  bit_err    core48 without injection, one edge of the line removed in frame
             120 (two runs merge into one of a wrong length, 1 ms after LOCK):
             LOCK must stay on to the end, the regenerated line must equal the
             ring's fault included, TDM must lose that one frame and nothing
             else, the UART must carry good blocks again after the damaged one.
             As first written, the framer unlocked on the first error, the
             regenerator emptied its FIFO and LOCK fell for HOLD_RE
The seven simulations run in parallel (a few minutes of wall time); on
this machine run them one at a time: --only NAME.

Usage: python run_core.py [--only NAME]      needs oss-cad-suite on PATH
"""
import argparse
import subprocess
import sys
from pathlib import Path

import check_core as cc

HERE = Path(__file__).resolve().parent
RTL = HERE.parent / "rtl"
SRC = ["tb_core.v", "si514_model.v"] + [str(RTL / f) for f in (
    "rx_runlen.v", "rx_classify.v", "rx_framer.v", "fs_fine.v", "regen.v", "tdm_out.v",
    "ctrl_uart.v", "uart_rx.v", "host_cmd.v", "dsp_core.v", "amp_out.v", "inject.v", "i2c_master.v",
    "si514_ctrl.v", "tx_pre.v", "dpll.v", "listener_core.v")]

CORNERS = [
    # name        stimulus (make_stim.py)                                    compile options
    ("core48",    ["--fs", "48000", "--frames", "240", "--pwd", "0.316", "--jit", "0.195",
                   "--ppm", "0", "--seed", "7"], []),
    ("core44",    ["--fs", "44100", "--frames", "240", "--pwd", "-0.15", "--jit", "0.195",
                   "--ppm", "-1000", "--seed", "11"], []),
    ("pre2",      ["--fs", "48000", "--frames", "240", "--pwd", "0.316", "--jit", "0.195",
                   "--ppm", "0", "--seed", "7", "--preamble", "spdif"], []),
    ("mut_nofix", ["--fs", "48000", "--frames", "240", "--pwd", "0.316", "--jit", "0.195",
                   "--ppm", "0", "--seed", "7"], ["-DNOFIX"]),
    ("inj_early", ["--fs", "48000", "--frames", "240", "--pwd", "0.316", "--jit", "0.195",
                   "--ppm", "0", "--seed", "7"], ["-Ptb_core.INJ_EARLY=1"]),
    ("gap",       ["--fs", "48000", "--frames", "480", "--pwd", "0.2", "--jit", "0.195",
                   "--ppm", "0", "--seed", "5"], ["-Ptb_core.MAXCLK=1100000",
                                                  "-Ptb_core.GAP_AFTER_LOCK_US=2000",
                                                  "-Ptb_core.GAP_US=20"]),
    ("fb_dead",   ["--fs", "48000", "--frames", "240", "--pwd", "0.316", "--jit", "0.195",
                   "--ppm", "0", "--seed", "7"], ["-Ptb_core.FB_DEAD_AFTER_LOCK_US=200"]),
    ("clk_stop",  ["--fs", "48000", "--frames", "240", "--pwd", "0.316", "--jit", "0.195",
                   "--ppm", "0", "--seed", "7"], ["-Ptb_core.CLKS_STOP_AFTER_LOCK_US=300"]),
    ("bit_err",   ["--fs", "48000", "--frames", "240", "--pwd", "0.316", "--jit", "0.195",
                   "--ppm", "0", "--seed", "7", "--kill-edge-frame", "120"], ["-Ptb_core.NO_INJECT=1"]),
]


def prepare(name, stim, opts, work):
    d = work / name
    subprocess.run([sys.executable, "make_stim.py"] + stim + ["--out", str(d)], cwd=HERE,
                   check=True, capture_output=True)
    vvp = d / "tb.vvp"
    subprocess.run(["iverilog", "-g2012", "-o", str(vvp), "-s", "tb_core", f"-I{RTL}"] + opts + SRC,
                   cwd=HERE, check=True)
    return d


def full_checks(d):
    truth = [l.strip() for l in (d / "frames.hex").read_text().split()]
    runs = [int(x, 16) for x in (d / "runs.hex").read_text().split()]
    cc.d_truth_ref = truth
    left = cc.as_left(d, truth)                      # the frames as they left us: J2/J3's truth
    names = ["SI", "TX", "TDM", "UART", "MCLK", "I2S", "INJ", "FS", "WD"]
    res = [cc.check_si514(d), cc.check_tx(d, runs), cc.check_tdm(d, left),
           cc.check_uart(d, truth), cc.check_mclk(d), cc.check_i2s(d, left),
           cc.check_inject(d, truth), cc.check_fs(d), cc.check_wd(d)]
    return dict(zip(names, res))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--work", type=Path, default=HERE / "work")
    a = ap.parse_args()
    todo = [c for c in CORNERS if not a.only or c[0] == a.only]
    dirs = {name: prepare(name, stim, opts, a.work) for name, stim, opts in todo}
    procs = {name: subprocess.Popen(["vvp", "-n", "tb.vvp"], cwd=d, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
             for name, d in dirs.items()}
    for p in procs.values():
        p.wait()
    fails = 0
    for name, d in dirs.items():
        print(f"== {name}")
        if name == "gap":
            ok = cc.check_gap(d, 48000) & cc.check_wd(d)
        elif name == "fb_dead":
            ok = cc.check_fbdead(d, 48000) & cc.check_wd(d)
        elif name == "clk_stop":
            ok = cc.check_clkstop(d)
        elif name == "bit_err":
            ok = cc.check_err(d, 48000) & cc.check_wd(d)
        else:
            r = full_checks(d)
            if name == "mut_nofix":
                ok = not r["INJ"] and all(v for k, v in r.items() if k != "INJ")
                print(f"MUT : {'PASS' if ok else 'FAIL'}  with the parity fix off, INJ "
                      f"{'fails and nothing else does' if ok else 'is not the only failure'}")
            else:
                ok = all(r.values())
        fails += not ok
    print(f"\n{'all corners pass' if not fails else f'{fails} corner(s) FAIL'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
