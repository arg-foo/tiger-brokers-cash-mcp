# TASK-006: Pre-Trade Safety Checks

## Status: pending

## Phase: 3 - Safety Layer

## Description
Implement `src/tiger_mcp/safety/checks.py` with 6 pre-trade validation checks that run before every order placement. Checks return errors (hard blocks) or warnings (informational). This is the core safety mechanism for cash account enforcement.

## Acceptance Criteria

### Functional
- `SafetyResult` dataclass with `passed: bool`, `errors: list[str]`, `warnings: list[str]`
- `run_safety_checks(order, account_info, positions, config, state) -> SafetyResult`
- 6 checks implemented:
  1. **Block short selling**: SELL action when position is 0 or quantity > held shares -> error
  2. **Buying power check**: estimated order cost > available cash -> error
  3. **Max order value**: order value > `config.max_order_value` (when > 0) -> error
  4. **Position concentration**: order value > `config.max_position_pct * portfolio_value` (when > 0) -> warning
  5. **Daily loss limit**: `state.get_daily_pnl()` already exceeds `config.daily_loss_limit` (when > 0) -> error
  6. **Duplicate detection**: `state.has_recent_order(fingerprint)` -> warning
- For BUY orders: estimate cost as `quantity * (limit_price or last_price) * 1.01` (1% buffer for market orders)
- For SELL orders: no buying power check needed
- Checks with limit=0 (disabled) are skipped
- All checks run even if early ones fail (collect all issues)

### Non-Functional
- 10+ unit test scenarios:
  - Valid buy order passes all checks
  - Valid sell order passes all checks
  - Short sell blocked (no position)
  - Short sell blocked (insufficient shares)
  - Insufficient buying power
  - Max order value exceeded
  - Position concentration warning
  - Daily loss limit hit
  - Duplicate order warning
  - Multiple failures at once
  - Disabled checks (limit=0) are skipped
- Tests use fixtures, no real API calls

## Dependencies
- TASK-002 (config module)
- TASK-005 (daily state tracker)

## Technical Notes
- Order parameter structure: `symbol`, `action` (BUY/SELL), `quantity`, `order_type` (MKT/LMT/STP/STP_LMT/TRAIL), `limit_price`, `stop_price`
- For market orders without a limit price, use the last traded price from quotes
- The safety layer is independent of the API client - it takes pre-fetched data as inputs
- Warnings don't block execution, errors do

## Complexity: Medium
