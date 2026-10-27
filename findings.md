# KeyStep Pro firmware 2.5.20 — findings

Source: Ghidra 12.1.4 headless on `firmware/elf/ksp_main_2.5.20.elf` (project `ghidra/proj/ksp`),
exports in `out/ksp_main_2.5.20_{functions.tsv,strings.tsv,decomp.c}` (1543 functions).
Scripts: `ghidra/scripts/KspVectors.java` (seeds 96 vector-table handlers), `KspExport.java`.
Rerun export only: `analyzeHeadless ghidra/proj ksp -process ksp_main_2.5.20.elf -noanalysis -scriptPath ghidra/scripts -postScript KspExport.java out`

Status legend: CONFIRMED = read in decompiled code; HYPOTHESIS = inferred, not yet traced/tested.

## SysEx receive path (CONFIRMED)

| addr | role |
|---|---|
| 0801a9cc.. (DIN parser obj) | MIDI byte parser: F0 starts SysEx (state 4), F7 ends, bytes <0x80 appended |
| 0803d496 | SysEx start: reset state machine |
| 0803d586 | SysEx byte state machine (header check, field capture) |
| 0803d4a8 | SysEx end/flush |
| 0801851c | message handler (via vtable, no direct callers): routes by command byte |
| 0800de9c | item dispatcher on item-ID byte 0x78..0x7E |
| 0800e694 | global-parameter setter, switch on global ID 1..0x9E |
| 0800d3c0 | pattern/step field setter (paramIds 0x30-0x32, 0x61-0x71) |

### Frame layout (arturia_v2)

```
F0 00 20 6B <dev> 42 <cmd> <item> <param> <idx0> [idx1..idx3] [value...] F7
```
- `<dev>`: must equal device ID or 0x7F (all).  `42` = product ID (matches MCC `productId`).
- Universal SysEx also accepted: `F0 7E 7F 06 01/02/06 ...` and `F0 7F 7F 06 ...` (identity / MMC-style); a third branch starts with `5A` (unknown, likely Arturia updater).
- `<cmd>` semantics (CONFIRMED: request handler 080187e0, set handler 0801851c, serializer 0800f11c/0800f0f0):
  - **0x01 = GET** -> device replies cmd **0x02** with same item/param/idx + value, then an **ACK frame cmd 0x1C**.
  - **0x02 = SET** (7-bit value) -> applied, then ACK 0x1C.
  - 0x31 = GET variant -> reply 0x32 (idx0 bit7 toggled); 0x32 = SET variant.
  - **0x0B = bulk GET** -> reply 0x0C bulk data + ACK; 0x0C = bulk SET; 0x04 = block data (item 0x70 param 0x7C idx 0x10 carries 16 bytes).
  - **0x7F = ping** -> ACK 0x1C only.
  - 0x09/0x0A carry 14-bit values (MSB = v>>7 & 0x7F, LSB = v & 0x7F); others 7-bit. String payloads (cmd 2 with length field) up to 100 bytes.
  - 0x20-0x25: parsed with 1-3 extra index bytes; 0801851c only ACKs 0x21/0x23/0x25 (purpose unknown).
  - GET of param 0x42 ('B') returns two 0x7F bytes (placeholder/unsupported marker).
  - Identity: universal `F0 7E <dev> 06 01 F7` -> standard `06 02` reply (manufacturer, family 2 bytes, member 2 bytes, version 4 bytes).
- **Safe read-only probe** for live test: `F0 00 20 6B 7F 42 01 00 41 <globalId> F7` (e.g. 0x3D velocity curve); expect `F0 00 20 6B <dev> 42 02 00 41 3D <v> F7` then a 0x1C ACK frame.
- **Global settings**: `F0 00 20 6B 7F 42 02 00 41 <globalId> <value> F7` — item 0x00, param 0x41 (=65, MCC `deviceGlobalParametersId`), idx0 = global ID 1..0x9E. CONFIRMED in 0801851c (`[2]==0 && [1]=='A' && idx-1 < 0x9e`).
- Other command-2 specials in 0801851c: item 0x00/param 0x10 (stores idx+value), item 0x7D/param 0x7D (idx 9 = some action, idx 0x0B with value 0x7F/0 = on/off flag), item 0x70 with param 0x54/0x60/0x50 (UI/remote events; 0x60 idx 1..8 = 8 discrete triggers).

### Item IDs (CONFIRMED; firmware dispatcher matches MCC `bulkItemId`)

| item | meaning | fw handler |
|---|---|---|
| 0x78 (120) | project | 0800cca8 |
| 0x79 (121) | scene | 0800cecc |
| 0x7A (122) | track control | 0800d31c |
| 0x7B (123) | track 1 / drum | 0800dd3c |
| 0x7C-0x7E (124-126) | tracks 2-4 | 0800d708 / d7ac / d854 |

Param IDs inside items match `mcc-params.md` paramId column, e.g. in 0800d3c0: 0x6D pitch, 0x6E gate, 0x6F velocity, 0x70 time shift, 0x71 randomness (5 bytes per step), 0x61 swing stored as value-25, 0x62 step count, 0x6B root note, 0x6C scale, 0x30 step active, 0x31 skip, 0x32 corresponding step (0x7F → 0xFF = none).

## Global settings map (SysEx `F0 00 20 6B 7F 42 02 00 41 <id> <value> F7`)

Method: every menu "value changed" callback (0802 33d8..0802 4040) calls setter 0800e694 with a fixed ID
and range-checks the value first (= option count); the menu state machine 0802432c routes page bytes to
callbacks; the label/option table is at 0x08058780 (12-byte entries: label ptr, option-name list ptr, count).
Setter stores only IDs that hit a case; anything else returns without storing (e.g. 5, 26, 27, 58, 66, 69, 111-113, 117, 125-127, 137, 147-151).

### Not exposed by MCC (new)

