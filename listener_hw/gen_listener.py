#!/usr/bin/env python3
"""gen_listener.py - the MOST25 to AUDIO listener board, rev 1.4, as one KiCad 10 sheet.

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
  TPS7B8133DRV, LP5907MFX                          - KiCad 10 library symbols
  LMR38020 (HSOIC-8, DDA)                          - TI SNVSC40E: Table 6-1 (pins),
                                                     8-1 (RT), 9-1 (L, COUT), 9.2.2.6 (CIN)
  TPS2553DBV (1 IN, 2 GND, 3 EN, 4 FAULT, 5 ILIM,
              6 OUT)                               - TI SLVS841F
  ESP32-DevKitC V4 headers (J2 = pads 1..19,
                            J3 = pads 20..38)     - Espressif ESP32-DevKitC user
                                                     guide and dimension drawing
                                                     (rows 25.40 mm apart)
  TE 1-1394640-1 (MOST FOT header)                 - usb2most v3 schematic, a
                                                     board proven on a real car;
                                                     Rext and supply filters per
                                                     Avago AN 5344 / AFBR-1013 data sheet;
                                                     pin allocation TE 114-18997 A3 4.1
  TE MOST pigtail FOT footprint                    - TE customer view model drawing
                                                     C-2-2141577-1 B (2:1 views, measured:
                                                     front view for x, side view for
                                                     depth), hole for hole the same as
                                                     usb2most's TYCO_1_1394640_1 (GPLv3)
  Tang Nano 20K header pads                        - Sipeed pin label drawing
  DIR9001 (TSSOP-28)                               - TI SLES198A: Pin Functions,
                                                     Tables 4, 6, 13, section 8.3.3
  SRC4192 (SSOP-28, DB)                            - TI SBFS022C: Pin Functions,
                                                     Tables 1, 2, 3, section 7.4.1
  PLR135/T10, PLT133/T10W (TOSLINK)                - Everlight data sheets DPL-135-017
                                                     Rev 2 (1 Vcc, 2 GND, 3 Vout) and
                                                     DPL-0000049 Rev.5 (1 Vin, 2 Vcc, 3 GND):
                                                     pin functions, the PCB layouts and the
                                                     package drawing (third-angle)
  BKL 0101153 RCA jack                             - BKL TDS drawing (P.C.B Layout 2:1,
                                                     side and front views)
  Tang Nano 20K, ESP32-DevKitC V4 outlines         - Sipeed data sheet v1.3 p.5-6;
                                                     Espressif dimensions drawing
  ASE-xxxMHz oscillator, Conn_Coaxial              - KiCad 10 library symbols
  PCM5102A (TSSOP-20)                              - TI SLAS859C: Pin Functions, 9.3.3
                                                     (XSMT), 10.1.1 (Figure 33: supplies,
                                                     CAPP-CAPM, VNEG, LDOO, 470R + 2.2 nF),
                                                     11.1 (LDOO 0.1 uF); pin numbers also
                                                     equal KiCad's Audio:PCM5100 symbol
  LP5907 output capacitance 0.7..10 uF             - TI LP5907 data sheet, Recommended
                                                     Operating Conditions
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
    "3V3_DA": rail("3V3_DA"),
    "3V3_DAC": rail("3V3_DAC"),
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
    "BUCK": ic("LMR38020DDA", "U", 17.78, 17.78, [
        ("3", "VIN", "power_in", "L", 2.54), ("4", "RT/SYNC", "input", "L", 8.89),
        ("2", "EN", "input", "L", 15.24),
        ("7", "BOOT", "passive", "R", 2.54), ("8", "SW", "power_out", "R", 10.16),
        ("5", "FB", "input", "R", 12.7), ("6", "PG", "open_collector", "R", 15.24),
        ("1", "GND", "power_in", "B", 3.81), ("9", "EP", "passive", "B", 7.62),
    ], "4.2-80 V, 2 A synchronous buck, 400 kHz set by RT, forced PWM (F)"),
    "DZ": from_kicad("Device", "D_Zener"),
    "CP": from_kicad("Device", "C_Polarized"),
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
        ("1", "SD0", "passive", "L", 2.54), ("2", "SD1", "passive", "L", 5.08),
        ("3", "FS", "passive", "L", 7.62), ("4", "MCLK", "passive", "L", 10.16),
        ("5", "UART_TX", "passive", "L", 12.7), ("6", "BCLK", "passive", "L", 15.24),
        ("7", "GND", "passive", "L", 17.78), ("8", "GND", "passive", "L", 20.32),
    ], "Analyser: MCLK 512 Fs, TDM (2 x TDM8), raw control blocks on UART"),
    "TOSLINK_RX": ic("PLR135", "J", 15.24, 12.7, [
        ("3", "VOUT", "output", "R", 3.81),
        ("1", "VCC", "power_in", "T", 7.62), ("2", "GND", "power_in", "B", 7.62),
    ], "TOSLINK receiver, 2.4-5.5 V, 16 Mbps (Everlight PLR135/T10: 1 Vcc, 2 GND, 3 Vout; 4 and 5 are the pegs)"),
    "TOSLINK_TX": ic("PLT133", "J", 15.24, 12.7, [
        ("1", "VIN", "input", "L", 3.81),
        ("2", "VCC", "power_in", "T", 7.62), ("3", "GND", "power_in", "B", 7.62),
    ], "TOSLINK transmitter, 2.7-5.5 V, 16 Mbps (Everlight PLT133/T10W: 1 Vin, 2 Vcc, 3 GND; 4 and 5 are the pegs)"),
    "DIR9001": ic("DIR9001", "U", 40.64, 43.18, [
        ("21", "RST", "input", "L", 5.08), ("20", "RXIN", "input", "L", 10.16), ("27", "ERROR", "output", "L", 15.24),
        ("1", "AUDIO", "output", "L", 17.78), ("22", "FILT", "passive", "L", 20.32), ("7", "XTO", "output", "L", 30.48),
        ("11", "BCKO", "output", "R", 5.08), ("10", "LRCKO", "output", "R", 7.62), ("12", "DOUT", "output", "R", 10.16),
        ("4", "SCKO", "output", "R", 15.24), ("17", "EMPH", "output", "R", 20.32),
        ("2", "FSOUT0", "output", "R", 22.86), ("3", "FSOUT1", "output", "R", 25.4), ("18", "BFRAME", "output", "R", 27.94),
        ("9", "CLKST", "output", "R", 30.48), ("15", "COUT", "output", "R", 33.02), ("16", "UOUT", "output", "R", 35.56),
        ("5", "VDD", "power_in", "T", 7.62), ("24", "VCC", "power_in", "T", 12.7),
        ("26", "FMT1", "input", "T", 25.4), ("25", "FMT0", "input", "T", 30.48),
        ("6", "DGND", "power_in", "B", 5.08), ("23", "AGND", "power_in", "B", 10.16),
        ("14", "PSCK1", "input", "B", 17.78), ("13", "PSCK0", "input", "B", 20.32), ("28", "CKSEL", "input", "B", 22.86),
        ("19", "RSV", "input", "B", 25.4), ("8", "XTI", "input", "B", 27.94),
    ], "S/PDIF receiver, PLL clock recovery, 24-bit I2S out, hardware mode (TI SLES198A)"),
    "SRC4192": ic("SRC4192", "U", 45.72, 43.18, [
        ("5", "BCKI", "input", "L", 5.08), ("6", "LRCKI", "input", "L", 7.62), ("4", "SDIN", "input", "L", 10.16),
        ("2", "RCKI", "input", "L", 17.78),
        ("23", "SDOUT", "output", "R", 5.08), ("25", "BCKO", "input", "R", 7.62), ("24", "LRCKO", "input", "R", 10.16),
        ("15", "RDY", "output", "R", 15.24), ("14", "MUTE", "input", "R", 17.78), ("13", "RST", "input", "R", 20.32), ("3", "NC", "no_connect", "R", 25.4),
        ("22", "VDD", "power_in", "T", 7.62), ("7", "VIO", "power_in", "T", 12.7),
        ("10", "IFMT0", "input", "T", 27.94), ("19", "OFMT0", "input", "T", 33.02),
        ("8", "DGND", "power_in", "B", 5.08), ("21", "DGND", "power_in", "B", 7.62),
        ("11", "IFMT1", "input", "B", 12.7), ("12", "IFMT2", "input", "B", 15.24),
        ("26", "MODE0", "input", "B", 17.78), ("27", "MODE1", "input", "B", 20.32), ("28", "MODE2", "input", "B", 22.86),
        ("1", "LGRP", "input", "B", 25.4), ("9", "BYPAS", "input", "B", 27.94),
        ("20", "TDMI", "input", "B", 33.02), ("17", "OWL0", "input", "B", 35.56), ("16", "OWL1", "input", "B", 38.1),
        ("18", "OFMT1", "input", "B", 40.64),
    ], "Asynchronous sample rate converter, both ports slave, 24-bit I2S in and out (TI SBFS022C)"),
    "OSC": from_kicad("Oscillator", "ASE-xxxMHz"),
    "COAX": from_kicad("Connector", "Conn_Coaxial"),
    "TP": from_kicad("Connector", "TestPoint"),
    "CONN_I2S": ic("Conn_I2S", "J", 15.24, 17.78, [
        ("1", "MCLK", "passive", "L", 2.54), ("2", "DOUT", "passive", "L", 5.08),
        ("3", "LRCK", "passive", "L", 7.62), ("4", "BCLK", "passive", "L", 10.16),
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

S["PCM5102A"] = ic("PCM5102A", "U", 40.64, 50.8, [
    ("13", "BCK", "input", "L", 5.08), ("15", "LRCK", "input", "L", 7.62), ("14", "DIN", "input", "L", 10.16),
    ("17", "XSMT", "input", "L", 15.24), ("12", "SCK", "input", "L", 22.86), ("16", "FMT", "input", "L", 25.4),
    ("11", "FLT", "input", "L", 27.94), ("10", "DEMP", "input", "L", 30.48),
    ("6", "OUTL", "output", "R", 5.08), ("7", "OUTR", "output", "R", 20.32), ("2", "CAPP", "passive", "R", 27.94),
    ("4", "CAPM", "passive", "R", 35.56), ("5", "VNEG", "passive", "R", 40.64), ("18", "LDOO", "passive", "R", 45.72),
    ("1", "CPVDD", "power_in", "T", 10.16), ("8", "AVDD", "power_in", "T", 20.32), ("20", "DVDD", "power_in", "T", 30.48),
    ("3", "CPGND", "power_in", "B", 10.16), ("9", "AGND", "power_in", "B", 20.32), ("19", "DGND", "power_in", "B", 30.48),
], "2.1 Vrms ground-centred stereo DAC, 112 dB, PLL from BCK (3-wire I2S), hardware mode (TI SLAS859C)")

# the line-out buffer (2026-10-01): a dual op-amp, drawn with channel B (left audio) on the top
# edge and channel A (right) on the bottom edge, so each Sallen-Key row runs past it without a
# crossing; the supplies on the right side
S["OPA1678"] = ic("OPA1678", "U", 10.16, 10.16, [
    ("5", "+B", "input", "T", 2.54), ("6", "-B", "input", "T", 5.08), ("7", "OB", "output", "T", 7.62),
    ("3", "+A", "input", "B", 2.54), ("2", "-A", "input", "B", 5.08), ("1", "OA", "output", "B", 7.62),
    ("8", "V+", "power_in", "R", 3.81), ("4", "V-", "power_in", "R", 6.35),
], "Dual audio op-amp, 4.5-36 V, rail-to-rail output, input to V- (TI SBOS783)")
S["TPS60403"] = ic("TPS60403", "U", 17.78, 10.16, [
    ("2", "IN", "power_in", "L", 5.08), ("1", "OUT", "power_out", "R", 5.08),
    ("5", "C+", "passive", "T", 5.08), ("3", "C-", "passive", "T", 12.7),
    ("4", "GND", "power_in", "B", 8.89),
], "Unregulated charge-pump inverter, 1.6-5.5 V in, 60 mA, 250 kHz (TI SLVS324)")
S["VNEG_A"] = rail("VNEG_A")

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
            val_at=None, fjust=None, bom=True):
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
            f'(exclude_from_sim no) (in_bom {"no" if is_pwr or not bom else "yes"}) (on_board yes) '
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
            f'(generator_version "10.0") (uuid "{uid("root")}") (paper "A2")\n'
            f'(title_block (title "MOST25 to AUDIO: listener board") (date "2026-10-02") '
            f'(rev "1.4") (comment 1 "Generated by listener_hw/gen_listener.py") '
            f'(comment 2 "Repeater with regeneration and a bypass watchdog; FPGA; ESP32 host; TDM, UART, I2S out; '
            f'S/PDIF in and out"))\n'
            f'(lib_symbols\n{libs}\n)\n{body}\n'
            f'(sheet_instances (path "/" (page "1")))\n)\n', encoding="utf-8")


SMD = {"R": "Resistor_SMD:R_0603_1608Metric", "C": "Capacitor_SMD:C_0603_1608Metric"}


# --------------------------------------------------------------- footprint
FP_SI514 = "Si514_3.2x5_2.5x3.2"
# Si514 land patterns, data sheet Rev 1.2, Tables 17, 19 and 21, in the data
# sheet's orientation: two pad columns C1 apart, pins P apart, pads W across x
# by H along the pitch; pin 1 top left, 1-2-3 down the left column, 4-5-6 up
# the right. Same pinout in all three packages (Table 15). The 5x7 stays in the
# table for reference only: since v1.4 U7 takes the 3.2x5 and the 2.5x3.2.
SI514_PKG = {
    #          C1    P     W     H     body w x h
    "5x7":     (4.20, 2.54, 1.95, 1.55, 5.0, 7.0),
    "3.2x5":   (2.60, 1.27, 1.70, 0.80, 3.2, 5.0),
    "2.5x3.2": (1.90, 1.25, 1.05, 0.70, 2.5, 3.2),
}


def si514_layout():
    """U7's one land pattern (v1.4): the 3.2x5 pads (Table 19) with their inner
    edge moved in to that of the 2.5x3.2 pads (Table 21), so either package sits
    on it - the 2.5x3.2 pads lie inside the 3.2x5 ones but for 0.025 mm on the
    inner edge (pitch 1.25 against 1.27 stays inside the 0.80 pad). The 5x7 does
    not nest - its pin 2 pad would come 0.1 mm from their pin 1 - and the shelf
    stock is 3.2x5, so it is dropped. Returns [(package, centre, rotation,
    pads {num: (x, y, w, h)}, body (w, h))]; the 2.5x3.2 entry carries no pads
    of its own, only its body outline."""
    side = {"1": (-1, -1), "2": (-1, 0), "3": (-1, 1), "4": (1, 1), "5": (1, 0), "6": (1, -1)}
    cb, pb, wb, hb = SI514_PKG["3.2x5"][:4]
    cc, pc, wc, hc = SI514_PKG["2.5x3.2"][:4]
    inner = min(cb / 2 - wb / 2, cc / 2 - wc / 2)
    outer = max(cb / 2 + wb / 2, cc / 2 + wc / 2)
    for sy in (-1, 0, 1):                    # the small package's pads inside the big ones
        assert sy * pb - hb / 2 <= sy * pc - hc / 2 and sy * pc + hc / 2 <= sy * pb + hb / 2
    pads = {n: (sx * (inner + outer) / 2, sy * pb, outer - inner, hb) for n, (sx, sy) in side.items()}
    return [("3.2x5", (0.0, 0.0), 0, pads, SI514_PKG["3.2x5"][4:]),
            ("2.5x3.2", (0.0, 0.0), 0, {}, SI514_PKG["2.5x3.2"][4:])]




# ------------------------------------------- footprints from the makers' drawings
def _fpl(x1, y1, x2, y2, layer, w, key):
    return (f'\t(fp_line (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) '
            f'(stroke (width {f(w)}) (type solid)) (layer "{layer}") (uuid "{uid(key)}"))')


def _fpbox(x1, y1, x2, y2, layer, w, key):
    pts = ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1))
    return "\n".join(_fpl(*p, layer, w, key + str(i)) for i, p in enumerate(pts))


def _fppad(num, kind, shape, x, y, sx, sy, drill, key):
    d = f" (drill {f(drill)})" if drill else ""
    return (f'\t(pad "{num}" {kind} {shape} (at {f(x)} {f(y)}) (size {f(sx)} {f(sy)}){d} '
            f'(layers "*.Cu" "*.Mask") (uuid "{uid(key)}"))')


def _fptext(s, x, y, layer, size, key, kind=None):
    head = f'(property "{kind}" "{s}"' if kind else f'(fp_text user "{s}"'
    return (f'\t{head} (at {f(x)} {f(y)} 0) (layer "{layer}") (uuid "{uid(key)}") '
            f'(effects (font (size {f(size)} {f(size)}) (thickness {f(size * 0.15)}))))')


def _fpdot(x, y, key):
    return (f'\t(fp_circle (center {f(x)} {f(y)}) (end {f(x + 0.15)} {f(y)}) '
            f'(stroke (width 0.1) (type solid)) (fill yes) (layer "F.SilkS") (uuid "{uid(key)}"))')


def _fpmodel(lib, name, x, y):
    """KiCad's 3D model lib/name with its origin at (x, y) of the footprint; the 3D offset's y
    points up, the board's down."""
    return (f'\t(model "${{KICAD10_3DMODEL_DIR}}/{lib}.3dshapes/{name}.step"\n'
            f'\t\t(offset (xyz {f(x)} {f(-y)} 0))\n\t\t(scale (xyz 1 1 1))\n\t\t(rotate (xyz 0 0 0))\n\t)')


