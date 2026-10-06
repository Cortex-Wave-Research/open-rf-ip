"""Yosys built-in SAT proofs and explicit reachable witnesses; no external solver."""
import json
import re
import subprocess


def run(root, report):
    output = report/'formal'
    output.mkdir(exist_ok=True)
    results = []
    configurations = [('wb', 0, 1)] + [('csr', hp, kind) for hp in (0, 1) for kind in (0, 1)]
    for boundary, hp, kind in configurations:
        label = f'{boundary}-{hp}-{kind}'
        top = 'openrf_'+boundary+'_formal'
        sources = ['rtl/control/openrf_control_pkg.sv',
                   'rtl/control/openrf_'+('wb_slave' if boundary=='wb' else 'csr_core')+'.sv',
                   'verification/formal/'+top+'.sv']
        setup = 'read_verilog -formal -sv ' + ' '.join(sources) + '\n'
        if boundary=='csr':
            setup += f'chparam -set HIGH_PURITY {hp} -set ENGINE_KIND {kind} {top}\n'
        setup += f'hierarchy -check -top {top}\nproc\nflatten\n'
        if boundary=='csr':
            # Only add observer fanout. Never replace a DUT driver or cut state.
            for i in range(9):
                setup += f'connect -nomap -nounset -set s{i} \\dut.shadow[{i}]\n'
            for name in ('errors','sequence_number','dirty','done_sticky'):
                setup += f'connect -nomap -nounset -set {name} dut.{name}\n'
        setup += 'async2sync\nchformal -lower\nopt\ncheck -assert\n'
        setup += f'write_json {output/label}.json\n'
        base = 'sat -set-assumes -seq 24 -prove-asserts -verify -timeout 120'
        induction = 'sat -set-assumes -seq 4 -tempinduct -maxsteps 12 -prove-asserts -verify -timeout 120'
        def execute(suffix, commands):
            script = output/(label+'-'+suffix+'.ys')
            script.write_text(setup+commands+'\n')
            with (output/(label+'-'+suffix+'.log')).open('w') as stream:
                subprocess.run(['yosys','-Q','-T','-s',str(script)],cwd=root,
                               stdout=stream,stderr=subprocess.STDOUT,check=True)
        if boundary == 'wb':
            execute('bounded', base+f' -dump_vcd {output/label}-counterexample.vcd')
        execute('induction', induction+f' -dump_vcd {output/label}-induction-counterexample.vcd')
        proof_log = (output/(label+'-induction.log')).read_text()
        assert 'Induction step proven: SUCCESS!' in proof_log
        induction_k = int(re.findall(r'\[induction step (\d+)\]', proof_log)[-1])
        netlist=json.loads((output/(label+'.json')).read_text())
        count=sum(c['type']=='$assert' for c in netlist['modules'][top]['cells'].values())
        bits = list(range(3)) if boundary=='wb' else [0,1,3,4,5,*range(6,12)] + ([2] if kind else [])
        # Require a witness for EACH goal, not just one satisfiable disjunction.
        commands=[]
        for bit in bits:
            commands.append(f'sat -set-assumes -seq 24 -prove reached[{bit}] 0 -falsify -timeout 120 '
                            f'-show-ports -dump_vcd {output}/{label}-cover-{bit}.vcd')
        execute('covers','chformal -assert -remove\nopt_clean\n'+'\n'.join(commands))
        cover_log = (output/(label+'-covers.log')).read_text()
        assert cover_log.count('SAT proof finished - model found: FAIL!') == len(bits), 'Missing cover witnesses'
        results.append({'boundary':boundary,'profile':hp,'kind':kind,'assertions':count,
                        'bounded_depth':24 if boundary=='wb' else None,
                        'induction':'PASS','induction_k':induction_k,'induction_seq':4,
                        'cover_bits':bits,'cover_depth':24,'result':'PASS'})
        (report/'formal_results.json').write_text(json.dumps({'result':'RUNNING','runs':results},indent=2)+'\n')
    return {'result':'PASS','engine':'Yosys SAT temporal induction','solver':'built-in ezSAT / MiniSAT',
            'runs':results,'assertion_instances':sum(r['assertions'] for r in results),
            'covers_reached':sum(len(r['cover_bits']) for r in results)}
