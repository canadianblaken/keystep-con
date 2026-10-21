#!/usr/bin/env python3
"""Read-only KeyStep Pro bulk GET over CoreMIDI (macOS); prints the device's reply.

Same request as tools/readchord.sh: open a read session on <project> (1-based),
then bulk GET <param> of <item> index <idx>. Default: project 1, track 1 (item
0x7B), param 0x27. Never sends a SET.
"""
from __future__ import annotations

import argparse
import ctypes
import sys
import threading
import time
from ctypes import CFUNCTYPE, POINTER, byref, c_uint8, c_uint16, c_uint32, c_uint64, c_void_p, Structure

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from set_project_name import SYSEX_PREFIX, MIDIPacketList, _cfstring, _midi_name  # noqa: E402

READ_PROC = CFUNCTYPE(None, c_void_p, c_void_p, c_void_p)


def find(core, cf, count_fn, get_fn, match: str) -> tuple[int, str]:
    found = []
    for index in range(count_fn()):
        endpoint = get_fn(index)
        label = _midi_name(core, cf, endpoint)
        if match.lower() in label.lower():
            found.append((endpoint, label))
    if len(found) != 1:
        raise SystemExit(f"expected one endpoint matching {match!r}; found {[l for _, l in found]}")
    return found[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=int, default=1)
    parser.add_argument("--item", type=lambda v: int(v, 0), default=0x7B)
    parser.add_argument("--param", type=lambda v: int(v, 0), default=0x27)
    parser.add_argument("--idx", type=int, default=1)
    parser.add_argument("--device", default="KeyStep Pro")
    args = parser.parse_args()

    core = ctypes.CDLL("/System/Library/Frameworks/CoreMIDI.framework/CoreMIDI")
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    for name in ("MIDIGetDestination", "MIDIGetSource"):
        getattr(core, name).argtypes = [c_uint32]
        getattr(core, name).restype = c_uint32
    core.MIDIGetNumberOfDestinations.restype = c_uint32
    core.MIDIGetNumberOfSources.restype = c_uint32
    core.MIDIObjectGetStringProperty.argtypes = [c_uint32, c_void_p, POINTER(c_void_p)]
    core.MIDIClientCreate.argtypes = [c_void_p, c_void_p, c_void_p, POINTER(c_uint32)]
    core.MIDIOutputPortCreate.argtypes = [c_uint32, c_void_p, POINTER(c_uint32)]
    core.MIDIInputPortCreate.argtypes = [c_uint32, c_void_p, READ_PROC, c_void_p, POINTER(c_uint32)]
    core.MIDIPortConnectSource.argtypes = [c_uint32, c_uint32, c_void_p]
    core.MIDISend.argtypes = [c_uint32, c_uint32, POINTER(MIDIPacketList)]
    cf.CFRelease.argtypes = [c_void_p]
    cf.CFStringGetCString.argtypes = [c_void_p, POINTER(ctypes.c_char), c_uint32, c_uint32]

    dest, dest_label = find(core, cf, core.MIDIGetNumberOfDestinations, core.MIDIGetDestination, args.device)
    src, src_label = find(core, cf, core.MIDIGetNumberOfSources, core.MIDIGetSource, args.device)
    received: list[bytes] = []
    lock = threading.Lock()

    @READ_PROC
    def on_packets(packet_list: int, _ref: int, _src: int) -> None:
        count = ctypes.c_uint32.from_address(packet_list).value
        offset = packet_list + 4
        for _ in range(count):
            length = ctypes.c_uint16.from_address(offset + 8).value
            data = ctypes.string_at(offset + 10, length)
            with lock:
                received.append(data)
            offset = (offset + 10 + length + 3) & ~3

    client, out_port, in_port = c_uint32(), c_uint32(), c_uint32()
    name = _cfstring(cf, "KeyStep Pro probe")
    if core.MIDIClientCreate(name, None, None, byref(client)):
        raise SystemExit("MIDIClientCreate failed")
    core.MIDIOutputPortCreate(client, name, byref(out_port))
    core.MIDIInputPortCreate(client, name, on_packets, None, byref(in_port))
    core.MIDIPortConnectSource(in_port, src, None)

    frames = [
        SYSEX_PREFIX + bytes((0x05, args.project, 0xF7)),
        SYSEX_PREFIX + bytes((0x0B, args.project, args.param, 0x01, args.item, args.idx, 0x01, 0xF7)),
    ]
    for frame in frames:
        plist = MIDIPacketList()
        plist.numPackets = 1
        plist.packet[0].timeStamp = 0
        plist.packet[0].length = len(frame)
        for i, b in enumerate(frame):
            plist.packet[0].data[i] = b
        status = core.MIDISend(out_port, dest, byref(plist))
        print(f"sent {frame.hex(' ').upper()} -> {dest_label} (status {status})")
        time.sleep(0.4)
    time.sleep(0.6)
    with lock:
        sysex = [d for d in received if d[:1] == b"\xF0"]
    if not sysex:
        print(f"NO SysEx reply from {src_label} ({len(received)} non-SysEx packets seen)")
        raise SystemExit(1)
    for d in sysex:
        print("reply", d.hex(" ").upper())
    cf.CFRelease(name)


if __name__ == "__main__":
    main()
