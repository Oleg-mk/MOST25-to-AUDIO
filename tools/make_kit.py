#!/usr/bin/env python3
"""make_kit.py - kit/, what the project hands over, kept equal to its sources.

    python tools/make_kit.py            copy the boards' and the laptop's files into kit/, check the
                                        bitstream and the firmware there
    python tools/make_kit.py --flash    the same, and take the last builds' bitstream and firmware
                                        into kit/2_flash
    python tools/make_kit.py --check    change nothing; fail when kit/ differs from its sources

kit/1_boards   the board order, v2.0: listener_hw2/fab's files for JLCPCB (the three assemblies' BOM
               and CPL), the full BOM, the schematic and the assembly drawings of both sides; with
               the tube's end caps from listener_hw2/caps (STL, STEP, the drawing), copied
kit/2_flash    fpga/listener.fs, the bitstream, and esp32/*.bin, the host's firmware, each with a
               BUILD.txt: the commit its sources are, the build's own numbers, the files' sha256.
               --flash takes them only from builds of committed sources (git shows no change there,
               the build is newer than every source file, the ESP32 image's version has no -dirty,
               the FPGA's timing check passes); the check fails as soon as those sources differ from
               that commit's, so the kit never holds a build older than its sources
kit/3_laptop   the laptop's programs: tools/console_log.py, console_format.py, trace_decode.py and
               capture_analyse.py, copied byte for byte (line ends aside)
The READMEs and the launchers in kit/ are written by hand; this script only checks they are there,
and that kit/ holds nothing else (a file left from an earlier kit fails the check).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "kit"
BOARD = ROOT / "listener_gw" / "board"
FW = ROOT / "listener_fw"

COPIES = {
    "1_boards/most_listener_v2-gerbers.zip": "listener_hw2/fab/most_listener_v2-gerbers.zip",
    **{f"1_boards/most_listener_v2-{kind}-jlcpcb-{a}.csv": f"listener_hw2/fab/most_listener_v2-{kind}-jlcpcb-{a}.csv"
       for a in ("min", "mid", "max") for kind in ("bom", "cpl")},
    "1_boards/most_listener_v2-bom.csv": "listener_hw2/fab/most_listener_v2-bom.csv",
    "1_boards/most_listener_v2-schematic.pdf": "listener_hw2/fab/most_listener_v2-schematic.pdf",
    "1_boards/most_listener_v2-assembly-top.pdf": "listener_hw2/fab/most_listener_v2-assembly-top.pdf",
    "1_boards/most_listener_v2-assembly-bottom.pdf": "listener_hw2/fab/most_listener_v2-assembly-bottom.pdf",
    **{f"1_boards/caps/{f}": f"listener_hw2/caps/{f}"
       for f in ("in_cap.stl", "in_cap.step", "out_cap.stl", "out_cap.step", "caps.svg")},
    "3_laptop/console_log.py": "tools/console_log.py",
    "3_laptop/console_format.py": "tools/console_format.py",
    "3_laptop/trace_decode.py": "tools/trace_decode.py",
    "3_laptop/capture_analyse.py": "tools/capture_analyse.py",
}
BY_HAND = [
    "README.md",
    "1_boards/README.md",
    "2_flash/README.md",
    "3_laptop/README.md", "3_laptop/requirements.txt",
    "3_laptop/record.bat", "3_laptop/decode.bat",
    "3_laptop/record.command", "3_laptop/decode.command",
]
TEXT = (".py", ".csv", ".md", ".txt", ".svg", ".step")
# what each build is made from: a difference here from the build's commit makes it stale
GATEWARE = ["listener_gw/rtl", "listener_gw/board/top_tangnano20k.v", "listener_gw/board/tangnano20k.cst",
            "listener_gw/board/tangnano20k.sdc", "listener_gw/board/build.tcl"]
FIRMWARE = ["listener_fw/main", "listener_fw/components", "listener_fw/CMakeLists.txt",
            "listener_fw/sdkconfig.defaults", "listener_fw/dependencies.lock"]
FS = KIT / "2_flash" / "fpga" / "listener.fs"
FS_INFO = KIT / "2_flash" / "fpga" / "BUILD.txt"
ESP = KIT / "2_flash" / "esp32"
ESP_INFO = ESP / "BUILD.txt"
ESP_FILES = {"bootloader.bin": "bootloader/bootloader.bin", "partition-table.bin": "partition_table/partition-table.bin",
             "listener_fw.bin": "listener_fw.bin"}
BUILDS = [FS, FS_INFO, ESP_INFO] + [ESP / f for f in ESP_FILES]


def git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def content(p: Path) -> bytes:
    b = p.read_bytes()
    return b.replace(b"\r\n", b"\n") if p.suffix in TEXT else b


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def changed(paths, since="HEAD") -> list[str]:
    """The files under paths that differ between the commit and the working tree, untracked ones too."""
    r = git("diff", "--name-only", since, "--", *paths)
    if r.returncode:
        return [f"git diff failed: {r.stderr.strip()}"]
    u = git("ls-files", "--others", "--exclude-standard", "--", *paths)
    return r.stdout.split() + u.stdout.split()


def newest(paths) -> float:
    files = [f for p in paths for f in ([ROOT / p] if (ROOT / p).is_file() else (ROOT / p).rglob("*")) if f.is_file()]
    return max(f.stat().st_mtime for f in files)


def last_commit(paths) -> str:
    return git("log", "-1", "--format=%H", "--", *paths).stdout.strip()


def info_of(path: Path) -> dict:
    """BUILD.txt's "key value" lines."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition(" ")
        if k and not k.startswith("#"):
            out.setdefault(k, v.strip())
    return out


