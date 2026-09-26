#!/usr/bin/env python3
"""gen_listener.py - the MOST25 to AUDIO listener board, rev 0.2, as one KiCad 10 sheet.

Drawn for a reader, not for a netlister:
  * parts sit where the signal goes, in framed, numbered blocks;
  * inside a block parts are joined by real wires, laid out so they do not cross;
  * net labels are used only where a signal leaves its block;
  * rails are power symbols; junction dots are placed automatically.

Every pinout below was checked against the maker's data sheet:
  74LVC1G34 / 74LVC1G125 / 74LVC1G157 / 74LVC1G123 /
  74LVC1G79                                        - Nexperia data sheets
  Si514 (6-pin: 1 SDA, 2 SCL, 3 GND, 4 CLK+,
         5 CLK-, 6 VDD)                            - Skyworks Si514 data sheet Rev 1.2
  TPS7B8133DRV, LMR33630ADDA, LP5907MFX            - KiCad 10 library symbols
  TPS2553DBV (1 IN, 2 GND, 3 EN, 4 FAULT, 5 ILIM,
              6 OUT)                               - TI SLVS841F
  ESP32-DevKitC V4 headers (J2 = pads 1..19,
                            J3 = pads 20..38)     - Espressif ESP32-DevKitC user
                                                     guide and dimension drawing
                                                     (rows 25.40 mm apart)
  TE 1-1394640-1 (MOST FOT header)                 - usb2most v3 schematic, a
                                                     board proven on a real car;
                                                     Rext and supply filters per
                                                     Avago AN 5344 / AFBR-1013 data sheet
  Tang Nano 20K header pads                        - Sipeed pin label drawing
Pin ORDER on the custom symbols is chosen for the drawing; pin NUMBERS are the
data-sheet ones.

Run:  python gen_listener.py      (writes most_listener.kicad_sch next to it)
"""
from __future__ import annotations

import math
import re
import uuid as _uuid
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
KLIB = Path(r"C:\Users\geniy\AppData\Local\Programs\KiCad\10.0\share\kicad\symbols")
PROJECT = "most_listener"
LIB = "most_listener"
NS = _uuid.UUID("3b1c7a52-9d0e-4f61-a2b3-5c4d6e7f8091")
FONT = 1.27
G = 2.54


def uid(key: str) -> str:
    return str(_uuid.uuid5(NS, key))


