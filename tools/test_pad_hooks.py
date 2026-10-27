#!/usr/bin/env python3
"""Exercise the step pad hooks (drum pads, chord pads, chord save) in Unicorn.

The firmware's own lane->note (080347c8, 0800e666) and MIDI message builders
(08017e70, 08017e28, 08017dd0) run for real; MIDI send (0801a6e0), the stock
button handlers (080500d8, 0804e700) and the flash helpers are stubbed and recorded.
"""
from __future__ import annotations

import sys
from pathlib import Path

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_THUMB, Uc
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_names_patch import decode_thumb_bl  # noqa: E402

BASE = 0x08008000
STOP = 0x08007FF0
PRESS_CALL, RELEASE_CALL, SAVE_CALL = 0x08012708, 0x080126EA, 0x08047D36
STOCK_PRESS, STOCK_RELEASE, MIDI_SEND = 0x080500D8, 0x0804E700, 0x0801A6E0
FLASH_READ, STAGE_WRITE, SECTOR_WRITE = 0x0803F774, 0x08047148, 0x080475D8
KEY_SEND_CALL = 0x080156F6
KEY_LED, LED_SET, SEL_TRACK, TRACK_COLOURS = 0x08034AB4, 0x08053EB8, 0x200001A4, 0x20000058
REC_NOTE, REC_END, REC_X, RECORDING, REC_ARMED = 0x0802A244, 0x08029E78, 0x20003D9D, 0x20003D91, 0x20002D5B
KEY_REC_CALL, STOCK_KEY_REC = 0x08015EE0, 0x080108A4
GLOBALS, PORT_PTR, PORT = 0x20000874, 0x20001800, 0x20003000
SEQ_PTR, SEQ, CUR_PROJECT, CUR_PAT, MASKS, HELD = 0x20001498, 0x20020000, 0x20004DAD, 0x20004DA8, 0x20000004, 0x20004DDC
BUTTONS = 0x200014B8 + 0x100
STATE = 0xC01EF800
FLASH, STAGE = 0x60000000, 0xC01F0000
SEQ_BTN, DRUM, STEP1, ERASE, SHIFT, EXIT = 0x14, 0x15, 0x2E, 0x10, 1, 0x0C
T2_SEQ, T2_ARP, T3_SEQ, T3_ARP, T2_MUTE, T1_MUTE = 0x1A, 0x1B, 0x20, 0x21, 0x1C, 0x16
T1_TRACK, T2_TRACK = 0x17, 0x1D
# make bass: popup (08025274 text, 0801f96c screen prep), scale map rebuild 0803094c (stubbed);
# the step index rebuild (0802caf0, 0802f340) and the edited flag (0802ceac) run for real
POPUP, UI_PREP, SCALE_REBUILD = 0x08025274, 0x0801F96C, 0x0803094C
# step lights: every LED send (08054c2c, stubbed) goes through led_flush; LED object at *0x20001490
LED_FLUSH, LED_FLUSH_CALLS, LEDS_PTR, LEDS = 0x08054C2C, (0x0800E328, 0x0800E84A, 0x0801696A, 0x0801F7BE, 0x0802A88C,
                                                         0x0802B876, 0x08030BD6), 0x20001490, 0x20060000
UI_PTR, UI_OBJ, POPUP_CTX_PTR, POPUP_CTX_VAL = 0x20001510, 0x20050000, 0x200017F8, 0x20051000
NOTES, STEPOF, PASSES, STEP_INDEX = 0xC0000000, 0xC015C000, 0xC0104000, 0x20003DA0
PAGE_SRC = Path(__file__).resolve().parents[1] / "web/src"


