#!/usr/bin/env python3
"""dpll_model.py - frame-level model of the Si514 clock loop, for choosing gains.

What is modelled (one step = one ring frame):
  ring      frame starts at k / (Fs (1 + d_ring)) plus Gaussian edge jitter
  sampler   every edge time-stamped on the local 792 Msps grid (27 MHz crystal
            off by d_xtal), floor to the sample - as rx_runlen does
  centring  L64 = 64 frame periods in samples; M_c = M_nom + (L_nom64 - L64) K
  Si514     f_r = FXO (1 + d_si) (M_c + u) / 2^29 / HS; a new u takes effect
            I2C_LAT after the update decision (write + 100 us settling)
  regen     TX frame k leaves 1024 / f_r after frame k-1; the FIFO starts half
            full; |delay - start| beyond FIFO_LIM samples = a slip (failure)
  detector  d_k = TX preamble stamp - RX preamble stamp (both on the sample grid)
  loop      every UPD frames: e = mean(d - target); PI in two gears
            (acquisition, then tracking once |e| < LOCK_E for LOCK_N updates)

Numbers from the Si514 data sheet Rev 1.2: FXO = 31.98 MHz, 0.026 ppb steps,
small changes settle within 100 us, +/-1000 ppm glitch-free window.

Usage: python dpll_model.py            prints a table of corners
"""
import math
import random

FXO = 31.98e6
FS_SAMP = 792e6
PLAN = {48000: (44, 36306575326), 44100: (48, 36389090270)}   # HS_DIV, M x 2^29
LNOM64 = {48000: 1056000.0, 44100: 64 * 792e6 / 44100}
K_CTR = {48000: 34381, 44100: 31660}                           # LSB per sample of L64

UPD = 24               # frames per loop update (0.50 ms at 48 kHz, 0.54 ms at 44.1)
I2C_LAT = 0.28e-3      # decision -> new frequency: 5-byte burst at 400 kHz + 100 us
FIFO_LIM = 600         # samples either side of the start point before a slip
SHIFT_E = 2           # |e| < 2 samples for LOCK_N updates -> tracking gear
LOCK_E, LOCK_N = 8, 16 # |e| < 8 samples for 16 more updates -> locked


def gains(fn_hz, zeta, fs):
    """PI gains in LSB per sample (per update for the integral) for a type-II
    loop with natural frequency fn and damping zeta."""
    hs, mfix = PLAN[fs]
    kd = FS_SAMP / mfix                     # samples/s of phase drift per LSB of u
    wn = 2 * math.pi * fn_hz
    t_up = UPD / fs
    return 2 * zeta * wn / kd, wn * wn / kd * t_up


def run(fs, d_ring_ppm, d_xtal_ppm, d_si_ppm, jit_ns=0.5, secs=0.6, acq=(40, 1.0),
        trk=(2.0, 1.0), seed=1):
    rnd = random.Random(seed)
    hs, mfix_nom = PLAN[fs]
    t_frame = 1.0 / (fs * (1 + d_ring_ppm * 1e-6))
    samp = FS_SAMP * (1 + d_xtal_ppm * 1e-6)

    def stamp(t):
        return math.floor((t + rnd.gauss(0, jit_ns * 1e-9)) * samp)

    # centring from 64 frames, measured on the local crystal
    l64 = stamp(64 * t_frame) - stamp(0.0)
    u0 = round((LNOM64[fs] - l64) * K_CTR[fs])
    mfix_c = mfix_nom + u0
    fxo = FXO * (1 + d_si_ppm * 1e-6)

    def f_r(u):
        return fxo * (mfix_c + u) / 2 ** 29 / hs

    kp_a, ki_a = gains(*acq, fs)
    kp_t, ki_t = gains(*trk, fs)
    n = int(secs * fs)
    u_now, u_next, t_apply = 0.0, 0.0, None
    integ = 0.0
    gear, good, locked_at = 0, 0, None
    t_rx0 = 0.0
    t_tx = t_rx0 + 1.0e-6                   # regenerator starts ~1 us behind, half full
    target = None
    acc, cnt = 0.0, 0
    max_dev, slip = 0.0, False
    trace = []
    for k in range(n):
        t_rx = t_rx0 + k * t_frame
        if k:
            t_tx += 1024.0 / f_r(u_now)
        if t_apply is not None and t_tx >= t_apply:
            u_now, t_apply = u_next, None
        d = stamp(t_tx) - stamp(t_rx)
        if target is None:
            target = d
        e = d - target
        max_dev = max(max_dev, abs(e))
        if abs(e) > FIFO_LIM:
            slip = True
            break
        acc += e
        cnt += 1
        if cnt == UPD:
            ea = acc / cnt
            acc, cnt = 0.0, 0
            kp, ki = (kp_a, ki_a) if gear == 0 else (kp_t, ki_t)
            integ += ki * ea
            u_next = kp * ea + integ
            t_apply = t_tx + I2C_LAT
            good = good + 1 if abs(ea) < (LOCK_E if gear else SHIFT_E) else 0
            if good >= LOCK_N:
                if gear == 0:
                    # bumpless: the acquisition gear's proportional term moves
                    # into the integrator, so u does not jump at the switch
                    integ += kp_a * ea - kp_t * ea
                    gear, good = 1, 0
                elif locked_at is None:
                    locked_at = k / fs
            trace.append((k / fs, ea, u_next / (mfix_c * 1e-6)))
    tail = [e for (t, e, u) in trace if t > secs / 2]         # steady state
    if locked_at is None:
        tail = []
    return dict(slip=slip, max_dev=max_dev, locked_at=locked_at,
                tail_pp=(max(tail) - min(tail) if tail else None), u0_ppm=u0 / (mfix_nom * 1e-6),
                trace=trace)


def main():
    print(f"{'Fs':>6} {'ring':>6} {'xtal':>5} {'Si514':>6} | {'centre ppm':>10} {'max |e|':>8} "
          f"{'locked s':>8} {'steady pp':>9}  (e in 1.26 ns samples; steady = 2nd half)")
    worst = 0
    for fs in (48000, 44100):
        for d_ring in (-1000, -45.45, 0, 400, 1000):
            for d_x, d_s in ((50, -50), (-50, 50), (0, 0)):
                r = run(fs, d_ring, d_x, d_s)
                worst = max(worst, r["max_dev"])
                lk = f"{r['locked_at']:.3f}" if r["locked_at"] is not None else "never"
                tp = f"{r['tail_pp']:.2f}" if r["tail_pp"] is not None else "-"
                print(f"{fs:>6} {d_ring:>6} {d_x:>5} {d_s:>6} | {r['u0_ppm']:>10.1f} "
                      f"{r['max_dev']:>8.0f} {lk:>8} {tp:>8} {'SLIP' if r['slip'] else ''}")
    print(f"worst excursion {worst:.0f} samples of {FIFO_LIM} allowed")


if __name__ == "__main__":
    main()