# ------------------------------------------- 3D bodies from the same drawings, as STEP
MODELS = f"{LIB}.3dshapes"      # next to the project; the footprints reach it through ${KIPRJMOD}


def _own_model(name):
    """The body this script writes for footprint `name` (MODELS/name.step), at the footprint's origin."""
    return (f'\t(model "${{KIPRJMOD}}/{MODELS}/{name}.step"\n'
            f'\t\t(offset (xyz 0 0 0))\n\t\t(scale (xyz 1 1 1))\n\t\t(rotate (xyz 0 0 0))\n\t)')


def _box(x0, x1, y0, y1, z0, z1):
    """A box in the footprint's frame (y as the footprint's, z up from the board), as its six faces."""
    p = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    return [[p[i] for i in q] for q in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4),
                                        (1, 3, 7, 5))]


def _cyl(axis, c, r, a0, a1, n=32):
    """A cylinder of radius r along the footprint's y or z through c (the other two coordinates,
    (x, z) or (x, y)), from a0 to a1, as an n-sided prism."""
    ring = [(r * math.cos(2 * math.pi * (k + 0.5) / n), r * math.sin(2 * math.pi * (k + 0.5) / n)) for k in range(n)]

    def pt(u, v, a):
        return (c[0] + u, a, c[1] + v) if axis == "y" else (c[0] + u, c[1] + v, a)
    e0, e1 = [pt(u, v, a0) for u, v in ring], [pt(u, v, a1) for u, v in ring]
    return [e0, e1] + [[e0[k], e0[(k + 1) % n], e1[(k + 1) % n], e1[k]] for k in range(n)]


def _step(name, solids):
    """An AP214 STEP file of convex, planar-faced solids [(rgb, faces)], each face a list of
    corners in the footprint's frame. KiCad's model frame has the footprint's x, the other y and z
    up, so y is turned over here; every face is then wound so that its normal points away from
    its solid's centre. The date is fixed, so the file is the same on every run."""
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
    mm = e("( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) )")
    rad = e("( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) )")
    sr = e("( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() )")
    unc = e(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),{mm},'distance_accuracy_value',"
            f"'confusion accuracy')")
    ctx = e(f"( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT(({unc})) "
            f"GLOBAL_UNIT_ASSIGNED_CONTEXT(({mm},{rad},{sr})) "
            f"REPRESENTATION_CONTEXT('Context #1','3D Context with UNIT and UNCERTAINTY') )")
    o, z, x = cp((0, 0, 0)), dr((0, 0, 1)), dr((1, 0, 0))
    items, styles = [e(f"AXIS2_PLACEMENT_3D('',{o},{z},{x})")], []
    for k, (rgb, faces) in enumerate(solids):
        faces = [[(round(p[0], 4), round(-p[1], 4), round(p[2], 4)) for p in fc] for fc in faces]
        corners = [p for fc in faces for p in fc]
        mid = [sum(p[i] for p in corners) / len(corners) for i in range(3)]
        verts, edges, fents = {}, {}, []
        for fc in faces:
            n = [0.0, 0.0, 0.0]                     # Newell's normal
            for i, a in enumerate(fc):
                b = fc[(i + 1) % len(fc)]
                n[0] += (a[1] - b[1]) * (a[2] + b[2])
                n[1] += (a[2] - b[2]) * (a[0] + b[0])
                n[2] += (a[0] - b[0]) * (a[1] + b[1])
            fm = [sum(p[i] for p in fc) / len(fc) for i in range(3)]
            if sum(n[i] * (fm[i] - mid[i]) for i in range(3)) < 0:
                fc, n = fc[::-1], [-v for v in n]
            for p in fc:
                if p not in verts:
                    verts[p] = e(f"VERTEX_POINT('',{cp(p)})")
            oes = []
            for i, a in enumerate(fc):
                b = fc[(i + 1) % len(fc)]
                key = (a, b) if a < b else (b, a)
                if key not in edges:
                    d = [key[1][j] - key[0][j] for j in range(3)]
                    vec = e(f"VECTOR('',{dr(d)},{r(math.sqrt(sum(v * v for v in d)))})")
                    line = e(f"LINE('',{cp(key[0])},{vec})")
                    edges[key] = e(f"EDGE_CURVE('',{verts[key[0]]},{verts[key[1]]},{line},.T.)")
                oes.append(e(f"ORIENTED_EDGE('',*,*,{edges[key]},{'.T.' if key == (a, b) else '.F.'})"))
            loop = e(f"EDGE_LOOP('',({','.join(oes)}))")
            bound = e(f"FACE_OUTER_BOUND('',{loop},.T.)")
            ax = e(f"AXIS2_PLACEMENT_3D('',{cp(fc[0])},{dr(n)},{dr([fc[1][j] - fc[0][j] for j in range(3)])})")
            fents.append(e(f"ADVANCED_FACE('',({bound}),{e(f'PLANE({chr(39) * 2},{ax})')},.T.)"))
        shell = e(f"CLOSED_SHELL('',({','.join(fents)}))")
        brep = e(f"MANIFOLD_SOLID_BREP('{name}_{k}',{shell})")
        items.append(brep)
        col = e(f"COLOUR_RGB('',{r(rgb[0])},{r(rgb[1])},{r(rgb[2])})")
        fill = e(f"FILL_AREA_STYLE('',({e(f'FILL_AREA_STYLE_COLOUR({chr(39) * 2},{col})')}))")
        side = e(f"SURFACE_SIDE_STYLE('',({e(f'SURFACE_STYLE_FILL_AREA({fill})')}))")
        psa = e(f"PRESENTATION_STYLE_ASSIGNMENT(({e(f'SURFACE_STYLE_USAGE(.BOTH.,{side})')}))")
        styles.append(e(f"STYLED_ITEM('color',({psa}),{brep})"))
    shape = e(f"ADVANCED_BREP_SHAPE_REPRESENTATION('{name}',({','.join(items)}),{ctx})")
    e(f"SHAPE_DEFINITION_REPRESENTATION({pds},{shape})")
    e(f"MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',({','.join(styles)}),{ctx})")
    return ("ISO-10303-21;\nHEADER;\n"
            f"FILE_DESCRIPTION(('{name}, drawn by gen_listener.py from the makers drawing'),'2;1');\n"
            f"FILE_NAME('{name}.step','2026-10-01T00:00:00',(''),(''),'gen_listener.py','gen_listener.py','');\n"
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\nENDSEC;\nDATA;\n"
            + "".join(f"#{i + 1}={t};\n" for i, t in enumerate(ents)) + "ENDSEC;\nEND-ISO-10303-21;\n")


BLACK, PORT_DARK, TIN, GOLD = (0.1, 0.1, 0.1), (0.02, 0.02, 0.02), (0.82, 0.82, 0.84), (0.86, 0.69, 0.3)


def _fp(name, descr, tags, attr, items, ref_y, val_y):
    props = [_fptext("REF**", 0, ref_y, "F.SilkS", 1.0, "fpr" + name, "Reference"),
             _fptext(name, 0, val_y, "F.Fab", 1.0, "fpv" + name, "Value")]
    return (f'(footprint "{name}"\n\t(version 20260206)\n\t(generator "gen_listener")\n\t(layer "F.Cu")\n'
            f'\t(descr "{descr}")\n\t(tags "{tags}")\n' + "\n".join(props) + f'\n\t(attr {attr})\n'
            + "\n".join(items) + "\n)\n")


FP_FOT = "TE_MOST_Pigtail_FOT_2+0"
FP_T10 = "Everlight_TOSLINK_T10"
FP_RCA = "BKL_0101153_RCA_RA"
FP_TANG = "Sipeed_TangNano20K"
FP_ESP = "Espressif_ESP32-DevKitC_V4"


def te_fot_footprint():
    """TE MOST pigtail FOT unit (1-1394640-1; drawing C-2-2141577-1): eight 0.5 mm pins in
    one row, 2.54 apart with 3.86 between pins 4 and 5 (TX 1..4, RX 5..8); two 2.0 mm
    standoffs; two 0.4 mm action pins in 1.8 mm holes (soldered or pressed, 114-18997 6.1)
    and four 0.4 mm guide legs. Measured off the 2:1 drawing: the front view gives x, the
    side view the depth; every hole equals usb2most's footprint. Pin 1 is at +x here (the
    front view, contacts down, has it at the left); the optical face is at -y, 15.4 past the
    pins and beyond the body's foot - it overhangs the board edge."""
    items = []
    for i in range(8):
        x = 9.55 - 2.54 * i - (3.86 - 2.54 if i >= 4 else 0)
        items.append(_fppad(str(i + 1), "thru_hole", "rect" if i == 0 else "circle", round(x, 2), 7.07,
                            1.6, 1.6, 1.0, f"fotp{i}"))
    for i, (x, y) in enumerate(((7.6, 1.0), (-6.1, -10.4))):
        items.append(_fppad("", "np_thru_hole", "circle", x, y, 2.1, 2.1, 2.1, f"fotpeg{i}"))
    for i, (x, y) in enumerate(((10.85, -8.3), (-12.85, -8.3))):
        items.append(_fppad("0", "thru_hole", "circle", x, y, 2.4, 2.4, 1.8, f"fotact{i}"))
    for i, (x, y) in enumerate(((0.0, 4.45), (-12.85, 6.2), (-4.47, 9.15), (7.01, 9.15))):
        items.append(_fppad("", "np_thru_hole", "circle", x, y, 1.1, 1.1, 1.1, f"fotguide{i}"))
    x0, x1, y0, y1 = -14.1, 11.1, -15.4, 9.35
    items.append(_fpbox(x0, y0, x1, y1, "F.Fab", 0.1, "fotfab"))
    items.append(_fpl(x0, -11.8, x1, -11.8, "F.Fab", 0.1, "fotfoot"))        # the foot ends; the port overhangs
    # silk: the right action pin's pad reaches past the housing's edge, so that edge is drawn
    # in two pieces around it, and the rear edge in three around the two guide legs at y 9.15;
    # the courtyard takes the pad in
    # the optical face overhangs the board edge (the foot line, y -11.8): no silk there, the sides
    # start 0.4 mm inside the edge
    sx0, sy0, sx1, sy1 = x0 - 0.11, -11.8 + 0.4, x1 + 0.11, y1 + 0.11
    for k, (ax, bx) in enumerate(((sx0, -5.4), (-3.55, 6.1), (7.95, sx1))):
        items.append(_fpl(ax, sy1, bx, sy1, "F.SilkS", 0.12, f"fotsilk1{k}"))
    items.append(_fpl(sx0, sy0, sx0, sy1, "F.SilkS", 0.12, "fotsilk2"))
    items.append(_fpl(sx1, sy0, sx1, -8.3 - 1.6, "F.SilkS", 0.12, "fotsilk3"))
    items.append(_fpl(sx1, -8.3 + 1.6, sx1, sy1, "F.SilkS", 0.12, "fotsilk4"))
    items.append(_fpbox(x0 - 0.25, y0 - 0.25, 12.3, y1 + 0.25, "F.CrtYd", 0.05, "fotcrt"))
    items.append(_fptext("optical face", -1.5, -13.6, "F.Fab", 0.7, "fottxt"))
    items.append(_fptext("TX 1..4", 5.7, 5.3, "F.Fab", 0.6, "fottx"))
    items.append(_fptext("RX 5..8", -5.7, 5.3, "F.Fab", 0.6, "fotrx"))
    items.append(_fpdot(11.7, 7.07, "fotpin1"))
    items.append(_own_model(FP_FOT))
    return _fp(FP_FOT, "TE MOST25 pigtail FOT unit with header (1-1394640-1, drawing C-2-2141577-1): 8 pins 0.5 mm "
               "in one row on 2.54 with 3.86 between 4 and 5, two 2.0 mm standoffs, two action pins in 1.8 mm "
               "holes (pad 0), four guide legs; the optical face at -y overhangs the board edge; pin 1 (TX data) "
               "at +x", "TE MOST FOT pigtail 1394640 2141577", "through_hole", items, -17.0, 10.8)


