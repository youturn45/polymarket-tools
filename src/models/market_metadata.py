"""Market metadata models for caching market information."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TokenInfo(BaseModel):
    """Token information within a market."""

    token_id: str
    outcome: str  # "YES" or "NO"


class MarketMetadata(BaseModel):
    """Cached market metadata with TTL management.

    Stores market information including question text and token mappings
    to avoid excessive API calls. Cached data expires after TTL period.
    """

    condition_id: str
    question: str
    tokens: list[TokenInfo]
    end_date: Optional[datetime] = None

    # TTL management
    cached_at: datetime = Field(default_factory=datetime.now)
    ttl_seconds: int = 3600  # 1 hour

    def is_stale(self) -> bool:
        """Check if cached data needs refresh.

        Returns:
            True if cache age exceeds TTL
        """
        age = (datetime.now() - self.cached_at).total_seconds()
        return age > self.ttl_seconds

    def get_token_outcome(self, token_id: str) -> Optional[str]:
        """Get outcome for a specific token ID.

        Args:
            token_id: Token ID to lookup

        Returns:
            Outcome string ("YES" or "NO") or None if not found
        """
        for token in self.tokens:
            if token.token_id == token_id:
                return token.outcome
        return None
