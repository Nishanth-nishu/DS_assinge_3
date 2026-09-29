#!/bin/bash
set -e
cd "$(dirname "$0")"
mkdir -p test_data
python3 gen_graph.py 1000    5000    --seed 1 --model er       > test_data/tri_small.txt
python3 gen_graph.py 10000   100000  --seed 2 --model er       > test_data/tri_medium.txt
python3 gen_graph.py 100000  1000000 --seed 3 --model er       > test_data/tri_large.txt
python3 gen_graph.py 50000   500000  --seed 4 --model powerlaw > test_data/tri_powerlaw.txt
ls -lh test_data
