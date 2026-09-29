#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export LC_ALL=C

INPUT_FILE=${1:-test_data/sample.txt}
OUTPUT_FILE=${2:-output.txt}

tail -n +2 "$INPUT_FILE" | python3 mapper1.py | sort | python3 reducer1.py \
  | python3 identity_mapper.py | sort | python3 reducer2.py \
  | python3 identity_mapper.py | sort | python3 reducer3.py \
  | python3 identity_mapper.py | sort | python3 combiner4.py | sort | python3 reducer4.py \
  | python3 sum_reducer.py > "$OUTPUT_FILE"

echo "MapReduce pipeline completed. Triangles = $(cat "$OUTPUT_FILE") (saved to $OUTPUT_FILE)"
