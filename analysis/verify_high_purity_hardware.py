"""Offline Milestone 5A.1: pinned physical evidence, exact reference, reports/PNGs.

Run: .venv/bin/python analysis/verify_high_purity_hardware.py
Never imports a hardware driver, searches offsets, normalizes, or uses tolerance.
The evidence manifest was recorded before analysis and is never regenerated here.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.python.high_purity import HighPurityChirp, HighPurityConfig, linear_config
from fpga.lifcl40.capture.capture_format import decode, image_size
from analysis import plot_hardware_verification as compact

EVIDENCE = ROOT / 'reports/high_purity_physical_verification'
OUT = EVIDENCE / 'derived'
INPUT = ROOT / 'reports/hardware_capture/high_purity_1024.csv'
MANIFEST = EVIDENCE / 'evidence_manifest.json'
TOP = ROOT / 'fpga/lifcl40/high_purity_capture/high_purity_capture_top.sv'
FIELDS = compact.FIELDS
COLUMNS = compact.COLUMNS
FIGURES = ['fpga_vs_python_high_purity_iq.png', 'fpga_python_high_purity_error.png',
           'high_purity_physical_validation_summary.png']
CONCLUSION = 'PHYSICAL HIGH-PURITY FPGA DIGITAL WAVEFORM VALIDATION: '


def check_evidence(manifest_path=MANIFEST):
    manifest = json.loads(manifest_path.read_text())
    for name, saved in manifest['evidence'].items():
        path = ROOT / name
        if compact.fingerprint(path) != {k: saved[k] for k in ('sha256', 'size_bytes')}:
            raise ValueError(f'Immutable evidence changed: {name}')
        if path.suffix == '.csv':
            data = path.read_bytes()
            if len(data.splitlines()) != saved['physical_line_count']:
                raise ValueError(f'Evidence line count changed: {name}')
            if len(list(csv.reader(data.decode().splitlines()))) - 1 != saved['data_row_count']:
                raise ValueError(f'Evidence row count changed: {name}')
    for name, sha in manifest['protected_source_sha256'].items():
        if compact.fingerprint(ROOT / name)['sha256'] != sha:
            raise ValueError(f'Protected source/bitstream changed: {name}')
    bitstream = ROOT / 'build/lifcl40/high_purity_capture.bit'
    if bitstream.exists() and compact.fingerprint(bitstream)['sha256'] != manifest['loaded_bitstream_sha256']:
        raise ValueError('Local bitstream differs from the recorded loaded image')
    return manifest


def validate_csv(path):
    with path.open(newline='') as f:
        rows = list(csv.reader(f, strict=True))
    if not rows or rows[0] != COLUMNS:
        raise ValueError(f'Expected columns exactly {COLUMNS}')
    if len(rows) != 1025:
        raise ValueError(f'Expected 1024 data rows, got {len(rows)-1}')
    result = []
    for k, row in enumerate(rows[1:]):
        if len(row) != 6 or any(re.fullmatch(r'-?\d+', v, re.ASCII) is None for v in row):
            raise ValueError(f'Malformed integer record {k}')
        values = tuple(map(int, row))
        if values[0] != k:
            raise ValueError(f'Index duplicate/missing/reordered at {k}')
        if any(not -131072 <= v <= 131071 for v in values[1:3]):
            raise ValueError(f'Signed 18-bit range violation at {k}')
        if any(v not in (0, 1) for v in values[3:]):
            raise ValueError(f'Nonbinary control at {k}')
        result.append(dict(zip(COLUMNS, values)))
    return result


def configuration():
    """Read explicitly connected literals; never infer words from captured data."""
    text = TOP.read_text()
    def value(port, width, signed=False):
        pattern = rf"\.{port}\({width}'{'s' if signed else ''}d(-?\d+)\)"
        found = re.findall(pattern, text)
        if len(found) != 1:
            raise ValueError(f'Capture configuration is not a unique literal: {port}')
        return int(found[0])
    if ".HIGH_PURITY(1)" not in text or ".repeat_mode(1'b0)" not in text:
        raise ValueError('Unexpected capture mode/repeat configuration')
    config = HighPurityConfig(value('start_phase_inc', 64), value('chirp_step', 64, True),
                             value('chirp_length', 32), False)
    # Clock is specified by the consumed PDC, corroborated by wrapper/documentation.
    pdc = (ROOT / 'fpga/lifcl40/capture/capture.pdc').read_text()
    period = re.findall(r'create_clock.*?-period\s+([\d.]+)', pdc)
    if len(period) != 1 or period[0] != '83.33333333333333':
        raise ValueError('Capture 12 MHz clock constraint changed')
    if config != linear_config(500000, 2000000, 12000000, 10000):
        raise ValueError('Wrapper differs from documented physical chirp')
    return dict(sample_rate_hz=12000000, start_word=config.start_word, step=config.step,
                length=config.length, repeat=config.repeat, depth=1024, initial_phase=0,
                phase_bits=64, phase_resolution_bits=16, output_bits=18, dither=False,
                output_convention='I=cos, Q=sin; pre-increment phase; nearest/ties-away; symmetric +/-131071',
                phase_arithmetic='W[k]=(start+k*step) mod 2^64; P[k]=(k*start+step*k*(k-1)/2) mod 2^64',
                amplitude_mapping='independent quarter-wave binary64 sine; top 16 phase bits; low 48 retained',
                reset='four synchronous startup reset edges; phase and both pipeline stages zero',
                start_condition='held start, enable=1; capture starts on first valid && chirp_start',
                nco_latency_active_edges=2, marker_delay_extra_edges=1,
                marker_latency='matches I/Q: first chirp_start at E2 after start acceptance E0',
                capture_latency_edges=1, alignment_offset=0,
                alignment_contract='E0 accept; E1 admit P0; E2 output sample0/start; E3 store pre-edge sample0 as capture index0')


def reference(config):
    model = HighPurityChirp()
    cfg = HighPurityConfig(config['start_word'], config['step'], config['length'], config['repeat'])
    for _ in range(4):
        model.tick(rst=True)
    # Model the SAME edge ordering as the synchronous passive capture store.
    previous = model.tick(cfg, start=True)  # E0: no sample.
    if previous['valid']:
        raise AssertionError('E0 must not emit a sample')
    rows = []
    active = False
    for edge in range(1, config['depth'] + 3):
        if previous['valid'] and (active or previous['chirp_start']):
            active = True
            k = len(rows)
            if previous['index'] != k or (k == 0 and edge != 3):
                raise AssertionError('Documented capture alignment changed')
            rows.append(dict(index=k, I=previous['i'], Q=previous['q'],
                             **{f: int(previous[f]) for f in FIELDS[2:]}))
        elif active:
            raise AssertionError('Reference capture valid gap')
        previous = model.tick(cfg, start=True)
    if len(rows) != 1024:
        raise AssertionError('Reference capture depth changed')
    return rows


def raw_crosscheck(hardware, path):
    if not path.exists():
        return dict(status='NOT AVAILABLE', message='RAW RFC2 CROSS-CHECK: NOT AVAILABLE',
                    header_validation='NOT AVAILABLE', records_compared=0)
    data = path.read_bytes()
    if data[:5] != b'RFC2\x02':
        raise ValueError('Physical raw capture must be RFC2 / version 2')
    image_size(data[:16])
    rows = decode(data)  # Existing pure decoder; no hardware API called.
    bad = [dict(index=k, raw=list(d), csv=[h[f] for f in COLUMNS])
           for k, (d, h) in enumerate(zip(rows, hardware)) if tuple(h[f] for f in COLUMNS) != d]
    return dict(status='PASS' if not bad and len(rows) == len(hardware) else 'FAIL',
                header_validation='PASS', format='RFC2', version=data[4], capture_done=bool(data[5]&1),
                gap_error=bool(data[5]&2), sample_count=int.from_bytes(data[6:8], 'little'),
                record_size_bytes=data[8], component_width_bits=data[9], image_size_bytes=len(data),
                reserved_header_and_record_bits_zero=True, records_compared=len(rows),
                records_with_any_mismatch=len(bad), first_eight_mismatches=bad[:8])


def write_comparison(hardware, expected, output):
    columns = ['index','hardware_I','expected_I','I_error','hardware_Q','expected_Q','Q_error',
               'hardware_valid','expected_valid','hardware_chirp_start','expected_chirp_start',
               'hardware_chirp_end','expected_chirp_end']
    with (output / 'high_purity_1024_comparison.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for h, e in zip(hardware, expected):
            row = dict(index=h['index'], I_error=h['I']-e['I'], Q_error=h['Q']-e['Q'])
            row.update({f'hardware_{field}': h[field] for field in FIELDS})
            row.update({f'expected_{field}': e[field] for field in FIELDS})
            writer.writerow(row)


def compact_result():
    source = ROOT / 'examples/physical_capture'
    hardware = compact.validate_csv(source / 'capture_1024.csv')
    result = compact.compare(hardware, compact.reference())
    result.update(raw_crosscheck=compact.raw_crosscheck(hardware, source), configuration=compact.CONFIG)
    return result


def comparison_table(result):
    old = result['compact_physical']
    rows = [('I/Q width',14,18), ('Phase accumulator width',32,64), ('Phase resolution',10,16),
            ('Capture depth',1024,1024), ('Capture format','RFC1','RFC2'),
            ('Hardware samples compared',old['samples_compared'],result['samples_compared']),
            ('I mismatches',old['mismatch_counts']['I'],result['mismatch_counts']['I']),
            ('Q mismatches',old['mismatch_counts']['Q'],result['mismatch_counts']['Q']),
            ('Control mismatches',sum(old['mismatch_counts'][f] for f in FIELDS[2:]),result['control_mismatches']),
            ('Alignment offset',old['configuration']['alignment_offset'],result['configuration']['alignment_offset']),
            ('Max I error',old['max_absolute_error']['I'],result['max_absolute_error']['I']),
            ('Max Q error',old['max_absolute_error']['Q'],result['max_absolute_error']['Q'])]
    return '\n'.join(['| Metric | Compact physical | High-purity physical |', '|---|---:|---:|'] +
                     [f'| {a} | {b} | {c} |' for a,b,c in rows])


def figures(hardware, expected, result, output):
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'build/matplotlib-hardware'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'text.color':'#203040',
                         'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})
    target = output / 'figures'
    target.mkdir(exist_ok=True)
    n, counts = result['samples_compared'], result['mismatch_counts']
    blue, orange = '#1464a0', '#bd5218'
    footer = 'Operator-reported physical capture • SHA256-pinned CSV + RFC2 binary • Digital correctness only; no analog/RF or SFDR measurement'
    def save(fig, name):
        fig.savefig(target / name, dpi=180)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(14,7.5))
    fig.subplots_adjust(left=.08,right=.97,bottom=.23,top=.73)
    fig.suptitle('Physical High-Purity FPGA I/Q Capture vs Independent Python Reference',
                 fontsize=19,fontweight='bold',y=.96)
    fig.text(.08,.85, f'LIFCL-40-EVN • 12 MHz physical FPGA clock • RFC2 • signed 18-bit I/Q\n{n} physical samples • High-purity 64-bit NCO • Dither OFF', linespacing=1.6)
    fig.text(.08,.77,f'{n} Samples — {counts["I"]+counts["Q"]} I/Q Mismatches',fontweight='bold',color=blue)
    for field,color in [('I',blue),('Q',orange)]:
        ax.plot(range(128),[h[field] for h in hardware[:128]],color=color,lw=2.6,label=f'FPGA Hardware {field}')
        ax.plot(range(128),[e[field] for e in expected[:128]],color=color,ls='--',lw=1,
                marker='o',markersize=3,markerfacecolor='white',markevery=3,label=f'Python Reference {field}')
    ax.set(xlim=(0,127),ylim=(-150000,150000),xlabel='Capture index (first 128 shown; all 1024 compared)',ylabel='Signed 18-bit code')
    ax.ticklabel_format(axis='y',style='plain'); ax.grid(alpha=.18)
    ax.legend(ncol=2,loc='upper center',bbox_to_anchor=(.5,-.18),frameon=False)
    fig.text(.03,.035,footer,fontsize=9)
    save(fig,FIGURES[0])

    fig,ax=plt.subplots(figsize=(14,7.5))
    fig.subplots_adjust(left=.08,right=.70,bottom=.19,top=.77)
    fig.suptitle('High-Purity FPGA Hardware − Python Reference Error',fontsize=22,fontweight='bold',y=.95)
    fig.text(.08,.85,f'All {n} physical samples • Exact integer differences • Alignment offset: {result["configuration"]["alignment_offset"]}')
    for field,color,style in [('I',blue,'-'),('Q',orange,'--')]:
        ax.plot(range(n),[h[field]-e[field] for h,e in zip(hardware,expected)],color=color,lw=2.5,ls=style,label=f'{field} hardware − {field} Python')
    lim=max(1,max(result['max_absolute_error'].values())*1.15)
    ax.set(xlim=(0,n-1),ylim=(-lim,lim),xlabel='Capture sample index',ylabel='Error (integer codes)')
    ax.grid(alpha=.2);ax.legend(loc='lower center',frameon=False)
    stats='MEASURED ERROR\n\n'+'\n'.join(f'{f} mismatches: {counts[f]}\nMax |{f} error|: {result["max_absolute_error"][f]}\nRMS {f} error: {result["rms_error"][f]:.6g}\n' for f in ('I','Q'))
    fig.text(.75,.73,stats,va='top',linespacing=1.6,bbox=dict(boxstyle='round,pad=.8',fc='#f0f5f9',ec='#d4dfe8'))
    fig.text(.08,.085,'Both traces sit at zero.' if not any(result['max_absolute_error'].values()) else 'Nonzero errors; no offset search or amplitude normalization.',fontweight='bold')
    fig.text(.03,.035,footer,fontsize=9)
    save(fig,FIGURES[1])

    fig,ax=plt.subplots(figsize=(14,11))
    fig.subplots_adjust(left=.03,right=.97,top=.87,bottom=.08)
    ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    label='BIT-EXACT PASS' if result['overall_pass'] else 'FAIL'
    fig.suptitle('PHYSICAL HIGH-PURITY FPGA DIGITAL VALIDATION — '+label,fontsize=18,fontweight='bold',y=.97)
    fig.text(.06,.915,f'LIFCL-40-EVN • 12 MHz • RFC2 • First {n} of {result["configuration"]["length"]} chirp samples')
    def box(x,y,w,h,text,color='#edf1f5',fontsize=11):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.008',fc=color,ec='#c3d1dc'))
        ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=fontsize,linespacing=1.4)
    def arrow(a,b):
        ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color='#526779',lw=1.6))
    flow=['Production SystemVerilog\nhigh-purity NCO/chirp','Yosys / nextpnr / Project Oxide',
          'LIFCL-40-EVN Physical FPGA','RFC2 1024-sample capture','FT2232H channel B / I²C',
          'Ubuntu capture file\nhigh_purity_1024.csv + .bin']
    for k,text in enumerate(flow):
        y=.87-k*.125
        box(.015,y,.44,.085,text,'#e7f2f8' if k in (2,3,4) else '#edf1f5')
        if k<5:arrow((.235,y),(.235,y-.04))
    box(.55,.835,.43,.12,'Independent 64-bit Python model\nQuarter-wave sine • 64-bit chirp arithmetic','#edf5eb')
    arrow((.765,.835),(.765,.695))
    ax.text(.785,.755,'expected samples',fontsize=10,va='center')
    stats=(f'EXACT SAMPLE COMPARISON\n\nSamples compared: {n}\nI mismatches: {counts["I"]}\nQ mismatches: {counts["Q"]}\nControl mismatches: {result["control_mismatches"]}\nMax I error: {result["max_absolute_error"]["I"]}\nMax Q error: {result["max_absolute_error"]["Q"]}\nAlignment offset: {result["configuration"]["alignment_offset"]}\nRaw vs CSV: {result["raw_crosscheck"]["status"]}')
    box(.55,.25,.43,.435,stats,'#edf5eb' if result['overall_pass'] else '#fff0e9',12)
    arrow((.455,.2875),(.55,.2875))
    box(.015,.075,.965,.105,'Compact: 32-bit phase / 14-bit I/Q      |      High-purity: 64-bit phase / 18-bit I/Q\nPhysical captured-prefix correctness; no analog/RF performance claim',fontsize=12)
    fig.text(.04,.035,footer,fontsize=9)
    save(fig,FIGURES[2])


def report(result, output):
    cfg, ev = result['configuration'], result['evidence']
    capture = ev[str(INPUT.relative_to(ROOT))]
    raw_hash = ev.get(str(INPUT.with_suffix('.bin').relative_to(ROOT)),{}).get('sha256','NOT AVAILABLE')
    passed = result['overall_pass']
    lines = ['# Milestone 5A.1 — Exact physical high-purity hardware vs Python', '',
             'Physical provenance: the operator reports successful loading of '
             '`build/lifcl40/high_purity_capture.bit`, JP2 shorted / JP1 open, '
             'D3 ON (done) / D4 OFF (no error), and successful FT2232H channel-B I²C '
             'readback: "Saved 1024 samples; RFC2; no numerical correctness claim". '
             'The board is powered off. All work in this milestone is offline.', '',
             f'Physical capture path: `{INPUT.relative_to(ROOT)}`  ',
             f'Capture SHA256: `{capture["sha256"]}`  ',f'Raw RFC2 SHA256: `{raw_hash}`  ',
             f'Prepared bitstream SHA256: `{result["loaded_bitstream_sha256"]}`  ',
             f'CSV size: {capture["size_bytes"]} bytes; rows: {capture["data_row_count"]} '
             f'({capture["physical_line_count"]} lines including header).  ',
             'Original CSV/BIN and protected source hashes checked before and after analysis; unchanged. The recorded loaded bitstream hash is checked only if the local generated image exists.', '',
             '## Reference configuration and alignment', '',
             'Configuration literals are extracted from the production physical wrapper, clock corroborated '
             'by capture.pdc and docs/high_purity_nco.md; no values inferred from physical samples. '
             'Expected samples use the unchanged independent models/python/high_purity.py model. '
             'The RTL LUT is hashed for preservation only and never supplies expected amplitudes.', '',
             '```json',json.dumps(cfg,indent=2),'```', '',
             'NCO latency: 2 active rising edges inclusive of admission. Marker latency: '
             'MARKER_DELAY=1 extra edge over compact, aligned with output at E2. Capture latency: '
             '1 further edge to write the already registered pair. At E3 the store sees pre-edge '
             'sample0/valid/start and writes RAM[0]. Thus capture index0 is model sample0: '
             'comparison alignment offset = 0. No arbitrary offset search or sample removal.', '',
             'The startup shift register resets for four edges. Held start can rearm later one-shots '
             'without phase reset; frozen capture RAM contains only the first 1024 samples of the first '
             '10000-sample chirp. End is expected only at index9999, outside this capture.', '',
             '## Exact measured comparison', '',f'Samples compared: {result["samples_compared"]}  ']
    for field in FIELDS:
        lines.append(f'{field} mismatches: {result["mismatch_counts"][field]}; first mismatch index: {result["first_mismatch_index"][field]}  ')
    lines += [f'Records with any mismatch: {result["records_with_any_mismatch"]}  ',
              f'Control mismatches (valid + start + end): {result["control_mismatches"]}  ']
    for field in ('I','Q'):
        lines += [f'Max |{field} error|: {result["max_absolute_error"][field]}  ',f'RMS {field} error: {result["rms_error"][field]}  ']
    lines += ['', '```json',json.dumps({key:result[key] for key in ('first_hardware_record','first_expected_record','last_hardware_record','last_expected_record','marker_checks','first_record_exact','first_eight_mismatches_per_field')},indent=2),'```', '',
              'Mismatch examples are bounded to eight per field; total counts above summarize all remaining mismatches.', '',
              '## Structure and raw-vs-CSV cross-check', '',
              'CSV requires exact columns index,I,Q,valid,chirp_start,chirp_end, exactly 1024 '
              'integer rows in index order 0…1023, no duplicates/gaps/reordering, signed 18-bit '
              'bounds −131072…131071, binary flags. Malformed input aborts before model comparison. '
              'CSV itself has no version header; format/version are established from the corresponding '
              'raw RFC2 image. The existing decoder checks framing, size, status, reserved bits, '
              'signed little-endian packing and marker legality. Every decoded record is compared to CSV.', '',
              '```json',json.dumps(result['raw_crosscheck'],indent=2),'```', '',
              '## Compact vs high-purity physical correctness', '',comparison_table(result), '',
              'Compact statistics were recomputed offline from its preserved physical CSV/BIN and '
              'independent compact model. No digital SFDR comparison is inferred from either short chirp capture.', '',
              '## Offline regression and reproduction', '',
              result['offline_regression']['summary'], '',
              '```sh',result['offline_regression']['command'],
              '.venv/bin/python analysis/verify_high_purity_hardware.py','```', '',
              'Regression logs: high_purity_physical_verification/offline_regression.log and regression_results.json. '
              'Existing RTL regressions use Verilator simulation with --Wall; transport tests simulate I²C '
              'signals only. No physical hardware access, synthesis, place/route or bitstream rebuild in this '
              'milestone. Historical synthesis/place/route results are summarized in docs/high_purity_nco.md remains historical.', '',
              '## Generated artifacts', '',
              '- [Evidence manifest](../evidence_manifest.json)',
              '- [Full comparison CSV](high_purity_1024_comparison.csv)',
              '- [Machine-readable results](comparison_results.json)']
    lines += [f'- [{name}](figures/{name})' for name in FIGURES]
    lines += ['', '## Scope and next step', '']
    if passed:
        lines += ['For this tested configuration and captured 1024-sample prefix: production high-purity '
                  'RTL is bit-exact to the independent Python model; the synthesized, placed and routed '
                  'implementation runs on physical LIFCL-40 silicon (operator-reported programming provenance); '
                  'full 18-bit I/Q survives RFC2 capture and host readback; high-purity valid/start/end markers '
                  'align with physical samples. No end assertion is exercised in this prefix. '
                  'This is not an exhaustive proof of all words, configurations or the uncaptured chirp tail.']
    else:
        lines += ['Validation failed. Do not change RTL/model in this milestone. Inspect the bounded mismatch '
                  'records and raw/header cross-check first. Start with packing/sign/byte order if raw differs; '
                  'otherwise inspect the documented E0→E3 phase/marker path and first divergent phase/word '
                  'offline. No offset is silently applied.']
    lines += ['', 'Not proven: analog DAC performance, RF phase noise in dBc/Hz, analog SFDR, GHz carrier '
              'generation, 400 MHz physical RF bandwidth, multi-lane performance, Candidate D, or external '
              'RF chain performance.', '',
              'Next: review the evidence, figures and regression, then decide whether to commit Milestone '
              '5/5A. No automatic commit or push, hardware access, or next architecture work.', '',
              CONCLUSION + ('BIT-EXACT PASS' if passed else 'FAIL')]
    if passed:
        lines += ['', 'The production high-purity NCO/chirp implementation is physically validated on the LIFCL-40-EVN with bit-exact 18-bit I/Q agreement against the independent Python model.']
    (output / 'report.md').write_text('\n'.join(lines)+'\n')


def run(output=OUT):
    manifest = check_evidence()
    output.mkdir(parents=True,exist_ok=True)
    hardware = validate_csv(INPUT)
    raw = raw_crosscheck(hardware, INPUT.with_suffix('.bin'))
    if raw['status'] == 'FAIL':
        raise ValueError('Raw-vs-CSV disagreement: '+json.dumps(raw))
    cfg = configuration()
    expected = reference(cfg)
    result = compact.compare(hardware, expected)
    result.update(configuration=cfg, raw_crosscheck=raw, evidence=manifest['evidence'],
                  protected_source_sha256=manifest['protected_source_sha256'],
                  loaded_bitstream_sha256=manifest['loaded_bitstream_sha256'],
                  compact_physical=compact_result(),
                  control_mismatches=sum(result['mismatch_counts'][f] for f in FIELDS[2:]),
                  first_record_exact=hardware[0]==expected[0],
                  first_hardware_record=hardware[0],first_expected_record=expected[0],
                  last_hardware_record=hardware[-1],last_expected_record=expected[-1])
    result['overall_pass'] = result['samples_compared']==1024 and result['exact_pass'] and raw['status'] == 'PASS'
    result['source_sha256'] = {str(p.relative_to(ROOT)):compact.fingerprint(p)['sha256'] for p in
                              (Path(__file__).resolve(), ROOT/'analysis/plot_hardware_verification.py')}
    regression = OUT / 'regression_results.json'
    result['offline_regression'] = json.loads(regression.read_text()) if regression.exists() else dict(summary='Pending; no regression result claimed.',command='Pending')
    result['generated_figures'] = [str((output/'figures'/name).relative_to(ROOT)) for name in FIGURES]
    write_comparison(hardware,expected,output)
    figures(hardware,expected,result,output)
    check_evidence()
    result['immutable_evidence_verified_after_analysis'] = True
    (output/'comparison_results.json').write_text(json.dumps(result,indent=2)+'\n')
    report(result,output)
    print(json.dumps({k:result[k] for k in ('samples_compared','mismatch_counts','raw_crosscheck','overall_pass')},indent=2))
    print(CONCLUSION+('BIT-EXACT PASS' if result['overall_pass'] else 'FAIL'))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        result = run()
        raise SystemExit(0 if result['overall_pass'] else 1)
    except (ValueError, OSError, AssertionError) as exc:
        print(f'Evidence/contract validation rejected: {exc}',file=sys.stderr)
        print(CONCLUSION+'FAIL',file=sys.stderr)
        raise SystemExit(1)
