import os,json
from pathlib import Path
import cocotb
from verification.cocotb.control_bus import Bus
from models.python import control_registers as R

@cocotb.test()
async def exact_controlled_waveform(d):
    hp=int(os.environ['HP']);kind=int(os.environ['KIND']);b=Bus(d,hp,kind,True)
    width=64 if hp else 32
    await b.reset()
    # All configuration and runtime controls go through Wishbone/CSR.
    from models.python.high_purity import linear_config as hcfg
    from models.python.chirp import linear_config as ccfg
    cfg=(hcfg if hp else ccfg)(2_000_000,20_000_000,100_000_000,10000)
    async def configure(start=cfg.start_word,step=cfg.step,length=10000,repeat=0):
        await b.write(R.ADDR_MODE,kind)
        await b.pair(R.ADDR_NCO_PHASE_INC_LO,(1<<width)//10,True)
        await b.pair(R.ADDR_CHIRP_START_LO,start)
        await b.pair(R.ADDR_CHIRP_STEP_LO,step%(1<<64),True)
        await b.write(R.ADDR_CHIRP_LENGTH,length)
        await b.write(R.ADDR_CHIRP_CONFIG,repeat)
        await b.command(R.CMD_COMMIT)
        assert b.model.valid and not b.model.dirty
    await configure()
    await b.write(R.ADDR_RUN_CONTROL,1)
    if kind:await b.command(R.CMD_START)
    while len(b.samples)<137:await b.tick()
    # Pause first. State may advance at the CSR execution edge with old enable;
    # the following engine edge must freeze, exactly as the existing model.
    await b.write(R.ADDR_RUN_CONTROL,0)
    phase=b.engine.phase;before=b.model.active.copy();n=len(b.samples)
    await b.pair(R.ADDR_CHIRP_START_LO,17)
    await b.access(R.ADDR_IP_ID);await b.write(R.ADDR_SCRATCH,0x81234567)
    await b.access(R.ADDR_SCRATCH)
    assert b.engine.phase==phase and len(b.samples)==n and b.model.active==before
    assert b.model.dirty
    if kind:
        await b.command(R.CMD_COMMIT)
        assert b.model.active==before and b.model.errors & R.ERR_COMMIT_WHILE_BUSY
        await b.command(R.CMD_START)
        assert b.model.errors & R.ERR_START_WHILE_BUSY
    # Dirty shadow must not gate an already-running active waveform.
    await b.write(R.ADDR_RUN_CONTROL,1)
    while len(b.samples)<10000:await b.tick()
    main=list(b.samples[:10000])
    if kind:
        assert len(b.samples)==10000
        assert sum(r['chirp_start'] for r in main)==1 and sum(r['chirp_end'] for r in main)==1
        for _ in range(4):await b.tick()
        assert b.model.done and not b.transaction
        await b.access(R.ADDR_STATUS)
        await b.command(R.CMD_START) # dirty must not implicitly commit
        assert b.model.errors & R.ERR_START_WITH_DIRTY_CONFIG
        assert len(b.samples)==10000
    else:
        await b.command(R.CMD_START)
        assert b.model.errors & R.ERR_BAD_COMMAND and not b.model.done
    await b.write(R.ADDR_RUN_CONTROL,0)
    # Restart phase continuity, signed extremes, wrap, short lengths and repeat.
    if kind:
        for length,step,repeat in [(1,0,0),(2,-1,0),(17,-(1<<(width-1)),0),(19,(1<<(width-1))-1,0),(11,-7,1),(2,0,1),(1,0,1)]:
            if b.transaction:await b.reset() # only reset aborts repeat
            await configure((1<<width)-3,step,length,repeat)
            count=len(b.samples)
            await b.write(R.ADDR_RUN_CONTROL,1);await b.command(R.CMD_START)
            while len(b.samples)-count<length*(3 if repeat else 1):await b.tick()
            for _ in range(4):await b.tick()
            await b.write(R.ADDR_RUN_CONTROL,0)
        # Length-zero is rejected before any engine start.
        await b.reset();await b.write(R.ADDR_CHIRP_LENGTH,0);await b.command(R.CMD_COMMIT)
        assert not b.model.valid and b.model.errors & R.ERR_INVALID_CONFIGURATION
        # Explicit pending final-sample pause with HP length 2.
        await configure(123,-5,2,0)
        await b.write(R.ADDR_RUN_CONTROL,1)
        # A/B/C of START leaves engine at acceptance at C, no output yet.
        await b.command(R.CMD_START)
        # RUN=0 executes after two more edges; HP scheduler ends at B but final
        # output remains pending when disable takes effect at C.
        await b.write(R.ADDR_RUN_CONTROL,0)
        if hp:
            assert b.transaction and not b.engine.busy and b.engine.pending is not None
            before=b.model.active.copy();await b.command(R.CMD_COMMIT)
            assert b.model.active==before and b.model.errors & R.ERR_COMMIT_WHILE_BUSY
            await b.command(R.CMD_START);assert b.model.errors & R.ERR_START_WHILE_BUSY
            await b.write(R.ADDR_RUN_CONTROL,1)
            for _ in range(4):await b.tick()
            assert b.model.done and not b.transaction
    else:
        for word in (0,1,(1<<width)-1,1<<(width-1)):
            await b.pair(R.ADDR_NCO_PHASE_INC_LO,word)
            await b.command(R.CMD_COMMIT)
            await b.write(R.ADDR_RUN_CONTROL,1)
            for _ in range(31):await b.tick()
            await b.write(R.ADDR_RUN_CONTROL,0)
    await b.reset()
    out=Path(os.environ['PROJECT_ROOT'])/'reports/control_plane';out.mkdir(parents=True,exist_ok=True)
    (out/f'waveform-{hp}-{kind}.json').write_text(json.dumps(dict(profile=hp,engine_kind=kind,cycles=b.cycles,main_samples=len(main),I_mismatches=0,Q_mismatches=0,valid_mismatches=0,chirp_start_mismatches=0,chirp_end_mismatches=0,alignment_search=False,pause_phase_continuity=True,configuration_via_csr_only=True),indent=2)+'\n')
