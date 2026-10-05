"""Classic bus master and independent edge scoreboard, shared by control tests."""
from cocotb.triggers import Timer
from models.python.control_plane import ControlPlane
from models.python import control_registers as R

class Bus:
    def __init__(self,d,hp,kind,waveform=False):
        self.d=d;self.model=ControlPlane(hp,kind);self.waveform=waveform
        self.cycles=0;self.starts=0;self.busy=False;self.completion=False
        self.samples=[];self.transaction=False;self.previous=None
        if waveform:
            from models.python.high_purity import HighPurityNCO,HighPurityChirp
            from models.python.nco_lut import LutNCO
            from models.python.chirp import ChirpModel
            self.engine=(HighPurityChirp() if hp else ChirpModel()) if kind else (HighPurityNCO() if hp else LutNCO())
        d.wb_clk_i.value=0;d.wb_rst_i.value=0
        self.idle_signals()
        if not waveform:d.engine_busy_i.value=0;d.engine_done_i.value=0

    def idle_signals(self):
        for name in ('wb_cyc_i','wb_stb_i','wb_we_i','wb_adr_i','wb_dat_i','wb_sel_i'):
            getattr(self.d,name).value=0

    async def tick(self,request=None,reset=False):
        d=self.d;m=self.model
        d.wb_clk_i.value=0;d.wb_rst_i.value=int(reset)
        if not self.waveform:
            d.engine_busy_i.value=int(self.busy);d.engine_done_i.value=int(self.completion)
        await Timer(5,unit='ns')
        if self.waveform:
            enable=m.run and m.valid
            if m.kind:
                from models.python.high_purity import HighPurityConfig
                from models.python.chirp import ChirpConfig
                step=m.pair(R.ADDR_CHIRP_STEP_LO,True)
                if step & (1<<63):step-=1<<64
                cfg=(HighPurityConfig if m.hp else ChirpConfig)(m.pair(R.ADDR_CHIRP_START_LO,True),step,m.active[R.ADDR_CHIRP_LENGTH],bool(m.active[R.ADDR_CHIRP_CONFIG]&1))
                busy=self.transaction
                completion=bool(self.previous and self.previous['valid'] and self.previous['chirp_end'])
                expected=self.engine.tick(cfg,start=m.start,enable=enable,rst=reset)
                if reset:self.transaction=False
                else:
                    if completion and not cfg.repeat:self.transaction=False
                    if m.start:self.transaction=True
            else:
                busy=enable;completion=False
                i,q,valid=self.engine.tick(m.pair(R.ADDR_NCO_PHASE_INC_LO,True),enable=enable,rst=reset)
                expected=dict(i=i,q=q,valid=valid,chirp_start=False,chirp_end=False)
            self.previous=expected
        else:busy=self.busy;completion=self.completion
        result=m.tick(request,busy=busy,completion=completion,reset=reset)
        d.wb_clk_i.value=1
        await Timer(5,unit='ns')
        self.cycles+=1;self.starts+=int(m.start)
        assert not (int(d.wb_ack_o.value) and int(d.wb_err_o.value))
        if self.waveform:
            for key,port in [('i','i_out'),('q','q_out'),('valid','sample_valid'),('chirp_start','chirp_start'),('chirp_end','chirp_end')]:
                actual=getattr(d,port).value.to_signed() if key in ('i','q') else int(getattr(d,port).value)
                assert actual==expected[key],(self.cycles,key,actual,expected)
            phase_path = 'high_purity.nco.phase' if m.hp else ('compact.chirp.nco.phase' if m.kind else 'compact.nco.phase')
            assert int(d.engine[phase_path].value)==self.engine.phase, (self.cycles,'phase')
            if expected['valid']:self.samples.append(expected.copy())
        else:
            for port,expected in [('active_nco_o',m.pair(R.ADDR_NCO_PHASE_INC_LO,True)),
                                  ('active_start_o',m.pair(R.ADDR_CHIRP_START_LO,True)),
                                  ('active_step_o',m.pair(R.ADDR_CHIRP_STEP_LO,True)),
                                  ('active_length_o',m.active[R.ADDR_CHIRP_LENGTH]),
                                  ('active_repeat_o',m.active[R.ADDR_CHIRP_CONFIG]&1),
                                  ('start_o',m.start),('run_enable_o',m.run),('config_valid_o',m.valid)]:
                assert int(getattr(d,port).value)==expected,(self.cycles,port,expected)
        return result

    async def reset(self):
        self.idle_signals();await self.tick(reset=True);await self.tick();self.samples=[]

    async def access(self,address,write=False,value=0,select=15,hold_cycle=False):
        d=self.d
        d.wb_cyc_i.value=1;d.wb_stb_i.value=1;d.wb_we_i.value=int(write)
        d.wb_adr_i.value=address;d.wb_dat_i.value=value&0xffffffff;d.wb_sel_i.value=select
        await self.tick() # A: adapter captures; no CSR side effect
        assert not int(d.wb_ack_o.value) and not int(d.wb_err_o.value)
        result=await self.tick((address,write,value&0xffffffff,select)) # B: execute
        assert (int(d.wb_ack_o.value),int(d.wb_err_o.value))==(int(not result[1]),int(result[1]))
        if not write and not result[1]:assert int(d.wb_dat_o.value)==result[0],(address,int(d.wb_dat_o.value),result)
        # C: master samples termination; STB still high must not execute twice.
        await self.tick()
        assert not int(d.wb_ack_o.value) and not int(d.wb_err_o.value)
        if not hold_cycle:self.idle_signals()
        return result

    async def write(self,a,v,sel=15,**kw):return await self.access(a,True,v,sel,**kw)
    async def command(self,c):return await self.write(R.ADDR_COMMAND,c)
    async def pair(self,a,value,high_first=False):
        halves=[(a,value&0xffffffff),(a+4,(value>>32)&0xffffffff)]
        for addr,v in reversed(halves) if high_first else halves:await self.write(addr,v)
