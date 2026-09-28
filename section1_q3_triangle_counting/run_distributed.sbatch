#!/bin/bash
#SBATCH --mem-per-cpu=2G
#SBATCH --job-name=mr_triangles
#SBATCH --output=triangles_%j.out
#SBATCH --error=triangles_%j.err
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00

# ============================================================
# Distributed MapReduce Triangle Counting - SLURM driver
#
#   sbatch run_distributed.sbatch [file1 file2 ...]      (files in test_data/)
#   sbatch --nodes=2 --ntasks=8 run_distributed.sbatch    (change parallelism)
#
# Every job runs as two distributed phases on $NT SLURM tasks:
#   MAP    : task t reads input split t -> mapper [-> sort -> combiner]
#            -> hash partition into $NT buckets   (j<J>_m<t>_p<r>)
#   REDUCE : task r gathers bucket r from all mappers -> sort -> reducer
#            (j<J>_out_<r>)
# i.e. a real map / shuffle(hash-partition) / sort / reduce, with the
# shared home filesystem acting as the "DFS" between nodes.
#
# Without SLURM (no srun) the tasks are run as local background processes,
# so the same script can be tested on a laptop.
# ============================================================
set -uo pipefail
export LC_ALL=C

if [ -n "${SLURM_SUBMIT_DIR:-}" ]; then SCRIPT_DIR="$SLURM_SUBMIT_DIR"
else SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; fi
cd "$SCRIPT_DIR"

export NT=${SLURM_NTASKS:-${NT:-4}}
export WORK="$SCRIPT_DIR/work_${SLURM_JOB_ID:-local$$}"
RESULTS_DIR="$SCRIPT_DIR/perf_results"
TEST_DATA_DIR="$SCRIPT_DIR/test_data"
SUMMARY_FILE="$RESULTS_DIR/triangles_dist_summary.csv"
mkdir -p "$RESULTS_DIR" "$WORK"

if [ ! -f "$SUMMARY_FILE" ]; then
  echo "input_file,input_size_bytes,V,E,num_tasks,split_s,j1_map_s,j1_reduce_s,j2_map_s,j2_reduce_s,j3_map_s,j3_reduce_s,j4_map_s,j4_reduce_s,final_sum_s,total_s,triangles,expected,correct" > "$SUMMARY_FILE"
fi

