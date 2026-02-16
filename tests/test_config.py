"""Tests for the Settings configuration module."""

from __future__ import annotations

from pathlib import Path

import pytest

from tiger_mcp.config import Settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_key_file(tmp_path: Path) -> Path:
    """Create a temporary file to act as a private key."""
    key_file = tmp_path / "private.pem"
    key_file.write_text("fake-key-content")
    return key_file


@pytest.fixture()
def valid_env(tmp_key_file: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Set the minimal required environment variables and return them."""
    env = {
        "TIGER_ID": "test-tiger-id",
        "TIGER_ACCOUNT": "test-account-123",
        "TIGER_PRIVATE_KEY_PATH": str(tmp_key_file),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


# ---------------------------------------------------------------------------
# Direct dataclass construction
# ---------------------------------------------------------------------------


class TestSettingsDirectConstruction:
    """Test creating Settings by passing arguments directly."""

    def test_valid_config_with_all_fields(self, tmp_key_file: Path) -> None:
        settings = Settings(
            tiger_id="my-id",
            tiger_account="my-account",
            private_key_path=tmp_key_file,
            sandbox=False,
            max_order_value=10_000.0,
            daily_loss_limit=500.0,
            max_position_pct=25.0,
            state_dir=Path("/tmp/state"),
        )
        assert settings.tiger_id == "my-id"
        assert settings.tiger_account == "my-account"
        assert settings.private_key_path == tmp_key_file
        assert settings.sandbox is False
        assert settings.max_order_value == 10_000.0
        assert settings.daily_loss_limit == 500.0
        assert settings.max_position_pct == 25.0
        assert settings.state_dir == Path("/tmp/state")

    def test_defaults_applied(self, tmp_key_file: Path) -> None:
        settings = Settings(
            tiger_id="id",
            tiger_account="acct",
            private_key_path=tmp_key_file,
        )
        assert settings.sandbox is True
        assert settings.max_order_value == 0.0
        assert settings.daily_loss_limit == 0.0
        assert settings.max_position_pct == 0.0
        assert settings.state_dir == Path.home() / ".tiger-mcp" / "state"

    def test_sandbox_default_is_true(self, tmp_key_file: Path) -> None:
        settings = Settings(
            tiger_id="id",
            tiger_account="acct",
            private_key_path=tmp_key_file,
        )
        assert settings.sandbox is True

    def test_zero_means_no_limit(self, tmp_key_file: Path) -> None:
        """A value of 0 for safety fields means 'no limit'."""
        settings = Settings(
            tiger_id="id",
            tiger_account="acct",
            private_key_path=tmp_key_file,
            max_order_value=0,
            daily_loss_limit=0,
            max_position_pct=0,
        )
        assert settings.max_order_value == 0.0
        assert settings.daily_loss_limit == 0.0
        assert settings.max_position_pct == 0.0

    def test_valid_port_boundaries(self, tmp_key_file: Path) -> None:
        for port in (1, 65535):
            settings = Settings(
                tiger_id="id",
                tiger_account="acct",
                private_key_path=tmp_key_file,
                mcp_port=port,
            )
            assert settings.mcp_port == port

    def test_transport_defaults(self, tmp_key_file: Path) -> None:
        settings = Settings(
            tiger_id="id",
            tiger_account="acct",
            private_key_path=tmp_key_file,
        )
        assert settings.mcp_transport == "stdio"
        assert settings.mcp_host == "0.0.0.0"
        assert settings.mcp_port == 8000


# ---------------------------------------------------------------------------
# Validation errors (direct construction)
# ---------------------------------------------------------------------------


class TestSettingsValidation:
    """Test __post_init__ validation raises ValueError for bad input."""

    def test_empty_tiger_id_raises(self, tmp_key_file: Path) -> None:
        with pytest.raises(ValueError, match="tiger_id"):
            Settings(
                tiger_id="",
                tiger_account="acct",
                private_key_path=tmp_key_file,
            )

    def test_empty_tiger_account_raises(self, tmp_key_file: Path) -> None:
        with pytest.raises(ValueError, match="tiger_account"):
            Settings(
                tiger_id="id",
                tiger_account="",
                private_key_path=tmp_key_file,
            )

    def test_private_key_path_must_exist(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "no-such-file.pem"
        with pytest.raises(ValueError, match="private_key_path"):
            Settings(
                tiger_id="id",
                tiger_account="acct",
                private_key_path=nonexistent,
            )

    def test_negative_max_order_value_raises(self, tmp_key_file: Path) -> None:
        with pytest.raises(ValueError, match="max_order_value"):
            Settings(
                tiger_id="id",
                tiger_account="acct",
                private_key_path=tmp_key_file,
                max_order_value=-1.0,
            )

    def test_negative_daily_loss_limit_raises(self, tmp_key_file: Path) -> None:
        with pytest.raises(ValueError, match="daily_loss_limit"):
            Settings(
                tiger_id="id",
                tiger_account="acct",
                private_key_path=tmp_key_file,
                daily_loss_limit=-0.01,
            )

    def test_negative_max_position_pct_raises(self, tmp_key_file: Path) -> None:
        with pytest.raises(ValueError, match="max_position_pct"):
            Settings(
                tiger_id="id",
                tiger_account="acct",
                private_key_path=tmp_key_file,
                max_position_pct=-50.0,
            )

    def test_invalid_transport_raises(self, tmp_key_file: Path) -> None:
        with pytest.raises(ValueError, match="mcp_transport"):
            Settings(
                tiger_id="id",
                tiger_account="acct",
                private_key_path=tmp_key_file,
                mcp_transport="grpc",
            )

    def test_port_zero_raises(self, tmp_key_file: Path) -> None:
        with pytest.raises(ValueError, match="mcp_port"):
            Settings(
                tiger_id="id",
                tiger_account="acct",
                private_key_path=tmp_key_file,
                mcp_port=0,
            )

    def test_port_above_65535_raises(self, tmp_key_file: Path) -> None:
        with pytest.raises(ValueError, match="mcp_port"):
            Settings(
                tiger_id="id",
                tiger_account="acct",
                private_key_path=tmp_key_file,
                mcp_port=65536,
            )

    def test_port_negative_raises(self, tmp_key_file: Path) -> None:
        with pytest.raises(ValueError, match="mcp_port"):
            Settings(
                tiger_id="id",
                tiger_account="acct",
                private_key_path=tmp_key_file,
                mcp_port=-1,
            )


# ---------------------------------------------------------------------------
# Factory: Settings.from_env()
# ---------------------------------------------------------------------------


class TestSettingsFromEnv:
    """Test the from_env() classmethod that reads os.environ."""

    def test_from_env_with_required_only(
        self, valid_env: dict[str, str], tmp_key_file: Path
    ) -> None:
        settings = Settings.from_env()
        assert settings.tiger_id == "test-tiger-id"
        assert settings.tiger_account == "test-account-123"
        assert settings.private_key_path == tmp_key_file
        # defaults
        assert settings.sandbox is True
        assert settings.max_order_value == 0.0
        assert settings.daily_loss_limit == 0.0
        assert settings.max_position_pct == 0.0
        assert settings.state_dir == Path.home() / ".tiger-mcp" / "state"

    def test_from_env_all_fields(
        self, valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TIGER_SANDBOX", "false")
        monkeypatch.setenv("TIGER_MAX_ORDER_VALUE", "5000.50")
        monkeypatch.setenv("TIGER_DAILY_LOSS_LIMIT", "200")
        monkeypatch.setenv("TIGER_MAX_POSITION_PCT", "10.5")
        monkeypatch.setenv("TIGER_STATE_DIR", "/tmp/custom-state")

        settings = Settings.from_env()
        assert settings.sandbox is False
        assert settings.max_order_value == 5000.50
        assert settings.daily_loss_limit == 200.0
        assert settings.max_position_pct == 10.5
        assert settings.state_dir == Path("/tmp/custom-state")

    def test_missing_tiger_id_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Ensure none of the required vars are set
        monkeypatch.delenv("TIGER_ID", raising=False)
        monkeypatch.delenv("TIGER_ACCOUNT", raising=False)
        monkeypatch.delenv("TIGER_PRIVATE_KEY_PATH", raising=False)
        with pytest.raises(ValueError, match="TIGER_ID"):
            Settings.from_env()

    def test_missing_tiger_account_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_key_file: Path
    ) -> None:
        monkeypatch.setenv("TIGER_ID", "id")
        monkeypatch.delenv("TIGER_ACCOUNT", raising=False)
        monkeypatch.delenv("TIGER_PRIVATE_KEY_PATH", raising=False)
        with pytest.raises(ValueError, match="TIGER_ACCOUNT"):
            Settings.from_env()

    def test_missing_private_key_path_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TIGER_ID", "id")
        monkeypatch.setenv("TIGER_ACCOUNT", "acct")
        monkeypatch.delenv("TIGER_PRIVATE_KEY_PATH", raising=False)
        with pytest.raises(ValueError, match="TIGER_PRIVATE_KEY_PATH"):
            Settings.from_env()

    # -----------------------------------------------------------------------
    # Boolean parsing for TIGER_SANDBOX
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("env_value", "expected"),
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("Yes", True),
            ("YES", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("No", False),
            ("NO", False),
        ],
    )
    def test_sandbox_boolean_parsing(
        self,
        valid_env: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        env_value: str,
        expected: bool,
    ) -> None:
        monkeypatch.setenv("TIGER_SANDBOX", env_value)
        settings = Settings.from_env()
        assert settings.sandbox is expected

    def test_sandbox_invalid_value_raises(
        self, valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TIGER_SANDBOX", "maybe")
        with pytest.raises(ValueError, match="(?i)sandbox"):
            Settings.from_env()

    # -----------------------------------------------------------------------
    # state_dir from env
    # -----------------------------------------------------------------------

    def test_state_dir_from_env(
        self, valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TIGER_STATE_DIR", "/opt/tiger/state")
        settings = Settings.from_env()
        assert settings.state_dir == Path("/opt/tiger/state")

    def test_state_dir_default_when_not_set(
        self, valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TIGER_STATE_DIR", raising=False)
        settings = Settings.from_env()
        assert settings.state_dir == Path.home() / ".tiger-mcp" / "state"

    # -----------------------------------------------------------------------
    # MCP transport settings from env
    # -----------------------------------------------------------------------

    def test_mcp_transport_from_env(
        self, valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
        monkeypatch.setenv("MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("MCP_PORT", "9090")
        settings = Settings.from_env()
        assert settings.mcp_transport == "streamable-http"
        assert settings.mcp_host == "127.0.0.1"
        assert settings.mcp_port == 9090

    def test_mcp_port_non_numeric_raises(
        self, valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MCP_PORT", "abc")
        with pytest.raises(ValueError, match="MCP_PORT"):
            Settings.from_env()

    def test_mcp_transport_defaults_when_not_set(
        self, valid_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        monkeypatch.delenv("MCP_HOST", raising=False)
        monkeypatch.delenv("MCP_PORT", raising=False)
        settings = Settings.from_env()
        assert settings.mcp_transport == "stdio"
        assert settings.mcp_host == "0.0.0.0"
        assert settings.mcp_port == 8000
