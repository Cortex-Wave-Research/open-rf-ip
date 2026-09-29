"""Confirm native clock constraint, final pins and retained counter resources."""
import json
from pathlib import Path
p = Path('build/lifcl40/native_clock_test')
s = json.loads((p/'synth.json').read_text())['modules']['native_clock_test_top']
assert set(s['ports']) == {'clk_12mhz', 'led0', 'led1'}
r = json.loads((p/'routed.json').read_text())['modules']['top']
pins = {}
for cell, pin in [('clk_12mhz_IB_I', 'L13'), ('led0_OB_O', 'E17'), ('led1_OB_O', 'F13')]:
    a = r['cells'][cell]['attributes']
    assert a['LOC'] == pin and a['IO_TYPE'] == 'LVCMOS33'
    pins[cell] = dict(pin=pin, bel=a['NEXTPNR_BEL'], io_standard=a['IO_TYPE'])
t = json.loads((p/'timing.json').read_text())
assert len(t['fmax']) == 1
clock, f = next(iter(t['fmax'].items()))
assert abs(f['constraint']-12) < 1e-6 and f['achieved'] > 12
u = {k:v['used'] for k,v in t['utilization'].items() if v['used']}
assert u == {'DCC':1, 'OXIDE_COMB':29, 'OXIDE_FF':24, 'SEIO33_CORE':3, 'VCC_DRV':1}
assert "constraining clock net 'clk_12mhz' to 12.00 MHz" in (p/'nextpnr.log').read_text()
out = dict(status='PREPARED; physical observation pending', pins=pins,
           recognized_clock=clock, requested_mhz=12, fmax_mhz=f['achieved'],
           worst_setup_slack_ns=1000/12-1000/f['achieved'], utilization=u,
           led0_hz=12000000/2**24, led1_hz=12000000/2**23)
(p/'analysis.json').write_text(json.dumps(out, indent=2)+'\n')
print(json.dumps(out, indent=2))
