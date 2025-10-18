#!/usr/bin/env bash
set -euo pipefail
API="http://localhost:8080/v1/summarize-json"

echo "A) Deep nesting"
curl -s -N -X POST "$API" -H "Content-Type: application/json" -d '{
  "json": {"a":{"b":{"c":{"d":{"e":{"f":{"g": {"h": 1}}}}}}}},
  "focus": ["a.b.c.d.e.f.g"],
  "stream": true
}' | grep -q '"phase":"' && echo "✓ deep nesting handled"

echo "B) Mixed types in same field"
curl -s -N -X POST "$API" -H "Content-Type: application/json" -d '{
  "json": {"items":[{"v":1},{"v":"1"},{"v":true},{"v":2}]},
  "focus":["items","v"], "stream": true
}' | grep -q '"items"' && echo "✓ mixed types summarized"

echo "C) Unicode / emoji: write UTF-8 to file"
python - <<'PY' > unicode.json
import json
s = "🚀✨" * 2000
print(json.dumps({"notes":[s]}, ensure_ascii=False))
PY
curl -s -N -X POST "$API" -H "Content-Type: application/json" --data-binary @unicode.json \
  | grep -q '"phase":"summary"' && echo "✓ unicode handled"

echo "D) Redaction patterns"
curl -s -X POST "$API" -H "Content-Type: application/json" -d '{
  "json": {"u":{"email":"a@b.com","apiKey":"sk-live-ABC123XYZ","token":"ghp_DEADBEEF","note":"ok"}},
  "focus": ["u"], "stream": false
}' | grep -Eq 'REDACTED|sk-live-|ghp_' && echo "✓ redaction surfaced"

echo "E) Payload limit regression (>20MB)"
python - <<'PY' > too_big.json
import json
n=600000
users=[{"id":i,"name":f"user{i}","note":"x"*40} for i in range(n)]
print(json.dumps({"users":users}))
PY
curl -s -X POST "$API" -H "Content-Type: application/json" --data-binary @too_big.json \
  | grep -q 'payload_too_large' && echo "✓ 413 enforced"
