import json
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
from models.python.high_purity import HighPurityChirp,linear_config
from fpga.lifcl40.capture.capture_format import decode

@cocotb.test()
async def first_block(d):
    model=HighPurityChirp();config=linear_config(500000,2000000,12000000,10000)
    expected=[]
    d.scl.value=1;d.sda.value=1
    for cycle in range(1150):
        r=model.tick(config,start=True,rst=cycle<4)
        d.clk_12mhz.value=0;await Timer(41.667,unit='ns')
        d.clk_12mhz.value=1;await Timer(41.667,unit='ns')
        assert d.i_sample.value.to_signed()==r['i']
        assert d.q_sample.value.to_signed()==r['q']
        assert int(d.valid.value)==r['valid']
        assert int(d.chirp_start.value)==r['chirp_start']
        assert int(d.chirp_end.value)==r['chirp_end']
        if r['valid'] and len(expected)<1024:
            expected.append((r['i']&262143)|((r['q']&262143)<<18)|(1<<36)|(int(r['chirp_start'])<<37)|(int(r['chirp_end'])<<38))
    assert int(d.done.value)==1 and int(d.error.value)==0
    assert int(d.led0.value)==0 and int(d.led1.value)==1
    assert len(expected)==1024
    actual=[int(d.store.ram[k].value) for k in range(1024)]
    assert actual==expected
    data=b'RFC2\x02\x01\x00\x04\x05\x12'+bytes(6)+b''.join(w.to_bytes(5,'little') for w in actual)
    rows=decode(data)
    assert rows[0]==(0,131071,0,1,1,0)
    assert all(row[5]==0 for row in rows)
    root=Path(__file__).resolve().parents[3]
    out=root/'reports/high_purity_integration'
    out.mkdir(parents=True,exist_ok=True)
    (out/'simulated_rfc2.bin').write_bytes(data)
    (out/'capture_simulation.json').write_text(json.dumps(dict(source='RTL SIMULATION, NOT PHYSICAL CAPTURE',records=1024,mismatches=0,start_word=str(config.start_word),step_word=str(config.step)),indent=2)+'\n')
