#!/usr/bin/env bash
set -euo pipefail

API="http://localhost:8080/v1/summarize-json"
CHAT="http://localhost:8080/v1/chat"

echo "===> 1) Build a mega mixed JSON (~5k users, nested devices)"
python - <<'PY' > mega.json
import json, random, datetime
users=[]
for i in range(5000):
    users.append({
        "user_id": i,
        "email": f"user{i}@example.com",
        "country": random.choice(["UK","US","DE","FR","IN","JP","CA"]),
        "signup_date": str(datetime.date(2023, random.randint(1,12), random.randint(1,28))),
        "spend": round(random.uniform(5,5000),2),
        "refunded": random.choice([True, False]),
        "devices": [
            {"type": random.choice(["mobile","desktop","tablet"]),
             "os": random.choice(["iOS","Android","Windows","Linux","macOS"]),
             "sessions": random.randint(1,50)}
            for _ in range(random.randint(1,3))
        ]
    })
payload = {"meta":{"report":"Q3_Aggregate"}, "users":users}
print(json.dumps(payload))
PY

bytes=$(wc -c < mega.json)
echo "    mega.json size: $bytes bytes"

echo "===> 2) Summarize (SSE) with focus + redaction"
cat > mega_req.json <<'REQ'
{
  "json": __JSON__,
  "focus": ["users","spend","country","refunded","devices"],
  "include_root_summary": true,
  "stream": true
}
REQ
# inline the big JSON safely
awk 'NR==FNR{j=j$0;next} {gsub(/__JSON__/, j)}1' mega.json mega_req.json > .mega_req && mv .mega_req mega_req.json

# time the request; capture output
{ time curl -N -s -X POST "$API" -H "Content-Type: application/json" --data-binary @mega_req.json > mega_out.sse; } 2> mega_time.txt

grep -q '"phase":"summary"' mega_out.sse && echo "    ✓ summary chunks present"
grep -q '"phase":"complete"' mega_out.sse && echo "    ✓ complete event present"
# Redaction hint (if your service auto-redacts emails)
grep -q 'REDACTED' mega_out.sse && echo "    ✓ redaction visible (emails)" || echo "    … email redaction not shown (ok if disabled)"
echo "    timing:"; cat mega_time.txt

echo "===> 3) Delta test (make 1000 refunds flip to true)"
python - <<'PY' > mega_baseline.json
import json
data=json.load(open("mega.json"))
for u in data["users"][:1000]:
    u["refunded"]=True
json.dump(data, open("mega_baseline.json","w"))
PY

# build delta request
cat > mega_delta_req.json <<'REQ'
{
  "json": __CUR__,
  "delta": {"baseline": __BASE__},
  "focus": ["users","refunded"],
  "stream": true
}
REQ
awk 'FNR==NR{c=c$0;next} {gsub(/__CUR__/, c)}1' mega.json mega_delta_req.json > .step1
awk 'FNR==NR{b=b$0;next} {gsub(/__BASE__/, b)}1' mega_baseline.json .step1 > .step2
mv .step2 mega_delta_req.json; rm -f .step1

{ time curl -N -s -X POST "$API" -H "Content-Type: application/json" --data-binary @mega_delta_req.json > mega_delta_out.sse; } 2> mega_delta_time.txt
grep -q '"phase":"complete"' mega_delta_out.sse && echo "    ✓ delta complete"
echo "    timing:"; cat mega_delta_time.txt

echo "===> 4) Chat refinement: avg spend by country + refund rate"
cat > mega_chat_req.json <<'REQ'
{
  "messages": [
    {"role":"system","content":"You summarize JSON evidence."},
    {"role":"user","content":"Show average spend by country and refund rate."}
  ],
  "json": __JSON__
}
REQ
awk 'NR==FNR{j=j$0;next} {gsub(/__JSON__/, j)}1' mega.json mega_chat_req.json > .mega_chat && mv .mega_chat mega_chat_req.json

{ time curl -s -X POST "$CHAT" -H "Content-Type: application/json" --data-binary @mega_chat_req.json > mega_chat_out.json; } 2> mega_chat_time.txt
grep -q '"reply"' mega_chat_out.json && echo "    ✓ chat reply present"
echo "    timing:"; cat mega_chat_time.txt

echo
echo "Artifacts:"
echo "  mega.json            (input)"
echo "  mega_out.sse         (streamed summary)"
echo "  mega_delta_out.sse   (delta stream)"
echo "  mega_chat_out.json   (chat response)"
