#!/usr/bin/env python3
"""make_views.py - pictures of listener v2.0 for the README: the board in its tube, cut open; the closed
tube from its input end and from its output end; the board's underside.

As the reader's (reader_hw2/make_views.py). The caps come from gen_caps.py's own solids (from check_fit.py's
model, which must pass), moved into the board's 3D frame point by point, so no KiCad model rotation is
involved; the tube is an 80 x 30 x 2 prism as long as the board, its inside corners R 2.0 as check_fit takes
them. Plain bodies stand in where KiCad 10 has none:
  * the modules, whose footprints carry their headers only: M1's PCB with its HDMI and USB-C, M2's PCB with
    the WROVER-IE and the micro-USB, from check_fit's numbers;
  * the parts whose 3D file KiCad 10 does not ship (J4's Micro-Fit, L2, U6's HTSOP-8, the oscillator): a box
    over the part's fabrication outline, as tall as check_fit's height;
  * the antenna's SMA jack: its nut and thread outside the input cap.
A copy of the board with them on it goes to work/ (not in git), and kicad-cli renders it at BASIC quality
only (high quality froze the PC on 2026-10-06) into views/. The master is only read.

    "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" listener_hw2/make_views.py
"""
from __future__ import annotations

import contextlib
import io
import math
import subprocess
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_fit  # noqa: E402
import gen_caps  # noqa: E402

WORK = HERE / "work"
OUT = HERE / "views"
KICAD_CLI = Path(sys.executable).with_name("kicad-cli.exe")
MODELS_3D = Path(sys.executable).resolve().parents[1] / "share" / "kicad" / "3dmodels"
ALU = (0.55, 0.57, 0.60)
DARK = (0.12, 0.12, 0.12)               # the printed caps
BODY = (0.16, 0.16, 0.16)               # a part's stand-in box
METAL = (0.60, 0.61, 0.64)              # connector shells, the WROVER-IE's can (lighter renders white)
GOLD = (0.83, 0.69, 0.33)               # the SMA jack
TANG_RGB = (0.10, 0.36, 0.17)           # the Tang Nano's PCB, green as in the reader's pictures
DEVKIT_RGB = (0.08, 0.08, 0.09)         # the DevKitC's PCB, black
TUBE_R_OUT = 0.5                        # the tube's outer corners: gen_caps' flange outline
TANG_USB_REAR = 5.85                    # the USB-C's rear from M1's end (Sipeed's DXF as quoted, not confirmed)
M2_USB_BODY = (7.5, 5.0, 2.75)          # the micro-B receptacle: wide, deep, high (check_fit: 2.5..3.0 high)
SMA_NUT_T, SMA_OUT = 2.4, 6.5           # the SMA's nut thick, its thread out of the flange's outer face
ARC_N = 6                               # segments of a quarter round
ROUND_N = 24                            # segments of a round outline

# name, which tube, kicad-cli's camera
VIEWS = [
    ("listener_v2_in_tube.png", "cut", ["--side", "top", "--rotate", "-62,0,-28", "--perspective", "--zoom", "0.9"]),
    ("listener_v2_input_end.png", "closed", ["--side", "top", "--rotate", "-70,0,52", "--perspective", "--zoom", "0.9"]),
    ("listener_v2_output_end.png", "closed", ["--side", "top", "--rotate", "-70,0,-128", "--perspective", "--zoom", "0.9"]),
    ("listener_v2_underside.png", "none", ["--side", "bottom", "--zoom", "1.45"]),
]


def prism(outer, holes, x0, x1):
    """A profile in the (y, z) plane, outer loop counter-clockwise, holes clockwise, run along x."""
    P = lambda x, p: (round(x, 4), round(p[0], 4), round(p[1], 4))
    faces = [([P(x1, p) for p in outer], [[P(x1, p) for p in h] for h in holes]),
             ([P(x0, p) for p in outer[::-1]], [[P(x0, p) for p in h[::-1]] for h in holes])]
    for loop in [outer] + holes:
        for i, a in enumerate(loop):
            b = loop[(i + 1) % len(loop)]
            faces.append(([P(x0, a), P(x0, b), P(x1, b), P(x1, a)], []))
    return faces


