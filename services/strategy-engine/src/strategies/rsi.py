"""
RSI Strategy - Relative Strength Index trading strategy.

Buy when RSI <= oversold threshold
Sell when RSI >= overbought threshold
"""

import logging
from typing import List

import numpy as np
import tulipy as ti

from .base import BaseStrategy
from shared.models.signal import Signal, SignalAction, StrategyType

logger = logging.getLogger(__name__)


class RSIStrategy(BaseStrategy):
    """
    RSI (Relative Strength Index) trading strategy.

    Generates buy signals when RSI is oversold and sell signals when overbought.
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ):
        """
        Initialize RSI strategy.

        Args:
            period: RSI calculation period
            oversold: Threshold for buy signal (default 30)
            overbought: Threshold for sell signal (default 70)
        """
        super().__init__("RSI")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def get_required_bars(self) -> int:
        """Get minimum required bars for RSI calculation."""
        return self.period + 1

    def calculate_signal(self, symbol: str, prices: List[float]) -> Signal:
        """
        Calculate RSI and generate trading signal.

        Args:
            symbol: Stock symbol
            prices: List of close prices (oldest to newest)

        Returns:
            Signal with BUY, SELL, or HOLD action
        """
        if not self.validate_data(prices):
            logger.warning(f"Insufficient data for RSI: {len(prices)} bars")
            return Signal(
                strategy=StrategyType.RSI,
                symbol=symbol,
                action=SignalAction.HOLD,
                confidence=0.0,
                indicators={"error": "Insufficient data"},
            )

        try:
            # Convert to numpy array
            prices_array = np.array(prices, dtype=np.float64)

            # Calculate RSI
            rsi_values = ti.rsi(prices_array, period=self.period)

            if len(rsi_values) < 2:
                return Signal(
                    strategy=StrategyType.RSI,
                    symbol=symbol,
                    action=SignalAction.HOLD,
                    confidence=0.0,
                    indicators={"error": "RSI calculation returned insufficient values"},
                )

            current_rsi = float(rsi_values[-1])
            previous_rsi = float(rsi_values[-2])

            # Determine signal
            action = SignalAction.HOLD
            confidence = 0.5

            if current_rsi <= self.oversold:
                # Oversold - BUY signal
                action = SignalAction.BUY
                # Higher confidence the more oversold
                confidence = min(1.0, (self.oversold - current_rsi) / self.oversold + 0.5)
                logger.info(f"RSI BUY signal for {symbol}: RSI={current_rsi:.2f}")

            elif current_rsi >= self.overbought:
                # Overbought - SELL signal
                action = SignalAction.SELL
                # Higher confidence the more overbought
                confidence = min(1.0, (current_rsi - self.overbought) / (100 - self.overbought) + 0.5)
                logger.info(f"RSI SELL signal for {symbol}: RSI={current_rsi:.2f}")

            return Signal(
                strategy=StrategyType.RSI,
                symbol=symbol,
                action=action,
                confidence=round(confidence, 4),
                indicators={
                    "rsi": round(current_rsi, 4),
                    "previous_rsi": round(previous_rsi, 4),
                    "period": self.period,
                    "oversold_threshold": self.oversold,
                    "overbought_threshold": self.overbought,
                    "current_price": prices[-1],
                },
            )

        except Exception as e:
            logger.error(f"Error calculating RSI signal: {e}")
            return Signal(
                strategy=StrategyType.RSI,
                symbol=symbol,
                action=SignalAction.HOLD,
                confidence=0.0,
                indicators={"error": str(e)},
            )
