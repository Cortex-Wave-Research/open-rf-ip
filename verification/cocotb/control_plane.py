import os,random,json
from pathlib import Path
import cocotb
from verification.cocotb.control_bus import Bus
from models.python import control_registers as R

@cocotb.test()
async def bus_and_atomicity(d):
    hp=int(os.environ['HP']);kind=int(os.environ['KIND']);b=Bus(d,hp,kind)
    await b.reset()
    for a in R.REGISTERS:await b.access(a)
    assert b.model.capabilities==((2 if hp else 1)|32|(24 if kind else 4))
    await b.write(R.ADDR_SCRATCH,0x12345678)
    for sel in range(16):await b.write(R.ADDR_SCRATCH,0xaabbccdd,sel,hold_cycle=True)
    b.idle_signals()
    for a in (1,2,3,0x11,0x45,0x48,0x7c,0x80,0xfffc):
        assert (await b.access(a))[1];assert (await b.write(a,0))[1]
    for a in (R.ADDR_IP_ID,R.ADDR_ABI_VERSION,R.ADDR_CAPABILITIES,R.ADDR_STATUS,R.ADDR_ERROR_STATUS,R.ADDR_CONFIG_SEQUENCE):
        assert (await b.write(a,0))[1]
    await b.access(R.ADDR_COMMAND)
    assert (await b.write(R.ADDR_RUN_CONTROL,2))[1]
    await b.write(R.ADDR_RUN_CONTROL,0xffffff00,0) # unselected reserved bits ignored
    await b.command(R.CMD_START)
    assert b.model.errors & R.ERR_START_WITHOUT_VALID_CONFIG
    for command in (0,3,5,6,7,8,0xffffffff):
        before=b.model.active.copy();seq=b.model.sequence
        await b.command(command);assert b.model.errors & R.ERR_BAD_COMMAND
        assert b.model.active==before and b.model.sequence==seq
    for sel in range(15):await b.write(R.ADDR_COMMAND,R.CMD_COMMIT,sel)
    await b.command(R.CMD_CLEAR_STATUS)
    assert b.model.errors==0
    await b.write(R.ADDR_CHIRP_LENGTH,2)
    # Dedicated all-three-pairs test, both write orders, edge-by-edge active checks.
    pairs=(R.ADDR_NCO_PHASE_INC_LO,R.ADDR_CHIRP_START_LO,R.ADDR_CHIRP_STEP_LO)
    for reverse in (False,True):
        for a in pairs:
            old=0xaaaaaaaaaaaaaaaa if hp else (0xffffffffaaaaaaaa if a==R.ADDR_CHIRP_STEP_LO else 0xaaaaaaaa)
            new=0xccccccccbbbbbbbb if hp else (0xffffffffbbbbbbbb if a==R.ADDR_CHIRP_STEP_LO else 0xbbbbbbbb)
            await b.pair(a,old);await b.command(R.CMD_COMMIT)
            assert b.model.pair(a,True)==old
            before=b.model.active.copy();seq=b.model.sequence
            halves=[(a,new&0xffffffff),(a+4,new>>32)]
            for addr,value in reversed(halves) if reverse else halves:
                await b.write(addr,value)
                assert b.model.active==before and b.model.dirty
            await b.command(R.CMD_COMMIT)
            assert b.model.pair(a,True)==new and b.model.sequence==seq+1
            assert not b.model.dirty and b.model.valid
    # Whole-configuration validation and atomic failure.
    for a,value in [(R.ADDR_MODE,1-kind),(R.ADDR_MODE,0x100),(R.ADDR_CHIRP_CONFIG,2)]+([(R.ADDR_CHIRP_LENGTH,0)] if kind else []):
        saved=b.model.shadow[a];before=b.model.active.copy();seq=b.model.sequence
        await b.write(a,value);await b.command(R.CMD_COMMIT)
        assert b.model.active==before and b.model.sequence==seq
        assert b.model.errors & R.ERR_INVALID_CONFIGURATION
        await b.write(a,saved)
    if not hp:
        for a,value in [(R.ADDR_NCO_PHASE_INC_HI,1),(R.ADDR_CHIRP_START_HI,1),(R.ADDR_CHIRP_STEP_HI,0)]:
            saved=b.model.shadow[a];before=b.model.active.copy()
            await b.write(a,value);await b.command(R.CMD_COMMIT)
            assert b.model.active==before and b.model.errors & R.ERR_INVALID_CONFIGURATION
            await b.write(a,saved)
    await b.command(R.CMD_COMMIT)
    await b.command(R.CMD_START) # disabled, never queued
    assert b.model.errors & R.ERR_START_WHILE_DISABLED
    await b.write(R.ADDR_RUN_CONTROL,1)
    b.busy=True
    before=b.model.active.copy();await b.command(R.CMD_COMMIT);await b.command(R.CMD_START)
    assert b.model.active==before and b.model.errors & R.ERR_COMMIT_WHILE_BUSY
    assert b.model.errors & R.ERR_START_WHILE_BUSY
    b.busy=False
    await b.write(R.ADDR_MODE,kind);await b.command(R.CMD_START)
    assert b.model.errors & R.ERR_START_WITH_DIRTY_CONFIG
    await b.command(R.CMD_COMMIT)
    starts=b.starts;await b.command(R.CMD_START)
    assert b.starts-starts==kind
    for _ in range(6):await b.tick()
    assert b.starts-starts==kind # pulse never a held start
    b.completion=True;await b.command(R.CMD_CLEAR_STATUS);b.completion=False
    assert b.model.done==bool(kind)
    await b.access(R.ADDR_STATUS);await b.command(R.CMD_CLEAR_STATUS)
    assert not b.model.done and not b.model.errors
    # Aborted request and reset during captured transaction cause no side effects.
    d.wb_cyc_i.value=1;d.wb_stb_i.value=1;d.wb_we_i.value=1
    d.wb_adr_i.value=R.ADDR_SCRATCH;d.wb_dat_i.value=0xfeedface;d.wb_sel_i.value=15
    await b.tick();b.idle_signals();await b.tick();await b.tick()
    await b.access(R.ADDR_SCRATCH)
    await b.write(R.ADDR_NCO_PHASE_INC_LO,123)
    assert b.model.dirty
    await b.reset()
    d.wb_cyc_i.value=1;d.wb_stb_i.value=1;d.wb_we_i.value=1
    d.wb_adr_i.value=R.ADDR_RUN_CONTROL;d.wb_dat_i.value=1;d.wb_sel_i.value=15
    await b.tick() # captured, not executed
    await b.tick(reset=True)
    b.idle_signals();await b.tick()
    assert not b.model.run and not int(d.wb_ack_o.value) and not int(d.wb_err_o.value)
    # Sequence rollover: inject only counter state, then exercise real command path.
    await b.write(R.ADDR_CHIRP_LENGTH,1)
    d.csr.sequence_number.value=0xffffffff;b.model.sequence=0xffffffff
    await b.command(R.CMD_COMMIT)
    await b.access(R.ADDR_CONFIG_SEQUENCE)
    assert b.model.sequence==0
    # Deterministic randomized protocol/state transitions, every active edge checked.
    rng=random.Random(6101)
    for _ in range(250):
        b.busy=bool(rng.randrange(4)==0);b.completion=bool(rng.randrange(20)==0)
        a=rng.choice(list(R.REGISTERS)+[0x48,1])
        await b.access(a,bool(rng.getrandbits(1)),rng.getrandbits(32),rng.randrange(16))
    b.busy=b.completion=False
    for a in R.REGISTERS:await b.access(a)
    out=Path(os.environ['PROJECT_ROOT'])/'reports/control_plane';out.mkdir(parents=True,exist_ok=True)
    (out/f'bus-{hp}-{kind}.json').write_text(json.dumps(dict(cycles=b.cycles,profile=hp,engine_kind=kind,atomic_pairs=3,write_orders=2,errors=0))+'\n')
