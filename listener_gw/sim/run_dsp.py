#!/usr/bin/env python3
"""run_dsp.py - amp_out / dsp_core against the bit-exact model in dsp_asm.py.

RTL (tb_dsp.v), per corner (48 and 44.1 kHz):
  * four sources in the frame: stream 0 stereo 24 bit, stream 1 mono 16 bit,
    stream 2 stereo 16 bit, stream 3 mono 16 bit; later stream 0 moves to
    other bytes at 16 bit, and streams 1 and 3 turn stereo (16 and 24 bit),
    each side its own signal, so every one of the eight inputs is told apart;
  * four coefficient sets, each written word by word with its own tag and
    committed with its last word: straight through; tone (bass shelf +10 dB,
    treble shelf -6 dB, a peak) with volume, balance, navigation and stream 3
    mixed in, gains gliding (k = 1/64); saturation everywhere (outputs clip, a
    biquad chain overflows); back to straight through. Refused commands in
    between: a word at address 70, a position of width 1, positions with a
    reserved bit set (P[3], P[6]). Sets that must NOT go live: one with a word
    lost on the way (committed all the same), a set whose commit was lost
    followed by another set with a word lost - with tags left out, the first
    set's word filled the second's gap and the mix went live - and, last, an
    old host's set of 47 words with the commit on word 46. A stray word of a
    tag never committed sits in between.
  Checks:
  PICK   every engine run starts on exactly the bytes of the last frame, with
         the positions, widths and mono flags that frame was collected with;
         the refused position commands never took effect
  BANK   words land only in the bank not in use; a run uses one bank from
         start to end; each switch is in use from the next run on
  TXN    the banks switch exactly for the whole sets, and the bank switched to
         holds that set, word for word, at every address of the set
  MODEL  every run's two outputs equal the model's, bit for bit
  I2S    SD carries each run's L R, frame after frame
  TIME   no run missed its frame
Model only (no RTL), what the numbers can do:
  RESP   a sine through bass/treble shelves comes out as the design says
  NOISE  a -60 dBFS tone through a +12 dB shelf at 40 Hz (poles near z = 1):
         the error against double precision, with and without fraction saving

Usage: python run_dsp.py [--only NAME]        needs oss-cad-suite on PATH
"""
import argparse
import math
import random
import subprocess
import sys
from pathlib import Path

import dsp_asm as da

HERE = Path(__file__).resolve().parent
RTL = HERE.parent / "rtl"
SRC = ["tb_dsp.v", str(RTL / "amp_out.v"), str(RTL / "dsp_core.v"), str(RTL / "spdif_tx.v")]
GAP = 1500                  # clk_s between commands (15 us; the UART's is 37 us)


# ------------------------------------------------------------- filters
def rbj(kind, fs, f0, gain_db=0.0, q=0.7071):
    """RBJ cookbook biquad (b0, b1, b2, a1, a2), a0 normalised to 1."""
    a = 10 ** (gain_db / 40)
    w = 2 * math.pi * f0 / fs
    cw, sw = math.cos(w), math.sin(w)
    al = sw / (2 * q)
    if kind == "peak":
        b = (1 + al * a, -2 * cw, 1 - al * a); d = (1 + al / a, -2 * cw, 1 - al / a)
    elif kind == "low":
        s = 2 * math.sqrt(a) * al
        b = (a * ((a + 1) - (a - 1) * cw + s), 2 * a * ((a - 1) - (a + 1) * cw), a * ((a + 1) - (a - 1) * cw - s))
        d = ((a + 1) + (a - 1) * cw + s, -2 * ((a - 1) + (a + 1) * cw), (a + 1) + (a - 1) * cw - s)
    elif kind == "high":
        s = 2 * math.sqrt(a) * al
        b = (a * ((a + 1) + (a - 1) * cw + s), -2 * a * ((a - 1) + (a + 1) * cw), a * ((a + 1) + (a - 1) * cw - s))
        d = ((a + 1) - (a - 1) * cw + s, 2 * ((a - 1) - (a + 1) * cw), (a + 1) - (a - 1) * cw - s)
    else:
        raise ValueError(kind)
    return (b[0] / d[0], b[1] / d[0], b[2] / d[0], d[1] / d[0], d[2] / d[0])


