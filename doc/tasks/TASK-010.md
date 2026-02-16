# TASK-010: Order Execution Tools (2 tools)

## Status: pending

## Phase: 5 - Order Tools

## Description
Implement 2 MCP tools in `src/tiger_mcp/tools/orders/` for order preview and placement: `preview_stock_order` and `place_stock_order`. These are the most critical tools as they involve real money. Both run the full safety check suite before proceeding.

## Acceptance Criteria

### Functional
- **`preview_stock_order`** (params: `symbol`, `action`, `quantity`, `order_type`, `limit_price?`, `stop_price?`):
  - Runs ALL 6 safety checks
  - Calls `TigerClient.preview_order()` for cost estimate
  - Returns: estimated cost, commission, safety check results (errors + warnings)
  - Does NOT execute the order
  - Returns safety errors/warnings even if preview succeeds

- **`place_stock_order`** (params: same as preview):
  - Runs ALL 6 safety checks
  - If any safety ERROR -> return error, do NOT place order
  - If only warnings -> include warnings in response, proceed with order
  - Calls `TigerClient.place_order()`
  - Records order in daily state (for dedup tracking)
  - Returns: order_id, status, fill details, any warnings

- Parameter validation:
  - `symbol`: non-empty, uppercase
  - `action`: must be `BUY` or `SELL`
  - `quantity`: positive integer
  - `order_type`: must be one of `MKT`, `LMT`, `STP`, `STP_LMT`, `TRAIL`
  - `limit_price`: required for `LMT` and `STP_LMT`
  - `stop_price`: required for `STP` and `STP_LMT`
  - `TRAIL` requires appropriate trailing parameters

### Non-Functional
- Comprehensive unit tests:
  - Preview with valid order
  - Preview with safety errors (blocked)
  - Place order success (all checks pass)
  - Place order blocked by safety error
  - Place order with warnings (proceeds)
  - Invalid parameters (bad symbol, negative quantity, missing limit price for LMT)
  - API error handling
- All tests use mocked TigerClient and mocked safety state

## Dependencies
- TASK-004 (API client)
- TASK-006 (safety checks)
- TASK-005 (daily state)

## Technical Notes
- This is the highest-risk tool - correctness is critical
- Safety checks must run BEFORE any API call to place the order
- For market orders, fetch current quote to estimate cost for safety checks
- Order fingerprint for dedup: hash of (symbol, action, quantity, order_type, limit_price)
- After successful placement, record the order fingerprint in DailyState
- Consider logging all order attempts (success and failure) for audit trail

## Complexity: Large
