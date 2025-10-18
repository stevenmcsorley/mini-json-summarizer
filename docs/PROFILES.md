# Profiles System Documentation

Profiles provide domain-specific extractors and sensible defaults for common JSON summarization use cases like logs, metrics, and policy analysis.

## Overview

A **profile** is a YAML configuration file that defines:
- **Extractors**: Targeted data extraction logic (categorical distributions, numeric stats, time buckets, diffs)
- **Defaults**: Preconfigured focus areas, styles, and output preferences
- **LLM Hints**: Domain-specific prompts for hybrid/LLM engines
- **Redaction Rules**: Field-level allow/deny lists and regex patterns
- **Limits**: Custom topK, depth, and aggregation thresholds

## Quick Start

### Using a Profile

Request summarization with a profile:

```bash
curl -X POST http://localhost:8080/v1/summarize-json \
  -H "Content-Type: application/json" \
  -d '{
    "profile": "logs",
    "json": {
      "logs": [
        {"timestamp": "2025-10-18T10:11:00Z", "level": "error", "service": "api", "code": 504},
        {"timestamp": "2025-10-18T10:11:10Z", "level": "warn", "service": "api", "code": 499}
      ]
    },
    "stream": false
  }'
```

### List Available Profiles

```bash
curl http://localhost:8080/v1/profiles
```

Response:
```json
[
  {
    "id": "logs",
    "version": "1.0.0",
    "title": "Log Analysis Profile",
    "description": "Extracts error patterns, service health, and temporal trends from application logs"
  },
  {
    "id": "metrics",
    "version": "1.0.0",
    "title": "Metrics and KPI Profile",
    "description": "Focuses on numeric statistics and performance indicators"
  },
  {
    "id": "policy",
    "version": "1.0.0",
    "title": "Policy and Compliance Profile",
    "description": "Analyzes policy changes and compliance violations with baseline comparison"
  }
]
```

## Profile YAML Schema

### Basic Structure

```yaml
id: my-profile
version: 1.0.0
title: My Custom Profile
description: Brief description of what this profile does

defaults:
  focus: [field1, field2]
  style: bullets
  length: medium
  engine: deterministic

extractors:
  - categorical:level
  - numeric:latency_ms
  - timebucket:timestamp:minute

llm_hints:
  system_suffix: "Custom instructions for LLM."
  narrative_tone: neutral

redaction:
  deny_paths: [$..*password, $..*token]
  allow_paths: [$.level, $.service]
  extra_regexes:
    - name: credit_card
      pattern: '\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'

limits:
  topk: 5
  max_categories: 100
  numeric_dominance_threshold: 0.8

time:
  timezone: UTC
  timebucket_default: minute
```

### Field Reference

#### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique profile identifier (lowercase, hyphens allowed) |
| `version` | string | Semantic version (e.g., "1.0.0") |
| `title` | string | Human-readable profile name |
| `description` | string | Brief description of profile purpose |

#### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `defaults` | object | Default values for request parameters |
| `extractors` | list[string] | Profile-specific extractor specifications |
| `llm_hints` | object | LLM-specific guidance |
| `redaction` | object | PII and sensitive data rules |
| `limits` | object | Custom thresholds and limits |
| `time` | object | Timezone and time bucketing settings |

### Defaults Section

Override request defaults:

```yaml
defaults:
  focus: [level, service, error]        # Default focus fields
  style: bullets                         # Output style: bullets, kpi-block, narrative
  length: medium                         # Response length: short, medium, long
  engine: deterministic                  # Engine: deterministic, llm, hybrid
  include_root_summary: true             # Include root-level summary
  top_k_categories: 10                   # Top-K for categorical aggregations
  top_k_numeric: 5                       # Top-K for numeric summaries
```

**Precedence**: Request parameters override profile defaults, profile defaults override engine defaults.

### Extractors

Extractors define targeted data extraction logic. Multiple extractors can be specified.

#### Categorical Extractor

Extract frequency distributions for string/categorical fields.

**Syntax**: `categorical:<field_name>`

**Example**:
```yaml
extractors:
  - categorical:level
  - categorical:service
```

