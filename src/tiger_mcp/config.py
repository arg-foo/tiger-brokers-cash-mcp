"""Configuration module for Tiger Brokers MCP server.

Provides a ``Settings`` dataclass that is populated either by direct
construction or via environment variables using the ``from_env()``
classmethod.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Truthy / falsy string literals accepted for boolean env vars.
_BOOL_TRUE = frozenset({"true", "1", "yes"})
_BOOL_FALSE = frozenset({"false", "0", "no"})


def _parse_bool(value: str, var_name: str) -> bool:
    """Parse a string into a boolean.

    Accepted truthy values: ``true``, ``1``, ``yes`` (case-insensitive).
    Accepted falsy  values: ``false``, ``0``, ``no``  (case-insensitive).

    Raises:
        ValueError: If *value* is not a recognised boolean string.
    """
    lower = value.lower()
    if lower in _BOOL_TRUE:
        return True
    if lower in _BOOL_FALSE:
        return False
    msg = (
        f"Invalid boolean value for {var_name}: {value!r}. "
        f"Expected one of: true, false, 1, 0, yes, no"
    )
    raise ValueError(msg)


@dataclass
class Settings:
    """Runtime configuration for the Tiger Brokers MCP server.

    Required fields must be supplied on construction or via ``from_env()``.
    Numeric safety fields default to ``0`` which means *no limit*.
    """

    tiger_id: str
    tiger_account: str
    private_key_path: Path
    sandbox: bool = True
    max_order_value: float = 0.0
    daily_loss_limit: float = 0.0
    max_position_pct: float = 0.0
    state_dir: Path = field(
        default_factory=lambda: Path.home() / ".tiger-mcp" / "state"
    )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        """Validate field values after dataclass initialisation."""
        # Coerce Path fields that may have been passed as strings.
        if not isinstance(self.private_key_path, Path):
            self.private_key_path = Path(self.private_key_path)
        if not isinstance(self.state_dir, Path):
            self.state_dir = Path(self.state_dir)

        # Required string fields must be non-empty.
        if not self.tiger_id:
            msg = "tiger_id must be a non-empty string"
            raise ValueError(msg)
        if not self.tiger_account:
            msg = "tiger_account must be a non-empty string"
            raise ValueError(msg)

        # Private key file must exist on disk.
        if not self.private_key_path.exists():
            msg = (
                f"private_key_path does not exist: {self.private_key_path}"
            )
            raise ValueError(msg)

        # Numeric safety fields must be non-negative.
        if self.max_order_value < 0:
            msg = f"max_order_value must be non-negative, got {self.max_order_value}"
            raise ValueError(msg)
        if self.daily_loss_limit < 0:
            msg = f"daily_loss_limit must be non-negative, got {self.daily_loss_limit}"
            raise ValueError(msg)
        if self.max_position_pct < 0:
            msg = f"max_position_pct must be non-negative, got {self.max_position_pct}"
            raise ValueError(msg)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> Settings:
        """Create a ``Settings`` instance from environment variables.

        Required environment variables:
            ``TIGER_ID``, ``TIGER_ACCOUNT``, ``TIGER_PRIVATE_KEY_PATH``

        Optional environment variables:
            ``TIGER_SANDBOX``          -- boolean (default ``True``)
            ``TIGER_MAX_ORDER_VALUE``  -- float   (default ``0``)
            ``TIGER_DAILY_LOSS_LIMIT`` -- float   (default ``0``)
            ``TIGER_MAX_POSITION_PCT`` -- float   (default ``0``)
            ``TIGER_STATE_DIR``        -- path    (default ``~/.tiger-mcp/state/``)

        Raises:
            ValueError: If a required variable is missing or a value is
                invalid.
        """
        # --- required ---
        tiger_id = os.environ.get("TIGER_ID")
        if not tiger_id:
            msg = "Required environment variable TIGER_ID is not set"
            raise ValueError(msg)

        tiger_account = os.environ.get("TIGER_ACCOUNT")
        if not tiger_account:
            msg = "Required environment variable TIGER_ACCOUNT is not set"
            raise ValueError(msg)

        private_key_raw = os.environ.get("TIGER_PRIVATE_KEY_PATH")
        if not private_key_raw:
            msg = "Required environment variable TIGER_PRIVATE_KEY_PATH is not set"
            raise ValueError(msg)
        private_key_path = Path(private_key_raw)

        # --- optional: sandbox ---
        sandbox_raw = os.environ.get("TIGER_SANDBOX")
        if sandbox_raw is not None:
            sandbox = _parse_bool(sandbox_raw, "TIGER_SANDBOX")
        else:
            sandbox = True

        # --- optional: numeric safety limits ---
        max_order_value = float(os.environ.get("TIGER_MAX_ORDER_VALUE", "0"))
        daily_loss_limit = float(os.environ.get("TIGER_DAILY_LOSS_LIMIT", "0"))
        max_position_pct = float(os.environ.get("TIGER_MAX_POSITION_PCT", "0"))

        # --- optional: state directory ---
        state_dir_raw = os.environ.get("TIGER_STATE_DIR")
        default_state = Path.home() / ".tiger-mcp" / "state"
        state_dir = Path(state_dir_raw) if state_dir_raw else default_state

        return cls(
            tiger_id=tiger_id,
            tiger_account=tiger_account,
            private_key_path=private_key_path,
            sandbox=sandbox,
            max_order_value=max_order_value,
            daily_loss_limit=daily_loss_limit,
            max_position_pct=max_position_pct,
            state_dir=state_dir,
        )
