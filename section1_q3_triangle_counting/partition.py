#!/usr/bin/env python3
"""
Hash partitioner used by the SLURM (non-Hadoop) distributed driver.

    partition.py <num_reducers> <output_prefix>

Reads key<TAB>value lines on stdin and appends each line to
"<output_prefix>_p<r>" where r = crc32(key) mod num_reducers.

This plays the role of Hadoop's HashPartitioner: all values for one key end
up at the same reducer. crc32 is used (not Python's hash()) because it is
deterministic across processes and nodes.
"""
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
