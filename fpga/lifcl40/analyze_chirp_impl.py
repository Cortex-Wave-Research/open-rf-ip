"""Audit target ROM and extract routed timing/resources versus Milestone 2.5.
Run from root: .venv/bin/python -m fpga.lifcl40.analyze_chirp_impl
"""
import json
from collections import Counter
from pathlib import Path
from models.python.nco_lut import sine_table

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/chirp'


def main():
    synth = json.loads((OUT / 'lifcl40-synth.json').read_text())['modules']['chirp_top']
    roms = [c for c in synth['cells'].values() if c['type'] == 'DP16K']
    assert len(roms) == 1
    p, ports = roms[0]['parameters'], roms[0]['connections']
    assert p['DATA_WIDTH_A'] == p['DATA_WIDTH_B'] == 'X18'
    zero = next(c['connections']['Z'] for c in synth['cells'].values() if c['type'] == 'VLO')
    assert ports['WEA'] == ports['WEB'] == zero
    assert ports['CLKA'] == ports['CLKB']
    chunks = []
    for i in range(64):
        value = int(p[f'INITVAL_{i:02X}'], 16)
        chunks.extend((value >> (10*j)) & 511 for j in range(32))
    assert [chunks[2*i] | (chunks[2*i+1] << 9) for i in range(1024)] == [x & 16383 for x in sine_table()]
    assert synth['netnames']['q_sample']['bits'] == ports['DOA'][:14]
    assert synth['netnames']['i_sample']['bits'] == ports['DOB'][:14]
    baseline = json.loads((ROOT / 'reports/lifcl40/timing-12.json').read_text())
    runs = []
    for mhz in (12,50,100,150,200):
        report = json.loads((OUT / f'timing-{mhz}.json').read_text())
        clock, timing = next(iter(report['fmax'].items()))
        assert len(report['fmax']) == 1 and timing['constraint'] == mhz
        log = (ROOT / f'reports/logs/m3-nextpnr-{mhz}.log').read_text()
        assert 'overused=0 overuse=0 archfail=0' in log
        exit_code = int((OUT / f'exit-{mhz}.txt').read_text())
        fmax = timing['achieved']
        assert exit_code == (0 if fmax >= mhz else 1)
        assert report['utilization']['OXIDE_EBR']['used'] == 1
        path = report['critical_paths'][0]['path']
        runs.append(dict(target_mhz=mhz, fmax_mhz=fmax,
                         worst_setup_slack_ns=1000/mhz-1000/fmax,
                         exit_code=exit_code, placement_routing='PASS',
                         timing='PASS' if fmax >= mhz else 'FAIL',
                         critical_path=path, utilization=report['utilization']))
    generic = json.loads((OUT / 'generic.json').read_text())['modules']
    coarse = json.loads((OUT / 'generic-coarse.json').read_text())['modules']
    controller = coarse['chirp_controller']['cells']
    arithmetic = {n: {'type': c['type'], 'y_width': len(c['connections']['Y'])}
                  for n,c in controller.items() if c['type'] in ('$add','$sub')}
    registers = {n: len(c['connections']['Q']) for n,c in controller.items()
                 if c['type'] in ('$dff','$dffe','$sdff','$sdffe')}
    summary = dict(rom_words_compared=1024, rom_mismatches=0,
                   synthesis_cells=dict(Counter(c['type'] for c in synth['cells'].values())),
                   controller_generic_cells=len(generic['chirp_controller']['cells']),
                   controller_register_bits=sum(registers.values()),
                   controller_arithmetic=arithmetic,
                   resource_delta={k: v['used']-baseline['utilization'][k]['used']
                                   for k,v in runs[0]['utilization'].items()}, runs=runs)
    (OUT / 'implementation_analysis.json').write_text(json.dumps(summary, indent=2)+'\n')
    print('ROM audit: 1 dual-port EBR, 1024 words, zero mismatches')
    print('Controller generic cells:', summary['controller_generic_cells'],
          'register bits:', summary['controller_register_bits'])
    print('Nonzero target resource deltas:', {k:v for k,v in summary['resource_delta'].items() if v})
    for row in runs:
        print(f'{row["target_mhz"]} MHz: route PASS; timing {row["timing"]}; '
              f'Fmax {row["fmax_mhz"]:.6f} MHz; slack {row["worst_setup_slack_ns"]:+.6f} ns')


if __name__ == '__main__':
    main()
