#!/usr/bin/env python3
"""Write a set list of songs to KeyStep Pro projects: name, chord shape, chord mode, key, chord pads.

Per project: the name; each planned track's chord shape (p0x57) with chord
mode on (p0x56 bit 0x10; a track with "chord": false gets it cleared); and for full-chord plans each track's root (p0x6B)
and scale (p0x6C) on all 16 patterns, plus the User 1 scale mask when used.

Root/scale live in patterns and only count when the pattern is valid. A
default pattern's stored bytes may be junk (erased flash), so before marking
it valid the tool writes every pattern parameter with the firmware's default
values (read from the getter, which reports defaults for default patterns).

Chord pads (KSCON build 5+, "pads" in the plan: track -> up to 16 chords): the song's chords on
that track's step pads, written last, straight to flash. They cannot be read back over SysEx,
so only --emulate verifies them; on the device, play them (hold Seq + press Arp on track 2).

Firmware quirk handled: a SysEx commit (cmd 06) flips every pattern's
valid/default marker unless its state is re-sent, so the tool reads the state
of all 16 scenes (item 0x79 p0x26) and all 80 patterns (track control 0x7A and
tracks 1-4, p0x28) first and writes them back unchanged.

    plans.json: [{"project": 1, "id": "mysong", "title": "My Song", "plan": "full", "shape": [64, 68, 71],
                  "tracks": [{"n": 1, "root": 4, "scale": "major"}]}, ...]
    tools/ksp_setlist.py plans.json --emulate          # offline, real firmware code
    tools/ksp_setlist.py plans.json --only 15 --send   # one project on the device
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ksp_link import CoreMIDILink, EmuLink, Link  # noqa: E402

TRACK_ITEMS = (0x7B, 0x7C, 0x7D, 0x7E)           # tracks 1-4
STATE_ITEMS = (0x7A,) + TRACK_ITEMS                # 0x7A track control has its own pattern states
P_TRACK_STATE, P_PATTERN_STATE, P_MODE, P_CHORD = 0x27, 0x28, 0x56, 0x57
SCENE_ITEM, P_SCENE_STATE = 0x79, 0x26
CHORD_MODE_BIT = 0x10
P_ROOT, P_SCALE = 0x6B, 0x6C
SCALES = {"chromatic": 0, "major": 1, "minor": 2, "user1": 8}
PROJECT_ITEM, P_USER1 = 0x78, (0x65, 0x66, 0x67)   # user scale 1 mask: bits 0-6, 7-11, (unused)
# Project-level settings of a stock project (120 BPM, scene 1, user scales all notes), as
# (param, index, value). Any project SET also marks the project block valid (0xAAAA); a
# project whose block is invalid (e.g. erased) loads as defaults on the panel (C Chromatic,
# 120 BPM) although its patterns read back fine over SysEx.
PROJECT_DEFAULTS = ([(0x37, i, 0) for i in range(1, 5)] + [(0x38, i, 0) for i in range(1, 4)]
                    + [(0x44, 1, 68), (0x45, 1, 4), (0x46, 1, 96), (0x47, 1, 93), (0x48, 1, 0),
                       (0x49, 1, 16), (0x4A, 1, 50), (0x4B, 1, 0), (0x65, 1, 127), (0x66, 1, 31),
                       (0x67, 1, 0), (0x68, 1, 127), (0x69, 1, 31), (0x6A, 1, 0)]
                    + [(0x7B, i, 0) for i in range(1, 6)])
VOICES, STEPS = 3, 64
# Pattern parameters (index shapes from classifier 08009102 / parser 080093e6).
SINGLE = {0x7B: [0x14, 0x15, 0x16, 0x17, 0x19, 0x1A, 0x1B, 0x1C, 0x61, 0x62, 0x63, 0x64,
                 0x6D, 0x6E, 0x6F, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79],
          "other": [0x14, 0x15, 0x16, 0x17, 0x61, 0x62, 0x63, 0x64, 0x6D, 0x6E, 0x6F, 0x70, 0x71]}
PER_STEP = {0x7B: [0x30, 0x31, 0x33, 0x34, 0x35, 0x36], "other": [0x30, 0x31]}
PER_VOICE_STEP = [0x32, 0x6D, 0x6E, 0x6F, 0x70, 0x71]
NAME_OVERRIDES: dict[str, str] = {}   # titles that need a shorter 16-character ASCII name: {"Long Title": "Short"}
PATCHED = Path(__file__).resolve().parents[1] / "firmware/patched/kscon_keysteppro_main__fw2_5_20_2085__2024_03_04.bin"


def display_name(title: str) -> str:
    name = NAME_OVERRIDES.get(title, title)
    if not 1 <= len(name) <= 16 or not name.isascii():
        raise SystemExit(f"name {name!r} must be 1..16 ASCII characters; add it to NAME_OVERRIDES")
    return name


def chord_bytes(shape: list[int]) -> list[int]:
    root = shape[0]
    offsets = [n - root for n in shape[1:]]
    if not 0 <= root <= 127 or any(not 0 < o < 0x7F for o in offsets) or len(shape) > 16:
        raise ValueError(f"bad chord shape {shape}")
    return [root, *offsets] + [0x7F] * (16 - len(shape))


def read_states(link: Link, proj: int) -> dict[tuple[int, int, int], int | None]:
    """Valid/default state of every scene and pattern (3 = valid, 2 = default)."""
    keys = [(SCENE_ITEM, P_SCENE_STATE, i) for i in range(1, 17)]
    keys += [(item, P_PATTERN_STATE, i) for item in STATE_ITEMS for i in range(1, 17)]
    return {k: link.get(proj, k[1], k[0], k[2]) for k in keys}


def project_block_bad(link: Link, proj: int) -> bool:
    """True when the project-level settings read as junk (erased block): no reply or tempo out of range."""
    tempo = [link.get(proj, p, PROJECT_ITEM, 1) for p in (0x46, 0x47, 0x48)]
    scene = link.get(proj, 0x4B, PROJECT_ITEM, 1)
    if None in tempo or scene is None or scene > 15:
        return True
    bpm100 = tempo[0] | tempo[1] << 7 | tempo[2] << 14   # 12000 = 120.00 BPM
    return not 3000 <= bpm100 <= 30000
def read_pattern_defaults(link: Link, proj: int, item: int, pat: int) -> list[tuple[int, list[int], list[int]]] | None:
    """(param, index path, values) for every parameter of a default pattern."""
    key = item if item == 0x7B else "other"
    out = []
    for p in SINGLE[key]:
        out.append((p, [pat], link.get_many(proj, p, item, [pat], 1)))
    for p in PER_STEP[key]:
        out.append((p, [pat, 1], link.get_many(proj, p, item, [pat, 1], STEPS)))
    for p in PER_VOICE_STEP:
        for v in range(1, VOICES + 1):
            out.append((p, [pat, v, 1], link.get_many(proj, p, item, [pat, v, 1], STEPS)))
    return None if any(vals is None for _, _, vals in out) else out


def user_mask_parts(intervals: list[int]) -> list[int]:
    mask = sum(1 << i for i in set(intervals))
    if not 0 < mask < 0x1000 or not mask & 1:
        raise ValueError(f"bad user scale {intervals}")
    return [mask & 0x7F, mask >> 7, 0]


def write_project(link: Link, song: dict, log=print) -> list[str]:
    """Returns a list of verification problems (empty = verified)."""
    proj, problems = song["project"], []
    tracks = [t["n"] for t in song["tracks"]]
    chord_tracks = [t["n"] for t in song["tracks"] if t.get("chord", True)]
    chord = chord_bytes(song["shape"])
    link.open(proj)
    states = read_states(link, proj)
    if None in states.values():
        return [f"no reply reading pattern states ({sum(v is None for v in states.values())} missing)"]
    modes = {t: link.get(proj, P_MODE, TRACK_ITEMS[t - 1], 1) for t in tracks}
    if None in modes.values():
        return ["no reply reading track modes"]
    keyed = [t for t in song["tracks"] if t["scale"] != "chromatic"]
    defaults = {}
    for t in keyed:
        item = TRACK_ITEMS[t["n"] - 1]
        pat = next((i for i in range(1, 17) if states[(item, P_PATTERN_STATE, i)] == 2), None)
        if pat is not None:
            defaults[item] = read_pattern_defaults(link, proj, item, pat)
            if defaults[item] is None:
                return [f"no reply reading default pattern content (track {t['n']})"]
    for t in tracks:
        item = TRACK_ITEMS[t - 1]
        if t in chord_tracks:
            for i, b in enumerate(chord, 1):
                link.set(proj, P_CHORD, item, i, [b])
            link.set(proj, P_MODE, item, 1, [modes[t] | CHORD_MODE_BIT])
        else:
            link.set(proj, P_MODE, item, 1, [modes[t] & ~CHORD_MODE_BIT])
    if project_block_bad(link, proj):
        log(f"P{proj}: project settings unreadable or out of range; writing stock values")
        for param, i, value in PROJECT_DEFAULTS:
            link.set(proj, param, PROJECT_ITEM, i, [value])
    target = dict(states)
    for t in keyed:
        item = TRACK_ITEMS[t["n"] - 1]
        for pat in range(1, 17):
            if states[(item, P_PATTERN_STATE, pat)] == 2:
                for param, path, vals in defaults[item]:
                    link.set_many(proj, param, item, [pat] + path[1:], vals)
            link.set(proj, P_ROOT, item, pat, [t["root"]])
            link.set(proj, P_SCALE, item, pat, [SCALES[t["scale"]]])
            target[(item, P_PATTERN_STATE, pat)] = 3
        if t["scale"] == "user1":
            for param, value in zip(P_USER1, user_mask_parts(t["userMask"])):
                link.set(proj, param, PROJECT_ITEM, 1, [value])
    for (item, param, i), state in target.items():
        link.set(proj, param, item, i, [state])
    link.commit(proj)

    link.open(proj)
    if project_block_bad(link, proj):
        problems.append("project settings still unreadable after the write")
    for t in tracks:
        item = TRACK_ITEMS[t - 1]
        mode = link.get(proj, P_MODE, item, 1)
        if t not in chord_tracks:
            if mode is None or mode & CHORD_MODE_BIT:
                problems.append(f"track {t} chord mode reads {mode}, expected off")
            continue
        got = [link.get(proj, P_CHORD, item, i) for i in range(1, 17)]
        if got != chord:
            problems.append(f"track {t} chord reads {got}, expected {chord}")
        if mode is None or not mode & CHORD_MODE_BIT:
            problems.append(f"track {t} chord mode reads {mode}")
    for t in keyed:
        item = TRACK_ITEMS[t["n"] - 1]
        for pat in range(1, 17):
            got = (link.get(proj, P_ROOT, item, pat), link.get(proj, P_SCALE, item, pat))
            if got != (t["root"], SCALES[t["scale"]]):
                problems.append(f"track {t['n']} pattern {pat} root/scale reads {got}")
        if t["scale"] == "user1":
            got = [link.get(proj, p, PROJECT_ITEM, 1) for p in P_USER1]
            if got != user_mask_parts(t["userMask"]):
                problems.append(f"user scale 1 reads {got}")
    after = read_states(link, proj)
    changed = {k: (target[k], v) for k, v in after.items() if v != target[k]}
    if changed:
        problems.append(f"pattern states differ from target: {changed}")
    link.set_name(proj, display_name(song["title"]))
    for trk, pads in sorted(song.get("pads", {}).items()):
        link.set_chord_pads(proj, int(trk), pads)
        if isinstance(link, EmuLink):
            at = (proj - 1) * 0x20000 + 0x1FEF0 + 8 + (int(trk) - 2) * 80
            want = sum(([*p] + [0xFF] * (5 - len(p)) for p in pads), []) + [0xFF] * 5 * (16 - len(pads))
            if list(link.emu.nor[at:at + 80]) != want:
                problems.append(f"track {trk} chord pads in flash differ from the plan")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plans", type=Path)
    ap.add_argument("--only", type=int, nargs="*", help="project numbers to write (default: all in the plan)")
    ap.add_argument("--map", nargs="*", default=[], help="override slot as SONGID=PROJECT, e.g. mysong=15 (for tests)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emulate", action="store_true", help="run against the emulated patched firmware")
    mode.add_argument("--send", action="store_true", help="write to the KeyStep Pro over CoreMIDI")
    mode.add_argument("--dry-run", action="store_true", help="print the plan only")
    args = ap.parse_args()

    songs = json.loads(args.plans.read_text())
    for spec in args.map:
        sid, proj = spec.split("=")
        next(s for s in songs if s["id"] == sid)["project"] = int(proj)
    if args.only:
        songs = [s for s in songs if s["project"] in args.only]
    for s in songs:
        if not 1 <= s["project"] <= 16:
            raise SystemExit(f"{s['title']}: project {s['project']} out of range")
        print(f"P{s['project']:>2} {display_name(s['title']):<16} {s['plan']:<5} tracks {[t['n'] for t in s['tracks']]} "
              f"chord {chord_bytes(s['shape'])[:len(s['shape'])]} pads " +
              " ".join(f"T{t}x{len(p)}" for t, p in sorted(s.get("pads", {}).items())))
    if args.dry_run:
        return
    link = EmuLink(str(PATCHED)) if args.emulate else CoreMIDILink()
    failed = 0
    for s in songs:
        problems = write_project(link, s)
        status = "OK" if not problems else "PROBLEM: " + "; ".join(problems)
        failed += bool(problems)
        print(f"P{s['project']:>2} {display_name(s['title'])}: {status}", flush=True)
    if failed:
        raise SystemExit(f"{failed} project(s) had problems")


if __name__ == "__main__":
    main()
