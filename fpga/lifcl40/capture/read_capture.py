"""Board-specific frozen capture reader. Hardware access occurs only with --url.
Offline: read_capture.py --input snapshot.bin --output capture.csv
"""
import argparse
import csv
from pathlib import Path

SIZE = 4112

def decode(data):
    if len(data) != SIZE:
        raise ValueError(f'expected {SIZE} bytes, got {len(data)}')
    if data[:5] != b'RFC1\x01' or data[6:10] != b'\x00\x04\x04\x0e' or any(data[10:16]):
        raise ValueError('unknown capture header')
    if data[5] != 1:
        raise ValueError(f'capture not complete or capture error: status={data[5]:#x}')
    rows=[]
    for index in range(1024):
        word=int.from_bytes(data[16+4*index:20+4*index], 'little')
        if word>>31: raise ValueError('reserved record bit set')
        i=word&0x3fff; q=(word>>14)&0x3fff
        rows.append((index, i-16384 if i&8192 else i, q-16384 if q&8192 else q,
                     (word>>28)&1, (word>>29)&1, (word>>30)&1))
    if not all(row[3] for row in rows): raise ValueError('invalid sample in capture')
    if rows[0][4] != 1 or any(row[4] for row in rows[1:]):
        raise ValueError('unexpected chirp start markers')
    return rows

def read_hardware(url):
    from pyftdi.i2c import I2cController
    controller=I2cController()
    try:
        controller.configure(url, frequency=25000)
        target=controller.get_port(0x2a)
        def block(offset, length):
            return bytes(target.exchange(offset.to_bytes(2,'big'),length))
        header=block(0,16)
        if header[:5] != b'RFC1\x01' or header[5] != 1:
            raise ValueError('capture signature/status not ready; no sample file saved')
        def snapshot():
            return b''.join(block(offset,min(64,SIZE-offset)) for offset in range(0,SIZE,64))
        first=snapshot(); second=snapshot()
        if first!=second: raise ValueError('two reads disagree; no sample file saved')
        decode(first)
        return first
    finally:
        controller.terminate()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--input',type=Path)
    source.add_argument('--url',help='explicit FTDI interface-2 URL; performs I2C transactions')
    p.add_argument('--output',type=Path,default=Path('reports/hardware_capture/capture_1024.csv'))
    args=p.parse_args()
    if args.url and not args.url.endswith('/2'): p.error('only FTDI channel B (interface /2) is allowed')
    data=args.input.read_bytes() if args.input else read_hardware(args.url)
    rows=decode(data)
    binary=args.output.with_suffix('.bin')
    if args.output.exists() or binary.exists():
        raise FileExistsError('output CSV or binary already exists; choose another --output')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',newline='') as f:
        w=csv.writer(f); w.writerow(['index','I','Q','valid','chirp_start','chirp_end']); w.writerows(rows)
    binary.write_bytes(data)
    print(f'Saved 1024 samples to {args.output}; no numerical correctness claim')
if __name__=='__main__': main()
