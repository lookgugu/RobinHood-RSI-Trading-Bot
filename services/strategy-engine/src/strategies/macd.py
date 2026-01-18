"""
MACD Strategy - Moving Average Convergence Divergence trading strategy.

Buy when MACD crosses above signal line (bullish crossover)
Sell when MACD crosses below signal line (bearish crossover)
"""

import logging
from typing import List

import numpy as np
import tulipy as ti

from .base import BaseStrategy
from shared.models.signal import Signal, SignalAction, StrategyType

logger = logging.getLogger(__name__)


class MACDStrategy(BaseStrategy):
    """
    MACD (Moving Average Convergence Divergence) trading strategy.

    Generates buy signals on bullish crossovers and sell signals on bearish crossovers.
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ):
        """
        Initialize MACD strategy.

        Args:
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line period (default 9)
        """
        super().__init__("MACD")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def get_required_bars(self) -> int:
        """Get minimum required bars for MACD calculation."""
        return self.slow_period + self.signal_period

    def calculate_signal(self, symbol: str, prices: List[float]) -> Signal:
        """
        Calculate MACD and generate trading signal based on crossovers.

        Args:
            symbol: Stock symbol
            prices: List of close prices (oldest to newest)

        Returns:
            Signal with BUY, SELL, or HOLD action
        """
        if not self.validate_data(prices):
            logger.warning(f"Insufficient data for MACD: {len(prices)} bars")
            return Signal(
                strategy=StrategyType.MACD,
                symbol=symbol,
                action=SignalAction.HOLD,
                confidence=0.0,
                indicators={"error": "Insufficient data"},
            )

        try:
            # Convert to numpy array
            prices_array = np.array(prices, dtype=np.float64)

            # Calculate MACD
            macd_line, signal_line, histogram = ti.macd(
                prices_array,
                short_period=self.fast_period,
                long_period=self.slow_period,
                signal_period=self.signal_period,
            )

            if len(macd_line) < 2 or len(signal_line) < 2:
                return Signal(
                    strategy=StrategyType.MACD,
                    symbol=symbol,
                    action=SignalAction.HOLD,
                    confidence=0.0,
                    indicators={"error": "MACD calculation returned insufficient values"},
                )

            # Get current and previous values
            current_macd = float(macd_line[-1])
            current_signal = float(signal_line[-1])
            current_histogram = float(histogram[-1])

            previous_macd = float(macd_line[-2])
            previous_signal = float(signal_line[-2])
            previous_histogram = float(histogram[-2])

            # Detect crossovers
            action = SignalAction.HOLD
            confidence = 0.5
            crossover_type = None

            # Bullish crossover: MACD crosses above signal line
            if previous_macd <= previous_signal and current_macd > current_signal:
                action = SignalAction.BUY
                crossover_type = "BULLISH"
                # Confidence based on histogram strength
                confidence = min(1.0, abs(current_histogram) * 10 + 0.6)
                logger.info(
                    f"MACD BULLISH crossover for {symbol}: "
                    f"MACD={current_macd:.4f}, Signal={current_signal:.4f}"
                )

            # Bearish crossover: MACD crosses below signal line
            elif previous_macd >= previous_signal and current_macd < current_signal:
                action = SignalAction.SELL
                crossover_type = "BEARISH"
                # Confidence based on histogram strength
                confidence = min(1.0, abs(current_histogram) * 10 + 0.6)
                logger.info(
                    f"MACD BEARISH crossover for {symbol}: "
                    f"MACD={current_macd:.4f}, Signal={current_signal:.4f}"
                )

            return Signal(
                strategy=StrategyType.MACD,
                symbol=symbol,
                action=action,
                confidence=round(confidence, 4),
                indicators={
                    "macd_line": round(current_macd, 6),
                    "signal_line": round(current_signal, 6),
                    "histogram": round(current_histogram, 6),
                    "previous_macd_line": round(previous_macd, 6),
                    "previous_signal_line": round(previous_signal, 6),
                    "previous_histogram": round(previous_histogram, 6),
                    "crossover_detected": crossover_type is not None,
                    "crossover_type": crossover_type,
                    "fast_period": self.fast_period,
                    "slow_period": self.slow_period,
                    "signal_period": self.signal_period,
                    "current_price": prices[-1],
                },
            )

        except Exception as e:
            logger.error(f"Error calculating MACD signal: {e}")
            return Signal(
                strategy=StrategyType.MACD,
                symbol=symbol,
                action=SignalAction.HOLD,
                confidence=0.0,
                indicators={"error": str(e)},
            )
