"""
Base Strategy - Abstract base class for trading strategies.
"""

from abc import ABC, abstractmethod
from typing import List

from shared.models.signal import Signal


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.

    All strategies must implement the calculate_signal method.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def calculate_signal(self, symbol: str, prices: List[float]) -> Signal:
        """
        Calculate a trading signal based on price data.

        Args:
            symbol: Stock symbol
            prices: List of close prices (oldest to newest)

        Returns:
            Signal object with action recommendation
        """
        pass

    @abstractmethod
    def get_required_bars(self) -> int:
        """
        Get the minimum number of price bars required for calculation.

        Returns:
            Minimum number of bars needed
        """
        pass

    def validate_data(self, prices: List[float]) -> bool:
        """
        Validate that sufficient data is available.

        Args:
            prices: List of close prices

        Returns:
            True if data is sufficient
        """
        return len(prices) >= self.get_required_bars()
