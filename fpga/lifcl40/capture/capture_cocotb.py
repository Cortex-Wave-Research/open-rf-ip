import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def capture_and_read(d):
    async def cycles(n=1):
        for _ in range(n):
            d.clk.value=0; await Timer(5,unit='ns')
            d.clk.value=1; await Timer(5,unit='ns')
    async def reset():
        d.rst.value=1; d.scl.value=1; d.master_low.value=0
        d.valid.value=0; d.chirp_start.value=0; d.chirp_end.value=0
        d.i_sample.value=0; d.q_sample.value=0
        await cycles(8); d.rst.value=0; await cycles(8)
    # 20 system clocks per half I2C bit: faster than planned 240, ample CDC margin.
    async def start():
        d.scl.value=0; d.master_low.value=0; await cycles(20)
        d.scl.value=1; await cycles(20)
        d.master_low.value=1; await cycles(20)
        d.scl.value=0; await cycles(20)
    async def stop():
        d.scl.value=0; d.master_low.value=1; await cycles(20)
        d.scl.value=1; await cycles(20)
        d.master_low.value=0; await cycles(20)
    async def send(value, ack=True):
        for bit in range(7,-1,-1):
            d.scl.value=0; d.master_low.value=not bool(value & (1<<bit)); await cycles(20)
            d.scl.value=1; await cycles(20)
        d.scl.value=0; d.master_low.value=0; await cycles(20)
        d.scl.value=1; await cycles(20)
        assert (int(d.sda.value)==0) == ack
        d.scl.value=0; await cycles(20)
    async def receive(more):
        value=0
        d.master_low.value=0
        for _ in range(8):
            d.scl.value=0; await cycles(20)
            d.scl.value=1; await cycles(20)
            value=(value<<1)|int(d.sda.value)
        d.scl.value=0; d.master_low.value=more; await cycles(20)
        d.scl.value=1; await cycles(20)
        d.scl.value=0; await cycles(20)
        d.master_low.value=0
        return value
    async def read(offset, count):
        await start(); await send(0x54); await send(offset>>8); await send(offset&255)
        await start(); await send(0x55)
        data=bytes([await receive(i<count-1) for i in range(count)])
        await stop()
        return data
    await reset()
    assert (await read(0,16)) == b'RFC1\x01\x00\x00\x04\x04\x0e'+bytes(6)
    await start(); await send(0x52,False); await stop() # wrong address NACK
    # A gap must fail closed, not silently skip a sample.
    d.valid.value=1; d.chirp_start.value=1; await cycles()
    d.valid.value=0; d.chirp_start.value=0; await cycles()
    assert int(d.error.value)==1 and int(d.done.value)==0
    await reset()
    expected=bytearray()
    for k in range(1024):
        i=(k*97)%16384-8192; q=(k*53+16383)%16384-8192
        d.i_sample.value=i; d.q_sample.value=q; d.valid.value=1
        d.chirp_start.value=(k==0); d.chirp_end.value=(k==1023)
        expected += ((i&16383)|((q&16383)<<14)|(1<<28)|((k==0)<<29)|((k==1023)<<30)).to_bytes(4,'little')
        await cycles()
    assert int(d.done.value)==1 and int(d.error.value)==0
    # Keep valid asserted and change tap data; captured RAM must stay frozen.
    d.i_sample.value=123; d.q_sample.value=-456
    await cycles(40)
    assert (await read(0,16)) == b'RFC1\x01\x01\x00\x04\x04\x0e'+bytes(6)
    result=bytearray()
    for offset in range(0,4096,64): result += await read(16+offset,64)
    assert result==expected
    assert await read(16+1020,12)==expected[1020:1032] # crosses RAM address boundary
    assert await read(4112,4)==bytes(4)
    assert await read(16,8)==expected[:8] # NACK/STOP and new transaction
