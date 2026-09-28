#!/usr/bin/env python3
"""
Job 4 - Reducer: close wedges and count triangles.

Input : "a,b<TAB>$" and "a,b<TAB><count>" grouped by edge id.
Output: a single line "triangles<TAB><partial count>" for this reducer.

For each edge id, if the edge exists ("$" seen) every wedge that points at it
is a real triangle. Each triangle produces exactly one wedge (at its
lowest-ranked vertex, see reducer2.py), so the sum is exact.
"""
import sys


def main():
    total = 0
    cur, has_edge, cnt = None, False, 0
    for line in sys.stdin:
        key, _, val = line.rstrip("\n").partition("\t")
        if not val:
            continue
        if key != cur:
            if has_edge:
                total += cnt
            cur, has_edge, cnt = key, False, 0
        if val == "$":
            has_edge = True
        else:
            cnt += int(val)
    if has_edge:
        total += cnt
    sys.stdout.write(f"triangles\t{total}\n")


if __name__ == "__main__":
    main()