T10_PEG, T10_FOOT, T10_PORT, T10_REAR = 2.63, 8.76, 11.11, -2.39     # from the pins, towards the port


def te_fot_body():
    """The TE pigtail FOT unit from the customer view model drawing C-2-2141577-1 (2:1 DXF,
    third-angle; its four views give x, depth and height, and its pegs and pins fall on this
    footprint's holes): the housing 25.2 wide, 12.8 high on 0.45 mm standoffs round the two pegs,
    its front at y -15.4; the header behind it, from y 4.0 to 9.35, 10.0 high; the oval port
    sleeve 12 x 6 standing 3.5 out of the front, the two fibre axes 6.0 apart at x +-3.0 (TX at +x,
    over pins 1..4) and 6.85 up; the eight pins 0.5 x 0.25, the action pins and guide legs 0.4,
    2.75 below the board, the pegs (2.0) 3.5."""
    za, yf, yn = 6.85, -15.4, -18.9
    solids = [(BLACK, _box(-14.1, 11.1, yf, 4.0, 0.45, 13.25)),
              (BLACK, _box(-12.25, 10.25, 4.0, 9.35, 0.45, 10.0)),
              (BLACK, _box(-3.0, 3.0, yn, yf, za - 3.0, za + 3.0)),
              (BLACK, _cyl("y", (-3.0, za), 3.0, yn, yf)),
              (BLACK, _cyl("y", (3.0, za), 3.0, yn, yf))]
    for x in (-3.0, 3.0):
        solids.append((PORT_DARK, _cyl("y", (x, za), 2.0, yn - 0.05, yn)))
    for (x, y), (ya, yb) in (((7.6, 1.0), (-1.0, 3.0)), ((-6.1, -10.4), (-12.4, -9.3))):
        solids.append((BLACK, _box(x - 2.0, x + 2.0, ya, yb, 0.0, 0.45)))
        solids.append((BLACK, _cyl("z", (x, y), 1.0, -3.5, 0.0, 16)))
    for i in range(8):
        x = 9.55 - 2.54 * i - (3.86 - 2.54 if i >= 4 else 0)
        solids.append((TIN, _box(x - 0.25, x + 0.25, 7.07 - 0.125, 7.07 + 0.125, -2.75, 0.45)))
    for x, y in ((10.85, -8.3), (-12.85, -8.3), (0.0, 4.45), (-12.85, 6.2), (-4.47, 9.15), (7.01, 9.15)):
        solids.append((TIN, _box(x - 0.2, x + 0.2, y - 0.2, y + 0.2, -2.75, 0.45)))
    return solids


def toslink_t10_footprint():
    """PLR135/T10 and PLT133/T10W share the housing; the drawings are third-angle (the bottom
    view, pins numbered, sits under the front view; the side view, right of it, has the port face
    at its left edge). 3 pins 0.80 on 2.54; two pegs 1.10 at 5.08 spacing 2.63 in front of the
    pins, towards the port (the PCB layouts); the body 9.70 wide, 13.50 deep, 10.00 high, the pins
    2.39 from its rear face and 11.11 from the port face; its front foot 2.35 behind the port face,
    8.76 in front of the pins - the side view dimensions the pins from it, and the board's edge
    belongs there, the port overhanging it. The port faces +y; pin 1 is at -x, as seen from the
    port (the front views). Up to v1.4 the pegs stood behind the pins and the port 1.24 in front
    of them, a first-angle reading that put the real part's pegs past the board's edge."""
    items = []
    for i in range(3):
        items.append(_fppad(str(i + 1), "thru_hole", "rect" if i == 0 else "circle", -2.54 + 2.54 * i, 0,
                            1.6, 1.6, 0.9, f"t10p{i}"))
    for i, x in enumerate((-2.54, 2.54)):
        items.append(_fppad("", "np_thru_hole", "circle", x, T10_PEG, 1.2, 1.2, 1.2, f"t10g{i}"))
    x0, x1, y0, y1 = -4.85, 4.85, T10_REAR, T10_PORT
    items.append(_fpbox(x0, y0, x1, y1, "F.Fab", 0.1, "t10fab"))
    items.append(_fpl(x0, T10_FOOT, x1, T10_FOOT, "F.Fab", 0.1, "t10edge"))    # the front foot: the board's edge
    # silk on three sides: the sides end 0.4 mm behind the board's edge
    ys = T10_FOOT - 0.4
    items.append(_fpl(x0 - 0.11, y0 - 0.11, x1 + 0.11, y0 - 0.11, "F.SilkS", 0.12, "t10silk0"))
    items.append(_fpl(x0 - 0.11, y0 - 0.11, x0 - 0.11, ys, "F.SilkS", 0.12, "t10silk1"))
    items.append(_fpl(x1 + 0.11, y0 - 0.11, x1 + 0.11, ys, "F.SilkS", 0.12, "t10silk2"))
    items.append(_fpbox(x0 - 0.25, y0 - 0.25, x1 + 0.25, y1 + 0.25, "F.CrtYd", 0.05, "t10crt"))
    items.append(_fptext("port", 0, y1 + 0.7, "F.Fab", 0.5, "t10txt"))
    items.append(_fptext("board edge", 0, T10_FOOT - 0.6, "F.Fab", 0.5, "t10edgetxt"))
    items.append(_fpdot(-4.2, 1.0, "t10pin1"))
    items.append(_own_model(FP_T10))
    return _fp(FP_T10, "Everlight PLR135/T10 receiver and PLT133/T10W transmitter (TOSLINK housing): 3 pins on "
               "2.54, two pegs 2.63 in front of them, towards the optical port, which faces +y; the board's "
               "edge at the front foot, 8.76 in front of the pins, the port 2.35 past it; data sheets "
               "DPL-135-017 p.2 and DPL-0000049 Rev.5 p.4", "TOSLINK Everlight PLR135 PLT133", "through_hole",
               items, y0 - 1.6, y1 + 1.6)


def t10_body():
    """The T10 housing in the footprint's frame (origin at pin 2, the port towards +y): the body
    10.00 high on four small feet, the port a dark square round the optical axis 4.35 up, the pins
    0.5 x 0.4 and the pegs 0.65 reaching 3.85 below the body."""
    solids = [(BLACK, _box(-4.85, 4.85, T10_REAR, T10_PORT, 0.2, 10.0)),
              (PORT_DARK, _box(-3.0, 3.0, T10_PORT, T10_PORT + 0.05, 4.35 - 3.0, 4.35 + 3.0))]
    for xa, xb in ((-4.85, -4.25), (4.25, 4.85)):
        for ya, yb in ((T10_FOOT - 1.05, T10_FOOT), (T10_REAR, T10_REAR + 0.6)):
            solids.append((BLACK, _box(xa, xb, ya, yb, 0.0, 0.2)))
    for x in (-2.54, 0.0, 2.54):
        solids.append((TIN, _box(x - 0.25, x + 0.25, -0.2, 0.2, -3.85, 0.2)))
    for x in (-2.54, 2.54):
        solids.append((TIN, _box(x - 0.325, x + 0.325, T10_PEG - 0.325, T10_PEG + 0.325, -3.85, 0.2)))
    return solids


def bkl_rca_footprint():
    """BKL 0101153, Cinch-Printbuchse 90 degrees (the TDS drawing, P.C.B Layout 2:1): a 1.0 hole on
    the axis and one 2.5 beside it, two 2.0 holes 10.1 apart 5.1 towards the port; the body
    14.7 wide, its rear face 2.0 behind the thin pins and the flange 8.0 in front of the thick
    legs (side view). Pad 1 = the centre contact on the axis; pad 2 = the thick legs; pad 3 =
    the thin pin beside the axis, whose function the drawing does not name: measure it on a
    sample (shell or centre) before the layout ties it to anything."""
    items = [_fppad("1", "thru_hole", "rect", 0, 0, 1.8, 1.8, 1.1, "rca1"),
             _fppad("3", "thru_hole", "circle", 2.5, 0, 1.8, 1.8, 1.1, "rca3"),
             _fppad("2", "thru_hole", "circle", -5.05, 5.1, 3.0, 3.0, 2.2, "rca2a"),
             _fppad("2", "thru_hole", "circle", 5.05, 5.1, 3.0, 3.0, 2.2, "rca2b")]
    x0, x1, y0, y1 = -7.35, 7.35, -2.0, 12.8
    items.append(_fpbox(x0, y0, x1, y1, "F.Fab", 0.1, "rcafab"))
    # silk on three sides: the flange sits at the board edge, the sides end 0.4 mm behind it
    ys = y1 - 0.4
    items.append(_fpl(x0 - 0.11, y0 - 0.11, x1 + 0.11, y0 - 0.11, "F.SilkS", 0.12, "rcasilk0"))
    items.append(_fpl(x0 - 0.11, y0 - 0.11, x0 - 0.11, ys, "F.SilkS", 0.12, "rcasilk1"))
    items.append(_fpl(x1 + 0.11, y0 - 0.11, x1 + 0.11, ys, "F.SilkS", 0.12, "rcasilk2"))
    items.append(_fpbox(x0 - 0.25, y0 - 0.25, x1 + 0.25, y1 + 0.25, "F.CrtYd", 0.05, "rcacrt"))
    items.append(_fptext("port", 0, 10.5, "F.Fab", 0.7, "rcatxt"))
    items.append(_fpdot(-1.4, -1.4, "rcapin1"))
    items.append(_own_model(FP_RCA))
    return _fp(FP_RCA, "BKL Electronic 0101153 RCA jack, right angle, gold, black: centre pin on the axis (1), "
               "thick legs (2), the thin pin 2.5 beside the axis (3, function not in the drawing - measure); "
               "body 14.7 x 14.8, the port faces +y", "RCA Cinch BKL 0101153", "through_hole", items, -3.5, 14.2)


def bkl_rca_body():
    """The BKL 0101153 in the footprint's frame (origin at the centre pin, the port towards +y):
    the housing 14.7 wide, 14.8 deep, 13.5 high; the metal part 35.2 from the housing's rear face -
    8.7 of thread (11.4 across in the side view), a collar 10.2 across and the 8.3 sleeve, 6.2 long -
    on an axis 6.75 up, mid-housing as the side view draws it; the black ring and the 3.2 bore at
    its mouth; the thin pins 9.45 and the thick legs (1.9) 5.4 below the board."""
    za = 6.75
    solids = [(BLACK, _box(-7.35, 7.35, -2.0, 12.8, 0.0, 13.5)),
              (GOLD, _cyl("y", (0.0, za), 5.7, 12.8, 21.5)),
              (GOLD, _cyl("y", (0.0, za), 5.1, 21.5, 27.0)),
              (GOLD, _cyl("y", (0.0, za), 4.15, 27.0, 33.2)),
              (BLACK, _cyl("y", (0.0, za), 3.3, 33.2, 33.25)),
              (PORT_DARK, _cyl("y", (0.0, za), 1.6, 33.25, 33.3))]
    for x in (0.0, 2.5):
        solids.append((TIN, _box(x - 0.3, x + 0.3, -0.3, 0.3, -9.45, 0.0)))
    for x in (-5.05, 5.05):
        solids.append((TIN, _cyl("z", (x, 5.1), 0.95, -5.4, 0.0, 16)))
    return solids


