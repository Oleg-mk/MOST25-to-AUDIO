#!/usr/bin/env python3
"""gen_listener2.py - the sheet of listener v2.0: the circuit of v1.6 on a compact board.

v2.0 is the same electronics on a board 60 x 98 mm, laid out anew (the user's decision of
2026-10-07): the inputs at one end (power J4, TOSLINK in J5, the ring's FOT J1), the outputs at
the other (TOSLINK out J6, the coax J7, the line out J8 and J9), M1 on top and M2 underneath, four
layers. The circuit is not drawn twice: this script loads listener_hw/gen_listener.py, the source
of v1.6's sheet, and writes its blocks as they are into this folder. What it changes describes
the board, not the circuit:
  * the project name (most_listener_v2) and its own UUIDs, so the two projects never mix;
  * the title block (rev 2.0);
  * the Tang Nano footprint's overhangs as the data sheet's photos show them: the HDMI about 4 mm
    past the module's end, the USB-C 2 mm (v1.6's fab text said 8 mm, which was never measured;
    JLR-MOST-Reader v2.0 found it);
  * J5/J6 are Cliff ORJ-8/OTJ-8 (FCR684208R/T) instead of ORJ-5/OTJ-5 (the user's decision of
    2026-10-07): the same pins, supply and speed, 10.0 mm high with no screw ear instead of 19.0.
    Their footprint and body are drawn here.
tools/check_v2_circuit.py holds the two sheets to the same parts and nets (J5/J6's part numbers and
footprint excepted), so the gateware, the firmware and kit/2_flash hold for v2.0 unchanged. v1.6's
files are not touched.

    python listener_hw2/gen_listener2.py
"""
from __future__ import annotations

import importlib.util
import uuid as _uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROJECT = "most_listener_v2"
DATE, REV = "2026-10-07", "2.0"
# the module as its data sheet v1.3 shows it (p.3-4 photos): USB-C 2.0 mm and HDMI about 4 mm past
# the PCB's ends
TANG_USB_OVER, TANG_HDMI_OVER = 2.0, 4.0
# J5/J6: Cliff ORJ-8 and OTJ-8, drawings FCR684208R and FCR684208T rev 2 (29/06/23). In the footprint's
# frame (origin at pin 2, the port towards +y): the metal pegs 2.60 and the plastic bosses 5.10 in front
# of the pins, the bosses 5.60 apart; the face 11.00 in front of the pins, the rear 2.50 behind them
FP_ORJ8, FP_ORJ5 = "Cliff_TOSLINK_ORJ8_OTJ8", "Cliff_TOSLINK_ORJ5_OTJ5"
ORJ8_MPN = {"J5": "FCR684208R", "J6": "FCR684208T"}
ORJ8_PEG, ORJ8_BOSS, ORJ8_BOSS_X = 2.60, 5.10, 2.80
ORJ8_FACE, ORJ8_REAR, ORJ8_HALF, ORJ8_CRT = 11.00, -2.50, 4.85, 0.15


