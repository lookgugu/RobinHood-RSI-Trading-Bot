"""
Robinhood Data Client - Fetches market data from Robinhood API.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

import redis.asyncio as redis
import httpx

from shared.models.price import PriceData, HistoricalData, QuoteData

logger = logging.getLogger(__name__)


class RobinhoodDataClient:
    """
    Client for fetching market data from Robinhood.

    Uses caching to reduce API calls and improve performance.
    """

    def __init__(
        self,
        gateway_url: str = "http://gateway:8000",
        redis_client: Optional[redis.Redis] = None,
        cache_ttl: int = 60,
    ):
        self.gateway_url = gateway_url
        self._redis = redis_client
        self._cache_ttl = cache_ttl
        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client."""
        await self._http_client.aclose()

    def _cache_key(self, symbol: str, data_type: str) -> str:
        """Generate cache key for a symbol and data type."""
        return f"market:{symbol}:{data_type}"

    async def _get_cached(self, key: str) -> Optional[dict]:
        """Get data from cache."""
        if not self._redis:
            return None

        try:
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")

        return None

    async def _set_cached(self, key: str, data: dict, ttl: Optional[int] = None) -> None:
        """Store data in cache."""
        if not self._redis:
            return

        try:
            await self._redis.set(
                key,
                json.dumps(data, default=str),
                ex=ttl or self._cache_ttl,
            )
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    async def get_historical_data(
        self,
        symbol: str,
        interval: str = "5minute",
        num_bars: int = 100,
    ) -> HistoricalData:
        """
        Get historical OHLCV data for a symbol.

        Args:
            symbol: Stock symbol
            interval: Data interval (5minute, 10minute, hour, day)
            num_bars: Number of bars to retrieve

        Returns:
            HistoricalData object with price bars
        """
        cache_key = self._cache_key(symbol, f"historical:{interval}:{num_bars}")

        # Check cache first
        cached = await self._get_cached(cache_key)
        if cached:
            logger.debug(f"Cache hit for {symbol} historical data")
            return HistoricalData(**cached)

        # Fetch from API
        logger.info(f"Fetching historical data for {symbol}")

        try:
            # In a real implementation, this would use the gateway to access Robinhood
            # For now, we'll simulate with mock data or direct API calls
            bars = await self._fetch_historical_from_robinhood(symbol, interval, num_bars)

            historical = HistoricalData(
                symbol=symbol,
                interval=interval,
                data=bars,
                start_time=bars[0].timestamp if bars else None,
                end_time=bars[-1].timestamp if bars else None,
            )

            # Cache the result
            await self._set_cached(cache_key, historical.model_dump())

            return historical

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            raise

    async def _fetch_historical_from_robinhood(
        self,
        symbol: str,
        interval: str,
        num_bars: int,
    ) -> List[PriceData]:
        """
        Fetch historical data from Robinhood API.

        This is a placeholder that simulates data.
        In production, this would use the pyrh library through the gateway.
        """
        # For demonstration, generate simulated price data
        # In production, this would call the actual Robinhood API
        import random
        from datetime import timedelta

        bars = []
        base_price = 65.0  # Base price for simulation
        current_time = datetime.utcnow()

        # Determine interval in minutes
        interval_minutes = {
            "5minute": 5,
            "10minute": 10,
            "hour": 60,
            "day": 1440,
        }.get(interval, 5)

        for i in range(num_bars):
            # Simulate price movement
            change = random.uniform(-0.5, 0.5)
            high_var = random.uniform(0, 0.3)
            low_var = random.uniform(0, 0.3)

            open_price = base_price
            close_price = base_price + change
            high_price = max(open_price, close_price) + high_var
            low_price = min(open_price, close_price) - low_var

            bar = PriceData(
                symbol=symbol,
                timestamp=current_time - timedelta(minutes=interval_minutes * (num_bars - i)),
                open=round(open_price, 4),
                high=round(high_price, 4),
                low=round(low_price, 4),
                close=round(close_price, 4),
                volume=random.randint(10000, 100000),
            )
            bars.append(bar)
            base_price = close_price

        return bars

    async def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        Get real-time quote for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            QuoteData object or None
        """
        cache_key = self._cache_key(symbol, "quote")

        # Check cache (with shorter TTL for quotes)
        cached = await self._get_cached(cache_key)
        if cached:
            logger.debug(f"Cache hit for {symbol} quote")
            return QuoteData(**cached)

        # Fetch from API
        logger.info(f"Fetching quote for {symbol}")

        try:
            quote = await self._fetch_quote_from_robinhood(symbol)

            if quote:
                # Cache with short TTL (10 seconds for quotes)
                await self._set_cached(cache_key, quote.model_dump(), ttl=10)

            return quote

        except Exception as e:
            logger.error(f"Error fetching quote: {e}")
            raise

    async def _fetch_quote_from_robinhood(self, symbol: str) -> Optional[QuoteData]:
        """
        Fetch quote from Robinhood API.

        This is a placeholder that simulates data.
        """
        import random

        # Simulate quote data
        base_price = 65.0
        spread = 0.02

        return QuoteData(
            symbol=symbol,
            bid_price=round(base_price - spread / 2, 4),
            ask_price=round(base_price + spread / 2, 4),
            last_price=round(base_price + random.uniform(-0.1, 0.1), 4),
            last_size=random.randint(100, 1000),
            timestamp=datetime.utcnow(),
        )

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get just the current price for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Current price or None
        """
        quote = await self.get_quote(symbol)
        if quote:
            return quote.last_price
        return None

    async def clear_cache(self, symbol: str) -> None:
        """Clear all cached data for a symbol."""
        if not self._redis:
            return

        try:
            # Find all keys for this symbol
            pattern = f"market:{symbol}:*"
            keys = []

            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await self._redis.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache entries for {symbol}")

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            raise
