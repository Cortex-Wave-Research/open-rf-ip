"""Offline lint, generic synthesis and LIFCL feasibility; never accesses hardware."""
import argparse
import collections
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.control_plane_sources import CONTROL, WAVE, WRAPPERS
OUT=ROOT/'reports/control_plane/implementation'

def run(cmd,where,name):
    (where/(name+'.command.json')).write_text(json.dumps(cmd)+'\n')
    with (where/(name+'.log')).open('w') as f:
        code=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT).returncode
    if code:raise RuntimeError(f'{name} failed ({code}): {where}')

def stat_cells(cells):
    types=collections.Counter(c['type'] for c in cells.values())
    flops=[c for c in cells.values() if 'dff' in c['type'].lower()]
    memories=[c for c in cells.values() if c['type']=='$mem_v2']
    def number(p):return int(p,2)
    return dict(cell_types=dict(types),total_cells=sum(types.values()),
        register_bits=sum(number(c['parameters']['WIDTH']) for c in flops),
        combinational_word_cells=sum(v for k,v in types.items() if 'dff' not in k.lower() and k not in ('$mem_v2','$scopeinfo')),
        memories=[dict(width=number(c['parameters']['WIDTH']),words=number(c['parameters']['SIZE'])) for c in memories],
        multipliers=types.get('$mul',0))

def generic(tops=None):
    result=json.loads((OUT/'generic.json').read_text()) if tops and (OUT/'generic.json').exists() else {}
    for top in tops or ('openrf_control','openrf_controlled_nco','openrf_controlled_chirp'):
        for hp in (0,1):
            d=OUT/f'generic-{top}-{hp}';d.mkdir(parents=True,exist_ok=True)
            sources=CONTROL if top=='openrf_control' else CONTROL+WAVE+WRAPPERS
            run(['verilator','--lint-only','--Wall','-Irtl/nco','--top-module',top,f'-GHIGH_PURITY={hp}',*sources],d,'lint')
            script=f'''read_verilog -defer -sv -Irtl/nco {' '.join(sources)}
chparam -set HIGH_PURITY {hp} {top}
hierarchy -check -top {top}
synth -top {top} -flatten -run begin:fine
check -assert
write_json {d}/netlist.json
stat
'''
            (d/'synth.ys').write_text(script);run(['yosys','-s',str(d/'synth.ys')],d,'yosys')
            cells=json.loads((d/'netlist.json').read_text())['modules'][top]['cells']
            r=stat_cells(cells);assert r['multipliers']==0
            assert len(r['memories'])==(0 if top=='openrf_control' else 1)
            result[f'{top}-{hp}']=r
            print('generic PASS',top,hp,flush=True)
    (OUT/'generic.json').write_text(json.dumps(result,indent=2)+'\n')

def target(kinds=None):
    result=json.loads((OUT/'target.json').read_text()) if kinds and (OUT/'target.json').exists() else {}
    for kind in kinds or (0,1):
        for hp in (0,1):
            top='control_plane_top';d=OUT/f'target-{hp}-{kind}';d.mkdir(parents=True,exist_ok=True)
            sources=CONTROL+WAVE+WRAPPERS+['fpga/lifcl40/control_plane/control_plane_top.sv']
            run(['verilator','--lint-only','--Wall','-Irtl/nco','--top-module',top,f'-GHIGH_PURITY={hp}',f'-GENGINE_KIND={kind}',*sources],d,'lint')
            script=f'''read_verilog -defer -sv -Irtl/nco {' '.join(sources)}
chparam -set HIGH_PURITY {hp} -set ENGINE_KIND {kind} {top}
hierarchy -check -top {top}
synth_nexus -family lifcl -top {top} -json {d}/synth.json
check -assert
stat
'''
            (d/'synth.ys').write_text(script);run(['yosys','-s',str(d/'synth.ys')],d,'yosys')
            run(['nextpnr-nexus','--device','LIFCL-40-9BG400C','--json',str(d/'synth.json'),
                 '--pdc','fpga/lifcl40/control_plane/control.pdc','--freq','100','--seed','1',
                 '--write',str(d/'routed.json'),'--fasm',str(d/'routed.fasm'),
                 '--report',str(d/'timing.json'),'--detailed-timing-report'],d,'nextpnr')
            timing=json.loads((d/'timing.json').read_text());f=next(iter(timing['fmax'].values()))
            u={k:v['used'] for k,v in timing['utilization'].items()}
            assert f['constraint']==100 and f['achieved']>=100
            assert u['OXIDE_EBR']==(16 if hp else 1)
            assert not any(v for k,v in u.items() if k.startswith('MULT'))
            run(['prjoxide','pack',str(d/'routed.fasm'),str(d/'feasibility.bit')],d,'pack')
            cells=json.loads((d/'routed.json').read_text())['modules']['top']['cells']
            attribution=collections.defaultdict(collections.Counter)
            for n,c in cells.items():
                if c['type'] in ('OXIDE_COMB','OXIDE_FF','OXIDE_EBR'):
                    group='harness'
                    if '.controlled.control.bus_adapter.' in n:group='wishbone'
                    elif '.controlled.control.csr.' in n:group='csr'
                    elif '.controlled.engine.' in n:group='waveform'
                    elif '.controlled.' in n:group='wrapper'
                    attribution[group][c['type']]+=1
            result[f'{hp}-{kind}']=dict(fmax_mhz=f['achieved'],slack_100_ns=10-1000/f['achieved'],
                slack_12_ns=1000/12-1000/f['achieved'],utilization=u,attribution=dict(attribution))
            (OUT/'target.json').write_text(json.dumps(result,indent=2)+'\n')
            print('target PASS',hp,kind,result[f'{hp}-{kind}'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--generic-only',action='store_true');p.add_argument('--target-only',action='store_true');a=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if not a.target_only:generic()
    if not a.generic_only:target()
