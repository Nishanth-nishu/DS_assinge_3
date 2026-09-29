import sys
import threading

import grpc

from proto_gen import pb, rpc, STATUS_NAME

_print_lock = threading.Lock()


def say(msg, prompt=False):
    with _print_lock:
        if prompt and sys.stdin.isatty():
            sys.stdout.write("\r" + msg + "\n> ")
        else:
            sys.stdout.write(msg + "\n")
        sys.stdout.flush()


def connect(address, timeout=10):
    channel = grpc.insecure_channel(address)
    try:
        grpc.channel_ready_future(channel).result(timeout=timeout)
    except grpc.FutureTimeoutError:
        sys.exit(f"[Error] Could not connect to server at {address}")
    return channel, rpc.FoodOrderingServiceStub(channel)


def err(e: grpc.RpcError):
    return f"[Error] {e.details()} (gRPC status: {e.code().name})"


def status(o):
    return STATUS_NAME.get(o.status, str(o.status))


def items_str(o):
    return ", ".join(f"{i.name} x{i.quantity}" for i in o.items)


def print_restaurants(resp, who="[Server]"):
    lines = [who]
    for n, r in enumerate(resp.restaurants, 1):
        lines.append(f"{n}. {r.name}")
        w = max(len(i.name) for i in r.items)
        for i in r.items:
            lines.append(f"   - {i.name:<{w}} : {i.price}")
    say("\n".join(lines))


def read_commands(prompt="> "):
    while True:
        try:
            if sys.stdin.isatty():
                line = input(prompt)
            else:
                line = sys.stdin.readline()
                if not line:
                    return
                line = line.rstrip("\n")
                if line.strip():
                    say(f"{prompt}{line}")
        except (EOFError, KeyboardInterrupt):
            return
        yield line.strip()
