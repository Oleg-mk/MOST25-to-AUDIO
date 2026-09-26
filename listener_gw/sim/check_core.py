#!/usr/bin/env python3
"""check_core.py - verify every output of listener_core against the stimulus.

  SI    the Si514 model was driven as its data sheet requires and clk_r ended
        up at 1024 x the ring's Fs; LOCK switched on
  TX    after LOCK, every regenerated run (in clk_r cycles = UI) equals the
        ring's run - the ring must not see a single wrong edge
  TDM   under LOCK every TDM frame equals the MOST frame, byte for byte, and
        the frames follow each other without a gap
  MCLK  under LOCK exactly 512 periods per TDM frame (512 Fs, locked to the ring)
  UART  every packet has the sync, a correct XOR, and control bytes equal to
        bytes 61, 62 of 16 consecutive ring frames starting on a block start
  I2S   after each host command (UART_RX), every I2S frame holds exactly the
        commanded bytes of consecutive ring frames; a wrong-XOR command is ignored
  FS    the frame-rate output to the clock multiplier: every edge at a constant
        offset from the ring's own frame edge, to the sample (1.26 ns)
  INJ   the regenerated line, decoded: frames unchanged before and after
        injection, and while injecting only the chosen bytes carry the audio
        in, with the parity XOR kept
Exit 0 only if all of them hold.
"""
import sys
from pathlib import Path

BIT_NS = 1e9 / 3e6 * 1.0          # UART bit time: 33 clk_s at 99 MHz = 333.33 ns
BIT_NS = 33 * (1e3 / 99.0)


def check_si514(d):
    """The clock loop drove the Si514 model as the data sheet requires, and the
    ring clock ended up on the ring: the model's I2C address (not the data
    sheet's example) found by one scan - every lower address probed once,
    nothing addressed wrongly after it; exactly one centring (FCAL), no small
    change outside +/-1000 ppm of the calibrated centre, reg 132's reserved
    bit kept (read-modify-write) and the output on, HS_DIV for the ring's
    rate, the final frequency 1024 x Fs of the ring within 20 ppm, and LOCK
    switched on."""
    import json
    meta = json.loads((d / "meta.json").read_text())
    w = (d / "out_si514.txt").read_text().split()
    kv = dict(zip(w[0::2], w[1::2]))
    want_hs = 44 if meta["fs"] == 48000 else 48
    want_f = 1024 * meta["fs"] * (1 + meta.get("ppm", 0.0) * 1e-6)
    f = float(kv["freq"])
    ppm = (f / want_f - 1) * 1e6
    reg132 = int(kv["reg132"], 16)
    locked = "lock=1" in (d / "out_lock.txt").read_text()
    addr, found, probes = int(kv["addr"], 16), int(kv["found"], 16), int(kv["probes"])
    ok = (found == addr and probes == addr - 0x08
          and int(kv["fcal"]) == 1 and int(kv["bad_small"]) == 0 and int(kv["bad_rmw"]) == 0
          and int(kv["nack"]) == 0 and int(kv["hs"]) == want_hs and abs(ppm) < 20
          and reg132 & 0x84 == 0x84 and locked)
    print(f"SI  : {'PASS' if ok else 'FAIL'}  address 0x{found:02x} found for 0x{addr:02x} after "
          f"{probes} probes, fcal {kv['fcal']}, {kv['small']} small changes "
          f"(outside window {kv['bad_small']}), reserved bit lost {kv['bad_rmw']}, nack {kv['nack']}, "
          f"HS_DIV {kv['hs']} (want {want_hs}), clk_r {f / 1e6:.6f} MHz = ring {ppm:+.2f} ppm, "
          f"reg132 {reg132:02x}, LOCK {'on' if locked else 'NEVER'}")
    return ok


