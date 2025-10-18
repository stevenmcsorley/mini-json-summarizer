# Live Error Monitoring Dashboard

**Real-time operational dashboard** powered by Mini JSON Summarizer's SSE streaming and profiles system.

<img src="https://img.shields.io/badge/SSE-Real--time-brightgreen" />
<img src="https://img.shields.io/badge/Profile-logs-blue" />
<img src="https://img.shields.io/badge/Stack-Docker-blue" />

---

## ✨ Features

- **🔴 Live Error Aggregation** - Real-time error tracking via SSE
- **🏥 Service Health Heatmap** - Red/Yellow/Green status indicators
- **📈 Temporal Spike Detection** - Minute-by-minute error rate charts
- **📊 Top-K Error Codes** - Weighted by frequency (504, 500, 401...)
- **🎯 Profile-Powered** - Uses `logs` profile from parent Mini JSON Summarizer
- **⚡ Zero Configuration** - `docker-compose up` and you're live

---

## 🚀 Quick Start

```bash
# From examples/live-dashboard directory
docker-compose up

# Open dashboard
open http://localhost:3000
```

**That's it!** The dashboard will automatically start receiving live error data.

---

## 🎯 What You'll See

### 1. **Top Errors Panel**
```
🔴 504 Gateway Timeout    (47)
🟠 500 Internal Error     (23)
🟡 401 Unauthorized       (12)
```

### 2. **Service Health Panel**
```
api-service     🔴 CRITICAL
auth-service    🟡 DEGRADED
worker-service  🟢 HEALTHY
```

### 3. **Error Rate Timeline**
Live Chart.js graph showing error spikes by minute

### 4. **Raw Log Stream**
Scrolling terminal view of incoming SSE events

---

## 📦 Stack Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Dashboard** | Vanilla JS + Tailwind | Beautiful UI with SSE client |
| **Summarizer** | Parent Mini JSON Summarizer | Profiles-powered log analysis |
| **Services** | 3x FastAPI microservices | Generate realistic error logs |
| **Log Collector** | Fluentd | Aggregate JSON logs to buffer |
| **Orchestration** | Docker Compose | One-command stack startup |

---

## 🔧 Architecture

```
┌──────────────┐
│ Microservices│ (api, auth, worker)
│  Generate    │
│  JSON Logs   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Fluentd    │ (log aggregation)
│   Buffer     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Mini JSON    │ (ACTUAL parent summarizer)
│ Summarizer   │ profile=logs, stream=true
│  :8080       │
└──────┬───────┘
       │ SSE
       ▼
┌──────────────┐
│  Dashboard   │ (EventSource API)
│   :3000      │
└──────────────┘
```

---

## 🎭 Simulate Incidents

### Spike 504 Errors
```bash
./scripts/generate-incidents.sh spike-504
```

**What happens:**
- API service error rate jumps to 80%
- Dashboard shows 504 dominating Top Errors
- Error chart spikes
- Service health goes RED

### Gradual Token Expiry
```bash
./scripts/generate-incidents.sh token-expiry-wave
```

**What happens:**
- Auth service 401 errors climb gradually
- Dashboard shows rolling pattern in timeline
- Service degrades from GREEN → YELLOW

### Total Outage
```bash
./scripts/generate-incidents.sh total-failure
```

**What happens:**
- All services go critical
- Error count explodes
- Dashboard fills with red indicators

---

## 🔌 How SSE Connection Works

The dashboard connects to the **actual Mini JSON Summarizer** from the parent directory:

```javascript
// dashboard/app.js (production version)
const eventSource = new EventSource(
  'http://localhost:8080/v1/summarize-json?' +
  new URLSearchParams({
    profile: 'logs',           // Use logs profile
    json_url: 'http://fluentd:9880/logs/last-5min',
    stream: true,              // Enable SSE
    focus: ['level', 'service', 'code']
  })
);

eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);

  if (data.phase === 'summary') {
    // Update dashboard with bullet.evidence
    updateTopErrors(data.bullet.evidence.code.top);
    updateServiceHealth(data.bullet.evidence.service.top);
    updateChart(data.bullet.evidence.level.top);
  }

  if (data.phase === 'complete') {
    console.log('Summary complete:', data.evidence_stats);
  }
});
```

