import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.join(HERE, "food_ordering.proto")
OUT = os.path.join(HERE, "food_ordering_pb2.py")
OUT_GRPC = os.path.join(HERE, "food_ordering_pb2_grpc.py")


def ensure():
    stale = (not os.path.exists(OUT) or not os.path.exists(OUT_GRPC)
             or os.path.getmtime(OUT) < os.path.getmtime(PROTO))
    if stale:
        try:
            from grpc_tools import protoc
        except ImportError:
            sys.exit("grpcio-tools missing: pip install --user grpcio grpcio-tools")
        rc = protoc.main(["grpc_tools.protoc", f"-I{HERE}", f"--python_out={HERE}",
                          f"--grpc_python_out={HERE}", PROTO])
        if rc != 0:
            sys.exit("protoc failed")
    if HERE not in sys.path:
        sys.path.insert(0, HERE)


ensure()
import food_ordering_pb2 as pb
import food_ordering_pb2_grpc as rpc

STATUS_NAME = {v: k for k, v in pb.OrderStatus.items()}
