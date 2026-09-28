#!/bin/bash
# Submit everything to SLURM from the RCE login node. Nothing heavy runs here:
# this script only calls sbatch (setup/tests/datasets run inside hw3_prep).
#   bash rce_run_all.sh          -> submit all jobs
#   bash rce_run_all.sh collect  -> print results after the jobs finish
cd "$(dirname "$0")"
ROOT=$PWD
if [ "$1" = "collect" ]; then
  squeue -u "$USER"
  echo; echo "######## Prep job (tests) ########"; cat hw3_prep_*.out 2>/dev/null; tail -n 5 hw3_prep_*.err 2>/dev/null
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
chmod +x rce_prep.sbatch section1_q3_triangle_counting/*.{sh,py,sbatch} section3_q2_food_ordering/*.{sh,py,sbatch}

PREP=$(sbatch --parsable rce_prep.sbatch)
echo "prep job:            $PREP"

# Section 1 Q3: scaling runs, one after another (fair timings), after prep succeeds
cd "$ROOT/section1_q3_triangle_counting"
J=$(sbatch --parsable --dependency=afterok:$PREP --nodes=1 --ntasks=1 run_distributed.sbatch)
echo "triangles 1n/1t:     $J"
for cfg in "2 2" "4 4" "4 8"; do
  set -- $cfg
  J=$(sbatch --parsable --dependency=afterany:$J --nodes=$1 --ntasks=$2 run_distributed.sbatch)
  echo "triangles ${1}n/${2}t:     $J"
done

# Section 3 P2: multi-node demo + tests, after prep succeeds
cd "$ROOT/section3_q2_food_ordering"
D=$(sbatch --parsable --dependency=afterok:$PREP run_demo.sbatch)
echo "food ordering demo:  $D"

echo
echo "Watch:  squeue -u $USER      When empty:  bash rce_run_all.sh collect"
