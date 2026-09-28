#!/bin/bash
# Run everything on the RCE cluster (from the login node):
#   bash rce_run_all.sh          -> installs deps, runs quick tests, submits SLURM jobs
#   bash rce_run_all.sh collect  -> prints all results once the jobs have finished
cd "$(dirname "$0")"
ROOT=$PWD
if [ "$1" = "collect" ]; then
  squeue -u "$USER"
  echo; echo "######## Section 1 Q3 - triangle counting (RCE) ########"
  column -t -s, section1_q3_triangle_counting/perf_results/triangles_dist_summary.csv 2>/dev/null \
    || cat section1_q3_triangle_counting/perf_results/triangles_dist_summary.csv
  tail -n 3 section1_q3_triangle_counting/triangles_*.err 2>/dev/null
  echo; echo "######## Section 3 P2 - food ordering (RCE) ########"
  cat section3_q2_food_ordering/food_demo_*.out 2>/dev/null
  tail -n 5 section3_q2_food_ordering/food_demo_*.err 2>/dev/null
  exit 0
fi

set -e
echo "== python: $(python3 --version)"
python3 -m pip install --user --quiet grpcio grpcio-tools

echo "== Section 1 Q3: correctness tests + datasets"
cd "$ROOT/section1_q3_triangle_counting"
chmod +x *.sh *.py *.sbatch
./run_tests.sh | tail -3
./make_datasets.sh >/dev/null
rm -f perf_results/triangles_dist_summary.csv
# scaling runs, one after another so they don't compete for nodes
J=$(sbatch --parsable --nodes=1 --ntasks=1 run_distributed.sbatch)
for cfg in "2 2" "4 4" "4 8"; do
  set -- $cfg
  J=$(sbatch --parsable --dependency=afterany:$J --nodes=$1 --ntasks=$2 run_distributed.sbatch)
done
echo "   submitted triangle jobs (last id $J)"

echo "== Section 3 P2: stubs + multi-node demo/tests"
cd "$ROOT/section3_q2_food_ordering"
chmod +x *.sh *.py *.sbatch
./setup.sh
sbatch run_demo.sbatch

echo
echo "Jobs submitted. Check with: squeue -u $USER"
echo "When the queue is empty run:  bash rce_run_all.sh collect"
