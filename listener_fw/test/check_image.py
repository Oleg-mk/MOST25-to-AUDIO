#!/usr/bin/env python3
"""check_image.py - the firmware's coefficient set through the FPGA engine's model.

test_sound writes one set (image_example.txt: 48 kHz, volume -20 dB, balance
+4 = R 8 dB down, bass +6 dB, treble -4 dB). This runs it through the
bit-exact model of dsp_core (listener_gw/sim/dsp_asm.py): a sine on stream 0,
both sides, until the gains have glided to their targets, then L and R are
measured. They must be what the settings say, on the same shelves - which
proves the firmware and the gateware agree on the map, the number format and
the arithmetic.
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
            ys.append(eng.run(c, [x, x, 0, 0, 0, 0]))
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
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
