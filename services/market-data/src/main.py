"""
Market Data Service - Fetches and caches price data.

This service handles:
- Historical price data retrieval
- Real-time quote fetching
- Price data caching
- Publishing price updates
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis.asyncio as redis
import httpx

from .robinhood_client import RobinhoodDataClient
from shared.models.price import PriceData, HistoricalData, QuoteData
from shared.messaging.publisher import EventPublisher
from shared.messaging.events import PriceUpdateEvent, EventType
from shared.utils.logging import setup_logging

# Setup logging
logger = setup_logging("market-data", level="INFO", format_type="console")


class Settings(BaseModel):
    """Market Data service settings."""

    service_name: str = "market-data"
    redis_url: str = "redis://redis:6379"
    gateway_url: str = "http://gateway:8000"
    default_symbol: str = "TQQQ"
    cache_ttl_seconds: int = 60
    historical_bars: int = 100

    class Config:
        env_file = ".env"


settings = Settings()

# Global instances
redis_client: Optional[redis.Redis] = None
publisher: Optional[EventPublisher] = None
data_client: Optional[RobinhoodDataClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global redis_client, publisher, data_client

    logger.info("Starting Market Data Service...")

    # Initialize Redis
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    # Initialize event publisher
    publisher = EventPublisher(settings.redis_url)
    await publisher.connect()

    # Initialize data client
    data_client = RobinhoodDataClient(
        gateway_url=settings.gateway_url,
        redis_client=redis_client,
        cache_ttl=settings.cache_ttl_seconds,
    )

    logger.info("Market Data Service started successfully")

    yield

    # Cleanup
    if publisher:
        await publisher.disconnect()
    if redis_client:
        await redis_client.close()

    logger.info("Market Data Service stopped")


app = FastAPI(
    title="Market Data Service",
    description="Fetches and caches market price data",
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
    redis_connected: bool


class HistoricalDataResponse(BaseModel):
    success: bool
    symbol: str
    interval: str
    data: List[PriceData]
    count: int


class QuoteResponse(BaseModel):
    success: bool
    quote: Optional[QuoteData] = None
    message: str = ""


# Health check
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health."""
    redis_ok = False

    try:
        if redis_client:
            await redis_client.ping()
            redis_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="healthy" if redis_ok else "degraded",
        service="market-data",
        redis_connected=redis_ok,
    )


# Data endpoints
@app.get("/data/{symbol}/historical", response_model=HistoricalDataResponse)
async def get_historical_data(
    symbol: str,
    interval: str = Query(default="5minute", description="Data interval"),
    bars: int = Query(default=100, ge=1, le=500, description="Number of bars"),
):
    """
    Get historical OHLCV data for a symbol.

    Args:
        symbol: Stock symbol (e.g., TQQQ, SPY)
        interval: Data interval (5minute, 10minute, hour, day)
        bars: Number of bars to retrieve
    """
    if data_client is None:
        raise HTTPException(status_code=500, detail="Data client not initialized")

    try:
        historical = await data_client.get_historical_data(
            symbol=symbol.upper(),
            interval=interval,
            num_bars=bars,
        )

        return HistoricalDataResponse(
            success=True,
            symbol=symbol.upper(),
            interval=interval,
            data=historical.data,
            count=len(historical.data),
        )

    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data/{symbol}/quote", response_model=QuoteResponse)
async def get_quote(symbol: str):
    """
    Get real-time quote for a symbol.

    Args:
        symbol: Stock symbol (e.g., TQQQ, SPY)
    """
    if data_client is None:
        raise HTTPException(status_code=500, detail="Data client not initialized")

    try:
        quote = await data_client.get_quote(symbol.upper())

        if quote:
            # Publish price update event
            if publisher:
                event = PriceUpdateEvent.create(
                    symbol=quote.symbol,
                    price=quote.last_price,
                    volume=quote.last_size,
                )
                await publisher.publish(event)

            return QuoteResponse(
                success=True,
                quote=quote,
            )
        else:
            return QuoteResponse(
                success=False,
                message=f"No quote available for {symbol}",
            )

    except Exception as e:
        logger.error(f"Error fetching quote for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data/{symbol}/price")
async def get_current_price(symbol: str):
    """
    Get just the current price for a symbol.

    Args:
        symbol: Stock symbol
    """
    if data_client is None:
        raise HTTPException(status_code=500, detail="Data client not initialized")

    try:
        price = await data_client.get_current_price(symbol.upper())

        if price is not None:
            return {
                "success": True,
                "symbol": symbol.upper(),
                "price": price,
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            raise HTTPException(
                status_code=404, detail=f"Price not available for {symbol}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data/{symbol}/closes")
async def get_close_prices(
    symbol: str,
    bars: int = Query(default=50, ge=1, le=500),
):
    """
    Get close prices as a simple array (useful for indicator calculations).

    Args:
        symbol: Stock symbol
        bars: Number of bars
    """
    if data_client is None:
        raise HTTPException(status_code=500, detail="Data client not initialized")

    try:
        historical = await data_client.get_historical_data(
            symbol=symbol.upper(),
            interval="5minute",
            num_bars=bars,
        )

        closes = historical.get_close_prices()

        return {
            "success": True,
            "symbol": symbol.upper(),
            "closes": closes,
            "count": len(closes),
        }

    except Exception as e:
        logger.error(f"Error fetching close prices for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/cache/{symbol}")
async def clear_cache(symbol: str):
    """Clear cached data for a symbol."""
    if data_client is None:
        raise HTTPException(status_code=500, detail="Data client not initialized")

    try:
        await data_client.clear_cache(symbol.upper())
        return {"success": True, "message": f"Cache cleared for {symbol}"}
    except Exception as e:
        logger.error(f"Error clearing cache for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
