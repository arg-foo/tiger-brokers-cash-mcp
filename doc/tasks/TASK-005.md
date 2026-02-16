# TASK-005: Daily State Tracker

## Status: pending

## Phase: 3 - Safety Layer

## Description
Implement `src/tiger_mcp/safety/state.py` to track daily trading state: realized P&L for the day and recent orders for duplicate detection. State persists as daily JSON files in `~/.tiger-mcp/state/` and auto-resets each calendar day.

## Acceptance Criteria

### Functional
- `DailyState` class tracks:
  - `date: str` (YYYY-MM-DD format)
  - `realized_pnl: float` (running total of realized P&L for the day)
  - `recent_orders: list` (recent order fingerprints with timestamps for dedup)
- Auto-reset: if current date differs from state date, reset to fresh state
- Persistence: save to `~/.tiger-mcp/state/YYYY-MM-DD.json` after each mutation
- Load from disk on startup (if today's file exists)
- `record_pnl(amount: float)` - add to daily realized P&L
- `record_order(fingerprint: str)` - store order fingerprint with timestamp
- `has_recent_order(fingerprint: str, window_seconds: int = 60) -> bool` - duplicate check
- `get_daily_pnl() -> float` - return current daily P&L
- Order fingerprint: hash of (symbol, action, quantity, order_type, limit_price)
- Clean up fingerprints older than `window_seconds` on access

### Non-Functional
- Unit tests covering: fresh state, day rollover, persistence round-trip, duplicate detection within/outside window, P&L accumulation
- No external dependencies beyond stdlib + orjson

## Dependencies
- TASK-001 (project scaffolding)
- TASK-002 (config module - for state_dir path)

## Technical Notes
- Use `orjson` for fast JSON serialization
- State directory: `config.state_dir` (default `~/.tiger-mcp/state/`)
- Create state directory if it doesn't exist
- File locking is not needed (single-process MCP server)
- Keep it simple: no database, just JSON files

## Complexity: Small
