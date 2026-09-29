#!/usr/bin/env python3
import argparse
import os
import queue
import threading
import time
from concurrent import futures

import grpc

from proto_gen import pb, rpc, STATUS_NAME

RESTAURANTS = {
    "Pizza House": {"Margherita Pizza": 250, "Farmhouse Pizza": 350, "Garlic Bread": 150},
    "Burger Point": {"Veg Burger": 180, "Cheese Burger": 220, "French Fries": 120},
    "Dosa Corner": {"Masala Dosa": 90, "Idli Vada": 70, "Filter Coffee": 40},
}

S = pb.OrderStatus
RESTAURANT_TRANSITIONS = {
    (S.Value("PLACED"), S.Value("ACCEPTED")),
    (S.Value("ACCEPTED"), S.Value("PREPARING")),
    (S.Value("PREPARING"), S.Value("READY")),
    (S.Value("PLACED"), S.Value("CANCELLED")),
}
TERMINAL = {S.Value("READY"), S.Value("CANCELLED")}
ACTIVE = {S.Value("PLACED"), S.Value("ACCEPTED"), S.Value("PREPARING")}


def now_ms():
    return int(time.time() * 1000)


def _canon(name, choices):
    key = " ".join(name.split()).lower()
    for c in choices:
        if c.lower() == key:
            return c
    return None


class FoodOrderingServicer(rpc.FoodOrderingServiceServicer):
    def __init__(self, verbose=True):
        self._lock = threading.Lock()
        self._orders = {}
        self._next_id = 101
        self._order_subs = {}
        self._new_order_subs = {}
        self._verbose = verbose

    def _log(self, msg):
        if self._verbose:
            print(f"[Server] {msg}", flush=True)

    def _snapshot(self, order):
        o = pb.Order()
        o.CopyFrom(order)
        return o

    def _get_order_locked(self, order_id, context):
        order = self._orders.get(order_id.strip().upper())
        if order is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Order {order_id} does not exist.")
        return order

    def _publish_locked(self, order, message):
        upd = pb.OrderUpdate(order=self._snapshot(order), message=message)
        for q in self._order_subs.get(order.order_id, []):
            q.put(upd)

    def ListRestaurants(self, request, context):
        resp = pb.RestaurantResponse()
        for name, menu in RESTAURANTS.items():
            r = resp.restaurants.add(name=name)
            for item, price in menu.items():
                r.items.add(name=item, price=price)
        return resp

    def PlaceOrder(self, request, context):
        rname = _canon(request.restaurant, RESTAURANTS)
        if rname is None:
            context.abort(grpc.StatusCode.NOT_FOUND,
                          f"Restaurant '{request.restaurant}' does not exist.")
        if not request.items:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Order must contain at least one item.")
        menu = RESTAURANTS[rname]
        items, total = [], 0
        for it in request.items:
            iname = _canon(it.name, menu)
            if iname is None:
                context.abort(grpc.StatusCode.NOT_FOUND,
                              f"Item '{it.name}' is not available at {rname}.")
            if it.quantity <= 0:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                              f"Quantity for '{iname}' must be positive.")
            items.append(pb.OrderItem(name=iname, quantity=it.quantity))
            total += menu[iname] * it.quantity

        with self._lock:
            oid = f"O{self._next_id}"
            self._next_id += 1
            t = now_ms()
            order = pb.Order(order_id=oid, restaurant=rname, customer=request.customer,
                             items=items, total=total, status=S.Value("PLACED"),
                             created_ms=t, updated_ms=t)
            self._orders[oid] = order
            snap = self._snapshot(order)
            for q in self._new_order_subs.get(rname, []):
                q.put(pb.OrderUpdate(order=snap, message="New order"))
        self._log(f"Order {oid} PLACED at {rname} by {request.customer or 'anonymous'} (total {total})")
        return pb.OrderResponse(order=snap)

    def GetOrderStatus(self, request, context):
        with self._lock:
            order = self._get_order_locked(request.order_id, context)
            return pb.OrderStatusResponse(order=self._snapshot(order))

    def UpdateOrderStatus(self, request, context):
        with self._lock:
            order = self._get_order_locked(request.order_id, context)
            caller = _canon(request.restaurant, RESTAURANTS)
            if caller != order.restaurant:
                context.abort(grpc.StatusCode.PERMISSION_DENIED,
                              f"Order {order.order_id} belongs to {order.restaurant}, "
                              f"not '{request.restaurant}'.")
            old, new = order.status, request.new_status
            if (old, new) not in RESTAURANT_TRANSITIONS:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION,
                              f"Invalid order state transition: {STATUS_NAME[old]} -> "
                              f"{STATUS_NAME.get(new, new)}.")
            order.status = new
            order.updated_ms = now_ms()
            self._publish_locked(order, f"Status changed by {caller}")
            snap = self._snapshot(order)
        self._log(f"Order {snap.order_id}: {STATUS_NAME[old]} -> {STATUS_NAME[new]} ({caller})")
        return pb.Acknowledge(success=True, message=f"Order {snap.order_id} : {STATUS_NAME[new]}",
                              order=snap)

    def CancelOrder(self, request, context):
        with self._lock:
            order = self._get_order_locked(request.order_id, context)
            if order.customer and request.customer and order.customer != request.customer:
                context.abort(grpc.StatusCode.PERMISSION_DENIED,
                              f"Order {order.order_id} was not placed by '{request.customer}'.")
            if order.status != S.Value("PLACED"):
                context.abort(grpc.StatusCode.FAILED_PRECONDITION,
                              f"Order {order.order_id} cannot be cancelled: it is already "
                              f"{STATUS_NAME[order.status]}.")
            order.status = S.Value("CANCELLED")
            order.updated_ms = now_ms()
            self._publish_locked(order, "Cancelled by customer")
            snap = self._snapshot(order)
        self._log(f"Order {snap.order_id}: PLACED -> CANCELLED (customer)")
        return pb.Acknowledge(success=True, message=f"Order {snap.order_id} : CANCELLED", order=snap)

    def ListRestaurantOrders(self, request, context):
        rname = _canon(request.restaurant, RESTAURANTS)
        if rname is None:
            context.abort(grpc.StatusCode.NOT_FOUND,
                          f"Restaurant '{request.restaurant}' does not exist.")
        with self._lock:
            orders = [self._snapshot(o) for o in self._orders.values()
                      if o.restaurant == rname and (request.include_completed or o.status in ACTIVE)]
        orders.sort(key=lambda o: int(o.order_id[1:]))
        return pb.RestaurantOrdersResponse(orders=orders)

    def SubscribeToOrderUpdates(self, request, context):
        q = queue.Queue()
        with self._lock:
            order = self._get_order_locked(request.order_id, context)
            oid = order.order_id
            self._order_subs.setdefault(oid, []).append(q)
            first = pb.OrderUpdate(order=self._snapshot(order), message="Current status")
        self._log(f"Subscriber attached to {oid}")
        try:
            yield first
            if first.order.status in TERMINAL:
                return
            while context.is_active():
                try:
                    upd = q.get(timeout=1.0)
                except queue.Empty:
                    continue
                yield upd
                if upd.order.status in TERMINAL:
                    return
        finally:
            with self._lock:
                subs = self._order_subs.get(oid, [])
                if q in subs:
                    subs.remove(q)
            self._log(f"Subscriber detached from {oid}")

    def SubscribeToNewOrders(self, request, context):
        rname = _canon(request.restaurant, RESTAURANTS)
        if rname is None:
            context.abort(grpc.StatusCode.NOT_FOUND,
                          f"Restaurant '{request.restaurant}' does not exist.")
        q = queue.Queue()
        with self._lock:
            self._new_order_subs.setdefault(rname, []).append(q)
        try:
            while context.is_active():
                try:
                    yield q.get(timeout=1.0)
                except queue.Empty:
                    continue
        finally:
            with self._lock:
                subs = self._new_order_subs.get(rname, [])
                if q in subs:
                    subs.remove(q)