def stale(what: str, info: dict, paths) -> list[str]:
    c = info.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", c):
        return [f"kit/2_flash/{what}/BUILD.txt: no commit line"]
    diff = changed(paths, c)
    if diff:
        return [f"kit/2_flash/{what} was built from {c[:7]}; its sources differ since: " + ", ".join(diff[:8])
                + (" ..." if len(diff) > 8 else "") + " (build, commit, python tools/make_kit.py --flash)"]
    return []


def check_fpga() -> list[str]:
    if not FS.exists() or not FS_INFO.exists():
        return ["kit/2_flash/fpga: no listener.fs or BUILD.txt (python tools/make_kit.py --flash after a clean build)"]
    info = info_of(FS_INFO)
    probs = [] if sha256(FS) == info.get("sha256") else ["kit/2_flash/fpga/listener.fs is not the file BUILD.txt describes"]
    return probs + stale("fpga", info, GATEWARE)


def check_esp32() -> list[str]:
    if not ESP_INFO.exists() or not all((ESP / f).exists() for f in ESP_FILES):
        return ["kit/2_flash/esp32: a .bin or BUILD.txt missing (python tools/make_kit.py --flash after a clean build)"]
    info = info_of(ESP_INFO)
    probs = [f"kit/2_flash/esp32/{f} is not the file BUILD.txt describes" for f in ESP_FILES
             if sha256(ESP / f) != info.get(f"sha256:{f}")]
    return probs + stale("esp32", info, FIRMWARE)


def take_fpga() -> None:
    fs = BOARD / "impl" / "pnr" / "listener.fs"
    if not fs.exists():
        sys.exit("no bitstream: python listener_gw/board/build.py first")
    diff = changed(GATEWARE)
    if diff:
        sys.exit("the gateware has uncommitted changes: " + ", ".join(diff[:8]) + " - commit, build, then --flash")
    if fs.stat().st_mtime < newest(GATEWARE):
        sys.exit("listener.fs is older than the gateware's sources: python listener_gw/board/build.py first")
    t = subprocess.run([sys.executable, str(BOARD / "check_timing.py")], cwd=BOARD, capture_output=True, text=True)
    if t.returncode:
        sys.exit("the build's timing check fails:\n" + t.stdout)
    # the .fs's own header: the part, the JTAG UserCode (Gowin Programmer's "Read User Code"), the
    # flash loading rate
    head = {}
    with open(fs, encoding="ascii", errors="replace") as f:
        for line in f:
            if not line.startswith("//"):
                break
            k, _, v = line[2:].partition(":")
            head[k.strip()] = v.strip()
    FS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fs, FS)
    commit = last_commit(GATEWARE)
    timing = [ln.strip() for ln in t.stdout.splitlines() if ln.strip()]
    FS_INFO.write_text(
        "listener.fs: the listener's FPGA bitstream, for the Tang Nano 20K's flash (../README.md)\n"
        f"device     {head.get('Part Number', '?')}\n"
        f"commit     {commit}\n"
        f"usercode   {head.get('UserCode', '?')}  (over JTAG: Gowin Programmer, Read User Code)\n"
        f"loading    {head.get('LoadingRate', '?')} from the flash\n"
        f"built      {datetime.fromtimestamp(fs.stat().st_mtime).strftime('%Y-%m-%d %H:%M')}\n"
        f"sha256     {sha256(FS)}\n"
        "timing     " + "\n           ".join(timing) + "\n",
        encoding="utf-8", newline="\n")
    print(f"kit/2_flash/fpga: listener.fs of {commit[:7]}, UserCode {head.get('UserCode', '?')}, "
          f"loading {head.get('LoadingRate', '?')}")


