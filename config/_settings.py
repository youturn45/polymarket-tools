"""Configuration management using pydantic-settings."""

from enum import Enum
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Side(str, Enum):
    """Order side enum."""

    BUY = "BUY"
    SELL = "SELL"


class SplittingStrategy(str, Enum):
    """Order splitting strategy enum."""

    TWAP = "TWAP"
    VWAP = "VWAP"
    ICEBERG = "ICEBERG"
    RANDOM = "RANDOM"


class PolymarketConfig(BaseSettings):
    """Polymarket API configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    private_key: str = Field(..., description="Ethereum private key without 0x prefix")
    polymarket_host: str = Field(
        default="https://clob.polymarket.com", description="Polymarket API host"
    )
    chain_id: int = Field(default=137, description="Polygon chain ID")
    signature_type: int = Field(default=0, description="Signature type (0=EOA, 1=Email, 2=Browser)")
    funder_address: Optional[str] = Field(
        default=None, description="Funder address for proxy wallets"
    )

    @field_validator("private_key")
    @classmethod
    def validate_private_key(cls, v: str) -> str:
        """Validate private key format."""
        v = v.strip()
        if v.startswith("0x"):
            v = v[2:]
        if len(v) != 64:
            raise ValueError("Private key must be 64 hex characters (without 0x prefix)")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("Private key must be valid hex") from None
        return v


class StrategyConfig(BaseSettings):
    """Trading strategy configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    token_id: str = Field(..., description="Market token ID to trade")
    side: Side = Field(..., description="Order side (BUY or SELL)")
    limit_price: float = Field(..., gt=0, le=1, description="Maximum price willing to pay (0-1)")
    total_shares: int = Field(..., gt=0, description="Total number of shares to trade")

    # Order splitting
    splitting_strategy: SplittingStrategy = Field(
        default=SplittingStrategy.TWAP, description="Order splitting strategy"
    )
    time_window_minutes: int = Field(
        default=60, gt=0, description="Time window for order execution in minutes"
    )
    min_order_size: int = Field(default=10, gt=0, description="Minimum shares per order")
    max_order_size: int = Field(default=100, gt=0, description="Maximum shares per order")

    # Top bidder
    poll_interval: int = Field(
        default=3, gt=0, le=60, description="Seconds between order book polls"
    )
    enable_top_bidder: bool = Field(
        default=True, description="Enable automatic top bidder functionality"
    )

    @field_validator("max_order_size")
    @classmethod
    def validate_order_sizes(cls, v: int, info: dict) -> int:
        """Validate max_order_size is greater than min_order_size."""
        if "min_order_size" in info.data and v < info.data["min_order_size"]:
            raise ValueError("max_order_size must be >= min_order_size")
        return v


class RiskLimits(BaseSettings):
    """Risk management limits."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    max_position_size: int = Field(
        default=5000, gt=0, description="Maximum shares per market position"
    )
    max_total_exposure: float = Field(
        default=10000.0, gt=0, description="Maximum total USD exposure"
    )
    max_daily_loss: float = Field(default=500.0, gt=0, description="Maximum daily loss in USD")
    max_order_size: int = Field(default=100, gt=0, description="Maximum shares per single order")


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/trading.log", description="Log file path")


class Settings:
    """Main settings container."""

    def __init__(self) -> None:
        """Initialize settings from environment."""
        self.polymarket = PolymarketConfig()
        self.strategy = StrategyConfig()
        self.risk = RiskLimits()
        self.logging = LoggingConfig()

    def validate_strategy_against_risk(self) -> None:
        """Validate strategy configuration against risk limits."""
        if self.strategy.max_order_size > self.risk.max_order_size:
            raise ValueError(
                f"Strategy max_order_size ({self.strategy.max_order_size}) "
                f"exceeds risk limit ({self.risk.max_order_size})"
            )

        if self.strategy.total_shares > self.risk.max_position_size:
            raise ValueError(
                f"Strategy total_shares ({self.strategy.total_shares}) "
                f"exceeds risk max_position_size ({self.risk.max_position_size})"
            )


def load_settings() -> Settings:
    """Load and validate settings from environment."""
    settings = Settings()
    settings.validate_strategy_against_risk()
    return settings
