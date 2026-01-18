from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Robinhood credentials
    robinhood_username: str = ""
    robinhood_password: str = ""

    # Trading configuration
    symbol: str = "TQQQ"
    max_investment: float = 20.00
    profit_target_pct: float = 1.0
    stop_loss_pct: float = -0.5
    check_interval_seconds: int = 300

    # Strategy parameters
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # PDT compliance
    pdt_tracking_days: int = 5
    max_day_trades: int = 3

    # Infrastructure
    redis_url: str = "redis://localhost:6379"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/trading_bot"

    # Service ports
    gateway_port: int = 8000
    market_data_port: int = 8001
    strategy_engine_port: int = 8002
    execution_port: int = 8003
    risk_management_port: int = 8004
    compliance_port: int = 8005
    portfolio_port: int = 8006

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


class ServiceSettings(BaseSettings):
    """Base settings for individual services."""

    service_name: str = "unknown"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    redis_url: str = "redis://redis:6379"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class GatewaySettings(ServiceSettings):
    """Settings for the Gateway service."""

    service_name: str = "gateway"
    port: int = 8000
    robinhood_username: str = ""
    robinhood_password: str = ""
    session_ttl_seconds: int = 3600


class MarketDataSettings(ServiceSettings):
    """Settings for the Market Data service."""

    service_name: str = "market-data"
    port: int = 8001
    cache_ttl_seconds: int = 60
    historical_bars: int = 100


class StrategyEngineSettings(ServiceSettings):
    """Settings for the Strategy Engine service."""

    service_name: str = "strategy-engine"
    port: int = 8002
    default_symbol: str = "TQQQ"
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9


class ExecutionSettings(ServiceSettings):
    """Settings for the Execution service."""

    service_name: str = "execution"
    port: int = 8003
    risk_service_url: str = "http://risk-management:8004"
    compliance_service_url: str = "http://compliance:8005"


class RiskManagementSettings(ServiceSettings):
    """Settings for the Risk Management service."""

    service_name: str = "risk-management"
    port: int = 8004
    max_investment: float = 20.00
    profit_target_pct: float = 1.0
    stop_loss_pct: float = -0.5
    max_position_value: float = 100.00


class ComplianceSettings(ServiceSettings):
    """Settings for the Compliance service."""

    service_name: str = "compliance"
    port: int = 8005
    database_url: str = "postgresql://postgres:postgres@postgres:5432/trading_bot"
    pdt_tracking_days: int = 5
    max_day_trades: int = 3


class PortfolioSettings(ServiceSettings):
    """Settings for the Portfolio service."""

    service_name: str = "portfolio"
    port: int = 8006
    database_url: str = "postgresql://postgres:postgres@postgres:5432/trading_bot"
