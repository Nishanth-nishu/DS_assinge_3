# Section 3 – Problem 2: Food Ordering System using gRPC

A simplified Swiggy-style system: one **Food Ordering Server**, many **Customer**
clients and many **Restaurant** clients, all talking gRPC (Python, `grpcio`).

```
                 +---------------------------+
                 |  server.py  (node 1)      |
                 |  FoodOrderingService      |
                 |  orders + subscribers     |
                 |  (in memory, 1 lock)      |
                 +------------+--------------+
            unary + server-streaming RPCs over the cluster network
        +-------------+--------------+----------------+
        v             v              v                v
  customer.py    customer.py   restaurant.py    restaurant.py
  (alice,node 2) (bob, node 2) (Pizza House,n3) (Burger Point,n3)
```

## Files

| File | Purpose |
|---|---|
| `food_ordering.proto` | `FoodOrderingService` + all messages |
| `server.py` | restaurants/menus, order management, validation, concurrency, streaming |
| `customer.py` | customer CLI |
| `restaurant.py` | restaurant CLI |
| `common.py`, `proto_gen.py` | shared client helpers; auto-generates the `_pb2` stubs from the `.proto` |
| `setup.sh` | one-time install of `grpcio`/`grpcio-tools` + stub generation |
| `test_food_ordering.py` | 20 automated correctness / concurrency tests |
| `run_demo_local.sh` | scripted demo with 4 concurrent clients on one machine |
| `run_demo.sbatch` | the same demo across 3 RCE nodes via SLURM |
| `demo/*.txt`, `demo/sample_logs_local/` | client command scripts and the logs of a demo run |

## gRPC interface

| RPC | Type | Notes |
|---|---|---|
| `ListRestaurants(RestaurantRequest) → RestaurantResponse` | unary | predefined restaurants + menus |
| `PlaceOrder(OrderRequest) → OrderResponse` | unary | validates restaurant/items/qty, assigns `O101, O102, …`, status `PLACED` |
| `GetOrderStatus(OrderStatusRequest) → OrderStatusResponse` | unary | |
| `UpdateOrderStatus(OrderStatusUpdate) → Acknowledge` | unary | restaurant identity is checked against the order owner |
| `SubscribeToOrderUpdates(OrderRequest) → stream OrderUpdate` | server-streaming | first message = current status; closes after `READY`/`CANCELLED` |
| `CancelOrder(CancelRequest) → Acknowledge` | unary (extra) | customer "Cancel Order"; only from `PLACED` |
| `ListRestaurantOrders(RestaurantOrdersRequest) → RestaurantOrdersResponse` | unary (extra) | restaurant "View Pending Orders" |
| `SubscribeToNewOrders(RestaurantOrdersRequest) → stream OrderUpdate` | server-streaming (extra) | pushes new orders to the restaurant CLI |

`OrderRequest` is used both to place an order (restaurant + items) and to subscribe
(order_id), exactly as the assignment's API signatures require.

### State machine

```
PLACED -> ACCEPTED -> PREPARING -> READY
PLACED -> CANCELLED            (customer cancels, or restaurant rejects)
```
Anything else (e.g. `READY -> PREPARING`, `ACCEPTED -> READY`) is rejected.

### Error handling (gRPC status codes)

| Situation | Status |
|---|---|
| Order from a non-existent restaurant | `NOT_FOUND` |
| Order an unavailable food item | `NOT_FOUND` |
| Empty order / quantity ≤ 0 | `INVALID_ARGUMENT` |
| Access a non-existent order | `NOT_FOUND` |
| Cancel an order that is already accepted / preparing / ready | `FAILED_PRECONDITION` |
| Restaurant updates another restaurant's order | `PERMISSION_DENIED` |
| Customer cancels someone else's order | `PERMISSION_DENIED` |
| Invalid status transition | `FAILED_PRECONDITION` |

The server raises these with `context.abort(code, message)`; clients print
`[Error] <message> (gRPC status: <CODE>)`.

## Concurrency design

* `grpc.server(ThreadPoolExecutor(64))` – RPCs from many clients run in parallel.
* One `threading.Lock` protects all mutable state (order table, id counter, subscriber
  lists). Each **check-then-act** (id generation; "is this transition valid?" + apply it
  + notify subscribers) is a single critical section, so racing requests are
  serialised: when 20 restaurant threads accept the same order at once exactly one
  succeeds and 19 get `FAILED_PRECONDITION`; accept-vs-cancel races always leave a
  consistent state.
* Streams never block while holding the lock. Every subscriber owns a thread-safe
  `queue.Queue`; writers push a **snapshot** (copy) of the order into each queue inside
  the critical section (so updates arrive in the order they were applied), and the
  streaming handler drains its queue outside the lock. A slow subscriber cannot stall
  writers. Disconnected subscribers are removed in a `finally` block
  (`context.is_active()` is polled every second).
* Menus are read-only, so no locking is needed for them.
* Clients run the tracking / new-order streams in **background threads**, so the CLI
  stays usable while updates arrive.

## Setup & running

Requires Python ≥ 3.8.
```bash
./setup.sh           # pip install --user grpcio grpcio-tools ; generate stubs
```
(The stubs are also generated automatically on first run by `proto_gen.py`.)

### Local (one machine, several terminals)
```bash
python3 server.py localhost:50051
python3 restaurant.py localhost:50051 "Pizza House"
python3 customer.py   localhost:50051 alice
python3 customer.py   localhost:50051 bob
```

