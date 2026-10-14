"""Offline RV32I build and final machine-instruction audit. No downloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def header():
    spec = json.loads((ROOT / 'spec/control_registers.json').read_text())
    values = {'OPENRF_BASE': 0x40000000, 'MAILBOX_BASE': 0x40010000,
              'IP_ID_VALUE': spec['ip_id'], 'ABI_VERSION_VALUE': spec['abi_version'],
              'RUN_ENABLE': 1, 'CHIRP_REPEAT': 1}
    values.update({'ADDR_' + r['name']: r['offset'] for r in spec['registers']})
    for group, prefix in [('commands', 'CMD_'), ('errors', 'ERR_'),
                          ('status', 'STATUS_'), ('capabilities', 'CAP_')]:
        values.update({prefix + k: 1 << v for k, v in spec[group].items()})
    values.update({'MODE_' + k: v for k, v in spec['modes'].items()})
    return ('/* Generated from spec/control_registers.json; checked at every build. */\n'
            '#ifndef OPENRF_H\n#define OPENRF_H\n' +
            ''.join(f'#define {k} 0x{v:08x}u\n' for k, v in values.items()) + '#endif\n')


def tools():
    result = {k: shutil.which(v) for k, v in
              [('clang', 'clang-21'), ('objdump', 'llvm-objdump-21'),
               ('objcopy', 'llvm-objcopy-21'), ('size', 'llvm-size-21')]}
    result['lld'] = os.environ.get('OPENRF_LLD') or shutil.which('ld.lld')
    if not result['lld']:
        candidates = sorted((Path.home() / '.rustup/toolchains').glob(
            '*/lib/rustlib/x86_64-unknown-linux-gnu/bin/gcc-ld/ld.lld'))
        if candidates: result['lld'] = str(candidates[0])
    if not all(result.values()): raise RuntimeError('Required LLVM tool unavailable')
    return result


def audit(text):
    allowed = set('lui auipc jal jalr beq bne blt bge bltu bgeu lb lh lw lbu lhu '
                  'sb sh sw addi slti sltiu xori ori andi slli srli srai '
                  'add sub sll slt sltu xor srl sra or and'.split())
    rows = re.findall(r'^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+(\S+)', text, re.M)
    if not rows: raise RuntimeError('No decoded instructions')
    # --no-aliases, fixed four-byte RV32I words; reject undecoded/short opcodes.
    address_rows = re.findall(r'^\s*[0-9a-f]+:\s+', text, re.M)
    if len(rows) != len(address_rows): raise RuntimeError('Undecoded/compressed instruction')
    for address, word, mnemonic in rows:
        if mnemonic not in allowed or int(word, 16) & 3 != 3:
            raise RuntimeError(f'Unsupported instruction at {address}: {word} {mnemonic}')
    return {'result': 'PASS', 'instructions': len(rows),
            'mnemonics': sorted({x[2] for x in rows})}


def build(out):
    out.mkdir(parents=True, exist_ok=True)
    if (ROOT / 'firmware/openrf.h').read_text() != header():
        raise RuntimeError('Firmware header differs from frozen ABI specification')
    t = tools()
    versions = {k: subprocess.check_output([v, '--version'], text=True).splitlines()[0]
                for k, v in t.items()}
    flags = ['--target=riscv32-unknown-elf', '-march=rv32i', '-mabi=ilp32',
             '-ffreestanding', '-fno-builtin', '-nostdlib', '-nostartfiles',
             '-msmall-data-limit=0', '-mno-relax', '-Os', '-fno-stack-protector',
             '-fno-unwind-tables', '-fno-asynchronous-unwind-tables']
    hashes = []
    for n in (0, 1):
        elf = out / f'firmware-{n}.elf'
        cmd = [t['clang'], *flags, '--ld-path=' + t['lld'],
               '-Wl,--build-id=none', '-Wl,--no-relax', '-Wl,-T,firmware/link.ld',
               '-Ifirmware', 'firmware/start.S', 'firmware/selftest.S',
               'firmware/control.c', '-o', str(elf)]
        (out / f'command-{n}.json').write_text(json.dumps(cmd, indent=2))
        subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True)
        hashes.append(hashlib.sha256(elf.read_bytes()).hexdigest())
    if hashes[0] != hashes[1]: raise RuntimeError('Non-reproducible ELF')
    elf = out / 'firmware-0.elf'
    dis = subprocess.check_output([t['objdump'], '-d', '-M', 'no-aliases', str(elf)], text=True)
    (out / 'firmware.dis').write_text(dis)
    result = audit(dis)
    subprocess.run([t['objcopy'], '-O', 'binary', str(elf), str(out / 'firmware.bin')], check=True)
    raw = (out / 'firmware.bin').read_bytes()
    if len(raw) > 4096 or len(raw) % 4: raise RuntimeError('ROM bounds/alignment')
    image = raw + bytes.fromhex('6f000000') * ((4096-len(raw))//4)
    (out / 'firmware.hex').write_text(''.join(f'{int.from_bytes(image[i:i+4], "little"):08x}\n'
                                           for i in range(0, 4096, 4)))
    size = subprocess.check_output([t['size'], str(elf)], text=True)
    (out / 'size.txt').write_text(size)
    result.update(versions=versions, flags=flags, elf_sha256=hashes[0],
                  rom_sha256=hashlib.sha256(image).hexdigest(),
                  binary_sha256=hashlib.sha256(raw).hexdigest(),
                  image_bytes=4096, payload_bytes=len(raw), ram_bytes=1024,
                  entry='0x80000000', reproducible=True)
    (out / 'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT/'build/vexriscv/firmware')
    p.add_argument('--generate-header', action='store_true')
    a = p.parse_args()
    if a.generate_header: (ROOT/'firmware/openrf.h').write_text(header())
    else: build(a.output.resolve())
