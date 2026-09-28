#!/usr/bin/env python3
"""
Final aggregation: add up the partial "triangles<TAB>N" lines produced by the
Job 4 reducers and print the single global triangle count (required output).
"""
import sys

total = 0
for line in sys.stdin:
    _, _, val = line.rstrip("\n").partition("\t")
    if val:
        total += int(val)
print(total)
