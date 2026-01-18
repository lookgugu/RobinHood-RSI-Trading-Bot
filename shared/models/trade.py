from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TradeType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Trade(BaseModel):
    """Represents a completed trade transaction."""

    id: Optional[str] = None
    trade_type: TradeType
    symbol: str
    quantity: int
    price: float
    total_value: float = Field(default=0.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    order_id: Optional[str] = None
    status: TradeStatus = TradeStatus.PENDING
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None

    def model_post_init(self, __context) -> None:
        if self.total_value == 0.0:
            self.total_value = self.quantity * self.price

    class Config:
        use_enum_values = True


class Position(BaseModel):
    """Represents a current holding position."""

    symbol: str
    quantity: int
    average_cost: float
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    opened_at: datetime = Field(default_factory=datetime.utcnow)

    def update_pnl(self, current_price: float) -> None:
        """Update unrealized P&L based on current price."""
        self.current_price = current_price
        self.unrealized_pnl = (current_price - self.average_cost) * self.quantity
        self.unrealized_pnl_pct = ((current_price - self.average_cost) / self.average_cost) * 100


class DayTrade(BaseModel):
    """Represents a day trade for PDT tracking."""

    symbol: str
    buy_time: datetime
    sell_time: datetime
    date: str  # YYYY-MM-DD format
    quantity: int
    buy_price: float
    sell_price: float
    profit_loss: float
