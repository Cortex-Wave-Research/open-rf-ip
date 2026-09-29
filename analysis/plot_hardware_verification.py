"""Offline Milestone 4A.3c comparison and figures; never opens hardware.

Run from repository root: .venv/bin/python analysis/plot_hardware_verification.py
Inputs are immutable. A persistent manifest pins their initial SHA256 and sizes.
Expected samples come only from the existing independent Python model.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.python.chirp import ChirpConfig, ChirpModel
from fpga.lifcl40.capture.read_capture import decode

OUT = ROOT / 'reports/hardware_capture'
COLUMNS = ['index', 'I', 'Q', 'valid', 'chirp_start', 'chirp_end']
FIELDS = COLUMNS[1:]
CONFIG = dict(sample_rate_hz=12000000, start_word=178956971, step=53692,
              length=10000, repeat=False, depth=1024, initial_phase=0,
              phase_bits=32, output_bits=14, lut_address_bits=10,
              alignment_offset=0)


def fingerprint(path):
    data = path.read_bytes()
    return dict(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))


def preserve_evidence(output_dir=None, input_dir=None):
    source = OUT if input_dir is None else input_dir
    paths = [source / 'capture_1024.csv']
    if (source / 'capture_1024.bin').exists():
        paths.append(source / 'capture_1024.bin')
    manifest = {p.name: fingerprint(p) for p in paths}
    # Record physical line count before structure validation or model generation.
    manifest['capture_1024.csv']['physical_line_count'] = len(paths[0].read_bytes().splitlines())
    dest = (OUT if output_dir is None else output_dir) / 'evidence_manifest.json'
    if dest.exists():
        if json.loads(dest.read_text()) != manifest:
            raise ValueError('Evidence differs from preserved manifest; refusing analysis')
    else:
        with dest.open('x') as f:
            json.dump(manifest, f, indent=2)
            f.write('\n')
    return manifest


def validate_csv(path):
    with path.open(newline='') as f:
        rows = list(csv.reader(f, strict=True))
    if not rows or rows[0] != COLUMNS:
        raise ValueError('CSV columns must be exactly ' + ','.join(COLUMNS))
    if len(rows) != 1025:
        raise ValueError(f'Expected 1024 sample rows, got {len(rows)-1}')
    values = []
    for index, row in enumerate(rows[1:]):
        if len(row) != 6 or any(re.fullmatch(r'-?\d+', v, flags=re.ASCII) is None for v in row):
            raise ValueError(f'Non-integer or malformed record at row {index}')
        v = tuple(map(int, row))
        if v[0] != index:
            raise ValueError(f'Noncontinuous/duplicate/missing index at row {index}: {v[0]}')
        if any(not -8192 <= x <= 8191 for x in v[1:3]):
            raise ValueError(f'I/Q outside signed 14-bit range at index {index}')
        if any(x not in (0, 1) for x in v[3:]):
            raise ValueError(f'Illegal control value at index {index}')
        values.append(dict(zip(COLUMNS, v)))
    return values


def reference():
    model = ChirpModel()
    config = ChirpConfig(CONFIG['start_word'], CONFIG['step'], CONFIG['length'], CONFIG['repeat'])
    for _ in range(4):
        model.tick(rst=True)
    accepted = model.tick(config, start=True)
    if accepted['valid']:
        raise AssertionError('Accepted start must emit no sample')
    rows = []
    for index in range(CONFIG['depth']):
        r = model.tick(config, start=True)
        if r['index'] != index:
            raise AssertionError('Reference sample alignment changed')
        rows.append(dict(index=index, I=r['i'], Q=r['q'], valid=int(r['valid']),
                         chirp_start=int(r['chirp_start']), chirp_end=int(r['chirp_end'])))
    return rows


def compare(hardware, expected):
    if len(hardware) != 1024 or len(expected) != 1024:
        raise ValueError('Comparison requires exactly 1024 records on both sides')
    counts, first, examples = {}, {}, {}
    for field in FIELDS:
        bad = [dict(index=k, hardware=h[field], expected=e[field], difference=h[field]-e[field])
               for k, (h, e) in enumerate(zip(hardware, expected)) if h[field] != e[field]]
        counts[field] = len(bad)
        first[field] = bad[0]['index'] if bad else None
        examples[field] = bad[:8]
    errors = {f: [h[f]-e[f] for h, e in zip(hardware, expected)] for f in ('I', 'Q')}
    checks = dict(first_record_start=hardware[0]['chirp_start'] == 1,
                  exactly_one_start=sum(h['chirp_start'] for h in hardware) == 1,
                  all_end_zero=all(h['chirp_end'] == 0 for h in hardware),
                  all_valid=all(h['valid'] == 1 for h in hardware))
    return dict(samples_compared=len(hardware), mismatch_counts=counts,
                first_mismatch_index=first, first_eight_mismatches_per_field=examples,
                records_with_any_mismatch=sum(any(h[f] != e[f] for f in FIELDS)
                                              for h, e in zip(hardware, expected)),
                max_absolute_error={f: max(map(abs, errors[f])) for f in errors},
                rms_error={f: math.sqrt(sum(v*v for v in errors[f])/len(hardware)) for f in errors},
                marker_checks=checks,
                exact_pass=not any(counts.values()) and all(checks.values()))


def raw_crosscheck(hardware, input_dir=None):
    path = (OUT if input_dir is None else input_dir) / 'capture_1024.bin'
    if not path.exists():
        return dict(status='UNAVAILABLE', records_compared=0)
    decoded = decode(path.read_bytes())  # Pure offline function, no PyFtdi import.
    bad = [dict(index=k, decoded=list(d), csv=[h[f] for f in COLUMNS])
           for k, (d, h) in enumerate(zip(decoded, hardware))
           if tuple(h[f] for f in COLUMNS) != d]
    return dict(status='PASS' if not bad and len(decoded) == len(hardware) else 'FAIL',
                records_compared=len(decoded), records_with_any_mismatch=len(bad),
                first_eight_mismatches=bad[:8])


def write_comparison(hardware, expected, output_dir):
    columns = ['index', 'hardware_I', 'expected_I', 'I_error', 'hardware_Q', 'expected_Q', 'Q_error',
               'hardware_valid', 'expected_valid', 'hardware_chirp_start', 'expected_chirp_start',
               'hardware_chirp_end', 'expected_chirp_end']
    with (output_dir / 'capture_1024_comparison.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for h, e in zip(hardware, expected):
            row = dict(index=h['index'], I_error=h['I']-e['I'], Q_error=h['Q']-e['Q'])
            row.update({f'hardware_{k}': h[k] for k in FIELDS})
            row.update({f'expected_{k}': e[k] for k in FIELDS})
            writer.writerow(row)


def figures(hardware, expected, result, output_dir):
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'build/matplotlib-hardware'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.labelcolor': '#203040', 'text.color': '#203040',
                         'savefig.facecolor': 'white'})
    target = output_dir / 'figures'
    target.mkdir(exist_ok=True)
    n = result['samples_compared']
    counts = result['mismatch_counts']
    blue, orange = '#1464a0', '#bd5218'
    footer = 'Source: capture_1024.csv • Physical provenance: operator-reported FPGA capture • Digital samples only; no analog/RF measurement'
    def save(fig, name):
        fig.savefig(target / name, dpi=180)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 6.8))
    fig.subplots_adjust(left=.09, right=.97, bottom=.22, top=.73)
    fig.suptitle('Physical FPGA I/Q Capture vs Independent Python Reference', fontsize=18, fontweight='bold', y=.96)
    fig.text(.09,.865,'LIFCL-40-EVN • 12 MHz FPGA sample clock • Compact NCO / FMCW chirp\n1024 samples captured over physical FT2232H / I²C readback • capture_1024.csv',fontsize=12,linespacing=1.6)
    # Show 128 samples to keep individual cycles readable in embedded figures.
    x = list(range(128))
    for field, color in [('I',blue),('Q',orange)]:
        ax.plot(x,[h[field] for h in hardware[:128]],color=color,lw=2.5,label=f'FPGA Hardware {field}')
        ax.plot(x,[e[field] for e in expected[:128]],color=color,ls='--',lw=1,
                marker='o',markersize=3,markerfacecolor='white',markevery=3,label=f'Python Reference {field}')
    ax.set(xlabel='Capture sample index (first 128 shown; all 1024 compared)',ylabel='Signed 14-bit code',xlim=(0,127),ylim=(-9500,9500))
    ax.grid(alpha=.18)
    ax.legend(ncol=2,loc='upper center',bbox_to_anchor=(.5,-.18),frameon=False,fontsize=11)
    fig.text(.09,.77,f'{n} Samples Compared — {counts["I"] + counts["Q"]} I/Q Mismatches',fontweight='bold',color=blue)
    fig.text(.03,.035,footer,fontsize=8.5)
    save(fig,'fpga_vs_python_iq.png')

    fig, ax = plt.subplots(figsize=(12,6.8))
    fig.subplots_adjust(left=.09,right=.70,bottom=.19,top=.77)
    fig.suptitle('FPGA Hardware − Python Reference Error',fontsize=21,fontweight='bold',y=.95)
    fig.text(.09,.85,f'All {n} physical capture records • Integer code difference • Zero alignment offset',fontsize=12)
    for field,color,style in [('I',blue,'-'),('Q',orange,'--')]:
        ax.plot(range(n),[h[field]-e[field] for h,e in zip(hardware,expected)],color=color,lw=2.5,ls=style,label=f'{field} hardware − {field} Python')
    lim=max(1,max(result['max_absolute_error'].values())*1.15)
    ax.set(xlim=(0,n-1),ylim=(-lim,lim),xlabel='Capture sample index',ylabel='Error (integer codes)')
    ax.grid(alpha=.2)
    ax.legend(loc='lower center',frameon=False)
    stat='MEASURED ERROR\n\n'+'\n'.join(f'{f} mismatches: {counts[f]}\nMax |{f} error|: {result["max_absolute_error"][f]}\nRMS {f} error: {result["rms_error"][f]:.6g}\n' for f in ('I','Q'))
    fig.text(.74,.73,stat,va='top',fontsize=12,linespacing=1.55,bbox=dict(boxstyle='round,pad=.9',fc='#f0f5f9',ec='#d4dfe8'))
    fig.text(.09,.085,'Both traces lie exactly at zero.' if not any(result['max_absolute_error'].values()) else 'Nonzero differences are shown without sample realignment.',fontweight='bold')
    fig.text(.03,.035,footer,fontsize=8.5)
    save(fig,'fpga_python_error.png')

    fig,ax=plt.subplots(figsize=(12,9))
    fig.subplots_adjust(left=.02,right=.98,top=.85,bottom=.09)
    ax.set(xlim=(0,1),ylim=(0,1)); ax.axis('off')
    passed=result['exact_pass'] and result['raw_crosscheck']['status'] != 'FAIL'
    title='Physical FPGA Digital Validation — '+('BIT-EXACT PASS' if passed else 'CHECK FAILED')
    fig.suptitle(title,fontsize=20,fontweight='bold',y=.965)
    fig.text(.05,.905,'LIFCL-40-EVN • 12 MHz • Compact FMCW chirp • First 1024 of 10000 samples',fontsize=12)
    def box(x,y,w,h,text,color):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.008',fc=color,ec='#c3d1dc'))
        ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=11,linespacing=1.4)
    def arrow(a,b):
        ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color='#526779',lw=1.6))
    flow=[('RTL / IMPLEMENTATION\nSystemVerilog → Yosys / nextpnr','#edf1f5'),
          ('PHYSICAL EXECUTION\nLIFCL-40-EVN FPGA → 1024-sample RAM','#e7f2f8'),
          ('PHYSICAL READBACK\nFT2232H Channel B / I²C → Ubuntu','#e7f2f8'),
          ('PRESERVED EVIDENCE\ncapture_1024.csv + raw .bin / SHA256','#edf1f5')]
    for i,(label,color) in enumerate(flow):
        y=.83-i*.19
        box(.02,y,.44,.13,label,color)
        if i<3: arrow((.24,y),(.24,y-.06))
    box(.56,.80,.41,.16,'INDEPENDENT PYTHON REFERENCE\nChirpModel + numerical sine LUT\nReset → accept start → samples 0…1023','#edf5eb')
    box(.56,.29,.41,.43,
        f'OFFLINE EXACT COMPARISON\n\nSamples: {n}\nI mismatches: {counts["I"]}    Q mismatches: {counts["Q"]}\nControl field mismatches: {sum(counts[f] for f in FIELDS[2:])}\nMaximum I / Q error: {result["max_absolute_error"]["I"]} / {result["max_absolute_error"]["Q"]}\nAlignment offset: 0 samples\nRaw binary vs CSV: {result["raw_crosscheck"]["status"]}', '#edf5eb' if passed else '#fff0e9')
    arrow((.765,.80),(.765,.72))
    arrow((.46,.325),(.56,.325))
    ax.text(.025,.13,'Model: 32-bit phase / 10-bit LUT address / signed 14-bit I/Q\nStart word 178956971 • Step +53692 • Repeat off',fontsize=11,linespacing=1.6)
    ax.text(.025,.025,'Physical execution/readback reported by operator; files analyzed offline.\nScope: this captured digital prefix. No analog/RF, spectral-purity, or full-chirp claim.',fontsize=10,linespacing=1.5)
    save(fig,'physical_verification_summary.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=ROOT / 'examples/physical_capture',
                        help='Immutable capture directory containing capture_1024.csv and optional .bin')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reports/hardware_verification',
                        help='Directory for derived comparison artifacts and figures')
    args = parser.parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest=preserve_evidence(output_dir, input_dir)
    hardware=validate_csv(input_dir / 'capture_1024.csv')  # Abort before model use if malformed.
    raw=raw_crosscheck(hardware, input_dir)
    expected=reference()
    result=compare(hardware,expected)
    result.update(configuration=CONFIG,evidence=manifest,raw_crosscheck=raw)
    result['overall_pass']=result['exact_pass'] and raw['status'] != 'FAIL'
    result['source_sha256']={str(p.relative_to(ROOT)):fingerprint(p)['sha256'] for p in
        [ROOT/'models/python/chirp.py', ROOT/'models/python/nco_lut.py', ROOT/'models/python/nco.py',
         ROOT/'fpga/lifcl40/capture/read_capture.py',Path(__file__)]}
    write_comparison(hardware,expected,output_dir)
    figures(hardware,expected,result,output_dir)
    if preserve_evidence(output_dir, input_dir)!=manifest:
        raise AssertionError('Evidence changed during analysis')
    (output_dir/'comparison_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 0 if result['overall_pass'] else 1


if __name__=='__main__':
    raise SystemExit(main())
