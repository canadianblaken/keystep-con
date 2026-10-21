#!/bin/bash
# Read-only: open a read session on project $1 (default 1) and dump track $2 (default 1) block from FLASH.
P=$(printf %02X ${1:-1}); T=$(printf %02X $((0x7A + ${2:-1})))
D=${MIDI_PORT:-hw:1,0,0}   # amidi -l lists the ports
amidi -p $D -S "F0 00 20 6B 7F 42 05 $P F7"; sleep 0.3
get(){ amidi -p $D -S "F0 00 20 6B 7F 42 0B $P $1 01 $T $2 01 F7" -d -t 0.4 | tr -d "\n" | awk "{print \$14}"; }
echo "state(p27)=$(get 27 01) oct/mode(p56)=$(get 56 01)"
printf "chord bytes:"; for n in $(seq 1 16); do printf " %s" $(get 57 $(printf %02X $n)); done; echo
