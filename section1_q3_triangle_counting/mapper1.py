#!/usr/bin/env python3
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