def inject_before_lock(d):
    """True if the tb sent "inject on" before LOCK came up (INJ_EARLY)."""
    lock_ps = next((int(l.split()[0]) for l in (d / "out_lock.txt").read_text().splitlines()
                    if l.split()[1] == "lock=1"), None)
    for l in (d / "out_cfg.txt").read_text().splitlines():
        t, c, bad, w = map(int, l.split()[:4])
        if c == 2 and not bad and w != 0 and lock_ps is not None and t * 1000 < lock_ps:
            return True
    return False


def align(seg, runs):
    """Where seg sits in the ring's runs - only if it sits there alone. A short
    window can match in several places: a frame's zero bytes are long rows of
    identical 2-UI runs. The window grows until exactly one place matches;
    None if none does, or none is unique even at 4000 runs."""
    n = 400
    while n <= min(4000, len(seg)):
        probe = seg[:n]
        head = probe[:16]
        hits = [s for s in range(len(runs) - n + 1)
                if runs[s:s + 16] == head and runs[s:s + n] == probe]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            return None
        n *= 2
    return None


def check_tx(d, runs):
    """Until the host turns injection on, the ring must get its own runs back,
    every one. The first run that differs must lie inside an injected frame -
    check_inject proves what is sent from there on. If injection was already
    on when LOCK came up (the command went in before the Si514 was centred),
    the same is checked from the other end: after injection is turned off,
    every run is the ring's again."""
    tx = [int(x) for x in (d / "out_tx.txt").read_text().split()][1:]   # first is partial
    if len(tx) < 1000:
        print(f"TX  : FAIL  only {len(tx)} regenerated runs after LOCK")
        return False
    if inject_before_lock(d):
        body = tx[:-1]                                    # the last run may be cut
        seg = body[-4000:]
        s = align(seg, runs)
        if s is None:
            print("TX  : FAIL  the regenerated runs after injection never line up with the ring's")
            return False
        off = s - (len(body) - len(seg))                  # runs[k + off] belongs to body[k]
        k = len(body) - 1
        while k >= 0 and k + off >= 0 and body[k] == runs[k + off]:
            k -= 1
        tail = len(body) - 1 - k
        bad = [r for r in tx if r not in (1, 2, 3)]
        ok = tail >= 1000 and not bad
        print(f"TX  : {'PASS' if ok else 'FAIL'}  injection on at LOCK; the last {tail} runs, after it "
              f"was turned off, identical to the ring; {len(bad)} runs of a wrong length")
        return ok
    best = align(tx, runs)
    if best is None:
        print("TX  : FAIL  regenerated runs never line up with the ring's runs")
        print("      first:", tx[:40])
        return False
    n = min(len(tx), len(runs) - best) - 1                # the last run may be cut
    first = next((i for i in range(n) if tx[i] != runs[best + i]), n)
    ok = first >= 1000
    print(f"TX  : {'PASS' if ok else 'FAIL'}  {first} runs after LOCK identical to the ring"
          f"{' (all of them)' if first == n else ', then injection'}")
    return ok


def tx_frames(d):
    """Decode the regenerated line (runs in UI) back into frames."""
    tx = [int(x) for x in (d / "out_tx.txt").read_text().split()][1:]
    frames, i = [], 0
    while i < len(tx) and tx[i] != 3:
        i += 1
    while i < len(tx):
        pos, j = 0, i                                     # preamble: 8 UI from a 3-run
        while j < len(tx) and pos < 8:
            pos += tx[j]; j += 1
        if pos != 8:
            break
        bits = []
        while j < len(tx) and len(bits) < 508:
            if tx[j] == 2:
                bits.append(0); j += 1
            elif tx[j] == 1 and j + 1 < len(tx) and tx[j + 1] == 1:
                bits.append(1); j += 2
            else:
                break
        if len(bits) < 508:
            break
        v = int("".join(map(str, [0, 0, 0, 0] + bits)), 2)
        frames.append(v.to_bytes(64, "big"))
        if j >= len(tx) or tx[j] != 3:
            break
        i = j
    return frames


