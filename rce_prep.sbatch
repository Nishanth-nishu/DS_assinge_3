#!/bin/bash
#SBATCH --mem-per-cpu=2G
#SBATCH --job-name=hw3_prep
#SBATCH --output=hw3_prep_%j.out
#SBATCH --error=hw3_prep_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:15:00
# Runs on a COMPUTE node: installs gRPC (if missing), generates stubs,
# runs the correctness tests and generates the benchmark datasets.
set -e
ROOT="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "$0")" && pwd)}"
cd "$ROOT"
echo "Node: $(hostname)   $(python3 --version)"

python3 -c "import grpc, grpc_tools" 2>/dev/null \
  || python3 -m pip install --user --quiet grpcio grpcio-tools

echo "== Section 3 P2: generate stubs"
cd "$ROOT/section3_q2_food_ordering"
python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. food_ordering.proto
python3 -c "import grpc, food_ordering_pb2, food_ordering_pb2_grpc; print('gRPC', grpc.__version__, 'stubs OK')"

echo "== Section 1 Q3: correctness tests"
cd "$ROOT/section1_q3_triangle_counting"
./run_tests.sh
echo "== Section 1 Q3: benchmark datasets"
./make_datasets.sh
rm -f perf_results/triangles_dist_summary.csv
