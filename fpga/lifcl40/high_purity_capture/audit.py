"""Offline pad/configuration/timing/resource audit of prepared RFC2 image."""
import json,collections,hashlib
from pathlib import Path
p=Path('build/lifcl40/high_purity_capture')
s=json.loads((p/'synth.json').read_text())['modules']['high_purity_capture_top']
assert set(s['ports'])=={'clk_12mhz','scl','sda','led0','led1'}
r=json.loads((p/'routed.json').read_text())['modules']['top']['cells']
pins={n:c['attributes']['LOC'] for n,c in r.items() if c['type']=='SEIO33_CORE'}
assert set(pins.values())=={'L13','F20','E20','E17','F13'}
for n,c in r.items():
    if c['type']=='SEIO33_CORE':assert c['attributes']['IO_TYPE']=='LVCMOS33'
assert pins['led0_OB_O']=='E17' and pins['led1_OB_O']=='F13'
sda=next(c for c in r.values() if c['type']=='SEIO33_CORE' and c['attributes']['LOC']=='E20')
assert sda['connections']['O'] and sda['connections']['T']
low=sda['connections']['I']
assert any(c['type']=='OXIDE_COMB' and c['connections'].get('F')==low and int(c['parameters']['INIT'],2)==0 for c in r.values())
fasm=(p/'unpacked.fasm').read_text()
assert 'CIB_R0C77__EFB_1_OSC.CONFIG_IP_CORE.MCPERSISTUI2C.DIS' in fasm
for forbidden in ['PERSISTI2C.EN','PERSISTI3C.EN','PERSISTSQUAD.EN','SLAVE_I2C_PORT.ENABLE','SLAVE_I3C_PORT.ENABLE','SLAVE_SPI_PORT.QUAD']:
    assert forbidden not in fasm
report=json.loads((p/'timing.json').read_text());clock,timing=next(iter(report['fmax'].items()))
assert timing['constraint']==12 and timing['achieved']>12
u={k:v['used'] for k,v in report['utilization'].items()}
assert u['OXIDE_EBR']==19 and not any(v for k,v in u.items() if k.startswith('MULT'))
counts=collections.defaultdict(collections.Counter)
for name,c in r.items():
    if c['type'] in ('OXIDE_COMB','OXIDE_FF','OXIDE_EBR'):
        counts['production_chirp' if name.startswith('chirp.') else 'capture_transport_wrapper'][c['type']]+=1
assert counts['capture_transport_wrapper']['OXIDE_EBR']==3
assert counts['production_chirp']['OXIDE_EBR']==16
bit=Path('build/lifcl40/high_purity_capture.bit')
result=dict(pins=pins,clock=clock,fmax_mhz=timing['achieved'],slack_ns=1000/12-1000/timing['achieved'],
            utilization=u,name_attribution=dict(counts),sha256=hashlib.sha256(bit.read_bytes()).hexdigest(),
            physical_programming='NOT PERFORMED',capture_format='RFC2',records=1024,ram_bits=39936,record_wire_bits=40)
(p/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
