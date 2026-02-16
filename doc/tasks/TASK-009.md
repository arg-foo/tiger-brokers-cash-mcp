# TASK-009: Order Query Tools (2 tools)

## Status: COMPLETED

## Phase: 5 - Order Tools

## Description
Implement 2 read-only MCP tools in `src/tiger_mcp/tools/orders/` for querying order status: `get_open_orders` and `get_order_detail`.

## Acceptance Criteria

### Functional
- **`get_open_orders`** (params: `symbol?: str`):
  - Returns: list of unfilled/partially filled orders
  - Calls `TigerClient.get_open_orders()`
  - Optional symbol filter
  - Shows: order_id, symbol, action, quantity, filled_quantity, order_type, limit_price, status, submitted_at
  - Handles empty list gracefully ("No open orders")

- **`get_order_detail`** (params: `order_id: int`):
  - Returns: full order details including fill information
  - Calls `TigerClient.get_order_detail()`
  - Shows: all order fields, fills, average fill price, commissions
  - Handles invalid order_id with clear error

- All tools registered with FastMCP
- All tools return structured text for LLM readability

### Non-Functional
- Unit tests for each tool with mocked TigerClient
- Tests verify parameter passing
- Tests verify formatting
- Tests verify error handling (invalid order_id, no orders found)

## Dependencies
- TASK-003 (server skeleton)
- TASK-004 (API client)

## Technical Notes
- These are read-only tools, no safety checks needed
- Order statuses from tigeropen: `Initial`, `PendingSubmit`, `Submitted`, `Filled`, `PartiallyFilled`, `Cancelled`, `Inactive`, `Invalid`
- Separate from execution tools to keep the module focused

## Complexity: Small
