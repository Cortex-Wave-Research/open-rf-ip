import csv,json,os,random
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
from models.python.high_purity import HighPurityNCO,HighPurityChirp,HighPurityConfig,linear_config as hp_config
from models.python.nco_lut import LutNCO
from models.python.chirp import ChirpModel,ChirpConfig,linear_config as compact_config

@cocotb.test()
async def exact(d):
    hp=bool(int(os.environ['MODE'])); width=64 if hp else 32; mask=(1<<width)-1
    root=Path(os.environ['PROJECT_ROOT']); out=root/'reports/high_purity_integration'
    out.mkdir(parents=True,exist_ok=True)
    rng=random.Random(5001)
    if os.environ['MODE_TOP']=='rf_nco_mode':
        m=HighPurityNCO() if hp else LutNCO()
        cycles=0
        async def tick(w=0,enable=True,rst=False):
            nonlocal cycles
            d.clk.value=0;d.rst.value=rst;d.enable.value=enable;d.phase_increment.value=w
            await Timer(5,unit='ns')
            r=m.tick(w,enable=enable,rst=rst)
            d.clk.value=1;await Timer(5,unit='ns')
            assert (d.i_out.value.to_signed(),d.q_out.value.to_signed(),bool(d.sample_valid.value))==r
            assert int(d["high_purity.nco.phase" if hp else "compact.nco.phase"].value)==m.phase
            cycles+=1
        await tick(rst=True)
        # All mapper addresses, cardinal endpoints and wrap; no phase injection.
        for _ in range((1<<(16 if hp else 10))+2): await tick(1<<(width-(16 if hp else 10)))
        tones=[0,1,(1<<(width-1))-1,1<<(width-1),mask,
               104857<<(width-20),3<<(width-4),int('051eb851eb851eb8',16)&mask,
               1024<<(width-20),8<<(width-20)]
        for w in tones:
            await tick(rst=True)
            for _ in range(10002): await tick(w)
        for k in range(12000):
            await tick(rng.getrandbits(width),enable=k%7!=0,rst=k in (99,901,11998))
        (out/f'nco_exact_{int(hp)}.json').write_text(json.dumps(dict(cycles=cycles,tones=[str(x) for x in tones],iq_valid_phase_mismatches=0,full_address_grid=True),indent=2)+'\n')
        return
    m=HighPurityChirp() if hp else ChirpModel()
    Config=HighPurityConfig if hp else ChirpConfig
    linear=hp_config if hp else compact_config
    default=Config(0,0,0); cycles=0
    async def tick(c=default,start=False,enable=True,rst=False):
        nonlocal cycles
        d.clk.value=0;d.rst.value=rst;d.enable.value=enable;d.start.value=start
        d.start_phase_inc.value=c.start_word;d.chirp_step.value=c.step
        d.chirp_length.value=c.length;d.repeat_mode.value=c.repeat
        await Timer(5,unit='ns')
        r=m.tick(c,start=start,enable=enable,rst=rst)
        d.clk.value=1;await Timer(5,unit='ns')
        for field,port in [('i','i_out'),('q','q_out')]:
            assert getattr(d,port).value.to_signed()==r[field],(cycles,field,r)
        for field,port in [('valid','sample_valid'),('chirp_start','chirp_start'),('chirp_end','chirp_end')]:
            assert bool(getattr(d,port).value)==r[field],(cycles,field,r)
        assert int(d.phase_increment.value)==m.current_word
        assert int(d.chirp_count.value)==m.index
        assert bool(d.busy.value)==m.busy
        assert int(d["high_purity.nco.phase" if hp else "compact.chirp.nco.phase"].value)==m.phase
        cycles+=1
        return r
    demo=linear(2_000_000,20_000_000,100_000_000,10000)
    await tick(rst=True)
    assert not (await tick(demo,start=True))['valid']
    rows=[]
    for _ in range(10002):
        r=await tick()
        if r['valid']: rows.append(r)
    assert len(rows)==10000
    with (out/f'chirp_10k_{int(hp)}.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    cases=[Config(1,0,0),Config(mask,-1,1),Config(mask,1,2),Config(mask,1,99),
           Config(7,-(1<<(width-1)),15),Config(mask,(1<<(width-1))-1,17),
           linear(20_000_000,2_000_000,100_000_000,10000),
           Config(1025,0,31),Config(mask,-53692,19,True),Config(0,0,1,True),
           Config(7,-9,2,True),Config(1,1,(1<<32)-1)]
    for c in cases:
        await tick(rst=True)
        await tick(c,start=True,enable=False) # not queued
        await tick(c,start=True)
        # Pause while first and last samples are pending; ignored busy config changes.
        for k in range(min(c.length+5,10010)*3):
            await tick(Config(mask,0,5),start=k%7==0,enable=k%5 not in (1,2))
        await tick(rst=True,enable=False)
    # Consecutive repeated 10000-sample chirps, no bubble after pipeline fill.
    rep=Config(demo.start_word,demo.step,10000,True)
    await tick(rst=True);await tick(rep,start=True)
    repeated=[]
    for _ in range(30000+int(hp)):
        r=await tick()
        if r['valid']: repeated.append(r)
    assert len(repeated)==30000
    assert sum(r['chirp_start'] for r in repeated)==3
    assert sum(r['chirp_end'] for r in repeated)==3
    # Random resets, pauses, signed extremes, changing and held starts/config.
    for k in range(6000):
        step=rng.getrandbits(width);step=step-(1<<width) if step>>(width-1) else step
        c=Config(rng.getrandbits(width),step,rng.choice([0,1,2,3,13,99]),bool(k%2))
        await tick(c,start=k%3==0,enable=k%7!=0,rst=k%151==0)
    physical_mismatches=None
    if not hp:
        c=Config(178956971,53692,10000,False)
        await tick(rst=True);await tick(c,start=True)
        with (root/'examples/physical_capture/capture_1024.csv').open() as f:
            capture=list(csv.DictReader(f))
        for h in capture:
            r=await tick()
            assert [int(h[k]) for k in ('I','Q','valid','chirp_start','chirp_end')]==[r[k] for k in ('i','q','valid','chirp_start','chirp_end')]
        physical_mismatches=0
    (out/f'chirp_exact_{int(hp)}.json').write_text(json.dumps(dict(cycles=cycles,demo_samples=10000,
        I_mismatches=0,Q_mismatches=0,valid_mismatches=0,chirp_start_mismatches=0,chirp_end_mismatches=0,
        phase_and_word_mismatches=0,physical_capture_mismatches=physical_mismatches,
        repeat_samples=len(repeated)),indent=2)+'\n')