def arc(cy, cz, r, a0, a1, n=ARC_N):
    return [(cy + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cz + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def rounded(y0, y1, z0, z1, r):
    """A rectangle in (y, z), counter-clockwise, its corners rounded."""
    return (arc(y1 - r, z0 + r, r, -90, 0) + arc(y1 - r, z1 - r, r, 0, 90)
            + arc(y0 + r, z1 - r, r, 90, 180) + arc(y0 + r, z0 + r, r, 180, 270))


def polygon(cy, cz, r, n, a0=0.0):
    return [(cy + r * math.cos(math.radians(a0 + 360 * i / n)), cz + r * math.sin(math.radians(a0 + 360 * i / n)))
            for i in range(n)]


def write_step(faces, name, rgb):
    text = gen_caps.step(faces, name, rgb).replace("listener v2.0 end cap, written by gen_caps.py",
                                                    "listener v2.0 view model, written by make_views.py")
    path = WORK / f"{name}.step"
    path.write_text(text, encoding="utf-8")
    return path


def resolve(model: str) -> Path:
    return Path(model.replace("${KICAD10_3DMODEL_DIR}", MODELS_3D.as_posix()).replace("${KIPRJMOD}", HERE.as_posix()))


def models():
    """Every added body as a STEP file in the board's 3D frame: x along the board from its input edge, y up
    the page from its top edge (pcbnew's -y), z up from its top face. Returns {ref: path} for each set."""
    with contextlib.redirect_stdout(io.StringIO()):
        m = gen_caps.model()
        caps, fails, _ = gen_caps.design(m)
    if fails:
        sys.exit("gen_caps.py fails: " + "; ".join(fails))
    c = check_fit
    L, W, s, zt, T, w = m["L"], m["W"], m["side"], m["zt"], c.CAP_T, c.WALL
    x0, y0 = m["x0"], m["y0"]
    zv = w + zt                          # the board's top face in a cap's v (from the tube's outer bottom)

    def pcb_box(rect, z0, z1):
        """A pcbnew rectangle (x0, y0, x1, y1), z0..z1 off the board's top face."""
        xa, ya, xb, yb = rect
        return prism([(-(yb - y0), z0), (-(ya - y0), z0), (-(ya - y0), z1), (-(yb - y0), z1)], [], xa - x0, xb - x0)

    common, sets = {}, {}
    # the caps: a cap's print frame is x = -u, y = v, z = w (depth from its outer face)
    to_board = {
        "input": lambda p: (p[2] - T, p[0] + w + s, p[1] - zv),
        "output": lambda p: (L + T - p[2], -p[0] - W - w - s, p[1] - zv),
    }
    capped = {}
    for cap in caps:
        f = to_board[cap["cap"]]
        faces = [([f(p) for p in outer], [[f(p) for p in h] for h in holes])
                 for outer, holes in gen_caps.solid(cap, T)]
        capped["V_" + cap["name"].upper()] = write_step(faces, f"view_{cap['name']}", DARK)
    # the SMA jack outside the input cap: its thread through the flange, the nut on its outer face
    su, sv = m["sma"]["c"]
    yc, zc = -su + w + s, sv - zv
    capped["V_SMA_THREAD"] = write_step(prism(polygon(yc, zc, c.SMA_THREAD / 2, ROUND_N), [], -T - SMA_OUT, 0.0),
                                        "view_sma_thread", GOLD)
    capped["V_SMA_NUT"] = write_step(prism(polygon(yc, zc, c.SMA_NUT_AF / math.sqrt(3), 6, 30.0), [],
                                           -T - SMA_NUT_T, -T), "view_sma_nut", GOLD)
    # the tube, closed and cut open (the floor and the wall along the board's top edge only)
    iy0, iy1, iz0, iz1 = -(W + s), s, -zt, c.TUBE_H - 2 * w - zt
    oy0, oy1, oz0, oz1 = iy0 - w, iy1 + w, iz0 - w, iz1 + w
    ri, ro = c.CORNER_R, TUBE_R_OUT
    closed = prism(rounded(oy0, oy1, oz0, oz1, ro), [rounded(iy0, iy1, iz0, iz1, ri)[::-1]], 0.0, L)
    cut = prism(arc(oy0 + ro, oz0 + ro, ro, 180, 270) + arc(oy1 - ro, oz0 + ro, ro, 270, 360)
                + arc(oy1 - ro, oz1 - ro, ro, 0, 90) + [(iy1, oz1)] + arc(iy1 - ri, iz0 + ri, ri, 0, -90)
                + [(oy0, iz0)], [], 0.0, L)
    sets["closed"] = {**capped, "V_TUBE": write_step(closed, "view_tube_closed", ALU)}
    sets["cut"] = {**capped, "V_TUBE": write_step(cut, "view_tube_cut", ALU)}
    sets["none"] = {}

    # the modules: their PCBs and largest parts (check_fit's numbers, as gen_caps.model takes them)
    b = pcbnew.LoadBoard(str(c.BOARD))
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    m1, m2 = c.Frame(fps[m["refs"]["M1"]], "20", "1", "21"), c.Frame(fps[m["refs"]["M2"]], "19", "1", "20")
    e_usb, e_hdmi = m1.half + c.TANG_END[0], -m1.half - c.TANG_END[1]
    za = c.TANG_HEADER                   # M1's PCB on its header's plastic
    zb = za + c.TANG_PCB_T
    front = e_hdmi - c.TANG_HDMI[0]
    bodies = [
        ("V_M1_PCB", TANG_RGB, m1.rect(e_hdmi, e_usb, -c.TANG_HALF_W, c.TANG_HALF_W), za, zb),
        ("V_M1_HDMI", METAL, m1.rect(front, front + c.TANG_HDMI[1], -c.TANG_HDMI[2] / 2, c.TANG_HDMI[2] / 2),
         zb, zb + c.TANG_HDMI[3]),
        ("V_M1_USBC", METAL, m1.rect(e_usb - TANG_USB_REAR, e_usb + c.TANG_USB[0], -c.TANG_USB[1] / 2, c.TANG_USB[1] / 2),
         zb, zb + c.TANG_USB[2]),
    ]
    zback = -c.PCB_T - c.M2_HEADER       # M2's back, under its header's plastic; its parts face down
    zcomp = zback - c.M2_PCB_T
    wr_end = c.M2_HALF[0] + c.M2_WROVER[2]
    usb_front = -c.M2_HALF[0] - c.M2_USB[1]
    bodies += [
        ("V_M2_PCB", DEVKIT_RGB, m2.rect(-c.M2_HALF[0], c.M2_HALF[0], -c.M2_HALF[1], c.M2_HALF[1]), zcomp, zback),
        ("V_M2_WROVER", METAL, m2.rect(wr_end - c.M2_WROVER[0], wr_end, -c.M2_WROVER[1] / 2, c.M2_WROVER[1] / 2),
         zcomp - c.M2_WROVER[3], zcomp),
        ("V_M2_USB", METAL, m2.rect(usb_front, usb_front + M2_USB_BODY[1], -M2_USB_BODY[0] / 2, M2_USB_BODY[0] / 2),
         zcomp - M2_USB_BODY[2], zcomp),
    ]
    # the parts whose 3D file KiCad does not ship: a box over the fabrication outline
    for ref, fp in sorted(fps.items()):
        files = [md.m_Filename for md in fp.Models()]
        if not files or any(resolve(f).exists() for f in files):
            continue
        layer = pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab
        shapes = [g.GetBoundingBox() for g in fp.GraphicalItems()
                  if g.GetLayer() == layer and not isinstance(g, pcbnew.PCB_TEXT)]
        if not shapes:
            sys.exit(f"{ref} has no 3D body and no fabrication outline")
        mm = pcbnew.ToMM
        rect = (min(mm(g.GetLeft()) for g in shapes), min(mm(g.GetTop()) for g in shapes),
                max(mm(g.GetRight()) for g in shapes), max(mm(g.GetBottom()) for g in shapes))
        h = c.HEIGHT[str(fp.GetFPID().GetLibItemName())][0]
        z = (-c.PCB_T - h, -c.PCB_T) if fp.IsFlipped() else (0.0, h)
        bodies.append((f"V_{ref}", BODY, rect, *z))
        print(f"{ref}: no 3D body in KiCad's library, a box {rect[2] - rect[0]:.2f} x {rect[3] - rect[1]:.2f} x {h:.2f}")
    for ref, rgb, rect, z0, z1 in bodies:
        common[ref] = write_step(pcb_box(rect, z0, z1), f"view_{ref[2:].lower()}", rgb)
    return {k: {**common, **v} for k, v in sets.items()}


def view_board(paths, tube):
    b = pcbnew.LoadBoard(str(check_fit.BOARD))
    mm, I = pcbnew.ToMM, pcbnew.FromMM
    ends = [(mm(q.x), mm(q.y)) for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts
            for q in (d.GetStart(), d.GetEnd())]
    x0, y0 = min(e[0] for e in ends), min(e[1] for e in ends)
    for ref, path in sorted(paths.items()):
        fp = pcbnew.FOOTPRINT(b)
        fp.SetReference(ref)
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        fp.SetPosition(pcbnew.VECTOR2I(I(x0), I(y0)))
        md = pcbnew.FP_3DMODEL()
        md.m_Filename = path.as_posix()
        md.m_Scale = pcbnew.VECTOR3D(1, 1, 1)
        fp.Add3DModel(md)
        fp.SetBoardOnly(True)
        fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)
        b.Add(fp)
    out = WORK / f"view_{tube}.kicad_pcb"
    pcbnew.SaveBoard(str(out), b)
    # the project's own models by their full path: ${KIPRJMOD} would be work/ here
    text = out.read_text(encoding="utf-8")
    out.write_text(text.replace("${KIPRJMOD}/", HERE.as_posix() + "/"), encoding="utf-8", newline="\n")
    return out


def main() -> int:
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    sets = models()
    boards = {}
    for name, tube, cam in VIEWS:            # one render at a time
        if tube not in boards:
            boards[tube] = view_board(sets[tube], tube)
        cmd = [str(KICAD_CLI), "pcb", "render", "--quality", "basic", "--background", "opaque",
               "--width", "1600", "--height", "900", *cam, "-o", str(OUT / name), str(boards[tube])]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            print(r.stdout, r.stderr)
            return 1
        print(f"views/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