def f(v: float) -> str:
    s = ("%.3f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def eff(size=FONT, hide=False, justify=None):
    j = f" (justify {justify})" if justify else ""
    h = " (hide yes)" if hide else ""
    return f"(effects (font (size {f(size)} {f(size)})){j}{h})"


# ------------------------------------------------------------------ symbols
class Sym:
    """A library symbol: s-expression, pin table {number: (x, y)}, body box."""

    def __init__(self, lib_id, text, pins, box=None, valpos="below"):
        self.lib_id, self.text, self.pins, self.box = lib_id, text, pins, box
        self.valpos = valpos


PIN_RE = re.compile(
    r'\(pin \S+ \S+\s*\(at ([-\d.]+) ([-\d.]+) [-\d.]+\).*?\(number "([^"]+)"', re.S)


def from_kicad(libfile: str, name: str) -> Sym:
    text = (KLIB / f"{libfile}.kicad_sym").read_text(encoding="utf-8")
    start = text.index(f'\n\t(symbol "{name}"\n') + 1
    depth, i = 0, start
    while True:
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    block = text[start:i + 1]
    pins = {m.group(3): (float(m.group(1)), float(m.group(2)))
            for m in PIN_RE.finditer(block)}
    block = block.replace(f'(symbol "{name}"', f'(symbol "{libfile}:{name}"', 1)
    return Sym(f"{libfile}:{name}", block, pins)


def ic(name, ref, w, h, pins, desc=""):
    """Rectangular part centred on the origin. pins: (num, name, type, side, off).
    side L/R/T/B; off runs down (L/R) or right (T/B) from the top-left corner."""
    x0, y0 = -w / 2, h / 2          # library y points up
    table, out = {}, []
    for num, pname, ptype, side, off in pins:
        if side == "L":
            x, y, a = x0 - G, y0 - off, 0
        elif side == "R":
            x, y, a = -x0 + G, y0 - off, 180
        elif side == "T":
            x, y, a = x0 + off, y0 + G, 270
        else:
            x, y, a = x0 + off, -y0 - G, 90
        table[num] = (x, y)
        out.append(f'(pin {ptype} line (at {f(x)} {f(y)} {a}) (length 2.54) '
                   f'(name "{pname}" {eff()}) (number "{num}" {eff()}))')
    text = (
        f'(symbol "{LIB}:{name}" (pin_names (offset 0.508)) (exclude_from_sim no) '
        f'(in_bom yes) (on_board yes)\n'
        f'  (property "Reference" "{ref}" (at {f(x0)} {f(y0 + 1.27)} 0) {eff(justify="left bottom")})\n'
        f'  (property "Value" "{name}" (at {f(x0)} {f(-y0 - 1.27)} 0) {eff(justify="left top")})\n'
        f'  (property "Footprint" "" (at 0 0 0) {eff(hide=True)})\n'
        f'  (property "Datasheet" "" (at 0 0 0) {eff(hide=True)})\n'
        f'  (property "Description" "{desc}" (at 0 0 0) {eff(hide=True)})\n'
        f'  (symbol "{name}_0_1" (rectangle (start {f(x0)} {f(y0)}) (end {f(-x0)} {f(-y0)}) '
        f'(stroke (width 0.254) (type default)) (fill (type background))))\n'
        f'  (symbol "{name}_1_1" ' + " ".join(out) + "))")
    return Sym(f"{LIB}:{name}", text, table, (w, h))


def rail(name):
    text = (
        f'(symbol "{LIB}:{name}" (power) (pin_names (offset 0) (hide yes)) '
        f'(exclude_from_sim no) (in_bom no) (on_board yes)\n'
        f'  (property "Reference" "#PWR" (at 0 -3.81 0) {eff(hide=True)})\n'
        f'  (property "Value" "{name}" (at 0 3.556 0) {eff()})\n'
        f'  (property "Footprint" "" (at 0 0 0) {eff(hide=True)})\n'
        f'  (property "Datasheet" "" (at 0 0 0) {eff(hide=True)})\n'
        f'  (symbol "{name}_0_1" (polyline (pts (xy -0.762 1.27) (xy 0 2.54)) '
        f'(stroke (width 0) (type default)) (fill (type none))) '
        f'(polyline (pts (xy 0 0) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none))) '
        f'(polyline (pts (xy 0 2.54) (xy 0.762 1.27)) (stroke (width 0) (type default)) (fill (type none))))\n'
        f'  (symbol "{name}_1_1" (pin power_in line (at 0 0 90) (length 0) (hide yes) '
        f'(name "{name}" {eff()}) (number "1" {eff()}))))')
    return Sym(f"{LIB}:{name}", text, {"1": (0.0, 0.0)})


S = {
    "R": from_kicad("Device", "R"),
    "C": from_kicad("Device", "C"),
    "L": from_kicad("Device", "L"),
    "FB": from_kicad("Device", "FerriteBead"),
    "F": from_kicad("Device", "Fuse"),
    "RN4": from_kicad("Device", "R_Pack04"),
    "DS": from_kicad("Device", "D_Schottky"),
    "TVS": from_kicad("Device", "D_TVS"),
    "GND": from_kicad("power", "GND"),
    "FLAG": from_kicad("power", "PWR_FLAG"),
    "VBAT_P": rail("VBAT_P"),
    "3V3_AON": rail("3V3_AON"),
    "3V3_SW": rail("3V3_SW"),
    "5V_SW": rail("5V_SW"),
    "J_FOT": ic("TE_1-1394640-1", "J", 25.4, 22.86, [
        ("5", "RXVCC", "power_in", "T", 5.08),
        ("3", "TXVCC", "power_in", "T", 10.16),
        ("4", "RGAIN", "passive", "T", 15.24),      # Rext to TXVCC, so drawn next to it
        ("8", "RXD", "output", "R", 7.62),
        ("7", "STATUS", "output", "R", 10.16),
        ("1", "TXD", "input", "R", 17.78),
        ("6", "RXGND", "power_in", "B", 5.08),
        ("2", "TXGND", "power_in", "B", 10.16),
        ("0", "SHIELD", "passive", "B", 15.24),
    ], "MOST25 POF header with integrated FOT receiver and transmitter"),
    "BUF34": ic("74LVC1G34", "U", 12.7, 12.7, [
        ("2", "A", "input", "L", 3.81), ("4", "Y", "output", "R", 3.81),
        ("5", "VCC", "power_in", "T", 6.35), ("3", "GND", "power_in", "B", 6.35),
        ("1", "NC", "no_connect", "L", 8.89),
    ], "Single buffer, Ioff"),
    "BUF125": ic("74LVC1G125", "U", 12.7, 12.7, [
        ("2", "A", "input", "L", 3.81), ("1", "~{OE}", "input", "L", 8.89),
        ("4", "Y", "tri_state", "R", 3.81),
        ("5", "VCC", "power_in", "T", 6.35), ("3", "GND", "power_in", "B", 6.35),
    ], "Single buffer, 3-state, Ioff"),
    "MUX157": ic("74LVC1G157", "U", 12.7, 12.7, [
        ("3", "I0", "input", "L", 3.81), ("1", "I1", "input", "L", 6.35),
        ("6", "S", "input", "L", 8.89), ("4", "Y", "output", "R", 3.81),
        ("5", "VCC", "power_in", "T", 6.35), ("2", "GND", "power_in", "B", 6.35),
    ], "2-input multiplexer: S=L -> Y=I0, S=H -> Y=I1"),
    "OS123": ic("74LVC1G123", "U", 25.4, 20.32, [
        ("3", "~{CLR}", "input", "L", 2.54), ("2", "B", "input", "L", 5.08),
        ("1", "~{A}", "input", "L", 7.62),
        ("7", "REXT/CEXT", "passive", "R", 2.54), ("6", "CEXT", "passive", "R", 10.16),
        ("5", "Q", "output", "R", 17.78),
        ("8", "VCC", "power_in", "T", 12.7), ("4", "GND", "power_in", "B", 12.7),
    ], "Retriggerable monostable multivibrator"),
    "LDO": ic("TPS7B8133DRV", "U", 22.86, 10.16, [
        ("1", "IN", "power_in", "L", 2.54), ("2", "EN", "input", "L", 5.08),
        ("6", "OUT", "power_out", "R", 2.54), ("5", "NC", "no_connect", "R", 7.62),
        ("3", "GND", "power_in", "B", 3.81), ("4", "GND", "passive", "B", 7.62),
        ("7", "PAD", "passive", "B", 11.43),
    ], "40 V, 150 mA, 2.7 uA Iq automotive LDO, 3.3 V fixed"),
    "BUCK": ic("LMR33630ADDA", "U", 17.78, 17.78, [
        ("2", "VIN", "power_in", "L", 2.54), ("3", "EN", "input", "L", 15.24),
        ("7", "BOOT", "passive", "R", 2.54), ("8", "SW", "power_out", "R", 10.16),
        ("5", "FB", "input", "R", 12.7), ("4", "PG", "open_collector", "R", 15.24),
        ("1", "GND", "power_in", "B", 3.81), ("9", "EP", "passive", "B", 7.62),
        ("6", "VCC", "power_out", "B", 13.97),
    ], "3.8-36 V, 3 A synchronous buck, 400 kHz"),
    "SW_ILIM": ic("TPS2553DBV", "U", 20.32, 10.16, [
        ("1", "IN", "power_in", "L", 2.54), ("3", "EN", "input", "L", 7.62),
        ("6", "OUT", "power_out", "R", 2.54),
        ("2", "GND", "power_in", "B", 5.08), ("4", "~{FAULT}", "open_collector", "B", 10.16),
        ("5", "ILIM", "passive", "B", 15.24),
    ], "Current-limited power switch: limit set by RILIM, 2 us response, blocks reverse current"),
    "SI514": ic("Si514", "U", 22.86, 15.24, [
        ("2", "SCL", "input", "L", 2.54), ("1", "SDA", "bidirectional", "L", 5.08),
        ("4", "CLK+", "output", "R", 2.54), ("5", "CLK-", "output", "R", 7.62),
        ("6", "VDD", "power_in", "T", 11.43), ("3", "GND", "power_in", "B", 11.43),
    ], "I2C programmable XO/DCO, 0.1-250 MHz, +/-1000 ppm glitch-free; any 3.3 V CMOS option (C, M, N)"),
    "LDO_CLK": ic("LP5907MFX-3.3", "U", 20.32, 10.16, [
        ("1", "IN", "power_in", "L", 2.54), ("3", "EN", "input", "L", 7.62),
        ("5", "OUT", "power_out", "R", 2.54), ("4", "NC", "no_connect", "R", 7.62),
        ("2", "GND", "power_in", "B", 10.16),
    ], "250 mA ultra-low-noise LDO, 3.3 V"),
    "FF79": ic("74LVC1G79", "U", 12.7, 12.7, [
        ("1", "D", "input", "L", 3.81), ("2", "CP", "input", "L", 8.89),
        ("4", "Q", "output", "R", 3.81),
        ("5", "VCC", "power_in", "T", 6.35), ("3", "GND", "power_in", "B", 6.35),
    ], "Single D flip-flop, positive edge, Ioff"),
    "CONN2": ic("Conn_Power", "J", 7.62, 7.62, [
        ("1", "VBAT", "passive", "R", 2.54), ("2", "GND", "passive", "R", 5.08),
    ], "Battery input"),
    "CONN8": ic("Conn_Analyser", "J", 20.32, 22.86, [
        ("1", "MCLK", "passive", "L", 2.54), ("2", "BCLK", "passive", "L", 5.08),
        ("3", "FS", "passive", "L", 7.62), ("4", "SD0", "passive", "L", 10.16),
        ("5", "SD1", "passive", "L", 12.7), ("6", "UART_TX", "passive", "L", 15.24),
        ("7", "GND", "passive", "L", 17.78), ("8", "GND", "passive", "L", 20.32),
    ], "Analyser: MCLK 512 Fs, TDM (2 x TDM8), raw control blocks on UART"),
    "CONN_I2S": ic("Conn_I2S", "J", 15.24, 17.78, [
        ("1", "MCLK", "passive", "L", 2.54), ("2", "BCLK", "passive", "L", 5.08),
        ("3", "LRCK", "passive", "L", 7.62), ("4", "DOUT", "passive", "L", 10.16),
        ("5", "GND", "passive", "L", 12.7), ("6", "GND", "passive", "L", 15.24),
    ], "Stereo I2S out (two channels picked by the host) for a DAC or DSP"),
}

# Tang Nano 20K: left header = pads 1..20, right header = pads 21..40, top to
# bottom (USB-C end first) as in the Sipeed Tang Nano 20K Datasheet v1.3, p. 5
# ("Fixed the issue of pinout picture"). Each name = GW2AR pin + what the board
# itself connects there. The older wiki drawing missed the BL616 HSPI lines on
# 71..76 and 86; nothing of the ring or its clock sits on those any more.
LEFT = ["73 HSPI_DIN2", "74 HSPI_DIN3", "75 HSPI_DIR", "85 SDIO_D1", "77 GCLKT_1",
        "15 LED0", "16 LED1", "27 LCD_B7", "28 LCD_B6", "25 LCD_HS", "26 LCD_VS",
        "29 LCD_B5", "30 LCD_B4", "31 LCD_B3", "17 LED2", "20 LED5", "19 LED4",
        "18 LED3", "3V3", "GND"]
RIGHT = ["5V", "GND", "76 HSPI_DAT", "80 SDIO_D2", "42 LCD_R3", "41 LCD_R4",
         "56 I2S_BCLK", "54 I2S_DIN", "51 PA_EN", "48 LCD_DE", "55 I2S_LRCK",
         "49 LCD_BL", "86 HSPI_CSN", "79 WS2812", "GND", "3V3", "72 HSPI_DIN1",
         "71 HSPI_DIN0", "53 EDID_CLK", "52 EDID_DAT"]


def module_pins():
    out = []
    for i, n in enumerate(LEFT):
        t = "power_out" if n == "3V3" else "power_in" if n == "GND" else "bidirectional"
        out.append((str(i + 1), n, t, "L", G * (i + 1)))
    for i, n in enumerate(RIGHT):
        t = ("power_in" if n in ("5V", "GND") else "power_out" if n == "3V3"
             else "bidirectional")
        out.append((str(i + 21), n, t, "R", G * (i + 1)))
    return out


for _k in ("J_FOT", "LDO", "BUCK", "SI514", "LDO_CLK", "SW_ILIM"):
    S[_k].valpos = "top_right"
for _k in ("BUF34", "BUF125", "MUX157", "OS123", "FF79"):
    S[_k].valpos = "under_left"

S["TANG"] = ic("Tang_Nano_20K", "M", 30.48, 53.34, module_pins(),
               "Sipeed Tang Nano 20K, GW2AR-LV18QN88C8/I7")

# ESP32-DevKitC V4, antenna end up: left header J2 = pads 1..19, right header
# J3 = pads 20..38, top to bottom, names as on the board (Espressif user guide)
DKC_LEFT = ["3V3", "EN", "VP", "VN", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26",
            "IO27", "IO14", "IO12", "GND", "IO13", "D2", "D3", "CMD", "5V"]
DKC_RIGHT = ["GND", "IO23", "IO22", "TX", "RX", "IO21", "GND", "IO19", "IO18", "IO5",
             "IO17", "IO16", "IO4", "IO0", "IO2", "IO15", "D1", "D0", "CLK"]


def devkitc_pins():
    out = []
    for i, n in enumerate(DKC_LEFT):
        t = "power_in" if n in ("5V", "GND") else "passive" if n == "3V3" else "bidirectional"
        out.append((str(i + 1), n, t, "L", G * (i + 1)))
    for i, n in enumerate(DKC_RIGHT):
        t = "power_in" if n == "GND" else "bidirectional"
        out.append((str(i + 20), n, t, "R", G * (i + 1)))
    return out


S["DEVKITC"] = ic("ESP32_DevKitC", "M", 20.32, 50.8, devkitc_pins(),
                  "Espressif ESP32-DevKitC V4, any module variant; J2 = pads 1..19, J3 = pads 20..38")


# ------------------------------------------------------------------- sheet
def rot(px, py, deg):
    a = math.radians(deg)
    return (px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a))


class Part:
    def __init__(self, sym, ref, x, y, r):
        self.sym, self.ref, self.x, self.y, self.rot = sym, ref, x, y, r

    def p(self, num):
        rx, ry = rot(*self.sym.pins[num], self.rot)
        return (round(self.x + rx, 3), round(self.y - ry, 3))


