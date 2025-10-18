"""Demo Worker service that generates timeout/queue error logs."""
import os
import random
import time
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fluent import sender
import uvicorn

app = FastAPI()

SERVICE_NAME = os.getenv("SERVICE_NAME", "worker")
TIMEOUT_RATE = float(os.getenv("TIMEOUT_RATE", "0.20"))
PORT = int(os.getenv("PORT", "8083"))

fluent_logger = sender.FluentSender("app", host="fluentd", port=24224)

# Worker-specific errors
WORKER_ERRORS = [
    {"code": 504, "message": "Job timeout", "weight": 40},
    {"code": 500, "message": "Queue full", "weight": 25},
    {"code": 500, "message": "Worker crashed", "weight": 20},
    {"code": 503, "message": "No workers available", "weight": 10},
    {"code": 500, "message": "Out of memory", "weight": 5},
]


def log_event(level: str, message: str, **extra):
    """Send structured log to Fluentd."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "service": SERVICE_NAME,
        "message": message,
        **extra,
    }
    fluent_logger.emit("log", log_entry)
    print(json.dumps(log_entry), flush=True)


@app.get("/")
async def root():
    """Health check."""
    log_event("info", "Health check")
    return {"status": "healthy", "service": SERVICE_NAME}


@app.post("/jobs/process")
async def process_job():
    """Background job processing."""
    job_id = f"job_{int(time.time() * 1000)}"

    # Simulate processing time
    processing_time = random.uniform(0.1, 2.0)

    if random.random() < TIMEOUT_RATE:
        error = random.choices(
            WORKER_ERRORS, weights=[e["weight"] for e in WORKER_ERRORS]
        )[0]
        log_event(
            "error",
            error["message"],
            code=error["code"],
            job_id=job_id,
            endpoint="/jobs/process",
            processing_time_ms=int(processing_time * 1000),
        )
        raise HTTPException(status_code=error["code"], detail=error["message"])

    await asyncio.sleep(processing_time)

    log_event(
        "info",
        "Job processed successfully",
        code=200,
        job_id=job_id,
        endpoint="/jobs/process",
        processing_time_ms=int(processing_time * 1000),
    )
    return {"job_id": job_id, "status": "completed"}


@app.post("/jobs/schedule")
async def schedule_job():
    """Job scheduling endpoint."""
    job_id = f"job_{int(time.time() * 1000)}"

    if random.random() < TIMEOUT_RATE / 2:
        log_event(
            "warn",
            "Job queue full",
            code=500,
            job_id=job_id,
            endpoint="/jobs/schedule",
            queue_size=random.randint(1000, 5000),
        )
        raise HTTPException(status_code=500, detail="Queue full")

    log_event(
        "info",
        "Job scheduled",
        code=202,
        job_id=job_id,
        endpoint="/jobs/schedule",
        queue_position=random.randint(1, 100),
    )
    return {"job_id": job_id, "status": "scheduled"}


@app.get("/jobs/{job_id}/status")
async def job_status(job_id: str):
    """Check job status."""

    if random.random() < TIMEOUT_RATE / 3:
        log_event(
            "error",
            "Job status lookup failed",
            code=500,
            job_id=job_id,
            endpoint=f"/jobs/{job_id}/status",
        )
        raise HTTPException(status_code=500, detail="Database error")

    log_event(
        "info",
        "Job status retrieved",
        code=200,
        job_id=job_id,
        endpoint=f"/jobs/{job_id}/status",
    )
    return {"job_id": job_id, "status": random.choice(["pending", "running", "completed"])}


if __name__ == "__main__":
    log_event("info", f"Service starting on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
