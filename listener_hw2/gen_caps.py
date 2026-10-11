#!/usr/bin/env python3
"""gen_caps.py - the two end caps of listener v2.0's tube, from check_fit.py's model of the board in it.

The tube is an aluminium rectangular tube 80 x 30 x 2, as long as the board (check_fit: cut to the soldered
board's length between the flanges' bearing faces +0.1/-0); the board is centred across it (8.0 mm a side) at
check_fit's height (the user's decisions of 2026-10-11). Each cap is the reader's (reader_hw2/gen_caps.py): a
flange of the tube's outline, 2.0 mm thick, that sits on the tube's end face, with blocks reaching into the
tube, GAP_TUBE off its inside all round (any tube in tolerance takes them; the saddle sets the height), and a
saddle under the tube with an ear either side:
  * a side block in each side margin of each cap holds the board: its post stands from the floor up
    beside the board's edge and holds it across, BOARD_PLAY off it; a lip under the edge carries the board
    at check_fit's height, a lip over it holds it down, with a slot SLOT_PLAY taller than the board between
    them, and a LEAD_IN x 45 degree lead-in at each lip's tip. A lip runs the block's whole depth where the
    parts and leads let it, and is cut short to a ledge where they do not: at the input end's y = 0 corner
    J1's action pin stands 1.55 mm from the board's edge, so that corner sits between two ledges;
  * the input cap (x = 0): J1's housing with its standoff's notch, J5 and J4 (one opening: the web
    between two would be 1.17), M2's micro-USB with room for its plug's overmould, and the Bluetooth
    antenna's SMA bulkhead (a round hole: no pigtail is chosen, its jack's thread may have flats or none),
    above the board in the side margin on J4's side, go through it. The side block under the SMA stops
    below its body and takes no screw; a third block, over the board between J4 and the SMA, takes the
    input cap's second screw and the ground bond (an M2 ring terminal, a short wire to J4's GND by its plug);
  * the output cap (x = 98): J6's port and the threaded bushings of the RCA jacks J7..J9 go through it, the
    bushings through vertical slots (their axis height is not dimensioned by BKL).
The board's ends butt against the flanges. The caps are held by DIN 7981 ST2.2 self-tapping screws drilled
at assembly through the tube's top into the blocks that reach it (not through its sides: a screw head there
stands in the way of a screwdriver on the ear below). Under the tube each flange runs on into a saddle with an
ear either side (teardrop holes for ST4.2 or M4 into the car, a washer under the head); the caps print outer
face down without supports, solid.

Written into caps/: a STEP and an STL of each cap (in the print's frame: the outer face on the bed, the
blocks up), a drawing (caps.svg, and caps_en.svg in English) and a README. The script fails, writing
nothing, when a wall is thinner than MIN_WEB, an opening comes closer than its clearance to its part, or a
block meets a part, a lead, the board, the SMA's body or the tube. The cut-outs, the board's height and the
SMA come from check_fit.py (it must pass); the parts and the leads the blocks must miss from the board.

    "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" listener_hw2/gen_caps.py
"""
from __future__ import annotations

import contextlib
import io
import math
import re
import struct
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_fit  # noqa: E402

OUT = HERE / "caps"
TUBE_W, TUBE_H, WALL = check_fit.TUBE_W, check_fit.TUBE_H, check_fit.WALL     # 80 x 30 x 2 (the user, 2026-10-11)
CORNER_R = check_fit.CORNER_R   # the tube's inside corners, at most
CAP_T = check_fit.CAP_T         # the flange; the board's ends butt against it
CLR, MIN_WEB = check_fit.CLR, check_fit.MIN_WEB     # an opening round its part, a side; the thinnest wall a 0.4 mm
                                                    # FDM nozzle prints solidly (three lines)
BLOCK_D = check_fit.BLOCK_D     # the blocks' depth into the tube (check_fit's lip windows hold over it)
LIP_GAP = check_fit.LIP_GAP     # a block off a part's courtyard in plan
LEAD_KEEP = check_fit.LEAD_KEEP     # a block off a soldered lead's centre on its solder side (the fillet; the reader's)
R_OUT = 0.5             # the flange's outer corners (the reader's)
R_HOLE = CLR            # an opening's corners: a larger radius would bring a part's corner nearer than CLR
EPS = 0.01              # check_fit prints its cut-outs to 0.01 mm
SAG = 0.008             # a round edge's facets lie inside it by at most this
GAP_TUBE = check_fit.CAP_FLOAT  # a block off the tube's inside walls, floor and top (check_fit: any tube in tolerance)
BOARD_PLAY = 0.3        # a post's face off the board's edge: JLCPCB's outline +/-0.2, FDM's outer faces 0.1 large
SLOT_PLAY = 0.4         # the slot over the board's 1.6: JLCPCB makes it 1.6 +/-10 % (to 1.76), FDM a gap 0.1..0.2 narrow
LEAD_IN = 0.5           # each lip's tip chamfered 45 degrees this much toward the slot (it rises with the print: no
                        # overhang): the board's end finds the slot from this far off
LIP_MAX = 2.0           # a lip over or under the board's edge reaches in this far at most
LIP_MIN = 0.5           # and this far at least, or it is not made
LEDGE_MIN = 1.0         # a lip cut short (a ledge) this deep at least
PEG_CLR = 0.4           # a block off a peg (an unsoldered pin), a side (the reader's slot round J1's peg)
TOP_GAP = 0.5           # a block over a part or a lead's tip (the reader's far block over the USB-C)
OPEN_GAP = 0.05         # a block's foot off an opening in the flange (the reader's)
GROUND_OPEN_GAP = 0.5   # the ground block's foot off J4's opening
SCREW = "ST2.2×9.5"     # DIN 7981 C ST2.2 x 9.5 (its lengths: 4.5, 6.5, 9.5, 13): one for all four, the ground's too,
SCREW_L = 9.5           # which loses about 1.1 under its head to the ring terminal and the serrated washer
PILOT = 1.6             # drilled into the block at assembly: the ST2.2's core 1.52..1.63
TUBE_HOLE = 2.4         # in the tube: ISO 273 medium for 2 mm, so the ST2.2 (2.24 at most) does not tap the wall
GROUND_STACK = 1.1      # an M2 ring terminal (about 0.8) and a serrated washer (about 0.3) under the ground screw's head
SADDLE_T = 3.0          # the saddle under the tube: its thickness (the reader's)
SADDLE_L = 9.0          # how far it runs along the tube from the tube's end (the reader's)
EAR = 10.0              # each ear past the tube's side (the reader's)
EAR_HOLE = 4.6          # DIN 7981 ST4.2 (4.22 at most) or M4 into the car: ISO 273 medium 4.5 + 0.1 for the print; a
                        # teardrop, its top flat, as the hole lies horizontal in the print
EAR_WASHER = 9.0        # DIN 125 M4 under the head (PETG under a bare 8 mm head creeps): it must clear the tube's side
PETG = 1.27             # g/cm3, for the caps' weight
SMA_THREAD = check_fit.SMA_THREAD   # the bulkhead's 1/4-36 UNS-2A thread across its crests (0.250 in)
R_SMA = check_fit.SMA_NUT_AF / math.sqrt(3)     # the SMA's 8.0 AF hex body and nut, across corners / 2
STEP_DATE = "2026-10-11T00:00:00"


def R4(x):
    return round(x, 4)


def V(zin):
    """A height above the tube's inside floor as v in a cap's frame (from the flange's bottom edge)."""
    return zin + WALL


VB = R4(WALL + GAP_TUBE)                # a block's foot over the floor
VT = R4(TUBE_H - WALL - GAP_TUBE)       # a block's top under the tube's top


# ---- the model --------------------------------------------------------------------------------

def model():
    """check_fit's numbers (it must pass), and the board's parts and leads the blocks must miss."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = check_fit.main()
    text = buf.getvalue()
    if rc:
        sys.exit("check_fit.py fails:\n" + text)

    def f(pat):
        hit = re.search(pat, text, re.M)
        if not hit:
            sys.exit(f"gen_caps.py: check_fit.py prints no line for {pat}")
        return [float(v) for v in hit.groups()]
    m = {}
    m["L"], m["W"], iw, ih, m["side"] = f(r"board ([\d.]+) x ([\d.]+) mm in a tube ([\d.]+) x ([\d.]+) inside: "
                                          r"([\d.]+) mm a side")
    if abs(iw - (TUBE_W - 2 * WALL)) > EPS or abs(ih - (TUBE_H - 2 * WALL)) > EPS:
        sys.exit("gen_caps.py: check_fit's tube is not this script's")
    m["z"], = f(r"Z_BOARD ([\d.]+)")
    m["zt"] = m["z"] + check_fit.PCB_T
    m["drop"], = f(r"Z_BOARD [\d.]+: ([\d.]+) mm under ")      # the board's end lies this much lower on M2
    m["tube_L"], m["proud"] = f(r"the tube: ([\d.]+) \+[\d.]+/-0 long, .*\(([\d.]+) past it\)")     # the RCA fronts
    # what stands through the flanges (check_fit's end checks, the board slid either way; for the README)
    m["j1_out"] = f(r"housing ([\d.]+)\.\.([\d.]+) mm out of the cap")
    m["faces"] = [(h.group(1), float(h.group(2)), float(h.group(3)), float(h.group(4))) for h in
                  re.finditer(r"^  (\w+)'s face ([\d.]+)\.\.([\d.]+) mm inside the (?:input|output) cap's outer face "
                              r"\(limit ([\d.]+)\)$", text, re.M)]
    m["usb_rec"] = f(r"micro-USB face ([\d.]+)\.\.([\d.]+) mm behind the flange's inner face.*\(limit ([\d.]+)\)")
    m["rca_out"], = f(r"threads ([\d.]+) mm out of the cap")
    m["band"] = f(r"both caps: the board's end on the flange u ([\d.]+)\.\.([\d.]+), v ([\d.]+)\.\.([\d.]+)")
    m["rects"] = {"input": [], "output": []}
    for hit in re.finditer(r"^  (input|output) cap: (.+?) u ([\d.]+)\.\.([\d.]+), v ([\d.]+)\.\.([\d.]+)$", text, re.M):
        nm = hit.group(2)
        apart = re.search(r" \(([\d.]+) apart: one opening\)$", nm)
        m["rects"][hit.group(1)].append({"name": nm[:apart.start()] if apart else nm,
                                         "apart": float(apart.group(1)) if apart else None,
                                         "box": tuple(float(hit.group(k)) for k in (3, 5, 4, 6))})
    m["holes"] = {"input": [], "output": []}       # round holes and vertical slots (h: their arcs' centres apart)
    for hit in re.finditer(r"^  (input|output) cap: (.+?) (?:hole ([\d.]+)|slot ([\d.]+) x ([\d.]+)), "
                           r"centre u ([\d.]+), v ([\d.]+)$", text, re.M):
        d = float(hit.group(3) or hit.group(4))
        m["holes"][hit.group(1)].append({"name": hit.group(2), "d": d, "h": float(hit.group(5)) - d if hit.group(5) else 0.0,
                                         "c": (float(hit.group(6)), float(hit.group(7)))})
    d, su, sv = f(r"SMA bulkhead hole ([\d.]+) round, centre u ([\d.]+), v ([\d.]+)")
    m["sma"] = {"d": d, "c": (su, sv)}
    m["sma"]["w1"], m["sma"]["wall"], m["sma"]["wall_min"] = f(r"its body inside to w ([\d.]+): ([\d.]+) off the wall "
                                                              r"\(([\d.]+) with its cap shifted")
    m["sma"]["win"] = f(r"the centre may go v ([\d.]+)\.\.([\d.]+)")
    m["pigtail"] = re.search(r"so a (\d+) mm pigtail", text).group(1)
    m["ufl_gap"], = f(r"the cable has ([\d.]+) under the WROVER-IE's end")
    m["usb"] = f(r"the receptacle's centre u ([\d.]+), v ([\d.]+)\.\.([\d.]+); the overmould ([\d.]+) x ([\d.]+)")
    m["lips"] = {}
    for hit in re.finditer(r"^  (input|output) cap, (left|right) \(y (\d+) edge\): .*; a lip over it (\S+) on top "
                           r"\((.+?)\), (\S+) underneath \((.+)\)$", text, re.M):
        num = lambda s: math.inf if s == "free" else float(s)
        m["lips"][(hit.group(1), hit.group(2))] = {"y": int(hit.group(3)), "top": num(hit.group(4)), "top_by": hit.group(5),
                                                    "bottom": num(hit.group(6)), "bottom_by": hit.group(7)}
    if len(m["lips"]) != 4 or not m["holes"]["output"] or len(m["rects"]["input"]) < 3:
        sys.exit("gen_caps.py: check_fit.py's cut-outs are not as expected:\n" + text)

    # the board: its parts as check_fit takes them, and every lead through it
    board = pcbnew.LoadBoard(str(check_fit.BOARD))
    mm = pcbnew.ToMM
    ends = [(mm(q.x), mm(q.y)) for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts
            for q in (d.GetStart(), d.GetEnd())]
    m["x0"], m["y0"] = min(q[0] for q in ends), min(q[1] for q in ends)
    m["x1"], m["y1"] = max(q[0] for q in ends), max(q[1] for q in ends)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    name = {r: str(fp.GetFPID().GetLibItemName()) for r, fp in fps.items()}
    side = {r: "B" if fp.IsFlipped() else "F" for r, fp in fps.items()}
    H = {r: check_fit.HEIGHT[name[r]][0] for r in fps}
    ref = {}
    for r in sorted(fps):
        ref.setdefault(name[r], []).append(r)
    m1r, m2r, j1r = ref[check_fit.TANG][0], ref[check_fit.DEVKIT][0], ref["TE_MOST_Pigtail_FOT_2+0"][0]
    j4r = ref["Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal"][0]
    m["refs"] = {"J1": j1r, "J4": j4r, "M1": m1r, "M2": m2r}
    # the modules by their PCBs and overhangs, J1 by its body (check_fit's boxes and rects)
    c = check_fit
    m1, m2 = c.Frame(fps[m1r], "20", "1", "21"), c.Frame(fps[m2r], "19", "1", "20")
    m1_end = (m1.half + c.TANG_END[0], -m1.half - c.TANG_END[1])
    m1_pcb = m1.rect(m1_end[1], m1_end[0], -c.TANG_HALF_W, c.TANG_HALF_W)
    hdmi = m1.rect(m1_end[1] - c.TANG_HDMI[0], m1_end[1], -c.TANG_HDMI[2] / 2, c.TANG_HDMI[2] / 2)
    usbc = m1.rect(m1_end[0], m1_end[0] + c.TANG_USB[0], -c.TANG_USB[1] / 2, c.TANG_USB[1] / 2)
    m2_pcb = m2.rect(-c.M2_HALF[0], c.M2_HALF[0], -c.M2_HALF[1], c.M2_HALF[1])
    wr_end = c.M2_HALF[0] + c.M2_WROVER[2]
    m2_wrover = m2.rect(wr_end - c.M2_WROVER[0], wr_end, -c.M2_WROVER[1] / 2, c.M2_WROVER[1] / 2)
    rects = {r: [c.box(fp)] for r, fp in fps.items()}
    rects[m1r] = [c.span([hdmi[:2], hdmi[2:], usbc[:2], usbc[2:], m1_pcb[:2], m1_pcb[2:]])] + m1.strips()
    rects[m2r] = [m2_pcb, m2_wrover] + m2.strips()
    rects[j1r] = [c.span([c.local(fps[j1r], fx, fy) for fx in (c.J1_HOUSING[0], c.J1_BUMP)
                          for fy in (c.J1_FRONT, c.J1_REAR)])]
    z, zt = m["z"], m["zt"]
    m["parts"] = [(r, rects[r], *((zt, zt + H[r]) if side[r] == "F" else (z - H[r], z)))
                  for r in sorted(fps) if H[r] > 0.05]          # a bare pad or an empty hole has no body
    leads = []
    for r, fp in sorted(fps.items()):
        if name[r] not in c.LEADS:
            continue
        lens = c.LEADS[name[r]][0]
        for pad in fp.Pads():
            att = pad.GetAttribute()
            if att not in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                continue
            kind = c.classify(name[r], pad)
            beyond = lens[kind] - c.PCB_T
            if r in c.CUT and kind in c.CUT[r][1]:
                beyond = min(beyond, c.CUT[r][0])
            try:
                size = pad.GetSize(pcbnew.F_Cu)
            except TypeError:
                size = pad.GetSize()
            leads.append({"ref": r, "pad": pad.GetNumber() or kind, "side": side[r], "beyond": beyond, "h": H[r],
                          "p": (mm(pad.GetPosition().x), mm(pad.GetPosition().y)), "rad": mm(pad.GetDrillSize().x) / 2,
                          "ring": max(mm(size.x), mm(size.y)) / 2, "soldered": att == pcbnew.PAD_ATTRIB_PTH})
    m["leads"] = leads
    return m


# ---- plane geometry ------------------------------------------------------------------------------

def area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2


def ccw(poly):
    return poly if area(poly) > 0 else poly[::-1]


def bbox(poly):
    us, vs = [p[0] for p in poly], [p[1] for p in poly]
    return min(us), min(vs), max(us), max(vs)


def rect_poly(b):
    return [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]


def rect_point(b, p):
    """A box's distance to a point (0 inside)."""
    return math.hypot(max(b[0] - p[0], 0.0, p[0] - b[2]), max(b[1] - p[1], 0.0, p[1] - b[3]))