def check_inject(d, truth):
    """What the ring gets while our audio goes in (tb: bytes 5..10, 24 bit,
    L = 5A nnnn, R = C3 (nnnn + 1234) from the DSP model, n + 1 per frame):
      * frames before and after injection equal the ring's frames bit for bit;
      * injected frames equal them except bytes 5..10 and the parity bit;
        bytes 5..10 carry consecutive samples; the XOR of bits 4..511 (what
        any XOR parity rule sees) is unchanged;
      * frames stay consecutive, order: original, injected, original;
      * the command naming byte 61 changed nothing (else byte 61 would move).
    """
    INJ = (5, 6, 7, 8, 9, 10)
    tb = [bytes.fromhex(t) for t in truth]
    out = tx_frames(d)

    def key(f):                                            # bytes injection never touches
        return f[1:5] + f[11:63] + bytes([f[63] & 0xFE, f[0] & 0x0F])

    def xor_bits(f):
        return bin(int.from_bytes(f, "big") & ((1 << 508) - 1)).count("1") & 1

    idx = {}
    for k, f in enumerate(tb):
        idx.setdefault(key(f), []).append(k)
    phase, last, n_inj, n_orig, bad, prev_n = 0, None, [0, 0], 0, 0, None
    for f in out:
        ks = idx.get(key(f), [])
        k = next((k for k in ks if last is None or k == last + 1), None)
        if k is None:
            bad += 1
            print(f"      TX frame with no ring counterpart: {f.hex()}")
            continue
        if last is not None and k != last + 1:
            bad += 1
        last = k
        t = tb[k]
        if f[1:] == t[1:] and (f[0] & 0x0F) == (t[0] & 0x0F):   # byte 0 high nibble = preamble
            if phase == 1:
                phase = 2
            n_orig += 1
            continue
        # injected
        if phase == 2:
            bad += 1
            print("      injection came back after it was turned off")
        phase = 1
        L = f[5] << 16 | f[6] << 8 | f[7]
        R = f[8] << 16 | f[9] << 8 | f[10]
        n = L & 0xFFFF
        good = (f[5] == 0x5A and f[8] == 0xC3 and (R & 0xFFFF) == ((n + 0x1234) & 0xFFFF)
                and (prev_n is None or n == (prev_n + 1) & 0xFFFF)
                and xor_bits(f) == xor_bits(t) and key(f) == key(t))
        if not good:
            bad += 1
            print(f"      bad injected frame {k}: L={L:06x} R={R:06x} prev n={prev_n} "
                  f"parity {xor_bits(f)} vs {xor_bits(t)}")
        prev_n = n
        n_inj[0] += 1
    ok = bad == 0 and n_inj[0] >= 8 and phase == 2 and len(out) >= 40
    print(f"INJ : {'PASS' if ok else 'FAIL'}  {len(out)} TX frames decoded: {n_orig} unchanged, "
          f"{n_inj[0]} injected (samples consecutive, parity XOR kept), {bad} bad, "
          f"{'returned to pass-through' if phase == 2 else 'NEVER returned to pass-through'}")
    return ok


def check_tdm(d, truth):
    """Only frames sent under LOCK count: before it the Si514 is centred once
    and its output is off for the calibration, so clk_r and TDM stop there."""
    rows = [l.strip() for l in (d / "out_tdm.txt").read_text().splitlines()]
    frames, cur = [], None
    for r in rows:
        if "x" in r or "z" in r or r[3] != "1":
            cur = None
            continue
        fs, s0, s1 = r[0], int(r[1]), int(r[2])
        if fs == "1":
            if cur and len(cur[0]) == 256:
                frames.append(cur)
            cur = ([], [])
        if cur is not None:
            cur[0].append(s0)
            cur[1].append(s1)
    out = []
    for b0, b1 in frames:
        by = bytearray(64)
        for b in range(256):
            by[b >> 3] |= b0[b] << (7 - (b & 7))
            by[32 + (b >> 3)] |= b1[b] << (7 - (b & 7))
        out.append(by.hex())
    live = [f for f in out if f[2:] != "0" * 126]         # skip frames before the first bank
    tnorm = ["0" + t[1:] for t in truth]
    matched = bad = 0
    for f in live:
        if f in truth:
            matched += 1
        elif "0" + f[1:] in tnorm:
            matched += 1                                   # block index not yet known
        else:
            bad += 1
    # consecutive order check
    idx = [truth.index(f) if f in truth else tnorm.index("0" + f[1:]) if "0" + f[1:] in tnorm else -1
           for f in live]
    order_ok = all(b == a + 1 for a, b in zip(idx, idx[1:]) if a >= 0 and b >= 0)
    ok = bad == 0 and matched >= 8 and order_ok
    print(f"TDM : {'PASS' if ok else 'FAIL'}  {matched} frames under LOCK matched, {bad} wrong, "
          f"{'in order' if order_ok else 'OUT OF ORDER (skipped or repeated)'}")
    return ok


