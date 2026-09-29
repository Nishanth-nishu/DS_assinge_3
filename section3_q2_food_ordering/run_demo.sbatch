#!/bin/bash
#SBATCH --partition=debug
#SBATCH --mem-per-cpu=2G
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
# PORT=0 (default): the server binds a free port chosen by the OS and reports it via a
# port file on the shared filesystem. A fixed port (e.g. 50051) can already be taken
# on a shared compute node by another user's server -> bind fails / wrong server answers.
PORT=${PORT:-0}
mapfile -t NODES < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
SERVER=${NODES[0]}; CUST=${NODES[1]}; REST=${NODES[2]}
LOG=demo/logs_${SLURM_JOB_ID}; mkdir -p "$LOG"

# --overlap lets several job steps share a node (Slurm >= 20.11); older Slurm shares by default
OVERLAP=""; srun --help 2>&1 | grep -q -- "--overlap" && OVERLAP="--overlap"
step() { srun --nodes=1 --ntasks=1 $OVERLAP -w "$1" "${@:2}"; }

# start_server <port-file> [server.py args...] : launches on $SERVER, waits for the port file
start_server() {
  local pf=$1; shift; rm -f "$pf"
  step "$SERVER" python3 -u server.py "0.0.0.0:$PORT" --port-file "$pf" "$@" &
  SRV_PID=$!
  for _ in $(seq 60); do [ -s "$pf" ] && { SRV_PORT=$(cat "$pf"); return 0; }
    kill -0 "$SRV_PID" 2>/dev/null || break; sleep 0.5; done
  echo "ERROR: server did not start on $SERVER (see logs)"; return 1
}

start_server "$LOG/server.port" > "$LOG/server.log" 2>&1 || { cat "$LOG/server.log"; exit 1; }
SP=$SRV_PID; P=$SRV_PORT
echo "Server=$SERVER  Customers=$CUST  Restaurants=$REST  Port=$P"
sleep 1

step "$REST" python3 -u restaurant.py "$SERVER:$P" "Pizza House"  < demo/restaurant.txt        > "$LOG/restaurant_pizza.log" 2>&1 &
step "$REST" python3 -u restaurant.py "$SERVER:$P" "Burger Point" < demo/restaurant_burger.txt > "$LOG/restaurant_burger.log" 2>&1 &
sleep 1
step "$CUST" python3 -u customer.py "$SERVER:$P" alice < demo/customer1.txt > "$LOG/customer_alice.log" 2>&1 &
step "$CUST" python3 -u customer.py "$SERVER:$P" bob   < demo/customer2.txt > "$LOG/customer_bob.log" 2>&1 &

for p in $(jobs -p); do [ "$p" != "$SP" ] && wait "$p"; done
kill "$SP" 2>/dev/null; wait "$SP" 2>/dev/null

for f in server restaurant_pizza restaurant_burger customer_alice customer_bob; do
  echo "================= $f ($LOG/$f.log) ================="; cat "$LOG/$f.log"
done

# Automated correctness + concurrency tests, client on another node than the server
start_server "$LOG/test_server.port" --quiet || exit 1
TP=$SRV_PID
echo "================= test_food_ordering.py ($CUST -> $SERVER:$SRV_PORT) ================="
step "$CUST" python3 -u test_food_ordering.py "$SERVER:$SRV_PORT" 2>&1 | tee "$LOG/tests.log"
RC=${PIPESTATUS[0]}
kill "$TP" 2>/dev/null; wait "$TP" 2>/dev/null
exit $RC
