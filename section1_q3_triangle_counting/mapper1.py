#!/usr/bin/env python3
"""
Job 1 - Mapper: build adjacency.

Input : one undirected edge per line, "u v" (the "V E" header line is stripped
        by the driver scripts before the data is split across mappers).
Output: "u<TAB>v" and "v<TAB>u" for every edge, so the reducer for vertex x
        receives the full neighbour list of x.

Self-loops (u == v) and malformed lines are ignored: they can never be part of
a triangle.
"""
import sys


def main():
    out = sys.stdout
    for line in sys.stdin:
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            u, v = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        if u == v:
            continue
        out.write(f"{u}\t{v}\n{v}\t{u}\n")


if __name__ == "__main__":
    main()
