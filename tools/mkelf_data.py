#!/usr/bin/env python3
"""Like mkelf.py, but also maps the .data init image at its RAM address so pointers into
initialised RAM resolve in Ghidra.
usage: mkelf_data.py in.bin out.elf flash_base ram_size data_flash data_ram data_end"""
import struct, sys

def mkelf(img, base, ram, dflash, dram, dend):
    entry = struct.unpack_from('<I', img, 4)[0]
    data = img[dflash - base:dflash - base + (dend - dram)]
    segs = [(base, img, len(img), 5),
            (0x20000000, b'', dram - 0x20000000, 6),              # SRAM below .data
            (dram, data, len(data), 6),                           # initialised .data
            (dend, b'', 0x20000000 + ram - dend, 6),              # .bss + rest of SRAM
            (0x40000000, b'', 0x20000000, 6)]
    phoff, phsz = 52, 32
    off = phoff + phsz * len(segs)
    hdr = struct.pack('<16sHHIIIIIHHHHHH', b'\x7fELF\x01\x01\x01' + b'\0' * 9,
                      2, 40, 1, entry, phoff, 0, 0x05000400, 52, phsz, len(segs), 40, 0, 0)
    body, ph = b'', b''
    for va, blob, memsz, flags in segs:
        ph += struct.pack('<8I', 1, off + len(body) if blob else 0, va, va, len(blob), memsz, flags, 4)
        body += blob
    return hdr + ph + body

if __name__ == '__main__':
    a = sys.argv
    img = open(a[1], 'rb').read()
    elf = mkelf(img, *(int(x, 0) for x in a[3:8]))
    assert elf[:4] == b'\x7fELF' and img in elf
    open(a[2], 'wb').write(elf)
