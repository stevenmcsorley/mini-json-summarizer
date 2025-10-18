"""Demo Auth service that generates auth-specific error logs."""
import os
import random
import time
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header
from fluent import sender
import uvicorn

app = FastAPI()

SERVICE_NAME = os.getenv("SERVICE_NAME", "auth")
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.08"))
PORT = int(os.getenv("PORT", "8082"))

fluent_logger = sender.FluentSender("app", host="fluentd", port=24224)

# Auth-specific errors
AUTH_ERRORS = [
    {"code": 401, "message": "Invalid token", "weight": 50},
    {"code": 401, "message": "Token expired", "weight": 30},
    {"code": 403, "message": "Insufficient permissions", "weight": 15},
    {"code": 429, "message": "Rate limit exceeded", "weight": 5},
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


@app.post("/auth/login")
async def login():
    """Login endpoint."""
    request_id = f"req_{int(time.time() * 1000)}"

    if random.random() < ERROR_RATE:
        error = random.choices(AUTH_ERRORS, weights=[e["weight"] for e in AUTH_ERRORS])[
            0
        ]
        log_event(
            "error",
            error["message"],
            code=error["code"],
            request_id=request_id,
            endpoint="/auth/login",
        )
        raise HTTPException(status_code=error["code"], detail=error["message"])

    log_event(
        "info",
        "Login successful",
        code=200,
        request_id=request_id,
        endpoint="/auth/login",
    )
    return {"token": f"tok_{request_id}"}


@app.post("/auth/verify")
async def verify_token(authorization: str = Header(None)):
    """Token verification."""
    request_id = f"req_{int(time.time() * 1000)}"

    if not authorization or random.random() < ERROR_RATE * 1.5:
        error = random.choices(AUTH_ERRORS, weights=[e["weight"] for e in AUTH_ERRORS])[
            0
        ]
        log_event(
            "warn",
            error["message"],
            code=error["code"],
            request_id=request_id,
            endpoint="/auth/verify",
        )
        raise HTTPException(status_code=error["code"], detail=error["message"])

    log_event(
        "info",
        "Token verified",
        code=200,
        request_id=request_id,
        endpoint="/auth/verify",
    )
    return {"valid": True}


@app.post("/auth/refresh")
async def refresh_token():
    """Token refresh endpoint."""
    request_id = f"req_{int(time.time() * 1000)}"

    if random.random() < ERROR_RATE * 2:
        log_event(
            "warn",
            "Token refresh failed - expired",
            code=401,
            request_id=request_id,
            endpoint="/auth/refresh",
        )
        raise HTTPException(status_code=401, detail="Token expired")

    log_event(
        "info",
        "Token refreshed",
        code=200,
        request_id=request_id,
        endpoint="/auth/refresh",
    )
    return {"token": f"tok_{request_id}"}


if __name__ == "__main__":
    log_event("info", f"Service starting on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
