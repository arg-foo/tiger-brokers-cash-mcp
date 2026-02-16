# TASK-007: Account Tools (4 tools)

## Status: pending

## Phase: 4 - Account & Market Data Tools

## Description
Implement 4 MCP tools in `src/tiger_mcp/tools/account/` for account information retrieval: `get_account_summary`, `get_buying_power`, `get_positions`, and `get_transaction_history`.

## Acceptance Criteria

### Functional
- **`get_account_summary`** (no params):
  - Returns: cash balance, buying power, P&L, net liquidation value
  - Calls `TigerClient.get_assets()`
  - Formats as readable text response

- **`get_buying_power`** (no params):
  - Returns: available cash minus value of pending buy orders
  - Calls `TigerClient.get_assets()`
  - Single focused value with context

- **`get_positions`** (no params):
  - Returns: current holdings with symbol, quantity, avg cost, market value, unrealized P&L, P&L %
  - Calls `TigerClient.get_positions()`
  - Handles empty portfolio gracefully

- **`get_transaction_history`** (params: `symbol?`, `start_date?`, `end_date?`, `limit?`):
  - Returns: execution history (fills)
  - Calls `TigerClient.get_order_transactions()`
  - Optional filters for symbol, date range, count limit
  - Default limit: 50

- All tools registered with FastMCP via `@mcp.tool()` decorator
- All tools return structured text (not raw JSON) for LLM readability
- All tools handle API errors gracefully with descriptive messages

### Non-Functional
- Unit tests for each tool with mocked TigerClient
- Tests verify correct parameter passing to client
- Tests verify response formatting
- Tests verify error handling

## Dependencies
- TASK-003 (server skeleton - for FastMCP registration)
- TASK-004 (API client - for TigerClient)

## Technical Notes
- Tools are async functions decorated with `@mcp.tool()`
- Access TigerClient via server context/dependency injection
- Format numbers nicely: currency with 2 decimals, percentages with 2 decimals
- Tool descriptions should be clear for LLM consumption (Claude reads them to decide which tool to use)

## Complexity: Medium
