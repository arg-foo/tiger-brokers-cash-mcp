"""Tests for TradePlanStore.

Covers: creation, multiple plans, modifications, archiving,
archive no-op, archive all, get_active_plans, get_plan,
persistence round-trip, and dataclass serialization.
"""

from __future__ import annotations

from pathlib import Path

from tiger_mcp.safety.trade_plan_store import Modification, TradePlan, TradePlanStore


# ---------------------------------------------------------------------------
# Modification dataclass serialization
# ---------------------------------------------------------------------------


class TestModificationSerialization:
    def test_to_dict_returns_all_fields(self) -> None:
        mod = Modification(
            timestamp="2026-01-15T10:30:00",
            changes={"quantity": 200, "limit_price": 155.0},
            reason="Adjusting position size",
        )
        d = mod.to_dict()
        assert d["timestamp"] == "2026-01-15T10:30:00"
        assert d["changes"] == {"quantity": 200, "limit_price": 155.0}
        assert d["reason"] == "Adjusting position size"

    def test_from_dict_round_trip(self) -> None:
        mod = Modification(
            timestamp="2026-01-15T10:30:00",
            changes={"quantity": 200},
            reason="size change",
        )
        restored = Modification.from_dict(mod.to_dict())
        assert restored.timestamp == mod.timestamp
        assert restored.changes == mod.changes
        assert restored.reason == mod.reason


# ---------------------------------------------------------------------------
# TradePlan dataclass serialization
# ---------------------------------------------------------------------------


class TestTradePlanSerialization:
    def test_to_dict_returns_all_fields(self) -> None:
        plan = TradePlan(
            order_id=12345,
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="LMT",
            limit_price=150.0,
            stop_price=None,
            reason="Bullish on earnings",
            status="active",
            created_at="2026-01-15T10:00:00",
            modified_at=None,
            archived_at=None,
            archive_reason=None,
            modifications=[],
        )
        d = plan.to_dict()
        assert d["order_id"] == 12345
        assert d["symbol"] == "AAPL"
        assert d["action"] == "BUY"
        assert d["quantity"] == 100
        assert d["order_type"] == "LMT"
        assert d["limit_price"] == 150.0
        assert d["stop_price"] is None
        assert d["reason"] == "Bullish on earnings"
        assert d["status"] == "active"
        assert d["created_at"] == "2026-01-15T10:00:00"
        assert d["modified_at"] is None
        assert d["archived_at"] is None
        assert d["archive_reason"] is None
        assert d["modifications"] == []

    def test_to_dict_includes_modifications(self) -> None:
        mod = Modification(
            timestamp="2026-01-15T10:30:00",
            changes={"quantity": 200},
            reason="size change",
        )
        plan = TradePlan(
            order_id=12345,
            symbol="AAPL",
            action="BUY",
            quantity=200,
            order_type="LMT",
            limit_price=150.0,
            stop_price=None,
            reason="Bullish",
            status="active",
            created_at="2026-01-15T10:00:00",
            modified_at="2026-01-15T10:30:00",
            archived_at=None,
            archive_reason=None,
            modifications=[mod],
        )
        d = plan.to_dict()
        assert len(d["modifications"]) == 1
        assert d["modifications"][0]["changes"] == {"quantity": 200}

    def test_from_dict_round_trip(self) -> None:
        mod = Modification(
            timestamp="2026-01-15T10:30:00",
            changes={"limit_price": 155.0},
            reason="price update",
        )
        plan = TradePlan(
            order_id=99999,
            symbol="GOOG",
            action="SELL",
            quantity=50,
            order_type="MKT",
            limit_price=None,
            stop_price=145.0,
            reason="Taking profit",
            status="archived",
            created_at="2026-01-15T09:00:00",
            modified_at="2026-01-15T09:30:00",
            archived_at="2026-01-15T10:00:00",
            archive_reason="Filled",
            modifications=[mod],
        )
        restored = TradePlan.from_dict(plan.to_dict())
        assert restored.order_id == plan.order_id
        assert restored.symbol == plan.symbol
        assert restored.action == plan.action
        assert restored.quantity == plan.quantity
        assert restored.order_type == plan.order_type
        assert restored.limit_price == plan.limit_price
        assert restored.stop_price == plan.stop_price
        assert restored.reason == plan.reason
        assert restored.status == plan.status
        assert restored.created_at == plan.created_at
        assert restored.modified_at == plan.modified_at
        assert restored.archived_at == plan.archived_at
        assert restored.archive_reason == plan.archive_reason
        assert len(restored.modifications) == 1
        assert restored.modifications[0].changes == {"limit_price": 155.0}


