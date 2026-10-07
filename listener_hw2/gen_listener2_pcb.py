#!/usr/bin/env python3
"""gen_listener2_pcb.py - listener v2.0's board, placed once by this script from the v2.0 sheet.

Run with KiCad's own Python (it carries the pcbnew module):
  "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" listener_hw2\\gen_listener2_pcb.py [--fresh]
It lays the parts out only, with listener_hw/gen_listener_pcb.py's helpers (the netlist from
kicad-cli, the net classes, the pours, the file's canonical order): from then on
most_listener_v2.kicad_pcb belongs to the PCB editor, and the script refuses to overwrite it unless
run with --fresh, which lays the parts out again and loses every track.

The board (the user's decisions of 2026-10-07): 98 x 60 mm, four layers, the inputs at one end and
the outputs at the other, M1 on top and M2 underneath. x runs from the inputs' end (0) to the
outputs' end (98), y across the board; KiCad's y points down.
  inputs   J1 (the ring's FOT) with its housing 3.6 mm past the edge; J5 (TOSLINK in) and J4 (power)
           between M2's pin rows (25.4 apart; the two take 21.2), J1 outside them: no module pin
           comes up under a connector's body. M2's USB on this end, under the board.
  middle   M1 on top and M2 underneath on one axis (y = AX): M1's rows 20.32 apart, M2's 25.4, so
           2.54 mm between them. M1's HDMI towards the inputs, its USB-C (flashing only) towards
           the outputs, inside the case.
  outputs  J6 (TOSLINK out), J7 (coax), J9 (line R), J8 (line L), their faces on the edge.
  J2, J3   along the long edge beside M1, their series resistors between them and M1's pins.
The other parts go by the sheet's blocks into the zones of the concept drawing (ZONES): each zone
is filled from its top-left corner, the biggest part first, clear of every through-hole pad and of
the parts already placed; what does not fit waits beside the board. A first placement for the user
to arrange in KiCad, not a final one.
Rotation is KiCad's (degrees counterclockwise on screen). A bottom part is placed as a top part with
the rotation given and then turned over top to bottom (FLIP_DIRECTION_TOP_BOTTOM), which keeps what
faces +x facing +x and mirrors y.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROJECT = "most_listener_v2"

spec = importlib.util.spec_from_file_location("gen_listener_pcb", ROOT / "listener_hw" / "gen_listener_pcb.py")
v1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v1)
v1.HERE, v1.PROJECT = HERE, PROJECT          # its helpers then read this folder and name this project

L, W = 98.0, 60.0
AX = 41.0               # the modules' axis: J1's pads (to y 26.45) clear M2's first row (28.3)
mm, pt = v1.mm, v1.pt
IO = pcbnew.PCB_IO_KICAD_SEXPR()         # one loader for every footprint (FootprintLoad alone fails in KiCad 10)

# ref: (x, y, rotation, side)
FIXED = {
    "J1": (11.8, 12.4, 90, "T"),          # the housing's front 3.6 mm past x 0, its pads y 0.35..26.45
    "J5": (10.65, 35.45, 270, "T"),       # ORJ-8: its face 0.35 past x 0, so its rear clears L2 and D1
    "J4": (9.52, 48.3, 90, "T"),          # as on v1.6: the face on the edge; its courtyard after J5's
    "M1": (53.52, AX, 270, "T"),          # x 26.5..80.54; HDMI to 22.5, USB-C to 82.54
    "M2": (25.43, AX, 270, "B"),          # its USB on x 0 under the board; rows x 2.57..48.29
    "J6": (87.0, 6.35, 90, "T"),          # ORJ-8: its face on x 98, 11.00 in front of the pins
    "J7": (85.2, 20.05, 90, "T"),
    "J9": (85.2, 35.35, 90, "T"),
    "J8": (85.2, 50.65, 90, "T"),
    "J2": (54.0, 56.5, 90, "T"),
    "J3": (34.0, 56.5, 90, "T"),
}
# the other parts by the sheet's blocks: (side, x0, y0, x1, y1, refs)
ZONES = [
    # top
    ("T", 22.5, 0.5, 55.0, 27.0, "power: the buck and the bulk", "C44 C45 L2 L1 U6 C1 C2 C4 C6 C7 C43 C47 C80 C82 R4 R5 R31"),
    ("T", 12.8, 29.4, 26.3, 52.6, "the input's protection, test points", "F1 D1 D2 C83 TP6 TP7 TP9"),
    ("T", 55.0, 0.5, 82.6, 29.4, "the regeneration clock and the FPGA's supply",
     "U7 U8 C13 C14 C15 R10 R11 R12 R14 R15 R17 D3 C64 C65 C66 C67 C68"),
    ("T", 49.5, 52.4, 82.6, 55.3, "J2's and J3's series resistors", "R18 R19 R34 R35 R36 R37 R38 R39 R40 R41"),
    # bottom
    ("B", 0.5, 0.5, 22.0, 26.9, "the ring, the wake and the bypass guard, 3V3_AON",
     "U1 U2 U4 U11 U5 C3 C46 C8 C9 C10 C11 C17 C18 C19 C20 C25 C26 FB1 FB2 R1 R2 R3 R6 R7 R8 R9 R23 R42"),
    ("B", 22.0, 0.5, 55.8, 26.9, "the TOSLINK input, the FPGA's ring buffers, 5V_HOST",
     "U13 U12 X1 U14 FB3 C63 U3 U9 C12 C16 R16 U10 C23 C24 R22 C27 C28 C30 C33 C34 C35 C36 C37 C38 C39 C40 C48 C49 "
     "R24 R25 R29 R30"),
    ("B", 3.0, 29.6, 47.0, 52.4, "under M2: the host's series resistors (low parts only)", "R20 R21"),
    ("B", 55.8, 0.5, 82.8, 59.5, "the S/PDIF output, the DAC and the line out",
     "C78 C81 U15 U17 U16 U18 R26 R27 R28 C29 C31 C32 D4 C50 C51 C52 C53 C54 C55 C56 C57 C58 C59 C60 C61 C62 "
     "C69 C70 C71 C72 C73 C74 C75 C76 C77 C79 D5 D6 R32 R33 R43 R44 R45 R46"),
]
GAPS = (2.0, 1.5, 1.0, 0.6, 0.3)   # between courtyards: the widest at which a zone takes all its parts
PAD_KEEP = 0.4          # round every through-hole pad
EDGE = 0.5
# parts whose reference stays where the footprint puts it
BIG = {"M1", "M2", "J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9", "U12", "U13", "C44", "C45", "L1", "L2", "U6"}
# JLCPCB's standard 4-layer stack (JLC04161H-7628), 1.6 mm, ENIG
STACKUP = (("F.SilkS", '(type "Top Silk Screen")', '(color "White")'),
           ("F.Paste", '(type "Top Solder Paste")'),
           ("F.Mask", '(type "Top Solder Mask")', '(color "Green")', "(thickness 0.01)"),
           ("F.Cu", '(type "copper")', "(thickness 0.035)"),
           ("dielectric 1", '(type "prepreg")', "(thickness 0.2104)", '(material "7628")', "(epsilon_r 4.4)",
            "(loss_tangent 0.02)"),
           ("In1.Cu", '(type "copper")', "(thickness 0.0152)"),
           ("dielectric 2", '(type "core")', "(thickness 1.065)", '(material "FR4")', "(epsilon_r 4.6)",
            "(loss_tangent 0.02)"),
           ("In2.Cu", '(type "copper")', "(thickness 0.0152)"),
           ("dielectric 3", '(type "prepreg")', "(thickness 0.2104)", '(material "7628")', "(epsilon_r 4.4)",
            "(loss_tangent 0.02)"),
           ("B.Cu", '(type "copper")', "(thickness 0.035)"),
           ("B.Mask", '(type "Bottom Solder Mask")', '(color "Green")', "(thickness 0.01)"),
           ("B.Paste", '(type "Bottom Solder Paste")'),
           ("B.SilkS", '(type "Bottom Silk Screen")'))


def load_footprint(fpid):
    lib, name = fpid.split(":")
    path = HERE / f"{v1.LIB}.pretty" if lib == v1.LIB else v1.KICAD_FP / f"{lib}.pretty"
    fp = IO.FootprintLoad(str(path), name)
    if fp is None:
        raise SystemExit(f"footprint {fpid} not found in {path}")
    return fp


def box(fp):
    """The courtyard (or the outline) of a placed footprint, mm."""
    if hasattr(fp, "BuildCourtyardCaches"):
        fp.BuildCourtyardCaches()
    bb = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd).BBox()
    if not bb.GetWidth():
        bb = fp.GetBoundingBox(False)
    return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))


def hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def texts(fp):
    """References in JLCPCB's minimum (1.0 mm text, 0.15 mm stroke) above each small part."""
    if fp.GetReference() in BIG:
        return
    x0, y0, x1, y1 = box(fp)
    r = fp.Reference()
    r.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
    r.SetTextThickness(mm(0.15))
    r.SetTextAngleDegrees(0)
    r.SetPosition(pt((x0 + x1) / 2, y0 - 0.6))