def mag_db(bq, fs, f):
    z = complex(math.cos(2 * math.pi * f / fs), math.sin(2 * math.pi * f / fs))
    b0, b1, b2, a1, a2 = bq
    h = (b0 + b1 / z + b2 / z ** 2) / (1 + a1 / z + a2 / z ** 2)
    return 20 * math.log10(abs(h))


# ------------------------------------------------------------- stimulus
S0A = (9, 10, 11, 12, 13, 14)       # stream 0, 24 bit
S0B = (40, 41, 42, 43)              # stream 0 later, 16 bit
S1 = (20, 21, 22, 23)               # stream 1, L R 16 bit (mono: L alone)
S2 = (30, 31, 32, 33)               # stream 2, 16 bit
S3 = (50, 51, 52, 53, 54, 55)       # stream 3, L R 24 bit (mono 16 bit: L0 L1 alone)


def put(fr, pos, v, nbytes):
    v &= (1 << (8 * nbytes)) - 1
    for i in range(nbytes):
        fr[pos[i]] = (v >> (8 * (nbytes - 1 - i))) & 0xFF


def frames(n, fs, rnd):
    out = []
    for i in range(n):
        fr = [rnd.randrange(256) for _ in range(64)]
        l = int(0.45 * 2 ** 23 * math.sin(2 * math.pi * 1000 * i / fs)) + rnd.randrange(-300, 300)
        r = int(0.60 * 2 ** 23 * math.sin(2 * math.pi * 3300 * i / fs + 1.0)) + rnd.randrange(-300, 300)
        put(fr, S0A[0:3], l, 3); put(fr, S0A[3:6], r, 3)
        put(fr, S0B[0:2], int(0.7 * 2 ** 15 * math.sin(2 * math.pi * 200 * i / fs)), 2)
        put(fr, S0B[2:4], int(-0.7 * 2 ** 15 * math.sin(2 * math.pi * 7000 * i / fs)), 2)
        put(fr, S1[0:2], int(0.3 * 2 ** 15 * math.sin(2 * math.pi * 440 * i / fs)), 2)
        put(fr, S1[2:4], int(0.25 * 2 ** 15 * math.sin(2 * math.pi * 5100 * i / fs)), 2)
        put(fr, S2[0:2], rnd.randrange(-2 ** 14, 2 ** 14), 2)
        put(fr, S2[2:4], rnd.randrange(-2 ** 14, 2 ** 14), 2)
        put(fr, S3[0:3], int(0.5 * 2 ** 23 * math.sin(2 * math.pi * 1800 * i / fs)), 3)
        put(fr, S3[3:6], int(-0.4 * 2 ** 23 * math.sin(2 * math.pi * 2700 * i / fs)), 3)
        out.append(fr)
    return out


def cmd01(s, width, mono, l, r=(0, 0, 0)):
    p0 = (s << 4) | (4 if mono else 0) | {0: 0, 16: 2, 24: 3}[width]
    l = list(l) + [0] * (3 - len(l)); r = list(r) + [0] * (3 - len(r))
    return [1, p0] + l + r