class Sheet:
    def __init__(self):
        self.items, self.used, self.parts, self.refs = [], {}, [], set()
        self.segs, self.pinpts, self.pwr = [], [], 0

    def add(self, key, ref, value, x, y, r=0, fp="", show_val=True, ref_at=None,
            val_at=None, fjust=None):
        sym = S[key]
        # every reference once: KiCad's ERC does not check annotation, and two
        # parts under one name (J3 was both the battery input and I2S) merge
        # in the netlist and the BOM
        assert ref.startswith("#") or ref not in self.refs, f"duplicate reference {ref}"
        self.refs.add(ref)
        self.used[sym.lib_id] = sym
        part = Part(sym, ref, x, y, r)
        self.parts.append(part)
        for n in sym.pins:
            self.pinpts.append(part.p(n))
        is_pwr = ref.startswith("#")
        two = key in ("R", "C", "L", "F", "FB")
        if ref_at is None:
            if sym.box:                       # IC: ref above the top-left corner
                w, h = sym.box
                ref_at = (x - w / 2, y - h / 2 - 1.27)
                if sym.valpos == "top_right":     # parts with pins on the bottom
                    val_at = (x + w / 2, y - h / 2 - 1.27)
                    fjust = ("left bottom", "right bottom")
                elif sym.valpos == "under_left":  # small logic: left of the GND pin
                    val_at = (x - 1.27, y + h / 2 + 1.27)
                    fjust = ("left bottom", "right top")
                else:
                    val_at = (x - w / 2, y + h / 2 + 1.27)
                    fjust = ("left bottom", "left top")
            elif two and r == 0:              # vertical passive: to the right
                ref_at, val_at = (x + 2.54, y - 1.27), (x + 2.54, y + 1.27)
                fjust = ("left", "left")
            elif two:                         # horizontal passive: above/below
                ref_at, val_at = (x, y - 2.54), (x, y + 2.54)
                fjust = (None, None)
            else:
                ref_at, val_at = (x, y - 3.81), (x, y + 3.81)
                fjust = (None, None)
        fjust = fjust or (None, None)
        fa = 90 if r in (90, 270) else 0     # keeps the text horizontal
        props = [
            f'(property "Reference" "{ref}" (at {f(ref_at[0])} {f(ref_at[1])} {fa}) '
            f'{eff(hide=is_pwr, justify=fjust[0])})',
            f'(property "Value" "{value}" (at {f(val_at[0])} {f(val_at[1])} {fa}) '
            f'{eff(hide=not show_val, justify=fjust[1])})',
            f'(property "Footprint" "{fp}" (at {f(x)} {f(y)} 0) {eff(hide=True)})',
            f'(property "Datasheet" "" (at {f(x)} {f(y)} 0) {eff(hide=True)})',
        ]
        pins = " ".join(f'(pin "{n}" (uuid "{uid(ref + n)}"))' for n in sym.pins)
        self.items.append(
            f'(symbol (lib_id "{sym.lib_id}") (at {f(x)} {f(y)} {r}) (unit 1) '
            f'(exclude_from_sim no) (in_bom {"no" if is_pwr else "yes"}) (on_board yes) '
            f'(dnp no) (uuid "{uid("sym" + ref)}")\n  ' + "\n  ".join(props) +
            f'\n  {pins}\n  (instances (project "{PROJECT}" (path "/{uid("root")}" '
            f'(reference "{ref}") (unit 1)))))')
        return part

    def at_pin(self, key, ref, value, pin, target, r=0, **kw):
        """Place a part so that pin `pin` lands exactly on `target`."""
        rx, ry = rot(*S[key].pins[pin], r)
        return self.add(key, ref, value, round(target[0] - rx, 3),
                        round(target[1] + ry, 3), r, **kw)

    # connectivity ---------------------------------------------------------
    def wire(self, *pts):
        pts = [(round(p[0], 3), round(p[1], 3)) for p in pts]
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            assert a[0] == b[0] or a[1] == b[1], (a, b)
            self.segs.append((a, b))

    def nc(self, p):
        self.items.append(f'(no_connect (at {f(p[0])} {f(p[1])}) (uuid "{uid("nc" + str(p))}"))')

    def label(self, name, p, side="R"):
        ang = {"R": 0, "L": 180}[side]
        just = {"R": "left", "L": "right"}[side]
        self.items.append(f'(label "{name}" (at {f(p[0])} {f(p[1])} {ang}) '
                          f'{eff(justify=just + " bottom")} (uuid "{uid("l" + name + str(p))}"))')

    def lbl(self, name, pin, length, side):
        """Stub of `length` from a pin, then a label facing away from the part."""
        dx = -length if side == "L" else length
        q = (round(pin[0] + dx, 3), pin[1])
        self.wire(pin, q)
        self.label(name, q, side)

    def power(self, key, p):
        self.pwr += 1
        va = (p[0], p[1] + 5.08) if key == "GND" else (p[0], p[1] - 3.81)
        self.add(key, f"#PWR{self.pwr:03d}", S[key].lib_id.split(":")[1], p[0], p[1], 0,
                 ref_at=(p[0], p[1] + 6.35), val_at=va, show_val=(key != "GND"))

    def gnd(self, p, stub=0.0):
        q = (p[0], round(p[1] + stub, 3))
        self.wire(p, q)
        self.power("GND", q)

    def up(self, key, p, stub=0.0):
        q = (p[0], round(p[1] - stub, 3))
        self.wire(p, q)
        self.power(key, q)

    def flag(self, p, dx=2.54):
        """PWR_FLAG on a short branch to the right of p."""
        q = (round(p[0] + dx, 3), p[1])
        self.wire(p, q)
        self.pwr += 1
        self.add("FLAG", f"#FLG{self.pwr:03d}", "PWR_FLAG", q[0], q[1], 0,
                 ref_at=(q[0], q[1] - 5.08), val_at=(q[0], q[1] - 3.81), show_val=False)

    def decouple(self, pin, railkey, ref, value="100n", dx=7.62, rise=10.16):
        """Supply pin -> up `rise` to the rail symbol -> right `dx` -> cap down
        to GND. The whole thing stays above the part's body."""
        top = (pin[0], round(pin[1] - rise, 3))
        self.up(railkey, pin, rise)
        c = self.at_pin("C", ref, value, "1", (top[0] + dx, top[1]), fp=SMD["C"])
        self.wire(top, c.p("1"))
        self.gnd(c.p("2"))
        return c

    # graphics -------------------------------------------------------------
    def frame(self, x1, y1, x2, y2, title):
        self.items.append(
            f'(rectangle (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) '
            f'(stroke (width 0.254) (type dash) (color 72 72 160 1)) (fill (type none)) '
            f'(uuid "{uid("fr" + title)}"))')
        self.text(title, x1 + 1.27, y1 + 3.81, 2.0, bold=True)

    def text(self, s, x, y, size=1.5, bold=False):
        b = " (bold yes)" if bold else ""
        s = s.replace('"', "'")
        self.items.append(
            f'(text "{s}" (exclude_from_sim no) (at {f(x)} {f(y)} 0) '
            f'(effects (font (size {f(size)} {f(size)}){b}) (justify left bottom)) '
            f'(uuid "{uid("t" + s + str(x) + str(y))}"))')

    def junctions(self):
        """Split every wire where a pin or another wire's end touches it
        (KiCad only joins at end points), then dot every 3-way meeting."""
        pins = Counter((round(x, 3), round(y, 3)) for x, y in self.pinpts)
        keys = set(pins)
        for a, b in self.segs:
            keys.add(a); keys.add(b)
        split = []
        for a, b in self.segs:
            cut = [a, b]
            for p in keys:
                if p in (a, b):
                    continue
                if a[0] == b[0] == p[0] and min(a[1], b[1]) < p[1] < max(a[1], b[1]):
                    cut.append(p)
                elif a[1] == b[1] == p[1] and min(a[0], b[0]) < p[0] < max(a[0], b[0]):
                    cut.append(p)
            cut.sort(key=lambda q: (q[0], q[1]))
            split += list(zip(cut, cut[1:]))
        self.segs = sorted(set(split))
        for a, b in self.segs:
            self.items.append(
                f'(wire (pts (xy {f(a[0])} {f(a[1])}) (xy {f(b[0])} {f(b[1])})) '
                f'(stroke (width 0) (type default)) (uuid "{uid(str((a, b)))}"))')
        ends = Counter()
        for a, b in self.segs:
            ends[a] += 1
            ends[b] += 1
        dots = {p for p, n in ends.items() if n + pins[p] >= 3}
        for p in sorted(dots):
            self.items.append(f'(junction (at {f(p[0])} {f(p[1])}) (diameter 0) '
                              f'(color 0 0 0 0) (uuid "{uid("j" + str(p))}"))')

    def write(self, path: Path):
        self.junctions()
        libs = "\n".join(sym.text for sym in self.used.values())
        body = "\n".join(self.items)
        path.write_text(
            f'(kicad_sch (version 20231120) (generator "gen_listener") '
            f'(generator_version "10.0") (uuid "{uid("root")}") (paper "A3")\n'
            f'(title_block (title "MOST25 to AUDIO: listener board") (date "2026-09-26") '
            f'(rev "0.2") (comment 1 "Generated by listener_hw/gen_listener.py") '
            f'(comment 2 "Repeater with regeneration and a bypass watchdog; FPGA; ESP32 host; TDM, UART, I2S out"))\n'
            f'(lib_symbols\n{libs}\n)\n{body}\n'
            f'(sheet_instances (path "/" (page "1")))\n)\n', encoding="utf-8")


SMD = {"R": "Resistor_SMD:R_0603_1608Metric", "C": "Capacitor_SMD:C_0603_1608Metric"}


# --------------------------------------------------------------- footprint
FP_SI514 = "Si514_5x7_3.2x5_2.5x3.2"
# Si514 land patterns, data sheet Rev 1.2, Tables 17, 19 and 21, in the data
# sheet's orientation: two pad columns C1 apart, pins P apart, pads W across x
# by H along the pitch; pin 1 top left, 1-2-3 down the left column, 4-5-6 up
# the right. Same pinout in all three packages (Table 15).
SI514_PKG = {
    #          C1    P     W     H     body w x h
    "5x7":     (4.20, 2.54, 1.95, 1.55, 5.0, 7.0),
    "3.2x5":   (2.60, 1.27, 1.70, 0.80, 3.2, 5.0),
    "2.5x3.2": (1.90, 1.25, 1.05, 0.70, 2.5, 3.2),
}


