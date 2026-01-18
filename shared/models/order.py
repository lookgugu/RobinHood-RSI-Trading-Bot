from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class Order(BaseModel):
    """Represents an order to be placed or that has been placed."""

    id: Optional[str] = None
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: int
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    filled_price: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    external_id: Optional[str] = None  # Robinhood order ID

    class Config:
        use_enum_values = True


class OrderRequest(BaseModel):
    """Request to place a new order."""

    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: int
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    strategy: Optional[str] = None  # Which strategy generated this order

    class Config:
        use_enum_values = True


class OrderResponse(BaseModel):
    """Response after placing an order."""

    success: bool
    order_id: Optional[str] = None
    message: str
    order: Optional[Order] = None
