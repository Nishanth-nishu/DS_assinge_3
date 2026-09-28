#!/usr/bin/env python3
"""
Job 3 - Reducer: generate wedges (open triads) at each vertex.

Input : "v<TAB>h" oriented edges (v has lower rank than h), grouped by v.
Output: two kinds of records, both keyed by a canonical edge id "a,b":
          "a,b<TAB>$"  - edge (v,h) exists  (one per oriented edge)
          "a,b<TAB>1"  - a wedge a <- v -> b was found; the triangle
                         {v,a,b} exists iff edge (a,b) exists.

Job 4 joins the two on the edge id.
"""
import sys


def flush(v, outs, out):
    if v is None:
        return
    vi = int(v)
    hs = sorted({int(h) for h in outs})
    for h in hs:
        a, b = (vi, h) if vi < h else (h, vi)
        out.write(f"{a},{b}\t$\n")
    n = len(hs)
    for i in range(n):
        a = hs[i]
        for j in range(i + 1, n):
            out.write(f"{a},{hs[j]}\t1\n")


def main():
    out = sys.stdout
    cur, outs = None, []
    for line in sys.stdin:
        key, _, val = line.rstrip("\n").partition("\t")
        if not val:
            continue
        if key != cur:
            flush(cur, outs, out)
            cur, outs = key, []
        outs.append(val)
    flush(cur, outs, out)


if __name__ == "__main__":
    main()
