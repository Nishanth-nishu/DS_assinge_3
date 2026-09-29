#!/usr/bin/env python3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import grpc

from proto_gen import pb, rpc

S = pb.OrderStatus
results = []


def check(name, cond, info=""):
    results.append(cond)
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  [{info}]" if info else ""))


def expect_code(name, fn, code):
    try:
        fn()
        check(name, False, "no error raised")
    except grpc.RpcError as e:
        check(name, e.code() == code, f"{e.code().name}: {e.details()}")


def place(stub, rest="Pizza House", items=(("Margherita Pizza", 1), ("Garlic Bread", 2)), cust="alice"):
    return stub.PlaceOrder(pb.OrderRequest(restaurant=rest, customer=cust,
                                           items=[pb.OrderItem(name=n, quantity=q) for n, q in items])).order


def upd(stub, oid, st, rest="Pizza House"):
    return stub.UpdateOrderStatus(pb.OrderStatusUpdate(order_id=oid, restaurant=rest,
                                                       new_status=S.Value(st)))


def main():
    server = None
    if len(sys.argv) > 1:
        addr = sys.argv[1]
    else:
        import server as srv
        server, port = srv.serve("127.0.0.1:0", verbose=False, block=False)
        addr = f"127.0.0.1:{port}"
    ch = grpc.insecure_channel(addr)
    grpc.channel_ready_future(ch).result(timeout=10)
    stub = rpc.FoodOrderingServiceStub(ch)

    rs = stub.ListRestaurants(pb.RestaurantRequest()).restaurants
    names = [r.name for r in rs]
    check("ListRestaurants returns predefined restaurants",
          "Pizza House" in names and "Burger Point" in names, ", ".join(names))

    o = place(stub)
    check("PlaceOrder assigns id, total, PLACED",
          o.order_id.startswith("O") and o.total == 550 and o.status == S.Value("PLACED"),
          f"{o.order_id} total={o.total}")
    check("GetOrderStatus", stub.GetOrderStatus(pb.OrderStatusRequest(order_id=o.order_id)).order.status
          == S.Value("PLACED"))

    got = []
    ready = threading.Event()

    def sub():
        for u in stub.SubscribeToOrderUpdates(pb.OrderRequest(order_id=o.order_id)):
            got.append(pb.OrderStatus.Name(u.order.status))
            ready.set()
    t = threading.Thread(target=sub)
    t.start()
    ready.wait(5)
    for st in ("ACCEPTED", "PREPARING", "READY"):
        upd(stub, o.order_id, st)
    t.join(5)
    check("Subscriber receives PLACED->ACCEPTED->PREPARING->READY and stream closes",
          got == ["PLACED", "ACCEPTED", "PREPARING", "READY"] and not t.is_alive(), " -> ".join(got))

    expect_code("Order from non-existent restaurant -> NOT_FOUND",
                lambda: place(stub, rest="Taco Town"), grpc.StatusCode.NOT_FOUND)
    expect_code("Order unavailable food item -> NOT_FOUND",
                lambda: place(stub, items=(("Sushi", 1),)), grpc.StatusCode.NOT_FOUND)
    expect_code("Zero quantity -> INVALID_ARGUMENT",
                lambda: place(stub, items=(("Garlic Bread", 0),)), grpc.StatusCode.INVALID_ARGUMENT)
    expect_code("Access non-existent order -> NOT_FOUND",
                lambda: stub.GetOrderStatus(pb.OrderStatusRequest(order_id="O99999")),
                grpc.StatusCode.NOT_FOUND)
    o2 = place(stub)
    upd(stub, o2.order_id, "ACCEPTED")
    expect_code("Cancel an already ACCEPTED order -> FAILED_PRECONDITION",
                lambda: stub.CancelOrder(pb.CancelRequest(order_id=o2.order_id, customer="alice")),
                grpc.StatusCode.FAILED_PRECONDITION)
    expect_code("Restaurant updates another restaurant's order -> PERMISSION_DENIED",
                lambda: upd(stub, o2.order_id, "PREPARING", rest="Burger Point"),
                grpc.StatusCode.PERMISSION_DENIED)
    expect_code("Invalid transition ACCEPTED->READY -> FAILED_PRECONDITION",
                lambda: upd(stub, o2.order_id, "READY"), grpc.StatusCode.FAILED_PRECONDITION)
    upd(stub, o2.order_id, "PREPARING")
    upd(stub, o2.order_id, "READY")
    expect_code("Invalid transition READY->PREPARING -> FAILED_PRECONDITION",
                lambda: upd(stub, o2.order_id, "PREPARING"), grpc.StatusCode.FAILED_PRECONDITION)
    o3 = place(stub, cust="bob")
    expect_code("Cancel someone else's order -> PERMISSION_DENIED",
                lambda: stub.CancelOrder(pb.CancelRequest(order_id=o3.order_id, customer="mallory")),
                grpc.StatusCode.PERMISSION_DENIED)
    ack = stub.CancelOrder(pb.CancelRequest(order_id=o3.order_id, customer="bob"))
    check("Customer cancels PLACED order", ack.order.status == S.Value("CANCELLED"))

    with ThreadPoolExecutor(32) as ex:
        ids = list(ex.map(lambda i: place(stub, cust=f"c{i}").order_id, range(200)))
    check("200 concurrent PlaceOrder calls get unique order IDs", len(set(ids)) == 200)

    o4 = place(stub)
    wins, fails = [], []
    barrier = threading.Barrier(20)

    def race():
        barrier.wait()
        try:
            upd(stub, o4.order_id, "ACCEPTED")
            wins.append(1)
        except grpc.RpcError as e:
            fails.append(e.code())
    ts = [threading.Thread(target=race) for _ in range(20)]
    [x.start() for x in ts]
    [x.join() for x in ts]
    check("20 racing ACCEPT calls on one order: exactly 1 wins",
          len(wins) == 1 and all(c == grpc.StatusCode.FAILED_PRECONDITION for c in fails),
          f"wins={len(wins)} failed_precondition={len(fails)}")

    ok = 0
    for _ in range(20):
        o5 = place(stub)
        res = []
        b = threading.Barrier(2)

        def a():
            b.wait()
            try:
                upd(stub, o5.order_id, "ACCEPTED"); res.append("A")
            except grpc.RpcError:
                pass

        def c():
            b.wait()
            try:
                stub.CancelOrder(pb.CancelRequest(order_id=o5.order_id, customer="alice")); res.append("C")
            except grpc.RpcError:
                pass
        x, y = threading.Thread(target=a), threading.Thread(target=c)
        x.start(); y.start(); x.join(); y.join()
        final = pb.OrderStatus.Name(stub.GetOrderStatus(pb.OrderStatusRequest(order_id=o5.order_id)).order.status)
        ok += len(res) == 1 and final == {"A": "ACCEPTED", "C": "CANCELLED"}[res[0]]
    check("Cancel-vs-accept race (20 trials): exactly one wins, state consistent", ok == 20, f"{ok}/20")

    o6 = place(stub)
    seen = [[] for _ in range(5)]
    started = threading.Barrier(6)

    def s(i):
        it = stub.SubscribeToOrderUpdates(pb.OrderRequest(order_id=o6.order_id))
        first = True
        for u in it:
            seen[i].append(pb.OrderStatus.Name(u.order.status))
            if first:
                first = False
                started.wait()
    subs = [threading.Thread(target=s, args=(i,)) for i in range(5)]
    [x.start() for x in subs]
    started.wait(5)
    for st in ("ACCEPTED", "PREPARING", "READY"):
        upd(stub, o6.order_id, st)
    [x.join(5) for x in subs]
    check("5 concurrent subscribers each receive all 4 states",
          all(v == ["PLACED", "ACCEPTED", "PREPARING", "READY"] for v in seen))

    pushed = []
    ev = threading.Event()

    def w():
        for u in stub.SubscribeToNewOrders(pb.RestaurantOrdersRequest(restaurant="Burger Point")):
            pushed.append(u.order.order_id)
            ev.set()
            return
    wt = threading.Thread(target=w, daemon=True)
    wt.start()
    time.sleep(0.3)
    o7 = place(stub, rest="Burger Point", items=(("Veg Burger", 2),))
    ev.wait(5)
    check("Restaurant is pushed new orders (SubscribeToNewOrders)", pushed == [o7.order_id])
    pend = stub.ListRestaurantOrders(pb.RestaurantOrdersRequest(restaurant="Burger Point")).orders
    check("ListRestaurantOrders shows only this restaurant's active orders",
          [x.order_id for x in pend] == [o7.order_id])

    ch.close()
    if server:
        server.stop(0)
    print("----")
    print(f"passed={sum(results)} failed={len(results) - sum(results)}")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