def si514_layout(gap_col=1.0, gap_row=0.5):
    """U7's three land patterns side by side, pads 1..6 repeated - one part is
    soldered. Column 1: 3.2x5 above 2.5x3.2, the latter turned 90 degrees to
    fit the column; gap_row between the 3.2x5 body and the 2.5x3.2 pads.
    Column 2: 5x7, turned 180 degrees so that the three CLK+ pads (pin 4) end
    up close together; gap_col between the columns' pads. The 5x7 cannot sit
    on top of the others: its pin 2 pad would come 0.1 mm from their pin 1.
    Returns [(package, centre, rotation, pads {num: (x, y, w, h)}, body (w, h))],
    screen coordinates (y down), origin in the middle."""
    side = {"1": (-1, -1), "2": (-1, 0), "3": (-1, 1), "4": (1, 1), "5": (1, 0), "6": (1, -1)}

    def rot(x, y, r):                        # r: 0, 90 (anticlockwise on screen), 180
        return {0: (x, y), 90: (y, -x), 180: (-x, -y)}[r]

    def pads(name, r):
        c1, p, w, h = SI514_PKG[name][:4]
        out = {}
        for n, (sx, sy) in side.items():
            x, y = rot(sx * c1 / 2, sy * p, r)
            out[n] = (x, y) + ((h, w) if r == 90 else (w, h))
        return out

    def span(pd):
        xs = [x + s * w / 2 for x, y, w, h in pd.values() for s in (-1, 1)]
        ys = [y + s * h / 2 for x, y, w, h in pd.values() for s in (-1, 1)]
        return max(xs) - min(xs), max(ys) - min(ys)

    pa, pb, pc = pads("3.2x5", 0), pads("2.5x3.2", 90), pads("5x7", 180)
    wa, wc = span(pa)[0], span(pc)[0]
    hb = span(pb)[1]
    bha = SI514_PKG["3.2x5"][5]
    x0 = -(wa + gap_col + wc) / 2
    cx1, cx2 = x0 + wa / 2, x0 + wa + gap_col + wc / 2
    h1 = bha + gap_row + hb                  # column 1: 3.2x5 body, gap, 2.5x3.2 pads
    cya = -h1 / 2 + bha / 2
    cyb = cya + bha / 2 + gap_row + hb / 2
    out = []
    for name, (cx, cy), r, pd in (("3.2x5", (cx1, cya), 0, pa), ("2.5x3.2", (cx1, cyb), 90, pb),
                                  ("5x7", (cx2, 0.0), 180, pc)):
        bw, bh = SI514_PKG[name][4:]
        body = (bh, bw) if r == 90 else (bw, bh)
        out.append((name, (cx, cy), r, {n: (cx + x, cy + y, w, h) for n, (x, y, w, h) in pd.items()},
                    body))
    return out


def rect_gap(a, b):
    """Clearance between two centred rectangles (x, y, w, h); negative = overlap."""
    dx = abs(a[0] - b[0]) - (a[2] + b[2]) / 2
    dy = abs(a[1] - b[1]) - (a[3] + b[3]) / 2
    return max(dx, dy)


def si514_footprint():
    """The .kicad_mod text for U7, and the figures it was checked by: the
    smallest copper gap between different pins, the smallest gap between a
    package body and another pattern's pads, and the courtyard size."""
    lay = si514_layout()
    pads = [(n, r) for _, _, _, pd, _ in lay for n, r in pd.items()]
    cu = min(rect_gap(a, b) for i, (na, a) in enumerate(pads) for nb_, b in pads[i + 1:] if na != nb_)
    bodies = []
    for name, (cx, cy), _, pd, (bw, bh) in lay:
        others = [r for nm, _, _, p2, _ in lay if nm != name for r in p2.values()]
        bodies.append(min(rect_gap((cx, cy, bw, bh), r) for r in others))
    items = []

    def line(x1, y1, x2, y2, layer, w):
        items.append(f'\t(fp_line (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) '
                     f'(stroke (width {f(w)}) (type solid)) (layer "{layer}") '
                     f'(uuid "{uid("fpl" + layer + str((x1, y1, x2, y2)))}"))')

    def box(x1, y1, x2, y2, layer, w):
        for a, b in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
            line(*a, *b, layer, w)

    def text(s, x, y, layer, size, kind=None):
        head = f'(property "{kind}" "{s}"' if kind else f'(fp_text user "{s}"'
        items.append(f'\t{head} (at {f(x)} {f(y)} 0) (layer "{layer}") '
                     f'(uuid "{uid("fpt" + s + layer)}") '
                     f'(effects (font (size {f(size)} {f(size)}) (thickness {f(size * 0.15)}))))')

    xs, ys = [], []
    for name, (cx, cy), r, pd, (bw, bh) in lay:
        x1, y1, x2, y2 = cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2
        box(x1, y1, x2, y2, "F.Fab", 0.1)                 # the body, and its name inside
        text(name, cx, cy, "F.Fab", 0.5)
        xs += [x1, x2]; ys += [y1, y2]
        for n, (x, y, w, h) in pd.items():
            items.append(f'\t(pad "{n}" smd rect (at {f(x)} {f(y)}) (size {f(w)} {f(h)}) '
                         f'(layers "F.Cu" "F.Mask" "F.Paste") (uuid "{uid("fpp" + name + n)}"))')
            xs += [x - w / 2, x + w / 2]; ys += [y - h / 2, y + h / 2]
        # pin 1: a dot on the silkscreen, off the pin 1 pad's outer corner
        x, y, w, h = pd["1"]
        dx, dy = (1 if x > cx else -1), (1 if y > cy else -1)
        px, py = x + dx * (w / 2 + 0.35), y + dy * (h / 2 + 0.35)
        items.append(f'\t(fp_circle (center {f(px)} {f(py)}) (end {f(px + 0.15)} {f(py)}) '
                     f'(stroke (width 0.1) (type solid)) (fill yes) (layer "F.SilkS") '
                     f'(uuid "{uid("fpc" + name)}"))')
        xs += [px - 0.2, px + 0.2]; ys += [py - 0.2, py + 0.2]
    k1, l1, k2, l2 = (round(min(xs) - 0.25, 2), round(min(ys) - 0.25, 2),
                      round(max(xs) + 0.25, 2), round(max(ys) + 0.25, 2))
    box(k1, l1, k2, l2, "F.CrtYd", 0.05)
    props = []
    text("REF**", 0, round(l1 - 1.0, 2), "F.SilkS", 1.0, "Reference")
    props.append(items.pop())
    text(FP_SI514, 0, round(l2 + 1.0, 2), "F.Fab", 1.0, "Value")
    props.append(items.pop())
    head = (f'(footprint "{FP_SI514}"\n\t(version 20260206)\n\t(generator "gen_listener")\n'
            f'\t(layer "F.Cu")\n'
            f'\t(descr "Skyworks Si514 in any of its packages: 5x7, 3.2x5 and 2.5x3.2 mm land '
            f'patterns (data sheet Rev 1.2, Tables 17, 19, 21) side by side, pads 1..6 repeated; '
            f'solder one part")\n\t(tags "Si514 oscillator 5x7 3.2x5 2.5x3.2")\n')
    body = "\n".join(props + ['\t(attr smd)', '\t(duplicate_pad_numbers_are_jumpers no)'] + items)
    return head + body + "\n)\n", cu, min(bodies), (k2 - k1, l2 - l1)


