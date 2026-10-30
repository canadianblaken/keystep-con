#!/usr/bin/env python3
"""Build KSCON (KeyStep Con): KeyStep Pro firmware 2.5.20 with project names + step pads, reporting 2.5.99,
and the display chip's startup screen redrawn as KEYSTEP CON (boot_logo.py).

Names hooks (tools/name_hooks.S) as in build_names_patch.py, plus the pad hooks
(tools/pad_hooks.S) on the event loop's button press/release calls.
Requires clang with an ARM target. Output stays under ignored firmware/.
This tool never contacts or writes to a device.
"""
from __future__ import annotations

import argparse
import re
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

from boot_logo import UI_ENTRY, patch_ui
from build_names_patch import (
    BASE, FLASH_LIMIT, KSPF, RAW_ENTRY, ROOT, SET_DISPATCH, TITLE_CALL, TITLE_FORMATTER,
    decode_thumb_b_w, decode_thumb_bl, elf_text_and_symbols, thumb_branch,
)

PRESS_CALL = 0x08012708      # bl 080500d8 (button press) in the event loop 08012338
RELEASE_CALL = 0x080126EA    # bl 0804e700 (button release)
SAVE_CALL = 0x08047D36       # bl 080475d8 (program the second sector) in Save Project 08047c84
SECTOR_WRITE = 0x080475D8
KEY_SEND_CALL = 0x080156F6   # bl 0801a6e0: a key's note on, in the event loop
MIDI_SEND = 0x0801A6E0
KEY_REC_CALL = 0x08015EE0    # bl 080108a4: live key record, in the event loop
LED_FLUSH = 0x08054C2C
LED_FLUSH_CALLS = (0x0800E328, 0x0800E84A, 0x0801696A, 0x0801F7BE, 0x0802A88C, 0x0802B876, 0x08030BD6)   # every bl to it
STOCK_KEY_REC = 0x080108A4
STOCK_PRESS = 0x080500D8
STOCK_RELEASE = 0x0804E700
STRIP_CALL = 0x080124DA     # bl 080542dc: a touch strip value change, in the event loop
STRIP_STOCK = 0x080542DC
CHORD_FLAG_CALLS = (0x08038368, 0x080383B8)   # bl 0802d160 (chord mode on?) in the chord expansion 080382e0
CHORD_FLAG = 0x0802D160
# version: the SysEx identity reply builds it from immediates (movs r3,#build / #patch / #minor, major 2 in r2) at
# 0x080181D2/D8/DE, which MCC shows as $3.$2.$1. Patched builds say 2.5.99 so they are not mistaken for stock 2.5.20
# (99 is above MCC's minimum 2.5.14 compared as numbers or as text); the build byte counts our builds.
ID_BUILD_IMM, ID_PATCH_IMM = 0x080181D2, 0x080181D8
PATCH_VERSION = 99
PATCH_BUILD = 10              # bump for every build that is flashed
VERSION_TEXT_PTR = 0x080589A4  # Utility > FW version text, stock "Firmware version :\n2.5.20\nbuild 2085"
STOCK_VERSION_TEXT = 0x0805AF3C
SOURCES = [ROOT / "tools/name_hooks.S", ROOT / "tools/pad_hooks.S"]
C_SOURCES = [ROOT / "tools/bass_gen.c", ROOT / "tools/note_show.c"]   # compiled to Thumb assembly and assembled with the hooks


def c_to_asm(path: Path, temp: Path) -> str:
    """clang -fropi: constant data is reached PC-relative, so it can sit in .text with the code (the build
    takes .text only and does not link). Any call to a symbol the file does not define (memset and
    friends) would be left unresolved, so it is refused."""
    out = temp / (path.stem + ".s")
    subprocess.run(["clang", "--target=arm-none-eabi", "-mcpu=cortex-m7", "-mthumb", "-mfloat-abi=soft", "-Os",
                    "-ffreestanding", "-fno-builtin", "-fropi", "-fno-jump-tables", "-fno-exceptions",
                    "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-S", str(path), "-o", str(out)], check=True)
    lines = []
    for line in out.read_text().splitlines():
        t = line.strip()
        if t.startswith((".section", ".data", ".bss")):
            if ".note.GNU-stack" in t:
                continue
            if not t.startswith(".section\t.text") and not t.startswith(".section .text"):
                if ".rodata" not in t:
                    raise SystemExit(f"{path.name}: writable data is not supported in the hook block: {t}")
            line = "\t.text"
        if t.startswith((".globl", ".global")):     # global symbols get relocations; the build does not link
            continue
        if t.startswith((".file", ".ident", ".addrsig", ".eabi_attribute", ".syntax", ".cpu", ".fpu", ".arch")):
            continue
        lines.append(line)
    text = "\n".join(lines)
    # each file's compiler-made local labels (.LBB0_1, .LCPI0_0, ...) get the file's name, so they do not clash
    text = re.sub(r"\.L([A-Za-z_$][\w$]*)", lambda m: f".L{path.stem}_{m.group(1)}", text)
    defined = set(re.findall(r"^([A-Za-z_.$][\w.$]*):", text, re.M))
    called = set(re.findall(r"^\s*(?:bl|blx|b|b\.w)\s+([A-Za-z_][\w.$]*)\s*$", text, re.M))
    called = {c for c in called if not re.fullmatch(r"r\d+|lr|ip|sp|pc", c)}
    if called - defined:
        raise SystemExit(f"{path.name} calls {sorted(called - defined)}: no library in the hook block")
    return "\n.balign 4\n.thumb\n" + text + "\n.balign 4\n"


