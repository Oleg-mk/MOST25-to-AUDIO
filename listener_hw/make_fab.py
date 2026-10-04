#!/usr/bin/env python3
"""make_fab.py - the manufacturing package of the listener board, written into fab/ from
most_listener.kicad_pcb and the sheet:

  * the Gerbers and both drill files, plus a zip of them for the board house;
  * the BOM, grouped by value and footprint;
  * the pick-and-place file of the SMD parts;
  * the same BOM and pick-and-place in JLCPCB's format, for an order with SMD assembly: every
    SMD part carries the LCSC number chosen below, every rotation JLCPCB's correction;
  * the schematic as a PDF, and an assembly drawing of the top (every reference, the silk's
    hidden ones too, the polarity marks, the outline);
  * a README with the board's numbers, taken from the board itself, and the order steps.

Every date KiCad writes into these files becomes the board's title-block date. The package
is then the same on every run, and check_all.py fails as soon as it no longer matches the
board.

Run:  python make_fab.py      (KiCad 10's kicad-cli; KICAD_CLI overrides its path, as in
                               check_all.py)
"""
import csv
import json
import os
import re
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PCB, SCH = HERE / "most_listener.kicad_pcb", HERE / "most_listener.kicad_sch"
OUT = HERE / "fab"
KICAD = Path(os.environ.get("KICAD_CLI", Path(os.environ.get("LOCALAPPDATA", "")) /
                            "Programs" / "KiCad" / "10.0" / "bin" / "kicad-cli.exe"))
# no parts and no text on the bottom, so no bottom paste or silkscreen
LAYERS = "F.Cu,B.Cu,F.Paste,F.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})([T ])\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2})?")

