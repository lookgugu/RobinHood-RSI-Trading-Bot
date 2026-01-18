"""
Strategy Engine Service - Calculates trading signals.

This service handles:
- RSI indicator calculation and signal generation
- MACD indicator calculation and signal generation
- Strategy configuration
- Signal publishing
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis.asyncio as redis
import httpx

from .strategies.rsi import RSIStrategy
from .strategies.macd import MACDStrategy
from .strategies.base import BaseStrategy
from shared.models.signal import (
    Signal,
    SignalAction,
    StrategyType,
    SignalRequest,
    SignalResponse,
)
from shared.messaging.publisher import EventPublisher
from shared.messaging.events import SignalGeneratedEvent
from shared.utils.logging import setup_logging

# Setup logging
logger = setup_logging("strategy-engine", level="INFO", format_type="console")


class Settings(BaseModel):
    """Strategy Engine service settings."""

    service_name: str = "strategy-engine"
    redis_url: str = "redis://redis:6379"
    market_data_url: str = "http://market-data:8001"
    default_symbol: str = "TQQQ"

    # RSI settings
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0

    # MACD settings
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    class Config:
        env_file = ".env"


settings = Settings()

# Global instances
redis_client: Optional[redis.Redis] = None
publisher: Optional[EventPublisher] = None
http_client: Optional[httpx.AsyncClient] = None
strategies: Dict[str, BaseStrategy] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global redis_client, publisher, http_client, strategies

    logger.info("Starting Strategy Engine Service...")

    # Initialize Redis
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    # Initialize event publisher
    publisher = EventPublisher(settings.redis_url)
    await publisher.connect()

    # Initialize HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)

    # Initialize strategies
    strategies["RSI"] = RSIStrategy(
        period=settings.rsi_period,
        oversold=settings.rsi_oversold,
        overbought=settings.rsi_overbought,
    )
    strategies["MACD"] = MACDStrategy(
        fast_period=settings.macd_fast,
        slow_period=settings.macd_slow,
        signal_period=settings.macd_signal,
    )

    logger.info("Strategy Engine Service started successfully")
    logger.info(f"Available strategies: {list(strategies.keys())}")

    yield

    # Cleanup
    if publisher:
        await publisher.disconnect()
    if http_client:
        await http_client.aclose()
    if redis_client:
        await redis_client.close()

    logger.info("Strategy Engine Service stopped")


app = FastAPI(
    title="Strategy Engine Service",
    description="Calculates trading signals using technical indicators",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Response models
class HealthResponse(BaseModel):
    status: str
    service: str
    strategies_loaded: int


class StrategyListResponse(BaseModel):
    strategies: list
    default_symbol: str


class IndicatorResponse(BaseModel):
    success: bool
    symbol: str
    indicator: str
    values: Dict[str, Any]


# Health check
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health."""
    return HealthResponse(
        status="healthy",
        service="strategy-engine",
        strategies_loaded=len(strategies),
    )


# Strategy list
@app.get("/strategies", response_model=StrategyListResponse)
async def list_strategies():
    """List available strategies."""
    return StrategyListResponse(
        strategies=list(strategies.keys()),
        default_symbol=settings.default_symbol,
    )


async def fetch_price_data(symbol: str, bars: int = 100) -> list:
    """Fetch price data from Market Data service."""
    if http_client is None:
        raise HTTPException(status_code=500, detail="HTTP client not initialized")

    try:
        response = await http_client.get(
            f"{settings.market_data_url}/data/{symbol}/closes",
            params={"bars": bars},
        )
        response.raise_for_status()
        data = response.json()

        if data.get("success"):
            return data.get("closes", [])
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch price data",
            )

    except httpx.HTTPError as e:
        logger.error(f"Error fetching price data: {e}")
        raise HTTPException(status_code=500, detail=f"Market data error: {e}")


