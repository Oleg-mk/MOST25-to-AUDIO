# MOST25 SP1 jitter, ring Fs tolerance, and how far each clock chip can follow the ring

*Conventions. The spec and datasheet wording below is closely paraphrased, with exact section, table and page locations, so the writer can quote from the primary source. There is one direct quote. "Calculation" and "simulation" mark my own arithmetic. δ is the ring's Fs offset relative to the repeater's local clock (clk_s), so it includes the local crystal's own error.*

## 1. How MOST PHY 1.1 defines and measures tUJ, tDDJ and wander at SP1/SP2; what §2.6 says about accumulation; the Fs tolerance and who sets it

### Takeaway
The SP1 limits are link-added jitter: tUJ1 ≤ 0.0045 UI and tDDJ1 ≤ 0.01 UI. The conformance test measures them with the scope triggered from the same node's own Tx pin, on a 10⁻⁹ error-rate basis, and defines no measurement bandwidth or high-pass corner. They do not limit how the transmit clock itself moves relative to the ring. That movement falls under the §2.6 system budget: wander below 1 Hz plus accumulated jitter. Every slave PLL tracks it, and it must fit inside the timing master's master-jitter-tolerance. Fs must stay within ±0.1 %, which is IEC958 normal accuracy mode, and the single timing master sets it.

### Cited Findings
**Where the text comes from**
- The PHY spec is *MOST Specification of Physical Layer* Rev 1.1, 09/2003, document version 1.1-00. It sits inside `MOST_2V5_Physical_Layer.zip → 3_MOST25_oPHY/MOST25_oPhy_Specification_1V1-0..zip → MOST Specification of Physical Layer.pdf`. — MOST PHY 1.1
- The SP tables in the plain-text dump (`scratchpad/phy/main.txt`) are column-shifted: the "Uncorrelated link jitter" row there shows pulse-width numbers. All limits below were re-read with xpdf `pdftotext -table`, which keeps table rows aligned. — MOST PHY 1.1
- Addenda A–E in the same archive contain no text on jitter, wander, tUJ/tDDJ or Fs accuracy (text search). — PHY archive
- The measurement procedure is *MOST Compliance Test of Physical Layer* Rev 1.0, 12/2003, v1.0-00. It sits inside `MOST_2V5_Physical_Layer_Conformance.zip → 3_MOST25_oPHY_CTP/MOST25_oPhy_Conformance_Test_Specification_1V0-0.zip`, and its errata sheet does not touch the jitter clauses. It is cited below as "CT". — CT

**Definitions (PHY §2.1–§2.1.1.3)**
- §2.1: a frame is 512 bits, B = 512·Fs and UI = 1/(2B), so UI = 22.14 ns at 44.1 kHz. — PHY §2.1
- §2.1.1: every timing-distortion parameter requires an error rate better than 10⁻⁹. — PHY §2.1.1
- §2.1.1: phase variation is always measured against a reference signal. It accumulates around the ring because the PLLs track changes in transition delay, and how it accumulates depends on its frequency and on the PLL transfer function. Link jitter is referenced to the Tx signal of the preceding node; system jitter is always referenced to the timing master's Tx. — PHY §2.1.1
- §2.1.1.2, wander: a very-low-frequency drift (below 1 Hz), mainly from temperature. All slave PLLs track it, so all wander accumulates around the ring. It is measured with constant frame content (e.g. all 0x00). — PHY §2.1.1.2
- §2.1.1.2, DDJ: comes from bandwidth-limited components (EOC/OEC). It is measured with frames alternating between all-0xFF and all-0x00, which gives a two-hump histogram; tDDJ is the distance between the hump means. Low-frequency DDJ accumulates and high-frequency DDJ is attenuated by the PLLs. — PHY §2.1.1.2
- §2.1.1.2, UJ: everything not data-dependent (white noise, supply noise, crosstalk). It is measured with a single-frequency pattern (all 0xFF), gives a single hump, and is determined from the standard deviation. UJ above the PLL cut-off is attenuated; UJ below it accumulates, and the accumulated part can be measured at the next node's Tx. — PHY §2.1.1.2
- DDJ and UJ must be taken on the edge the receiving NIC's clock recovery locks to (the "active edge"), which the NIC datasheet must name. — PHY §2.1.1.2
- The SP1–SP4 link-jitter limits come from what MOST NICs need for clock recovery; system jitter is derived in §2.6. — PHY §2.1.1.2, end

**Limits per specification point (PHY Tables 2-1 to 2-4; the SP1 ns values are from CT Table 2-3)**

| Point | What it is | tDDJ max | tUJ max | Trigger note |
|---|---|---|---|---|
| SP1 | EOC electrical input | 0.01 UI (0.22 ns @44.1 kHz, 0.20 ns @48 kHz) | 0.0045 UI (0.10 ns @44.1, 0.09 ns @48) | note 5: triggered from Tx |
| SP2 | EOC optical output | 0.035 UI | 0.015 UI | note 8: triggered from Tx |
| SP3 | OEC optical input | 0.035 UI | 0.015 UI | note 9: triggered from Tx |
| SP4 | OEC electrical output | 0.15 UI | 0.045 UI | note 5: triggered from Tx |

— PHY Tables 2-1…2-4; CT Table 2-3
- At SP1, tDDJ1 and tUJ1 carry conditions 3) (measured at 1.5 V), 4) (see §2.1) and 5) (triggered from Tx). SP1 also sets tpwv1 at 0.955–1.045 UI and tapwd1 at ±0.023 UI. SP4 sets tpwv4 at 0.743–1.40 UI. — PHY Table 2-1, 2-4

