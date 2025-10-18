#!/usr/bin/env bash
set -euo pipefail

API="http://localhost:8080/v1/summarize-json"

fail() { echo "❌ $1"; echo "---- response ----"; echo "$2" | head -n 20; echo "-------------------"; exit 1; }
pass() { echo "✓ $1"; }

# A) Deep nesting
out=$(curl -s -N -w "\n%{http_code}" -X POST "$API" \
  -H "Content-Type: application/json" \
  -d '{"json":{"a":{"b":{"c":{"d":{"e":{"f":{"g":{"h":1}}}}}}}},"focus":["a.b.c.d.e.f.g"],"stream":true}')
code="${out##*$'\n'}"; body="${out%$'\n'*}"
[[ "$code" == "200" ]] || fail "deep nesting HTTP $code" "$body"
echo "$body" | grep -q '"phase":"summary"' || fail "deep nesting: no summary phase" "$body"
pass "deep nesting handled"

# B) Mixed types in same field
out=$(curl -s -N -w "\n%{http_code}" -X POST "$API" \
  -H "Content-Type: application/json" \
  -d '{"json":{"items":[{"v":1},{"v":"1"},{"v":true},{"v":2}]},"focus":["items","v"],"stream":true}')
code="${out##*$'\n'}"; body="${out%$'\n'*}"
[[ "$code" == "200" ]] || fail "mixed types HTTP $code" "$body"
echo "$body" | grep -q '"items"' || fail "mixed types: items not summarized" "$body"
pass "mixed types summarized"

# C) Unicode / emoji (force UTF-8)
export PYTHONIOENCODING=UTF-8
python - <<'PY' > unicode.json
import json
s = "🚀✨" * 2000
print(json.dumps({"notes":[s]}, ensure_ascii=False))
PY
out=$(curl -s -N -w "\n%{http_code}" -X POST "$API" \
  -H "Content-Type: application/json" \
  --data-binary @unicode.json)
code="${out##*$'\n'}"; body="${out%$'\n'*}"
[[ "$code" == "200" ]] || fail "unicode HTTP $code" "$body"
echo "$body" | grep -q '"phase":"summary"' || fail "unicode: no summary phase" "$body"
pass "unicode handled"

# D) Redaction patterns
out=$(curl -s -w "\n%{http_code}" -X POST "$API" \
  -H "Content-Type: application/json" \
  -d '{"json":{"u":{"email":"a@b.com","apiKey":"sk-live-ABC123XYZ","token":"ghp_DEADBEEF","note":"ok"}},"focus":["u"],"stream":false}')
code="${out##*$'\n'}"; body="${out%$'\n'*}"
[[ "$code" == "200" ]] || fail "redaction HTTP $code" "$body"
echo "$body" | grep -Eq 'REDACTED|sk-live-|ghp_' || fail "redaction not surfaced" "$body"
pass "redaction surfaced"

# E) Payload limit regression (>20MB)
python - <<'PY' > too_big.json
import json
n=600000
users=[{"id":i,"name":f"user{i}","note":"x"*40} for i in range(n)]
print(json.dumps({"users":users}))
PY
out=$(curl -s -w "\n%{http_code}" -X POST "$API" \
  -H "Content-Type: application/json" --data-binary @too_big.json || true)
code="${out##*$'\n'}"; body="${out%$'\n'*}"
[[ "$code" == "413" ]] || fail "expected 413, got $code" "$body"
echo "$body" | grep -q 'payload_too_large' || fail "413 body missing payload_too_large" "$body"
pass "413 enforced"