def stackup(path):
    t3, t4 = "\t" * 3, "\t" * 4
    layers = "".join(f'{t3}(layer "{name}"\n' + "".join(f"{t4}{a}\n" for a in attrs) + f"{t3})\n"
                     for name, *attrs in STACKUP)
    block = f'\t\t(stackup\n{layers}{t3}(copper_finish "ENIG")\n{t3}(dielectric_constraints no)\n\t\t)\n'
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("\n\t(setup\n", "\n\t(setup\n" + block, 1), encoding="utf-8", newline="\n")


def fit(fp, side, zone, blocked, gap):
    """Put fp at the first free spot of zone from its top left (0 then 90 degrees), clear of
    blocked by gap; add it to blocked. False if it fits nowhere."""
    zx0, zy0, zx1, zy1 = zone
    for rot in (0, 90):
        fp.SetOrientationDegrees(rot)
        bx0, by0, bx1, by1 = box(fp)
        px, py = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
        w, h = bx1 - bx0, by1 - by0
        y = zy0
        while y + h <= zy1 + 1e-6:
            x = zx0
            while x + w <= zx1 + 1e-6:
                cand = (x - gap / 2, y - gap / 2, x + w + gap / 2, y + h + gap / 2)
                c = next((b for b in blocked if hit(cand, b)), None)
                if c is None:
                    fp.SetPosition(pt(px + x - bx0, py + y - by0))
                    blocked.append(box(fp))
                    return True
                x = max(x + 0.25, c[2] + 1e-3)
            y += 0.5
    return False


