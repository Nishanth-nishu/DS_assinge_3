#!/bin/bash
#SBATCH --partition=debug
#SBATCH --mem-per-cpu=4G
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
echo "Node: $(hostname)   $(python3 --version)   repo: $(git rev-parse --short HEAD 2>/dev/null)"

# RCE compute nodes run Python 3.6.8 with an old pip that cannot use manylinux2014
# wheels and falls back to compiling grpcio from source (runs out of memory).
# -> upgrade pip (21.3.1 is the last for py3.6) and install prebuilt wheels only:
#    grpcio / grpcio-tools 1.48.2 are the last releases with cp36 wheels.
python3 -c "import grpc, grpc_tools" 2>/dev/null || {
  echo "== installing gRPC wheels (py3.6)"
  python3 -m pip install --user --quiet --upgrade "pip<22"
  python3 -m pip --version
  python3 -m pip install --user --quiet --only-binary=:all: \
      "grpcio==1.48.2" "grpcio-tools==1.48.2" "protobuf<4"
}

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
