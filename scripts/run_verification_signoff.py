#!/usr/bin/env python3
"""Offline signoff. No downloads, hardware access, evidence writes, or Git mutations."""
import argparse
import hashlib
import json
import os
import importlib.metadata
import re
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.control_plane_sources import CONTROL, WAVE
from verification.signoff.transactions import vectors

BASELINE = '9b853ad1b9596229859ed35ae2ce5324b7ba891f'
REPORT = ROOT / 'reports/verification_hardening'
SEEDS = list(range(61101, 61111))
CROSS_SEEDS = [61201, 61202, 61203, 61204, 61205]
TESTS = [
    'verification/pytest/' + name + '.py' for name in (
        'test_control_register_map', 'test_control_plane_model', 'test_control_plane_rtl',
        'test_nco', 'test_nco_lut', 'test_chirp', 'test_rf_nco', 'test_rf_chirp_nco',
        'test_nco_waveform', 'test_high_purity_model', 'test_production_modes')
] + [
    'fpga/lifcl40/test_nco_top.py', 'fpga/lifcl40/test_chirp_top.py',
    'fpga/lifcl40/test_physical_top.py', 'fpga/lifcl40/capture/test_capture.py',
    'fpga/lifcl40/capture/test_format.py',
    'fpga/lifcl40/high_purity_capture/test_high_purity_format.py',
    'fpga/lifcl40/high_purity_capture/test_high_purity_capture.py',
    'analysis/test_hardware_verification.py', 'analysis/test_high_purity_hardware.py',
]


def save(name, result):
    (REPORT / name).write_text(json.dumps(result, indent=2) + '\n')


def command(args, log):
    with (REPORT / log).open('w') as stream:
        stream.write('COMMAND: ' + repr(args) + '\n'); stream.flush()
        subprocess.run(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)


def tools():
    names = 'verilator iverilog vvp yosys yosys-smtbmc sby z3 boolector yices yices-smt2 bitwuzla ccache vcs xrun vsim cvc nvc'.split()
    record = {name: {'path': shutil.which(name)} for name in names}
    for name, args in [('verilator',['--version']), ('yosys',['-V']), ('ccache',['--version']),
                       ('iverilog',['-V']), ('vvp',['-V'])]:
        if record[name]['path']:
            result = subprocess.run([name, *args], capture_output=True, text=True, check=True)
            record[name]['version'] = (result.stdout + result.stderr).strip()
    record['python'] = sys.version
    for name in ('pytest','cocotb'):
        record[name] = importlib.metadata.version(name)
    record['os'] = Path('/etc/os-release').read_text()
    # Audit repository-owned invocation sources; do not inspect private state.
    violations = []
    for folder in ('scripts','verification','fpga','analysis','rtl'):
        for source in (ROOT/folder).rglob('*'):
            if source.suffix not in ('.py','.sv','.sh'):
                continue
            for lineno, line in enumerate(source.read_text().splitlines(), 1):
                if re.search(r"--bbox-(unsup|sys)|--x-(initial|assign)\s+fast|lint_off|-Wno-", line):
                    # This line is the auditor's pattern, not a simulator option.
                    if source == Path(__file__):
                        continue
                    violations.append(f'{source.relative_to(ROOT)}:{lineno}: {line}')
    assert not violations, f'Signoff policy audit requires review: {violations}'
    record['policy_audit'] = 'PASS: no repository blackboxing, warning suppression, or explicit fast-X option'
    record['additional_installed_locations'] = []
    for base in ('/opt','/usr/local',str(Path.home()/'.local'),str(Path.home()/'tools'),
                 str(ROOT/'tools'), str(ROOT/'downloads'), str(ROOT/'third_party_build')):
        for parent, directories, filenames in os.walk(base):
            directories[:] = [d for d in directories if d not in ('node_modules','.git','__pycache__')]
            record['additional_installed_locations'] += [str(Path(parent)/name) for name in filenames
                if name in names and os.access(Path(parent)/name, os.X_OK)]
    record['result'] = 'PASS'
    return record


def hashes():
    manifest = json.loads((REPORT / 'baseline_hashes.json').read_text())
    current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    changed = [p for p, sha in manifest['files'].items()
               if not (ROOT / p).is_file() or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != sha]
    assert manifest['head'] == BASELINE, 'Unexpected baseline snapshot'
    # Verification-only commits must remain runnable without moving the frozen
    # source baseline or weakening any of its per-file hash checks.
    subprocess.run(['git', 'merge-base', '--is-ancestor', BASELINE, current],
                   cwd=ROOT, check=True)
    assert not changed, f'Frozen tracked files changed: {changed}'
    return {'result': 'PASS', 'head': current, 'tracked_files_unchanged': len(manifest['files']),
            'production_files': sum(p.startswith('rtl/') for p in manifest['files']),
            'physical_evidence': {p: sha for p, sha in manifest['files'].items()
                if p.startswith(('examples/physical_capture/', 'reports/hardware_capture/',
                                 'reports/high_purity_physical_verification/'))}}


