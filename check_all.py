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
  KICAD_PY   KiCad's python, with pcbnew (v2.0's tube and caps), default beside kicad-cli
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
KIPY = Path(os.environ.get("KICAD_PY", KICAD.with_name("python.exe")))

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
    step("recorder: the console's formats against host.c, port, keys, alarms (tools/test_console_log.py)",
         [py, str(ROOT / "tools" / "test_console_log.py")], ROOT)
    step("a made-up recording decoded (tools/test_trace_decode.py)",
         [py, str(ROOT / "tools" / "test_trace_decode.py")], ROOT)
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
    hw, hw2 = ROOT / "listener_hw", ROOT / "listener_hw2"
    # each board (laid out once by its script, then placed by hand and routed) is the master, so
    # only its DRC runs here: no error, nothing unconnected, no difference from the sheet; the
    # verdict is read from the JSON report
    drc_ok = [py, "-c", "import json, sys; d = json.load(open('work/drc.json', encoding='utf-8')); "
                        "p = d.get('schematic_parity', []); "
                        "print(len(d['violations']), 'errors,', len(p), 'differences from the sheet,', "
                        "len(d['unconnected_items']), 'unconnected'); "
                        "sys.exit(1 if d['violations'] or p or d['unconnected_items'] else 0)"]

    def drc(pcb):
        return [str(KICAD), "pcb", "drc", "--severity-error", "--schematic-parity", "--format", "json",
                "--output", "work/drc.json", pcb]

    def committed(path, what):
        """Fails while git shows a change under path (relative to the step's folder)."""
        return [py, "-c", "import subprocess, sys; "
                          f"o = subprocess.run(['git', 'status', '--porcelain', '--', '{path}'], capture_output=True, "
                          f"text=True).stdout; print(o or '{what}'); sys.exit(1 if o.strip() else 0)"]

    step("v1.6 schematic: generate", [py, "gen_listener.py"], hw)
    step("v1.6 schematic: ERC", [str(KICAD), "sch", "erc", "--exit-code-violations", "--output", "erc.rpt",
                                 "most_listener.kicad_sch"], hw, need=KICAD)
    (hw / "work").mkdir(exist_ok=True)
    (hw / "work" / "drc.json").unlink(missing_ok=True)      # this run's report or none
    step("v1.6 board: DRC", drc("most_listener.kicad_pcb"), hw, need=KICAD)
    step("v1.6 board: DRC reports no error, nothing unconnected, and the board matches the sheet", drc_ok, hw,
         need=hw / "work" / "drc.json")
    # v2.0: v1.6's circuit on a board for an 80 x 30 x 2 tube, with its end caps (listener_hw2)
    step("v2.0 schematic: generate (gen_listener2.py)", [py, "gen_listener2.py"], hw2)
    step("v2.0 schematic: v1.6's circuit, part for part and net for net (tools/check_v2_circuit.py)",
         [py, str(ROOT / "tools" / "check_v2_circuit.py")], ROOT, need=KICAD)
    (hw2 / "work").mkdir(exist_ok=True)
    step("v2.0 schematic: ERC", [str(KICAD), "sch", "erc", "--exit-code-violations", "--output", "work/erc.rpt",
                                 "most_listener_v2.kicad_sch"], hw2, need=KICAD)
    (hw2 / "work" / "drc.json").unlink(missing_ok=True)
    step("v2.0 board: DRC", drc("most_listener_v2.kicad_pcb"), hw2, need=KICAD)
    step("v2.0 board: DRC reports no error, nothing unconnected, and the board matches the sheet", drc_ok, hw2,
         need=hw2 / "work" / "drc.json")
    step("v2.0 tube: the board in the tube, its leads, the caps' cut-outs (check_fit.py)",
         [str(KIPY), "check_fit.py"], hw2, need=KIPY)
    step("v2.0 caps: the tube's end caps from check_fit's model (gen_caps.py)", [str(KIPY), "gen_caps.py"], hw2,
         need=KIPY)
    if not (shutil.which("git") and (ROOT / ".git").exists()):
        print("\n=== the generators', fab/'s, caps/' and kit's checks against the commit: SKIPPED (no git, or no .git)",
              flush=True)
        results.append(("schematics, fab, caps and kit against the commit", "SKIPPED", 0.0))
    else:
        # everything a schematic generator writes, not the sheet alone
        lib = ["most_listener.kicad_sym", "most_listener.pretty", "most_listener.3dshapes", "fp-lib-table",
               "sym-lib-table"]
        step("v1.6 schematic: the generator reproduces the committed files",
             ["git", "diff", "--exit-code", "--stat", "--", "most_listener.kicad_sch", *lib], hw)
        step("v2.0 schematic: the generator reproduces the committed files",
             ["git", "diff", "--exit-code", "--stat", "--", "most_listener_v2.kicad_sch", *lib], hw2)
        # each manufacturing package is written from its board and sheet; what goes to the board
        # house must be the committed package of this very board, and the caps those of this board
        step("v1.6 fab: the manufacturing package (make_fab.py)", [py, "make_fab.py"], hw, need=KICAD)
        step("v1.6 fab: the package matches the commit", committed("fab", "fab/ is the committed package"), hw)
        step("v2.0 fab: the manufacturing package, three assemblies (make_fab2.py)", [py, "make_fab2.py"], hw2,
             need=KICAD)
        step("v2.0 fab: the package matches the commit", committed("fab", "fab/ is the committed package"), hw2)
        step("v2.0 caps: the caps match the commit", committed("caps", "caps/ is the committed set"), hw2)
        # kit/ hands over copies of fab/, of the builds and of the laptop's programs: each equal to its
        # source, and no build older than its committed sources
        step("kit: the copies and the builds match their sources (tools/make_kit.py --check)",
             [py, str(ROOT / "tools" / "make_kit.py"), "--check"], ROOT)

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
