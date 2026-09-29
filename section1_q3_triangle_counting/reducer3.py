#!/usr/bin/env python3
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