def serve(address, max_workers=64, verbose=True, block=True, port_file=None):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    servicer = FoodOrderingServicer(verbose=verbose)
    rpc.add_FoodOrderingServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port(address)
    if port == 0:
        raise SystemExit(f"Could not bind to {address}")
    server.start()
    if address.rsplit(":", 1)[-1] == "0":
        address = f"{address.rsplit(':', 1)[0]}:{port}"
    if port_file:
        with open(port_file + ".tmp", "w") as f:
            f.write(f"{port}\n")
        os.replace(port_file + ".tmp", port_file)
    if verbose:
        print(f"[Server] Food Ordering Server listening on {address} "
              f"(thread pool = {max_workers})", flush=True)
        for r, menu in RESTAURANTS.items():
            print(f"[Server]   {r}: " + ", ".join(f"{i} ({p})" for i, p in menu.items()), flush=True)
    if not block:
        return server, port
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...", flush=True)
        server.stop(grace=2).wait()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="gRPC Food Ordering Server")
    ap.add_argument("address", nargs="?", default="0.0.0.0:50051",
                    help="host:port to listen on (use 0.0.0.0:PORT on the cluster)")
    ap.add_argument("--max-workers", type=int, default=64,
                    help="thread-pool size (each open stream holds one thread)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--port-file", help="write the bound port here (use with port 0)")
    a = ap.parse_args()
    serve(a.address, a.max_workers, verbose=not a.quiet, port_file=a.port_file)
