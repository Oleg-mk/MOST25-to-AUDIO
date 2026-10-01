# Manufacturing package: MOST25 to AUDIO: listener board, rev 1.4 (2026-10-01)

Written by `make_fab.py` from `most_listener.kicad_pcb` and the sheet; do not edit by hand. Run it
again after any change to the board: `check_all.py` fails while this folder does not match.

| File | What |
|---|---|
| `most_listener-gerbers.zip` | everything below that the board house needs: the Gerbers, both drill files, the job file |
| `most_listener-F_Cu.gtl`, `-B_Cu.gbl` | copper, top and bottom (the bottom is the ground plane) |
| `most_listener-F_Mask.gts`, `-B_Mask.gbs` | solder mask, top and bottom |
| `most_listener-F_Silkscreen.gto` | silkscreen, top only |
| `most_listener-F_Paste.gtp` | solder paste, top, for a stencil: every SMD part is on the top |
| `most_listener-Edge_Cuts.gm1` | board outline |
| `most_listener-PTH.drl`, `-NPTH.drl` | drill files, Excellon, mm: plated and non-plated holes |
| `most_listener-job.gbrjob` | Gerber job file: the layers and the stack-up, for the board house's software |
| `most_listener-bom.csv` | the parts, grouped by value and footprint |
| `most_listener-pos.csv` | pick-and-place, SMD parts on the top, mm, KiCad's rotations |

## The board

- 125 x 80 mm, 2 layers, FR-4 1.6 mm,
  35 um (1 oz) copper on both sides.
- Tracks from 0.25 mm, clearance 0.15 mm; 293 vias of 0.6/0.3 mm.
- Smallest hole 0.3 mm; 423 plated and 15 non-plated holes; no slots.
- Solder mask on both sides, silkscreen on the top only.
- Surface finish ENIG: flat pads for U4/U11 (VSSOP-8, 0.5 mm pitch) and the exposed pads of U5
  (WSON-6, 2 x 2 mm) and U6 (HSOP-8).

## Notes for the parts

- U7, Si514: any 3.3 V CMOS variant off the shelf (format C, M or N), in the 3.2 x 5 (B) or
  2.5 x 3.2 (C) package, with any start-up frequency and I2C address - the FPGA finds the
  address and sets the frequency. Example: 514CBA000110BAGR.
- C61, C62, C69..C72 (the line out's filter): C0G/NP0.
- X1: 24.576 MHz 3.3 V CMOS oscillator, Abracon ASE (3.2 x 2.5 mm).
- M1 (Tang Nano 20K) and M2 (ESP32-DevKitC-VIE) are soldered in on their own pin headers,
  2 x 20 and 2 x 19 on 2.54 mm; no sockets.
- J7..J9 (BKL 0101153): pad 3, the thin pin beside the axis, is not connected.