# ----------------------------------------------------------------- drawing
def power_block(sh):
    sh.frame(12.7, 12.7, 203.2, 101.6, "1. ЖИВЛЕННЯ   J4 акумулятор -> 3V3_AON (завжди) і 5V_SW (за WAKE) -> 5V_HOST (M2)")
    # input: J4 -> F1 -> D1 -> VBAT_P
    j4 = sh.add("CONN2", "J4", "VBAT_IN", 25.4, 45.72,
                fp="Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical")
    y = j4.p("1")[1]
    f1 = sh.at_pin("F", "F1", "1A", "1", (38.1, y), r=90, fp="Fuse:Fuse_1206_3216Metric")
    d1 = sh.at_pin("DS", "D1", "SS34", "2", (53.34, y), r=180, fp="Diode_SMD:D_SMA",
                   ref_at=(53.34, y - 3.81), val_at=(53.34, y + 3.81))
    sh.wire(j4.p("1"), f1.p("1"))
    sh.wire(f1.p("2"), d1.p("2"))
    node = (68.58, y)
    sh.wire(d1.p("1"), node, (99.06, y))
    g = j4.p("2")
    sh.wire(g, (33.02, g[1]), (33.02, 60.96))
    sh.gnd((33.02, 60.96))
    sh.flag((33.02, 55.88))
    sh.up("VBAT_P", node, 5.08)
    sh.flag((78.74, y))
    d2 = sh.at_pin("TVS", "D2", "SMBJ26CA", "1", (68.58, y + 5.08), r=270, fp="Diode_SMD:D_SMB",
                   ref_at=(66.04, y + 7.62), val_at=(66.04, y + 10.16), fjust=("right", "right"))
    sh.wire(node, d2.p("1")); sh.gnd(d2.p("2"))
    c1 = sh.at_pin("C", "C1", "10u 50V", "1", (86.36, y + 5.08), fp="Capacitor_SMD:C_1210_3225Metric")
    c2 = sh.at_pin("C", "C2", "100n 50V", "1", (99.06, y + 5.08), fp=SMD["C"])
    sh.wire((86.36, y), c1.p("1")); sh.wire((99.06, y), c2.p("1"))
    sh.gnd(c1.p("2")); sh.gnd(c2.p("2"))
    sh.text("Захист: F1 запобіжник, D1 від переполюсовки, D2 TVS (26 В: провідність від ~29 В - див. README, пункт про load dump).", 17.78, 87.63, 1.27)
    sh.text("3V3_AON (U5) завжди: FOT, U1, U2, U4, U11. На стоянці (кільце спить) разом до ~60 мкА: FOT у сні <= 25, логіка, LDO 2.7.", 17.78, 91.44, 1.27)
    sh.text("5V_SW (U6) вмикає WAKE: модуль FPGA. VOUT = 1.0 В x (1 + R4/R5) = 5.31 В; після D3 ~5.0 В.", 17.78, 95.25, 1.27)
    sh.text("5V_HOST (U10): живлення M2 (ESP32), межа ~1 А (R22 24k9): радіо модуля бере піки понад 0.5 А; 5 В з USB модуля назад у 5V_SW не проходять.", 17.78, 99.06, 1.27)

    # LDO: VBAT_P -> 3V3_AON, always on
    u5 = sh.add("LDO", "U5", "TPS7B8133DRV", 116.84, 31.75,
                fp="Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm")
    vin, en = u5.p("1"), u5.p("2")
    sh.wire((101.6, vin[1]), vin)
    sh.wire((101.6, vin[1]), (101.6, en[1]), en)
    sh.up("VBAT_P", (101.6, vin[1]), 5.08)
    sh.nc(u5.p("5"))
    b = u5.p("3")[1] + 2.54
    for n in ("3", "4", "7"):
        sh.wire(u5.p(n), (u5.p(n)[0], b))
    sh.wire((u5.p("3")[0], b), (u5.p("7")[0], b))
    sh.gnd((u5.p("4")[0], b))
    out = u5.p("6")
    sh.wire(out, (137.16, out[1]))
    c3 = sh.at_pin("C", "C3", "2u2", "1", (137.16, out[1] + 5.08), fp=SMD["C"])
    sh.wire((137.16, out[1]), c3.p("1")); sh.gnd(c3.p("2"))
    sh.up("3V3_AON", (137.16, out[1]), 5.08)

    # Buck: VBAT_P -> 5V_SW for the FPGA module, enabled by WAKE
    u6 = sh.add("BUCK", "U6", "LMR33630ADDA", 142.24, 69.85,
                fp="Package_SO:Texas_HSOP-8-1EP_3.9x4.9mm_P1.27mm_ThermalVias")
    vin = u6.p("2")
    vn = (vin[0] - 7.62, vin[1])
    sh.wire(vn, vin)
    sh.up("VBAT_P", vn, 5.08)
    c4 = sh.at_pin("C", "C4", "10u 50V", "1", (vn[0] - 10.16, vin[1]), fp="Capacitor_SMD:C_1210_3225Metric")
    sh.wire(vn, c4.p("1")); sh.gnd(c4.p("2"))
    sh.lbl("WAKE", u6.p("3"), 20.32, "L")
    b = u6.p("1")[1] + 2.54
    sh.wire(u6.p("1"), (u6.p("1")[0], b)); sh.wire(u6.p("9"), (u6.p("9")[0], b))
    sh.wire((u6.p("1")[0], b), (u6.p("9")[0], b)); sh.gnd((u6.p("1")[0], b))
    c5 = sh.at_pin("C", "C5", "1u", "1", u6.p("6"), fp=SMD["C"])
    sh.gnd(c5.p("2"))
    boot, sw = u6.p("7"), u6.p("8")
    c6 = sh.at_pin("C", "C6", "100n", "1", (boot[0] + 5.08, boot[1]), fp=SMD["C"])
    sh.wire(boot, c6.p("1")); sh.wire(sw, c6.p("2"))
    l1 = sh.at_pin("L", "L1", "10u", "1", (boot[0] + 12.7, sw[1]), r=90,
                   fp="Inductor_SMD:L_Bourns_SRN6045TA", ref_at=(boot[0] + 16.51, sw[1] - 2.54),
                   val_at=(boot[0] + 16.51, sw[1] + 2.54))
    sh.wire(c6.p("2"), l1.p("1"))
    o = (l1.p("2")[0] + 5.08, sw[1])
    oc = (o[0] + 10.16, sw[1])
    sh.wire(l1.p("2"), o, oc)
    sh.up("5V_SW", o, 5.08)
    sh.flag(oc)
    c7 = sh.at_pin("C", "C7", "22u", "1", (oc[0], sw[1] + 5.08), fp="Capacitor_SMD:C_1206_3216Metric")
    sh.wire(oc, c7.p("1")); sh.gnd(c7.p("2"))
    r4 = sh.at_pin("R", "R4", "100k", "1", (o[0], sw[1] + 2.54), fp=SMD["R"])
    sh.wire(o, r4.p("1"))
    fbn = (o[0], r4.p("2")[1] + 2.54)
    r5 = sh.at_pin("R", "R5", "23k2", "1", (o[0], fbn[1] + 2.54), fp=SMD["R"])
    sh.wire(r4.p("2"), fbn, r5.p("1")); sh.gnd(r5.p("2"))
    fb = u6.p("5")
    sh.wire(fb, (fb[0] + 2.54, fb[1]), (fb[0] + 2.54, fbn[1]), fbn)
    sh.nc(u6.p("4"))

    # Switch: 5V_SW -> 5V_HOST, the supply of the host module M2 (ESP32). The
    # FPGA sits in the ring and lives on 5V_SW, so a fault on M2 must not pull
    # 5V_SW down: TPS2553 limits to about 1 A (R22 = 24.9k; 0.52 A typ at
    # 49.9k per its table, the limit scales with 1/R) in 2 us, and blocks
    # current back from M2's own USB when it is flashed in place (1 uA max,
    # even with IN at 0 V). EN tied to IN: on whenever 5V_SW is. Espressif
    # asks for a 500 mA supply for the module and the radio draws it in peaks;
    # the earlier 0.52 A limit (0.475-0.565 A) sat on that line, a brown-out
    # reset waiting to happen, and 1 uF behind it could not carry a peak.
    u10 = sh.add("SW_ILIM", "U10", "TPS2553DBVR", 177.8, 30.48, fp="Package_TO_SOT_SMD:SOT-23-6")
    vin, en = u10.p("1"), u10.p("3")
    xr = vin[0] - 5.08
    sh.wire(vin, (xr, vin[1]))
    sh.wire(en, (xr, en[1]))
    sh.wire((xr, vin[1]), (xr, en[1]))
    sh.up("5V_SW", (xr, vin[1]), 2.54)
    c23 = sh.at_pin("C", "C23", "100n", "1", (xr, en[1]), fp=SMD["C"],
                    ref_at=(xr - 2.54, en[1] + 2.54), val_at=(xr - 2.54, en[1] + 5.08),
                    fjust=("right", "right"))
    sh.gnd(c23.p("2"))
    sh.gnd(u10.p("2"))
    sh.nc(u10.p("4"))
    r22 = sh.at_pin("R", "R22", "24k9 1%", "1", u10.p("5"), fp=SMD["R"])
    sh.gnd(r22.p("2"))
    out = u10.p("6")
    node = (out[0] + 2.54, out[1])
    sh.wire(out, node)
    c24 = sh.at_pin("C", "C24", "10u 6V3", "1", node, fp="Capacitor_SMD:C_0805_2012Metric")
    sh.gnd(c24.p("2"))
    sh.label("5V_HOST", node, "R")


def one_shot(sh, ref, y, rref, rval, cref, cval, dref, out):
    """A 74LVC1G123 at (256.54, y), retriggered by rising edges on B:
    REXT/CEXT to 3V3_AON through R, C between REXT/CEXT and CEXT, Q -> `out`.
    Returns the part; ~CLR, B and ~A are the caller's."""
    u = sh.add("OS123", ref, "74LVC1G123", 256.54, y, fp="Package_SO:VSSOP-8_2.3x2mm_P0.5mm")
    sh.decouple(u.p("8"), "3V3_AON", dref, rise=7.62)
    sh.gnd(u.p("4"))
    rc, ce, q = u.p("7"), u.p("6"), u.p("5")
    xc = rc[0] + 5.08
    sh.wire(rc, (xc, rc[1]))
    c = sh.at_pin("C", cref, cval, "1", (xc, rc[1]), fp=SMD["C"])
    sh.wire(c.p("2"), (xc, ce[1]), ce)
    xr = rc[0] + 15.24
    sh.wire((xc, rc[1]), (xr, rc[1]))
    r = sh.at_pin("R", rref, rval, "2", (xr, rc[1]), fp=SMD["R"])
    sh.up("3V3_AON", r.p("1"), 2.54)
    sh.lbl(out, q, 12.7, "R")
    return u


def wake_block(sh):
    sh.frame(208.28, 12.7, 330.2, 101.6, "2. ПРОБУДЖЕННЯ (U4) І СТОРОЖ ОБХОДУ (U11)")
    # U4: every RX edge restarts ~0.1 s; the ring asleep -> WAKE = 0 -> no power
    u4 = one_shot(sh, "U4", 43.18, "R6", "100k", "C9", "1u", "C8", "WAKE")
    clr, bb, aa = u4.p("3"), u4.p("2"), u4.p("1")
    sh.wire(clr, (241.3, clr[1])); sh.up("3V3_AON", (241.3, clr[1]), 5.08)
    sh.lbl("RX_BUF", bb, 20.32, "L")
    sh.wire(aa, (241.3, aa[1])); sh.gnd((241.3, aa[1]), 5.08)
    # U11: the bypass watchdog. TX_SEL (U2's select) is 1 only while LOCK is 1
    # AND TX_REGEN keeps toggling: whatever stops TX - clk_s or clk_r dead, U9
    # stuck or unclocked, the FPGA hung - bypass follows within ~10 us, with
    # no clock of the FPGA's involved. R8 holds LOCK low while the FPGA is
    # unconfigured (its pins float or pull up).
    u11 = one_shot(sh, "U11", 85.09, "R23", "10k", "C25", "1n", "C26", "TX_SEL")
    clr, bb, aa = u11.p("3"), u11.p("2"), u11.p("1")
    sh.wire(clr, (218.44, clr[1])); sh.label("LOCK", (218.44, clr[1]), "L")
    r8 = sh.at_pin("R", "R8", "10k", "1", (223.52, clr[1]), fp=SMD["R"],
                   ref_at=(222.25, clr[1] + 2.54), val_at=(222.25, clr[1] + 5.08),
                   fjust=("right", "right"))
    sh.gnd(r8.p("2"))
    sh.lbl("TX_REGEN", bb, 5.08, "L")
    sh.wire(aa, (241.3, aa[1])); sh.gnd((241.3, aa[1]), 5.08)
    for i, line in enumerate((
            "U4: кожен фронт RX", "перезапускає ~0.1 с", "(R6 x C9). Кільце спить",
            "-> WAKE = 0 -> U6 вимк.,", "FPGA без живлення.", "Полярність STATUS",
            "знати не треба.", "",
            "U11: TX_SEL = 1, лише", "поки LOCK = 1 і фронти", "TX_REGEN є (R23 x C25",
            "~10 мкс; TX без фронтів", "довше - не MOST).",
            "TX став (такт, U9, FPGA)", "-> TX_SEL = 0: обхід.",
            "R8: FPGA не завантажена", "-> LOCK = 0 -> обхід.")):
        if line:
            sh.text(line, 298.45, 21.59 + 3.81 * i, 1.27)


