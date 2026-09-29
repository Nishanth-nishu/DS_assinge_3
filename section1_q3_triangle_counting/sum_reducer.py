#!/usr/bin/env python3
import sys

total = 0
for line in sys.stdin:
    _, _, val = line.rstrip("\n").partition("\t")
    if val:
        total += int(val)
print(total)