**How the conformance test measures it**
- CT §1.1.6: a NIC or a pattern generator produces the pattern, and the Tx of the previous node or pattern generator is the scope trigger. DDJ and UJ may be taken at any of SP1–SP4 (setup in Fig. 1-5). CT Table 1-7 says wander matters only at system level, while DDJ and UJ matter at both link and system level. — CT §1.1.6
- CT §1.1.6.1: when the device under test is a slave, triggering on that slave's own Tx removes all phase variation of the preceding master-to-slave link from the result. — CT §1.1.6.1
- CT §2.1.5 (SP1): the SP1 DDJ/UJ measurement may be skipped if there are no components between the NIC's Tx output and SP1, high-speed layout rules are followed and the other SP1 requirements are met. It adds: "In practice the signals for Tx and SP1 are identical regarding jitter." — CT §2.1.5
- CT §1.1.6.3: for UJ, the standard deviation of the single hump is determined. — CT §1.1.6.3
- CT §1.1.7: PWV, APWD, DDJ and UJ at SP1–SP4 all rest on a BER of 10⁻⁹. CT §1.1.7.3 converts Gaussian tails to 10⁻⁹ peak values as mean ± 6σ (worked for PWV). — CT §1.1.7
- CT §1.1.4.3: the UJ test signal may be a 512·Fs square wave with less than 500 ps of jitter. — CT §1.1.4.3
- CT §1.2.1 recommends a 2 GS/s, 500 MHz scope with trigger jitter below 25 ps, histogram and standard-deviation functions, and a 200–300 MHz input filter to cut OEC noise. Neither document defines a jitter measurement filter, a high-pass corner or a reference-clock PLL (text search of both documents). — CT §1.2.1

**System budget (PHY §2.6; CT §3)**
- PHY §2.6: network stability is limited by how much phase variation the timing master tolerates. That amount is the master-jitter-tolerance, and each NIC datasheet must state it. Accumulation is set by the slave PLLs: low-frequency variation passes through them completely, while high-frequency variation is attenuated. — PHY §2.6
- PHY Table 2-5 (clean definitions in CT Table 3-1): M-Jitter-Tol ≥ Σₙ₌₁..ₘ tW(n) + Σₙ₌₁..ₘ₋₁ tDDJacc(n) + Σₙ₌₁..ₘ₋₁ tUJacc(n) + tDDJ(m) + tUJ(m).
  - tW(n) is the wander per node and link.
  - tDDJacc(n) and tUJacc(n) are the accumulated DDJ and UJ from node to node, Tx(n−1)→Tx(n).
  - tDDJ(m)+tUJ(m) is the jitter of the last link, from the last slave's Tx to the master's SP4.
  - The master tolerance is a property of the master's NIC and must be in its datasheet (CT §3).
  — PHY Table 2-5; CT §3
- PHY Table 2-6:
  - The timing master has no PLL in its input stage, so the full peak-to-peak DDJ+UJ of the last link adds to the accumulated jitter and wander at the last slave's Tx.
  - For the other nodes, only the accumulated (below-cut-off) part of DDJ and UJ counts.
  - DDJ arises between the 256·Fs (2 UI) and 512·Fs (1 UI) signal components.
  - A system that meets the formula is stable under all conditions.
  — PHY Table 2-6
- CT §3.2.1, system wander: the whole ring goes into a climatic chamber, and the scope triggers on a Tx preamble at the master (a 3 UI pulse longer than 60 ns). The Tx→Rx preamble delay is read at each temperature step (e.g. 10 °C), and wander is the change in that delay. The example screenshots are labelled 812 ns (the delay) and 20 ns. — CT §3.2.1
- CT §3.2.2–§3.2.3.1, total and accumulated jitter:
  - Up to about 0.75 UI (16.5 ns at 44.1 kHz), total DDJ+UJ can be read at the master's Rx triggered from its Tx; the example shows 3.74 ns.
  - Larger values are measured as master RMCK (trigger) against last-slave RMCK. RMCK comes from the same PLL as Tx and so has the same phase behavior; the example shows 19.2 ns pp with the worst-case DDJ pattern at high temperature.
  - §3.1: with RMCK at 64·Fs, about 170 ns is measurable.
  — CT §3.1–§3.2.3