def tangnano_footprint():
    """Sipeed Tang Nano 20K (data sheet v1.3 p.6): 54.04 x 22.55 mm, two rows of 20 on 2.54, rows
    20.32 apart (the board's width less two edge margins); pad 1 at the USB-C end, left row,
    as the pinout drawing (p.5) and the schematic symbol number them. The HDMI connector
    stands 8 mm past the far end, the USB-C 1.5 mm past the near one. The module is soldered in
    on its pin headers, 2.5 mm of plastic between the boards (no sockets), so the courtyard is
    the two header rows and low parts may sit under it."""
    items = []
    for i in range(20):
        y = -24.13 + 2.54 * i
        items.append(_fppad(str(i + 1), "thru_hole", "rect" if i == 0 else "circle", -10.16, y, 1.7, 1.7, 1.0,
                            f"tn{i + 1}"))
        items.append(_fppad(str(i + 21), "thru_hole", "circle", 10.16, y, 1.7, 1.7, 1.0, f"tn{i + 21}"))
    x0, x1, y0, y1 = -11.275, 11.275, -27.02, 27.02
    items.append(_fpbox(x0, y0, x1, y1, "F.Fab", 0.1, "tnfab"))
    items.append(_fpbox(x0 - 0.11, y0 - 0.11, x1 + 0.11, y1 + 0.11, "F.SilkS", 0.12, "tnsilk"))
    # soldered in on its pin headers: the courtyard is the two header rows (2.54 wide), so low
    # parts may sit under the module between them; its outline stays on F.Fab and the silk
    for side, x in (("l", -10.16), ("r", 10.16)):
        items.append(_fpbox(x - 1.52, -24.13 - 1.52, x + 1.52, 24.13 + 1.52, "F.CrtYd", 0.05, f"tncrt{side}"))
    items.append(_fptext("USB-C", 0, -25.6, "F.Fab", 0.8, "tnusb"))
    items.append(_fptext("HDMI, +8 mm", 0, 25.6, "F.Fab", 0.8, "tnhdmi"))
    items.append(_fpdot(-11.9, -24.13, "tnpin1"))
    # soldered in on pin headers, no sockets: KiCad's 1x20 header under each row, as J2 and J3 show theirs
    for x in (-10.16, 10.16):
        items.append(_fpmodel("Connector_PinHeader_2.54mm", "PinHeader_1x20_P2.54mm_Vertical", x, -24.13))
    return _fp(FP_TANG, "Sipeed Tang Nano 20K module, 54.04 x 22.55 mm, 2 x 20 pins on 2.54, rows 20.32 apart, "
               "pad 1 = pin 73 (HSPI_DIN2) at the USB-C end; the HDMI connector overhangs the far end by 8 mm "
               "(data sheet v1.3 p.5, p.6); soldered to the board on two 1x20 pin headers, 2.54 mm, no sockets",
               "Sipeed Tang Nano 20K GW2AR", "through_hole", items, -29.0, 29.5)


def devkitc_footprint():
    """Espressif ESP32-DevKitC V4 (dimensions drawing): 48.26 x 27.94 mm, two rows of 19 on 2.54,
    rows 25.40 apart, the first pin 1.27 from the antenna end; pad 1 = 3V3, top left with the
    antenna up, pads 20..38 the right row from GND down to CLK. The antenna reaches 6.04 past
    the end (18 wide): no copper under it, so it is in the courtyard; the USB socket 1.3 past
    the other end. The module is soldered in on its pin headers, 2.5 mm of plastic between the
    boards, so the courtyard is the two pin rows and the antenna's end, and low parts may sit
    under the module between the rows."""
    items = []
    for i in range(19):
        y = -22.86 + 2.54 * i
        items.append(_fppad(str(i + 1), "thru_hole", "rect" if i == 0 else "circle", -12.7, y, 1.7, 1.7, 1.0,
                            f"dk{i + 1}"))
        items.append(_fppad(str(i + 20), "thru_hole", "circle", 12.7, y, 1.7, 1.7, 1.0, f"dk{i + 20}"))
    x0, x1, y0, y1 = -13.97, 13.97, -24.13, 24.13
    items.append(_fpbox(x0, y0, x1, y1, "F.Fab", 0.1, "dkfab"))
    items.append(_fpbox(x0 - 0.11, y0 - 0.11, x1 + 0.11, y1 + 0.11, "F.SilkS", 0.12, "dksilk"))
    items.append(_fpbox(-9.0, -30.17, 9.0, -24.13, "F.Fab", 0.1, "dkant"))
    # the courtyard: the two pin rows (2.54 wide) and the antenna's end; the outline stays on F.Fab and the silk
    for side, x in (("l", -12.7), ("r", 12.7)):
        items.append(_fpbox(x - 1.52, -22.86 - 1.52, x + 1.52, 22.86 + 1.52, "F.CrtYd", 0.05, f"dkcrt{side}"))
    items.append(_fpbox(-9.25, -30.42, 9.25, y0, "F.CrtYd", 0.05, "dkcrtant"))
    items.append(_fptext("antenna: no copper", 0, -27.2, "F.Fab", 0.7, "dkanttxt"))
    items.append(_fptext("USB", 0, 23.0, "F.Fab", 0.8, "dkusb"))
    items.append(_fpdot(-14.6, -22.86, "dkpin1"))
    # soldered in on pin headers, no sockets: KiCad's 1x19 header under each row, as J2 and J3 show theirs
    for x in (-12.7, 12.7):
        items.append(_fpmodel("Connector_PinHeader_2.54mm", "PinHeader_1x19_P2.54mm_Vertical", x, -22.86))
    return _fp(FP_ESP, "Espressif ESP32-DevKitC V4, 48.26 x 27.94 mm, 2 x 19 pins on 2.54, rows 25.40 apart, "
               "pad 1 = 3V3 at the antenna end; the antenna overhangs that end by 6.04 mm and wants no copper "
               "under it (Espressif dimensions drawing); soldered to the board on two 1x19 pin headers, 2.54 mm, "
               "no sockets", "Espressif ESP32 DevKitC", "through_hole", items, -31.7, 26.9)


NEW_FOOTPRINTS = ((FP_FOT, te_fot_footprint), (FP_T10, toslink_t10_footprint), (FP_RCA, bkl_rca_footprint),
                  (FP_TANG, tangnano_footprint), (FP_ESP, devkitc_footprint))


def rect_gap(a, b):
    """Clearance between two centred rectangles (x, y, w, h); negative = overlap."""
    dx = abs(a[0] - b[0]) - (a[2] + b[2]) / 2
    dy = abs(a[1] - b[1]) - (a[3] + b[3]) / 2
    return max(dx, dy)


def si514_footprint():
    """The .kicad_mod text for U7, and the figures it was checked by: the
    smallest copper gap between different pins and the courtyard size."""
    lay = si514_layout()
    pads = [(n, r) for _, _, _, pd, _ in lay for n, r in pd.items()]
    cu = min(rect_gap(a, b) for i, (na, a) in enumerate(pads) for nb_, b in pads[i + 1:] if na != nb_)
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
        box(x1, y1, x2, y2, "F.Fab", 0.1)                 # both bodies, one inside the other
        xs += [x1, x2]; ys += [y1, y2]
        for n, (x, y, w, h) in pd.items():
            items.append(f'\t(pad "{n}" smd rect (at {f(x)} {f(y)}) (size {f(w)} {f(h)}) '
                         f'(layers "F.Cu" "F.Mask" "F.Paste") (uuid "{uid("fpp" + name + n)}"))')
            xs += [x - w / 2, x + w / 2]; ys += [y - h / 2, y + h / 2]
    text("3.2x5 / 2.5x3.2", 0, 0, "F.Fab", 0.5)
    # pin 1: a dot on the silkscreen, off the pin 1 pad's outer corner
    x, y, w, h = lay[0][3]["1"]
    px, py = x - (w / 2 + 0.35), y - (h / 2 + 0.35)
    items.append(f'\t(fp_circle (center {f(px)} {f(py)}) (end {f(px + 0.15)} {f(py)}) '
                 f'(stroke (width 0.1) (type solid)) (fill yes) (layer "F.SilkS") '
                 f'(uuid "{uid("fpc3.2x5")}"))')
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
            f'\t(descr "Skyworks Si514 in the 3.2x5 or the 2.5x3.2 mm package: the 3.2x5 land '
            f'pattern (data sheet Rev 1.2, Table 19) with the inner pad edge of the 2.5x3.2 one '
            f'(Table 21), which lies inside it")\n\t(tags "Si514 oscillator 3.2x5 2.5x3.2")\n')
    body = "\n".join(props + ['\t(attr smd)'] + items)
    return head + body + "\n)\n", cu, (k2 - k1, l2 - l1)


