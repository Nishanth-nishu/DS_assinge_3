#!/bin/bash
#SBATCH --job-name=grpc_food_demo
#SBATCH --output=food_demo_%j.out
#SBATCH --error=food_demo_%j.err
#SBATCH --nodes=3
#SBATCH --ntasks-per-node=2
#SBATCH --cpus-per-task=1
#SBATCH --time=00:05:00

# ============================================================
# Non-interactive, multi-node demo of the Food Ordering system on RCE.
#   node 1 : gRPC server             (0.0.0.0:$PORT)
#   node 2 : customers alice + bob   (connect to <node1>:$PORT)
#   node 3 : restaurants Pizza House + Burger Point
# Clients replay the command scripts in demo/*.txt. Logs -> demo/logs_<jobid>/
#
#   sbatch run_demo.sbatch            (run ./setup.sh once on the login node first)
# ============================================================
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")}"
PORT=${PORT:-50051}
mapfile -t NODES < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
SERVER=${NODES[0]}; CUST=${NODES[1]}; REST=${NODES[2]}
LOG=demo/logs_${SLURM_JOB_ID}; mkdir -p "$LOG"
echo "Server=$SERVER  Customers=$CUST  Restaurants=$REST  Port=$PORT"

# --overlap lets several job steps share a node (Slurm >= 20.11)
step() { srun --nodes=1 --ntasks=1 --overlap -w "$1" "${@:2}"; }

step "$SERVER" python3 -u server.py "0.0.0.0:$PORT" > "$LOG/server.log" 2>&1 &
SP=$!
sleep 5

step "$REST" python3 -u restaurant.py "$SERVER:$PORT" "Pizza House"  < demo/restaurant.txt        > "$LOG/restaurant_pizza.log" 2>&1 &
step "$REST" python3 -u restaurant.py "$SERVER:$PORT" "Burger Point" < demo/restaurant_burger.txt > "$LOG/restaurant_burger.log" 2>&1 &
sleep 1
step "$CUST" python3 -u customer.py "$SERVER:$PORT" alice < demo/customer1.txt > "$LOG/customer_alice.log" 2>&1 &
step "$CUST" python3 -u customer.py "$SERVER:$PORT" bob   < demo/customer2.txt > "$LOG/customer_bob.log" 2>&1 &

for p in $(jobs -p); do [ "$p" != "$SP" ] && wait "$p"; done
kill "$SP" 2>/dev/null; wait "$SP" 2>/dev/null

for f in server restaurant_pizza restaurant_burger customer_alice customer_bob; do
  echo "================= $f ($LOG/$f.log) ================="; cat "$LOG/$f.log"
done

# Automated correctness + concurrency tests, client on another node than the server
echo "================= test_food_ordering.py ($CUST -> $SERVER:$((PORT+1))) ================="
step "$SERVER" python3 -u server.py "0.0.0.0:$((PORT+1))" --quiet &
TP=$!; sleep 5
step "$CUST" python3 -u test_food_ordering.py "$SERVER:$((PORT+1))" 2>&1 | tee "$LOG/tests.log"
kill "$TP" 2>/dev/null; wait "$TP" 2>/dev/null
