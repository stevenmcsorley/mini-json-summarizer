#!/usr/bin/env bash
set -euo pipefail
API="http://localhost:8080/v1/summarize-json"

gen() {
python - <<'PY'
import json,random
orders=[{"id":i,"total":random.randint(10,500),"status":random.choice(["paid","failed","pending"])} for i in range(10000)]
print(json.dumps({"json":{"orders":orders},"focus":["orders","totals"],"stream":True}))
PY
}

runs=${1:-50}   # total requests
conc=${2:-20}   # concurrency
echo "Runs=$runs Concurrency=$conc"

# build body once to a file (faster)
gen > body.json

# fire requests
seq "$runs" | xargs -I{} -P "$conc" bash -c '
  t0=$(date +%s%3N)
  out=$(curl -s -N -X POST "'"$API"'" -H "Content-Type: application/json" --data-binary @body.json || true)
  t1=$(date +%s%3N)
  dur=$((t1 - t0))
  if echo "$out" | grep -q "\"phase\":\"complete\""; then echo "OK $dur"; else echo "FAIL $dur"; fi
' > results.txt

oks=$(grep -c "^OK" results.txt || true)
fails=$(grep -c "^FAIL" results.txt || true)
p95=$(awk '/^OK/{print $2}' results.txt | sort -n | awk ' {a[NR]=$1} END{if(NR){print a[int(0.95*NR)]} }')
echo "OK=$oks FAIL=$fails p95_ms=${p95:-N/A}"