def run(path: Path) -> None:
    image = path.read_bytes()
    raw = image[64:]
    assert sum(image[:64]) & 0xFF == 0 and (sum(raw) + image[9]) & 0xFF == 0, "checksums"
    target = lambda a: decode_thumb_bl(a, raw[a - BASE:a - BASE + 4])
    press, release, save = target(PRESS_CALL), target(RELEASE_CALL), target(SAVE_CALL)
    assert press != STOCK_PRESS and release != STOCK_RELEASE and save != SECTOR_WRITE, "call sites not redirected"
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    uc.mem_map(0x08000000, 0x80000)
    uc.mem_write(BASE, raw)
    uc.mem_map(0x20000000, 0x100000)
    uc.mem_map(0xC0000000, 0x200000)
    uc.mem_map(FLASH, 0x200000)
    uc.mem_write(PORT_PTR, PORT.to_bytes(4, "little"))
    uc.mem_write(SEQ_PTR, SEQ.to_bytes(4, "little"))
    uc.mem_write(UI_PTR, UI_OBJ.to_bytes(4, "little"))          # screen: keys and pads show popups (note_show.c)
    uc.mem_write(POPUP_CTX_PTR, POPUP_CTX_VAL.to_bytes(4, "little"))
    uc.mem_write(LEDS_PTR, LEDS.to_bytes(4, "little"))
    flash = bytearray(b"\xff" * 0x200000)
    sent: list[bytes] = []
    stock: list[tuple[str, int]] = []
    sector_writes: list[int] = []
    sps: list[int] = []
    leds: list[tuple[int, int, int]] = []
    recs: list[tuple] = []
    popups: list[str] = []
    rebuilt: list[int] = []
    flushes: list[int] = []
    next_slot = [10]

    def hook(m: Uc, address: int, _size: int, _data: object) -> None:
        r = m.reg_read
        ret = lambda: m.reg_write(UC_ARM_REG_PC, r(UC_ARM_REG_LR))
        if address == MIDI_SEND:
            msg = r(UC_ARM_REG_R1)
            assert r(UC_ARM_REG_R0) == PORT and r(UC_ARM_REG_R2) == 3
            sent.append(bytes((msg & 0xFF, msg >> 8 & 0xFF, msg >> 16 & 0xFF)))
            sps.append(r(UC_ARM_REG_SP))
            ret()
        elif address in (STOCK_PRESS, STOCK_RELEASE):
            stock.append(("press" if address == STOCK_PRESS else "release", r(UC_ARM_REG_R1)))
            assert r(UC_ARM_REG_R0) == BUTTONS and r(UC_ARM_REG_LR) == STOP | 1
            if address == STOCK_PRESS:
                assert r(UC_ARM_REG_R2) == 1
            ret()
        elif address == FLASH_READ:
            src, dst, n = r(UC_ARM_REG_R1), r(UC_ARM_REG_R2), r(UC_ARM_REG_R3) * 2
            assert r(UC_ARM_REG_R0) == 0x20001820
            m.mem_write(dst, bytes(flash[src - FLASH:src - FLASH + n]))
            ret()
        elif address == STAGE_WRITE:
            off, src, n = r(UC_ARM_REG_R1), r(UC_ARM_REG_R2), r(UC_ARM_REG_R3) * 2
            stage = int.from_bytes(m.mem_read(r(UC_ARM_REG_SP), 4), "little")
            m.mem_write(stage + off, bytes(m.mem_read(src, n)))
            ret()
        elif address == SECTOR_WRITE:
            dest = r(UC_ARM_REG_R1)
            assert r(UC_ARM_REG_R0) == 0x20009999, "flash context passed through"
            flash[dest - FLASH:dest - FLASH + 0x10000] = m.mem_read(STAGE, 0x10000)
            sector_writes.append(dest)
            assert r(UC_ARM_REG_LR) == STOP | 1
            ret()
        elif address == KEY_LED:
            note, track = r(UC_ARM_REG_R1), r(UC_ARM_REG_R2)
            assert r(UC_ARM_REG_R0) == SEQ
            m.reg_write(UC_ARM_REG_R0, 0x46 + note % 37 if note < 120 else 0x78)
            ret()
        elif address == LED_SET:
            sp = r(UC_ARM_REG_SP)
            assert m.mem_read(sp, 8) == b"\0" * 8, "LED_SET stack args"
            assert sp % 8 == 0
            leds.append((r(UC_ARM_REG_R1), r(UC_ARM_REG_R2), r(UC_ARM_REG_R3)))
            ret()
        elif address == REC_NOTE:
            recs.append(("rec", r(UC_ARM_REG_R0), r(UC_ARM_REG_R1), r(UC_ARM_REG_R2), r(UC_ARM_REG_R3)))
            m.reg_write(UC_ARM_REG_R0, next_slot[0])
            next_slot[0] += 1
            ret()
        elif address == REC_END:
            recs.append(("end", r(UC_ARM_REG_R0), r(UC_ARM_REG_R1)))
            ret()
        elif address == STOCK_KEY_REC:
            recs.append(("keyrec", r(UC_ARM_REG_R3)))
            m.reg_write(UC_ARM_REG_R0, 7)
            ret()
        elif address == POPUP:
            text = bytes(m.mem_read(r(UC_ARM_REG_R1), 64)).split(b"\0")[0].decode()
            assert r(UC_ARM_REG_R0) == POPUP_CTX_VAL and r(UC_ARM_REG_R2) == 1000
            popups.append(text)
            ret()
        elif address == UI_PREP:
            assert r(UC_ARM_REG_R0) == UI_OBJ
            ret()
        elif address == SCALE_REBUILD:
            assert r(UC_ARM_REG_R0) == SEQ
            rebuilt.append(r(UC_ARM_REG_R1))
            ret()
        elif address == LED_FLUSH:
            flushes.append(r(UC_ARM_REG_R0))
            assert r(UC_ARM_REG_SP) % 8 == 0
            ret()
        elif address == STOP:
            m.emu_stop()

    uc.hook_add(UC_HOOK_CODE, hook)

    def held(button: int, down: bool) -> None:
        uc.mem_write(BUTTONS + 0x6C + button * 3 + 2, b"\0" if down else b"\1")

    def start(address: int, regs: dict[int, int]) -> None:
        uc.reg_write(UC_ARM_REG_SP, 0x200FF000)
        uc.reg_write(UC_ARM_REG_LR, STOP | 1)
        for k, v in regs.items():
            uc.reg_write(k, v)
        uc.emu_start(address | 1, 0, count=3_000_000)

    def event(kind: str, button: int) -> None:
        start(press if kind == "press" else release, {UC_ARM_REG_R0: BUTTONS, UC_ARM_REG_R1: button, UC_ARM_REG_R2: 1})

    def tap(button: int) -> None:
        event("press", button)
        event("release", button)

    def combo(first: int, second: int) -> None:
        held(first, True)
        tap(second)
        held(first, False)

    def glob(gid: int, v: int) -> None:
        uc.mem_write(GLOBALS + 4 + gid, bytes((v,)))

    def track_key(t: int, root: int, scale: int, octave: int = 3, project: int = 2, pattern: int = 0) -> None:
        uc.mem_write(CUR_PROJECT, bytes((project,)))
        uc.mem_write(CUR_PAT + t, bytes((pattern,)))
        blk = SEQ + project * 0xFEC + pattern * 0x14 + t * 0x140 + 0x93A
        uc.mem_write(blk, bytes((root << 4, scale)))
        uc.mem_write(SEQ + project * 0xFEC + t * 0x16 + 0x1752, bytes((octave,)))

    def keys(*held_keys: tuple[int, int]) -> None:
        table = bytearray(b"\xff" * 37 * 3)
        for i, (note, t) in enumerate(held_keys):
            table[i * 3:i * 3 + 3] = bytes((note, 0, t))
        uc.mem_write(HELD, bytes(table))

    def pad(n: int) -> list[bytes]:
        sent.clear()
        tap(STEP1 + n - 1)
        out = list(sent)
        sent.clear()
        return out

    on = lambda ch, *notes: [bytes((0x90 | ch, n, 100)) for n in notes]
    off = lambda ch, *notes: [bytes((0x80 | ch, n, 0)) for n in notes]

    for b in range(0x44):
        held(b, False)
    uc.mem_write(STATE, b"\xa5" * 0x200)        # random RAM after power-up
    for idx, mask in {1: 0xAB5, 2: 0x5AD, 6: 0x4E9}.items():
        uc.mem_write(MASKS + idx * 2, mask.to_bytes(2, "little"))
    glob(79, 9); glob(81, 0); glob(82, 36); glob(1, 0); glob(76, 1); glob(77, 2)
    keys()
    track_key(1, 0, 1)

    # off: everything is stock
    for b in (STEP1, SEQ_BTN, DRUM, T2_SEQ, T2_ARP, ERASE, 0x3E, 1):
        tap(b)
    assert stock == [(k, b) for b in (STEP1, SEQ_BTN, DRUM, T2_SEQ, T2_ARP, ERASE, 0x3E, 1) for k in ("press", "release")], stock
    assert not sent
    stock.clear()

    # drum pads (Drum + Seq)
    combo(DRUM, SEQ_BTN)
    assert not stock and uc.mem_read(STATE + 4, 1) == b"\1"
    assert pad(1) == on(9, 36) + off(9, 36) and pad(16) == on(9, 51) + off(9, 51)
    assert popups[-1] == "Drum 16\nD#3", popups
    pad(1)
    assert popups[-1] == "Drum 1\nC2", popups
    tap(SEQ_BTN)                                 # Seq alone stays stock
    assert stock == [("press", SEQ_BTN), ("release", SEQ_BTN)]
    stock.clear()

    # key lights: drum hits light their key while track 1 is selected (as drums = 4), not otherwise
    uc.mem_write(TRACK_COLOURS, bytes((11, 22, 33, 44)))
    uc.mem_write(SEL_TRACK, b"\4")
    leds.clear()
    pad(1)
    assert leds == [(0x46 + 36 % 37, 1, 11), (0x46 + 36 % 37, 0, 8)], leds
    uc.mem_write(SEL_TRACK, b"\1")
    leds.clear()
    pad(1)
    assert leds == [], "drum hits do not light keys while another track is selected"
    # chord pads on track 2 (Seq + Arp) switch drum pads off; scale chords in C major, octave 3
    combo(T2_SEQ, T2_ARP)
    assert not stock and uc.mem_read(STATE + 4, 1) == b"\2", stock
    assert pad(1) == on(1, 60, 64, 67) + off(1, 60, 64, 67), pad(1)
    assert popups[-1] == "C\nC4 E4 G4", popups
    assert pad(5)[:3] == on(1, 67, 71, 74)
    assert popups[-1] == "G\nG4 B4 D5", popups
    leds.clear()
    pad(1)
    assert leds == [(0x46 + n % 37, 1, 22) for n in (60, 64, 67)] + [(0x46 + n % 37, 0, 8) for n in (60, 64, 67)], leds
    uc.mem_write(SEL_TRACK, b"\2")
    leds.clear()
    pad(1)
    assert leds == [], "only the selected track lights"
    uc.mem_write(SEL_TRACK, b"\1")
    assert pad(8)[:3] == on(1, 72, 76, 79)
    assert pad(9)[:4] == on(1, 60, 64, 67, 71)
    assert pad(15)[:4] == on(1, 71, 74, 77, 81)
    assert pad(16)[:4] == on(1, 72, 76, 79, 83)
    track_key(1, 2, 2)                           # D minor
    assert pad(1)[:3] == on(1, 62, 65, 69) and pad(9)[:4] == on(1, 62, 65, 69, 72)
    track_key(1, 9, 0, octave=2)                 # A Chromatic -> A major, one octave lower (keys from 48)
    assert pad(1)[:3] == on(1, 57, 61, 64)
    track_key(1, 0, 1)

    # capture: keys held on track 2 (index 1) are kept sorted, other tracks ignored, no sound on capture
    keys((67, 1), (60, 1), (70, 1), (64, 1), (40, 2))
    assert pad(3) == [] and not stock
    keys()
    assert pad(3) == on(1, 60, 64, 67, 70) + off(1, 60, 64, 67, 70)
    keys((72, 1), (60, 1), (64, 1), (67, 1), (71, 1), (74, 1), (60, 1))   # 6 different: lowest 5, duplicate skipped
    pad(4)
    keys()
    assert pad(4) == on(1, 60, 64, 67, 71, 72) + off(1, 60, 64, 67, 71, 72)
    # kept chords move with the octave (kept as played at octave 0 = byte 3)
    track_key(1, 0, 1, octave=1)
    assert pad(4) == on(1, 36, 40, 43, 47, 48) + off(1, 36, 40, 43, 47, 48), "two octaves down"
    keys((45, 1), (38, 1), (41, 1))              # captured at octave 1
    assert pad(6) == []
    keys()
    assert pad(6) == on(1, 38, 41, 45) + off(1, 38, 41, 45), "plays where it was captured"
    track_key(1, 0, 1, octave=0)
    assert pad(6) == on(1, 26, 29, 33) + off(1, 26, 29, 33)
    track_key(1, 0, 1, octave=7)                 # top of the byte range
    assert pad(4) == on(1, 108, 112, 115, 119, 120) + off(1, 108, 112, 115, 119, 120)
    track_key(1, 0, 1)
    assert pad(6) == on(1, 62, 65, 69) + off(1, 62, 65, 69)
    # Erase + step forgets it: back to the scale chord
    held(ERASE, True)
    assert pad(4) == [] and not stock
    held(ERASE, False)
    assert pad(4)[:3] == on(1, 65, 69, 72)
    # Shift + Exit undoes the last chord change, again redoes it
    held(SHIFT, True)
    tap(EXIT)
    held(SHIFT, False)
    assert not stock, stock
    assert pad(4) == on(1, 60, 64, 67, 71, 72) + off(1, 60, 64, 67, 71, 72), "erase undone"
    held(SHIFT, True)
    tap(EXIT)
    held(SHIFT, False)
    assert pad(4)[:3] == on(1, 65, 69, 72), "erase redone"
    keys((62, 1), (65, 1))
    pad(4)
    keys()
    held(SHIFT, True)
    tap(EXIT)
    held(SHIFT, False)
    assert pad(4)[:3] == on(1, 65, 69, 72), "capture undone"
    tap(EXIT)                                    # Exit alone stays stock
    assert stock == [("press", EXIT), ("release", EXIT)]
    stock.clear()
    # a pad held while the mode goes off still sends its note offs
    sent.clear()
    event("press", STEP1 + 2)
    combo(T2_SEQ, T2_ARP)
    assert uc.mem_read(STATE + 4, 1) == b"\0"
    event("release", STEP1 + 2)
    assert sent == on(1, 60, 64, 67, 70) + off(1, 60, 64, 67, 70) and not stock, (sent, stock)
    tap(STEP1 + 2)
    assert stock == [("press", STEP1 + 2), ("release", STEP1 + 2)]
    stock.clear()

    # track 3 has its own chords and channel; drum pads switch chord pads off
    combo(T3_SEQ, T3_ARP)
    assert uc.mem_read(STATE + 4, 1) == b"\3"
    track_key(2, 7, 1)
    assert pad(1)[:3] == on(2, 67, 71, 74) and pad(3)[:3] == on(2, 71, 74, 78)
    combo(DRUM, SEQ_BTN)
    assert uc.mem_read(STATE + 4, 1) == b"\1"
    combo(T2_SEQ, T2_ARP)

    # Save Project carries the chord table into the staged second sector, then programs it
    slot_sector = FLASH + 2 * 0x20000 + 0x10000
    flash[slot_sector - FLASH + 0xFFF0:slot_sector - FLASH + 0x10000] = b"Amazing Grace\0\0\0"
    uc.mem_write(STAGE, bytes(flash[slot_sector - FLASH:slot_sector - FLASH + 0x10000]))
    start(save, {UC_ARM_REG_R0: 0x20009999, UC_ARM_REG_R1: slot_sector})
    assert sector_writes == [slot_sector]
    blk = flash[slot_sector - FLASH + 0xFEF0:slot_sector - FLASH + 0xFFF0]
    assert blk[:4] == b"CHD1" and blk[8 + 2 * 5:8 + 3 * 5] == bytes((60, 64, 67, 70, 0xFF)), blk[:30].hex()
    assert blk[8 + 3 * 5:8 + 4 * 5] == b"\xff" * 5, "erased pad saved empty"
    assert flash[slot_sector - FLASH + 0xFFF0:slot_sector - FLASH + 0xFFFD] == b"Amazing Grace", "name kept"

    # another project: its own (empty) chords from flash; back again: the saved chords from flash
    uc.mem_write(STATE + 6, b"\x07")             # forget the RAM copy's project tag
    track_key(1, 0, 1, project=5)
    assert pad(3)[:3] == on(1, 64, 67, 71)
    track_key(1, 0, 1, project=2)
    assert pad(3) == on(1, 60, 64, 67, 70) + off(1, 60, 64, 67, 70)

    # after a project switch there is nothing to undo: Shift + Exit is the stock undo
    held(SHIFT, True)
    tap(EXIT)
    held(SHIFT, False)
    assert stock == [("press", EXIT), ("release", EXIT)], stock
    stock.clear()
    # in drum pad mode Shift + Exit is always stock
    combo(DRUM, SEQ_BTN)
    held(SHIFT, True)
    tap(EXIT)
    held(SHIFT, False)
    assert stock == [("press", EXIT), ("release", EXIT)], stock
    stock.clear()
    combo(T2_SEQ, T2_ARP)
    # root chords: Seq + Mute on track 2; keys on that track only pick the root (silent)
    keysend = target(KEY_SEND_CALL)
    assert keysend != MIDI_SEND
    combo(T2_SEQ, T2_MUTE)
    assert not stock and uc.mem_read(STATE + 4, 1) == bytes((5 + 1,)), (stock, uc.mem_read(STATE + 4, 1))
    tap(T2_MUTE)                                 # Mute alone stays stock
    assert stock == [("press", T2_MUTE), ("release", T2_MUTE)]
    stock.clear()
    track_key(1, 0, 1, octave=2)                 # C major, octave 2: keys 48-84
    assert pad(3) == on(1, 48, 52, 55) + off(1, 48, 52, 55), "no key yet: the scale root on the lowest key"

    def key(note: int, track: int) -> list[bytes]:
        keys((note, track))                      # key 0 held, as the event loop sets it before sending
        sp = 0x200FE000
        uc.mem_write(sp + 0x6A, b"\0")
        sent.clear()
        start(keysend, {UC_ARM_REG_SP: sp, UC_ARM_REG_R0: PORT, UC_ARM_REG_R1: 0x640000 | note << 8 | 0x90, UC_ARM_REG_R2: 3})
        out = list(sent)
        sent.clear()
        keys()
        return out

    assert key(50, 1) == [], "a key on the root-chord track is silent"
    assert popups[-1] == "Root: D", popups
    assert key(64, 2) == [bytes((0x90, 64, 0x64))], "keys on other tracks are sent"
    assert popups[-1] == "E4", popups
    expect = {1: [50, 62], 2: [50, 52, 57], 3: [50, 53, 57], 4: [50, 55, 57], 5: [50, 57, 62], 6: [50, 53, 57, 59],
              7: [50, 53, 57, 60], 8: [62, 65, 69], 9: [50, 53, 57, 60, 64], 10: [50, 53, 57, 64], 11: [50, 53, 60, 64, 67],
              12: [53, 57, 62], 13: [50, 53, 60, 64, 71], 14: [57, 62, 65], 15: [50, 55, 57, 60], 16: [50, 53, 57]}
    for step, notes in expect.items():
        got = pad(step)
        assert got == on(1, *notes) + off(1, *notes), (step, got)
    # near the top key (84) chords move down an octave to stay on the keys, voicing kept
    key(79, 1)
    assert pad(3)[:3] == on(1, 67, 71, 74) and pad(1)[:2] == on(1, 67, 79) and pad(2)[:3] == on(1, 67, 69, 74)
    assert pad(13)[:5] == on(1, 55, 59, 65, 69, 76), "two octaves down"
    # a key held when the step is pressed picks the root even if its note-on never came by
    keys((65, 1), (62, 1), (64, 2))
    assert pad(3)[:3] == on(1, 62, 65, 69), "lowest held key on the track is the root"
    keys()
    assert pad(3)[:3] == on(1, 62, 65, 69), "root kept after the key is let go"
    key(49, 1)                                   # C#, not in C major: the root itself, then scale notes above it
    assert pad(3)[:3] == on(1, 49, 52, 55)
    track_key(1, 0, 2, octave=2)                 # C minor
    key(48, 1)
    assert pad(3)[:3] == on(1, 48, 51, 55) and pad(7)[:4] == on(1, 48, 51, 55, 58)
    track_key(1, 0, 1)
    # Shift + Exit is stock here; chord pads take over and keys sound again on that track
    held(SHIFT, True)
    tap(EXIT)
    held(SHIFT, False)
    assert stock == [("press", EXIT), ("release", EXIT)]
    stock.clear()
    combo(T2_SEQ, T2_ARP)
    assert uc.mem_read(STATE + 4, 1) == b"\2" and key(50, 1) == [bytes((0x90, 50, 0x64))]
    combo(T1_MUTE - 2, T1_MUTE)                  # track 1: Seq + Mute
    assert uc.mem_read(STATE + 4, 1) == b"\5" and key(50, 0) == [] and key(50, 1) != []
    combo(T1_MUTE - 2, T1_MUTE)
    assert uc.mem_read(STATE + 4, 1) == b"\0"
    combo(T2_SEQ, T2_ARP)

    # recording: what the steps play is recorded on the selected track; notes get their length at release
    uc.mem_write(REC_X, b"\x05")
    uc.mem_write(SEL_TRACK, b"\1")
    track_key(1, 0, 1)
    recs.clear()
    pad(1)
    assert recs == [], "not recording"
    uc.mem_write(RECORDING, b"\1")
    next_slot[0] = 10
    pad(1)
    assert recs == [("rec", 1, 60, 100, 5), ("rec", 1, 64, 100, 5), ("rec", 1, 67, 100, 5),
                    ("end", 1, 10), ("end", 1, 11), ("end", 1, 12)], recs
    recs.clear()
    uc.mem_write(SEL_TRACK, b"\2")
    pad(1)
    assert recs == [], "only the selected track records"
    uc.mem_write(SEL_TRACK, b"\1")
    next_slot[0] = 0xC0                          # the KeyStep refused (pattern full): nothing to end
    pad(3)
    assert [x[0] for x in recs] == ["rec"] * 4, recs
    recs.clear()
    uc.mem_write(RECORDING, b"\0")
    uc.mem_write(REC_ARMED, b"\1")
    uc.mem_write(SEQ + 0xC, b"\1")
    next_slot[0] = 20
    pad(1)
    assert len([x for x in recs if x[0] == "rec"]) == 3 and len([x for x in recs if x[0] == "end"]) == 3, "armed + playing"
    recs.clear()
    uc.mem_write(SEQ + 0xC, b"\0")
    pad(1)
    assert recs == [], "armed but stopped"
    uc.mem_write(RECORDING, b"\1")
    # drum hits record as lanes, only while track 1 shows drums
    combo(DRUM, SEQ_BTN)
    uc.mem_write(SEL_TRACK, b"\4")
    next_slot[0] = 30
    pad(5)
    assert recs == [("rec", 0, 4, 100, 4), ("end", 0, 30)], recs
    recs.clear()
    uc.mem_write(SEL_TRACK, b"\0")
    pad(5)
    assert recs == [], "track 1 not showing drums: no drum recording"
    # root chords: the root keys are not recorded on their track; other keys are
    combo(T2_SEQ, T2_MUTE)
    keyrec = target(KEY_REC_CALL)
    uc.mem_write(0x20010000, b"\1\2")
    uc.mem_write(0x20010004, bytes((61,)))                        # key note C#4
    uc.mem_write(0x20000674 + 1 * 0x80 + 61, bytes((62,)))        # track 2's scale map: C# -> D
    start(keyrec, {UC_ARM_REG_R1: 0x20010004, UC_ARM_REG_R3: 0x20010000})
    assert uc.reg_read(UC_ARM_REG_R0) == 0 and recs == [], recs
    assert uc.mem_read(STATE + 120, 1) == bytes((62,)), "the key picks the root, mapped to the scale"
    assert popups[-1] == "Root: D", popups
    track_key(1, 0, 1, octave=2)
    recs.clear()
    assert pad(3)[:3] == on(1, 62, 65, 69), "steps follow the key the handler dropped"
    start(keyrec, {UC_ARM_REG_R3: 0x20010001})
    assert uc.reg_read(UC_ARM_REG_R0) == 7 and recs == [("keyrec", 0x20010001)], recs
    recs.clear()
    uc.mem_write(SEL_TRACK, b"\1")
    next_slot[0] = 40
    pad(3)
    assert [x[:3] for x in recs if x[0] == "rec"] == [("rec", 1, 62), ("rec", 1, 65), ("rec", 1, 69)], recs
    recs.clear()
    uc.mem_write(RECORDING, b"\0")
    combo(T2_SEQ, T2_ARP)

    note_show_tests(uc, start, keysend, keys, sent, popups)

    # step lights (led_flush -> ns_leds): pads shown while a pad mode is on, stock lights back after
    flush = target(LED_FLUSH_CALLS[0])
    assert all(target(c) == flush for c in LED_FLUSH_CALLS), "all 7 LED sends redirected"
    step_led = lambda i: LEDS + 0x1C + (0x35 + i) * 3
    def lights() -> list[tuple[int, int, int]]:
        flushes.clear()
        uc.mem_write(LEDS + 0x184, b"\0" * 0x78)
        start(flush, {UC_ARM_REG_R0: LEDS})
        assert flushes == [LEDS], "the stock send runs after"
        b = uc.mem_read(LEDS + 0x1C + 0x35 * 3, 48)
        return [(b[i * 3], b[i * 3 + 1], b[i * 3 + 2] & 0xF) for i in range(16)]
    sent_flags = lambda: [uc.mem_read(LEDS + 0x184 + 0x35 + i, 1)[0] for i in range(16)]
    stock_leds = [(1, 1, 3) if i % 4 == 0 else (0, 0, 8) for i in range(16)]
    for i, v in enumerate(stock_leds):
        uc.mem_write(step_led(i), bytes(v))
    assert uc.mem_read(STATE + 4, 1) == b"\2"
    combo(T2_SEQ, T2_ARP)                        # chord pads off
    assert uc.mem_read(STATE + 4, 1) == b"\0"
    assert lights() == stock_leds and not any(sent_flags()), "no pad mode: untouched"
    track_key(1, 0, 1)                           # C major, octave 3
    combo(T2_SEQ, T2_ARP)                        # chord pads, track 2 (colour 22 & 15 = 6)
    keys((60, 1), (64, 1), (67, 1), (71, 1))     # Cmaj7 held: capture on step 2
    pad(2)
    keys()
    got = lights()
    table = uc.mem_read(STATE + 128 + 8, 80)                  # track 2's kept chords (earlier tests kept some)
    kept = [table[i * 5] <= 127 for i in range(16)]
    assert kept[1] and not all(kept)
    assert got == [(1, 1, 6) if k else (1, 1, 5) for k in kept], ("kept: track colour, dim; empty: white, dim", got)
    assert all(sent_flags()[i] for i in range(16) if stock_leds[i] != got[i]), "changed lights are sent"
    assert lights() == got and not any(sent_flags()), "nothing changed: nothing sent"
    event("press", STEP1 + 4)                    # pad 5 held
    assert lights()[4] == (1, 0, 5), "held: white, bright"
    event("release", STEP1 + 4)
    assert lights()[4] == (1, 1, 5)
    keys((64, 1), (67, 1), (72, 1))              # C E G on the keys (any octave): scale chord pads 1 and 8
    got = lights()
    assert not kept[0] and not kept[7]
    assert got[0] == (1, 0, 6) and got[7] == (1, 0, 6), ("matching pads: track colour, bright", got)
    keys((60, 1), (64, 1), (67, 1), (71, 1))     # Cmaj7: the kept chord on pad 2 (and the scale 7th on pad 9)
    got = lights()
    assert got[1] == (1, 0, 6) and got[8] == (1, 0, 6) and got[0] == (1, 1, 6 if kept[0] else 5), got
    keys((64, 2), (67, 2), (72, 2))              # keys on another track: no match
    assert lights()[0] == (1, 1, 6 if kept[0] else 5)
    keys()
    uc.mem_write(step_led(3), bytes((1, 0, 9)))   # the stock firmware sets a step (playhead) meanwhile
    assert lights()[3] == (1, 1, 6 if kept[3] else 5), "the pads stay shown"
    held(SHIFT, False)
    combo(T2_SEQ, T2_ARP)                        # off: the stock lights come back
    got = lights()
    assert got[3] == (1, 0, 9) and all(got[i] == stock_leds[i] for i in range(16) if i != 3), got
    assert lights() == got, "stays stock"
    combo(DRUM, SEQ_BTN)                         # drum pads: every lane in track 1's colour (11), dim
    assert lights() == [(1, 1, 11)] * 16
    combo(DRUM, SEQ_BTN)
    assert lights()[0] == stock_leds[0]
    uc.mem_write(step_led(0), bytes((0, 0, 8)))  # another LED object (not *0x20001490) is never touched
    combo(T2_SEQ, T2_ARP)
    flushes.clear()
    start(flush, {UC_ARM_REG_R0: 0x20070000})
    assert flushes == [0x20070000] and uc.mem_read(0x20070000 + 0x1C + 0x35 * 3, 3) == b"\0\0\0"
    lights()                                     # chord pads stay on for the tests below
    bass_tests(uc, start, held, tap, stock, popups, rebuilt)

    # channel OFF: pads are taken, nothing sent
    glob(76, 127)
    assert pad(1) == [] and not stock
    assert all(sp % 8 == 0 for sp in sps), "stack alignment at MIDI send"
    print("PASS: stock passthrough when off, drum pads (Drum+Seq), Seq alone stock, chord pads (Seq+Arp) "
          "switching drum pads off and back, scale chords (major, minor, Chromatic->major, octave, 7ths), "
          "capture sorted/dedup/5 max/other tracks ignored, Erase+step, Shift+Exit undo/redo of capture and erase (else stock), note offs after mode off, track 3 channel, "
          "Save Project stages chords and keeps the name, root chords (Seq+Mute toggle, silent root keys on its track only, all 16 step chords in C major from D, root outside the scale, minor, exclusive with pads), per-project load from flash, recording (selected track only, chords and drum lanes, note length at release, armed+playing, refused notes, root keys not recorded), key lights (drum on track 1 as drums, chords in the track colour, off on release, selected track only), screen names notes and chords (keys, Chord mode, chord and root-chord pads, root keys, drum lanes; not menus), step lights show the pads (kept/empty/held/matching the keys, stock lights restored), channel OFF, stack alignment")


