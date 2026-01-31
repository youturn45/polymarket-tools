"""Enumerations for order management system."""

from enum import Enum


class OrderSide(str, Enum):
    """Order side: BUY or SELL."""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    """Order execution status."""

    QUEUED = "queued"
    ACTIVE = "active"
    PARTIALLY_FILLED = "partially_filled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Urgency(str, Enum):
    """Order urgency level."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