def orj8_footprint(gen):
    """Cliff FCR684208R (ORJ-8, receiver) and FCR684208T (OTJ-8, transmitter) share the housing:
    their drawings (rev 2, 29/06/23, third-angle) give the rear, the side and the port face, and the
    PCB layout seen from the top. 3 pins 0.50 on 2.54 (0.80 holes: 0.9 here, as the other jacks);
    two metal pegs (copper alloy, tinned) in 1.10 holes on pin 1's and pin 3's lines, 2.60 in front
    of the pins: plated, no net, soldered for strength; two plastic snap bosses in 1.70 holes, 5.60
    apart, a further 2.50 forward; the face 5.90 past the bosses, 11.00 in front of the pins, with
    the board's edge there. The body is 9.70 wide, 13.50 deep and 10.00 high (its front 2.37 only
    8.87), with no screw ear; the optical axis is 4.37 up. Seen from the port the pins read 3 2 1
    from the left, so pin 1 is at +x, as on ORJ-5."""
    items = []
    for n, x in (("1", 2.54), ("2", 0.0), ("3", -2.54)):
        items.append(gen._fppad(n, "thru_hole", "rect" if n == "1" else "circle", x, 0, 1.6, 1.6, 0.9, f"orj8p{n}"))
    for i, x in enumerate((2.54, -2.54)):
        items.append(gen._fppad("", "thru_hole", "circle", x, ORJ8_PEG, 1.8, 1.8, 1.1, f"orj8m{i}"))
    for i, x in enumerate((ORJ8_BOSS_X, -ORJ8_BOSS_X)):
        items.append(gen._fppad("", "np_thru_hole", "circle", x, ORJ8_BOSS, 1.7, 1.7, 1.7, f"orj8b{i}"))
    x0, x1, y0, y1 = -ORJ8_HALF, ORJ8_HALF, ORJ8_REAR, ORJ8_FACE
    items.append(gen._fpbox(x0, y0, x1, y1, "F.Fab", 0.1, "orj8fab"))
    items.append(gen._fpl(x0, y1 - 2.37, x1, y1 - 2.37, "F.Fab", 0.1, "orj8step"))     # the lower front frame
    # silk on three sides: the sides end 0.65 behind the face
    ys = y1 - 0.65
    items.append(gen._fpl(x0 - 0.11, y0 - 0.11, x1 + 0.11, y0 - 0.11, "F.SilkS", 0.15, "orj8silk0"))
    items.append(gen._fpl(x0 - 0.11, y0 - 0.11, x0 - 0.11, ys, "F.SilkS", 0.15, "orj8silk1"))
    items.append(gen._fpl(x1 + 0.11, y0 - 0.11, x1 + 0.11, ys, "F.SilkS", 0.15, "orj8silk2"))
    items.append(gen._fpbox(x0 - ORJ8_CRT, y0 - ORJ8_CRT, x1 + ORJ8_CRT, y1 + ORJ8_CRT, "F.CrtYd", 0.05, "orj8crt"))
    items.append(gen._fptext("port: the face at the board edge", 0, y1 - 0.8, "F.Fab", 0.5, "orj8txt"))
    items.append(gen._fpdot(3.85, -1.3, "orj8pin1"))
    items.append(gen._own_model(FP_ORJ8))
    return gen._fp(FP_ORJ8, "Cliff FCR684208R (ORJ-8) receiver and FCR684208T (OTJ-8) transmitter, TOSLINK: 3 pins "
                   "on 2.54, pin 1 at +x; two metal pegs in 1.10 holes 2.60 in front of pins 1 and 3 (plated, no "
                   "net), two plastic bosses in 1.70 holes 5.60 apart 2.50 further; the port faces +y, the board's "
                   "edge at the face 11.00 in front of the pins; body 9.70 x 13.50 x 10.00, no screw ear; drawings "
                   "FCR684208R and FCR684208T rev 2", "TOSLINK Cliff FCR684208R FCR684208T ORJ8 OTJ8",
                   "through_hole", items, y0 - 1.6, y1 + 1.6)


def orj8_body(gen):
    """The ORJ-8/OTJ-8 housing in the footprint's frame (origin at pin 2, the port towards +y), from
    the same drawings: the block 9.70 x 13.50, 10.00 high, its front 2.37 only 8.87; the port dark
    round the optical axis 4.37 up; the pins 0.50 x 0.25 and the metal pegs 3.00 below the board,
    the plastic bosses about 1.7."""
    za, yf = 4.37, ORJ8_FACE
    solids = [(gen.BLACK, gen._box(-ORJ8_HALF, ORJ8_HALF, ORJ8_REAR, yf - 2.37, 0.0, 10.0)),
              (gen.BLACK, gen._box(-ORJ8_HALF, ORJ8_HALF, yf - 2.37, yf, 0.0, 8.87)),
              (gen.PORT_DARK, gen._box(-3.0, 3.0, yf, yf + 0.05, za - 2.8, za + 2.8))]
    for x in (-2.54, 0.0, 2.54):
        solids.append((gen.TIN, gen._box(x - 0.25, x + 0.25, -0.125, 0.125, -3.0, 0.0)))
    for x in (-2.54, 2.54):
        solids.append((gen.TIN, gen._cyl("z", (x, ORJ8_PEG), 0.45, -3.0, 0.0, 16)))
    for x in (-ORJ8_BOSS_X, ORJ8_BOSS_X):
        solids.append((gen.BLACK, gen._cyl("z", (x, ORJ8_BOSS), 0.8, -1.7, 0.0, 16)))
    return solids


