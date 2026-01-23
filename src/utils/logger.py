"""Logging configuration utility with structured logging support."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs JSON-structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "order_id"):
            log_data["order_id"] = record.order_id
        if hasattr(record, "market_id"):
            log_data["market_id"] = record.market_id
        if hasattr(record, "event_type"):
            log_data["event_type"] = record.event_type
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logger(
    name: str = "polymarket",
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = False,
) -> logging.Logger:
    """Set up logger with console and optional file output.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        json_format: If True, use JSON formatting for structured logs

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Choose formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def log_order_event(
    logger: logging.Logger,
    event_type: str,
    order_id: str,
    message: str,
    market_id: Optional[str] = None,
    extra_data: Optional[dict[str, Any]] = None,
) -> None:
    """Log an order lifecycle event with structured data.

    Args:
        logger: Logger instance
        event_type: Type of event (e.g., "order_placed", "tranche_filled")
        order_id: Order identifier
        message: Human-readable message
        market_id: Optional market identifier
        extra_data: Optional additional data to include
    """
    logger.info(
        message,
        extra={
            "event_type": event_type,
            "order_id": order_id,
            "market_id": market_id,
            "extra_data": extra_data or {},
        },
    )
