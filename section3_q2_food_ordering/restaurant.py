#!/usr/bin/env python3
import shlex
import sys
import threading
import time

import grpc

from common import connect, err, items_str, read_commands, say, status
from proto_gen import pb

HELP = """Options:
  1. View Pending Orders -> pending
  2. Accept Order        -> accept <order_id>
  3. Start Preparing     -> prepare <order_id>
  4. Mark Ready          -> ready <order_id>
  5. Exit                -> exit"""

S = pb.OrderStatus


class RestaurantClient:
    def __init__(self, address, name, watch=True):
        self.channel, self.stub = connect(address)
        names = [r.name for r in self.stub.ListRestaurants(pb.RestaurantRequest()).restaurants]
        match = [n for n in names if n.lower() == name.lower()]
        if not match:
            sys.exit(f"[Error] Unknown restaurant '{name}'. Known: {', '.join(names)}")
        self.name = match[0]
        if watch:
            threading.Thread(target=self._watch, daemon=True).start()

    def _watch(self):
        try:
            for u in self.stub.SubscribeToNewOrders(pb.RestaurantOrdersRequest(restaurant=self.name)):
                o = u.order
                say(f"[New Order] {o.order_id} from {o.customer or 'customer'}: "
                    f"{items_str(o)} (total {o.total})", prompt=True)
        except grpc.RpcError:
            pass

    def list_orders(self, include_completed=False):
        resp = self.stub.ListRestaurantOrders(pb.RestaurantOrdersRequest(
            restaurant=self.name, include_completed=include_completed))
        if not resp.orders:
            say("[Restaurant] No pending orders." if not include_completed else "[Restaurant] No orders.")
        for o in resp.orders:
            say(f"[Restaurant] Order {o.order_id} : {status(o)}   ({items_str(o)}; total {o.total})")

    def update(self, oid, new_status):
        ack = self.stub.UpdateOrderStatus(pb.OrderStatusUpdate(
            order_id=oid, restaurant=self.name, new_status=new_status))
        say(f"[Restaurant] Order {ack.order.order_id} : {status(ack.order)}")

    def loop(self):
        say(f"[Restaurant] Logged in as '{self.name}'.\n{HELP}")
        actions = {"2": "ACCEPTED", "accept": "ACCEPTED", "3": "PREPARING", "prepare": "PREPARING",
                   "4": "READY", "ready": "READY", "reject": "CANCELLED"}
        for line in read_commands():
            if not line:
                continue
            try:
                toks = shlex.split(line)
            except ValueError as e:
                say(f"[Restaurant] Parse error: {e}")
                continue
            cmd, args = toks[0].lower(), toks[1:]
            try:
                if cmd in ("1", "pending"):
                    self.list_orders()
                elif cmd == "all":
                    self.list_orders(include_completed=True)
                elif cmd in actions:
                    oid = args[0] if args else input("Order ID: ").strip()
                    self.update(oid, S.Value(actions[cmd]))
                elif cmd in ("5", "exit", "quit"):
                    break
                elif cmd == "sleep":
                    time.sleep(float(args[0]) if args else 1)
                elif cmd == "help":
                    say(HELP)
                else:
                    say(f"[Restaurant] Unknown command '{cmd}'. Type 'help'.")
            except grpc.RpcError as e:
                say(err(e))
            except (ValueError, IndexError) as e:
                say(f"[Restaurant] Bad input: {e}")
        say("[Restaurant] Bye.")
        self.channel.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        sys.exit('usage: restaurant.py <server_host:port> "<Restaurant Name>" [--no-watch]')
    RestaurantClient(args[0], " ".join(args[1:]), watch="--no-watch" not in sys.argv).loop()
