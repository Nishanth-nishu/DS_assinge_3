#!/bin/bash
# One-time setup. On RCE this is done inside rce_prep.sbatch on a compute node.
set -e
cd "$(dirname "$0")"
python3 -c "import grpc, grpc_tools" 2>/dev/null || {
  python3 -m pip install --user --quiet --upgrade "pip<22"          # py3.6 on RCE
  python3 -m pip install --user --quiet --only-binary=:all: \
      "grpcio==1.48.2" "grpcio-tools==1.48.2" "protobuf<4"
}
python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. food_ordering.proto
python3 -c "import grpc, food_ordering_pb2, food_ordering_pb2_grpc; print('gRPC', grpc.__version__, '- stubs OK')"