| ID | hex | setting | options | confidence |
|---|---|---|---|---|
| 142-146 | 0x8E-0x92 | **PC Send** (CONFIRMED via RAM menu list 0x20000084: [0]IN [1]OUT [2]PC Send [3]PC Val [4]MSB [5]LSB [6]Fixed Velocity), per track (Track Settings page 0x5C). T1 uses 0x8E or 0x8F depending on a track-1 mode check (seq vs drum, TBC); T2 0x90, T3 0x91, T4 0x92 | 0=OFF 1=ON | high (menu sub-item 2 of Track Settings, descriptor order IN/OUT/PC Send/PC Val/MSB/LSB/Fixed Vel) |
| 154-158 | 0x9A-0x9E | **Fixed Velocity**, per track (page 0x5D). T1 0x9A/0x9B (same mode split), T2 0x9C, T3 0x9D, T4 0x9E | 0=OFF 1=ON | high (sub-item 4 = descriptor 6 "Fixed Velocity :") |
| 152 | 0x98 | **Brightness** (page 0x60) | 0 Very Low, 1 Low, 2 High; forced at boot to 1 or 2 by a power-sense pin (USB bus vs PSU) | high |
| 153 | 0x99 | **Transpose Latch** (on: latches current transposition; off: clears) | menu stores inverted (menu 0 -> 1). Polarity TBC on device | medium-high |
| 1 | 0x01 | sets two flags, no stored value (action/trigger, unknown) | - | low |
| 118-121 | 0x76-0x79 | stored, no side effects; candidates for Brightness USB / Colour Set / other | ? | unknown |

Still unmapped menu items: Brightness USB (Very Low/Low), Colour Set (21 names), Velocity/Pitch/Gate/Time/Random *Offset* (track edit, probably project data not globals).

### Confirmed equal to MCC (spot checks from callbacks)
2-4 launch quantize; 6-9 CV pitch format; 10-13 base note; 14-17 gate format; 18-21 mod source; 22-25 mod max V;
28-57 knobs 1-5 (CC/port/channel/mode/min/max); 59-61 knob accel / AT curve / vel curve; 62-63 transport; 64-65 clock send/recv;
67-68 touch strip send/recv + CC; 70-79 track/drum MIDI in/out channel; 80 global channel; 81 drum map mode; 82 low note (0..103);
83-106 custom drum notes; 107 touch strip on/off; 108 vegas; 109 screen saver; 110 step listen; 114 count-in; 115 time sig;
116 time div; 122 sync input; 123 clock rate; 124 sync output; 128-135 drum gates; 136 MIDI Out 2; 138-141 pitch-bend range.


## Scales, quantizer and chord mode (CONFIRMED)

Analysis ELF with .data mapped: `firmware/elf/ksp_main_2.5.20_data.elf` (tools/mkelf_data.py; .data = flash 0x0805CB60 -> RAM 0x20000004..0x20000650, copied by reset entry 08057218). Exports: `out/ksp_main_2.5.20_data_*`.

- **Scale masks** (12-bit, bit n = semitone n above root) at flash 0x0805CB60 / RAM 0x20000004, index = Pattern Seq scale value:
  0 Chromatic 0xFFF, 1 Major 0xAB5, 2 Minor 0x5AD, 3 Dorian 0x6AD, 4 Mixolydian 0x6B5, 5 Harmonic minor 0x9AD, 6 Blues 0x4E9 (0 3 5 6 7 10), 7 = 0x000 (unused slot), 8/9 = User 1/User 2 (read from project, MCC paramIds 101-106).