# The part JLCPCB places for each BOM line (value, footprint) - chosen 2026-10-01 from JLCPCB's
# parts library: a basic part where one fits, the maker's own part for every IC. A BOM line
# missing here stops the script, so a new part cannot reach the order without a decision.
R, C6, C8, C12 = "R_0603_1608Metric", "C_0603_1608Metric", "C_0805_2012Metric", "C_1210_3225Metric"
LCSC = {
    ("10u 100V", C12): ("C576517", "Murata GRM32EC72A106KE05L, X7S"),
    ("100n 100V", C6): ("C15725", "Samsung CL10B104KC8NNNC, X7R"),
    ("2u2", C6): ("C23630", "Samsung CL10A225KO8NNNC, 16 V X5R"),
    ("4u7 100V", C12): ("C385986", "Taiyo Yuden HMK325C7475KMHPE, X7S"),
    ("100n", C6): ("C14663", "Yageo CC0603KRX7R9BB104, 50 V X7R"),
    ("47u 10V", C12): ("C77101", "Murata GRM32ER61C476KE15L, 16 V X5R"),
    ("1u", C6): ("C15849", "Samsung CL10A105KB8NNNC, 50 V X5R"),
    ("10u", C8): ("C15850", "Samsung CL21A106KAYNNNE, 25 V X5R"),
    ("10u 16V", C8): ("C15850", "Samsung CL21A106KAYNNNE, 25 V X5R"),
    ("10u 6V3", C8): ("C15850", "Samsung CL21A106KAYNNNE, 25 V X5R"),
    ("1n", C6): ("C1588", "Samsung CL10B102KB8NNNC, 50 V X7R"),
    ("68n", C6): ("C107098", "Yageo CC0603KRX7R9BB683, 50 V X7R"),
    ("4n7", C6): ("C53987", "FH 0603B472K500NT, 50 V X7R"),
    ("100u 63V", "CP_Elec_10x10.5"): ("C53330124", "SamYoung CLZ 63V 100uF 10x10, 125 C"),
    ("4u7", C8): ("C1779", "Samsung CL21A475KAQNNNE, 25 V X5R"),
    ("2n2", C6): ("C2991172", "FH 0603CG222J500NT, C0G"),
    ("100u 16V", "CP_Elec_6.3x7.7"): ("C359220", "SamYoung BLA 16V 100uF 6.3x6"),
    ("820p", C6): ("C99081", "FH 0603CG821J500NT, C0G"),
    ("390p", C6): ("C1667", "FH 0603CG391J500NT, C0G"),
    ("SS34", "D_SMA"): ("C8678", "MDD SS34"),
    ("SMBJ36A", "D_SMB"): ("C135070", "Diodes SMBJ36A-13-F"),
    ("PESD5V0S1BL", "D_SOD-882"): ("C84374", "Nexperia PESD5V0S1BL,315"),
    ("2A T", "Fuse_1206_3216Metric"): ("C2925010", "TLC F12T2, slow blow, 72 V"),
    ("600R", "L_0603_1608Metric"): ("C1002", "Sunlord GZ1608D601TF"),
    ("15u", "L_Bourns_SRN6045TA"): ("C1330797", "Bourns SRN6045TA-150M"),
    ("22u", "L_Bourns-SRN8040_8x8.15mm"): ("C2041547", "Bourns SRN8040-220M"),
    ("150", R): ("C22808", "UNI-ROYAL 0603WAF1500T5E"),
    ("27k", R): ("C22967", "UNI-ROYAL 0603WAF2702T5E"),
    ("100k", R): ("C25803", "UNI-ROYAL 0603WAF1003T5E"),
    ("23k2", R): ("C23346", "UNI-ROYAL 0603WAF2322T5E"),
    ("10k", R): ("C25804", "UNI-ROYAL 0603WAF1002T5E"),
    ("22", R): ("C23345", "UNI-ROYAL 0603WAF220JT5E"),
    ("2k", R): ("C22975", "UNI-ROYAL 0603WAF2001T5E"),
    ("33", R): ("C23140", "UNI-ROYAL 0603WAF330JT5E"),
    ("24k9 1%", R): ("C25962", "UNI-ROYAL 0603WAF2492T5E"),
    ("680", R): ("C23228", "UNI-ROYAL 0603WAF6800T5E"),
    ("100", R): ("C22775", "UNI-ROYAL 0603WAF1000T5E"),
    ("240", R): ("C23350", "UNI-ROYAL 0603WAF2400T5E"),
    ("110", R): ("C22781", "UNI-ROYAL 0603WAF1100T5E"),
    ("64k9 1%", R): ("C14891", "UNI-ROYAL 0603WAF6492T5E"),
    ("4k7", R): ("C23162", "UNI-ROYAL 0603WAF4701T5E"),
    ("74LVC1G34", "SOT-353_SC-70-5"): ("C353880", "TI SN74LVC1G34DCKR"),
    ("74LVC1G157", "SOT-363_SC-70-6"): ("C135822", "Nexperia 74LVC1G157GW,125"),
    ("74LVC1G125", "SOT-353_SC-70-5"): ("C7833", "TI SN74LVC1G125DCKR"),
    ("74LVC1G123", "VSSOP-8_2.3x2mm_P0.5mm"): ("C352969", "TI SN74LVC1G123DCUR"),
    ("TPS7B8133DRV", "WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm"): ("C2876250", "TI TPS7B8133DRVR"),
    ("LMR38020F", "Texas_HSOP-8-1EP_3.9x4.9mm_P1.27mm_ThermalVias"): ("C5149193", "TI LMR38020FDDAR"),
    ("Si514", "Si514_3.2x5_2.5x3.2"): ("", "Skyworks Si514, consigned (see the README)"),
    ("LP5907MFX-3.3", "SOT-23-5"): ("C130005", "TI LP5907QMFX-3.3Q1"),
    ("74LVC1G79", "SOT-353_SC-70-5"): ("C2677837", "TI SN74LVC1G79DCKR"),
    ("TPS2553DBVR", "SOT-23-6"): ("C55266", "TI TPS2553DBVR"),
    ("DIR9001", "TSSOP-28_4.4x9.7mm_P0.65mm"): ("C96215", "TI DIR9001PWR"),
    ("SRC4192", "SSOP-28_5.3x10.2mm_P0.65mm"): ("C2662561", "TI SRC4192IDBR"),
    ("PCM5102A", "TSSOP-20_4.4x6.5mm_P0.65mm"): ("C107671", "TI PCM5102APWR"),
    ("OPA1678", "SOIC-8_3.9x4.9mm_P1.27mm"): ("C192421", "TI OPA1678IDR"),
    ("TPS60403", "SOT-23-5"): ("C11338", "TI TPS60403DBVR"),
    ("24.576MHz", "Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm"): ("C2831388", "YXC OT322524.576MJBA4SL, 3.3 V CMOS"),
}
# JLCPCB's rotation minus KiCad's, by LCSC part: JLCPCB's zero is the part's own LCSC (EasyEDA)
# footprint, so each turn was read off that footprint, pad by pad against KiCad's (2026-10-03).
# Pin 1 bottom-right with the pins in columns, as LCSC draws these SOT-23-5/6, SOT-353 and
# SOT-363: 180. Pin 1 bottom-left with the pins in rows (U9's SC-70-5, the VSSOP-8, the TSSOPs,
# the SSOP, the SOIC and the HSOP-8, an ESOP-8 to LCSC): 270. U9 shares KiCad's footprint with U1
# and U3 but not LCSC's, so the key is the part. Drawn as KiCad's, 0: the WSON-6, X1, the
# electrolytics (+ on pad 1, left), the diodes (cathode on pad 1, left), the inductors, and every
# chip resistor, capacitor, bead and fuse (pads along X). The community table this replaces put
# the SOT-23s, U9 and the VSSOP-8s a quarter turn off and the electrolytics in reversed. A placed
# part neither listed nor a chip part stops the script.
JLC_TURN = {
    "C353880": 180, "C135822": 180, "C7833": 180, "C130005": 180, "C55266": 180, "C11338": 180,
    "C2677837": 270, "C352969": 270, "C5149193": 270, "C96215": 270, "C2662561": 270,
    "C107671": 270, "C192421": 270,
    "C2876250": 0, "C2831388": 0, "C53330124": 0, "C359220": 0, "C8678": 0, "C135070": 0,
    "C84374": 0, "C1330797": 0, "C2041547": 0,
}
CHIP = re.compile(r"^(R|C|L|Fuse)_\d{4}_\d{4}Metric$")


