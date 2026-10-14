#!/usr/bin/env python3
"""Offline compact and high-purity LIFCL-40-9BG400C implementation preflight."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.synth_vexriscv_integration import sources

REPORT = ROOT / "reports/vexriscv_integration/lifcl40_preflight"
TOP = "vexriscv_preflight_top"
TARGET_MHZ = 12


def run(command, log, allow_timing_failure=False):
    with log.open("w") as output:
        result = subprocess.run(command, cwd=ROOT, stdout=output,
                                stderr=subprocess.STDOUT)
    if result.returncode and not allow_timing_failure:
        raise RuntimeError(f"Command failed ({result.returncode}): {command}; see {log}")
    return result.returncode


def profile(hp):
    kind = 1  # Chirp exercises the fuller sequencer in each precision profile.
    label = f"lifcl40-{['compact','high-purity'][hp]}"
    dest = REPORT / label
    dest.mkdir(parents=True, exist_ok=True)
    rtl_sources = sources(hp, kind) + ["verification/lifcl40/vexriscv_preflight_top.sv"]
    ys = dest / "synth.ys"
    netlist = dest / "synth.json"
    ys.write_text(
        "read_verilog -defer -sv -Irtl/nco " + " ".join(rtl_sources) + "\n"
        f"chparam -set HIGH_PURITY {hp} -set ENGINE_KIND {kind} {TOP}\n"
        f"hierarchy -check -top {TOP}\n"
        f"synth_nexus -family lifcl -top {TOP} -json {netlist}\n"
        "check -assert\nstat\n"
    )
    run(["yosys", "-Q", "-T", "-s", str(ys)], dest / "yosys.log")
    route_rc = run(["nextpnr-nexus", "--device", "LIFCL-40-9BG400C", "--json", str(netlist),
         "--pdc", "verification/lifcl40/vexriscv_preflight.pdc", "--freq", str(TARGET_MHZ),
         "--seed", "6201", "--threads", "1", "--write", str(dest / "routed.json"),
         "--fasm", str(dest / "routed.fasm"), "--report", str(dest / "timing.json"),
         "--detailed-timing-report"], dest / "nextpnr.log", allow_timing_failure=True)
    route_log = (dest / "nextpnr.log").read_text()
    timing_only_failure = route_rc != 0 and "ERROR: Max frequency for clock" in route_log
    if route_rc and not timing_only_failure:
        raise RuntimeError(f"LIFCL implementation failed beyond timing; inspect {dest / 'nextpnr.log'}")
    timing = json.loads((dest / "timing.json").read_text())
    fmax = next(iter(timing["fmax"].values()))
    passed = route_rc == 0 and fmax["achieved"] >= fmax["constraint"]
    result = {"result": "PASS" if passed else "FAIL_TIMING",
              "route_completed": True,
              "profile": "high-purity" if hp else "compact",
              "engine_kind": "chirp", "device": "LIFCL-40-9BG400C",
              "frequency_mhz": TARGET_MHZ, "achieved_mhz": fmax["achieved"],
              "utilization": {key: value["used"]
                              for key, value in timing["utilization"].items()},
              "artifacts": str(dest.relative_to(ROOT))}
    (dest / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    results = []
    for hp in (0, 1):
        print(f"LIFCL-40 {['compact','high-purity'][hp]} preflight: running", flush=True)
        results.append(profile(hp))
        (REPORT / "results.json").write_text(json.dumps(
            {"result": "RUNNING", "profiles": results}, indent=2) + "\n")
        print(f"LIFCL-40 {['compact','high-purity'][hp]} preflight: {results[-1]['result']}", flush=True)
    outcome = "PASS" if all(row["result"] == "PASS" for row in results) else "FAIL_TIMING"
    (REPORT / "results.json").write_text(json.dumps(
        {"result": outcome, "profiles": results}, indent=2) + "\n")
    return 0 if outcome == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
