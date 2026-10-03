from pathlib import Path
import csv
import pytest
from fpga.lifcl40.capture.capture_format import decode,image_size

def fixture():
    header=b'RFC2\x02\x01\x00\x04\x05\x12'+bytes(6)
    words=[(1<<36)|(int(k==0)<<37)|(((-131072+k)&262143)<<18)|((131071-k)&262143) for k in range(1024)]
    return header+b''.join(w.to_bytes(5,'little') for w in words)

def test_signed18_and_rfc1_evidence():
    rows=decode(fixture())
    assert image_size(fixture()[:16])==5136
    assert rows[0]==(0,131071,-131072,1,1,0)
    assert rows[-1]==(1023,130048,-130049,1,0,0)
    root=Path(__file__).resolve().parents[3]
    data=(root/'examples/physical_capture/capture_1024.bin').read_bytes()
    with (root/'examples/physical_capture/capture_1024.csv').open() as f:
        saved=[tuple(map(int,r.values())) for r in csv.DictReader(f)]
    assert decode(data)==saved

@pytest.mark.parametrize('kind',['short','extra','magic','version','error','reserved','invalid','start','second_start','width','count','header_reserved'])
def test_reject(kind):
    data=bytearray(fixture())
    if kind=='short':data.pop()
    if kind=='extra':data.append(0)
    if kind=='magic':data[0]=0
    if kind=='version':data[4]=1
    if kind=='error':data[5]=3
    if kind=='reserved':data[20]|=128
    if kind=='invalid':data[20]&=239
    if kind=='start':data[20]&=223
    if kind=='second_start':data[25]|=32
    if kind=='width':data[9]=14
    if kind=='count':data[6]=1
    if kind=='header_reserved':data[15]=1
    with pytest.raises(ValueError):decode(data)