---

## 🎨 Customization

### Change Update Interval

Edit `docker-compose.yml`:
```yaml
summarizer:
  environment:
    STREAMING_CHUNK_DELAY_MS: "100"  # Faster updates
```

### Adjust Error Rates

Tune service error rates:
```yaml
api-service:
  environment:
    ERROR_RATE: "0.30"  # 30% errors (high)

auth-service:
  environment:
    ERROR_RATE: "0.05"  # 5% errors (low)
```

### Use Different Profile

Change to metrics profile:
```javascript
// dashboard/app.js
const eventSource = new EventSource(
  'http://localhost:8080/v1/summarize-json?' +
  new URLSearchParams({
    profile: 'metrics',  // Changed from 'logs'
    stream: true
  })
);
```

---

## 📊 Sample Dashboard Output

### Top Errors (Real SSE Data)
```json
{
  "phase": "summary",
  "bullet": {
    "text": "code: 504 (47), 500 (23), 401 (12) | service: api (52), auth (18), worker (12)",
    "evidence": {
      "code": {
        "top": [
          [504, 47],
          [500, 23],
          [401, 12]
        ]
      },
      "service": {
        "top": [
          ["api", 52],
          ["auth", 18],
          ["worker", 12]
        ]
      }
    },
    "citations": [
      {"path": "$.logs[*].code"},
      {"path": "$.logs[*].service"}
    ]
  }
}
```

This data automatically populates the dashboard panels!

---

## 🐛 Troubleshooting

### Dashboard shows "Waiting for data..."

**Check:**
```bash
# Verify summarizer is running
curl http://localhost:8080/healthz

# Verify services are generating logs
docker-compose logs api-service | tail -n 20

# Verify Fluentd is receiving logs
docker-compose logs fluentd | tail -n 20
```

### SSE Connection Fails

**Check CORS:**
```bash
# Summarizer should allow dashboard origin
# In parent ../../app/config.py
ALLOW_ORIGINS: ["*"]
```

---

## 🎓 Learning Points

This example demonstrates:

1. **SSE Streaming** - Real-time updates without WebSockets
2. **Profiles System** - `logs` profile handles all extraction logic
3. **Evidence-Based UI** - Dashboard uses `evidence` field for data
4. **JSONPath Citations** - Every claim traceable to source
5. **Production Patterns** - Fluentd → Summarizer → Dashboard (real ops stack)

---

## 📦 Services

| Service | Port | Purpose |
|---------|------|---------|
| `summarizer` | 8080 | **Parent Mini JSON Summarizer** |
| `api-service` | 8081 | Generates API errors (504, 500, 401) |
| `auth-service` | 8082 | Generates auth errors (401, 403, 429) |
| `worker-service` | 8083 | Generates job errors (504, 500, 503) |
| `fluentd` | 24224 | Log aggregation |
| `dashboard` | 3000 | Live monitoring UI |

---

## 🚀 Next Steps

1. **Add Hybrid LLM** - Get natural language summaries
   ```javascript
   profile: 'logs',
   engine: 'hybrid'  // Add this
   ```

2. **Baseline Comparison** - Detect regressions
   ```javascript
   baseline_json_url: 'http://fluentd:9880/logs/yesterday'
   ```

3. **Custom Profiles** - Create your own extractors
   ```yaml
   # ../../profiles/my-ops-profile.yaml
   id: my-ops-profile
   extractors:
     - categorical:error_category
     - numeric:response_time_ms
   ```

---

## 📄 License

MIT © 2025 Steven McSorley

Part of [Mini JSON Summarizer](https://github.com/stevenmcsorley/mini-json-summarizer) project.
