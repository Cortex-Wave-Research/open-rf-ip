"""Versioned pure offline decoder. RFC1 delegates to the unchanged proven decoder."""
from fpga.lifcl40.capture.read_capture import decode as decode_rfc1


def image_size(header):
    if len(header) != 16:
        raise ValueError('capture header must be 16 bytes')
    if header[:5] == b'RFC1\x01' and header[6:10] == b'\x00\x04\x04\x0e':
        size=4112
    elif header[:5] == b'RFC2\x02' and header[6:10] == b'\x00\x04\x05\x12':
        size=5136
    else:
        raise ValueError('unknown capture format/count/width')
    if header[5] != 1 or any(header[10:16]):
        raise ValueError('capture not complete, error or reserved header bits')
    return size


def decode(data):
    size=image_size(data[:16])
    if len(data) != size:
        raise ValueError('incorrect capture image size')
    if size == 4112:
        return decode_rfc1(data)
    rows=[]
    for k in range(1024):
        word=int.from_bytes(data[16+5*k:21+5*k],'little')
        if word>>39:
            raise ValueError('reserved record bit set')
        def signed(v): return v-(1<<18) if v&(1<<17) else v
        rows.append((k,signed(word&0x3ffff),signed((word>>18)&0x3ffff),
                     (word>>36)&1,(word>>37)&1,(word>>38)&1))
    if not all(row[3] for row in rows):
        raise ValueError('invalid sample')
    if rows[0][4] != 1 or any(row[4] for row in rows[1:]):
        raise ValueError('unexpected start markers')
    return rows
