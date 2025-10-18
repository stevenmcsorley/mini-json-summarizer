# Mini JSON Summarizer

Deterministic-first service for summarizing large JSON payloads with evidence, redaction, and optional chat refinement, based on the accompanying PRD.

## Features
- `/v1/summarize-json` endpoint accepts inline JSON or remote URLs (up to 20 MB) and emits Server-Sent Events or batched responses.
- Deterministic engine performs schema-guided traversal, computes numeric rollups, categorical frequency tables, and attaches JSONPath citations for every claim.
- Citations include representative value previews (up to three values) taken directly from the referenced JSON paths.
- Streaming responses standardize on `{"phase":"summary","bullet":...}` events and end with `{"phase":"complete","evidence_stats":...}` metadata.
- Automatic PII scrubbing with configurable regexes and JSONPath deny-lists executed before any summarization work.
- `baseline_json` support highlights additions, removals, and changes between payloads.
- `/v1/chat` endpoint reuses the deterministic engine to refine focus based on conversation history, preparing the surface for future LLM integration.
- Container-ready via FastAPI + Uvicorn, with streaming defaults and CORS configuration.

## Getting Started
```bash
python -m venv .venv
. .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .[dev]
uvicorn app.main:app --reload --port 8080
```

### Summarization Request
```bash
curl -N -X POST http://localhost:8080/v1/summarize-json \
  -H "Content-Type: application/json" \
  -d '{
        "json": {"orders":[{"id":1,"total":20,"status":"paid"}]},
        "focus": ["orders", "totals"],
        "include_root_summary": false,
        "stream": true
      }'
```

#### Sample SSE stream
```
data: {"phase":"summary","bullet":{"text":"orders: 1 record; total: sum 20, avg 20.00, min 20, max 20","citations":[{"path":"$.orders","value_preview":[{"id":1,"total":20,"status":"paid"}]}],"evidence":{"records":1,"total":{"count":1,"sum":20.0,"min":20.0,"max":20.0,"avg":20.0}}}}

data: {"phase":"complete","evidence_stats":{"paths_count":1,"bytes_examined":122,"elapsed_ms":5}}
```

#### Sample non-streaming response
```
{
  "engine": "deterministic",
  "focus": ["orders", "totals"],
  "redactions_applied": false,
  "bullets": [
    {
      "text": "orders: 3 records; total: sum 65, avg 21.67, min 5, max 40 | status: paid (2), failed (1)",
      "citations": [
        {"path": "$.orders[*].total", "value_preview": [20, 40, 5]},
        {"path": "$.orders[*].status", "value_preview": ["paid", "paid", "failed"]}
      ],
      "evidence": {
        "records": 3,
        "total": {"count": 3, "sum": 65.0, "min": 5.0, "max": 40.0, "avg": 21.666666666666668},
        "status": {"top": [["paid", 2], ["failed", 1]]}
      }
    }
  ],
  "evidence_stats": {
    "paths_count": 2,
    "bytes_examined": 254,
    "elapsed_ms": 7
  }
}
```

### Chat Refinement
```bash
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
        "messages": [
          {"role":"system","content":"You summarize JSON evidence."},
          {"role":"user","content":"Zoom into failed payments."}
        ],
        "json": {"payments":[{"amount":50,"status":"failed"}]},
        "include_root_summary": true
      }'
```

### Output Schema
- `bullet.text` – concise, human-readable summary sentence.
- `bullet.citations[]` – `{ "path": "<JSONPath>", "value_preview": [<example values…>] }`.
- `bullet.evidence` – structured aggregates (counts, sums, top-k tables) backing each claim.
- `evidence_stats` – `{ "paths_count": int, "bytes_examined": int, "elapsed_ms": int }` capturing traceability metadata.

### Structured error example
```
{
  "error": "payload_too_large",
  "limit_bytes": 20971520
}
```

Each SSE `data:` line is a complete JSON object; the `phase:"complete"` event marks the end of the stream.

Visit http://localhost:8080/docs for interactive OpenAPI documentation.

Health check:
```bash
curl http://localhost:8080/healthz
# -> {"status":"ok","engine":"deterministic","version":"1.0.0"}
```

### Example Use Case
Point the service at a 10 MB API export to get instant rollups and top categories with verified JSONPath citations—ideal for log digests, compliance-safe reporting, and noisy incident payloads.

## Testing
```bash
pytest
```

## Docker
```bash
docker build -t mini-json-summarizer .
docker run -p 8080:8080 mini-json-summarizer
```

## Configuration
Settings are supplied via environment variables or `.env`:
- `MAX_PAYLOAD_BYTES` (default 20971520)
- `MAX_JSON_DEPTH` (default 64)
- `PII_REDACTION_ENABLED` (default true)
- `ALLOW_ORIGINS` for CORS whitelisting
- `STREAMING_CHUNK_DELAY_MS` (default 100)

