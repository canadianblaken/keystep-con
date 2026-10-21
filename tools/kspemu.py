#!/usr/bin/env python3
"""Emulated KeyStep Pro 2.5.20 SysEx endpoint (Unicorn) for offline verification.

Runs the real byte parser, router, dispatchers, setters/getters, session load
(05), session commit (06) and project reload. Only hardware is replaced:
NOR reads (0803f774) and sector programming (080475d8) act on an in-memory
2 MB NOR image, outgoing replies are captured, and the UI refresh is skipped.

    emu = KSPEmu("firmware/patched/keysteppro_main__fw2_5_20_2085__2024_03_04.bin")
    replies = emu.send(bytes.fromhex("F0 00 20 6B 7F 42 05 01 F7"))
"""
from __future__ import annotations

import struct
from pathlib import Path

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED, UC_MODE_THUMB, Uc, UcError
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP

BASE = 0x08008000
NOR, NOR_SIZE = 0x60000000, 0x200000
STAGE = 0xC01F0000
STOP = 0x08007FF0
PARSER = 0x0803D586
ROUTER_VTABLE = 0x08059274
DATA_FLASH, DATA_RAM, DATA_END = 0x0805CB60, 0x20000004, 0x20000650

NOR_READ = 0x0803F774       # (ctx, nor_addr, dst, halfwords)
NOR_PROGRAM_HW = 0x0803F6E0  # (ctx, nor_addr, src*): program one halfword
NOR_ERASE = 0x0803F814       # (ctx, byte_offset, 0x60000000): erase containing sector
NOR_WAIT = 0x0803F944        # busy-wait for ready
REPLY_FUNCS = (0x0800EFBC,)          # (queue, struct*, n): capture struct
SKIP = (0x0800F358, 0x0803B0D0, 0x08046858)  # reply flush, UI refresh, RAM project reload
BOOT_OBJECTS = {
    0x20001498: 0xC0800000,  # project/track state (base of the 0xFEC-per-project blocks)
    0x200014A8: 0xC0900000,  # project loader object (08046858)
    0x20001804: 0xC0A00000,  # MIDI reply queue (stubbed)
}


class KSPEmu:
    def __init__(self, image_path: str | Path, nor: bytes | None = None) -> None:
        image = Path(image_path).read_bytes()
        raw = image[64:] if image[:2] == b"\x75\x1c" else image
        self.uc = uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        uc.mem_map(0x08000000, 0x80000)
        uc.mem_write(BASE, raw)
        uc.mem_map(0x20000000, 0x80000)
        uc.mem_write(DATA_RAM, raw[DATA_FLASH - BASE:DATA_FLASH - BASE + DATA_END - DATA_RAM])
        uc.mem_map(0x24000000, 0x80000)
        uc.mem_map(0xC0000000, 0x1000000)
        uc.mem_map(NOR, NOR_SIZE)
        uc.mem_map(0x40000000, 0x20000000)
        uc.mem_map(0xE0000000, 0x100000)
        self.nor = bytearray(nor if nor is not None else b"\xff" * NOR_SIZE)
        self.programmed: list[int] = []
        self.replies: list[bytes] = []
        self.errors: list[str] = []
        uc.hook_add(UC_HOOK_CODE, self._code)
        uc.hook_add(UC_HOOK_MEM_UNMAPPED, self._unmapped)
        # Object pointers that boot code fills in; point them at zeroed SDRAM.
        for ptr, obj in BOOT_OBJECTS.items():
            uc.mem_write(ptr, struct.pack("<I", obj))
        self.parser, listener = 0x20070000, 0x20071000
        uc.mem_write(listener, struct.pack("<I", ROUTER_VTABLE))
        uc.mem_write(self.parser, struct.pack("<IIII", listener, 0, 1, 0))
        uc.mem_write(self.parser + 0x21, b"\x00")

    def _ret(self, value: int | None = 0) -> None:
        if value is not None:
            self.uc.reg_write(UC_ARM_REG_R0, value)
        self.uc.reg_write(UC_ARM_REG_PC, self.uc.reg_read(UC_ARM_REG_LR))

    def _code(self, uc: Uc, address: int, _size: int, _data: object) -> None:
        if address == NOR_READ:
            src, dst, n = (uc.reg_read(r) for r in (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3))
            uc.mem_write(dst, bytes(self.nor[src - NOR:src - NOR + 2 * n]))
            self._ret()
        elif address == NOR_PROGRAM_HW:
            dst, src = uc.reg_read(UC_ARM_REG_R1) - NOR, uc.reg_read(UC_ARM_REG_R2)
            value = bytes(uc.mem_read(src, 2))
            self.nor[dst] &= value[0]
            self.nor[dst + 1] &= value[1]
            self._ret()
        elif address == NOR_ERASE:
            start, size = self.sector_of(uc.reg_read(UC_ARM_REG_R1) & 0x1FFFFF)
            self.nor[start:start + size] = b"\xff" * size
            self.programmed.append(NOR + start)
            self._ret()
        elif address == NOR_WAIT:
            self._ret()
        elif address in REPLY_FUNCS:
            msg = bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R1), 0x72))
            self.replies.append(msg)
            self._ret()
        elif address in SKIP:
            self._ret()
        elif address == STOP:
            uc.emu_stop()

    @staticmethod
    def sector_of(offset: int) -> tuple[int, int]:
        """Top-boot 2 MB NOR: 31 x 64 KB, then 32 KB, 8 KB, 8 KB, 16 KB."""
        for start, size in ((0x1FC000, 0x4000), (0x1FA000, 0x2000), (0x1F8000, 0x2000), (0x1F0000, 0x8000)):
            if offset >= start:
                return start, size
        return offset & ~0xFFFF, 0x10000

    def _unmapped(self, uc: Uc, access: int, address: int, *_: object) -> bool:
        self.errors.append(f"unmapped access {access} at {address:#x} pc={uc.reg_read(UC_ARM_REG_PC):#x} lr={uc.reg_read(UC_ARM_REG_LR):#x}")
        return False

    def send(self, frame: bytes) -> list[bytes]:
        """Feed one complete SysEx frame; returns captured reply structs."""
        start = len(self.replies)
        body = frame[1:-1] if frame[:1] == b"\xF0" else frame
        self.uc.mem_write(self.parser + 0x20, b"\x01")
        for byte in body:
            self.uc.reg_write(UC_ARM_REG_SP, 0x2007F000)
            self.uc.reg_write(UC_ARM_REG_LR, STOP | 1)
            self.uc.reg_write(UC_ARM_REG_R0, self.parser)
            self.uc.reg_write(UC_ARM_REG_R1, byte)
            try:
                self.uc.emu_start(PARSER | 1, 0, count=50_000_000)
            except UcError as exc:
                self.errors.append(f"{exc} pc={self.uc.reg_read(UC_ARM_REG_PC):#x} frame={frame.hex(' ')}")
                raise
        return self.replies[start:]

    @staticmethod
    def reply_value(msg: bytes) -> bytes:
        """Data bytes of a captured bulk reply struct (length at +7, data at +0x0E)."""
        return msg[0x0E:0x0E + msg[7]]