def assemble(address: int) -> tuple[bytes, dict[str, int]]:
    with tempfile.TemporaryDirectory(prefix="ksp-build-") as temp:
        temp_path = Path(temp)
        source = (f".equ HOOK_IMAGE_ADDRESS, {address:#x}\n" + "\n".join(p.read_text() for p in SOURCES)
                  + "".join(c_to_asm(p, temp_path) for p in C_SOURCES))
        asm_path, obj_path = temp_path / "hooks.S", temp_path / "hooks.o"
        asm_path.write_text(source)
        subprocess.run(["clang", "--target=arm-none-eabi", "-mcpu=cortex-m7", "-mthumb",
                        "-c", str(asm_path), "-o", str(obj_path)], check=True)
        if relocations(obj_path):
            raise SystemExit(f"unresolved references in the hook block: {relocations(obj_path)} (the build does not link)")
        return elf_text_and_symbols(obj_path)


def relocations(path: Path) -> list[str]:
    """names of non-empty relocation sections: the build copies .text as is, so there must be none"""
    data = path.read_bytes()
    shoff = struct.unpack_from("<I", data, 32)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 46)
    sections = [struct.unpack_from("<IIIIIIIIII", data, shoff + i * shentsize) for i in range(shnum)]
    names = data[sections[shstrndx][4]:sections[shstrndx][4] + sections[shstrndx][5]]
    name = lambda sec: names[sec[0]:names.find(b"\0", sec[0])].decode()
    return [name(sec) for sec in sections if sec[1] in (4, 9) and sec[5] and name(sec).endswith(".text")]


def version_text() -> str:
    return f"Firmware version :\nKSCON 2.5.{PATCH_VERSION} b{PATCH_BUILD}\nbased on 2.5.20"


