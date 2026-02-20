"""Configuration module for Tiger Brokers MCP server.

Provides a ``Settings`` dataclass that is populated either by direct
construction or via environment variables using the ``from_env()``
classmethod.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    """Runtime configuration for the Tiger Brokers MCP server.

    Required fields must be supplied on construction or via ``from_env()``.
    Numeric safety fields default to ``0`` which means *no limit*.
    """

    tiger_id: str
    tiger_account: str
    private_key_path: Path
    max_order_value: float = 0.0
    daily_loss_limit: float = 0.0
    max_position_pct: float = 0.0
    state_dir: Path = field(
        default_factory=lambda: Path.home() / ".tiger-mcp" / "state"
    )
    mcp_transport: str = "stdio"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000

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

        # MCP transport must be a recognised value.
        _valid_transports = {"stdio", "streamable-http"}
        if self.mcp_transport not in _valid_transports:
            msg = (
                f"mcp_transport must be one of {sorted(_valid_transports)}, "
                f"got {self.mcp_transport!r}"
            )
            raise ValueError(msg)

        # MCP port must be a valid TCP port number.
        if not (1 <= self.mcp_port <= 65535):
            msg = f"mcp_port must be in range 1-65535, got {self.mcp_port}"
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

        # --- optional: numeric safety limits ---
        max_order_value = float(os.environ.get("TIGER_MAX_ORDER_VALUE", "0"))
        daily_loss_limit = float(os.environ.get("TIGER_DAILY_LOSS_LIMIT", "0"))
        max_position_pct = float(os.environ.get("TIGER_MAX_POSITION_PCT", "0"))

        # --- optional: state directory ---
        state_dir_raw = os.environ.get("TIGER_STATE_DIR")
        default_state = Path.home() / ".tiger-mcp" / "state"
        state_dir = Path(state_dir_raw) if state_dir_raw else default_state

        # --- optional: MCP transport settings ---
        mcp_transport = os.environ.get("MCP_TRANSPORT", "stdio")
        mcp_host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp_port_raw = os.environ.get("MCP_PORT", "8000")
        try:
            mcp_port = int(mcp_port_raw)
        except ValueError:
            msg = f"MCP_PORT must be a valid integer, got {mcp_port_raw!r}"
            raise ValueError(msg) from None

        return cls(
            tiger_id=tiger_id,
            tiger_account=tiger_account,
            private_key_path=private_key_path,
            max_order_value=max_order_value,
            daily_loss_limit=daily_loss_limit,
            max_position_pct=max_position_pct,
            state_dir=state_dir,
            mcp_transport=mcp_transport,
            mcp_host=mcp_host,
            mcp_port=mcp_port,
        )
