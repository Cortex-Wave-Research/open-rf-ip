"""Final offline source, ROM, physical banking, exact-result and artifact checks."""
import hashlib,json,struct,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from models.python.high_purity import quarter_table
from models.python.nco_lut import sine_table
OUT=ROOT/'reports/high_purity_integration'

def main():
    manifest=json.loads((ROOT/'reports/high_purity_physical_verification/evidence_manifest.json').read_text())
    baseline='71691d62aa119ca9bd8ddc7cbf01222e80a7b4a0'
    paths=['rtl/chirp/chirp_controller.sv','rtl/chirp/rf_chirp_nco.sv','rtl/nco/rf_nco.sv','rtl/nco/sine_lut_12b.svh','models/python/chirp.py','models/python/nco.py','models/python/nco_lut.py']
    paths += ['fpga/lifcl40/capture/'+name for name in ('capture_i2c.sv','capture_store.sv','capture_readback_top.sv','sim_top.sv','read_capture.py')]
    for name, info in manifest['evidence'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==info['sha256'],name
    before={p:hashlib.sha256(subprocess.check_output(['git','show',f'{baseline}:{p}'],cwd=ROOT)).hexdigest() for p in paths}
    changes=[p for p,h in before.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    assert changes==['rtl/chirp/chirp_controller.sv'],changes
    roms={}
    for top in ('rf_nco_mode','rf_chirp_nco_mode'):
        for hp in (0,1):
            d=OUT/f'generic-{top}-{hp}'
            mod=json.loads((d/'netlist.json').read_text())['modules'][top]
            memories=[c for c in mod['cells'].values() if c['type']=='$mem_v2']
            assert len(memories)==1
            params=memories[0]['parameters'];w=int(params['WIDTH'],2);n=int(params['SIZE'],2)
            assert int(params['RD_PORTS'],2)==2 and int(params['WR_PORTS'],2)==0
            init=int(params['INIT'],2)
            actual=[(init>>(k*w))&((1<<w)-1) for k in range(n)]
            expect=quarter_table() if hp else sine_table()
            assert actual==[v&((1<<w)-1) for v in expect]
            roms[f'{top}-{hp}']=dict(words_checked=n,width=w,mismatches=0,read_ports=2,copies=1)
    banking={}
    for kind,top in [('target','mode_top'),('target-chirp','chirp_mode_top')]:
        for hp in (0,1):
            d=OUT/f'{kind}-{hp}'
            cells=json.loads((d/'synth.json').read_text())['modules'][top]['cells']
            memories=[c for c in cells.values() if c['type']=='DP16K']
            assert len(memories)==(16 if hp else 1)
            zero=next(c['connections']['Z'] for c in cells.values() if c['type']=='VLO')
            for c in memories:
                assert c['connections']['WEA']==c['connections']['WEB']==zero
                assert c['connections']['CLKA']==c['connections']['CLKB']
                assert c['parameters']['OUTREG_A']==c['parameters']['OUTREG_B']=='BYPASSED'
                assert any(isinstance(v,int) for v in c['connections']['DOA'])
                assert any(isinstance(v,int) for v in c['connections']['DOB'])
            banking[f'{kind}-{hp}']=dict(physical_ebr=len(memories),both_read_ports_connected=True,
                modes=sorted(set(c['parameters']['DATA_WIDTH_A'] for c in memories)))
    for hp in (0,1):
        for kind in ('chirp','nco'):
            r=json.loads((OUT/f'{kind}_exact_{hp}.json').read_text())
            assert all(v==0 for k,v in r.items() if 'mismatches' in k and v is not None)
    spec=json.loads((OUT/'spectral.json').read_text())
    assert spec['summaries']['High-purity']['worst_sfdr_db']>90
    capture=json.loads((ROOT/'build/lifcl40/high_purity_capture/analysis.json').read_text())
    bit=ROOT/'build/lifcl40/high_purity_capture.bit'
    assert hashlib.sha256(bit.read_bytes()).hexdigest()==capture['sha256']
    figures={}
    for p in (OUT/'figures').glob('*.png'):
        w,h=struct.unpack('>II',p.read_bytes()[16:24]);assert w>=1600
        figures[p.name]=dict(width=w,height=h)
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for base in ('rtl','models/python','fpga/lifcl40/high_purity_capture') for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    (OUT/'production-after.json').write_text(json.dumps(hashes,indent=2)+'\n')
    result=dict(changed_preserved_sources=changes,all_other_baseline_sources_and_physical_evidence_unchanged=True,
                logical_rom_audit=roms,physical_banking=banking,figures=figures,
                generated_rom_sha256=hashlib.sha256((ROOT/'rtl/nco/high_purity_quarter.svh').read_bytes()).hexdigest(),
                capture_bitstream_sha256=capture['sha256'],physical_high_purity_validation='See docs/high_purity_physical_validation.md; build audit alone is not physical proof',
                recorded_loaded_bitstream_sha256=manifest['loaded_bitstream_sha256'])
    (OUT/'final_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