# ----------------------------------------------------------------- drawing
def power_block(sh):
    sh.frame(12.7, 12.7, 203.2, 101.6, "1. ЖИВЛЕННЯ   J4 акумулятор -> 3V3_AON (завжди) і 5V_SW (за WAKE) -> 5V_HOST (M2)")
    # input: J4 -> F1 -> D1 -> VBAT_P
    j4 = sh.add("CONN2", "J4", "VBAT_IN", 25.4, 45.72,
                fp="Connector_Molex:Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal")
    y = j4.p("1")[1]
    f1 = sh.at_pin("F", "F1", "2A T", "1", (38.1, y), r=90, fp="Fuse:Fuse_1206_3216Metric")
    d1 = sh.at_pin("DS", "D1", "SS34", "2", (53.34, y), r=180, fp="Diode_SMD:D_SMA",
                   ref_at=(53.34, y - 3.81), val_at=(53.34, y + 3.81))
    sh.wire(j4.p("1"), f1.p("1"))
    sh.wire(f1.p("2"), d1.p("2"))
    # L2 (Bourns SRN8040-220M, 22 uH, 3 A) with the capacitors behind it is a pi filter:
    # ~40 dB at 400 kHz against the electrolytics' ESR, so U6's switching stays off the
    # harness the amplifier hangs on; the same ESR damps the 2.2 kHz resonance (zeta ~1.6)
    l2 = sh.at_pin("L", "L2", "22u", "1", (d1.p("1")[0] + 2.54, y), r=90,
                   fp="Inductor_SMD:L_Bourns-SRN8040_8x8.15mm")
    sh.wire(d1.p("1"), l2.p("1"))
    node = (73.66, y)
    sh.wire(l2.p("2"), node, (99.06, y))
    g = j4.p("2")
    sh.wire(g, (33.02, g[1]), (33.02, 58.42))
    sh.gnd((33.02, 58.42))
    sh.flag((33.02, 55.88))
    sh.up("VBAT_P", node, 5.08)
    sh.flag((78.74, y))
    # D2 in front of D1, unidirectional: silent at the 35 V of a suppressed load dump
    # (ISO 16750-2 test B), clamps the fast ISO 7637-2 pulses around 50 V - nothing
    # to an 80 V buck - and shunts negative ones through its forward diode, so D1
    # never sees more than its own drop plus the battery. Behind D1 (where it was,
    # as an SMBJ26CA) a negative pulse broke D1 first, and 35 V burnt the TVS.
    d2 = sh.at_pin("DZ", "D2", "SMBJ36A", "1", (48.26, y + 5.08), r=270, fp="Diode_SMD:D_SMB",
                   ref_at=(45.72, y + 7.62), val_at=(45.72, y + 10.16), fjust=("right", "right"))
    sh.wire((48.26, y), d2.p("1")); sh.gnd(d2.p("2"))
    c1 = sh.at_pin("C", "C1", "10u 100V", "1", (86.36, y + 5.08), fp="Capacitor_SMD:C_1210_3225Metric")
    c2 = sh.at_pin("C", "C2", "100n 100V", "1", (99.06, y + 5.08), fp=SMD["C"])
    sh.wire((86.36, y), c1.p("1")); sh.wire((99.06, y), c2.p("1"))
    sh.gnd(c1.p("2")); sh.gnd(c2.p("2"))
    sh.text("J4 Molex Micro-Fit 3.0 кутовий 43650-0200 на лівому краю під J1 (відповідна частина 43645-0200, контакти 43030), із защіпкою, 5 А. Захист: F1 2 А інерційний; D2 SMBJ36A перед D1: мовчить при 35 В (ISO 16750-2 B), імпульси ISO 7637-2 тисне до ~50 В.", 17.78, 87.63, 1.27)
    sh.text("3V3_AON (U5) завжди: FOT, U1, U2, U4, U11. На стоянці (кільце спить) разом до ~60 мкА: FOT у сні <= 25, логіка, LDO 2.7.", 17.78, 91.44, 1.27)
    sh.text("5V_SW (U6 LMR38020, 80 В, 400 кГц) вмикає WAKE: модуль FPGA і U14 (3V3_DA, блок 9). VOUT 5.31 В. C44/C45 + L2 22 мкГн: дзвін джгута і 400 кГц не в джгут.", 17.78, 95.25, 1.27)
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

    # Buck: VBAT_P -> 5V_SW for the FPGA module, enabled by WAKE. An 80 V part
    # (LMR38020, 85 V absolute maximum): whatever D2 lets through is within its
    # rating, and a 35 V load dump is ordinary input. 400 kHz from R31 (Table
    # 8-1), forced PWM so the frequency never drops into the audio band at light
    # load; L and COUT per Table 9-1 for 5 V at 2 A, CIN per 9.2.2.6 (100 V parts).
    u6 = sh.add("BUCK", "U6", "LMR38020F", 142.24, 69.85,
                fp="Package_SO:Texas_HSOP-8-1EP_3.9x4.9mm_P1.27mm_ThermalVias")
    vin = u6.p("3")
    vn = (vin[0] - 7.62, vin[1])
    sh.wire(vn, vin)
    sh.up("VBAT_P", vn, 5.08)
    c4 = sh.at_pin("C", "C4", "4u7 100V", "1", (vn[0] - 10.16, vin[1]), fp="Capacitor_SMD:C_1210_3225Metric",
                   ref_at=(vn[0] - 12.7, vin[1] + 2.54), val_at=(vn[0] - 12.7, vin[1] + 5.08), fjust=("right", "right"))
    c43 = sh.at_pin("C", "C43", "100n 100V", "1", (vn[0] - 20.32, vin[1]), fp=SMD["C"],
                    ref_at=(vn[0] - 22.86, vin[1] + 2.54), val_at=(vn[0] - 22.86, vin[1] + 5.08),
                    fjust=("right", "right"))
    sh.wire(vn, c4.p("1"), c43.p("1")); sh.gnd(c4.p("2")); sh.gnd(c43.p("2"))
    # two electrolytics, each with a ceramic beside it: the harness is long, and its
    # inductance rings with ceramics alone on load steps (LMR38020 data sheet 9.2.2.6);
    # C82 (2026-10-02): the user's copy of C47, on the board beside L2 and C45
    prev = c43
    for k, (key, ref, val, fp) in enumerate((("CP", "C44", "100u 63V", "Capacitor_SMD:CP_Elec_10x10.5"),
                                             ("C", "C46", "100n 100V", SMD["C"]),
                                             ("CP", "C45", "100u 63V", "Capacitor_SMD:CP_Elec_10x10.5"),
                                             ("C", "C47", "100n 100V", SMD["C"]),
                                             ("C", "C82", "100n 100V", SMD["C"]))):
        x = vn[0] - 35.56 - 15.24 * k
        c = sh.at_pin(key, ref, val, "1", (x, vin[1]), fp=fp, ref_at=(x - 2.54, vin[1] + 2.54),
                      val_at=(x - 2.54, vin[1] + 5.08), fjust=("right", "right"))
        sh.wire(prev.p("1"), c.p("1")); sh.gnd(c.p("2"))
        prev = c
    sh.lbl("WAKE", u6.p("2"), 20.32, "L")
    b = u6.p("1")[1] + 2.54
    sh.wire(u6.p("1"), (u6.p("1")[0], b)); sh.wire(u6.p("9"), (u6.p("9")[0], b))
    sh.wire((u6.p("1")[0], b), (u6.p("9")[0], b)); sh.gnd((u6.p("1")[0], b))
    rt = u6.p("4")
    r31 = sh.at_pin("R", "R31", "64k9 1%", "2", rt, r=90, fp=SMD["R"],
                    ref_at=(rt[0] - 6.35, rt[1] - 3.81), val_at=(rt[0] - 6.35, rt[1] - 1.27),
                    fjust=("left", "left"))
    sh.gnd(r31.p("1"))
    boot, sw = u6.p("7"), u6.p("8")
    c6 = sh.at_pin("C", "C6", "100n", "1", (boot[0] + 5.08, boot[1]), fp=SMD["C"])
    sh.wire(boot, c6.p("1")); sh.wire(sw, c6.p("2"))
    l1 = sh.at_pin("L", "L1", "15u", "1", (boot[0] + 12.7, sw[1]), r=90,
                   fp="Inductor_SMD:L_Bourns_SRN6045TA", ref_at=(boot[0] + 16.51, sw[1] - 2.54),
                   val_at=(boot[0] + 16.51, sw[1] + 2.54))
    sh.wire(c6.p("2"), l1.p("1"))
    o = (l1.p("2")[0] + 5.08, sw[1])
    oc = (o[0] + 10.16, sw[1])
    sh.wire(l1.p("2"), o, oc)
    sh.up("5V_SW", o, 5.08)
    sh.flag(oc)
    c7 = sh.at_pin("C", "C7", "47u 10V", "1", (oc[0], sw[1] + 5.08), fp="Capacitor_SMD:C_1210_3225Metric")
    sh.wire(oc, c7.p("1")); sh.gnd(c7.p("2"))
    r4 = sh.at_pin("R", "R4", "100k", "1", (o[0], sw[1] + 2.54), fp=SMD["R"])
    sh.wire(o, r4.p("1"))
    fbn = (o[0], r4.p("2")[1] + 2.54)
    r5 = sh.at_pin("R", "R5", "23k2", "1", (o[0], fbn[1] + 2.54), fp=SMD["R"])
    sh.wire(r4.p("2"), fbn, r5.p("1")); sh.gnd(r5.p("2"))
    fb = u6.p("5")
    sh.wire(fb, (fb[0] + 2.54, fb[1]), (fb[0] + 2.54, fbn[1]), fbn)
    sh.nc(u6.p("6"))

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
    # C23 10u (v1.2): U10 sits at the far end of 17 cm of 5V_SW that also feeds M1 and U8;
    # the host's radio pulses (0.3..0.5 A) come out of C23, the trunk carries their average
    c23 = sh.at_pin("C", "C23", "10u 16V", "1", (xr, en[1]), fp="Capacitor_SMD:C_0805_2012Metric",
                    ref_at=(xr - 2.54, en[1] + 2.54), val_at=(xr - 2.54, en[1] + 5.08),
                    fjust=("right", "right"))
    sh.gnd(c23.p("2"))
    # C80 100n (2026-10-02): on the board beside U10 and C23, the one at the trunk's end once C66
    # went over to U14
    c80 = sh.at_pin("C", "C80", "100n", "1", (xr - 12.7, vin[1]), fp=SMD["C"],
                    ref_at=(xr - 15.24, vin[1] + 2.54), val_at=(xr - 15.24, vin[1] + 5.08),
                    fjust=("right", "right"))
    sh.wire((xr, vin[1]), c80.p("1"))
    sh.gnd(c80.p("2"))
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
    j1 = sh.add("J_FOT", "J1", "1-1394640-1", 45.72, 151.13, fp=f"{LIB}:{FP_FOT}",
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
    # v1.4, the user's choice: Rext is two 27k in parallel, 13.5k - the bottom of AN 5344's
    # 13.5..33k range (13k7 1% before)
    r3 = sh.at_pin("R", "R3", "27k", "2", rg, fp=SMD["R"])
    sh.wire(r3.p("1"), (rg[0], ntx[1]))
    r42 = sh.at_pin("R", "R42", "27k", "2", (rg[0] + 22.86, rg[1]), fp=SMD["R"])
    sh.wire(rg, r42.p("2"))
    sh.wire(r42.p("1"), (r42.p("1")[0], ntx[1]))
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
    sh.text("R3 || R42 = 2 x 27k = 13k5: RGAIN -> TXVCC (AN 5344: 13.5..33k).", 17.78, 184.15, 1.27)
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
    m1 = sh.add("TANG", "M1", "Tang Nano 20K", 340.36, 151.13, fp=f"{LIB}:{FP_TANG}")
    # ring and Si514 signals only on pins whose sole other load is the empty
    # LCD FPC connector
    # TX_FB comes in through an 8:1 deserialiser (IDES8, 1.26 ns, like RX_IN);
    # that takes the whole IOB6 pair, so pad 11 (pin 26) stays unconnected
    # v1.2: U13's clocks and data leave over the top of the module from the left
    # row; LOCK on the left row too, next to U11; every other line bound for the
    # right half of the board on the right row, in the order it meets J2, J3, the
    # DAC and the host there
    left = {"1": "SRC_BCLK_F", "2": "SRC_LRCK_F", "3": "I2S_DIN2_F",
            "5": "CLK_1024", "8": "RX_IN", "9": "TX_PRE", "10": "TX_FB",
            "12": "SI_SCL", "13": "SI_SDA", "14": "LOCK"}
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
    right = {"23": "UART_RX_F", "25": "SPDIF_F", "26": "BCLK_F", "27": "UART_TX_F", "28": "MCLK_F",
             "30": "FS_F", "31": "SD1_F", "32": "SD0_F", "33": "I2S_DIN_F", "37": "I2S_BCLK_F",
             "38": "I2S_LRCK_F", "39": "I2S_DOUT_F", "40": "I2S_MCLK_F"}
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
            # C63/C64 (v1.4), on the board beside D3: this end of ~17 cm of 1 mm trunk had only
            # ceramics (C15, the module's own), and the trunk's inductance rings with them on the
            # module's and U8's load steps; the electrolytic's ESR damps it, as C44/C45 do for
            # the harness
            x63, x64, yc = p[0] + 26.67, p[0] + 36.83, p[1] + 15.24
            c63 = sh.at_pin("CP", "C63", "100u 16V", "1", (x63, yc), fp="Capacitor_SMD:CP_Elec_6.3x7.7",
                            ref_at=(x63, yc + 12.7), val_at=(x63, yc + 15.24))
            c64 = sh.at_pin("C", "C64", "100n", "1", (x64, yc), fp=SMD["C"],
                            ref_at=(x64, yc + 12.7), val_at=(x64, yc + 15.24))
            sh.wire(c63.p("1"), c64.p("1")); sh.up("5V_SW", c63.p("1"), 2.54)
            sh.gnd(c63.p("2")); sh.gnd(c64.p("2"))
            # C65..C68 (2026-10-01): 100n spread along the same trunk on the board, each by a
            # load or a bend of it
            yr = yc + 22.86
            xs = [p[0] + 25.4 + 6.35 * i for i in range(4)]
            row = [sh.at_pin("C", f"C{65 + i}", "100n", "1", (x, yr), fp=SMD["C"],
                             ref_at=(x, yr + 12.7), val_at=(x, yr + 15.24)) for i, x in enumerate(xs)]
            sh.wire(row[0].p("1"), row[-1].p("1")); sh.up("5V_SW", row[1].p("1"), 0)
            for c in row:
                sh.gnd(c.p("2"))
        elif n in ("22", "35"):
            sh.wire(p, (p[0] + 5.08, p[1])); sh.gnd((p[0] + 5.08, p[1]))
        else:
            sh.nc(p)
    sh.text("Контакти 1..20 / 21..40 згори вниз, від USB-C; назва = вивід GW2AR + що на ньому на платі (datasheet v1.3).", 279.4, 184.15, 1.27)
    sh.text("Кільце і Si514 - лише на виводах LCD (порожній роз'єм): LOCK на 31, S/PDIF на 42. HSPI, 54..56 (входи підсилювача модуля; PA_EN = 51 тримає його вимкненим), EDID 52/53: UART, MCLK, I2S, SD1, DIN2.", 279.4, 187.96, 1.27)
    sh.text("CLK_1024 (Si514) -> 77 (GCLKT_1). TX_FB -> 25 через IDES8 (1.26 нс); він займає пару, тому 26 не підключено.", 279.4, 191.77, 1.27)
    sh.text("D3: USB і 5V_SW разом не з'єднуються; U6 дає 5.3 В, на модулі ~5.0 В.", 279.4, 195.58, 1.27)
    sh.text("v1.2: лінії праворуч - з правого ряду в порядку J2, J3, ЦАП, хост; U13 (SRC_BCLK, SRC_LRCK, DIN2) - з лівого ряду понад модулем.", 279.4, 110.49, 1.27)


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
    # U7: the Si514, whichever 3.3 V CMOS part was in stock, in the 3.2x5 or the
    # 2.5x3.2 package - one land pattern takes both (v1.4; the 5x7 is dropped).
    # VDD from U8 on a real wire, 1u at U8 and a 100n at U7.
    u7 = sh.add("SI514", "U7", "Si514", 99.06, 243.84, fp=f"{LIB}:{FP_SI514}")
    vo, vdd = u8.p("5"), u7.p("6")
    c14 = sh.at_pin("C", "C14", "1u", "1", (vo[0] + 7.62, vo[1]), fp=SMD["C"])
    sh.wire(vo, c14.p("1"), (vdd[0], vo[1]), vdd)
    sh.gnd(c14.p("2"))
    nd = (vdd[0], vo[1] + 5.08)
    caps = [sh.at_pin("C", ref, "100n", "1", (vdd[0] + 10.16 * (i + 1), nd[1]), fp=SMD["C"])
            for i, ref in enumerate(("C13",))]
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
        "U7 Si514: будь-який з полиці з 3.3 В CMOS - у номері після 514 літера C, M або N; корпус 3.2x5 або 2.5x3.2 (літера перед AG: B або C), обидва сідають на одне посадкове місце.",
        "CLK+ -> FPGA (clk_r = 1024 Fs) і через R15 на U9: фронти TX стоять на такті Si514, а не на виході FPGA. CLK- не потрібен.",
        "FPGA сама знаходить I2C адресу Si514 (перебирає 0x08..0x77) і крутить M (dpll.v): затримка TX_FB відносно RX_IN до 1.26 нс, крок 0.026 ppb.",
        "На старті центрування (FCAL, до 10 мс): вихід Si514 тоді у високому імпедансі, R14 і R17 тримають лінії в 0. U8: окремий LDO з 5V_SW.",
    ):
        sh.text(line, 17.78, y, 1.27)
        y += 3.81


