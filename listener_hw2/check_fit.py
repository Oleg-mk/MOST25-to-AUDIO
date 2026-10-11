#!/usr/bin/env python3
"""check_fit.py - listener v2.0's board in its tube, the model: does every part fit, and where do the
end caps need their cut-outs, their blocks and the antenna's SMA.

Run with KiCad's own Python (it reads the board through pcbnew):
  "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" listener_hw2\\check_fit.py [board.kicad_pcb]

The tube is an 80 x 30 x 2 aluminium rectangular tube (76 x 26 inside, corners rounded inside by up
to CORNER_R), as long as the board (the user's decisions of 2026-10-11): cut to the soldered board's
length between the flanges' bearing faces, its input end and the farthest of its output end and the
RCA housings' fronts, +TUBE_L_TOL. The end caps are the reader's: a flange of the tube's outline on
each end face, the board's ends butting against the flanges, blocks into the tube (CAP_FLOAT off its
inside) that carry and hold the board, a saddle under the tube. The board is centred across the tube;
its height is set by the caps' blocks. Every part is a box: its courtyard on
the board, its height from HEIGHT (the makers' drawings, the sources beside each line); a part with
leads through the board carries them on the far side (LEADS), shortened where the assembly cuts them
(CUT). The checks:
  1. width: the board in the tube with SIDE_MIN a side;
  2. height: the tallest part on top plus the board plus the tallest underneath leave at least CLEAR
     above and below; the board goes in the middle of what is left (Z_BOARD, the caps' slots);
  3. corners: no box corner outside the tube's rounded inside;
  4. leads: no lead lands on a part on the far side or under a module's header strip; under a
     module no lead reaches the module's back and no part is taller than the gap;
  5. the ends, the board slid TUBE_L_TOL either way: J1's housing at least flush with the input cap's
     outer face; the TOSLINK faces (J5, J6) no deeper than TOSLINK_RECESS_MAX, J4's no deeper than
     J4_RECESS_MAX; the RCA bushings (J7..J9) through the output cap, their housings' fronts on the
     output flange; M2's micro-USB within USB_RECESS_MAX of where its plug's overmould reaches; M1's
     HDMI over L2, reported as a margin;
  6. the caps: every opening (its part + CLR a side; the RCA bushings' vertical slots, as tall as
     their axis is uncertain) at least MIN_WEB from the next and from the flange's edge (rectangles
     closer than that become one opening, as J5's and J4's); the SMA bulkhead of the Bluetooth
     antenna in the input cap's side margin on J4's side, its nut on the flange, its body clear of
     the walls (its cap shifted CAP_FLOAT), the board and the parts.
It prints, in each cap's own frame (seen from outside that end: u from the flange's left edge, v
from its bottom edge, w from its outer face into the tube; mm), every opening, the windows for the
blocks in the side margins and the SMA's position, for the caps' generator. Every number it assumes
is a constant below; the part numbers come from the sourced and checked table of 2026-10-11
(heights.json), the corrected value wherever a check corrected one.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
BOARD = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "most_listener_v2.kicad_pcb"

# the tube: aluminium rectangular tube 80 x 30 x 2, as long as the board (the user, 2026-10-11)
TUBE_W, TUBE_H, WALL = 80.0, 30.0, 2.0
INNER_W, INNER_H = TUBE_W - 2 * WALL, TUBE_H - 2 * WALL      # 76 x 26
CORNER_R = 2.0          # the inside corners' radius, at most (taken as up to 2.0, 2026-10-11)
TUBE_L_TOL = 0.1        # the tube is cut to the soldered board's length between the flanges' bearing faces (its input end,
                        # and the farthest of its output end and the RCA housings' fronts) +0.1/-0: the board may slide
                        # this much between the flanges, so every face is checked that much deeper (+0.2 would put J6's
                        # face past its limit)
CAP_FLOAT = 0.7         # a cap's blocks off the tube's inside walls, floor and top (gen_caps' GAP_TUBE), so that any tube
                        # in tolerance takes the caps unmeasured: the outside 0.3 small and a wall 0.25 thick (EN 755-9
                        # holds a 2 mm wall to +/-0.15..0.35, as the review read it) with FDM's outer faces 0.15 large put
                        # the tube's inside top 0.7 under the nominal; the saddle sets the height, so a cap shifts only
                        # across the tube, by up to this much, until its screws pin it
SIDE_MIN = 0.2          # the board's edge to the wall
CLEAR = 0.5             # air above the tallest part and under the lowest; a lead off a module's back
PCB_T = 1.6
# the caps, as the reader's (reader_hw2/gen_caps.py)
CAP_T = 2.0             # the flange's thickness at the cut-outs; the board's ends butt against it
CLR = 0.25              # an opening round its part, a side
MIN_WEB = 1.2           # the thinnest wall a 0.4 mm FDM nozzle prints solidly (three lines)
BLOCK_D = 6.0           # a block's depth into the tube (the reader's far block): the lips below hold over it
LIP_GAP = 0.2           # a block's lip off a part's courtyard
LEAD_KEEP = 2.0         # a block's lip off a soldered lead's centre (its fillet; the reader's gen_caps)
# the ends
J4_RECESS_MAX = 3.0     # J4's face may sit this far inside the input cap's outer face (the reader's: the same part)
TOSLINK_RECESS_MAX = CAP_T + 0.2    # a TOSLINK face as deep as the flange: the plug goes in through an opening of
                                    # the jack's size; + Cliff's general +/-0.2 on the face's position
USB_RECESS_MAX = 1.0    # M2's micro-USB face behind the deepest its plug's overmould reaches (the flange's inner
                        # face: the opening passes the overmould); judgement, as J4_RECESS_MAX: no plug drawing at
                        # hand gives the mated gap
USB_PLUG = (10.6, 8.5)  # a Micro-B plug's overmould at most, wide x high (the Micro-USB spec's boundary as quoted by
                        # ora.it.com, not read from the spec; cables are smaller): the opening passes it

# footprint -> (height of the body above its side of the board, the source)
HEIGHT = {
    "BKL_0101153_RCA_RA": (13.5, "BKL TDS 0101153: housing 14.7 x 14.8 x 13.5; the thread's top about 11.8"),
    "TE_MOST_Pigtail_FOT_2+0": (13.25, "TE C-2-2141577-1 rev B (DXF, 2:1): housing 12.8 on 0.45 standoffs"),
    "Sipeed_TangNano20K": (10.8, "header 2.54 + module PCB 1.75 (1.6 +0.15, unpublished) + HDMI 6.5 (bound; "
                                 "Foxconn QJ51191 on the same land is 6.07, so 10.2 typical)"),
    "CP_Elec_10x10.5": (10.5, "SamYoung CLZ case J10 (LCSC C53330124, 10 x 10): L 10 +0.5, catalogue p.74 note 1"),
    "Cliff_TOSLINK_ORJ8_OTJ8": (10.2, "Cliff FCR684208R/T rev 2: 10.00, general +/-0.2"),
    "PinHeader_1x08_P2.54mm_Vertical": (8.9, "Wurth 61300811121: 2.54 + 6.0, 8.89 at full tolerance"),
    "PinHeader_1x06_P2.54mm_Vertical": (8.9, "Wurth 61300611121: 2.54 + 6.0, 8.89 at full tolerance"),
    "Espressif_ESP32-DevKitC_V4": (8.4, "header 2.5 + DevKitC 1.6 + EN/BOOT switch 4.3 (bound; the WROVER-IE's 3.3, "
                                        "data sheet v2.4 fig. 13, gives 7.4)"),
    "Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal": (6.98, "Molex 'Mated Height' 6.98 (part attributes); "
                                                                     "the header alone is unpublished"),
    "CP_Elec_6.3x7.7": (6.0, "SamYoung BLA 16V 100u, case F60: L 5.7 +0.3 (catalogue p.72); the footprint is the "
                             "land only"),
    "L_Bourns_SRN6045TA": (4.6, "Bourns SRN6045TA: 4.2 +/-0.3, + 0.1 solder"),
    "L_Bourns-SRN8040_8x8.15mm": (4.2, "Bourns SRN8040: 4.0 max, + 0.2 solder"),
    "C_1210_3225Metric": (2.7, "Murata GRM32E, Taiyo Yuden MK325 code M: T 2.5 +/-0.2"),
    "D_SMA": (2.5, "MDD SS34, DO-214AC: 2.45 max, + solder"),
    "D_SMB": (2.5, "Diodes SMBJ (DS19002), SMB: J 2.50 max"),
    "SSOP-28_5.3x10.2mm_P0.65mm": (2.0, "TI DB0028A: 2 max"),
    "SOIC-8_3.9x4.9mm_P1.27mm": (1.75, "TI D0008A: 1.75 max"),
    "Texas_HSOP-8-1EP_3.9x4.9mm_P1.27mm_ThermalVias": (1.7, "TI DDA0008B: 1.7 max"),
    "SOT-23-5": (1.45, "TI DBV0005A: 1.45 max"),
    "SOT-23-6": (1.45, "TI DBV0006A: 1.45 max"),
    "C_0805_2012Metric": (1.45, "Samsung CL21, code Y: T 1.25 +/-0.20"),
    "Si514_3.2x5_2.5x3.2": (1.33, "Skyworks Si514 rev 1.2, table 18 (3.2 x 5): A 1.33 max"),
    "TSSOP-28_4.4x9.7mm_P0.65mm": (1.2, "TI PW 4040064-7/G (DIR9001 data sheet p.37): 1.20 max"),
    "TSSOP-20_4.4x6.5mm_P0.65mm": (1.2, "TI PW0020A: 1.2 max"),
    "Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm": (1.2, "YXC OT3225 (C2831388 data sheet p.3): 1.2 max"),
    "SOT-353_SC-70-5": (1.1, "TI DCK0005A: 1.1 max"),
    "SOT-363_SC-70-6": (1.1, "Nexperia SOT363-2: A 1.1 max"),
    "C_0603_1608Metric": (0.95, "Samsung, Yageo, FH 0603: T 0.80 +/-0.10, + solder"),
    "L_0603_1608Metric": (0.95, "Sunlord GZ1608 (SPEC GZ10130000): T 0.8 +/-0.15"),
    "VSSOP-8_2.3x2mm_P0.5mm": (0.9, "TI DCU0008A: 0.9 max"),
    "Fuse_1206_3216Metric": (0.8, "TLC ISS:F12T2 rev B p.3: 0.60 +0.20/-0.15"),
    "WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm": (0.8, "TI DRV0006A: 0.8 max"),
    "R_0603_1608Metric": (0.6, "UNI-ROYAL 0603: H 0.45 +/-0.10, + solder"),
    "D_SOD-882": (0.5, "Nexperia DFN1006-2 (SOD882): A 0.50 max"),
    "TestPoint_Pad_D2.0mm": (0.05, "a bare ENIG pad, no paste"),
    "MountingHole_2.7mm_M2.5": (0.0, "an empty hole: the caps hold the board, H1..H3 carry nothing in the tube"),
}
# the parts with leads through the board: footprint -> ({kind: length below its seating plane}, the source).
# Kinds: "pin" a numbered lead; "leg" J1's guide legs and the RCAs' thick legs (pad 2); "peg" an unnumbered peg
LEADS = {
    "TE_MOST_Pigtail_FOT_2+0": ({"pin": 2.75, "leg": 2.75, "peg": 4.0},
                                "TE C-2-2141577-1 rev B (DXF): pins, action pins and guide legs 2.75; the two 2.0 "
                                "pegs 4.0 to the tip (3.5 + 0.5 chamfer)"),
    "Cliff_TOSLINK_ORJ8_OTJ8": ({"pin": 3.5, "peg": 3.5},
                                "Cliff FCR684208R/T rev 2: pins, metal pegs and plastic bosses 3.00 +/-0.50"),
    "BKL_0101153_RCA_RA": ({"pin": 10.2, "leg": 5.85},
                           "BKL TDS 0101153: thin pins 9.45 +/-0.75, thick legs 5.4 +/-0.45"),
    "Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal": ({"pin": 3.5, "peg": 3.6},
                                                               "Digi-Key: post 3.18, taken as 3.5; the plastic peg "
                                                               "about 2.0 under the board (no figure found)"),
    "PinHeader_1x08_P2.54mm_Vertical": ({"pin": 3.2}, "Wurth 61300811121: tail 3.0 +/-0.2"),
    "PinHeader_1x06_P2.54mm_Vertical": ({"pin": 3.2}, "Wurth 61300611121: tail 3.0 +/-0.2"),
    "Sipeed_TangNano20K": ({"pin": 3.2}, "the header's short side into the board: 3.0 +/-0.2 (Wurth WR-PHD)"),
    "Espressif_ESP32-DevKitC_V4": ({"pin": 6.2}, "the header's long side into the board: 6.0 +/-0.2 (Wurth WR-PHD); "
                                                 "its short 3.0 through the DevKitC stays within the WROVER's 3.3"),
}
# cut at assembly: reference -> (what is left past the board's far face, the kinds cut, why)
CUT = {
    "M1": (0.5, ("pin",), "cut flush under the board before M2 goes on, the fillet left (fab/README.md)"),
    "J4": (1.0, ("pin", "peg"), "the tails and the plastic peg cut short before M2 goes on"),
    "J5": (1.0, ("pin", "peg"), "the pins, metal pegs and plastic bosses cut short before M2 goes on"),
    "J7": (2.0, ("pin",), "the thin pins trimmed to 2: uncut (8.6) they would set the bottom's height"),
    "J8": (2.0, ("pin",), "the thin pins trimmed to 2: uncut (8.6) they would set the bottom's height"),
    "J9": (2.0, ("pin",), "the thin pins trimmed to 2: uncut (8.6) they would set the bottom's height"),
}

# M1, the Tang Nano 20K, on top on its own pins (Sipeed data sheet v1.3, p.4 photo and p.6 drawing, scaled)
TANG = "Sipeed_TangNano20K"
TANG_HALF_W = 11.275            # 22.55 wide
TANG_END = (2.60, 3.19)         # the end pins to the module's USB-C end, to its HDMI end: not centred on its pins
TANG_HEADER, TANG_PCB_T = 2.54, 1.6     # the header's plastic (KiCad's model, Wurth 2.54); the module (unpublished)
TANG_HDMI = (3.77, 11.5, 15.0, 6.07)    # past the end (p.4 photo, an upper bound), deep (gen_reader2.py), wide, high
                                        # (Foxconn QJ51191-WFD6, the same land)
TANG_USB = (1.7, 8.94, 3.26)    # the USB-C past the end (p.4 photo, 1.6..1.7), wide, high (HRO TYPE-C-31-M-12 class)
TANG_LOW = 0.5                  # the module's own underside parts reach down to this above the board (the reader's
                                # TANG_UNDER; unpublished)
# M2, the ESP32-DevKitC-VIE, underneath on its own pins, component side down (Espressif's dimensions drawing;
# ESP32-WROVER-E/IE data sheet v2.4, fig. 13)
DEVKIT = "Espressif_ESP32-DevKitC_V4"
M2_HALF = (24.13, 13.97)        # the DevKitC 48.26 x 27.94, centred on its pins
M2_HEADER, M2_PCB_T = 2.5, 1.6  # its back this far under the board (the header's plastic, gen_listener.py); its PCB
M2_WROVER = (31.4, 18.0, 5.98, 3.3)     # the module: long, wide, past the DevKitC's antenna end, high with its PCB
M2_SWITCH_MAX = 5.0             # EN/BOOT 3 x 6 switches 5.0 high are stocked (LCSC, Botland): printed as a margin
M2_USB = (0.95, 1.30, 2.5, 3.0)    # the micro-USB past the DevKitC's end: 0.95 (Espressif's DXF silk) .. 1.30
                                    # (gen_listener.py); its body's height, unpublished: 2.5 (a common SMT micro-B
                                    # shell) .. 3.0 (the bound), so the plug's axis 1.25..1.50 under the DevKitC
UFL_BACK = 8.6                  # the WROVER-IE's U.FL within this of its antenna end (fig. 13: 23.05 from the far
                                # end of 31.4; the render is unverified, so the whole module's width)
# the ends: the connectors in their footprints' frames (fx across, fy along; local())
J1_HOUSING, J1_BUMP = (-14.1, 11.1), 11.4      # J1 across: the housing (TE DXF), its side bump at fy -9.0..-2.2
J1_FRONT, J1_REAR, J1_LIFT, J1_SLEEVE = -15.4, 9.35, 0.45, 3.5     # the housing's front, the header's rear (fy); the
                                                                    # housing's standoffs; the port sleeve past it
J1_STANDOFF = (-8.1, -4.1, -12.4)   # the front standoff across (fx) and its front (fy): 0.6 past the board's end
MF_FACE, MF_FX = -8.92, (-3.325, 6.325)     # J4: the face (fy), the body across (KiCad's generator for Molex 43650)
T8_FACE, T8_HALF, T8_FRAME = 11.00, 4.85, (0.30, 9.37)  # J5, J6: the face from pin 2, half the width, the front
                                                         # frame's z (on 0.30 feet; 9.17 +0.2)
RCA_FRONT, RCA_REAR, RCA_HALF = 12.87, -2.0, 7.35   # J7..J9 from pin 1: the housing's front (BKL TDS by scale,
                                                    # heights.json's check: the fronts at x 97.93..98.05), its rear,
                                                    # half its width
RCA_AXIS_Z, RCA_AXIS_TOL = 6.75, 0.3    # the bushing's axis above the board: BKL's TDS does not dimension it, it scales
                                        # 6.47..7.0 (heights.json's check)
RCA_THREAD = (8.7, 12.7)        # 1/2-28 UNEF from the housing's front: long, across (BKL TDS)
RCA_HOLE = 13.2                 # across: the thread + CLR a side, the widest that keeps MIN_WEB to J6's opening; a
                                # vertical slot, its arcs' centres RCA_AXIS_TOL above and below the model's axis, so the
                                # thread keeps CLR anywhere in the axis's range, no jack measured
RCA_NUT = 16.0                  # the TDS's nut across flats: more than J9-J8's pitch, so the jacks go without nuts
# the Bluetooth antenna: an SMA female bulkhead in the input cap, the jack of a U.FL-to-SMA pigtail from M2 (the
# user, 2026-10-11). No pigtail is chosen and their jacks' 1/4-36 UNS-2A threads come round or with one or two flats,
# so the hole is round and takes any of them: the thread across its crests + CLR a side (an FDM hole prints
# 0.1..0.2 small); the nut and its internal-tooth lock washer outside keep the jack from turning
SMA_THREAD = 6.35               # 1/4-36 UNS-2A: 0.250 in across the crests
SMA_HOLE = SMA_THREAD + 2 * CLR
SMA_NUT_AF = 8.0                # the nut outside; the body behind the panel taken no larger (a flanged or O-ring
                                # type, 11 across, does not fit the 8.0 margin)
SMA_PANEL_MAX = 3.2             # the least found: Amphenol's SMA-to-U.FL assemblies
SMA_BODY_IN = 20.0              # behind the panel: a pigtail jack's body, crimp ferrule and boot, taken long (Amphenol's
                                # panel jack 901-10736 is 10.85)
SMA_GAP = 0.3                   # the body off the walls (with its cap shifted CAP_FLOAT against them), the board, the
                                # parts
PIGTAIL_D = 1.37                # the pigtail's cable (1.13 or 1.37)
PIGTAIL_STOCK = (100, 150, 200)
PIGTAIL_SLACK = 1.2             # bends and the plugs' exits over the path's straight runs
DUPONT_H = 16.4                 # a 2.54 crimp housing on J2/J3 above the board (2.54 + 13.85: RS, Amphenol 65039)


def mm(v):
    return pcbnew.ToMM(v)


def local(fp, fx, fy):
    """A point of footprint fp's own frame (as drawn, on top) on the board."""
    assert not fp.IsFlipped(), "local() is for the top's parts"
    a = math.radians(fp.GetOrientationDegrees())
    p = fp.GetPosition()
    return (mm(p.x) + fx * math.cos(a) + fy * math.sin(a), mm(p.y) - fx * math.sin(a) + fy * math.cos(a))


