#!/usr/bin/env python3
import sys

sys.stdout.writelines(line for line in sys.stdin if "\t" in line)
