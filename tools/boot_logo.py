#!/usr/bin/env python3
"""Startup screen of the KeyStep Pro display chip (UI firmware 0.0.1 build 1823).

The display chip copies a 128x64 1-bit picture (SSD1306 page format: 8 pages of 128 bytes, bit 0 = top row of
the page) from 0x08027F08 into its frame buffer at power-on, then animates a few moving dots over it
(FUN_08016f14). This tool redraws the big "PRO" of that picture as "CON" in the same pixel style, keeping the box,
the other lettering and the animation, and fixes the image header checksums. With --preview it writes a PNG.
This tool never contacts or writes to a device.
"""
from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path

UI_ENTRY = "keysteppro_ui__fw0_0_1_1823__2024_03_04.bin"
UI_BASE = 0x08000000
LOGO = 0x08027F08
LOGO_REF = 0x08017130          # literal the copy loads the picture address from
ROW0, ROWS = 23, 12            # the big second line ("PRO") is rows 23-34
OLD_X0, OLD_X1 = 46, 80        # its columns
O_X = 69                       # the original O (11 columns wide)

# C: the original O with its right side open in the middle rows; N: 2-pixel strokes like the rest
C_SHAPE = ["...#####...", ".########..", ".##.....##.", "##.........", "##.........", "##.........",
           "##.........", "##.........", "##.........", ".##.....##.", ".#########.", "...#####..."]


def n_shape() -> list[str]:
    rows = []
    for i in range(ROWS):
        line = ["."] * 11
        line[0] = line[1] = line[9] = line[10] = "#"
        x = 2 + round(i * 6 / (ROWS - 1))
        for k in (x, x + 1):
            if 2 <= k <= 8:
                line[k] = "#"
        rows.append("".join(line))
    return rows


def get(pic: bytes | bytearray, x: int, y: int) -> int:
    return pic[(y // 8) * 128 + x] >> (y % 8) & 1


def put(pic: bytearray, x: int, y: int, on: int) -> None:
    if on:
        pic[(y // 8) * 128 + x] |= 1 << (y % 8)
    else:
        pic[(y // 8) * 128 + x] &= ~(1 << (y % 8)) & 0xFF


def con_logo(pic: bytes) -> bytearray:
    out = bytearray(pic)
    o_shape = ["".join("#" if get(pic, O_X + c, ROW0 + r) else "." for c in range(11)) for r in range(ROWS)]
    for y in range(ROW0, ROW0 + ROWS):
        for x in range(OLD_X0, OLD_X1 + 1):
            put(out, x, y, 0)
    x0 = 44                     # C O N, 11 + 2 + 11 + 2 + 11 = 37 columns, centred under KEYSTEP like PRO was
    for k, shape in enumerate((C_SHAPE, o_shape, n_shape())):
        for r, line in enumerate(shape):
            for c, ch in enumerate(line):
                put(out, x0 + k * 13 + c, ROW0 + r, ch == "#")
    return out


def patch_ui(ui_bin: bytes) -> bytes:
    if sum(ui_bin[:64]) & 0xFF or (sum(ui_bin[64:]) + ui_bin[9]) & 0xFF:
        raise SystemExit("UI image checksum mismatch")
    raw = bytearray(ui_bin[64:])
    if struct.unpack_from("<I", raw, LOGO_REF - UI_BASE)[0] != LOGO:
        raise SystemExit("startup picture address changed; refusing stale patch")
    pic = bytes(raw[LOGO - UI_BASE:LOGO - UI_BASE + 1024])
    if "".join("#" if get(pic, x, 23) else "." for x in range(46, 81)) != "#######....########.......#####....":
        raise SystemExit("startup picture is not the stock KEYSTEP PRO logo; refusing stale patch")
    raw[LOGO - UI_BASE:LOGO - UI_BASE + 1024] = con_logo(pic)
    out = bytearray(ui_bin[:64]) + raw
    out[9] = -sum(out[64:]) & 0xFF
    out[63] = -sum(out[:63]) & 0xFF
    if sum(out[:64]) & 0xFF or (sum(out[64:]) + out[9]) & 0xFF:
        raise SystemExit("patched UI checksum mismatch")
    return bytes(out)


def preview(pic: bytes, path: Path, scale: int = 4) -> None:
    w, h = 128 * scale, 64 * scale
    rows = bytearray()
    for y in range(h):
        rows.append(0)
        line = bytearray(w // 8)
        for x in range(w):
            if get(pic, x // scale, y // scale):
                line[x >> 3] |= 0x80 >> (x & 7)
        rows += line
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 1, 0, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))


def main() -> None:
    import zipfile
    from build_names_patch import KSPF
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=Path, help="write the new startup picture as a PNG")
    args = parser.parse_args()
    ui = zipfile.ZipFile(KSPF).read(UI_ENTRY)
    new = patch_ui(ui)
    pic = new[64 + LOGO - UI_BASE:64 + LOGO - UI_BASE + 1024]
    for y in range(20, 38):
        print("".join("#" if get(pic, x, y) else "." for x in range(22, 108)))
    if args.preview:
        preview(pic, args.preview)
        print(f"preview: {args.preview}")
    print("No device was contacted or written.")


if __name__ == "__main__":
    main()
