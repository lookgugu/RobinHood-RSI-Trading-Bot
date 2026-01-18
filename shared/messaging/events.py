from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events in the trading system."""

    # Price events
    PRICE_UPDATE = "price_update"
    HISTORICAL_DATA_READY = "historical_data_ready"

    # Signal events
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_EXPIRED = "signal_expired"

    # Order events
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"

    # Trade events
    TRADE_COMPLETED = "trade_completed"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"

    # Risk events
    RISK_LIMIT_REACHED = "risk_limit_reached"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    PROFIT_TARGET_REACHED = "profit_target_reached"

    # Compliance events
    PDT_WARNING = "pdt_warning"
    PDT_LIMIT_REACHED = "pdt_limit_reached"

    # System events
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    ERROR_OCCURRED = "error_occurred"


class BaseEvent(BaseModel):
    """Base class for all events."""

    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_service: str
    correlation_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True

    def to_channel(self) -> str:
        """Get the Redis channel name for this event type."""
        return f"trading:{self.event_type}"


class PriceUpdateEvent(BaseEvent):
    """Event for price updates."""

    event_type: EventType = EventType.PRICE_UPDATE
    source_service: str = "market-data"

    @classmethod
    def create(cls, symbol: str, price: float, volume: int = 0) -> "PriceUpdateEvent":
        return cls(
            payload={
                "symbol": symbol,
                "price": price,
                "volume": volume,
            }
        )


class SignalGeneratedEvent(BaseEvent):
    """Event when a trading signal is generated."""

    event_type: EventType = EventType.SIGNAL_GENERATED
    source_service: str = "strategy-engine"

    @classmethod
    def create(
        cls,
        symbol: str,
        action: str,
        strategy: str,
        confidence: float,
        indicators: Dict[str, Any],
    ) -> "SignalGeneratedEvent":
        return cls(
            payload={
                "symbol": symbol,
                "action": action,
                "strategy": strategy,
                "confidence": confidence,
                "indicators": indicators,
            }
        )


class TradeCompletedEvent(BaseEvent):
    """Event when a trade is completed."""

    event_type: EventType = EventType.TRADE_COMPLETED
    source_service: str = "execution"

    @classmethod
    def create(
        cls,
        order_id: str,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        profit_loss: Optional[float] = None,
    ) -> "TradeCompletedEvent":
        return cls(
            payload={
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "profit_loss": profit_loss,
            }
        )
