# PRD — Mini Chatbot Model for Summarizing JSON Data

## 1) Overview

**Goal:** Build a small, fast “mini chatbot” that can read arbitrary JSON payloads and produce accurate, structured, and human‑friendly summaries—optionally chat‑refinable—while guaranteeing schema fidelity and zero leakage of non‑requested fields.

**Outcome:** A containerized service exposing a minimal API (`/v1/summarize-json`, `/v1/chat`) with a pluggable summarization engine:

- **Deterministic mode:** schema‑guided traversal + compression + templates (fast, cheap, predictable).
- **LLM mode:** local or remote small LLM with constraints (for natural phrasing, inference, and flexible focus prompts).

**Why now:** Teams are drowning in large JSON logs, API responses, and analytics exports. They need concise, reliable summaries with proof they didn’t hallucinate keys or values.

---

## 2) Problem Statement

- JSON payloads are often deeply nested, verbose, and repetitive (logs, telemetry, API responses, financial/IoT data).
- Readers need highlights, KPIs, anomalies, and a clean narrative without reading every node.
- Existing LLM‑only approaches risk hallucinations and lack guarantees about field provenance.

**We need** a tool that:

1. Summarizes while citing exactly which JSON paths informed each bullet.
2. Can be steered by user focus (e.g., specific keys/paths, time windows, entities).
3. Can operate deterministically when needed (compliance), and conversationally when helpful.

---

## 3) Objectives & Non‑Goals

**Objectives**

- O1. Summarize arbitrary JSON up to **20 MB** with progressive/streaming output.
- O2. Guarantee **no invented fields**; every claim maps to a real JSONPath.
- O3. Support **focus prompts** (e.g., “errors by service”, “top 5 customers by spend”).
- O4. Offer **two engines** (Deterministic, LLM) with a single front‑door API.
- O5. Provide **explanations**: each bullet links to `$.path.to.value` and shows source snippets.
- O6. Provide **redaction policies** and **PII scrubbing** before any LLM invocation.

**Non‑Goals**

- N1. Not a general data‑viz/report builder (charts out of scope for v1; may emit numeric KPI blocks though).
- N2. Not a full text‑RAG platform; we focus on **JSON** inputs only (CSV/Parquet are future).
- N3. Not a BI semantic modeler; we won’t infer business metrics beyond simple aggregations in v1.

---

## 4) Users & Use Cases

**Primary Users**

- Data/API engineers: summarize API responses or nightly exports.
- SRE/Platform: summarize incident logs or config diffs.
- Analysts/PMs: get executive summaries with KPIs and anomalies.

**Key Use Cases**

1. _API Response Digests:_ Point tool at 2–10 MB JSON response → get bullets + KPIs within seconds.
2. _Error/Anomaly Readout:_ From log JSON, extract error types, counts, top offenders, impacted tenants.
3. _Entity Summary:_ For arrays of objects, compute top‑N, totals, min/max, and notable outliers.
4. _Delta Summary:_ Compare two JSON payloads, highlight additions/removals/changed keys.

---

## 5) Functional Requirements

- F1. Accept input via: raw JSON string, `application/json`, or URL to fetch (optional).
- F2. **Focus & Style Controls:**

  - `focus`: JSONPaths or natural language (e.g., "summarize errors and performance regressions").
  - `length`: `short|medium|long` (default `medium`).
  - `style`: `bullets|narrative|kpi-block|mixed`.
  - `template`: optional summarization template DSL (see §10).

- F3. **Engine Selection:** `engine = deterministic|llm|hybrid` (default `hybrid`: deterministic pre‑compress + LLM rephrase).
- F4. **Citations & Traceability:** Each bullet includes a list of JSONPaths and values used.
- F5. **Redaction:** Apply regex & path‑based redactions prior to LLM calls.
- F6. **Streaming:** Server‑sent events / WebSocket for progressive tokens.
- F7. **Limits:** Single request up to 20 MB; arrays up to 250k items with streaming aggregation.
- F8. **Deterministic Aggregations:** count, sum, min, max, avg, top‑k, group‑by at shallow depth; rollups configurable.
- F9. **Delta Mode:** Given `baseline_json` + `current_json`, produce changeset summary.
- F10. **Chat Refinement:** `/v1/chat` can ask follow‑ups, filter, or zoom into paths.

---

## 6) Non‑Functional Requirements

- NFR1. Latency targets (95th percentile, on a modest VM):

  - ≤ **2s** for ≤ 200 KB JSON in deterministic mode;
  - ≤ **8s** for 5 MB; ≤ **15s** for 20 MB with streaming output;
  - LLM mode adds model‑dependent overhead but must stream within **1s**.

- NFR2. Availability: **99.9%** monthly for API; graceful degradation to deterministic mode if LLM unavailable.
- NFR3. Resource bounds: Memory ≤ **1.5× input size** during parse/compress; CPU bounded via worker pool.
- NFR4. Security: TLS, authenticated API keys, per‑route RBAC (read/summary only).
- NFR5. Privacy: Redaction by default for PII patterns (emails, phones, credit‑cards, access tokens).
- NFR6. Observability: Structured logs, request IDs, metrics (latency, tokens, bytes), tracing hooks.

