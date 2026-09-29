"""Verify retained NCO ROM and actual target timing before bitstream packing."""
import json
from pathlib import Path
from models.python.nco_lut import sine_table
from models.python.chirp import linear_config,word_frequency
D=Path('build/lifcl40')
synth=json.loads((D/'physical-synth.json').read_text())['modules']['physical_top']
roms=[c for c in synth['cells'].values() if c['type']=='DP16K']
assert len(roms)==1,'NCO ROM must survive optimization'
c=roms[0];p=c['parameters'];ports=c['connections']
assert p['DATA_WIDTH_A']==p['DATA_WIDTH_B']=='X18'
assert p['OUTREG_A']==p['OUTREG_B']=='BYPASSED'
assert ports['CLKA']==ports['CLKB']
zero=next(c['connections']['Z'] for c in synth['cells'].values() if c['type']=='VLO')
assert ports['WEA']==ports['WEB']==zero
assert synth['netnames']['q_sample']['bits']==ports['DOA'][:14]
assert synth['netnames']['i_sample']['bits']==ports['DOB'][:14]
chunks=[]
for j in range(64):
    v=int(p[f'INITVAL_{j:02X}'],16);chunks.extend((v>>(10*k))&511 for k in range(32))
words=[chunks[2*k]|chunks[2*k+1]<<9 for k in range(1024)]
assert words==[v&0x3fff for v in sine_table()]
r=json.loads((D/'timing.json').read_text());u=r['utilization']
assert u['OXIDE_EBR']['used']==1,'EBR must survive nextpnr pruning'
clock,t=next(iter(r['fmax'].items()));assert len(r['fmax'])==1
assert t['constraint']==12 and t['achieved']>12
cfg=linear_config(500000,2000000,12000000,10000,repeat=True)
out=dict(device='LIFCL-40-9BG400C',clock_hz=12000000,chirp_samples=10000,duration_seconds=10000/12000000,
 start_word=cfg.start_word,step=cfg.step,final_word=cfg.word(9999),start_hz=float(word_frequency(cfg.start_word,12000000)),final_hz=float(word_frequency(cfg.word(9999),12000000)),
 requested_start_hz=500000,requested_stop_hz=2000000,rom_words_checked=1024,rom_mismatches=0,utilization=u,
 routed_fmax_mhz=t['achieved'],worst_setup_slack_ns=1000/12-1000/t['achieved'])
(D/'analysis.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
