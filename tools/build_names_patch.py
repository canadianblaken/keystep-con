#!/usr/bin/env python3
"""Build an offline KeyStep Pro 2.5.20 project-name firmware candidate.

Requires clang with an ARM target. Output remains under ignored firmware/.
This tool never contacts or writes to a device.
"""
from __future__ import annotations

import argparse
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x08008000
FLASH_LIMIT = 0x08080000
TITLE_CALL = 0x0802654C
SET_DISPATCH = 0x0800DF28
TITLE_FORMATTER = 0x0805761C
RAW_ENTRY = "keysteppro_main__fw2_5_20_2085__2024_03_04.bin"
KSPF = ROOT / "firmware/keystep-pro_Firmware_Update_2.5.20.0.kspf"
HOOK_ASM = ROOT / "tools/name_hooks.S"


def thumb_branch(source: int, target: int, link: bool) -> bytes:
    delta = target - (source + 4)
    if delta & 1 or not -(1 << 24) <= delta < (1 << 24):
        raise ValueError(f"Thumb branch out of range: {source:#x} -> {target:#x}")
    imm = delta & 0x01FFFFFF
    s = (imm >> 24) & 1
    i1 = (imm >> 23) & 1
    i2 = (imm >> 22) & 1
    j1 = 1 ^ (i1 ^ s)
    j2 = 1 ^ (i2 ^ s)
    h1 = 0xF000 | (s << 10) | ((imm >> 12) & 0x03FF)
    h2 = (0xD000 if link else 0x9000) | (j1 << 13) | (j2 << 11) | ((imm >> 1) & 0x07FF)
    return struct.pack("<HH", h1, h2)


def decode_thumb_bl(source: int, code: bytes) -> int:
    h1, h2 = struct.unpack_from("<HH", code)
    if h1 & 0xF800 != 0xF000 or h2 & 0xD000 != 0xD000:
        raise ValueError(f"expected Thumb BL at {source:#x}")
    s = (h1 >> 10) & 1
    j1, j2 = (h2 >> 13) & 1, (h2 >> 11) & 1
    i1, i2 = 1 ^ (j1 ^ s), 1 ^ (j2 ^ s)
    imm = (s << 24) | (i1 << 23) | (i2 << 22) | ((h1 & 0x3FF) << 12) | ((h2 & 0x7FF) << 1)
    if s:
        imm -= 1 << 25
    return source + 4 + imm


def decode_thumb_b_w(source: int, code: bytes) -> int:
    h1, h2 = struct.unpack_from("<HH", code)
    if h1 & 0xF800 != 0xF000 or h2 & 0xD000 != 0x9000:
        raise ValueError(f"expected Thumb B.W at {source:#x}")
    s = (h1 >> 10) & 1
    j1, j2 = (h2 >> 13) & 1, (h2 >> 11) & 1
    i1, i2 = 1 ^ (j1 ^ s), 1 ^ (j2 ^ s)
    imm = (s << 24) | (i1 << 23) | (i2 << 22) | ((h1 & 0x3FF) << 12) | ((h2 & 0x7FF) << 1)
    if s:
        imm -= 1 << 25
    return source + 4 + imm


def elf_text_and_symbols(path: Path) -> tuple[bytes, dict[str, int]]:
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        raise ValueError("assembler output is not little-endian ELF32")
    shoff = struct.unpack_from("<I", data, 32)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 46)
    sections = [struct.unpack_from("<IIIIIIIIII", data, shoff + i * shentsize) for i in range(shnum)]
    names_section = sections[shstrndx]
    names = data[names_section[4]:names_section[4] + names_section[5]]
    text = None
    symbols: dict[str, int] = {}
    for section in sections:
        end = names.find(b"\0", section[0])
        name = names[section[0]:end]
        if name == b".text":
            start, size = section[4], section[5]
            text = data[start:start + size]
        if section[1] == 2:  # SHT_SYMTAB
            strings = sections[section[6]]
            string_data = data[strings[4]:strings[4] + strings[5]]
            for off in range(section[4], section[4] + section[5], section[9]):
                name_off, value, _size, _info, _other, _shndx = struct.unpack_from("<IIIBBH", data, off)
                name_end = string_data.find(b"\0", name_off)
                sym_name = string_data[name_off:name_end].decode("ascii")
                if sym_name:
                    symbols[sym_name] = value
    if text is None:
        raise ValueError("no .text section in assembler output")
    return text, symbols


