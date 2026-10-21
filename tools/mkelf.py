#!/usr/bin/env python3
"""Wrap a headerless Cortex-M flash image in a minimal ELF32/ARM so Ghidra auto-loads it.
usage: mkelf.py in.bin out.elf flash_base ram_size"""
import struct, sys

def mkelf(img, base, ram):
    entry = struct.unpack_from('<I', img, 4)[0]           # reset vector (thumb bit kept)
    segs = [(base, img, len(img), 5),                     # flash, R-X
            (0x20000000, b'', ram, 6),                    # SRAM, RW (NOBITS)
            (0x40000000, b'', 0x20000000, 6)]             # APB/AHB peripherals + USB OTG
    phoff, phsz = 52, 32
    off = phoff + phsz * len(segs)
    out = struct.pack('<16sHHIIIIIHHHHHH', b'\x7fELF\x01\x01\x01' + b'\0' * 9,
                      2, 40, 1, entry, phoff, 0, 0x05000400, 52, phsz, len(segs), 40, 0, 0)
    for va, data, memsz, flags in segs:
        out += struct.pack('<8I', 1, off if data else 0, va, va, len(data), memsz, flags, 4)
    return out + img

if __name__ == '__main__':
    src, dst, base, ram = sys.argv[1], sys.argv[2], int(sys.argv[3], 0), int(sys.argv[4], 0)
    img = open(src, 'rb').read()
    elf = mkelf(img, base, ram)
    assert elf[:4] == b'\x7fELF' and elf.endswith(img) and struct.unpack_from('<H', elf, 18)[0] == 40
    open(dst, 'wb').write(elf)
