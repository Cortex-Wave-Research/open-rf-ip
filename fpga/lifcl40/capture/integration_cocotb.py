import cocotb
from cocotb.triggers import Timer
from models.python.chirp import ChirpModel, ChirpConfig

@cocotb.test()
async def exact_first_block(d):
    model=ChirpModel(); config=ChirpConfig(178956971,53692,10000,False)
    expected=[]
    d.scl.value=1; d.sda.value=1
    for cycle in range(1100):
        result=model.tick(config,start=True,rst=cycle<4)
        d.clk_12mhz.value=0; await Timer(41.667,unit='ns')
        d.clk_12mhz.value=1; await Timer(41.667,unit='ns')
        assert d.i_sample.value.to_signed()==result['i']
        assert d.q_sample.value.to_signed()==result['q']
        assert int(d.valid.value)==result['valid']
        assert int(d.chirp_start.value)==result['chirp_start']
        assert int(d.chirp_end.value)==result['chirp_end']
        if result['valid'] and len(expected)<1024:
            expected.append((result['i']&16383)|((result['q']&16383)<<14)|(1<<28)|(int(result['chirp_start'])<<29)|(int(result['chirp_end'])<<30))
    assert int(d.done.value)==1 and int(d.error.value)==0
    assert int(d.led0.value)==0 and int(d.led1.value)==1
    assert len(expected)==1024
    for k,word in enumerate(expected):
        assert int(d.store.ram[k].value)==word, f'capture record {k}'
