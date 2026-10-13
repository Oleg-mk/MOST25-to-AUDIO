# MOST25 to AUDIO

A passive listener for the MOST25 optical ring in a car. It sits in the
fibre as an invisible repeater - physically present, never a node: no
address, never a word on the control channel - and turns what the ring
carries into audio and data the owner can use:

- **J3: what the factory amplifier would play**, as stereo I2S and, the
  same stream, as S/PDIF on TOSLINK and coax: the main source with the head
  unit's volume, mute, balance, bass, treble and loudness applied, and up to
  three more of the amplifier's sinks - navigation and phone, the parking
  sensors, the chimes, where the car sends them as audio - mixed in at their
  own levels, so speakers moved to an
  amplifier or DSP of the owner's choice keep the car's controls and its
  voices;
- **J2: everything, raw**: every frame byte on two TDM8 lines, the control
  channel's blocks on UART, MCLK from the ring - for an analyser or a DSP.
  J2 and J3 show the frame as it leaves the listener: when the phone plays
  into the car's AUX channels, they carry the phone, as the factory
  amplifier after the listener does;
- **phone audio into the car**: a phone's Bluetooth stream while it plays,
  otherwise whatever plays into the board's TOSLINK input, replaces the bytes
  of the car's own AUX source while the amplifier plays them, so it is heard
  through the factory system with the factory controls.

**Status, 2026-10-12: designed and verified in simulation, host tests and
builds, but never built and never tried in a car.** Every file needed to
order, flash and assemble one is in this repository.

**This is a research project.** Every finding, recording, correction or bit
of help is welcome: open an issue or a pull request, or write in the forum
thread.