def optics_block(sh):
    sh.frame(12.7, 106.68, 203.2, 198.12, "3. КІЛЬЦЕ   J1 = вхід і вихід MOST (обидва волокна); ретрансляція, завжди живлено")
    j1 = sh.add("J_FOT", "J1", "1-1394640-1", 45.72, 151.13, fp="",
                ref_at=(33.02, 138.43), val_at=(31.75, 151.13), fjust=("left bottom", "right"))
    sh.text("волокно ВІД попереднього вузла -> RX", 17.78, 176.53, 1.27)
    sh.text("волокно ДО наступного вузла  <- TX", 17.78, 180.34, 1.27)
    # supplies (AN 5344): RX and TX each through its own ferrite, 100n + 10u
    # on the FOT side; Rext from RGAIN to the TX supply sets the LED current
    rx, tx, rg = j1.p("5"), j1.p("3"), j1.p("4")
    nrx = (rx[0], rx[1] - 7.62)
    sh.wire(rx, nrx)
    fb1 = sh.at_pin("FB", "FB1", "600R", "2", nrx, fp="Inductor_SMD:L_0603_1608Metric",
                    ref_at=(rx[0] - 2.54, nrx[1] - 5.08), val_at=(rx[0] - 2.54, nrx[1] - 2.54),
                    fjust=("right", "right"))
    sh.up("3V3_AON", fb1.p("1"), 2.54)
    c10 = sh.at_pin("C", "C10", "100n", "1", (nrx[0] - 10.16, nrx[1]), fp=SMD["C"])
    c18 = sh.at_pin("C", "C18", "10u", "1", (nrx[0] - 20.32, nrx[1]),
                    fp="Capacitor_SMD:C_0805_2012Metric")
    sh.wire(nrx, c10.p("1"), c18.p("1"))
    sh.gnd(c10.p("2")); sh.gnd(c18.p("2"))
    sh.flag(c18.p("1"), dx=0)                         # fed through FB1: driven
    ntx = (tx[0], nrx[1] - 7.62)                      # TX supply node, level with FB1's top
    sh.wire(tx, ntx)
    r3 = sh.at_pin("R", "R3", "13k7 1%", "2", rg, fp=SMD["R"])
    sh.wire(r3.p("1"), (rg[0], ntx[1]))
    c19 = sh.at_pin("C", "C19", "100n", "1", (ntx[0] + 12.7, ntx[1]), fp=SMD["C"])
    c20 = sh.at_pin("C", "C20", "10u", "1", (ntx[0] + 22.86, ntx[1]),
                    fp="Capacitor_SMD:C_0805_2012Metric")
    sh.gnd(c19.p("2")); sh.gnd(c20.p("2"))
    sh.flag(c20.p("1"), dx=0)                         # fed through FB2: driven
    fb2 = sh.at_pin("FB", "FB2", "600R", "1", (ntx[0] + 33.02, ntx[1]), r=90,
                    fp="Inductor_SMD:L_0603_1608Metric")
    rt = (fb2.p("2")[0] + 5.08, ntx[1])
    sh.wire(ntx, (rg[0], ntx[1]), c19.p("1"), c20.p("1"), fb2.p("1"))
    sh.wire(fb2.p("2"), rt)
    sh.up("3V3_AON", rt, 2.54)
    b = j1.p("6")[1] + 2.54
    for n in ("6", "2", "0"):
        sh.wire(j1.p(n), (j1.p(n)[0], b))
    sh.wire((j1.p("6")[0], b), (j1.p("0")[0], b)); sh.gnd((j1.p("2")[0], b))
    sh.nc(j1.p("7"))
    # RX: J1.RXD -> R1 -> U1 -> RX_BUF; R7 holds the line low while the
    # receiver sleeps (the data sheet does not say what RXD does then)
    rxd = j1.p("8")
    r1 = sh.at_pin("R", "R1", "150", "1", (rxd[0] + 7.62, rxd[1]), r=90, fp=SMD["R"])
    sh.wire(rxd, r1.p("1"))
    u1 = sh.at_pin("BUF34", "U1", "74LVC1G34", "2", (r1.p("2")[0] + 7.62, rxd[1]),
                   fp="Package_TO_SOT_SMD:SOT-353_SC-70-5")
    sh.wire(r1.p("2"), u1.p("2"))
    xpd = r1.p("2")[0] + 2.54
    r7 = sh.at_pin("R", "R7", "100k", "1", (xpd, rxd[1]), fp=SMD["R"],
                   ref_at=(xpd - 1.27, rxd[1] + 5.08), val_at=(xpd - 1.27, rxd[1] + 7.62),
                   fjust=("right", "right"))
    sh.gnd(r7.p("2"))
    sh.nc(u1.p("1"))
    sh.decouple(u1.p("5"), "3V3_AON", "C17")
    sh.gnd(u1.p("3"))
    y = u1.p("4")
    node = (y[0] + 12.7, y[1])
    sh.wire(y, node)
    sh.wire(node, (node[0], y[1] - 12.7)); sh.label("RX_BUF", (node[0], y[1] - 12.7), "R")
    # MUX: I0 = RX_BUF (bypass), I1 = TX_REGEN, S = TX_SEL (U11: LOCK and TX toggling)
    u2 = sh.at_pin("MUX157", "U2", "74LVC1G157", "3", (node[0] + 22.86, y[1]),
                   fp="Package_TO_SOT_SMD:SOT-363_SC-70-6")
    sh.wire(node, u2.p("3"))
    i1, s_ = u2.p("1"), u2.p("6")
    xa, xl = i1[0] - 5.08, i1[0] - 17.78
    sh.wire(i1, (xa, i1[1]), (xl, i1[1])); sh.label("TX_REGEN", (xl, i1[1]), "L")
    sh.wire(s_, (xl, s_[1])); sh.label("TX_SEL", (xl, s_[1]), "L")
    # R9: TX_REGEN low while U9 is unpowered (Ioff: its output floats), for
    # U2's I1 and U11's B alike
    r9 = sh.at_pin("R", "R9", "10k", "1", (xa, s_[1] + 5.08), fp=SMD["R"])
    sh.wire((xa, i1[1]), r9.p("1"))
    sh.gnd(r9.p("2"))
    sh.decouple(u2.p("5"), "3V3_AON", "C11")
    sh.gnd(u2.p("2"))
    # Y -> R2 -> J1.TXD (loop under the parts)
    yy = u2.p("4")
    r2 = sh.at_pin("R", "R2", "150", "1", (yy[0] + 7.62, yy[1]), r=90, fp=SMD["R"])
    sh.wire(yy, r2.p("1"))
    txd = j1.p("1")
    lo = 184.15
    sh.wire(r2.p("2"), (r2.p("2")[0] + 5.08, yy[1]), (r2.p("2")[0] + 5.08, lo),
            (txd[0] + 7.62, lo), (txd[0] + 7.62, txd[1]), txd)
    sh.text("S = TX_SEL = 0: FPGA вимкнена, без захоплення або TX став -> прямий прохід RX -> TX.", 76.2, 190.5, 1.27)
    sh.text("S = 1 (LOCK і фронти TX, U11): TX = перегенерований сигнал з FPGA. Мережа нас не бачить.", 76.2, 194.31, 1.27)
    sh.text("R3 13k7: RGAIN -> TXVCC (AN 5344).", 17.78, 184.15, 1.27)
    sh.text("FB1/FB2 + 100n + 10u: RX і TX окремо.", 17.78, 187.96, 1.27)
    sh.text("R7: RXD у 0, коли приймач спить.", 17.78, 191.77, 1.27)


