"""
Log aggregator service - exposes Fluentd logs via HTTP endpoint.
Reads from Fluentd buffer and serves recent logs in JSON format.
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
from collections import deque

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn


app = FastAPI(title="Log Aggregator", version="1.0.0")

# Enable CORS for dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory buffer for recent logs (last 5 minutes)
LOG_BUFFER = deque(maxlen=1000)
BUFFER_WINDOW = timedelta(minutes=5)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "buffer_size": len(LOG_BUFFER)}


@app.post("/ingest")
async def ingest_log(log_entry: Dict[str, Any]):
    """
    Receives logs from Fluentd forward output.
    Adds timestamp and stores in buffer.
    """
    log_entry["ingested_at"] = datetime.utcnow().isoformat()
    LOG_BUFFER.append(log_entry)
    return {"status": "ok"}


@app.get("/logs/last-5min")
async def get_recent_logs():
    """
    Returns logs from the last 5 minutes.
    This endpoint is called by the summarizer.
    """
    cutoff_time = datetime.utcnow() - BUFFER_WINDOW

    recent_logs = []
    for log in LOG_BUFFER:
        try:
            ingested_at = datetime.fromisoformat(log.get("ingested_at", ""))
            if ingested_at >= cutoff_time:
                recent_logs.append(log)
        except (ValueError, TypeError):
            # Include logs without valid timestamp
            recent_logs.append(log)

    return JSONResponse(content=recent_logs)


@app.get("/logs/stats")
async def get_log_stats():
    """Statistics about buffered logs."""
    if not LOG_BUFFER:
        return {
            "total_logs": 0,
            "services": [],
            "levels": {},
            "oldest_log": None,
            "newest_log": None,
        }

    services = set()
    levels = {}

    for log in LOG_BUFFER:
        service = log.get("service", "unknown")
        level = log.get("level", "unknown")

        services.add(service)
        levels[level] = levels.get(level, 0) + 1

    oldest = list(LOG_BUFFER)[0].get("ingested_at", "unknown")
    newest = list(LOG_BUFFER)[-1].get("ingested_at", "unknown")

    return {
        "total_logs": len(LOG_BUFFER),
        "services": sorted(services),
        "levels": levels,
        "oldest_log": oldest,
        "newest_log": newest,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9880)