def baseline():
    command([sys.executable, 'scripts/generate_control_registers.py', '--check'], 'generator.log')
    command([sys.executable, '-m', 'pytest', '-q', *TESTS,
             '--junitxml=' + str(REPORT/'baseline.xml')], 'baseline.log')
    tree = ET.parse(REPORT/'baseline.xml')
    cases = tree.findall('.//testcase')
    assert len(cases) == 247, f'Baseline collection changed: {len(cases)}'
    return {'result': 'PASS', 'tests': len(cases), 'new_pytest_cases': 0,
            'exact_waveforms': [json.loads((ROOT/'reports/control_plane'/f'waveform-{hp}-{kind}.json').read_text())
                                for hp in (0, 1) for kind in (0, 1)]}


def lint():
    checked = []
    for hp in (0, 1):
        for top in ('openrf_control', 'openrf_controlled_nco', 'openrf_controlled_chirp'):
            sources = CONTROL if top == 'openrf_control' else CONTROL + WAVE + ['rtl/control/'+top+'.sv']
            command(['verilator', '--lint-only', '--Wall', '-Irtl/nco', '--top-module', top,
                     '-GHIGH_PURITY='+str(hp), *sources], f'lint-{top}-{hp}.log')
            checked.append([top, hp])
    return {'result': 'PASS', 'configurations': checked, 'flags': ['--Wall'], 'suppressions': []}


def build(top, hp, kind, simulator='verilator', randomized=False):
    from cocotb_tools.runner import get_runner
    runner = get_runner(simulator)
    directory = ROOT/'build/verification_hardening'/f'{simulator}-{top}-{hp}-{kind}-{int(randomized)}'
    sources = CONTROL if top == 'openrf_control' else CONTROL + WAVE + ['rtl/control/'+top+'.sv']
    params = {'HIGH_PURITY': hp}
    if top == 'openrf_control':
        params['ENGINE_KIND'] = kind
    flags = ['--Wall'] if simulator == 'verilator' else ['-g2012']
    if randomized:
        flags += ['--x-initial', 'unique', '--x-assign', 'unique']
    runner.build(sources=[ROOT/p for p in sources], includes=[ROOT/'rtl/nco'],
                 hdl_toplevel=top, parameters=params, build_dir=directory, build_args=flags,
                 timescale=('1ns', '1ps'), log_file=REPORT/(directory.name+'-build.log'))
    return runner


def simulate(runner, top, hp, kind, modules, label, seed, **env):
    directory = REPORT/label
    directory.mkdir(parents=True, exist_ok=True)
    runner.test(hdl_toplevel=top, test_module=modules, seed=seed,
                plusargs=[f'+verilator+seed+{seed}', '+verilator+rand+reset+2']
                    if runner.__class__.__name__ == 'Verilator' else [],
                extra_env={'HP': str(hp), 'KIND': str(kind), 'PROJECT_ROOT': str(ROOT),
                           'WAVEFORM': str(int(top != 'openrf_control')), 'SIGNOFF_SEED': str(seed),
                           'RESET_RESULT': str(directory/'reset.json'), **env},
                test_dir=directory, results_xml=str(directory/'results.xml'),
                log_file=directory/'simulation.log')
    cases = ET.parse(directory/'results.xml').findall('.//testcase')
    assert cases and not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
    return directory


def randomized():
    results = []
    for hp in (0, 1):
        for kind in (0, 1):
            top = 'openrf_control'
            runner = build(top, hp, kind, randomized=True)
            for seed in SEEDS:
                label = f'random-csr-{hp}-{kind}-{seed}'
                directory = simulate(runner, top, hp, kind,
                    ['verification.signoff.reset_stress', 'verification.cocotb.control_plane'], label, seed)
                results.append({'label': label, **json.loads((directory/'reset.json').read_text())})
                save('randomized_init_results.json', {'result': 'RUNNING', 'runs': results})
        top = 'openrf_controlled_chirp'
        runner = build(top, hp, 1, randomized=True)
        for seed in SEEDS[:3]:
            label = f'random-chirp-{hp}-{seed}'
            directory = simulate(runner, top, hp, 1,
                ['verification.signoff.reset_stress', 'verification.cocotb.control_waveform'], label, seed)
            wave = json.loads((ROOT/'reports/control_plane'/f'waveform-{hp}-1.json').read_text())
            (directory/'waveform.json').write_text(json.dumps(wave, indent=2)+'\n')
            results.append({'label': label, **json.loads((directory/'reset.json').read_text()), 'waveform': wave})
            save('randomized_init_results.json', {'result': 'RUNNING', 'runs': results})
    for hp in (0, 1):
        for kind in (0, 1):
            probes = {r['pre_reset_probe'] for r in results if r['label'].startswith(f'random-csr-{hp}-{kind}-')}
            assert len(probes) > 1, 'Initial state did not vary across seeds'
    return {'result': 'PASS', 'flags': ['--x-initial unique', '--x-assign unique'],
            'runtime': ['+verilator+rand+reset+2', '+verilator+seed+N'], 'runs': results}


