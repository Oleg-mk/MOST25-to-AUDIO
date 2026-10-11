#!/usr/bin/env python3
"""check_image.py - the firmware's coefficient sets through the FPGA engine's model.

test_sound writes two sets. image_example.txt: 48 kHz, volume -20 dB, balance
+4 = R 8 dB down, bass +6 dB, treble -4 dB. This runs it through the
bit-exact model of dsp_core (listener_gw/sim/dsp_asm.py): a sine on stream 0,
both sides, until the gains have glided to their targets, then L and R are
measured. They must be what the settings say, on the same shelves - which
proves the firmware and the gateware agree on the map, the number format and
the arithmetic. image_mix.txt: the amplifier's four sinks mixed - sink 1 on
stream 0 flat at -20 dB, sink 2 on stream 1 (mono, the same sample on both
of its inputs, as amp_out feeds a mono stream) at -10 dB, sink 3 on stream 2
at -26 dB with R 8 dB down, sink 4 (the chimes) on stream 3 at -14 dB; a sine
of its own on each stream, and each must come out of L and R at its level.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "listener_gw" / "sim"))
import dsp_asm as da                                    # noqa: E402
from run_dsp import rbj, mag_db                         # noqa: E402

FS = 48000


def main():
    words = [int(l) for l in (HERE / "image_example.txt").read_text().split("\n")
             if l.strip() and not l.startswith("#")]
    c = words + [0] * (da.C_WORDS - len(words))
    shelves = [rbj("low", FS, 100, 6.0), rbj("high", FS, 10000, -4.0)]
    worst, ok = 0.0, True
    for f in (50, 1000, 12000):
        eng = da.Engine()
        amp = 0.25 * 2 ** 23
        n = 6000                                        # 125 ms: the glide (k = 1/256) settles in ~40 ms
        ys = []
        for i in range(n):
            x = int(round(amp * math.sin(2 * math.pi * f * i / FS)))
            ys.append(eng.run(c, [x, x] + [0] * (2 * da.N_STREAMS - 2)))
        levels = []
        for side in (0, 1):
            sss = scc = ssc = ys_ = yc_ = 0.0
            for i in range(n // 2, n):
                sv, cv = math.sin(2 * math.pi * f * i / FS), math.cos(2 * math.pi * f * i / FS)
                y = ys[i][side]
                sss += sv * sv; scc += cv * cv; ssc += sv * cv; ys_ += y * sv; yc_ += y * cv
            det = sss * scc - ssc * ssc
            a_s, a_c = (ys_ * scc - yc_ * ssc) / det, (yc_ * sss - ys_ * ssc) / det
            levels.append(20 * math.log10(math.hypot(a_s, a_c) / amp))
        tone = sum(mag_db(b, FS, f) for b in shelves)
        want = (-20.0 + tone, -28.0 + tone)
        err = max(abs(levels[0] - want[0]), abs(levels[1] - want[1]))
        worst = max(worst, err)
        print(f"  {f:5d} Hz: L {levels[0]:+.3f} dB (want {want[0]:+.3f}), R {levels[1]:+.3f} dB "
              f"(want {want[1]:+.3f})")
    ok = worst < 0.01
    print(f"engine model: {'PASS' if ok else 'FAIL'}  the firmware's set does what it says, "
          f"within {worst:.4f} dB")
    return 0 if ok and check_mix() else 1


def level_db(ys, side, f, amp, lo, hi):
    """The amplitude of f in ys[lo:hi][side], in dB against amp (least squares on sin, cos)."""
    sss = scc = ssc = ys_ = yc_ = 0.0
    for i in range(lo, hi):
        sv, cv = math.sin(2 * math.pi * f * i / FS), math.cos(2 * math.pi * f * i / FS)
        y = ys[i][side]
        sss += sv * sv; scc += cv * cv; ssc += sv * cv; ys_ += y * sv; yc_ += y * cv
    det = sss * scc - ssc * ssc
    a_s, a_c = (ys_ * scc - yc_ * ssc) / det, (yc_ * sss - ys_ * ssc) / det
    return 20 * math.log10(math.hypot(a_s, a_c) / amp)


def check_mix():
    words = [int(l) for l in (HERE / "image_mix.txt").read_text().split("\n")
             if l.strip() and not l.startswith("#")]
    c = words + [0] * (da.C_WORDS - len(words))
    # a whole number of cycles in the measured half, so the four do not leak into each other
    f0, f1, f2, f3 = 1008, 432, 3008, 2000
    amp = 0.25 * 2 ** 23
    n = 6000
    eng = da.Engine()
    ys = []
    for i in range(n):
        x0 = int(round(amp * math.sin(2 * math.pi * f0 * i / FS)))
        x1 = int(round(amp * math.sin(2 * math.pi * f1 * i / FS)))
        x2 = int(round(amp * math.sin(2 * math.pi * f2 * i / FS)))
        x3 = int(round(amp * math.sin(2 * math.pi * f3 * i / FS)))
        ys.append(eng.run(c, [x0, x0, x1, x1, x2, x2, x3, x3]))
    want = {f0: (-20.0, -20.0), f1: (-10.0, -10.0), f2: (-26.0, -34.0), f3: (-14.0, -14.0)}
    worst = 0.0
    for f, (wl, wr) in want.items():
        got = (level_db(ys, 0, f, amp, n // 2, n), level_db(ys, 1, f, amp, n // 2, n))
        worst = max(worst, abs(got[0] - wl), abs(got[1] - wr))
        print(f"  {f:5d} Hz (stream {[f0, f1, f2, f3].index(f)}): L {got[0]:+.3f} dB (want {wl:+.3f}), "
              f"R {got[1]:+.3f} dB (want {wr:+.3f})")
    ok = worst < 0.01
    print(f"engine model: {'PASS' if ok else 'FAIL'}  the four sinks mixed as the firmware says, "
          f"within {worst:.4f} dB")
    return ok


if __name__ == "__main__":
    sys.exit(main())
