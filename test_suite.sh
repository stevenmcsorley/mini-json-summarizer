#!/usr/bin/env bash
set -e

API="http://localhost:8080/v1/summarize-json"
CHAT="http://localhost:8080/v1/chat"

echo "===> Test 1: Basic rollup"
curl -N -s -X POST $API \
  -H "Content-Type: application/json" \
  -d '{
    "json": {
      "orders": [
        {"id":1,"total":20,"status":"paid"},
        {"id":2,"total":40,"status":"paid"},
        {"id":3,"total":5,"status":"failed"}
      ]
    },
    "focus":["orders","totals"],
    "stream":true
  }' | grep -q '"phase":"summary"' && echo "✓ basic rollup passed"

echo
echo "===> Test 2: Nested service metrics"
curl -N -s -X POST $API \
  -H "Content-Type: application/json" \
  -d '{
    "json": {
      "services": [
        {"name":"checkout","latency_ms":120,"errors":5},
        {"name":"search","latency_ms":95,"errors":1},
        {"name":"profile","latency_ms":140,"errors":0}
      ]
    },
    "focus":["services","latency","errors"],
    "stream":true
  }' | grep -q '"latency_ms"' && echo "✓ nested metrics passed"

echo
echo "===> Test 3: Delta mode"
curl -N -s -X POST $API \
  -H "Content-Type: application/json" \
  -d '{
    "json": {"settings":{"mode":"production","debug":false}},
    "delta": {"baseline":{"settings":{"mode":"staging","debug":true}}},
    "focus":["settings"],
    "stream":true
  }' | grep -q '"mode"' && echo "✓ delta mode passed"

echo
echo "===> Test 4: Matrix summary"
curl -N -s -X POST $API \
  -H "Content-Type: application/json" \
  -d '{
    "json": {
      "matrix": [
        [1,2,3],
        [4,5,6],
        [7,8,9]
      ]
    },
    "focus":["matrix"],
    "stream":true
  }' | grep -q '"matrix"' && echo "✓ matrix summary passed"

echo
echo "===> Test 5: Redaction check"
curl -s -X POST $API \
  -H "Content-Type: application/json" \
  -d '{
    "json":{"users":[{"email":"secret@example.com","apiKey":"ABCD1234SECRET","balance":99.9}]},
    "focus":["users"],
    "stream":false
  }' | grep -q 'REDACTED' && echo "✓ redaction passed"

echo
echo "===> Test 6: Chat summarization"
curl -s -X POST $CHAT \
  -H "Content-Type: application/json" \
  -d '{
    "messages":[
      {"role":"system","content":"You summarize JSON evidence."},
      {"role":"user","content":"Show top spenders and failed payments"}
    ],
    "json":{
      "payments":[
        {"user":"alice","amount":150,"status":"failed"},
        {"user":"bob","amount":200,"status":"paid"},
        {"user":"carol","amount":500,"status":"paid"}
      ]
    }
  }' | grep -q '"reply"' && echo "✓ chat summarization passed"

echo
echo "===> Test 7: Large 10k-record input"
python - <<'PY' > large.json
import json, random
orders=[{"id":i,"total":random.randint(10,500),"status":random.choice(["paid","failed","pending"])} for i in range(10000)]
print(json.dumps({"orders":orders}))
PY
curl -N -s -X POST $API -H "Content-Type: application/json" --data-binary @large.json \
  | grep -q '"phase":"complete"' && echo "✓ large input handled"

echo
echo "===> Test 8: Oversized (>20MB) payload"
python - <<'PY' > too_big.json
import json, random
n = 400000
users=[{"id":i,"name":f"user{i}","note":"x"*40} for i in range(n)]
print(json.dumps({"users":users}))
PY
if curl -s -X POST $API -H "Content-Type: application/json" --data-binary @too_big.json | grep -q 'payload_too_large'; then
  echo "✓ payload_too_large handled"
else
  echo "⚠ oversized payload not rejected (check limit)" >&2
fi

echo
echo "===> Test 9: Invalid JSON"
curl -s -X POST $API -H "Content-Type: application/json" \
  -d '{"json": {"broken": [1,2,3}}' | grep -q '"error"' && echo "✓ invalid JSON handled"

echo
echo "===> Test 10: Health check"
curl -s http://localhost:8080/healthz | grep -q '"status":"ok"' && echo "✓ health check passed"

echo
echo "✅ All deterministic summarizer tests executed"
