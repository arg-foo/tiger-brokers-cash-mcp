# TASK-011: Order Management Tools (3 tools)

## Status: pending

## Phase: 5 - Order Tools

## Description
Implement 3 MCP tools in `src/tiger_mcp/tools/orders/` for managing existing orders: `modify_order`, `cancel_order`, and `cancel_all_orders`.

## Acceptance Criteria

### Functional
- **`modify_order`** (params: `order_id: int`, `quantity?: int`, `limit_price?: float`, `stop_price?: float`):
  - At least one modification parameter must be provided
  - Fetches current order details to validate it's open/modifiable
  - Runs relevant safety checks on the modified values (e.g., if increasing quantity, check buying power)
  - Calls `TigerClient.modify_order()`
  - Returns: updated order details, any warnings

- **`cancel_order`** (params: `order_id: int`):
  - Validates order exists and is cancellable
  - Calls `TigerClient.cancel_order()`
  - Returns: cancellation confirmation with order details

- **`cancel_all_orders`** (no params):
  - Calls `TigerClient.cancel_all_orders()`
  - Returns: count of cancelled orders, list of order_ids cancelled
  - Handles case of no open orders gracefully

### Non-Functional
- Unit tests:
  - Modify order success
  - Modify order with no changes (error)
  - Modify non-existent order (error)
  - Cancel order success
  - Cancel already-cancelled order (error)
  - Cancel all with open orders
  - Cancel all with no orders
- All tests use mocked TigerClient

## Dependencies
- TASK-003 (server skeleton)
- TASK-004 (API client)
- TASK-006 (safety checks - for modify validation)

## Technical Notes
- Only open/partially-filled orders can be modified or cancelled
- For `modify_order`, if quantity is increased, re-run buying power check
- `cancel_all_orders` is a convenience tool - it's the "emergency stop" button
- All modifications should be logged for audit trail

## Complexity: Medium