**Output**:
```json
{
  "text": "level: \"error\" (5), \"warn\" (3), \"info\" (2) | total: 10",
  "citations": [{"path": "$.logs[*].level"}],
  "evidence": {
    "field": "level",
    "total_count": 10,
    "unique_values": 3,
    "top": [["error", 5], ["warn", 3], ["info", 2]]
  }
}
```

**Behavior**:
- Suppresses output if max count < 2 (avoids noise)
- High cardinality (>10 unique values) returns summary instead of full distribution
- Collects up to 3 example JSONPath citations

#### Numeric Extractor

Extract statistical aggregations for numeric fields.

**Syntax**: `numeric:<field_name>`

**Example**:
```yaml
extractors:
  - numeric:latency_ms
  - numeric:cpu_percent
```

**Output**:
```json
{
  "text": "latency_ms: count=100, mean=125.50, min=45.00, max=350.00, sum=12550.00",
  "citations": [{"path": "$.metrics[*].latency_ms"}],
  "evidence": {
    "field": "latency_ms",
    "count": 100,
    "sum": 12550.0,
    "mean": 125.5,
    "min": 45.0,
    "max": 350.0
  }
}
```

**Behavior**:
- Strict numeric type checking (no bool→int coercion)
- Requires 80% numeric dominance (configurable via `limits.numeric_dominance_threshold`)
- Skips fields with mixed types below dominance threshold

#### Timebucket Extractor

Extract temporal distributions by bucketing timestamps.

**Syntax**: `timebucket:<field_name>:<bucket_size>`

**Bucket sizes**: `minute`, `hour`, `day`

**Example**:
```yaml
extractors:
  - timebucket:timestamp:minute
  - timebucket:created_at:hour
```

**Output**:
```json
{
  "text": "timestamp (minute buckets): 2025-10-18 10:11 (15), 2025-10-18 10:12 (8) | total events: 23",
  "citations": [{"path": "$.logs[*].timestamp"}],
  "evidence": {
    "field": "timestamp",
    "bucket_size": "minute",
    "total_events": 23,
    "unique_buckets": 2,
    "top_buckets": [["2025-10-18 10:11", 15], ["2025-10-18 10:12", 8]]
  }
}
```

**Behavior**:
- Parses ISO 8601 timestamps (e.g., "2025-10-18T10:11:00Z")
- Supports configurable timezone (via `time.timezone`)
- Returns top 5 buckets by event count

#### Diff Extractor

Compare payload against baseline to detect additions and removals.

**Syntax**: `diff:baseline`

**Example**:
```yaml
extractors:
  - diff:baseline
```

**Usage**:
```bash
curl -X POST http://localhost:8080/v1/summarize-json \
  -d '{
    "profile": "policy",
    "json": {"users": [{"id": 1, "role": "admin"}]},
    "baseline_json": {"users": [{"id": 1}]},
    "stream": false
  }'
```

**Output**:
```json
{
  "text": "Baseline diff: added 1 paths (e.g., $.users[0].role)",
  "citations": [{"path": "$.users[0].role"}],
  "evidence": {
    "added": 1,
    "removed": 0,
    "added_paths": ["$.users[0].role"],
    "removed_paths": []
  }
}
```

### LLM Hints

Guide LLM behavior for hybrid/llm engines.

```yaml
llm_hints:
  system_suffix: "Focus on error patterns and service health metrics. Use urgent language for critical issues."
  narrative_tone: urgent  # neutral, urgent, compliance, technical
  user_message_prefix: "Analyze the following evidence for security compliance:"
```

**Fields**:
- `system_suffix`: Appended to system prompt
- `narrative_tone`: Suggested tone for LLM output
- `user_message_prefix`: Prepended to user message

**Note**: LLM hints only affect `hybrid` and `llm` engines. Deterministic engine ignores these fields.

### Redaction Rules

Control PII and sensitive data handling.

```yaml
redaction:
  deny_paths: [$..*password, $..*token, $..*secret]
  allow_paths: [$.level, $.service, $.timestamp]
  extra_regexes:
    - name: ssn
      pattern: '\b\d{3}-\d{2}-\d{4}\b'
    - name: credit_card
      pattern: '\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'
```