def check_uart(d, truth):
    ev = []
    for l in (d / "out_uart.txt").read_text().splitlines():
        t, v = l.split()
        if v in "01":
            ev.append((float(t) / 1000.0, int(v)))         # ps -> ns
    def level(t):
        lv = 1
        for te, v in ev:
            if te > t:
                break
            lv = v
        return lv
    # decode bytes: a start bit is a 1->0 transition while idle
    bytes_ = []
    i = 0
    t_idle = 0.0
    while i < len(ev):
        t, v = ev[i]
        if v == 0 and t >= t_idle:
            val = 0
            for k in range(8):
                val |= level(t + BIT_NS * (1.5 + k)) << k
            stop = level(t + BIT_NS * 9.5)
            bytes_.append((val, stop))
            t_idle = t + BIT_NS * 9.8
        i += 1
    data = [v for v, s in bytes_]
    pk, n_ok, n_bad = [], 0, 0
    j = 0
    blocks = {}
    for s in range(0, len(truth) - 15):
        if int(truth[s][0], 16) == 0:                      # block start frame
            blocks[bytes(bytes.fromhex(truth[s + k])[p] for k in range(16) for p in (61, 62))] = s
    while j + 42 <= len(data):
        if data[j] == 0xA5 and data[j + 1] == 0x5A:
            p = data[j:j + 42]
            x = 0
            for b in p[:41]:
                x ^= b
            ctrl = bytes(p[9:41])
            if x == p[41] and ctrl in blocks and all(s for v, s in bytes_[j:j + 42]):
                n_ok += 1
            else:
                n_bad += 1
            j += 42
        else:
            j += 1
    ok = n_ok >= 1 and n_bad == 0
    print(f"UART: {'PASS' if ok else 'FAIL'}  {n_ok} packets good, {n_bad} bad")
    return ok


def check_mclk(d):
    """MCLK must be exactly 512 periods per TDM (= MOST) frame: 512 Fs. Each
    row is one frame's count and LOCK at its end; a frame counts if LOCK was
    on at both of its ends (before LOCK the clock stops once, for centring)."""
    rows = [l.split() for l in (d / "out_mclk.txt").read_text().splitlines()]
    n = [int(c) for (c, lk), (_, lk0) in zip(rows[1:], rows[:-1]) if lk == "1" and lk0 == "1"]
    ok = len(n) >= 8 and all(v == 512 for v in n)
    print(f"MCLK: {'PASS' if ok else 'FAIL'}  {len(n)} frames under LOCK, periods per frame {sorted(set(n))}")
    return ok


