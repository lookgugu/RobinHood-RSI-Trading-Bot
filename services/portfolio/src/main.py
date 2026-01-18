"""
Portfolio Service - Position and P&L tracking.

This service handles:
- Current position tracking
- Transaction history
- Profit/loss calculations
- Portfolio summary
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis.asyncio as redis

from shared.models.trade import Trade, TradeType, TradeStatus, Position
from shared.messaging.subscriber import EventSubscriber
from shared.messaging.events import EventType
from shared.utils.logging import setup_logging

logger = setup_logging("portfolio", level="INFO", format_type="console")


class Settings(BaseModel):
    service_name: str = "portfolio"
    redis_url: str = "redis://redis:6379"
    database_url: str = "postgresql://postgres:postgres@postgres:5432/trading_bot"

    class Config:
        env_file = ".env"


settings = Settings()

redis_client: Optional[redis.Redis] = None

# In-memory storage for demo (use database in production)
positions: Dict[str, Position] = {}
transactions: List[Trade] = []
total_realized_pnl: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client

    logger.info("Starting Portfolio Service...")

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    logger.info("Portfolio Service started successfully")

    yield

    if redis_client:
        await redis_client.close()

    logger.info("Portfolio Service stopped")


app = FastAPI(
    title="Portfolio Service",
    description="Position and P&L tracking",
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


class PositionResponse(BaseModel):
    symbol: str
    quantity: int
    average_cost: float
    current_price: Optional[float]
    unrealized_pnl: Optional[float]
    unrealized_pnl_pct: Optional[float]


class PortfolioSummaryResponse(BaseModel):
    total_positions: int
    total_value: float
    total_cost: float
    unrealized_pnl: float
    realized_pnl: float
    positions: List[PositionResponse]


class TransactionResponse(BaseModel):
    id: Optional[str]
    trade_type: str
    symbol: str
    quantity: int
    price: float
    total_value: float
    timestamp: datetime
    profit_loss: Optional[float]


class UpdateRequest(BaseModel):
    type: str  # BUY or SELL
    symbol: str
    quantity: int
    price: float
    order_id: Optional[str] = None
    timestamp: Optional[str] = None


class UpdateResponse(BaseModel):
    success: bool
    message: str
    position: Optional[PositionResponse] = None


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", service="portfolio")


@app.get("/portfolio/positions")
async def get_positions():
    """Get all current positions."""
    return {
        "count": len(positions),
        "positions": [
            PositionResponse(
                symbol=p.symbol,
                quantity=p.quantity,
                average_cost=p.average_cost,
                current_price=p.current_price,
                unrealized_pnl=p.unrealized_pnl,
                unrealized_pnl_pct=p.unrealized_pnl_pct,
            )
            for p in positions.values()
            if p.quantity > 0
        ],
    }


@app.get("/portfolio/positions/{symbol}")
async def get_position(symbol: str):
    """Get position for a specific symbol."""
    symbol = symbol.upper()

    if symbol not in positions:
        return {
            "symbol": symbol,
            "quantity": 0,
            "average_cost": 0,
            "current_price": None,
            "unrealized_pnl": None,
            "has_position": False,
        }

    p = positions[symbol]
    return PositionResponse(
        symbol=p.symbol,
        quantity=p.quantity,
        average_cost=p.average_cost,
        current_price=p.current_price,
        unrealized_pnl=p.unrealized_pnl,
        unrealized_pnl_pct=p.unrealized_pnl_pct,
    )


@app.get("/portfolio/transactions")
async def get_transactions(limit: int = 50):
    """Get recent transactions."""
    recent = sorted(transactions, key=lambda t: t.timestamp, reverse=True)[:limit]

    return {
        "count": len(recent),
        "total_transactions": len(transactions),
        "transactions": [
            TransactionResponse(
                id=t.id,
                trade_type=t.trade_type.value,
                symbol=t.symbol,
                quantity=t.quantity,
                price=t.price,
                total_value=t.total_value,
                timestamp=t.timestamp,
                profit_loss=t.profit_loss,
            )
            for t in recent
        ],
    }


@app.get("/portfolio/pnl")
async def get_pnl():
    """Get profit/loss summary."""
    unrealized = sum(p.unrealized_pnl or 0 for p in positions.values())
    total_cost = sum(p.average_cost * p.quantity for p in positions.values())
    total_value = sum(
        (p.current_price or p.average_cost) * p.quantity for p in positions.values()
    )

    return {
        "realized_pnl": round(total_realized_pnl, 2),
        "unrealized_pnl": round(unrealized, 2),
        "total_pnl": round(total_realized_pnl + unrealized, 2),
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
    }


@app.get("/portfolio/summary", response_model=PortfolioSummaryResponse)
async def get_summary():
    """Get complete portfolio summary."""
    active_positions = [p for p in positions.values() if p.quantity > 0]
    unrealized = sum(p.unrealized_pnl or 0 for p in active_positions)
    total_cost = sum(p.average_cost * p.quantity for p in active_positions)
    total_value = sum(
        (p.current_price or p.average_cost) * p.quantity for p in active_positions
    )

    return PortfolioSummaryResponse(
        total_positions=len(active_positions),
        total_value=round(total_value, 2),
        total_cost=round(total_cost, 2),
        unrealized_pnl=round(unrealized, 2),
        realized_pnl=round(total_realized_pnl, 2),
        positions=[
            PositionResponse(
                symbol=p.symbol,
                quantity=p.quantity,
                average_cost=p.average_cost,
                current_price=p.current_price,
                unrealized_pnl=p.unrealized_pnl,
                unrealized_pnl_pct=p.unrealized_pnl_pct,
            )
            for p in active_positions
        ],
    )


@app.post("/portfolio/update", response_model=UpdateResponse)
async def update_portfolio(request: UpdateRequest):
    """
    Update portfolio with a new trade.

    Handles both BUY and SELL transactions.
    """
    global total_realized_pnl

    symbol = request.symbol.upper()
    timestamp = (
        datetime.fromisoformat(request.timestamp)
        if request.timestamp
        else datetime.utcnow()
    )

    logger.info(f"Portfolio update: {request.type} {request.quantity} {symbol} @ ${request.price}")

    if request.type == "BUY":
        # Add to position
        if symbol in positions:
            # Average up/down
            existing = positions[symbol]
            total_qty = existing.quantity + request.quantity
            total_cost = (existing.average_cost * existing.quantity) + (
                request.price * request.quantity
            )
            new_avg = total_cost / total_qty

            positions[symbol] = Position(
                symbol=symbol,
                quantity=total_qty,
                average_cost=round(new_avg, 4),
                current_price=request.price,
                opened_at=existing.opened_at,
            )
        else:
            # New position
            positions[symbol] = Position(
                symbol=symbol,
                quantity=request.quantity,
                average_cost=request.price,
                current_price=request.price,
                opened_at=timestamp,
            )

        # Record transaction
        trade = Trade(
            id=request.order_id,
            trade_type=TradeType.BUY,
            symbol=symbol,
            quantity=request.quantity,
            price=request.price,
            total_value=request.quantity * request.price,
            timestamp=timestamp,
            status=TradeStatus.EXECUTED,
        )
        transactions.append(trade)

        pos = positions[symbol]
        return UpdateResponse(
            success=True,
            message=f"Bought {request.quantity} {symbol}",
            position=PositionResponse(
                symbol=pos.symbol,
                quantity=pos.quantity,
                average_cost=pos.average_cost,
                current_price=pos.current_price,
                unrealized_pnl=pos.unrealized_pnl,
                unrealized_pnl_pct=pos.unrealized_pnl_pct,
            ),
        )

    elif request.type == "SELL":
        if symbol not in positions or positions[symbol].quantity < request.quantity:
            return UpdateResponse(
                success=False,
                message=f"Insufficient position in {symbol}",
            )

        existing = positions[symbol]
        profit_loss = (request.price - existing.average_cost) * request.quantity
        profit_loss_pct = ((request.price - existing.average_cost) / existing.average_cost) * 100

        # Update position
        new_qty = existing.quantity - request.quantity
        if new_qty > 0:
            positions[symbol] = Position(
                symbol=symbol,
                quantity=new_qty,
                average_cost=existing.average_cost,
                current_price=request.price,
                opened_at=existing.opened_at,
            )
        else:
            # Position closed
            del positions[symbol]

        # Update realized P&L
        total_realized_pnl += profit_loss

        # Record transaction
        trade = Trade(
            id=request.order_id,
            trade_type=TradeType.SELL,
            symbol=symbol,
            quantity=request.quantity,
            price=request.price,
            total_value=request.quantity * request.price,
            timestamp=timestamp,
            status=TradeStatus.EXECUTED,
            profit_loss=round(profit_loss, 2),
            profit_loss_pct=round(profit_loss_pct, 4),
        )
        transactions.append(trade)

        logger.info(f"Sold {request.quantity} {symbol} P/L: ${profit_loss:.2f} ({profit_loss_pct:.2f}%)")

        return UpdateResponse(
            success=True,
            message=f"Sold {request.quantity} {symbol} (P/L: ${profit_loss:.2f})",
            position=PositionResponse(
                symbol=symbol,
                quantity=new_qty,
                average_cost=existing.average_cost if new_qty > 0 else 0,
                current_price=request.price,
                unrealized_pnl=None,
                unrealized_pnl_pct=None,
            ) if new_qty > 0 else None,
        )

    return UpdateResponse(success=False, message=f"Unknown trade type: {request.type}")


@app.post("/portfolio/update-price/{symbol}")
async def update_price(symbol: str, price: float):
    """Update current price for a position."""
    symbol = symbol.upper()

    if symbol not in positions:
        raise HTTPException(status_code=404, detail=f"No position in {symbol}")

    pos = positions[symbol]
    pos.update_pnl(price)

    return {
        "symbol": symbol,
        "current_price": price,
        "unrealized_pnl": pos.unrealized_pnl,
        "unrealized_pnl_pct": pos.unrealized_pnl_pct,
    }


@app.delete("/portfolio/reset")
async def reset_portfolio():
    """Reset portfolio (for testing purposes)."""
    global positions, transactions, total_realized_pnl
    positions = {}
    transactions = []
    total_realized_pnl = 0.0
    logger.info("Portfolio reset")
    return {"success": True, "message": "Portfolio reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
