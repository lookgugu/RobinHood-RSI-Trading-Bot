from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PriceData(BaseModel):
    """Represents a single price data point (OHLCV)."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0

    class Config:
        use_enum_values = True


class HistoricalData(BaseModel):
    """Collection of historical price data."""

    symbol: str
    interval: str  # e.g., "5minute", "1hour", "1day"
    data: List[PriceData] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def get_close_prices(self) -> List[float]:
        """Extract close prices as a list."""
        return [bar.close for bar in self.data]

    def get_latest_price(self) -> Optional[float]:
        """Get the most recent close price."""
        if self.data:
            return self.data[-1].close
        return None


class QuoteData(BaseModel):
    """Real-time quote data for a symbol."""

    symbol: str
    bid_price: float
    ask_price: float
    last_price: float
    last_size: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def mid_price(self) -> float:
        """Calculate mid price between bid and ask."""
        return (self.bid_price + self.ask_price) / 2


class PriceUpdateEvent(BaseModel):
    """Event published when price updates."""

    event: str = "price_update"
    symbol: str
    price: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    volume: Optional[int] = None
