"""Configuration management for Polymarket API."""

import os
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PolymarketConfig(BaseSettings):
    """Polymarket API configuration."""

    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="POLYMARKET_",
    )

    # L1 Authentication: Private key (required for trading)
    private_key: str = Field(description="Ethereum private key without 0x prefix")

    # L2 Authentication: API credentials (optional, for full trading access)
    api_key: Optional[str] = Field(default=None, description="Polymarket API key")
    api_secret: Optional[str] = Field(default=None, description="Polymarket API secret")
    api_passphrase: Optional[str] = Field(default=None, description="Polymarket API passphrase")

    # Connection settings
    host: str = Field(default="https://clob.polymarket.com", description="Polymarket API host")
    chain_id: int = Field(default=137, description="Polygon chain ID")

    # Optional: Proxy wallet settings
    signature_type: int = Field(default=0, description="Signature type (0=EOA, 1=Email, 2=Browser)")
    funder_address: Optional[str] = Field(
        default="", description="Funder address for proxy wallets"
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

    def has_l1_auth(self) -> bool:
        """Check if L1 (private key) authentication is available."""
        return self.private_key is not None

    def has_l2_auth(self) -> bool:
        """Check if L2 (API credentials) authentication is available."""
        return (
            self.api_key is not None
            and self.api_secret is not None
            and self.api_passphrase is not None
        )

    def get_auth_level(self) -> str:
        """
        Get the authentication level available.

        Returns:
            "L1": Private key only (can create orders, derive API creds)
            "L2": Private key + API creds (full trading with post/cancel)
        """
        if self.has_l2_auth():
            return "L2"
        return "L1"


def load_config(env_file: Optional[str] = None) -> PolymarketConfig:
    """Load and validate configuration from environment.

    Args:
        env_file: Optional path to .env file. If not provided, uses:
                  1. ENV_FILE environment variable
                  2. Environment-specific file (.env.{ENV})
                  3. Default .env file

    Environment priority (highest to lowest):
        1. System environment variables
        2. .env file
        3. Default values

    Examples:
        # Use default .env
        config = load_config()

        # Use specific env file
        config = load_config(".env.production")

        # Use environment-specific file
        # export ENV=production
        config = load_config()  # loads .env.production

        # Override via system env
        # export POLYMARKET_PRIVATE_KEY=abc123
        config = load_config()  # uses system env var
    """
    if env_file:
        # Explicitly provided env file
        os.environ["ENV_FILE"] = env_file
    elif "ENV_FILE" not in os.environ:
        # Try environment-specific file (e.g., .env.production)
        env = os.getenv("ENV", "development")
        env_specific_file = f".env.{env}"
        if os.path.exists(env_specific_file):
            os.environ["ENV_FILE"] = env_specific_file
        # Otherwise falls back to .env (default in SettingsConfigDict)

    return PolymarketConfig()


# Usage example
if __name__ == "__main__":
    # Example 1: Default loading
    config = load_config()

    # Example 2: Load specific environment
    # config = load_config(".env.production")

    # Example 3: Use ENV variable
    # export ENV=staging
    # config = load_config()  # loads .env.staging

    print(f"Polymarket Host: {config.host}")
    print(f"Chain ID: {config.chain_id}")
    print(f"Signature Type: {config.signature_type}")
    print(f"Auth Level: {config.get_auth_level()}")

    # Show authentication status
    if config.private_key:
        print(f"Private Key: {config.private_key[:10]}...")
    if config.has_l2_auth():
        print(f"API Key: {config.api_key}")
        print("L2 Auth: Enabled (full trading)")
    else:
        print("L2 Auth: Disabled (use generate_api_creds to enable)")
