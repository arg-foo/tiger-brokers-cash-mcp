# TASK-008: Market Data Tools (3 tools)

## Status: COMPLETED

## Phase: 4 - Account & Market Data Tools

## Description
Implement 3 MCP tools in `src/tiger_mcp/tools/market_data/` for stock quotes and historical data: `get_stock_quote`, `get_stock_quotes`, and `get_stock_bars`.

## Acceptance Criteria

### Functional
- **`get_stock_quote`** (params: `symbol: str`):
  - Returns: real-time quote with last price, bid/ask, volume, change, change %
  - Calls `TigerClient.get_quote()`
  - Symbol validated (uppercase, non-empty)

- **`get_stock_quotes`** (params: `symbols: str` comma-separated):
  - Returns: batch quotes for multiple symbols (max 50)
  - Calls `TigerClient.get_quotes()`
  - Validates symbol count <= 50
  - Parses comma-separated string, trims whitespace

- **`get_stock_bars`** (params: `symbol: str`, `period: str`, `limit?: int`):
  - Returns: historical OHLCV bars
  - Calls `TigerClient.get_bars()`
  - Period values: `1d`, `1w`, `1m`, `3m`, `6m`, `1y`
  - Default limit: 100
  - Formats as table-like text

- All tools registered with FastMCP
- All tools return structured text for LLM readability
- All tools handle API errors gracefully

### Non-Functional
- Unit tests for each tool with mocked TigerClient
- Tests verify parameter validation (invalid symbol, too many symbols, invalid period)
- Tests verify response formatting

## Dependencies
- TASK-003 (server skeleton)
- TASK-004 (API client)

## Technical Notes
- Quote data benefits from the 30s cache in TigerClient
- Symbols should be uppercased before passing to API
- Period mapping to tigeropen SDK's `BarPeriod` enum
- For bars, consider formatting as a compact table or structured list

## Complexity: Small
