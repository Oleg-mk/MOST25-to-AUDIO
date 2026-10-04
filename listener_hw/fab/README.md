# Manufacturing package: MOST25 to AUDIO: listener board, rev 1.6 (2026-10-04)

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
| `most_listener-bom-jlcpcb.csv` | JLCPCB's BOM: the parts it places, with their LCSC numbers |
| `most_listener-cpl-jlcpcb.csv` | JLCPCB's pick-and-place: the same parts, JLCPCB's rotations |

## The board

- 123.55 x 78.9 mm, 2 layers, FR-4 1.6 mm,
  35 um (1 oz) copper on both sides.
- Tracks from 0.25 mm, clearance 0.15 mm; 252 vias of 0.6/0.3 mm.
- Smallest hole 0.3 mm; 382 plated and 17 non-plated holes; no slots.
- Solder mask on both sides, silkscreen on the top only.
- Surface finish ENIG: flat pads for U4/U11 (VSSOP-8, 0.5 mm pitch) and the exposed pads of U5
  (WSON-6, 2 x 2 mm) and U6 (HSOP-8).

## Notes for the parts

- U7, Si514: any 3.3 V CMOS variant off the shelf (format C, M or N), in the 3.2 x 5 (B) or
  2.5 x 3.2 (C) package, with any start-up frequency and I2C address - the FPGA finds the
  address and sets the frequency. Example: 514CBA000110BAGR.
- C61, C62, C69..C72 (the line out's filter): C0G/NP0.
- X1: any 24.576 MHz 3.3 V CMOS oscillator in the 4-pin 3.2 x 2.5 mm package (1 OE, 2 GND,
  3 output, 4 VDD), as the Abracon ASE the footprint was drawn for.
- M1 (Tang Nano 20K) and M2 (ESP32-DevKitC-VIE) are soldered in on their own pin headers,
  2 x 20 and 2 x 19 on 2.54 mm; no sockets.
- J7..J9 (BKL 0101153): pad 3, the thin pin beside the axis, is not connected.

## Ordering at JLCPCB, with the SMD parts assembled

1. **PCB.** Upload `most_listener-gerbers.zip`. Choose 2 layers, 1.6 mm, 1 oz outer copper,
   ENIG, green mask with white silkscreen, and 5 boards or more.
2. **Assembly.** Top side, Standard PCBA (consigned parts need it), and "Confirm parts
   placement" on.
3. **BOM and CPL.** Upload `most_listener-bom-jlcpcb.csv` and `most_listener-cpl-jlcpcb.csv`:
   57 lines, 54 LCSC parts.
   - F1 (C2925010) is an LCSC part. If JLCPCB holds none, its BOM page buys it from LCSC
     with the order.
   - On 2026-10-01 JLCPCB held 9 SRC4192IDBR (U13). For more boards, consign the rest.
4. **Placement preview.** Before paying, check pin 1 of every IC and of X1, and the polarity of
   D1..D3, C44, C45, C63, C78 and C81.
   - The rotations were read off each chosen part's LCSC footprint (2026-10-03). A generic
     table gets these wrong: the electrolytics (reversed) and U4, U8..U11, U14, U16, U18 (a
     quarter turn off). Each pin 1 dot goes to the board's pin 1 mark, the + of each
     electrolytic to the side of its silk +.
   - U7 (Si514) is consigned and has no LCSC footprint: JLCPCB draws its own, so check its
     pin 1 against the board's mark.
5. **Consigned:** U7 (Si514). Send these to JLCPCB, or add them through its global sourcing.
   For the Si514, any code by the rule above.
6. **By hand, after delivery.** These are not in JLCPCB's files. Their holes follow these exact
   parts, so a look-alike may not fit:
   - J1 (1-1394640-1): TE 1-1394640-1, the MOST pigtail FOT unit
   - J2 (ANALYSER): pin header 1x08, 2.54 mm
   - J3 (I2S): pin header 1x06, 2.54 mm
   - J4 (VBAT_IN): Molex 43650-0200, Micro-Fit 3.0, right angle
   - J5 (FCR684205R): Cliff ORJ-5 / OTJ-5 (FCR684205R / FCR684205T), from TME or Farnell (not at LCSC)
   - J6 (FCR684205T): Cliff ORJ-5 / OTJ-5 (FCR684205R / FCR684205T), from TME or Farnell (not at LCSC)
   - J7 (RCA 75R): BKL Electronic 0101153
   - J8 (LINE L): BKL Electronic 0101153
   - J9 (LINE R): BKL Electronic 0101153
   - M1 (Tang Nano 20K): Sipeed Tang Nano 20K, on its own pin headers
   - M2 (ESP32-DevKitC-VIE): Espressif ESP32-DevKitC-VIE, on its own pin headers