def isolation_block(sh):
    sh.frame(208.28, 106.68, 269.24, 198.12, "4. РОЗВ'ЯЗКА FPGA, ТРИГЕР TX")
    u3 = sh.add("BUF125", "U3", "74LVC1G125", 238.76, 134.62,
                fp="Package_TO_SOT_SMD:SOT-353_SC-70-5")
    sh.lbl("RX_BUF", u3.p("2"), 15.24, "L")
    oe = u3.p("1")
    sh.wire(oe, (oe[0] - 7.62, oe[1])); sh.gnd((oe[0] - 7.62, oe[1]), 5.08)
    sh.lbl("RX_IN", u3.p("4"), 10.16, "R")
    sh.decouple(u3.p("5"), "3V3_SW", "C12")
    sh.gnd(u3.p("3"))
    # U9 retimes the FPGA's TX on the Si514's own edge (CLK+, the edge the
    # FPGA itself runs on, through a series resistor of its own): the ring
    # sees the clean clock, not the FPGA's output jitter. Q goes to the mux and back into the FPGA, whose
    # clock loop measures the line exactly as the ring gets it.
    u9 = sh.add("FF79", "U9", "74LVC1G79", 238.76, 170.18,
                fp="Package_TO_SOT_SMD:SOT-353_SC-70-5")
    sh.lbl("TX_PRE", u9.p("1"), 10.16, "L")
    sh.lbl("RT_CLK", u9.p("2"), 10.16, "L")
    sh.decouple(u9.p("5"), "3V3_SW", "C16", rise=7.62)
    sh.gnd(u9.p("3"))
    q = u9.p("4")
    nq = (q[0] + 5.08, q[1])
    sh.lbl("TX_REGEN", q, 10.16, "R")
    r16 = sh.at_pin("R", "R16", "33", "1", (nq[0], nq[1] + 2.54), fp=SMD["R"],
                    ref_at=(nq[0] + 2.54, nq[1] + 3.81), val_at=(nq[0] + 2.54, nq[1] + 6.35),
                    fjust=("left", "left"))
    sh.wire(nq, r16.p("1"))
    sh.lbl("TX_FB", r16.p("2"), 5.08, "R")
    sh.text("U3, U9 від 3V3_SW: коли FPGA", 210.82, 184.15, 1.27)
    sh.text("вимкнена, вони (Ioff) не вантажать лінії.", 210.82, 187.96, 1.27)
    sh.text("U9: фронти TX на такті Si514 (RT_CLK).", 210.82, 191.77, 1.27)
    sh.text("Q -> U2 (TX_REGEN) і в FPGA (TX_FB).", 210.82, 195.58, 1.27)


def fpga_block(sh):
    sh.frame(274.32, 106.68, 406.4, 198.12, "5. FPGA   Sipeed Tang Nano 20K")
    m1 = sh.add("TANG", "M1", "Tang Nano 20K", 340.36, 151.13, fp="")
    # ring and Si514 signals only on pins whose sole other load is the empty
    # LCD FPC connector
    # TX_FB comes in through an 8:1 deserialiser (IDES8, 1.26 ns, like RX_IN);
    # that takes the whole IOB6 pair, so pad 11 (pin 26) stays unconnected
    left = {"1": "UART_RX_F", "2": "I2S_BCLK_F", "3": "I2S_LRCK_F", "4": "I2S_MCLK_F",
            "5": "CLK_1024", "8": "RX_IN", "9": "TX_PRE", "10": "TX_FB",
            "12": "SI_SCL", "13": "SI_SDA"}
    for n in map(str, range(1, 21)):
        p = m1.p(n)
        if n in left:
            sh.lbl(left[n], p, 10.16, "L")
        elif n == "19":
            sh.wire(p, (p[0] - 7.62, p[1])); sh.up("3V3_SW", (p[0] - 7.62, p[1]), 0)
        elif n == "20":
            sh.wire(p, (p[0] - 5.08, p[1])); sh.gnd((p[0] - 5.08, p[1]))
        else:
            sh.nc(p)
    right = {"23": "I2S_DOUT_F", "24": "SD1_F", "25": "BCLK_F", "26": "FS_F", "30": "SD0_F",
             "32": "LOCK", "33": "I2S_DIN_F", "37": "UART_TX_F", "38": "MCLK_F"}
    for n in map(str, range(21, 41)):
        p = m1.p(n)
        if n in right:
            sh.lbl(right[n], p, 10.16, "R")
        elif n == "21":
            # D3: 5V_SW only flows INTO the module, so plugging USB in on the
            # bench never ties two 5 V supplies together
            d3 = sh.at_pin("DS", "D3", "SS34", "1", (p[0] + 7.62, p[1]), fp="Diode_SMD:D_SMA",
                          ref_at=(p[0] + 11.43, p[1] - 3.81), val_at=(p[0] + 19.05, p[1] + 2.54),
                          fjust=(None, "left"))
            sh.wire(p, d3.p("1"))
            # the module's 5V net is fed through a diode: tell ERC it is driven
            fp_ = (p[0] + 2.54, p[1]); fq = (fp_[0], p[1] - 2.54)
            sh.wire(fp_, fq)
            sh.pwr += 1
            sh.add("FLAG", f"#FLG{sh.pwr:03d}", "PWR_FLAG", fq[0], fq[1], 0,
                   ref_at=(fq[0], fq[1] - 5.08), val_at=(fq[0], fq[1] - 3.81), show_val=False)
            a = d3.p("2")
            sh.wire(a, (a[0] + 2.54, a[1])); sh.up("5V_SW", (a[0] + 2.54, a[1]), 0)
        elif n in ("22", "35"):
            sh.wire(p, (p[0] + 5.08, p[1])); sh.gnd((p[0] + 5.08, p[1]))
        else:
            sh.nc(p)
    sh.text("Контакти 1..20 / 21..40 згори вниз, від USB-C; назва = вивід GW2AR + що на ньому на платі (datasheet v1.3).", 279.4, 184.15, 1.27)
    sh.text("Кільце і Si514 - лише на виводах LCD (порожній роз'єм). На HSPI і TF (80, 85) - лише UART, MCLK, I2S, SD1.", 279.4, 187.96, 1.27)
    sh.text("CLK_1024 (Si514) -> 77 (GCLKT_1). TX_FB -> 25 через IDES8 (1.26 нс); він займає пару, тому 26 не підключено.", 279.4, 191.77, 1.27)
    sh.text("D3: USB і 5V_SW разом не з'єднуються; U6 дає 5.3 В, на модулі ~5.0 В.", 279.4, 195.58, 1.27)


def clock_block(sh):
    sh.frame(12.7, 203.2, 203.2, 284.48,
             "6. ТАКТ ПЕРЕГЕНЕРАЦІЇ   Si514 = 1024 x FS кільця (45.16 / 49.15 МГц), крутить FPGA")
    # U8: a quiet 3.3 V of the clock's own, from 5V_SW (on with the FPGA)
    u8 = sh.add("LDO_CLK", "U8", "LP5907MFX-3.3", 48.26, 218.44,
                fp="Package_TO_SOT_SMD:SOT-23-5")
    vin, en = u8.p("1"), u8.p("3")
    xr = vin[0] - 7.62
    sh.wire(vin, (xr, vin[1]))
    sh.up("5V_SW", (xr, vin[1]), 2.54)
    sh.wire(en, (vin[0] - 5.08, en[1]), (vin[0] - 5.08, vin[1]))
    c15 = sh.at_pin("C", "C15", "1u", "1", (xr - 7.62, vin[1]), fp=SMD["C"])
    sh.wire((xr, vin[1]), c15.p("1")); sh.gnd(c15.p("2"))
    sh.nc(u8.p("4"))
    sh.gnd(u8.p("2"))
    # U7: the Si514, whichever 3.3 V CMOS part was in stock: one symbol, three
    # land patterns (5x7, 3.2x5, 2.5x3.2), one of them soldered. VDD from U8
    # on a real wire, 1u at U8 and a 100n beside each land pattern.
    u7 = sh.add("SI514", "U7", "Si514", 99.06, 243.84, fp=f"{LIB}:{FP_SI514}")
    vo, vdd = u8.p("5"), u7.p("6")
    c14 = sh.at_pin("C", "C14", "1u", "1", (vo[0] + 7.62, vo[1]), fp=SMD["C"])
    sh.wire(vo, c14.p("1"), (vdd[0], vo[1]), vdd)
    sh.gnd(c14.p("2"))
    nd = (vdd[0], vo[1] + 5.08)
    caps = [sh.at_pin("C", ref, "100n", "1", (vdd[0] + 10.16 * (i + 1), nd[1]), fp=SMD["C"])
            for i, ref in enumerate(("C13", "C21", "C22"))]
    sh.wire(nd, *[c.p("1") for c in caps])
    for c in caps:
        sh.gnd(c.p("2"))
    sh.gnd(u7.p("3"))
    # I2C on its own two FPGA pins; pull-ups to the FPGA's 3.3 V. SDA runs
    # further left than the SCL label, so R12 rises clear of the SCL line.
    scl, sda = u7.p("2"), u7.p("1")
    sh.lbl("SI_SCL", scl, 12.7, "L")
    sh.lbl("SI_SDA", sda, 35.56, "L")
    r11 = sh.at_pin("R", "R11", "2k", "2", (scl[0] - 5.08, scl[1]), fp=SMD["R"])
    sh.up("3V3_SW", r11.p("1"), 2.54)
    r12 = sh.at_pin("R", "R12", "2k", "2", (sda[0] - 27.94, sda[1]), fp=SMD["R"])
    sh.up("3V3_SW", r12.p("1"), 2.54)
    # CLK+ feeds the FPGA (clk_r) and U9 (the retiming flip-flop), each through
    # its own 22R at the source. Both lines get a pull-down: while the Si514
    # is centred its output is disabled, and disabled means high impedance
    # (OE_STATE = 00, the default). CLK- is not used - a single-output part
    # (format C) has none; the branch to R15 runs below its pin to show it.
    cp, cm = u7.p("4"), u7.p("5")
    sh.nc(cm)
    # texts of the two series resistors: R10 above its line, R15 below its own
    r10 = sh.at_pin("R", "R10", "22", "1", (cp[0] + 5.08, cp[1]), r=90, fp=SMD["R"],
                    ref_at=(cp[0] + 8.89, cp[1] - 5.08), val_at=(cp[0] + 8.89, cp[1] - 2.54))
    sh.wire(cp, r10.p("1"))
    np_ = (r10.p("2")[0] + 20.32, cp[1])
    sh.wire(r10.p("2"), np_)
    r14 = sh.at_pin("R", "R14", "10k", "1", (np_[0], np_[1] + 2.54), fp=SMD["R"])
    sh.wire(np_, r14.p("1")); sh.gnd(r14.p("2"))
    sh.lbl("CLK_1024", np_, 7.62, "R")
    yb = cm[1] + 2.54                                     # the U9 branch, below CLK-
    nb = (cp[0] + 2.54, cp[1])
    r15 = sh.at_pin("R", "R15", "22", "1", (r10.p("1")[0], yb), r=90, fp=SMD["R"],
                    ref_at=(cp[0] + 8.89, yb + 2.54), val_at=(cp[0] + 8.89, yb + 5.08))
    sh.wire(nb, (nb[0], yb), r15.p("1"))
    nm = (r15.p("2")[0] + 2.54, yb)
    sh.wire(r15.p("2"), nm)
    r17 = sh.at_pin("R", "R17", "10k", "1", (nm[0], nm[1] + 2.54), fp=SMD["R"])
    sh.wire(nm, r17.p("1")); sh.gnd(r17.p("2"))
    sh.lbl("RT_CLK", nm, 5.08, "R")
    y = 265.43
    for line in (
        "U7 Si514: будь-який з полиці з 3.3 В CMOS - у номері після 514 літера C, M або N. Під U7 три посадкові місця (5x7, 3.2x5, 2.5x3.2): паяти одне.",
        "CLK+ -> FPGA (clk_r = 1024 Fs) і через R15 на U9: фронти TX стоять на такті Si514, а не на виході FPGA. CLK- не потрібен.",
        "FPGA сама знаходить I2C адресу Si514 (перебирає 0x08..0x77) і крутить M (dpll.v): затримка TX_FB відносно RX_IN до 1.26 нс, крок 0.026 ppb.",
        "На старті центрування (FCAL, до 10 мс): вихід Si514 тоді у високому імпедансі, R14 і R17 тримають лінії в 0. U8: окремий LDO з 5V_SW.",
    ):
        sh.text(line, 17.78, y, 1.27)
        y += 3.81


