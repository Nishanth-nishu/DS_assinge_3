#!/usr/bin/env python3
"""Identity mapper used by Jobs 2-4 (their input is already key<TAB>value)."""
import sys

sys.stdout.writelines(line for line in sys.stdin if "\t" in line)