Its offspring, [JLR-MOST-Reader](https://github.com/Oleg-mk/JLR-MOST-Reader),
is the same receiver, DSP engine, S/PDIF coder and optical front end cut down
to one job on Jaguar and Land Rover: the amplifier's stereo out on TOSLINK.

![Board v2.0 in its 80 x 30 mm aluminium tube, cut open: M1 on top, the RCA jacks at the output end, the printed caps with their saddles](listener_hw2/views/listener_v2_in_tube.png)

Ukrainian: [README.uk.md](README.uk.md).

## Which cars

- **What the car must have:** a MOST25 ring that carries the entertainment
  audio to a separate amplifier as plain PCM. Cars without that external
  amplifier keep the audio inside the head unit, and the ring carries little
  or none of it; a copy-protected stream (DTCP) gives nothing to play either.
  Having MOST25 does not make a car one of them - only a recording of that
  car says.
- **Both ring rates:** 48 kHz (Jaguar and Land Rover) and 44.1 kHz (Audi MMI
  2G/3G/3G+, BMW E65/F01). The receiver learns the bit time from the line, and
  the regenerator's clock is centred on the measured rate.
- **The controls:** every source agrees that the PCM on the ring is the same at
  any volume, and that the amplifier applies the volume, balance, tone and
  mixer levels. So the listener reads the control channel and applies them
  itself. Known: Jaguar and Land Rover (the gateway's 0xF0.0x409 levels and the
  amplifier's 0x22.0x46D SpeakerLevel) and BMW (AudioMaster 0x20.0x200);
  Mercedes, VAG and Volvo are not public. Every scale is a placeholder until
  that car's ring is recorded, and the listener's own console trace is the
  tool for it (`listener_fw/README.md`, Recording). Until it has heard one of
  the volume messages it knows, J3 stays silent (the chimes excepted).
- **The phone into the car** needs the car's AUX to be a MOST source: where AUX
  is mixed inside the head unit there are no AUX bytes to replace. It also needs
  the listener on the fibre into the amplifier: the phone goes into the frames
  as they leave the listener, so only the nodes after it hear it. For listening,
  any place in the ring will do.

[docs/vehicle_survey.md](docs/vehicle_survey.md) lists each car with its
sources and how sure each fact is.

## Is it safe for the car's ring?

- **The ring's path:** the fibre receiver, a buffer, a multiplexer (U2) and the
  fibre transmitter. U2 passes either the fibre's own signal or the FPGA's
  regenerated one. That path runs on the always-on 3.3 V (3V3_AON, U5), fed
  from KL30 and drawing tens of microamps with the car parked.
- **The bypass:** U2 falls back to the fibre's own signal whenever the FPGA is
  off or not configured, has not locked to the ring, or its transmit edges
  stop; a watchdog (U11) does that last even if the FPGA's clocks die. So a
  failure of the FPGA, its clocks or the regeneration leaves the ring passing
  straight through.
- **The switch:** when the listener locks and moves the ring from the plain
  path to its regenerated one, the ring sees a short phase step, as it does when
  any MOST node leaves its bypass at start-up. The next node relocks within a few
  frames, and the amplifier may mute for that moment.
- **When the ring opens:** the bypass is an electrical path, not an optical
  one. If its supply is lost (a blown fuse, KL30 disconnected) or a fibre part
  fails, the ring opens, as with every factory MOST node. Fit your own fuse
  where you tap KL30.
- **Nothing new on the network:** no address, never a word on the control
  channel. Until injection is allowed, the frames leave as they came.
- **Injection is off until you allow it** ('i' on the host's console, kept in
  flash; a new module has it off). Then it replaces only the bytes of the car's
  own AUX source while the amplifier plays them, and the FPGA drops it 2 s after
  the host's last command, so a host that hangs takes the phone out.
- **Fully reversible:** unplug the loop-in cable and the car is back to stock.

## Status: what is proved and what is not

**Verified in models** (run `python check_all.py`; every step passes, and
`--sweep` adds 32 random rings):

- The gateware, in Icarus Verilog against Python models:
  - the receiver, and the J3 engine at 48 and 44.1 kHz, word for word against
    its model;
  - the S/PDIF output, decoded back;
  - the whole core from the optical line, in 14 corners: both rates, preamble
    variants, injection, gaps in the control blocks, a dead transmit feedback, a
    stopped clock, bit errors, the Si514's start and its loss, the capture,
    fades, the injection's lease, and a deliberate fault the checks must catch;
  - the regenerator's clock loop, and 32 random rings.
- The host's firmware: its tests on the PC and the ESP-IDF build with no
  warnings. JLR-MOST-Reader's checks compile its decoder and gain tables and
  compare them with their own.
- The Gowin build meets timing with at least 10 % margin; the bitstream and
  the firmware in `kit/2_flash` were built from the committed sources.
- The boards: ERC and DRC clean, with parity between sheet and board, for v1.6
  and v2.0; v2.0's sheet held to v1.6's part for part and net for net; the
  board's fit in the tube and its caps from one model; the fab packages and
  the kit reproduced from the commit.
- The laptop's recorder and decoder, against the host's own formats.

**Unknown until a bench or a car:**

- **The line:** the preamble's full pattern, which variant marks a block start,
  the parity rule. The simulations assume them; the capture (command 04)
  settles them on the first ring.
- **The per-car scales:** volume, tone and the mixer levels stay placeholders
  until a recording of the car's controls.
- **The car's own messages:** whether a stock head unit sends 0x22.0x111
  Connect at all (J3 and the phone into the car take their channels from it);
  which of 0xF0.0x409 and SpeakerLevel a Jaguar XF's amplifier gets, and
  0x409's byte positions (two layouts in one author's code, the later one
  used); whether JLR mutes with 0x113 or with 0x466 MuteParameters; whether
  the parking sensors and the chimes travel the ring as audio, as mObridge's
  guide says for JLR. The capture and the recording settle these too.
- **Real hardware:** no board has been powered, the regeneration has never run
  in a real ring, and no real S/PDIF receiver has taken the output.

Bring-up goes in three steps, each with a recording (Bring-up, in this order,
below).

## Build one

The full guide is [BUILD.md](BUILD.md); `kit/` holds the same in Ukrainian with
every file to order, flash and fit. There are two boards with the same
circuit. **v2.0** (`listener_hw2/`) is the one to build: 98 x 60 mm, four
layers, inside an 80 x 30 x 2 mm aluminium tube with two 3D-printed end caps.
v1.6 (`listener_hw/`) is the first, flat board, 123.55 x 78.9 mm on two layers.

![The closed tube from the input end: J1's housing, J5 and J4 in one opening, M2's micro-USB below, the antenna's SMA jack](listener_hw2/views/listener_v2_input_end.png)

![The closed tube from the output end: the RCA jacks and J6, the saddles with their ears under the tube](listener_hw2/views/listener_v2_output_end.png)

1. **Order the boards** from JLCPCB, with the SMD parts assembled on both
   sides. Everything is in `listener_hw2/fab/`, copied into `kit/1_boards/`.
   One board gives three assemblies:

   | Assembly | What works | Parts JLCPCB places |
   |---|---|---|
   | min | the core and the S/PDIF outputs: J6 (TOSLINK) and J7 (coax) | 103 |
   | mid | min and the line out, J8 and J9 | 143 |
   | max | mid and the TOSLINK input, J5 | 163 |

   U7, the Si514, is not in JLCPCB's stock: send your own, or have JLCPCB pre-order it.
   Any 3.3 V CMOS variant in the 3.2 x 5 or 2.5 x 3.2 package fits, for example
   514CBB000112BAG, which DigiKey sells singly and JLCPCB can pre-order (C1670489).
2. **Buy the hand-soldered parts:** J1 (TE 1-1394640-1, the MOST FOT header:
   marketplaces only, look early), J4 (Molex 43650-0200), J5 and J6 (Cliff
   FCR684208R and FCR684208T), J7..J9 (BKL Electronic 0101153), J2 and J3 (pin
   headers), M1 (Sipeed Tang Nano 20K), M2 (Espressif ESP32-DevKitC-VIE) and the
   modules' pin headers.
3. **The enclosure:** the tube, cut to the soldered board's length; the two
   caps, printed from `listener_hw2/caps/` in PETG or ASA; a 150 mm U.FL-to-SMA
   pigtail and a 2.4 GHz antenna; screws.
4. **Flash both modules before soldering them** (`kit/2_flash/`): once M1 is in,
   the RCA jacks cover its USB-C.
5. **Assemble, power up on the bench, then fit the tube**, as BUILD.md says.
6. **In the car**, one step at a time, each with a recording (`kit/3_laptop/`):
   the bypass and listening first, then the regeneration, then the injection.

Also needed: a 12 V feed from KL30 with a fuse of your own, and a loop-in cable
that opens the ring at one node and brings it to J1 (Kufatec, Dension and
Trioma make them).

![The underside of board v2.0: M2 with its WROVER-IE, and the SMD parts the board house places on this side](listener_hw2/views/listener_v2_underside.png)

## Repository map

| Folder | What | Built with |
|---|---|---|
| [listener_hw2](listener_hw2) | **board v2.0, the one to order**: v1.6's circuit on 98 x 60 mm and four layers, for an aluminium tube 80 x 30 x 2 mm; the sheet written by `gen_listener2.py` from v1.6's generator and held to v1.6 by `tools/check_v2_circuit.py`; the manufacturing package for three assemblies in `fab/`, written by `make_fab2.py`; the board in the tube modelled by `check_fit.py`, the two printed end caps in `caps/`, written by `gen_caps.py`; the pictures in `views/`, rendered by `make_views.py` - see The board, v2.0 | Python, KiCad 10 |
| [listener_hw](listener_hw) | board v1.6, the first one, and the circuit's source: one KiCad 10 sheet, generated by `gen_listener.py` (symbols and the footprints drawn from the makers' drawings included: Si514, the TOSLINK housings, the RCA jack, both modules; the bodies of the FOT, the TOSLINK housings and the RCA jack for the 3D view too); the manufacturing package in `fab/`, written by `make_fab.py`: Gerbers and drill files, BOM, pick-and-place, and JLCPCB's BOM and CPL for an order with the SMD parts assembled; TOSLINK in through DIR9001 and SRC4192, S/PDIF out on TOSLINK and coax; J3's stereo as an analog line out on two RCA through a PCM5102A and an OPA1678 buffer with a 60 kHz low-pass; test points for the bench. The PCB, 123.55 x 78.9 mm on two layers, first laid out by `gen_listener_pcb.py` from the same sheet (every part's place and why is in that file), placed by hand in KiCad and routed over a ground plane - see Board v1.6 | Python, KiCad 10 |
| [listener_gw](listener_gw) | FPGA (Sipeed Tang Nano 20K): receiver, regenerator on a ring-locked clock (an Si514 the FPGA steers), TDM/UART outputs, J3's DSP engine and its S/PDIF twin, audio injection from the host or the S/PDIF input | Gowin EDA 1.9.12; simulation: Icarus Verilog (OSS CAD Suite) |
| [listener_fw](listener_fw) | ESP32 host (M2, ESP32-DevKitC-VIE): Bluetooth A2DP in (AAC, SBC), the phone's rate onto the ring's, MOST telegram decoding, the amplifier model, J3's coefficients, the steering wheel's track keys to the phone (AVRCP) | ESP-IDF v6.1; host tests: gcc |
| [virtual_most_source](virtual_most_source) | MOST25 frames and Biphase Mark line coding - the simulations' stimulus | Python + numpy |
| [tools](tools) | `console_log.py`: a recording of the host's console on a laptop on M2's USB port, kept whole, with marks and alarms (the port lost, the ESP32 started anew, a loss counter rising, silence); `trace_decode.py`: that recording at home - every telegram, the sound values a car's scales are fixed from, the telegrams beside each mark, the starts, losses and silences, and each dump through `capture_analyse.py`: what a recording of a real line says (UI and rate, preamble patterns, block marker, parity rule, frame control); each with its test (the console's formats against host.c's own, a made-up recording, known frames) | Python; pyserial for the recorder |
| [kit](kit) | what the project hands over, without the rest of the repository: `1_boards` v2.0's order (JLCPCB's files for the three assemblies, the BOM, the schematic and assembly PDFs, the parts by hand, the tube's printed caps, the first power-up, the assembly into the tube), `2_flash` the FPGA's bitstream and the host's firmware with how to write each from Windows or macOS, `3_laptop` the recorder and the decoder with their launchers; written by `tools/make_kit.py`, the builds only from committed sources, checked by `check_all.py` | Ukrainian READMEs; the same in English is [BUILD.md](BUILD.md) |
| [BUILD.md](BUILD.md) | the build guide in English: the order, the parts, flashing, the assembly, the tube, the first power-up, the laptop's recorder | - |
| [SOURCES.md](SOURCES.md) | where the knowledge of MOST25, of the cars' messages and of the parts comes from | - |
| [docs](docs) | the MOST control formats the host decodes, which cars carry audio and how they send volume, the research behind the regenerator's clock | - |

Each part's README says how it works, what is verified and how.

## Build and test

```text
python check_all.py            everything, one step at a time (~40 min)
python check_all.py --quick    without the clock loop's long runs
python check_all.py --sweep    plus the whole core over 32 random rings (~1 h more)
```

It runs the steps strictly one after another and stops at nothing: each
prints PASS or FAIL, and the summary lists them. The simulation scripts
themselves run one simulation at a time too. Tools it expects (override with
environment variables, see the script's header):
OSS CAD Suite in `~/toolchains/oss-cad-suite`, Gowin EDA in
`C:\Gowin\Gowin_V1.9.12.03_x64`, ESP-IDF v6.1 in `~/toolchains/esp-idf`
(tools in `~/toolchains/espressif`), MinGW gcc in `~/toolchains/mingw64`,
KiCad 10.

## The board, v2.0

v2.0 (`listener_hw2/`; `most_listener_v2.kicad_pro` opens it in KiCad 10) is the board to order:
v1.6's circuit on a board of 98 x 60 mm with four layers, made to slide into an aluminium tube
80 x 30 x 2 mm closed by two printed caps. The inputs sit at one end - J1 (the ring's FOT), J5
(TOSLINK in), J4 (power) - and the outputs at the other - J6 (TOSLINK out), J7 (coax S/PDIF), J8
and J9 (the line out). M1 (the FPGA) stands on top; M2 (the host) hangs underneath, component side
down, its micro-USB at the input end. In1 and In2 are solid ground under both signal layers.

- **The sheet** is not drawn twice. `gen_listener2.py` loads v1.6's `gen_listener.py` and writes its
  blocks with v2.0's title and UUIDs, J5 and J6 as Cliff ORJ-8/OTJ-8 (10 mm high, no screw ear), the
  modules' footprints with holes only for the pins in use and the corner pins, and the parts
  v2.0 adds: R47 10R + C84 10u and R48 10R + C85 10u filter the line out's rails,
  R49..R51 (33R) sit in I2S's BCLK, LRCK and DOUT, R52 (33R) in RX_IN at U3, R53 (33R) at U1's
  output. `tools/check_v2_circuit.py` holds the sheet to v1.6's part for part and net for net, these
  parts taken out, so the gateware, the firmware and `kit/2_flash` hold for both boards.
- **The PCB** was placed once by `gen_listener2_pcb.py` and routed, then edited round by round in
  the PCB editor; the ring's FOT block is the reader v2.0's (JLR-MOST-Reader). It passes DRC with no
  error, nothing unconnected and no difference from the sheet.
- **Three assemblies, one board and one case.** Every connector is fitted in each; they differ in
  the parts behind the connectors: min (the core and the S/PDIF outputs), mid (+ the line out), max
  (+ the TOSLINK input). `make_fab2.py` writes `fab/` from the board and the sheet: the Gerbers and
  drill files, the BOM, the pick-and-place of both sides, JLCPCB's BOM and CPL for each assembly,
  the schematic and the assembly drawings of both sides, and a README with the order's steps.
- **The tube.** `check_fit.py` models the board in the tube from the PCB and every part's height,
  each with its source: the board centred across, 8 mm a side, at the height that leaves the same
  room over the tallest parts on top (the RCA jacks) and under M2; each part's face against its cap;
  the leads under the board; the caps' openings and the webs between them. `gen_caps.py` writes the
  caps into `caps/` (STEP, STL, a drawing, a README), and writes nothing when a wall comes out
  thinner than a printer makes or a block meets a part or a lead. Each cap is a flange on the tube's
  end, blocks in the side margins that hold the board's edges in slots, 0.7 mm off the tube's walls
  so any tube in tolerance takes them, and a saddle under the tube with an ear either side to screw
  it down. The input cap passes J1, J5 with J4, M2's micro-USB and the Bluetooth antenna's SMA jack;
  the output cap J6 and the RCA jacks.
- **What the tube asks.** M1's USB-C ends up behind the RCA housings, so the FPGA is flashed before
  M1 is soldered in and cannot be flashed in the assembled board; the host's micro-USB stays
  reachable through the input cap, for its firmware and for the laptop's recording. J2 and J3 are
  for the bench: a crimp housing on them would stand 16.4 mm high, and the tube leaves 14.75.
- **The pictures** here are rendered by `make_views.py` from the same models. KiCad has no body for
  the modules and four of the parts, and plain boxes stand in for them.

`check_all.py` regenerates v2.0's sheet and holds it to v1.6's, runs ERC and DRC, runs
`check_fit.py` and `gen_caps.py`, and fails while `fab/` or `caps/` differ from what their scripts
write. `kit/1_boards` hands v2.0 over: the order of each assembly, the parts by hand, the tube and
its caps, the assembly into the tube.

## Board v1.6

Board v1.6 is the first board, on two layers; its sheet is v2.0's circuit too.
`listener_hw/most_listener.kicad_pro` opens the project in KiCad 10. The sheet
is generated (`gen_listener.py`); the PCB was laid out once by
`gen_listener_pcb.py`, then placed by hand in the PCB editor and routed. From there on
`most_listener.kicad_pcb` is the master: parts may be moved freely, and the
generator refuses to overwrite the file unless run with `--fresh`, which lays
the parts out again from its table and discards every track.

What the board already carries: the outline (123.55 x 78.9 mm, two layers), four
M3 holes about 4 mm from their edges, ground pours on both sides (B fills them), the copper keep-out
under M2's antenna, the net classes - Default 0.25 mm tracks with 0.15 mm
clearance, Rail 0.35 mm for the 3.3 V rails, Power 0.6 mm for the battery path
and the 5 V rails, vias 0.6/0.3 and 0.8/0.4 mm - and `most_listener.kicad_dru`,
which lets one resolved thermal spoke connect a pad to a pour. The reasons
behind every part's place are in the generator's table.

The routing (board v1.6): the bottom is one ground plane, crossed only by
short jumpers (4 of them, 9 mm in all, the longest 3.65 mm); signals and
supplies run on top, the supplies as wide tracks that change layer nowhere but
at one 3V3_AON jumper, and the top's ground pour is stitched to the plane by
vias about every 6 mm. Every SMD ground pad has a via of its own beside it. The
5 V trunk runs 1 mm wide from C7 up the left edge under J1 and along the top
edge; the host's switch U10 sits at M2's 5 V pin with 10 uF at its input (the
radio's pulses come out of it, not over the trunk); 100 uF + 100 nF (C63, C64)
sit by D3 at the module's end of the trunk, 100 uF + 100 nF (C81, C80) at its
other end by U10 and U14, four more 100 nF (C65-C68) along it.
M1 and M2 are soldered to the board on pin headers, no sockets - two 1x20 and
two 1x19 on 2.54 mm, which the 3D view shows under them, as it shows J2's and
J3's. The headers' plastic leaves 2.5 mm under each module: room for the 0603
resistors under M1 (R11, R12) and under M2 (R18..R21, R34..R41);
M2's courtyard is its two pin rows and the antenna's end.
KiCad has no model for the MOST FOT, the TOSLINK housings or the RCA jacks, so
`gen_listener.py` draws their bodies from the same drawings, as STEP files in
`most_listener.3dshapes`.
`make_fab.py` writes the manufacturing package into `listener_hw/fab`: the
Gerbers and drill files (zipped for the board house), the BOM, the pick-and-place
file, the same two in JLCPCB's format, and a README with the board's numbers and
the notes the BOM's values do not carry. JLCPCB's rotations were read off each
chosen part's LCSC footprint.
`check_all.py` fails while the package does not match the board.

Every footprint is linked to its symbol, so after a change of the sheet: run
`gen_listener.py`, then in the PCB editor Tools > Update PCB from Schematic. `python check_all.py` runs KiCad's DRC on
the board as it is, checked against the sheet; the board passes with no error
and nothing unconnected. Warnings are silk only: references the hand placement
left overlapping a pad or another reference.

## Limits, by design

- **Only the light tells the host what plays.** The listener never sends a
  word, so the host learns which frame bytes carry the AUX source, and whether
  the amplifier plays them, only from the telegrams it happens to hear. At a
  cold start the ring, the FPGA and the ESP32 wake together (WAKE); if the
  head unit connects the amplifier to AUX before the host is listening, the
  phone is not injected until the head unit next changes a source. The FPGA
  reads its bitstream from the module's flash in about 290 ms, so that window
  is kept short. Asking (a SourceInfo.Get on the control channel) would end
  the listener's silence, so this stays as it is.
- **Cars whose AUX is not a MOST source** - mixed inside the head unit - have
  no AUX bytes to replace; the phone cannot be injected there. Listening
  (J2, J3) needs the audio on the fibre as plain PCM: cars without the
  external amplifier, or with a copy-protected stream (DTCP), give it nothing
  to play (docs/vehicle_survey.md). Having MOST25 does not make a car one of
  them - only a recording of that car says.
- **The per-car scales** - volume, tone, the Jaguar XF's navigation and
  parking-sensor levels (0xF0.0x409 bytes 9 and 11) - are placeholders until
  a real ring is recorded.
- **Sink 4 is the chimes in every car**, as Jaguar Land Rover numbers the
  amplifier's sinks: with no SpeakerLevel of its own it plays at -6 dB,
  never at the volume, so a chime is heard with the volume down. A car
  that puts something else on sink 4 gets that at -6 dB too.
- **What an amplifier does on its own** is not on the bus: if it turns the
  music down while a prompt plays, J3 does not; it follows what the head unit
  sends (levels, mutes).
- **The control channel's CRC is not checked**: its polynomial is in no
  document we have. What is checked instead: the FPGA drops a block in which
  the line broke its code, and the host drops a block whose frames disagree
  in parity (the count a clean block has is learnt on the ring). A bit can
  still flip unseen in a way neither shows; the CRC follows once a recording
  gives the polynomial.
- **Injection is guarded.** It is off until allowed on the host's console
  ('i', kept in flash), so nothing of ours enters a car's ring before a
  recording of that car has shown the telegrams read right. The FPGA keeps an
  "on" for 2 s after the host's last command (repeated every 0.5 s), so a host
  that hangs takes our audio out. After any gap in the control blocks,
  injection waits until AUX's channels are told again (the car's next
  Allocate.Result or SourceInfo for AUX), since the gap may have hidden the
  DeAllocate that gave those bytes to another source.

## Bring-up, in this order

1. **Bypass only.** U2 left on the fibre's own signal (LOCK held low), the
   FPGA listening: J2's TDM and UART, and the capture (command 04: the FPGA
   keeps the line's first 65536 runs after power-up, the host's `d` key dumps
   them, `c` captures anew; `tools/capture_analyse.py` reads them) from a real
   ring, recorded with `tools/console_log.py` and read with
   `tools/trace_decode.py`. This settles what the simulations could only
   assume - the preamble pattern, the block-start marker, the parity rule - and
   shows the control telegrams the host decodes.
2. **Regeneration**, on the bench with a loop of fibre, then in the car.
3. **Injection**, allowed with 'i' on the console only now, from the phone and
   from the TOSLINK input, then J3's sound and the per-car scales.

On v1.6's bench (on v2.0 the RCA housings cover M1's USB-C once it is soldered
in), keep J4 powered while the FPGA module is on its own USB, or plug that USB
in only to flash. With J4 dead from the start, the module still feeds
the unpowered ESP32 through its UART line, and the Si514 through R11/R12. The
FPGA cannot tell that state from a Si514 that does not start, and the UART must
stay up to debug that.

In the car it is covered: once the Si514 has run and then gone with 5V_SW (the
ring asleep, a laptop on the FPGA module), the FPGA holds every such line low
and centres the Si514 anew when it returns (listener_gw/README.md, Ring clock).
The other way round is harmless: the ESP32 on its USB drives the unpowered FPGA
module through R20/R21, and the GW2AR's inputs are hot-socket rated at 150 uA at
most (DS226, Table 3-4).

The battery input is built for ISO 16750-2 test B (a suppressed load dump,
35 V for up to 400 ms) and ISO 7637-2 pulses 1, 2a, 3a and 3b: the buck is an
LMR38020 (80 V in, 85 V absolute maximum), the TVS an SMBJ36A in front of the
reverse-polarity diode (silent at 35 V, clamping the fast pulses around
50 V, shunting negative ones through its forward diode), the fuse a slow-blow
2 A, with 100 nF 100 V (C83) right behind it at the TVS. The unsuppressed
load dump (test A, 80..100 V) is not covered: it would take a 6.6 kW TVS,
and cars of the MOST era have avalanche alternators.

## Licence

Copyright 2026 Oleg-mk.

- **Hardware, under CERN-OHL-S-2.0** ([LICENSE](LICENSE)):
  - `listener_hw/` and `listener_hw2/`: the KiCad designs and the scripts that generate them,
    the footprints and 3D models, the fabrication files, the tube's end caps, the pictures;
  - the gateware in `listener_gw/rtl/` and `listener_gw/board/`;
  - `kit/1_boards/` and `kit/2_flash/fpga/`.
- **Software, under GPL-3.0-or-later** ([COPYING](COPYING)): `listener_fw/` (the host's
  firmware), `virtual_most_source/`, `tools/`, `listener_gw/sim/`, `kit/2_flash/esp32/`,
  `kit/3_laptop/` and `check_all.py`.
- **Documentation:** each README and drawing is under the licence of the directory it sits in;
  `docs/` is under GPL-3.0-or-later.

The host's firmware is built with Espressif's ESP-IDF, some of whose libraries come only as
binaries (the Bluetooth controller among them), and with Espressif's `esp_audio_codec` component
(the AAC and SBC decoders), which is under the Espressif Modified MIT License. As an additional
permission under section 7 of the GPL, you may link the firmware with those Espressif libraries
and convey the combined binary, provided that the firmware's own code is conveyed under the GPL.

If you build or change the hardware and share it, share your sources under the same licence.

## How it was made

The author made the decisions and placed the parts. Claude (Anthropic's AI
model, in Claude Code) wrote the gateware, the host's firmware, the models and
simulations, the board generators and copper, and the checks, as a co-author.
The commit history shows both.
