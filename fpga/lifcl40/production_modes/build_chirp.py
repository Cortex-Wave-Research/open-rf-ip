"""Equivalent complete chirp harnesses at 100 MHz, offline synthesis/P&R/pack."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from fpga.lifcl40.production_modes.build import run,OUT,SOURCES

def main():
    result={}
    for hp in (0,1):
        d=OUT/f'target-chirp-{hp}';d.mkdir(parents=True,exist_ok=True)
        source='fpga/lifcl40/production_modes/chirp_mode_top.sv'
        run(['verilator','--lint-only','--Wall','-Irtl/nco','--top-module','chirp_mode_top',f'-GHIGH_PURITY={hp}',*SOURCES.split(),source],d/'lint.log')
        script=f'''read_verilog -defer -sv -Irtl/nco {SOURCES} {source}
chparam -set HIGH_PURITY {hp} chirp_mode_top
hierarchy -check -top chirp_mode_top
synth_nexus -family lifcl -top chirp_mode_top -json {d}/synth.json
check -assert
tee -o {d}/stat.txt stat
'''
        (d/'synth.ys').write_text(script)
        run(['yosys','-l',str(d/'yosys.log'),str(d/'synth.ys')],d/'console.log')
        run(['nextpnr-nexus','--device','LIFCL-40-9BG400C','--json',str(d/'synth.json'),
             '--pdc','fpga/lifcl40/nco.pdc','--freq','100','--seed','1','--write',str(d/'routed.json'),
             '--fasm',str(d/'routed.fasm'),'--report',str(d/'timing.json'),'--detailed-timing-report','--log',str(d/'nextpnr.log')],d/'route.log')
        run(['prjoxide','pack',str(d/'routed.fasm'),str(d/'harness.bit')],d/'pack.log')
        r=json.loads((d/'timing.json').read_text());f=next(iter(r['fmax'].values()))['achieved']
        result[str(hp)]=dict(fmax_mhz=f,slack_ns=10-1000/f,utilization={k:v['used'] for k,v in r['utilization'].items()})
        (OUT/'chirp_implementation.json').write_text(json.dumps(result,indent=2)+'\n')
        print(hp,result[str(hp)],flush=True)

if __name__=='__main__':main()
