#!/usr/bin/env python3
"""make_fab2.py - listener v2.0's manufacturing package, written into fab/ from
most_listener_v2.kicad_pcb and the sheet, for three assemblies:

  min  the core and the S/PDIF outputs: J7 (coax) and J6 (optical);
  mid  min and the line out: J8, J9;
  max  mid and the TOSLINK input: J5.

Every connector is fitted in all three (one case for all), so the assemblies differ only in the
parts behind the connectors (ASSEMBLIES below). The gateware and the firmware are the same for
all three: without the TOSLINK input's parts the host and the FPGA hold its lines at "no signal".

It loads listener_hw/make_fab.py and keeps its LCSC parts, JLCPCB's rotations, the silk check and
the date stamps, so v1.6 and v2.0 have one choice of parts. What differs: four copper layers,
parts and silk on both sides, the bottom's rotations as JLCPCB counts them, and one JLCPCB BOM and
CPL per assembly. Written into fab/:
  * the Gerbers (four copper layers; paste, silk and mask on both sides), both drill files, and a
    zip of them;
  * the BOM of every part, and the pick-and-place of both sides;
  * JLCPCB's BOM and CPL for each assembly;
  * the schematic, and the assembly drawings of the top and of the bottom (seen from below), as
    PDFs;
  * a README with the board's numbers, the assemblies and the order steps.
Every date KiCad writes becomes the board's title-block date, so the package is the same on
every run.

Run:  python make_fab2.py      (KiCad 10's kicad-cli; KICAD_CLI overrides its path)
"""
import csv
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NAME = "most_listener_v2"
PCB, SCH = HERE / f"{NAME}.kicad_pcb", HERE / f"{NAME}.kicad_sch"
OUT = HERE / "fab"