**Fs tolerance and who sets it**
- PHY §2.1: Fs must stay within ±0.1 % of the nominal sample rate (e.g. 44.1 kHz ± 44.1 Hz), which corresponds to IEC958 normal accuracy mode. The revision history records this tolerance as new in rev 1.1. PHY 1.1 mentions no other accuracy mode (text search). — PHY §2.1 and revision history
- IEC 60958-3, as summarized by Garner (IEEE 802.3 ResE study group, May 2005, slide on consumer-application frequency accuracy), defines three clock-accuracy levels:
  - Level I (high accuracy): ±50 ppm.
  - Level II (normal accuracy): ±1000 ppm.
  - Level III (variable pitch): a range of 12.5 % is envisaged.
  - Receivers should lock to Level II signals, i.e. a ±1000 ppm pull-in range; a receiver with less pull-in must still exceed ±50 ppm and is to be specified as Level I.
  — [Garner, IEEE 802.3 ResE 05/2005](https://grouper.ieee.org/groups/802/3/re_study/public/200505/garner_2_0505.pdf) (secondary source; the IEC text itself was not accessed)
- OS8104 §6 intro and §6.1: there is one timing master (frame generator) per ring. It runs from its own crystal or an external clock, and all slaves use the clock recovered from RX. §7.4.1: a master can lock its PLL to an incoming S/PDIF stream, and the whole ring then follows that stream. — OS8104 datasheet DS8104FP4
- The MOST core specification Rev 2.5 (MOST25 part) gives 44,100 frames/s as the typical frame rate. — MOST Spec Rev 2.5 text dump (a scratch file, not kept)

### Inferences
- **The repeater's clock phase modulation is not SP1 jitter.** Three things show this:
  - The trigger is the transmitting node's own Tx (CT §1.1.6 and §1.1.6.1).
  - CT §2.1.5 treats Tx and SP1 as jitter-identical.
  - The limits grow along the link exactly as the EOC, fibre and OEC add jitter: UJ goes 0.0045 → 0.015 → 0.015 → 0.045 UI and DDJ goes 0.01 → 0.035 → 0.035 → 0.15 UI.

  For the repeater, "Tx" is the FPGA output pin, so SP1 only limits what the FOT drive path adds after that pin. That is a PCB question, not a clock-chip question.
- **Where it counts instead.** In MOST terms the repeater is an extra node. Its output phase relative to its input is a node-to-node term, Tx(n−1)→Tx(n), in the §2.6 formula, and which term it lands in depends on frequency:
  - Below 1 Hz it is wander (tW).
  - Below the downstream NIC's PLL cut-off it is tUJacc-type accumulated jitter; this and the wander both reach the master's Rx and eat the master tolerance.
  - Above that cut-off it is link jitter that the next NIC's clock recovery must absorb.
- **Implied high-pass of the "triggered from Tx" method (calculation).** A histogram triggered from the very edge that produced the measured edge sees the transmitter's own phase modulation φ only as φ(t) − φ(t−τ), a gain of |2 sin(πfτ)|. For SP1/SP2, τ is a few ns; with τ = 10 ns the gain at 24 kHz is 1.5×10⁻³ (−56 dB). SP1/SP2 therefore cannot see audio-band clock modulation at all.
- **Peak-to-peak vs sigma.** Three points together read the UJ limits as peak-to-peak values at 10⁻⁹: the 10⁻⁹ basis, the ±6σ tail convention (CT §1.1.7.3) and Table 2-6's statement that last-link DDJ and UJ enter peak-to-peak. At 10⁻⁹ that is about 12σ. So tUJ1 ≈ 91.6 ps pp ≈ 7.6 ps rms at 48 kHz, and ≈ 99.6 ps pp ≈ 8.3 ps rms at 44.1 kHz. The sentence that UJ "is determined by the standard deviation" (PHY §2.1.1.2, CT §1.1.6.3) allows a literal reading of σ = 0.0045 UI, but that reading contradicts Table 2-6.
- **The ±0.1 % is an allowance, not a typical value.** It is inherited from IEC958 Level II so that a timing master can follow an external normal-accuracy digital-audio source. The ring's actual offset is whatever the master's clock source delivers (see section 2 for a crystal-timed OS8104).

### Gaps
- Neither document states the σ-to-pp factor for UJ explicitly.
- PHY 1.1 has no normative limit on a node's own transmit-clock jitter generation. It enters only through NIC datasheets and the master tolerance.
- I found no evidence of whether production MOST25 cars run the timing master from S/PDIF or SCK, the only way to approach ±0.1 %, rather than from a crystal.
- Later MOST25 oPHY revisions outside this archive, if any exist, were not checked.

## 2. MOST25 NIC reality (OS8104): master clock accuracy, what a slave's PLL tracks, TX jitter figures

### Takeaway
The OS8104 datasheet puts a timing master on a 256/384/512·Fs crystal with ±50 ppm tolerance (at 25 °C, listed as typical). Slaves lock anywhere from 37.9 to 48.1 kHz. The master's RX-to-TX jitter tolerance is 25 ns pp for revisions after C, and 1/(3072·Fs), exactly 1/3 UI, for revisions B and C. The datasheet gives no PLL loop bandwidth, no jitter-transfer figure and no TX jitter-generation figure.

### Cited Findings
- §9.4:
  - A crystal on XTI/XTO sets the network timing when the node is master; slaves usually have one too, for diagnostics.
  - An external clock on XTO must be jitter-free for a master node.
  - Table 9-5 lists crystals at 256/384/512·Fs: 11.2896/16.9344/22.5792 MHz at 44.1 kHz and 12.288/18.432/24.576 MHz at 48 kHz.
  — OS8104 §9.4
- §20.1, Table 20-1:
  - AT cut, fundamental mode, CL 16–20 pF, ESR ≤ 40 Ω (256/384·Fs) or ≤ 20 Ω (512·Fs), −40…85 °C.
  - Frequency tolerance ±50 ppm at 25 °C, labelled a typical value.
  - The text says cut and tolerance are typical and may be changed to suit the system.
  — OS8104 §20.1
- §18.5.1, Clocks (−40…85 °C, PLL locked at 44.1 kHz):
  - Crystal 9.7024 MHz (256× at 37.9 kHz) to 24.6272 MHz (512× at 48.1 kHz).
  - Network frame frequency Fs 37.9 min / 44.1 typ / 48.1 max kHz with the PLL locked, and 5–10 kHz when unlocked (RX low).
  — OS8104 §18.5.1
- §18.5.1, jitter tolerance as timing master (note 7 defines it as the jitter the part tolerates without errors; Fig. 18-2 draws it as RX timing relative to TX):
  - XTO/SR0/SCK reference input: 0.8 ns pp (note 1).
  - RX, revisions B and C: 1/(3072·Fs), i.e. 7.38 ns pp at 44.1 kHz (note 2).
  - RX, revisions after C: 25 ns pp. Note 2 calls this the worst case over all RX-to-TX phase variations and says the actual tolerance may reach 30 ns pp.
  - The revision history says jitter tolerance was updated and split by chip revision.
  — OS8104 §18.5.1 and revision history
- §18.5.1 note 1: the MOST Specification requires every node to have a crystal-based master clock, so that a slave can become timing master for ring-break diagnostics. — OS8104 §18.5.1
- §18.5.1: RX pulse-width variation tpwmn is 0.7 UI and tpwmx 1.4 UI (1.36 UI as master); APWD applies to slaves only. The only TX timing entry is rise/fall time; the datasheet has no TX jitter row (text search of §18). — OS8104 §18.5.1
- §9.1 and §9.2:
  - The clock manager's analog PLL takes the crystal, SCK, S/PDIF on SR0, or RX as its input.
  - Unlocked, the PLL drifts to 7–10 kHz.
  - After lock, source data takes three frames to synchronize.
  — OS8104 §9.1–9.2
- §9.3, Fig. 9-2: the FLT loop filter is 2.2 kΩ + 0.1 µF. A metal-film capacitor is recommended because ceramic parts can cause unlocks under vibration, and FLT leakage above 1 µA degrades APWD tolerance. No loop bandwidth or jitter-transfer figure appears anywhere in the datasheet (text search). — OS8104 §9.3

### Inferences
- **Realistic ring offset.** A crystal-timed master holds Fs to its crystal's tolerance. With ±50 ppm at 25 °C plus AT-cut temperature drift and aging (neither given in the datasheet), a ring offset on the order of ±100 ppm is the realistic envelope. This is my estimate, not a datasheet number. Reaching the ±1000 ppm limit needs a master slaved to an external source on S/PDIF or SCK.
- **Slaves are not the limit.** They lock anywhere from 37.9 to 48.1 kHz, about ±12 % around 43 kHz, so the ±0.1 % question only matters for the repeater's own clock chip.
- **Master tolerance in UI (calculation).**
  - 25 ns = 1.13 UI at 44.1 kHz and 1.23 UI at 48 kHz.
  - For revisions B and C, 1/(3072·Fs) = UI/3, which is 7.38 ns at 44.1 kHz and 6.78 ns at 48 kHz.
  - This budget is shared by every node's wander, every node's accumulated jitter and the last link's jitter.
- **Slave loop bandwidth: unknown.** The FLT network's zero at 1/(2π·2.2 kΩ·0.1 µF) ≈ 723 Hz hints at a slave loop bandwidth somewhere from the high hundreds of Hz to a few kHz. Without the charge-pump and VCO gains this is a guess, so treat the OS8104 jitter-transfer corner as unknown.

### Gaps
- The OS8104 slave PLL bandwidth and jitter transfer, its slave-mode RX jitter tolerance (only the master tolerance is given) and its TX jitter generation are all unspecified.
- I did not check the master tolerance of other MOST25 NICs (e.g. the INIC family). Which NIC and revision acts as timing master in a given car is unknown.

## 3. Worked estimate: spectrum of the fs_sq quantization error, what a jitter-attenuating PLL of bandwidth B passes, and what changes with 1.26 ns edges

### Takeaway
At a 10.1 ns edge grid the error is 10.1 ns pp at every offset. What reaches the ring depends on a beat frequency:
- **Fixed-pattern lines at Fs/q and above:** any B up to about 500 Hz removes them. The residue is ≤ 0.22 ns at B = 60 Hz and ≤ 0.03 ns at 4 Hz.
- **The slow beat sawtooth:** its pp is T/q at |q·f_clk_s − p·Fs|, and it passes whenever that beat is below B. The q = 1 case passes the full ~10 ns, 8–11 ns pp or 0.40–0.55 UI with loop overshoot, whatever B is.

That in-band part is ring wander or accumulated jitter, not SP1 jitter. It can use a third to nearly half of an OS8104 master's 25 ns tolerance, and it exceeds a revision B/C master's 7.38 ns on its own. B only changes how often this happens, about 2B/Fs of all offsets. Edges at 1.26 ns cut the worst case eightfold, to about 1.0–1.4 ns pp (≈0.05 UI).

### Cited Findings
- Inputs to the budget:
  - UI = 22.14 ns at 44.1 kHz. — PHY §2.1
  - SP4 link allowance: tDDJ4 0.15 UI and tUJ4 0.045 UI. — PHY Table 2-4
  - Wander is below 1 Hz and tracked by every slave PLL; UJ below the PLL cut-off accumulates; the master has no input PLL. — PHY §2.1.1.2, Table 2-6
  - Master tolerance: 25 ns pp for revisions after C, 1/(3072·Fs) for revisions B and C. — OS8104 §18.5.1
- The conformance test's example screenshots show 20 ns of system wander over temperature and 19.2 ns pp of accumulated DDJ+UJ under the worst-case pattern. These are examples, not limits. — CT §3.2.1, §3.2.3.1
- Loop bandwidth ranges:
  - Si5319 floor 60 Hz and Si5324 4–525 Hz. — [skyworks_jitter_attenuators.md](skyworks_jitter_attenuators.md)
  - AD9557 0.1 Hz–2 kHz. — [adi_microchip_cirrus_other.md](adi_microchip_cirrus_other.md)
  - 8T49N241 down to 0.2 Hz (task statement; see [renesas_ti_jitter_attenuators.md](renesas_ti_jitter_attenuators.md)).
  - ZL30253 14–500 Hz. — [ZL30252/53 datasheet §5.7.3](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)

### Inferences
All items below are calculation or simulation unless stated otherwise.

**Model.** Each fs_sq edge is emitted on the first clk_s edge after the true ring run edge. The error is e_k = T·frac(−k·r), with r = f_q/Fs_ring.
- f_q = 99 MHz gives T = 10.101 ns; the IDES8 grid, f_q = 792 MHz, gives T = 1.2626 ns.
- e_k lies in [0, T), so it is 10.1 ns pp: 0.50 UI at 48 kHz and 0.46 UI at 44.1 kHz. For 1.26 ns edges it is 0.062 / 0.057 UI.
- There is one phase-detector sample per frame (20.833 µs at 48 kHz, 22.676 µs at 44.1 kHz).
- 1 UI equals one period of clk = 1024·Fs.

**Spectrum.** The sawtooth's Fourier series puts line m at the folded frequency f_m = |m·f_q − N·Fs|, where N·Fs is the nearest multiple, with amplitude T/(π·m) peak. That is 3.2 ns/m for 10.1 ns edges and 0.40 ns/m for 1.26 ns edges. Total rms is T/√12: 2.9 ns and 0.36 ns. When r is near a fraction p/q, the error splits into two parts:
1. a fixed pattern repeating every q frames, with lines at multiples of Fs/q (high frequency when q is small);
2. a slow beat sawtooth of T/q pp at f_beat = |q·f_q − p·Fs|.

**Where the bad offsets sit with f_q = 99 MHz.**
- **48 kHz.** r_nom = 2062.5 exactly (q = 2).
  - At the exact nominal ratio the error only alternates between 0 and 5.05 ns at 24 kHz.
  - Any offset δ adds a 5.05 ns pp sawtooth at 198 MHz·|δ|: 1 ppm gives 198 Hz, 0.1 ppm gives 19.8 Hz.
  - The full 10.1 ns sawtooth (q = 1), with beat 99 MHz·|δ − δc|, occurs at δc = +242.5, −242.4, +727.8 and −726.7 ppm.
- **44.1 kHz.** r_nom = 110000/49 = 2244.898.
  - At the exact ratio the pattern repeats every 49 frames, giving lines at multiples of 900 Hz; its biggest low-frequency part is a ~1 ns pp q = 10 sub-sawtooth at 900 Hz.
  - q = 1 occurs at δc = −45.45 ppm, inside ordinary crystal tolerance, and again at +400.2, −490.7, +846.2 and −935.5 ppm.

**With f_q = 792 MHz.**
- At 48 kHz, 792 MHz / 48 kHz = 16500 exactly, so q = 1 sits right at the nominal ratio and repeats every 60.6 ppm.
- At 44.1 kHz the ratio is 880000/49: q = 1 at +10.23 ppm, then every 55.7 ppm.

**Frequency planning cannot dodge this.**
- Over ±100 ppm, frac(r) sweeps ±0.21 at 99 MHz. That window, 0.41 wide, is wider than the largest gap (1/3) between fractions with q ≤ 3, so a ≥ 3.4 ns (T/3) sawtooth always has an offset where it falls in band.
- At 792 MHz the sweep is ±1.65, so q = 1 points always lie inside it.

**What the PLL passes.** Model: a type-2 loop, flat to about B and falling 20 dB/decade above it.
- Fixed-pattern lines at Fs/q and above are removed when q is small.
- The beat sawtooth passes whenever f_beat < B, and passes completely (plus type-2 overshoot) when f_beat ≪ B.
- **How often.** As δ varies, the q = 1 beat spreads evenly over 0…Fs/2, so it is in band for about 2B/Fs of all offsets. At 48 kHz that is 4×10⁻⁶ (0.1 Hz), 1.7×10⁻⁴ (4 Hz), 2.5×10⁻³ (60 Hz) and 2.2×10⁻² (525 Hz). This share does not depend on the edge grid; only the amplitude does.
- **How wide.** Each crossing's window is ±B/f_q in δ. At 99 MHz that is ±0.001 ppm (0.1 Hz), ±0.04 ppm (4 Hz), ±0.61 ppm (60 Hz) and ±5.3 ppm (525 Hz); at 792 MHz each window is eight times narrower.

**Simulation.** Model: numpy, a type-2 loop with ζ = 1, B taken as the −3 dB bandwidth, and output pp measured after settling (script `scratchpad/fsq_sim2.py`). Values are output pp in ns.
- **"generic"**: δ = +37 ppm.
- **"beat = B/2"** and **"beat = 10B"**: δ placed near the nearest q = 1 crossing.

| Fs | Edge grid | B | generic (+37 ppm) | q = 1, beat = B/2 | q = 1, beat = 10B |
|---|---|---|---|---|---|
| 48 kHz | 10.1 ns | 0.1 Hz | 0.001 | 8.17 (0.40 UI) | 0.64 |
| 48 kHz | 10.1 ns | 4 Hz | 0.026 | 8.17 | 0.64 |
| 48 kHz | 10.1 ns | 60 Hz | 0.148 | 8.17 | 0.74 |
| 48 kHz | 10.1 ns | 525 Hz | 0.794 | 8.23 | 1.16 |
| 44.1 kHz | 10.1 ns | 0.1 / 4 / 60 / 525 Hz | 0.002 / 0.026 / 0.217 / 0.942 | 8.17–8.23 (0.37 UI) | 0.64 / 0.64 / 0.71 / 1.05 |
| 48 kHz | 1.26 ns | 0.1 / 4 / 60 / 525 Hz | 0.000 / 0.002 / 0.016 / 0.102 | 1.02–1.03 (0.050 UI) | 0.08 / 0.08 / 0.08 / 0.15 |
| 44.1 kHz | 1.26 ns | 0.1 / 4 / 60 / 525 Hz | 0.000 / 0.003 / 0.033 / 0.174 | 1.02–1.03 (0.046 UI) | 0.08 / 0.08 / 0.09 / 0.13 |

Extra runs (48 kHz, 10.1 ns edges, B = 60 Hz):
- q = 2 with beat = B/2 gives 4.12 ns.
- q = 2 with beat = B/20 gives 5.58 ns.
- q = 1 with beat = B/20 gives 11.09 ns (0.545 UI): the whole sawtooth plus about 10 % type-2 overshoot.
- At the exact nominal ratio, the 48 kHz 24 kHz alternation is removed completely (0.000–0.001 ns). At 44.1 kHz nominal the residue is 0.10 ns at 60 Hz and 0.93 ns at 525 Hz.

**Which part counts against what (my position).** What the attenuator passes is phase variation of the repeater's Tx relative to the ring:
- Below 1 Hz it is wander (tW).
- From 1 Hz up to the downstream NIC's PLL cut-off it is accumulated jitter (tUJacc-type).
  - Every slave tracks both.
  - Both add peak-to-peak at the master's Rx, inside a 25 ns budget (revisions after C) that the ring's own wander and jitter already share.
- Above the downstream cut-off it is link jitter at the next node's clock recovery. That sits on top of the SP4 allowance of 0.045 UI UJ (≈0.92 ns) and 0.15 UI DDJ (≈3.05 ns) at 48 kHz.
- None of it is SP1 tUJ1.
- The 40 dB target of the other notes (10 ns down to about 0.1 ns) is the right order only for the out-of-band residue. There, B ≤ ~60 Hz is enough: 0.15–0.22 ns at 60 Hz, 0.03 ns at 4 Hz. A 525 Hz loop leaves 0.8–0.9 ns, about the whole SP4 UJ allowance.

**Worst case with 10.1 ns edges.**
- Output is 8.2 ns pp (beat = B/2) to 11.1 ns pp (beat → 0): 0.40–0.55 UI at 48 kHz.
- That is 33–44 % of a 25 ns master tolerance, and more than the entire 7.38 ns (1/3 UI) of a revision B/C master.
- No choice of B removes it; a lower B only narrows the offset windows.
- At B = 0.1 Hz the window is ±0.001 ppm and the sawtooth is slower than 0.1 Hz. It then appears only as a transient while the two crystals' relative drift crosses a window: wander-like, but still up to about 10 ns.
- With 99 MHz edges at 44.1 kHz, one q = 1 point sits at −45 ppm. A car whose relative offset parks there sees this repeatedly with a 60–525 Hz loop.

**With 1.26 ns edges.**
- Every amplitude drops 8× (−18 dB).
- The worst in-band case is 1.02–1.03 ns pp at beat = B/2, about 1.4 ns with overshoot as the beat goes to zero (≈0.05–0.07 UI). That is 4–6 % of 25 ns, about one link's SP4 UJ allowance, and 14–19 % of a revision B/C master.
- The generic residue is ≤ 0.03 ns at 60 Hz and ≤ 0.17 ns at 525 Hz.
- The ring edges themselves already carry up to about 4 ns pp of upstream link DDJ+UJ (the SP4 limits), which any slave's PLL also faces. With 1.26 ns edges the quantization term is smaller than that, so the repeater behaves like an ordinary node; with 10.1 ns edges it does not.

**Design option (inference, not evaluated in detail).** Error feedback would reach the same worst case without a fine output serializer:
- Carry each frame's coarse-grid error, which the 792 Msps capture measures to 1.26 ns, into the next edge's choice.
- This high-passes the 10.1 ns error by |2 sin(πf/Fs)|, which is −42 dB at 60 Hz for 48 kHz.
- It leaves only the unshaped 1.26 ns measurement term, the same worst case as a 1.26 ns output.

### Gaps
- The downstream OS8104 PLL cut-off is unknown, so residual lines between about 1 Hz and a few kHz cannot be split into "accumulates around the ring" versus "filtered at the next node".
- The model assumes ideal edge detection and a type-2, ζ = 1 loop; real attenuators differ in peaking and order. The ring's own edge jitter and the 792 Msps detection error were not simulated.
- How much of the 25 ns a real car ring already uses is unknown; the conformance-test figures are examples only.
- The relative drift rate between the ring's and the local crystal, which sets how long the offset dwells in a bad window, was not quantified.

## 4. How far each shortlisted chip can follow the ring (±1000 ppm?)

### Takeaway
Only three parts document a range that covers ±1000 ppm:
- **The DCXOs.** SiT5358 offers ±1200, ±1600 or ±3200 ppm; Si570 changes up to ±3500 ppm without interrupting the output.
- **ZL30253**, at its maximum setting: hold-in ±1000 ppm, but pull-in only about ±500 ppm.

The other three are limited differently:
- **Si5319/Si5324** state no ppm limit. They follow any static offset that is present when ICAL runs, but may recalibrate by themselves if the input moves 500 ppm or more after that.
- **AD9557**'s DPLL can be opened to ±1000 ppm, but its output APLL is only guaranteed ±100 ppm around its calibration frequency.
- **8T49N241/242** document nothing beyond an assumption of input references stable to 100 ppm or better.

For crystal-timed rings, all of them are adequate if calibration is done with the ring's own rate applied.

### Cited Findings
**Skyworks Si5319 / Si5324 (Si53xx Family Reference Manual Rev 1.3, 10/16)**
- §6.11.8, loss of lock:
  - LOL comes from comparing input and feedback clock phase. Each potential cycle slip retriggers a one-shot, and LOL clears after a slip-free retrigger time.
  - LOCKT sets that time, selectable from 0.833 to 106 ms (Table 45).
  - LOL is held during calibration. No frequency window is involved.
  — [Si53xx-RM §6.11.8](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- §6.2.1, self-calibration (ICAL):
  - Automatic ICAL starts when internal DCO registers go out of range (meaning the DCO must relock), or when ICAL = 1 is written. The user must write ICAL = 1 after writing dividers or PLL registers.
  - It starts only with a valid selected input and, on narrowband parts, the XA/XB reference present.
  - During ICAL the outputs either run with up to ±20 % frequency excursion (SQ_ICAL = 0) or are squelched (SQ_ICAL = 1).
  - After one good ICAL, a lost input sends the part into digital hold, and it relocks without a new ICAL when the input returns.
  — [Si53xx-RM §6.2.1](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- §6.2.2: ICAL needs the selected CKIN stable and inside the range DSPLLsim reports; other CKINs must be within 100 ppm of nominal or squelched. §6.2.3: if the selected CKIN has moved 500 ppm or more since the last calibration, the device may start a self-calibration. — [Si53xx-RM §6.2.2–6.2.3](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Table 26: CKIN 2 kHz–710 MHz, f3 2 kHz–2 MHz, fOSC 4.85–5.67 GHz, each with a 500 ppm margin at both ends. §6.2.1.1: Si5324 lock time with FAST_LOCK is typically 1–5 s, and LOCKT = 001 is recommended. — [Si53xx-RM Table 26, §6.2.1.1](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- §6.11.2–6.11.3, FOS:
  - FOS covers Si5324; Si5319 is not in its device list.
  - It compares an input against a FOS reference: CKIN2 by default, or XA/XB, but only in the 37–41 MHz band.
  - Thresholds are selectable for SONET-minimum-clock or Stratum 3/3E compatibility (values are in the device datasheet), and FOS_EN switches it off.
  — [Si53xx-RM §6.11.2–6.11.3](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- A single register set (N31 = 1, N2 = 112,640, N1 = 110) keeps fOSC at least 2.3 % inside the VCO limits at ±0.1 % Fs for both rates. — [skyworks_jitter_attenuators.md](skyworks_jitter_attenuators.md)

**Renesas 8T49N241 / 8T49N242 (datasheet dated Aug 1, 2025)**
- p. 8: inputs do not support spread-spectrum sources. The family assumes input references stable to 100 ppm or better, except for gapped clocks. The same sentence is in the 8T49N242 text. — [8T49N241 datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet); 8T49N242 text (a scratch file, not kept)
- p. 8, input clock monitor:
  - It detects loss of signal (LOS) only.
  - A counter of monitor-clock edges (VCO/8, i.e. 375–500 MHz for a 3–4 GHz VCO) is set slightly longer than the nominal input period, with a suggested margin of 2–3 monitor clocks; the counters are 17-bit.
  - One expiry raises a soft alarm that freezes PLL tracking; a second declares LOS.
  — [8T49N241 datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet)
- Register map, digital PLL feedback configuration:
  - Lock window LOCK[7:0] in 2.5 ns steps up to 640 ns (default 3Fh, i.e. 157.5 ns — calculation).
  - Phase-slope control SLEW: no limit (default), 64 µs/s or 11 µs/s.
  - A holdover option returns to the centre of the VCO tuning range.
  — [8T49N241 datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet)
- No DPLL pull-in or hold-in range is specified anywhere in the datasheet. — [renesas_ti_jitter_attenuators.md](renesas_ti_jitter_attenuators.md); confirmed by my search of the local text.

**ADI AD9557 (datasheet Rev. C; text read from an identical mirror copy)**
- DPLL setup includes pull-in range limits (upper and lower, as 20-bit frequency tuning words). A digital tuning-word clamp keeps the DPLL output inside a set range, which also keeps the APLL VCO inside its tuning range. — [AD9557 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf) ([mirror](https://www.marutsu.co.jp/contents/shop/marutsu/ds/AD9557.pdf))
- Reference monitor:
  - It compares the measured reference period with a nominal period, using an inner and an outer tolerance for hysteresis; each tolerance is stored as its reciprocal (50 ppm → 20,000).
  - Table 8: the out-of-range limit is programmable up to 10⁵ ppm (Δf/fREF), with a lower bound limited by SYSCLK accuracy; the validation timer runs 0.001–65.535 s.
  — [AD9557 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)
- APLL:
  - It multiplies the DPLL output (usually 175–200 MHz) up to 3.35–4.05 GHz.
  - VCO calibration centres the control voltage at the frequency present during calibration, and must be repeated whenever the APLL frequency changes.
  - In the output-frequency-adjustment section, adjustment is limited to ±100 ppm before the APLL needs recalibration. Larger variations are possible, but lock over temperature extremes may be compromised.
  — [AD9557 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)
- DPLL lock detectors: the phase threshold goes up to 65.535 ns and the frequency (period-difference) threshold up to 16.777 µs. — [AD9557 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)

**Microchip ZL30253 (ZL30252/ZL30253 datasheet, Jan 2018)**
- §5.7.3:
  - The DPLL tracking range is settable from ±1 to ±1000 ppm, and the FLIM status bit flags when the limit is reached.
  - Hold-in equals the tracking range. Pull-in should be taken as half of it for reasonable pull-in time, i.e. ±500 ppm at the ±1000 ppm setting.
  - Lock criteria can also declare loss of lock when the fractional frequency offset exceeds the limit.
  - Loop bandwidth is 14–500 Hz.
  — [ZL30252/53 datasheet §5.7.3](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)
- §5.6.2: the frequency monitor is a percent monitor, 1–20 % in 1 % steps. §5.7.4: wander is tolerated until the apparent long-term frequency offset exceeds the input-monitor threshold. Inputs run from 1 kHz to 1250 MHz (1 kHz–300 MHz for CMOS). — [ZL30252/53 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)

**Architecture B oscillators**
- SiT5358 offers pull-range options up to ±1200, ±1600 and ±3200 ppm, set over I²C. — [dcxo_architecture_b.md](dcxo_architecture_b.md), citing the [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- Si570's DCO can move up to ±3500 ppm from the centre setting without interrupting the output; larger changes interrupt it. — [Si570/571 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si570-71.pdf) (read from the local text copy)

### Inferences
**Verdict per chip**

| Chip | Documented range | What actually limits it | ±1000 ppm? |
|---|---|---|---|
| Si5319 / Si5324 | No ppm figure. LOL is a cycle-slip detector with no frequency window. | The calibration point: a move of 500 ppm or more since ICAL may trigger an automatic ICAL (output ±20 % or squelched). Table 26 VCO limits, 500 ppm margins. | **Yes as a static offset**, if ICAL runs with the ring's fs_sq applied. **No as a swing after ICAL** larger than 500 ppm. Si5319 has no FOS; on Si5324 leave FOS_EN off. |
| 8T49N241 / 242 | None; only an assumption of references stable to 100 ppm or better. | Not documented. The LOS count must cover the longer period. The VCO (3–4 GHz) has ample raw range. | **Undocumented.** Needs a Renesas statement or a bench test. |
| AD9557 | DPLL pull-in limits and clamp programmable; monitor up to 10⁵ ppm. | APLL: ±100 ppm around its calibration frequency, beyond which lock over temperature extremes may be compromised. | **DPLL yes; APLL only after calibrating at the ring's actual rate**, then a ±100 ppm drift budget. |
| ZL30253 | Hold-in ±1…±1000 ppm; pull-in about half. | Maximum setting reached; pull-in ±500 ppm "for reasonable time". | **At the edge.** Holds ±1000 ppm, but acquisition beyond ±500 ppm may be slow. |
| SiT5358 (arch. B) | ±1200 / ±1600 / ±3200 ppm options | Pull option | **Yes**; the ±1600 or ±3200 ppm option leaves margin. |
| Si570 (arch. B) | ±3500 ppm without interruption | — | **Yes** |

**Common points**
- **Offset seen by each chip.**
  - For ZL30253, and for the DCO-type steering limits the other notes list, the offset to follow is the ring's error minus the local reference's error. Those limits are LMK05318B ±100 ppm; RC310xxB and 8A34001 ±244 ppm frequency-control-word range; and an 8A34001 input monitor of about ±100 ppm (task statement and [renesas_ti_jitter_attenuators.md](renesas_ti_jitter_attenuators.md), not re-verified). For example, a −100 ppm ring with a +50 ppm local oscillator is 150 ppm to follow.
  - For Si5319/Si5324 and AD9557, what matters is distance from the calibration frequency, which the actual input sets at calibration time.
  - This is my reading of how those limits are referenced; the datasheets do not say it in these words.
- **Crystal-timed rings.** The OS8104 recommends ±50 ppm at 25 °C (typical), so I expect about ±100 ppm with drift. All shortlisted chips would follow such a ring, provided the Si53xx ICAL and the AD9557 APLL calibration run with the ring present. The ±1000 ppm case only separates the chips for a master slaved to an external Level-II source (section 1).
- **Settings the design must respect.**
  - **8T49N241 LOS count.** At 48 kHz, 0.1 % of the 20.83 µs period is 20.8 ns, i.e. 8–11 monitor clocks, so the count needs about 11–14 clocks of margin instead of the suggested 2–3. At 44.1 kHz it is 8.5–11.3 clocks.
  - **AD9557 phase-lock threshold.** It must exceed the frame-to-frame fs_sq phase step, about 10 ns pp with 10.1 ns edges or 1.3 ns with fine edges, plus the ring's input jitter; otherwise the lock indication will chatter (inference).
  - **Si53xx ICAL timing.** ICAL should be issued only after the FPGA has a valid ring lock, not from a free-running local fs_sq, so that a ring appearing far from nominal does not land 500 ppm or more from the calibration point.

### Gaps
- **8T49N241/242.** The real DPLL tracking and pull-in range is undocumented; it needs a vendor answer or a bench test at ±1000 ppm.
- **Si5319/Si5324.**
  - The FRM gives no numeric tracking range after ICAL.
  - The 500 ppm auto-ICAL condition is worded "may", not "will".
  - I did not extract the Si5324 FOS threshold values, which are in the device datasheet.
- **AD9557.**
  - I did not extract the default pull-in limit registers.
  - The ±100 ppm APLL statement sits in the adaptive-clocking (frequency-adjustment) section. That it applies equally when the DPLL follows an offset reference is my reading, though its APLL-calibration section supports it.
- **ZL30253.** That its ±1000 ppm range is referenced to the local master clock, so that local oscillator error eats into it, is my reading.
- **LMK05318B, RC310xxB, 8A34001.** I did not re-verify the other researchers' figures.