**Merge Formula**: `(global.deny ∪ profile.deny) − profile.allow`

**Behavior**:
- Profile `deny_paths` merge with global deny list
- Profile `allow_paths` override merged deny list
- `extra_regexes` supplement global PII patterns
- Redaction applied BEFORE extractor execution

### Limits

Customize aggregation thresholds.

```yaml
limits:
  topk: 5                                # Default top-K for all aggregations
  max_categories: 100                    # Max unique values before marking high-cardinality
  numeric_dominance_threshold: 0.8       # Require 80% numeric values for numeric extraction
  max_timebuckets: 10                    # Max time buckets to return
```

### Time Settings

Configure timezone and bucketing behavior.

```yaml
time:
  timezone: UTC                          # Timezone for timestamp parsing
  timebucket_default: minute             # Default bucket size: minute, hour, day
```

## Built-in Profiles

### logs.yaml

**Purpose**: Application log analysis with error tracking and temporal patterns.

**Extractors**:
- `categorical:level` - Log level distribution (error, warn, info)
- `categorical:service` - Service-level breakdown
- `timebucket:timestamp:minute` - Event timeline by minute

**Defaults**:
- Focus: level, service, error, code, timestamp
- Style: bullets

**LLM Hints**:
- System suffix: "Focus on error patterns, service health, and temporal trends."
- Narrative tone: urgent

**Use Case**: Analyzing incident logs, debugging production issues, service health monitoring.

### metrics.yaml

**Purpose**: Metrics and KPI summarization with statistical analysis.

**Extractors**:
- `numeric:latency_ms` - Latency statistics
- `numeric:cpu_percent` - CPU usage stats
- `categorical:endpoint` - Endpoint distribution

**Defaults**:
- Focus: latency, throughput, error_rate
- Style: kpi-block

**LLM Hints**:
- Narrative tone: neutral

**Use Case**: Performance monitoring, SLA compliance, capacity planning.

### policy.yaml

**Purpose**: Policy and compliance analysis with baseline comparison.

**Extractors**:
- `categorical:action` - Action type distribution
- `diff:baseline` - Detect policy changes

**Defaults**:
- Style: narrative
- Length: long

**LLM Hints**:
- Narrative tone: compliance

**Redaction**:
- Extra regexes: credit card pattern

**Use Case**: Compliance audits, security policy validation, change detection.

## Creating Custom Profiles

### Step 1: Create YAML File

Create a new file in `profiles/` directory:

```bash
touch profiles/my-profile.yaml
```

### Step 2: Define Profile Schema

```yaml
id: my-profile
version: 1.0.0
title: My Custom Profile
description: Custom profile for my specific use case

defaults:
  focus: [field1, field2]
  style: bullets

extractors:
  - categorical:status
  - numeric:amount
```

### Step 3: Test Profile

```bash
# Restart server to load new profile
uvicorn app.main:app --reload --port 8080

# Verify profile loaded
curl http://localhost:8080/v1/profiles | jq '.[] | select(.id == "my-profile")'

# Test with sample data
curl -X POST http://localhost:8080/v1/summarize-json \
  -d '{
    "profile": "my-profile",
    "json": {"data": [{"status": "active", "amount": 100}]},
    "stream": false
  }'
```

### Step 4: Iterate

Refine extractors and defaults based on output quality.

## Best Practices

### 1. Use Specific Extractors

Bad:
```yaml
extractors:
  - categorical:*  # Too broad
```

Good:
```yaml
extractors:
  - categorical:level
  - categorical:service
  - categorical:error_code
```

### 2. Match Extractors to Data Types

Ensure numeric extractors target numeric fields:

```yaml
# Good: latency_ms contains numbers
extractors:
  - numeric:latency_ms

# Bad: status is a string
extractors:
  - numeric:status  # Will fail numeric dominance check
```

### 3. Order Extractors by Importance

Extractors run in order. Place most important first:

```yaml
extractors:
  - categorical:level           # Most important: error levels
  - categorical:service         # Important: service breakdown
  - timebucket:timestamp:minute # Less critical: timeline
```

### 4. Use Allow Lists for Sensitive Data

Instead of broad deny patterns, use targeted allow lists:

```yaml
redaction:
  deny_paths: [$..*]  # Deny everything by default
  allow_paths:
    - $.level
    - $.service
    - $.timestamp
    - $.error_code
```

### 5. Test with Real Data

Always test profiles with representative production data:

```bash
# Export sample from production
curl https://api.example.com/logs?limit=100 > sample.json

# Test profile
curl -X POST http://localhost:8080/v1/summarize-json \
  -d @sample.json \
  --data-urlencode "profile=logs"
```

### 6. Version Your Profiles

Use semantic versioning for profile evolution:

- **Patch** (1.0.0 → 1.0.1): Bug fixes, documentation
- **Minor** (1.0.1 → 1.1.0): New extractors, backward-compatible changes
- **Major** (1.1.0 → 2.0.0): Breaking changes to schema or behavior

## Troubleshooting

### Profile Not Found

**Error**:
```json
{
  "error": "unknown_profile",
  "available": ["logs", "metrics", "policy"]
}
```

**Solution**: Check profile ID matches YAML filename (without extension):
- File: `profiles/my-profile.yaml`
- ID: `my-profile`

### Extractor Returns No Results

**Causes**:
1. Field name doesn't match JSON structure
2. Numeric dominance threshold not met (mixed types)
3. Low count suppression (max count < 2)

**Debug**:
```bash
# Check raw JSON structure
curl -X POST http://localhost:8080/v1/summarize-json \
  -d '{"profile":"logs","json":{...},"stream":false}' | jq '.bullets[].evidence'
```

### YAML Parse Error

**Error**:
```
Failed to load profiles: yaml.scanner.ScannerError
```

**Solution**: Validate YAML syntax with linter:
```bash
python -c "import yaml; yaml.safe_load(open('profiles/my-profile.yaml'))"
```

### High Cardinality Warning

**Output**:
```json
{
  "text": "user_id: high-cardinality (1000 unique values), no dominant values"
}
```

**Meaning**: Field has >10 unique values with no clear dominant value.

**Solution**: Consider whether this field should be extracted. High-cardinality fields (user IDs, UUIDs) often provide little insight.

## Advanced Usage

### Combining Profiles with LLM

Use hybrid engine for natural language output:

```bash
curl -X POST http://localhost:8080/v1/summarize-json \
  -d '{
    "profile": "metrics",
    "engine": "hybrid",
    "json": {"latency_ms": [95, 120, 140]},
    "stream": false
  }'
```

Profile extractors run first, then LLM rephrases evidence into natural language.

### Profile Precedence Override

Request parameters override profile defaults:

```bash
curl -X POST http://localhost:8080/v1/summarize-json \
  -d '{
    "profile": "metrics",      # Default: style=kpi-block
    "style": "narrative",       # Override to narrative
    "json": {...},
    "stream": false
  }'
```

### Baseline Comparison

Use `diff:baseline` extractor with baseline payload:

```bash
curl -X POST http://localhost:8080/v1/summarize-json \
  -d '{
    "profile": "policy",
    "json": {"policies": [{"id": 1, "level": "admin"}]},
    "baseline_json": {"policies": [{"id": 1}]},
    "stream": false
  }'
```

Output highlights added/removed fields.

## Configuration

### Environment Variables

```bash
# Enable/disable profiles system
PROFILES_ENABLED=true

# Directory containing profile YAML files
PROFILES_DIR=profiles

# Hot reload profiles on file change (development only)
PROFILES_HOT_RELOAD=false
```

### Startup Logging

When profiles load successfully:

```
INFO:app.profiles.loader:Profiles loaded: logs@1.0.0, metrics@1.0.0, policy@1.0.0
```

## API Reference

### GET /v1/profiles

List all available profiles.