def output_block(sh):
    sh.frame(208.28, 203.2, 406.4, 284.48, "7. ВИХОДИ   J2: аналізатор (MCLK, 2 x TDM8, UART_TX);   J3: стерео I2S для ЦАП / DSP")

    def series(j, lines):
        """lines: (src label, connector pin, ref) top to bottom, each through its own 33R. The
        connector's pins are 2.54 apart, the resistors 5.08, so each line jogs from its pin to
        its resistor: the outer lines jog nearest the connector and the inner ones further out,
        so no wire crosses another; the jogs start 7.62 out, clear of the ground pins below."""
        n = len(lines)
        y0 = j.p(lines[0][1])[1]
        xj = j.p(lines[0][1])[0]
        jmax = (n - 1) // 2
        xr = round(xj - 7.62 - 2.54 * jmax - 5.08, 3)          # every resistor's pin 2
        for k, (src, jp, ref) in enumerate(lines):
            m = j.p(jp)
            yr = round(y0 + 5.08 * k - 1.27 * (n - 1), 3)
            xjog = round(xj - 7.62 - 2.54 * min(k, n - 1 - k), 3)
            r = sh.at_pin("R", ref, "33", "2", (xr, yr), r=90, fp=SMD["R"],
                          ref_at=(xr - 5.715, yr - 1.905), val_at=(xr - 1.905, yr - 1.905),
                          fjust=(None, None))
            sh.wire(m, (xjog, m[1]), (xjog, yr), r.p("2"))
            sh.lbl(src, r.p("1"), 5.08, "L")

    def grounds(j, pins, stub=2.54):
        gx = j.p(pins[0])[0] - 5.08
        for n in pins:
            sh.wire(j.p(n), (gx, j.p(n)[1]))
        sh.wire((gx, j.p(pins[0])[1]), (gx, j.p(pins[-1])[1]))
        sh.gnd((gx, j.p(pins[-1])[1]), stub)

    # J2: analyser (TDM, raw control blocks)
    j2 = sh.add("CONN8", "J2", "ANALYSER", 373.38, 232.41,
                fp="Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical")
    series(j2, [("SD0_F", "1", "R36"), ("SD1_F", "2", "R37"), ("FS_F", "3", "R35"), ("MCLK_F", "4", "R19"),
                ("UART_TX_F", "5", "R18"), ("BCLK_F", "6", "R34")])
    grounds(j2, ("7", "8"))

    # J3: stereo I2S to a DAC / DSP
    j3 = sh.add("CONN_I2S", "J3", "I2S", 289.56, 233.68,
                fp="Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical")
    series(j3, [("I2S_MCLK_F", "1", "R38"), ("I2S_DOUT_F", "2", "R41"), ("I2S_LRCK_F", "3", "R40"),
                ("I2S_BCLK_F", "4", "R39")])
    grounds(j3, ("5", "6"))

    y = 252.73
    for line in (
        "J2 SD0/SD1: байти кадру 0..31 / 32..63, кадр TDM = кадр MOST.",
        "J2 UART_TX: сирі керувальні блоки (ті самі, що читає M2).",
        "J3: I2S, BCLK 64 Fs, слоти 32 біт, 24 біт з регулюваннями ГУ; те саме S/PDIF - J6, J7 (блок 9).",
        "Входів на J2 і J3 немає: хост один - M2 (блок 8).",
        "R18..R21, R34..R41 (33 Ом): кожен біля свого виводу FPGA (узгодження джерела); R38..R41 - під M2.",
        "MCLK на J2 і J3 - з окремих виводів FPGA, без відгалуження.",
        "v1.2: порядок контактів J2 і J3 - як їхні виводи на правому ряду M1, доріжки без перехрещень.",
    ):
        sh.text(line, 213.36, y, 1.27)
        y += 3.81


def host_block(sh):
    sh.frame(335.28, 12.7, 406.4, 101.6, "8. ХОСТ   M2 = ESP32-DevKitC-VIE")
    m2 = sh.add("DEVKITC", "M2", "ESP32-DevKitC-VIE", 370.84, 50.8, fp=f"{LIB}:{FP_ESP}")
    # v1.2: everything the FPGA meets on the header row that faces M1 (pads
    # 20..38), each opposite its FPGA pin: the ring-locked I2S clocks and the raw
    # control blocks in; the commands and our audio out, each through 33R at the
    # FPGA pin (R20, R21 sit under M1); OPT_ERR and (v1.3) OPT_NPCM from U12 on the far row
    for pad, name in (("21", "I2S_LRCK_F"), ("22", "I2S_BCLK_F"), ("32", "UART_TX_F")):
        sh.lbl(name, m2.p(pad), 7.62, "R")
    for pad, ref, name in (("35", "R20", "UART_RX_F"), ("25", "R21", "I2S_DIN_F")):
        q = m2.p(pad)
        r = sh.at_pin("R", ref, "33", "2", (q[0] + 2.54, q[1]), r=270, fp=SMD["R"],
                      ref_at=(q[0] + 5.08, q[1] - 2.54), val_at=(q[0] + 8.89, q[1] - 2.54))
        sh.wire(q, r.p("2"))
        sh.lbl(name, r.p("1"), 2.54, "R")
    sh.lbl("OPT_ERR", m2.p("15"), 12.7, "L")
    sh.lbl("OPT_NPCM", m2.p("11"), 7.62, "L")
    sh.lbl("5V_HOST", m2.p("19"), 12.7, "L")
    g = m2.p("14")
    sh.wire(g, (g[0] - 5.08, g[1]))
    sh.gnd((g[0] - 5.08, g[1]))           # no stub: OPT_ERR runs along the next row
    for pad in ("20", "26"):
        q = m2.p(pad)
        sh.wire(q, (q[0] + 2.54, q[1]))
        sh.gnd((q[0] + 2.54, q[1]))
    used = {"11", "14", "15", "19", "20", "21", "22", "25", "26", "32", "35"}
    for n in map(str, range(1, 39)):
        if n not in used:
            sh.nc(m2.p(n))
    y = 81.28
    for line in (
        "M2: ESP32-DevKitC-VIE (WROVER-IE): 8 МБ PSRAM,",
        "антена IPEX (виносна, 2.4 ГГц), -40...85 °C.",
        "Гнізда 2 x 1x19, крок 2.54, між рядами 25.40 мм.",
        "5V_HOST -> 5V; USB модуля - через його діод.",
        "UART 3 Мбод: IO4 <- UART_TX, IO15 -> R20 -> UART_RX.",
        "I2S slave: IO22/23 <- BCLK/LRCK, IO21 -> R21 -> DIN.",
        "IO13 <- OPT_ERR, IO27 <- OPT_NPCM (U12, блок 9; v1.3).",
        "v1.2: зв'язки з FPGA - на ряду, що дивиться на M1.",
    ):
        sh.text(line, 337.82, y, 1.27)
        y += 2.54



def digital_audio_block(sh):
    sh.frame(12.7, 289.56, 406.4, 394.97,
             "9. ЦИФРОВЕ АУДІО   J5 TOSLINK IN -> U12 DIR9001 -> U13 SRC4192 -> I2S_DIN2_F;   SPDIF_F -> J6 TOSLINK OUT і J7 коаксіал")
    # ---- TOSLINK in: J5 -> R25 (damping, DIR9001 data sheet 8.3.1) -> U12.RXIN
    u12 = sh.add("DIR9001", "U12", "DIR9001", 109.22, 340.36, fp="Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm",
                 ref_at=(88.9, 317.5), val_at=(86.36, 360.68), fjust=("left bottom", "right bottom"))
    rxin, rst12, err, filt, xto = u12.p("20"), u12.p("21"), u12.p("27"), u12.p("22"), u12.p("7")
    j5 = sh.at_pin("TOSLINK_RX", "J5", "PLR135/T10", "3", (63.5, rxin[1]), fp=f"{LIB}:{FP_T10}",
                   ref_at=(45.72, 323.85), val_at=(43.18, 336.55), fjust=("left bottom", "right bottom"))
    r25 = sh.at_pin("R", "R25", "100", "1", (71.12, rxin[1]), r=90, fp=SMD["R"])
    sh.wire(j5.p("3"), r25.p("1")); sh.wire(r25.p("2"), rxin)
    # J5's supply: a ferrite and 100n within 2 cm of the module (its data sheet, layout notes)
    vcc5 = j5.p("1")
    n5 = (vcc5[0], round(vcc5[1] - 6.35, 3))
    sh.wire(vcc5, n5)
    fb3 = sh.at_pin("FB", "FB3", "600R", "1", (n5[0] + 2.54, n5[1]), r=90, fp="Inductor_SMD:L_0603_1608Metric")
    sh.wire(n5, fb3.p("1")); sh.up("3V3_DA", fb3.p("2"), 2.54)
    c30 = sh.at_pin("C", "C30", "100n", "1", (n5[0] - 10.16, n5[1]), fp=SMD["C"])
    sh.wire(n5, c30.p("1")); sh.gnd(c30.p("2"))
    sh.flag(c30.p("1"), dx=0)                          # fed through FB3: driven
    sh.gnd(j5.p("2"), 2.54)
    # reset (shared with U13, RC below right), the lock flag to the host, the PLL loop filter
    sh.lbl("RST_AIN", rst12, 5.08, "L")
    sh.lbl("OPT_ERR", err, 5.08, "L")
    sh.lbl("OPT_NPCM", u12.p("1"), 5.08, "L")      # v1.3: channel-status bit 1, 1 = not PCM
    f0 = (round(filt[0] - 10.16, 3), filt[1]); f1 = (f0[0], round(f0[1] + 5.08, 3))
    sh.wire(filt, f0, f1)
    c28 = sh.at_pin("C", "C28", "4n7", "1", f1, fp=SMD["C"]); sh.gnd(c28.p("2"))
    r24 = sh.at_pin("R", "R24", "680", "2", f1, r=90, fp=SMD["R"])
    c27 = sh.at_pin("C", "C27", "68n", "1", r24.p("1"), fp=SMD["C"],
                    ref_at=(r24.p("1")[0] - 5.08, f1[1] + 2.54), val_at=(r24.p("1")[0] - 5.08, f1[1] + 5.08),
                    fjust=("right", "right"))
    sh.gnd(c27.p("2"))
    sh.nc(xto)
    # top: VDD, VCC and the two format straps (24-bit I2S) on 3V3_SW; bottom: grounds and
    # every strap that is low (PSCK = 00: SCKO unused, CKSEL = L: PLL clock, RSV, XTI unused)
    top = [u12.p(n) for n in ("5", "24", "26", "25")]
    yb = round(top[0][1] - 2.54, 3)
    for p in top:
        sh.wire(p, (p[0], yb))
    sh.wire((top[0][0], yb), (top[-1][0], yb))
    sh.up("3V3_DA", (u12.x, yb), 2.54)
    bot = [u12.p(n) for n in ("6", "23", "14", "13", "28", "19", "8")]
    yg = round(bot[0][1] + 2.54, 3)
    for p in bot:
        sh.wire(p, (p[0], yg))
    sh.wire((bot[0][0], yg), (bot[-1][0], yg))
    sh.gnd((u12.x, yg))
    for n in ("4", "17", "2", "3", "18", "9", "15", "16"):
        sh.nc(u12.p(n))

    # ---- U13: the receiver's I2S, on the receiver's clock, onto the FPGA's BCLK/LRCK
    u13 = sh.add("SRC4192", "U13", "SRC4192", 190.5, 340.36, fp="Package_SO:SSOP-28_5.3x10.2mm_P0.65mm",
                 ref_at=(167.64, 317.5), val_at=(165.1, 360.68), fjust=("left bottom", "right bottom"))
    for a, b in (("11", "5"), ("10", "6"), ("12", "4")):       # BCKO -> BCKI, LRCKO -> LRCKI, DOUT -> SDIN
        sh.wire(u12.p(a), u13.p(b))
    top = [u13.p(n) for n in ("22", "7", "10", "19")]          # VDD VIO IFMT0 OFMT0 (I2S in and out)
    yb = round(top[0][1] - 2.54, 3)
    for p in top:
        sh.wire(p, (p[0], yb))
    sh.wire((top[0][0], yb), (top[-1][0], yb))
    sh.up("3V3_DA", (u13.x, yb), 2.54)
    bot = [u13.p(n) for n in ("8", "21", "11", "12", "26", "27", "28", "1", "9", "20", "17", "16", "18")]
    yg = round(bot[0][1] + 2.54, 3)
    for p in bot:
        sh.wire(p, (p[0], yg))
    sh.wire((bot[0][0], yg), (bot[-1][0], yg))
    sh.gnd((u13.x, yg))
    # X1: the rate estimator's reference clock, asynchronous to both ports
    rcki = u13.p("2")
    x1 = sh.add("OSC", "X1", "24.576MHz", 149.86, 344.17, fp="Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm",
                ref_at=(143.51, 339.09), val_at=(156.21, 349.25), fjust=("left bottom", "left bottom"))
    out, en, vdd, g = x1.p("3"), x1.p("1"), x1.p("4"), x1.p("2")
    sh.wire(out, (out[0], rcki[1]), rcki)
    sh.wire(en, (en[0] - 2.54, en[1]), (en[0] - 2.54, vdd[1]), vdd)
    sh.up("3V3_DA", vdd, 0)
    sh.gnd(g, 2.54)
    # output port, slave on the FPGA's I2S clocks; data to the FPGA through 33R
    sdout, bcko13, lrcko13, rdy, rst13, nc3 = (u13.p(n) for n in ("23", "25", "24", "15", "13", "3"))
    r29 = sh.at_pin("R", "R29", "33", "1", (sdout[0] + 7.62, sdout[1]), r=90, fp=SMD["R"],
                    ref_at=(sdout[0] + 7.62, sdout[1] - 3.81), val_at=(sdout[0] + 13.97, sdout[1] - 3.81))
    sh.wire(sdout, r29.p("1")); sh.lbl("I2S_DIN2_F", r29.p("2"), 5.08, "R")
    sh.lbl("SRC_BCLK_F", bcko13, 10.16, "R"); sh.lbl("SRC_LRCK_F", lrcko13, 10.16, "R")
    # v1.3: RDY (active low: the rate ratio is known) holds MUTE (active high) until then - the
    # auto-mute of SBFS022C 7.3.5, so a rate change on the TOSLINK input is never heard
    mute = u13.p("14")
    xr = round(rdy[0] + 2.54, 3)
    sh.wire(rdy, (xr, rdy[1]), (xr, mute[1]), mute)
    sh.text("v1.3: RDY -> MUTE - тиша, поки SRC4192", round(rdy[0] + 2.54, 3), round(u13.y + 11.43, 3), 1.27)
    sh.text("не визначив співвідношення частот.", round(rdy[0] + 2.54, 3), round(u13.y + 13.97, 3), 1.27)
    sh.nc(nc3)
    sh.lbl("RST_AIN", rst13, 10.16, "R")

    # ---- S/PDIF out: one FPGA pin (DRIVE 16) into the TOSLINK transmitter and the coax divider
    n1 = (271.78, 323.85)
    sh.label("SPDIF_F", (264.16, n1[1]), "L"); sh.wire((264.16, n1[1]), n1)
    r28 = sh.at_pin("R", "R28", "33", "1", (n1[0] + 2.54, n1[1]), r=90, fp=SMD["R"])
    sh.wire(n1, r28.p("1"))
    j6 = sh.at_pin("TOSLINK_TX", "J6", "PLT133/T10W", "1", (r28.p("2")[0] + 7.62, n1[1]), fp=f"{LIB}:{FP_T10}",
                   ref_at=(292.1, 318.77), val_at=(309.88, 331.47), fjust=("left bottom", "left bottom"))
    sh.wire(r28.p("2"), j6.p("1"))
    sh.up("3V3_DA", j6.p("2"), 6.35); sh.gnd(j6.p("3"), 2.54)
    n2 = (n1[0], 346.71)
    sh.wire(n1, n2)
    r26 = sh.at_pin("R", "R26", "240", "1", (n2[0] + 2.54, n2[1]), r=90, fp=SMD["R"])
    sh.wire(n2, r26.p("1"))
    nd = r26.p("2")
    r27 = sh.at_pin("R", "R27", "110", "1", nd, fp=SMD["R"]); sh.gnd(r27.p("2"))
    c29 = sh.at_pin("C", "C29", "100n", "1", (nd[0] + 7.62, nd[1]), r=90, fp=SMD["C"])
    sh.wire(nd, c29.p("1"))
    j7 = sh.at_pin("COAX", "J7", "RCA 75R", "1", (c29.p("2")[0] + 5.08, nd[1]), fp=f"{LIB}:{FP_RCA}",
                   ref_at=(307.34, 342.9), val_at=(312.42, 346.71), fjust=(None, "left"))
    sh.wire(c29.p("2"), j7.p("1")); sh.gnd(j7.p("2"), 2.54)
    # D4: ESD on the jack's centre pin, a 0.1 pF-class bidirectional diode (SOD-882)
    n4 = (299.72, nd[1])
    d4 = sh.at_pin("TVS", "D4", "PESD5V0S1BL", "1", (n4[0], n4[1] + 2.54), r=270, fp="Diode_SMD:D_SOD-882",
                   ref_at=(n4[0] - 2.54, n4[1] + 5.08), val_at=(n4[0] - 2.54, n4[1] + 7.62), fjust=("right", "right"))
    sh.wire(n4, d4.p("1")); sh.gnd(d4.p("2"))

    # ---- U14: the block's own 3.3 V from 5V_SW. The module's regulator (3V3_SW) has an
    # unknown margin, and this block takes ~0.1 A; an LDO of its own also keeps the
    # receiver's PLL and the ASRC off the FPGA's supply noise.
    u14 = sh.add("LDO_CLK", "U14", "LP5907MFX-3.3", 358.14, 312.42, fp="Package_TO_SOT_SMD:SOT-23-5")
    vin, en = u14.p("1"), u14.p("3")
    xr = vin[0] - 7.62
    sh.wire(vin, (xr, vin[1]))
    sh.up("5V_SW", (xr, vin[1]), 2.54)
    sh.wire(en, (vin[0] - 5.08, en[1]), (vin[0] - 5.08, vin[1]))
    c48 = sh.at_pin("C", "C48", "1u", "1", (xr - 7.62, vin[1]), fp=SMD["C"])
    sh.wire((xr, vin[1]), c48.p("1")); sh.gnd(c48.p("2"))
    # C81 100u 16V (2026-10-02): the user's copy of C78, on the board at the trunk's top-right
    # end beside U10 and U14 - the counterpart of C63 at D3
    c81 = sh.at_pin("CP", "C81", "100u 16V", "1", (xr - 17.78, vin[1]), fp="Capacitor_SMD:CP_Elec_6.3x7.7",
                    ref_at=(xr - 20.32, vin[1] + 2.54), val_at=(xr - 20.32, vin[1] + 5.08),
                    fjust=("right", "right"))
    sh.wire(c48.p("1"), c81.p("1")); sh.gnd(c81.p("2"))
    sh.nc(u14.p("4")); sh.gnd(u14.p("2"))
    vo = u14.p("5")
    nda = (vo[0] + 5.08, vo[1])
    sh.wire(vo, nda); sh.up("3V3_DA", nda, 2.54)
    c49 = sh.at_pin("C", "C49", "1u", "1", (nda[0] + 5.08, vo[1]), fp=SMD["C"])
    sh.wire(nda, c49.p("1")); sh.gnd(c49.p("2"))
    sh.text("U14 LP5907: 3V3_DA (250 мА) для блоку 9 від 5V_SW, не з LDO модуля. J7 пад 3 (тонкий штир поза віссю): функції в кресленні BKL нема, зміряти на зразку.", 17.78, 392.43, 1.27)

    # ---- the shared reset: 10 ms after 3V3_DA, when X1 already runs (the SRC4192 has no
    # power-on reset and wants RCKI alive during RST); and the decoupling, drawn as a row
    r30 = sh.at_pin("R", "R30", "10k", "2", (317.5, 365.76), fp=SMD["R"],
                    ref_at=(314.96, 360.68), val_at=(314.96, 363.22), fjust=("right", "right"))
    sh.up("3V3_DA", r30.p("1"), 2.54)
    c40 = sh.at_pin("C", "C40", "1u", "1", r30.p("2"), fp=SMD["C"]); sh.gnd(c40.p("2"))
    sh.wire(r30.p("2"), (312.42, 365.76)); sh.label("RST_AIN", (312.42, 365.76), "L")
    caps = [("C31", "100n", SMD["C"]), ("C32", "100n", SMD["C"]), ("C33", "10u", "Capacitor_SMD:C_0805_2012Metric"),
            ("C34", "100n", SMD["C"]), ("C35", "10u", "Capacitor_SMD:C_0805_2012Metric"),
            ("C36", "100n", SMD["C"]), ("C37", "10u", "Capacitor_SMD:C_0805_2012Metric"),
            ("C38", "100n", SMD["C"]), ("C39", "100n", SMD["C"])]
    ys = 365.76
    xs = [round(325.12 + 8.89 * i, 3) for i in range(len(caps))]
    for x, (ref, val, fp) in zip(xs, caps):
        c = sh.at_pin("C", ref, val, "1", (x, ys), fp=fp)
        sh.gnd(c.p("2"))
    sh.wire((xs[0], ys), (xs[-1], ys))
    sh.up("3V3_DA", (xs[4], ys), 2.54)
    sh.text("C31 J6; C32/C33 U12 VDD; C34/C35 U12 VCC;", 325.12, 381.0, 1.27)
    sh.text("C36/C37 U13 VDD; C38 U13 VIO; C39 X1: біля виводів.", 325.12, 384.81, 1.27)

    y = 373.38
    for line in (
        "J5 TOSLINK IN -> R25 -> U12 DIR9001: PLL відновлює такт із сигналу, вихід I2S 24 біт (FMT1 FMT0 = HH), CKSEL = L. XTI на землю: кварц не потрібен.",
        "U13 SRC4192: обидва порти slave (MODE = 000); вхід I2S 24 біт (IFMT = 001) від U12; вихід I2S 24 біт (OFMT = 01, OWL = 00) на тактах FPGA (власні копії BCLK, LRCK: SRC_BCLK_F, SRC_LRCK_F) -> I2S_DIN2_F.",
        "X1 24.576 МГц: опорний такт оцінювача швидкості SRC4192 (RCKI), асинхронний до обох портів. RST_AIN: R30/C40 = 10 мс, коли X1 уже іде (SRC4192 без POR).",
        "OPT_ERR (U12 ERROR) -> M2 IO13: 1 = TOSLINK без сигналу або помилка парності; OPT_NPCM (U12 AUDIO) -> M2 IO27: 1 = не PCM (AC-3/DTS DIR9001 не глушить); хост тоді не інжектує. Джерело: команда 02, біт M[2].",
        "S/PDIF OUT: SPDIF_F (FPGA 42) -> R28 -> J6 PLT133; R26/R27: 0.5 В на 75 Ом, вихідний опір 75 Ом; C29 без постійної -> J7 RCA. Той самий потік, що й на J3.",
    ):
        sh.text(line, 17.78, y, 1.27)
        y += 3.81


