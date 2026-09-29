"""Check both constant configurations and physical output mappings offline."""
import hashlib
import json
from pathlib import Path

root = Path('build/lifcl40/led_ab')
results = {}
for variant, values in [('A', (0, 1)), ('B', (1, 0))]:
    p = root / variant
    synth = json.loads((p / 'synth.json').read_text())['modules']['led_ab_top']
    assert set(synth['ports']) == {'led0', 'led1'}
    assert sorted(c['type'] for c in synth['cells'].values()) == ['OB', 'OB', 'VHI', 'VLO']
    routed = json.loads((p / 'routed.json').read_text())['modules']['top']
    assert len(routed['cells']) == 3
    pins = {}
    for index, (pin, bel) in enumerate([('E17', 'X87/Y3/PIOB'), ('F13', 'X87/Y4/PIOA')]):
        name = f'led{index}'
        assert synth['ports'][name]['direction'] == 'output'
        ob = synth['cells'][name + '_OB_O']['connections']
        driver = next(c for c in synth['cells'].values() if c['type'] == ('VHI' if values[index] else 'VLO'))
        assert ob['I'] == driver['connections']['Z']
        assert ob['O'] == synth['ports'][name]['bits']
        cell = routed['cells'][name + '_OB_O']
        assert cell['type'] == 'SEIO33_CORE'
        assert cell['attributes']['LOC'] == pin
        assert cell['attributes']['NEXTPNR_BEL'] == bel
        assert cell['attributes']['IO_TYPE'] == 'LVCMOS33'
        assert cell['connections']['B'] == routed['ports'][name]['bits']
        assert cell['parameters']['TMUX'].strip() == '0'
        if values[index]:
            assert cell['parameters']['IMUX'].strip() == '1'
        else:
            zero = next(c for c in routed['cells'].values() if c['type'] == 'OXIDE_COMB')
            assert int(zero['parameters']['INIT'], 2) == 0
            assert zero['connections']['F'] == cell['connections']['I']
        pins[name] = dict(pin=pin, bel=bel, value=values[index])
    timing = json.loads((p / 'timing.json').read_text())
    assert timing['fmax'] == {} and timing['critical_paths'] == []
    assert {k:v['used'] for k,v in timing['utilization'].items() if v['used']} == {'OXIDE_COMB':1, 'SEIO33_CORE':2}
    unpacked = (p / 'unpacked.fasm').read_text()
    for feature in ['CIB_R3C87__SYSIO_B1_DED.PIOB.BASE_TYPE.OUTPUT_LVCMOS33',
                    'CIB_R4C87__SYSIO_B1_0_ODD.PIOA.BASE_TYPE.OUTPUT_LVCMOS33']:
        assert feature in unpacked.splitlines()
    bit = Path(f'build/lifcl40/led_ab_{variant}.bit')
    results[variant] = dict(bitstream=str(bit), sha256=hashlib.sha256(bit.read_bytes()).hexdigest(), pins=pins)
a = Path(results['A']['bitstream']).read_bytes()
b = Path(results['B']['bitstream']).read_bytes()
assert a != b, 'A and B must differ'
results['identical'] = False
results['differing_bytes'] = sum(x != y for x,y in zip(a,b)) + abs(len(a)-len(b))
(root / 'audit.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
print('PASS: opposite constants, preserved outputs, exact pins, no clock, distinct images')
