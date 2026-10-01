#!/usr/bin/env python3
"""make_fab.py - the manufacturing package of the listener board, written into fab/ from
most_listener.kicad_pcb and the sheet:

  * the Gerbers and both drill files, plus a zip of them for the board house;
  * the BOM, grouped by value and footprint;
  * the pick-and-place file of the SMD parts;
  * a README with the board's numbers, taken from the board itself.

Every date KiCad writes into these files becomes the board's title-block date. The package
is then the same on every run, and check_all.py fails as soon as it no longer matches the
board.

Run:  python make_fab.py      (KiCad 10's kicad-cli; KICAD_CLI overrides its path, as in
                               check_all.py)
"""
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
    return {"size": (max(xs) - min(xs), max(ys) - min(ys)),"title": tb.group(1), "date": tb.group(2), "rev": tb.group(3),
            "thickness": float(re.search(r'\(general\s+\(thickness ([\d.]+)\)', text).group(1)),
            "min_track": min(widths), "vias": vias, "min_hole": min(holes),
            "slots": "drill oval" in text}


def normalise(path, date):
    """KiCad's creation stamps -> the board's date at midnight (UTC where a zone is given)."""
    t = path.read_text(encoding="utf-8")
    t = STAMP.sub(lambda m: f"{date}{m.group(2)}00:00:00" + ("+00:00" if m.group(3) else ""), t)
    path.write_text(t, encoding="utf-8", newline="\n")


def zip_files(target, files, date):
    stamp = tuple(int(v) for v in date.split("-")) + (0, 0, 0)
    with zipfile.ZipFile(target, "w") as z:
        for f in sorted(files, key=lambda p: p.name):
            info = zipfile.ZipInfo(f.name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, f.read_bytes())


def readme(n, job, drills):
    """The board's numbers and the notes the BOM's values do not carry."""
    rules = job["DesignRules"][0]
    via = ", ".join(f"{s}/{d} mm" for (s, d), _ in n["vias"].most_common())
    nvia = sum(n["vias"].values())
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
- X1: 24.576 MHz 3.3 V CMOS oscillator, Abracon ASE (3.2 x 2.5 mm).
- M1 (Tang Nano 20K) and M2 (ESP32-DevKitC-VIE) are soldered in on their own pin headers,
  2 x 20 and 2 x 19 on 2.54 mm; no sockets.
- J7..J9 (BKL 0101153): pad 3, the thin pin beside the axis, is not connected.
"""


def main():
    if not KICAD.exists():
        sys.exit(f"kicad-cli not found: {KICAD}")
    n = board_numbers(PCB.read_text(encoding="utf-8"))
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
    fab = sorted(p for p in OUT.iterdir() if p.suffix in (".gtl", ".gbl", ".gtp", ".gto", ".gts", ".gbs", ".gm1",
                                                         ".drl", ".gbrjob"))
    for p in fab:
        normalise(p, n["date"])
    for p in OUT.glob("*.csv"):
        p.write_text(p.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    zip_files(OUT / "most_listener-gerbers.zip", fab, n["date"])
    job = json.loads((OUT / "most_listener-job.gbrjob").read_text(encoding="utf-8"))
    drills = {k: sum(1 for line in (OUT / f"most_listener-{k}.drl").read_text(encoding="utf-8").splitlines()
                     if re.match(r"X-?[\d.]+Y-?[\d.]+$", line)) for k in ("PTH", "NPTH")}
    (OUT / "README.md").write_text(readme(n, job, drills), encoding="utf-8", newline="\n")
    print(f"wrote {len(list(OUT.iterdir()))} files to {OUT}: rev {n['rev']} of {n['date']}, "
          f"{drills['PTH']} plated and {drills['NPTH']} non-plated holes")


if __name__ == "__main__":
    main()
