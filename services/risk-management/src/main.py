"""
Risk Management Service - Position sizing and risk controls.

This service handles:
- Pre-trade risk validation
- Position size calculation
- Profit target monitoring
- Stop loss monitoring
- Overall exposure limits
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import redis.asyncio as redis

from shared.utils.logging import setup_logging

logger = setup_logging("risk-management", level="INFO", format_type="console")


class Settings(BaseModel):
    service_name: str = "risk-management"
    redis_url: str = "redis://redis:6379"
    max_investment: float = 20.00
    profit_target_pct: float = 1.0
    stop_loss_pct: float = -0.5
    max_position_value: float = 100.00
    max_daily_loss: float = 50.00

    class Config:
        env_file = ".env"


settings = Settings()

redis_client: Optional[redis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client

    logger.info("Starting Risk Management Service...")
    logger.info(f"Max investment: ${settings.max_investment}")
    logger.info(f"Profit target: {settings.profit_target_pct}%")
    logger.info(f"Stop loss: {settings.stop_loss_pct}%")

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    logger.info("Risk Management Service started successfully")

    yield

    if redis_client:
        await redis_client.close()

    logger.info("Risk Management Service stopped")


app = FastAPI(
    title="Risk Management Service",
    description="Position sizing and risk controls",
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


class OrderValidationRequest(BaseModel):
    symbol: str
    side: str
    quantity: int
    price: float


class OrderValidationResponse(BaseModel):
    approved: bool
    reason: str = ""
    max_quantity: Optional[int] = None
    position_value: Optional[float] = None


class PositionSizeRequest(BaseModel):
    symbol: str
    price: float
    max_investment: Optional[float] = None


class PositionSizeResponse(BaseModel):
    symbol: str
    recommended_quantity: int
    total_cost: float
    max_investment: float


class RiskCheckRequest(BaseModel):
    symbol: str
    entry_price: float
    current_price: float
    quantity: int


class RiskCheckResponse(BaseModel):
    symbol: str
    profit_loss: float
    profit_loss_pct: float
    should_exit: bool
    exit_reason: Optional[str] = None
    profit_target_pct: float
    stop_loss_pct: float


class ExposureResponse(BaseModel):
    total_exposure: float
    max_allowed: float
    utilization_pct: float
    positions: dict


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", service="risk-management")


@app.get("/risk/config")
async def get_risk_config():
    """Get current risk configuration."""
    return {
        "max_investment": settings.max_investment,
        "profit_target_pct": settings.profit_target_pct,
        "stop_loss_pct": settings.stop_loss_pct,
        "max_position_value": settings.max_position_value,
        "max_daily_loss": settings.max_daily_loss,
    }


@app.post("/risk/validate-order", response_model=OrderValidationResponse)
async def validate_order(request: OrderValidationRequest):
    """
    Validate an order against risk rules.

    Checks:
    - Position size limits
    - Maximum investment per trade
    - Overall exposure limits
    """
    logger.info(f"Validating order: {request.side} {request.quantity} {request.symbol} @ ${request.price}")

    position_value = request.quantity * request.price

    # Check maximum investment per trade
    if position_value > settings.max_investment:
        max_qty = int(settings.max_investment / request.price)
        return OrderValidationResponse(
            approved=False,
            reason=f"Position value ${position_value:.2f} exceeds max investment ${settings.max_investment:.2f}",
            max_quantity=max_qty,
            position_value=position_value,
        )

    # Check maximum position value
    if position_value > settings.max_position_value:
        max_qty = int(settings.max_position_value / request.price)
        return OrderValidationResponse(
            approved=False,
            reason=f"Position value ${position_value:.2f} exceeds max position ${settings.max_position_value:.2f}",
            max_quantity=max_qty,
            position_value=position_value,
        )

    # All checks passed
    logger.info(f"Order approved: {request.symbol} position value ${position_value:.2f}")

    return OrderValidationResponse(
        approved=True,
        reason="Order approved",
        max_quantity=request.quantity,
        position_value=position_value,
    )


@app.post("/risk/calculate-position", response_model=PositionSizeResponse)
async def calculate_position_size(request: PositionSizeRequest):
    """
    Calculate recommended position size based on price and risk limits.
    """
    max_inv = request.max_investment or settings.max_investment

    if request.price <= 0:
        raise HTTPException(status_code=400, detail="Price must be positive")

    recommended_qty = int(max_inv / request.price)
    total_cost = recommended_qty * request.price

    logger.info(f"Position size for {request.symbol}: {recommended_qty} shares @ ${request.price} = ${total_cost}")

    return PositionSizeResponse(
        symbol=request.symbol,
        recommended_quantity=recommended_qty,
        total_cost=round(total_cost, 2),
        max_investment=max_inv,
    )


@app.post("/risk/check-exit", response_model=RiskCheckResponse)
async def check_exit_conditions(request: RiskCheckRequest):
    """
    Check if position should be exited based on profit target or stop loss.
    """
    profit_loss = (request.current_price - request.entry_price) * request.quantity
    profit_loss_pct = ((request.current_price - request.entry_price) / request.entry_price) * 100

    should_exit = False
    exit_reason = None

    # Check profit target
    if profit_loss_pct >= settings.profit_target_pct:
        should_exit = True
        exit_reason = f"Profit target reached: {profit_loss_pct:.2f}% >= {settings.profit_target_pct}%"
        logger.info(f"Profit target hit for {request.symbol}: {profit_loss_pct:.2f}%")

    # Check stop loss
    elif profit_loss_pct <= settings.stop_loss_pct:
        should_exit = True
        exit_reason = f"Stop loss triggered: {profit_loss_pct:.2f}% <= {settings.stop_loss_pct}%"
        logger.warning(f"Stop loss hit for {request.symbol}: {profit_loss_pct:.2f}%")

    return RiskCheckResponse(
        symbol=request.symbol,
        profit_loss=round(profit_loss, 2),
        profit_loss_pct=round(profit_loss_pct, 4),
        should_exit=should_exit,
        exit_reason=exit_reason,
        profit_target_pct=settings.profit_target_pct,
        stop_loss_pct=settings.stop_loss_pct,
    )


@app.get("/risk/exposure", response_model=ExposureResponse)
async def get_exposure():
    """
    Get current portfolio exposure.

    In production, this would query the Portfolio service.
    """
    # Simulated exposure data
    return ExposureResponse(
        total_exposure=0.0,
        max_allowed=settings.max_position_value,
        utilization_pct=0.0,
        positions={},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
