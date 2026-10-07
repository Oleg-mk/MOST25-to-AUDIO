#!/usr/bin/env python3
"""check_v2_circuit.py - listener v2.0's sheet carries v1.6's circuit, part for part and net for net.

v2.0 is the same electronics on a compact board (listener_hw2/gen_listener2.py). Exports both sheets'
netlists with kicad-cli and compares every part (reference, value, footprint) and every net (its name
and the pins on it). The gateware, the firmware and the kit's builds, made for v1.6's pins, then hold
for v2.0 too. The parts v2.0 swaps on purpose (SWAPPED) must differ exactly as listed; their pins and
nets are held like every other part's.

    python tools/check_v2_circuit.py
    KICAD_CLI   kicad-cli, default %LOCALAPPDATA%/Programs/KiCad/10.0/bin/kicad-cli.exe
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHEETS = {"v1.6": ROOT / "listener_hw" / "most_listener.kicad_sch",
          "v2.0": ROOT / "listener_hw2" / "most_listener_v2.kicad_sch"}
KICAD_CLI = os.environ.get("KICAD_CLI", str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "KiCad" / "10.0"
                                              / "bin" / "kicad-cli.exe"))
# J5/J6: Cliff ORJ-8/OTJ-8 in v2.0 (2026-10-07) - the same pins, 10 mm high with no screw ear
FP5, FP8 = "most_listener:Cliff_TOSLINK_ORJ5_OTJ5", "most_listener:Cliff_TOSLINK_ORJ8_OTJ8"
SWAPPED = {"J5": (("FCR684205R", FP5), ("FCR684208R", FP8)),
           "J6": (("FCR684205T", FP5), ("FCR684208T", FP8))}


def circuit(sch: Path):
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "n.net"
        r = subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "--output", str(out),
                            str(sch)], capture_output=True, text=True)
        if r.returncode or not out.exists():
            sys.exit(f"kicad-cli netlist export failed for {sch.name}: " + r.stdout + r.stderr)
        text = out.read_text(encoding="utf-8")
    parts = {m[0]: (m[1], m[2]) for m in re.findall(
        r'\(comp\s*\(ref "([^"]+)"\)\s*\(value "([^"]*)"\)\s*\(footprint "([^"]*)"\)', text)}
    nets = {m.group(1): sorted(re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2)))
            for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', text[text.index("(nets"):],
                                 re.S)}
    return parts, nets


def main() -> int:
    (p1, n1), (p2, n2) = (circuit(s) for s in SHEETS.values())
    bad = [f"part {r}: v1.6 {p1.get(r)}, v2.0 {p2.get(r)}" for r in sorted(set(p1) | set(p2))
           if (p1.get(r), p2.get(r)) != SWAPPED.get(r, (p1.get(r), p1.get(r)))]
    bad += [f"net {n}: v1.6 {n1.get(n)}, v2.0 {n2.get(n)}" for n in sorted(set(n1) | set(n2)) if n1.get(n) != n2.get(n)]
    for b in bad[:20]:
        print(" ", b)
    print(f"{len(p1)} / {len(p2)} parts, {len(n1)} / {len(n2)} nets (v1.6 / v2.0): {len(bad)} differences")
    ok = not bad and p1 and n1
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