def assemble_hooks(address: int) -> bytes:
    with tempfile.TemporaryDirectory(prefix="ksp-name-build-") as temp:
        temp_path = Path(temp)
        source = HOOK_ASM.read_text()
        source = f".equ HOOK_IMAGE_ADDRESS, {address:#x}\n" + source
        asm_path = temp_path / "hooks.S"
        obj_path = temp_path / "hooks.o"
        asm_path.write_text(source)
        subprocess.run([
            "clang", "--target=arm-none-eabi", "-mcpu=cortex-m7", "-mthumb",
            "-c", str(asm_path), "-o", str(obj_path),
        ], check=True)
        return elf_text_and_symbols(obj_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "firmware/patched")
    args = parser.parse_args()
    with zipfile.ZipFile(KSPF) as archive:
        info = archive.getinfo(RAW_ENTRY)
        stock_bin = archive.read(RAW_ENTRY)
        entries = [(item, archive.read(item.filename)) for item in archive.infolist()]
    if stock_bin[:4] != struct.pack("<I", 0x02181C75):
        raise SystemExit("stock model header mismatch")
    if len(stock_bin) < 64:
        raise SystemExit("truncated stock image")
    if sum(stock_bin[:64]) & 0xFF:
        raise SystemExit("stock header checksum mismatch")
    if (sum(stock_bin[64:]) + stock_bin[9]) & 0xFF:
        raise SystemExit("stock payload checksum mismatch")
    raw = stock_bin[64:]
    length_word = struct.unpack_from("<I", stock_bin, 4)[0]
    if length_word >> 8 != len(raw):
        raise SystemExit("header image length does not match stock payload")
    if BASE + len(raw) >= FLASH_LIMIT:
        raise SystemExit("stock image exceeds expected internal flash range")

    hook_address = (BASE + len(raw) + 3) & ~3
    hooks, hook_symbols = assemble_hooks(hook_address)
    if hook_address + len(hooks) > FLASH_LIMIT:
        raise SystemExit("name hooks exceed internal flash range")
    if len(raw) != 0x551AC:
        raise SystemExit(f"unexpected 2.5.20 image size: {len(raw):#x}")
    if raw[TITLE_CALL - BASE:TITLE_CALL - BASE + 4] != bytes.fromhex("31f066f8"):
        raise SystemExit("project-title formatter call changed; refusing stale patch")
    if decode_thumb_bl(TITLE_CALL, raw[TITLE_CALL - BASE:TITLE_CALL - BASE + 4]) != TITLE_FORMATTER:
        raise SystemExit("project-title call target mismatch")
    if raw[SET_DISPATCH - BASE:SET_DISPATCH - BASE + 4] != bytes.fromhex("3a462146"):
        raise SystemExit("project item dispatch changed; refusing stale patch")

    patched = bytearray(raw)
    patched[TITLE_CALL - BASE:TITLE_CALL - BASE + 4] = thumb_branch(TITLE_CALL, hook_address, True)
    set_hook = (hook_address + hook_symbols["setname_hook"]) & ~1
    patched[SET_DISPATCH - BASE:SET_DISPATCH - BASE + 4] = thumb_branch(SET_DISPATCH, set_hook, False)
    if decode_thumb_bl(TITLE_CALL, patched[TITLE_CALL - BASE:TITLE_CALL - BASE + 4]) != hook_address:
        raise SystemExit("built title branch does not reach title hook")
    if decode_thumb_b_w(SET_DISPATCH, patched[SET_DISPATCH - BASE:SET_DISPATCH - BASE + 4]) != set_hook:
        raise SystemExit("built dispatcher branch does not reach setter hook")
    if len(patched) < hook_address - BASE:
        patched.extend(b"\xff" * (hook_address - BASE - len(patched)))
    patched.extend(hooks)

    patched_bin = bytearray(stock_bin[:64]) + patched
    struct.pack_into("<I", patched_bin, 4, (len(patched) << 8) | (length_word & 0xFF))
    # Header byte 9 makes the payload sum to 0 mod 256; byte 0x3F then makes the
    # 64 header bytes sum to 0 mod 256 (both hold for all four stock images).
    patched_bin[9] = -sum(patched_bin[64:]) & 0xFF
    patched_bin[63] = -sum(patched_bin[:63]) & 0xFF
    if sum(patched_bin[:64]) & 0xFF:
        raise SystemExit("patched header checksum mismatch")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_kspf = args.output_dir / "KeyStepPro_2.5.20_project_names.kspf"
    output_bin = args.output_dir / RAW_ENTRY
    output_bin.write_bytes(patched_bin)
    with zipfile.ZipFile(output_kspf, "w") as archive:
        for item, data in entries:
            archive.writestr(item, bytes(patched_bin) if item.filename == RAW_ENTRY else data)
    with zipfile.ZipFile(output_kspf) as archive:
        if archive.read(RAW_ENTRY) != patched_bin:
            raise SystemExit("packaged main image differs from built image")
        if archive.testzip() is not None:
            raise SystemExit("rebuilt package has a ZIP CRC error")
    print(f"hook address: {hook_address:#010x}; hook bytes: {len(hooks)}")
    print(f"patched image: {output_bin} ({len(patched_bin)} bytes)")
    print(f"candidate package: {output_kspf}")
    print("No device was contacted or written.")


if __name__ == "__main__":
    main()
