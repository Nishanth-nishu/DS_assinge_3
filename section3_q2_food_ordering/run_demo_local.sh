#!/bin/bash
# Scripted multi-client demo on ONE machine (4 client processes + server).
# Logs are written to demo/logs/. For the cluster version see run_demo.sbatch.
cd "$(dirname "$0")"
PORT=${1:-50051}
mkdir -p demo/logs
python3 -u server.py 127.0.0.1:$PORT > demo/logs/server.log 2>&1 &
SP=$!; sleep 2
python3 -u restaurant.py 127.0.0.1:$PORT "Pizza House"  < demo/restaurant.txt        > demo/logs/restaurant_pizza.log 2>&1 &
python3 -u restaurant.py 127.0.0.1:$PORT "Burger Point" < demo/restaurant_burger.txt > demo/logs/restaurant_burger.log 2>&1 &
sleep 0.5
python3 -u customer.py 127.0.0.1:$PORT alice < demo/customer1.txt > demo/logs/customer_alice.log 2>&1 &
python3 -u customer.py 127.0.0.1:$PORT bob   < demo/customer2.txt > demo/logs/customer_bob.log 2>&1 &
wait $(jobs -p | grep -v "^$SP$")
kill $SP; wait $SP 2>/dev/null
for f in server restaurant_pizza restaurant_burger customer_alice customer_bob; do
  echo "================= $f ================="; cat demo/logs/$f.log
done
