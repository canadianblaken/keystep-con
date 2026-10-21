#!/usr/bin/env python3
"""Set a KeyStep Pro project title with the custom 2.5.20 firmware.

On macOS this uses CoreMIDI directly and has no Python package dependencies.
Without --send it only prints the SysEx bytes and never opens a MIDI port.
"""
from __future__ import annotations

import argparse
import ctypes
import sys
import time
from ctypes import POINTER, Structure, byref, c_char, c_char_p, c_uint8, c_uint16, c_uint32, c_uint64, c_void_p

SYSEX_PREFIX = bytes((0xF0, 0x00, 0x20, 0x6B, 0x7F, 0x42))
NAME_PARAM = 0x7C
PROJECT_ITEM = 0x78


def encode_frames(project: int, name: str) -> tuple[bytes, bytes]:
    if not 1 <= project <= 16:
        raise ValueError("project must be in 1..16")
    try:
        encoded = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("name must use printable ASCII") from exc
    if not 1 <= len(encoded) <= 16 or any(byte < 32 or byte > 126 for byte in encoded):
        raise ValueError("name must be 1..16 printable ASCII characters")
    payload = encoded.ljust(16, b"\0")
    # SysEx project byte is 1-based (0 = current project); 08009048 subtracts 1.
    open_session = SYSEX_PREFIX + bytes((0x05, project, 0xF7))
    set_name = SYSEX_PREFIX + bytes((0x0C, project, NAME_PARAM, 0x01, PROJECT_ITEM, 0x01, 0x10)) + payload + b"\xF7"
    return open_session, set_name


class MIDIPacket(Structure):
    _pack_ = 4  # CoreMIDI headers use #pragma pack(push, 4)
    _layout_ = "ms"
    _fields_ = [("timeStamp", c_uint64), ("length", c_uint16), ("data", c_uint8 * 256)]


class MIDIPacketList(Structure):
    _pack_ = 4
    _layout_ = "ms"
    _fields_ = [("numPackets", c_uint32), ("packet", MIDIPacket * 1)]


assert MIDIPacketList.packet.offset == 4 and MIDIPacket.length.offset == 8


def _cfstring(corefoundation: ctypes.CDLL, value: str) -> int:
    create = corefoundation.CFStringCreateWithCString
    create.restype = c_void_p
    create.argtypes = [c_void_p, c_char_p, c_uint32]
    ref = create(None, value.encode("utf-8"), 0x08000100)  # UTF-8
    if not ref:
        raise RuntimeError(f"could not create CoreFoundation string: {value}")
    return ref


def _midi_name(core: ctypes.CDLL, corefoundation: ctypes.CDLL, endpoint: int) -> str:
    key = _cfstring(corefoundation, "name")
    value = c_void_p()
    status = core.MIDIObjectGetStringProperty(endpoint, key, byref(value))
    corefoundation.CFRelease(key)
    if status != 0 or not value.value:
        return f"MIDI endpoint {endpoint}"
    buffer = ctypes.create_string_buffer(512)
    corefoundation.CFStringGetCString(value, buffer, len(buffer), 0x08000100)
    corefoundation.CFRelease(value)
    return buffer.value.decode("utf-8", "replace")


def send(project: int, name: str, match: str) -> None:
    if sys.platform != "darwin":
        raise SystemExit("--send requires macOS CoreMIDI")
    frames = encode_frames(project, name)
    core = ctypes.CDLL("/System/Library/Frameworks/CoreMIDI.framework/CoreMIDI")
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    core.MIDIGetNumberOfDestinations.restype = c_uint32
    core.MIDIGetDestination.argtypes = [c_uint32]
    core.MIDIGetDestination.restype = c_uint32
    core.MIDIObjectGetStringProperty.argtypes = [c_uint32, c_void_p, POINTER(c_void_p)]
    core.MIDIClientCreate.argtypes = [c_void_p, c_void_p, c_void_p, POINTER(c_uint32)]
    core.MIDIOutputPortCreate.argtypes = [c_uint32, c_void_p, POINTER(c_uint32)]
    core.MIDISend.argtypes = [c_uint32, c_uint32, POINTER(MIDIPacketList)]
    core.MIDIPortDispose.argtypes = [c_uint32]
    core.MIDIClientDispose.argtypes = [c_uint32]
    cf.CFRelease.argtypes = [c_void_p]
    cf.CFStringGetCString.argtypes = [c_void_p, POINTER(c_char), c_uint32, c_uint32]

    candidates = []
    for index in range(core.MIDIGetNumberOfDestinations()):
        endpoint = core.MIDIGetDestination(index)
        label = _midi_name(core, cf, endpoint)
        if match.lower() in label.lower():
            candidates.append((endpoint, label))
    if len(candidates) != 1:
        found = ", ".join(label for _, label in candidates) or "none"
        raise SystemExit(f"expected one destination matching {match!r}; found: {found}")
    endpoint, label = candidates[0]

    client = c_uint32()
    port = c_uint32()
    client_name = _cfstring(cf, "KeyStep Pro project names")
    port_name = _cfstring(cf, "KeyStep Pro project names")
    status = core.MIDIClientCreate(client_name, None, None, byref(client))
    cf.CFRelease(client_name)
    if status != 0:
        raise SystemExit(f"MIDIClientCreate failed: {status}")
    try:
        status = core.MIDIOutputPortCreate(client, port_name, byref(port))
        if status != 0:
            raise SystemExit(f"MIDIOutputPortCreate failed: {status}")
        for frame in frames:
            packet_list = MIDIPacketList()
            packet_list.numPackets = 1
            packet_list.packet[0].timeStamp = 0
            packet_list.packet[0].length = len(frame)
            for index, byte in enumerate(frame):
                packet_list.packet[0].data[index] = byte
            status = core.MIDISend(port, endpoint, byref(packet_list))
            if status != 0:
                raise SystemExit(f"MIDISend failed: {status}")
            time.sleep(0.2)
        print(f"Sent project {project} name to {label}")
    finally:
        if port.value:
            core.MIDIPortDispose(port)
        core.MIDIClientDispose(client)
        cf.CFRelease(port_name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=int, help="project slot 1..16")
    parser.add_argument("name", help="1..16 printable ASCII characters")
    parser.add_argument("--send", action="store_true", help="send to the selected CoreMIDI destination")
    parser.add_argument("--destination", default="KeyStep", help="substring of the MIDI destination name")
    args = parser.parse_args()
    try:
        frames = encode_frames(args.project, args.name)
    except ValueError as exc:
        parser.error(str(exc))
    if args.send:
        send(args.project, args.name, args.destination)
    else:
        print("Dry run; no MIDI port opened. Pass --send to transmit.")
        for frame in frames:
            print(" ".join(f"{byte:02X}" for byte in frame))


if __name__ == "__main__":
    main()