if [ $# -gt 0 ]; then TEST_FILES=("$@")
else TEST_FILES=(sample.txt tri_small.txt tri_medium.txt tri_large.txt tri_powerlaw.txt); fi

USE_SRUN=0
if [ -n "${SLURM_JOB_ID:-}" ] && command -v srun >/dev/null 2>&1; then USE_SRUN=1; fi

# run a command string on NT parallel tasks; $SLURM_PROCID = task id
launch() {
  if [ "$USE_SRUN" = 1 ]; then
    srun --ntasks="$NT" --kill-on-bad-exit=1 bash -c "$1"
  else
    local pids=()
    for ((i = 0; i < NT; i++)); do SLURM_PROCID=$i bash -c "$1" & pids+=($!); done
    for p in "${pids[@]}"; do wait "$p"; done
  fi
}

now() { date +%s%N; }
secs() { echo "scale=6; ($2 - $1) / 1000000000" | bc; }

# ---- generic MapReduce job ---------------------------------------------
# run_job J MAPPER COMBINER(or "") REDUCER IN_PREFIX   -> sets MAP_T, RED_T
run_job() {
  export J=$1 MAPPER=$2 COMBINER=$3 REDUCER=$4 IN_PREFIX=$5
  local s e
  rm -f "$WORK"/j"$J"_m*_p* "$WORK"/j"$J"_out_*

  s=$(now)
  launch '
    TID=$(printf "%02d" "$SLURM_PROCID")
    IN="$WORK/${IN_PREFIX}${TID}"
    [ -f "$IN" ] || : > "$IN"
    if [ -n "$COMBINER" ]; then
      python3 "$MAPPER" < "$IN" | sort | python3 "$COMBINER" \
        | python3 partition.py "$NT" "$WORK/j${J}_m${TID}"
    else
      python3 "$MAPPER" < "$IN" | python3 partition.py "$NT" "$WORK/j${J}_m${TID}"
    fi'
  e=$(now); MAP_T=$(secs "$s" "$e")

  s=$(now)
  launch '
    TID=$(printf "%02d" "$SLURM_PROCID")
    cat "$WORK"/j${J}_m*_p${TID} 2>/dev/null | sort | python3 "$REDUCER" \
      > "$WORK/j${J}_out_${TID}"'
  e=$(now); RED_T=$(secs "$s" "$e")
  echo "  Job $J: map ${MAP_T}s  shuffle+sort+reduce ${RED_T}s"
}

echo "============================================"
echo "Distributed MapReduce Triangle Counting"
echo "Date: $(date)"
echo "Nodes: ${SLURM_JOB_NODELIST:-local}   Tasks: $NT   srun: $USE_SRUN"
echo "============================================"

for TEST_FILE in "${TEST_FILES[@]}"; do
  INPUT_PATH="$TEST_DATA_DIR/$TEST_FILE"
  [ -f "$INPUT_PATH" ] || { echo "WARNING: $INPUT_PATH not found, skipping."; continue; }

  INPUT_SIZE=$(stat --format=%s "$INPUT_PATH" 2>/dev/null || stat -f%z "$INPUT_PATH")
  read -r V E < "$INPUT_PATH"
  echo "--------------------------------------------"
  echo "Input: $TEST_FILE  ($INPUT_SIZE bytes, V=$V, E=$E)"

  rm -f "$WORK"/*
  TOTAL_START=$(now)

  # Setup: strip header, split edge list into NT line-aligned chunks (the "DFS blocks")
  s=$(now)
  tail -n +2 "$INPUT_PATH" > "$WORK/edges.txt"
  split -d -a 2 -n l/"$NT" "$WORK/edges.txt" "$WORK/j0_out_"
  rm -f "$WORK/edges.txt"
  SPLIT_T=$(secs "$s" "$(now)")

  run_job 1 mapper1.py         ""            reducer1.py j0_out_; J1M=$MAP_T; J1R=$RED_T
  run_job 2 identity_mapper.py ""            reducer2.py j1_out_; J2M=$MAP_T; J2R=$RED_T
  run_job 3 identity_mapper.py ""            reducer3.py j2_out_; J3M=$MAP_T; J3R=$RED_T
  run_job 4 identity_mapper.py combiner4.py  reducer4.py j3_out_; J4M=$MAP_T; J4R=$RED_T

  s=$(now)
  OUTPUT_FILE="$RESULTS_DIR/dist_output_${TEST_FILE}"
  cat "$WORK"/j4_out_* | python3 sum_reducer.py > "$OUTPUT_FILE"
  SUM_T=$(secs "$s" "$(now)")
  TOTAL_T=$(secs "$TOTAL_START" "$(now)")
  TRI=$(cat "$OUTPUT_FILE")

  EXPECTED=$(python3 verify_sequential.py "$INPUT_PATH")
  if [ "$TRI" = "$EXPECTED" ]; then OK=yes; else OK=NO; fi

  echo "  Final sum: ${SUM_T}s"
  echo "  TOTAL: ${TOTAL_T}s   triangles=$TRI   sequential=$EXPECTED   correct=$OK"
  echo "$TEST_FILE,$INPUT_SIZE,$V,$E,$NT,$SPLIT_T,$J1M,$J1R,$J2M,$J2R,$J3M,$J3R,$J4M,$J4R,$SUM_T,$TOTAL_T,$TRI,$EXPECTED,$OK" >> "$SUMMARY_FILE"
done

rm -rf "$WORK"
echo ""
echo "--- CSV Summary ($SUMMARY_FILE) ---"
column -t -s',' "$SUMMARY_FILE" 2>/dev/null || cat "$SUMMARY_FILE"
