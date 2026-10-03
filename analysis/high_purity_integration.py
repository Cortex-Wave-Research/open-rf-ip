"""Production model spectral regression; same 72 coherent bins as Milestone 3.5.
Full grid is RTL-verified separately, linking model FFT results to production RTL.
No dither, windows, spur exclusions, phase fitting or captured-data LUT fitting.
"""
import json,os,sys
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from models.python.high_purity import phase_to_iq,linear_config
from models.python.nco_lut import lut_phase_to_iq
from models.python.chirp import linear_config as compact_config
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'build/mpl-m5'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=ROOT/'reports/high_purity_integration';FIG=OUT/'figures'
N=1<<20

def main():
    FIG.mkdir(parents=True,exist_ok=True)
    bins=sorted(set([1,3,17,1023,1024,1025,8191,32767,65535,104857,131071,174763,
                    209715,262143,262144,262145,393215,524285,524287]+
                   [1<<j for j in range(19)]+[3*(1<<j) for j in range(18)]+
                   np.random.default_rng(3501).integers(1,N//2,size=20).tolist()))
    assert len(bins)==72
    summaries={};tones=[];spectra={};errors={};traces={};endpoints={}
    for name,width,p,b,mapper in [('Compact',32,10,14,lut_phase_to_iq),('High-purity',64,16,18,phase_to_iq)]:
        iq=np.array([mapper(a<<(width-p)) for a in range(1<<p)],dtype=np.int64)
        table=(iq[:,0]+1j*iq[:,1])/((1<<(b-1))-1)
        def convert(ph):
            return table[(ph >> np.uint64(width-p)).astype(np.int64)]
        rr=[]
        for k in bins:
            phase=((np.arange(N,dtype=np.uint64)*np.uint64(k))&np.uint64(N-1))<<np.uint64(width-20)
            z=convert(phase)
            fft=abs(np.fft.fft(z))/N
            carrier=fft[k];normalized=fft/carrier
            fft[k]=0;spur=int(np.argmax(fft));ratio=float(fft[spur]/carrier)
            sfdr=-20*np.log10(max(ratio,1e-18))
            row=dict(mode=name,bin=k,tuning_word=str(k<<(width-20)),sfdr_db=float(sfdr),
                     spur_bin=spur,spur_resolved=ratio>1e-15)
            tones.append(row);rr.append(row)
            if k==104857: spectra[name]=normalized
        summaries[name]=dict(worst_sfdr_db=min(r['sfdr_db'] for r in rr),
                             median_sfdr_db=float(np.median([r['sfdr_db'] for r in rr])),
                             unresolved_tones=sum(not r['spur_resolved'] for r in rr))
        ph=(np.arange(1<<p,dtype=np.uint64)<<np.uint64(width-p))+np.uint64((1<<(width-p))-1)
        e=np.angle(convert(ph)*np.exp(-2j*np.pi*ph.astype(float)/(1<<width)))
        rng=np.random.default_rng(3502);ph=rng.integers(0,1<<width,size=N,dtype=np.uint64)
        er=np.angle(convert(ph)*np.exp(-2j*np.pi*ph.astype(float)/(1<<width)))
        errors[name]=dict(max_phase_error_rad=float(abs(e).max()),rms_phase_error_rad=float(np.sqrt(np.mean(er**2))))
        # Same continuous phase trajectory for visual comparison.
        phase=np.arange(N,dtype=np.uint64)<<np.uint64(width-20)
        traces[name]=np.angle(convert(phase)*np.exp(-2j*np.pi*np.arange(N)/N))
        c=(linear_config if width==64 else compact_config)(2_000_000,20_000_000,100_000_000,10000)
        start=Fraction(c.start_word*100_000_000,1<<width)
        final=Fraction(c.word(9999)*100_000_000,1<<width)
        endpoints[name]=dict(requested_start_hz=2000000,requested_stop_hz=20000000,
                            start_word=str(c.start_word),step_word=str(c.step),
                            actual_start_hz=float(start),actual_final_hz=float(final),
                            start_error_hz=float(start-2000000),endpoint_error_hz=float(final-20000000),
                            endpoint_error_exact=str(final-20000000))
        print(name,summaries[name],errors[name],flush=True)
    assert summaries['High-purity']['worst_sfdr_db']>90
    result=dict(method='72 coherent complex tones, N=2^20, rectangular FFT, all noncarrier bins searched; no dither',
                n=N,bins=bins,summaries=summaries,phase_errors=errors,endpoints=endpoints,tones=tones)
    (OUT/'spectral.json').write_text(json.dumps(result,indent=2)+'\n')
    np.savez_compressed(OUT/'spectra.npz',**spectra)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,'axes.spines.right':False})
    colors={'Compact':'#bd5218','High-purity':'#1464a0'}
    fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
    for ax,name in zip(axes,colors):
        spec=spectra[name];stats=next(r for r in tones if r['mode']==name and r['bin']==104857)
        ax.plot(np.fft.fftshift(np.fft.fftfreq(N)),np.fft.fftshift(20*np.log10(np.maximum(spec,1e-9))),lw=.65,color=colors[name])
        ax.set(ylim=(-150,5),ylabel='Normalized spectrum (dBc)',title=f'{name} — representative tone SFDR {stats["sfdr_db"]:.2f} dBc')
        ax.grid(alpha=.2)
    axes[-1].set_xlabel('Frequency / sample rate')
    fig.suptitle('Production NCO Digital Spectrum Comparison',fontsize=20,fontweight='bold')
    fig.text(.1,.015,'Equivalent coherent tone: bin 104857 / 2²⁰ • Model spectra; full mapper grid verified against production RTL • Dither OFF',fontsize=10)
    fig.tight_layout(rect=(0,.05,1,.95));fig.savefig(FIG/'compact_vs_high_purity_spectrum.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
    for ax,name in zip(axes,colors):
        ax.plot(np.arange(4096)/N*360,traces[name][:4096]*1e6,color=colors[name],lw=1)
        ax.set(ylabel='Phase error (µrad)',title=f'{name} — boundary max {errors[name]["max_phase_error_rad"]*1e6:.2f} µrad; random RMS {errors[name]["rms_phase_error_rad"]*1e6:.2f} µrad')
        ax.grid(alpha=.2)
    axes[-1].set_xlabel('Ideal phase (degrees; zoom near zero)')
    fig.suptitle('Production NCO Phase Error',fontsize=20,fontweight='bold')
    fig.text(.1,.015,'Error relative to ideal accumulator phase • Separate vertical scales • Deterministic phase/amplitude quantization',fontsize=10)
    fig.tight_layout(rect=(0,.05,1,.95));fig.savefig(FIG/'phase_error_comparison.png',dpi=180);plt.close(fig)

if __name__=='__main__':main()
