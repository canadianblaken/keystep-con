| field | name | paramId | globalParamId | item type / global group | type | range/default | values |
|---|---|---|---|---|---|---|---|
| 1 | Project tempo part 3 (LSB) | 70 |  | project |  |  |  |
| 2 | Project tempo part 2 (MidSB) | 71 |  | project |  |  |  |
| 3 | Project tempo part 1 (MSB) | 72 |  | project |  |  |  |
| 4 | global BPM, metronome triplet, metronome size, wait to load in a bitfield | 73 |  | project |  |  |  |
| 5 | Global swing (%) | 74 |  | project |  |  |  |
| 6 | Current scene | 75 |  | project |  |  |  |
| 7 | Scene / Current track, Scene / Chain state in a bitfield | 76 |  | sceneIdx |  |  |  |
| 8 | Scene / Mute state (4 LSB useful) | 77 |  | sceneIdx |  |  |  |
| 9 | Scene / Solo state (4 LSB useful) | 78 |  | sceneIdx |  |  |  |
| 10 | Drum mute state part 4 (LSB) | 79 |  | sceneIdx |  |  |  |
| 11 | Drum mute state part 3 (MidLSB) | 80 |  | sceneIdx |  |  |  |
| 12 | Drum mute state part 2 (MidMSB) | 81 |  | sceneIdx |  |  |  |
| 13 | Drum mute state part 1 (MSB) | 82 |  | sceneIdx |  |  |  |
| 14 | Scene / Track / Current pattern | 83 |  | sceneIdx-trackIdx |  |  |  |
| 15 | Scene / Track / Chain | 84 |  | sceneIdx-trackIdx-chainIdx |  |  |  |
| 16 | Track transposition state, transposition octave in a bitfield | 85 |  | track4 |  |  |  |
| 17 | Track keyboard octave, chord mode state, Arp/Drum mode state in a bitfield | 86 |  | track4 |  |  |  |
| 60 | Track transposition | 122 |  | track4 |  |  |  |
| 18 | Chord | 87 |  | track4-paramIdx |  |  |  |
| 19 | Pattern CC triplet state, step size in a bitfield | 88 |  | trackCtrl-paramIdx |  |  |  |
| 20 | Pattern CC Step count | 89 |  | trackCtrl-paramIdx |  |  |  |
| 21 | Knob 1 (pitch) CC | 90 |  | trackCtrl-patternIdx-stepIdx |  |  |  |
| 22 | Knob 2 (gate length) CC | 91 |  | trackCtrl-patternIdx-stepIdx |  |  |  |
| 23 | Knob 3 (velocity) CC | 92 |  | trackCtrl-patternIdx-stepIdx |  |  |  |
| 24 | Knob 4 (time shift) CC | 93 |  | trackCtrl-patternIdx-stepIdx |  |  |  |
| 25 | Knob 5 (randomness) CC | 94 |  | trackCtrl-patternIdx-stepIdx |  |  |  |
| 26 | Step CC active | 95 |  | trackCtrl-patternIdx-stepIdx |  |  |  |
| 27 | Step CC skip | 96 |  | trackCtrl-patternIdx-stepIdx |  |  |  |
| 28 | Pattern Seq swing (%) (an offset of 25 is applied to be send by MIDI) (-25% to +25%) | 97 |  | track4-paramIdx |  |  |  |
| 29 | Pattern Seq step count | 98 |  | track4-paramIdx |  |  |  |
| 30 | Pattern Seq triplet state, swing offset state, polyrythm state, step size, playback direction in a bitfield | 99 |  | track4-paramIdx |  |  |  |
| 31 | Pattern Seq ARP/Drum mode, ARP type, ARP octave in a bitfield | 100 |  | track4-paramIdx |  |  |  |
| 32 | Pattern Seq user scale 1 part 3 (LSB) | 101 |  | project |  |  |  |
| 33 | Pattern Seq user scale 1 part 2 (MidSB) | 102 |  | project |  |  |  |
| 34 | Pattern Seq user scale 1 part 1 (MSB) | 103 |  | project |  |  |  |
| 35 | Pattern Seq user scale 2 part 3 (LSB) | 104 |  | project |  |  |  |
| 36 | Pattern Seq user scale 2 part 2 (MidSB) | 105 |  | project |  |  |  |
| 37 | Pattern Seq user scale 2 part 1 (MSB) | 106 |  | project |  |  |  |
| 38 | Pattern Seq root note | 107 |  | track4-paramIdx |  |  |  |
| 39 | Pattern Seq scale | 108 |  | track4-paramIdx |  |  |  |
| 40 | Seq note pitch | 109 |  | track4-paramIdx-groupIdx-paramIdx |  |  |  |
| 41 | Seq note gate length | 110 |  | track4-paramIdx-groupIdx-paramIdx |  |  |  |
| 42 | Seq note velocity | 111 |  | track4-paramIdx-groupIdx-paramIdx |  |  |  |
| 43 | Seq note time shift | 112 |  | track4-paramIdx-groupIdx-paramIdx |  |  |  |
| 44 | Seq note randomness | 113 |  | track4-paramIdx-groupIdx-paramIdx |  |  |  |
| 45 | Pattern DRUM swing (%) (an offset of 25 is applied to be send by MIDI) (-25% to +25%) | 114 |  | track1-paramIdx |  |  |  |
| 46 | Pattern DRUM step count | 115 |  | track1-paramIdx |  |  |  |
| 47 | Pattern DRUM triplet state, swing offset state, polyrythm state, step size, playback direction in a bitfield | 116 |  | track1-paramIdx |  |  |  |
| 48 | DRUM note pitch | 117 |  | track1-paramIdx-groupIdx-paramIdx |  |  |  |
| 49 | DRUM note gate length | 118 |  | track1-paramIdx-groupIdx-paramIdx |  |  |  |
| 50 | DRUM note velocity | 119 |  | track1-paramIdx-groupIdx-paramIdx |  |  |  |
| 51 | DRUM note time shift | 120 |  | track1-paramIdx-groupIdx-paramIdx |  |  |  |
| 52 | DRUM note randomness | 121 |  | track1-paramIdx-groupIdx-paramIdx |  |  |  |
| 53 | Step Seq step active | 48 |  | track4-paramIdx-groupIdx-paramIdx |  |  |  |
| 54 | Step Seq step skip | 49 |  | track4-paramIdx-groupIdx-paramIdx |  |  |  |
| 55 | Seq note corresponding step | 50 |  | track4-paramIdx-groupIdx-paramIdx |  |  |  |
| 56 | DRUM poly step count | 51 |  | track1-paramIdx-groupIdx-paramIdx |  |  |  |
| 57 | DRUM step active | 52 |  | track1-paramIdx-groupIdx-paramIdx |  |  |  |
| 58 | DRUM step skip | 53 |  | track1-paramIdx-groupIdx-paramIdx |  |  |  |
| 59 | DRUM step corresponding step | 54 |  | track1-paramIdx-groupIdx-paramIdx |  |  |  |
| 61 | ARP group 1 parameters | 68 |  | project |  |  |  |
| 62 | ARP group 2 parameters | 69 |  | project |  |  |  |
| 63 | Track MIDI channel | 123 |  | project-trackIdx |  |  |  |
| 64 | Track tranpose group | 55 |  | project-trackIdx |  |  |  |
| 65 | ARP swing | 56 |  | project-trackIdx |  |  |  |
| 66 | Project data state | 37 |  | project |  |  |  |
| 67 | Scene data state | 38 |  | sceneIdx |  |  |  |
| 68 | Track data state | 39 |  | track4 |  |  |  |
| 69 | Pattern data state | 40 |  | track4-paramIdx |  |  |  |
| 70 | Track seq color | 59 |  | track4 |  | .. d=8 |  |
| 71 | Track drum color | 60 |  | track1 |  | .. d=8 |  |
| 72 | Pattern Seq Program Change Value | 20 |  | track4-paramIdx |  | .. d=0 |  |
| 73 | Pattern Seq Program Change Value | 21 |  | track4-paramIdx |  | .. d=0 |  |
| 74 | Pattern Seq Program Change Value MSB | 22 |  | track4-paramIdx |  | .. d=0 |  |
| 75 | Pattern Seq Program Change Value LSB | 23 |  | track4-paramIdx |  | .. d=0 |  |
| 76 | Pattern Drum Program Change Value | 25 |  | track1-paramIdx |  | .. d=0 |  |
| 77 | Pattern Drum Program Change Value | 26 |  | track1-paramIdx |  | .. d=0 |  |
| 78 | Pattern Drum Program Change Value MSB | 27 |  | track1-paramIdx |  | .. d=0 |  |
| 79 | Pattern Drum Program Change Value LSB | 28 |  | track1-paramIdx |  | .. d=0 |  |
| 500 | Wait to Load Scene | 65 | 2 | Launch Quantize | LIST | .. d=1 | 0=1 beat, 1=1 bar, 2=2 bars, 3=4 bars |
| 501 | Wait to Load Project | 65 | 3 | Launch Quantize | LIST | .. d=1 | 0=OFF, 1=1 bar, 2=2 bars, 3=4 bars |
| 502 | Wait to Load Pattern | 65 | 4 | Launch Quantize | LIST | .. d=1 | 1=At end, 2=1 bar |
| 510 | Voice 1 PITCH CV output | 65 | 6 | CV/Gate Settings | LIST | .. d=0 | 0=1 V/Oct, 1=1,2 V/Oct, 2=Hz/Volt |
| 520 | Voice 2 PITCH CV output | 65 | 7 | CV/Gate Settings | LIST | .. d=0 | 0=1 V/Oct, 1=1,2 V/Oct, 2=Hz/Volt |
| 530 | Voice 3 PITCH CV output | 65 | 8 | CV/Gate Settings | LIST | .. d=0 | 0=1 V/Oct, 1=1,2 V/Oct, 2=Hz/Volt |
| 540 | Voice 4 PITCH CV output | 65 | 9 | CV/Gate Settings | LIST | .. d=0 | 0=1 V/Oct, 1=1,2 V/Oct, 2=Hz/Volt |
| 511 | Voice 1 base note | 65 | 10 | CV/Gate Settings | NOTE | .. d=36 |  |
| 521 | Voice 2 base note | 65 | 11 | CV/Gate Settings | NOTE | .. d=36 |  |
| 531 | Voice 3 base note | 65 | 12 | CV/Gate Settings | NOTE | .. d=36 |  |
| 541 | Voice 4 base note | 65 | 13 | CV/Gate Settings | NOTE | .. d=36 |  |
| 512 | Voice 1 GATE CV output | 65 | 14 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 522 | Voice 2 GATE CV output | 65 | 15 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 532 | Voice 3 GATE CV output | 65 | 16 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 542 | Voice 4 GATE CV output | 65 | 17 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 513 | Voice 1 MOD CV source | 65 | 18 | CV/Gate Settings | LIST | .. d=0 | 0=Velocity, 1=Pressure, 2=Mod Wheel |
| 523 | Voice 2 MOD CV source | 65 | 19 | CV/Gate Settings | LIST | .. d=0 | 0=Velocity, 1=Pressure, 2=Mod Wheel |
| 533 | Voice 3 MOD CV source | 65 | 20 | CV/Gate Settings | LIST | .. d=0 | 0=Velocity, 1=Pressure, 2=Mod Wheel |
| 543 | Voice 4 MOD CV source | 65 | 21 | CV/Gate Settings | LIST | .. d=0 | 0=Velocity, 1=Pressure, 2=Mod Wheel |
| 514 | Voice 1 MOD CV max voltage | 65 | 22 | CV/Gate Settings | LIST | .. d=4 | 0=1 V, 1=2 V, 2=3 V, 3=4 V, 4=5 V, 5=6 V, 6=7 V, 7=8 V, 8=9 V, 9=10 V |
| 524 | Voice 2 MOD CV max voltage | 65 | 23 | CV/Gate Settings | LIST | .. d=4 | 0=1 V, 1=2 V, 2=3 V, 3=4 V, 4=5 V, 5=6 V, 6=7 V, 7=8 V, 8=9 V, 9=10 V |
| 534 | Voice 3 MOD CV max voltage | 65 | 24 | CV/Gate Settings | LIST | .. d=4 | 0=1 V, 1=2 V, 2=3 V, 3=4 V, 4=5 V, 5=6 V, 6=7 V, 7=8 V, 8=9 V, 9=10 V |
| 544 | Voice 4 MOD CV max voltage | 65 | 25 | CV/Gate Settings | LIST | .. d=4 | 0=1 V, 1=2 V, 2=3 V, 3=4 V, 4=5 V, 5=6 V, 6=7 V, 7=8 V, 8=9 V, 9=10 V |
| 515 | Voice 1 Pitch Bend range | 65 | 138 | CV/Gate Settings | LIST |  | 0=1 semitone, 1=2 semitones, 2=3 semitones, 3=4 semitones, 4=5 semitones, 5=6 semitones, 6=7 semitones, 7=8 semitones, 8=9 semitones, 9=10 semitones, 10=11 semitones, 11=12 semitones, 12=13 semitones, 13=14 semitones, 14=15 semitones, 15=16 semitones, 16=17 semitones, 17=18 semitones, 18=19 semitone |
| 525 | Voice 2 Pitch Bend range | 65 | 139 | CV/Gate Settings | LIST |  | 0=1 semitone, 1=2 semitones, 2=3 semitones, 3=4 semitones, 4=5 semitones, 5=6 semitones, 6=7 semitones, 7=8 semitones, 8=9 semitones, 9=10 semitones, 10=11 semitones, 11=12 semitones, 12=13 semitones, 13=14 semitones, 14=15 semitones, 15=16 semitones, 16=17 semitones, 17=18 semitones, 18=19 semitone |
| 535 | Voice 3 Pitch Bend range | 65 | 140 | CV/Gate Settings | LIST |  | 0=1 semitone, 1=2 semitones, 2=3 semitones, 3=4 semitones, 4=5 semitones, 5=6 semitones, 6=7 semitones, 7=8 semitones, 8=9 semitones, 9=10 semitones, 10=11 semitones, 11=12 semitones, 12=13 semitones, 13=14 semitones, 14=15 semitones, 15=16 semitones, 16=17 semitones, 17=18 semitones, 18=19 semitone |
| 545 | Voice 4 Pitch Bend range | 65 | 141 | CV/Gate Settings | LIST |  | 0=1 semitone, 1=2 semitones, 2=3 semitones, 3=4 semitones, 4=5 semitones, 5=6 semitones, 6=7 semitones, 7=8 semitones, 8=9 semitones, 9=10 semitones, 10=11 semitones, 11=12 semitones, 12=13 semitones, 13=14 semitones, 14=15 semitones, 15=16 semitones, 16=17 semitones, 17=18 semitones, 18=19 semitone |
| 550 | Knob acceleration | 65 | 59 | MIDI Settings | LIST | .. d=1 | 0=Slow, 1=Medium, 2=Fast |
| 551 | Aftertouch curve | 65 | 60 | MIDI Settings | LIST | .. d=0 | 0=Linear, 1=Exponential, 2=Logarithmic |
| 552 | Velocity curve | 65 | 61 | MIDI Settings | LIST | .. d=0 | 0=Linear, 1=Exponential, 2=Logarithmic |
| 553 | Transport send | 65 | 62 | MIDI Settings | LIST | .. d=3 | 0=OFF, 1=MMC, 2=Real Time, 3=Both |
| 554 | Transport receive | 65 | 63 | MIDI Settings | LIST | .. d=3 | 0=OFF, 1=MMC, 2=Real Time, 3=Both |
| 555 | Clock send | 65 | 64 | MIDI Settings | LIST | .. d=1 | 0=OFF, 1=ON |
| 556 | Clock receive | 65 | 65 | MIDI Settings | LIST | .. d=1 | 0=OFF, 1=ON |
| 557 | MIDI Out 2 | 65 | 136 | MIDI Settings | LIST | .. d=0 | 0=Out, 1=Thru |
| 560 | MIDI send/receive | 65 | 67 | Touch Strip | LIST | .. d=1 | 0=OFF, 1=Send, 2=Receive, 3=Both |
| 561 | MIDI CC | 65 | 68 | Touch Strip | RANGE_HORIZONTAL | 0..127 d=9 |  |
| 562 | Touch Strip | 65 | 107 | Touch Strip | LIST | .. d=0 | 1=OFF, 0=ON |
| 570 | Track 1 input | 65 | 70 | MIDI Channel | CHANNEL | .. d=0 | 127=OFF |
| 571 | Track 2 input | 65 | 71 | MIDI Channel | CHANNEL | .. d=1 | 127=OFF |
| 572 | Track 3 input | 65 | 72 | MIDI Channel | CHANNEL | .. d=2 | 127=OFF |
| 573 | Track 4 input | 65 | 73 | MIDI Channel | CHANNEL | .. d=3 | 127=OFF |
| 574 | Drum input | 65 | 74 | MIDI Channel | CHANNEL | .. d=10 | 127=OFF |
| 575 | Track 1 output | 65 | 75 | MIDI Channel | CHANNEL | .. d=0 | 127=OFF |
| 576 | Track 2 output | 65 | 76 | MIDI Channel | CHANNEL | .. d=1 | 127=OFF |
| 577 | Track 3 output | 65 | 77 | MIDI Channel | CHANNEL | .. d=2 | 127=OFF |
| 578 | Track 4 output | 65 | 78 | MIDI Channel | CHANNEL | .. d=3 | 127=OFF |
| 579 | Drum output | 65 | 79 | MIDI Channel | CHANNEL | .. d=10 | 127=OFF |
| 590 | Mode | 65 | 81 | Drum Map | LIST | .. d=0 | 0=Chromatic, 1=Custom |
| 591 | Low note | 65 | 82 | Drum Map | RANGE_HORIZONTAL | 0..103 d=0 |  |
| 592 | Note 1 | 65 | 83 | Drum Map | RANGE_HORIZONTAL | 0..127 d=36 |  |
| 593 | Note 2 | 65 | 84 | Drum Map | RANGE_HORIZONTAL | 0..127 d=37 |  |
| 594 | Note 3 | 65 | 85 | Drum Map | RANGE_HORIZONTAL | 0..127 d=38 |  |
| 595 | Note 4 | 65 | 86 | Drum Map | RANGE_HORIZONTAL | 0..127 d=39 |  |
| 596 | Note 5 | 65 | 87 | Drum Map | RANGE_HORIZONTAL | 0..127 d=40 |  |
| 597 | Note 6 | 65 | 88 | Drum Map | RANGE_HORIZONTAL | 0..127 d=41 |  |
| 598 | Note 7 | 65 | 89 | Drum Map | RANGE_HORIZONTAL | 0..127 d=42 |  |
| 599 | Note 8 | 65 | 90 | Drum Map | RANGE_HORIZONTAL | 0..127 d=43 |  |
| 600 | Note 9 | 65 | 91 | Drum Map | RANGE_HORIZONTAL | 0..127 d=44 |  |
| 601 | Note 10 | 65 | 92 | Drum Map | RANGE_HORIZONTAL | 0..127 d=45 |  |
| 602 | Note 11 | 65 | 93 | Drum Map | RANGE_HORIZONTAL | 0..127 d=46 |  |
| 603 | Note 12 | 65 | 94 | Drum Map | RANGE_HORIZONTAL | 0..127 d=47 |  |
| 604 | Note 13 | 65 | 95 | Drum Map | RANGE_HORIZONTAL | 0..127 d=48 |  |
| 605 | Note 14 | 65 | 96 | Drum Map | RANGE_HORIZONTAL | 0..127 d=49 |  |
| 606 | Note 15 | 65 | 97 | Drum Map | RANGE_HORIZONTAL | 0..127 d=50 |  |
| 607 | Note 16 | 65 | 98 | Drum Map | RANGE_HORIZONTAL | 0..127 d=51 |  |
| 608 | Note 17 | 65 | 99 | Drum Map | RANGE_HORIZONTAL | 0..127 d=52 |  |
| 609 | Note 18 | 65 | 100 | Drum Map | RANGE_HORIZONTAL | 0..127 d=53 |  |
| 610 | Note 19 | 65 | 101 | Drum Map | RANGE_HORIZONTAL | 0..127 d=54 |  |
| 611 | Note 20 | 65 | 102 | Drum Map | RANGE_HORIZONTAL | 0..127 d=55 |  |
| 612 | Note 21 | 65 | 103 | Drum Map | RANGE_HORIZONTAL | 0..127 d=56 |  |
| 613 | Note 22 | 65 | 104 | Drum Map | RANGE_HORIZONTAL | 0..127 d=57 |  |
| 614 | Note 23 | 65 | 105 | Drum Map | RANGE_HORIZONTAL | 0..127 d=58 |  |
| 615 | Note 24 | 65 | 106 | Drum Map | RANGE_HORIZONTAL | 0..127 d=59 |  |
| 616 | Empty row | 65 | 139 | Drum Map | TEXT_LIST | .. d=0 | 0= |
| 620 | Input | 65 | 122 | Sync | LIST | .. d=0 | 0=Internal, 1=USB, 2=MIDI, 3=Clock, 4=Auto |
| 622 | Clock rate | 65 | 123 | Sync | LIST | .. d=6 | 0=1 PP16, 5=2 PPQ, 6=24 PPQ, 7=48 PPQ |
| 621 | Output | 65 | 124 | Sync | LIST | .. d=0 | 4=1 PP4Q, 3=1 PP2Q, 2=1 PPQ, 1=1 PP8, 0=1 PP16, 5=2 PPQ, 6=24 PPQ, 7=48 PPQ |
| 623 | Empty row | 65 | 139 | Sync | TEXT_LIST | .. d=0 | 0= |
| 630 | Count in | 65 | 114 | Metronome | LIST | .. d=1 | 0=OFF, 1=1 bar, 2=2 bars |
| 631 | Time signature | 65 | 115 | Metronome | LIST | .. d=4 | 0=1, 1=2, 2=3, 3=4, 4=5, 5=6, 6=7, 7=8, 8=9, 9=10, 10=11, 11=12, 12=13, 13=14, 14=15, 15=16 |
| 632 | Time division | 65 | 116 | Metronome | LIST | .. d=4 | 0=1/4, 1=1/4 Triplet, 2=1/8, 3=1/8 Triplet, 4=1/16, 5=1/16 Triplet, 6=1/32, 7=1/32 Triplet |
| 640 | Vegas mode | 65 | 108 | Misc | LIST | .. d=0 | 0=5 min, 1=10 min, 2=Never |
| 641 | Screen saver | 65 | 109 | Misc | LIST | .. d=0 | 0=2 min, 1=10 min, 2=30 min |
| 642 | Step listen | 65 | 110 | Misc | LIST | .. d=0 | 1=OFF, 0=ON |
| 650 | Global channel | 65 | 80 | Controller | CHANNEL | .. d=0 |  |
| 651 | Empty row | 65 | 139 | Controller | TEXT_LIST | .. d=0 | 0= |
| 660 | Drum Gate 1 | 65 | 128 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 661 | Drum Gate 2 | 65 | 129 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 662 | Drum Gate 3 | 65 | 130 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 663 | Drum Gate 4 | 65 | 131 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 664 | Drum Gate 5 | 65 | 132 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 665 | Drum Gate 6 | 65 | 133 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 666 | Drum Gate 7 | 65 | 134 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 667 | Drum Gate 8 | 65 | 135 | CV/Gate Settings | LIST | .. d=0 | 0=V-Trig 5 V, 1=V-Trig 12 V, 2=S-Trig |
| 668 | Empty row | 65 | 139 | CV/Gate Settings | TEXT_LIST | .. d=0 | 0= |
| 670 | Knob 1 MIDI CC | 65 | 28 | Controller | RANGE_HORIZONTAL | 0..127 d=74 |  |
| 671 | Knob 1 port | 65 | 33 | Controller | LIST | .. d=3 | 0=USB, 1=MIDI 1, 2=MIDI 2, 3=All |
| 672 | Knob 1 channel | 65 | 38 | Controller | CHANNEL | .. d=127 | 127=Global |
| 673 | Knob 1 mode | 65 | 43 |  | LIST | .. d=0 | 0=Absolute, 1=Relative 1, 2=Relative 2, 3=Relative 3 |
| 674 | Knob 1 min range | 65 | 48 | Controller | RANGE_HORIZONTAL | 0..127 d=0 |  |
| 675 | Knob 1 max range | 65 | 53 | Controller | RANGE_HORIZONTAL | 0..127 d=127 |  |
| 680 | Knob 2 MIDI CC | 65 | 29 | Controller | RANGE_HORIZONTAL | 0..127 d=74 |  |
| 681 | Knob 2 port | 65 | 34 | Controller | LIST | .. d=3 | 0=USB, 1=MIDI 1, 2=MIDI 2, 3=All |
| 682 | Knob 2 channel | 65 | 39 | Controller | CHANNEL | .. d=127 | 127=Global |
| 683 | Knob 2 mode | 65 | 44 |  | LIST | .. d=0 | 0=Absolute, 1=Relative 1, 2=Relative 2, 3=Relative 3 |
| 684 | Knob 2 min range | 65 | 49 | Controller | RANGE_HORIZONTAL | 0..127 d=0 |  |
| 685 | Knob 2 max range | 65 | 54 | Controller | RANGE_HORIZONTAL | 0..127 d=127 |  |
| 690 | Knob 3 MIDI CC | 65 | 30 | Controller | RANGE_HORIZONTAL | 0..127 d=74 |  |
| 691 | Knob 3 port | 65 | 35 | Controller | LIST | .. d=3 | 0=USB, 1=MIDI 1, 2=MIDI 2, 3=All |
| 692 | Knob 3 channel | 65 | 40 | Controller | CHANNEL | .. d=127 | 127=Global |
| 693 | Knob 3 mode | 65 | 45 |  | LIST | .. d=0 | 0=Absolute, 1=Relative 1, 2=Relative 2, 3=Relative 3 |
| 694 | Knob 3 min range | 65 | 50 | Controller | RANGE_HORIZONTAL | 0..127 d=0 |  |
| 695 | Knob 3 max range | 65 | 55 | Controller | RANGE_HORIZONTAL | 0..127 d=127 |  |
| 700 | Knob 4 MIDI CC | 65 | 31 | Controller | RANGE_HORIZONTAL | 0..127 d=74 |  |
| 701 | Knob 4 port | 65 | 36 | Controller | LIST | .. d=3 | 0=USB, 1=MIDI 1, 2=MIDI 2, 3=All |
| 702 | Knob 4 channel | 65 | 41 | Controller | CHANNEL | .. d=127 | 127=Global |
| 703 | Knob 4 mode | 65 | 46 |  | LIST | .. d=0 | 0=Absolute, 1=Relative 1, 2=Relative 2, 3=Relative 3 |
| 704 | Knob 4 min range | 65 | 51 | Controller | RANGE_HORIZONTAL | 0..127 d=0 |  |
| 705 | Knob 4 max range | 65 | 56 | Controller | RANGE_HORIZONTAL | 0..127 d=127 |  |
| 710 | Knob 5 MIDI CC | 65 | 32 | Controller | RANGE_HORIZONTAL | 0..127 d=74 |  |
| 711 | Knob 5 port | 65 | 37 | Controller | LIST | .. d=3 | 0=USB, 1=MIDI 1, 2=MIDI 2, 3=All |
| 712 | Knob 5 channel | 65 | 42 | Controller | CHANNEL | .. d=127 | 127=Global |
| 713 | Knob 5 mode | 65 | 47 |  | LIST | .. d=0 | 0=Absolute, 1=Relative 1, 2=Relative 2, 3=Relative 3 |
| 714 | Knob 5 min range | 65 | 52 | Controller | RANGE_HORIZONTAL | 0..127 d=0 |  |
| 715 | Knob 5 max range | 65 | 57 | Controller | RANGE_HORIZONTAL | 0..127 d=127 |  |