def run(*args):
    r = subprocess.run([str(KICAD), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"kicad-cli {' '.join(args[:3])} failed:\n{r.stdout}{r.stderr}")


def board_numbers(text):
    """What a board house asks for, read off the board file."""
    tb = re.search(r'\(title_block\s+\(title "([^"]*)"\)\s+\(date "([^"]*)"\)\s+\(rev "([^"]*)"\)', text)
    widths = [float(w) for w in re.findall(r'\(segment\s+\(start[^)]*\)\s+\(end[^)]*\)\s+\(width ([\d.]+)\)', text)]
    vias = Counter(re.findall(r'\(via(?:\s+\w+)?\s+\(at[^)]*\)\s+\(size ([\d.]+)\)\s+\(drill ([\d.]+)\)', text))
    holes = [float(d) for d in re.findall(r'\(drill ([\d.]+)\)', text)]
    edge = [tuple(map(float, m)) for m in re.findall(
        r'\(gr_line\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(stroke\s+\(width [\d.]+\)\s+'
        r'\(type \w+\)\s+\)\s+\(layer "Edge.Cuts"\)', text)]
    xs = [v for e in edge for v in (e[0], e[2])]
    ys = [v for e in edge for v in (e[1], e[3])]
    return {"size": (max(xs) - min(xs), max(ys) - min(ys)), "title": tb.group(1), "date": tb.group(2), "rev": tb.group(3),
            "thickness": float(re.search(r'\(general\s+\(thickness ([\d.]+)\)', text).group(1)),
            "min_track": min(widths), "vias": vias, "min_hole": min(holes),
            "slots": "drill oval" in text}


SILK_TEXT, SILK_LINE = 1.0, 0.15        # JLCPCB's least on silk: text height, and stroke and line width
TEXTS = ("property", "fp_text", "gr_text")
LINES = ("fp_line", "fp_rect", "fp_circle", "fp_arc", "fp_poly", "gr_line", "gr_rect", "gr_circle",
         "gr_arc", "gr_poly")


def silk_under(text):
    """Visible F.SilkS texts under SILK_TEXT high or SILK_LINE thick, and F.SilkS lines thinner
    than SILK_LINE: JLCPCB prints them blurred or not at all. KiCad's DRC checks the texts (the
    project's limits) but has no rule for the lines."""
    stack, cur = [], []
    for m in re.finditer(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text):
        t = m.group(0)
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(t)
    bad, owner = [], [""]

    def kid(node, name):
        return next((x for x in node if isinstance(x, list) and x and x[0] == name), None)

    def walk(node):
        if node[0] == "footprint":
            ref = next((x[2] for x in node if isinstance(x, list) and x[:2] == ["property", '"Reference"']), "")
            owner[0] = ref.strip('"')
        layer = kid(node, "layer")
        if layer and layer[1] == '"F.SilkS"':
            eff = kid(node, "effects")
            hidden = kid(node, "hide") in (["hide", "yes"],) or (eff is not None and "hide" in eff)
            if node[0] in TEXTS and eff is not None and not hidden:
                font = kid(eff, "font")
                size, thick = kid(font, "size"), kid(font, "thickness")
                if float(size[1]) < SILK_TEXT - 1e-6 or (thick and float(thick[1]) < SILK_LINE - 1e-6):
                    bad.append(f"text {node[2] if len(node) > 2 else ''} at {owner[0] or 'the board'}")
            elif node[0] in LINES:
                stroke = kid(node, "stroke")
                width = kid(stroke, "width") if stroke else kid(node, "width")
                if width and float(width[1]) < SILK_LINE - 1e-6:
                    bad.append(f"{node[0]} of {owner[0] or 'the board'}, {width[1]} mm")
        for x in node:
            if isinstance(x, list) and x:
                walk(x)
        if node[0] == "footprint":
            owner[0] = ""

    walk(cur[0])
    return bad


def normalise(path, date):
    """KiCad's creation stamps -> the board's date at midnight (UTC where a zone is given)."""
    t = path.read_text(encoding="utf-8")
    t = STAMP.sub(lambda m: f"{date}{m.group(2)}00:00:00" + ("+00:00" if m.group(3) else ""), t)
    path.write_text(t, encoding="utf-8", newline="\n")


def normalise_pdf(path, date):
    """KiCad's PDF creation stamp, (D:YYYY:MM:DD:hh:mm:ss), -> the board's date at midnight; the
    same length, so the PDF's offsets hold."""
    y, m, d = date.split("-")
    b = path.read_bytes()
    b = re.sub(rb"\(D:\d{4}:\d{2}:\d{2}:\d{2}:\d{2}:\d{2}\)", f"(D:{y}:{m}:{d}:00:00:00)".encode(), b)
    path.write_bytes(b)


def zip_files(target, files, date):
    stamp = tuple(int(v) for v in date.split("-")) + (0, 0, 0)
    with zipfile.ZipFile(target, "w") as z:
        for f in sorted(files, key=lambda p: p.name):
            info = zipfile.ZipInfo(f.name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, f.read_bytes())


# the parts soldered by hand after the boards arrive, by footprint: their holes follow these
# exact parts
HAND_PARTS = {
    "TE_MOST_Pigtail_FOT_2+0": "TE 1-1394640-1, the MOST pigtail FOT unit",
    "PinHeader_1x08_P2.54mm_Vertical": "pin header 1x08, 2.54 mm",
    "PinHeader_1x06_P2.54mm_Vertical": "pin header 1x06, 2.54 mm",
    "Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal": "Molex 43650-0200, Micro-Fit 3.0, right angle",
    "Cliff_TOSLINK_ORJ5_OTJ5": "Cliff ORJ-5 / OTJ-5 (FCR684205R / FCR684205T), from TME or Farnell (not at LCSC)",
    "BKL_0101153_RCA_RA": "BKL Electronic 0101153",
    "Sipeed_TangNano20K": "Sipeed Tang Nano 20K, on its own pin headers",
    "Espressif_ESP32-DevKitC_V4": "Espressif ESP32-DevKitC-VIE, on its own pin headers",
}


def jlc_files(out):
    """JLCPCB's BOM (Comment, Designator, Footprint, LCSC Part #) of the parts it places and its
    CPL (Designator, Mid X, Mid Y, Layer, Rotation), from KiCad's BOM and pick-and-place.
    Returns the hand-soldered and the consigned lines and the counts, for the README."""
    with (out / "most_listener-bom.csv").open(encoding="utf-8") as f:
        bom = list(csv.DictReader(f))
    with (out / "most_listener-pos.csv").open(encoding="utf-8") as f:
        pos = list(csv.DictReader(f))
    placed = {p["Ref"] for p in pos}
    rows, hand, consigned, missing = [], [], [], []
    for b in bom:
        fp = b["Footprint"].split(":")[-1]
        if not placed.intersection(b["Refs"].split(",")):
            hand.append((b["Refs"], b["Value"], HAND_PARTS.get(fp, fp)))
            continue
        if (b["Value"], fp) not in LCSC:
            missing.append(f"{b['Value']} ({fp})")
            continue
        code, part = LCSC[(b["Value"], fp)]
        rows.append((b["Value"], b["Refs"], fp, code, part))
        if not code:
            consigned.append((b["Refs"], b["Value"]))
    if missing:
        sys.exit("no LCSC part chosen for: " + "; ".join(missing))
    code_of = {ref: code for _, refs, _, code, _ in rows for ref in refs.split(",")}
    unread = {f"{code_of[p['Ref']]} ({p['Package']})" for p in pos
              if code_of[p["Ref"]] and code_of[p["Ref"]] not in JLC_TURN and not CHIP.match(p["Package"])}
    if unread:
        sys.exit("no JLCPCB rotation read for: " + "; ".join(sorted(unread)))
    with (out / "most_listener-bom-jlcpcb.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "Manufacturer Part"])
        w.writerows(rows)
    with (out / "most_listener-cpl-jlcpcb.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for p in pos:
            turn = JLC_TURN.get(code_of[p["Ref"]], 0)
            w.writerow([p["Ref"], f"{float(p['PosX']):.4f}mm", f"{float(p['PosY']):.4f}mm",
                        "Top" if p["Side"] == "top" else "Bottom", f"{(float(p['Rot']) + turn) % 360:g}"])
    return {"hand": hand, "consigned": consigned, "lines": len(rows), "codes": len({r[3] for r in rows if r[3]})}


def readme(n, job, drills, jlc):
    """The board's numbers, the notes the BOM's values do not carry, and the order steps."""
    rules = job["DesignRules"][0]
    via = ", ".join(f"{s}/{d} mm" for (s, d), _ in n["vias"].most_common())
    nvia = sum(n["vias"].values())
    consigned = "; ".join(f"{refs} ({value})" for refs, value in jlc["consigned"])
    hand = "\n".join(f"   - {refs.replace(',', ', ')} ({value}): {part}" for refs, value, part in jlc["hand"])
    return f"""# Manufacturing package: {n['title']}, rev {n['rev']} ({n['date']})

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
| `most_listener-schematic.pdf` | the schematic |
| `most_listener-assembly.pdf` | the top side for assembly: every reference (also those hidden on the silk), the polarity marks, the outline |

## The board

- {n['size'][0]:g} x {n['size'][1]:g} mm, {job['GeneralSpecs']['LayerNumber']} layers, FR-4 {n['thickness']} mm,
  35 um (1 oz) copper on both sides.
- Tracks from {n['min_track']} mm, clearance {rules['TrackToTrack']} mm; {nvia} vias of {via}.
- Smallest hole {n['min_hole']} mm; {drills['PTH']} plated and {drills['NPTH']} non-plated holes; {'slots' if n['slots'] else 'no slots'}.
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
   {jlc['lines']} lines, {jlc['codes']} LCSC parts.
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
5. **Consigned:** {consigned}. Send these to JLCPCB, or add them through its global sourcing.
   For the Si514, any code by the rule above.
6. **By hand, after delivery.** These are not in JLCPCB's files. Their holes follow these exact
   parts, so a look-alike may not fit:
{hand}
"""


def main():
    if not KICAD.exists():
        sys.exit(f"kicad-cli not found: {KICAD}")
    text = PCB.read_text(encoding="utf-8")
    under = silk_under(text)
    if under:
        sys.exit(f"silkscreen under JLCPCB's {SILK_TEXT}/{SILK_LINE} mm: " + "; ".join(under[:20]) +
                 (f"; and {len(under) - 20} more" if len(under) > 20 else ""))
    n = board_numbers(text)
    OUT.mkdir(exist_ok=True)
    for old in OUT.iterdir():
        old.unlink()
    run("pcb", "export", "gerbers", "--output", f"{OUT}{os.sep}", "--layers", LAYERS, "--check-zones", str(PCB))
    run("pcb", "export", "drill", "--output", f"{OUT}{os.sep}", "--format", "excellon", "--excellon-units", "mm",
        "--excellon-separate-th", str(PCB))
    run("pcb", "export", "pos", "--output", str(OUT / "most_listener-pos.csv"), "--side", "front", "--format", "csv",
        "--units", "mm", "--smd-only", str(PCB))
    run("sch", "export", "bom", "--output", str(OUT / "most_listener-bom.csv"),
        "--fields", "Reference,Value,Footprint,${QUANTITY}", "--labels", "Refs,Value,Footprint,Qty",
        "--group-by", "Value,Footprint", "--ref-range-delimiter", "", str(SCH))
    run("sch", "export", "pdf", "--black-and-white", "--output", str(OUT / "most_listener-schematic.pdf"), str(SCH))
    run("pcb", "export", "pdf", "--layers", "F.Fab,F.Silkscreen,Edge.Cuts", "--mode-single", "--scale", "0",
        "--exclude-value", "--black-and-white", "--output", str(OUT / "most_listener-assembly.pdf"), str(PCB))
    for p in OUT.glob("*.pdf"):
        normalise_pdf(p, n["date"])
    fab = sorted(p for p in OUT.iterdir() if p.suffix in (".gtl", ".gbl", ".gtp", ".gto", ".gts", ".gbs", ".gm1",
                                                         ".drl", ".gbrjob"))
    for p in fab:
        normalise(p, n["date"])
    for p in OUT.glob("*.csv"):
        p.write_text(p.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    jlc = jlc_files(OUT)
    zip_files(OUT / "most_listener-gerbers.zip", fab, n["date"])
    job = json.loads((OUT / "most_listener-job.gbrjob").read_text(encoding="utf-8"))
    drills = {k: sum(1 for line in (OUT / f"most_listener-{k}.drl").read_text(encoding="utf-8").splitlines()
                     if re.match(r"X-?[\d.]+Y-?[\d.]+$", line)) for k in ("PTH", "NPTH")}
    (OUT / "README.md").write_text(readme(n, job, drills, jlc), encoding="utf-8", newline="\n")
    print(f"wrote {len(list(OUT.iterdir()))} files to {OUT}: rev {n['rev']} of {n['date']}, "
          f"{drills['PTH']} plated and {drills['NPTH']} non-plated holes")


if __name__ == "__main__":
    main()