def check_i2s(d, truth):
    """J3 carries exactly the bytes the host asked for, through amp_out, frame after frame.

    out_cfg.txt lists the commands sent (a wrong-XOR one must change nothing).
    The host first sets amp_out straight through with stream 0 to L x 1 and
    R x 0.5 (tb_core.v). Each I2S frame (LRCK low = left, MSB one BCLK after
    the edge) must equal the chosen bytes of one ring frame, so scaled: zeros
    before the first good command, then config A, then config B, the ring
    frames consecutive throughout.
    """
    cfgs = []
    for l in (d / "out_cfg.txt").read_text().splitlines():
        t, c, bad, w, *pos = map(int, l.split())
        if c == 1 and not bad:
            cfgs.append((w, pos))
    rows = [l.strip() for l in (d / "out_i2s.txt").read_text().splitlines()]
    rows = [r for r in rows if "x" not in r and "z" not in r]
    frames = []
    for i in range(1, len(rows) - 64):
        if rows[i - 1][0] == "1" and rows[i][0] == "0":           # LRCK fell: slot 0
            f = rows[i:i + 64]
            if all(f[s][0] == ("0" if s < 32 else "1") for s in range(64)):
                bits = [int(f[s][1]) for s in range(1, 64)] + [0]  # slots 1..63, then next slot 0
                frames.append((int("".join(map(str, bits[:32])), 2), int("".join(map(str, bits[32:])), 2)))

    def s24(v):
        return v - (1 << 24) if v >> 23 else v

    def slot(v):                                                   # a 24-bit sample in its 32-bit slot
        v = max(-(1 << 23), min((1 << 23) - 1, v))
        return (v & 0xFFFFFF) << 8

    def want(fr, w, pos):
        b = bytes.fromhex(fr)
        l = [b[p] for p in pos[:3]]; r = [b[p] for p in pos[3:]]
        if w == 2:
            l[2] = r[2] = 0
        L = s24(l[0] << 16 | l[1] << 8 | l[2]); R = s24(r[0] << 16 | r[1] << 8 | r[2])
        return (slot(L), slot((R + 1) >> 1))

    stage, last, counts, bad = 0, None, [0] * (len(cfgs) + 1), 0
    for fw in frames:
        if stage == 0 and fw == (0, 0):
            counts[0] += 1
            continue
        hit = None
        for st in range(max(stage, 1), len(cfgs) + 1):
            w, pos = cfgs[st - 1]
            idx = [k for k, fr in enumerate(truth) if want(fr, w, pos) == fw]
            if idx:
                hit = (st, idx)
                break
        if hit is None:
            bad += 1
            print("      no ring frame gives L R = " + " ".join(f"{v:08x}" for v in fw))
            continue
        st, idx = hit
        k = idx[0] if last is None else next((k for k in idx if k == last + 1), idx[0])
        if last is not None and k != last + 1:
            bad += 1                                          # skipped or repeated frame
            print(f"      ring frame {k} follows {last}")
        stage, last = st, k
        counts[st] += 1
    ok = bad == 0 and all(c >= 4 for c in counts[1:]) and len(cfgs) == 2
    print(f"I2S : {'PASS' if ok else 'FAIL'}  {len(frames)} frames: {counts[0]} silent before the "
          f"first command, " + ", ".join(f"cfg{i} {c}" for i, c in enumerate(counts[1:], 1))
          + f"; {bad} wrong or out of order")
    return ok


