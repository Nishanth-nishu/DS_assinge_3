#!/usr/bin/env python3
import sys
import zlib


def main():
    n = int(sys.argv[1])
    prefix = sys.argv[2]
    files = [open(f"{prefix}_p{r:02d}", "w") for r in range(n)]
    for line in sys.stdin:
        key = line.split("\t", 1)[0]
        files[zlib.crc32(key.encode()) % n].write(line)
    for f in files:
        f.close()


if __name__ == "__main__":
    main()