def testpoint_block(sh):
    sh.frame(411.48, 289.56, 523.24, 360.68, "10. ТЕСТОВІ ТОЧКИ (стенд)")
    x = 467.36
    # no probe points on the ring's own lines: TX_REGEN (U9's output into the ring) and RT_CLK
    # (the Si514's clock into U9), whose stubs would load the edges the regenerator's jitter
    # depends on, and RX_BUF and TX_SEL (dropped in board v1.4): RX_BUF is the bypass path's
    # own edge, and both had to be carried 50..90 mm to a corner. Probe them at U1 pin 4 and
    # U2 pin 6. WAKE's own point (TP4) went in board v1.4 as well: probe it at R31 or U4.
    y = 299.72
    for ref, rail in (("TP6", "3V3_AON"), ("TP7", "5V_SW")):
        tp = sh.at_pin("TP", ref, rail, "1", (x, y), fp="TestPoint:TestPoint_Pad_D2.0mm", bom=False,
                       ref_at=(x + 2.54, y - 1.27), val_at=(x + 2.54, y + 1.27), fjust=("left", "left"))
        q = (x - 7.62, y)
        sh.wire(tp.p("1"), q); sh.up(rail, q, 2.54)
        y += 7.62
    for i, ref in enumerate(("TP9",)):
        xx = x + 15.24 * i
        tp = sh.at_pin("TP", ref, "GND", "1", (xx, y), fp="TestPoint:TestPoint_Pad_D2.0mm", bom=False,
                       ref_at=(xx + 2.54, y - 1.27), val_at=(xx + 2.54, y + 1.27), fjust=("left", "left"))
        q = (xx - 5.08, y)
        sh.wire(tp.p("1"), q); sh.gnd(q, 2.54)
    sh.text("Під щуп на стенді: шини 3V3_AON і 5V_SW, земля. Лінії кільця без точок: відвід на їхніх фронтах", 414.02, 353.06, 1.27)
    sh.text("зайвий. RX_BUF - на виводі 4 U1, TX_SEL - на виводі 6 U2, TX_REGEN і RT_CLK - на U9 і на M1 (TX_FB).", 414.02, 356.87, 1.27)


