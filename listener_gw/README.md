# MOST25 listener gateware, v0.2

FPGA code for the MOST25 listener in `listener_hw/`. Target: Sipeed
Tang Nano 20K (GW2AR-LV18QN88C8/I7). It sits in the ring as an invisible
repeater, never sends a message of its own, and puts out:

- **the ring, regenerated**: every edge retimed on a ring-locked clock, bit
  for bit and preamble for preamble what came in;
- **every frame byte on TDM**: two TDM8 x 32-bit lines, one TDM frame = one
  MOST frame, BCLK = 256 Fs from the ring - the frame as it leaves the
  listener, our injected audio included;
- **MCLK = 512 Fs**, also from the ring: a DSP or codec runs synchronously at
  44.1/48 kHz (512 Fs) or 88.2/96 kHz (256 x 2 Fs). Higher rates are an
  upsampling job for that DSP; the ring itself carries 44.1/48 kHz;
- **raw control blocks on UART**: 32 bytes per block plus a frame counter,
  3 Mbaud. Telegram decoding and the CRC belong to the receiving software;
- **what the factory amplifier would play, as stereo I2S** (J3): the host
  (ESP32 module M2 on the board) reads the control traffic, finds which frame
  bytes carry up to three sources (the main one, navigation, phone: each
  sink's Connect, 0x22.0x111, lists the channels) and what the head unit told
  the amplifier (volume, balance, tone), and sends the byte positions and the
  coefficients back on UART_RX. The FPGA applies them sample by sample
  (section J3). BCLK 64 Fs, 32-bit slots, 24-bit data, MCLK 512 Fs. The
  sources are taken from the frame as it leaves the listener: while our audio
  replaces the AUX source's bytes, J3 carries our audio, as the factory
  amplifier after us does.

- **audio into the ring** (optional, DIN from the host M2): the host names up
  to six frame bytes (e.g. the AUX source's channels) and our own samples
  replace them on the way out. Everything else - preambles, other bytes, the
  control channel - leaves edge for edge as it came in.

Host command 01, where a source is in the frame (UART_RX, 3 Mbaud 8N1;
packet format in `rtl/host_cmd.v`):

```text
A5 5A 01  P  L0 L1 L2  R0 R1 R2  X
  P[1:0]  0 = off (zeros in), 2 = 16 bit, 3 = 24 bit
  P[2]    mono: the left bytes only, to both sides
  P[5:4]  stream 0..2 (0 = the main source, which the tone applies to)
  P[7:6], P[3] zero; anything else refuses the packet
  L0..L2  frame byte index (0..63, as on the TDM output) of the left sample, MSB first
  R0..R2  the same for the right sample; L2/R2 ignored at 16 bit, R0..R2 when mono
  X       XOR of the 10 bytes before it; a packet with a wrong X changes nothing
```

P = 0, 2 or 3 is stream 0 in stereo, as the command was before there were
three streams. A command takes effect at the next frame boundary, so no
sample is ever assembled from two different position sets.

Host command 03, one coefficient word for J3:

```text
A5 5A 03  A  V3 V2 V1 V0  F  0  X
  A       address 0..63 (map in sim/dsp_asm.py)
  V3..V0  the word, Q4.28, most significant byte first
  F[0]    commit: after this word, the set written becomes the set in use
  F[7:1] and the byte after F zero; anything else refuses the packet
```

Host command 02, audio in:

```text
A5 5A 02  M  L0 L1 L2  R0 R1 R2  X
  M[1:0]  0 = off, 2 = 16 bit, 3 = 24 bit;  M[7] = 1: do not touch the parity bit
  L0..R2  frame byte index of each sample byte, MSB first; only 1..60 accepted -
          a command naming byte 0 or 61..63 is refused as a whole
```

How it works (`rtl/inject.v`): the regenerator reports every run as it
starts; the injector re-draws the line one UI per clock and tracks the UI
position in the frame. It also hands the set it used for the frame just ended
(on or off, positions, the six bytes) to `tdm_out` and `amp_out`, which put
those bytes in place of the ring's: J2 and J3 show the frame as it left us,
not as it came - a DSP fed from J3 hears the phone as the factory amplifier
does. As first written they showed the received frame, so with the phone
playing into AUX, J3 carried the car's own AUX bytes. In biphase mark every bit cell opens with an edge and
a '1' adds one in the middle, so a different bit changes only that middle
edge - the cell length stays, the next cell still opens with an edge. Bit 511
(parity, Book 2 Table 5.1, rule unknown) is flipped by the XOR of all changed
bits, which keeps any XOR parity over those bits exactly as it was; M[7] turns
that off. Samples come in on DIN clocked by our own ring-locked BCLK/LRCK, so
one sample pair per MOST frame and no rate conversion; latency is fixed.
Injection runs only while the command is on, the injector has seen 8 frames in
a row exactly 1024 UI apart, and the I2S clocks run; any of these lost stops it
at once, and the line is copied again. A frame opens with a 3-UI run; a second
3-UI run inside the first 8 UI is part of the preamble (S/PDIF-like preambles
have one) and is copied, a 3-UI run anywhere else opens a frame anew.

## J3: the amplifier's outputs

What reaches the amplifier on the ring is the source's audio before any
volume: the amplifier applies what the head unit tells it. A listener that
feeds speakers of its own has to do the same, so J3 carries L and R as the
factory amplifier would play them - volume, balance, bass, treble, with
navigation and phone mixed in - but digitally, for a DAC, a DSP or an
amplifier of the owner's choice (through an I2S-to-optical converter, any
car DSP with an optical input). There is no front and rear: the head unit's
fader is left to whatever follows J3, which splits front, rear and sub
itself anyway.

`rtl/dsp_core.v` is a small multiply-accumulate engine that runs one fixed
program per ring frame; `rtl/amp_out.v` feeds it and serialises the result.
The program, its memory map and a bit-exact model are one Python file,
`sim/dsp_asm.py`, which generates the ROM (`rtl/dsp_prog.vh`) and the host's
map (`listener_fw/components/mostctl/include/dsp_map.h`):

- the three sources (command 01) are picked out of every frame, 16 or 24
  bit, stereo or mono;
- stream 0 runs through 8 biquads per side (bass, treble, loudness and room
  for the head unit's equaliser; unused ones pass straight through);
- L and R are each the sum of the three sources, each with its own gain:
  volume, balance and the navigation / phone levels are all in these six
  gains, which the host computes;
- the gains glide towards their targets, g = k t + (1 - k) g once per frame,
  so a volume step does not click (the host writes k t and 1 - k; k = 1
  makes a change instant).

Every word is 32 bit, Q4.28 (range +/-8, 1.0 = 2^28); products are Q8.56 in
a 72-bit accumulator; a 24-bit sample enters as sample << 5, so the filters
work 5 bits below the input's last bit. The biquads save the fraction below
their output's last bit and add it to the next sample's sum: a +12 dB shelf
at 40 Hz (poles close to z = 1) is off double precision by -159 dBFS that
way, and by -77 dBFS without it. The engine takes 3 clocks per instruction,
149 instructions: 449 of the 1024 clocks of a frame. The output leaves one
frame after its input, about two frames after the ring.

Coefficients live in two banks: the host writes the bank not in use and
commits with the last word; the engine switches only between two runs of
its program, so no frame is computed from half a set. Nothing is cleared by
a reset: after power-up everything is zero and J3 is silent until the host
has written a set.

## Ring clock

The regenerated line, TDM, I2S and MCLK all run on clk_r = 1024 Fs from a
Skyworks Si514, an I2C-programmable oscillator that the FPGA steers itself
(`rtl/dpll.v`, `rtl/si514_ctrl.v`):

1. Once the receiver is locked, 64 ring frames are counted on the 792 Msps
   time base. That picks 44.1 or 48 kHz and the ring's offset from nominal.
2. The Si514 is centred on that rate: a "large change" (output off, FCAL,
   up to 10 ms). This is the only time clk_r stops; LOCK is off then. Until
   this first centring the whole ring-clock domain (regenerator, TDM, J3,
   injection, MCLK) is held in reset: a part off the shelf powers up at
   whatever frequency the factory set, anything to 250 MHz, and that domain
   is built for 50.
3. Our own TX comes back through a second IDES8 (TX_FB). Each TX preamble
   minus the same preamble on RX_IN, to 1.26 ns, is the regenerator's delay.
   A PI loop holds that delay constant by writing the Si514's M as "small
   changes": glitch-free within +/-1000 ppm, 0.026 ppb steps, one every 24
   frames. It acquires at fn 40 Hz, then tracks at fn 2 Hz.

If the ring stops, M stays where it was (holdover). When the ring comes back
at the same rate and within 500 ppm, the loop carries on without re-centring.
The TX edges are retimed by a flip-flop (U9) on the same Si514 edge the
FPGA runs on (CLK+, through its own series resistor), so the ring sees the
oscillator's sub-picosecond jitter, not the FPGA's output jitter.

Any Si514 off the shelf fits, as long as its output is 3.3 V CMOS: the
letter after "514" in its part number is C, M or N. Nothing else in the part
number matters. Start-up frequency and stability are overwritten by the
centring, and nothing runs on the start-up frequency (corner `si_start`
powers the model up at 250 MHz). The I2C address is found: before the first centring the FPGA
probes 0x08..0x77 and takes the address that answers. U7's footprint carries
all three packages (5x7, 3.2x5, 2.5x3.2), and one of them is soldered.

The phase detector works on the 1.26 ns sample grid on purpose: frame edges
on the 99 MHz clock would let 8-11 ns of beat wander through any PLL (report
[docs/research/regen_clock/report.md](../docs/research/regen_clock/report.md)).

## Structure

```text
rtl/  rx_runlen    run lengths from 8 samples per clock (IDES8, 792 Msps), and each
                   edge's time in samples (1.26 ns)
      rx_classify  1/2/3 UI; learns the UI (44.1 or 48 kHz) and the pulse-width bias,
                   both kept to what a MOST25 line can be, relearned after 5 ms unlocked;
                   every run also leaves with its length in whole UI (an error run its
                   rounded one), and the run after a two-edge sampler word is an error
      rx_framer    bits, frames, block index, parity; lock, kept through one bad frame
                   if the next opens on time; the UI 0 and UI 512 edges of every frame
                   with their sample times
      fs_fine      the frame-rate square wave, edges placed to the sample, 8 bits
                   per clock - for a board with an external clock multiplier
                   (the Tang Nano board does not use it; synthesis removes it)
      regen        the runs, in whole UI and errors included, through an async FIFO,
                   out on clk_r = 1024 Fs
      tdm_out      2 x TDM8, BCLK = clk_r / 4; the injected bytes in place of the ring's
      ctrl_uart    control blocks -> 42-byte packets
      uart_rx      host commands in, 8N1 at the same baud
      host_cmd     11-byte command packets, XOR checked
      amp_out      J3: picks up to 3 sources out of every frame (as it left us: the
                   injected bytes in place of the ring's), coefficient banks
                   (commands 01, 03), dsp_core, two I2S lines on the TDM frame count
      dsp_core     the multiply-accumulate engine; its program is dsp_prog.vh,
                   generated by sim/dsp_asm.py
      inject       re-draws the regenerated line and swaps chosen bytes for DIN samples
      tx_pre       time-stamps the preambles of our own TX, fed back (TX_FB): one
                   per frame, the first 3-UI run at least 1016 UI after the last
      dpll         the ring clock loop: rate measurement, Si514 centring, then
                   the TX-behind-RX delay held constant through the Si514's M
      si514_ctrl   finds the Si514's I2C address; its large (FCAL) and small
                   frequency changes
      i2c_master   byte-level I2C master, 393 kHz
      listener_core  all of the above + the LOCK decision (in clk_s; it also needs our
                   TX back on TX_FB at least every 4 frames)
board/ top_tangnano20k.v  rPLL 396 MHz, CLKDIV 99 MHz, two IDES8 (RX_IN, TX_FB);
       pins as in the schematic. Pins follow the Sipeed datasheet v1.3
       (corrected pinout): ring and Si514 signals only on pins shared with the
       empty LCD connector; the BL616 HSPI lines and the TF slot lines 80, 85
       carry only the host UART, MCLK, I2S and TDM SD1. TX_FB comes in through
       IDES8 on pin 25; an 8:1 deserialiser takes the whole IOB pair, so pin 26
       stays unused
       tangnano20k.cst / .sdc / build.tcl   Gowin EDA batch build
sim/  make_stim.py  frames from virtual_most_source, distorted to the SP4 limits, sampled at
                    792 Msps; the preamble's run pattern is a parameter (--preamble)
      run_rx.py     receiver regression, 10 corners and 4 noise bursts
      dpll_model.py frame-level model of the clock loop, used to pick the gains
      si514_model.v behavioural Si514 from its data sheet: I2C registers, small
                    and large changes, FCAL, the factory start-up frequency, and
                    checks of how it is driven
      tb_dpll.v + run_dpll.py     the loop against the Si514 model and a
                    frame-level ring, 150-200 ms per corner, 9 corners
      sweep_core.py the whole-core test over random rings: rate, pulse width,
                    jitter, ring offset, the Si514's own error and address,
                    the preamble's shape, early commands, dead lines
      tb_core.v + check_core.py   whole core, Si514 model on its I2C bus, TX
                    fed back at 792 Msps
      dsp_asm.py    J3's engine: its program (writes rtl/dsp_prog.vh), memory map
                    (and the firmware's dsp_map.h), a bit-exact model and the
                    coefficient words for a setting
      tb_dsp.v + run_dsp.py   amp_out alone against that model, bit for bit
```

## Verified, and how

| What | How | Result |
|---|---|---|
| Receiver: 44.1 / 48 kHz, PWD -0.15 / +0.316 UI, jitter 0.195 UI, FS +/- 0.1 %; the placeholder preamble and the S/PDIF-like one (two 3-UI runs in a preamble) | `python sim/run_rx.py` | 10/10 corners: every locked frame byte-exact, every run class right |
| Receiver after noise | `run_rx.py`, four more corners: 5 us of noise (runs of 9..12 samples, 0.56..0.75 UI) over frame 16 of a line at PWD -0.15 UI | as built (ui kept in 15.5..18.25 samples, b within +-7.5, relearning after 5 ms unlocked): decoding again 2 to 6 frames after the burst at 48 and 44.1 kHz (the framer keeps its lock through the first bad frame), every frame after it right and in order; with relearning alone (bounds off, 0.25 ms) it comes back after the relearn; with neither it stays lost at ui 11.6 samples (0.72 UI), the false point the loops fell into before - an outside review found it, the corner reproduces it |
| Clock loop, real parameters | `python sim/run_dpll.py`: `tb_dpll.v` runs dpll + si514_ctrl + i2c_master against the Si514 model and a frame-level ring and regenerator (preamble jitter 0.5 ns rms), 150-200 ms simulated per corner | 9/9: 48 kHz at 0, +1000 and -1000 ppm; 44.1 kHz on a beat point (+10.23 ppm) and at +1000 ppm; a 5 ms ring dropout; a Si514 100 ppm off on its own (the widest stability grade on the shelf; the centring cannot see that error, the loop takes it out: 48 kHz at +1000 ppm with -100, 44.1 kHz at -1000 ppm with +100); a disturbed I2C bus (the Si514 ignores its address for 0.6 ms while tracking: two transfers refused, no re-centring, lock kept, and the NACK flag - which holds LOCK off - clears with the next update; with a sticky flag, as first written, it stayed set and LOCK would not have come back until the ring restarted). The Si514's I2C address differs per corner (0x08, 0x55, 0x6A, 0x77 - the ends of the probed range included) and is found by one scan each. Lock in 32-66 ms; largest delay excursion 69 samples (87 ns) with a Si514 within 50 ppm, 141 samples (178 ns) at 100 ppm, of the FIFO's +/-600; last half within 0-5 samples; M ends within 0.02 ppm of the ring; one FCAL each (the dropout resumes without re-centring), no small change outside the +/-1000 ppm window, no slip, nothing addressed wrongly |
| Whole core with the Si514, 48 kHz PWD +0.316 ring at 0 ppm and 44.1 kHz PWD -0.15 ring at -1000 ppm | `python sim/run_core.py` (`tb_core.v`, `check_core.py`), seven corners; the loop is sped up for simulation (8-frame rate measurement, an update every 4 frames, fn 150 / 30 Hz) | the Si514 model sits at I2C address 0x6A and the core finds it after 98 probes (0x08..0x69); one FCAL and 53 small changes each, all inside the window, reg 132's reserved bit kept, nothing addressed wrongly, HS_DIV 44 / 48; LOCK at 1.5 / 1.7 ms; clk_r ends +0.24 / -0.01 ppm from 1024 x the ring's Fs; TX after LOCK 27704 / 25580 runs, 0 wrong; TDM 168 / 162 frames under LOCK byte-exact in order; UART packets correct. This test found that the FIFO's read side, reset alone while the Si514 is centred, restarted from pointer 0 against a running writer - near full, dropping runs without flagging it; it now aligns to the writer first. Corner `inj_early` sends "inject" before the Si514 is centred: the injector as first written cleared its copy of the command with the ring domain's reset and never injected (0 of 168 frames); it now keeps it (83 injected, then pass-through again after "off") |
| Preamble shape | `run_core.py` corner `pre2`: core48 with S/PDIF-like preambles, 3-3-1-1 and 3-1-1-3 for a block start | every check passes, LOCK at 1.5 ms as with the placeholder. As first written, tx_pre stamped every 3-UI run and the loop saw two events per frame (LOCK came at 4.4 ms in this test, with twice the corrections), and inject.v took the preamble's second 3-UI run for a lost frame and never injected (0 of 34 frames); the stimulus and its test had only ever produced one 3-UI run per preamble, and asserted it |
| Random rings | `python sim/sweep_core.py --jobs 1`, twice (seeds 1000 and 2000, 32 cases each): per case the rate, PWD -0.15..+0.316 UI, jitter 0.1..0.195 UI, ring -1000..+1000 ppm, the Si514's own error -100..+100 ppm and its I2C address 0x08..0x77 are drawn; ~30 % send "inject" before the Si514 is centred; every third kills the line for 5..50 us 2 ms after LOCK | 64/64: all eight checks (or the dead-line checks) pass; LOCK after 1.3-8.4 ms of simulated loop, dead lines dropped LOCK in 0.07-1.5 us and it came back 71-83 frames later without re-centring. The first draft of the sweep (360-frame rings, the Si514 within 50 ppm, the dead line at a fixed time) failed 6 of 32 cases, none of them in the design: LOCK came at 6.7-6.8 ms, because the centring cannot see the Si514's own crystal error and the simulated loop has to pull it in, so the test ended, or the line died, before the host's commands were through. One later case failed on the TX check itself: 400 runs taken from a frame's zero bytes matched the ring in several places; windows now grow until they match in exactly one. Rerun after the receiver's guards and the TX_FB check (seed 1000, one case at a time, `--jobs 1`): 32/32, dead lines dropped LOCK in 0.07-1.5 us and it came back 71-83 frames later, as before |
| MCLK | `check_core.py` | exactly 512 MCLK periods per TDM frame under LOCK, 44.1 and 48 kHz |
| A shelf part's start-up frequency | `run_core.py` corner `si_start`: core48 with the Si514 model powering up at 250 MHz, the top of its range; every corner also logs the first MCLK and BCLK edges against the moment the loop reports the centring | every check passes; MCLK's and BCLK's first edges come after the centring in every corner (before: the ring domain ran on the start-up frequency until then, MCLK on J2/J3 with it - out of timing above 78 MHz, and with a model that always started at 49.152 MHz nothing saw it) |
| Clock dead, the board's watchdog | `run_core.py` corner `clk_stop`: core48, clk_s stops for good 300 us after LOCK; tb_core.v models U11 (TX_SEL = LOCK and a TX rising edge within 10 us). Every core corner also checks that the model never dropped TX_SEL while LOCK was on | LOCK stays on - no clk_s logic can help; TX's last edge 1.3 us after the stop (the FIFO runs dry), TX_SEL - bypass - 11.4 us after. 0 false drops in all seven corners (commands, injection on and off, a dead line, dead feedback) |
| One bad bit on the line | `run_core.py` corner `bit_err`: core48 without injection, one edge of the line removed in frame 120 (two runs merge into a 3-UI run inside the data, 1 ms after LOCK) | LOCK stays on to the end of the stimulus; every regenerated run equals the ring's, the wrong one included; TDM loses exactly frame 120 (frame 119 once more, then 121) and is right and in order otherwise; the damaged block's packet is withheld and good ones follow. Before: the framer unlocked on the first error, the regenerator's FIFO was emptied, LOCK fell and stayed off for HOLD_RE - two phase steps on the ring and two mutes of the amplifier, from one bit |
| TX feedback lost | `run_core.py` corner `fb_dead`: core48, TX_FB forced dead 200 us after LOCK and kept dead (what the FPGA sees if U9's output sticks) | LOCK drops 3.4 frames after it and stays off. Before, it stayed on until the ring input itself ended, 3.3 ms later: nothing in LOCK looked at TX_FB |
| Dropout and re-entry | `run_core.py` corner `gap`: a 480-frame 48 kHz ring (PWD +0.2 UI), the line dead for 20 us 2 ms after LOCK (the tb places it after LOCK, wherever LOCK comes) | LOCK drops 1.4 us after the line dies, when the FIFO runs dry; the framer keeps its lock through the gap (one lost frame, the next preamble on time), so the loop stays in tracking and holds M; LOCK returns 25 frames after the line, HOLD_RE 24 in that test plus one. With the real parameters HOLD_RE alone is > 200 ms |
| J3 in the whole core | `tb_core.v` writes a coefficient set over the UART (every biquad straight through, stream 0 to L x 1 and R x 0.5, committed with the last word), then a wrong-XOR command, 24-bit scrambled positions, and 16-bit positions mid-run; `check_core.py` decodes J3 | 48 kHz: 49 + 92 frames per config; 44.1 kHz: 45 + 92; every frame equals the commanded bytes of consecutive ring frames, so scaled, exactly (x 0.5 rounds as the engine rounds), 0 wrong, the bad command ignored |
| J3's engine, bit for bit | `python sim/run_dsp.py`: `tb_dsp.v` drives amp_out alone at 48 and 44.1 kHz - three sources (24-bit stereo, 16-bit mono, 16-bit stereo; stream 0 later moved to other bytes), four coefficient sets written word by word at 15 us spacing (straight through; bass shelf +10 dB, treble shelf -6 dB, a peak, volume, balance and navigation mixed in, gains gliding at k = 1/64; everything saturating; straight through again), refused commands in between - and compares every run with the model in `sim/dsp_asm.py` | 522 runs per rate: every run starts on exactly the bytes and settings of the last frame; both outputs of every run equal the model, bit for bit, including 193 / 180 saturations inside the chain and 210 / 196 at the output; J3 carries them frame after frame; 188 of 188 valid words accepted, the 3 refused ones not; no word written into the bank in use, no bank change during a run; the program never missed its frame. Mutation checks: letting the bank switch during a run, or not moving the host to the other bank after a commit, fails BANK and MODEL (2 and 122 runs differ). Model only: a sine through the shelves comes out within 0.0001 dB of the design at 7 frequencies; fraction saving: -159 dBFS against double precision with a +12 dB shelf at 40 Hz, -77 dBFS without |
| Frame-rate output for an external clock multiplier (fs_fine) at 1.26 ns | `tb_core.v` rebuilds the edges from the 8-bit words; `check_core.py` finds every frame's UI 0 and UI 512 edge in the stimulus itself (pulse-width corrected, 1024 UI apart) | 48 kHz: 235 rising and 235 falling edges, 44.1 kHz: 236 / 236, each exactly 192 samples after its ring edge, spread 0. Drawn on the 99 MHz clock (the old fs_sq) the same edges spread 4 and 7 samples (5-9 ns); that grid lets up to ~10 ns of wander through any PLL (report [docs/research/regen_clock/report.md](../docs/research/regen_clock/report.md)) |
| Audio into the ring | `tb_core.v`: DSP model on DIN (L = 5A n, R = C3 n+1234h, n + 1 per frame); inject into bytes 1..6 - the bytes J3's two configurations pick from; mid-run a command naming byte 61 (must be refused); later injection off. `check_core.py` decodes the regenerated line back into frames | 48 kHz: 134 frames unchanged, 34 injected; 44.1 kHz: 131 / 31. Unchanged frames equal the ring's bit for bit; injected ones differ only in bytes 1..6 (consecutive samples) and bit 511, with the XOR of bits 4..511 kept; back to pass-through after "off". TDM and J3 carry the injected bytes in exactly those 34 / 31 frames (their truth is built from the regenerated line: the frame as it left us); before, they carried the received bytes. Mutation check (`run_core.py` corner `mut_nofix`): with the parity fix turned off (M = 83h) 14 of 34 injected frames fail and nothing else does, so the test does see parity |
| IDES8 bit order (Q0 = earliest) | Gowin's own `prim_sim.v` model, asymmetric pattern | confirmed |
| Synthesis, place and route, timing | `gw_sh board/build.tcl` (Gowin EDA 1.9.12) | 21 % logic, 21 % registers, 8 of 24 DSP, 4 of 46 BSRAM; clk_s 120.4 MHz (needs 99), clk_1024 80.2 MHz (needs 50: 49.152 MHz steered up to ~0.2 % above); setup and hold TNS 0. The clock loop's arithmetic is pipelined, one adder or multiplier per clock (unpipelined it reached 46.6 MHz). rx_framer registers its inputs once more: its decode, started from rx_classify's output register, had drifted to 108 MHz (below the 10 % rule) as the placement moved. J3's engine moved the placement again, and two old paths fell below the rule: the loop's state decode (the enables of u and integ, 80 flip-flops, from a 3-bit state: 99.8 MHz) and the reset, one net from the power-on counter across the chip (104.5 MHz). The loop's state machine is now one-hot, with S_CEN's two tests registered (exact: their inputs have settled during S_PIPE's 8 clocks), and the reset is registered in the top. The slowest paths are now ordinary loop and tx_pre logic |

Simulate: put `~/toolchains/oss-cad-suite/bin` and `lib` on PATH, then
`cd sim` and `python run_rx.py` (receiver), `python run_dpll.py` (clock loop,
about 10 minutes), `python run_core.py` (whole core, a few minutes),
`python run_dsp.py` (J3's engine against its model, about a minute),
`python sweep_core.py` (the whole core over 32 random rings, about an hour).
Build: `cd board && python build.py` - it runs `gw_sh build.tcl`, then `check_timing.py`, and fails if any clock misses
timing (TNS not 0) or keeps less than 10 % above its constraint. The
bitstream is `board/impl/pnr/listener.fs`. Place and route is deterministic:
the same sources give the same result; any change moves the margins, which
is why the check runs on every build.

## Not proved - read before trusting it on a car

1. **The preamble starts with a 3-UI run and is 8 UI long.** The MOST specs
   on disk do not draw the pattern. Two Oasis SiliconSystems patents by
   D. Knapp, who designed MOST25, do support it: US 2005/0053179 A1 counts
   "512 bits ... between coding violations which represent the beginning of
   each preamble", and US 2004/0057542 A1 Fig. 10 draws parity, a 3-cell
   run, a 1-cell run, and data again about 8 cells later. A patent shows an
   example, not the specification, so the rest of the pattern (and which
   variant marks a block start) is learned from the line, and nothing else
   is assumed about it: the design is tested with a placeholder (one 3-UI
   run) and with S/PDIF-like preambles (two). If a real ring differs, the
   framer reports errors; it does not produce wrong bytes.
2. **The switch from bypass to regenerated is a phase step on the ring** -
   and the MOST specification treats that as a normal event. Section 3.2.5.2
   of MOST Specification 2V5 lists "a node opens or closes its bypass" as a
   cause of unlock; only unlocks longer than tUnlock (60..100 ms), alone or
   added up without tLock (75..115 ms) of stable lock in between, cause an
   Error Shutdown (section 3.8). A node relocks after 3 valid preambles
   (Oasis patent EP 1333580 B1), i.e. within a few frames, so one switch
   costs tens of microseconds, and the downstream amplifier may mute that
   briefly ("an amplifier mutes the outputs" on unlock, 3.2.5.2). Every
   ordinary MOST node does the same when it leaves bypass at start-up, and so
   do Trioma, usb2most and PiMost. To stay far from tUnlock, `listener_core`
   never flaps: after LOCK is lost once, it needs HOLD_RE frames (> 200 ms,
   beyond the largest tLock) of good state before switching back, and a
   single coding error is no reason to switch at all - the framer keeps its
   lock through one bad frame and the regenerator sends the faulty run on as
   it came (corner `bit_err`). Directed test: a 20 us dropout drops LOCK
   within 2 us and brings it back 25 frames after the line returns (HOLD_RE
   = 24 in that test). Still to see on a car: whether its amplifier's brief
   mute at start-up is audible.
3. **Parity sense** (even or odd, over which bits) is unknown. It is reported
   raw per block in the UART status byte, not checked.
4. **Injection and the car.** Nothing on disk says whether any head unit
   or amplifier checks the audio content (MOST25 has no audio checksum; only
   DTCP-protected sources are encrypted, and those must not be touched). The
   parity rule is unknown - the XOR fix covers every XOR rule over the changed
   bits, and M[7] turns it off if a car shows parity errors with it.
5. **The bypass watchdog is a part on the board.** LOCK is a clk_s register:
   if the PLL or its crystal fails while LOCK is on, LOCK stays on and the
   ring would hang on a TX that has stopped. U11 (listener_hw block 2, a
   74LVC1G123 retriggered by TX_REGEN's rising edges, cleared by LOCK)
   drives U2's select instead of LOCK: any TX that stops toggling - either
   clock dead, U9 stuck or unclocked, the FPGA hung - means bypass. In
   simulation (corner `clk_stop`, U11 modelled at 10 us) TX stops 1.3 us
   after clk_s and TX_SEL falls 11.4 us after; the model never dropped TX_SEL
   while LOCK was on in any other corner. The real one-shot's time (10k x 1n)
   is not critical: anything from ~1 us (the longest gap between TX's rising
   edges is ~0.15 us) to far below MOST's 60 ms of tolerated unlock works.
6. **Nothing here has run on hardware.** The Si514 is a behavioural model
   written from its data sheet (Rev 1.2): register map, small and large
   changes, FCAL, the address it answers to, the start-up frequency. The IDES8 inputs have only been
   checked in Gowin's simulation model. The ring's real wander has not been through the loop: the gains
   assume wander the 2 Hz tracking loop can follow within the FIFO's +/-600
   samples (+/-760 ns); a ring that wanders more would show as FIFO restarts.
