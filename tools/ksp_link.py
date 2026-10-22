#!/usr/bin/env python3
"""KeyStep Pro SysEx link: one interface over real CoreMIDI or the Unicorn emulator.

    link = CoreMIDILink("KeyStep Pro")      # macOS, real device
    link = EmuLink("firmware/patched/...bin")  # offline, real firmware code
    link.get(proj, param, item, idx) -> int | None   (bulk GET, one index)
    link.set(proj, param, item, idx, bytes)          (bulk SET)
    link.open(proj); link.commit(proj)               (cmd 05 / 06)

Project numbers are 1-based, as on the KeyStep screen.
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import CFUNCTYPE, POINTER, byref, c_uint32, c_void_p

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from set_project_name import SYSEX_PREFIX, MIDIPacketList, _cfstring, _midi_name, encode_frames  # noqa: E402

COMMIT_WAIT = 3.0   # seconds for the 2-sector erase/program after cmd 06


def frame(*body: int) -> bytes:
    return SYSEX_PREFIX + bytes(body) + b"\xF7"


class Link:
    def send(self, data: bytes) -> list[bytes]:
        raise NotImplementedError

    def open(self, proj: int) -> None:
        self.send(frame(0x05, proj))

    def commit(self, proj: int) -> None:
        self.send(frame(0x06, proj))

    def set(self, proj: int, param: int, item: int, idx: int, data: bytes | list[int]) -> None:
        data = bytes(data)
        self.send(frame(0x0C, proj, param, 1, item, idx, len(data), *data))

    def get(self, proj: int, param: int, item: int, idx: int, tries: int = 3) -> int | None:
        """Read-only, so a dropped reply is simply asked for again."""
        for _ in range(tries):
            for reply in self.send(frame(0x0B, proj, param, 1, item, idx, 1)):
                if len(reply) >= 15 and reply[6] == 0x0C and reply[7] == proj and reply[8] == param \
                        and reply[10] == item and reply[11] == idx:
                    return reply[13]
        return None

    def get_many(self, proj: int, param: int, item: int, idxs: list[int], n: int, tries: int = 3) -> list[int] | None:
        """Bulk GET of n consecutive values at the given index path (1-based indices)."""
        k = len(idxs)
        for _ in range(tries):
            for r in self.send(frame(0x0B, proj, param, k, item, *idxs, n)):
                if len(r) >= 13 + k and r[6] == 0x0C and r[7] == proj and r[8] == param and r[9] == k \
                        and r[10] == item and list(r[11:11 + k]) == idxs and r[11 + k] == n:
                    return list(r[12 + k:12 + k + n])
        return None

    def set_many(self, proj: int, param: int, item: int, idxs: list[int], data: list[int]) -> None:
        self.send(frame(0x0C, proj, param, len(idxs), item, *idxs, len(data), *data))

    def set_chord_pads(self, proj: int, track: int, pads: list[list[int]]) -> None:
        """KSCON build 5+: the 16 chord pads of track 2-4, up to 5 notes each (written to flash)."""
        if track not in (2, 3, 4) or len(pads) > 16:
            raise ValueError("track 2-4, at most 16 pads")
        data = []
        for i in range(16):
            notes = list(pads[i]) if i < len(pads) else []
            if len(notes) > 5 or any(not 0 <= n <= 126 for n in notes):
                raise ValueError(f"pad {i + 1}: up to 5 notes 0..126, got {notes}")
            data += notes + [0x7F] * (5 - len(notes))
        self.open(proj)
        self.send(frame(0x0C, proj, 0x7D, 1, 0x78, track - 1, len(data), *data))

    def set_name(self, proj: int, name: str) -> None:
        for data in encode_frames(proj, name):
            self.send(data)


class EmuLink(Link):
    """Replies are converted from captured firmware structs into wire-format frames."""

    def __init__(self, image: str, nor: bytes | None = None) -> None:
        from kspemu import KSPEmu
        self.emu = KSPEmu(image, nor)

    def send(self, data: bytes) -> list[bytes]:
        out = []
        for msg in self.emu.send(data):
            # struct: [0]=cmd [1]=param [2]=proj [6]=count [7]=len [10]=item [11..]=indices [14..]=data
            if msg[0] == 0x0C:
                count = msg[6]
                out.append(SYSEX_PREFIX + bytes((0x0C, msg[2], msg[1], count, msg[10], *msg[11:11 + count], msg[7]))
                           + msg[14:14 + msg[7]] + b"\xF7")
        return out


class CoreMIDILink(Link):
    READ_PROC = CFUNCTYPE(None, c_void_p, c_void_p, c_void_p)

    def __init__(self, device: str = "KeyStep Pro", reply_timeout: float = 0.5, gap: float = 0.01) -> None:
        if sys.platform != "darwin":
            raise SystemExit("CoreMIDILink needs macOS")
        self.reply_timeout, self.gap = reply_timeout, gap
        core = self.core = ctypes.CDLL("/System/Library/Frameworks/CoreMIDI.framework/CoreMIDI")
        cf = self.cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        for name in ("MIDIGetDestination", "MIDIGetSource"):
            getattr(core, name).argtypes = [c_uint32]
            getattr(core, name).restype = c_uint32
        core.MIDIGetNumberOfDestinations.restype = c_uint32
        core.MIDIGetNumberOfSources.restype = c_uint32
        core.MIDIObjectGetStringProperty.argtypes = [c_uint32, c_void_p, POINTER(c_void_p)]
        core.MIDIClientCreate.argtypes = [c_void_p, c_void_p, c_void_p, POINTER(c_uint32)]
        core.MIDIOutputPortCreate.argtypes = [c_uint32, c_void_p, POINTER(c_uint32)]
        core.MIDIInputPortCreate.argtypes = [c_uint32, c_void_p, self.READ_PROC, c_void_p, POINTER(c_uint32)]
        core.MIDIPortConnectSource.argtypes = [c_uint32, c_uint32, c_void_p]
        core.MIDISend.argtypes = [c_uint32, c_uint32, POINTER(MIDIPacketList)]
        core.MIDIClientDispose.argtypes = [c_uint32]
        cf.CFRelease.argtypes = [c_void_p]
        cf.CFStringGetCString.argtypes = [c_void_p, POINTER(ctypes.c_char), c_uint32, c_uint32]
        self.dest = self._find(core.MIDIGetNumberOfDestinations, core.MIDIGetDestination, device)
        src = self._find(core.MIDIGetNumberOfSources, core.MIDIGetSource, device)
        self.lock = threading.Lock()
        self.inbox: list[bytes] = []
        self.partial = b""
        self._proc = self.READ_PROC(self._on_packets)
        self.client, self.out_port, in_port = c_uint32(), c_uint32(), c_uint32()
        name = _cfstring(cf, "KeyStep Pro set list")
        if core.MIDIClientCreate(name, None, None, byref(self.client)):
            raise SystemExit("MIDIClientCreate failed")
        core.MIDIOutputPortCreate(self.client, name, byref(self.out_port))
        core.MIDIInputPortCreate(self.client, name, self._proc, None, byref(in_port))
        core.MIDIPortConnectSource(in_port, src, None)
        cf.CFRelease(name)

    def _find(self, count_fn, get_fn, match: str) -> int:
        found = [(get_fn(i), _midi_name(self.core, self.cf, get_fn(i))) for i in range(count_fn())]
        found = [(e, label) for e, label in found if match.lower() in label.lower()]
        if len(found) != 1:
            raise SystemExit(f"expected one MIDI endpoint matching {match!r}; found {[l for _, l in found]}")
        return found[0][0]

    def _on_packets(self, packet_list: int, _ref: int, _src: int) -> None:
        count = ctypes.c_uint32.from_address(packet_list).value
        offset = packet_list + 4
        for _ in range(count):
            length = ctypes.c_uint16.from_address(offset + 8).value
            data = ctypes.string_at(offset + 10, length)
            offset = (offset + 10 + length + 3) & ~3
            with self.lock:
                buf = self.partial + data
                while b"\xF7" in buf:
                    start = buf.find(b"\xF0")
                    end = buf.find(b"\xF7")
                    if start != -1 and start < end:
                        self.inbox.append(buf[start:end + 1])
                    buf = buf[end + 1:]
                self.partial = buf if b"\xF0" in buf else b""

    def send(self, data: bytes) -> list[bytes]:
        with self.lock:
            self.inbox.clear()
        plist = MIDIPacketList()
        plist.numPackets = 1
        plist.packet[0].timeStamp = 0
        plist.packet[0].length = len(data)
        for i, b in enumerate(data):
            plist.packet[0].data[i] = b
        status = self.core.MIDISend(self.out_port, self.dest, byref(plist))
        if status:
            raise RuntimeError(f"MIDISend failed: {status}")
        if data[6] == 0x0B:   # GET: wait for the reply frame
            deadline = time.monotonic() + self.reply_timeout
            while time.monotonic() < deadline:
                with self.lock:
                    if any(m[6:7] == b"\x0C" for m in self.inbox):
                        break
                time.sleep(0.005)
        elif data[6] == 0x06:
            time.sleep(COMMIT_WAIT)
        else:
            time.sleep(self.gap)
        with self.lock:
            return list(self.inbox)

    def close(self) -> None:
        self.core.MIDIClientDispose(self.client)