- `0800e35c(scale, root…)`: rotates the mask by the root note.
- `0800e3a8(track, scale…)`: builds a 128-entry per-track note map at RAM 0x20000674 + track*0x80. In-scale notes map to themselves; out-of-scale notes snap to the nearest in-scale note, checking **down before up at each distance, so ties resolve DOWN** (C major: C#->C, D#->D, F#->F, G#->G, A#->A).
- Rebuilt by `0803094c` whenever the pattern changes: the scale index lives per pattern (offset scene*0xFEC + pattern*0x14 + track*0x140 + 0x93B, low 4 bits). Track 5 (index 4) = drum, never quantized.
- Live key note-on `0803890c`: note = map[track][key].
- Sequencer playback `0802d1e4` / `0802d31c`: step pitch -> optional transposition (`0802cc30`) -> map[track][…]. Quantize is applied at play time, so recorded steps keep their raw pitch.
- **Chord mode** `080382e0`: chord = up to 15 signed offsets per track (byte array at state + track*0x16 + 0xFEC*cur + 0x1754 + i, i=1..15, 0 terminates; root implicit). For each offset, note = (quantized key) + offset, **then each chord note is snapped through the scale map individually** (ties down). So one stored shape becomes diatonic per key. E major + E-G#-B shape: E->E maj, F#->F#m, G#->G#m, A->A, B->B, C#->C#m (F->E by tie), D#->D# F# A (diminished: G->F#, A#->A by tie).
- Limits from strings: 16 notes per step, 192 notes per pattern, 16 notes per arp.


## UI MCU image (light pass)

`firmware/elf/ksp_ui_0.0.1.elf`, exports `out/ksp_ui_0.0.1_*` (406 functions, 33 vectors). Base 0x08000000, SP 0x20008000 (32 KB RAM).
Peripheral map (GPIO at 0x48000000, ADC at 0x40012400, TIM15-17 at 0x40014000+) = STM32F0/G0-class part, not F4 (HYPOTHESIS: F07x/F09x).
Contains bitmap fonts ("copyright ADAPTIVE 2002", "pix Chicago") and "Pitch Bend" -> it renders the OLED; main MCU sends the menu text (all UI strings live in main). Uses ADC (wheels/touch strip/aftertouch likely), SPI1+SPI2 (display / LED drivers likely), several UARTs (link to main; main has uart.cpp).

## Arpeggiator (open)
Arp type = pattern byte 10 bits 1-3 (setter 0800d3c0 case 0x64), read via accessor functions, no direct mode switch found; likely per-mode C++ objects. Random source = newlib rand() (08057500) prefilling a 256-entry pool (08029c90/08029d40).

## Menu tree (from strings, CONFIRMED text)

Utility/ Sync/Input, Drum/Config, Ctrl/Knob 1-5, CV/Voice 1-4, CV/DrumGates, Track Settings, Launch Quant, CV Settings, Controller, MIDI Settings, Touch Strip, MIDI Channels, Drum Map, Drum Gates, Sync, Metronome, Misc.
Colour set names: Aquamarine, Azure, Electric Blue, Ivory, Light Green, Light Orange, Light Yellow, Orange, Pale Purple, Peach, Purple, Royal Blue, Tea Green, Violet, White Celeste, Yellow.
Limits: 16 notes per step, 192 notes per pattern, 16 notes per arp.


## Live verification (2026-10-18, KSP regular PID 0x0218 over USB on Linux, read-only GETs via amidi)

- Identity reply: `F0 7E 7F 06 02 00 20 6B 02 00 09 00 25 14 05 02 F7` -> Arturia, family 02 00, member 09 00, version bytes 25 14 05 02 = fw 2.5.20 (MCC format $3.$2.$1; 0x25 likely build). Device ID answers as 7F.
- GET works exactly as decoded: `F0 00 20 6B 7F 42 01 00 41 3D F7` -> `F0 00 20 6B 7F 42 02 00 41 3D 00 F7` + ACK `F0 00 20 6B 7F 42 1C 00 F7`.
- **IDs >= 128 need cmd 0x31/0x32 with idx = id-128** (7-bit SysEx limit; firmware ORs/XORs 0x80). cmd 0x01 for 128+ gets no reply. This is what 0x31/0x32 are for.
- A full snapshot of all 158 globals was read from one unit (not included). Notable: 142-146 PC Send = 1,1,1,1,1; 152 Brightness = 1 (Low); 153 Transpose Latch = 1; 154 = 0, **155 = 1**, 156-158 = 0 (Fixed Velocity: only track 1 seq-mode on); 118-121 = 0,1,2,3 (per-track default-like, so probably not Brightness USB / Colour Set).
- Track-1 split: code picks 0x9B/0x8F when track 1 is NOT in drum mode (0802cca2 == 0), 0x9A/0x8E in drum mode.


## Persistence / storage (CONFIRMED from code)

- Storage: external parallel NOR flash on FMC bank 1 (0x60000000, AMD command set 0xAA/0x55/0xF0), driver 0803f774 (read halfwords). 128 KB per project (`project << 17`), 16 projects. Empty blocks are marked 0xAAAA.
- Globals: one block of 0x4F halfwords (158 bytes = the global ID array) read at boot by 08046264; defaults (0800e478) if empty. Knob CC assignments are globals: they persist, but are NOT per project.
- Boot (0803b1c8 from init 0803b1fc) loads ALL 16 projects from flash into RAM (per-project RAM stride 0xFEC); switching project only changes the current index. Edits live in RAM until the project is saved; there is no autosave path seen yet.
- Project loader 08046858 restores per project: 5 tracks x 16 patterns (080464d0), a per-track block of 10 halfwords at state + track*0x16 + proj*0xFEC + 0x1750 (**includes the chord shape bytes 0x1755-0x1763**), 16 scenes x 0x2E halfwords (08046800, base +0x1130 + scene*0x62), and a project block of 0x0E halfwords (+0x17BE).
- Scale/root are per pattern (pattern params, stride 0x14) and are inside the saved pattern data.
- Not saved: bytes 20-21 of each 22-byte track struct (0x1764-0x1765), contents unknown.
- Global SET (cmd 02/32 to item 00 param 41) returns no ACK; only GETs are answered.
- Live write test OK: Brightness (152) set 1->2->1 via `F0 00 20 6B 7F 42 32 00 41 18 <v> F7`, readback matched.


## Project transfer sessions and correct item addressing (CONFIRMED live)

- **Frame field order is `<cmd> <project> <param> <item/idx0> ...`**: the byte after cmd is the PROJECT (0 = current, 1-16 = that project; firmware 08009048 uses n-1). For globals project=00, param=0x41, idx0=global ID.
- Item params are only answered inside a transfer session (state var 0x20000671, project var 0x20000670):
  - **cmd 0x05 `<proj>` = open read session** (router 0801893c -> 0800aa20): copies that project FROM FLASH into a transfer buffer (0800a0fc, reads at 0x60000000 + proj*0x20000). So session reads show what is SAVED, not live RAM. No reply.
  - **cmd 0x06 `<proj>` = close write session** (0800bbf0): reloads the project from flash into RAM.
- Single GET (cmd 01) only fills addr index 0. Use **bulk GET with one index**: `F0 00 20 6B 7F 42 0B <proj> <param> 01 <item> <idx 1-based> 01 F7` -> reply cmd 0x0C, value at byte 13.
  Example, track 1 chord byte n: `F0 00 20 6B 7F 42 0B 01 57 01 7B <n> 01 F7`.
- Track getter 0800c188 decodes the 22-byte track struct: p0x27 data state (3 = marker 0xAAAA valid), p0x55 transposition bits, p0x56 = octave (bits0-2) | chord mode (bit7 -> bit4) | byte3 bit0 -> bit6, p0x57[n] = struct byte 4+n (chord root at n=0, offsets after), p0x7A = byte3 >> 1.
- Track struct (22 bytes, state + track*0x16 + proj*0xFEC + 0x1750): +0 marker (0xAAAA valid / 0xBBBB default), +2 octave/chord-mode, +3 0x78 default, +4 chord root (0xFF none), +5..+19 chord offsets, +20 default 100 (likely fixed-velocity level, not saved), +21 ?.
- Saved colours differ per track (p0x3B: T1 0, T2 1, T3 10, T4 12), so session reads return real flash data.

## Persistence test results (2026-10-18, project 1, track 1)

- Code says Save Project (080240f0 case 1 -> 08047540 + 08047c84) and Save Track (08047444) write the 20-byte track block incl. chord + chord-mode bit, and boot reloads all 16 projects (0803b1c8).
- Live: recorded chord + Save Project, Save + Track 1, octave +2 + Save + Track 1; on USB power, USB Y-cable and wall adapter (brightness read 02 after boot = external power detected). **Saved copy never changed** (chord root 0x7F, offsets 0, p56 0x02) and **the unit itself lost chord and octave after every power cycle**.
- Firmware does not gate saves on power source (PA15 power-sense flag only drives LED brightness, 0802b588).
- Not yet done: control test with a recorded sequence (do ANY saves persist?). If not, unit-level save fault (others report this; try reflashing 2.5.20 via MCC / Arturia support). If yes, chord/octave specifically dropped -> Mac helper re-sends chords at power-on, or firmware patch.

## Next
1. Live check (KSP on USB): read-only GETs of a few globals incl. 0x9A-0x9E Fixed Velocity and 0x99 Transpose Latch polarity; identity request.
2. Arp engine: trace pattern-byte-10 accessors to the arp step code.
3. Remaining unmapped: Brightness USB, Colour Set (candidates 118-121).
4. Playable manual (last).

## Chord/octave save trace (2026-10-18)

Control test: MIDI channels (globals) and recorded steps survive save + power cycle, so flash works. Only chord/octave are lost.

- Chord entry `080104bc` writes the chord straight into the RAM track block (base `*0x20001498`, track, project `*0x20004DAD`) and sets the 0xAAAA marker. Octave setter `0802b22c` does the same. Save and load use the same base and project index.
- Track block flash location (per project, base `proj<<17`): `trackBase + trackSize - 0x14`. T1 0xA740, T2 0x14B40, T3 0x19694, T4 0x1E1E8, Drum 0x1F8FC. Saver `08047a9c`, loader `08046858` and the SysEx session copy `0800a0fc` all agree, so session reads of the saved block are faithful.
- Saving works by reading a 64 KB flash sector into SDRAM staging at 0xC01F0000 (`080470ec`), patching it with `08047148`, then erasing and programming it (`080475d8`).
- **BUG, Save + Track** (button combo, handler `080163cc` -> `08047a9c(obj, trk, trk, cur, cur, 1)`): with param_6=1, `08047a9c` programs the sector(s) first and only then writes the 20-byte track block (chord + octave) into staging. The staging buffer is never programmed again (the next save re-reads flash over it), so **Save + Track never stores chord/octave**. Patterns are staged before the program and do persist.
- Save Project from the Project menu ("Save Project %u / Confirm ?", menu state 0x0B -> `080240f0` case 1 -> `08047540` + `08047c84` -> reload `08046858`): `08047c84` calls `08047a9c` with param_6=0 and stages the block before programming, so on paper it DOES store chord/octave. It then reloads the project from flash, so a failed write would make the chord vanish immediately after saving, not only after a power cycle.
- `08047540` is NOT a flash write: it copies the project to the copy/paste clipboard at SDRAM 0xC0198000 (clipboard type 0x200004F4: 0 scene, 1 pattern, 2 project). Menu case 2 = Erase Project (`08047dcc`), case 3 = Copy Project (`08047c84` src->dst).
- Patch idea for Save + Track: move the track-block `08047148` call in `08047a9c` ahead of the `080475d8` program calls (or re-run program after it).
- Next live test: set chord, Project menu -> Save Project -> Confirm ("Project Saved"), check the chord still plays immediately, then power-cycle.

### Resolved (2026-10-19)
- Root cause on the user side: at "Save Project %u / Confirm ?" the user pressed step pad 1, which selects/LOADS project 1 ("Project Loaded"). That reloaded flash over the RAM edits, so the save never ran. **Confirm is a push of the clickable menu encoder next to the display.**
- After a real Save Project + power cycle, the chord survived. The saved block read back `p56=0x12` (chord mode on) and chord bytes `34 04 07` (root 0x34 = E3, +4, +7 = major triad).
- The Save + Track bug (`08047a9c` param_6=1 stages the track block after programming) still stands: use Save Project to keep chord/octave.
- `tools/readchord.sh <proj> <track>` (Linux, amidi; port in `MIDI_PORT`): read-only dump of the saved track block. Project 0 also returns the flash copy, not live RAM.

## Project-name feature investigation (2026-10-19)

- The stock project SysEx setter (`0800cca8`, item `0x78`) has no project-name parameter. Its handled IDs cover project state, user scales, and current scene; none stores text.
- The UI string table contains the static format `Project %u` plus Save/Erase Project prompts. No project-name string or setter is present in the exported 2.5.20 strings.
- **Storage candidate (HYPOTHESIS):** each 128 KB slot has two 64 KB sectors. Project save reads each sector into staging (`080470ec`), patches fields, then rewrites it (`080475d8`). The project block ends at slot offset `0x1FEEC` (`08047c84` writes 14 halfwords at `0x1FED0`); the final `0x114` bytes are not touched by that save routine. Offset `0x1FFF0` is a plausible 16-byte name location. Project erase (`08047dcc`) erases both sectors, so a name there would also be cleared by erase.
- **Flash-path check:** `08047c84` reads the second sector before patching the project block and reprogramming the full sector, so data at `0x1FFF0` is preserved by Save Project. The first-sector metadata writer `08047d98` uses offset `0xFFF0` in project 0; it does not overlap the second-sector candidate. Do not treat the candidate as confirmed until an offline flash-image save simulation verifies the preserved bytes.
- **SysEx hook:** bulk SET (`0x0C`) normalizes the project into message byte 2, parameter into byte 8, and item into byte 7; the payload length is dispatcher argument 4. Item `0x78` currently ignores parameter `0x7C`, so the candidate patch reserves it for a 16-byte printable-ASCII name. The Mac utility opens the project session (`0x05`), then sends bulk SET with item `0x78`, parameter `0x7C`, one index, length 16, and a NUL-padded payload. The hook writes the second-sector tail and clears the transfer-session state so the normal close handler cannot rewrite the project immediately afterward.
- **Display hook:** `080264f0` calls `0805761c` at `0802654c` to format the title before sending the line through `0802648a`. The candidate patch intercepts that call only when the format pointer is `0805AE68` (`Project %u`), reads the selected slot's 16-byte name through `0803f774`, and falls back to the stock formatter when the field is empty or invalid.
- Arturia's MCC documentation describes a recalled device project becoming an MCC project that can be renamed there, but that documents MCC-side naming, not an on-device field: [MCC Control Codes](https://support.arturia.com/hc/en-us/articles/4405748124306-KeyStep-Pro-MCC-Control-Codes).
- Offline candidate: `tools/name_hooks.S`, `tools/build_names_patch.py`, `tools/test_names_hooks.py`, and `tools/set_project_name.py`. The builder appends 304 Thumb bytes at `0805D1AC`, patches only the title-format call and item-`0x78` dispatch, updates the 24-bit image length stored in header word 1, then rebuilds the `.kspf` ZIP. The original stock package is untouched.
- Offline Unicorn checks pass for per-slot name lookup, stock title fallback, per-slot sector update, preservation of neighboring sector bytes, and rejection of non-16-byte payloads. The rebuilt ZIP CRCs and both branch targets are checked by the builder.
- **Review fixes (2026-10-19, Claude):**
  - Header byte `0x3F` is an 8-bit checksum: the 64 header bytes sum to 0 mod 256 in all four stock images. The builder now recomputes it after changing the length word. Header byte 9 is an 8-bit payload checksum: payload bytes + byte 9 sum to 0 mod 256 (main 0x6B+0x95, chroma 0x77+0x89, UI 0x8D+0x73). The builder sets it before the header checksum. The decoded header layout is: 0-1 VID `0x1C75`, 2-3 PID, 4 image number, 5-7 24-bit payload length, 9 payload checksum, 10 `0x01`, 11-14 load address (`0x08008000` main, `0x08000000` UI), 15-18 end address (`0x0807FFF7` main, `0x0803FFFF` UI), 63 header checksum. No CRC16/CRC32/Adler of the payload appears in the header. Any further check would live in the bootloader, which is not in the `.kspf`.
  - The SysEx project byte is 1-based. 0 means the current project, and `08009048` turns any other byte into byte-1 before the dispatcher, so the hook sees slots 0..15. `set_project_name.py` sends the screen number 1..16 unchanged, as Codex originally had it. The setter hook rejects normalized slots above 15. The title hook reads slot `n-1` for "Project n". An earlier version of this fix wrongly sent 0..15. On-device, `set_project_name.py 16 "Test"` therefore wrote slot 14, which is Project 15.
  - The setter hook replaces `mov r2,r7; mov r1,r4` at `0800df28`, so it now takes the message pointer from r4. r1 is clobbered on the auto-open-session path (`0800defa` -> `0800a0fc`).
  - `title_hook` keeps the stack 8-byte aligned for the formatter call.
  - Tests now cover a Mac-tool -> setter -> title round trip, slot range guard, stock setter passthrough with garbage r1, header checksum, and stack alignment.
  - `08047c84` is the project save writer. Menu case 1 (`0802418c`) saves the current project into the selected slot, and case 3 saves into the same slot. It is not only Copy. Because it reads the destination's second sector, saving into another slot keeps that slot's existing name.
- The candidate is at `firmware/patched/KeyStepPro_2.5.20_project_names.kspf` (ignored local artifact). The 64-byte Arturia header's bootloader acceptance and any runtime integrity check are not verified. No device SysEx write or firmware flash has occurred; stock 2.5.20 remains available for restore.
- **Hardware verification (2026-10-19, Mac + MCC):**
  - The patched firmware flashed through MCC and boots normally.
  - `set_project_name.py 16 "Test" --send` shows "Test" on Project 16. Other projects still show "Project N".
  - The name survives a power cycle, and it survives Save Project followed by a power cycle.
  - Erase Project clears the name.
  - MCC Recall (device to computer) works without errors.
  - The earlier sends that seemed to do nothing never left the Mac. The ctypes CoreMIDI structs lacked `pack(4)`, so CoreMIDI saw zero-length packets.
  - Save + Track is not yet tested.

## Set list writer: names + chords (2026-10-19)

- `tools/ksp_setlist.py` takes a set list plan (JSON: project, title, chord shape, tracks with root and scale) and writes each project's name, chord shape (`p0x57`, one SET per index: root then semitone offsets, 0x7F padding) and chord mode (`p0x56` | 0x10) on the planned tracks. It verifies by reading back. Written and verified on hardware for a 14-song set list; root/scale (phase 2) are not written yet.
- **SysEx commit quirk (stock 2.5.20):** cmd 06 (`0800aeb0`) decides each scene's and pattern's flash marker from the transfer-buffer header bits (bit1 and bit0 set -> AAAA valid, bit1 only -> BBBB default). The session load copies the raw marker, so an untouched AAAA becomes BBBB, BBBB becomes AAAA, and erased FFFF becomes AAAA with junk content. Every commit therefore flips all untouched scene and pattern states. MCC is unaffected because it sends whole projects. Workaround: read and re-send all states first. That covers scene `0x79`/`p0x26` and patterns `p0x28` on items `0x7A` (track control) and `0x7B`-`0x7E` (tracks 1-4), 96 values; states read 3 = valid, 2 = default. Track-level data (chord, chord mode) is not affected.
- Root/scale are per pattern (`p0x6B` root in the high nibble, `p0x6C` scale in the low nibble, idx = pattern 1..16). A pattern only uses them when its state is valid, and making a default pattern valid exposes its stored content. Phase 2 has to write proper default pattern content first.
- `tools/kspemu.py` emulates the real parser, session load, setters, getters and commit. It models NOR read, program, erase (top-boot sectors) and stubs RAM reload/UI. `tools/ksp_link.py` gives the same API over CoreMIDI or the emulator.
- An identical re-run changes zero flash bytes, and other projects stay untouched (emulated). The first run on a project changes only the planned track chord blocks and the name.
- The Erase Project routine (`08047dcc`) only erases both sectors, which leaves `FF` with no default content.

## Set list writer phase 2: keys (2026-10-19)

- `ksp_setlist.py` now also writes root (`p0x6B`) and scale (`p0x6C`: 0 chromatic, 1 major, 2 minor, 8 User 1) on all 16 patterns of each keyed track, and marks them valid (`p0x28` = 3). For a User 1 scale it writes the mask (`p0x65`/`p0x66`/`p0x67` on item 0x78, 7-bit parts, intervals above the root).
- Default patterns are made clean before they become valid. The getter reports firmware defaults for a default pattern, and every pattern parameter is written back with those values.
  - Single values: `0x14`-`0x17`, `0x61`-`0x64`, and the default note `0x6D`-`0x71`; track 1 also has `0x19`-`0x1C` and `0x72`-`0x79`.
  - Per step (pattern, step 1..64): `0x30`, `0x31`; track 1 also has `0x33`-`0x36`.
  - Per voice and step (pattern, voice 1..3, step): `0x32` and `0x6D`-`0x71`.
- A coverage test wrote these defaults onto an FF-filled and a 00-filled flash image. The written pattern regions are identical except bits 6-7 of header byte `+0x0B`, which no parameter writes.
- Reply framing for multi-index GETs mirrors the request: `0C proj param count item idx... len data`.
- On hardware, all keyed projects (2, 3, 4, 5, 6, 7, 10, 11, 14, plus test 15) verified by readback. On project 15, track 1 (E major) played G# -> G#m and F# -> F#m by ear. The device displays a stored chord shape anchored at middle C; only the intervals matter.
- Scenes store each track's current pattern (`p0x53`) and the current track (`p0x4C` bitfield). Root/scale can therefore differ per scene through patterns; the chord shape is per track.

### Step drum pads patch (built and emulator-tested 2026-10-20, not flashed)
- Toggle: hold Drum (0x15), press Seq (0x14). Stock, Drum press switches track 1 to drum mode and Seq-while-Drum would switch it back; that Seq press/release is taken. Shift+Control = Control mode toggle and Shift+Drum = unmute all drum lanes (`0802ad34`) stay stock. Button record byte +2 is 0 while held; Shift is id 1.
- `tools/pad_hooks.S` + `tools/build_ksp_patch.py` (names + pads; names part byte-identical to the flashed names image except the two redirected BLs at 080126ea / 08012708) + `tools/test_pad_hooks.py` (Unicorn; runs the firmware's own lane->note and MIDI builders).
- Pads send note-on vel 100 / note-off via `08017e70`/`08017e28` + `0801a6e0(*(0x20001800),msg,3)` on the drum output channel (globals 0x20000874 + 4 + 79); no CV drum gates yet; no screen message or LED.
- State: 64 bytes at external RAM 0xC01EF800 with a magic word. The 0xC01E6000-0xC01EFFFF stretch has no code references (static scan only; not proven unused at runtime).
- Output: firmware/patched/KeyStepPro_2.5.20_names_drumpads.kspf.

### Chord pads + chord save (built and emulator-tested 2026-10-20, not flashed)
- Hold Seq, press Arp on track 2-4 (ids 0x1a/0x1b, 0x20/0x21, 0x26/0x27): chord pads for that track; exclusive with drum pads (mode byte 0 off / 1 drums / 2-4 chord track 2-4). Keys held on that track + step = capture (held-key table 37 x {note, ch, track} at 0x20004ddc, note 0xff = up; notes are already scale-mapped, octave included); step alone = play stored chord, else the scale chord (root = pattern block +0x93a >> 4, scale = +0x93b & 15, block = *(0x20001498) + project*0xfec + pattern*0x14 + track*0x140; project byte 0x20004dad, current pattern per track 0x20004da8+t; keyboard octave = *(seq + project*0xfec + track*0x16 + 0x1752) & 7, lowest key = octave*12; masks u16 at 0x20000004, user scales at seq+project*0xfec+0x17c6/0x17c8). Erase (id 0x10, from its step-erase branch; to confirm on hardware) + step clears.
- Storage: 256 bytes at project offset 0x1FEF0 (between the project block ending 0x1FEEC and the name at 0x1FFF0): "CHD1", 4 spare, track 2-4 x 16 pads x 5 notes, 0xff unused. Save Project (08047c84) BL to SECTOR_WRITE at 08047d36 redirected to chord_save, which stages the table into the second sector then programs it (one write, before the reload). Loaded lazily from flash when the RAM copy's project tag differs. Erase Project clears it. Not known: whether a SysEx Store (session commit) keeps this area; not in web-app backups yet.
- Output: firmware/patched/KeyStepPro_2.5.20_names_pads.kspf. Supersedes names_drumpads.
- Undo: Shift (1) + Exit (0xc) is the stock undo (only after a paste: flag 0x20005a40, type 0x200004f4). In chord pad mode with a pending chord change, the hook swaps the pad with the saved copy instead (undo, again = redo); cleared on project switch; otherwise stock.
- Chord-type mode (Orchid-style one-finger chords): hold Seq + press Mute on track 1-4 (Mute ids 0x16/0x1c/0x22/0x28) -> mode 5-8; steps 1-8 latch Maj/Min/Sus4/Dim/7/Maj7/Min7/add9; 9-16 stock. Uses stock Chord mode without touching project data: chord expansion `080382e0` asks `0802d160` (chord flag = bit 7 of seq+project*0xfec+track*0x16+0x1752) at 08038368/080383b8 -> ct_flag answers 1 for the chord-type track; the offset load `movw r2,#0x1754; ldrsb r3,[r3,r2]` at 0803857a -> ct_offs sets r2 so the load reads the type table (lr is not live there; only 080386de uses lr). Chord notes are released from the stored table 0x20000928 (`08031ae8`), not recomputed, so no stuck notes from the hook. Notes still snap to the scale map (Chromatic = exact types).
- Chord-type (Orchid) mode REMOVED at the user's request (hard to remember); Seq + Mute now toggles root chords.
- Root chords (mode 5-8 = track 1-4): the key note-on MIDI send in the event loop (bl 0801a6e0 at 080156f6; key index at [sp+0x6a], held-key table already filled) is redirected to key_send: a key on the root-chord track only sets the root (silent), other keys are sent. Steps play chords built from the track's scale above the root, by step number: 1 root+oct, 2 sus2, 3 triad, 4 sus4, 5 power, 6 6th, 7 7th, 8 triad +oct, 9 9th, 10 add9, 11 11th (no 5th), 12 1st inv, 13 13th (no 5th/11th), 14 2nd inv, 15 7sus4, 16 triad -oct. CV gate and sequencer recording of the silent key are not suppressed.
- Keyboard range (from the key-LED mapper 08034ab4 / octave getter 0802b200): the 37 keys shown are octave*12+24 .. octave*12+60, octave = track byte +0x1752 & 7. Scale chords (chord pads) and the default root (root chords) now sit in that lowest octave (were an octave below the keys); root chords move by whole octaves (fit_keys) to stay on the keys shown where they fit.
- The key note-on at 080156f6 only runs on one branch of the key-press case (the decomp suggests "not playing"); otherwise keys go via 080117b4 and key_send never sees them. Root chords therefore take the root from the held-key table (lowest note held on the track) when a step is pressed; key_send still silences keys on the branch it hooks.
- 080108a4 (called at 08015ee0) is the stock key handler, not only live record: (obj, &note, &vel, &track, ..., key, 0); a 0 return drops the key entirely (no note, no record, no held-key entry). key_rec returned 0 for root-track keys, so the root was never picked on hardware. key_rec now sets the root itself from the key note mapped through the track's scale table 0x20000674 + track*0x80 (as the event loop fills the held-key table), then drops the key.
- Key lights for pads: LED id = `08034ab4(seq, note, track)` (0x46-0x6a keys, 0x45/0x6b octave arrows, 0x78 none); on `08053eb8(*(0x20001490), id, 1, colour (0x20000058+track), 0, 0)`, off `(…, 0, 8, 0, 0)`; only while the pad's track is selected (0x200001a4; 4 = track 1 shown as drums).
- Recording for pads: live record = `0802a244(track, note, vel, *(0x20003d9d))` -> slot (0xc0+ refused), drums `0802a244(0, lane, vel, lane)`; length at release `08029e78(track, slot)`. Recording when *(0x20003d91) or (*(0x20002d5b) and seq+0xc) — the drum-key test (080105c8). Root-chord keys kept out of recording by redirecting the event loop's live key record (bl 080108a4 at 08015ee0; r3 -> track byte).
- Version (2026-10-21): the SysEx identity reply is built at 080181a6-080181f0 from immediates (strb to a 16-byte struct: 00 20 6B / 02 00 / 09 00 / build&0x7F=0x25 / 20 / 5 / 2, queued with 0800f03c, sent by 0800f222); MCC shows $3.$2.$1. Utility > FW version shows the string at 0805af3c through the pointer at 080589a4 ("Firmware version :\n2.5.20\nbuild 2085"). Patched builds now report 2.5.99 (patch byte at 080181d8) with our own build counter in the build byte (080181d2), point the menu text at "2.5.99 = 2.5.20 MOD / names+pads build N", and set info.json version_number to 2.5.99. Scheme: keep Arturia's major.minor of the base firmware, 99 = patched, build byte counts our builds. 99 passes MCC's minimalVersionRequired 2.5.14 under numeric and text comparison.
- Startup screen (2026-10-21): the display chip (UI fw 0.0.1 build 1823, base 0x08000000, same 64-byte header/checksum format as the main image) has a 128x64 frame buffer (0x400 bytes, SSD1306 page format). At power-on FUN_08016f14 copies the picture at 0x08027F08 (literal at 0x08017130) into it and animates moving dots over it (state 1/2, 14 and 3 points from tables). Screen-saver pictures sit nearby (0x08028708 keys, 0x08028B08 radio, 0x08028F08 mask). tools/boot_logo.py redraws the big PRO as CON in the same 2-pixel style (C from the O opened on the right, original O, drawn N); build 2 ships it.

- Hardware check 2026-10-21: build 2 (e3e42f3) flashed by the user; startup screen, 2.5.99 version, root chords (held key picks the root, chords on the keys shown) and key lights confirmed working.

## Make bass on the device (build 4, 2026-10-21; confirmed on hardware)

- Hold Seq on the bass track, press the Track button of the chord track: the bass track's current pattern becomes a bass line from the chord track's current pattern. Still holding Seq, steps 1-5 pick the style and write again (1 Root, 2 Root + 5th, 3 Octaves, 4 Pulse, 5 Follow rhythm); the style is kept. Popup names it ("Bass: Root + 5th / from track 1"). Seq + its own row's Track stays stock. Releasing the bass track's Seq ends it.
- Generator in C (`tools/bass_gen.c`, same rules as `makeBass` in the page; the emulator test runs the page's makeBass in node and compares every note of all 5 styles). The build compiles it with `clang -fropi -Os` to Thumb assembly, keeps everything in .text, drops `.globl` (a global symbol left `bl bass_go` as a relocation = branch to itself) and now refuses any object with relocations or calls to undefined symbols.
- Live sequencer RAM, project p, track t 0-3 in sequencer mode, pattern n (from loader 080464d0 and accessors 0802f51c/0802d908/0802d6a0/0802d31c):
  - notes `0xC0000000 + p*0xF000 + t*0x3C00 + n*0x3C0`, 192 x {pitch (0xff unused), gate, vel, shift, rand}
  - slot -> step `0xC015C000 + p*0x3000 + t*0xC00 + n*0xC0` (0xff unused)
  - pass masks `0xC0104000 + ((p*5+t)*16+n)*0x20`, 4 bits per step, 8 steps per word
  - header `seq + p*0xFEC + t*0x140 + n*0x14 + 0x930` (`0802b4b0`), same 20 bytes as the SysEx buffer: +0 u16 state 0xAAAA/0xBBBB, +2..+6 default note (stock clear copies +3..+6 into cleared slots, `080299e0`), +7 swing, +8 length-1, +0xA root high nibble, +0xB scale low nibble (bit 6 = edited, set by `0802ceac(seq,1,n,t,p)` with state 0xAAAA), +0xC 64 on bits
  - current pattern step index `0x20003DA0 + (t*64 + step)*16 + k` = slot; rebuilt with `0802caf0(seq,t,0)` then `0802f340(seq,t)`; scale map with `0803094c(seq,t)`
  - track 1 in drum mode (seq + p*0xFEC + 0x1753 bit 0) keeps its data elsewhere (0xC0114000/0xC018C000): refused as source or target
- Sequencer note offs come from its own queue of sounding notes (seq + (q + t*0x80 + 0x21b3)*8, `08034b80`), not from pattern data, so rewriting a playing pattern should not hang notes (hardware check).
- Popup with our own text: as `08020e3c` does: state = ui[0xC] (ui = *0x20001510), shown when state <= 0x60 and its tbb byte at 0x08020e4e is 0x31 (0x6c: only when *0x200014d7 == 0; 0xa9: never); `0801f96c(ui,3/4/5/0x50)`, `08025274(*0x200017f8, text, ms)`, ui[0xC] = 0xF.
- Scratch: chord list at 0xC01EFA00 (512 bytes), popup text at 0xC01EFF80, inside the pad state block; pad state magic now "ZDAQ" (v9: ST_BT/ST_BS/ST_BSTYLE at 480-482).
- To check on hardware: the combo (stock Seq press first switches the bass track to sequencer mode), all 5 styles while stopped and while playing, no hanging notes, popup text, Save Project keeps the bass, drum-mode refusal.
- Hardware check 2026-10-21: build 4 (a843011) flashed by the user, identity reads 2.5.99 b4. Make bass (Root) from track 2 into track 3, saved as project 1, read back over SysEx: T3 = C2 step 1 for 9 steps, E2 step 10 for 1 step, C2 step 11 for 6 steps; this matches the source's on steps (1,4-7 C, 10 E, 11 C), and notes on its off steps are ignored. Root and scale were copied (C, 0), length 16. Then the user ran the build 4 checklist (all styles, switching while playing, popup text, drum-mode refusal, build 3 features) and reported everything working.

## Firmware patcher in the page (2026-10-22)

- The .kspf is a stored (uncompressed) zip with five entries: info.json, main and UI images for the KeyStep Pro, and main and UI images for the Chroma (untouched). KSCON changes info.json (2 bytes), the main image (18 runs, 5484 bytes including the appended hook block) and the UI image (17 runs, 76 bytes: the startup picture and checksums).
- `tools/make_web_patch.py` writes only those runs plus SHA-256 of every stock and patched entry into the page (`src/1f-fwpatch.js`, about 7.5 KB). The page's Firmware card reads the user's own 2.5.20 file, refuses it unless every entry matches stock, applies the runs, refuses unless every result matches the tested build, and rebuilds the zip with the input's own headers, so the download is byte for byte the tested .kspf (checked in the browser against the whole-file hash).
- `tools/test_web_patch.py <page dir>` runs the page's `tests/fwpatch.js` in headless Chrome with the stock file and checks the output is identical to the built .kspf; a KSCON file, a changed stock file and a non-zip are refused.
- After every new build: regenerate `src/1f-fwpatch.js`, run test_web_patch.py, release the page.

## Chord pads over SysEx (build 5, 2026-10-22; emulator-tested, not on hardware yet)

- Bulk SET item `0x78` (project), param `0x7D`, one index = track 2-4 as 1-3 (struct byte +4 holds it 0-based), 80 bytes: 16 pads x 5 notes, `0x7F` = unused (stored as `0xFF`). `setname_hook` passes it to `chord_set` (pad_hooks.S): converts into scratch at PAD_STATE+0x200, reads the project's second sector into staging, writes an empty "CHD1" block first if the staged block at +0xFEF0 has no magic, stages the track's 80 bytes at +0xFEF8 + (track-2)*80, programs the sector (one erase per track), clears the session byte 0x20000671 as the name does, and drops the pad RAM copy (ST_TAG = 0xFF, undo cleared) so the next pad press reloads from flash.
- Wrong length, index past track 4 or slot > 15 is ignored. Other projects untouched; the block survives a name write and a stock open/SET/commit (kspemu, real firmware code).
- No GET: the pads still cannot be read back over SysEx.
- `ksp_link.Link.set_chord_pads(proj, track, pads)` sends it; `ksp_setlist.py` writes a plan's `pads` (track -> up to 16 chords) after the name.

## Kept pad chords follow the octave (build 6, 2026-10-26; confirmed on hardware 2026-10-27)

- Chord pads stored chords played at fixed pitch, so at a low keyboard octave they sounded up to 2 octaves above the keys. Now `oct_shift` (pad_hooks.S) gives (track octave byte - 3) * 12; byte 3 = octave 0 on the panel (range -3..+2 = bytes 0..5). Capture stores notes minus the shift, play adds it (notes past 0..127 skipped). Stored chords (flash "CHD1" block and SysEx `0x7D` writes) therefore mean "as played at octave 0". Chords captured at another octave before build 6 play shifted by that difference.

## Note and chord names on the screen (build 7, 2026-10-27; emulator only)

- `tools/note_show.c` (second C file in the hook block; `build_ksp_patch.py` now prefixes each C file's `.L` labels with its name so they cannot clash). Popup as Make bass (`08025274`, 1000 ms, after the `0801f96c` 3/4/5/0x50 prep; skipped when UI state > 0x60 or the `08020e3c` table says no), text at 0xC01EFF00 (64 bytes, pad state block, below Make bass's 0xC01EFF80).
- `key_send` (080156f6) now sends the key, then `ns_key(slot)`: all held keys on that key's track (held-key table), and on a Chord-mode track each key + the track's chord offsets (track struct +0x1755.., 0 ends; root byte +0x1754 0xFF = no chord) through the track's scale map 0x20000674 + t*0x80, as `080382e0` does; Chord mode from `0802d160(seq, t, p)`. Track 1 in drum mode and track > 3 show nothing.
- `press_send` after a chord pad or root-chord step: `ns_pad(&notes[pad])`; drum pads show nothing. Root-chord keys (`key_rec`, and `key_send`'s root branch): "Root: E".
- Text: one note "E3" (C4 = 60); several: chord name on line 1 (root position first, else slash chord over the lowest note; 35 shapes: triads, 5, sus, dim/aug, 6, 7ths, 9/11/13 with or without the 5th), notes on line 2 cut at 16 characters with "..". No known chord: the pitch classes. Sharps only, as the panel.
- Not done: clearing the popup on key release (it times out after ~1 s), an on/off switch, naming notes the arpeggiator or sequencer plays. To check on hardware: popup timing with fast playing, no lag on keys, no popup over menus/Shift pages, Chord-mode names match what sounds.

## Step lights show the pads, drum names (build 8, 2026-10-27; emulator only)

- LED object `*(0x20001490)`: per LED 3 bytes at +0x1C + id*3 {on, dim, colour (low nibble)}, send flag at +0x184 + id; steps are ids 0x35-0x44 (0x74.. are the length LEDs, 0x46-0x6a keys). `08053eb8` (and the bulk step setters `08053f1c`/`08053f90`) only update the buffer and flag; `08054c2c` sends every flagged LED (steps batched via `08054520`), called from 7 places (0800e328, 0800e84a, 0801696a, 0801f7be, 0802a88c, 0802b876, 08030bd6; one passes a stack copy). Colours (`0802b588`): 5 white, 4 red, 6 blue, 8 off, track colours at 0x20000058; the dim byte scales the colour down (stock: steps not under the playhead).
- All 7 calls go to `led_flush` -> `ns_leds(leds, chord_notes)` -> stock send. Only for the real object: while a pad mode is on, the 16 steps get held = white bright, chord pad matching the keys held on its track (pitch classes, Chord mode included; kept or scale chord) = track colour bright, kept chord / any drum or root-chord pad = track colour dim, empty chord pad = white dim. What the stock firmware sets meanwhile is kept and put back when the mode ends (unless it set something newer). Scratch at 0xC01EFC00 ("LGT1"). Match result cached on held notes + track + project + kept table checksum.
- Turning a chord pad mode on now loads the project's kept chords (`chords_load`) so the lights are right before the first press.
- Drum pads name their lane and note ("Drum 1 / C2").
- To check on hardware: colours/brightness as described, no flicker while the sequencer plays (playhead), stock step lights correct after leaving pad mode, no slowdown.

## Invalid project block (hardware, 2026-10-27)

- A project whose project-level block (item 0x78) is erased flash loads on the panel as defaults (C Chromatic, 120 BPM), although its patterns read back correctly over SysEx. Signs: tempo `p0x46-48` = 127 127 3, `p0x4B` (current scene) gives no reply. Any project SET (`0800cca8`) writes the block marker 0xAAAA. `ksp_setlist.py` checks the block (`project_block_bad`) and, if bad, writes stock values (`PROJECT_DEFAULTS`) before the commit; verified in the emulator and on hardware.