def load_v1():
    spec = importlib.util.spec_from_file_location("gen_listener", ROOT / "listener_hw" / "gen_listener.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return gen


def patch(gen, here: Path):
    """Point v1.6's generator at this folder and give it v2.0's title and module footprint."""
    gen.HERE = here
    gen.PROJECT = PROJECT
    gen.NS = _uuid.UUID("7d2e9a41-6c3b-4f08-9e15-2a4b6c8d0e1f")     # v2.0's own UUIDs
    uid = gen.uid

    def write(self, path: Path):
        self.junctions()
        libs = "\n".join(sym.text for sym in self.used.values())
        body = "\n".join(self.items)
        path.write_text(
            f'(kicad_sch (version 20231120) (generator "gen_listener") '
            f'(generator_version "10.0") (uuid "{uid("root")}") (paper "A2")\n'
            f'(title_block (title "MOST25 to AUDIO: listener board v2.0") (date "{DATE}") '
            f'(rev "{REV}") (comment 1 "Generated by listener_hw2/gen_listener2.py from listener_hw/gen_listener.py: '
            f'the circuit of v1.6") '
            f'(comment 2 "Repeater with regeneration and a bypass watchdog; FPGA; ESP32 host; TDM, UART, I2S out; '
            f'S/PDIF in and out"))\n'
            f'(lib_symbols\n{libs}\n)\n{body}\n'
            f'(sheet_instances (path "/" (page "1")))\n)\n', encoding="utf-8")

    gen.Sheet.write = write
    v1_tang = gen.tangnano_footprint

    def tangnano_footprint():
        text = v1_tang()
        for old, new in (('"USB-C"', f'"USB-C, +{TANG_USB_OVER:g} mm"'),
                         ('"HDMI, +8 mm"', f'"HDMI, about +{TANG_HDMI_OVER:g} mm"'),
                         ("the HDMI connector overhangs the far end by 8 mm (data sheet v1.3 p.5, p.6)",
                          f"the HDMI connector overhangs the far end by about {TANG_HDMI_OVER:g} mm and the USB-C the "
                          f"near end by {TANG_USB_OVER:g} mm (data sheet v1.3 p.3-6)")):
            assert text.count(old) == 1, f"the Tang Nano footprint changed in gen_listener.py: {old}"
            text = text.replace(old, new)
        return text

    # J5/J6: ORJ-8/OTJ-8 - the same pins as ORJ-5/OTJ-5, so only the part numbers, the footprint and
    # the body change
    gen.S["TOSLINK_RX"] = gen.ic("FCR684208R", "J", 15.24, 12.7, [
        ("1", "VOUT", "output", "R", 3.81),
        ("3", "VCC", "power_in", "T", 7.62), ("2", "GND", "power_in", "B", 7.62),
    ], "TOSLINK receiver, 2.7-5.5 V, 16 Mbps (Cliff FCR684208R, ORJ-8: 1 Vout, 2 GND, 3 Vcc; the pegs unnumbered)")
    gen.S["TOSLINK_TX"] = gen.ic("FCR684208T", "J", 15.24, 12.7, [
        ("3", "VIN", "input", "L", 3.81),
        ("2", "VCC", "power_in", "T", 7.62), ("1", "GND", "power_in", "B", 7.62),
    ], "TOSLINK transmitter, 2.7-5.5 V, 16 Mbps (Cliff FCR684208T, OTJ-8: 1 GND, 2 Vcc, 3 Vin; the pegs unnumbered)")
    v1_at_pin, v1_text = gen.Sheet.at_pin, gen.Sheet.text

    def at_pin(self, key, ref, value, pin, target, r=0, **kw):
        return v1_at_pin(self, key, ref, ORJ8_MPN.get(ref, value), pin, target, r, **kw)

    def text(self, s, *a, **kw):
        return v1_text(self, s.replace("FCR684205R", ORJ8_MPN["J5"]).replace("FCR684205T", ORJ8_MPN["J6"]), *a, **kw)

    gen.Sheet.at_pin, gen.Sheet.text = at_pin, text
    assert gen.FP_CLIFF == FP_ORJ5, f"J5/J6's footprint changed in gen_listener.py: {gen.FP_CLIFF}"
    gen.FP_CLIFF = FP_ORJ8                                  # J5/J6 in the sheet, and the body main() writes
    gen.cliff_body = lambda: orj8_body(gen)
    new = {gen.FP_TANG: (gen.FP_TANG, tangnano_footprint), FP_ORJ5: (FP_ORJ8, lambda: orj8_footprint(gen))}
    gen.NEW_FOOTPRINTS = tuple(new.get(name, (name, make)) for name, make in gen.NEW_FOOTPRINTS)
    return gen


def main(here: Path = HERE):
    here.mkdir(exist_ok=True)
    patch(load_v1(), here).main()
    for old in (here / "most_listener.pretty" / f"{FP_ORJ5}.kicad_mod",       # J5/J6 up to 2026-10-07
                here / "most_listener.3dshapes" / f"{FP_ORJ5}.step"):
        if old.exists():
            old.unlink()


if __name__ == "__main__":
    main()
