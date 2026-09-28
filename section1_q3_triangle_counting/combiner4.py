#!/usr/bin/env python3
"""
Job 4 - Combiner (optional, map-side): pre-aggregate wedge counts per edge id.

Input : sorted "a,b<TAB>$" / "a,b<TAB><count>" lines of ONE mapper.
Output: at most one "$" and one "<count>" line per key.

Reduces shuffle volume when the same closing edge is the target of many
wedges (common around hubs). It is associative, so it is safe to run zero,
one or many times.
"""
import sys


def flush(key, has_edge, cnt, out):
    if key is None:
        return
    if has_edge:
        out.write(f"{key}\t$\n")
    if cnt:
        out.write(f"{key}\t{cnt}\n")


def main():
    out = sys.stdout
    cur, has_edge, cnt = None, False, 0
    for line in sys.stdin:
        key, _, val = line.rstrip("\n").partition("\t")
        if not val:
            continue
        if key != cur:
            flush(cur, has_edge, cnt, out)
            cur, has_edge, cnt = key, False, 0
        if val == "$":
            has_edge = True
        else:
            cnt += int(val)
    flush(cur, has_edge, cnt, out)


if __name__ == "__main__":
    main()
