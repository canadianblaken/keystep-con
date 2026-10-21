#!/usr/bin/env python3
"""Run raw SysEx bytes through the real 2.5.20 parser/router/dispatcher in Unicorn.

Only hardware drivers are stubbed (NOR read/program, session flash copy, MIDI
replies). Usage: emu_sysex_path.py <main.bin> "<hex frame>" ["<hex frame>" ...]
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED, UC_MODE_THUMB, Uc, UcError
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP,
)

BASE = 0x08008000
NOR = 0x60000000
NOR_SIZE = 0x200000
STOP = 0x08007FF0
PARSER = 0x0803D586
ROUTER_VTABLE = 0x08059274
DATA_FLASH, DATA_RAM, DATA_END = 0x0805CB60, 0x20000004, 0x20000650

TRACE = {
    0x0801851C: "handler 0801851c",
    0x0801893C: "session router 0801893c",
    0x0800AA20: "open session 0800aa20",
    0x0800DE9C: "dispatcher 0800de9c",
    0x0800DF28: "item 0x78 case 0800df28",
    0x0800CCA8: "stock item-0x78 setter",
}


def main() -> None:
    image = Path(sys.argv[1]).read_bytes()
    raw = image[64:] if image[:2] == b"\x75\x1c" else image
    frames = [bytes.fromhex(f) for f in sys.argv[2:]]
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    uc.mem_map(0x08000000, 0x80000)
    uc.mem_write(BASE, raw)
    uc.mem_map(0x20000000, 0x80000)
    uc.mem_write(DATA_RAM, raw[DATA_FLASH - BASE:DATA_FLASH - BASE + DATA_END - DATA_RAM])
    uc.mem_map(0xC0000000, 0x400000)
    uc.mem_map(NOR, NOR_SIZE)
    uc.mem_map(0x40000000, 0x20000000)
    uc.mem_map(0xE0000000, 0x100000)
    nor = bytearray(b"\xff" * NOR_SIZE)
    uc.mem_write(NOR, bytes(nor))
    hook_addr = None
    # setter hook address from the patched branch at 0800df28 (B.W)
    h1, h2 = struct.unpack_from("<HH", raw, 0x0800DF28 - BASE)
    if h1 & 0xF800 == 0xF000 and h2 & 0xD000 == 0x9000:
        s = (h1 >> 10) & 1
        i1, i2 = 1 ^ (((h2 >> 13) & 1) ^ s), 1 ^ (((h2 >> 11) & 1) ^ s)
        imm = (s << 24) | (i1 << 23) | (i2 << 22) | ((h1 & 0x3FF) << 12) | ((h2 & 0x7FF) << 1)
        hook_addr = 0x0800DF28 + 4 + (imm - (1 << 25) if s else imm)
        TRACE[hook_addr] = "setname_hook"
    events: list[str] = []
    programmed: list[int] = []

    def ret(machine: Uc, value: int | None = 0) -> None:
        if value is not None:
            machine.reg_write(UC_ARM_REG_R0, value)
        machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

    def code(machine: Uc, address: int, _size: int, _data: object) -> None:
        if address in TRACE:
            r = [machine.reg_read(x) for x in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
            events.append(f"{TRACE[address]} r0={r[0]:#x} r1={r[1]:#x} r2={r[2]:#x} r3={r[3]:#x}")
        if address == 0x0803F774:  # NOR read halfwords
            src, dst, n = (machine.reg_read(x) for x in (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3))
            machine.mem_write(dst, bytes(nor[src - NOR:src - NOR + 2 * n]))
            ret(machine)
        elif address == 0x080475D8:  # program 64 KB sector from staging
            dst = machine.reg_read(UC_ARM_REG_R1)
            nor[dst - NOR:dst - NOR + 0x10000] = machine.mem_read(0xC01F0000, 0x10000)
            programmed.append(dst)
            events.append(f"PROGRAM sector {dst:#x}")
            ret(machine, None)
        elif address in (0x0800A0FC, 0x0800A9F0, 0x0800F358, 0x0800EFBC):
            events.append(f"stub {address:#x}")
            ret(machine)
        elif address == STOP:
            machine.emu_stop()

    def unmapped(machine: Uc, access: int, address: int, size: int, value: int, _d: object) -> bool:
        events.append(f"UNMAPPED access {access} at {address:#x} pc={machine.reg_read(UC_ARM_REG_PC):#x}")
        return False

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_UNMAPPED, unmapped)

    parser = 0x20070000
    listener = 0x20071000
    uc.mem_write(listener, struct.pack("<I", ROUTER_VTABLE))
    uc.mem_write(parser, struct.pack("<IIII", listener, 0, 0, 1) + b"\0" * 0x10)  # listeners[0], count at +8, +0xc arg=0
    uc.mem_write(parser + 8, struct.pack("<I", 1))
    uc.mem_write(parser + 0xC, struct.pack("<I", 0))
    uc.mem_write(parser + 0x21, b"\x00")

    for frame in frames:
        body = frame[1:-1] if frame[0] == 0xF0 else frame
        uc.mem_write(parser + 0x20, b"\x01")  # state after F0
        events.append(f"--- frame {frame.hex(' ')}")
        for byte in body:
            uc.reg_write(UC_ARM_REG_SP, 0x2007F000)
            uc.reg_write(UC_ARM_REG_LR, STOP | 1)
            uc.reg_write(UC_ARM_REG_R0, parser)
            uc.reg_write(UC_ARM_REG_R1, byte)
            try:
                uc.emu_start(PARSER | 1, 0, count=2_000_000)
            except UcError as exc:
                events.append(f"EMU ERROR {exc} pc={uc.reg_read(UC_ARM_REG_PC):#x}")
                break
        state = bytes(uc.mem_read(0x20000670, 3))
        events.append(f"session proj/state/flag = {state.hex(' ')}")
    for e in events:
        print(e)
    for dst in programmed:
        tail = bytes(nor[dst - NOR + 0xFFF0:dst - NOR + 0x10000])
        slot = (dst - NOR) >> 17
        print(f"slot {slot} (Project {slot + 1}) name bytes: {tail!r}")
    if not programmed:
        print("NO FLASH PROGRAM HAPPENED")


if __name__ == "__main__":
    main()