---

## 7) High‑Level Architecture

```
Client → API Gateway → Summarizer Service
                      ├─ Deterministic Engine (JSONPath walker, aggregator, templater)
                      ├─ LLM Engine (local GGUF or remote provider) with constraints
                      ├─ Redaction & Policy Layer
                      └─ Evidence Store (paths, snippets, stats) → in response + logs
```

**Data Flow (hybrid default):**

1. Parse JSON → 2) Redact by rules → 3) Deterministic compression: extract focused paths, stats, exemplars → 4) Build structured “evidence bundle” → 5) (Optional) LLM rephrases into natural summary **without adding facts**, allowed only to transform evidence → 6) Emit bullets + citations.

**Pluggability:** Engines behind an interface (`SummarizerEngine`) so we can swap LLM backends or run offline.

---

## 8) Model / Engine Design

**Deterministic Engine**

- JSON cursor traversal (iterative, memory‑aware).
- Built‑ins: `groupBy(path)`, `topK(path, k)`, `stats(path)`, `distinct(path)`, `freq(path)`.
- Template compiler turns DSL into traversal + aggregation plan (see §10).
- Emits `EvidenceBundle`:

```json
{
  "kpis": [
    { "name": "error_count", "value": 128, "paths": ["$.events[*].level"] }
  ],
  "bullets": [
    {
      "text": "128 errors across 3 services; checkout spikes at 19:00 UTC.",
      "evidence": [
        "$.events[*].service",
        "$.events[*].timestamp",
        "$.events[*].level"
      ],
      "verbatim": [
        { "path": "$.events[203].message", "value": "DB timeout on cart" }
      ]
    }
  ]
}
```

**LLM Engine**

- Input is **only** the `EvidenceBundle` (never raw JSON unless user disables redaction).
- System prompt enforces: _no new facts, preserve numbers/names, keep citations._
- Constrained decoding: JSON schema for output; reject/repair invalid generations.
- Target: small local model (1–7B) via llama.cpp / GGUF **or** remote API; adapter pattern.

---

## 9) API Design

### 9.1 `POST /v1/summarize-json`

**Request (JSON)**

```json
{
  "json": { "...": "..." },
  "focus": ["$.errors[*]", "service performance", "top customers by spend"],
  "engine": "hybrid",
  "length": "medium",
  "style": "mixed",
  "template": "optional DSL string",
  "redact": {
    "paths": ["$.users[*].email"],
    "patterns": ["(?i)apikey\\s*=:?\\s*([A-Za-z0-9-_]{20,})"]
  },
  "delta": { "baseline": null, "mode": "auto" },
  "response_format": "json|markdown",
  "stream": true
}
```

**Response (JSON)**

```json
{
  "summary": {
    "bullets": [
      {
        "text": "Errors rose 42% (128→182), driven by checkout service after 19:00 UTC.",
        "citations": [
          "$.events[*].level",
          "$.events[*].service",
          "$.events[*].timestamp"
        ],
        "snippets": [
          { "path": "$.events[203].message", "value": "DB timeout on cart" }
        ]
      }
    ],
    "kpis": [{ "name": "error_count", "value": 182 }],
    "top": { "services": [{ "name": "checkout", "errors": 121 }] }
  },
  "engine_used": "hybrid",
  "evidence_stats": { "paths_count": 37, "bytes_examined": 5242880 }
}
```

### 9.2 `POST /v1/chat`

Turn‑based refinement with tool‑calls:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a JSON summarizer. Do not invent facts."
    },
    { "role": "user", "content": "Focus on tenant=acme and payment failures" }
  ],
  "context": { "last_evidence_bundle": { "...": "..." } },
  "tools": ["get_json_path", "summarize_section", "compute_topk"],
  "stream": true
}
```

---

## 10) Template DSL (Optional)

**Purpose:** Let power users define outputs deterministically.

```
TEMPLATE "Incident Digest"
SECTION "KPIs" AS KPIS
  KPI name:error_count = COUNT($.events[?(@.level == 'error')])
  KPI name:services_impacted = COUNT(DISTINCT($.events[*].service))
END
SECTION "Bullets" AS BULLETS
  BULLET "Top offenders" FROM TOPK($.events[*].service, k=3) WITH FORMAT "{key}: {count} errors"
