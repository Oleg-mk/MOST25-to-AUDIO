#!/usr/bin/env python3
"""capture_analyse.py - what a recording of a real MOST25 line says.

    python tools/capture_analyse.py console.log            the ESP32 console log with a dump in it
    python tools/capture_analyse.py console.log --json out.json

The listener's FPGA keeps the line's run lengths (listener_gw/rtl/capture.v);
the host prints a dump as text (listener_fw/main/host.c):

    CAP BEGIN runs=<n> packets=<p> missing=<m>
    CAP <packet> <64 hex digits: 32 run lengths in samples of 1.26 ns> <8 hex digits: glitch flags>
    CAP <packet> -
    CAP END

From that, without any assumption the simulations made:
  * the UI in samples and so the ring's rate (44.1 or 48 kHz), from the
    lengths themselves (the most common run is one UI);
  * every run's class (1, 2, 3 UI) and the runs that are none of these;
  * the frames: 3-UI runs that repeat 1024 UI apart, the preamble's run
    pattern of every frame, and how often each pattern occurs - the rare one,
    every 16th frame, marks a control block;
  * the parity rule: whether frame bit 511 equals the XOR of bits 4..510 in
    every frame (even) or never (odd), or neither;
  * the frame control bits 504..510 and the boundary descriptor, bits 4..7;
  * the pulse-width distortion: the two polarities' mean lengths differ.
Errors are reported, never silently mended: a run that fits no class ends
its frame, and the frame is not counted.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

FS_SAMP = 792e6
FRAME_UI = 1024
PRE_UI = 8


def parse_dump(text: str):
    """The runs of the last dump in a console log: (lengths, glitch flags, header)."""
    runs, glitch, header = [], [], {}
    in_dump = False
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) < 2 or parts[0] != "CAP":
            continue
        if parts[1] == "BEGIN":
            runs, glitch, in_dump = [], [], True
            header = dict(kv.split("=") for kv in parts[2:] if "=" in kv)
            continue
        if parts[1] == "END":
            in_dump = False
            continue
        if not in_dump or len(parts) < 3:
            continue
        if parts[2] == "-":                        # a packet that never came
            runs += [None] * 32
            glitch += [0] * 32
            continue
        lens = bytes.fromhex(parts[2])
        g = int.from_bytes(bytes.fromhex(parts[3]), "little") if len(parts) > 3 else 0   # bit i = run i
        runs += list(lens)
        glitch += [(g >> i) & 1 for i in range(32)]
    n = int(header.get("runs", len(runs)))
    return runs[:n], glitch[:n], header


def polarities(runs, glitch):
    """Which of the two line levels each run has: runs alternate, except that the
    run after a sampler word with two edges (glitch) merged two runs and keeps
    the level of the run before it. Which level is high is not recorded."""
    pol, out = 0, []
    for k in range(len(runs)):
        if k and not glitch[k]:
            pol ^= 1
        out.append(pol)
    return out


def peak(lens):
    """The one-UI run length of one polarity: the shortest length that occurs in
    numbers (at least 1 % of these runs within a sample of it, and no shorter
    than half of the fastest ring's UI, 8 samples), refined by the mean of the
    lengths within a quarter of it. Most of a MOST frame is zero bytes, so
    two-UI runs outnumber one-UI runs: the mode would mislead."""
    hist = Counter(lens)
    total = len(lens)
    first = next((L for L in sorted(hist)
                  if L >= 8 and hist[L] + hist.get(L - 1, 0) + hist.get(L + 1, 0) >= 0.01 * total), None)
    if first is None:
        first = hist.most_common(1)[0][0]
    top = first                                            # up the cluster's slope to its peak
    while hist.get(top + 1, 0) > hist.get(top, 0):
        top += 1
    near = [r for r in lens if abs(r - top) <= top / 4]
    return sum(near) / len(near)


def estimate_ui(runs, pols):
    """One UI in samples and the pulse-width bias of each polarity: pulse-width
    distortion lengthens one level's runs by what it shortens the other's (the
    receiver's own model, rx_classify.v), so the one-UI peaks of the two
    polarities sit either side of the UI."""
    by = [[r for r, p in zip(runs, pols) if r is not None and 0 < r < 255 and p == q] for q in (0, 1)]
    if not by[0] or not by[1]:
        raise ValueError("no runs")
    u = [peak(by[0]), peak(by[1])]
    ui = (u[0] + u[1]) / 2
    return ui, [u[0] - ui, u[1] - ui]


def classify(runs, pols, ui, bias):
    """1, 2, 3 per run (its length less its polarity's bias, in UI, rounded), 0
    for a run that fits no class or is missing."""
    out = []
    for r, p in zip(runs, pols):
        if r is None:
            out.append(0)
            continue
        c = r - bias[p]
        k = int(round(c / ui))
        out.append(k if 1 <= k <= 3 and abs(c - k * ui) <= 0.5 * ui else 0)
    return out


def frames_from(classes, glitch):
    """Frames: each opens with a 3-UI run and holds 1024 UI; the first 8 UI are the
    preamble (its run pattern is recorded), then 508 biphase-mark cells. A run
    that fits no class, a glitch, or a frame of the wrong length ends the
    frame unfinished; the next 3-UI run opens the next one."""
    frames, errors = [], Counter()
    i = 0
    n = len(classes)
    while i < n:
        if classes[i] != 3:
            i += 1
            continue
        start = i
        # preamble: runs until 8 UI
        acc, pre, j, bad = 0, [], i, False
        while j < n and acc < PRE_UI:
            if classes[j] == 0 or glitch[j]:
                bad = True
                break
            acc += classes[j]
            pre.append(classes[j])
            j += 1
        if bad or acc != PRE_UI:
            errors["preamble"] += 1
            i += 1
            continue
        bits, ui_pos, ok = [], PRE_UI, True
        while j < n and len(bits) < 508:
            c = classes[j]
            if c == 0 or glitch[j]:
                errors["run"] += 1
                ok = False
                break
            if c == 2:
                bits.append(0)
                j += 1
            elif c == 1:
                if j + 1 >= n or classes[j + 1] != 1 or glitch[j + 1]:
                    errors["half"] += 1
                    ok = False
                    break
                bits.append(1)
                j += 2
            else:                                   # a 3-UI run inside the data: the frame was short
                errors["short"] += 1
                ok = False
                break
        if not ok or len(bits) < 508:
            i = j if j > i else i + 1
            continue
        if j < n and classes[j] != 3:               # the frame did not end on a preamble
            errors["long"] += 1
            i = j
            continue
        frames.append(dict(start=start, pre=tuple(pre), bits=bits))
        i = j
    return frames, errors


def analyse(runs, glitch):
    if len(glitch) != len(runs):
        glitch = [0] * len(runs)
    pols = polarities(runs, glitch)
    ui, bias = estimate_ui(runs, pols)
    fs = FS_SAMP / (FRAME_UI * ui)
    rate = 48000 if abs(fs - 48000) < abs(fs - 44100) else 44100
    classes = classify(runs, pols, ui, bias)
    unclass = sum(1 for c, r in zip(classes, runs) if c == 0 and r is not None)
    frames, errors = frames_from(classes, glitch)
    pats = Counter(f["pre"] for f in frames)
    common = pats.most_common(1)[0][0] if pats else None
    rare_pos = [k for k, f in enumerate(frames) if f["pre"] != common]
    period = Counter(b - a for a, b in zip(rare_pos, rare_pos[1:]))
    # parity: bit 511 against the XOR of bits 4..510 (bits 0..3 are the preamble, not data)
    even = odd = 0
    fc = Counter()
    bd = Counter()
    for f in frames:
        b = f["bits"]                              # b[0] = frame bit 4
        x = 0
        for v in b[:-1]:
            x ^= v
        if b[-1] == x:
            even += 1
        else:
            odd += 1
        fc[int("".join(map(str, b[500:507])), 2)] += 1     # frame bits 504..510
        bd[int("".join(map(str, b[0:4])), 2)] += 1         # frame bits 4..7
    pwd = (bias[0] - bias[1]) / 2 / ui                   # UI: one level's runs longer by this, the other's shorter
    starts = [f["start"] for f in frames]
    dist = Counter()
    pos = 0
    ui_pos = []
    for c in classes:
        ui_pos.append(pos)
        pos += c
    for a, b in zip(starts, starts[1:]):
        dist[ui_pos[b] - ui_pos[a]] += 1
    # the UI to the ppm: whole frames are 1024 UI, their length in samples is exact
    pairs = [(a, b) for a, b in zip(starts, starts[1:])
             if ui_pos[b] - ui_pos[a] == FRAME_UI and all(r is not None for r in runs[a:b])]
    if pairs:
        ui = sum(sum(runs[a:b]) for a, b in pairs) / (FRAME_UI * len(pairs))
        fs = FS_SAMP / (FRAME_UI * ui)
    return dict(
        runs=len(runs), missing=sum(1 for r in runs if r is None), glitches=sum(glitch),
        ui_samples=ui, frame_rate_hz=fs, rate=rate, unclassified=unclass,
        frames=len(frames), errors=dict(errors), frame_distance_ui=dict(dist),
        preambles={" ".join(map(str, p)): c for p, c in pats.most_common()},
        common_preamble=" ".join(map(str, common)) if common else None,
        rare_preamble_period=dict(period),
        parity_even=even, parity_odd=odd,
        frame_control=dict(fc.most_common()), boundary_descriptor=dict(bd.most_common()),
        pwd_ui=pwd,
    )


def report(a):
    out = []
    out.append(f"{a['runs']} runs, {a['missing']} missing, {a['glitches']} glitch flags")
    out.append(f"UI {a['ui_samples']:.4f} samples = {a['ui_samples'] / FS_SAMP * 1e9:.4f} ns -> frame rate "
               f"{a['frame_rate_hz']:.2f} Hz: a {a['rate']} Hz ring ({(a['frame_rate_hz'] / a['rate'] - 1) * 1e6:+.0f} ppm"
               f"{', from whole frames' if a['frames'] > 1 else ''})")
    out.append(f"{a['unclassified']} runs of no legal length; {a['frames']} whole frames, "
               f"errors {a['errors'] or 'none'}; distance between frames (UI) {a['frame_distance_ui']}")
    if a['pwd_ui'] is not None:
        out.append(f"pulse-width distortion {abs(a['pwd_ui']):.3f} UI: one level's runs longer by that, "
                   f"the other's shorter (which level is high is not recorded)")
    out.append("preamble run patterns: " + ", ".join(f"[{p}] x{c}" for p, c in a["preambles"].items()))
    if a["rare_preamble_period"]:
        out.append(f"the rarer pattern repeats every {a['rare_preamble_period']} frames (16 = a control block)")
    n = a["parity_even"] + a["parity_odd"]
    if n:
        rule = ("EVEN over bits 4..511" if a["parity_odd"] == 0 else
                "ODD over bits 4..511" if a["parity_even"] == 0 else "NO XOR rule over bits 4..511")
        out.append(f"parity: bit 511 = XOR(bits 4..510) in {a['parity_even']} of {n} frames -> {rule}")
    out.append(f"frame control bits 504..510: {a['frame_control']}")
    out.append(f"boundary descriptor (bits 4..7): {a['boundary_descriptor']}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    runs, glitch, header = parse_dump(a.log.read_text(encoding="utf-8", errors="ignore"))
    if not runs:
        print("no dump (CAP lines) in the log")
        return 1
    res = analyse(runs, glitch)
    print(report(res))
    if a.json:
        a.json.write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