### RCE cluster – interactive (as in the RCE execution guide)
```bash
ssh cs3401.58@rce.iiit.ac.in                  # IIIT network / VPN
git clone https://github.com/Nishanth-nishu/DS_assinge_3.git
cd DS_assinge_3/section3_q2_food_ordering && ./setup.sh
salloc -A default --qos=normal --nodes=3 --ntasks-per-node=1
scontrol show hostnames $SLURM_JOB_NODELIST   # e.g. node01 node02 node03

# terminal 1
ssh node01 ; cd ~/DS_assinge_3/section3_q2_food_ordering ; python3 server.py 0.0.0.0:50051
# terminal 2
ssh node02 ; cd ~/DS_assinge_3/section3_q2_food_ordering ; python3 customer.py node01:50051 alice
# terminal 3
ssh node03 ; cd ~/DS_assinge_3/section3_q2_food_ordering ; python3 restaurant.py node01:50051 "Pizza House"
```
Use `0.0.0.0:PORT` for the server and `<server-node>:PORT` for clients (not
`localhost`). Pick another port if 50051 is taken.

### RCE cluster – batch demo
```bash
sbatch run_demo.sbatch        # server on node 1, 2 customers on node 2, 2 restaurants on node 3
cat food_demo_<jobid>.out     # all five logs, also in demo/logs_<jobid>/
```

### Tests
```bash
python3 test_food_ordering.py                 # starts its own server
python3 test_food_ordering.py node01:50051    # or test a running server
```

## CLI reference

Customer (`customer.py <server> [name]`) – type the number or the command:
```
1 restaurants
2 order <Restaurant> "<Item>" <qty> ["<Item>" <qty> ...]    (or just 2 for prompts)
3 status <order_id>
4 track  <order_id>        live updates in the background
5 cancel <order_id>
6 exit
```
Restaurant (`restaurant.py <server> "<Restaurant>"`):
```
1 pending    2 accept <id>    3 prepare <id>    4 ready <id>    5 exit
all (every order)   reject <id> (PLACED -> CANCELLED)
```
Both CLIs also accept `sleep <sec>` and read commands from a pipe, which is how the
scripted demos work.

## Demonstration (actual output – `demo/sample_logs_local/`)

Four clients run concurrently against one server (Pizza House, Burger Point, alice, bob).

**1. Listing restaurants** (alice)
```
> restaurants
[Server]
1. Pizza House
   - Margherita Pizza : 250
   - Farmhouse Pizza  : 350
   - Garlic Bread     : 150
2. Burger Point
   - Veg Burger    : 180
   - Cheese Burger : 220
   - French Fries  : 120
3. Dosa Corner ...
```
**2. Placing an order and tracking it** (alice)
```
> order Pizza House "Margherita Pizza" 1 "Garlic Bread" 2
[Client] Order placed successfully.
[Client] Order ID: O101
[Client] Items: Margherita Pizza x1, Garlic Bread x2
[Client] Total: 550
[Client] Status: PLACED
> track O101
[Client] Tracking order O101...
[Update] Order O101 : PLACED
[Update] Order O101 : ACCEPTED
[Update] Order O101 : PREPARING
[Update] Order O101 : READY
[Client] Order O101 finished; tracking stopped.
```
**3. Restaurant processing the order** (Pizza House) – the new order is pushed to it
```
[New Order] O101 from alice: Margherita Pizza x1, Garlic Bread x2 (total 550)
> pending
[Restaurant] Order O101 : PLACED   (Margherita Pizza x1, Garlic Bread x2; total 550)
> accept O101
[Restaurant] Order O101 : ACCEPTED
> prepare O101
[Restaurant] Order O101 : PREPARING
> ready O101
[Restaurant] Order O101 : READY
```
**4. Exceptional cases (gRPC status codes)**
```
(Pizza House)  > prepare O101
[Error] Invalid order state transition: READY -> PREPARING. (gRPC status: FAILED_PRECONDITION)
(Pizza House)  > accept O102
[Error] Order O102 belongs to Burger Point, not 'Pizza House'. (gRPC status: PERMISSION_DENIED)
(Burger Point) > accept O101
[Error] Order O101 belongs to Pizza House, not 'Burger Point'. (gRPC status: PERMISSION_DENIED)
(bob)          > order Taco Town "Tacos" 1
[Error] Restaurant 'Taco Town' does not exist. (gRPC status: NOT_FOUND)
(bob)          > order Pizza House "Sushi" 1
[Error] Item 'Sushi' is not available at Pizza House. (gRPC status: NOT_FOUND)
(bob)          > status O999
[Error] Order O999 does not exist. (gRPC status: NOT_FOUND)
(alice)        > cancel O101
[Error] Order O101 cannot be cancelled: it is already READY. (gRPC status: FAILED_PRECONDITION)
```
**5. Cancel from PLACED** (bob)
```
> order Burger Point "Cheese Burger" 1 "French Fries" 2
[Client] Order ID: O102  ...  Total: 460
> cancel O102
[Client] Order O102 : CANCELLED
```

## Correctness verification (`test_food_ordering.py`, 20/20 pass)

Listing; order id/total/status; full lifecycle over a stream (stream closes after
`READY`); all exception cases with the expected status codes; **200 concurrent
`PlaceOrder` calls → 200 unique ids**; **20 threads racing to accept one order → exactly
1 winner**; **accept-vs-cancel race × 20 → exactly one wins, final state consistent**;
**5 concurrent subscribers each receive every update in order**; new-order push to the
restaurant; restaurant sees only its own active orders.
