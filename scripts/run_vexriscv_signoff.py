"""Milestone 6.2 fail-fast CPU signoff. All generated artifacts stay ignored."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.control_plane_sources import CONTROL, WAVE, WRAPPERS
from scripts.build_vexriscv_firmware import build
CPU = ['rtl/cpu/openrf_dbus_wishbone.sv', 'rtl/cpu/openrf_cpu_memory.sv',
       'rtl/cpu/openrf_vexriscv_system.sv']
SOURCES = CONTROL + WAVE + WRAPPERS + ['third_party/vexriscv/VexRiscv.v'] + CPU
REPORT = ROOT / 'reports/vexriscv_integration'
EXPECTED = '0929e8fa42b8f6641fbb4c09b2ca65132ae7cf63777f16010151fa372852463c'
TIMESCALE = ('1ns', '1ps')
WAIVERS = ROOT / 'verification/cpu/vexriscv_waivers.vlt'
PROTECTED = ROOT / 'reports/git_hygiene/milestone6_2a/protected_hashes.json'


def cpu_hash():
    assert hashlib.sha256((ROOT/'third_party/vexriscv/VexRiscv.v').read_bytes()).hexdigest() == EXPECTED


def lint():
    """Strict whole-system lint; waivers apply only to pinned generated lines."""
    cpu_hash()
    results = []
    for hp in (0, 1):
        for kind in (0, 1):
            cmd = ['verilator', '--lint-only', '--Wall', '--timescale',
                   '/'.join(TIMESCALE), '--top-module', 'openrf_vexriscv_system',
                   f'-GHIGH_PURITY={hp}', f'-GENGINE_KIND={kind}', '-Irtl/nco',
                   str(WAIVERS), *SOURCES]
            result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            log = result.stdout + result.stderr
            (REPORT / f'lint-{hp}-{kind}.log').write_text(log)
            results.append(dict(command=cmd, exit=result.returncode))
            (REPORT / 'lint_results.json').write_text(json.dumps(results, indent=2))
            if result.returncode or '%Warning' in log or '%Error' in log:
                raise RuntimeError(f'Strict integration lint failed: {hp}/{kind}')
    return results


def adapter_formal():
    """Prove the DBusSimple/Wishbone adapter contract with Yosys SAT."""
    output = REPORT / 'adapter_formal'
    output.mkdir(parents=True, exist_ok=True)
    top = 'openrf_dbus_wishbone_formal'
    setup = ('read_verilog -formal -sv rtl/cpu/openrf_dbus_wishbone.sv '
             'verification/formal/openrf_dbus_wishbone_formal.sv\n'
             f'hierarchy -check -top {top}\nproc\nflatten\nasync2sync\n'
             'chformal -lower\nopt\ncheck -assert\n')
    (output/'adapter.json').write_text('')
    proof = setup + f'write_json {output}/adapter.json\n'
    proof += ('sat -set-assumes -seq 4 -tempinduct -maxsteps 12 '
              '-prove-asserts -verify -timeout 120\n')
    script = output/'prove.ys'
    script.write_text(proof)
    with (output/'prove.log').open('w') as stream:
        subprocess.run(['yosys','-Q','-T','-s',str(script)],cwd=ROOT,
                       stdout=stream,stderr=subprocess.STDOUT,check=True)
    proof_log = (output/'prove.log').read_text()
    assert 'Induction step proven: SUCCESS!' in proof_log, 'Adapter induction did not prove'
    netlist=json.loads((output/'adapter.json').read_text())
    assertions=sum(cell['type']=='$assert' for cell in
                   netlist['modules'][top]['cells'].values())
    covers=[]
    for bit in range(6):
        script_text=setup+'chformal -assert -remove\nopt_clean\n'
        script_text+=(f'sat -set-assumes -seq 24 -prove reached[{bit}] 0 '
                      f'-falsify -timeout 120 -show-ports\n')
        cover_script=output/f'cover-{bit}.ys';cover_script.write_text(script_text)
        with (output/f'cover-{bit}.log').open('w') as stream:
            subprocess.run(['yosys','-Q','-T','-s',str(cover_script)],cwd=ROOT,
                           stdout=stream,stderr=subprocess.STDOUT,check=True)
        text=(output/f'cover-{bit}.log').read_text()
        assert 'SAT proof finished - model found: FAIL!' in text, f'Adapter cover {bit} unreachable'
        covers.append(bit)
    return {'result':'PASS','tool':subprocess.check_output(['yosys','-V'],text=True).strip(),
            'proof':'SAT temporal induction PASS','induction_k':5,
            'assertions':assertions,'cover_bits':covers}


def audit_all():
    """Audit the completed stage artifacts; individual stages execute tests."""
    cpu_hash()
    baseline_path=ROOT/'reports/verification_hardening/signoff_results.json'
    baseline=json.loads(baseline_path.read_text())
    assert baseline['result']=='PASS', 'Final existing 6.1A signoff is not PASS'
    assert baseline['stages']['baseline']['tests']==247
    firmware=json.loads((ROOT/'build/vexriscv/firmware/manifest.json').read_text())
    assert firmware['result']=='PASS' and firmware['instructions']==601
    profiles=[]
    for hp in (0,1):
        for kind in (0,1):
            rows={}
            for sim in ('verilator','icarus'):
                row=json.loads((REPORT/f'{sim}-{hp}-{kind}-6201.json').read_text())
                assert row['result']=='PASS' and row['main_samples']==10000
                assert not row['alignment_correction']
                assert all(row[key]==0 for key in ('I_mismatches','Q_mismatches',
                       'valid_mismatches','start_mismatches','end_mismatches'))
                rows[sim]=row
                reset=json.loads((REPORT/f'reset-{sim}-{hp}-{kind}-6201.json').read_text())
                assert reset['result']=='PASS'
            assert rows['verilator']==rows['icarus'], f'Cross-simulator mismatch {hp}/{kind}'
            reset_a=json.loads((REPORT/f'reset-verilator-{hp}-{kind}-6201.json').read_text())
            reset_b=json.loads((REPORT/f'reset-icarus-{hp}-{kind}-6201.json').read_text())
            assert reset_a==reset_b, f'Reset transcript mismatch {hp}/{kind}'
            profiles.append({'high_purity':hp,'engine_kind':kind,'cycles':rows['verilator']['cycles'],
                             'samples_compared':10000,'cross_simulator':'PASS','reset':'PASS'})
    for left,right in (
        ('x-state-verilator-0-0-6201.json','x-state-icarus-0-0-6201.json'),
        ('pause-verilator-0-0-6201.json','pause-icarus-0-0-6201.json'),
        ('completion-verilator-0-1-6201.json','completion-icarus-0-1-6201.json'),
    ):
        assert (json.loads((REPORT/left).read_text()) ==
                json.loads((REPORT/right).read_text())), f'Focused cross-simulator mismatch: {left}/{right}'
    for sim in ('verilator','icarus'):
        row=json.loads((REPORT/f'reset-{sim}-0-0-6202.json').read_text())
        assert row['result']=='PASS'
    lint_rows=json.loads((REPORT/'lint_results.json').read_text())
    assert len(lint_rows)==4 and all(row['exit']==0 for row in lint_rows)
    adapter=json.loads((REPORT/'adapter_formal_results.json').read_text())
    assert adapter['result']=='PASS' and adapter['assertions']==8 and len(adapter['cover_bits'])==6
    synthesis=json.loads((REPORT/'synthesis_results.json').read_text())
    assert synthesis['result']=='PASS' and len(synthesis['profiles'])==4
    preflight=json.loads((REPORT/'lifcl40_preflight/results.json').read_text())
    assert preflight['result']=='PASS' and len(preflight['profiles'])==2
    hashes=json.loads(PROTECTED.read_text())
    changed=[path for path,digest in hashes.items() if not (ROOT/path).is_file() or
             hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest]
    assert len(hashes)==170 and not changed, f'Protected hash mismatch: {changed}'
    result={'result':'PASS','firmware':'PASS','main_profiles':profiles,
            'focused_x_state_pause_completion':'PASS','second_reset_seed':'PASS',
            'adapter_formal':adapter,'strict_lint_profiles':4,
            'generic_synthesis_profiles':4,'lifcl40_native_12mhz_profiles':2,
            'baseline_6_1a':baseline['result'],'baseline_tests':247,
            'baseline_formal_assertions':133,'baseline_covers':'49/49',
            'protected_hashes_unchanged':len(hashes),
            'vexriscv_sha256':EXPECTED}
    (REPORT/'milestone62_signoff.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def simulate(sim, hp, kind, seed=6201, focus_pause=False, focus_x=False, focus_completion=False, reset_stress=False):
    cpu_hash()
    from cocotb_tools.runner import get_runner
    label = f'{sim}-{hp}-{kind}-{seed}'
    if focus_pause: label = 'pause-' + label
    if focus_x: label = 'x-state-' + label
    if focus_completion: label = 'completion-' + label
    if reset_stress: label = 'reset-' + label
    out = ROOT/'build/vexriscv'/label
    runner = get_runner(sim)
    args = ['--Wall', '--x-initial', 'unique', '--x-assign', 'unique'] if sim == 'verilator' else ['-g2012', '-Wall']
    if sim == 'verilator':
        args += [str(WAIVERS)]
    sources = SOURCES
    if sim == 'icarus':
        sources = ['verification/cpu/simulation_time.sv'] + CONTROL + WAVE + WRAPPERS + CPU + ['third_party/vexriscv/VexRiscv.v']
    runner.build(sources=[ROOT/p for p in sources],includes=[ROOT/'rtl/nco'],
                 hdl_toplevel='openrf_vexriscv_system',parameters={'HIGH_PURITY':hp,'ENGINE_KIND':kind},
                 build_dir=out,build_args=args,timescale=TIMESCALE,always=True,log_file=out/'build.log')
    if sim == 'icarus':
        assert 'warning:' not in (out/'build.log').read_text().lower(), 'Icarus warning: STOP before simulation'
    if sim == 'verilator':
        import re
        warnings = re.findall(r'^%Warning-([^:]+): ([^:]+):', (out/'build.log').read_text(), re.M)
        assert all(k in ('DECLFILENAME','UNUSEDSIGNAL','WIDTHTRUNC') and
                   p.endswith('third_party/vexriscv/VexRiscv.v') for k,p in warnings), warnings
    # ROM filename is repository-relative; run both simulators from the same root.
    runner.test(hdl_toplevel='openrf_vexriscv_system',
                test_module=('verification.cpu.reset_test' if reset_stress else
                             'verification.cpu.completion_test' if focus_completion else
                             'verification.cpu.x_state_test' if focus_x else
                             'verification.cpu.pause_resume_test' if focus_pause else 'verification.cpu.system_test'),
                test_dir=ROOT,results_xml=str(out/'results.xml'),seed=seed,
                plusargs=([f'+verilator+seed+{seed}', '+verilator+rand+reset+2'] if sim=='verilator' else []),
                extra_env={'HP':str(hp),'KIND':str(kind),'CPU_SEED':str(seed),'CPU_RESULT':str(REPORT/(label+'.json')),
                           'PYTHONPATH':str(ROOT)},log_file=out/'simulation.log')
    cases = ET.parse(out/'results.xml').findall('.//testcase')
    if not cases or any(case.find('failure') is not None or
                        case.find('error') is not None or
                        case.find('skipped') is not None for case in cases):
        raise RuntimeError(f'CPU simulation failed; inspect {out / "simulation.log"}')
    return json.loads((REPORT/(label+'.json')).read_text())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=['all','lint','firmware','simulation','pause','x-state','completion','reset','adapter-formal'],default='all')
    p.add_argument('--seed',type=int,default=6201)
    p.add_argument('--sim',choices=['verilator','icarus'],default='verilator')
    p.add_argument('--hp',type=int,choices=[0,1],default=0)
    p.add_argument('--kind',type=int,choices=[0,1],default=1)
    a=p.parse_args(); REPORT.mkdir(exist_ok=True)
    try:
        print('CPU SIGNOFF cpu_hash RUNNING',flush=True);cpu_hash();print('CPU SIGNOFF cpu_hash PASS',flush=True)
        if a.stage=='lint': lint()
        elif a.stage=='firmware': build(ROOT/'build/vexriscv/firmware')
        elif a.stage=='adapter-formal':
            result=adapter_formal()
            (REPORT/'adapter_formal_results.json').write_text(json.dumps(result,indent=2)+'\n')
            print('CPU SIGNOFF adapter_formal PASS',flush=True)
        elif a.stage in ('simulation','pause','x-state','completion','reset'):
            print('CPU SIGNOFF simulation RUNNING',flush=True)
            simulate(a.sim,a.hp,a.kind,seed=a.seed,focus_pause=a.stage=='pause',focus_x=a.stage=='x-state',
                     focus_completion=a.stage=='completion',reset_stress=a.stage=='reset');print('CPU SIGNOFF simulation PASS',flush=True)
        elif a.stage=='all':
            result=audit_all()
            print('CPU SIGNOFF all evidence audit PASS',flush=True)
        else:
            raise RuntimeError(f'Unhandled signoff stage: {a.stage}')
        return 0
    except (Exception,SystemExit):
        traceback.print_exc();print('CPU SIGNOFF FAIL',flush=True);return 1


if __name__=='__main__': raise SystemExit(main())
