#!/usr/bin/env python3
"""Generic Yosys synthesis of the four frozen-profile CPU demonstrations."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPORT = ROOT / "reports/vexriscv_integration"


def sources(hp, kind):
    selected_engine = (["rtl/nco/rf_nco.sv", "rtl/chirp/chirp_controller.sv",
                        "rtl/chirp/rf_chirp_nco.sv", "rtl/chirp/rf_chirp_nco_mode.sv"] if kind else
                       ["rtl/nco/rf_nco.sv", "rtl/nco/rf_nco_mode.sv"])
    if hp:
        selected_engine += ["rtl/nco/rf_nco_high_purity.sv"]
    selected_wrapper = ("rtl/control/openrf_controlled_chirp.sv" if kind else
                        "rtl/control/openrf_controlled_nco.sv")
    return [
        "rtl/control/openrf_control_pkg.sv", "rtl/control/openrf_wb_slave.sv",
        "rtl/control/openrf_csr_core.sv", "rtl/control/openrf_control.sv",
        *selected_engine, selected_wrapper,
        "rtl/cpu/openrf_dbus_wishbone.sv", "rtl/cpu/openrf_cpu_memory.sv",
        "rtl/cpu/openrf_vexriscv_system.sv", "third_party/vexriscv/VexRiscv.v",
    ]


def synthesize(hp, kind):
    label = f"synth-{hp}-{kind}"
    script = REPORT / f"{label}.ys"
    netlist = ROOT / "build/vexriscv" / f"{label}.json"
    script.write_text(
        "read_verilog -sv -Irtl/nco " + " ".join(sources(hp, kind)) + "\n"
        f"chparam -set HIGH_PURITY {hp} -set ENGINE_KIND {kind} openrf_vexriscv_system\n"
        "hierarchy -check -top openrf_vexriscv_system\n"
        "synth -top openrf_vexriscv_system -flatten\n"
        "check -assert\n"
        "stat\n"
        f"write_json {netlist}\n"
    )
    log = REPORT / f"{label}.log"
    with log.open("w") as output:
        run = subprocess.run(["yosys", "-Q", "-T", "-s", str(script)], cwd=ROOT,
                             stdout=output, stderr=subprocess.STDOUT)
    contents = log.read_text()
    if run.returncode or "Found and reported 0 problems" not in contents:
        raise RuntimeError(f"Generic synthesis failed for profile {hp}/{kind}; inspect {log}")
    match = re.search(r"Number of cells:\s+(\d+)", contents)
    result = {"profile": hp, "engine_kind": kind, "result": "PASS",
              "generic_cell_count": int(match.group(1)) if match else None,
              "netlist": str(netlist.relative_to(ROOT)), "log": str(log.relative_to(ROOT))}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hp", type=int, choices=(0, 1))
    parser.add_argument("--kind", type=int, choices=(0, 1))
    parser.add_argument("--collect", action="store_true",
                        help="summarize the four already completed per-profile synthesis logs")
    args = parser.parse_args()
    REPORT.mkdir(parents=True, exist_ok=True)
    if args.collect:
        results = []
        for hp in (0, 1):
            for kind in (0, 1):
                label = f"synth-{hp}-{kind}"
                log = REPORT / f"{label}.log"
                netlist = ROOT / "build/vexriscv" / f"{label}.json"
                text = log.read_text()
                if "Found and reported 0 problems" not in text or not netlist.is_file():
                    raise RuntimeError(f"Missing clean synthesis evidence for {hp}/{kind}")
                match = re.search(r"Number of cells:\s+(\d+)", text)
                results.append({"profile": hp, "engine_kind": kind, "result": "PASS",
                                "generic_cell_count": int(match.group(1)) if match else None,
                                "netlist": str(netlist.relative_to(ROOT)),
                                "log": str(log.relative_to(ROOT))})
        (REPORT / "synthesis_results.json").write_text(json.dumps(
            {"result": "PASS", "tool": subprocess.check_output(
                ["yosys", "-V"], text=True).strip(), "profiles": results}, indent=2) + "\n")
        return 0
    profiles = [(args.hp, args.kind)] if args.hp is not None and args.kind is not None else [
        (hp, kind) for hp in (0, 1) for kind in (0, 1)]
    results = []
    for hp, kind in profiles:
        print(f"CPU GENERIC SYNTH {hp}/{kind}: running", flush=True)
        results.append(synthesize(hp, kind))
        (REPORT / "synthesis_results.json").write_text(json.dumps(
            {"result": "RUNNING", "profiles": results}, indent=2) + "\n")
        print(f"CPU GENERIC SYNTH {hp}/{kind}: PASS", flush=True)
    outcome = {"result": "PASS", "tool": subprocess.check_output(
        ["yosys", "-V"], text=True).strip(), "profiles": results}
    (REPORT / "synthesis_results.json").write_text(json.dumps(outcome, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