def box(fp):
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    bb = fp.GetCourtyard(layer).BBox()
    if not bb.GetWidth():
        bb = fp.GetBoundingBox(False)
    return (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))


def span(pts):
    return (min(q[0] for q in pts), min(q[1] for q in pts), max(q[0] for q in pts), max(q[1] for q in pts))


def inside(p, b, r=0.0):
    return b[0] - r < p[0] < b[2] + r and b[1] - r < p[1] < b[3] + r


def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def gap(a, b):
    """The clearance between two boxes (negative when they overlap), as the reader's gen_caps."""
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])


class Frame:
    """A module's frame from three of its pads: a and b on one row (b at the end s points to), c across
    from b; s along the module from its pins' centre, t across."""

    def __init__(self, fp, a, b, c):
        xy = {p.GetNumber(): (mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in fp.Pads()}
        pa, pb, pc = xy[a], xy[b], xy[c]
        ln, row = math.dist(pa, pb), math.dist(pb, pc)
        self.e = ((pb[0] - pa[0]) / ln, (pb[1] - pa[1]) / ln)
        self.n = ((pc[0] - pb[0]) / row, (pc[1] - pb[1]) / row)
        self.half, self.row = ln / 2, row
        self.o = ((pa[0] + pb[0]) / 2 + (pc[0] - pb[0]) / 2, (pa[1] + pb[1]) / 2 + (pc[1] - pb[1]) / 2)

    def at(self, s, t):
        return (self.o[0] + s * self.e[0] + t * self.n[0], self.o[1] + s * self.e[1] + t * self.n[1])

    def rect(self, s0, s1, t0, t1):
        return span([self.at(s, t) for s in (s0, s1) for t in (t0, t1)])

    def strips(self):
        """The two header strips' plastic on the board, end to end over the module's pins."""
        return [self.rect(-self.half - 1.27, self.half + 1.27, t - 1.27, t + 1.27)
                for t in (-self.row / 2, self.row / 2)]


def classify(fpname, pad):
    num = pad.GetNumber()
    if fpname == "BKL_0101153_RCA_RA":
        return "leg" if num == "2" else "pin"
    if num:
        return "pin"
    if fpname == "TE_MOST_Pigtail_FOT_2+0":
        return "peg" if mm(pad.GetDrillSize().x) >= 2.0 else "leg"
    return "peg"


def main() -> int:
    board = pcbnew.LoadBoard(str(BOARD))
    ends = [(mm(q.x), mm(q.y)) for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts
            for q in (d.GetStart(), d.GetEnd())]                        # the outline's lines, not their stroke
    x0, y0 = min(q[0] for q in ends), min(q[1] for q in ends)
    x1, y1 = max(q[0] for q in ends), max(q[1] for q in ends)
    L, W = x1 - x0, y1 - y0
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    name = {r: str(fp.GetFPID().GetLibItemName()) for r, fp in fps.items()}
    side = {r: "B" if fp.IsFlipped() else "F" for r, fp in fps.items()}
    H = {r: HEIGHT[name[r]][0] for r in fps if name[r] in HEIGHT}
    fails, notes = [], []

    unknown = sorted(f"{r} ({name[r]})" for r in fps if name[r] not in HEIGHT)
    if unknown:
        print("FAIL: no height for " + ", ".join(unknown))
        return 1
    t_pcb = mm(board.GetDesignSettings().GetBoardThickness())
    if abs(t_pcb - PCB_T) > 0.001:
        print(f"FAIL: the board is {t_pcb:.2f} thick, the model {PCB_T}")
        return 1
    ref = {n: [r for r in fps if name[r] == n] for n in set(name.values())}
    m1r, m2r, j1r = ref[TANG][0], ref[DEVKIT][0], ref["TE_MOST_Pigtail_FOT_2+0"][0]

    # 1. width
    side_gap = (INNER_W - W) / 2
    print(f"board {L:.2f} x {W:.2f} mm in a tube {INNER_W:.1f} x {INNER_H:.1f} inside: {side_gap:.2f} mm a side")
    if side_gap < SIDE_MIN:
        fails.append(f"the board is {W:.2f} wide: {side_gap:.2f} a side, {SIDE_MIN} wanted")

    # the modules and the parts' boxes (a module by its PCB, J1 by its body: their courtyards are pin rows)
    m1, m2 = Frame(fps[m1r], "20", "1", "21"), Frame(fps[m2r], "19", "1", "20")    # s to M1's USB-C, M2's antenna
    m1_end = (m1.half + TANG_END[0], -m1.half - TANG_END[1])                       # the USB-C end, the HDMI end
    m1_pcb = m1.rect(m1_end[1], m1_end[0], -TANG_HALF_W, TANG_HALF_W)
    hdmi_s = m1_end[1] - TANG_HDMI[0]
    hdmi_over = m1.rect(hdmi_s, m1_end[1], -TANG_HDMI[2] / 2, TANG_HDMI[2] / 2)   # the HDMI past the module's end
    usbc_s = m1_end[0] + TANG_USB[0]
    usbc_over = m1.rect(m1_end[0], usbc_s, -TANG_USB[1] / 2, TANG_USB[1] / 2)
    m2_pcb = m2.rect(-M2_HALF[0], M2_HALF[0], -M2_HALF[1], M2_HALF[1])
    wr_end = M2_HALF[0] + M2_WROVER[2]
    m2_wrover = m2.rect(wr_end - M2_WROVER[0], wr_end, -M2_WROVER[1] / 2, M2_WROVER[1] / 2)
    m2_over = m2.rect(M2_HALF[0], wr_end, -M2_WROVER[1] / 2, M2_WROVER[1] / 2)     # the module past the DevKitC
    ufl = m2.rect(wr_end - UFL_BACK, wr_end, -M2_WROVER[1] / 2, M2_WROVER[1] / 2)
    boxes = {r: box(fp) for r, fp in fps.items()}
    boxes[m1r] = span([hdmi_over[:2], hdmi_over[2:], usbc_over[:2], usbc_over[2:], m1_pcb[:2], m1_pcb[2:]])
    boxes[m2r] = span([m2_pcb[:2], m2_pcb[2:], m2_wrover[:2], m2_wrover[2:]])
    j1 = fps[j1r]
    boxes[j1r] = span([local(j1, fx, fy) for fx in (J1_HOUSING[0], J1_BUMP) for fy in (J1_FRONT, J1_REAR)])
    rects = {r: [b] for r, b in boxes.items()}          # what a block's lip meets
    rects[m1r] = [boxes[m1r]] + m1.strips()
    rects[m2r] = [m2_pcb, m2_wrover] + m2.strips()

    # the leads through the board, on the far side of their parts
    leads = []
    for r, fp in sorted(fps.items()):
        if name[r] not in LEADS:
            continue
        lens = LEADS[name[r]][0]
        for pad in fp.Pads():
            att = pad.GetAttribute()
            if att not in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                continue
            kind = classify(name[r], pad)
            beyond = lens[kind] - PCB_T
            if r in CUT and kind in CUT[r][1]:
                beyond = min(beyond, CUT[r][0])
            leads.append({"ref": r, "pad": pad.GetNumber() or kind, "kind": kind, "side": side[r], "beyond": beyond,
                          "p": (mm(pad.GetPosition().x), mm(pad.GetPosition().y)),
                          "rad": mm(pad.GetDrillSize().x) / 2, "soldered": att == pcbnew.PAD_ATTRIB_PTH})

    # 2. height
    tops = [(H[r], r) for r in fps if side[r] == "F"]
    bots = [(H[r], r) for r in fps if side[r] == "B"]
    for ld in leads:
        (bots if ld["side"] == "F" else tops).append((ld["beyond"], ld["ref"] + " leads"))
    top, bot = max(tops), max(bots)
    lo, hi = bot[0] + CLEAR, INNER_H - CLEAR - PCB_T - top[0]
    z = (lo + hi) / 2                       # the spare half above, half below
    zt = z + PCB_T
    print(f"tallest on top {top[1]} {top[0]:.2f}, underneath {bot[1]} {bot[0]:.2f}: the board's underside may sit "
          f"{lo:.2f}..{hi:.2f} above the floor")
    if hi < lo:
        fails.append(f"no room in height: {top[0]} + {PCB_T} + {bot[0]} + 2 x {CLEAR} > {INNER_H}")
    else:
        print(f"  Z_BOARD {z:.2f}: {z - bot[0]:.2f} mm under {bot[1]}, {INNER_H - zt - top[0]:.2f} mm over {top[1]}; "
              f"a tube {hi - lo:.2f} mm lower still fits")
    m2_sw = M2_HEADER + M2_PCB_T + M2_SWITCH_MAX
    print(f"  M2 with {M2_SWITCH_MAX} mm EN/BOOT switches would reach {m2_sw:.2f} under the board: {z - m2_sw:.2f} "
          f"above the floor")

    # 3. the corners: every box's outer corners inside the tube's rounded inside
    def in_tube(u, v, r=0.0):
        """(u, v) in the tube's inside (u from its left wall, v from its floor), r off it."""
        hu, hv = INNER_W / 2, INNER_H / 2
        du, dv = abs(u - hu), abs(v - hv)
        if du > hu - r + 1e-9 or dv > hv - r + 1e-9:
            return False
        cu, cv, cr = hu - CORNER_R, hv - CORNER_R, CORNER_R - r
        return not (du > cu and dv > cv and math.hypot(du - cu, dv - cv) > max(cr, 0.0) + 1e-9)
    for r in sorted(fps):
        b = boxes[r]
        za, zb = (zt, zt + H[r]) if side[r] == "F" else (z - H[r], z)
        for yc in (b[1], b[3]):
            for zc in (za, zb):
                if not in_tube(yc - y0 + side_gap, zc):
                    fails.append(f"{r} reaches outside the tube at y {yc:.2f}, {zc:.2f} above the floor")
    jy = (boxes[j1r][1], boxes[j1r][3])
    print(f"{j1r}'s housing {jy[0] - y0 + side_gap:.2f} / {INNER_W - (jy[1] - y0 + side_gap):.2f} mm from the walls, "
          f"{INNER_H - zt - H[j1r]:.2f} under the top")

    # 4. leads: on the far side's parts, under the modules
    modules = {m1r: ("F", [m1_pcb], m1.strips(), TANG_LOW),
               m2r: ("B", [m2_pcb, m2_over], m2.strips(), None)}
    under = {}                                          # (part, module) -> (cut leads under it, the least left)
    for ld in leads:
        if ld["beyond"] <= 0:
            continue
        far = "B" if ld["side"] == "F" else "F"
        what = f"{ld['ref']} pad {ld['pad']} at ({ld['p'][0]:.2f}, {ld['p'][1]:.2f}), {ld['beyond']:.2f} through"
        for o in fps:
            if side[o] != far or o in modules or H[o] < 0.2:     # a bare pad or a hole has no body to hit
                continue
            if inside(ld["p"], boxes[o], ld["rad"]):
                fails.append(f"{what}, lands on {o}")
        for mr, (mside, pcbs, strips, low) in modules.items():
            if mside != far or mr == ld["ref"]:
                continue
            if any(inside(ld["p"], s, ld["rad"]) for s in strips):
                fails.append(f"{what}, lands on {mr}'s header strip")
                continue
            if mr == m2r:
                limits = [(M2_HEADER, pcbs[0]), (M2_HEADER + M2_PCB_T, pcbs[1])]
            else:
                limits = [(low, pcbs[0])]
            for back, b in limits:
                if inside(ld["p"], b, ld["rad"]):
                    if ld["beyond"] > back - CLEAR:
                        fails.append(f"{what}, under {mr}, whose back is {back} off the board")
                    elif ld["ref"] in CUT and ld["kind"] in CUT[ld["ref"]][1]:
                        k, left = under.get((ld["ref"], mr), (0, math.inf))
                        under[(ld["ref"], mr)] = (k + 1, min(left, back - ld["beyond"]))
                    break
    for (r, mr), (k, left) in sorted(under.items()):
        notes.append(f"{r}: {k} leads under {mr}'s back, {CUT[r][2]}; {left:.2f} left to it")
    for r in sorted(fps):                               # parts under the modules
        if r in modules or H[r] <= 0.05:
            continue
        for mr, (mside, pcbs, strips, low) in modules.items():
            if side[r] != mside:
                continue
            if any(overlap(boxes[r], s) for s in strips):
                fails.append(f"{r} under {mr}'s header strip")
            if mr == m2r:
                for back, b in ((M2_HEADER, m2_pcb), (M2_HEADER + M2_PCB_T, m2_over)):
                    if overlap(boxes[r], b) and H[r] > back - CLEAR:
                        fails.append(f"{r} ({H[r]}) under {mr}, whose back is {back} off the board")
            elif overlap(boxes[r], m1_pcb):
                if H[r] > TANG_HEADER - CLEAR:
                    fails.append(f"{r} ({H[r]}) under {mr}, whose PCB is {TANG_HEADER} off the board")
                else:
                    b = boxes[r]
                    ov = (min(b[2], m1_pcb[2]) - max(b[0], m1_pcb[0]), min(b[3], m1_pcb[3]) - max(b[1], m1_pcb[1]))
                    notes.append(f"{r} ({H[r]}) has {ov[0]:.2f} x {ov[1]:.2f} of its courtyard under {mr}'s PCB: "
                                 f"the module's own underside must be free {TANG_HEADER - H[r]:.2f} down there")
    for r in sorted(fps):                               # under the modules' overhangs (M1's HDMI and USB-C)
        if side[r] == "F" and r != m1r:
            for what, b in (("HDMI", hdmi_over), ("USB-C", usbc_over)):
                if overlap(boxes[r], b) and H[r] > TANG_HEADER + TANG_PCB_T:
                    fails.append(f"{r} ({H[r]}) under {m1r}'s {what}, {TANG_HEADER + TANG_PCB_T:.2f} off the board")
    print(f"leads through: {sum(1 for ld in leads if ld['side'] == 'F')} from the top, "
          f"{sum(1 for ld in leads if ld['side'] == 'B')} from underside parts; under {m2r} the gap is {M2_HEADER}, "
          f"under {m1r}'s own parts {TANG_LOW}")

    # 5. the ends: x0 is the input end, x1 the output end. The input flange's inner face bears on the board's end
    # (J1's standoff goes through its notch, M2's micro-USB into its opening, both larger), the output flange's on
    # the farthest of the board's end and the RCA housings' fronts (wider than their holes). The tube is cut to the
    # length between those +TUBE_L_TOL, so the board slides by up to that much: each face is taken that much deeper,
    # J1's housing and the RCA threads that much less out
    rca = sorted(ref["BKL_0101153_RCA_RA"], key=lambda r: mm(fps[r].GetPosition().y))
    fr = [local(fps[r], 0, RCA_FRONT)[0] for r in rca]
    x_out = max([x1] + fr)
    in_outer, out_outer = x0 - CAP_T, x_out + CAP_T
    print(f"the tube: {x_out - x0:.2f} +{TUBE_L_TOL}/-0 long, the soldered board's length from its input end to the "
          f"farthest of its output end and the RCA housings' fronts ({x_out - x1:.2f} past it); the board slides up "
          f"to {TUBE_L_TOL} between the flanges")
    front = min(local(j1, fx, J1_FRONT)[0] for fx in J1_HOUSING)
    print(f"input end: {j1r}'s housing {in_outer - front - TUBE_L_TOL:.2f}..{in_outer - front:.2f} mm out of the cap "
          f"(cap {CAP_T} mm), its port sleeve {J1_SLEEVE} more")
    if front + TUBE_L_TOL > in_outer:
        fails.append(f"{j1r}'s housing {front + TUBE_L_TOL - in_outer:.2f} mm inside the input cap's outer face")
    toslink = {}
    for r in ref["Cliff_TOSLINK_ORJ8_OTJ8"]:
        fx_ = local(fps[r], 0, T8_FACE)[0]
        at_in = abs(fx_ - x0) < abs(fx_ - x1)
        toslink[r] = (at_in, (fx_ - in_outer) if at_in else (out_outer - fx_))

    def deep(r, d, lim, cap):
        print(f"  {r}'s face {d:.2f}..{d + TUBE_L_TOL:.2f} mm inside the {cap} cap's outer face (limit {lim:.2f})")
        if d + TUBE_L_TOL > lim:
            fails.append(f"{r}'s face {d + TUBE_L_TOL:.2f} mm inside the {cap} cap's outer face, {lim:.2f} at most")

    def toslink_face(at_in):
        for r, (a, d) in sorted(toslink.items()):
            if a == at_in:
                deep(r, d, TOSLINK_RECESS_MAX, "input" if at_in else "output")
    toslink_face(True)
    for r in ref["Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal"]:
        deep(r, local(fps[r], 0, MF_FACE)[0] - in_outer, J4_RECESS_MAX, "input")
    usb_x = [m2.at(-M2_HALF[0] - o, 0)[0] for o in M2_USB[:2]]        # the micro-USB's face, both bounds
    if abs(min(usb_x) - x0) > abs(max(usb_x) - x1):
        fails.append(f"{m2r}'s micro-USB does not face the input end")
    rec = [u - x0 for u in usb_x]
    print(f"  {m2r}'s micro-USB face {min(rec):.2f}..{max(rec) + TUBE_L_TOL:.2f} mm behind the flange's inner face, the "
          f"plug's overmould let through to it (limit {USB_RECESS_MAX:.2f})")
    if max(rec) + TUBE_L_TOL > USB_RECESS_MAX or min(rec) < -CAP_T:
        fails.append(f"{m2r}'s micro-USB face {min(rec):.2f}..{max(rec) + TUBE_L_TOL:.2f} behind the flange's inner "
                     f"face, {USB_RECESS_MAX} at most, in front of its outer face at least")
    out_by = min(fr) + RCA_THREAD[0] - out_outer - TUBE_L_TOL
    print("output end:")
    toslink_face(False)
    print(f"  {'/'.join(rca)}'s threads {out_by:.2f} mm out of the cap; their housings' fronts "
          f"{x_out - max(fr):.2f}..{x_out - min(fr):.2f} behind the flange's inner face (the farthest bears on it); "
          f"slots {RCA_HOLE:.2f} wide, {RCA_HOLE + 2 * RCA_AXIS_TOL:.2f} tall round the {RCA_THREAD[1]:.2f} thread, "
          f"{(RCA_HOLE - RCA_THREAD[1]) / 2:.2f} a side at either end of the axis's {RCA_AXIS_Z - RCA_AXIS_TOL:.2f}.."
          f"{RCA_AXIS_Z + RCA_AXIS_TOL:.2f}")
    if out_by <= 0:
        fails.append(f"the RCA threads end {-out_by:.2f} mm inside the output cap's outer face")
    if x_out - x1 > BLOCK_D / 2:
        fails.append(f"the RCA housings stand {x_out - x1:.2f} past the board's end: the lips lose that much of it")
    if (RCA_HOLE - RCA_THREAD[1]) / 2 < CLR - 1e-9:
        fails.append(f"the RCA holes {RCA_HOLE} leave less than {CLR} round the {RCA_THREAD[1]} thread")
    usbc = m1.at(usbc_s, 0)
    rear = min(local(fps[r], 0, RCA_REAR)[0] for r in rca)
    held, open_ = sorted((min(a, b), max(a, b)) for a, b in
                         ((local(fps[r], -RCA_HALF, 0)[1], local(fps[r], RCA_HALF, 0)[1]) for r in rca)), 0.0
    reach = usbc_over[1]                                # the widest gap the housings leave in front of the USB-C
    for a, b in held:
        open_ = max(open_, min(a, usbc_over[3]) - reach)
        reach = max(reach, b)
    open_ = max(open_, usbc_over[3] - reach)
    print(f"  {m1r}'s USB-C face {rear - usbc[0]:.2f} mm behind the RCA housings' rears, the widest gap between them "
          f"in front of it {open_:.2f}: {'covered' if open_ < TANG_USB[1] else 'open'}")
    hd = hdmi_over
    for r in ref["L_Bourns-SRN8040_8x8.15mm"]:
        g = gap(hd, boxes[r])
        hz = TANG_HEADER + TANG_PCB_T - H[r]
        print(f"  {m1r}'s HDMI {g:.2f} mm clear of {r} in plan (taken {TANG_HDMI[0]} past the module, front at x "
              f"{hd[0]:.2f}); over {r}'s top it would leave {hz:.2f}")
        if g <= 0 and hz <= 0:
            fails.append(f"{m1r}'s HDMI meets {r}")

    # 6. the caps. u, v in each cap's frame: seen from outside, u from the flange's left edge, v from its
    # bottom edge; at the input end the y0 edge is on the left, at the output end the y1 edge
    def U(y, cap):
        return (y - y0 if cap == "input" else y1 - y) + side_gap + WALL

    def V(zin):
        return zin + WALL
    caps = {"input": [], "output": []}

    def rect(cap, nm, ya, yb, za, zb):
        ua, ub = sorted((U(ya, cap), U(yb, cap)))
        caps[cap].append({"name": nm, "box": (ua - CLR, V(za) - CLR, ub + CLR, V(zb) + CLR)})

    # input: J1's housing with its standoff's notch, J5, J4, M2's micro-USB, the SMA
    ya, yb = (local(j1, fx, 0)[1] for fx in J1_HOUSING)
    rect("input", f"{j1r}'s housing", ya, yb, zt + J1_LIFT, zt + H[j1r])
    sa, sb = (local(j1, fx, 0)[1] for fx in J1_STANDOFF[:2])
    ua, ub = sorted((U(sa, "input"), U(sb, "input")))
    notch = (ua - CLR, V(zt) - CLR, ub + CLR, V(zt + J1_LIFT) - CLR)
    if local(j1, 0, J1_STANDOFF[2])[0] >= x0:
        notch = None
    for r in sorted(toslink):
        fp = fps[r]
        ya, yb = (local(fp, fx, T8_FACE)[1] for fx in (-T8_HALF, T8_HALF))
        rect("input" if toslink[r][0] else "output", f"{r}'s frame", ya, yb, zt + T8_FRAME[0], zt + T8_FRAME[1])
    for r in ref["Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal"]:
        ya, yb = (local(fps[r], fx, MF_FACE)[1] for fx in MF_FX)
        rect("input", f"{r}'s face", ya, yb, zt, zt + H[r])
    uy = m2.at(-M2_HALF[0], 0)[1]
    uz = [z - M2_HEADER - M2_PCB_T - h / 2 for h in M2_USB[2:]]     # the receptacle's centre above the floor: the
    uc = (U(uy, "input"), V(min(uz)), V(max(uz)))                   # tallest body's (lowest) .. the lowest's
    caps["input"].append({"name": f"{m2r}'s micro-USB, its plug's overmould",
                          "box": (uc[0] - USB_PLUG[0] / 2 - CLR, uc[1] - USB_PLUG[1] / 2 - CLR,
                                  uc[0] + USB_PLUG[0] / 2 + CLR, uc[2] + USB_PLUG[1] / 2 + CLR)})
    for r in rca:
        caps["output"].append({"name": f"{r}'s bushing", "c": (U(mm(fps[r].GetPosition().y), "output"),
                                                               V(zt + RCA_AXIS_Z)), "d": RCA_HOLE,
                               "h": 2 * RCA_AXIS_TOL})
    # rectangles closer than MIN_WEB become one (the reader's J6 and J4)
    merged = {}
    for cap, ops in caps.items():
        again = True
        while again:
            again = False
            rs = [o for o in ops if "box" in o]
            for i in range(len(rs)):
                for k in range(i + 1, len(rs)):
                    g = gap(rs[i]["box"], rs[k]["box"])
                    if g < MIN_WEB:
                        a, b = rs[i], rs[k]
                        nb = (min(a["box"][0], b["box"][0]), min(a["box"][1], b["box"][1]),
                              max(a["box"][2], b["box"][2]), max(a["box"][3], b["box"][3]))
                        nm = a["name"] + " and " + b["name"]
                        merged[nm] = g
                        ops.remove(a)
                        ops.remove(b)
                        ops.append({"name": nm, "box": nb})
                        again = True
                        break
                if again:
                    break

    # the SMA: in the margin beyond the board's y1 edge, as far out as the wall lets its body; above or below
    # the board, where its body clears the board's slab and the parts within its reach
    r_sma = SMA_NUT_AF / math.sqrt(3)                       # across corners / 2
    su = INNER_W - r_sma - SMA_GAP - CAP_FLOAT              # in the input cap, the y1 margin is on the right
    yb_ = su - r_sma - SMA_GAP - side_gap + y0              # the board's y the body reaches over
    xa, xb = x0, x0 + SMA_BODY_IN
    ht = max([H[r] for r in fps if side[r] == "F" and H[r] > 0.05 and boxes[r][3] > yb_ and
              boxes[r][0] < xb and boxes[r][2] > xa] +
             [ld["beyond"] for ld in leads if ld["side"] == "B" and ld["p"][1] + ld["rad"] > yb_ and
              xa < ld["p"][0] < xb] + [0.0])
    hb = max([H[r] for r in fps if side[r] == "B" and H[r] > 0.05 and boxes[r][3] > yb_ and
              boxes[r][0] < xb and boxes[r][2] > xa] +
             [ld["beyond"] for ld in leads if ld["side"] == "F" and ld["p"][1] + ld["rad"] > yb_ and
              xa < ld["p"][0] < xb] + [0.0])
    lim = r_sma + SMA_GAP
    if yb_ >= y1:
        wins = [(lim, INNER_H - lim, "beside the board")]
    else:
        wins = [(zt + ht + lim, INNER_H - lim, "above the board"), (lim, z - hb - lim, "below the board")]
    wins = [w for w in wins if w[1] >= w[0]]
    sma = None
    if not wins:
        fails.append("no room for the SMA's body in the input cap's margin")
    else:
        w = max(wins, key=lambda q: q[1] - q[0])
        sv = (w[0] + w[1]) / 2
        if not in_tube(su, sv, r_sma):
            fails.append("the SMA's body leaves the tube's inside")
        sma = {"c": (su + WALL, V(sv)), "where": w[2], "win": (V(w[0]), V(w[1])), "vin": sv}
        caps["input"].append({"name": "SMA bulkhead", "c": sma["c"], "d": SMA_HOLE})
        if CAP_T > SMA_PANEL_MAX:
            fails.append(f"the input flange {CAP_T} is thicker than the SMA's panel limit {SMA_PANEL_MAX}")

    # webs: between the openings, to the flange's edges; the SMA's nut on the flange, off the openings. A round
    # opening is its centre line (a vertical segment h long; a point for a hole) and a radius
    def seg(o):
        h = o.get("h", 0.0) / 2
        return o["c"][0], o["c"][1] - h, o["c"][1] + h, o["d"] / 2

    def web(a, b):
        if "box" in a and "box" in b:
            return gap(a["box"], b["box"])
        if "box" in a or "box" in b:
            rr, cc = (a, b) if "box" in a else (b, a)
            cu, cv0, cv1, rad = seg(cc)
            bx = rr["box"]
            return math.hypot(max(bx[0] - cu, 0.0, cu - bx[2]), max(bx[1] - cv1, 0.0, cv0 - bx[3])) - rad
        au, a0, a1, ra = seg(a)
        bu, b0, b1, rb = seg(b)
        return math.hypot(au - bu, max(b0 - a1, 0.0, a0 - b1)) - ra - rb

    def edge(o):
        if "box" in o:
            b = o["box"]
        else:
            cu, cv0, cv1, rad = seg(o)
            b = (cu - rad, cv0 - rad, cu + rad, cv1 + rad)
        return min(b[0], b[1], TUBE_W - b[2], TUBE_H - b[3])
    thin = {}
    for cap, ops in caps.items():
        worst = (math.inf, "")
        for i, a in enumerate(ops):
            e = edge(a)
            if e < MIN_WEB:
                fails.append(f"{cap} cap: {a['name']} leaves {e:.2f} to the flange's edge, {MIN_WEB} wanted")
            worst = min(worst, (e, f"{a['name']} to the edge"))
            for b in ops[i + 1:]:
                g = web(a, b)
                if g < MIN_WEB:
                    fails.append(f"{cap} cap: {g:.2f} between {a['name']} and {b['name']}, {MIN_WEB} wanted")
                worst = min(worst, (g, f"{a['name']} - {b['name']}"))
        thin[cap] = worst
    if notch:                                           # the notch hangs under J1's housing opening
        for o in caps["input"]:
            if not o["name"].startswith(f"{j1r}'s") and web({"box": notch}, o) < MIN_WEB:
                fails.append(f"input cap: {web({'box': notch}, o):.2f} between {j1r}'s notch and {o['name']}")
        if edge({"box": notch}) < MIN_WEB:
            fails.append(f"input cap: {j1r}'s notch leaves {edge({'box': notch}):.2f} to the flange's edge")
    if sma:
        nut = {"c": sma["c"], "d": 2 * r_sma}
        others = [o for o in caps["input"] if o["name"] != "SMA bulkhead"]
        g = min(web(nut, o) for o in others)
        if g < 0 or edge(nut) < 0:
            fails.append(f"the SMA's nut ({2 * r_sma:.2f} across corners) overlaps an opening or the flange's edge")
        sma["nut_gap"], sma["nut_edge"] = g, edge(nut)

    print(f"cut-outs, each its part + {CLR} a side (mm; each cap seen from outside: u from the flange's left edge, "
          f"v from its bottom edge):")
    print(f"  both caps: the board's end on the flange u {WALL + side_gap:.2f}..{WALL + side_gap + W:.2f}, "
          f"v {V(z):.2f}..{V(zt):.2f}")
    for cap, ops in caps.items():
        for o in ops:
            if "box" in o:
                b = o["box"]
                extra = f" ({merged[o['name']]:.2f} apart: one opening)" if o["name"] in merged else ""
                print(f"  {cap} cap: {o['name']}{extra} u {b[0]:.2f}..{b[2]:.2f}, v {b[1]:.2f}..{b[3]:.2f}")
                if cap == "input" and o["name"].startswith(f"{j1r}'s") and notch:
                    print(f"  {cap} cap: {j1r}'s standoff notch below it u {notch[0]:.2f}..{notch[2]:.2f}, "
                          f"v {notch[1]:.2f}..{notch[3]:.2f}")
                if o["name"].startswith(f"{m2r}'s micro-USB"):
                    print(f"    (the receptacle's centre u {uc[0]:.2f}, v {uc[1]:.2f}..{uc[2]:.2f}; the overmould "
                          f"{USB_PLUG[0]} x {USB_PLUG[1]})")
            elif o["name"] == "SMA bulkhead":
                print(f"  {cap} cap: SMA bulkhead hole {SMA_HOLE:.2f} round, centre u {o['c'][0]:.2f}, "
                      f"v {o['c'][1]:.2f}")
            elif o.get("h"):
                print(f"  {cap} cap: {o['name']} slot {o['d']:.2f} x {o['d'] + o['h']:.2f}, centre u {o['c'][0]:.2f}, "
                      f"v {o['c'][1]:.2f}")
            else:
                print(f"  {cap} cap: {o['name']} hole {o['d']:.2f}, centre u {o['c'][0]:.2f}, v {o['c'][1]:.2f}")
        print(f"  {cap} cap: the thinnest web {thin[cap][0]:.2f} ({thin[cap][1]})")

    # the blocks' windows: the side margins, a slot for the board's edge, lips over its faces as far as the
    # parts and leads within BLOCK_D of the end allow
    def lip(xa, xb, ey, face):
        best = (math.inf, "nothing")
        dist = (lambda lo_, hi_: lo_ - y0) if ey == y0 else (lambda lo_, hi_: y1 - hi_)
        for r in fps:
            if side[r] != face or H[r] <= 0.05:
                continue
            for b in rects[r]:
                if b[0] < xb and b[2] > xa:
                    best = min(best, (dist(b[1], b[3]) - LIP_GAP, r))
        for ld in leads:
            if ld["side"] == face or ld["beyond"] <= 0:
                continue
            keep = LEAD_KEEP if ld["soldered"] else ld["rad"] + LIP_GAP
            cx, cy = ld["p"]
            if cx + keep > xa and cx - keep < xb:
                best = min(best, (dist(cy, cy) - keep, f"{ld['ref']} pad {ld['pad']} at ({cx:.2f}, {cy:.2f})"))
        return max(best[0], 0.0), best[1]
    print(f"block windows (the tube's inside in the side margins, corners R {CORNER_R}; w from the outer face):")
    for cap, (xa, xb) in (("input", (x0, x0 + BLOCK_D)), ("output", (x1 - BLOCK_D, x1))):
        for hand, ey in (("left", y0 if cap == "input" else y1), ("right", y1 if cap == "input" else y0)):
            ua, ub = (WALL, WALL + side_gap) if hand == "left" else (WALL + side_gap + W, WALL + INNER_W)
            vtop = V(INNER_H)
            if sma and cap == "input" and ey == y1 and BLOCK_D > 0:
                vtop = min(vtop, sma["c"][1] - r_sma - SMA_GAP)
            lt, wt = lip(xa, xb, ey, "F")
            lb, wb = lip(xa, xb, ey, "B")
            print(f"  {cap} cap, {hand} (y {ey:.0f} edge): u {ua:.2f}..{ub:.2f}, v {V(0):.2f}..{vtop:.2f}, "
                  f"w {CAP_T:.2f}..{CAP_T + BLOCK_D:.2f}{' (under the SMA body)' if vtop < V(INNER_H) else ''}; "
                  f"the board's edge v {V(z):.2f}..{V(zt):.2f}; a lip over it "
                  f"{'free' if math.isinf(lt) else f'{lt:.2f}'} on top ({wt}), "
                  f"{'free' if math.isinf(lb) else f'{lb:.2f}'} underneath ({wb})")

    # the SMA and its pigtail
    if sma:
        j4r = ref["Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal"][0]
        print(f"SMA (input cap, {sma['where']} in the margin on {j4r}'s side): centre u {sma['c'][0]:.2f}, "
              f"v {sma['c'][1]:.2f} (the centre may go v {sma['win'][0]:.2f}.."
              f"{sma['win'][1]:.2f}); nut {SMA_NUT_AF} AF, {2 * r_sma:.2f} across corners, {sma['nut_gap']:.2f} off "
              f"the next opening, {sma['nut_edge']:.2f} off the flange's edge; flange {CAP_T} of {SMA_PANEL_MAX} max")
        print(f"  its body inside to w {CAP_T + SMA_BODY_IN:.2f}: {INNER_W - su - r_sma:.2f} off the wall "
              f"({INNER_W - su - r_sma - CAP_FLOAT:.2f} with its cap shifted against it), "
              f"{sma['vin'] - r_sma - zt - ht:.2f} over the parts by the board's edge ({ht:.2f} tall)")
        sy = su - side_gap + y0
        ufl_v = z - M2_HEADER - M2_PCB_T - (M2_WROVER[3] + 0.8) / 2   # the plug's middle, on the module's face
        dxs = (ufl[0] - x0, ufl[2] - x0)        # from the panel: the jack's body, unknown, is taken as cable
        dys = (sy - ufl[3], sy - ufl[1])
        dv = sma["vin"] - ufl_v
        path = (dxs[0] + dys[0] + dv, dxs[1] + dys[1] + dv)
        stock = next((s for s in PIGTAIL_STOCK if s >= path[1] * PIGTAIL_SLACK), None)
        floor = z - M2_HEADER - M2_PCB_T - M2_WROVER[3]
        print(f"  pigtail: from the SMA down the margin past the blocks, on the floor under the WROVER-IE's end "
              f"({floor:.2f} high there, the cable {PIGTAIL_D}) to the U.FL in x {ufl[0]:.2f}..{ufl[2]:.2f}, "
              f"y {ufl[1]:.2f}..{ufl[3]:.2f}: {path[0]:.0f}..{path[1]:.0f} mm, so a {stock} mm pigtail")
        if floor < PIGTAIL_D:
            fails.append(f"the pigtail's cable ({PIGTAIL_D}) does not pass under the WROVER-IE ({floor:.2f})")
        if stock is None:
            fails.append(f"no stock pigtail reaches {path[1] * PIGTAIL_SLACK:.0f} mm")
        notes.append(f"the pigtail's U.FL is clipped onto {m2r} before the board goes into the tube; from then the "
                     f"board must never rest on {m2r} (on its EN/BOOT end it lies {z - bot[0]:.2f} lower, and the "
                     f"cable has {floor - PIGTAIL_D:.2f} under the WROVER-IE's end even with the caps on)")

    # the assembly, as the model takes it
    notes.append(f"{m2r} hangs component side down, the headers' long side through this board "
                 f"({LEADS[DEVKIT][0]['pin'] - PCB_T:.1f} "
                 f"up on top) and the short side through the DevKitC: the other way round its tails add 1.4 under it")
    for r, (left, kinds, why) in sorted(CUT.items()):
        if r in fps and not any(k[0] == r for k in under):
            notes.append(f"{r}: {why} ({left} left)")
    if open_ < TANG_USB[1]:
        notes.append(f"{m1r}'s USB-C is covered by the RCA housings: the FPGA is flashed before {m1r} is soldered in")
    pitch = min(abs(mm(fps[a].GetPosition().y) - mm(fps[b].GetPosition().y)) for a, b in zip(rca, rca[1:]))
    if pitch < RCA_NUT:
        notes.append(f"the RCA jacks go without nuts: the TDS's nut is {RCA_NUT} across flats, the jacks {pitch:.2f} "
                     f"apart")
    hdr = sorted(ref.get("PinHeader_1x08_P2.54mm_Vertical", []) + ref.get("PinHeader_1x06_P2.54mm_Vertical", []))
    if hdr and DUPONT_H > INNER_H - zt:
        notes.append(f"{' and '.join(hdr)} take no cable in the tube: a 2.54 crimp housing stands {DUPONT_H} above the "
                     f"board, the tube leaves {INNER_H - zt:.2f}")
    notes.append(f"the tube's ground: an M2 ring terminal under the input cap's screw, a short wire to "
                 f"{ref['Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal'][0]}'s GND by its plug")
    notes.append(f"the WROVER-IE's U.FL spot is unverified (fig. 13's 23.05 and 2.25): the path takes the module's "
                 f"last {UFL_BACK} mm")

    for n in notes:
        print("  note:", n)
    for f in fails:
        print("  FAIL:", f)
    print("PASS" if not fails else f"FAIL ({len(fails)})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
