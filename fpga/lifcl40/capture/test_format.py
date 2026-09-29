import pytest
from fpga.lifcl40.capture.read_capture import decode

def fixture():
    header=b'RFC1\x01\x01\x00\x04\x04\x0e'+bytes(6)
    words=[(1<<28)|(int(k==0)<<29)|(((-8192+k)&16383)<<14)|((8191-k)&16383) for k in range(1024)]
    return header+b''.join(w.to_bytes(4,'little') for w in words)

def test_signs_and_indices():
    rows=decode(fixture())
    assert rows[0]==(0,8191,-8192,1,1,0)
    assert rows[-1]==(1023,7168,-7169,1,0,0)

@pytest.mark.parametrize('kind',['short','magic','error','reserved','invalid','start'])
def test_reject(kind):
    data=bytearray(fixture())
    if kind=='short': data.pop()
    if kind=='magic': data[0]=0
    if kind=='error': data[5]=3
    if kind=='reserved': data[19]|=128
    if kind=='invalid': data[19]&=239
    if kind=='start': data[19]&=223
    with pytest.raises(ValueError): decode(data)