def cmd03(addr, value, commit=False, p6=0):
    v = value & 0xFFFFFFFF
    return [3, addr, v >> 24, (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF, 1 if commit else 0, p6]


def image_cmds(c, tag, lose=()):
    """A set's words under one tag, the commit with the last; the addresses in `lose` never arrive."""
    return [cmd03(a, c[a], commit=(a == da.C_1MK), p6=tag) for a in range(da.C_1MK + 1) if a not in lose]


def schedule(fs):
    """(delay in clk_s, command) and the list of sets in commit order."""
    straight = da.image(gains={(0, 0): 1.0, (0, 1): 1.0, (1, 0): 0.25, (2, 1): 0.125, (3, 0): 0.2, (3, 1): 0.3},
                        k=1.0)
    vol = 10 ** (-12 / 20)
    tone = da.image(bq=[rbj("low", fs, 100, 10.0), rbj("high", fs, 8000, -6.0),
                        rbj("peak", fs, 2500, 4.0, 1.4)],
                    gains={(0, 0): vol, (0, 1): vol * 0.7, (1, 0): 0.4, (1, 1): 0.4, (3, 0): 0.5, (3, 1): 0.5},
                    k=1 / 64)
    boost = (7.9, 0.0, 0.0, 0.0, 0.0)
    clip = da.image(bq=[boost, boost], gains={(0, 0): 6.0, (0, 1): -6.0, (2, 0): 7.9, (3, 1): -7.9}, k=1.0)
    sets = [straight, tone, clip, straight]
    seq = [(5000, cmd01(0, 24, False, S0A[0:3], S0A[3:6])),
           (GAP, cmd01(1, 16, True, S1[0:2])),
           (GAP, cmd01(2, 16, False, S2[0:2], S2[2:4])),
           (GAP, cmd01(3, 16, True, S3[0:2])),
           (GAP, [1, 0x31] + [1] * 6),                              # width 1: refused
           (GAP, [1, 0x0A] + [1] * 6),                              # P[3] set: refused
           (GAP, [1, 0x42] + [1] * 6)]                              # P[6] set: refused
    seq += [(GAP, c) for c in image_cmds(sets[0], 1)]
    seq.append((150000, cmd03(70, 0x10000000)))                     # address 70: refused
    seq += [(GAP, c) for c in image_cmds(sets[1], 2)]
    seq.append((GAP, cmd03(5, 0x10000000, p6=9)))                   # a stray word, tag 9: never committed
    seq.append((150000, cmd01(0, 16, False, S0B[0:2], S0B[2:4])))
    seq.append((GAP, cmd01(1, 16, False, S1[0:2], S1[2:4])))       # streams 1 and 3 turn stereo
    seq.append((GAP, cmd01(3, 24, False, S3[0:3], S3[3:6])))
    seq += [(GAP, c) for c in image_cmds(sets[2], 3, lose=(7,))]    # a word lost: must not go live
    seq += [(60000, c) for c in image_cmds(sets[2], 4)[:1]]
    seq += [(GAP, c) for c in image_cmds(sets[2], 4)[1:]]           # the whole set: live
    seq += [(150000, c) for c in image_cmds(sets[3], 5, lose=(da.C_1MK,))]   # its commit lost...
    seq += [(GAP, c) for c in image_cmds(sets[1], 6, lose=(12,))]   # ...then a set with a gap: not live
    seq += [(60000, c) for c in image_cmds(sets[3], 7)[:1]]
    seq += [(GAP, c) for c in image_cmds(sets[3], 7)[1:]]
    # an old host's set, as it was before stream 3: 47 words, the commit on word 46 - not live
    old = [cmd03(a, sets[1][a], commit=(a == 46), p6=8) for a in range(47)]
    seq += [(60000, old[0])] + [(GAP, c) for c in old[1:]]
    # the commits that must switch, by tag, and the set each one puts in use
    live = {1: sets[0], 2: sets[1], 4: sets[2], 7: sets[3]}
    return seq, sets, live


# --------------------------------------------------------------- checks
def s24(v):
    return v - (1 << 24) if v >> 23 else v


def expect_in(fr, pos, wid, mon):
    out = []
    for s in range(4):
        p = pos[6 * s:6 * s + 6]
        w = wid[s]
        if w == 3:
            l = fr[p[0]] << 16 | fr[p[1]] << 8 | fr[p[2]]; r = fr[p[3]] << 16 | fr[p[4]] << 8 | fr[p[5]]
        elif w == 2:
            l = fr[p[0]] << 16 | fr[p[1]] << 8; r = fr[p[3]] << 16 | fr[p[4]] << 8
        else:
            l = r = 0
        out += [s24(l), s24(l if mon[s] else r)]
    return out


def run_corner(name, fs, work):
    d = work / name
    d.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(1 if fs == 48000 else 2)
    seq, sets, live = schedule(fs)
    nfr = int(sum(dl + 1 for dl, _ in seq) / 99e6 * fs) + 120      # the whole schedule and a margin
    frs = frames(nfr, fs, rnd)
    (d / "frames.hex").write_text("\n".join(f"{b:02x}" for fr in frs for b in fr) + "\n")
    (d / "cmds.hex").write_text("\n".join(" ".join(f"{x:08x}" for x in [dl] + c) for dl, c in seq) + "\n")
    vvp = d / "tb.vvp"
    subprocess.run(["iverilog", "-g2012", "-o", str(vvp), f"-Ptb_dsp.FS={fs}", f"-Ptb_dsp.NFRAMES={nfr}", f"-Ptb_dsp.NCMD={len(seq) + 8}",
                    f"-I{RTL}"] + SRC, cwd=HERE, check=True)
    subprocess.run(["vvp", "-n", str(vvp)], cwd=d, check=True, capture_output=True)

    flog = {}
    for l in (d / "out_frames.txt").read_text().split("\n"):
        if l.startswith("F "):
            v = list(map(int, l.split()[1:]))
            flog[v[0]] = (v[1:25], v[25:29], v[29:33])
    S, E, W, K, ev, errs = {}, {}, [], [], [], []
    for l in (d / "out_engine.txt").read_text().split("\n"):
        t = l.split()
        if not t:
            continue
        if t[0] == "S":
            h = int(t[3], 16)
            S[int(t[1])] = (int(t[2]), [s24((h >> (24 * (7 - k))) & 0xFFFFFF) for k in range(8)])
        elif t[0] == "E":
            h = int(t[2], 16)
            E[int(t[1])] = ([s24((h >> (24 * (1 - k))) & 0xFFFFFF) for k in range(2)], int(t[3]))
        elif t[0] == "W":
            W.append(tuple(map(int, t[1:])))
            ev.append(("W", W[-1]))
        elif t[0] == "K":
            K.append(tuple(map(int, t[1:])))
            ev.append(("K", K[-1]))
        else:
            errs.append(l)
    ok_all = True

    # PICK
    bad = 0
    for n, (lf, ins) in S.items():
        if lf >= 0 and ins != expect_in(frs[lf], *flog[lf]):
            bad += 1
    # every frame was collected with a configuration that was sent (or none yet)
    mono1, st1 = (S1[0:2] + (0,) * 4, 2, 1), (S1[0:2] + (0,) + S1[2:4] + (0,), 2, 0)
    mono3, st3 = (S3[0:2] + (0,) * 4, 2, 1), (S3, 3, 0)
    valid = [{((0,) * 6, 0, 0), (S0A, 3, 0), (S0B[0:2] + (0,) + S0B[2:4] + (0,), 2, 0)},
             {((0,) * 6, 0, 0), mono1, st1},
             {((0,) * 6, 0, 0), (S2[0:2] + (0,) + S2[2:4] + (0,), 2, 0)},
             {((0,) * 6, 0, 0), mono3, st3}]
    stray = sum(1 for pos, wid, mon in flog.values() for s in range(4)
                if (tuple(pos[6 * s:6 * s + 6]), wid[s], mon[s]) not in valid[s])
    seen = {(tuple(pos[0:6]), wid[0]) for pos, wid, _ in flog.values()}
    seen1 = {(tuple(pos[6:12]), wid[1], mon[1]) for pos, wid, mon in flog.values()}
    seen3 = {(tuple(pos[18:24]), wid[3], mon[3]) for pos, wid, mon in flog.values()}
    ok = (bad == 0 and stray == 0 and len(S) > nfr - 5 and (S0B[0:2] + (0,) + S0B[2:4] + (0,), 2) in seen
          and {mono1, st1} <= seen1 and {mono3, st3} <= seen3)
    print(f"  PICK : {'PASS' if ok else 'FAIL'}  {len(S)} runs, {bad} on wrong samples; streams 1 and 3 "
          f"seen mono and stereo; {stray} stream settings never sent (the refused positions among them)")
    ok_all &= ok

    # BANK: every accepted word, where it went; which bank each run used
    sent = [c for _, c in seq if c[0] == 3 and c[1] < 64]
    ok = len(W) == len(sent) and all(w[2] < 64 for w in W)
    commits = [w for w in W if w[4]]
    for i, sw in enumerate(K):
        # runs starting after the switch, and before the next one, use its bank (it may take one run)
        after = [n for n in E if n > sw[0] + 1 and (i + 1 == len(K) or n <= K[i + 1][0])]
        if any(E[n][1] != sw[1] for n in after):
            ok = False
    into_use = sum(1 for w in W if w[1] == w[5])      # written into the bank the engine was using
    ok &= into_use == 0 and not any(e.startswith("BANKERR") for e in errs)
    print(f"  BANK : {'PASS' if ok else 'FAIL'}  {len(W)} words accepted of {len(sent)} valid sent, "
          f"{len(commits)} commits, {len(K)} switches; {into_use} written into the bank in use; "
          f"refused ones not written")
    ok_all &= ok

    # TXN: which commits switched, and what the bank switched to held
    def s32(v):
        v &= 0xFFFFFFFF
        return v - (1 << 32) if v >> 31 else v
    banks = [[0] * 64, [0] * 64]
    last_tag, switched, wrong = None, [], 0
    for kind, e in ev:
        if kind == "W":
            banks[e[1]][e[2]] = e[3]
            if e[4]:
                last_tag = e[6]
        else:
            switched.append(last_tag)
            want = live.get(last_tag)
            if want is None or banks[e[1]][:da.C_1MK + 1] != [s32(want[a]) for a in range(da.C_1MK + 1)]:
                wrong += 1
    ok = switched == sorted(live) and wrong == 0
    print(f"  TXN  : {'PASS' if ok else 'FAIL'}  switched for tags {switched} (whole sets {sorted(live)}); "
          f"{wrong} switched to a bank that was not the set; the set with a lost word, the gap after "
          f"a lost commit and the old host's 47 words stayed out")
    ok_all &= ok

    # MODEL
    eng = da.Engine()
    banks = [[0] * 64, [0] * 64]
    wi, bad, first_bad = 0, 0, None
    outs = {}
    for n in sorted(S):
        while wi < len(W) and W[wi][0] < n:
            _, bank, addr, val, _, _, _ = W[wi]
            banks[bank][addr] = val
            wi += 1
        if n not in E:
            break
        got = eng.run(banks[E[n][1]], S[n][1])
        outs[n] = got
        if got != E[n][0]:
            bad += 1
            if first_bad is None:
                first_bad = (n, got, E[n][0])
    ok = bad == 0 and len(outs) > nfr - 5 and eng.sat_str > 0 and eng.sat_out > 0
    print(f"  MODEL: {'PASS' if ok else 'FAIL'}  {len(outs)} runs, {bad} differ; saturated on the way "
          f"{eng.sat_str} times, at the output {eng.sat_out} times"
          + (f"; first at run {first_bad[0]}: model {first_bad[1]} rtl {first_bad[2]}" if first_bad else ""))
    ok_all &= ok

    # I2S
    rows = [l.strip() for l in (d / "out_i2s.txt").read_text().split("\n") if l.strip()]
    rows = [r for r in rows if "x" not in r and "z" not in r]
    fr_io = []
    for i in range(1, len(rows) - 64):
        if rows[i - 1][0] == "1" and rows[i][0] == "0":
            f = rows[i:i + 64]
            if all(f[s][0] == ("0" if s < 32 else "1") for s in range(64)):
                b0 = [int(f[s][1]) for s in range(1, 64)] + [0]
                w0 = [int("".join(map(str, b0[:32])), 2), int("".join(map(str, b0[32:])), 2)]
                if any(w & 0xFF for w in w0):
                    fr_io.append(None)
                else:
                    fr_io.append([s24(w >> 8) for w in w0])
    seqE = [E[n][0] for n in sorted(E)]
    # align: find the first decoded frame equal to some run's outputs, then walk on
    bad, start = 0, None
    for j in range(len(fr_io)):
        for m in range(len(seqE)):
            if fr_io[j] == seqE[m] and any(v != 0 for v in seqE[m]):
                start = (j, m)
                break
        if start:
            break
    n_cmp = 0
    if start:
        j, m = start
        while j < len(fr_io) and m < len(seqE):
            if fr_io[j] != seqE[m]:
                bad += 1
            j += 1; m += 1; n_cmp += 1
    ok = start is not None and bad == 0 and n_cmp > nfr - 60
    print(f"  I2S  : {'PASS' if ok else 'FAIL'}  {n_cmp} frames on SD compared with the runs, {bad} differ")
    ok_all &= ok

    ok = not any(e.startswith("OVERRUN") for e in errs)
    print(f"  TIME : {'PASS' if ok else 'FAIL'}  program {da.cycles(da.program())} of 1024 clocks; "
          f"{'no overrun' if ok else 'OVERRUN'}")
    ok_all &= ok

    return ok_all


# ----------------------------------------------------- model-only checks
def model_resp(fs):
    bq = [rbj("low", fs, 100, 10.0), rbj("high", fs, 8000, -6.0)]
    c = da.image(bq=bq, gains={(0, 0): 1.0, (0, 1): 1.0}, k=1.0)
    worst = 0.0
    for f in (50, 100, 300, 1000, 5000, 8000, 15000):
        eng = da.Engine()
        n = int(fs * 0.2)
        amp = 0.2 * 2 ** 23
        ys = []
        for i in range(n):
            x = int(round(amp * math.sin(2 * math.pi * f * i / fs)))
            ys.append(eng.run(c, [x, x] + [0] * (2 * da.N_STREAMS - 2))[0])
        # least-squares sine at f over the second half (settled)
        sss = scc = ssc = ys_ = yc_ = 0.0
        for i in range(n // 2, n):
            sv, cv = math.sin(2 * math.pi * f * i / fs), math.cos(2 * math.pi * f * i / fs)
            sss += sv * sv; scc += cv * cv; ssc += sv * cv; ys_ += ys[i] * sv; yc_ += ys[i] * cv
        det = sss * scc - ssc * ssc
        si = (ys_ * scc - yc_ * ssc) / det
        co = (yc_ * sss - ys_ * ssc) / det
        got = 20 * math.log10(math.hypot(si, co) / amp)
        want = sum(mag_db(b, fs, f) for b in bq)
        worst = max(worst, abs(got - want))
    ok = worst < 0.01
    print(f"  RESP : {'PASS' if ok else 'FAIL'}  shelves +10 dB / 100 Hz and -6 dB / 8 kHz, 7 frequencies: "
          f"largest error {worst:.4f} dB")
    return ok


def model_noise(fs):
    bq = rbj("low", fs, 40, 12.0)
    c = da.image(bq=[bq], gains={(0, 0): 1.0}, k=1.0)
    n = int(fs * 1.0)
    amp = 2 ** 23 * 10 ** (-60 / 20)
    xs = [int(round(amp * math.sin(2 * math.pi * 997 * i / fs))) for i in range(n)]

    def ref():
        b0, b1, b2, a1, a2 = [da.q28(v) / da.ONE for v in bq[:3]] + [-da.q28(-v) / da.ONE for v in bq[3:]]
        x1 = x2 = y1 = y2 = 0.0
        out = []
        for x in xs:
            xv = x / 2 ** 23
            y = b0 * xv + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1, y2, y1 = x1, xv, y1, y
            out.append(y)
        return out

    r = ref()

    def err(fraction_saving):
        eng = da.Engine()
        e2 = 0.0
        # compare before the 24-bit output rounding: read the last node directly
        for i, x in enumerate(xs):
            if not fraction_saving:     # every remainder dropped: plain truncation
                for side in (0, 1):
                    for bb in range(da.N_BQ):
                        eng.d[da.d_rem(side, bb)] = 0
            eng.run(c, [x, x] + [0] * (2 * da.N_STREAMS - 2))
            y = da.s32(eng.d[da.d_node(0, da.N_BQ, 1)]) / da.ONE      # moved to d1 at the end of the run
            if i > fs // 4:
                e2 += (y - r[i]) ** 2
        return 10 * math.log10(e2 / (n - fs // 4) + 1e-300)

    with_fs, without = err(True), err(False)
    ok = with_fs < -144     # below the 24-bit output's own rounding (-151 dBFS rms)
    print(f"  NOISE: {'PASS' if ok else 'FAIL'}  +12 dB shelf at 40 Hz, -60 dBFS tone: error "
          f"{with_fs:.1f} dBFS with fraction saving, {without:.1f} dBFS without")
    return ok


CORNERS = [("dsp48", 48000), ("dsp44", 44100)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    da.write_vh(da.program())
    work = HERE / "work"
    ok = True
    for name, fs in CORNERS:
        if args.only and args.only != name:
            continue
        print(f"{name}: {fs} Hz")
        ok &= run_corner(name, fs, work)
    if not args.only or args.only == "model":
        print("model (48 kHz):")
        ok &= model_resp(48000)
        ok &= model_noise(48000)
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