def cross():
    available = bool(shutil.which('iverilog') and shutil.which('vvp'))
    results = []
    for hp in (0, 1):
        simulators = ['verilator'] + (['icarus'] if available else [])
        runners = {sim: build('openrf_control', hp, 1, sim) for sim in simulators}
        for seed in [None, *CROSS_SEEDS]:
            label = 'directed' if seed is None else str(seed)
            vector = REPORT/f'vectors-{label}.json'
            vector.write_text(json.dumps(vectors(seed), indent=2)+'\n')
            transcripts = []
            for sim in simulators:
                transcript = REPORT/f'transcript-{sim}-{hp}-{label}.json'
                simulate(runners[sim], 'openrf_control', hp, 1, 'verification.signoff.cross_sim',
                         f'cross-{sim}-{hp}-{label}', seed or 61200,
                         VECTOR_FILE=str(vector), TRANSCRIPT_FILE=str(transcript))
                transcripts.append(transcript)
            if available:
                a, b = [json.loads(p.read_text()) for p in transcripts]
                if a != b:
                    mismatch = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a),len(b)))
                    save('first_cross_mismatch.json', {'index': mismatch, 'files': list(map(str, transcripts))})
                    raise AssertionError(f'Cross-simulator mismatch at row {mismatch}; preserve and classify')
            results.append({'profile': hp, 'seed': seed, 'transactions': len(vectors(seed)['transactions']),
                            'verilator_python': 'PASS', 'cross_simulator': 'PASS' if available else 'NOT_EXECUTED'})
    return {'result': 'PASS' if available else 'FAIL', 'runs': results,
            'reason': None if available else 'SECOND SIMULATOR NOT AVAILABLE; independent second-simulator gate not executed'}


def formal():
    from verification.signoff.formal import run
    return run(ROOT, REPORT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['all','tools','hashes','baseline','lint','randomized','cross','formal'], default='all')
    args = parser.parse_args()
    REPORT.mkdir(parents=True, exist_ok=True)
    # A fresh clone can reconstruct the frozen snapshot from Git, not from its
    # potentially modified worktree. Never overwrite a recorded snapshot.
    if not (REPORT/'baseline_hashes.json').exists():
        files = subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE],cwd=ROOT,text=True).splitlines()
        save('baseline_hashes.json', {'head': BASELINE, 'files': {p: hashlib.sha256(
            subprocess.check_output(['git','show',f'{BASELINE}:{p}'],cwd=ROOT)).hexdigest() for p in files}})
    if shutil.which('ccache'):
        os.environ['OBJCACHE'] = shutil.which('ccache')
        os.environ['CCACHE_DIR'] = str(ROOT/'build/verification_hardening/ccache')
    os.environ['PYTHONPATH'] = str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH','')
    stages = ['tools','hashes','baseline','lint','randomized','cross','formal','hashes'] if args.stage == 'all' else [args.stage]
    results = {}
    names = {'tools': 'tool_versions.json', 'randomized': 'randomized_init_results.json', 'cross': 'cross_sim_results.json',
             'formal': 'formal_results.json'}
    for stage in stages:
        print(f'SIGNOFF {stage}: running', flush=True)
        try:
            result = globals()[stage]()
        except (Exception, SystemExit) as error:
            traceback.print_exc()
            result = {'result': 'FAIL', 'error': str(error), 'classification': 'REQUIRES INVESTIGATION'}
            save(names.get(stage, stage+'_results.json'), result)
            results[stage] = result
            archive = REPORT/'failures'/str(time.time_ns())
            shutil.copytree(REPORT, archive, ignore=shutil.ignore_patterns('failures'))
            # Do not continue after an unexplained failure. The known missing
            # second-simulator gate returns a normal FAIL and permits other work.
            break
        save(names.get(stage, stage+'_results.json'), result)
        results[stage] = result
        print(f'SIGNOFF {stage}: {result["result"]}', flush=True)
    passed = all(r['result'] == 'PASS' for r in results.values())
    added_sources = [ROOT/'scripts/run_verification_signoff.py', ROOT/'docs/verification_policy.md']
    added_sources += list((ROOT/'verification/signoff').glob('*.py'))
    added_sources += list((ROOT/'verification/formal').glob('*.sv'))
    summary = {'result': 'PASS' if passed else 'FAIL', 'scope': args.stage, 'stages': results,
               'verification_source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                              for p in added_sources}}
    save('signoff_results.json' if args.stage == 'all' else f'stage-{args.stage}.json', summary)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