def build(stock_bin: bytes) -> tuple[bytearray, dict[str, int], int]:
    if stock_bin[:4] != struct.pack("<I", 0x02181C75):
        raise SystemExit("stock model header mismatch")
    if sum(stock_bin[:64]) & 0xFF or (sum(stock_bin[64:]) + stock_bin[9]) & 0xFF:
        raise SystemExit("stock checksum mismatch")
    raw = stock_bin[64:]
    length_word = struct.unpack_from("<I", stock_bin, 4)[0]
    if length_word >> 8 != len(raw) or len(raw) != 0x551AC:
        raise SystemExit(f"unexpected 2.5.20 image size: {len(raw):#x}")
    hook_address = (BASE + len(raw) + 3) & ~3
    hooks, symbols = assemble(hook_address)
    if symbols.get("title_hook", 2) & ~1 != 0:
        raise SystemExit("title_hook must stay at the start of the hook block")
    if hook_address + len(hooks) > FLASH_LIMIT:
        raise SystemExit("hooks exceed internal flash range")
    site = lambda a: raw[a - BASE:a - BASE + 4]
    if site(TITLE_CALL) != bytes.fromhex("31f066f8") or decode_thumb_bl(TITLE_CALL, site(TITLE_CALL)) != TITLE_FORMATTER:
        raise SystemExit("project-title formatter call changed; refusing stale patch")
    if site(SET_DISPATCH) != bytes.fromhex("3a462146"):
        raise SystemExit("project item dispatch changed; refusing stale patch")
    if decode_thumb_bl(PRESS_CALL, site(PRESS_CALL)) != STOCK_PRESS:
        raise SystemExit("button press call changed; refusing stale patch")
    if decode_thumb_bl(RELEASE_CALL, site(RELEASE_CALL)) != STOCK_RELEASE:
        raise SystemExit("button release call changed; refusing stale patch")
    if decode_thumb_bl(SAVE_CALL, site(SAVE_CALL)) != SECTOR_WRITE:
        raise SystemExit("save project sector write changed; refusing stale patch")
    if decode_thumb_bl(KEY_SEND_CALL, site(KEY_SEND_CALL)) != MIDI_SEND:
        raise SystemExit("key note-on send changed; refusing stale patch")
    if decode_thumb_bl(STRIP_CALL, site(STRIP_CALL)) != STRIP_STOCK:
        raise SystemExit("strip call site does not match stock 2.5.20")
    if decode_thumb_bl(KEY_REC_CALL, site(KEY_REC_CALL)) != STOCK_KEY_REC:
        raise SystemExit("key record call changed; refusing stale patch")
    for call in CHORD_FLAG_CALLS:
        if decode_thumb_bl(call, site(call)) != CHORD_FLAG:
            raise SystemExit(f"chord flag call at {call:#x} changed; refusing stale patch")
    for call in LED_FLUSH_CALLS:
        if decode_thumb_bl(call, site(call)) != LED_FLUSH:
            raise SystemExit(f"LED send call at {call:#x} changed; refusing stale patch")
    if raw[ID_BUILD_IMM - BASE:ID_BUILD_IMM - BASE + 2] != bytes((0x25, 0x23)) or raw[ID_PATCH_IMM - BASE:ID_PATCH_IMM - BASE + 2] != bytes((0x14, 0x23)):
        raise SystemExit("identity version immediates changed; refusing stale patch")
    if struct.unpack_from("<I", raw, VERSION_TEXT_PTR - BASE)[0] != STOCK_VERSION_TEXT:
        raise SystemExit("firmware version text pointer changed; refusing stale patch")

    at = lambda name: (hook_address + symbols[name]) & ~1
    patched = bytearray(raw)
    patches = [(TITLE_CALL, hook_address, True), (SET_DISPATCH, at("setname_hook"), False),
               (PRESS_CALL, at("pad_press"), True), (RELEASE_CALL, at("pad_release"), True),
               (SAVE_CALL, at("chord_save"), True), (KEY_SEND_CALL, at("key_send"), True),
               (KEY_REC_CALL, at("key_rec"), True), (STRIP_CALL, at("strip_hook"), True)] + [(c, at("led_flush"), True) for c in LED_FLUSH_CALLS] \
        + [(c, at("pa_chord_flag"), True) for c in CHORD_FLAG_CALLS]
    for source, target, link in patches:
        patched[source - BASE:source - BASE + 4] = thumb_branch(source, target, link)
        decode = decode_thumb_bl if link else decode_thumb_b_w
        if decode(source, patched[source - BASE:source - BASE + 4]) != target:
            raise SystemExit(f"branch at {source:#x} does not reach {target:#x}")
    patched[ID_BUILD_IMM - BASE] = PATCH_BUILD & 0x7F
    patched[ID_PATCH_IMM - BASE] = PATCH_VERSION
    patched.extend(b"\xff" * (hook_address - BASE - len(patched)))
    patched.extend(hooks)
    while len(patched) % 4:
        patched.append(0)
    text_address = BASE + len(patched)
    patched.extend(version_text().encode("ascii") + b"\0")
    while len(patched) % 4:
        patched.append(0)
    if BASE + len(patched) > FLASH_LIMIT:
        raise SystemExit("hooks and version text exceed internal flash range")
    struct.pack_into("<I", patched, VERSION_TEXT_PTR - BASE, text_address)

    out = bytearray(stock_bin[:64]) + patched
    struct.pack_into("<I", out, 4, (len(patched) << 8) | (length_word & 0xFF))
    out[9] = -sum(out[64:]) & 0xFF
    out[63] = -sum(out[:63]) & 0xFF
    if sum(out[:64]) & 0xFF or (sum(out[64:]) + out[9]) & 0xFF:
        raise SystemExit("patched checksum mismatch")
    return out, {k: hook_address + v for k, v in symbols.items()}, hook_address


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "firmware/patched")
    args = parser.parse_args()
    with zipfile.ZipFile(KSPF) as archive:
        stock_bin = archive.read(RAW_ENTRY)
        entries = [(item, archive.read(item.filename)) for item in archive.infolist()]
    out, symbols, hook_address = build(stock_bin)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_bin = args.output_dir / ("kscon_" + RAW_ENTRY)
    output_kspf = args.output_dir / f"KSCON_2.5.{PATCH_VERSION}_build{PATCH_BUILD}.kspf"
    output_bin.write_bytes(out)
    with zipfile.ZipFile(output_kspf, "w") as archive:
        for item, data in entries:
            if item.filename == UI_ENTRY:
                data = patch_ui(data)          # startup screen: KEYSTEP CON (boot_logo.py)
            if item.filename == "info.json":
                data = data.replace(b'"version_number": "2.5.20"', f'"version_number": "2.5.{PATCH_VERSION}"'.encode())
            archive.writestr(item, bytes(out) if item.filename == RAW_ENTRY else data)
    with zipfile.ZipFile(output_kspf) as archive:
        if archive.read(RAW_ENTRY) != out or archive.testzip() is not None:
            raise SystemExit("rebuilt package check failed")
    print(f"hooks at {hook_address:#010x} ({len(out) - 64 - (hook_address - BASE)} bytes): "
          + ", ".join(f"{k} {v:#x}" for k, v in sorted(symbols.items(), key=lambda kv: kv[1]) if not k.startswith("$")))
    print(f"reports version 2.5.{PATCH_VERSION} build {PATCH_BUILD}; menu text {version_text()!r}")
    print(f"patched image: {output_bin}")
    print(f"candidate package: {output_kspf}")
    print("No device was contacted or written.")


if __name__ == "__main__":
    main()