def load_v1():
    spec = importlib.util.spec_from_file_location("make_fab", ROOT / "listener_hw" / "make_fab.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


V1 = load_v1()
LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
GERBER = (".gtl", ".g1", ".g2", ".gbl", ".gtp", ".gbp", ".gto", ".gbo", ".gts", ".gbs", ".gm1", ".drl", ".gbrjob")

# The assemblies (2026-10-07). The optional parts are the ones behind the optional functions
# (the sheet's blocks 9 and 11); every other part, every connector among them, is in all three.
BLOCKS = {
    # J7, the coax (0.5 V on 75 ohm, ESD), and J6, the optical (its 33R and 100n, and U14 with its
    # two 1u, the 3V3_DA that J6 runs on)
    "S/PDIF out": "R26 R27 C29 D4 R28 C31 U14 C48 C49".split(),
    # U15 PCM5102A with U16 (its 3V3_DAC), U17 OPA1678 with U18 (its -5.2 V), the filters, the
    # decoupling and the jacks' ESD; R47/C84 and R48/C85 filter U17's rails (5V_A, VNEG_A), 2026-10-11
    "line out": ("U15 U16 U17 U18 C50 C51 C52 C53 C54 C55 C56 C57 C58 C59 C60 C61 C62 "
                 "C69 C70 C71 C72 C73 C74 C75 C76 C77 C78 C79 C84 C85 D5 D6 R32 R33 R43 R44 R45 R46 R47 R48").split(),
    # U12 DIR9001, U13 SRC4192 and its X1, J5's supply (FB3, C30), the PLL filter, the reset and
    # the 3V3_DA decoupling of the three
    "TOSLINK in": "U12 U13 X1 FB3 C27 C28 C30 C32 C33 C34 C35 C36 C37 C38 C39 C40 R24 R25 R29 R30".split(),
}
ASSEMBLIES = {"min": ("S/PDIF out",), "mid": ("S/PDIF out", "line out"),
              "max": ("S/PDIF out", "line out", "TOSLINK in")}

HAND_PARTS = {fp: what for fp, what in V1.HAND_PARTS.items() if fp != "Cliff_TOSLINK_ORJ5_OTJ5"}
HAND_PARTS["Cliff_TOSLINK_ORJ8_OTJ8"] = ("Cliff ORJ-8 / OTJ-8 (FCR684208R / FCR684208T), from DigiKey (not at "
                                        "LCSC)")


def ref_key(r):
    m = re.match(r"([A-Z]+)(\d+)", r)
    return (m.group(1), int(m.group(2))) if m else (r, 0)


def jlc_rotation(rot, side, turn):
    """JLCPCB's rotation of a part: KiCad's plus the part's turn on the top; on the bottom KiCad's
    is mirrored first, 180 - rot + turn, as JLCPCB counts the bottom (KiBot's mirror_bottom,
    kicad-jlcpcb-tools)."""
    return (rot + turn) % 360 if side == "top" else (180 - rot + turn) % 360


def jlc_files(out):
    """JLCPCB's BOM and CPL for each assembly, from KiCad's BOM and pick-and-place. Returns the
    hand-soldered and the consigned lines and each assembly's counts, for the README."""
    with (out / f"{NAME}-bom.csv").open(encoding="utf-8") as f:
        bom = list(csv.DictReader(f))
    with (out / f"{NAME}-pos.csv").open(encoding="utf-8") as f:
        pos = list(csv.DictReader(f))
    placed = {p["Ref"] for p in pos}
    optional = {r for refs in BLOCKS.values() for r in refs}
    stray = sorted(optional - placed, key=ref_key)
    if stray:
        sys.exit("the assemblies name parts JLCPCB does not place: " + " ".join(stray))
    lines, hand, consigned, missing = [], [], [], []
    for b in bom:
        fp = b["Footprint"].split(":")[-1]
        refs = b["Refs"].split(",")
        if not placed.intersection(refs):
            hand.append((b["Refs"], b["Value"], HAND_PARTS.get(fp, fp)))
            continue
        if (b["Value"], fp) not in V1.LCSC:
            missing.append(f"{b['Value']} ({fp})")
            continue
        code, part = V1.LCSC[(b["Value"], fp)]
        lines.append((b["Value"], refs, fp, code, part))
        if not code:
            consigned.append((b["Refs"], b["Value"]))
    if missing:
        sys.exit("no LCSC part chosen for: " + "; ".join(missing))
    code_of = {ref: code for _, refs, _, code, _ in lines for ref in refs}
    unread = {f"{code_of[p['Ref']]} ({p['Package']})" for p in pos
              if code_of[p["Ref"]] and code_of[p["Ref"]] not in V1.JLC_TURN and not V1.CHIP.match(p["Package"])}
    if unread:
        sys.exit("no JLCPCB rotation read for: " + "; ".join(sorted(unread)))
    counts = {}
    for name, blocks in ASSEMBLIES.items():
        dnp = optional - {r for blk in blocks for r in BLOCKS[blk]}
        rows = [(value, ",".join(r for r in refs if r not in dnp), fp, code, part)
                for value, refs, fp, code, part in lines if any(r not in dnp for r in refs)]
        with (out / f"{NAME}-bom-jlcpcb-{name}.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "Manufacturer Part"])
            w.writerows(rows)
        kept = [p for p in pos if p["Ref"] not in dnp]
        with (out / f"{NAME}-cpl-jlcpcb-{name}.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
            for p in kept:
                rot = jlc_rotation(float(p["Rot"]), p["Side"], V1.JLC_TURN.get(code_of[p["Ref"]], 0))
                w.writerow([p["Ref"], f"{float(p['PosX']):.4f}mm", f"{float(p['PosY']):.4f}mm",
                            "Top" if p["Side"] == "top" else "Bottom", f"{rot:g}"])
        counts[name] = {"lines": len(rows), "codes": len({r[3] for r in rows if r[3]}), "parts": len(kept),
                        "top": sum(p["Side"] == "top" for p in kept), "bottom": sum(p["Side"] != "top" for p in kept),
                        "dnp": len(dnp)}
    return {"hand": hand, "consigned": consigned, "assemblies": counts}


def copper(text):
    """The outer and the inner copper thickness from the board's stack-up, um."""
    th = {m.group(1): float(m.group(2)) for m in re.finditer(
        r'\(layer "([^"]+\.Cu)"\s+\(type "copper"\)\s+\(thickness ([\d.]+)\)', text)}
    return round(th["F.Cu"] * 1000), round(th["In1.Cu"] * 1000)


def readme(n, job, drills, jlc, cu):
    rules = job["DesignRules"][0]
    via = ", ".join(f"{s}/{d} mm" for (s, d), _ in n["vias"].most_common())
    nvia = sum(n["vias"].values())
    consigned = "; ".join(f"{refs} ({value})" for refs, value in jlc["consigned"])
    hand = "\n".join(f"   - {refs.replace(',', ', ')} ({value}): {part}" for refs, value, part in jlc["hand"])
    a = jlc["assemblies"]
    blocks = "\n".join(f"| {blk} | {' '.join(sorted(refs, key=ref_key))} |" for blk, refs in BLOCKS.items())
    rows = "\n".join(
        f"| **{name}** | {' + '.join(('the core',) + ASSEMBLIES[name])} | `{NAME}-bom-jlcpcb-{name}.csv`, "
        f"`{NAME}-cpl-jlcpcb-{name}.csv` | {c['parts']} ({c['top']} top, {c['bottom']} bottom) | {c['lines']} | "
        f"{c['dnp']} |" for name, c in a.items())
    return f"""# Manufacturing package: {n['title']}, rev {n['rev']} ({n['date']})

Written by `make_fab2.py` from `{NAME}.kicad_pcb` and the sheet; do not edit by hand. Run it
again after any change to the board or the sheet.

| File | What |
|---|---|
| `{NAME}-gerbers.zip` | everything below that the board house needs: the Gerbers, both drill files, the job file |
| `{NAME}-F_Cu.gtl`, `-In1_Cu.g1`, `-In2_Cu.g2`, `-B_Cu.gbl` | copper, top to bottom (In1 and In2 are the ground planes) |
| `{NAME}-F_Mask.gts`, `-B_Mask.gbs` | solder mask, top and bottom |
| `{NAME}-F_Silkscreen.gto`, `-B_Silkscreen.gbo` | silkscreen, top and bottom |
| `{NAME}-F_Paste.gtp`, `-B_Paste.gbp` | solder paste, top and bottom: SMD parts on both sides |
| `{NAME}-Edge_Cuts.gm1` | board outline |
| `{NAME}-PTH.drl`, `-NPTH.drl` | drill files, Excellon, mm: plated and non-plated holes |
| `{NAME}-job.gbrjob` | Gerber job file: the layers and the stack-up, for the board house's software |
| `{NAME}-bom.csv` | every part, grouped by value and footprint (the max assembly and the hand parts) |
| `{NAME}-pos.csv` | pick-and-place, SMD parts on both sides, mm, KiCad's rotations |
| `{NAME}-bom-jlcpcb-<assembly>.csv` | JLCPCB's BOM of one assembly: the parts it places, with their LCSC numbers |
| `{NAME}-cpl-jlcpcb-<assembly>.csv` | JLCPCB's pick-and-place of the same parts, JLCPCB's rotations |
| `{NAME}-schematic.pdf` | the schematic |
| `{NAME}-assembly-top.pdf`, `-assembly-bottom.pdf` | each side for assembly (the bottom seen from below): every reference, also those hidden on the silk, the polarity marks, the outline |

## The assemblies

One board and one case for all three: every connector is fitted in each. The assemblies differ
only in the parts behind the connectors, and the gateware and the firmware are the same.

| Assembly | Fitted | JLCPCB files | Parts JLCPCB places | BOM lines | Parts left off |
|---|---|---|---|---|---|
{rows}

The core is everything not listed below: power, the ring with its bypass and watchdog, M1 (the
FPGA), U7 (Si514), M2 (the host, Bluetooth in), J3 (I2S) and J2 (the analyser).

| Block | Its parts |
|---|---|
{blocks}

- **min.** J5 (TOSLINK in), J8 and J9 (line out) are fitted but not connected: J5 has no supply,
  and J8 and J9 no signal.
- **mid.** J5 is fitted but not connected, as in min.
- **max.** U13 (SRC4192) is most of the difference in price: LCSC had 8 on 2026-10-07. For more
  boards, consign the rest.

## The board

- {n['size'][0]:g} x {n['size'][1]:g} mm, {job['GeneralSpecs']['LayerNumber']} layers, FR-4 {n['thickness']} mm,
  {cu[0]} um copper outside and {cu[1]} um inside: JLCPCB's stack-up JLC04161H-7628 (prepreg 7628 between the
  outer and the inner layers). In1 and In2 are solid ground.
- Tracks from {n['min_track']} mm, clearance {rules['TrackToTrack']} mm; {nvia} vias of {via}.
- Smallest hole {n['min_hole']} mm; {drills['PTH']} plated and {drills['NPTH']} non-plated holes; {'slots' if n['slots'] else 'no slots'}.
- Solder mask and silkscreen on both sides; SMD parts on both sides.
- Surface finish ENIG: flat pads for U4/U11 (VSSOP-8, 0.5 mm pitch) and the exposed pads of U5
  (WSON-6, 2 x 2 mm) and U6 (HSOP-8).

## Notes for the parts

- U7, Si514: any 3.3 V CMOS variant off the shelf (format C, M or N), in the 3.2 x 5 (B) or
  2.5 x 3.2 (C) package, with any start-up frequency and I2C address - the FPGA finds the
  address and sets the frequency. Example: 514CBB000112BAG, which DigiKey sells singly and JLCPCB can pre-order (C1670489).
- C61, C62, C69..C72 (the line out's filter): C0G/NP0.
- X1: any 24.576 MHz 3.3 V CMOS oscillator in the 4-pin 3.2 x 2.5 mm package (1 OE, 2 GND,
  3 output, 4 VDD), as the Abracon ASE the footprint was drawn for.
- M1 (Tang Nano 20K, top) and M2 (ESP32-DevKitC-VIE, bottom) are soldered in on their own pin
  headers, 2 x 20 and 2 x 19 on 2.54 mm; no sockets. Solder M1 first and cut its pins flush on
  the bottom, then M2.
- J7..J9 (BKL 0101153): pad 3, the thin pin beside the axis, is not connected.

## Ordering at JLCPCB, with the SMD parts assembled

1. **PCB.** Upload `{NAME}-gerbers.zip`. Choose 4 layers, 1.6 mm, the stack-up JLC04161H-7628,
   1 oz outer and 0.5 oz inner copper, ENIG, green mask with white silkscreen, and 5 boards or
   more.
2. **Assembly.** Both sides, Standard PCBA (Economic assembles one side only), and "Confirm parts
   placement" on.
3. **BOM and CPL.** Upload the pair of the assembly you want, `{NAME}-bom-jlcpcb-<assembly>.csv`
   and `{NAME}-cpl-jlcpcb-<assembly>.csv`. The two files leave out the same parts, and nothing
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
5. **Consigned:** {consigned}. Send these to JLCPCB, or add them through its global sourcing.
   For the Si514, any code by the rule above.
6. **By hand, after delivery.** These are not in JLCPCB's files. Their holes follow these exact
   parts, so a look-alike may not fit:
{hand}
"""


def main():
    if not V1.KICAD.exists():
        sys.exit(f"kicad-cli not found: {V1.KICAD}")
    text = PCB.read_text(encoding="utf-8")
    # make_fab.py's silk check reads F.SilkS; the bottom's silk is held to the same sizes
    under = V1.silk_under(text.replace('"B.SilkS"', '"F.SilkS"'))
    if under:
        sys.exit(f"silkscreen under JLCPCB's {V1.SILK_TEXT}/{V1.SILK_LINE} mm: " + "; ".join(under[:20]) +
                 (f"; and {len(under) - 20} more" if len(under) > 20 else ""))
    n = V1.board_numbers(text)
    OUT.mkdir(exist_ok=True)
    for old in OUT.iterdir():
        old.unlink()
    run = V1.run
    run("pcb", "export", "gerbers", "--output", f"{OUT}{os.sep}", "--layers", LAYERS, "--check-zones", str(PCB))
    run("pcb", "export", "drill", "--output", f"{OUT}{os.sep}", "--format", "excellon", "--excellon-units", "mm",
        "--excellon-separate-th", str(PCB))
    run("pcb", "export", "pos", "--output", str(OUT / f"{NAME}-pos.csv"), "--side", "both", "--format", "csv",
        "--units", "mm", "--smd-only", str(PCB))
    run("sch", "export", "bom", "--output", str(OUT / f"{NAME}-bom.csv"),
        "--fields", "Reference,Value,Footprint,${QUANTITY}", "--labels", "Refs,Value,Footprint,Qty",
        "--group-by", "Value,Footprint", "--ref-range-delimiter", "", str(SCH))
    run("sch", "export", "pdf", "--black-and-white", "--output", str(OUT / f"{NAME}-schematic.pdf"), str(SCH))
    for side, layers, extra in (("top", "F.Fab,F.Silkscreen,Edge.Cuts", ()),
                                ("bottom", "B.Fab,B.Silkscreen,Edge.Cuts", ("--mirror",))):
        run("pcb", "export", "pdf", "--layers", layers, "--mode-single", "--scale", "0", *extra,
            "--exclude-value", "--black-and-white", "--output", str(OUT / f"{NAME}-assembly-{side}.pdf"), str(PCB))
    for p in OUT.glob("*.pdf"):
        V1.normalise_pdf(p, n["date"])
    fab = sorted(p for p in OUT.iterdir() if p.suffix in GERBER)
    for p in fab:
        V1.normalise(p, n["date"])
    for p in OUT.glob("*.csv"):
        p.write_text(p.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    jlc = jlc_files(OUT)
    V1.zip_files(OUT / f"{NAME}-gerbers.zip", fab, n["date"])
    job = json.loads((OUT / f"{NAME}-job.gbrjob").read_text(encoding="utf-8"))
    drills = {k: sum(1 for line in (OUT / f"{NAME}-{k}.drl").read_text(encoding="utf-8").splitlines()
                     if re.match(r"X-?[\d.]+Y-?[\d.]+$", line)) for k in ("PTH", "NPTH")}
    (OUT / "README.md").write_text(readme(n, job, drills, jlc, copper(text)), encoding="utf-8", newline="\n")
    print(f"wrote {len(list(OUT.iterdir()))} files to {OUT}: rev {n['rev']} of {n['date']}, "
          f"{drills['PTH']} plated and {drills['NPTH']} non-plated holes; "
          + ", ".join(f"{k}: {c['parts']} parts in {c['lines']} lines" for k, c in jlc["assemblies"].items()))


if __name__ == "__main__":
    main()
