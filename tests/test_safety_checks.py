"""Tests for pre-trade safety checks (TASK-006).

Covers all 6 safety checks:
  1. Block short selling
  2. Buying power check
  3. Max order value
  4. Position concentration (warning)
  5. Daily loss limit
  6. Duplicate detection (warning)

Also tests combined failures, disabled checks (limit=0), and market
order cost estimation via last_price.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tiger_mcp.config import Settings
from tiger_mcp.safety.checks import (
    AccountInfo,
    OrderParams,
    PositionInfo,
    SafetyResult,
    run_safety_checks,
)
from tiger_mcp.safety.state import DailyState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_match(items: list[str], *keywords: str) -> bool:
    """Return True if any item contains at least one keyword."""
    return any(
        any(kw in item.lower() for kw in keywords)
        for item in items
    )


def _filter_match(items: list[str], *keywords: str) -> list[str]:
    """Return items containing at least one keyword."""
    return [
        item
        for item in items
        if any(kw in item.lower() for kw in keywords)
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    """Settings with all safety limits enabled."""
    key_file = tmp_path / "private.pem"
    key_file.write_text("fake-key")
    return Settings(
        tiger_id="test_id",
        tiger_account="test_account",
        private_key_path=key_file,
        max_order_value=50_000.0,
        daily_loss_limit=5_000.0,
        max_position_pct=0.25,
        state_dir=tmp_path / "state",
    )


@pytest.fixture()
def settings_no_limits(tmp_path: Path) -> Settings:
    """Settings with all safety limits disabled (0)."""
    key_file = tmp_path / "private.pem"
    key_file.write_text("fake-key")
    return Settings(
        tiger_id="test_id",
        tiger_account="test_account",
        private_key_path=key_file,
        max_order_value=0.0,
        daily_loss_limit=0.0,
        max_position_pct=0.0,
        state_dir=tmp_path / "state",
    )


@pytest.fixture()
def account() -> AccountInfo:
    """Account with $100K cash and $200K net liquidation."""
    return AccountInfo(
        cash_balance=100_000.0,
        net_liquidation=200_000.0,
    )


@pytest.fixture()
def buy_order() -> OrderParams:
    """Standard limit buy: 100 AAPL at $150."""
    return OrderParams(
        symbol="AAPL",
        action="BUY",
        quantity=100,
        order_type="LMT",
        limit_price=150.0,
    )


@pytest.fixture()
def sell_order() -> OrderParams:
    """Standard limit sell: 50 AAPL at $155."""
    return OrderParams(
        symbol="AAPL",
        action="SELL",
        quantity=50,
        order_type="LMT",
        limit_price=155.0,
    )


@pytest.fixture()
def positions() -> list[PositionInfo]:
    """Portfolio with 200 AAPL and 100 GOOG."""
    return [
        PositionInfo(symbol="AAPL", quantity=200),
        PositionInfo(symbol="GOOG", quantity=100),
    ]


@pytest.fixture()
def mock_state() -> MagicMock:
    """Mocked DailyState: no losses, no recent duplicates."""
    state = MagicMock(spec=DailyState)
    state.get_daily_pnl.return_value = 0.0
    state.has_recent_order.return_value = False
    return state


# ---------------------------------------------------------------------------
# SafetyResult dataclass
# ---------------------------------------------------------------------------


class TestSafetyResult:
    def test_passed_true_when_no_errors(self) -> None:
        result = SafetyResult(
            passed=True, errors=[], warnings=[]
        )
        assert result.passed is True

    def test_passed_false_when_errors_present(self) -> None:
        result = SafetyResult(
            passed=False, errors=["some error"], warnings=[]
        )
        assert result.passed is False

    def test_warnings_independent_of_passed(self) -> None:
        result = SafetyResult(
            passed=True, errors=[], warnings=["warn"]
        )
        assert result.passed is True
        assert len(result.warnings) == 1


# ---------------------------------------------------------------------------
# Valid orders pass all checks
# ---------------------------------------------------------------------------


class TestValidOrders:
    def test_valid_buy_order_passes(
        self,
        buy_order: OrderParams,
        account: AccountInfo,
        positions: list[PositionInfo],
        settings: Settings,
        mock_state: MagicMock,
    ) -> None:
        result = run_safety_checks(
            buy_order, account, positions, settings, mock_state
        )
        assert result.passed is True
        assert result.errors == []

    def test_valid_sell_order_passes(
        self,
        sell_order: OrderParams,
        account: AccountInfo,
        positions: list[PositionInfo],
        settings: Settings,
        mock_state: MagicMock,
    ) -> None:
        result = run_safety_checks(
            sell_order, account, positions, settings, mock_state
        )
        assert result.passed is True
        assert result.errors == []


# ---------------------------------------------------------------------------
# Check 1: Block short selling
# ---------------------------------------------------------------------------


class TestBlockShortSelling:
    def test_sell_blocked_when_no_position(
        self,
        sell_order: OrderParams,
        account: AccountInfo,
        settings: Settings,
        mock_state: MagicMock,
    ) -> None:
        result = run_safety_checks(
            sell_order, account, [], settings, mock_state
        )
        assert result.passed is False
        assert _has_match(result.errors, "short", "position")

    def test_sell_blocked_when_insufficient_shares(
        self,
        account: AccountInfo,
        settings: Settings,
        mock_state: MagicMock,
    ) -> None:
        order = OrderParams(
            symbol="AAPL",
            action="SELL",
            quantity=300,
            order_type="LMT",
            limit_price=155.0,
        )
        pos = [PositionInfo(symbol="AAPL", quantity=200)]
        result = run_safety_checks(
            order, account, pos, settings, mock_state
        )
        assert result.passed is False
        assert _has_match(
            result.errors, "short", "insufficient", "exceed"
        )

    def test_sell_exact_position_allowed(
        self,
        account: AccountInfo,
        settings: Settings,
        mock_state: MagicMock,
    ) -> None:
        order = OrderParams(
            symbol="AAPL",
            action="SELL",
            quantity=200,
            order_type="LMT",
            limit_price=155.0,
        )
        pos = [PositionInfo(symbol="AAPL", quantity=200)]
        result = run_safety_checks(
            order, account, pos, settings, mock_state
        )
        short_errors = _filter_match(
            result.errors, "short", "position"
        )
        assert short_errors == []


# ---------------------------------------------------------------------------
# Check 2: Buying power
# ---------------------------------------------------------------------------


class TestBuyingPower:
    def test_insufficient_buying_power(
        self,
        positions: list[PositionInfo],
        settings: Settings,
        mock_state: MagicMock,
    ) -> None:
        # 100 * $150 * 1.01 = $15,150 > $10,000
        account = AccountInfo(
            cash_balance=10_000.0,
            net_liquidation=200_000.0,
        )
        order = OrderParams(
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="LMT",
            limit_price=150.0,
        )
        result = run_safety_checks(
            order, account, positions, settings, mock_state
        )
        assert result.passed is False
        assert _has_match(
            result.errors, "buying power", "cash", "insufficient"
        )

    def test_buying_power_uses_1pct_buffer(
        self,
        positions: list[PositionInfo],
        settings: Settings,
        mock_state: MagicMock,
    ) -> None:
        # 100 * 150 * 1.01 = 15,150 > 15,100
        account = AccountInfo(
            cash_balance=15_100.0,
            net_liquidation=200_000.0,
        )
        order = OrderParams(
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="LMT",
            limit_price=150.0,
        )
        result = run_safety_checks(
            order, account, positions, settings, mock_state
        )
        assert result.passed is False

    def test_buying_power_sufficient_with_buffer(
        self,
        positions: list[PositionInfo],
        settings: Settings,
        mock_state: MagicMock,
    ) -> None:
        # 100 * 150 * 1.01 = 15,150 < 16,000
        account = AccountInfo(
            cash_balance=16_000.0,
            net_liquidation=200_000.0,
        )
        order = OrderParams(
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="LMT",
            limit_price=150.0,
        )
        result = run_safety_checks(
            order, account, positions, settings, mock_state
        )
        buying_errors = _filter_match(
            result.errors, "buying power", "cash", "insufficient"
        )
        assert buying_errors == []

    def test_sell_order_skips_buying_power_check(
        self,
        sell_order: OrderParams,
        positions: list[PositionInfo],
        settings: Settings,
        mock_state: MagicMock,
    ) -> None:
        account = AccountInfo(
            cash_balance=0.0,
            net_liquidation=200_000.0,
        )
        result = run_safety_checks(
            sell_order, account, positions, settings, mock_state
        )
        buying_errors = _filter_match(
            result.errors, "buying power", "cash"
        )
        assert buying_errors == []


# ---------------------------------------------------------------------------
# Check 3: Max order value
# ---------------------------------------------------------------------------


class TestMaxOrderValue:
    def test_order_value_exceeds_limit(
        self,
        account: AccountInfo,
        positions: list[PositionInfo],
        mock_state: MagicMock,
        tmp_path: Path,
    ) -> None:
        key_file = tmp_path / "private.pem"
        key_file.write_text("fake-key")
        config = Settings(
            tiger_id="test_id",
            tiger_account="test_account",
            private_key_path=key_file,
            max_order_value=10_000.0,
            daily_loss_limit=0.0,
            max_position_pct=0.0,
        )
        order = OrderParams(
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="LMT",
            limit_price=150.0,  # 15,000 > 10,000
        )
        result = run_safety_checks(
            order, account, positions, config, mock_state
        )
        assert result.passed is False
        assert _has_match(
            result.errors, "max order", "order value"
        )


# ---------------------------------------------------------------------------
# Check 4: Position concentration (warning only)
# ---------------------------------------------------------------------------


class TestPositionConcentration:
    def test_position_concentration_warning(
        self,
        account: AccountInfo,
        positions: list[PositionInfo],
        mock_state: MagicMock,
        tmp_path: Path,
    ) -> None:
        key_file = tmp_path / "private.pem"
        key_file.write_text("fake-key")
        config = Settings(
            tiger_id="test_id",
            tiger_account="test_account",
            private_key_path=key_file,
            max_order_value=0.0,
            daily_loss_limit=0.0,
            max_position_pct=0.05,  # 5% of $200K = $10K
        )
        order = OrderParams(
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="LMT",
            limit_price=150.0,  # 15,000 > 10,000
        )
        result = run_safety_checks(
            order, account, positions, config, mock_state
        )
        assert result.passed is True
        assert _has_match(
            result.warnings, "concentration", "position"
        )

    def test_under_limit_no_warning(
        self,
        account: AccountInfo,
        positions: list[PositionInfo],
        mock_state: MagicMock,
        tmp_path: Path,
    ) -> None:
        key_file = tmp_path / "private.pem"
        key_file.write_text("fake-key")
        config = Settings(
            tiger_id="test_id",
            tiger_account="test_account",
            private_key_path=key_file,
            max_order_value=0.0,
            daily_loss_limit=0.0,
            max_position_pct=0.50,  # 50% of $200K = $100K
        )
        order = OrderParams(
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="LMT",
            limit_price=150.0,  # 15,000 < 100,000
        )
        result = run_safety_checks(
            order, account, positions, config, mock_state
        )
        conc_warns = _filter_match(
            result.warnings, "concentration", "position"
        )
        assert conc_warns == []


# ---------------------------------------------------------------------------
# Check 5: Daily loss limit
# ---------------------------------------------------------------------------


class TestDailyLossLimit:
    def test_daily_loss_limit_exceeded(
        self,
        buy_order: OrderParams,
        account: AccountInfo,
        positions: list[PositionInfo],
        settings: Settings,
    ) -> None:
        state = MagicMock(spec=DailyState)
        state.get_daily_pnl.return_value = -6_000.0
        state.has_recent_order.return_value = False
        result = run_safety_checks(
            buy_order, account, positions, settings, state
        )
        assert result.passed is False
        assert _has_match(
            result.errors, "daily loss", "loss limit"
        )

    def test_exact_limit_does_not_trigger(
        self,
        buy_order: OrderParams,
        account: AccountInfo,
        positions: list[PositionInfo],
        settings: Settings,
    ) -> None:
        state = MagicMock(spec=DailyState)
        state.get_daily_pnl.return_value = -5_000.0
        state.has_recent_order.return_value = False
        result = run_safety_checks(
            buy_order, account, positions, settings, state
        )
        loss_errors = _filter_match(
            result.errors, "daily loss", "loss limit"
        )
        assert loss_errors == []

    def test_positive_pnl_does_not_trigger(
        self,
        buy_order: OrderParams,
        account: AccountInfo,
        positions: list[PositionInfo],
        settings: Settings,
        mock_state: MagicMock,
    ) -> None:
        mock_state.get_daily_pnl.return_value = 1_000.0
        result = run_safety_checks(
            buy_order, account, positions, settings, mock_state
        )
        loss_errors = _filter_match(
            result.errors, "daily loss", "loss limit"
        )
        assert loss_errors == []


# ---------------------------------------------------------------------------
# Check 6: Duplicate detection (warning only)
# ---------------------------------------------------------------------------


class TestDuplicateDetection:
    def test_duplicate_order_warning(
        self,
        buy_order: OrderParams,
        account: AccountInfo,
        positions: list[PositionInfo],
        settings: Settings,
    ) -> None:
        state = MagicMock(spec=DailyState)
        state.get_daily_pnl.return_value = 0.0
        state.has_recent_order.return_value = True
        result = run_safety_checks(
            buy_order, account, positions, settings, state
        )
        assert result.passed is True
        assert _has_match(result.warnings, "duplicate")

    def test_no_duplicate_no_warning(
        self,
        buy_order: OrderParams,
        account: AccountInfo,
        positions: list[PositionInfo],
        settings: Settings,
        mock_state: MagicMock,
    ) -> None:
        result = run_safety_checks(
            buy_order, account, positions, settings, mock_state
        )
        dup_warns = _filter_match(
            result.warnings, "duplicate"
        )
        assert dup_warns == []


# ---------------------------------------------------------------------------
# Multiple failures at once (no short-circuiting)
# ---------------------------------------------------------------------------


class TestMultipleFailures:
    def test_all_errors_collected(
        self,
        tmp_path: Path,
    ) -> None:
        key_file = tmp_path / "private.pem"
        key_file.write_text("fake-key")
        config = Settings(
            tiger_id="test_id",
            tiger_account="test_account",
            private_key_path=key_file,
            max_order_value=1_000.0,
            daily_loss_limit=100.0,
            max_position_pct=0.01,
        )
        order = OrderParams(
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="LMT",
            limit_price=150.0,
        )
        account = AccountInfo(
            cash_balance=500.0,
            net_liquidation=200_000.0,
        )

        state = MagicMock(spec=DailyState)
        state.get_daily_pnl.return_value = -200.0
        state.has_recent_order.return_value = True

        result = run_safety_checks(
            order, account, [], config, state
        )

        assert result.passed is False
        # buying power + max order value + daily loss = 3 errors
        assert len(result.errors) >= 3
        # concentration + duplicate = warnings
        assert len(result.warnings) >= 1


# ---------------------------------------------------------------------------
# Disabled checks (limit=0 means skip)
# ---------------------------------------------------------------------------


class TestDisabledChecks:
    def test_disabled_max_order_value_skipped(
        self,
        buy_order: OrderParams,
        account: AccountInfo,
        positions: list[PositionInfo],
        settings_no_limits: Settings,
        mock_state: MagicMock,
    ) -> None:
        result = run_safety_checks(
            buy_order,
            account,
            positions,
            settings_no_limits,
            mock_state,
        )
        order_errs = _filter_match(
            result.errors, "max order", "order value"
        )
        assert order_errs == []

    def test_disabled_daily_loss_limit_skipped(
        self,
        buy_order: OrderParams,
        account: AccountInfo,
        positions: list[PositionInfo],
        settings_no_limits: Settings,
    ) -> None:
        state = MagicMock(spec=DailyState)
        state.get_daily_pnl.return_value = -999_999.0
        state.has_recent_order.return_value = False
        result = run_safety_checks(
            buy_order,
            account,
            positions,
            settings_no_limits,
            state,
        )
        loss_errors = _filter_match(
            result.errors, "daily loss", "loss limit"
        )
        assert loss_errors == []

    def test_disabled_position_concentration_skipped(
        self,
        buy_order: OrderParams,
        account: AccountInfo,
        positions: list[PositionInfo],
        settings_no_limits: Settings,
        mock_state: MagicMock,
    ) -> None:
        result = run_safety_checks(
            buy_order,
            account,
            positions,
            settings_no_limits,
            mock_state,
        )
        conc_warns = _filter_match(
            result.warnings, "concentration", "position"
        )
        assert conc_warns == []


# ---------------------------------------------------------------------------
# Market order uses last_price for estimation
# ---------------------------------------------------------------------------


class TestMarketOrderEstimation:
    def test_market_order_uses_last_price(
        self,
        account: AccountInfo,
        positions: list[PositionInfo],
        mock_state: MagicMock,
        tmp_path: Path,
    ) -> None:
        key_file = tmp_path / "private.pem"
        key_file.write_text("fake-key")
        config = Settings(
            tiger_id="test_id",
            tiger_account="test_account",
            private_key_path=key_file,
            max_order_value=10_000.0,
            daily_loss_limit=0.0,
            max_position_pct=0.0,
        )
        order = OrderParams(
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="MKT",
            limit_price=None,
            last_price=150.0,
        )
        result = run_safety_checks(
            order, account, positions, config, mock_state
        )
        assert result.passed is False
        assert _has_match(
            result.errors, "max order", "order value"
        )

    def test_limit_price_preferred_over_last(
        self,
        account: AccountInfo,
        positions: list[PositionInfo],
        mock_state: MagicMock,
        tmp_path: Path,
    ) -> None:
        key_file = tmp_path / "private.pem"
        key_file.write_text("fake-key")
        config = Settings(
            tiger_id="test_id",
            tiger_account="test_account",
            private_key_path=key_file,
            max_order_value=12_000.0,
            daily_loss_limit=0.0,
            max_position_pct=0.0,
        )
        # limit=150 -> value=15,000 > 12,000 (triggers)
        # last=100 -> value=10,000 < 12,000 (would pass)
        order = OrderParams(
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="LMT",
            limit_price=150.0,
            last_price=100.0,
        )
        result = run_safety_checks(
            order, account, positions, config, mock_state
        )
        assert result.passed is False
        assert _has_match(
            result.errors, "max order", "order value"
        )
