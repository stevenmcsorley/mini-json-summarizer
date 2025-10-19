"""
E-Commerce Backend API with Intentional Errors
Demonstrates realistic error scenarios for monitoring
"""

import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fluent import sender
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fluentd logger
fluent_logger = sender.FluentSender("ecommerce", host="fluentd", port=24224)

app = FastAPI(title="TechStore API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error rates (configurable)
CART_ERROR_RATE = float(os.getenv("CART_ERROR_RATE", "0.30"))  # 30% failure
CHECKOUT_ERROR_RATE = float(os.getenv("CHECKOUT_ERROR_RATE", "0.40"))  # 40% failure


# Request models
class AddToCartRequest(BaseModel):
    product_id: int
    quantity: int = 1


class CheckoutRequest(BaseModel):
    items: list
    total: float
    payment_method: str


def log_to_fluentd(level: str, message: str, **kwargs):
    """Send structured log to Fluentd"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "service": "ecommerce-api",
        "message": message,
        **kwargs,
    }
    fluent_logger.emit("log", log_entry)
    return log_entry


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ecommerce-api"}


@app.post("/api/cart/add")
async def add_to_cart(request: AddToCartRequest):
    """
    Add item to cart - intentionally fails sometimes
    Simulates: inventory errors, database timeouts, validation failures
    """
    request_id = f"cart_{int(time.time() * 1000)}"

    # Randomly fail to simulate real-world errors
    if random.random() < CART_ERROR_RATE:
        error_scenarios = [
            {
                "code": 500,
                "message": "Database connection timeout",
                "error_type": "database_error",
            },
            {
                "code": 409,
                "message": "Product out of stock",
                "error_type": "inventory_error",
            },
            {
                "code": 400,
                "message": "Invalid product ID",
                "error_type": "validation_error",
            },
            {
                "code": 503,
                "message": "Cart service unavailable",
                "error_type": "service_error",
            },
        ]

        error = random.choice(error_scenarios)

        log_to_fluentd(
            level="error",
            message=error["message"],
            code=error["code"],
            error_type=error["error_type"],
            request_id=request_id,
            endpoint="/api/cart/add",
            product_id=request.product_id,
            quantity=request.quantity,
        )

        raise HTTPException(
            status_code=error["code"], detail={"message": error["message"]}
        )

    # Success case
    log_to_fluentd(
        level="info",
        message="Item added to cart successfully",
        code=200,
        request_id=request_id,
        endpoint="/api/cart/add",
        product_id=request.product_id,
        quantity=request.quantity,
    )

    return {"status": "success", "request_id": request_id}


@app.post("/api/checkout")
async def checkout(request: CheckoutRequest):
    """
    Process checkout - intentionally fails frequently
    Simulates: payment failures, inventory issues, fraud detection
    """
    request_id = f"checkout_{int(time.time() * 1000)}"
    order_id = f"ORD-{random.randint(10000, 99999)}"

    # Higher failure rate for checkout (more critical operation)
    if random.random() < CHECKOUT_ERROR_RATE:
        error_scenarios = [
            {
                "code": 402,
                "message": "Payment processing failed",
                "error_type": "payment_error",
            },
            {
                "code": 409,
                "message": "Items no longer available",
                "error_type": "inventory_error",
            },
            {
                "code": 403,
                "message": "Transaction blocked by fraud detection",
                "error_type": "fraud_detection",
            },
            {
                "code": 504,
                "message": "Payment gateway timeout",
                "error_type": "gateway_timeout",
            },
            {
                "code": 500,
                "message": "Internal server error during checkout",
                "error_type": "server_error",
            },
        ]

        error = random.choice(error_scenarios)

        log_to_fluentd(
            level="error",
            message=error["message"],
            code=error["code"],
            error_type=error["error_type"],
            request_id=request_id,
            order_id=order_id,
            endpoint="/api/checkout",
            total=request.total,
            payment_method=request.payment_method,
            items_count=len(request.items),
        )

        raise HTTPException(
            status_code=error["code"], detail={"message": error["message"]}
        )

    # Success case
    log_to_fluentd(
        level="info",
        message="Checkout completed successfully",
        code=200,
        request_id=request_id,
        order_id=order_id,
        endpoint="/api/checkout",
        total=request.total,
        payment_method=request.payment_method,
        items_count=len(request.items),
    )

    return {"status": "success", "order_id": order_id, "total": request.total}


@app.get("/api/products")
async def get_products():
    """Get product list - rarely fails"""
    request_id = f"products_{int(time.time() * 1000)}"

    # 5% failure rate
    if random.random() < 0.05:
        log_to_fluentd(
            level="error",
            message="Failed to fetch products",
            code=500,
            request_id=request_id,
            endpoint="/api/products",
        )
        raise HTTPException(status_code=500, detail={"message": "Database error"})

    log_to_fluentd(
        level="info",
        message="Products fetched successfully",
        code=200,
        request_id=request_id,
        endpoint="/api/products",
    )

    return {"status": "success", "count": 8}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
