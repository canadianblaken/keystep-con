#!/usr/bin/env python3
"""Find Thumb BL/B.W callers of target addresses in the main image: blxref.py <hex>..."""
import sys
IMG = 'firmware/raw/keysteppro_main__fw2_5_20_2085__2024_03_04.raw.bin'
B = 0x08008000
d = open(IMG, 'rb').read()
def callers(T):
    r = []
    for i in range(0, len(d) - 3, 2):
        h1 = d[i] | d[i+1] << 8; h2 = d[i+2] | d[i+3] << 8
        if (h1 & 0xf800) == 0xf000 and (h2 & 0xd000) in (0xd000, 0x9000):
            S = (h1 >> 10) & 1; J1 = (h2 >> 13) & 1; J2 = (h2 >> 11) & 1
            off = (S << 24) | ((1 - (J1 ^ S)) << 23) | ((1 - (J2 ^ S)) << 22) | ((h1 & 0x3ff) << 12) | ((h2 & 0x7ff) << 1)
            if S: off -= 1 << 25
            if B + i + 4 + off == T: r.append(('bl' if h2 & 0x4000 else 'b.w', hex(B + i)))
    return r
for t in sys.argv[1:]:
    print(t, callers(int(t, 16)))
