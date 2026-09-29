#!/usr/bin/env python3
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
