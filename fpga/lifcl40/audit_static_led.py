"""Offline checks of the clockless design, mapped pins, and packed I/O modes."""
import json
from pathlib import Path

root = Path('build/lifcl40/static_led')
synth = json.loads((root / 'synth.json').read_text())['modules']['static_led_top']
assert set(synth['ports']) == {'led0', 'led1'}
assert all(p['direction'] == 'output' for p in synth['ports'].values())
assert sorted(c['type'] for c in synth['cells'].values()) == ['OB', 'OB', 'VHI', 'VLO']
for port, source in [('led0', 'VLO'), ('led1', 'VHI')]:
    output = synth['cells'][port + '_OB_O']['connections']
    constant = next(c for c in synth['cells'].values() if c['type'] == source)
    assert output['I'] == constant['connections']['Z']
    assert output['O'] == synth['ports'][port]['bits']

routed = json.loads((root / 'routed.json').read_text())['modules']['top']
assert len(routed['cells']) == 3
pins = {}
for port, pin, bel in [('led0', 'E17', 'X87/Y3/PIOB'), ('led1', 'F13', 'X87/Y4/PIOA')]:
    cell = routed['cells'][port + '_OB_O']
    assert cell['type'] == 'SEIO33_CORE'
    assert cell['attributes']['LOC'] == pin
    assert cell['attributes']['NEXTPNR_BEL'] == bel
    assert cell['attributes']['IO_TYPE'] == 'LVCMOS33'
    assert cell['connections']['B'] == routed['ports'][port]['bits']
    assert cell['parameters']['TMUX'].strip() == '0'
    pins[port] = dict(pin=pin, bel=bel, io_standard='LVCMOS33')
zero = routed['cells']['led0_OB_O_I_VLO_Z']
assert zero['type'] == 'OXIDE_COMB' and int(zero['parameters']['INIT'], 2) == 0
assert zero['connections']['F'] == routed['cells']['led0_OB_O']['connections']['I']
assert routed['cells']['led1_OB_O']['parameters']['IMUX'].strip() == '1'
timing = json.loads((root / 'timing.json').read_text())
assert timing['fmax'] == {} and timing['critical_paths'] == []
assert {k:v['used'] for k,v in timing['utilization'].items() if v['used']} == {'OXIDE_COMB':1, 'SEIO33_CORE':2}
unpacked = (root / 'unpacked.fasm').read_text()
features = [
    'CIB_R3C87__SYSIO_B1_DED.PIOB.BASE_TYPE.OUTPUT_LVCMOS33',
    'CIB_R4C87__SYSIO_B1_0_ODD.PIOA.BASE_TYPE.OUTPUT_LVCMOS33',
    'CIB_R3C87__SYSIO_B1_DED.PIOB.TMUX.INV',
    'CIB_R4C87__SYSIO_B1_0_ODD.PIOA.TMUX.INV',
]
assert all(f in unpacked.splitlines() for f in features)
summary = dict(top='static_led_top', pins=pins, values={'led0':0,'led1':1},
               clock_expected=False, logic=1, registers=0, ebr=0, dsp=0,
               unpacked_io_features=features)
(root / 'audit.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
print('PASS: constant drivers, retained outputs, final pins, no clock, unpacked I/O modes')