**Response**:
```json
[
  {
    "id": "logs",
    "version": "1.0.0",
    "title": "Log Analysis Profile",
    "description": "...",
    "defaults": {...},
    "extractors": [...],
    "llm_hints": {...}
  }
]
```

### POST /v1/summarize-json

Summarize JSON with optional profile.

**Request**:
```json
{
  "profile": "logs",
  "json": {...},
  "stream": false
}
```

**Response** (success):
```json
{
  "engine": "deterministic",
  "profile": "logs",
  "bullets": [
    {
      "text": "level: \"error\" (5), \"warn\" (3)",
      "citations": [{"path": "$.logs[*].level"}],
      "evidence": {...}
    }
  ],
  "evidence_stats": {...}
}
```

**Response** (unknown profile):
```json
{
  "error": "unknown_profile",
  "available": ["logs", "metrics", "policy"]
}
```

## Examples

### Example 1: Log Analysis

```bash
curl -X POST http://localhost:8080/v1/summarize-json \
  -H "Content-Type: application/json" \
  -d '{
    "profile": "logs",
    "json": {
      "logs": [
        {"timestamp": "2025-10-18T10:11:00Z", "level": "error", "service": "api", "code": 504},
        {"timestamp": "2025-10-18T10:11:10Z", "level": "warn", "service": "api", "code": 499},
        {"timestamp": "2025-10-18T10:11:29Z", "level": "error", "service": "auth", "code": 401}
      ]
    },
    "stream": false
  }'
```

**Output**:
```json
{
  "profile": "logs",
  "bullets": [
    {
      "text": "level: \"error\" (2), \"warn\" (1) | total: 3",
      "citations": [{"path": "$.logs[*].level"}]
    },
    {
      "text": "service: \"api\" (2), \"auth\" (1) | total: 3",
      "citations": [{"path": "$.logs[*].service"}]
    },
    {
      "text": "timestamp (minute buckets): 2025-10-18 10:11 (3) | total events: 3",
      "citations": [{"path": "$.logs[*].timestamp"}]
    }
  ]
}
```

### Example 2: Metrics with Hybrid LLM

```bash
curl -X POST http://localhost:8080/v1/summarize-json \
  -H "Content-Type: application/json" \
  -d '{
    "profile": "metrics",
    "engine": "hybrid",
    "json": {
      "cpu": [0.4, 0.6, 0.9],
      "latency_ms": [95, 120, 140]
    },
    "stream": false
  }'
```

**Output** (natural language from LLM):
```json
{
  "engine": "hybrid",
  "profile": "metrics",
  "bullets": [
    {
      "text": "CPU utilization averaged 63.3% with a peak of 90%, indicating moderate load with occasional spikes.",
      "citations": [{"path": "$.cpu[*]"}]
    },
    {
      "text": "Latency averaged 118.33ms (min: 95ms, max: 140ms), suggesting acceptable performance within SLA targets.",
      "citations": [{"path": "$.latency_ms[*]"}]
    }
  ]
}
```

### Example 3: Policy Diff

```bash
curl -X POST http://localhost:8080/v1/summarize-json \
  -H "Content-Type: application/json" \
  -d '{
    "profile": "policy",
    "json": {
      "policies": [
        {"id": 1, "action": "allow", "resource": "users", "role": "admin"}
      ]
    },
    "baseline_json": {
      "policies": [
        {"id": 1, "action": "deny", "resource": "users"}
      ]
    },
    "stream": false
  }'
```

**Output**:
```json
{
  "profile": "policy",
  "bullets": [
    {
      "text": "action: \"allow\" (1) | total: 1",
      "citations": [{"path": "$.policies[*].action"}]
    },
    {
      "text": "Baseline diff: added 1 paths (e.g., $.policies[0].role)",
      "citations": [{"path": "$.policies[0].role"}]
    }
  ]
}
```

## Further Reading

- [Main README](../README.md): Overall project documentation
- [API Documentation](http://localhost:8080/docs): Interactive OpenAPI docs
- [PRD](../PRD.md): Full product requirements document (if available)

---

**Questions or feedback?** Open an issue at https://github.com/stevenmcsorley/mini-json-summarizer/issues
