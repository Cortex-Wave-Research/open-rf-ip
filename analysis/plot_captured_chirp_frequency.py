"""Offline time/frequency figure: full configured chirp and physical capture prefix.

Run: .venv/bin/python analysis/plot_captured_chirp_frequency.py
The I/Q estimate uses adjacent complex phase differences, with no smoothing.
Each difference is assigned to its left sample because sample k advances by W[k].
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.plot_hardware_verification import (
    CONFIG, compare, fingerprint, reference, validate_csv,
)
from models.python.chirp import ChirpConfig

os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'build/matplotlib-hardware'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=ROOT / 'examples/physical_capture')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reports/hardware_verification')
    args = parser.parse_args()
    source, output = args.input_dir, args.output_dir
    manifest = json.loads((output / 'evidence_manifest.json').read_text())
    for name, meta in manifest.items():
        actual = fingerprint(source / name)
        if any(actual[key] != meta[key] for key in ('sha256', 'size_bytes')):
            raise ValueError('Evidence hash/size changed: ' + name)
    rows = validate_csv(source / 'capture_1024.csv')
    result = compare(rows, reference())
    fs = CONFIG['sample_rate_hz']
    config = ChirpConfig(CONFIG['start_word'], CONFIG['step'], CONFIG['length'], False)
    k = np.arange(config.length)
    t = k / fs * 1e6
    f = np.array([config.word(int(index)) * fs / 2**32 for index in k])
    z = np.array([complex(r['I'], r['Q']) for r in rows])
    measured = np.angle(z[1:] * z[:-1].conjugate()) * fs / (2*np.pi)
    count = len(rows)
    span = (count-1)/fs*1e6
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'text.color': '#203040', 'axes.labelcolor': '#203040'})
    fig, axes = plt.subplots(2, 1, figsize=(12, 9))
    fig.subplots_adjust(left=.10, right=.96, bottom=.18, top=.83, hspace=.65)
    fig.suptitle('FMCW Chirp — Frequency vs Time', fontsize=24, fontweight='bold', y=.965)
    fig.text(.10,.895,'LIFCL-40-EVN • 12 MHz sample clock • Compact NCO • Physical capture: 1024 I/Q samples',fontsize=12)
    blue, orange = '#1464a0', '#bd5218'
    ax=axes[0]
    ax.plot(t, f/1e6, color=blue, lw=2.5, label='Configured chirp frequency (exact tuning words)')
    ax.axvspan(0, span, color='#51a7b8', alpha=.20, label='Physical capture window')
    ax.scatter([t[0], t[-1]], [f[0]/1e6, f[-1]/1e6], color=blue, s=25, zorder=3)
    ax.set(title='Full configured waveform — only the shaded prefix was captured',
           xlabel='Time from first chirp sample (µs)', ylabel='Frequency (MHz)',
           xlim=(0,t[-1]), ylim=(.4,2.13))
    ax.text(.025,.89,f'{f[0]/1e6:.3f} → {f[-1]/1e6:.3f} MHz over {config.length/fs*1e6:.3f} µs\n10,000 configured samples; capture spans 0–{span:.2f} µs',transform=ax.transAxes,va='top',fontsize=11)
    ax.legend(loc='lower right',fontsize=10,frameon=False)
    ax.grid(alpha=.20)
    ax=axes[1]
    ax.plot(t[:count-1], measured/1e3, color=orange, alpha=.8, lw=1,
            label='Physical I/Q phase-difference estimate (unsmoothed)')
    ax.plot(t[:count],f[:count]/1e3,color=blue,lw=2.4,label='Expected frequency from independent model configuration')
    ax.set(title='Captured prefix — physical I/Q estimate compared with the programmed ramp',
           xlabel='Time from first captured sample (µs)',ylabel='Frequency (kHz)',xlim=(0,span))
    ax.grid(alpha=.20)
    ax.legend(loc='upper left',fontsize=10,frameon=False)
    iq_mismatches=result['mismatch_counts']['I']+result['mismatch_counts']['Q']
    fig.text(.10,.067,f'{count} I/Q samples • {len(measured)} adjacent phase differences • {iq_mismatches} I/Q mismatches vs Python',fontsize=11,fontweight='bold')
    fig.text(.10,.025,'Small estimate ripple comes from LUT / amplitude quantization. Digital frequency only; no analog or RF measurement.\nSource: capture_1024.csv. The remainder of the full chirp is configured, not physically captured.',fontsize=9,linespacing=1.5)
    destination=output/'figures/fpga_chirp_frequency_vs_time.png'
    fig.savefig(destination,dpi=180,facecolor='white')
    plt.close(fig)
    metrics=dict(capture_sha256=manifest['capture_1024.csv']['sha256'],
                 captured_samples=count,phase_difference_estimates=len(measured),
                 captured_first_last_span_us=span,configured_sample_slots_us=config.length/fs*1e6,
                 full_first_last_span_us=float(t[-1]),start_frequency_hz=float(f[0]),
                 last_captured_word_frequency_hz=float(f[count-1]),
                 full_last_word_frequency_hz=float(f[-1]),
                 frequency_estimate_error_rms_hz=float(np.sqrt(np.mean((measured-f[:count-1])**2))),
                 iq_mismatches=iq_mismatches,alignment_offset=0)
    (output/'chirp_frequency_metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    print(json.dumps(metrics,indent=2))
    print(destination)


if __name__=='__main__':
    main()
