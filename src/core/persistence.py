"""SQLite persistence for order state and history."""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from models.order import Order


class OrderDatabase:
    """SQLite database for order persistence.

    Features:
    - WAL mode for better concurrency
    - Full order lifecycle tracking
    - Fill history
    - Event audit trail
    """

    def __init__(self, db_path: str = "data/orders.db", logger: Optional[logging.Logger] = None):
        """Initialize database.

        Args:
            db_path: Path to SQLite database file
            logger: Optional logger instance
        """
        self.db_path = Path(db_path)
        self.logger = logger or logging.getLogger(__name__)

        # Create data directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")

            # Orders table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    token_id TEXT NOT NULL,
                    market_id TEXT,
                    side TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    total_size INTEGER NOT NULL,
                    filled_amount INTEGER DEFAULT 0,
                    remaining_amount INTEGER,
                    target_price REAL NOT NULL,
                    max_price REAL NOT NULL,
                    min_price REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    adjustment_count INTEGER DEFAULT 0,
                    undercut_count INTEGER DEFAULT 0,
                    strategy_params TEXT
                )
            """
            )

            # Indexes for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_token ON orders(token_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON orders(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON orders(created_at)")

            # Fills table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(order_id)
                )
            """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fill_order ON fills(order_id)")

            # Events table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT,
                    FOREIGN KEY (order_id) REFERENCES orders(order_id)
                )
            """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event_order ON events(order_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON events(event_type)")

        self.logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get database connection with auto-commit/rollback.

        Yields:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_order(self, order: Order, strategy_type: str = "unknown"):
        """Save or update order.

        Args:
            order: Order to save
            strategy_type: Strategy type name
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO orders (
                    order_id, token_id, market_id, side, strategy_type,
                    total_size, filled_amount, remaining_amount,
                    target_price, max_price, min_price, status,
                    created_at, updated_at, adjustment_count, undercut_count,
                    strategy_params
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    order.order_id,
                    order.token_id,
                    order.market_id,
                    order.side.value,
                    strategy_type,
                    order.total_size,
                    order.filled_amount,
                    order.remaining_amount,
                    order.target_price,
                    order.max_price,
                    order.min_price,
                    order.status.value,
                    order.created_at.isoformat(),
                    order.updated_at.isoformat(),
                    order.adjustment_count,
                    order.undercut_count,
                    (
                        json.dumps(order.strategy_params.model_dump())
                        if order.strategy_params
                        else None
                    ),
                ),
            )

    def record_fill(self, order_id: str, amount: int, price: float):
        """Record a fill.

        Args:
            order_id: Order identifier
            amount: Fill amount
            price: Fill price
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO fills (order_id, amount, price, timestamp)
                VALUES (?, ?, ?, ?)
            """,
                (order_id, amount, price, datetime.now().isoformat()),
            )

    def record_event(self, order_id: str, event_type: str, details: dict):
        """Record an event.

        Args:
            order_id: Order identifier
            event_type: Event type name
            details: Event details dictionary
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO events (order_id, event_type, timestamp, details)
                VALUES (?, ?, ?, ?)
            """,
                (order_id, event_type, datetime.now().isoformat(), json.dumps(details)),
            )

    def load_active_orders(self) -> list[dict]:
        """Load active orders on startup.

        Returns:
            List of order dictionaries
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM orders
                WHERE status IN ('queued', 'active', 'partially_filled')
                ORDER BY created_at
            """
            ).fetchall()
            return [dict(row) for row in rows]

    def get_order_history(self, token_id: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Query order history.

        Args:
            token_id: Optional token filter
            limit: Maximum number of orders to return

        Returns:
            List of order dictionaries
        """
        with self._get_connection() as conn:
            if token_id:
                rows = conn.execute(
                    """
                    SELECT * FROM orders
                    WHERE token_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (token_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM orders
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (limit,),
                ).fetchall()
            return [dict(row) for row in rows]

    def get_fills(self, order_id: str) -> list[dict]:
        """Get fills for an order.

        Args:
            order_id: Order identifier

        Returns:
            List of fill dictionaries
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM fills
                WHERE order_id = ?
                ORDER BY timestamp
            """,
                (order_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_events(self, order_id: str) -> list[dict]:
        """Get events for an order.

        Args:
            order_id: Order identifier

        Returns:
            List of event dictionaries
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE order_id = ?
                ORDER BY timestamp
            """,
                (order_id,),
            ).fetchall()
            return [dict(row) for row in rows]