def check_fs(d):
    """The frame-rate output (for an external clock multiplier) keeps the sampler's resolution.

    Truth comes from the stimulus itself: every transition of samples.hex (8
    samples per word, bit 0 first), the frames' UI 0 edges (the edge that opens
    each 3-UI run) and their UI 512 edges. Each rising edge of fs must sit a
    constant number of samples after its frame's UI 0 edge, each falling edge
    a constant number after UI 512 - spread 0, i.e. 1.26 ns resolution. For
    comparison, the same edges drawn on the clk_s grid (the old fs_sq) spread
    over up to 8 samples, 10.1 ns.
    """
    import json
    meta = json.loads((d / "meta.json").read_text())
    ui = meta["ui_samples"]
    words = [int(x, 16) for x in (d / "samples.hex").read_text().split()]
    bits = [(w >> k) & 1 for w in words for k in range(8)]
    tr = [j for j in range(1, len(bits)) if bits[j] != bits[j - 1]]
    # a run's length in UI, corrected for the stimulus' pulse-width distortion
    # (high runs stretched by pwd, low runs shortened), as the receiver learns
    # to do; then only runs that repeat exactly one frame (1024 UI) apart
    pwd = meta.get("pwd", 0.0)

    def ui_len(n):
        r = (tr[n + 1] - tr[n]) / ui
        return r - pwd if bits[tr[n]] else r + pwd
    cand = [tr[n] for n in range(len(tr) - 1) if 2.5 < ui_len(n) < 3.5]
    frame = 1024 * ui
    starts = [s for k, s in enumerate(cand)
              if any(abs(abs(c - s) - frame) < ui for c in cand[max(0, k - 3):k + 4] if c != s)]
    mids = []
    for f in starts:
        want = f + 512 * ui
        near = min(tr, key=lambda t: abs(t - want))
        if abs(near - want) < ui / 2:
            mids.append(near)

    rise, fall, late = [], [], None
    for l in (d / "out_fs.txt").read_text().splitlines():
        a, b = l.split()
        if a == "late":
            late = int(b)
        elif b == "1":
            rise.append(int(a))
        elif b == "0":
            fall.append(int(a))

    def offsets(edges, truth):
        out = []
        for e in edges:
            before = [t for t in truth if t < e]
            if before:
                out.append(e - before[-1])
        return out

    ro, fo = offsets(rise, starts), offsets(fall, mids)
    old = sorted({(-f) % 8 for f in starts})          # clk_s-grid lag of the same edges
    ok = (len(ro) >= 20 and len(fo) >= 20 and len(set(ro)) == 1 and len(set(fo)) == 1
          and late == 0)
    print(f"FS  : {'PASS' if ok else 'FAIL'}  {len(ro)} rising / {len(fo)} falling edges; "
          f"offset to UI 0 {sorted(set(ro))} and to UI 512 {sorted(set(fo))} samples "
          f"(spread {max(ro) - min(ro) if ro else '-'} / {max(fo) - min(fo) if fo else '-'}); "
          f"late={late}; on the clk_s grid the same edges would spread {max(old) - min(old)} samples")
    return ok


def check_gap(d, fs):
    """A dead line after LOCK (tb GAP_AFTER_LOCK_US; out_gap.txt holds its
    start and end in ns): LOCK must drop within 5 us of the line dying and come
    back after it returns; the Si514 is not centred again (holdover, then
    resume), no small change leaves its window, nothing is addressed wrongly."""
    t0, t1 = map(float, (d / "out_gap.txt").read_text().split())
    ev = []
    for l in (d / "out_lock.txt").read_text().splitlines():
        t, lk = l.split()[0], l.split()[1]
        if lk in ("lock=0", "lock=1"):
            ev.append((int(t) / 1000.0, lk == "lock=1"))          # ps -> ns
    w = (d / "out_si514.txt").read_text().split()
    kv = dict(zip(w[0::2], w[1::2]))
    first = next((t for t, v in ev if v), None)
    drop = next((t for t, v in ev if not v and t >= t0), None)
    back = next((t for t, v in ev if v and t > t1), None)
    frame = 1e9 / fs
    ok = (first is not None and first < t0 and drop is not None and drop - t0 <= 5000.0
          and back is not None and int(kv["fcal"]) == 1 and int(kv["bad_small"]) == 0
          and int(kv["bad_rmw"]) == 0 and int(kv["nack"]) == 0
          and int(kv["found"], 16) == int(kv["addr"], 16))
    fmt = lambda x, f: f(x) if x is not None else "never"
    print(f"GAP : {'PASS' if ok else 'FAIL'}  LOCK at {fmt(first, lambda x: f'{x / 1e6:.2f} ms')}; "
          f"line dead at {t0 / 1e6:.3f} ms for {(t1 - t0) / 1e3:.1f} us; LOCK dropped "
          f"{fmt(drop, lambda x: f'{(x - t0) / 1e3:.2f} us')} after, back "
          f"{fmt(back, lambda x: f'{(x - t1) / frame:.1f} frames')} after it returned; "
          f"fcal {kv['fcal']}, bad_small {kv['bad_small']}, bad_rmw {kv['bad_rmw']}, nack {kv['nack']}")
    return ok


