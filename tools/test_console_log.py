#!/usr/bin/env python3
"""test_console_log.py - the recorder's decisions that need no ESP32, and the console's formats.

    python tools/test_console_log.py

  formats   host.c's own format strings (the trace, the status line, the dump, the OPType names,
            the status period) and the console's baud rate in sdkconfig.defaults, filled with known
            values: console_format must read every value back. A changed format in the firmware
            fails here, not in a car.
  sound     every function sound.c takes a value from has a name and a value here; the Jaguar XF's
            0xF0.0x409 gives bytes 2 and 8, and byte 10 (the parking sensors) once it is 11 bytes long
  port      the DevKitC's bridge picked by its USB ID: CP2102N, CH9102, the FPGA module's bridge
            beside it ignored, two bridges refused (a wrong guess records nothing), macOS's cu node
  keys      Latin, Caps Lock, the Ukrainian layout
  monitor   a scripted console: the first start and a restart, a loss counter rising and the
            counters starting anew after a restart, a line split across chunks, the sound value
            shown, a dump, the silence alarm and its repeat, a key answered and one not, the port lost
            (and no silence alarm while it is away)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import console_format as CF                                                # noqa: E402
import console_log as CL                                                   # noqa: E402

BAD = 0


def check(cond, msg):
    global BAD
    if not cond:
        BAD += 1
        print("  BAD ", msg)
    return cond


def c_strings(src: str, start: int) -> str:
    """The C string literals from src[start:] that follow each other, joined (the first one starts
    at start)."""
    out, i = [], start
    lit = re.compile(r'\s*"((?:[^"\\]|\\.)*)"')
    while True:
        m = lit.match(src, i)
        if not m:
            break
        out.append(m.group(1))
        i = m.end()
    return bytes("".join(out), "utf-8").decode("unicode_escape")


def c_fill(fmt: str, values) -> str:
    """printf with the C length modifiers taken off (%lu, %08lX -> Python's %)."""
    return re.sub(r"%(0?\d*)l?([diuXxs])", lambda m: "%" + m.group(1) + ("d" if m.group(2) in "iu" else m.group(2)),
                  fmt) % tuple(values)


def formats():
    host = (ROOT / "listener_fw" / "main" / "host.c").read_text(encoding="utf-8")
    i = host.index('ESP_LOGI("tel",') + len('ESP_LOGI("tel",')
    tel_fmt = c_strings(host, i)
    i = host.index('ESP_LOGI(TAG, "packets') + len("ESP_LOGI(TAG,")
    st_fmt = c_strings(host, i)
    tag = re.search(r'static const char \*TAG = "([^"]+)";', host).group(1)
    ops = re.findall(r'"([^"]+)"', re.search(r"static const char \*n\[16\] = \{(.*?)\};", host, re.S).group(1))
    status_us = int(re.search(r"#define STATUS_US\s+(\d+)", host).group(1))
    cap = re.findall(r'printf\("(CAP [^"]*)\\n"', host)
    sdk = (ROOT / "listener_fw" / "sdkconfig.defaults").read_text(encoding="utf-8")
    baud = int(re.search(r"CONFIG_ESP_CONSOLE_UART_BAUDRATE=(\d+)", sdk).group(1))
    check(tag == "host", f"the host's tag is {tag!r}, console_format reads 'host'")
    check(tuple(ops) == CF.OPS, f"op_name() {ops} vs {CF.OPS}")
    check(status_us == CF.STATUS_S * 1_000_000, f"STATUS_US {status_us} vs {CF.STATUS_S} s")
    check(baud == CF.BAUD, f"the console at {baud} baud, console_format says {CF.BAUD}")
    check(cap == ["CAP BEGIN runs=%lu packets=%lu missing=%lu", "CAP %lu -", "CAP %lu %s", "CAP END"],
          f"the dump's lines changed: {cap}")
    # the trace: every OPType, a payload, an empty one, a cut one
    for k, op in enumerate(CF.OPS):
        data = bytes((k * 37 + j) & 0xFF for j in range(k % 5))
        hexs = "".join(f" {b:02X}" for b in data)
        trunc = " ..." if k == 3 else ""
        msg = c_fill(tel_fmt, (0x1F2A0 + k, 0x0100, 0x0180 + k, 0x22, k, 0x400 + k, op, len(data), hexs, trunc))
        ln = CF.classify(f"I ({1000 + k}) tel: {msg}\r\n".encode())
        t = ln.tel
        check(ln.kind == "tel" and t is not None and ln.ms == 1000 + k and
              (t.frame, t.source, t.target, t.fblock, t.inst, t.fkt, t.op, t.length, t.data, t.truncated) ==
              (0x1F2A0 + k, 0x100, 0x180 + k, 0x22, k, 0x400 + k, op, len(data), data, bool(trunc)),
              f"trace line {msg!r} read as {ln}")
    # the status line, each counter its own value, every audio-in name the host prints
    names = [("none", "idle", "no signal"), ("the phone", "streaming", "locked"),
             ("the TOSLINK input", "idle", "not PCM")]
    for k, (src, ph, opt) in enumerate(names):
        vals = [100 * k + j for j in range(12)]
        msg = c_fill(st_fmt, vals + [src, ph, opt])
        ln = CF.classify(f"I (20000) {tag}: {msg}\r\n")
        want = dict(zip(CF.COUNTERS, vals), audio_in=src, phone=ph, toslink=opt)
        check(ln.kind == "status" and ln.status == want, f"status line {msg!r} read as {ln.status}")
    print(f"{'ok  ' if not BAD else '    '} formats: the trace, the status line, the dump, the OPTypes, "
          f"{baud} baud - as host.c prints them")


def sound():
    bad0 = BAD
    src = (ROOT / "listener_fw" / "components" / "mostctl" / "sound.c").read_text(encoding="utf-8")
    body = src[src.index("int snd_tel("):src.index("float snd_volume_db(")]
    b22 = body[body.index("t->fblock == 0x22"):body.index("t->fblock == 0x20")]
    b20 = body[body.index("t->fblock == 0x20"):body.index("t->fblock == 0xF0")]
    funcs = [(0x22, int(x, 16)) for x in re.findall(r"case 0x([0-9A-F]+):", b22)] + \
            [(0x20, int(x, 16)) for x in re.findall(r"case 0x([0-9A-F]+):", b20)] + [(0xF0, 0x409)]
    check(len(funcs) == 12, f"sound.c's functions: {funcs}")
    for fb, fkt in funcs:
        data = bytes([0, 0, 0xFB, 0x80, 0, 0, 0, 0, 7]) if fkt in (0x467, 0x409) else bytes([3, 1, 0xEC, 0xF6])
        t = CF.Tel(0, 0x100, 0x180, fb, 1, fkt, "Set/Start", len(data), data, False)
        check(CF.name(fb, fkt) != "", f"{fb:02X}.{fkt:03X}: no name")
        check(CF.sound_values(t), f"{fb:02X}.{fkt:03X}: no sound value from {data.hex()}")
        g = CF.Tel(0, 0x100, 0x180, fb, 1, fkt, "Get/Abort", len(data), data, False)
        check(not CF.sound_values(g), f"{fb:02X}.{fkt:03X}: a value from a Get")
    v = CF.sound_values(CF.Tel(0, 0x100, 0x180, 0x22, 1, 0x46D, "Status/Result", 6, bytes([1, 1, 0xEC, 0xF0, 0xE2, 0x02]),
                               False))
    check(v == [("22.46D SpeakerLevel, sink 1 (its loudest speaker, dB)", 2, "2 dB")], f"SpeakerLevel: {v}")
    v = CF.sound_values(CF.Tel(0, 0x100, 0x180, 0x22, 1, 0x202, "Set/Start", 1, bytes([0xFD]), False))
    check(v == [("22.202 Bass", -3, "-3")], f"Bass: {v}")
    # the XF's levels: bytes 2 and 8 in a 9-byte Status, byte 10 (the parking sensors) once it is 11 long
    xf = bytes([1, 0, 30, 0, 0, 0, 0, 0, 20, 0, 12])
    for n, want in ((9, [30, 20]), (11, [30, 20, 12])):
        v = CF.sound_values(CF.Tel(0, 0x161, 0x16E, 0xF0, 1, 0x409, "Status/Result", n, xf[:n], False))
        check([x for _, x, _ in v] == want, f"F0.409, {n} bytes: {v}")
    check(v[2:] == [("F0.409 parking sensors volume (Jaguar XF)", 12, "volume 12")], f"F0.409 byte 10: {v[2:]}")
    print(f"{'ok  ' if BAD == bad0 else '    '} sound: the {len(funcs)} functions sound.c reads, named and read; "
          f"0xF0.0x409's bytes 2, 8 and 10")


def port(dev, vid, pid, sn="0001"):
    return SimpleNamespace(device=dev, vid=vid, pid=pid, serial_number=sn)


CP, CH, FT = (0x10C4, 0xEA60), (0x1A86, 0x55D4), (0x0403, 0x6010)
CASES = [
    ("Windows, CP2102N", [port("COM5", *CP)], "COM5"),
    ("Windows, CH9102", [port("COM4", *CH)], "COM4"),
    ("the FPGA module's bridge beside it", [port("COM6", *FT), port("COM7", *FT), port("COM5", *CP)], "COM5"),
    ("only the FPGA module's bridge", [port("COM6", *FT), port("COM7", *FT)], None),
    ("two ESP32 bridges", [port("COM5", *CP), port("COM9", *CH)], None),
    ("macOS, cu and tty nodes", [port("/dev/tty.usbserial-0001", *CP), port("/dev/cu.usbserial-0001", *CP)],
     "/dev/cu.usbserial-0001"),
    ("nothing", [], None),
]


def ports():
    bad0 = BAD
    for name, ps, want in CASES:
        CL.serial.tools.list_ports.comports = lambda ps=ps: list(ps)
        got = CL.find_port(None)
        check(got == want, f"port: {name}: {got}, want {want}")
        check(want is not None or CL.PORT_NOTE, f"port: {name}: no hint on the screen")
        if name == "two ESP32 bridges":
            check("COM5" in CL.PORT_NOTE[0] and "COM9" in CL.PORT_NOTE[0], f"the hint names both: {CL.PORT_NOTE}")
    check(CL.find_port("COM7") == "COM7", "--port is not taken as given")
    keys = {"m": "m", "M": "m", "ь": "m", "Ь": "m", "т": "n", "в": "d", "с": "c", "c": "c", "C": "c",
            "й": "q", "н": "y", "i": "i", "x": "x", None: None}
    for k, want in keys.items():
        check(CL.command_key(k) == want, f"key {k!r}: {CL.command_key(k)!r}, want {want!r}")
    print(f"{'ok  ' if BAD == bad0 else '    '} port and keys: {len(CASES)} port cases, Latin, Caps Lock, "
          f"the Ukrainian layout")


def status(ms, **kw):
    v = dict.fromkeys(CF.COUNTERS, 0)
    v.update(kw)
    return (f"I ({ms}) host: packets {v['packets']} (bad {v['bad']}, lost in the FPGA {v['fpga_lost']}, gaps "
            f"{v['gaps']}, parity dropped {v['parity_dropped']}), telegrams {v['telegrams']}, refused {v['refused']}, "
            f"segments dropped {v['seg_dropped']}, trace lost {v['trace_lost']}, capture packets {v['cap_packets']} "
            f"(bad {v['cap_bad']}), dumps {v['dumps']}, audio in none (phone idle, TOSLINK no signal)\r\n").encode()


def monitor():
    bad0 = BAD
    got = []
    m = CL.Monitor(got.append)
    m.port("open", 0.0)
    m.feed(0.1, b"\x00\xff\x8a ets noise at 115200\r\nI (29) boot: ESP-IDF v6.1 2nd stage bootloader\r\n")
    check(m.starts == 1 and got == [], f"the first start: starts {m.starts}, alarms {got}")
    m.feed(0.2, b"I (310) main: listener host\r\n" + status(10000, packets=5))
    m.feed(1.0, status(20000, packets=9, trace_lost=2))
    check(got == ["loss"] and m.rose["trace_lost"] == 2, f"trace lost rising: {got}, {m.rose}")
    m.feed(1.1, b"I (20100) tel: 0001F2A0 0100>0180 22.01.4")             # a line in two chunks
    m.feed(1.2, b"00 Set/Start [1] 1C\r\n")
    check(m.tels == 1 and m.last_sound == "22.400 Volume: volume 28", f"split telegram: {m.tels}, {m.last_sound!r}")
    m.feed(2.0, b"I (35) main: started again\r\n")                         # its ms went back: a restart
    check(got[-1:] == ["restart"] and m.starts == 2 and m.status is None, f"restart: {got}, starts {m.starts}")
    m.feed(3.0, status(10000, packets=2))                                   # counters anew: no loss
    check(got.count("loss") == 1, f"a new start's counters taken as a loss: {got}")
    m.feed(3.1, b"CAP BEGIN runs=0 packets=0 missing=0\r\nCAP END\r\n")
    check(m.dumps == 1, f"dump not counted: {m.dumps}")
    m.sent("d", 3.2)
    m.feed(3.3, b"I (10300) host: capture: dumping what was captured\r\n")
    m.tick(5.0)
    check("unanswered" not in got, f"an answered key raised an alarm: {got}")
    m.sent("c", 5.0)
    m.tick(6.6)
    check(got[-1:] == ["unanswered"], f"an unanswered key: {got}")
    m.feed(7.0, b"W (10900) host: a gap in the control blocks: injection held until AUX's channels are told again\r\n")
    check(m.warnings == 1 and m.last_warn.startswith("W host: a gap"), f"warning: {m.warnings} {m.last_warn!r}")
    n = len(got)
    m.tick(7.0 + 24)
    check(len(got) == n, f"silence alarm too early: {got[n:]}")
    m.tick(7.0 + 26)
    m.tick(7.0 + 30)
    check(got[n:] == ["silent"], f"silence: {got[n:]}")
    m.tick(7.0 + 52)
    check(got[n:] == ["silent", "silent"], f"silence repeated: {got[n:]}")
    check("NO LINE FOR" in m.screen(7.0 + 52), f"the screen: {m.screen(7.0 + 52)!r}")
    m.port("lost", 60.0)
    check(got[-1] == "port", f"port lost: {got}")
    n = len(got)
    m.tick(60.0 + 40)
    check(len(got) == n and "NO LINE" not in m.screen(100.0), f"silence counted while the port is away: {got[n:]}")
    print(f"{'ok  ' if BAD == bad0 else '    '} monitor: starts, losses, a split line, the sound value, a dump, "
          f"keys answered or not, silence, the port")


def main() -> int:
    sys.stdout.reconfigure(errors="backslashreplace")       # a console in cp1251 still shows a failure
    formats()
    sound()
    ports()
    monitor()
    print("CONSOLE_LOG: " + ("PASS" if not BAD else f"FAIL, {BAD}"))
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