def clip(a, b):
    """Two boxes' common part, or None."""
    c = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return c if c[0] < c[2] and c[1] < c[3] else None


def seg_point(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = dx * dx + dy * dy
    t = 0.0 if not ln else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ln))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def inside(p, poly):
    """p strictly inside poly (ray casting)."""
    k, n = False, len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
            k = not k
    return k


def edge_dist(p, poly):
    return min(seg_point(p, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def crosses(a, b, c, d):
    o = lambda p, q, r: (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0


def apart(P, Q):
    """The clearance between two polygons' outlines; negative when they overlap."""
    bp, bq = bbox(P), bbox(Q)
    far = max(bq[0] - bp[2], bp[0] - bq[2], bq[1] - bp[3], bp[1] - bq[3])
    if far > 5:
        return far          # their boxes' gap: no more than the outlines' clearance
    if inside(P[0], Q) or inside(Q[0], P):
        return -1.0
    n, k = len(P), len(Q)
    for i in range(n):
        for j in range(k):
            if crosses(P[i], P[(i + 1) % n], Q[j], Q[(j + 1) % k]):
                return -1.0
    return min(min(edge_dist(p, Q) for p in P), min(edge_dist(q, P) for q in Q))


def segments(r, turn=2 * math.pi):
    """Facets enough for a round edge of radius r turning by turn to stay within SAG of it."""
    return max(2, math.ceil(turn / (2 * math.acos(1 - min(SAG / r, 1.0)))))


def fillet(poly, radii):
    """Round the convex corners of a ccw polygon of axis-parallel edges: radii[i] at vertex i (0: sharp)."""
    out, n = [], len(poly)
    for i in range(n):
        a, p, b = poly[i - 1], poly[i], poly[(i + 1) % n]
        l1, l2 = math.dist(a, p), math.dist(p, b)
        d1 = ((p[0] - a[0]) / l1, (p[1] - a[1]) / l1)
        d2 = ((b[0] - p[0]) / l2, (b[1] - p[1]) / l2)
        r = radii[i]
        if r <= 0 or d1[0] * d2[1] - d1[1] * d2[0] <= 0:
            out.append((R4(p[0]), R4(p[1])))
            continue
        cx, cy = p[0] - r * d1[0] + r * d2[0], p[1] - r * d1[1] + r * d2[1]
        a0, k = math.atan2(-d2[1], -d2[0]), segments(r, math.pi / 2)
        for j in range(k + 1):
            t = a0 + math.pi / 2 * j / k
            q = (R4(cx + r * math.cos(t)), R4(cy + r * math.sin(t)))
            if not out or q != out[-1]:
                out.append(q)
    return out[:-1] if out[-1] == out[0] else out


def circle(cu, cv, d):
    n = segments(d / 2)
    return [(R4(cu + d / 2 * math.cos(2 * math.pi * k / n)), R4(cv + d / 2 * math.sin(2 * math.pi * k / n)))
            for k in range(n)]


def stadium(cu, cv, d, h):
    """A vertical slot d wide: two half circles of diameter d, their centres h apart (h 0: a circle), counter-
    clockwise from the right end of the upper one's diameter."""
    if h <= 0:
        return circle(cu, cv, d)
    r, k = d / 2, max(2, math.ceil(segments(d / 2) / 2))
    top = [(R4(cu + r * math.cos(math.pi * i / k)), R4(cv + h / 2 + r * math.sin(math.pi * i / k))) for i in range(k + 1)]
    bot = [(R4(cu - r * math.cos(math.pi * i / k)), R4(cv - h / 2 - r * math.sin(math.pi * i / k))) for i in range(k + 1)]
    return top + bot


def teardrop(cu, cw, d):
    """A hole whose axis lies horizontal in the print, in the (u, w) plane, w up: round below, a 45 degree roof
    above, cut flat at the circle's top (a short bridge), so no edge overhangs more than 45 degrees and the hole
    keeps the circle's extent. Counter-clockwise."""
    r = d / 2
    k = segments(r, 1.5 * math.pi)
    arc = [(R4(cu + r * math.cos(math.radians(135) + 1.5 * math.pi * i / k)),
            R4(cw + r * math.sin(math.radians(135) + 1.5 * math.pi * i / k))) for i in range(k + 1)]
    f = r * (math.sqrt(2) - 1)                  # the flat's half-width where the roof's 45 degree lines meet w = cw + r
    return arc + [(R4(cu + f), R4(cw + r)), (R4(cu - f), R4(cw + r))]


def seg_dist(a0, a1, b0, b1):
    """The distance between two segments that do not cross (a point is a segment of no length)."""
    return min(seg_point(a0, b0, b1), seg_point(a1, b0, b1), seg_point(b0, a0, a1), seg_point(b1, a0, a1))


def depth_at(rg, v):
    """A block region's depth at height v: its depth, or along a lead-in's slope (v, depth there; v, depth there)."""
    if "slope" not in rg:
        return rg["depth"]
    va, da, vb, db = rg["slope"]
    return R4(da + (v - va) * (db - da) / (vb - va))


def in_tube(u, v, r=0.0):
    """(u, v) in a cap's frame inside the tube's inside, at least r off its walls and rounded corners."""
    hu, hv = TUBE_W / 2 - WALL, TUBE_H / 2 - WALL
    du, dv = abs(u - TUBE_W / 2), abs(v - TUBE_H / 2)
    if du > hu - r + 1e-6 or dv > hv - r + 1e-6:
        return False
    cu, cv = hu - CORNER_R, hv - CORNER_R
    return not (du > cu and dv > cv and math.hypot(du - cu, dv - cv) > max(CORNER_R - r, 0.0) + 1e-6)


def flange_outline():
    """The flange's outline, counter-clockwise from its bottom left corner: rounded at the top, square at
    the bottom, where the saddle carries on."""
    r = R_OUT
    pts = [(0.0, 0.0), (TUBE_W, 0.0)]
    for cu, cv, a0 in ((TUBE_W - r, TUBE_H - r, 0), (r, TUBE_H - r, 90)):
        for k in range(7):
            a = math.radians(a0 + 90 * k / 6)
            pts.append((R4(cu + r * math.cos(a)), R4(cv + r * math.sin(a))))
    return pts


# ---- the blocks: what a piece meets ----------------------------------------------------------------
# a piece is a box in a cap's frame (u0, v0, u1, v1, w0, w1); the board's frame: input end x0, output end x1

def to_board(m, cap, pc):
    u0, v0, u1, v1, w0, w1 = pc
    s = m["side"]
    if cap == "input":
        ya, yb = m["y0"] + u0 - WALL - s, m["y0"] + u1 - WALL - s
        xa, xb = m["x0"] + w0 - CAP_T, m["x0"] + w1 - CAP_T
    else:
        ya, yb = m["y1"] - (u1 - WALL - s), m["y1"] - (u0 - WALL - s)
        xa, xb = m["x1"] - (w1 - CAP_T), m["x1"] - (w0 - CAP_T)
    return (xa, ya, xb, yb), (v0 - WALL, v1 - WALL)


def meets(m, cap, pc, first=False):
    """What the piece comes too close to (a list of words; empty when it is clear): the board's slab; a part
    (LIP_GAP in plan unless TOP_GAP above or below it); a lead on its far side (the lead LIP_GAP or a peg
    PEG_CLR off; a soldered lead's fillet LEAD_KEEP off its centre, on the board); a soldered lead's pad and
    top fillet on its own side (LIP_GAP off the pad, up into its part); the SMA's body (SMA_GAP)."""
    bx, bz = to_board(m, cap, pc)
    z, zt = m["z"], m["zt"]
    brd = (m["x0"], m["y0"], m["x1"], m["y1"])
    hits = []
    tol = 1e-6
    zgap = lambda za, zb: max(za - bz[1], bz[0] - zb)
    if clip(bx, brd) and bz[0] < zt - tol and bz[1] > z + tol:
        hits.append("the board")
        if first:
            return hits
    for r, rects, za, zb in m["parts"]:
        if zgap(za, zb) >= TOP_GAP - tol:
            continue
        g = min(check_fit.gap(bx, rc) for rc in rects)
        if g < LIP_GAP - tol:
            hits.append(f"{r} ({g:.2f} off in plan)")
            if first:
                return hits
    for ld in m["leads"]:
        p = ld["p"]
        what = f"{ld['ref']} pad {ld['pad']} at ({p[0]:.2f}, {p[1]:.2f})"
        if ld["beyond"] > 0:
            za, zb = (z - ld["beyond"], z) if ld["side"] == "F" else (zt, zt + ld["beyond"])
            if zgap(za, zb) < TOP_GAP - tol:
                keep = ld["rad"] + (LIP_GAP if ld["soldered"] else PEG_CLR)
                d = rect_point(bx, p)
                cb = clip(bx, brd)
                if d < keep - tol:
                    hits.append(f"{what}, its {'lead' if ld['soldered'] else 'peg'} ({d:.2f} off)")
                elif ld["soldered"] and cb and rect_point(cb, p) < LEAD_KEEP - tol:
                    hits.append(f"{what}, its fillet ({rect_point(cb, p):.2f} off the centre)")
                if hits and first:
                    return hits
        if ld["soldered"]:
            za, zb = (zt, zt + ld["h"]) if ld["side"] == "F" else (z - ld["h"], z)
            cb = clip(bx, brd)
            if zgap(za, zb) < TOP_GAP - tol and cb and rect_point(cb, p) < ld["ring"] + LIP_GAP - tol:
                hits.append(f"{what}, its pad on its own side ({rect_point(cb, p):.2f} off the centre)")
                if first:
                    return hits
    if cap == "input" and pc[4] < m["sma"]["w1"] and pc[5] > CAP_T:
        d = rect_point(pc[:4], m["sma"]["c"]) - R_SMA
        if d < check_fit.SMA_GAP - tol:
            hits.append(f"the SMA's body ({d:.2f} off)")
    return hits


# ---- the caps ---------------------------------------------------------------------------------------

def margins(m, hand):
    """A side margin in a cap's frame: the post's outer face (off the wall), its face to the board, the
    board's edge."""
    s, W = m["side"], m["W"]
    if hand == "left":
        return R4(WALL + GAP_TUBE), R4(WALL + s - BOARD_PLAY), WALL + s
    return R4(TUBE_W - WALL - GAP_TUBE), R4(WALL + s + W + BOARD_PLAY), WALL + s + W


def lip_piece(m, hand, which, width, depth, vtop):
    _, ui, edge = margins(m, hand)
    ul = R4(edge + width) if hand == "left" else R4(edge - width)
    v0, v1 = (R4(V(m["zt"]) + SLOT_PLAY), vtop) if which == "top" else (VB, R4(V(m["z"])))
    return (min(ui, ul), v0, max(ui, ul), v1, CAP_T, R4(CAP_T + depth))


def best_lip(m, cap, hand, which, vtop):
    """(width, depth) of a lip: the widest over the block's whole depth; failing that, the ledge of the largest
    area (the deeper of equals); None when not even a ledge fits."""
    widths = [w / 20 for w in range(round(LIP_MAX * 20), round(LIP_MIN * 20) - 1, -1)]
    for wd in widths:
        if not meets(m, cap, lip_piece(m, hand, which, wd, BLOCK_D, vtop), first=True):
            return wd, BLOCK_D
    best = None
    for d10 in range(round(BLOCK_D * 10) - 1, round(LEDGE_MIN * 10) - 1, -1):
        d = d10 / 10
        for wd in widths:
            if best and wd * d <= best[0] * best[1] + 1e-9:
                break
            if not meets(m, cap, lip_piece(m, hand, which, wd, d, vtop), first=True):
                best = (wd, d)
                break
    return best


def side_block(m, cap, hand, vtop):
    """A post in the side margin and its lips over and under the board's edge, as regions of one block."""
    uo, ui, edge = margins(m, hand)
    vz, vs = R4(V(m["z"])), R4(V(m["zt"]) + SLOT_PLAY)
    lips, regions, why = {}, [], {}
    for which in ("top", "bottom"):
        lp = best_lip(m, cap, hand, which, vtop)
        lips[which] = lp
        if lp:
            wd, d = lp
            more_w = meets(m, cap, lip_piece(m, hand, which, wd + 0.05, d, vtop), first=True) if wd < LIP_MAX else []
            more_d = meets(m, cap, lip_piece(m, hand, which, wd, d + 0.1, vtop), first=True) if d < BLOCK_D else []
            why[which] = (more_w[0] if more_w else f"{LIP_MAX} at most", more_d[0] if more_d else "")
    top, bot = lips["top"], lips["bottom"]
    rc = R4(CORNER_R - GAP_TUBE)
    round_top = abs(vtop - VT) < 1e-6
    vzl, vsl = R4(vz - LEAD_IN), R4(vs + LEAD_IN)       # where the lips' lead-ins end on the post's face
    if hand == "left":
        pts = ([(uo, VB), (ui, VB)] + ([(ui, vzl), (ui, vz)] if bot else []) + ([(ui, vs), (ui, vsl)] if top else [])
               + [(ui, vtop), (uo, vtop)])
        radii = [rc] + [0] * (len(pts) - 2) + [rc if round_top else 0]
    else:
        pts = ([(ui, VB), (uo, VB), (uo, vtop), (ui, vtop)] + ([(ui, vsl), (ui, vs)] if top else [])
               + ([(ui, vz), (ui, vzl)] if bot else []))
        radii = [0, rc, rc if round_top else 0] + [0] * (len(pts) - 3)
    post = fillet(pts, radii)
    regions.append({"name": "post", "ua": "стійка", "poly": post, "depth": BLOCK_D,
                    "box": (min(uo, ui), VB, max(uo, ui), vtop)})
    for which, lp in (("top", top), ("bottom", bot)):
        if not lp:
            continue
        wd, d = lp
        b = lip_piece(m, hand, which, wd, d, vtop)
        ledge = d < BLOCK_D
        over = which == "top"
        # the lip as a plain prism and, along its face to the board, a LEAD_IN strip whose top slopes 45 degrees
        # down to that face: the board's end meets a ramp, not the lip's square tip
        if over:
            v_face, v_end = b[1], vsl
            flat, lead = (b[0], v_end, b[2], b[3]), (b[0], b[1], b[2], v_end)
        else:
            v_face, v_end = b[3], vzl
            flat, lead = (b[0], b[1], b[2], v_end), (b[0], v_end, b[2], b[3])
        if b[3] - b[1] < LEAD_IN + MIN_WEB or d < LEAD_IN + 0.5:
            sys.exit(f"gen_caps.py: the {which} lip of the {hand} block has no room for its lead-in")
        regions.append({"name": f"{'ledge' if ledge else 'lip'} {'over' if over else 'under'} the board",
                        "ua": f"{'коротка ' if ledge else ''}{'верхня' if over else 'нижня'} щока паза "
                              f"({'над платою' if over else 'під платою'})",
                        "poly": rect_poly(flat), "depth": d, "box": b[:4], "width": wd, "why": why[which]})
        regions.append({"name": f"{'ledge' if ledge else 'lip'} {'over' if over else 'under'} the board, its lead-in",
                        "ua": "заходна фаска", "lead": True, "poly": rect_poly(lead), "depth": d,
                        "slope": (v_face, R4(d - LEAD_IN), v_end, d), "box": lead})
    edge_y = 0 if (cap == "input") == (hand == "left") else int(round(m["y1"] - m["y0"]))
    blk = {"name": f"{hand} block (y {edge_y} edge)", "ua": f"{'лівий' if hand == 'left' else 'правий'} блок (край y {edge_y})",
           "regions": regions, "hand": hand, "lips": lips, "screw": None}
    if round_top:                                       # a post that reaches the tube's top takes a screw through it
        blk["screw"] = (R4((uo + ui) / 2), R4(CAP_T + BLOCK_D / 2))
    return blk


def screw_tip():
    """The screws' tip in a block (v): through the tube's top wall and the gap over the block."""
    return R4(VT - (SCREW_L - WALL - GAP_TUBE))


def ground_block(m, j4_open):
    """Over the board between J4's opening and the SMA's body, from the tube's top down to TOP_GAP over what is
    under it: the input cap's second screw, under whose head the tube's ground wire goes."""
    sc = m["sma"]["c"]
    u0 = math.ceil((bbox(j4_open)[2] + GROUND_OPEN_GAP) * 20 - 1e-6) / 20
    u1 = math.floor((sc[0] - R_SMA - check_fit.SMA_GAP) * 20 + 1e-6) / 20
    v0 = None
    for k in range(round((screw_tip() - 0.5) * 20), round(V(m["zt"]) * 20) - 1, -1):
        if meets(m, "input", (u0, k / 20, u1, VT, CAP_T, CAP_T + BLOCK_D), first=True):
            break
        v0 = k / 20
    if v0 is None:
        return None
    lower = meets(m, "input", (u0, R4(v0 - 0.05), u1, VT, CAP_T, CAP_T + BLOCK_D), first=True)
    box = (u0, v0, u1, VT)
    return {"name": f"ground block (over {m['refs']['J4']}'s side)", "ua": f"блок заземлення (над боком {m['refs']['J4']})",
            "regions": [{"name": "block", "ua": "блок", "poly": rect_poly(box), "depth": BLOCK_D, "box": box,
                         "why": (lower[0] if lower else "",)}],
            "lips": {}, "screw": (R4(round((u0 + u1) / 2 * 20) / 20), R4(CAP_T + BLOCK_D / 2)), "ground": True}


def ua_name(nm):
    """An opening's name in Ukrainian."""
    t = re.sub(r"(\w+)'s housing", r"корпус \1", nm)
    t = re.sub(r"(\w+)'s micro-USB, its plug's overmould", r"micro-USB \1 під литий корпус штекера", t)
    t = re.sub(r"(\w+)'s frame", r"рамка \1", t)
    t = re.sub(r"(\w+)'s face", r"грань \1", t)
    t = re.sub(r"(\w+)'s bushing", r"різьбова втулка \1", t)
    return t.replace(" and ", " і ")


def cap_openings(m, cap):
    """The cut-outs: check_fit's rectangles (corners R_HOLE, J1's with its standoff's notch), its round holes,
    and the SMA's hole as its maker gives it. Each with the parts it lets through and its clearance."""
    ops = []
    rects = m["rects"][cap]
    notch = next((r for r in rects if "notch" in r["name"]), None)
    for r in rects:
        if r is notch:
            continue
        b = r["box"]
        pts, parts, nm, ua = rect_poly(b), [(b[0] + CLR, b[1] + CLR, b[2] - CLR, b[3] - CLR)], r["name"], ua_name(r["name"])
        if notch and r["name"] == f"{m['refs']['J1']}'s housing":
            n = notch["box"]
            if abs(n[3] - b[1]) > EPS or not b[0] < n[0] < n[2] < b[2]:
                sys.exit("gen_caps.py: J1's notch is not under its housing's opening")
            pts = [(b[0], b[1]), (n[0], b[1]), (n[0], n[1]), (n[2], n[1]), (n[2], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]
            parts.append((n[0] + CLR, n[1] + CLR, n[2] - CLR, n[3] + CLR))      # the standoff runs on up into J1
            nm += ", with the notch for its standoff"
            ua += " з вирізом під його ніжку"
        ops.append({"name": nm, "ua": ua, "poly": fillet(pts, [R_HOLE] * len(pts)), "parts": parts, "clr": CLR,
                    "apart": r["apart"]})
    for h in m["holes"][cap]:
        ops.append({"name": h["name"], "ua": ua_name(h["name"]), "poly": stadium(*h["c"], h["d"], h["h"]),
                    "round": (h["c"], h["d"], check_fit.RCA_THREAD[1], h["h"]), "clr": CLR})
    if cap == "input":
        s = m["sma"]
        ops.append({"name": "the antenna's SMA bulkhead", "ua": "SMA-гніздо антени", "poly": circle(*s["c"], s["d"]),
                    "round": (s["c"], s["d"], SMA_THREAD, 0.0), "clr": CLR, "sma": True})
    return ops


def saddle(T):
    s = {"u0": -EAR, "u1": TUBE_W + EAR, "v0": -SADDLE_T, "v1": 0.0, "l": T + SADDLE_L, "holes": []}
    wc = T + SADDLE_L / 2
    s["holes"] = [{"name": "ear hole", "ua": "отвір у вусі", "u": -EAR / 2, "w": wc, "d": EAR_HOLE},
                  {"name": "ear hole", "ua": "отвір у вусі", "u": TUBE_W + EAR / 2, "w": wc, "d": EAR_HOLE}]
    return s


def design(m):
    """Both caps: openings, blocks, saddles; and the checks. Returns (caps, fails, notes)."""
    fails, notes = [], []
    O = flange_outline()
    caps = []
    for cap, fname, title in (("input", "in_cap", "input cap"), ("output", "out_cap", "output cap")):
        ops = cap_openings(m, cap)
        blocks = []
        for hand in ("left", "right"):
            vtop = VT
            if cap == "input" and hand == "right":          # under the SMA's body
                vtop = math.floor((m["sma"]["c"][1] - R_SMA - check_fit.SMA_GAP) * 20 + 1e-6) / 20
            blocks.append(side_block(m, cap, hand, vtop))
        if cap == "input":
            j4 = next((o for o in ops if f"{m['refs']['J4']}'s face" in o["name"]), None)
            gb = ground_block(m, j4["poly"]) if j4 else None
            if not gb:
                fails.append("input cap: no room for the ground block between J4 and the SMA")
            else:
                blocks.append(gb)
        caps.append({"cap": cap, "name": fname, "title": title, "openings": ops, "blocks": blocks, "saddle": saddle(CAP_T)})

    for c in caps:
        nm = c["name"]
        ops = c["openings"]
        # the openings round their parts
        for o in ops:
            if "round" in o:                    # its part anywhere on the centre line (a slot's), off every facet
                (cu, cv), d, part, h = o["round"]
                a0, a1, P = (cu, cv - h / 2), (cu, cv + h / 2), o["poly"]
                g = min(seg_dist(a0, a1, P[i], P[(i + 1) % len(P)]) for i in range(len(P))) - part / 2
                if g < o["clr"] - EPS or not inside((cu, cv), P):
                    fails.append(f"{nm}: {o['name']} {g:.3f} round its {part} part, {o['clr']:.3f} wanted")
                continue
            for b in o["parts"]:
                n = max(2, math.ceil(max(b[2] - b[0], b[3] - b[1]) / 0.25))
                pts = [(b[0] + (b[2] - b[0]) * i / n, b[1] + (b[3] - b[1]) * j)
                       for i in range(n + 1) for j in (0, 1)] + \
                      [(b[0] + (b[2] - b[0]) * j, b[1] + (b[3] - b[1]) * i / n) for i in range(n + 1) for j in (0, 1)]
                worst = min((edge_dist(p, o["poly"]) if inside(p, o["poly"]) else -edge_dist(p, o["poly"])) for p in pts)
                if worst < o["clr"] - EPS:
                    fails.append(f"{nm}: {o['name']} {worst:.3f} round its part, {o['clr']} wanted")
        # the walls: between the openings, to the flange's edge; the SMA's nut on the flange
        thin = (math.inf, "")
        for i, a in enumerate(ops):
            if not all(inside(p, O) for p in a["poly"]):
                fails.append(f"{nm}: {a['name']} leaves the flange")
            e = min(edge_dist(p, O) for p in a["poly"])
            thin = min(thin, (e, f"{a['name']} to the flange's edge"))
            for b in ops[i + 1:]:
                thin = min(thin, (apart(a["poly"], b["poly"]), f"{a['name']} - {b['name']}"))
        c["thin"] = thin
        if thin[0] < MIN_WEB - EPS:
            fails.append(f"{nm}: {thin[0]:.2f} mm of wall ({thin[1]}), {MIN_WEB} wanted")
        for o in ops:
            if o.get("sma"):
                nut = circle(*o["round"][0], 2 * R_SMA)
                g = min(apart(nut, x["poly"]) for x in ops if x is not o)
                e = min(edge_dist(p, O) for p in nut) if all(inside(p, O) for p in nut) else -1.0
                c["nut"] = (g, e)
                if g < 0 or e < 0:
                    fails.append(f"{nm}: the SMA's nut ({2 * R_SMA:.2f} across corners) is not on the flange alone")
                if CAP_T > check_fit.SMA_PANEL_MAX:
                    fails.append(f"{nm}: the flange {CAP_T} thicker than the SMA's panel limit {check_fit.SMA_PANEL_MAX}")
        # the blocks
        for blk in c["blocks"]:
            for rg in blk["regions"]:
                pc = (*rg["box"], CAP_T, R4(CAP_T + rg["depth"]))
                for h in meets(m, c["cap"], pc):
                    fails.append(f"{nm}: {blk['name']}'s {rg['name']} meets {h}")
                for p in rg["poly"]:
                    if not in_tube(*p, GAP_TUBE - 1e-4):        # the points are rounded to 0.1 um
                        fails.append(f"{nm}: {blk['name']}'s {rg['name']} at ({p[0]:.2f}, {p[1]:.2f}) is not "
                                     f"{GAP_TUBE} inside the tube")
                        break
                for o in ops:
                    g = apart(rect_poly(rg["box"]), o["poly"])
                    if g <= OPEN_GAP:
                        fails.append(f"{nm}: {blk['name']}'s {rg['name']} stands {g:.2f} off {o['name']}")
                b = rg["box"]
                if not rg.get("lead") and min(b[2] - b[0], b[3] - b[1]) < (LIP_MIN if rg["name"] not in ("post", "block")
                                                                          else MIN_WEB) - 1e-6:
                    fails.append(f"{nm}: {blk['name']}'s {rg['name']} is too thin")
            if blk["screw"]:                    # the pilot drilled through the tube's hole may sit off its centre by
                su, sw = blk["screw"]           # their difference (the cap centred by its flange on the tube's outline)
                rb = blk["regions"][0]["box"]
                off = PILOT / 2 + (TUBE_HOLE - PILOT) / 2
                walls = (su - off - rb[0], rb[2] - su - off, sw - CAP_T - off, CAP_T + blk["regions"][0]["depth"] - sw - off)
                blk["screw_wall"] = min(walls)
                if min(walls) < MIN_WEB or screw_tip() - rb[1] < 0.5 or abs(rb[3] - VT) > 1e-6:
                    fails.append(f"{nm}: {blk['name']} does not take its screw (walls {min(walls):.2f}, its tip "
                                 f"{screw_tip() - rb[1]:.2f} over the block's foot)")
        for i, a in enumerate(c["blocks"]):                 # blocks apart from each other
            for b in c["blocks"][i + 1:]:
                for ra in a["regions"]:
                    for rb in b["regions"]:
                        if apart(rect_poly(ra["box"]), rect_poly(rb["box"])) < MIN_WEB:
                            fails.append(f"{nm}: {a['name']} and {b['name']} too close")
        # the board: carried from below at its corners
        for blk in c["blocks"]:
            if "hand" in blk and not blk["lips"]["bottom"]:
                notes.append(f"{nm}: {blk['name']} carries no lip under the board")
            if "hand" in blk and not blk["lips"]["top"]:
                notes.append(f"{nm}: {blk['name']} has no lip over the board")
        # the saddle
        s = c["saddle"]
        for h in s["holes"]:
            r = h["d"] / 2
            web = min(h["u"] - r - s["u0"], s["u1"] - h["u"] - r, h["w"] - r, s["l"] - h["w"] - r)
            if h["u"] - r < TUBE_W and h["u"] + r > 0:
                web = min(web, h["w"] - r - CAP_T)
            if web < MIN_WEB:
                fails.append(f"{nm}: the saddle's {h['name']} at u {h['u']:.2f} leaves {web:.2f} mm, {MIN_WEB} wanted")
            if h["w"] - EAR_WASHER / 2 < -1e-6 or h["w"] + EAR_WASHER / 2 > s["l"] + 1e-6:
                fails.append(f"{nm}: the {EAR_WASHER} washer at u {h['u']:.2f} runs off the ear")
        if EAR / 2 < EAR_WASHER / 2 + 0.5 - 1e-6:
            fails.append(f"{nm}: an ear screw's washer ({EAR_WASHER}) does not clear the tube's side by 0.5")
    return caps, fails, notes


# ---- the solid: faces in the print's frame ------------------------------------------------------
# x = -u (the cap seen from inside, so the frame stays right-handed), y = v, z = w: the outer face on the bed
# at z = 0, the flange up to z = T, the blocks from T up, the saddle from 0 to its length under the tube

def union_loops(regions):
    """The outlines of a block's regions taken together (their edges without a twin), counter-clockwise."""
    own = {}
    for rg in regions:
        poly = rg["poly"]
        for k in range(len(poly)):
            own[(poly[k], poly[(k + 1) % len(poly)])] = rg
    nxt = {a: b for (a, b) in own if (b, a) not in own}
    loops = []
    while nxt:
        a0 = next(iter(nxt))
        loop, a = [a0], nxt.pop(a0)
        while a != a0:
            loop.append(a)
            a = nxt.pop(a)
        loops.append(loop)
    return loops, own


def solid(cap, T):
    faces = []              # (outer loop, [hole loops]) of 3-D points, wound counter-clockwise about the normal

    def P(u, v, w):
        return (round(-u, 4), round(v, 4), round(w, 4))

    def face(outer, holes, n):
        """Loops of (u, v, w) points; n the outward normal in (u, v, w)."""
        o = [P(*q) for q in outer]
        hs = [[P(*q) for q in h] for h in holes]
        np_ = (-n[0], n[1], n[2])
        dot = lambda a: sum(a[i] * np_[i] for i in range(3))
        if dot(newell(o)) < 0:
            o = o[::-1]
        hs = [h[::-1] if dot(newell(h)) > 0 else h for h in hs]
        faces.append((o, hs))

    def walls(loop, w0, w1, inward):
        """Side faces of a loop (counter-clockwise in u, v) from w0 to w1."""
        for i in range(len(loop)):
            a, b = loop[i], loop[(i + 1) % len(loop)]
            du, dv = b[0] - a[0], b[1] - a[1]
            n = (-dv, du, 0) if inward else (dv, -du, 0)
            face([(a[0], a[1], w0), (b[0], b[1], w0), (b[0], b[1], w1), (a[0], a[1], w1)], [], n)

    O = flange_outline()
    s = cap["saddle"]
    A0, A1, B0, B1, L = s["u0"], s["u1"], s["v0"], s["v1"], s["l"]
    openings = [ccw(o["poly"]) for o in cap["openings"]]
    outlines = []
    for blk in cap["blocks"]:
        loops, _ = union_loops(blk["regions"])
        outlines += loops
    holes = [teardrop(h["u"], h["w"], h["d"]) for h in s["holes"]]

    # the outer face: the flange and the saddle's front as one
    front = [(A0, B0), (A1, B0), (A1, B1)] + O[1:] + [O[0], (A0, B1)]
    face([(u, v, 0) for u, v in front], [[(u, v, 0) for u, v in h] for h in openings], (0, 0, -1))
    # the flange's inner face: the tube's end and the board's ends bear on it, the blocks stand on it
    face([(u, v, T) for u, v in O], [[(u, v, T) for u, v in h] for h in openings] +
         [[(u, v, T) for u, v in b] for b in outlines], (0, 0, 1))
    # the flange's sides, but its bottom edge, where the saddle carries on
    walls(O[1:] + [O[0]], 0, T, False)
    faces.pop()             # the bottom edge's face (from O[0] round to O[1])
    for h in openings:
        walls(h, 0, T, True)
    # the blocks: each region a prism from the flange to its top (flat, or a lead-in's slope); where two meet,
    # the higher one's side above the other's top; every vertical edge split at every level that meets it (no
    # T-junctions)
    def top(rg, p):
        return R4(T + depth_at(rg, p[1]))
    for blk in cap["blocks"]:
        _, own = union_loops(blk["regions"])
        levels = {}
        for rg in blk["regions"]:
            for p in rg["poly"]:
                levels.setdefault(p, {T}).add(top(rg, p))
        for (a, b), rg in own.items():
            w1a, w1b = top(rg, a), top(rg, b)
            twin = own.get((b, a))
            if twin is None:
                w0a = w0b = T
            else:
                w0a, w0b = top(twin, a), top(twin, b)
                if w0a >= w1a and w0b >= w1b:
                    continue                    # the twin's side, or none
                if w0a > w1a or w0b > w1b:
                    raise RuntimeError(f"two regions' tops cross along the edge {a}-{b}")
            la = sorted(x for x in levels[a] if w0a < x < w1a)
            lb = sorted(x for x in levels[b] if w0b < x < w1b)
            loop = ([(a[0], a[1], w0a), (b[0], b[1], w0b)] + [(b[0], b[1], x) for x in lb]
                    + [(b[0], b[1], w1b), (a[0], a[1], w1a)] + [(a[0], a[1], x) for x in reversed(la)])
            pts = [q for i, q in enumerate(loop) if q != loop[i - 1]]     # an end where the two tops meet: a triangle
            face(pts, [], (b[1] - a[1], a[0] - b[0], 0))
        for rg in blk["regions"]:
            face([(u, v, top(rg, (u, v))) for u, v in rg["poly"]], [], (0, 0, 1))
    # the saddle: its top (the tube's floor rests on it, the flange stands on it), bottom, sides, end
    top = [(A0, 0), (O[0][0], 0), (O[0][0], T), (O[1][0], T), (O[1][0], 0), (A1, 0), (A1, L), (A0, L)]
    face([(u, B1, w) for u, w in top], [[(u, B1, w) for u, w in h] for h in holes], (0, 1, 0))
    face([(A0, B0, 0), (A1, B0, 0), (A1, B0, L), (A0, B0, L)], [[(u, B0, w) for u, w in h] for h in holes], (0, -1, 0))
    face([(A0, B0, 0), (A0, B1, 0), (A0, B1, L), (A0, B0, L)], [], (-1, 0, 0))
    face([(A1, B0, 0), (A1, B1, 0), (A1, B1, L), (A1, B0, L)], [], (1, 0, 0))
    face([(A0, B0, L), (A1, B0, L), (A1, B1, L), (A0, B1, L)], [], (0, 0, 1))
    for h in holes:         # the holes' walls, facing their axes
        cu, cw = sum(q[0] for q in h) / len(h), sum(q[1] for q in h) / len(h)
        for i in range(len(h)):
            a, b = h[i], h[(i + 1) % len(h)]
            mu, mw = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            face([(a[0], B0, a[1]), (b[0], B0, b[1]), (b[0], B1, b[1]), (a[0], B1, a[1])], [], (cu - mu, 0, cw - mw))
    return faces


# ---- triangles for the STL ----------------------------------------------------------------------

def _inside_tri(p, a, b, c, closed=False):
    """p inside the triangle; closed: on its edges counts too (a vertex on an ear's new edge, as the
    flange's foot and the saddle's ends lie on one line, would leave a sliver the clipping stalls on)."""
    d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
    d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
    d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
    e = -1e-12 if closed else 1e-12
    return (d1 > e and d2 > e and d3 > e) or (d1 < -e and d2 < -e and d3 < -e)


def _bridge(outer, holes):
    """One loop out of an outer loop (ccw) and holes (cw), joined by slits (Eberly)."""
    poly = list(outer)
    for h in sorted(holes, key=lambda h: -max(p[0] for p in h)):
        im = max(range(len(h)), key=lambda i: (h[i][0], -h[i][1]))
        M = h[im]
        best = None
        for j in range(len(poly)):
            a, b = poly[j], poly[(j + 1) % len(poly)]
            if (a[1] > M[1]) == (b[1] > M[1]) or a[1] == b[1]:
                continue
            x = a[0] + (M[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x >= M[0] and (best is None or x < best[0]):
                best = (x, j)
        x, j = best
        a, b = poly[j], poly[(j + 1) % len(poly)]
        k = j if a[0] > b[0] else (j + 1) % len(poly)
        I = (x, M[1])
        cand = [q for q in range(len(poly)) if q != k and _inside_tri(poly[q], M, I, poly[k])]
        if cand:
            k = min(cand, key=lambda q: (abs(math.atan2(poly[q][1] - M[1], poly[q][0] - M[0])),
                                         (poly[q][0] - M[0]) ** 2 + (poly[q][1] - M[1]) ** 2))
        poly = poly[:k + 1] + h[im:] + h[:im + 1] + poly[k:]
    return poly


def triangulate(outer, holes):
    """Ear clipping of a planar face given in 2-D (outer ccw, holes cw); triangles of 2-D points."""
    poly = _bridge(outer, holes)
    idx = list(range(len(poly)))
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 1000000:
        guard += 1
        n = len(idx)
        for i in range(n):
            a, b, c = poly[idx[i - 1]], poly[idx[i]], poly[idx[(i + 1) % n]]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-12:
                continue
            if any(_inside_tri(poly[q], a, b, c, closed=True) for q in idx if poly[q] not in (a, b, c)):
                continue
            tris.append((a, b, c))
            del idx[i]
            break
        else:
            raise RuntimeError("ear clipping stalled")
    tris.append(tuple(poly[q] for q in idx))
    return tris


def stl(faces, name):
    tris = []
    for outer, holes in faces:
        n = newell(outer)
        ax = max(range(3), key=lambda i: abs(n[i]))
        keep = [i for i in range(3) if i != ax]
        sgn = 1 if n[ax] > 0 else -1
        if ax == 1:
            sgn = -sgn          # (z, x) is the right-handed pair about y
        def to2(p):
            q = (p[keep[0]], p[keep[1]])
            return q if sgn > 0 else (q[0], -q[1])
        lift = {}
        for p in outer + [q for h in holes for q in h]:
            lift[to2(p)] = p
        for t in triangulate([to2(p) for p in outer], [[to2(p) for p in h] for h in holes]):
            tris.append((n, tuple(lift[q] for q in t)))
    data = bytearray(name.encode()[:80].ljust(80, b" ")) + struct.pack("<I", len(tris))
    for n, (a, b, c) in tris:
        ln = math.sqrt(sum(v * v for v in n)) or 1
        data += struct.pack("<12fH", *(v / ln for v in n), *a, *b, *c, 0)
    return bytes(data), tris


def newell(loop):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(loop):
        b = loop[(i + 1) % len(loop)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def mesh_checks(tris):
    """Closed and outward: every edge used once each way; the volume positive."""
    edges = {}
    vol = 0.0
    for _, (a, b, c) in tris:
        for p, q in ((a, b), (b, c), (c, a)):
            edges[(p, q)] = edges.get((p, q), 0) + 1
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    bad = [e for e, k in edges.items() if k != 1 or edges.get((e[1], e[0]), 0) != 1]
    return bad, vol


# ---- STEP ---------------------------------------------------------------------------------------

def step(faces, name, rgb=(0.15, 0.15, 0.15)):
    """AP214: one closed shell of planar faces with their holes, as wound."""
    ents = []

    def e(text):
        ents.append(text)
        return f"#{len(ents)}"

    def r(v, d=4):
        t = (f"%.{d}f" % v).rstrip("0")
        return "0." if t in ("0.", "-0.") else t

    def cp(p):
        return e(f"CARTESIAN_POINT('',({r(p[0])},{r(p[1])},{r(p[2])}))")

    def dr(v):
        n = math.sqrt(sum(c * c for c in v))
        return e(f"DIRECTION('',({r(v[0] / n, 6)},{r(v[1] / n, 6)},{r(v[2] / n, 6)}))")

    app = e("APPLICATION_CONTEXT('core data for automotive mechanical design processes')")
    e(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,{app})")
    pc = e(f"PRODUCT_CONTEXT('',{app},'mechanical')")
    prod = e(f"PRODUCT('{name}','{name}','',({pc}))")
    pdf = e(f"PRODUCT_DEFINITION_FORMATION('','',{prod})")
    pdc = e(f"PRODUCT_DEFINITION_CONTEXT('part definition',{app},'design')")
    pdef = e(f"PRODUCT_DEFINITION('design','',{pdf},{pdc})")
    pds = e(f"PRODUCT_DEFINITION_SHAPE('','',{pdef})")
    mmu = e("( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) )")
    rad = e("( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) )")
    sr = e("( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() )")
    unc = e(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),{mmu},'distance_accuracy_value','confusion accuracy')")
    ctx = e(f"( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT(({unc})) "
            f"GLOBAL_UNIT_ASSIGNED_CONTEXT(({mmu},{rad},{sr})) "
            f"REPRESENTATION_CONTEXT('Context #1','3D Context with UNIT and UNCERTAINTY') )")
    o = cp((0, 0, 0))
    items = [e(f"AXIS2_PLACEMENT_3D('',{o},{dr((0, 0, 1))},{dr((1, 0, 0))})")]
    verts, edges, fents = {}, {}, []

    def loop_ent(lp):
        oes = []
        for p in lp:
            if p not in verts:
                verts[p] = e(f"VERTEX_POINT('',{cp(p)})")
        for i, a in enumerate(lp):
            b = lp[(i + 1) % len(lp)]
            key = (a, b) if a < b else (b, a)
            if key not in edges:
                d = [key[1][j] - key[0][j] for j in range(3)]
                vec = e(f"VECTOR('',{dr(d)},{r(math.sqrt(sum(v * v for v in d)))})")
                edges[key] = e(f"EDGE_CURVE('',{verts[key[0]]},{verts[key[1]]},{e(f'LINE({chr(39) * 2},{cp(key[0])},{vec})')},.T.)")
            oes.append(e(f"ORIENTED_EDGE('',*,*,{edges[key]},{'.T.' if key == (a, b) else '.F.'})"))
        return e(f"EDGE_LOOP('',({','.join(oes)}))")

    for outer, holes in faces:
        n = newell(outer)
        bounds = [e(f"FACE_OUTER_BOUND('',{loop_ent(outer)},.T.)")]
        bounds += [e(f"FACE_BOUND('',{loop_ent(h)},.T.)") for h in holes]
        refd = [outer[1][j] - outer[0][j] for j in range(3)]
        ax = e(f"AXIS2_PLACEMENT_3D('',{cp(outer[0])},{dr(n)},{dr(refd)})")
        fents.append(e(f"ADVANCED_FACE('',({','.join(bounds)}),{e(f'PLANE({chr(39) * 2},{ax})')},.T.)"))
    shell = e(f"CLOSED_SHELL('',({','.join(fents)}))")
    brep = e(f"MANIFOLD_SOLID_BREP('{name}',{shell})")
    items.append(brep)
    col = e(f"COLOUR_RGB('',{r(rgb[0])},{r(rgb[1])},{r(rgb[2])})")
    fill = e(f"FILL_AREA_STYLE('',({e(f'FILL_AREA_STYLE_COLOUR({chr(39) * 2},{col})')}))")
    side = e(f"SURFACE_SIDE_STYLE('',({e(f'SURFACE_STYLE_FILL_AREA({fill})')}))")
    psa = e(f"PRESENTATION_STYLE_ASSIGNMENT(({e(f'SURFACE_STYLE_USAGE(.BOTH.,{side})')}))")
    styled = e(f"STYLED_ITEM('color',({psa}),{brep})")
    shape = e(f"ADVANCED_BREP_SHAPE_REPRESENTATION('{name}',({','.join(items)}),{ctx})")
    e(f"SHAPE_DEFINITION_REPRESENTATION({pds},{shape})")
    e(f"MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',({styled}),{ctx})")
    return ("ISO-10303-21;\nHEADER;\n"
            f"FILE_DESCRIPTION(('{name}, listener v2.0 end cap, written by gen_caps.py'),'2;1');\n"
            f"FILE_NAME('{name}.step','{STEP_DATE}',(''),(''),'gen_caps.py','gen_caps.py','');\n"
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\nENDSEC;\nDATA;\n"
            + "".join(f"#{i + 1}={t};\n" for i, t in enumerate(ents)) + "ENDSEC;\nEND-ISO-10303-21;\n")


# ---- the tables -----------------------------------------------------------------------------------

def rows(cap, lang):
    """The sizes of one cap, as (what, u, v, w) strings: u, v from the flange's outer edges, w from its outer face."""
    U = lang == "uk"
    out = []
    for o in cap["openings"]:
        b = bbox(o["poly"])
        nm = o["ua"] if U else o["name"]
        if "round" in o:
            (cu, cv), d, _, h = o["round"]
            if h:
                what = (f"{nm}: паз {d:.2f} завширшки, {d + h:.2f} заввишки, центр" if U else
                        f"{nm}: slot {d:.2f} wide, {d + h:.2f} tall, centre")
            else:
                what = f"{nm}: Ø{d:.2f}, центр" if U else f"{nm}: Ø{d:.2f}, centre"
            out.append((what, f"{cu:.2f}", f"{cv:.2f}", f"0…{CAP_T:.1f}" if U else f"0..{CAP_T:.1f}"))
        else:
            what = nm
            if o.get("apart"):
                what += (f" (одним вирізом: між ними було б {o['apart']:.2f})" if U else
                         f" (one opening: {o['apart']:.2f} between them)")
            out.append((what, f"{b[0]:.2f}…{b[2]:.2f}", f"{b[1]:.2f}…{b[3]:.2f}", f"0…{CAP_T:.1f}"))
    for blk in cap["blocks"]:
        for rg in blk["regions"]:
            if rg.get("lead"):                  # inside its lip's row
                continue
            b = rg["box"]
            what = f"{blk['ua'] if U else blk['name']}: {rg['ua'] if U else rg['name']}"
            out.append((what, f"{b[0]:.2f}…{b[2]:.2f}", f"{b[1]:.2f}…{b[3]:.2f}", f"{CAP_T:.1f}…{CAP_T + rg['depth']:.1f}"))
        if blk["screw"]:
            su, sw = blk["screw"]
            what = (f"{blk['ua']}: саморіз {SCREW} крізь стелю" + (", під ним земля" if blk.get("ground") else "")
                    if U else f"{blk['name']}: {SCREW} screw through the top" + (", ground under it" if blk.get("ground") else ""))
            out.append((what, f"{su:.2f}", f"{TUBE_H - WALL:.2f}…{TUBE_H:.2f}", f"{sw:.2f}"))
    s = cap["saddle"]
    out.append(("сідло" if U else "the saddle", f"{s['u0']:.2f}…{s['u1']:.2f}", f"{s['v0']:.2f}…{s['v1']:.2f}", f"0…{s['l']:.1f}"))
    for h in s["holes"]:
        out.append((f"{h['ua'] if U else h['name']}: Ø{h['d']}, " + ("крапля, вістрям від фланця" if U else
                    "a teardrop, its point away from the flange"), f"{h['u']:.2f}", f"{s['v0']:.2f}…{s['v1']:.2f}",
                    f"{h['w']:.2f}"))
    return out


# ---- the drawing --------------------------------------------------------------------------------

def drawing(caps, m, lang="uk"):
    """caps.svg: each cap seen from outside, from below and in section through its left block's lips, with
    its sizes (mm: u, v from the flange's outer edges as seen from outside that end, w from its outer face).
    lang "en": caps_en.svg, the same drawing in English."""
    S = 2.0                                     # the scale: 2:1, on A2
    U = lang == "uk"
    o = []
    W, H = 594, 420
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}" '
             'font-family="Arial, sans-serif" fill="none" stroke="black" stroke-width="0.25">')
    o.append(f'<rect width="{W}" height="{H}" fill="white" stroke="none"/>')   # white on a dark viewer too
    o.append(f'<rect x="5" y="5" width="{W - 10}" height="{H - 10}" stroke-width="0.5"/>')

    def text(x, y, s, size=3.0, anchor="start", weight="normal"):
        o.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" '
                 f'fill="black" stroke="none">{s}</text>')

    def path(pts, x0, y0, dash=None, close=True, width=0.35):
        d = " ".join(f"{'M' if i == 0 else 'L'}{x0 + p[0] * S:.2f},{y0 - p[1] * S:.2f}" for i, p in enumerate(pts))
        z = " Z" if close else ""
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        o.append(f'<path d="{d}{z}" stroke-width="{width}"{dash_attr}/>')

    def dim_h(xa, xb, y, label, x0, y0):
        ya = y0 - y * S
        o.append(f'<line x1="{x0 + xa * S:.2f}" y1="{ya:.2f}" x2="{x0 + xb * S:.2f}" y2="{ya:.2f}" stroke-width="0.18" '
                 'marker-start="url(#a)" marker-end="url(#a)"/>')
        text(x0 + (xa + xb) / 2 * S, ya - 1.2, label, 2.6, "middle")

    def dim_v(ya, yb, x, label, x0, y0):
        xa = x0 + x * S
        o.append(f'<line x1="{xa:.2f}" y1="{y0 - ya * S:.2f}" x2="{xa:.2f}" y2="{y0 - yb * S:.2f}" stroke-width="0.18" '
                 'marker-start="url(#a)" marker-end="url(#a)"/>')
        o.append(f'<text x="{xa - 1.2:.2f}" y="{y0 - (ya + yb) / 2 * S:.2f}" font-size="2.6" text-anchor="middle" '
                 f'fill="black" stroke="none" transform="rotate(-90 {xa - 1.2:.2f} {y0 - (ya + yb) / 2 * S:.2f})">{label}</text>')

    DASH, DOT = "1.5,1", "3,1,0.5,1"
    o.append('<defs><marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" '
             'orient="auto-start-reverse"><path d="M0,2 L10,5 L0,8 z" fill="black" stroke="none"/></marker></defs>')
    text(12, 15, "MOST25-to-AUDIO listener v2.0: торцеві кришки труби 80×30×2 (gen_caps.py)" if U else
         "MOST25-to-AUDIO listener v2.0: the end caps of the 80×30×2 tube (gen_caps.py)", 5.0, weight="bold")
    text(12, 21, "Масштаб 2:1, розміри в мм. Вигляд — ззовні на свій торець; u від лівого зовнішнього краю фланця, v від "
         f"нижнього, w від зовнішньої грані всередину труби. Вирізи — деталь + {CLR} на бік, кути R {R_HOLE}; "
         "отвори SMA і RCA — різьба + стільки ж." if U else
         "Scale 2:1, mm. Each cap seen from outside its end; u from the flange's left outer edge, v from its bottom one, "
         f"w from its outer face into the tube. Openings: the part + {CLR} a side, corners R {R_HOLE}; the SMA's and "
         "the RCAs' holes: the thread + the same.", 3.0)
    O = flange_outline()
    low = 0.0                                   # the lowest the views reach: the notes go under it
    for k, cap in enumerate(caps):
        bx = 10 + k * 292
        ox, oy = bx + 42, 128                   # the front view's origin: the flange's outer bottom-left corner
        s = cap["saddle"]
        A0, A1, B0, B1, L = s["u0"], s["u1"], s["v0"], s["v1"], s["l"]
        if U:
            title = ("Вхідна кришка (J1, J5, J4, micro-USB M2, SMA)" if cap["cap"] == "input" else
                     "Вихідна кришка (J6, RCA J7…J9)")
        else:
            title = ("Input cap (J1, J5, J4, M2's micro-USB, SMA)" if cap["cap"] == "input" else
                     "Output cap (J6, RCA J7..J9)")
        text(bx + 6, 36, f"{title} — {cap['name']}", 4.2, weight="bold")
        text(bx + 6, 42, "вигляд ззовні (блоки — пунктир, торець плати — штрихпунктир)" if U else
             "seen from outside (blocks dashed, the board's end dash-dotted)", 3.0)
        path([(A0, B0), (A1, B0), (A1, B1)] + O[1:] + [O[0], (A0, B1)], ox, oy, width=0.5)
        inner = fillet(rect_poly((WALL, WALL, TUBE_W - WALL, TUBE_H - WALL)), [CORNER_R] * 4)
        path(inner, ox, oy, dash=DASH, width=0.2)
        bd = m["band"]
        path(rect_poly((bd[0], bd[2], bd[1], bd[3])), ox, oy, dash=DOT, width=0.2)
        for op in cap["openings"]:
            path(op["poly"], ox, oy, width=0.5)
        for blk in cap["blocks"]:
            for lp in union_loops(blk["regions"])[0]:
                path(lp, ox, oy, dash=DASH, width=0.3)
            if blk["screw"]:
                su = blk["screw"][0]
                x = ox + su * S
                o.append(f'<line x1="{x:.2f}" y1="{oy - (TUBE_H + 5) * S:.2f}" x2="{x:.2f}" y2="{oy - TUBE_H * S:.2f}" '
                         'stroke-width="0.25" marker-end="url(#a)"/>')
                path([(su, TUBE_H - WALL), (su, TUBE_H - SCREW_L)], ox, oy, dash=DASH, close=False, width=0.2)
                text(x, oy - (TUBE_H + 5.6) * S, SCREW + ((", земля" if U else ", ground") if blk.get("ground") else ""),
                     2.6, "middle")
        for h in s["holes"]:                    # through the saddle, upwards: hidden lines
            for e_ in (-1, 1):
                x = h["u"] + e_ * h["d"] / 2
                path([(x, B0), (x, B1)], ox, oy, dash=DASH, close=False, width=0.2)
        dim_h(0, TUBE_W, -5.0, f"{TUBE_W:.1f}", ox, oy)
        dim_h(A0, A1, -8.5, f"{A1 - A0:.1f}", ox, oy)
        dim_v(0, TUBE_H, -14.0, f"{TUBE_H:.1f}", ox, oy)
        dim_v(B0, B1, A1 + 2.5, f"{B1 - B0:.1f}", ox, oy)
        # the table
        ty = 160
        text(bx + 6, ty, "Розміри: що — u — v — w" if U else "Sizes: what — u — v — w", 3.0, weight="bold")
        rr = rows(cap, lang)
        for i, (what, u, v, w) in enumerate(rr):
            y = ty + 4.6 + 4.6 * i
            text(bx + 6, y, what, 2.5)
            text(bx + 130, y, u, 2.5)
            text(bx + 157, y, v, 2.5)
            text(bx + 181, y, w, 2.5)
        # the section through the left block's lips: w to the right (into the tube), v up
        blk = next(b for b in cap["blocks"] if b.get("hand") == "left")
        uc = R4(WALL + m["side"] + 0.4)
        sx, sy = bx + 205, ty + 6 + TUBE_H * S
        text(sx - 8, ty - 6, f"розріз при u = {uc:.2f} (всередину — праворуч)" if U else
             f"section at u = {uc:.2f} (inside to the right)", 2.8)
        cuts = []
        for op in cap["openings"]:
            vs = [q for q in crossings(op["poly"], uc)]
            cuts += [(vs[i], vs[i + 1]) for i in range(0, len(vs) - 1, 2)]
        cuts.sort()
        c0 = cuts[0][0] if cuts else TUBE_H
        path([(0, B0), (L, B0), (L, B1), (CAP_T, B1), (CAP_T, c0), (0, c0)], sx, sy, width=0.5)
        for i, (k0, k1) in enumerate(cuts):
            nxt = cuts[i + 1][0] if i + 1 < len(cuts) else TUBE_H
            path([(0, k1), (CAP_T, k1), (CAP_T, nxt), (0, nxt)], sx, sy, width=0.5)
        for rg in blk["regions"]:
            vs = crossings(rg["poly"], uc)
            for i in range(0, len(vs) - 1, 2):
                da, db = depth_at(rg, vs[i]), depth_at(rg, vs[i + 1])      # a lead-in's top slopes
                path([(CAP_T, vs[i]), (CAP_T + da, vs[i]), (CAP_T + db, vs[i + 1]), (CAP_T, vs[i + 1])], sx, sy, width=0.5)
                if not rg.get("lead"):
                    text(sx + (CAP_T + rg["depth"] + 0.6) * S, sy - (vs[i] + vs[i + 1]) / 2 * S + 1, f"{rg['depth']:.1f}", 2.4)
        zb, ztp = V(m["z"]), V(m["zt"])
        path([(CAP_T, zb), (CAP_T + 14, zb), (CAP_T + 14, ztp), (CAP_T, ztp)], sx, sy, dash=DASH, width=0.2)
        text(sx + (CAP_T + 14.5) * S, sy - (zb + 0.4) * S, f"плата: низ {m['z']:.2f} від дна труби" if U else
             f"board: {m['z']:.2f} above the floor", 2.5)
        for vv in (0, WALL, TUBE_H - WALL, TUBE_H):
            path([(CAP_T, vv), (CAP_T + 14, vv)], sx, sy, dash=DASH, close=False, width=0.15)
        text(sx + (CAP_T + 14.5) * S, sy - (WALL / 2) * S + 1, "стінка труби" if U else "tube wall", 2.4)
        text(sx + (L + 1.0) * S, sy - (B0 / 2) * S + 1, "сідло" if U else "saddle", 2.4)
        dim_h(0, CAP_T, -5.0, f"{CAP_T:.1f}", sx, sy)
        dim_h(0, L, -8.5, f"{L:.1f}", sx, sy)
        # the view from below: u as in the front view, w downwards from the outer face
        by = ty + 4.6 + 4.6 * len(rr) + 12
        text(bx + 6, by - 4, "вигляд знизу (зовнішня грань — угорі)" if U else "seen from below (the outer face at the top)", 3.0)
        bxy = lambda u, w: (ox + u * S, by + w * S)
        pts = [bxy(A0, 0), bxy(A1, 0), bxy(A1, L), bxy(A0, L)]
        o.append('<path d="' + " ".join(f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}" for i, (x, y) in enumerate(pts))
                 + ' Z" stroke-width="0.5"/>')
        x0_, y0_ = bxy(0, CAP_T)
        x1_, y1_ = bxy(TUBE_W, L)
        o.append(f'<path d="M{x0_:.2f},{y1_:.2f} L{x0_:.2f},{y0_:.2f} L{x1_:.2f},{y0_:.2f} L{x1_:.2f},{y1_:.2f}" '
                 f'stroke-width="0.2" stroke-dasharray="{DASH}"/>')       # the tube resting on it, and the flange's foot
        for h in s["holes"]:
            cx, cy = bxy(h["u"], h["w"])
            td = [bxy(u, w) for u, w in teardrop(h["u"], h["w"], h["d"])]
            o.append('<path d="' + " ".join(f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}" for i, (x, y) in enumerate(td))
                     + ' Z" stroke-width="0.4"/>')
            o.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{EAR_WASHER / 2 * S:.2f}" stroke-width="0.15" '
                     f'stroke-dasharray="{DASH}"/>')      # the washer under the head
            text(cx, cy + EAR_WASHER / 2 * S + 3.2, f"Ø{h['d']}", 2.4, "middle")
        xa = ox + A1 * S + 3
        o.append(f'<line x1="{xa:.2f}" y1="{by:.2f}" x2="{xa:.2f}" y2="{by + L * S:.2f}" stroke-width="0.18" '
                 'marker-start="url(#a)" marker-end="url(#a)"/>')
        text(xa + 1.2, by + L * S / 2 + 1, f"{L:.1f}", 2.6)
        low = max(low, by + L * S + 10, sy + 20)

    notes = notes_text(caps, m, lang)
    top = min(low + 8, H - 12 - 4.8 * len(notes))
    text(12, top - 5.5, "Примітки" if U else "Notes", 3.2, weight="bold")
    for i, s_ in enumerate(notes):
        text(12, top + 4.8 * i, s_, 3.0)
    o.append("</svg>")
    return "\n".join(o) + "\n"


def crossings(poly, u):
    """The v where a vertical line at u crosses a polygon's outline, sorted."""
    vs = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if (a[0] > u) != (b[0] > u):
            vs.append(a[1] + (u - a[0]) * (b[1] - a[1]) / (b[0] - a[0]))
    return sorted(vs)


def screws(caps):
    return [(c, b) for c in caps for b in c["blocks"] if b["screw"]]


def droop(m):
    """Upside down (the tube's top on the bench) the board hangs from the input cap's slots: the top parts its
    free end can droop onto first, their room under the tube's top, and the most the slots let it droop there.
    The underside, M2 and the pigtail, only moves away from the tube's floor."""
    pivot = m["x0"] + BLOCK_D - LEAD_IN
    first, best = [], math.inf
    for r, rects, za, zb in m["parts"]:
        if za < m["zt"] - 1e-6:
            continue
        far = max(rc[2] for rc in rects)
        if far <= pivot:
            continue
        a = (TUBE_H - 2 * WALL - zb) / (far - pivot)
        if a < best - 1e-4:
            first, best = [r], a
        elif a < best + 1e-4:
            first.append(r)
    room = TUBE_H - 2 * WALL - max(zb for r, _, _, zb in m["parts"] if r in first)
    return sorted(first), room, SLOT_PLAY / (BLOCK_D - LEAD_IN) * (m["x1"] - pivot)    # the slot full height over that


def notes_text(caps, m, lang):
    U = lang == "uk"
    sc = screws(caps)
    gb = next(b for c, b in sc if b.get("ground"))
    lips = {(c["name"], b["hand"]): b for c in caps for b in c["blocks"] if "hand" in b}
    il = lips[("in_cap", "left")]
    t, bt = il["lips"]["top"], il["lips"]["bottom"]
    vol = sum(c.get("volume", 0) for c in caps) / 1000
    rest, room, _ = droop(m)
    rest = "/".join(rest)
    slot = check_fit.PCB_T + SLOT_PLAY
    ax = (check_fit.RCA_AXIS_Z - check_fit.RCA_AXIS_TOL, check_fit.RCA_AXIS_Z + check_fit.RCA_AXIS_TOL)
    rh = (check_fit.RCA_HOLE, check_fit.RCA_HOLE + 2 * check_fit.RCA_AXIS_TOL)
    if U:
        return [
            "Друк: FDM із PETG або ASA (PLA у машині м'якне), або замовлення MJF PA12; зовнішньою гранню на стіл, без підтримок; "
            f"заповнення 100 % (саморізи йдуть у блоки): обидві кришки {vol:.1f} см³, близько {vol * PETG:.0f} г PETG.",
            f"Стінки не тонші {MIN_WEB} мм. Фланець {CAP_T} мм лягає на торець труби. Трубу 80×30×2 різати по запаяній платі: від її "
            f"вхідного торця до найдальшого з вихідного торця й передків RCA (номінал {m['tube_L']:.2f}), +{check_fit.TUBE_L_TOL}/−0 мм; "
            "торці рівні, без задирок.",
            f"Блоки — за {GAP_TUBE} від стінок, дна й стелі труби: труба в допуску входить без замірів. Плата: краї в пазах бічних "
            f"блоків (паз {slot:.1f} на плату {check_fit.PCB_T}, стійки за {BOARD_PLAY} від її країв, щоки з фаскою {LEAD_IN}×45° на кінці);",
            f"  нижня щока несе плату на висоті {m['z']:.2f} від дна, верхня тримає. Біля J1 щоки короткі ({t[1]:.1f} і {bt[1]:.1f} мм): "
            f"штир J1 за 1.55 від краю. Втулки RCA — у пази {rh[0]:.1f}×{rh[1]:.1f}: висоту осі BKL не задає ({ax[0]:.2f}…{ax[1]:.2f}).",
            "Складання: виводи обрізати, як у check_fit (M1 урівень, J4/J5 коротко до M2, тонкі виводи RCA до 2 мм). U.FL кабелю антени — на "
            "WROVER-IE модуля M2; кабель — повз антенний кінець модуля, не через екран,",
            f"  під платою до її краю y = 60, уздовж нього й через край угору до SMA, далі ніж за {BLOCK_D + CAP_T:.0f} мм від вхідного торця (за блоками); "
            "його й запас пласкою петлею приклеїти до низу плати. SMA — у вхідну кришку зсередини, зубчаста шайба й гайка ззовні; "
            "цю кришку надіти на вхідний кінець плати поза трубою.",
            "  Трубу покласти стелею донизу, плату — M2 догори; плату з кришкою всунути в трубу вихідним кінцем уперед: вільний кінець "
            f"ляже на корпуси {rest} ({room:.2f} від стелі), M2 і кабель ні на що не лягають.",
            "  Вихідну кришку надіти, тримаючи кінець плати за втулки RCA на висоті пазів; тоді перевернути. Щойно U.FL на місці, плата "
            f"ніколи не лягає на M2 (під кінцем WROVER-IE кабелю лишається {m['ufl_gap']:.2f} мм).",
            f"Фіксація: саморізи DIN 7981 C {SCREW} крізь стелю труби, {BLOCK_D / 2:.1f} мм від торця: отвір Ø{TUBE_HOLE} у трубі; фланець "
            f"урівень з контуром труби, у блок свердлити Ø{PILOT} рівно крізь отвір; затягнути до прилягання головки:",
            "  " + "; ".join(f"{'вхідна' if c['cap'] == 'input' else 'вихідна'} u {b['screw'][0]:.2f}" for c, b in sc)
            + " (u — від лівого краю, як дивитись ззовні на свій торець).",
            "Кріплення в машині: труба лежить на двох сідлах; чотири гвинти крізь вуха — саморізи ST4.2 (DIN 7981) або M4 в отвори "
            f"Ø{EAR_HOLE}, під головку шайба DIN 125 M4 (Ø{EAR_WASHER:.0f}).",
            f"Земля труби: кільцевий наконечник M2 і зубчаста шайба під саморіз блока заземлення (вхідна кришка, u {gb['screw'][0]:.2f}, "
            "над J4); провід 3–5 см",
            "  до мінуса джгута J4 біля колодки (пайка, термоусадка). Труба без покриття або зачищена під шайбою.",
            f"Антена: кабель U.FL–SMA {m['pigtail']} мм, будь-який з гніздом SMA на панель без фланця (шестигранник "
            f"{check_fit.SMA_NUT_AF:.0f} мм, різьба з лисками чи без): круглий отвір Ø{m['sma']['d']:.2f}, фланець {CAP_T} мм із "
            f"{check_fit.SMA_PANEL_MAX} допустимих.",
        ]
    return [
        "Print: FDM in PETG or ASA (PLA softens in a car), or order MJF PA12; the outer face on the bed, no supports; 100 % infill "
        f"(the screws go into the blocks): both caps {vol:.1f} cm³, about {vol * PETG:.0f} g of PETG.",
        f"No wall thinner than {MIN_WEB} mm. The {CAP_T} mm flange sits on the tube's end. Cut the 80×30×2 tube to the soldered "
        f"board: its input end to the farthest of its output end and the RCA fronts (nominally {m['tube_L']:.2f}), "
        f"+{check_fit.TUBE_L_TOL}/−0 mm; ends square and deburred.",
        f"The blocks stand {GAP_TUBE} off the tube's walls, floor and top: a tube in tolerance takes them unmeasured. The board: "
        f"its edges in the side blocks' slots ({slot:.1f} for the {check_fit.PCB_T} board, the posts {BOARD_PLAY} off its edges, "
        f"each lip's tip a {LEAD_IN}×45° lead-in);",
        f"  the lower lip carries it {m['z']:.2f} above the floor, the upper holds it. By J1 the lips are short ledges ({t[1]:.1f} "
        f"and {bt[1]:.1f} mm): J1's pin is 1.55 from the edge. The RCA bushings go through {rh[0]:.1f}×{rh[1]:.1f} slots: "
        f"BKL does not dimension the axis ({ax[0]:.2f}..{ax[1]:.2f}).",
        "Assembly: the leads cut as check_fit says (M1 flush, J4/J5 short before M2, the RCA thin pins to 2 mm). Clip the antenna "
        "pigtail's U.FL onto M2's WROVER-IE; lead the cable past the module's antenna end, not across its shield,",
        f"  under the board to its y = 60 edge, along it and round it up to the SMA beyond {BLOCK_D + CAP_T:.0f} mm from the input end "
        "(past the blocks); tape it and the spare, a flat loop, to the board's underside. The SMA into the input cap from inside, "
        "the lock washer and nut outside; that cap onto the board's input end, outside the tube.",
        "  Lay the tube on its top and the board M2 up; slide the board and cap in, output end first: the free end can droop onto "
        f"{rest} ({room:.2f} under the tube's top); M2 and the cable rest on nothing.",
        "  Fit the output cap, holding the board's end at the slots by the RCA bushings; then turn it over. Once the U.FL is on, "
        f"never let the board rest on M2 (the cable has {m['ufl_gap']:.2f} under the WROVER-IE's end).",
        f"Fixing: DIN 7981 C {SCREW} self-tapping screws through the tube's top, {BLOCK_D / 2:.1f} mm from its end: a Ø{TUBE_HOLE} "
        f"hole in the tube; the flange flush with the tube's outline, Ø{PILOT} drilled square through it into the block; tightened "
        "until the head seats:",
        "  " + "; ".join(f"{c['cap']} cap u {b['screw'][0]:.2f}" for c, b in sc)
        + " (u from the left edge, seen from outside that end).",
        "Mounting in the car: the tube rests on the two saddles; four screws through the ears, ST4.2 self-tapping (DIN 7981) or "
        f"M4 in the Ø{EAR_HOLE} holes, a DIN 125 M4 washer (Ø{EAR_WASHER:.0f}) under each head.",
        f"The tube's ground: an M2 ring terminal and a serrated washer under the ground block's screw (input cap, u "
        f"{gb['screw'][0]:.2f}, over J4); a 3–5 cm wire",
        "  to J4's harness ground next to the plug (soldered, heat-shrunk). The tube bare, or cleaned to metal under the washer.",
        f"Antenna: a {m['pigtail']} mm U.FL-to-SMA pigtail, any with a plain-hex panel jack ({check_fit.SMA_NUT_AF:.0f} mm, its "
        f"thread with flats or none): a round Ø{m['sma']['d']:.2f} hole, the flange {CAP_T} of the {check_fit.SMA_PANEL_MAX} it takes.",
    ]


def readme(caps, m):
    lines = []
    for c in caps:
        for what, u, v, w in rows(c, "en"):
            lines.append(f"| {c['name']} | {what} | {u.replace('…', '..')} | {v.replace('…', '..')} | {w.replace('…', '..')} |")
    table = "\n".join(lines)
    sc = screws(caps)
    gb = next(b for c, b in sc if b.get("ground"))
    lips = {(c["name"], b["hand"]): b for c in caps for b in c["blocks"] if "hand" in b}
    il, ir = lips[("in_cap", "left")], lips[("in_cap", "right")]
    t, bt = il["lips"]["top"], il["lips"]["bottom"]
    screw_lines = "\n".join(f"   - {c['name']}: u {b['screw'][0]:.2f}, {b['name']}" for c, b in sc)
    sma = m["sma"]
    vtop_ir = ir["regions"][0]["box"][3]
    gbox = gb["regions"][0]["box"]
    thin = "\n".join(f"  - {c['name']}: {c['thin'][0]:.2f} mm, {c['thin'][1]}" for c in caps)
    faces = "; ".join(f"{r}'s {d0:.2f}..{d1:.2f} (limit {lim:.2f})" for r, d0, d1, lim in m["faces"])
    usb0, usb1, usb_lim = m["usb_rec"]
    vols = " and ".join(f"{c['name']} {c['volume'] / 1000:.1f} cm3" for c in caps)
    grams = sum(c["volume"] for c in caps) / 1000 * PETG
    rest, room, most = droop(m)
    rest = "/".join(rest)
    ax = (check_fit.RCA_AXIS_Z - check_fit.RCA_AXIS_TOL, check_fit.RCA_AXIS_Z + check_fit.RCA_AXIS_TOL)
    rh = (check_fit.RCA_HOLE, check_fit.RCA_HOLE + 2 * check_fit.RCA_AXIS_TOL)
    grip = VT - screw_tip()
    min_wall = min(b["screw_wall"] for c, b in sc)
    tol = check_fit.TUBE_L_TOL
    return f"""# The end caps of listener v2.0's tube

Written by `gen_caps.py` from `check_fit.py`'s model of the board in the tube; do not edit by hand.

| File | What |
|---|---|
| `in_cap.step`, `in_cap.stl` | the cap at the input end (x = 0): J1, J5, J4, M2's micro-USB, the antenna's SMA |
| `out_cap.step`, `out_cap.stl` | the cap at the output end (x = 98): J6 and the RCA jacks J7..J9 |
| `caps.svg` | the drawing (A2, 2:1): both caps seen from outside, in section and from below, the sizes, the notes (in Ukrainian) |
| `caps_en.svg` | the same drawing in English |

The models are in the print's frame: the outer face on the bed (z = 0), the flange up to {CAP_T} mm, the
blocks above it to {CAP_T + BLOCK_D:.1f} mm, the saddle up to {CAP_T + SADDLE_L:.1f} mm; x runs to the left as seen from outside.

## The caps

- A flange of the tube's outline ({TUBE_W:.1f} x {TUBE_H:.1f} mm, corners R {R_OUT}), {CAP_T} mm thick, sits on the
  tube's end face; the board's ends butt against the flanges. The tube is as long as the soldered board
  between the flanges' bearing faces: from its input end to the farthest of its output end and the RCA
  housings' fronts (nominally {m['tube_L']:.2f} mm, the fronts {m['proud']:.2f} past the board's end by BKL's drawing),
  +{tol}/-0 mm, its ends square and deburred. The board then slides at most {tol} mm between the flanges;
  check_fit takes every face that much deeper.
- Each opening is its part's outline plus {CLR} mm a side, its corners R {R_HOLE} (a larger radius would
  bring a part's corner nearer than {CLR}); the SMA's hole and the RCA bushings' slots are the thread plus
  the same. No wall is thinner than {MIN_WEB} mm (three lines of a 0.4 mm nozzle). J5's frame and J4's face
  share one opening: the web between two would be thinner than that. The thinnest walls:
{thin}
- Through the flanges (check_fit, the board slid either way): J1's housing stands {m['j1_out'][0]:.2f}..{m['j1_out'][1]:.2f} mm out
  of the input cap. The faces sit inside their cap's outer face, mm: {faces};
  a TOSLINK face may sit as deep as the flange, its plug entering a jack-sized opening. M2's micro-USB
  is {usb0:.2f}..{usb1:.2f} mm behind the flange's inner face, the opening passing its plug's overmould to there
  (limit {usb_lim:.2f}); the opening is tall enough for the receptacle's unpublished height, {check_fit.M2_USB[2]}..{check_fit.M2_USB[3]} mm.
  The RCA threads stand {m['rca_out']:.2f} mm out of the output cap; the jacks go without nuts (their nut is
  wider than their pitch).
- The RCA bushings go through vertical slots {rh[0]:.2f} mm wide and {rh[1]:.2f} mm tall: BKL's TDS does not
  dimension the axis's height, which scales {ax[0]:.2f}..{ax[1]:.2f} mm above the board, so the slot keeps {CLR} mm
  round the thread anywhere in that range, with no jack measured.
- Each cap has a block in each side margin ({m['side']:.1f} mm, the board centred across); its post stands
  from the floor. Every block stands {GAP_TUBE} mm off the tube's walls, floor and top, rounded into its
  corners (inside R up to {CORNER_R}): an extruded tube's outside and walls are held only to a few tenths and
  FDM prints outer faces large, so any tube in tolerance takes the caps without being measured. The
  saddle sets the height; across the tube a cap shifts at most {GAP_TUBE} mm until its screws pin it. The
  post's face, {BOARD_PLAY} mm off the board's edge (JLCPCB's outline: +/-0.2), holds the board across. A lip
  under the edge carries the board's underside at {m['z']:.2f} mm above the tube's floor, a lip over it holds it
  down: the slot between them is {check_fit.PCB_T + SLOT_PLAY:.1f} mm for the {check_fit.PCB_T} board (JLCPCB: +/-10 %; FDM prints a slot
  narrow). Each lip's tip has a {LEAD_IN} x 45 degree lead-in toward the slot (it rises with the print: no
  overhang), so the board's end finds the slot from that far off. A lip reaches up to {LIP_MAX} mm in and
  runs the block's whole {BLOCK_D} mm depth where the parts and leads let it ({LIP_GAP} mm off a part's
  courtyard in plan, {LEAD_KEEP} mm off a soldered lead's centre on its solder side, {PEG_CLR} mm off a peg,
  {LIP_GAP} mm off a soldered pad on its part's side, {TOP_GAP} mm over a part or a lead's tip); where they do
  not, it is cut short to a ledge. At the input end's y = 0 corner J1's action pin (pad 0 at 3.50, 1.55)
  stands 1.55 mm from the board's edge, so that corner sits between a {t[0]:.2f} x {t[1]:.1f} mm ledge over the
  board and a {bt[0]:.2f} x {bt[1]:.1f} mm ledge under it (width x depth).
- The input cap's block on J4's side stops at v {vtop_ir:.2f}, {check_fit.SMA_GAP} mm under the SMA's body; it
  does not reach the tube's top, so it takes no screw. A third block stands over the board between
  J4's opening and the SMA (u {gbox[0]:.2f}..{gbox[2]:.2f}, from the tube's top down to v {gbox[1]:.2f}, {TOP_GAP} mm over
  M2's header tails, which stand {check_fit.LEADS[check_fit.DEVKIT][0]['pin'] - check_fit.PCB_T:.1f} mm up through the board there): it takes the input cap's second
  screw and the ground bond.
- Under the tube each flange runs on into a saddle, {SADDLE_T} mm thick and {SADDLE_L} mm along the tube
  from its end, with an ear {EAR} mm out on either side. The tube's floor rests on the two saddles, and
  four screws through the ears' {EAR_HOLE} mm holes hold the listener: DIN 7981 ST4.2 self-tapping (4.22 mm at
  most across the thread) or M4, a DIN 125 M4 washer ({EAR_WASHER:.0f} mm) under each head (PETG creeps under a
  bare head), which clears the tube's side by {EAR / 2 - EAR_WASHER / 2:.1f} mm. The ear holes lie horizontal in the print, so
  they are teardrops, their point away from the flange, cut flat at the circle's top. The saddle rises
  from the bed with the flange, so the caps print without supports.

Openings, blocks, screws and the saddle, mm, seen from outside that end: u from the flange's left edge,
v from its bottom edge, w from its outer face into the tube. At the input end the left side is the
board's y = 0 edge (J1's), at the output end its y = 60 edge (J8's). A lip's row gives the whole lip,
its lead-in included.

| Cap | What | u | v | w |
|---|---|---|---|---|
{table}

## Printing

- FDM in PETG or ASA (PLA softens in a parked car), or MJF PA12 from a print service; the outer face
  on the bed, no supports.
- 100 % infill: the screws are drilled into the blocks at assembly, and sparse infill round them would
  strip. The caps are {vols}, about {grams:.0f} g of PETG together.

## Assembly

1. Before the board goes in (check_fit's notes): the FPGA flashed before M1 is soldered in (the RCA
   housings cover its USB-C); M1's tails cut flush underneath and J4's and J5's leads cut short before M2
   goes on; M2 hangs component side down; the RCA jacks' thin pins trimmed to 2 mm.
2. Measure the soldered board from its input end to the farthest of its output end and the RCA
   housings' fronts, and cut the tube to that +{tol}/-0 mm. Drill {TUBE_HOLE} mm holes in its top for the screws
   (ISO 273 medium for 2 mm, so the screws do not tap the wall), {BLOCK_D / 2:.1f} mm from each end, at u from the
   left edge seen from outside that end:
{screw_lines}

   Not through the tube's sides: a screw head there stands in the way of a screwdriver on the ear
   below it ({EAR / 2:.1f} mm from the side).
3. The antenna pigtail: clip its U.FL onto M2's WROVER-IE (component side down, the plug at the module's
   antenna end). Lead the cable off past the module's antenna end, not across its shield, under the
   board to its y = 60 edge, along that edge toward the input end, and round the edge up to the SMA's
   place more than {BLOCK_D + CAP_T:.0f} mm from the input end, past the cap's blocks. Tape it, the spare as a flat
   loop along that edge, to the board's underside so that nothing hangs below M2. Put the SMA through the
   input cap from the inside, its internal-tooth lock washer and nut outside.
4. Fit the input cap onto the board's input end, outside the tube: J1's housing through its opening,
   the board's edges into the slots.
5. Lay the tube on its top, and the board with its M2 side up. Slide the board, the input cap trailing,
   into the tube from its input end, output end first, until the flange sits on the tube's end. The
   board hangs from the input cap's slots (their play would let its free end droop {most:.1f} mm), so it
   can only come down onto the tops of {rest}, {room:.2f} mm under the tube's top; M2 and the pigtail
   move away from the tube's floor and rest on nothing.
6. Fit the output cap, still upside down: hold the board's end at the slots' height by the RCA
   bushings, which stand out of the tube's end, put the cap's slots over them and push it home: J6 through
   its opening, the board's edges into the slots over the lead-ins. Turn the tube right way up.
7. Set each flange flush with the tube's outline (that centres its blocks), drill each block {PILOT} mm square
   through the tube's hole, about {grip + 1:.0f} mm deep (the thinnest wall round a pilot {min_wall:.2f} mm, the pilot off
   the hole's centre by {(TUBE_HOLE - PILOT) / 2:.1f}), and drive the four DIN 7981 C {SCREW} screws until their heads
   seat: the blocks stay up to {GAP_TUBE} mm under the tube's top, the screws pin the caps and do not pull
   them up. Each grips {grip:.1f} mm of its block, the ground screw {grip - GROUND_STACK:.1f} mm under its ring terminal
   and washer (see below).
8. Once the pigtail is plugged in, never let the board rest on M2: its EN/BOOT end lies {m['drop']:.2f} mm lower
   than the slots, and under the WROVER-IE's end the cable has only {m['ufl_gap']:.2f} mm with the caps on.

In the car: the tube's floor down on the two saddles, four screws through the ears.

## The ground bond

An M2 ring terminal and a serrated washer under the head of the ground block's screw (input cap, u
{gb['screw'][0]:.2f}, on the tube's top {BLOCK_D / 2:.1f} mm from its end, over J4), a 3-5 cm wire to the GND wire of J4's
harness by its plug (soldered, heat-shrunk). A raw tube, or its anodizing scraped off under the washer.

## The antenna

- A U.FL-to-SMA pigtail, {m['pigtail']} mm (check_fit's path from the panel to the U.FL's zone, +20 % for the
  bends), any whose SMA female bulkhead jack is the plain hex type, {check_fit.SMA_NUT_AF:.0f} mm across flats (a flanged or
  O-ring one, 11 across, does not fit the {m['side']:.0f} mm margin); its 1/4"-36 UNS-2A thread may be round or
  have flats. No particular one is chosen, so the hole is round, {sma['d']:.2f} mm (the thread's {SMA_THREAD} + {CLR} a
  side), in the input cap above the board in the margin on J4's side (centre u {sma['c'][0]:.2f}, v {sma['c'][1]:.2f}).
  The nut and the jack's internal-tooth lock washer outside keep it from turning; the flange is {CAP_T} mm,
  within the {check_fit.SMA_PANEL_MAX} mm panel limit of Amphenol's SMA-to-U.FL assemblies (the least found).
- Behind the panel the jack has room to w {sma['w1']:.2f} for its body, ferrule and boot: {sma['wall']:.2f} mm off the tube's
  wall ({sma['wall_min']:.2f} with its cap shifted against it), clear of the blocks and the parts.
- The cable's route is step 3 above; the WROVER-IE's U.FL spot is unverified (check_fit takes the
  module's last {check_fit.UFL_BACK} mm).
"""


# ---- main ---------------------------------------------------------------------------------------

def main() -> int:
    m = model()
    caps, fails, notes = design(m)
    out = {}
    for cap in caps:
        try:
            faces = solid(cap, CAP_T)
            data, tris = stl(faces, f"listener v2.0 {cap['name']}")
        except RuntimeError as err:
            fails.append(f"{cap['name']}: {err}")
            continue
        bad, vol = mesh_checks(tris)
        if bad:
            fails.append(f"{cap['name']}: the mesh is open at {len(bad)} edges")
        if vol <= 0:
            fails.append(f"{cap['name']}: the mesh is inside out")
        cap["volume"] = vol
        out[f"{cap['name']}.stl"] = data
        out[f"{cap['name']}.step"] = step(faces, cap["name"]).encode()
    for cap in caps:
        print(f"{cap['name']} ({cap['title']}): " + ", ".join(o["name"] for o in cap["openings"]))
        print(f"  the thinnest wall {cap['thin'][0]:.2f} ({cap['thin'][1]})" +
              (f"; the SMA's nut {cap['nut'][0]:.2f} off the next opening, {cap['nut'][1]:.2f} off the edge" if "nut" in cap else ""))
        for blk in cap["blocks"]:
            for rg in blk["regions"]:
                if rg.get("lead"):              # within its lip's box
                    continue
                b = rg["box"]
                line = (f"  {blk['name']}: {rg['name']} u {b[0]:.2f}..{b[2]:.2f}, v {b[1]:.2f}..{b[3]:.2f}, "
                        f"{rg['depth']:.1f} deep" + (f", a {LEAD_IN} lead-in at its tip" if "width" in rg else ""))
                if "width" in rg:
                    line += f", {rg['width']:.2f} over the board's edge; wider: {rg['why'][0]}"
                    if rg["why"][1]:
                        line += f"; deeper: {rg['why'][1]}"
                elif rg["why"] if isinstance(rg.get("why"), str) else rg.get("why", ("",))[0]:
                    line += f"; lower: {rg['why'][0]}"
                print(line)
            if blk["screw"]:
                grip = VT - screw_tip() - (GROUND_STACK if blk.get("ground") else 0.0)
                print(f"  {blk['name']}: {SCREW} screw through the tube's top at u {blk['screw'][0]:.2f}, w {blk['screw'][1]:.2f}, "
                      f"{grip:.1f} into the block" + (", the ground bond under its head" if blk.get("ground") else ""))
        if "volume" in cap:
            print(f"  {cap['volume'] / 1000:.2f} cm3")
    for n in notes:
        print("note:", n)
    for f in fails:
        print("FAIL:", f)
    if fails:
        print("nothing written")
        return 1
    out["caps.svg"] = drawing(caps, m).encode("utf-8")
    out["caps_en.svg"] = drawing(caps, m, "en").encode("utf-8")
    out["README.md"] = readme(caps, m).encode("utf-8")
    OUT.mkdir(exist_ok=True)
    for name, data in out.items():
        (OUT / name).write_bytes(data)
    print(f"wrote {len(out)} files to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
