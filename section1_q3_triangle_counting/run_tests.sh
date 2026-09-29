#!/bin/bash
set -u
cd "$(dirname "$0")"
export LC_ALL=C
TMP=$(mktemp -d)
pass=0; fail=0

check() {
  local got
  ./run_local.sh "$2" "$TMP/out" >/dev/null
  got=$(cat "$TMP/out")
  if [ "$got" = "$3" ]; then echo "PASS  $1  ($got)"; pass=$((pass+1))
  else echo "FAIL  $1  got=$got expected=$3"; fail=$((fail+1)); fi
}

check "assignment sample" test_data/sample.txt 2

printf '3 3\n0 1\n1 2\n2 0\n' > "$TMP/k3";            check "single triangle" "$TMP/k3" 1
printf '4 3\n0 1\n1 2\n2 3\n' > "$TMP/path";          check "path (no triangle)" "$TMP/path" 0
printf '4 6\n0 1\n0 2\n0 3\n1 2\n1 3\n2 3\n' > "$TMP/k4"; check "K4" "$TMP/k4" 4
printf '3 6\n0 1\n1 0\n1 2\n2 1\n2 0\n0 2\n' > "$TMP/dup"; check "duplicate/reversed edges" "$TMP/dup" 1
printf '3 4\n0 0\n0 1\n1 2\n2 0\n' > "$TMP/loop";     check "self loop ignored" "$TMP/loop" 1
python3 -c "
n=30;e=[(i,j) for i in range(n) for j in range(i+1,n)]
print(n,len(e));[print(i,j) for i,j in e]" > "$TMP/k30"; check "K30 (C(30,3))" "$TMP/k30" 4060

for s in 11 12 13 14 15; do
  python3 gen_graph.py 60 400 --seed $s > "$TMP/r$s"
  check "random ER seed=$s (brute force)" "$TMP/r$s" "$(python3 verify_sequential.py "$TMP/r$s" --brute)"
  python3 gen_graph.py 300 2000 --seed $s --model powerlaw > "$TMP/p$s"
  check "random powerlaw seed=$s" "$TMP/p$s" "$(python3 verify_sequential.py "$TMP/p$s")"
done

rm -rf "$TMP"
echo "----"; echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
