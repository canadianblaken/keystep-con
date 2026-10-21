#!/usr/bin/env python3
"""Disassemble Thumb code from the main image: dis.py <hexaddr> [count]"""
import sys, capstone
IMG = 'firmware/raw/keysteppro_main__fw2_5_20_2085__2024_03_04.raw.bin'
BASE = 0x08008000
d = open(IMG, 'rb').read()
a = int(sys.argv[1], 16); n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
for i, ins in enumerate(md.disasm(d[a - BASE:a - BASE + n * 4], a)):
    if i >= n: break
    print(f'{ins.address:08x}: {ins.bytes.hex():<10} {ins.mnemonic} {ins.op_str}')