def app_desc(app: Path) -> dict:
    """The ESP-IDF image's esp_app_desc_t: the version (git describe when built), the project, the
    time, the IDF."""
    b = app.read_bytes()
    i = b.find(bytes.fromhex("3254cdab"))            # ESP_APP_DESC_MAGIC_WORD, little-endian
    if i < 0:
        sys.exit(f"{app}: no app description")
    s = lambda o, n: b[i + o:i + o + n].split(b"\0")[0].decode(errors="replace")   # noqa: E731
    return dict(version=s(16, 32), project=s(48, 32), time=s(80, 16), date=s(96, 16), idf=s(112, 32))


def take_esp32() -> None:
    build = FW / "build"
    args = build / "flasher_args.json"
    if not args.exists() or not all((build / s).exists() for s in ESP_FILES.values()):
        sys.exit("no firmware build: listener_fw/idf.ps1 build first")
    diff = changed(FIRMWARE)
    if diff:
        sys.exit("the firmware has uncommitted changes: " + ", ".join(diff[:8]) + " - commit, build, then --flash")
    if (build / "listener_fw.bin").stat().st_mtime < newest(FIRMWARE):
        sys.exit("listener_fw.bin is older than the firmware's sources: build again first")
    d = app_desc(build / "listener_fw.bin")
    if d["version"].endswith("-dirty"):
        sys.exit(f"the image says version {d['version']}: built with uncommitted changes in the repository "
                 "(ESP-IDF takes git describe at configure time); commit, idf.ps1 fullclean, build, then --flash")
    fa = json.loads(args.read_text(encoding="utf-8"))
    by_file = {v: k for k, v in fa["flash_files"].items()}
    ESP.mkdir(parents=True, exist_ok=True)
    lines = []
    for name, src in ESP_FILES.items():
        shutil.copyfile(build / src, ESP / name)
        lines.append(f"sha256:{name} {sha256(ESP / name)}")
    commit = last_commit(FIRMWARE)
    fs = fa["flash_settings"]
    ESP_INFO.write_text(
        "the host's firmware for M2 (ESP32-DevKitC-VIE): three images and where each goes (../README.md)\n"
        f"commit     {commit}\n"
        f"version    {d['version']}  (the console shows it at start: \"App version:\")\n"
        f"built      {d['date']} {d['time']}, ESP-IDF {d['idf']}\n"
        f"chip       {fa['extra_esptool_args']['chip']}, flash {fs['flash_mode']} {fs['flash_size']} {fs['flash_freq']}\n"
        + "".join(f"offset     {by_file[src]} {name}\n" for name, src in ESP_FILES.items())
        + "\n".join(lines) + "\n",
        encoding="utf-8", newline="\n")
    print(f"kit/2_flash/esp32: firmware of {commit[:7]}, version {d['version']}, ESP-IDF {d['idf']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="change nothing, fail on any difference")
    g.add_argument("--flash", action="store_true", help="also take the last builds' bitstream and firmware")
    a = ap.parse_args()

    probs = []
    for dst, src in COPIES.items():
        s, d = ROOT / src, KIT / dst
        if not s.exists():
            probs.append(f"{src}: missing")
            continue
        if d.exists() and content(d) == content(s):
            continue
        if a.check:
            probs.append(f"kit/{dst} differs from {src}")
        else:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(s, d)
            print(f"kit/{dst} <- {src}")
    if a.flash:
        take_fpga()
        take_esp32()
    probs += check_fpga() + check_esp32()
    probs += [f"kit/{p}: missing (written by hand)" for p in BY_HAND if not (KIT / p).exists()]
    known = set(COPIES) | set(BY_HAND) | {b.relative_to(KIT).as_posix() for b in BUILDS}
    probs += [f"kit/{p}: not a copy, a build or a file written by hand (left from an earlier kit?)"
              for p in sorted(f.relative_to(KIT).as_posix() for f in KIT.rglob("*") if f.is_file())
              if p not in known]
    # the macOS launchers are committed executable (git add --chmod=+x), or a clone cannot run them
    for p in ("3_laptop/record.command", "3_laptop/decode.command"):
        mode = git("ls-files", "-s", "--", f"kit/{p}").stdout.split()[:1]
        if mode and mode[0] != "100755":
            probs.append(f"kit/{p}: committed as {mode[0]}, not 100755 (git update-index --chmod=+x)")
    for p in probs:
        print("KIT: " + p)
    print("KIT: " + ("FAIL" if probs else f"kit/ matches its sources ({len(COPIES)} copies, the bitstream, "
                                          f"the firmware, {len(BY_HAND)} files by hand)"))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
