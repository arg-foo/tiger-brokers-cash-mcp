"""Tests for DailyState tracker (TASK-005).

Covers: fresh state, day rollover, persistence round-trip,
duplicate detection, P&L accumulation, fingerprint hashing,
and state directory creation.
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from unittest.mock import patch

from tiger_mcp.safety.state import DailyState

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _today_str() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Fresh state (new day, no file on disk)
# ---------------------------------------------------------------------------

class TestFreshState:
    def test_fresh_state_has_zero_pnl(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        assert state.get_daily_pnl() == 0.0

    def test_fresh_state_has_todays_date(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        assert state.date == _today_str()

    def test_fresh_state_has_empty_recent_orders(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        assert state.recent_orders == []


# ---------------------------------------------------------------------------
# Day rollover (date changes, state resets)
# ---------------------------------------------------------------------------

class TestDayRollover:
    def test_rollover_resets_pnl(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        state.record_pnl(100.0)
        assert state.get_daily_pnl() == 100.0

        # Simulate date change by patching
        with patch("tiger_mcp.safety.state.date") as mock_date:
            mock_date.today.return_value = date(2099, 1, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            pnl = state.get_daily_pnl()

        assert pnl == 0.0

    def test_rollover_resets_recent_orders(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        state.record_order("fp123")

        with patch("tiger_mcp.safety.state.date") as mock_date:
            mock_date.today.return_value = date(2099, 1, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            has = state.has_recent_order("fp123", window_seconds=9999)

        assert has is False

    def test_rollover_updates_date(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)

        with patch("tiger_mcp.safety.state.date") as mock_date:
            mock_date.today.return_value = date(2099, 1, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            state.get_daily_pnl()  # triggers _ensure_today

        assert state.date == "2099-01-01"


# ---------------------------------------------------------------------------
# Persistence round-trip (save then reload)
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_pnl_survives_reload(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        state.record_pnl(42.5)
        state.record_pnl(-10.0)

        state2 = DailyState(state_dir=tmp_path)
        assert state2.get_daily_pnl() == 32.5

    def test_orders_survive_reload(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        state.record_order("abc")

        state2 = DailyState(state_dir=tmp_path)
        assert state2.has_recent_order("abc", window_seconds=9999) is True

    def test_state_file_is_created(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        state.record_pnl(1.0)

        expected_file = tmp_path / f"{_today_str()}.json"
        assert expected_file.exists()


# ---------------------------------------------------------------------------
# Duplicate detection within window
# ---------------------------------------------------------------------------

class TestDuplicateDetection:
    def test_recent_order_detected_within_window(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        state.record_order("dup_fp")
        assert state.has_recent_order("dup_fp", window_seconds=60) is True

    def test_different_fingerprint_not_detected(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        state.record_order("fp_a")
        assert state.has_recent_order("fp_b", window_seconds=60) is False

    def test_expired_order_not_detected(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        state.record_order("old_fp")

        # Patch time so the fingerprint appears old
        future_time = time.time() + 120
        with patch("tiger_mcp.safety.state.time") as mock_time:
            mock_time.time.return_value = future_time
            result = state.has_recent_order("old_fp", window_seconds=60)

        assert result is False

    def test_expired_entries_cleaned_up(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        state.record_order("old_fp")

        future_time = time.time() + 120
        with patch("tiger_mcp.safety.state.time") as mock_time:
            mock_time.time.return_value = future_time
            state.has_recent_order("old_fp", window_seconds=60)

        # After cleanup, the old entry should be removed from the list
        matching = [
            o for o in state.recent_orders if o["fingerprint"] == "old_fp"
        ]
        assert matching == []


# ---------------------------------------------------------------------------
# P&L accumulation
# ---------------------------------------------------------------------------

class TestPnlAccumulation:
    def test_multiple_pnl_records_accumulate(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        state.record_pnl(10.0)
        state.record_pnl(20.0)
        state.record_pnl(-5.0)
        assert state.get_daily_pnl() == 25.0

    def test_pnl_starts_at_zero(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        assert state.get_daily_pnl() == 0.0


# ---------------------------------------------------------------------------
# Fingerprint generation
# ---------------------------------------------------------------------------

class TestFingerprint:
    def test_determinism_same_inputs_same_hash(self) -> None:
        fp1 = DailyState.make_fingerprint("AAPL", "BUY", 100, "LMT", 150.0)
        fp2 = DailyState.make_fingerprint("AAPL", "BUY", 100, "LMT", 150.0)
        assert fp1 == fp2

    def test_uniqueness_different_symbol(self) -> None:
        fp1 = DailyState.make_fingerprint("AAPL", "BUY", 100, "LMT", 150.0)
        fp2 = DailyState.make_fingerprint("GOOG", "BUY", 100, "LMT", 150.0)
        assert fp1 != fp2

    def test_uniqueness_different_action(self) -> None:
        fp1 = DailyState.make_fingerprint("AAPL", "BUY", 100, "LMT", 150.0)
        fp2 = DailyState.make_fingerprint("AAPL", "SELL", 100, "LMT", 150.0)
        assert fp1 != fp2

    def test_uniqueness_different_quantity(self) -> None:
        fp1 = DailyState.make_fingerprint("AAPL", "BUY", 100, "LMT", 150.0)
        fp2 = DailyState.make_fingerprint("AAPL", "BUY", 200, "LMT", 150.0)
        assert fp1 != fp2

    def test_uniqueness_different_order_type(self) -> None:
        fp1 = DailyState.make_fingerprint("AAPL", "BUY", 100, "LMT", 150.0)
        fp2 = DailyState.make_fingerprint("AAPL", "BUY", 100, "MKT", 150.0)
        assert fp1 != fp2

    def test_uniqueness_different_price(self) -> None:
        fp1 = DailyState.make_fingerprint("AAPL", "BUY", 100, "LMT", 150.0)
        fp2 = DailyState.make_fingerprint("AAPL", "BUY", 100, "LMT", 155.0)
        assert fp1 != fp2

    def test_none_limit_price(self) -> None:
        fp = DailyState.make_fingerprint("AAPL", "BUY", 100, "MKT", None)
        assert isinstance(fp, str)
        assert len(fp) > 0

    def test_none_vs_zero_price_differ(self) -> None:
        fp1 = DailyState.make_fingerprint("AAPL", "BUY", 100, "MKT", None)
        fp2 = DailyState.make_fingerprint("AAPL", "BUY", 100, "MKT", 0.0)
        assert fp1 != fp2


# ---------------------------------------------------------------------------
# State directory creation
# ---------------------------------------------------------------------------

class TestStateDirectoryCreation:
    def test_creates_state_dir_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "state"
        assert not nested.exists()

        state = DailyState(state_dir=nested)
        state.record_pnl(1.0)  # triggers _save which should create dir

        assert nested.exists()
        assert nested.is_dir()

    def test_works_with_existing_dir(self, tmp_path: Path) -> None:
        state = DailyState(state_dir=tmp_path)
        state.record_pnl(5.0)
        assert state.get_daily_pnl() == 5.0
