#!/usr/bin/env python3
"""
Job 2 - Reducer: orient every edge from lower rank to higher rank.

Input : "a,b<TAB>x deg(x)" grouped by edge id; two values per edge.
Output: "low<TAB>high" where rank(v) = (deg(v), v).

Orienting edges by (degree, id) gives a total order on vertices. Every
triangle {p, q, r} with rank(p) < rank(q) < rank(r) is therefore discovered
exactly once - at its lowest-ranked vertex p - which is what guarantees no
double counting. Pointing edges towards higher-degree vertices also bounds the
out-degree of every vertex by O(sqrt(E)), which keeps the number of wedges
generated in Job 3 at O(E^1.5) even on skewed (power-law) graphs.
"""
import sys


def flush(key, vals, out):
    if key is None or len(vals) < 2:
        return
    (x, dx), (y, dy) = vals[0], vals[1]
    if (dx, x) < (dy, y):
        out.write(f"{x}\t{y}\n")
    else:
        out.write(f"{y}\t{x}\n")


def main():
    out = sys.stdout
    cur, vals = None, []
    for line in sys.stdin:
        key, _, val = line.rstrip("\n").partition("\t")
        if not val:
            continue
        if key != cur:
            flush(cur, vals, out)
            cur, vals = key, []
        v, d = val.split()
        vals.append((int(v), int(d)))
    flush(cur, vals, out)


if __name__ == "__main__":
    main()
