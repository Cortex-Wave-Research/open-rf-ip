"""Explicit opt-in hardware reader for RFC1/RFC2. --input is entirely offline."""
import argparse,csv
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from fpga.lifcl40.capture.capture_format import decode,image_size


def read_hardware(url):
    from pyftdi.i2c import I2cController
    controller=I2cController()
    try:
        controller.configure(url,frequency=25000)
        target=controller.get_port(0x2a)
        def block(offset,length):
            return bytes(target.exchange(offset.to_bytes(2,'big'),length))
        size=image_size(block(0,16))
        def snapshot():
            return b''.join(block(offset,min(64,size-offset)) for offset in range(0,size,64))
        first=snapshot();second=snapshot()
        if first != second:
            raise ValueError('two reads disagree')
        decode(first)
        return first
    finally:
        controller.terminate()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--input',type=Path)
    g.add_argument('--url')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.url and not a.url.endswith('/2'): p.error('only FTDI channel B /2 allowed')
    binary=a.output.with_suffix('.bin')
    if a.output.exists() or binary.exists():
        raise FileExistsError('preserving existing evidence; choose new output paths')
    data=a.input.read_bytes() if a.input else read_hardware(a.url)
    rows=decode(data)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',newline='') as f:
        w=csv.writer(f);w.writerow(['index','I','Q','valid','chirp_start','chirp_end']);w.writerows(rows)
    with binary.open('xb') as f: f.write(data)
    print(f'Saved {len(rows)} samples; {data[:4].decode()}; no numerical correctness claim')

if __name__=='__main__':main()
