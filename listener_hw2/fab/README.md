# Manufacturing package: MOST25 to AUDIO: listener board v2.0, rev 2.0 (2026-10-11)

Written by `make_fab2.py` from `most_listener_v2.kicad_pcb` and the sheet; do not edit by hand. Run it
again after any change to the board or the sheet.

| File | What |
|---|---|
| `most_listener_v2-gerbers.zip` | everything below that the board house needs: the Gerbers, both drill files, the job file |
| `most_listener_v2-F_Cu.gtl`, `-In1_Cu.g1`, `-In2_Cu.g2`, `-B_Cu.gbl` | copper, top to bottom (In1 and In2 are the ground planes) |
| `most_listener_v2-F_Mask.gts`, `-B_Mask.gbs` | solder mask, top and bottom |
| `most_listener_v2-F_Silkscreen.gto`, `-B_Silkscreen.gbo` | silkscreen, top and bottom |
| `most_listener_v2-F_Paste.gtp`, `-B_Paste.gbp` | solder paste, top and bottom: SMD parts on both sides |
| `most_listener_v2-Edge_Cuts.gm1` | board outline |
| `most_listener_v2-PTH.drl`, `-NPTH.drl` | drill files, Excellon, mm: plated and non-plated holes |
| `most_listener_v2-job.gbrjob` | Gerber job file: the layers and the stack-up, for the board house's software |
| `most_listener_v2-bom.csv` | every part, grouped by value and footprint (the max assembly and the hand parts) |
| `most_listener_v2-pos.csv` | pick-and-place, SMD parts on both sides, mm, KiCad's rotations |
| `most_listener_v2-bom-jlcpcb-<assembly>.csv` | JLCPCB's BOM of one assembly: the parts it places, with their LCSC numbers |
| `most_listener_v2-cpl-jlcpcb-<assembly>.csv` | JLCPCB's pick-and-place of the same parts, JLCPCB's rotations |
| `most_listener_v2-schematic.pdf` | the schematic |
| `most_listener_v2-assembly-top.pdf`, `-assembly-bottom.pdf` | each side for assembly (the bottom seen from below): every reference, also those hidden on the silk, the polarity marks, the outline |

## The assemblies

One board and one case for all three: every connector is fitted in each. The assemblies differ
only in the parts behind the connectors, and the gateware and the firmware are the same.

| Assembly | Fitted | JLCPCB files | Parts JLCPCB places | BOM lines | Parts left off |
|---|---|---|---|---|---|
| **min** | the core + S/PDIF out | `most_listener_v2-bom-jlcpcb-min.csv`, `most_listener_v2-cpl-jlcpcb-min.csv` | 103 (44 top, 59 bottom) | 42 | 60 |
| **mid** | the core + S/PDIF out + line out | `most_listener_v2-bom-jlcpcb-mid.csv`, `most_listener_v2-cpl-jlcpcb-mid.csv` | 143 (44 top, 99 bottom) | 52 | 20 |
| **max** | the core + S/PDIF out + line out + TOSLINK in | `most_listener_v2-bom-jlcpcb-max.csv`, `most_listener_v2-cpl-jlcpcb-max.csv` | 163 (57 top, 106 bottom) | 58 | 0 |

The core is everything not listed below: power, the ring with its bypass and watchdog, M1 (the
FPGA), U7 (Si514), M2 (the host, Bluetooth in), J3 (I2S) and J2 (the analyser).

| Block | Its parts |
|---|---|
| S/PDIF out | C29 C31 C48 C49 D4 R26 R27 R28 U14 |
| line out | C50 C51 C52 C53 C54 C55 C56 C57 C58 C59 C60 C61 C62 C69 C70 C71 C72 C73 C74 C75 C76 C77 C78 C79 C84 C85 D5 D6 R32 R33 R43 R44 R45 R46 R47 R48 U15 U16 U17 U18 |
| TOSLINK in | C27 C28 C30 C32 C33 C34 C35 C36 C37 C38 C39 C40 FB3 R24 R25 R29 R30 U12 U13 X1 |

