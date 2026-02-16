"""Daily state tracker for Tiger Brokers MCP server (TASK-005).

Persists per-day trading state (realized P&L, recent order fingerprints)
to disk using ``orjson``. Automatically resets when the calendar date
rolls over.
"""

from __future__ import annotations

import hashlib
import time
from datetime import date
from pathlib import Path

import orjson


class DailyState:
    """Tracks daily trading state with on-disk persistence.

    State is stored per calendar day in ``state_dir/YYYY-MM-DD.json``.
    When the date rolls over, the in-memory state is automatically
    reset to a fresh day.

    Attributes:
        date: Current state date in YYYY-MM-DD format.
        realized_pnl: Running total of realized profit/loss for the day.
        recent_orders: List of order fingerprint dicts with timestamps.
        state_dir: Directory where state files are persisted.
    """

    def __init__(self, state_dir: Path) -> None:
        """Initialize the daily state tracker.

        Loads today's state from disk if a matching file exists,
        otherwise starts with a fresh (zeroed) state.

        Args:
            state_dir: Directory for persisting state files.
        """
        self.state_dir: Path = state_dir
        self.date: str = date.today().isoformat()
        self.realized_pnl: float = 0.0
        self.recent_orders: list[dict] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_pnl(self, amount: float) -> None:
        """Add *amount* to the daily realized P&L and persist.

        Args:
            amount: Profit (positive) or loss (negative) to record.
        """
        self._ensure_today()
        self.realized_pnl += amount
        self._save()

    def record_order(self, fingerprint: str) -> None:
        """Store an order fingerprint with the current timestamp and persist.

        Args:
            fingerprint: Hash string identifying the order parameters.
        """
        self._ensure_today()
        self.recent_orders.append(
            {"fingerprint": fingerprint, "timestamp": time.time()}
        )
        self._save()

    def has_recent_order(
        self, fingerprint: str, window_seconds: int = 60
    ) -> bool:
        """Check whether *fingerprint* exists within the time window.

        Entries older than *window_seconds* are cleaned up as a
        side-effect.

        Args:
            fingerprint: The order fingerprint to look for.
            window_seconds: How far back (in seconds) to search.

        Returns:
            ``True`` if a matching fingerprint is found within the window.
        """
        self._ensure_today()
        now = time.time()
        cutoff = now - window_seconds

        # Prune expired entries
        self.recent_orders = [
            entry
            for entry in self.recent_orders
            if entry["timestamp"] >= cutoff
        ]

        return any(
            entry["fingerprint"] == fingerprint
            for entry in self.recent_orders
        )

    def get_daily_pnl(self) -> float:
        """Return the current daily realized P&L.

        Performs a date check first so that stale state is never
        returned after midnight.

        Returns:
            The accumulated realized P&L for today.
        """
        self._ensure_today()
        return self.realized_pnl

    # ------------------------------------------------------------------
    # Fingerprint generation
    # ------------------------------------------------------------------

    @staticmethod
    def make_fingerprint(
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: float | None,
    ) -> str:
        """Generate a deterministic SHA-256 fingerprint for an order.

        Args:
            symbol: Ticker symbol (e.g. ``"AAPL"``).
            action: Order action (e.g. ``"BUY"``, ``"SELL"``).
            quantity: Number of shares/contracts.
            order_type: Order type string (e.g. ``"LMT"``, ``"MKT"``).
            limit_price: Limit price, or ``None`` for market orders.

        Returns:
            Hex-encoded SHA-256 hash of the combined inputs.
        """
        raw = f"{symbol}|{action}|{quantity}|{order_type}|{limit_price}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_today(self) -> None:
        """Reset state if the calendar date has changed since last access."""
        today = date.today().isoformat()
        if self.date != today:
            self.date = today
            self.realized_pnl = 0.0
            self.recent_orders = []

    def _save(self) -> None:
        """Persist current state to ``state_dir/YYYY-MM-DD.json``."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "date": self.date,
            "realized_pnl": self.realized_pnl,
            "recent_orders": self.recent_orders,
        }
        filepath = self.state_dir / f"{self.date}.json"
        filepath.write_bytes(orjson.dumps(payload))

    def _load(self) -> None:
        """Load state from disk if today's file exists."""
        filepath = self.state_dir / f"{self.date}.json"
        if not filepath.exists():
            return
        data = orjson.loads(filepath.read_bytes())
        self.date = data["date"]
        self.realized_pnl = data["realized_pnl"]
        self.recent_orders = data["recent_orders"]
