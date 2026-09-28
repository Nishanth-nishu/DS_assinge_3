#!/usr/bin/env python3
"""
Sequential reference implementation used for correctness verification.

    verify_sequential.py graph.txt            -> prints the triangle count
    verify_sequential.py graph.txt --brute    -> O(V^3) brute force (tiny graphs)

The fast path is the classic "forward" algorithm with (degree, id) ordering;
the brute-force path checks every vertex triple and is completely independent
of the MapReduce logic.
"""
import sys
from itertools import combinations


def read_graph(path):
    adj = {}
    with open(path) as f:
        f.readline()  # header "V E"
        for line in f:
            p = line.split()
            if len(p) != 2:
                continue
            u, v = int(p[0]), int(p[1])
            if u == v:
                continue
            adj.setdefault(u, set()).add(v)
            adj.setdefault(v, set()).add(u)
    return adj


def fast(adj):
    rank = {v: (len(n), v) for v, n in adj.items()}
    out = {v: {w for w in n if rank[w] > rank[v]} for v, n in adj.items()}
    total = 0
    for v, hs in out.items():
        for w in hs:
            total += len(hs & out[w])
    return total


def brute(adj):
    return sum(1 for a, b, c in combinations(sorted(adj), 3)
               if b in adj[a] and c in adj[a] and c in adj[b])


if __name__ == "__main__":
    g = read_graph(sys.argv[1])
    print(brute(g) if "--brute" in sys.argv else fast(g))
