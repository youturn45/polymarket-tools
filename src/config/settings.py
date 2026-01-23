"""Configuration management for Polymarket API."""

import os
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.encryption import decrypt_secret


class PolymarketConfig(BaseSettings):
    """Polymarket API configuration."""

    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="POLYMARKET_",
    )

    # Authentication: Private key (required for trading)
    private_key: str = Field(description="Ethereum private key without 0x prefix")

    # Connection settings
    host: str = Field(default="https://clob.polymarket.com", description="Polymarket API host")
    chain_id: int = Field(default=137, description="Polygon chain ID")

    # Optional: Proxy wallet settings
    signature_type: int = Field(default=0, description="Signature type (0=EOA, 1=Email, 2=Browser)")
    funder_address: Optional[str] = Field(
        default="", description="Funder address for proxy wallets"
    )

    # Database settings
    db_path: str = Field(
        default="data/orders.db", description="SQLite database path for order persistence"
    )

    # Concurrency settings
    max_concurrent_orders: int = Field(
        default=5, ge=1, le=20, description="Maximum concurrent order executions"
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


def _decrypt_private_key(
    secrets_file: str = "secrets.age",
    identity_file: str = "~/.ssh/Youturn",
) -> str:
    """Decrypt age-encrypted private key using SSH identity.

    Args:
        secrets_file: Path to age-encrypted secrets file
        identity_file: Path to SSH private key for decryption

    Returns:
        Decrypted private key as string

    Raises:
        FileNotFoundError: If secrets or identity file not found
        ValueError: If decryption fails
    """
    return decrypt_secret(secrets_file, identity_file)


def load_config(
    env_file: Optional[str] = None,
    secrets_file: str = "secrets.age",
    identity_file: str = "~/.ssh/Youturn",
) -> PolymarketConfig:
    """Load and validate configuration from environment.

    Args:
        env_file: Optional path to .env file. If not provided, uses:
                  1. ENV_FILE environment variable
                  2. Environment-specific file (.env.{ENV})
                  3. Default .env file
        secrets_file: Path to age-encrypted secrets file (default: secrets.age)
        identity_file: Path to SSH private key for decryption (default: ~/.ssh/Youturn)

    Environment priority (highest to lowest):
        1. System environment variables
        2. Decrypted secrets.age file (for private_key)
        3. .env file
        4. Default values

    Examples:
        # Use default secrets.age and .env
        config = load_config()

        # Use custom secrets file
        config = load_config(secrets_file="config/secrets.age")

        # Use specific env file and custom identity
        config = load_config(".env.production", identity_file="~/.ssh/prod_key")

        # Override via system env (takes precedence over secrets file)
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

    # Decrypt and set private key if not already in environment
    if "POLYMARKET_PRIVATE_KEY" not in os.environ:
        try:
            decrypted_key = _decrypt_private_key(secrets_file, identity_file)
            os.environ["POLYMARKET_PRIVATE_KEY"] = decrypted_key
        except (FileNotFoundError, ValueError) as e:
            raise RuntimeError(f"Failed to load private key from encrypted file: {e}") from e

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

    if config.private_key:
        print(f"Private Key: {config.private_key[:10]}...")
        print("Authentication: Ready (API creds will be generated on-the-fly)")
