#!/usr/bin/env python3
"""console_format.py - the listener's console (the host's UART0, 921600 baud) line by line.

One parser for everything that reads the console: the recorder (console_log.py) live, the
decoder at home (trace_decode.py) and their tests. The host prints (listener_fw/main/host.c):

    I (<ms>) tel: <frame> <source>><target> <FBlock>.<Inst>.<FktID> <OPType> [<length>] <data>[ ...]
    I (<ms>) host: packets N (bad N, lost in the FPGA N, gaps N, parity dropped N), telegrams N, ...
    CAP BEGIN runs=N packets=N missing=N      a capture's dump (tools/capture_analyse.py)
    CAP <packet> <64 hex digits> <8 hex digits>  |  CAP <packet> -  |  CAP END

and ESP-IDF prints its own lines in the same form, "<E|W|I|D|V> (<ms>) <tag>: <text>", the
second-stage bootloader's ("I (29) boot: ESP-IDF v6.1 2nd stage bootloader") among them; <ms>
counts from the ESP32's start. The ROM's lines come at 115200 baud and arrive as noise.
test_console_log.py checks these formats against host.c's own strings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

BAUD = 921600
STATUS_S = 10                     # host.c STATUS_US: the status line's period
ESC = re.compile(r"\x1b\[[0-9;]*m")                                       # colours, if turned on
LOG = re.compile(r"^([EWIDV]) \((\d+)\) ([^:]*): (.*)$")
TEL = re.compile(r"^([0-9A-F]{8}) ([0-9A-F]{4})>([0-9A-F]{4}) ([0-9A-F]{2})\.([0-9A-F]{2})\.([0-9A-F]{3}) "
                 r"(\S+) \[(\d+)\]((?: [0-9A-F]{2})*)( \.\.\.)?$")
STATUS = re.compile(r"^packets (\d+) \(bad (\d+), lost in the FPGA (\d+), gaps (\d+), parity dropped (\d+)\), "
                    r"telegrams (\d+), refused (\d+), segments dropped (\d+), trace lost (\d+), "
                    r"capture packets (\d+) \(bad (\d+)\), dumps (\d+), audio in (.+?) \(phone (\S+), TOSLINK (.+)\)$")
COUNTERS = ("packets", "bad", "fpga_lost", "gaps", "parity_dropped", "telegrams", "refused", "seg_dropped",
            "trace_lost", "cap_packets", "cap_bad", "dumps")
# lost on our side of the ring: a packet the ESP32 could not read, a block the FPGA had no room
# for, a long telegram whose segments could not be kept, a telegram the console had no time for
LOSSES = ("bad", "fpga_lost", "seg_dropped", "trace_lost")
OPS = ("Set/Start", "Get/Abort", "SetGet/StartResult", "Inc", "Dec", "GetInterface", "StartResultAck",
       "AbortAck", "StartAck", "ErrorAck", "ProcessingAck", "Processing", "Status/Result", "ResultAck",
       "Interface", "Error")                                              # host.c op_name()
VALUE_OPS = ("Set/Start", "SetGet/StartResult", "Status/Result")          # what sound.c takes values from

# Names for the functions the host acts on, as listener_fw/components/mostctl cites them (sound.h,
# amp_model.h, wheel.h); everything else is shown by its numbers.
NAMES = {
    (0x22, 0x110): "SinkInfo", (0x22, 0x111): "Connect", (0x22, 0x112): "DisConnect", (0x22, 0x113): "Mute",
    (0x22, 0x200): "Balance", (0x22, 0x201): "Loudness", (0x22, 0x202): "Bass", (0x22, 0x203): "Treble",
    (0x22, 0x204): "Fader", (0x22, 0x400): "Volume", (0x22, 0x46D): "SpeakerLevel",
    (0x24, 0x100): "SourceInfo", (0x24, 0x101): "Allocate", (0x24, 0x102): "DeAllocate",
    (0x20, 0x200): "VolumeActual (BMW)", (0x20, 0x220): "Balance (BMW)", (0x20, 0x221): "Fader (BMW)",
    (0x20, 0x222): "Bass (BMW)", (0x20, 0x223): "Treble (BMW)",
    (0xF0, 0x409): "volumes (Jaguar XF)",
}
WHEEL_FKT = 0xCA1                 # the wheel's track keys, any FBlock (wheel.h)
SND_SINKS = 8                     # sound.h


@dataclass
class Tel:
    frame: int
    source: int
    target: int
    fblock: int
    inst: int
    fkt: int
    op: str
    length: int
    data: bytes
    truncated: bool

    @property
    def func(self) -> str:
        """FBlock.Inst.FktID as the trace prints it, with a name where the host knows one."""
        s = f"{self.fblock:02X}.{self.inst:02X}.{self.fkt:03X}"
        n = name(self.fblock, self.fkt)
        return f"{s} {n}" if n else s

    def short(self) -> str:
        return f"{self.func} {self.op} [{self.length}]" + "".join(f" {b:02X}" for b in self.data) + \
            (" ..." if self.truncated else "")


@dataclass
class Line:
    kind: str                     # "tel", "status", "cap", "log" (any other ESP-IDF line), "other"
    text: str                     # the line as it came, without colours and line end
    level: str = ""
    ms: int | None = None         # the ESP32's milliseconds since its start
    tag: str = ""
    msg: str = ""
    tel: Tel | None = None
    status: dict = field(default_factory=dict)

    @property
    def boot_banner(self) -> bool:
        return self.tag == "boot" and self.msg.startswith("ESP-IDF")


def name(fblock: int, fkt: int) -> str:
    if fkt == WHEEL_FKT:
        return "wheel keys"
    return NAMES.get((fblock, fkt), "")


def parse_tel(msg: str) -> Tel | None:
    m = TEL.match(msg)
    if not m:
        return None
    data = bytes(int(x, 16) for x in m.group(9).split())
    if len(data) != int(m.group(8)) or m.group(7) not in OPS:
        return None
    return Tel(int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16), int(m.group(4), 16),
               int(m.group(5), 16), int(m.group(6), 16), m.group(7), int(m.group(8)), data, bool(m.group(10)))


def parse_status(msg: str) -> dict | None:
    m = STATUS.match(msg)
    if not m:
        return None
    d = {k: int(v) for k, v in zip(COUNTERS, m.groups()[:12])}
    d["audio_in"], d["phone"], d["toslink"] = m.group(13), m.group(14), m.group(15)
    return d


def classify(raw: bytes | str) -> Line:
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    text = ESC.sub("", text.rstrip("\r\n"))
    if text.startswith("CAP "):
        return Line("cap", text)
    m = LOG.match(text)
    if not m:
        return Line("other", text)
    ln = Line("log", text, level=m.group(1), ms=int(m.group(2)), tag=m.group(3), msg=m.group(4))
    if ln.tag == "tel" and ln.level == "I":
        t = parse_tel(ln.msg)
        if t:
            ln.kind, ln.tel = "tel", t
    elif ln.tag == "host" and ln.level == "I" and ln.msg.startswith("packets "):
        s = parse_status(ln.msg)
        if s is not None:
            ln.kind, ln.status = "status", s
    return ln


def sound_values(t: Tel) -> list:
    """What sound.c takes from this telegram for J3's sound: [(what, number or None, as text)], one
    for each value (a SpeakerLevel per sink; every level in a 0x409 record, and the screen's Set to
    one of them, so that the recording shows them all). These raw values are what a car's scales
    are fixed from (snd_cfg_t, listener_fw/README.md)."""
    if t.op not in VALUE_OPS or t.length < 1:
        return []
    d = t.data
    s8 = lambda v: v - 256 if v > 127 else v                             # noqa: E731
    if t.fblock == 0x22:
        if t.fkt == 0x400:
            return [("22.400 Volume", d[0], f"volume {d[0]}")]
        if t.fkt == 0x46D:
            if t.length < 3 or not 1 <= d[1] <= SND_SINKS:
                return []
            m = max(s8(v) for v in d[2:])
            return [(f"22.46D SpeakerLevel, sink {d[1]} (its loudest speaker, dB)", None if m <= -120 else m,
                     "silent" if m <= -120 else f"{m} dB")]
        if t.fkt in (0x200, 0x202, 0x203):
            return [(f"22.{t.fkt:03X} {NAMES[(0x22, t.fkt)]}", s8(d[0]), f"{s8(d[0]):+d}")]
        if t.fkt == 0x201:
            return [("22.201 Loudness", 1 if d[0] else 0, "on" if d[0] else "off")]
    if t.fblock == 0x20:
        if t.fkt == 0x200:
            return [("20.200 VolumeActual (BMW)", d[0], f"volume {d[0]}")]
        if t.fkt in (0x220, 0x222, 0x223):
            return [(f"20.{t.fkt:03X} {NAMES[(0x20, t.fkt)]}", s8(d[0]), f"{s8(d[0]):+d}")]
    if t.fblock == 0xF0 and t.fkt == 0x409 and t.length >= 3:
        # the gateway's Status: byte 0 the record's kind; kind 0, the whole record, has the volume in
        # byte 2 and the levels (sent + 5) in bytes 7, 9, 10, 11; the screen's Set is [channel, 0, level + 5]
        lvl = lambda v: max(0, v - 5)                                     # noqa: E731
        if t.op == "Set/Start":
            return [(f"F0.409 Set, channel {d[0]:02X} (Jaguar XF)", lvl(d[2]), f"level {lvl(d[2])}")]
        if t.op != "Status/Result":
            return []
        if d[0] != 0:
            return [(f"F0.409 a record of kind {d[0]} (Jaguar XF)", None, d[:t.length].hex(" ").upper())]
        out = [("F0.409 volume (Jaguar XF)", d[2], f"volume {d[2]}")]
        for i, what in ((7, "phone"), (9, "navigation"), (10, "voice"), (11, "parking sensors")):
            if t.length > i:
                out.append((f"F0.409 {what} level (Jaguar XF)", lvl(d[i]), f"level {lvl(d[i])}"))
        return out
    return []


def sound_value(t: Tel) -> str | None:
    """The same as one line of text for the screen; None if nothing."""
    v = sound_values(t)
    return "; ".join(f"{w}: {x}" for w, _, x in v) if v else None


class Lines:
    """A byte stream into whole lines; a line's first byte's offset kept with it."""

    def __init__(self, limit: int = 4096):
        self.buf = bytearray()
        self.start = 0                    # the stream offset of buf[0]
        self.limit = limit                # a "line" this long without an end is noise, cut there

    def feed(self, data: bytes):
        self.buf += data
        out = []
        while True:
            i = self.buf.find(b"\n")
            if i < 0:
                if len(self.buf) > self.limit:
                    out.append((self.start, bytes(self.buf[:self.limit])))
                    del self.buf[:self.limit]
                    self.start += self.limit
                break
            out.append((self.start, bytes(self.buf[:i])))
            del self.buf[:i + 1]
            self.start += i + 1
        return out

    def rest(self):
        """What is left without its line end (a cut line), and empty after."""
        r = (self.start, bytes(self.buf)) if self.buf else None
        self.start += len(self.buf)
        self.buf.clear()
        return r