END
```

Compiler produces the traversal/aggregations and returns a structured summary object.

---

## 11) Redaction & Compliance

- Default PII masks: emails, phone numbers, card numbers, IBAN, access tokens, secrets.
- Path‑based redaction list is evaluated **before** LLM.
- Data retention: None by default; optional transient logs with hashing of sensitive values.
- Compliance guardrail: LLM sees only evidence bundle, not raw payload.

---

## 12) Observability

- Metrics: request size, parse time, traversal time, LLM tokens/time, output size.
- Tracing spans: `parse`, `redact`, `compress`, `llm_format`, `emit`.
- Logs: structured JSON with request ID, engine, latency, evidence_count.
- Sampling: retain full evidence for ≤1% of requests (configurable) for QA.

---

## 13) Quality & Evaluation

**Datasets**

- Synthetic large JSON (e‑commerce orders, logs, telemetry) + real open datasets.

**Metrics**

- **Schema fidelity:** % bullets with valid citations to real paths (target ≥ 99.5%).
- **Factual consistency:** no contradicted values (target ≥ 99%).
- **Compression ratio:** output tokens / input bytes (target ≤ 0.005 for ≥5 MB inputs).
- **Task success rate:** human eval pass for 10 core tasks (target ≥ 90%).
- **Latency p95:** see NFR1 targets.

**Tests**

- Unit: JSONPath walker, aggregators, redactors, DSL compiler.
- Golden tests: fixed inputs → expected summaries.
- Property‑based: never reference non‑existent paths; redactions enforced.
- Load: 20 MB inputs, 50 RPS, streaming back‑pressure.

---

## 14) Security

- API keys + optional JWT per tenant; per‑route RBAC.
- Payload size and depth limits; cycle detection; timeouts.
- Sandbox LLM call; deny network/file access for local models.

---

## 15) Deployment & Infra

- **Docker Compose (v1):**

  - `api` (FastAPI/Express), `summarizer` worker, optional `llm` (llama.cpp server), `redis` (queues), `nginx` (TLS).

- **Scaling:** HPA on CPU/time; isolate LLM to separate node pool if remote.
- **Storage:** ephemeral; optional S3 for evidence samples.

---

## 16) Rollout Plan

- **Alpha (Week 2):** Deterministic engine + `/v1/summarize-json` with streaming.
- **Beta (Week 3–4):** Hybrid mode with local small LLM; redaction; citations.
- **GA (Week 5–6):** `/v1/chat`, DSL v1, delta mode, dashboards/metrics, hard limits.

---

## 17) Risks & Mitigations

- **R1: Hallucinations in LLM mode.** Mitigate with evidence‑only input, constrained decoding, and validation.
- **R2: Large payload memory blow‑ups.** Use iterative streaming traversal; cap buffers; chunk arrays.
- **R3: PII leakage.** Default redaction + path deny‑lists; privacy review.
- **R4: Performance variance on 20 MB+.** Progressive emit + back‑pressure; worker pools.

---

## 18) Acceptance Criteria

1. For a 5 MB log JSON, service returns a 10–15 bullet summary with per‑bullet citations within **8s p95** in deterministic mode.
2. Hybrid mode preserves all numbers/names from evidence; no invented fields in 100 random trials.
3. Redaction masks all configured secrets before LLM is called.
4. `/v1/chat` can refine focus (e.g., “only tenant=acme last 1h”) without re‑upload.

---

## 19) Initial Backlog (v1)

- [ ] JSON parser with streaming cursor + depth/size guards
- [ ] JSONPath library (read‑only), plus minimal jq‑like ops
- [ ] Aggregators: count/sum/avg/min/max/topK/groupBy/distinct
- [ ] EvidenceBundle spec + validator
- [ ] Redaction module (regex + path list)
- [ ] Deterministic template DSL compiler + renderer
- [ ] FastAPI/Express service: `/v1/summarize-json` (sync + SSE)
- [ ] Engine interface + deterministic implementation
- [ ] Unit tests + golden tests
- [ ] Basic metrics + structured logging

**v1.1**

- [ ] Llama.cpp (local) adapter + constrained JSON generation
- [ ] Hybrid pipeline + system prompt + repair loop
- [ ] `/v1/chat` with tool‑calls (get_json_path, summarize_section)
- [ ] Delta mode

**v1.2**

- [ ] Template DSL v1 polishing
- [ ] RBAC per tenant + rate limiting
- [ ] Dashboard for metrics and evidence sampling

---

## 20) Appendix

### A. Example Prompt (LLM Engine)

```
System: You are a JSON summarizer. You must not invent fields, values, or entities.
You will receive an EvidenceBundle (citations + numbers). Your job is to rewrite it
into clear bullets while preserving all facts and including citations.
Output must match the JSON schema provided. Reject unknown fields.
```

### B. Example Request

```json
{
  "json": {
    "orders": [
      { "id": 1, "total": 99.5, "status": "paid" },
      { "id": 2, "total": 10.0, "status": "failed" }
    ]
  },
  "focus": ["top customers", "failures"],
  "engine": "hybrid",
  "style": "mixed",
  "length": "short"
}
```

### C. Example Summary (Markdown)

- **Orders:** 2 total; **paid:** 1; **failed:** 1.
  _Citations:_ `$.orders[*].status`, `$.orders[*].id`.
- **Revenue:** 109.5 total (avg 54.75).
  _Citations:_ `$.orders[*].total`.
