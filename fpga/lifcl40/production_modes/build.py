"""M5 generic synthesis and equivalent LIFCL-40 NCO harnesses. No hardware access."""
import collections,json,subprocess
from pathlib import Path
OUT=Path('reports/high_purity_integration')
SOURCES='rtl/nco/rf_nco.sv rtl/nco/rf_nco_high_purity.sv rtl/nco/rf_nco_mode.sv rtl/chirp/chirp_controller.sv rtl/chirp/rf_chirp_nco.sv rtl/chirp/rf_chirp_nco_mode.sv'

def run(cmd,log,allow_failure=False):
    with log.open('w') as f:
        r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
    if r.returncode and not allow_failure:
        raise RuntimeError(f'{cmd[0]} failed ({r.returncode}): {log}')
    return r.returncode


def generic():
    result={}
    for top in ('rf_nco_mode','rf_chirp_nco_mode'):
        for hp in (0,1):
            d=OUT/f'generic-{top}-{hp}';d.mkdir(parents=True,exist_ok=True)
            run(['verilator','--lint-only','--Wall','-Irtl/nco','--top-module',top,f'-GHIGH_PURITY={hp}',*SOURCES.split()],d/'lint.log')
            # Keep ROMs in portable memory form, identically for all four designs.
            script=f'''read_verilog -defer -sv -Irtl/nco {SOURCES}
chparam -set HIGH_PURITY {hp} {top}
hierarchy -check -top {top}
synth -top {top} -flatten -run begin:fine
check -assert
tee -o {d}/stat.txt stat
write_json {d}/netlist.json
'''
            (d/'synth.ys').write_text(script)
            run(['yosys','-l',str(d/'yosys.log'),str(d/'synth.ys')],d/'console.log')
            cells=json.loads((d/'netlist.json').read_text())['modules'][top]['cells']
            counts=dict(collections.Counter(c['type'] for c in cells.values()))
            memories=[]
            for name,c in cells.items():
                if c['type']=='$mem_v2':
                    p=c['parameters'];memories.append(dict(name=name,**{k:int(p[k],2) for k in ('WIDTH','SIZE','RD_PORTS','WR_PORTS')}))
            assert len(memories)==1 and memories[0]['WR_PORTS']==0 and memories[0]['RD_PORTS']==2
            assert memories[0]['SIZE']==(16384 if hp else 1024)
            assert memories[0]['WIDTH']==(17 if hp else 14)
            result[f'{top}-{hp}']=dict(cells=counts,total_cells=sum(counts.values()),memories=memories)
            (OUT/'generic.json').write_text(json.dumps(result,indent=2)+'\n')
            print('generic',top,hp,'PASS',flush=True)


def target():
    results={}
    for hp in (0,1):
        d=OUT/f'target-{hp}';d.mkdir(parents=True,exist_ok=True)
        script=f'''read_verilog -defer -sv -Irtl/nco {SOURCES} fpga/lifcl40/production_modes/mode_top.sv
chparam -set HIGH_PURITY {hp} mode_top
hierarchy -check -top mode_top
synth_nexus -family lifcl -top mode_top -json {d}/synth.json
check -assert
tee -o {d}/stat.txt stat
'''
        (d/'synth.ys').write_text(script)
        run(['verilator','--lint-only','--Wall','-Irtl/nco','--top-module','mode_top',f'-GHIGH_PURITY={hp}',*SOURCES.split(),'fpga/lifcl40/production_modes/mode_top.sv'],d/'lint.log')
        run(['yosys','-l',str(d/'yosys.log'),str(d/'synth.ys')],d/'console.log')
        sweeps={}
        for freq in ((100,) if not hp else (12,50,100,125,150)):
            r=d/str(freq);r.mkdir(exist_ok=True)
            code=run(['nextpnr-nexus','--device','LIFCL-40-9BG400C','--json',str(d/'synth.json'),
                '--pdc','fpga/lifcl40/nco.pdc','--freq',str(freq),'--seed','1','--write',str(r/'routed.json'),
                '--fasm',str(r/'routed.fasm'),'--report',str(r/'timing.json'),'--detailed-timing-report','--log',str(r/'nextpnr.log')],r/'console.log',True)
            report=json.loads((r/'timing.json').read_text());f=next(iter(report['fmax'].values()))
            sweeps[str(freq)]=dict(exit_code=code,fmax_mhz=f['achieved'],slack_ns=1000/freq-1000/f['achieved'],
                                  utilization={k:v['used'] for k,v in report['utilization'].items()})
            if freq<=100 and code: raise RuntimeError(f'{hp} mode fails required {freq} MHz')
            if code and sweeps[str(freq)]['slack_ns']>=0: raise RuntimeError('non-timing route failure')
            # Offline pack every routed frequency artifact, never program.
            run(['prjoxide','pack',str(r/'routed.fasm'),str(r/'harness.bit')],r/'pack.log')
            print('target',hp,freq,sweeps[str(freq)],flush=True)
        results[str(hp)]=sweeps
        (OUT/'implementation.json').write_text(json.dumps(results,indent=2)+'\n')

if __name__=='__main__':
    generic();target()
