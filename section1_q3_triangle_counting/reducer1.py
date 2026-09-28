#!/usr/bin/env python3
"""
Job 1 - Reducer: compute the degree of every vertex.

Input : "x<TAB>y" lines grouped (sorted) by x.
Output: for every distinct neighbour y of x, one record keyed by the
        canonical edge id "min(x,y),max(x,y)" carrying "x deg(x)".

Duplicate edges in the input are removed here (neighbours kept in a set),
so an edge listed twice (e.g. "0 1" and "1 0") is not counted twice.
Job 2 then sees exactly two records per edge: one from each endpoint.
"""
import sys


def flush(x, nbrs, out):
    if x is None:
        return
    deg = len(nbrs)
    xi = int(x)
    for y in nbrs:
        yi = int(y)
        a, b = (xi, yi) if xi < yi else (yi, xi)
        out.write(f"{a},{b}\t{xi} {deg}\n")


def main():
    out = sys.stdout
    cur, nbrs = None, set()
    for line in sys.stdin:
        key, _, val = line.rstrip("\n").partition("\t")
        if not val:
            continue
        if key != cur:
            flush(cur, nbrs, out)
            cur, nbrs = key, set()
        nbrs.add(val)
    flush(cur, nbrs, out)


if __name__ == "__main__":
    main()
