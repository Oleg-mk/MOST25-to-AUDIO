#!/usr/bin/env python3
"""check_all.py - every build and test of MOST25 to AUDIO, one at a time.

    python check_all.py            everything (~40 min)
    python check_all.py --quick    without run_dpll.py (the clock loop's long runs)
    python check_all.py --sweep    plus sweep_core.py --jobs 1 (32 random rings, ~1 h more)
    python check_all.py --strict   a step that could not run counts as failed (for a release)

Strictly sequential: never two simulations or builds at once. Each step
prints PASS or FAIL as its own tool returned it; the summary lists them and
the exit status is 1 if any failed. A step whose tool is missing is reported
as SKIPPED - read the word, it is not a pass; with --strict a SKIPPED step,
and the git steps left out for want of git, make the exit status 1 too.
A report a later step reads (the DRC's JSON) is deleted before the step that
writes it, so a step that did not run can never pass on an old report.

Tools (environment variables override the defaults):
  OSS_CAD    ~/toolchains/oss-cad-suite       iverilog, vvp (simulations)
  MINGW      ~/toolchains/mingw64             gcc, make (the firmware's host tests)
  KICAD_CLI  %LOCALAPPDATA%/Programs/KiCad/10.0/bin/kicad-cli.exe
  Gowin EDA: listener_gw/board/build.py; ESP-IDF: listener_fw/idf.ps1 (each finds its own)
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SIM = ROOT / "listener_gw" / "sim"
HOME = Path.home()
OSS = Path(os.environ.get("OSS_CAD", HOME / "toolchains" / "oss-cad-suite"))
MINGW = Path(os.environ.get("MINGW", HOME / "toolchains" / "mingw64"))
KICAD = Path(os.environ.get("KICAD_CLI", Path(os.environ.get("LOCALAPPDATA", "")) /
                            "Programs" / "KiCad" / "10.0" / "bin" / "kicad-cli.exe"))

results = []


def env_with(*dirs):
    e = dict(os.environ)
    e["PATH"] = os.pathsep.join([str(d) for d in dirs] + [e.get("PATH", "")])
    return e


def step(name, cmd, cwd, env=None, need=None):
    """Run one step to its end; PASS if it returned 0."""
    if need is not None and not Path(need).exists():
        print(f"\n=== {name}: SKIPPED ({need} not found)", flush=True)
        results.append((name, "SKIPPED", 0.0))
        return
    print(f"\n=== {name}", flush=True)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=cwd, env=env)
    dt = time.time() - t0
    verdict = "PASS" if r.returncode == 0 else "FAIL"
    print(f"=== {name}: {verdict} ({dt / 60:.1f} min)", flush=True)
    results.append((name, verdict, dt))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="leave out run_dpll.py")
    ap.add_argument("--sweep", action="store_true", help="add sweep_core.py --jobs 1")
    ap.add_argument("--strict", action="store_true", help="a step that cannot run is a failure")
    a = ap.parse_args()
    py = sys.executable
    sim_env = env_with(OSS / "bin", OSS / "lib")
    iverilog = OSS / "bin" / ("iverilog.exe" if os.name == "nt" else "iverilog")

    step("stimulus model: frames and line coding", [py, "-m", "virtual_most_source.tests.test_frames"], ROOT)
    step("capture analysis against known frames (tools/test_capture_analyse.py)",
         [py, str(ROOT / "tools" / "test_capture_analyse.py")], ROOT)
    step("receiver (run_rx.py)", [py, "run_rx.py"], SIM, sim_env, need=iverilog)
    step("J3 engine (run_dsp.py)", [py, "run_dsp.py"], SIM, sim_env, need=iverilog)
    step("S/PDIF output (run_spdif.py)", [py, "run_spdif.py"], SIM, sim_env, need=iverilog)
    sys.path.insert(0, str(SIM))
    import run_core                                            # corner names only
    for name, _, _ in run_core.CORNERS:
        step(f"whole core, corner {name} (run_core.py)", [py, "run_core.py", "--only", name], SIM, sim_env,
             need=iverilog)
    if not a.quick:
        step("clock loop (run_dpll.py)", [py, "run_dpll.py"], SIM, sim_env, need=iverilog)
    if a.sweep:
        step("random rings (sweep_core.py --jobs 1)", [py, "sweep_core.py", "--jobs", "1"], SIM, sim_env,
             need=iverilog)
    make = MINGW / "bin" / ("make.exe" if os.name == "nt" else "make")
    step("firmware host tests (make run)", [str(make), "CC=gcc", "run"], ROOT / "listener_fw" / "test",
         env_with(MINGW / "bin"), need=make)
    if os.name == "nt":
        step("firmware build (ESP-IDF)", ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                          str(ROOT / "listener_fw" / "idf.ps1"), "build"], ROOT / "listener_fw")
    step("FPGA build and timing (Gowin)", [py, "build.py"], ROOT / "listener_gw" / "board")
    hw = ROOT / "listener_hw"
    step("schematic: generate", [py, "gen_listener.py"], hw)
    step("schematic: ERC", [str(KICAD), "sch", "erc", "--exit-code-violations", "--output", "erc.rpt",
                            "most_listener.kicad_sch"], hw, need=KICAD)
    # the board (laid out once by gen_listener_pcb.py, then placed by hand and routed) is the
    # master, so only its DRC runs here: no error, nothing unconnected, no difference from the
    # sheet; the verdict is read from the JSON report
    (hw / "work").mkdir(exist_ok=True)
    (hw / "work" / "drc.json").unlink(missing_ok=True)      # this run's report or none
    step("board: DRC", [str(KICAD), "pcb", "drc", "--severity-error", "--schematic-parity", "--format", "json",
                        "--output", "work/drc.json", "most_listener.kicad_pcb"], hw, need=KICAD)
    step("board: DRC reports no error, nothing unconnected, and the board matches the sheet",
         [py, "-c", "import json, sys; d = json.load(open('work/drc.json', encoding='utf-8')); "
                    "p = d.get('schematic_parity', []); "
                    "print(len(d['violations']), 'errors,', len(p), 'differences from the sheet,', "
                    "len(d['unconnected_items']), 'unconnected'); "
                    "sys.exit(1 if d['violations'] or p or d['unconnected_items'] else 0)"], hw,
         need=hw / "work" / "drc.json")
    if not (shutil.which("git") and (ROOT / ".git").exists()):
        print("\n=== the generator's and fab/'s checks against the commit: SKIPPED (no git, or no .git)", flush=True)
        results.append(("schematic and fab against the commit", "SKIPPED", 0.0))
    else:
        # everything the schematic generator writes, not the sheet alone
        step("schematic: the generator reproduces the committed files",
             ["git", "diff", "--exit-code", "--stat", "--", "most_listener.kicad_sch", "most_listener.kicad_sym",
              "most_listener.pretty", "most_listener.3dshapes", "fp-lib-table", "sym-lib-table"], hw)
        # the manufacturing package is written from the board and the sheet; what goes to the
        # board house must be the committed package of this very board
        step("fab: the manufacturing package (make_fab.py)", [py, "make_fab.py"], hw, need=KICAD)
        step("fab: the package matches the commit",
             [py, "-c", "import subprocess, sys; "
                        "o = subprocess.run(['git', 'status', '--porcelain', '--', 'fab'], capture_output=True, "
                        "text=True).stdout; print(o or 'fab/ is the committed package'); sys.exit(1 if o.strip() else 0)"],
             hw)

    print("\n" + "=" * 60)
    for name, verdict, dt in results:
        print(f"{verdict:8s} {dt / 60:5.1f} min  {name}")
    bad = [r for r in results if r[1] == "FAIL"]
    skipped = [r for r in results if r[1] == "SKIPPED"]
    print(f"\n{len(results) - len(bad) - len(skipped)} passed, {len(bad)} failed, {len(skipped)} skipped"
          + (" - strict: a skipped step is a failure" if a.strict and skipped else ""))
    return 1 if bad or (a.strict and skipped) else 0


if __name__ == "__main__":
    sys.exit(main())