def line_out_block(sh):
    sh.frame(411.48, 12.7, 580.34, 153.67,
             "11. ЛІНІЙНИЙ ВИХІД   стерео J3 -> U15 PCM5102A -> J8 L, J9 R (RCA, 2.1 Вrms)")
    # ---- U16: the DAC's own 3.3 V from 5V_SW, like U14 for block 9
    u16 = sh.add("LDO_CLK", "U16", "LP5907MFX-3.3", 441.96, 30.48, fp="Package_TO_SOT_SMD:SOT-23-5")
    vin, en = u16.p("1"), u16.p("3")
    xr = vin[0] - 7.62
    sh.wire(vin, (xr, vin[1]))
    sh.up("5V_SW", (xr, vin[1]), 2.54)
    sh.wire(en, (vin[0] - 5.08, en[1]), (vin[0] - 5.08, vin[1]))
    c50 = sh.at_pin("C", "C50", "1u", "1", (xr - 7.62, vin[1]), fp=SMD["C"])
    sh.wire((xr, vin[1]), c50.p("1")); sh.gnd(c50.p("2"))
    sh.nc(u16.p("4")); sh.gnd(u16.p("2"))
    vo = u16.p("5")
    nda = (vo[0] + 5.08, vo[1])
    sh.wire(vo, nda); sh.up("3V3_DAC", nda, 2.54)
    c51 = sh.at_pin("C", "C51", "1u", "1", (nda[0] + 5.08, vo[1]), fp=SMD["C"])
    sh.wire(nda, c51.p("1")); sh.gnd(c51.p("2"))

    # ---- U15: hardware mode, three I2S wires, mute from LOCK
    cx, cy = 474.98, 81.28
    u15 = sh.add("PCM5102A", "U15", "PCM5102A", cx, cy, fp="Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm",
                 ref_at=(cx, cy - 2.54), val_at=(cx, cy + 2.54))
    sh.lbl("I2S_BCLK_F", u15.p("13"), 10.16, "L")
    sh.lbl("I2S_LRCK_F", u15.p("15"), 10.16, "L")
    sh.lbl("I2S_DOUT_F", u15.p("14"), 10.16, "L")
    sh.lbl("LOCK", u15.p("17"), 10.16, "L")
    # SCK low: the PLL makes the system clock from BCK; FMT, FLT, DEMP low: I2S, normal
    # latency, no de-emphasis
    ties = [u15.p(n) for n in ("12", "16", "11", "10")]
    xb = round(ties[0][0] - 5.08, 3)
    for t in ties:
        sh.wire(t, (xb, t[1]))
    sh.wire((xb, ties[0][1]), (xb, ties[-1][1]))
    sh.gnd((xb, ties[-1][1]), 2.54)
    for n in ("1", "8", "20"):
        sh.up("3V3_DAC", u15.p(n), 5.08)
    for n in ("3", "9", "19"):
        sh.gnd(u15.p(n), 2.54)
    # charge pump: the flying cap across CAPP-CAPM, VNEG to ground; LDOO (the core's 1.8 V)
    capp, capm, vneg, ldoo = (u15.p(n) for n in ("2", "4", "5", "18"))
    xo = capp[0]
    c57 = sh.at_pin("C", "C57", "2u2", "1", (xo + 7.62, capp[1]), fp=SMD["C"])
    sh.wire(capp, c57.p("1")); sh.wire(capm, c57.p("2"))
    c58 = sh.at_pin("C", "C58", "2u2", "1", (xo + 25.4, vneg[1]), fp=SMD["C"])
    sh.wire(vneg, c58.p("1")); sh.gnd(c58.p("2"))
    c59 = sh.at_pin("C", "C59", "100n", "1", (xo + 5.08, ldoo[1]), fp=SMD["C"])
    c60 = sh.at_pin("C", "C60", "10u", "1", (xo + 15.24, ldoo[1]), fp="Capacitor_SMD:C_0805_2012Metric")
    sh.wire(ldoo, c60.p("1")); sh.gnd(c59.p("2")); sh.gnd(c60.p("2"))
    # ---- the outputs (2026-10-01): a unity-gain Sallen-Key low-pass per channel on U17, then
    # 100R + 2n2 and an ESD diode at each jack as D4 on J7. R1 = R2 = 4k7, C1 = 820p, C2 = 390p:
    # Butterworth (Q 0.72), fc 60 kHz - flat to 20 kHz, the DAC's out-of-band noise rolled off
    oL, oR = u15.p("6"), u15.p("7")
    x0 = oL[0]
    u17 = sh.add("OPA1678", "U17", "OPA1678", round(x0 + 36.83, 3), round(oL[1] + 7.62, 3),
                 fp="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
                 ref_at=(round(x0 + 36.83, 3), round(oL[1] - 9.14, 3)),
                 val_at=(round(x0 + 36.83, 3), round(oL[1] - 7.62, 3)), fjust=(None, None))
    rows = (("L", oL, "R32", "R43", "C69", "C71", "R45", "C61", "D5", "J8", "LINE L", "5", "6", "7", -1),
            ("R", oR, "R33", "R44", "C70", "C72", "R46", "C62", "D6", "J9", "LINE R", "3", "2", "1", 1))
    for _, o, r1ref, r2ref, c1ref, c2ref, roref, cref, dref, jref, jval, pin_p, pin_m, pin_o, side in rows:
        y = o[1]
        r1 = sh.at_pin("R", r1ref, "4k7", "1", (x0 + 2.54, y), r=90, fp=SMD["R"])
        sh.wire(o, r1.p("1"))
        na = (round(x0 + 12.7, 3), y)                       # R1-R2-C1
        sh.wire(r1.p("2"), na)
        r2 = sh.at_pin("R", r2ref, "4k7", "1", (x0 + 15.24, y), r=90, fp=SMD["R"])
        sh.wire(na, r2.p("1"))
        nb = (round(x0 + 25.4, 3), y)                       # R2-C2-+IN
        sh.wire(r2.p("2"), nb, u17.p(pin_p))
        # C2 to ground: the left channel's hangs down, the right one's stands up; they meet
        c2 = sh.at_pin("C", c2ref, "390p", "1" if side < 0 else "2", nb, fp=SMD["C"],
                       ref_at=(round(nb[0] + 1.27, 3), round(y + 3.81 if side < 0 else y - 5.08, 3)),
                       val_at=(round(nb[0] + 1.27, 3), round(y + 5.08 if side < 0 else y - 3.81, 3)),
                       fjust=("left", "left"))
        # the follower: -IN to OUT, OUT on to R_out; C1 from R1-R2 over (left) or under (right) to OUT
        sh.wire(u17.p(pin_m), u17.p(pin_o))
        no = (round(u17.p(pin_o)[0] + 2.54, 3), y)
        sh.wire(u17.p(pin_o), no)
        yc = round(y + side * 5.08, 3)
        c1 = sh.at_pin("C", c1ref, "820p", "1", (round(x0 + 22.86, 3), yc), r=90, fp=SMD["C"])
        sh.wire(na, (na[0], yc), c1.p("1"))
        sh.wire(c1.p("2"), (no[0], yc), no)
        rx = round(no[0] + 6.35, 3)                         # labels away from U17's supply symbols
        ro = sh.at_pin("R", roref, "100", "1", (round(no[0] + 2.54, 3), y), r=90, fp=SMD["R"],
                       ref_at=(rx, round(y - 4.32 if side < 0 else y + 2.54, 3)),
                       val_at=(rx, round(y - 2.54 if side < 0 else y + 4.32, 3)), fjust=(None, None))
        sh.wire(no, ro.p("1"))
        n = (round(ro.p("2")[0] + 2.54, 3), y)
        sh.wire(ro.p("2"), n)
        c = sh.at_pin("C", cref, "2n2", "1", n, fp=SMD["C"]); sh.gnd(c.p("2"))
        nd = (round(n[0] + 10.16, 3), y)
        d = sh.at_pin("TVS", dref, "PESD5V0S1BL", "1", (nd[0], nd[1] + 2.54), r=270, fp="Diode_SMD:D_SOD-882",
                      ref_at=(nd[0] + 2.54, nd[1] + 5.08), val_at=(nd[0] + 2.54, nd[1] + 7.62),
                      fjust=("left", "left"))
        sh.wire(nd, d.p("1")); sh.gnd(d.p("2"))
        j = sh.at_pin("COAX", jref, jval, "1", (round(nd[0] + 10.16, 3), y), fp=f"{LIB}:{FP_RCA}",
                      ref_at=(round(nd[0] + 12.7, 3), y - 5.08), val_at=(round(nd[0] + 12.7, 3), y - 3.81),
                      fjust=(None, None))
        sh.wire(n, nd, j.p("1")); sh.gnd(j.p("2"), 2.54)
    # the two C2s meet between the rows: one ground for both
    mid = (round(x0 + 25.4, 3), round(oL[1] + 7.62, 3))
    sh.wire(mid, (round(mid[0] - 2.54, 3), mid[1])); sh.gnd((round(mid[0] - 2.54, 3), mid[1]))
    # supplies: V+ = 5V_SW, V- = VNEG_A
    vp, vn = u17.p("8"), u17.p("4")
    sh.up("5V_SW", (round(vp[0] + 2.54, 3), vp[1]), 0); sh.wire(vp, (round(vp[0] + 2.54, 3), vp[1]))
    qn = (round(vn[0] + 2.54, 3), vn[1])
    sh.wire(vn, qn)
    sh.pwr += 1
    sh.add("VNEG_A", f"#PWR{sh.pwr:03d}", "VNEG_A", qn[0], qn[1], 180,
           ref_at=(qn[0], qn[1] - 3.81), val_at=(qn[0], round(qn[1] + 3.81, 3)))

    # ---- U18: VNEG_A, about -5.2 V, inverted from 5V_SW for U17 only
    ux, uy = round(x0 + 50.8, 3), 106.68
    u18 = sh.add("TPS60403", "U18", "TPS60403", ux, uy, fp="Package_TO_SOT_SMD:SOT-23-5",
                 ref_at=(ux, round(uy - 1.9, 3)), val_at=(ux, round(uy - 0.63, 3)), fjust=(None, None))
    pin_in, pin_out = u18.p("2"), u18.p("1")
    nin = (round(pin_in[0] - 5.08, 3), pin_in[1])
    sh.wire(pin_in, nin); sh.up("5V_SW", nin, 2.54)
    c73 = sh.at_pin("C", "C73", "1u", "1", nin, fp=SMD["C"]); sh.gnd(c73.p("2"))
    nout = (round(pin_out[0] + 5.08, 3), pin_out[1])
    sh.wire(pin_out, nout); sh.up("VNEG_A", nout, 2.54)
    c75 = sh.at_pin("C", "C75", "4u7", "1", nout, fp="Capacitor_SMD:C_0805_2012Metric"); sh.gnd(c75.p("2"))
    cp, cm = u18.p("5"), u18.p("3")
    c74 = sh.at_pin("C", "C74", "1u", "1", (cp[0], round(cp[1] - 2.54, 3)), r=90, fp=SMD["C"])
    sh.wire(cp, c74.p("1")); sh.wire(c74.p("2"), cm)
    sh.gnd(u18.p("4"))
    # U17's own decoupling, one 100n per supply pin
    for k, (ref, rail_) in enumerate((("C76", "5V_SW"), ("C77", "VNEG_A"))):
        top = (round(x0 + 40.64 + 20.32 * k, 3), 119.38)
        sh.up(rail_, top, 0)
        c = sh.at_pin("C", ref, "100n", "1", top, fp=SMD["C"]); sh.gnd(c.p("2"))
    # C78/C79 (2026-10-01): 100u + 100n at the buffer's end of 5V_SW, which comes ~85 mm from
    # U16 beside 3V3_DAC - the same pair as C63/C64 at D3; the user copied them there on the board
    xt, yt = (round(x0 + 17.78, 3), round(x0 + 29.21, 3)), 119.38
    c78 = sh.at_pin("CP", "C78", "100u 16V", "1", (xt[0], yt), fp="Capacitor_SMD:CP_Elec_6.3x7.7")
    c79 = sh.at_pin("C", "C79", "100n", "1", (xt[1], yt), fp=SMD["C"])
    sh.wire(c78.p("1"), c79.p("1"), (round(x0 + 40.64, 3), yt))
    sh.gnd(c78.p("2")); sh.gnd(c79.p("2"))

    # ---- the 3V3_DAC decoupling, drawn as a row; on the board each cap sits at its pin
    caps = [("C52", "100n", SMD["C"]), ("C53", "2u2", SMD["C"]), ("C54", "100n", SMD["C"]),
            ("C55", "4u7", "Capacitor_SMD:C_0805_2012Metric"), ("C56", "100n", SMD["C"])]
    ys = 119.38
    xs = [round(419.1 + 8.89 * i, 3) for i in range(len(caps))]
    for x, (ref, val, fp) in zip(xs, caps):
        c = sh.at_pin("C", ref, val, "1", (x, ys), fp=fp)
        sh.gnd(c.p("2"))
    sh.wire((xs[0], ys), (xs[-1], ys))
    sh.up("3V3_DAC", (xs[2], ys), 2.54)

    y = 134.62
    for line in (
        "U15 PCM5102A, апаратний режим: FMT = 0 (I2S), FLT = 0 (звичайна затримка), DEMP = 0. SCK на землі: PLL бере такт з BCK (3 проводи, BCK = 64 Fs).",
        "Вхід - те саме стерео, що на J3. XSMT = LOCK: без захоплення кільця і до конфігурації FPGA (R8) ЦАП приглушений; спад і підйом за 104 відліки.",
        "Вихід 2.1 Вrms відносно землі, без розділових конденсаторів. U17: повторювач з ФНЧ Саллена-Кі 2-го порядку (Баттерворт, 60 кГц), C0G; далі 100 Ом + 2.2 нФ і D5, D6 (ESD) на RCA.",
        "U17 живиться від +5V_SW і VNEG_A (-5.2 В, U18 TPS60403): вихід до шин, вхід до V-, тож +-3 В сигналу проходять з запасом. J8, J9 пад 3: як у J7, зміряти на зразку.",
        "U16 LP5907: 3V3_DAC від 5V_SW. Ємність на його виході - до 10 мкФ, тому AVDD 4.7 мкФ і CPVDD 2.2 мкФ замість 10 мкФ з рис. 33.",
        "На платі кожен конденсатор ряду стоїть біля свого виводу: C52, C53 - CPVDD; C54, C55 - AVDD; C56 - DVDD.",
    ):
        sh.text(line, 414.02, y, 1.27)
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
    digital_audio_block(sh)
    testpoint_block(sh)
    line_out_block(sh)
    return sh


def main():
    sh = build()
    out = HERE / f"{PROJECT}.kicad_sch"
    sh.write(out)
    pro = HERE / f"{PROJECT}.kicad_pro"
    if not pro.exists():            # gen_listener_pcb.py fills it in (the board net classes)
        pro.write_text(
            '{"meta": {"filename": "%s.kicad_pro", "version": 3}, "schematic": {}}\n' % PROJECT,
            encoding="utf-8")
    # project symbol library + table, so the sheet opens with no "missing
    # library" warnings and the parts can be reused
    own = [sym.text.replace(f'(symbol "{LIB}:', '(symbol "', 1)
           for sym in S.values() if sym.lib_id.startswith(LIB + ":")]
    (HERE / f"{LIB}.kicad_sym").write_text(
        '(kicad_symbol_lib (version 20231120) (generator "gen_listener")\n'
        + "\n".join(own) + "\n)\n", encoding="utf-8")
    fp, cu, size = si514_footprint()
    assert cu >= 0.2, cu
    old = HERE / f"{LIB}.pretty" / "Si514_5x7_3.2x5_2.5x3.2.kicad_mod"     # the three-package U7 of v1.1..v1.3
    if old.exists():
        old.unlink()
    (HERE / f"{LIB}.pretty").mkdir(exist_ok=True)
    (HERE / f"{LIB}.pretty" / f"{FP_SI514}.kicad_mod").write_text(fp, encoding="utf-8")
    for name, make in NEW_FOOTPRINTS:
        (HERE / f"{LIB}.pretty" / f"{name}.kicad_mod").write_text(make(), encoding="utf-8")
        print("wrote", name)
    (HERE / MODELS).mkdir(exist_ok=True)
    for name, body in ((FP_FOT, te_fot_body), (FP_T10, t10_body), (FP_RCA, bkl_rca_body)):
        (HERE / MODELS / f"{name}.step").write_text(_step(name, body()), encoding="utf-8")
        print("wrote", f"{MODELS}/{name}.step")
    (HERE / "fp-lib-table").write_text(
        '(fp_lib_table (version 7)\n'
        f'  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB}.pretty")(options "")'
        '(descr "Project footprints, written by gen_listener.py"))\n)\n', encoding="utf-8")
    print(f"wrote {FP_SI514}: {size[0]:.2f} x {size[1]:.2f} mm courtyard, "
          f"copper gap between pins >= {cu:.2f} mm")
    (HERE / "sym-lib-table").write_text(
        '(sym_lib_table (version 7)\n'
        f'  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB}.kicad_sym")(options "")'
        '(descr "Project symbols, written by gen_listener.py"))\n)\n', encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
