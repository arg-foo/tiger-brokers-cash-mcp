# Tiger Brokers MCP Server

An MCP (Model Context Protocol) server that gives AI assistants programmatic access to Tiger Brokers cash account trading. Supports real-time stock trading, account monitoring, and market data retrieval for US equities with built-in safety checks.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- A Tiger Brokers account with API access
- An RSA private key (PKCS#1 format) from Tiger Brokers

## Quick Start (Docker)

### 1. Clone the repository

```bash
git clone <repo-url>
cd tiger-brokers-cash-mcp
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Required
TIGER_ID=your_tiger_developer_id
TIGER_ACCOUNT=your_account_number

# Optional safety limits (0 = no limit)
TIGER_MAX_ORDER_VALUE=5000
TIGER_DAILY_LOSS_LIMIT=1000
TIGER_MAX_POSITION_PCT=0.25
```

### 3. Place your private key

Copy your Tiger Brokers RSA private key to the project root:

```bash
cp /path/to/your/private.pem ./private.pem
```

> The key is mounted read-only into the container at `/secrets/private.pem`. Never commit this file to git (it's already in `.gitignore`).

### 4. Start the server

```bash
docker compose up -d
```

The server starts on port **8000** with the streamable-http transport. Verify it's running:

```bash
curl http://localhost:8000/health
```

### 5. Connect your MCP client

Point your MCP client to `http://localhost:8000` using the `streamable-http` transport.

**Claude Desktop example** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "tiger": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Claude Code example** (`.mcp.json`):

```json
{
  "mcpServers": {
    "tiger": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Available Tools

### Account (4 tools)

| Tool | Description |
|------|-------------|
| `get_account_summary` | Returns cash balance, buying power, realized/unrealized P&L, and net liquidation value |
| `get_buying_power` | Returns available buying power and current cash balance |
| `get_positions` | Lists all current holdings with quantity, average cost, market value, and unrealized P&L |
| `get_transaction_history` | Returns execution history. Optional filters: `symbol`, `start_date`, `end_date`, `limit` |

### Market Data (3 tools)

| Tool | Description |
|------|-------------|
| `get_stock_quote` | Real-time quote for a single symbol (price, bid/ask, volume, change) |
| `get_stock_quotes` | Batch quotes for up to 50 comma-separated symbols |
| `get_stock_bars` | OHLCV bar data. Params: `symbol`, `period` (`1d`, `1w`, `1m`, `3m`, `6m`, `1y`), `limit` |

### Orders (9 tools)

#### Execution

| Tool | Description |
|------|-------------|
| `preview_stock_order` | Simulates an order with all safety checks. Returns estimated cost, commission, and safety results without executing |
| `place_stock_order` | Places an order after passing all safety checks. Params: `symbol`, `action` (BUY/SELL), `quantity`, `order_type` (MKT, LMT, STP, STP_LMT, TRAIL), optional `limit_price`/`stop_price`, required `reason` |

#### Management

| Tool | Description |
|------|-------------|
| `modify_order` | Modifies an open order's quantity, limit price, or stop price |
| `cancel_order` | Cancels a specific open order by ID |
| `cancel_all_orders` | Cancels all open orders |

#### Query

| Tool | Description |
|------|-------------|
| `get_open_orders` | Lists open/partially-filled orders. Optional `symbol` filter |
| `get_order_detail` | Full details for a specific order by ID |

#### Trade Plans

| Tool | Description |
|------|-------------|
| `get_trade_plans` | Lists all active trade plans with reasons and modification history |
| `mark_order_filled` | Archives a trade plan as filled |

## Safety System

Six pre-trade checks run automatically before every order placement:

| Check | Type | Description |
|-------|------|-------------|
| Short selling block | Error | Prevents selling more shares than currently held |
| Buying power | Error | Ensures sufficient cash for BUY orders |
| Max order value | Error | Blocks orders exceeding `TIGER_MAX_ORDER_VALUE` |
| Position concentration | Warning | Alerts if a position would exceed `TIGER_MAX_POSITION_PCT` of the portfolio |
| Daily loss limit | Error | Blocks trading if realized losses exceed `TIGER_DAILY_LOSS_LIMIT` |
| Duplicate detection | Warning | Alerts on identical orders placed within 60 seconds |

**Errors** block order execution. **Warnings** are informational and do not block.

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TIGER_ID` | Yes | - | Tiger Brokers developer ID |
| `TIGER_ACCOUNT` | Yes | - | Trading account number |
| `TIGER_PRIVATE_KEY_PATH` | Yes | - | Path to RSA private key (set automatically in Docker) |
| `TIGER_MAX_ORDER_VALUE` | No | `0` | Max single order value in USD (0 = unlimited) |
| `TIGER_DAILY_LOSS_LIMIT` | No | `0` | Max daily realized loss in USD (0 = unlimited) |
| `TIGER_MAX_POSITION_PCT` | No | `0` | Max position as fraction of portfolio, e.g. `0.25` (0 = unlimited) |
| `MCP_TRANSPORT` | No | `stdio` | Transport protocol: `stdio` or `streamable-http` |
| `MCP_HOST` | No | `0.0.0.0` | Bind host for HTTP transport |
| `MCP_PORT` | No | `8000` | Bind port for HTTP transport |

### Docker Volumes

| Mount | Purpose |
|-------|---------|
| `./private.pem:/secrets/private.pem:ro` | RSA private key (read-only) |
| `tiger-state:/data/state` | Persistent trade state (daily P&L, trade plans) |

## Local Development (without Docker)

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install dependencies
uv sync

# Run the server (stdio transport)
uv run python -m tiger_mcp

# Run tests
uv run pytest

# Lint and format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/ tests/
```

## License

Private - All rights reserved.
