"""Audit saved implementation artifacts; run with python -m fpga.lifcl40.analyze_impl.

Slack is derived from nextpnr's routed Fmax, not its pre-route estimate.
DP16K INITVAL packing follows Yosys nexus/brams_map.v:init_slice.
This is a structural/content audit, not post-route functional simulation.
"""
import json
from collections import Counter
from pathlib import Path

from models.python.nco_lut import sine_table

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/lifcl40"


def read(name):
    return json.loads((OUT / name).read_text())


def main():
    synth = read("nco-synth.json")["modules"]["nco_top"]
    roms = [c for c in synth["cells"].values() if c["type"] == "DP16K"]
    assert len(roms) == 1, "Expected one physical dual-port EBR, no duplication"
    rom = roms[0]
    params, ports = rom["parameters"], rom["connections"]
    assert params["DATA_WIDTH_A"] == params["DATA_WIDTH_B"] == "X18"
    assert ports["CLKA"] == ports["CLKB"]
    zero = next(c["connections"]["Z"] for c in synth["cells"].values()
                if c["type"] == "VLO")
    assert ports["WEA"] == ports["WEB"] == zero
    assert synth["netnames"]["q_sample"]["bits"] == ports["DOA"][:14]
    assert synth["netnames"]["i_sample"]["bits"] == ports["DOB"][:14]
    chunks = []
    for index in range(64):
        value = int(params[f"INITVAL_{index:02X}"], 16)
        chunks.extend((value >> (10 * j)) & 0x1ff for j in range(32))
    words = [chunks[2 * i] | (chunks[2 * i + 1] << 9) for i in range(1024)]
    expected = [sample & 0x3fff for sample in sine_table()]
    assert words == expected, "Physical EBR contents differ from independent model"

    runs = []
    for mhz in (12, 50, 100, 150, 200):
        report = read(f"timing-{mhz}.json")
        clock, timing = next(iter(report["fmax"].items()))
        assert len(report["fmax"]) == 1 and timing["constraint"] == mhz
        fmax = timing["achieved"]
        status = int((OUT / f"exit-{mhz}.txt").read_text())
        routed = read(f"routed-{mhz}.json")["modules"]["top"]
        counts = Counter(c["type"] for c in routed["cells"].values())
        assert counts["OXIDE_EBR"] == 1
        assert status == (0 if fmax >= mhz else 1)
        path = report["critical_paths"][0]["path"]
        runs.append({
            "target_mhz": mhz, "clock": clock, "fmax_mhz": fmax,
            "derived_setup_slack_ns": 1000 / mhz - 1000 / fmax,
            "timing_pass": fmax >= mhz, "exit_status": status,
            "routed_cells": dict(counts), "utilization": report["utilization"],
            "critical_path_source": path[1]["from"],
            "critical_path_sink": path[-1]["to"],
        })
    summary = {
        "physical_rom": "one DP16K, both ports X18, writes disabled",
        "rom_words_compared": 1024, "rom_mismatches": 0,
        "synthesis_cells": dict(Counter(c["type"] for c in synth["cells"].values())),
        "runs": runs,
    }
    (OUT / "analysis.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("ROM: one EBR, two read ports, 1024 physical words checked, zero mismatches")
    for r in runs:
        print(f'{r["target_mhz"]:3} MHz: Fmax={r["fmax_mhz"]:.3f} MHz, '
              f'slack={r["derived_setup_slack_ns"]:+.3f} ns, '
              f'{"PASS" if r["timing_pass"] else "FAIL"}, exit={r["exit_status"]}')


if __name__ == "__main__":
    main()
