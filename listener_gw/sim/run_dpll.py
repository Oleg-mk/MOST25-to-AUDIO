#!/usr/bin/env python3
"""run_dpll.py - the Si514 clock loop against the Si514 model, corner by corner.

Each corner compiles tb_dpll.v with its parameters and runs it for SIM_MS of
simulated time (about 0.4 s of wall time per simulated ms). A corner passes if:
  * the regenerator FIFO never slips (delay stays within +/-600 samples),
  * the loop reports lock, and after lock the delay error stays within
    +/-STEADY samples (1.26 ns each),
  * every small frequency change stays within +/-1000 ppm of the calibrated
    centre (the Si514's glitch-free window), and reg 132's reserved bit
    survives (read-modify-write),
  * the Si514 is centred exactly once (a ring dropout resumes without FCAL),
  * the final M matches the ring: M/M_nom - 1 = DREL - DSI within 2 ppm,
  * the Si514's I2C address, different per corner (first, last and the data
    sheet's example of the range probed), is found by one scan,
  * a disturbed I2C bus (the Si514 ignores its address for 0.6 ms, corner
    48k_i2c_glitch) costs an update or two, not the loop: no re-centring,
    lock kept, and the NACK flag - which holds LOCK off - clear again.

Usage: python run_dpll.py [--only NAME]      needs oss-cad-suite on PATH
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RTL = HERE.parent / "rtl"
SRC = ["tb_dpll.v", "si514_model.v", str(RTL / "dpll.v"), str(RTL / "si514_ctrl.v"),
       str(RTL / "i2c_master.v")]
STEADY = 12

CORNERS = [
    # name              FS       DREL      DSI   SIM_MS  DROP_AT_MS  I2C   GLITCH_AT_MS
    ("48k_nominal",     48000.0, 0.0,      0.0,  150.0,  0.0,        0x55, -1.0),
    ("48k_ring+1000",   48000.0, 1000.0,  -50.0, 150.0,  0.0,        0x08, -1.0),
    ("48k_ring-1000",   48000.0, -1000.0,  50.0, 150.0,  0.0,        0x77, -1.0),
    ("44k1_beat",       44100.0, 10.23,    0.0,  150.0,  0.0,        0x6A, -1.0),
    ("44k1_ring+1000",  44100.0, 1000.0,   50.0, 150.0,  0.0,        0x55, -1.0),
    ("48k_dropout",     48000.0, 300.0,    0.0,  200.0,  90.0,       0x55, -1.0),
    ("48k_i2c_glitch",  48000.0, 200.0,    0.0,  150.0,  0.0,        0x55, 100.0),
    # an off-the-shelf part of the widest stability grade: +/-100 ppm of its own,
    # which the centring cannot see (it assumes the nominal crystal)
    ("48k_si-100",      48000.0, 1000.0, -100.0, 200.0,  0.0,        0x55, -1.0),
    ("44k1_si+100",     44100.0, -1000.0, 100.0, 200.0,  0.0,        0x55, -1.0),
]


def run(name, fs, drel, dsi, sim_ms, drop_at, addr, glitch_at, work):
    d = work / name
    d.mkdir(parents=True, exist_ok=True)
    vvp = d / "tb.vvp"
    params = [f"-Ptb_dpll.FS={fs}", f"-Ptb_dpll.DREL_PPM={drel}", f"-Ptb_dpll.DSI_PPM={dsi}",
              f"-Ptb_dpll.SIM_MS={sim_ms}", f"-Ptb_dpll.DROP_AT_MS={drop_at}",
              f"-Ptb_dpll.SI_ADDR={addr}", f"-Ptb_dpll.GLITCH_AT_MS={glitch_at}"]
    subprocess.run(["iverilog", "-g2012", "-o", str(vvp)] + params + SRC, cwd=HERE, check=True)
    subprocess.run(["vvp", "-n", str(vvp)], cwd=d, check=True, capture_output=True)
    rows, end = [], ""
    for l in (d / "out_dpll.txt").read_text().splitlines():
        if l.startswith("END"):
            end = l
        else:
            t, e, ppm, gear, lk, cen = l.split()
            rows.append((float(t), int(e), float(ppm), int(gear), int(lk), int(cen)))
    kv = dict(x.split("=") for x in end.split()[1:])
    lock_t = next((t for t, e, p, g, lk, c in rows if lk), None)
    # steady state: from 30 ms after the (last) lock, outside any dropout window
    last_lock = None
    for i, r in enumerate(rows):
        if r[4] and (i == 0 or not rows[i - 1][4]):
            last_lock = r[0]
    steady = [e for t, e, p, g, lk, c in rows
              if last_lock is not None and t > last_lock + 30 and lk]
    final_ppm = rows[-1][2] if rows else None
    want_ppm = (1 + drel * 1e-6) / (1 + dsi * 1e-6) * 1e6 - 1e6
    ok = (int(kv["slips"]) == 0 and kv["locked"] == "1" and int(kv["bad_small"]) == 0
          and int(kv["bad_rmw"]) == 0 and int(kv["fcal"]) == 1 and int(kv["nack"]) == 0
          and int(kv["found"]) == addr and int(kv["probes"]) == addr - 0x08
          and int(kv["nackerr"]) == 0 and (glitch_at < 0 or int(kv["glitch"]) > 0)
          and steady and max(abs(x) for x in steady) <= STEADY
          and final_ppm is not None and abs(final_ppm - want_ppm) < 2.0)
    sp = f"{min(steady)}..{max(steady)}" if steady else "-"
    lk = f"{lock_t:.1f}" if lock_t is not None else "never"
    print(f"{'PASS' if ok else 'FAIL'}  {name:15s} lock {lk:>6} ms, max dev {kv['maxdev']:>4}, "
          f"steady {sp:>8} samples, M {final_ppm:+9.2f} ppm (ring {want_ppm:+9.2f}), "
          f"updates {kv['small']}, fcal {kv['fcal']}, slips {kv['slips']}, "
          f"bad_small {kv['bad_small']}, bad_rmw {kv['bad_rmw']}, nack {kv['nack']}, "
          f"I2C 0x{int(kv['found']):02x} found for 0x{addr:02x} after {kv['probes']} probes"
          + (f", glitch refused {kv['glitch']} transfers, NACK flag at the end {kv['nackerr']}"
             if glitch_at >= 0 else ""))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--work", type=Path, default=HERE / "work" / "dpll")
    a = ap.parse_args()
    fails = 0
    for c in CORNERS:
        if a.only and c[0] != a.only:
            continue
        fails += not run(*c, a.work)
    print(f"\n{'all corners pass' if not fails else f'{fails} corner(s) FAIL'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
