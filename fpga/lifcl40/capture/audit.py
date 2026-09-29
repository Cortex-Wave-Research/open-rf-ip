"""Audit implementation, open-drain pad, and configuration ownership; no USB."""
import collections
import json
from pathlib import Path
p=Path('build/lifcl40/capture_readback')
s=json.loads((p/'synth.json').read_text())['modules']['capture_readback_top']
assert set(s['ports'])=={'clk_12mhz','scl','sda','led0','led1'}
r=json.loads((p/'routed.json').read_text())['modules']['top']['cells']
pins={}
for name,cell in r.items():
    if cell['type']=='SEIO33_CORE':
        a=cell['attributes']; assert a['IO_TYPE']=='LVCMOS33'
        pins[name]=a['LOC']
assert pins=={'transport.scl_IB_O':'F20','sda_BB_B':'E20','led0_OB_O':'E17','led1_OB_O':'F13','chirp.clk_IB_O':'L13'}
sda=r['sda_BB_B']; low_net=sda['connections']['I'][0]
assert sda['connections']['T'] and sda['connections']['O']
assert any(c['type']=='OXIDE_COMB' and c['connections'].get('F')==[low_net]
           and int(c['parameters']['INIT'],2)==0 for c in r.values())
fasm=(p/'unpacked.fasm').read_text()
assert 'CIB_R0C77__EFB_1_OSC.CONFIG_IP_CORE.MCPERSISTUI2C.DIS' in fasm
for forbidden in ['PERSISTI2C.EN','PERSISTI3C.EN','PERSISTSQUAD.EN',
                  'SLAVE_I2C_PORT.ENABLE','SLAVE_I3C_PORT.ENABLE','SLAVE_SPI_PORT.QUAD']:
    assert forbidden not in fasm
# DISABLE has an empty bit set in Oxide's database; absent EN is expected.
t=json.loads((p/'timing.json').read_text())
assert len(t['fmax'])==1
clock,f=next(iter(t['fmax'].items()))
assert f['constraint']==12 and f['achieved']>12
counts=collections.defaultdict(collections.Counter)
for name,cell in r.items():
    if cell['type'] in ('OXIDE_COMB','OXIDE_FF','OXIDE_EBR'):
        counts['production_chirp' if name.startswith('chirp.') else 'capture_transport_wrapper'][cell['type']]+=1
out=dict(pins=pins,clock=clock,fmax_mhz=f['achieved'],
         setup_slack_ns=1000/12-1000/f['achieved'],
         utilization={k:v['used'] for k,v in t['utilization'].items() if v['used']},
         name_attribution=dict(counts),
         note='Name-based attribution after optimization, not isolated-core synthesis. Timing excludes asynchronous external I2C path.')
(p/'analysis.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
