#!/usr/bin/env bash
set -euo pipefail

API="http://localhost:8080"
TZ_PARAM="?tz=Europe/London"   # change if you want UTC
ENG="${1:-deterministic}"      # pass "hybrid" or "llm" to try LLM
OUTDIR="${2:-incident_artifacts}"
mkdir -p "$OUTDIR"

echo "===> 0) Sanity: profiles list"
curl -s "$API/v1/profiles" | python -m json.tool || true

echo
echo "===> 1) Build PRE-incident logs (mostly healthy)"
python - <<'PY' > pre_incident.json
import json, random, datetime as dt
random.seed(42)
base = dt.datetime(2025,10,18,10,0,0)  # morning
levels = ["info","warn","error"]
services = ["api","auth","web","search"]
logs=[]
for i in range(180):  # 180 events
    t = base + dt.timedelta(seconds=i*10)
    lvl = random.choices(levels, weights=[0.8,0.15,0.05])[0]
    svc = random.choice(services)
    code = 200
    if lvl=="warn": code = random.choice([499,429])
    if lvl=="error": code = random.choice([500,502,504,401])
    logs.append({
        "timestamp": (t.isoformat() + "Z"),
        "level": lvl,
        "service": svc,
        "code": code,
        "latency_ms": random.randint(50,250),
        "user_email": "user{}@example.com".format(random.randint(1,50))
    })
json.dump({"logs":logs}, open("pre_incident.json","w"))
PY
wc -c pre_incident.json

echo
echo "===> 2) Build INCIDENT logs (spike errors on api/auth, 5xx heavy, PII present)"
python - <<'PY' > incident.json
import json, random, datetime as dt
random.seed(43)
base = dt.datetime(2025,10,18,10,10,0)  # incident window
levels = ["info","warn","error"]
services = ["api","auth","web","search"]
logs=[]
for i in range(240):  # 240 events (higher volume)
    t = base + dt.timedelta(seconds=i*7)
    # higher error probability during incident
    lvl = random.choices(levels, weights=[0.4,0.2,0.4])[0]
    svc = random.choices(services, weights=[0.45,0.3,0.15,0.1])[0]  # api/auth dominate
    code = 200
    if lvl=="warn": code = random.choice([499,429])
    if lvl=="error":
        code = random.choices([500,502,504,401], weights=[0.5,0.2,0.25,0.05])[0]
    logs.append({
        "timestamp": (t.isoformat() + "Z"),
        "level": lvl,
        "service": svc,
        "code": code,
        "latency_ms": random.randint(120,1000),
        "user_email": "leak{}@example.com".format(random.randint(1,10)),  # should redact
        "apiKey": "SECRET-API-KEY-{}".format(random.randint(100,999))     # should redact unless allow-listed
    })
json.dump({"logs":logs}, open("incident.json","w"))
PY
wc -c incident.json

echo
echo "===> 3) Profile=logs (non-stream) – PRE incident snapshot (${ENG})"
curl -s -X POST "${API}/v1/summarize-json${TZ_PARAM}" \
  -H "Content-Type: application/json" \
  -d "{
    \"profile\":\"logs\",
    \"engine\":\"${ENG}\",
    \"json\": $(cat pre_incident.json),
    \"stream\": false
  }" > "${OUTDIR}/pre_out.json"
python -m json.tool < "${OUTDIR}/pre_out.json" > /dev/null || true
echo "   saved -> ${OUTDIR}/pre_out.json"

echo
echo "===> 4) Profile=logs (SSE) – INCIDENT window (${ENG})"
curl -N -X POST "${API}/v1/summarize-json${TZ_PARAM}" \
  -H "Content-Type: application/json" \
  -d "{
    \"profile\":\"logs\",
    \"engine\":\"${ENG}\",
    \"json\": $(cat incident.json),
    \"stream\": true
  }" | tee "${OUTDIR}/incident_stream.sse" >/dev/null
echo "   saved -> ${OUTDIR}/incident_stream.sse"
echo "   check order: profile bullets should precede generic; last event is phase=complete"

echo
echo "===> 5) DIFF: baseline=pre_incident vs incident (non-stream)"
curl -s -X POST "${API}/v1/summarize-json${TZ_PARAM}" \
  -H "Content-Type: application/json" \
  -d "{
    \"profile\":\"policy\",
    \"engine\":\"${ENG}\",
    \"json\": $(cat incident.json),
    \"baseline_json\": $(cat pre_incident.json),
    \"stream\": false
  }" > "${OUTDIR}/diff_out.json"
python -m json.tool < "${OUTDIR}/diff_out.json" > /dev/null || true
echo "   saved -> ${OUTDIR}/diff_out.json"
echo "   expect a 'Baseline diff' bullet with added/removed paths"

echo
echo "===> 6) Redaction check (non-stream) – ensure sensitive fields are masked"
curl -s -X POST "${API}/v1/summarize-json" \
  -H "Content-Type: application/json" \
  -d "{
    \"profile\":\"logs\",
    \"json\": {\"logs\":[{\"timestamp\":\"2025-10-18T10:20:00Z\",\"level\":\"error\",\"service\":\"api\",\"user_email\":\"secret@example.com\",\"apiKey\":\"ABCD1234SECRET\"}]},
    \"stream\": false
  }" > "${OUTDIR}/redaction_out.json"
python -m json.tool < "${OUTDIR}/redaction_out.json" > /dev/null || true
echo "   saved -> ${OUTDIR}/redaction_out.json"
echo "   expect email/apiKey redacted unless explicitly allow-listed by profile"

echo
echo "===> 7) Quick greps (human checks) – no jq needed"
echo "   • Errors present (incident):"
grep -Eo '"level": *"error"' incident.json | wc -l || true
echo "   • SSE complete present:"
grep -F '"phase":"complete"' "${OUTDIR}/incident_stream.sse" || true
echo "   • Any [REDACTED] flags:"
grep -F '[REDACTED]' "${OUTDIR}/pre_out.json" "${OUTDIR}/diff_out.json" "${OUTDIR}/redaction_out.json" 2>/dev/null || true

echo
echo "✅ Done. Artifacts in: ${OUTDIR}"