- **min.** J5 (TOSLINK in), J8 and J9 (line out) are fitted but not connected: J5 has no supply,
  and J8 and J9 no signal.
- **mid.** J5 is fitted but not connected, as in min.
- **max.** U13 (SRC4192) is most of the difference in price: LCSC had 8 on 2026-10-07. For more
  boards, consign the rest.

## The board

- 98 x 60 mm, 4 layers, FR-4 1.6 mm,
  35 um copper outside and 15 um inside: JLCPCB's stack-up JLC04161H-7628 (prepreg 7628 between the
  outer and the inner layers). In1 and In2 are solid ground.
- Tracks from 0.2 mm, clearance 0.15 mm; 222 vias of 0.6/0.3 mm.
- Smallest hole 0.3 mm; 319 plated and 14 non-plated holes; no slots.
- Solder mask and silkscreen on both sides; SMD parts on both sides.
- Surface finish ENIG: flat pads for U4/U11 (VSSOP-8, 0.5 mm pitch) and the exposed pads of U5
  (WSON-6, 2 x 2 mm) and U6 (HSOP-8).

## Notes for the parts

- U7, Si514: any 3.3 V CMOS variant off the shelf (format C, M or N), in the 3.2 x 5 (B) or
  2.5 x 3.2 (C) package, with any start-up frequency and I2C address - the FPGA finds the
  address and sets the frequency. Example: 514CBA000110BAGR.
- C61, C62, C69..C72 (the line out's filter): C0G/NP0.
- X1: any 24.576 MHz 3.3 V CMOS oscillator in the 4-pin 3.2 x 2.5 mm package (1 OE, 2 GND,
  3 output, 4 VDD), as the Abracon ASE the footprint was drawn for.
- M1 (Tang Nano 20K, top) and M2 (ESP32-DevKitC-VIE, bottom) are soldered in on their own pin
  headers, 2 x 20 and 2 x 19 on 2.54 mm; no sockets. Solder M1 first and cut its pins flush on
  the bottom, then M2.
- J7..J9 (BKL 0101153): pad 3, the thin pin beside the axis, is not connected.

## Ordering at JLCPCB, with the SMD parts assembled

1. **PCB.** Upload `most_listener_v2-gerbers.zip`. Choose 4 layers, 1.6 mm, the stack-up JLC04161H-7628,
   1 oz outer and 0.5 oz inner copper, ENIG, green mask with white silkscreen, and 5 boards or
   more.
2. **Assembly.** Both sides, Standard PCBA (consigned parts need it), and "Confirm parts
   placement" on.
3. **BOM and CPL.** Upload the pair of the assembly you want, `most_listener_v2-bom-jlcpcb-<assembly>.csv`
   and `most_listener_v2-cpl-jlcpcb-<assembly>.csv`. The two files leave out the same parts, and nothing
   else changes.
   - F1 (C2925010) is an LCSC part. If JLCPCB holds none, its BOM page buys it from LCSC
     with the order.
4. **Placement preview.** Before paying, check pin 1 of every IC and of X1 on both sides, and the
   polarity of D1..D3, C44, C45, C63, C78 and C81.
   - The rotations were read off each chosen part's LCSC footprint (2026-10-03). On the bottom,
     JLCPCB counts them as KiCad's mirrored: 180 - KiCad's + the part's turn.
   - Each pin 1 dot goes to the board's pin 1 mark, the + of each electrolytic to the side of
     its silk +.
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
   - J5 (FCR684208R): Cliff ORJ-8 / OTJ-8 (FCR684208R / FCR684208T), from DigiKey (not at LCSC)
   - J6 (FCR684208T): Cliff ORJ-8 / OTJ-8 (FCR684208R / FCR684208T), from DigiKey (not at LCSC)
   - J7 (RCA 75R): BKL Electronic 0101153
   - J8 (LINE L): BKL Electronic 0101153
   - J9 (LINE R): BKL Electronic 0101153
   - M1 (Tang Nano 20K): Sipeed Tang Nano 20K, on its own pin headers
   - M2 (ESP32-DevKitC-VIE): Espressif ESP32-DevKitC-VIE, on its own pin headers
