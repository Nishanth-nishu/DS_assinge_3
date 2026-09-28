#!/usr/bin/env python3
"""
Customer client (CLI).

    python3 customer.py <server_host:port> [customer_name]

Menu options (type the number or the command):
  1  restaurants                                  List Restaurants
  2  order <Restaurant> "<Item>" <qty> ...        Place Order
  3  status <order_id>                            Check Order Status
  4  track <order_id>                             Track Order (live stream)
  5  cancel <order_id>                            Cancel Order
  6  exit                                         Exit
     sleep <sec>, help

`track` runs the server-streaming RPC in a background thread, so the customer
keeps using the CLI while updates arrive.
"""
import shlex
import sys
import threading
import time

import grpc

from common import connect, err, items_str, print_restaurants, read_commands, say, status
from proto_gen import pb

HELP = """Options:
  1. List Restaurants   -> restaurants
  2. Place Order        -> order <Restaurant> "<Item>" <qty> ["<Item>" <qty> ...]
  3. Check Order Status -> status <order_id>
  4. Track Order        -> track <order_id>
  5. Cancel Order       -> cancel <order_id>
  6. Exit               -> exit"""


class Customer:
    def __init__(self, address, name):
        self.name = name
        self.channel, self.stub = connect(address)
        self.tracking = {}
        self._restaurants = None

    # ---------------------------------------------------------------------
    def restaurants(self):
        resp = self.stub.ListRestaurants(pb.RestaurantRequest())
        self._restaurants = [r.name for r in resp.restaurants]
        print_restaurants(resp)

    def _split_order_args(self, toks):
        """Split `Pizza House "Margherita Pizza" 1 "Garlic Bread" 2` into
        restaurant + (item, qty) pairs; restaurant may be unquoted."""
        if self._restaurants is None:
            self._restaurants = [r.name for r in self.stub.ListRestaurants(pb.RestaurantRequest()).restaurants]
        known = {r.lower() for r in self._restaurants}
        candidates = []
        for r in range(1, len(toks) - 1):
            rest = toks[r:]
            if len(rest) % 2 or not all(q.lstrip("-").isdigit() for q in rest[1::2]):
                continue
            candidates.append(r)
        if not candidates:
            return None, None
        pick = next((r for r in candidates if " ".join(toks[:r]).lower() in known), candidates[0])
        rest = toks[pick:]
        return " ".join(toks[:pick]), [(rest[i], int(rest[i + 1])) for i in range(0, len(rest), 2)]

    def order(self, toks):
        if not toks:  # interactive mode
            rname = input("Restaurant: ").strip()
            items = []
            while True:
                it = input("Item (blank to finish): ").strip()
                if not it:
                    break
                items.append((it, int(input("Quantity: ").strip() or "1")))
        else:
            rname, items = self._split_order_args(toks)
            if rname is None:
                say('[Client] Usage: order <Restaurant> "<Item>" <qty> ["<Item>" <qty> ...]')
                return
        req = pb.OrderRequest(restaurant=rname, customer=self.name,
                              items=[pb.OrderItem(name=n, quantity=q) for n, q in items])
        o = self.stub.PlaceOrder(req).order
        say(f"[Client] Order placed successfully.\n[Client] Order ID: {o.order_id}\n"
            f"[Client] Items: {items_str(o)}\n[Client] Total: {o.total}\n[Client] Status: {status(o)}")

    def status(self, oid):
        o = self.stub.GetOrderStatus(pb.OrderStatusRequest(order_id=oid)).order
        say(f"[Client] Order {o.order_id} ({o.restaurant}: {items_str(o)}) : {status(o)}")

    def track(self, oid):
        oid = oid.upper()
        if oid in self.tracking and self.tracking[oid].is_alive():
            say(f"[Client] Already tracking {oid}.")
            return
        # Validate synchronously so NOT_FOUND is reported immediately.
        self.stub.GetOrderStatus(pb.OrderStatusRequest(order_id=oid))
        say(f"[Client] Tracking order {oid}...")

        def run():
            try:
                for u in self.stub.SubscribeToOrderUpdates(pb.OrderRequest(order_id=oid)):
                    say(f"[Update] Order {u.order.order_id} : {status(u.order)}", prompt=True)
                say(f"[Client] Order {oid} finished; tracking stopped.", prompt=True)
            except grpc.RpcError as e:
                if e.code() != grpc.StatusCode.CANCELLED:
                    say(err(e), prompt=True)

        t = threading.Thread(target=run, daemon=True)
        self.tracking[oid] = t
        t.start()

    def cancel(self, oid):
        ack = self.stub.CancelOrder(pb.CancelRequest(order_id=oid, customer=self.name))
        say(f"[Client] {ack.message}")

    # ---------------------------------------------------------------------
    def loop(self):
        say(f"[Client] Connected as customer '{self.name}'.\n{HELP}")
        for line in read_commands():
            if not line:
                continue
            try:
                toks = shlex.split(line)
            except ValueError as e:
                say(f"[Client] Parse error: {e}")
                continue
            cmd, args = toks[0].lower(), toks[1:]
            try:
                if cmd in ("1", "restaurants", "list"):
                    self.restaurants()
                elif cmd in ("2", "order"):
                    self.order(args)
                elif cmd in ("3", "status"):
                    self.status(args[0] if args else input("Order ID: ").strip())
                elif cmd in ("4", "track"):
                    self.track(args[0] if args else input("Order ID: ").strip())
                elif cmd in ("5", "cancel"):
                    self.cancel(args[0] if args else input("Order ID: ").strip())
                elif cmd in ("6", "exit", "quit"):
                    break
                elif cmd == "sleep":
                    time.sleep(float(args[0]) if args else 1)
                elif cmd == "help":
                    say(HELP)
                else:
                    say(f"[Client] Unknown command '{cmd}'. Type 'help'.")
            except grpc.RpcError as e:
                say(err(e))
            except (ValueError, IndexError) as e:
                say(f"[Client] Bad input: {e}")
        say("[Client] Bye.")
        self.channel.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: customer.py <server_host:port> [customer_name]")
    Customer(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "customer").loop()
