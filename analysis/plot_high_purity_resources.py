"""Render measured production architecture/cost table from current build results."""
import json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'build/mpl-m5'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=ROOT/'reports/high_purity_integration'

def main():
    impl=json.loads((OUT/'implementation.json').read_text())
    spec=json.loads((OUT/'spectral.json').read_text())
    compact=impl['0']['100'];hp=impl['1']['100']
    a,b=compact['utilization'],hp['utilization']
    def dsp(u):return sum(v for k,v in u.items() if k.startswith('MULT'))
    rows=[['Phase accumulator','32 bits','64 bits'],['Effective phase address','10 bits','16 bits'],
          ['Signed I/Q','14 bits','18 bits'],['Logical ROM','1024 × 14 full-wave','16384 × 17 quarter-wave'],
          ['Pipeline stages','1','2'],['COMB sites',str(a['OXIDE_COMB']),str(b['OXIDE_COMB'])],
          ['Fabric FF',str(a['OXIDE_FF']),str(b['OXIDE_FF'])],['EBR blocks',str(a['OXIDE_EBR']),str(b['OXIDE_EBR'])],
          ['DSP blocks',str(dsp(a)),str(dsp(b))],['Routed Fmax',f'{compact["fmax_mhz"]:.2f} MHz',f'{hp["fmax_mhz"]:.2f} MHz'],
          ['100 MHz setup slack',f'{compact["slack_ns"]:+.3f} ns',f'{hp["slack_ns"]:+.3f} ns'],
          ['Worst measured digital SFDR',f'{spec["summaries"]["Compact"]["worst_sfdr_db"]:.2f} dBc',f'{spec["summaries"]["High-purity"]["worst_sfdr_db"]:.2f} dBc']]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12})
    fig,ax=plt.subplots(figsize=(12,8.2));ax.axis('off')
    fig.subplots_adjust(left=.04,right=.96,bottom=.16,top=.80)
    fig.suptitle('Production NCO Architecture & Measured Resources',fontsize=21,fontweight='bold',y=.96)
    fig.text(.055,.88,'LIFCL-40-9BG400C • Equivalent Fs/12 NCO-only harnesses • Yosys / nextpnr-nexus • Seed 1',fontsize=12)
    table=ax.table(cellText=rows,colLabels=['Metric','Compact','High-purity'],cellLoc='left',colLoc='left',bbox=[0,0,1,1],colWidths=[.42,.27,.31])
    table.auto_set_font_size(False);table.set_fontsize(12)
    for (r,c),cell in table.get_celld().items():
        cell.set_edgecolor('#d6e0e7');cell.PAD=.13
        if r==0:
            cell.set_facecolor('#203f59');cell.set_text_props(color='white',weight='bold')
        else:cell.set_facecolor('#eef4f8' if r%2 else 'white')
    fig.text(.055,.09,'SFDR: 72 coherent tones, 2²⁰ samples each, all noncarrier bins searched; dither OFF.\nTiming is a routed estimate for constant-control harnesses, not a hardware maximum or full programmable-interface claim.',fontsize=10,linespacing=1.6)
    fig.text(.055,.035,'Compact and high-purity physical digital captures: bit-exact validated. No analog/RF claim.',fontsize=10,fontweight='bold')
    fig.savefig(OUT/'figures/architecture_resources.png',dpi=180,facecolor='white');plt.close(fig)

if __name__=='__main__':main()