### LLM Configuration (Optional)
Enable LLM-powered summarization with OpenAI or Anthropic models for more natural, refined summaries while maintaining evidence-based accuracy.

#### Quick Start with LLM

**1. Configure your LLM provider in `.env`:**

```bash
# OpenAI Configuration
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-proj-your-key-here

# OR Anthropic Configuration
# LLM_PROVIDER=anthropic
# LLM_MODEL=claude-3-haiku-20240307
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# OR Ollama Configuration (Local, No API Key Needed)
# LLM_PROVIDER=ollama
# LLM_MODEL=llama3.2
# OLLAMA_BASE_URL=http://localhost:11434

# Optional LLM settings
LLM_MAX_TOKENS=1500
LLM_TEMPERATURE=0.1
LLM_FALLBACK_TO_DETERMINISTIC=true
```

**Using Ollama (Local LLM - No API Costs):**

Ollama allows you to run LLMs completely locally without sending data to external services.

1. Install Ollama from https://ollama.ai
2. Pull a model: `ollama pull llama3.2`
3. Start Ollama: `ollama serve` (usually starts automatically)
4. Configure `.env`:
```bash
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

Popular Ollama models:
- `llama3.2` - Latest Llama model, good general performance
- `mistral` - Fast and capable, good for JSON tasks
- `phi` - Small and efficient, runs on lower-end hardware
- `codellama` - Optimized for code understanding

```

**2. Request LLM-powered summarization:**

```bash
# Use hybrid engine (recommended - combines deterministic + LLM)
curl -X POST http://localhost:8080/v1/summarize-json \
  -H "Content-Type: application/json" \
  -d '{
        "json": {"orders":[{"id":1,"total":20,"status":"paid"}]},
        "engine": "hybrid",
        "stream": false
      }'

# Or use pure LLM engine
curl -X POST http://localhost:8080/v1/summarize-json \
  -H "Content-Type: application/json" \
  -d '{
        "json": {"orders":[{"id":1,"total":20,"status":"paid"}]},
        "engine": "llm",
        "stream": false
      }'
```

#### Available Engines

| Engine | Description | Use Case |
|--------|-------------|----------|
| `deterministic` | Fast, rule-based extraction with JSONPath citations | Default mode, no API costs, fully offline |
| `llm` | LLM-powered rephrasing of evidence bundles | Natural language summaries with API costs |
| `hybrid` | Deterministic evidence + LLM refinement | **Recommended**: Best of both worlds |

#### How LLM Mode Works

1. **Evidence Extraction**: Deterministic engine analyzes JSON and creates evidence bundles with citations
2. **Evidence-Only LLM Input**: Only the structured evidence (not raw JSON) is sent to the LLM
3. **Constrained Generation**: LLM rephrases using strict system prompts that enforce fact preservation
4. **No Hallucinations**: LLM cannot introduce new facts, only rephrase existing evidence

**Safety Features:**
- PII redaction applied **before** evidence extraction
- Evidence bundles include citation paths for traceability
- Fallback to deterministic mode if LLM fails
- No raw JSON sent to external APIs

#### Supported LLM Providers

**OpenAI:**
- Models: `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`, etc.
- Cost-effective with `gpt-4o-mini` (~$0.15 per 1M tokens)
- Fast response times

**Anthropic Claude:**
- Models: `claude-3-haiku-20240307`, `claude-3-sonnet-20240229`, `claude-3-opus-20240229`
- Excellent at following instructions and maintaining accuracy
- `haiku` is fastest and most cost-effective

**Ollama (Local):**
- Models: `llama3.2`, `mistral`, `codellama`, `phi`, and many others
- Runs completely locally on your machine - no API costs
- No data sent to external services - perfect for sensitive data
- Requires Ollama installed and running locally

#### Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `LLM_PROVIDER` | `none` | `none`, `openai`, `anthropic`, or `ollama` |
| `LLM_MODEL` | Provider-specific | Model identifier |
| `OPENAI_API_KEY` | - | OpenAI API key (required for OpenAI) |
| `ANTHROPIC_API_KEY` | - | Anthropic API key (required for Claude) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL (for Ollama) |
| `LLM_MAX_TOKENS` | `1500` | Maximum tokens for LLM response |
| `LLM_TEMPERATURE` | `0.1` | Lower = more deterministic output |
| `LLM_FALLBACK_TO_DETERMINISTIC` | `true` | Fall back if LLM fails |

Modify `app/config.py` for additional tuning (top-K limits, streaming cadence, redaction patterns).

## License
MIT © 2025 Steven McSorley
