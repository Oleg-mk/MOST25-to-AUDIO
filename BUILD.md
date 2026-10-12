# Building the MOST25-to-AUDIO listener v2.0

The kit, `kit/`, holds everything you need to make the listener and to record a car with it,
without the rest of the repository. The listener sits in the MOST25 ring and says nothing into it.
It hears the head unit's audio and commands and puts the audio out on TDM, I2S, S/PDIF and the line
out. When allowed, it injects the phone (Bluetooth) or the TOSLINK input into the car's AUX source.
It has not been tested in a car yet.

The board is v2.0: v1.6's circuit with a few added resistors and filters, on a board of 98 x 60 mm
that fits into an aluminium tube 80x30x2 with two printed caps. One board gives three assemblies:
min, mid and max.

The same instructions in Ukrainian are the kit's READMEs: `kit/README.md`, `kit/1_boards/README.md`,
`kit/2_flash/README.md` and `kit/3_laptop/README.md`.

## The order

1. **Boards.** Order them as in [Ordering from JLCPCB](#ordering-from-jlcpcb). Buy the
   [hand-soldered parts](#hand-soldered-parts) and the tube separately, and print the caps
   ([The tube and the caps](#the-tube-and-the-caps)).
2. **Firmware.** Before the modules are soldered in, write `listener.fs` into the Tang Nano 20K and
   the host's firmware into the ESP32-DevKitC-VIE, each module through its own USB
   ([Flashing the FPGA and the ESP32](#flashing-the-fpga-and-the-esp32)). After assembly, the RCA
   jacks cover the FPGA module's USB-C.
3. **Assembly, the first power-up on the bench, the assembly into the tube:**
   [Assembly](#assembly), [The first power-up](#the-first-power-up), [Into the tube](#into-the-tube).
4. **The car, step by step** (the repository's README,
   ["Bring-up, in this order"](README.md#bring-up-in-this-order)): first only listening and
   capturing the line, then regeneration, then injection. Each step goes with a recording
   ([The laptop](#the-laptop-recording-a-drive-and-decoding-it-at-home)).

## The files

| Folder | What is inside |
|---|---|
| `kit/1_boards/` | ordering the boards from JLCPCB with SMD assembly on both sides, three assemblies; the parts for hand soldering; the tube and the caps to print; the schematic, the assembly drawings, the checks before power, the assembly into the tube |
| `kit/2_flash/` | the FPGA's firmware (`kit/2_flash/fpga/listener.fs`) for the Tang Nano 20K and the host's firmware (`kit/2_flash/esp32/*.bin`) for the ESP32-DevKitC-VIE, and how to write each from Windows or macOS |
| `kit/3_laptop/` | recording the host's console in the car and decoding it at home, for Windows 10/11 and macOS (Apple Silicon too) |

### kit/1_boards

| File | What it is |
|---|---|
| `kit/1_boards/most_listener_v2-gerbers.zip` | the board itself, for the factory: the Gerber files, the drill files, the job file |
| `kit/1_boards/most_listener_v2-bom-jlcpcb-min.csv`, `kit/1_boards/most_listener_v2-cpl-jlcpcb-min.csv` | the min assembly: the parts list for assembly at JLCPCB, with LCSC numbers, and the parts' placement, with JLCPCB's rotations |
| `kit/1_boards/most_listener_v2-bom-jlcpcb-mid.csv`, `kit/1_boards/most_listener_v2-cpl-jlcpcb-mid.csv` | the mid assembly: the same |
| `kit/1_boards/most_listener_v2-bom-jlcpcb-max.csv`, `kit/1_boards/most_listener_v2-cpl-jlcpcb-max.csv` | the max assembly: the same |
| `kit/1_boards/most_listener_v2-bom.csv` | the full parts list (the max assembly), the hand-soldered parts included |
| `kit/1_boards/most_listener_v2-schematic.pdf` | the schematic |
| `kit/1_boards/most_listener_v2-assembly-top.pdf`, `kit/1_boards/most_listener_v2-assembly-bottom.pdf` | both sides for assembly (the bottom as seen from below): every part's reference, including those not shown on the silkscreen, the polarity marks, the outline |
| `kit/1_boards/caps/in_cap.stl`, `kit/1_boards/caps/in_cap.step` | the tube's input cap (J1, J5, J4, M2's micro-USB, the antenna's SMA), for printing |
| `kit/1_boards/caps/out_cap.stl`, `kit/1_boards/caps/out_cap.step` | the output cap (J6 and the RCA jacks J7..J9), for printing |
| `kit/1_boards/caps/caps.svg` | the drawing of both caps: the view from outside, the section, the view from below, the sizes, the notes (in Ukrainian; the same in English is `listener_hw2/caps/caps_en.svg`) |

These files are copies from `listener_hw2/fab` and `listener_hw2/caps`. `listener_hw2/make_fab2.py`
writes them from the KiCad board, and `listener_hw2/gen_caps.py` from the model of the board in the
tube (`listener_hw2/check_fit.py`). Don't edit them by hand.

### kit/2_flash

| File | What it is |
|---|---|
| `kit/2_flash/fpga/listener.fs` | the FPGA's bitstream for the GW2AR-LV18QN88C8/I7 on the Sipeed Tang Nano 20K module (M1) |
| `kit/2_flash/fpga/BUILD.txt` | which commit it was built from, the UserCode, the flash read frequency (25 MHz), the build's timing |
| `kit/2_flash/esp32/bootloader.bin`, `kit/2_flash/esp32/partition-table.bin`, `kit/2_flash/esp32/listener_fw.bin` | the host's firmware for the ESP32-DevKitC-VIE (M2): the bootloader, the partition table, the program |
| `kit/2_flash/esp32/BUILD.txt` | which commit it was built from, its version (`App version`), ESP-IDF, the write addresses, the sha256 of each file |

`tools/make_kit.py --flash` takes only builds from committed sources into this folder, and only if
the FPGA build has a timing margin of at least 10 %. `check_all.py` fails if the sources have
changed since these builds.

### kit/3_laptop

| File | What it is |
|---|---|
| `kit/3_laptop/record.bat`, `kit/3_laptop/record.command` | start a recording: Windows and macOS |
| `kit/3_laptop/decode.bat`, `kit/3_laptop/decode.command` | start the decoding at home |
| `kit/3_laptop/console_log.py` | the recorder of the host's (ESP32's) console, with marks and alarms |
| `kit/3_laptop/trace_decode.py` | decodes a recording into files you can read |
| `kit/3_laptop/console_format.py`, `kit/3_laptop/capture_analyse.py` | parse the console's lines and the line's dump; both programs use them |
| `kit/3_laptop/requirements.txt` | pyserial, which `record` installs itself |

The programs are copies from the repository's `tools/`. The recordings go to `logs/` next to these
files.

### Where the files come from

`tools/make_kit.py` collects the kit from the repository. The files of the boards, the caps, the
firmware and the programs are copies, while the explanations (the `README.md` files) and the launch
files are written by hand. `check_all.py` fails if a copy has drifted from its source, if an extra
file is left in the kit, or if a firmware is older than its sources. Which commit each firmware was
built from is recorded in `kit/2_flash/fpga/BUILD.txt` and `kit/2_flash/esp32/BUILD.txt`.

The full descriptions are in the repository:
- [`README.md`](README.md): the decisions and their reasons, the bring-up order;
- [`listener_hw2/fab/README.md`](listener_hw2/fab/README.md): board v2.0 and the three assemblies;
- [`listener_hw2/caps/README.md`](listener_hw2/caps/README.md): the tube and the caps;
- [`listener_gw/README.md`](listener_gw/README.md): the FPGA;
- [`listener_fw/README.md`](listener_fw/README.md): the host and the recording.

The previous board, v1.6 (two layers, 123.55 x 78.9 mm, no tube), is in `listener_hw/` together
with its package for ordering, `listener_hw/fab`. It is no longer part of the kit.

## The board

- **Size and layers:** 98 x 60 mm, 4 layers, FR-4 1.6 mm, revision 2.0. JLCPCB will show
  98.1 x 60.1 mm, because it counts the outline together with the line's width.
- **Stack-up:** JLCPCB's JLC04161H-7628, 1 oz copper outside and 0.5 oz inside. Both inner layers
  are solid ground.
- **Rules:** tracks from 0.2 mm, clearance 0.15 mm, vias 0.6/0.3 mm, smallest hole 0.3 mm, no
  cut-outs.
- **Sides:** SMD parts, mask and silkscreen on both sides.
- **Finish:** ENIG, because U4 and U11 (VSSOP-8, 0.5 mm pitch), U5 (WSON-6) and U6 (HSOP-8) need
  flat pads.

## The three assemblies

One board and one case: the connectors are fitted in every assembly, and only the parts behind them
differ. The firmware is the same for all three.

| Assembly | What works | Parts JLCPCB places | BOM lines |
|---|---|---|---|
| **min** | the core and the S/PDIF outputs: J6 (optical) and J7 (coax) | 103 (44 on top, 59 on the bottom) | 42 |
| **mid** | min and the line out, J8 and J9 | 143 (44 on top, 99 on the bottom) | 52 |
| **max** | mid and the TOSLINK input, J5 | 163 (57 on top, 106 on the bottom) | 58 |

The core is the power, the ring with its bypass and watchdog, M1 (the FPGA), U7 (Si514), M2 (the
host, Bluetooth), J3 (I2S) and J2 (the analyser). In min, J5, J8 and J9 are fitted but not
connected: J5 has no supply, and J8 and J9 no signal. In mid, J5 is likewise not connected.

## Ordering from JLCPCB

1. **Board.** Upload `most_listener_v2-gerbers.zip`. Choose 4 layers, 1.6 mm, the stack-up
   JLC04161H-7628, 1 oz copper outside and 0.5 oz inside, ENIG, green mask, white silkscreen, and
   5 boards or more.
2. **Assembly.** Both sides, Standard PCBA (Economic assembles one side only), with "Confirm parts
   placement" on.
3. **BOM and CPL.** Upload the pair of files of the assembly you want:
   `most_listener_v2-bom-jlcpcb-<assembly>.csv` and `most_listener_v2-cpl-jlcpcb-<assembly>.csv`.
   - JLCPCB shows the stock at once. Buy any part that is missing from LCSC on the same page (F1,
     C2925010).
   - In max, U13 (SRC4192) makes up most of the difference in price: on 7 October LCSC had 8 of
     them. For more boards, supply the rest as your own parts.
4. **Your own part: U7, Si514.** Send it to JLCPCB, or add it through their global sourcing.
   - Any 3.3 V CMOS variant fits (format C, M or N), in the 3.2 x 5 (B) or 2.5 x 3.2 (C) package,
     with any start-up frequency and I2C address. The FPGA finds the address and sets the frequency
     itself.
   - Example: 514CBB000112BAG, which DigiKey sells singly and JLCPCB can pre-order (C1670489).
5. **The placement preview, before paying**, on both sides. Check:
   - pin 1 of every IC and of X1;
   - the polarity of D1, D2, D3, C44, C45, C63, C78 and C81 (those in the chosen assembly).

   The rotations are taken from the LCSC footprint of each chosen part. JLCPCB counts the bottom
   side mirrored: 180° minus the angle in KiCad plus the part's own turn. The pin-1 dot must sit on
   the board's pin-1 mark, and the "+" of every electrolytic on the "+" side of the silkscreen. U7
   has no LCSC footprint, and JLCPCB draws its own: check its pin 1 against the mark on the board.

## Hand-soldered parts

For one board:

| Ref | Part | Part number | Where to buy |
|---|---|---|---|
| J1 | MOST optical module (pigtail FOT, 2+0) | TE 1-1394640-1 | not found in Mouser's or DigiKey's catalogues, only on marketplaces: look for it early |
| J2 | pin header 1x08, 2.54 mm pitch (TDM and UART out) | — | anywhere |
| J3 | pin header 1x06, 2.54 mm pitch (I2S out) | — | anywhere |
| J4 | Micro-Fit 3.0, 2 pins, right angle | Molex 43650-0200 | any Molex distributor |
| J5 | TOSLINK receiver (input) | Cliff FCR684208R (ORJ-8) | DigiKey; LCSC doesn't have it |
| J6 | TOSLINK transmitter (S/PDIF output) | Cliff FCR684208T (OTJ-8) | DigiKey |
| J7, J8, J9 | RCA jack, right angle: J7 coax S/PDIF, J8 and J9 the line out L and R | BKL Electronic 0101153 | BKL distributors |
| M1 | FPGA module | Sipeed Tang Nano 20K | Sipeed's store |
| M2 | ESP32 module with a connector for an external antenna | Espressif ESP32-DevKitC-VIE | Espressif distributors |
| — | pin headers for the modules: two 1x20 (M1) and two 1x19 (M2), 2.54 mm pitch | — | anywhere |

The holes are made for exactly these parts; look-alikes may not fit.

J2 and J3 are for the bench: the tube leaves 14.75 mm above the board, and a 2.54 mm housing stands
16.4 mm high.

## Everything else you need

- **Power for J4.** A Molex 43645-0200 housing and two 43030 terminals (20–24 AWG wire).
  - Feed it from the battery's permanent plus (KL30) and ground.
  - Without power the bypass doesn't work, and the car's ring is broken: it is the fibre's path
    through the board that runs on the always-on 3.3 V (3V3_AON).
  - Fit a fuse of your own near the point where you connect to the car's wiring. F1 on the board
    (2 A) protects only what is behind it, not the wire.
- **A loop-in cable for the MOST ring.** A cable that opens the ring at one of the nodes and brings
  it to J1. The repository has no part number for it. Kufatec, Dension and Trioma make such cables;
  pick one for your node. For the phone into the car, that node is the amplifier: the listener has
  to sit on the fibre into it.
- **An antenna for M2**, with its pigtail, as in [The tube and the caps](#the-tube-and-the-caps).
  The VIE module has no antenna on its board; without an external one there is no Bluetooth.
- **The tube, the caps and the small parts**, as in [The tube and the caps](#the-tube-and-the-caps):
  four ST2.2x9.5 self-tapping screws, an M2 ring terminal, an M2 serrated washer, 3–5 cm of
  20–22 AWG wire; for the car, four 4.2 mm self-tapping screws or M4 screws, and M4 washers.
- **Cables, as needed:**
  - TOSLINK to J5 (input) and J6 (output);
  - 75 Ω coax to J7;
  - ordinary RCA cables to J8 and J9.
- **For the bench** you need light into J1: a live car ring or another MOST board. Otherwise the
  WAKE signal doesn't switch on 5V_SW, and the modules get no power from the board.

## The tube and the caps

- **The tube.** Rectangular aluminium, 80x30x2 (76 x 26 mm inside). Its length equals the assembled
  board, measured from the input edge to the farthest of the output edge and the RCA jacks' front
  faces (nominally 98.05 mm), +0.1/−0 mm. Its ends are square and deburred. Better without a coating:
  anodizing insulates, and the tube is bonded to ground (below).
- **The caps** are printed from `kit/1_boards/caps/`: STL for the slicer, STEP for CAD, the drawing
  in `kit/1_boards/caps/caps.svg` (in English: `listener_hw2/caps/caps_en.svg`). Material: PETG or ASA (PLA softens in a car in the sun), or
  order an MJF PA12 print. Print them with the outer face on the bed, without supports, at 100 %
  infill: the self-tapping screws go into the blocks' body. Both together take about 23 g of PETG.
- **Design.** Each cap is an 80x30 flange, 2.0 mm thick, that sits on the tube's end. The board's
  ends butt against the flanges. Blocks in the side margins (8 mm either side of the board) hold its
  edges in 2.0 mm slots. The blocks stop 0.7 mm short of the tube's walls, so any tube within
  tolerance fits, without measuring.
  - Input cap: J1's housing passes through it; J5 and J4 share one opening; below, an opening for
    M2's micro-USB (with room for the plug's moulded body); the antenna's SMA in the side margin on
    J4's side, above the board.
  - Output cap: an opening for J6 and three vertical slots, 13.2 x 13.8, for the RCA threads (BKL
    doesn't give the height of the jack's axis; the slot covers its spread).
- **Saddles and ears.** Underneath, each flange runs on into a saddle under the tube: 3 mm thick,
  9 mm along the tube, with a 10 mm ear on either side and a Ø4.6 hole in each. The tube's floor
  rests on the two saddles. In the car, four 4.2 mm self-tapping screws (DIN 7981) or M4 screws
  through the ears hold the listener, with a DIN 125 M4 washer under each head.
- **Fixing the caps:** four DIN 7981 C ST2.2x9.5 self-tapping screws through the tube's top. Ø2.4
  holes in the top wall, 3.0 mm from the end, at a distance u from the left edge as seen from
  outside that end:
  - input: u 6.20 (the left block) and u 64.90 (the ground block, over J4);
  - output: u 6.20 (the left block) and u 73.80 (the right block).

  Not through the side walls: a screw head there would be in the way of a screwdriver on the ear
  below it.
- **The tube's ground.** Under the head of the ground block's screw (input cap, over J4), put an M2
  ring terminal and a serrated washer. From the terminal, run 3–5 cm of wire to the negative wire
  of J4's harness, right at the plug (soldered, heat-shrunk). Scrape an anodized tube down to bare
  metal under the washer.
- **The antenna.** A U.FL–SMA pigtail, 150 mm, with an SMA jack for an 8 mm nut (a flanged one or
  one with a seal, 11 mm, doesn't fit into the side margin). The hole in the cap is round, Ø6.85, so
  a thread with flats fits, and so does one without. The jack's nut and serrated washer go outside.
  Take a 2.4 GHz antenna with the same kind of connector as the pigtail's jack: SMA or RP-SMA.

## Flashing the FPGA and the ESP32

The bitstream and the host's firmware are in `kit/2_flash/` ([The files](#the-files)).

### When

Best before the modules are soldered into the board. Each module is plugged into the laptop by its
own USB, without the board.

On the assembled board v2.0 only the host can be updated: M2's micro-USB comes out in the input
cap's opening. The bodies of the RCA jacks (J8, J9) cover the FPGA module's USB-C, so write the
bitstream before M1 goes onto the board.

### The FPGA: Tang Nano 20K

The bitstream is written into the module's SPI flash. The FPGA reads it from there every time 5V_SW
appears as the ring wakes, in about 290 ms. So a write to the flash survives power-off, while a
write to SRAM is no use for the listener: it is lost with the power.

#### The BL616 debugger's firmware

The USB bridge on the module has its own firmware. It must be version 2025030317 or newer: with
older ones, `openFPGALoader` doesn't write the flash.

- **How to read the version.**
  - Windows: Device Manager, USB Converter A, Details, "Parent": the last 10 digits.
  - macOS: `ioreg -p IOUSB -l -w0 | grep -E '"USB Serial Number"|"bcdDevice"'`, the last 10 digits
    of the serial number.
- **How to update it.** With BouffaloLabDevCube (Windows and macOS): choose the BL616/618 chip and
  plug in the USB while holding the UPDATE button behind the HDMI socket. Step by step:
  wiki.sipeed.com, page "update_debugger".

#### Windows 10 or 11: Gowin Programmer

1. Gowin Programmer comes with Gowin EDA (Education, from gowinsemi.com), or installs on its own
   from Sipeed's package (dl.sipeed.com, TANG, programmer). The FTDI driver installs with it.
2. Plug the module straight into a port on the PC, without a hub. Device Manager must show
   USB Converter A, USB Converter B and a COM port.
3. Run Programmer:
   - **Cable Setting:** the cable it found (USB Debugger A), a frequency of 2.5 MHz or lower, Save.
   - **Scan:** pick **GW2AR-18C** from the list, because GW2A-18C and GW2ANR-18C have the same ID.
   - Double-click in the Operation column, then:
     - Access Mode: **External Flash Mode**;
     - Operation: **exFlash Erase,Program thru GAO-Bridge**;
     - File: `listener.fs`;
     - External Flash Device: **Generic Flash**;
     - Start Address: **0x000000**.

     Save, then Program/Configure.
   - Sipeed advises against the operations with "Verify": with this bridge they can be very slow or
     break off. The check is [below](#checking-that-this-firmware-is-running).
4. The same from the command line, in the `Programmer\bin` folder:

   ```bat
   programmer_cli.exe --scan-cables
   programmer_cli.exe --cable-index 4 --frequency 2.5MHz --device GW2AR-18C --run 36 --spiaddr 0x000000 --fsFile C:\path\to\kit\2_flash\fpga\listener.fs
   ```

   Use the `--cable-index` under which `--scan-cables` showed USB Debugger A.

#### macOS (Apple Silicon too): openFPGALoader

1. Install Homebrew (brew.sh), then `brew install openfpgaloader`.
2. Plug the module into the Mac. On a Mac with Apple Silicon, answer "Allow" when it asks about the
   new accessory.
3. Check the link: `openFPGALoader -b tangnano20k --detect`. It must show idcode 0x0000081b.
4. Write the flash:

   ```bash
   openFPGALoader -b tangnano20k -f --verify listener.fs
   ```

   If it says "unable to claim usb device", run it again with `sudo`. Apple's driver holds the
   bridge, and only root can make it let go. There is no need to unload Apple's driver.
5. Unplug the USB and plug it back in.

### The host: ESP32-DevKitC-VIE

It is written with esptool, the same way from Windows and macOS (Apple Silicon too).

1. **esptool.** You need Python 3 ([Python](#python)). Then
   `python -m pip install esptool==5.4.0`. That is the version that comes with ESP-IDF 6.1, which
   the firmware was built with. On macOS, type `python3` instead of `python`.
2. **Port.** Connect the module with a USB cable (one that carries data, not a charge-only one).
   - Windows: Device Manager shows a COM port "Silicon Labs CP210x" or "USB-SERIAL CH9102".
   - macOS: `ls /dev/cu.*` shows `/dev/cu.usbserial-…`. If there is no port, you need the bridge's
     driver ([The bridge's driver](#the-bridges-driver)).
3. **Writing**, from the folder `kit/2_flash/esp32` (replace COM5 with your port; on a Mac,
   `/dev/cu.usbserial-…`):

   ```bash
   python -m esptool --chip esp32 -p COM5 -b 460800 --before default-reset --after hard-reset write-flash --flash-mode dio --flash-size 4MB --flash-freq 40m 0x1000 bootloader.bin 0x8000 partition-table.bin 0x10000 listener_fw.bin
   ```

   The addresses are the same as in `kit/2_flash/esp32/BUILD.txt`.
4. **If it says "Failed to connect".** Hold the BOOT button, press EN briefly, release BOOT and try
   again.

Writing the program doesn't erase the settings the host keeps in its flash (the injection
permission, `i`, and the sound). On a new module, injection is not allowed.

### Checking that this firmware is running

- **The host.** At start, the console at 921600 (`kit/3_laptop`: `record`, or any terminal) shows
  `App version:`. It must equal `version` in `kit/2_flash/esp32/BUILD.txt`.
- **The FPGA through JTAG.** Gowin Programmer's "Read User Code" must show the `usercode` from
  `kit/2_flash/fpga/BUILD.txt`.
- **The FPGA on the board.** With light in J1, the host's console shows a status line every 10 s.
  The `packets` numbers in it grow once the FPGA has configured and is passing the control blocks
  to the host.

### Building your own

Building it yourself is not necessary. If you want to:
- FPGA: Gowin EDA 1.9.12.03, `python listener_gw/board/build.py` (it builds and checks the timing);
- host: ESP-IDF 6.1, `listener_fw/idf.ps1 build`;
- then commit, and run `python tools/make_kit.py --flash`.

## Assembly

1. **Firmware.** Before soldering, write the firmware into both modules, each through its own USB,
   without the board ([Flashing the FPGA and the ESP32](#flashing-the-fpga-and-the-esp32)). The
   bodies of J8 and J9 will cover the FPGA module's USB-C afterwards.
2. **The modules' headers.** The board has holes only for the pins in use and for the corner pins
   that hold the module. So lay each header against its row of holes and pull out with pliers the
   pins that have no hole under them. These are, by the module's pin numbers counted from the
   square pad 1:
   - M1: 4, 6, 7, 11, 15, 16, 17, 18 in one row; 24, 29, 34, 36 in the other;
   - M2: 2–10, 12, 13, 16, 17, 18 in one row; 23, 24, 27–31, 33, 34, 36, 37 in the other.
3. **Order.**
   1. J1..J9, in any order. Trim the thin pins of the RCA jacks (J7..J9) underneath to 2 mm.
   2. M1: put the headers into the board and the module on top; solder the module first, then the
      board from below. Cut M1's leads underneath flush with the board, leaving the solder: M2 will
      lie over them.
   3. Cut the leads and the retaining pegs of J4 and J5 underneath to 1 mm: M2 will lie over them
      too.
   4. M2: on headers the same way, component side down, away from the board. No sockets.
4. **Orientation.** Check it twice before soldering: a module turned by 180° gets its power on the
   wrong pins. Everything below is as on the top side's drawing: the input edge (J1, J5, J4) on the
   left, the output edge (J6..J9) on the right.
   - **M1 (Tang Nano 20K), on top:** the USB-C toward the output edge, the HDMI end toward the input
     edge, the square pad 1 at the top right.
   - **M2 (ESP32-DevKitC-VIE), underneath, component side down:** the micro-USB toward the input
     edge (it comes out in the input cap's opening), the antenna end (WROVER-IE) toward the middle
     of the board. The square pad 1, seen from above, at the bottom right.
   - **J1:** its optical face past the input edge; pad 1 (TX) is rectangular, the upper one.
   - **J5 and J4:** on the input edge below J1, J4 lower. On J4 the lower pad, with rounded
     corners, is pin 1 (VBAT, through F1), and the upper pad is pin 2 (GND). The polarity is not
     marked on the silkscreen.
   - **J6, J7, J9, J8:** top to bottom on the output edge: the TOSLINK output, coax S/PDIF, line R,
     line L.
5. **Hidden references.** The small references that didn't fit on the silkscreen are on the
   assembly drawings.

## Before the first power

- Inspect everything on the list from step 5 of [Ordering from JLCPCB](#ordering-from-jlcpcb).
- With an ohmmeter, check that there is no short: J4 between pins 1 and 2, TP6 (3V3_AON) to TP9
  (GND), TP7 (5V_SW) to TP9. These three pads stand in a row above M1, from left to right TP6, TP9,
  TP7.

## The first power-up

On the bench, outside the tube.

1. Feed J4 from a 12 V lab supply with the current limited: reversed polarity will blow F1.
2. TP6 must show 3.3 V (U5, always on). Without light in J1, the WAKE signal is 0 and U6 is off, so
   TP7 = 0 V and the modules have no power. That is as it should be.
3. With light in J1, TP7 shows about 5.3 V. The FPGA reads its firmware from its flash in about
   290 ms, and the ESP32 starts from its own. With a laptop on M2's USB, the console shows the
   host's start ([The laptop](#the-laptop-recording-a-drive-and-decoding-it-at-home)).

## Into the tube

1. Cut the tube to the measured assembled board and drill the four Ø2.4 holes
   ([The tube and the caps](#the-tube-and-the-caps)).
2. **Antenna.** Clip the pigtail's U.FL onto M2's WROVER-IE, at the module's antenna end. Lead the
   cable past that end, not across the module's shield: under the board to the edge with J2, J3
   and J8, along that edge toward the input edge, and up round the edge, more than 8 mm from the
   input edge and past the cap's blocks, to the SMA's place. Tape the cable and its spare, in a flat
   loop, to the underside of the board, so that nothing hangs below M2. Put the SMA into the input
   cap from the inside, the serrated washer and the nut outside.
3. Fit the input cap onto the board's input edge, outside the tube: J1's housing into its cut-out,
   the board's edges into the slots.
4. Lay the tube on its top, and the board with its M2 side up. Slide the board into the tube from
   the input end, output edge first, the cap trailing, until the flange sits on the tube's end. The
   board's free end can come down only onto the RCA housings, and M2 and the cable touch nothing.
5. Fit the output cap without turning the tube over: hold the board's end at the slots' height by
   the RCA threads that stick out of the tube, put the cap on by its slots and press it home: J6
   into its cut-out, the board's edges into the slots. Now turn the tube over.
6. Line up each flange with the tube's outline, drill Ø1.6 through the tube's holes into the blocks,
   about 8 mm deep, and drive in the four self-tapping screws until their heads seat. Put the ring
   terminal and the serrated washer under the ground block's screw.
7. Solder the wire from the terminal to the negative wire of J4's harness, by the plug, and cover it
   with heat-shrink. With an ohmmeter: zero between the tube and J4's pin 2.
8. Once the pigtail is on, never rest the board on M2: M2's end with the EN/BOOT buttons lies
   1.25 mm lower than the slots, and under the WROVER-IE's end the cable has 0.88 mm left.

## In the car

Mount the tube floor down on the two saddles, with four screws through the ears. First listening
only: the listener in the ring, powered, and the car sounds as before. Then a recording
([The laptop](#the-laptop-recording-a-drive-and-decoding-it-at-home)), then regeneration, and only
then injection (the repository's README,
["Bring-up, in this order"](README.md#bring-up-in-this-order)).

## The laptop: recording a drive and decoding it at home

The recorder, the decoder and their launchers are in `kit/3_laptop/` ([The files](#the-files)).

### Python

- **Windows 10/11:** Python 3 from python.org (3.13 or newer). When installing, tick "Add
  python.exe to PATH".
- **macOS (Apple Silicon too):** Python 3 from python.org, or `brew install python`.

The first run of `record` creates a `.venv` with pyserial by itself. The internet is needed once.

### Connecting

The laptop goes on the USB of M2 (the ESP32-DevKitC), not of the FPGA module.

#### The bridge's driver

The ESP32 board carries a CP2102N or a CH9102 bridge. `record` finds it by itself by its USB ID;
the port's name doesn't matter. If the port doesn't appear, you need a driver:
- **Windows** usually installs the driver itself. If Device Manager shows no COM port, install the
  Silicon Labs CP210x VCP (silabs.com) or WCH's driver for the CH9102 (wch-ic.com).
- **macOS:**
  - for the CP2102N, if `ls /dev/cu.*` doesn't show `cu.usbserial-…`, install the Silicon Labs
    CP210x VCP (there is a build for Apple Silicon) and allow it in "Privacy & Security";
  - macOS 13 and newer pick up the CH9102 with their own driver.
- **Apple Silicon:** answer "Allow" when it asks about the new accessory.

`record` opens the port without touching DTR and RTS. On the DevKitC they reset the ESP32, so the
recording doesn't restart the host. Some drivers still pulse them when the port opens: then the
ESP32 starts anew, and the recording shows it.

### Recording

**Windows:** double-click `record.bat`.

**macOS:** double-click `record.command`. If macOS won't let it run, the first time: right-click it,
"Open".

If there is a `record_args.txt` next to it, its line is added to every run. For example
`--port COM7` if there are several bridges, or `--auto-mark 60` for a mark every minute.

#### The status line

`mark` is the number of the last mark. Then:
- `lost: bad … fpga … seg … trace …`: losses on our side since the ESP32 started. They must stay
  at 0.
- `gaps`, `parity`: gaps in the control blocks, and blocks dropped for parity.
- `tel`: how many telegrams have come.
- `starts`: how many times the ESP32 has started.
- `W/E`: the host's warnings and errors.
- `dumps`: the line's dumps.
- At the end, the last sound value (volume, tone), or, if there has been none yet, the last
  telegram.

The alarms stand at the start of the line while they last: `NO LINE FOR … s`, `PORT …`,
`DISK ERROR`.

#### Sounds

A short high beep is a mark. Long low beeps are an alarm:
- the port lost (repeated every 10 s while it is gone);
- the ESP32 started anew;
- a loss counter rose;
- 25 s without a single line;
- the host didn't answer a key;
- a disk error.

The status line shows what exactly happened.

#### Keys

- `m`: a mark, with a beep and a big number on the screen. Say what you did, with this number, into
  the phone's voice recorder, or add a note.
- `n`: a note to the last mark. It is typed in the status line; Enter ends it, Esc cancels it. The
  recording doesn't stop meanwhile.
- `d`: the host prints a dump of what the FPGA captured. After power-on, that is the ring's start.
- `c`: the FPGA captures the line anew, and the host prints the dump when the buffer is full. The
  program asks first: a dump of the ring's start that has not been printed yet will be lost.
- `q`: quit (it asks first).

The keys also work in a Ukrainian or Russian keyboard layout (`ь т в с й н`) and with Caps Lock
on. Injection (`i` on the host's console) is never switched on from this program.

The laptop doesn't sleep while the recording runs. But on Windows, for a closed lid, you have to set
"closing the lid: do nothing", and a MacBook must stay open.

### What to record in the car

1. **The ring's start.** Connect the laptop and start `record` before the car wakes up. After the
   wake-up, press `d`: the dump of the ring's start is needed for step 1 of the bring-up
   ([README](README.md#bring-up-in-this-order)).
2. **The sound scales.** Take every control (volume, bass, treble, balance) from one end to the
   other, with a mark at each end and a note of what it was. If the car's menu has a volume for the
   parking sensors or for the chimes, take those the same way.
3. **The steering wheel's buttons.** Press a button, then at once a mark and a note ("next track"
   and so on).
4. **Sources.** Switch the sources, to AUX among them, each with a mark.
5. **Reverse gear and a chime.** Put the car in reverse, and set off a chime (a door, the key, the
   belt), each with a mark: they show whether the parking sensors and the chimes travel the ring as
   audio.

### Decoding at home

**Windows:** double-clicking `decode.bat` decodes the newest recording. You can also drop the
`.log` of the recording you want onto it.

**macOS:** `decode.command`, or in Terminal `bash decode.command logs/<recording>`.

The result goes to `logs/<recording>.d/`:
- `summary.txt`: the recording's parts, the ESP32's starts, the counters and each time they rose,
  the silences, the marks, the dumps, the functions by frequency.
- `sound.txt`: for every sound value, the lowest, the highest and every change, with the marks
  between them. The car's scales are worked out from this.
- `marks.txt`: the telegrams from 5 s before each mark to 3 s after it, each showing how often its
  function occurred over the whole recording. A rare one next to a mark is the button that was
  pressed.
- `telegrams.csv`: all the telegrams.
- `functions.txt`: every function with its payload.
- `console.txt`: the host's other lines.
- `dump_N.txt` with `dump_N_analysis.txt`: each dump of the line and what can be read from it: the
  ring's rate, the preambles, the parity.

The decoded recording (`logs/<recording>.d/`) goes back into the repository: the scales are filled
in from it.
