#!/usr/bin/env python3
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
