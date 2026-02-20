# Tiger MCP Server - Implementation Plan

## Context

Create a **separate MCP server** for Tiger Brokers to enable **spot stock trading only** with a basic cash account. This complements the existing Zaza MCP (research-only, 66 tools) by adding trade execution capabilities (14 tools). Claude Code will run both servers side-by-side: Zaza for analysis, Tiger for execution.

The Tiger Brokers API is accessed via the `tigeropen` Python SDK (v3.5+), which uses RSA key-based authentication and provides `TradeClient` and `QuoteClient`. **Scope: US stocks only, spot orders only (no options).**

## Project Location

`/Users/zifcrypto/Desktop/tiger-mcp` (new repository, independent of Zaza)

## Project Structure

```
tiger-mcp/
├── pyproject.toml                 # hatchling build, uv, Python 3.12+
├── .mcp.json                      # MCP server registration for Claude Code
├── .env.example                   # Template for credentials + safety limits
├── .gitignore
├── CLAUDE.md                      # Agent instructions
├── src/tiger_mcp/
│   ├── __init__.py                # __version__
│   ├── __main__.py                # asyncio.run(main())
│   ├── server.py                  # FastMCP server, domain registry
│   ├── config.py                  # Env vars, safety limits, paths
│   ├── api/
│   │   ├── __init__.py
│   │   └── tiger_client.py        # Wraps TradeClient + QuoteClient
│   ├── safety/
│   │   ├── __init__.py
│   │   ├── checks.py             # Pre-trade validation (6 checks)
│   │   └── state.py              # Daily P&L tracker, order dedup
│   └── tools/
│       ├── __init__.py
│       ├── account/              # 4 tools
│       ├── orders/               # 7 tools
│       └── market_data/          # 3 tools
└── tests/
    ├── conftest.py               # Mock TigerClient, DailyState fixtures
    ├── test_safety.py            # Safety layer tests (10+ scenarios)
    └── tools/                    # Per-domain tool tests
```

## 14 MCP Tools (3 domains)

### Account (4 tools)
| Tool | Params | Purpose |
|------|--------|---------|
| `get_account_summary` | - | Cash balance, buying power, P&L, net liquidation |
| `get_buying_power` | - | Available cash minus pending buy orders |
| `get_positions` | - | Current holdings with cost, market value, unrealized P&L |
| `get_transaction_history` | `symbol?`, `start_date?`, `end_date?`, `limit?` | Execution history |

### Orders (7 tools)
| Tool | Params | Purpose |
|------|--------|---------|
| `preview_stock_order` | `symbol`, `action`, `quantity`, `order_type`, `limit_price?`, `stop_price?` | Dry run with cost estimate + safety checks. Does NOT execute. |
| `place_stock_order` | same as preview | Execute order after all safety checks pass |
| `modify_order` | `order_id`, `quantity?`, `limit_price?`, `stop_price?` | Change open order |
| `cancel_order` | `order_id` | Cancel specific order |
| `cancel_all_orders` | - | Cancel all open orders |
| `get_open_orders` | `symbol?` | List unfilled/partial orders |
| `get_order_detail` | `order_id` | Full order details with fill info |

Order types: `MKT`, `LMT`, `STP`, `STP_LMT`, `TRAIL`

### Market Data (3 tools)
| Tool | Params | Purpose |
|------|--------|---------|
| `get_stock_quote` | `symbol` | Real-time quote with bid/ask |
| `get_stock_quotes` | `symbols` (comma-sep, max 50) | Batch quotes |
| `get_stock_bars` | `symbol`, `period`, `limit?` | Historical OHLCV |

## Safety Layer (Cash Account Enforcement)

6 pre-trade checks run before every order:

1. **Block short selling** - SELL stock you don't hold (or more than you hold) → error
2. **Buying power check** - order cost > available cash → error
3. **Max order value** - exceeds `TIGER_MAX_ORDER_VALUE` → error
4. **Position concentration** - order > `TIGER_MAX_POSITION_PCT` of portfolio → warning
5. **Daily loss limit** - realized losses exceed `TIGER_DAILY_LOSS_LIMIT` → error
6. **Duplicate detection** - identical order within 60s → warning

State tracked via daily JSON files in `~/.tiger-mcp/state/` (auto-reset each day).

## API Client Design

`TigerClient` wraps `tigeropen`'s synchronous SDK:
- All blocking SDK calls run via `asyncio.run_in_executor()` to avoid blocking the MCP event loop
- **No caching** for account/positions/orders (must always be fresh)
- Market data: minimal 30s cache for quotes only
- Singleton created at server startup, injected into all tool domains

## Configuration

Environment variables:
```
# Required
TIGER_ID=                          # Developer ID
TIGER_ACCOUNT=                     # Trading account number
TIGER_PRIVATE_KEY_PATH=            # Path to PKCS#1 RSA private key

# Safety (defaults shown)
TIGER_MAX_ORDER_VALUE=0            # 0 = no limit
TIGER_DAILY_LOSS_LIMIT=0           # 0 = no limit
TIGER_MAX_POSITION_PCT=0           # 0 = no limit (e.g., 0.25 = 25%)
```

## Dependencies

```
mcp>=1.20,<2.0          # MCP SDK (FastMCP)
tigeropen>=3.5,<4.0     # Tiger Brokers SDK
pandas>=2.1,<3.0        # DataFrame handling from SDK responses
structlog>=24.0,<26.0   # Structured logging to stderr
orjson>=3.9,<4.0        # Fast JSON serialization
```

Dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-timeout`, `ruff`, `mypy`

## Claude Code Integration

Register in `.mcp.json`:
```json
{
  "mcpServers": {
    "tiger": {
      "command": "uv",
      "args": ["--directory", "/Users/zifcrypto/Desktop/tiger-mcp", "run", "python", "-m", "tiger_mcp.server"],
      "env": { "TIGER_ID": "", "TIGER_ACCOUNT": "", "TIGER_PRIVATE_KEY_PATH": "" }
    }
  }
}
```

Tools appear as `mcp__tiger__place_stock_order`, etc. alongside Zaza's `mcp__zaza__get_price_snapshot`.

## Implementation Phases

1. **Scaffolding** - project structure, pyproject.toml, config.py, server.py skeleton → verify `uv sync` + `--check`
2. **API Client** - `tiger_client.py` with thread pool executor, all methods (account, orders, quotes)
3. **Safety Layer** - checks.py, state.py, full test suite (10+ scenarios)
4. **Account + Market Data tools** (7 tools) + tests
5. **Order tools** (7 tools) with safety integration + tests
6. **Integration** - CLAUDE.md, .mcp.json, end-to-end test

## Verification

1. `uv sync` - dependencies install
2. `uv run python -m tiger_mcp.server --check` - server starts, registers 14 tools
3. `uv run pytest tests/ --cov=tiger_mcp` - all tests pass, >80% coverage
4. `uv run ruff check src/ tests/` - no lint errors
5. Manual test: place a test order via Claude Code using a paper account
