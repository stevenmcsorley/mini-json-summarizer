"""
Auto Traffic Generator for E-Commerce Demo
Continuously generates realistic traffic to create monitoring data
"""
import asyncio
import random
import httpx
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE = "http://ecommerce-api:8000"

PRODUCTS = [1, 2, 3, 4, 5, 6, 7, 8]
PAYMENT_METHODS = ["credit_card", "paypal", "debit_card"]


async def add_to_cart():
    """Add random product to cart - triggers errors 30% of the time"""
    product_id = random.choice(PRODUCTS)
    quantity = random.randint(1, 3)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/api/cart/add",
                json={"product_id": product_id, "quantity": quantity},
                timeout=10.0
            )
            status = response.status_code
            logger.info(f"Cart add: product={product_id}, status={status}")
            return status == 200
    except Exception as e:
        logger.error(f"Cart add failed: {e}")
        return False


async def checkout():
    """Checkout with random items - triggers errors 40% of the time"""
    items_count = random.randint(3, 10)
    total = round(random.uniform(50, 500), 2)
    payment_method = random.choice(PAYMENT_METHODS)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/api/checkout",
                json={
                    "items": [{"id": i, "qty": 1} for i in range(items_count)],
                    "total": total,
                    "payment_method": payment_method
                },
                timeout=10.0
            )
            status = response.status_code
            logger.info(f"Checkout: items={items_count}, total=${total}, status={status}")
            return status == 200
    except Exception as e:
        logger.error(f"Checkout failed: {e}")
        return False


async def traffic_loop():
    """Main traffic generation loop"""
    logger.info("🚀 Traffic generator started")

    while True:
        try:
            # Generate 3-7 cart operations
            cart_ops = random.randint(3, 7)
            for _ in range(cart_ops):
                await add_to_cart()
                await asyncio.sleep(random.uniform(0.5, 2.0))

            # Then do a checkout
            await checkout()

            # Wait before next batch
            await asyncio.sleep(random.uniform(2.0, 5.0))

        except KeyboardInterrupt:
            logger.info("Traffic generator stopped")
            break
        except Exception as e:
            logger.error(f"Traffic loop error: {e}")
            await asyncio.sleep(5.0)


if __name__ == "__main__":
    asyncio.run(traffic_loop())
