"""
Log aggregator service - exposes Fluentd logs via HTTP endpoint.
Reads from Fluentd buffer and serves recent logs in JSON format.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Set
from collections import deque

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
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

# WebSocket connections for real-time updates
WEBSOCKET_CLIENTS: Set[WebSocket] = set()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "buffer_size": len(LOG_BUFFER)}


async def broadcast_log(log_entry: Dict[str, Any]):
    """Broadcast new log to all connected WebSocket clients."""
    if not WEBSOCKET_CLIENTS:
        return

    message = json.dumps({"type": "new_log", "log": log_entry})
    dead_clients = set()

    for client in WEBSOCKET_CLIENTS:
        try:
            await client.send_text(message)
        except Exception:
            dead_clients.add(client)

    # Remove disconnected clients
    WEBSOCKET_CLIENTS.difference_update(dead_clients)


@app.post("/ingest")
async def ingest_log(request: Request):
    """
    Receives logs from Fluentd HTTP output.
    Fluentd sends raw JSON string in body.
    """
    try:
        body = await request.body()
        body_str = body.decode("utf-8")

        # Parse the JSON log entry
        log_entry = json.loads(body_str)

        # Add ingestion timestamp
        log_entry["ingested_at"] = datetime.utcnow().isoformat()
        LOG_BUFFER.append(log_entry)

        # Broadcast to WebSocket clients
        asyncio.create_task(broadcast_log(log_entry))

        return {"status": "ok", "buffered": len(LOG_BUFFER)}
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time log streaming.
    Sends new logs as they arrive to connected clients.
    """
    await websocket.accept()
    WEBSOCKET_CLIENTS.add(websocket)

    try:
        # Send initial connection message
        await websocket.send_json(
            {
                "type": "connected",
                "message": "WebSocket connection established",
                "buffer_size": len(LOG_BUFFER),
            }
        )

        # Keep connection alive and listen for client messages
        while True:
            # Wait for any client message (ping/pong)
            data = await websocket.receive_text()

            # Echo back pings
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        WEBSOCKET_CLIENTS.discard(websocket)
    except Exception as e:
        WEBSOCKET_CLIENTS.discard(websocket)
        print(f"WebSocket error: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9880)
