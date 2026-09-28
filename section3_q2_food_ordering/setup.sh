#!/bin/bash
# One-time setup (run on the RCE login node; home is shared with compute nodes).
set -e
cd "$(dirname "$0")"
python3 -m pip install --user --quiet grpcio grpcio-tools
python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. food_ordering.proto
python3 -c "import grpc, food_ordering_pb2, food_ordering_pb2_grpc; print('gRPC', grpc.__version__, '- stubs OK')"
