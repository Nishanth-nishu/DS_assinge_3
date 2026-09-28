#!/bin/bash
# ============================================================
# Optional: the same 4-job pipeline on a real Hadoop cluster (Hadoop Streaming).
#
#   ./run_hadoop.sh <local_graph_file> [num_reducers]
#
# Needs HADOOP_HOME (or `hadoop` on PATH) and HDFS/YARN running.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"
IN=${1:?usage: run_hadoop.sh graph.txt [reducers]}
R=${2:-4}
HD=hdfs_triangles_$$
STREAM_JAR=$(ls "${HADOOP_HOME:-/usr/local/hadoop}"/share/hadoop/tools/lib/hadoop-streaming-*.jar | head -1)

hdfs dfs -mkdir -p "$HD"
tail -n +2 "$IN" | hdfs dfs -put -f - "$HD/edges.txt"

job() {  # name mapper combiner reducer in out
  local comb=() files="$2,$4"
  if [ -n "$3" ]; then comb=(-combiner "python3 $3"); files="$files,$3"; fi
  hadoop jar "$STREAM_JAR" \
    -D mapreduce.job.name="triangles-$1" -D mapreduce.job.reduces="$R" \
    -files "$files" ${comb[@]+"${comb[@]}"} \
    -mapper "python3 $2" -reducer "python3 $4" \
    -input "$5" -output "$6"
}

job 1-degree   mapper1.py         ""           reducer1.py "$HD/edges.txt" "$HD/j1"
job 2-orient   identity_mapper.py ""           reducer2.py "$HD/j1"        "$HD/j2"
job 3-wedges   identity_mapper.py ""           reducer3.py "$HD/j2"        "$HD/j3"
job 4-close    identity_mapper.py combiner4.py reducer4.py "$HD/j3"        "$HD/j4"

hdfs dfs -cat "$HD/j4/part-*" | python3 sum_reducer.py | tee output_hadoop.txt
hdfs dfs -rm -r -f "$HD" >/dev/null
