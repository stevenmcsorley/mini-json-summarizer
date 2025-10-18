"""Demo API service that generates realistic error logs."""
import os
import random
import time
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fluent import sender
import uvicorn

app = FastAPI()

SERVICE_NAME = os.getenv("SERVICE_NAME", "api")
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.15"))
PORT = int(os.getenv("PORT", "8081"))

# Fluentd logger
fluent_logger = sender.FluentSender("app", host="fluentd", port=24224)

# Error scenarios
ERROR_SCENARIOS = [
    {"code": 504, "message": "Gateway timeout", "weight": 40},
    {"code": 500, "message": "Internal server error", "weight": 25},
    {"code": 401, "message": "Unauthorized", "weight": 15},
    {"code": 429, "message": "Rate limit exceeded", "weight": 10},
    {"code": 503, "message": "Service unavailable", "weight": 10},
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

    # Send to Fluentd
    fluent_logger.emit("log", log_entry)

    # Also print for docker logs
    print(json.dumps(log_entry), flush=True)


def should_error():
    """Determine if this request should error."""
    return random.random() < ERROR_RATE


def select_error():
    """Weighted random error selection."""
    weights = [s["weight"] for s in ERROR_SCENARIOS]
    return random.choices(ERROR_SCENARIOS, weights=weights)[0]


@app.get("/")
async def root():
    """Health check endpoint."""
    log_event("info", "Health check")
    return {"status": "healthy", "service": SERVICE_NAME}


@app.get("/api/users")
async def get_users():
    """Simulated API endpoint with realistic errors."""
    request_id = f"req_{int(time.time() * 1000)}"

    if should_error():
        error = select_error()
        log_event(
            "error",
            error["message"],
            code=error["code"],
            request_id=request_id,
            endpoint="/api/users",
        )
        raise HTTPException(status_code=error["code"], detail=error["message"])

    log_event(
        "info",
        "Users fetched successfully",
        code=200,
        request_id=request_id,
        endpoint="/api/users",
        user_count=random.randint(10, 50),
    )

    return {"users": [], "count": 0}


@app.post("/api/orders")
async def create_order():
    """Order creation endpoint."""
    request_id = f"req_{int(time.time() * 1000)}"

    # Higher error rate for order creation
    if random.random() < ERROR_RATE * 1.5:
        error = select_error()
        log_event(
            "error",
            error["message"],
            code=error["code"],
            request_id=request_id,
            endpoint="/api/orders",
        )
        raise HTTPException(status_code=error["code"], detail=error["message"])

    log_event(
        "info",
        "Order created",
        code=201,
        request_id=request_id,
        endpoint="/api/orders",
        order_total=round(random.uniform(10, 500), 2),
    )

    return {"order_id": request_id, "status": "created"}


@app.get("/api/products/{product_id}")
async def get_product(product_id: int):
    """Product detail endpoint."""
    request_id = f"req_{int(time.time() * 1000)}"

    if should_error():
        error = select_error()
        log_event(
            "error",
            error["message"],
            code=error["code"],
            request_id=request_id,
            endpoint=f"/api/products/{product_id}",
            product_id=product_id,
        )
        raise HTTPException(status_code=error["code"], detail=error["message"])

    log_event(
        "info",
        "Product retrieved",
        code=200,
        request_id=request_id,
        endpoint=f"/api/products/{product_id}",
        product_id=product_id,
    )

    return {"product_id": product_id, "name": f"Product {product_id}"}


if __name__ == "__main__":
    log_event("info", f"Service starting on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
