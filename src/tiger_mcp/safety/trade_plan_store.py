"""Trade plan store for Tiger Brokers MCP server.

Persists trade plans (active and archived) to disk using ``orjson``.
Atomic writes ensure data integrity even if the process is interrupted
mid-write.
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import orjson

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Modification:
    """A single recorded modification to a trade plan."""

    timestamp: str  # ISO format
    changes: dict[str, Any]  # e.g. {"quantity": 200, "limit_price": 155.0}
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "timestamp": self.timestamp,
            "changes": self.changes,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Modification:
        """Deserialize from a plain dict."""
        return cls(
            timestamp=data["timestamp"],
            changes=data["changes"],
            reason=data["reason"],
        )


@dataclass
class TradePlan:
    """A trade plan associated with an order."""

    order_id: int
    symbol: str
    action: str
    quantity: int
    order_type: str
    limit_price: float | None
    stop_price: float | None
    reason: str
    status: str  # "active" or "archived"
    created_at: str  # ISO format
    modified_at: str | None
    archived_at: str | None
    archive_reason: str | None
    modifications: list[Modification] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "action": self.action,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "reason": self.reason,
            "status": self.status,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "archived_at": self.archived_at,
            "archive_reason": self.archive_reason,
            "modifications": [m.to_dict() for m in self.modifications],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TradePlan:
        """Deserialize from a plain dict."""
        return cls(
            order_id=data["order_id"],
            symbol=data["symbol"],
            action=data["action"],
            quantity=data["quantity"],
            order_type=data["order_type"],
            limit_price=data["limit_price"],
            stop_price=data["stop_price"],
            reason=data["reason"],
            status=data["status"],
            created_at=data["created_at"],
            modified_at=data["modified_at"],
            archived_at=data["archived_at"],
            archive_reason=data["archive_reason"],
            modifications=[
                Modification.from_dict(m) for m in data.get("modifications", [])
            ],
        )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class TradePlanStore:
    """Persistent store for trade plans (active and archived).

    Plans are keyed by ``str(order_id)`` in both the in-memory dicts
    and the on-disk JSON files.  Two files are maintained:

    * ``trade_plans.json`` -- currently active plans.
    * ``trade_plans_archive.json`` -- archived (completed/cancelled) plans.

    All writes are atomic: data is first written to a temporary file in
    the same directory, then ``os.replace()``-d over the target path.
    """

    def __init__(self, state_dir: Path) -> None:
        self.state_dir: Path = state_dir
        self._active_file: Path = state_dir / "trade_plans.json"
        self._archive_file: Path = state_dir / "trade_plans_archive.json"
        self._plans: dict[str, TradePlan] = {}
        self._archived: dict[str, TradePlan] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(
        self,
        order_id: int,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        reason: str,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> TradePlan:
        """Create and persist a new trade plan.

        Args:
            order_id: Broker-assigned order identifier.
            symbol: Ticker symbol (e.g. ``"AAPL"``).
            action: Order action (``"BUY"`` or ``"SELL"``).
            quantity: Number of shares.
            order_type: Order type (e.g. ``"LMT"``, ``"MKT"``, ``"STP"``).
            reason: Human-readable reason for the trade.
            limit_price: Limit price, or ``None`` for non-limit orders.
            stop_price: Stop price, or ``None`` for non-stop orders.

        Returns:
            The newly created ``TradePlan``.
        """
        plan = TradePlan(
            order_id=order_id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            reason=reason,
            status="active",
            created_at=datetime.now().isoformat(),
            modified_at=None,
            archived_at=None,
            archive_reason=None,
            modifications=[],
        )
        self._plans[str(order_id)] = plan
        self._save_active()
        return plan

    def record_modification(
        self,
        order_id: int,
        changes: dict[str, Any],
        reason: str = "",
    ) -> None:
        """Record a modification to an existing trade plan.

        Args:
            order_id: The order whose plan should be modified.
            changes: Dict of field names to new values.
            reason: Human-readable reason for the modification.
        """
        key = str(order_id)
        plan = self._plans.get(key)
        if plan is None:
            return
        mod = Modification(
            timestamp=datetime.now().isoformat(),
            changes=changes,
            reason=reason,
        )
        plan.modifications.append(mod)
        plan.modified_at = mod.timestamp
        self._save_active()

    def archive(
        self,
        order_id: int,
        archive_reason: str = "",
    ) -> None:
        """Move a trade plan from active to archive.

        This is a no-op if *order_id* does not exist in active plans.

        Args:
            order_id: The order to archive.
            archive_reason: Stored on the plan as ``archive_reason``.
        """
        key = str(order_id)
        plan = self._plans.pop(key, None)
        if plan is None:
            return
        plan.status = "archived"
        plan.archived_at = datetime.now().isoformat()
        plan.archive_reason = archive_reason
        self._archived[key] = plan
        self._save_active()
        self._save_archive()

    def archive_all(self, reason: str = "") -> None:
        """Archive all active trade plans.

        Args:
            reason: Stored as ``archive_reason`` on each plan.
        """
        keys = list(self._plans.keys())
        for key in keys:
            plan = self._plans.pop(key)
            plan.status = "archived"
            plan.archived_at = datetime.now().isoformat()
            plan.archive_reason = reason
            self._archived[key] = plan
        self._save_active()
        self._save_archive()

    def get_active_plans(self) -> dict[str, TradePlan]:
        """Return all active trade plans.

        Returns:
            Dict keyed by ``str(order_id)``.
        """
        return dict(self._plans)

    def get_plan(self, order_id: int) -> TradePlan | None:
        """Get a specific trade plan (active or archived).

        Args:
            order_id: The order to look up.

        Returns:
            The ``TradePlan`` if found, otherwise ``None``.
        """
        key = str(order_id)
        plan = self._plans.get(key)
        if plan is not None:
            return plan
        return self._archived.get(key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_active(self) -> None:
        """Atomically save active plans to disk."""
        self._save_file(self._active_file, self._plans)

    def _save_archive(self) -> None:
        """Atomically save archived plans to disk."""
        self._save_file(self._archive_file, self._archived)

    def _save_file(self, filepath: Path, plans: dict[str, TradePlan]) -> None:
        """Atomic write: write to a tempfile then ``os.replace()``.

        Args:
            filepath: Target file path.
            plans: Dict of plans to serialize.
        """
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {key: plan.to_dict() for key, plan in plans.items()}
        data = orjson.dumps(payload)
        fd = tempfile.NamedTemporaryFile(
            dir=self.state_dir, delete=False, suffix=".tmp"
        )
        try:
            fd.write(data)
            fd.close()
            os.replace(fd.name, filepath)
        except BaseException:
            # Clean up the temp file on failure
            fd.close()
            try:
                os.unlink(fd.name)
            except OSError:
                pass
            raise

    def _load(self) -> None:
        """Load both active and archive files from disk.

        Creates ``state_dir`` if it does not already exist.  If a file
        contains corrupt or malformed JSON, it is logged and skipped
        (the in-memory state falls back to empty).
        """
        self.state_dir.mkdir(parents=True, exist_ok=True)

        if self._active_file.exists():
            try:
                raw = orjson.loads(self._active_file.read_bytes())
                self._plans = {
                    key: TradePlan.from_dict(val) for key, val in raw.items()
                }
            except (orjson.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning(
                    "Failed to load %s, starting with empty plans: %s",
                    self._active_file, exc,
                )

        if self._archive_file.exists():
            try:
                raw = orjson.loads(self._archive_file.read_bytes())
                self._archived = {
                    key: TradePlan.from_dict(val) for key, val in raw.items()
                }
            except (orjson.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning(
                    "Failed to load %s, starting with empty archive: %s",
                    self._archive_file, exc,
                )