# RSI endpoints
@app.post("/strategy/rsi/signal", response_model=SignalResponse)
async def get_rsi_signal(request: SignalRequest):
    """
    Calculate RSI and generate trading signal.

    Args:
        request: Signal request with symbol and parameters
    """
    strategy = strategies.get("RSI")
    if not strategy:
        raise HTTPException(status_code=500, detail="RSI strategy not loaded")

    try:
        # Fetch price data
        closes = await fetch_price_data(request.symbol, bars=100)

        if len(closes) < settings.rsi_period + 1:
            return SignalResponse(
                success=False,
                message=f"Insufficient data: need {settings.rsi_period + 1} bars, got {len(closes)}",
            )

        # Calculate signal
        signal = strategy.calculate_signal(request.symbol, closes)

        # Publish signal event
        if publisher and signal.action != SignalAction.HOLD:
            event = SignalGeneratedEvent.create(
                symbol=signal.symbol,
                action=signal.action.value,
                strategy=signal.strategy.value,
                confidence=signal.confidence,
                indicators=signal.indicators,
            )
            await publisher.publish(event)

        return SignalResponse(
            success=True,
            signal=signal,
            message=f"RSI signal: {signal.action.value}",
            raw_data=signal.indicators,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating RSI signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/strategy/rsi/calculate", response_model=IndicatorResponse)
async def calculate_rsi(
    symbol: str,
    period: int = Query(default=14, ge=2, le=100),
):
    """
    Calculate RSI values without generating a signal.

    Args:
        symbol: Stock symbol
        period: RSI period
    """
    try:
        closes = await fetch_price_data(symbol, bars=period + 50)

        if len(closes) < period + 1:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data for RSI calculation",
            )

        import numpy as np
        import tulipy as ti

        closes_array = np.array(closes, dtype=np.float64)
        rsi_values = ti.rsi(closes_array, period=period)

        return IndicatorResponse(
            success=True,
            symbol=symbol,
            indicator="RSI",
            values={
                "current": float(rsi_values[-1]) if len(rsi_values) > 0 else None,
                "previous": float(rsi_values[-2]) if len(rsi_values) > 1 else None,
                "period": period,
                "history": [float(v) for v in rsi_values[-10:]],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating RSI: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# MACD endpoints
@app.post("/strategy/macd/signal", response_model=SignalResponse)
async def get_macd_signal(request: SignalRequest):
    """
    Calculate MACD and generate trading signal.

    Args:
        request: Signal request with symbol and parameters
    """
    strategy = strategies.get("MACD")
    if not strategy:
        raise HTTPException(status_code=500, detail="MACD strategy not loaded")

    try:
        # Need more data for MACD
        min_bars = settings.macd_slow + settings.macd_signal + 10
        closes = await fetch_price_data(request.symbol, bars=min_bars)

        if len(closes) < settings.macd_slow + settings.macd_signal:
            return SignalResponse(
                success=False,
                message=f"Insufficient data: need {settings.macd_slow + settings.macd_signal} bars",
            )

        # Calculate signal
        signal = strategy.calculate_signal(request.symbol, closes)

        # Publish signal event
        if publisher and signal.action != SignalAction.HOLD:
            event = SignalGeneratedEvent.create(
                symbol=signal.symbol,
                action=signal.action.value,
                strategy=signal.strategy.value,
                confidence=signal.confidence,
                indicators=signal.indicators,
            )
            await publisher.publish(event)

        return SignalResponse(
            success=True,
            signal=signal,
            message=f"MACD signal: {signal.action.value}",
            raw_data=signal.indicators,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating MACD signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/strategy/macd/calculate", response_model=IndicatorResponse)
async def calculate_macd(
    symbol: str,
    fast: int = Query(default=12, ge=2, le=100),
    slow: int = Query(default=26, ge=2, le=200),
    signal: int = Query(default=9, ge=2, le=50),
):
    """
    Calculate MACD values without generating a signal.

    Args:
        symbol: Stock symbol
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period
    """
    try:
        closes = await fetch_price_data(symbol, bars=slow + signal + 50)

        if len(closes) < slow + signal:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data for MACD calculation",
            )

        import numpy as np
        import tulipy as ti

        closes_array = np.array(closes, dtype=np.float64)
        macd_line, signal_line, histogram = ti.macd(
            closes_array,
            short_period=fast,
            long_period=slow,
            signal_period=signal,
        )

        return IndicatorResponse(
            success=True,
            symbol=symbol,
            indicator="MACD",
            values={
                "macd_line": float(macd_line[-1]) if len(macd_line) > 0 else None,
                "signal_line": float(signal_line[-1]) if len(signal_line) > 0 else None,
                "histogram": float(histogram[-1]) if len(histogram) > 0 else None,
                "prev_macd_line": float(macd_line[-2]) if len(macd_line) > 1 else None,
                "prev_signal_line": float(signal_line[-2]) if len(signal_line) > 1 else None,
                "prev_histogram": float(histogram[-2]) if len(histogram) > 1 else None,
                "fast_period": fast,
                "slow_period": slow,
                "signal_period": signal,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating MACD: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
