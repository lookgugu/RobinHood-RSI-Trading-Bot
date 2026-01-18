"""
Compliance Service - PDT tracking and regulatory compliance.

This service handles:
- Pattern Day Trader (PDT) rule tracking
- Day trade counting
- Trade recording for compliance
- Regulatory checks
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis.asyncio as redis

from shared.models.trade import DayTrade
from shared.utils.logging import setup_logging

logger = setup_logging("compliance", level="INFO", format_type="console")


class Settings(BaseModel):
    service_name: str = "compliance"
    redis_url: str = "redis://redis:6379"
    database_url: str = "postgresql://postgres:postgres@postgres:5432/trading_bot"
    pdt_tracking_days: int = 5
    max_day_trades: int = 3

    class Config:
        env_file = ".env"


settings = Settings()

redis_client: Optional[redis.Redis] = None

# In-memory storage for demo (use database in production)
day_trades: List[DayTrade] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client

    logger.info("Starting Compliance Service...")
    logger.info(f"PDT tracking: {settings.pdt_tracking_days} days")
    logger.info(f"Max day trades: {settings.max_day_trades}")

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    logger.info("Compliance Service started successfully")

    yield

    if redis_client:
        await redis_client.close()

    logger.info("Compliance Service stopped")


app = FastAPI(
    title="Compliance Service",
    description="PDT tracking and regulatory compliance",
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


class PDTStatusResponse(BaseModel):
    day_trades_count: int
    max_day_trades: int
    remaining_day_trades: int
    tracking_period_days: int
    can_day_trade: bool
    trades_by_date: dict


class CanTradeRequest(BaseModel):
    symbol: str
    side: str
    is_day_trade: bool = False


class CanTradeResponse(BaseModel):
    can_trade: bool
    reason: str = ""
    day_trades_count: int
    remaining_day_trades: int


class RecordTradeRequest(BaseModel):
    symbol: str
    buy_time: datetime
    sell_time: datetime
    quantity: int
    buy_price: float
    sell_price: float


class RecordTradeResponse(BaseModel):
    success: bool
    message: str
    is_day_trade: bool
    day_trades_count: int


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", service="compliance")


def get_recent_day_trades() -> List[DayTrade]:
    """Get day trades from the last N tracking days."""
    cutoff_date = date.today() - timedelta(days=settings.pdt_tracking_days)
    return [
        trade for trade in day_trades
        if datetime.strptime(trade.date, "%Y-%m-%d").date() >= cutoff_date
    ]


def count_day_trades() -> int:
    """Count day trades in the tracking period."""
    return len(get_recent_day_trades())


def get_trades_by_date() -> dict:
    """Group day trades by date."""
    recent = get_recent_day_trades()
    by_date = {}
    for trade in recent:
        if trade.date not in by_date:
            by_date[trade.date] = 0
        by_date[trade.date] += 1
    return by_date


@app.get("/compliance/pdt-status", response_model=PDTStatusResponse)
async def get_pdt_status():
    """
    Get current PDT (Pattern Day Trader) status.

    Returns the number of day trades in the tracking period and remaining allowance.
    """
    count = count_day_trades()
    remaining = max(0, settings.max_day_trades - count)

    return PDTStatusResponse(
        day_trades_count=count,
        max_day_trades=settings.max_day_trades,
        remaining_day_trades=remaining,
        tracking_period_days=settings.pdt_tracking_days,
        can_day_trade=remaining > 0,
        trades_by_date=get_trades_by_date(),
    )


@app.post("/compliance/can-trade", response_model=CanTradeResponse)
async def can_trade(request: CanTradeRequest):
    """
    Check if a trade can be made without violating PDT rules.

    For SELL orders that would result in a day trade, checks the limit.
    """
    count = count_day_trades()
    remaining = max(0, settings.max_day_trades - count)

    # BUY orders don't trigger PDT by themselves
    if request.side == "BUY":
        return CanTradeResponse(
            can_trade=True,
            reason="Buy orders are allowed",
            day_trades_count=count,
            remaining_day_trades=remaining,
        )

    # SELL orders that are day trades need PDT check
    if request.is_day_trade:
        if remaining <= 0:
            logger.warning(f"PDT limit reached: {count} day trades in tracking period")
            return CanTradeResponse(
                can_trade=False,
                reason=f"PDT limit reached: {count}/{settings.max_day_trades} day trades used",
                day_trades_count=count,
                remaining_day_trades=0,
            )

    return CanTradeResponse(
        can_trade=True,
        reason="Trade allowed",
        day_trades_count=count,
        remaining_day_trades=remaining,
    )


@app.post("/compliance/record-trade", response_model=RecordTradeResponse)
async def record_trade(request: RecordTradeRequest):
    """
    Record a completed trade for compliance tracking.

    If the buy and sell occur on the same day, it's recorded as a day trade.
    """
    buy_date = request.buy_time.date()
    sell_date = request.sell_time.date()

    is_day_trade = buy_date == sell_date

    if is_day_trade:
        trade = DayTrade(
            symbol=request.symbol,
            trade_date=sell_date.isoformat(),
            date=sell_date.isoformat(),
            buy_time=request.buy_time,
            sell_time=request.sell_time,
            quantity=request.quantity,
            buy_price=request.buy_price,
            sell_price=request.sell_price,
            profit_loss=(request.sell_price - request.buy_price) * request.quantity,
        )
        day_trades.append(trade)
        logger.info(f"Recorded day trade for {request.symbol}")

    count = count_day_trades()

    return RecordTradeResponse(
        success=True,
        message="Trade recorded" + (" as day trade" if is_day_trade else ""),
        is_day_trade=is_day_trade,
        day_trades_count=count,
    )


@app.get("/compliance/day-trades")
async def list_day_trades():
    """List all day trades in the tracking period."""
    recent = get_recent_day_trades()
    return {
        "count": len(recent),
        "tracking_days": settings.pdt_tracking_days,
        "trades": [
            {
                "symbol": t.symbol,
                "date": t.date,
                "quantity": t.quantity,
                "buy_price": t.buy_price,
                "sell_price": t.sell_price,
                "profit_loss": t.profit_loss,
            }
            for t in recent
        ],
    }


@app.delete("/compliance/reset")
async def reset_day_trades():
    """Reset day trade tracking (for testing purposes)."""
    global day_trades
    day_trades = []
    logger.info("Day trade tracking reset")
    return {"success": True, "message": "Day trade tracking reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