def output_block(sh):
    sh.frame(208.28, 203.2, 406.4, 284.48, "7. ВИХОДИ   J2: аналізатор (MCLK, 2 x TDM8, UART_TX);   J3: стерео I2S для ЦАП / DSP")

    def series(j, rows, rn_ref, singles):
        """rows: (src label, connector pin) through one 4x33 array, top to bottom;
        singles: (src label, connector pin, ref, text side) through their own 33 R;
        the reference and value go on the side where no wire runs."""
        top = j.p(rows[0][1])
        rn = sh.at_pin("RN4", rn_ref, "4x33", "4", (top[0] - 20.32, top[1]), r=90,
                       fp="Resistor_SMD:R_Array_Convex_4x0603",
                       ref_at=(top[0] - 25.4, top[1] - 5.08), val_at=(top[0] - 20.32, top[1] - 5.08))
        xlab = rn.p("8")[0] - 20.32
        # RN4 rotated 90: left pins 5,6,7,8 top->bottom, right pins 4,3,2,1
        for (src, jp), lp, rp in zip(rows, "5678", "4321"):
            sh.wire(rn.p(rp), j.p(jp))
            sh.lbl(src, rn.p(lp), rn.p(lp)[0] - xlab, "L")
        for src, jp, ref, side in singles:
            m = j.p(jp)
            dy = -2.54 if side == "up" else 2.54
            r = sh.at_pin("R", ref, "33", "2", (xlab + 10.16, m[1]), r=90, fp=SMD["R"],
                          ref_at=(xlab + 6.35, m[1] + dy), val_at=(xlab + 11.43, m[1] + dy))
            sh.wire(r.p("2"), m)
            sh.lbl(src, r.p("1"), r.p("1")[0] - xlab, "L")

    def grounds(j, pins, stub=2.54):
        gx = j.p(pins[0])[0] - 5.08
        for n in pins:
            sh.wire(j.p(n), (gx, j.p(n)[1]))
        sh.wire((gx, j.p(pins[0])[1]), (gx, j.p(pins[-1])[1]))
        sh.gnd((gx, j.p(pins[-1])[1]), stub)

    # J2: analyser (TDM, raw control blocks)
    j2 = sh.add("CONN8", "J2", "ANALYSER", 373.38, 232.41,
                fp="Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical")
    series(j2, [("BCLK_F", "2"), ("FS_F", "3"), ("SD0_F", "4"), ("SD1_F", "5")], "RN1",
           [("MCLK_F", "1", "R19", "up"), ("UART_TX_F", "6", "R18", "down")])
    grounds(j2, ("7", "8"))

    # J3: stereo I2S to a DAC / DSP
    j3 = sh.add("CONN_I2S", "J3", "I2S", 289.56, 233.68,
                fp="Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical")
    series(j3, [("I2S_MCLK_F", "1"), ("I2S_BCLK_F", "2"), ("I2S_LRCK_F", "3"), ("I2S_DOUT_F", "4")],
           "RN2", [])
    grounds(j3, ("5", "6"))

    y = 252.73
    for line in (
        "J2 SD0/SD1: байти кадру 0..31 / 32..63, кадр TDM = кадр MOST.",
        "J2 UART_TX: сирі керувальні блоки (ті самі, що читає M2).",
        "J3: I2S, BCLK 64 Fs, слоти 32 біт, 24 біт з регулюваннями ГУ.",
        "Входів на J2 і J3 немає: хост один - M2 (блок 8).",
        "RN1, RN2, R18..R21 (33 Ом) - біля виводів FPGA.",
        "MCLK на J2 і J3 - з окремих виводів FPGA, без відгалуження.",
    ):
        sh.text(line, 213.36, y, 1.27)
        y += 3.81


def host_block(sh):
    sh.frame(335.28, 12.7, 406.4, 101.6, "8. ХОСТ   M2 = ESP32-DevKitC-VIE")
    m2 = sh.add("DEVKITC", "M2", "ESP32-DevKitC-VIE", 375.92, 50.8, fp="")
    # from the FPGA: the ring-locked I2S clocks and the raw control blocks
    for pad, name in (("5", "I2S_BCLK_F"), ("6", "I2S_LRCK_F"), ("8", "UART_TX_F")):
        sh.lbl(name, m2.p(pad), 12.7, "L")
    # into the FPGA: host commands and our audio, each through 33R at the FPGA
    # pin; the texts go below, onto the unused row
    for pad, ref, name in (("9", "R20", "UART_RX_F"), ("11", "R21", "I2S_DIN_F")):
        q = m2.p(pad)
        r = sh.at_pin("R", ref, "33", "2", (q[0] - 2.54, q[1]), r=90, fp=SMD["R"],
                      ref_at=(q[0] - 7.62, q[1] + 2.54), val_at=(q[0] - 3.81, q[1] + 2.54))
        sh.wire(q, r.p("2"))
        sh.lbl(name, r.p("1"), 2.54, "L")
    sh.lbl("5V_HOST", m2.p("19"), 12.7, "L")
    g = m2.p("14")
    sh.wire(g, (g[0] - 5.08, g[1]))
    sh.gnd((g[0] - 5.08, g[1]), 2.54)
    gx = m2.p("20")[0] + 5.08
    for pad in ("20", "26"):
        sh.wire(m2.p(pad), (gx, m2.p(pad)[1]))
    sh.wire((gx, m2.p("20")[1]), (gx, m2.p("26")[1]))
    sh.gnd((gx, m2.p("26")[1]), 2.54)
    used = {"5", "6", "8", "9", "11", "14", "19", "20", "26"}
    for n in map(str, range(1, 39)):
        if n not in used:
            sh.nc(m2.p(n))
    y = 81.28
    for line in (
        "M2: ESP32-DevKitC-VIE (WROVER-IE): 8 МБ PSRAM,",
        "антена IPEX (виносна, 2.4 ГГц), -40...85 °C.",
        "Гнізда 2 x 1x19, крок 2.54, між рядами 25.40 мм.",
        "5V_HOST -> 5V; USB модуля - через його діод.",
        "UART 3 Мбод: IO33 <- UART_TX, IO25 -> UART_RX.",
        "I2S slave: IO34/35 <- BCLK/LRCK, IO27 -> DIN.",
    ):
        sh.text(line, 337.82, y, 1.27)
        y += 3.81


def build():
    sh = Sheet()
    power_block(sh)
    wake_block(sh)
    optics_block(sh)
    isolation_block(sh)
    fpga_block(sh)
    clock_block(sh)
    output_block(sh)
    host_block(sh)
    return sh


def main():
    sh = build()
    out = HERE / f"{PROJECT}.kicad_sch"
    sh.write(out)
    (HERE / f"{PROJECT}.kicad_pro").write_text(
        '{"meta": {"filename": "%s.kicad_pro", "version": 3}, "schematic": {}}\n' % PROJECT,
        encoding="utf-8")
    # project symbol library + table, so the sheet opens with no "missing
    # library" warnings and the parts can be reused
    own = [sym.text.replace(f'(symbol "{LIB}:', '(symbol "', 1)
           for sym in S.values() if sym.lib_id.startswith(LIB + ":")]
    (HERE / f"{LIB}.kicad_sym").write_text(
        '(kicad_symbol_lib (version 20231120) (generator "gen_listener")\n'
        + "\n".join(own) + "\n)\n", encoding="utf-8")
    fp, cu, clear, size = si514_footprint()
    assert cu >= 0.2 and clear > 0, (cu, clear)
    (HERE / f"{LIB}.pretty").mkdir(exist_ok=True)
    (HERE / f"{LIB}.pretty" / f"{FP_SI514}.kicad_mod").write_text(fp, encoding="utf-8")
    (HERE / "fp-lib-table").write_text(
        '(fp_lib_table (version 7)\n'
        f'  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB}.pretty")(options "")'
        '(descr "Project footprints, written by gen_listener.py"))\n)\n', encoding="utf-8")
    print(f"wrote {FP_SI514}: {size[0]:.2f} x {size[1]:.2f} mm courtyard, "
          f"copper gap between pins >= {cu:.2f} mm, bodies clear of other pads by >= {clear:.2f} mm")
    (HERE / "sym-lib-table").write_text(
        '(sym_lib_table (version 7)\n'
        f'  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB}.kicad_sym")(options "")'
        '(descr "Project symbols, written by gen_listener.py"))\n)\n', encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
