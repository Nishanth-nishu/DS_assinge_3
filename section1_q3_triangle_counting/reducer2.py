#!/usr/bin/env python3
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