def page_bass(chords: list[tuple[int, list[int]]], length: int) -> dict[str, list] | None:
    """makeBass from the KeyStep Con page, run in node on the same part: the firmware must write the same notes."""
    import json
    import shutil
    import subprocess
    import re as _re
    if not shutil.which("node") or not PAGE_SRC.exists():
        return None
    data, ui, editor = ((PAGE_SRC / f).read_text() for f in ("1-data.js", "5-ui.js", "6b-editor.js"))
    pick = lambda text, start, end: text[text.index(start):text.index(end, text.index(start))]
    js = "\n".join([
        _re.search(r"^const clamp=.*$", data, _re.M).group(0),
        _re.search(r"^const gateSteps=.*$", ui, _re.M).group(0),
        _re.search(r"^const G=gateSteps,Graw=.*$", ui, _re.M).group(0),
        pick(editor, "const BASS_STYLES", "const noteName"),
        f"const src={{len:{length},root:0,scale:1,steps:Array.from({{length:64}},()=>({{on:false,passes:15,notes:[]}}))}};",
        f"for(const [i,ps] of {json.dumps(chords)}){{src.steps[i].on=true;ps.forEach(p=>src.steps[i].notes.push({{pitch:p,gate:7,vel:90,shift:49,rand:100}}))}}",
        "const out={};for(const [k] of BASS_STYLES){const b=makeBass(src,k);out[k]=b.steps.flatMap((s,i)=>s.notes.map(n=>[i,n.pitch,n.gate,n.vel,n.shift,n.rand]))}",
        "console.log(JSON.stringify(out))"])
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def note_show_tests(uc, start, keysend, keys, sent, popups) -> None:
    """The screen names the notes held on a key's track after the key is sent (track 3 here)."""
    proj, t = 2, 2
    uc.mem_write(CUR_PROJECT, bytes((proj,)))
    trk = SEQ + proj * 0xFEC + t * 0x16 + 0x1752
    uc.mem_write(trk, bytes((3, 0x78, 0xFF)))                     # octave 0, Chord mode off, no chord
    uc.mem_write(0x20000674 + t * 0x80, bytes(range(128)))        # scale map: Chromatic

    def show(*held_keys: tuple[int, int]) -> str | None:
        keys(*held_keys)                                          # slot 0 is the key being sent
        sp = 0x200FE000
        uc.mem_write(sp + 0x6A, b"\0")
        popups.clear()
        sent.clear()
        start(keysend, {UC_ARM_REG_SP: sp, UC_ARM_REG_R0: PORT, UC_ARM_REG_R1: 0x640000 | held_keys[0][0] << 8 | 0x90,
                        UC_ARM_REG_R2: 3})
        assert sent == [bytes((0x90, held_keys[0][0], 0x64))], "the key is still sent"
        keys()
        assert len(popups) <= 1
        return popups[0] if popups else None

    k = lambda *notes: [(n, t) for n in notes]
    assert show(*k(64)) == "E4"
    assert show(*k(21)) == "A0" and show(*k(0)) == "C-1"
    assert show(*k(60, 64, 67)) == "C\nC4 E4 G4"
    assert show(*k(67, 60, 64)) == "C\nC4 E4 G4", "held order does not matter"
    assert show(*k(64, 67, 72)) == "C/E\nE4 G4 C5"
    assert show(*k(57, 60, 64, 67)) == "Am7\nA3 C4 E4 G4"
    assert show(*k(61, 65, 68)) == "C#\nC#4 F4 G#4"
    assert show(*k(62, 65, 69, 72)) == "Dm7\nD4 F4 A4 C5"
    assert show(*k(67, 71, 74, 77)) == "G7\nG4 B4 D5 F5"
    assert show(*k(60, 67)) == "C5\nC4 G4"
    assert show(*k(62, 67, 69)) == "Dsus4\nD4 G4 A4"
    assert show(*k(60, 61)) == "C C#\nC4 C#4", "no known chord: the notes"
    assert show(*k(60, 72)) == "C\nC4 C5", "octaves of one note"
    assert show(*k(60, 62, 64, 65, 67, 69, 71)) == "C D E F G A B\nC4 D4 E4 F4 G4..", "long lists are cut"
    assert show((64, t), (60, 1)) == "E4", "only the key's own track"
    # Chord mode: each key adds the track's chord, every note through the scale map (C major: G# -> G)
    uc.mem_write(trk, bytes((0x83, 0x78, 64, 4, 7, 0)))
    uc.mem_write(0x20000674 + t * 0x80 + 68, bytes((67,)))
    assert show(*k(64)) == "Em\nE4 G4 B4"
    assert show(*k(60)) == "C\nC4 E4 G4"
    uc.mem_write(trk, bytes((3, 0x78, 0xFF)))
    uc.mem_write(0x20000674 + t * 0x80 + 68, bytes((68,)))
    # nothing for track 1 in drum mode or a key without a track
    uc.mem_write(CUR_PROJECT, bytes((proj,)))
    uc.mem_write(SEQ + proj * 0xFEC + 0x1753, b"\1")
    assert show((36, 0)) is None
    uc.mem_write(SEQ + proj * 0xFEC + 0x1753, b"\0")
    assert show((36, 0)) == "C2"
    assert show((36, 4)) is None
    # no popup over menus or other screens (UI state above 0x60), as the stock popup
    uc.mem_write(UI_OBJ + 0xC, b"\x70")
    assert show(*k(64)) is None
    uc.mem_write(UI_OBJ + 0xC, b"\0")


