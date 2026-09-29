"""Presentation diagnostics from the exact-comparison RTL capture, not a golden model.

Run: .venv/bin/python scripts/analyze_chirp.py
"""
from pathlib import Path
import os
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'build/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import spectrogram
from models.python.chirp import linear_config, word_frequency


def main():
    fs, n = 100_000_000, 10000
    config = linear_config(2_000_000, 20_000_000, fs, n)
    rows = np.genfromtxt(ROOT / 'reports/chirp/demo_rtl_samples.csv', delimiter=',', names=True)
    assert len(rows) == n and np.all(rows['valid'] == 1)
    assert np.array_equal(rows['phase_increment'], [config.word(k) for k in range(n)])
    z = rows['i'] + 1j * rows['q']
    phase = np.unwrap(np.angle(z))
    measured = np.diff(phase) * fs / (2*np.pi)
    commanded = rows['phase_increment'][:-1] * fs / (1 << 32)
    # The k-th difference spans samples k and k+1 and measures W[k].
    times = (np.arange(n-1)+0.5) / fs
    error = measured-commanded
    actual_start = word_frequency(config.start_word, fs)
    actual_end = word_frequency(config.word(n-1), fs)
    data = {
        'sample_rate_hz': fs, 'samples': n, 'duration_us': n/fs*1e6,
        'last_sample_time_us': (n-1)/fs*1e6,
        'requested_start_hz': 2_000_000, 'requested_end_hz': 20_000_000,
        'start_word': config.start_word, 'start_word_hex': f'0x{config.start_word:08x}',
        'signed_step': config.step, 'step_hex': f'0x{config.step:08x}',
        'final_word': config.word(n-1),
        'actual_start_hz': float(actual_start), 'actual_end_hz': float(actual_end),
        'actual_start_exact_hz': str(actual_start), 'actual_end_exact_hz': str(actual_end),
        'start_error_hz': float(actual_start-2_000_000),
        'end_error_hz': float(actual_end-20_000_000),
        'actual_step_hz_per_sample': float(word_frequency(config.step, fs)),
        'iq_frequency_error_rms_hz': float(np.sqrt(np.mean(error**2))),
        'iq_frequency_error_max_abs_hz': float(np.max(np.abs(error))),
        'iq_phase_differences': len(measured),
        'note': 'Last frequency word is verified digitally; no final I/Q interval is available in N samples.',
    }
    plots = ROOT / 'reports/plots'
    plots.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(10,5), layout='constrained')
    ax.plot(times*1e6, measured/1e6, lw=.5, alpha=.45, label='RTL I/Q unwrapped phase differences')
    ax.plot(times*1e6, commanded/1e6, lw=1.2, color='black', label='Exact applied frequency words')
    ax.set(xlabel='Interval midpoint (µs)', ylabel='Frequency (MHz)',
           title='10,000-sample linear chirp at 100 MS/s')
    ax.grid(alpha=.25)
    ax.legend()
    fig.savefig(plots / 'chirp_frequency_vs_time.png', dpi=160)
    plt.close(fig)
    f, t, s = spectrogram(z/8191, fs=fs, window='hann', nperseg=256, noverlap=224,
                           detrend=False, return_onesided=False, scaling='spectrum', mode='magnitude')
    order = np.argsort(f)
    f, s = f[order], s[order]
    selection = (f >= 0) & (f <= 25_000_000)
    db = 20*np.log10(np.maximum(s[selection], 1e-6))
    fig, ax = plt.subplots(figsize=(10,5), layout='constrained')
    mesh = ax.pcolormesh(t*1e6, f[selection]/1e6, db, shading='auto', vmin=-60, vmax=0)
    ax.set(xlabel='Time (µs)', ylabel='Frequency (MHz)', title='RTL I/Q spectrogram — Hann 256 samples, hop 32')
    fig.colorbar(mesh, ax=ax, label='Magnitude (dB relative to full scale)')
    fig.savefig(plots / 'chirp_spectrogram.png', dpi=160)
    plt.close(fig)
    (ROOT / 'reports/chirp/demo_config.json').write_text(json.dumps(data, indent=2)+'\n')
    print(json.dumps(data, indent=2))


if __name__ == '__main__':
    main()