def build():
    comps, nets = v1.netlist()
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    tb = board.GetTitleBlock()
    tb.SetTitle("MOST25 to AUDIO: listener board v2.0"); tb.SetDate("2026-10-07"); tb.SetRevision("2.0")
    tb.SetComment(0, "Generated layout: listener_hw2/gen_listener2_pcb.py, the first placement")
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.15)
    ds.m_ViasMinSize = mm(0.5)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_MinClearance = mm(0.127)
    ds.m_CopperEdgeClearance = mm(0.3)
    ds.m_MinSilkTextHeight = mm(1.0)
    ds.m_MinSilkTextThickness = mm(0.15)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(mm(0.15)); nc.SetTrackWidth(mm(0.25)); nc.SetViaDiameter(mm(0.6)); nc.SetViaDrill(mm(0.3))
    for name, width, via, drill in (("Power", 0.6, 0.8, 0.4), ("Rail", 0.35, 0.6, 0.3)):
        cls = pcbnew.NETCLASS(name)
        cls.SetClearance(mm(0.15)); cls.SetTrackWidth(mm(width)); cls.SetViaDiameter(mm(via)); cls.SetViaDrill(mm(drill))
        ds.m_NetSettings.SetNetclass(name, cls)
    for cls, names in (("Power", v1.POWER), ("Rail", v1.RAIL)):
        for name in sorted(names):
            if name not in nets:
                raise SystemExit(f"{cls} names a net that does not exist: {name}")
            ds.m_NetSettings.SetNetclassPatternAssignment(name, cls)

    netinfo = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni
    pad_net = {(ref, pin): name for name, nodes in nets.items() for ref, pin in nodes}
    zoned = {r: z for z in ZONES for r in z[6].split()}
    known = set(FIXED) | set(zoned)
    missing, extra = sorted(set(comps) - known), sorted(known - set(comps))
    dup = [r for r in zoned if r in FIXED]
    if missing or extra or dup:
        raise SystemExit(f"placement: no place for {missing}, unknown {extra}, both fixed and zoned {dup}")

    def make(ref):
        value, fpid, path = comps[ref]
        fp = load_footprint(fpid)
        lib, name = fpid.split(":")
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetPath(pcbnew.KIID_PATH(path))
        fp.SetReference(ref)
        fp.SetValue(value)
        for pad in fp.Pads():
            n = pad_net.get((ref, pad.GetNumber()))
            if n:
                pad.SetNet(netinfo[n])
            if ref == "U6" and pad.GetNumber() == "9":      # the buck's pad and its vias: solid into the pour
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        return fp

    def put(fp, x, y, rot, side):
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(pt(x, y))
        if side == "B" and not fp.IsFlipped():
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)

    placed = {}
    for ref, (x, y, rot, side) in FIXED.items():
        fp = make(ref)
        board.Add(fp)
        put(fp, x, y, rot, side)
        placed[ref] = fp
    # what the zones must keep clear of, per side: every through-hole pad (they reach both
    # sides), the fixed parts' bodies on that side, M1's body on top (its own parts are under
    # it) and M2's underneath except in the zone that is meant for under it
    pads = []
    for fp in placed.values():
        for pad in fp.Pads():
            if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                bb = pad.GetBoundingBox()
                pads.append((pcbnew.ToMM(bb.GetLeft()) - PAD_KEEP, pcbnew.ToMM(bb.GetTop()) - PAD_KEEP,
                             pcbnew.ToMM(bb.GetRight()) + PAD_KEEP, pcbnew.ToMM(bb.GetBottom()) + PAD_KEEP))
    bodies = {"T": [], "B": []}
    for ref, fp in placed.items():
        if ref not in ("M1", "M2"):            # the modules: their pads above, their bodies below
            bodies["B" if fp.IsFlipped() else "T"].append(box(fp))
    m1 = (26.5, AX - 11.275, 80.54, AX + 11.275)
    m2 = (1.3, AX - 13.97, 55.6, AX + 13.97)
    bodies["T"].append(m1)

    parked = []
    for side, zx0, zy0, zx1, zy1, what, refs in ZONES:
        under_m2 = "under M2" in what
        blocked = pads + bodies[side] + ([] if under_m2 or side == "T" else [m2])
        fps = []
        for ref in refs.split():
            fp = make(ref)
            board.Add(fp)
            fps.append((ref, fp))
        # the biggest first; each tries 0 and 90 degrees, the first free spot from the top left
        def area(item):
            x0, y0, x1, y1 = box(item[1])
            return -(x1 - x0) * (y1 - y0)
        for ref, fp in fps:
            put(fp, 0, 0, 0, side)
        fps.sort(key=area)
        for gap in GAPS:
            here, left = list(blocked), []
            for ref, fp in fps:
                if not fit(fp, side, (zx0, zy0, zx1, zy1), here, gap):
                    left.append(ref)
            if not left or gap == GAPS[-1]:
                break
        for ref, fp in fps:
            if ref in left:
                parked.append(ref)
                i = len(parked) - 1
                put(fp, L + 8.0 + 7.0 * (i % 6), 4.0 + 7.0 * (i // 6), 0, side)
            else:
                # its through-hole pads (U6's thermal vias) reach the other side too
                for pad in fp.Pads():
                    if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                        bb = pad.GetBoundingBox()
                        pads.append((pcbnew.ToMM(bb.GetLeft()) - PAD_KEEP, pcbnew.ToMM(bb.GetTop()) - PAD_KEEP,
                                     pcbnew.ToMM(bb.GetRight()) + PAD_KEEP, pcbnew.ToMM(bb.GetBottom()) + PAD_KEEP))
    for fp in board.GetFootprints():
        texts(fp)
    for (x1, y1), (x2, y2) in (((0, 0), (L, 0)), ((L, 0), (L, W)), ((L, W), (0, W)), ((0, W), (0, 0))):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(x1, y1)); s.SetEnd(pt(x2, y2))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        board.Add(s)
    for layer in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        v1.zone(board, layer, netinfo["GND"], (EDGE, EDGE, L - EDGE, W - EDGE))
    return board, comps, nets, parked


def main():
    out = HERE / f"{PROJECT}.kicad_pcb"
    if out.exists() and "--fresh" not in sys.argv:
        print(f"{out.name} exists and belongs to the PCB editor; --fresh lays the parts out again and loses every track")
        return
    board, comps, nets, parked = build()
    board.SetFileName(str(out))
    (HERE / f"{PROJECT}.kicad_dru").write_text(v1.RULES, encoding="utf-8", newline="\n")
    pcbnew.SaveBoard(str(out), board)
    v1.canonical(out)
    stackup(out)
    print(f"wrote {out}: {len(comps)} parts, {len(nets)} nets, {L:.0f} x {W:.0f} mm, 4 layers, no tracks")
    if parked:
        print("beside the board, no room in their zone:", " ".join(parked))


if __name__ == "__main__":
    main()
