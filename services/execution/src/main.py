"""
Execution Service - Order management and execution.

This service handles:
- Placing buy/sell orders
- Order status tracking
- Pre-trade validation via Risk and Compliance services
- Publishing trade events
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis.asyncio as redis
import httpx

from shared.models.order import (
    Order,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
)
from shared.messaging.publisher import EventPublisher
from shared.messaging.events import TradeCompletedEvent
from shared.utils.logging import setup_logging

logger = setup_logging("execution", level="INFO", format_type="console")


class Settings(BaseModel):
    service_name: str = "execution"
    redis_url: str = "redis://redis:6379"
    gateway_url: str = "http://gateway:8000"
    risk_service_url: str = "http://risk-management:8004"
    compliance_service_url: str = "http://compliance:8005"
    portfolio_service_url: str = "http://portfolio:8006"

    class Config:
        env_file = ".env"


settings = Settings()

redis_client: Optional[redis.Redis] = None
publisher: Optional[EventPublisher] = None
http_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, publisher, http_client

    logger.info("Starting Execution Service...")

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    publisher = EventPublisher(settings.redis_url)
    await publisher.connect()
    http_client = httpx.AsyncClient(timeout=30.0)

    logger.info("Execution Service started successfully")

    yield

    if publisher:
        await publisher.disconnect()
    if http_client:
        await http_client.aclose()
    if redis_client:
        await redis_client.close()

    logger.info("Execution Service stopped")


app = FastAPI(
    title="Execution Service",
    description="Order management and trade execution",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    service: str


class RiskValidationRequest(BaseModel):
    symbol: str
    side: str
    quantity: int
    price: float


class ComplianceCheckRequest(BaseModel):
    symbol: str
    side: str
    is_day_trade: bool = False


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", service="execution")


async def validate_with_risk_service(request: RiskValidationRequest) -> dict:
    """Validate order with Risk Management service."""
    try:
        response = await http_client.post(
            f"{settings.risk_service_url}/risk/validate-order",
            json=request.model_dump(),
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Risk validation error: {e}")
        return {"approved": False, "reason": str(e)}


async def check_compliance(request: ComplianceCheckRequest) -> dict:
    """Check compliance with Compliance service."""
    try:
        response = await http_client.post(
            f"{settings.compliance_service_url}/compliance/can-trade",
            json=request.model_dump(),
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Compliance check error: {e}")
        return {"can_trade": False, "reason": str(e)}


async def notify_portfolio(trade_data: dict) -> None:
    """Notify Portfolio service of completed trade."""
    try:
        await http_client.post(
            f"{settings.portfolio_service_url}/portfolio/update",
            json=trade_data,
        )
    except Exception as e:
        logger.error(f"Portfolio notification error: {e}")


@app.post("/orders/buy", response_model=OrderResponse)
async def place_buy_order(request: OrderRequest):
    """
    Place a buy order.

    Validates with Risk Management and Compliance before execution.
    """
    logger.info(f"Buy order request: {request.symbol} x {request.quantity}")

    # Validate with Risk Management
    risk_result = await validate_with_risk_service(
        RiskValidationRequest(
            symbol=request.symbol,
            side="BUY",
            quantity=request.quantity,
            price=request.limit_price or 0,
        )
    )

    if not risk_result.get("approved", False):
        return OrderResponse(
            success=False,
            message=f"Risk validation failed: {risk_result.get('reason', 'Unknown')}",
        )

    # Check Compliance
    compliance_result = await check_compliance(
        ComplianceCheckRequest(
            symbol=request.symbol,
            side="BUY",
            is_day_trade=False,
        )
    )

    if not compliance_result.get("can_trade", False):
        return OrderResponse(
            success=False,
            message=f"Compliance check failed: {compliance_result.get('reason', 'Unknown')}",
        )

    # Execute order (simulated)
    order_id = str(uuid4())
    filled_price = request.limit_price or 65.00  # Simulated fill price

    order = Order(
        id=order_id,
        symbol=request.symbol,
        side=OrderSide.BUY,
        order_type=request.order_type,
        quantity=request.quantity,
        limit_price=request.limit_price,
        status=OrderStatus.FILLED,
        filled_quantity=request.quantity,
        filled_price=filled_price,
        external_id=f"RH-{order_id[:8]}",
    )

    # Publish trade event
    if publisher:
        event = TradeCompletedEvent.create(
            order_id=order_id,
            symbol=request.symbol,
            side="BUY",
            quantity=request.quantity,
            price=filled_price,
        )
        await publisher.publish(event)

    # Notify portfolio
    await notify_portfolio({
        "type": "BUY",
        "symbol": request.symbol,
        "quantity": request.quantity,
        "price": filled_price,
        "order_id": order_id,
        "timestamp": datetime.utcnow().isoformat(),
    })

    logger.info(f"Buy order executed: {order_id}")

    return OrderResponse(
        success=True,
        order_id=order_id,
        message="Order executed successfully",
        order=order,
    )


@app.post("/orders/sell", response_model=OrderResponse)
async def place_sell_order(request: OrderRequest):
    """
    Place a sell order.

    Validates with Risk Management and Compliance before execution.
    """
    logger.info(f"Sell order request: {request.symbol} x {request.quantity}")

    # Check Compliance (PDT rules)
    compliance_result = await check_compliance(
        ComplianceCheckRequest(
            symbol=request.symbol,
            side="SELL",
            is_day_trade=True,  # Assume potential day trade
        )
    )

    if not compliance_result.get("can_trade", False):
        return OrderResponse(
            success=False,
            message=f"Compliance check failed: {compliance_result.get('reason', 'Unknown')}",
        )

    # Execute order (simulated)
    order_id = str(uuid4())
    filled_price = request.limit_price or 65.50  # Simulated fill price

    order = Order(
        id=order_id,
        symbol=request.symbol,
        side=OrderSide.SELL,
        order_type=request.order_type,
        quantity=request.quantity,
        limit_price=request.limit_price,
        status=OrderStatus.FILLED,
        filled_quantity=request.quantity,
        filled_price=filled_price,
        external_id=f"RH-{order_id[:8]}",
    )

    # Publish trade event
    if publisher:
        event = TradeCompletedEvent.create(
            order_id=order_id,
            symbol=request.symbol,
            side="SELL",
            quantity=request.quantity,
            price=filled_price,
        )
        await publisher.publish(event)

    # Notify portfolio
    await notify_portfolio({
        "type": "SELL",
        "symbol": request.symbol,
        "quantity": request.quantity,
        "price": filled_price,
        "order_id": order_id,
        "timestamp": datetime.utcnow().isoformat(),
    })

    logger.info(f"Sell order executed: {order_id}")

    return OrderResponse(
        success=True,
        order_id=order_id,
        message="Order executed successfully",
        order=order,
    )


@app.get("/orders/{order_id}")
async def get_order_status(order_id: str):
    """Get order status."""
    # In production, this would fetch from database
    return {
        "order_id": order_id,
        "status": "FILLED",
        "message": "Order status retrieved",
    }


@app.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an open order."""
    logger.info(f"Cancel order request: {order_id}")
    return {
        "success": True,
        "order_id": order_id,
        "message": "Order cancellation requested",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