def check_fbdead(d, fs):
    """TX_FB dead after LOCK, for good (tb FB_DEAD_AFTER_LOCK_US; out_fbdead.txt
    holds the moment in ns) - what the FPGA sees if U9's output sticks: LOCK
    must drop within 4 ring frames (plus one for the frame in progress) and
    stay off."""
    t0 = float((d / "out_fbdead.txt").read_text().split()[0])
    ev = []
    for l in (d / "out_lock.txt").read_text().splitlines():
        t, lk = l.split()[0], l.split()[1]
        if lk in ("lock=0", "lock=1"):
            ev.append((int(t) / 1000.0, lk == "lock=1"))          # ps -> ns
    frame = 1e9 / fs
    first = next((t for t, v in ev if v), None)
    drop = next((t for t, v in ev if not v and t >= t0), None)
    back = next((t for t, v in ev if v and drop is not None and t > drop), None)
    ok = first is not None and first < t0 and drop is not None and drop - t0 <= 5 * frame and back is None
    fmt = lambda x, f: f(x) if x is not None else "never"
    print(f"FB  : {'PASS' if ok else 'FAIL'}  LOCK at {fmt(first, lambda x: f'{x / 1e6:.2f} ms')}; "
          f"TX_FB dead at {t0 / 1e6:.3f} ms; LOCK dropped "
          f"{fmt(drop, lambda x: f'{(x - t0) / frame:.2f} frames')} after, "
          f"{'came back' if back is not None else 'stayed off'}")
    return ok


def check_wd(d):
    """The board's bypass watchdog (U11, modelled in tb_core.v) never dropped
    TX_SEL while LOCK was on and clk_s ran: TX kept toggling through
    everything the run does (host commands, injection on and off)."""
    drops = int((d / "out_wd.txt").read_text().split()[0])
    ok = drops == 0
    print(f"WD  : {'PASS' if ok else 'FAIL'}  {drops} watchdog drops while LOCK was on")
    return ok


def check_clkstop(d, tw_ns=10000.0):
    """clk_s stops for good after LOCK (tb CLKS_STOP_AFTER_LOCK_US; out_clkstop.txt:
    stop, TX's last rising edge, TX_SEL's fall in ns, TX_SEL and LOCK at the end,
    watchdog drops before the stop). LOCK must stay on - the failure itself;
    TX must stop toggling within 3 us (the regenerator's FIFO runs dry); the
    board's watchdog (U11 model) must then drop TX_SEL, i.e. bypass, within
    its time plus 3 us, and must never have dropped while clk_s ran."""
    t_stop, t_last, t_fall, sel, lk, drops = (float(x) for x in (d / "out_clkstop.txt").read_text().split())
    ok = (lk == 1 and sel == 0 and drops == 0 and t_last - t_stop <= 3000.0
          and t_fall - t_stop <= tw_ns + 3000.0)
    print(f"CLK : {'PASS' if ok else 'FAIL'}  clk_s stopped at {t_stop / 1e6:.3f} ms; LOCK "
          f"{'stayed on' if lk == 1 else 'went off'}; TX's last edge {(t_last - t_stop) / 1e3:.2f} us after, "
          f"TX_SEL (bypass) {(t_fall - t_stop) / 1e3:.2f} us after; {int(drops)} watchdog drops before")
    return ok


def main(d):
    d = Path(d)
    truth = [l.strip() for l in (d / "frames.hex").read_text().split()]
    runs = [int(x, 16) for x in (d / "runs.hex").read_text().split()]
    res = [check_si514(d), check_tx(d, runs), check_tdm(d, truth), check_uart(d, truth),
           check_mclk(d), check_i2s(d, truth), check_inject(d, truth), check_fs(d)]
    print("PASS" if all(res) else "FAIL")
    return 0 if all(res) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