def bass_tests(uc, start, held, tap, stock, popups, rebuilt) -> None:
    """Hold Seq on track 3, press Track 1: track 3's pattern becomes a bass line from track 1's."""
    proj, src_t, src_n, dst_t, dst_n = 2, 0, 3, 2, 5
    uc.mem_write(UI_PTR, UI_OBJ.to_bytes(4, "little"))
    uc.mem_write(UI_OBJ + 0xC, b"\0")
    uc.mem_write(POPUP_CTX_PTR, POPUP_CTX_VAL.to_bytes(4, "little"))
    uc.mem_write(CUR_PROJECT, bytes((proj,)))
    uc.mem_write(CUR_PAT + src_t, bytes((src_n,)))
    uc.mem_write(CUR_PAT + dst_t, bytes((dst_n,)))
    uc.mem_write(SEQ + proj * 0xFEC + 0x1753, b"\0")              # track 1 in sequencer mode
    notes = lambda t, n: NOTES + proj * 0xF000 + t * 0x3C00 + n * 0x3C0
    stepof = lambda t, n: STEPOF + proj * 0x3000 + t * 0xC00 + n * 0xC0
    passes = lambda t, n: PASSES + ((proj * 5 + t) * 16 + n) * 0x20
    header = lambda t, n: SEQ + proj * 0xFEC + t * 0x140 + n * 0x14 + 0x930
    chords = [(0, [60, 64, 67]), (2, [60, 64, 67]), (4, [57, 60, 64, 67]), (8, [57, 60, 65]), (12, [55, 59, 62])]

    def source(chords: list[tuple[int, list[int]]], length: int = 16) -> None:
        nb, sb = bytearray(b"\xff" * 0x3C0), bytearray(b"\xff" * 0xC0)
        slot, on = 0, 0
        for step, ps in chords:
            for p_ in reversed(ps):                                 # stored out of order: the root must not depend on it
                nb[slot * 5:slot * 5 + 5] = bytes((p_, 7, 90 - slot % 3, 49, 100))
                sb[slot] = step
                slot += 1
            on |= 1 << step
        uc.mem_write(notes(src_t, src_n), bytes(nb))
        uc.mem_write(stepof(src_t, src_n), bytes(sb))
        uc.mem_write(passes(src_t, src_n), b"\xff" * 0x20)
        hdr = bytearray(0x14)
        hdr[0:2] = (0xAAAA).to_bytes(2, "little")
        hdr[2:7] = bytes((60, 7, 100, 49, 100))
        hdr[8], hdr[0xA], hdr[0xB] = length - 1, 0x02, 0x21            # root C (high nibble), scale Major (low nibble)
        hdr[0xC:0x14] = on.to_bytes(8, "little")
        uc.mem_write(header(src_t, src_n), bytes(hdr))

    def target_notes() -> list[tuple]:
        nb, sb = uc.mem_read(notes(dst_t, dst_n), 0x3C0), uc.mem_read(stepof(dst_t, dst_n), 0xC0)
        out = [(sb[s], *nb[s * 5:s * 5 + 5]) for s in range(192) if sb[s] != 0xFF]
        assert all(nb[s * 5] == 0xFF for s in range(192) if sb[s] == 0xFF), "unused slots hold no note"
        return out

    # the target pattern starts with old notes, an odd default note and a scale of its own
    uc.mem_write(notes(dst_t, dst_n), bytes((72, 20, 80, 49, 100)) * 192)
    uc.mem_write(stepof(dst_t, dst_n), bytes(range(64)) * 3)
    th = bytearray(0x14)
    th[0:2] = (0xBBBB).to_bytes(2, "little")
    th[2:7] = bytes((60, 9, 101, 50, 99))
    th[8], th[0xA], th[0xB] = 63, 0x75, 0x05
    uc.mem_write(header(dst_t, dst_n), bytes(th))
    uc.mem_write(STEP_INDEX + dst_t * 0x400, b"\x07" * 0x400)        # stale step index
    source(chords)
    stock.clear()

    # Seq on track 3 held, Track 1 pressed: Root (the default style)
    held(T3_SEQ, True)
    tap(T1_TRACK)
    assert not stock, "the Track press and release are taken"
    got = target_notes()
    names = lambda ns: " ".join(f"{s + 1}:{p}" for s, p, *_ in ns)
    assert names(got) == "1:36 5:45 9:41 13:43", names(got)
    assert [g for _, _, g, *_ in got] == [31] * 4, "held to the next chord: 4 steps = gate 31"
    assert [v for _, _, _, v, *_ in got] == [90] * 4, "loudest note of the chord"
    assert popups[-1] == "Bass: Root\nfrom track 1", popups
    h = uc.mem_read(header(dst_t, dst_n), 0x14)
    assert h[0:2] == b"\xaa\xaa" and h[8] == 15, "state: holds data; length from the chord pattern"
    assert h[0xA] == 0x05 and h[0xB] & 0x0F == 1 and h[0xB] & 0x40, "root C and scale Major copied, edited flag set"
    assert int.from_bytes(h[0xC:0x14], "little") == (1 << 0) | (1 << 4) | (1 << 8) | (1 << 12), "steps on"
    unused = uc.mem_read(notes(dst_t, dst_n) + 191 * 5, 5)
    assert unused == bytes((0xFF, 9, 101, 50, 99)), "cleared slots keep the pattern's default note, as the device clears"
    assert uc.mem_read(passes(dst_t, dst_n), 0x20) == b"\xff" * 0x20
    idx = uc.mem_read(STEP_INDEX + dst_t * 0x400, 0x400)
    assert idx[0] == 0 and idx[1] == 0xFF and idx[4 * 16] == 1 and idx[12 * 16] == 3 and idx[16] == 0xFF, "step index rebuilt"
    assert rebuilt[-1] == dst_t, "scale map rebuilt for the bass track"

    # still holding Seq: steps 1-5 switch the style
    expect = {
        2: "1:36 3:43 5:45 7:52 9:41 11:48 13:43 15:50",
        3: " ".join(f"{i + 1}:{r + (12 if (i % 4) % 2 else 0)}" for i, r in enumerate([36] * 4 + [45] * 4 + [41] * 4 + [43] * 4)),
        4: " ".join(f"{i + 1}:{r}" for i, r in enumerate([36] * 4 + [45] * 4 + [41] * 4 + [43] * 4)),
        5: "1:36 3:36 5:45 9:41 13:43",
    }
    texts = {2: "Root + 5th", 3: "Octaves", 4: "Pulse", 5: "Follow"}
    for step, want in expect.items():
        tap(STEP1 + step - 1)
        got = target_notes()
        assert names(got) == want, (step, names(got))
        assert popups[-1] == f"Bass: {texts[step]}\nfrom track 1", popups[-1]
    assert [g for _, _, g, *_ in target_notes()] == [7] * 5, "Follow keeps the part's gates"
    assert not stock
    page = page_bass([(s, ps) for s, ps in chords], 16)
    if page is not None:
        for step, key in ((1, "root"), (2, "fifth"), (3, "oct"), (4, "pulse"), (5, "follow")):
            tap(STEP1 + step - 1)
            fw = [[s, p, g, v, sh, r] for s, p, g, v, sh, r in target_notes()]
            pg = [[s, p, g, 90, sh, r] for s, p, g, v, sh, r in page[key]]   # the page test part has one velocity
            assert [x[:3] + x[4:] for x in fw] == [x[:3] + x[4:] for x in pg], (key, fw, pg)
    held(T3_SEQ, False)
    tap(T3_SEQ)                                                       # the Seq release ends it
    assert stock == [("press", T3_SEQ), ("release", T3_SEQ)], stock
    stock.clear()
    before = target_notes()
    assert uc.mem_read(STATE + 480, 1) == b"\xff", "Seq let go: no bass track"
    tap(STEP1 + 1)                                                    # steps go back to what they did (root chords here)
    assert target_notes() == before and not popups[-1].startswith("Bass"), "the step plays (and names) its chord"
    stock.clear()

    # the style is kept: the next Seq + Track uses Follow; Seq on the same row + its Track is stock
    held(T3_SEQ, True)
    source([(0, [62, 65, 69]), (8, [64, 67, 71])], length=12)
    tap(T1_TRACK)
    assert names(target_notes()) == "1:38 9:40" and popups[-1].startswith("Bass: Follow")
    assert uc.mem_read(header(dst_t, dst_n) + 8, 1) == bytes((11,))
    tap(0x23)                                                         # track 3's own Track button
    assert stock == [("press", 0x23), ("release", 0x23)], stock
    stock.clear()
    held(T3_SEQ, False)

    # refused: an empty chord pattern, a chord track in drum mode (target untouched)
    before = target_notes()
    source([])
    held(T3_SEQ, True)
    tap(T1_TRACK)
    assert popups[-1] == "Bass: no notes\nin track 1" and target_notes() == before
    source(chords)
    uc.mem_write(SEQ + proj * 0xFEC + 0x1753, b"\1")
    tap(T1_TRACK)
    assert popups[-1] == "Bass: not with\ndrum mode on track 1" and target_notes() == before
    uc.mem_write(SEQ + proj * 0xFEC + 0x1753, b"\0")
    # no popup on screens that do not take one (08020e3c's table), the bass is still written
    n = len(popups)
    uc.mem_write(UI_OBJ + 0xC, b"\x2e")
    tap(T1_TRACK)
    assert len(popups) == n and names(target_notes()) == "1:36 3:36 5:45 9:41 13:43"
    uc.mem_write(UI_OBJ + 0xC, b"\0")
    held(T3_SEQ, False)
    tap(T3_SEQ)
    stock.clear()
    print("bass: Seq + Track writes the bass, steps 1-5 switch style, page makeBass gives the same notes"
          + ("" if page is not None else " (node or page source missing: cross-check skipped)"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: test_pad_hooks.py patched-main.bin")
    run(Path(sys.argv[1]))