# ---------------------------------------------------------------------------
# TradePlanStore: creation
# ---------------------------------------------------------------------------


class TestCreatePlan:
    def test_create_returns_trade_plan(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        plan = store.create(
            order_id=100,
            symbol="AAPL",
            action="BUY",
            quantity=10,
            order_type="LMT",
            reason="Test buy",
            limit_price=150.0,
        )
        assert isinstance(plan, TradePlan)
        assert plan.order_id == 100
        assert plan.symbol == "AAPL"
        assert plan.action == "BUY"
        assert plan.quantity == 10
        assert plan.order_type == "LMT"
        assert plan.limit_price == 150.0
        assert plan.stop_price is None
        assert plan.reason == "Test buy"
        assert plan.status == "active"
        assert plan.created_at is not None
        assert plan.modified_at is None
        assert plan.archived_at is None
        assert plan.archive_reason is None
        assert plan.modifications == []

    def test_create_with_stop_price(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        plan = store.create(
            order_id=101,
            symbol="TSLA",
            action="SELL",
            quantity=5,
            order_type="STP",
            reason="Stop loss",
            stop_price=200.0,
        )
        assert plan.stop_price == 200.0
        assert plan.limit_price is None

    def test_create_multiple_plans(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy AAPL",
            limit_price=150.0,
        )
        store.create(
            order_id=200, symbol="GOOG", action="SELL",
            quantity=5, order_type="MKT", reason="Sell GOOG",
        )
        active = store.get_active_plans()
        assert len(active) == 2
        assert "100" in active
        assert "200" in active


# ---------------------------------------------------------------------------
# TradePlanStore: modifications
# ---------------------------------------------------------------------------


class TestRecordModification:
    def test_record_modification_appends_to_list(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
            limit_price=150.0,
        )
        store.record_modification(
            order_id=100,
            changes={"quantity": 20, "limit_price": 155.0},
            reason="Increased position",
        )
        plan = store.get_plan(100)
        assert plan is not None
        assert len(plan.modifications) == 1
        assert plan.modifications[0].changes == {"quantity": 20, "limit_price": 155.0}
        assert plan.modifications[0].reason == "Increased position"
        assert plan.modified_at is not None

    def test_record_multiple_modifications(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
            limit_price=150.0,
        )
        store.record_modification(100, {"quantity": 20}, "First change")
        store.record_modification(100, {"limit_price": 160.0}, "Second change")
        plan = store.get_plan(100)
        assert plan is not None
        assert len(plan.modifications) == 2
        assert plan.modifications[0].reason == "First change"
        assert plan.modifications[1].reason == "Second change"


# ---------------------------------------------------------------------------
# TradePlanStore: archiving
# ---------------------------------------------------------------------------


class TestArchive:
    def test_archive_moves_plan_from_active_to_archived(
        self, tmp_path: Path
    ) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
            limit_price=150.0,
        )
        store.archive(order_id=100, reason="Filled", archive_reason="Order filled")
        active = store.get_active_plans()
        assert "100" not in active
        plan = store.get_plan(100)
        assert plan is not None
        assert plan.status == "archived"
        assert plan.archived_at is not None
        assert plan.archive_reason == "Order filled"

    def test_archive_nonexistent_plan_is_noop(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        # Should not raise
        store.archive(order_id=99999, reason="Does not exist")

    def test_archive_all_moves_all_plans(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy AAPL",
            limit_price=150.0,
        )
        store.create(
            order_id=200, symbol="GOOG", action="SELL",
            quantity=5, order_type="MKT", reason="Sell GOOG",
        )
        store.archive_all(reason="End of day")
        active = store.get_active_plans()
        assert len(active) == 0
        # Both should still be retrievable via get_plan
        assert store.get_plan(100) is not None
        assert store.get_plan(100).status == "archived"
        assert store.get_plan(200) is not None
        assert store.get_plan(200).status == "archived"


# ---------------------------------------------------------------------------
# TradePlanStore: get_active_plans / get_plan
# ---------------------------------------------------------------------------


class TestGetPlans:
    def test_get_active_plans_returns_only_active(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
            limit_price=150.0,
        )
        store.create(
            order_id=200, symbol="GOOG", action="SELL",
            quantity=5, order_type="MKT", reason="Sell",
        )
        store.archive(order_id=100, reason="Done")
        active = store.get_active_plans()
        assert len(active) == 1
        assert "200" in active
        assert "100" not in active

    def test_get_plan_returns_active_plan(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
            limit_price=150.0,
        )
        plan = store.get_plan(100)
        assert plan is not None
        assert plan.symbol == "AAPL"

    def test_get_plan_returns_archived_plan(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
            limit_price=150.0,
        )
        store.archive(order_id=100, reason="Done")
        plan = store.get_plan(100)
        assert plan is not None
        assert plan.status == "archived"

    def test_get_plan_returns_none_for_unknown(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        assert store.get_plan(99999) is None


# ---------------------------------------------------------------------------
# TradePlanStore: persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_active_plan_survives_reload(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
            limit_price=150.0,
        )
        # Create a new store instance from the same directory
        store2 = TradePlanStore(state_dir=tmp_path)
        plan = store2.get_plan(100)
        assert plan is not None
        assert plan.symbol == "AAPL"
        assert plan.quantity == 10

    def test_archived_plan_survives_reload(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
            limit_price=150.0,
        )
        store.archive(order_id=100, reason="Done", archive_reason="Filled")

        store2 = TradePlanStore(state_dir=tmp_path)
        assert len(store2.get_active_plans()) == 0
        plan = store2.get_plan(100)
        assert plan is not None
        assert plan.status == "archived"
        assert plan.archive_reason == "Filled"

    def test_modification_survives_reload(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
            limit_price=150.0,
        )
        store.record_modification(100, {"quantity": 20}, "Changed size")

        store2 = TradePlanStore(state_dir=tmp_path)
        plan = store2.get_plan(100)
        assert plan is not None
        assert len(plan.modifications) == 1
        assert plan.modifications[0].changes == {"quantity": 20}
        assert plan.modifications[0].reason == "Changed size"

    def test_active_file_is_created(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
        )
        assert (tmp_path / "trade_plans.json").exists()

    def test_archive_file_is_created(self, tmp_path: Path) -> None:
        store = TradePlanStore(state_dir=tmp_path)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
        )
        store.archive(order_id=100, reason="Done")
        assert (tmp_path / "trade_plans_archive.json").exists()

    def test_creates_state_dir_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "state"
        assert not nested.exists()
        store = TradePlanStore(state_dir=nested)
        store.create(
            order_id=100, symbol="AAPL", action="BUY",
            quantity=10, order_type="LMT", reason="Buy",
        )
        assert nested.exists()
        assert nested.is_dir()

    def test_load_creates_state_dir_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "new" / "dir"
        assert not nested.exists()
        # Just creating the store should create the dir
        TradePlanStore(state_dir=nested)
        assert nested.exists()

    def test_corrupt_active_file_falls_back_to_empty(self, tmp_path: Path) -> None:
        """Loading a corrupt active file should log and start empty."""
        active_file = tmp_path / "trade_plans.json"
        active_file.write_bytes(b"not valid json{{{")
        store = TradePlanStore(state_dir=tmp_path)
        assert len(store.get_active_plans()) == 0

    def test_corrupt_archive_file_falls_back_to_empty(self, tmp_path: Path) -> None:
        """Loading a corrupt archive file should log and start empty."""
        archive_file = tmp_path / "trade_plans_archive.json"
        archive_file.write_bytes(b"not valid json{{{")
        store = TradePlanStore(state_dir=tmp_path)
        assert store.get_plan(99999) is None

    def test_malformed_plan_data_falls_back_to_empty(self, tmp_path: Path) -> None:
        """Loading a file with missing keys should log and start empty."""
        import orjson

        active_file = tmp_path / "trade_plans.json"
        # Valid JSON but missing required TradePlan fields
        active_file.write_bytes(orjson.dumps({"123": {"order_id": 123}}))
        store = TradePlanStore(state_dir=tmp_path)
        assert len(store.get_active_plans()) == 0
