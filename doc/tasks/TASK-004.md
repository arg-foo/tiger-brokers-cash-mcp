# TASK-004: Tiger API Client

## Status: COMPLETED

## Phase: 2 - API Client

## Description
Implement `src/tiger_mcp/api/tiger_client.py` wrapping the `tigeropen` SDK's `TradeClient` and `QuoteClient`. All blocking SDK calls must run via `asyncio.run_in_executor()` to avoid blocking the MCP event loop. This is the single integration point with the Tiger Brokers API.

## Acceptance Criteria

### Functional
- `TigerClient` class wraps both `TradeClient` and `QuoteClient` from `tigeropen`
- Constructor accepts config and initializes both clients with RSA key auth
- Async methods for all operations needed by tools:
  - **Account**: `get_assets()`, `get_positions()`, `get_order_transactions()`
  - **Orders**: `preview_order()`, `place_order()`, `modify_order()`, `cancel_order()`, `cancel_all_orders()`, `get_open_orders()`, `get_order_detail()`
  - **Quotes**: `get_quote()`, `get_quotes()`, `get_bars()`
- All SDK calls wrapped with `asyncio.get_event_loop().run_in_executor(None, ...)`
- Market data quotes cached for 30 seconds (minimal TTL cache)
- No caching for account, positions, or order data (must always be fresh)
- Proper error handling: SDK exceptions wrapped into descriptive error messages
- Singleton pattern or dependency injection for server-wide use

### Non-Functional
- Unit tests with mocked `TradeClient`/`QuoteClient` (no real API calls)
- Tests verify async wrapping works correctly
- Tests verify cache behavior (hit/miss/expiry)

## Dependencies
- TASK-001 (project scaffolding)
- TASK-002 (config module)

## Technical Notes
- `tigeropen` SDK authentication:
  ```python
  from tigeropen.common.consts import Language
  from tigeropen.tiger_open_config import TigerOpenClientConfig
  client_config = TigerOpenClientConfig(sandbox_debug=config.sandbox)
  client_config.private_key = read_private_key(config.private_key_path)
  client_config.tiger_id = config.tiger_id
  client_config.account = config.tiger_account
  client_config.language = Language.en_US
  ```
- Use `concurrent.futures.ThreadPoolExecutor` (default) for `run_in_executor`
- For quote caching, consider `functools.lru_cache` with time-based invalidation or a simple dict with timestamps
- The SDK returns pandas DataFrames for many calls - handle appropriately
- Scope is US stocks only - no options, no futures

## Complexity: Medium
