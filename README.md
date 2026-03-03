# Tiger Brokers MCP Server

An MCP (Model Context Protocol) server that gives AI assistants programmatic access to Tiger Brokers cash account trading. Supports real-time stock trading, account monitoring, and market data retrieval for US equities with built-in safety checks.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- A Tiger Brokers account with API access
- An RSA private key (PKCS#1 format) from Tiger Brokers

## Quick Start (Docker)

### 1. Clone the repository

```bash
git clone git@github.com:arg-foo/tiger-brokers-cash-mcp.git
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

Copy your Tiger Brokers RSA private key into the `secrets/` directory:

```bash
mkdir -p secrets
cp /path/to/your/private.pem ./secrets/private.pem
```

> The key is mounted read-only into the container at `/secrets/private.pem`. Never commit this file to git (the `secrets/` directory is already in `.gitignore`).

### 4. Start the server

```bash
docker compose up -d
```

The server starts on port **8000** with the streamable-http transport. Verify it's running:

```bash
curl http://localhost:8000/health
```

### 5. Connect your MCP client

When running via Docker, the server uses the `streamable-http` transport on port **8000**. Point your MCP client to `http://localhost:8000/mcp`.

> If you changed `MCP_PORT` in your `.env`, replace `8000` with your chosen port in the URLs below.

**Claude Desktop** — add to `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "tiger": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Claude Code** — add to `.mcp.json` in your project root (or `~/.claude/.mcp.json` for global access):

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

**Other MCP clients** — use any client that supports the `streamable-http` transport with the URL `http://localhost:8000/mcp`.

> **Remote access**: To connect from another machine, replace `localhost` with the host's IP or hostname. Ensure port 8000 is open and consider placing a reverse proxy (e.g. nginx, Caddy) in front for TLS.

### Docker Management

```bash
# View logs
docker compose logs -f tiger-mcp

# Restart the server
docker compose restart tiger-mcp

# Rebuild after code changes
docker compose up -d --build

# Stop everything
docker compose down

# Stop and remove volumes (clears all persistent data)
docker compose down -v
```

## Available Tools

### Account (4 tools)

| Tool | Description |
|------|-------------|
| `get_account_summary` | Returns cash balance, buying power, realized/unrealized P&L, and net liquidation value |
| `get_buying_power` | Returns available buying power and current cash balance |
| `get_positions` | Lists all current holdings with quantity, average cost, market value, and unrealized P&L |
| `get_transaction_history` | Returns execution history. Optional filters: `symbol`, `start_date`, `end_date`, `limit` |

### Market Data (1 tool)

| Tool | Description |
|------|-------------|
| `get_stock_bars` | Historical OHLCV bar data. Params: `symbol`, `period` (`1d`, `1w`, `1m`, `3m`, `6m`, `1y`), `limit` |

### Orders (7 tools)

#### Execution

| Tool | Description |
|------|-------------|
| `preview_stock_order` | Simulates an order with all safety checks. Returns estimated cost, commission, and safety results without executing |
| `place_stock_order` | Places an order after passing all safety checks. Params: `symbol`, `action` (BUY/SELL), `quantity`, `order_type` (LMT, STP_LMT), `limit_price` (required), `stop_price` (required for STP_LMT) |

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
| `TIGER_STATE_DIR` | No | `~/.tiger-mcp/state` | Directory for persistent state files (daily P&L, order dedup) |
| `MCP_TRANSPORT` | No | `stdio` | Transport protocol: `stdio` or `streamable-http` |
| `MCP_HOST` | No | `0.0.0.0` | Bind host for HTTP transport |
| `MCP_PORT` | No | `8000` | Bind port for HTTP transport |
| `REDIS_PORT` | No | `6379` | Host port for Redis (Docker only) |
| `TIGER_EVENTS_ENABLED` | No | `false` | Enable Tiger WebSocket event subscription (`true` by default in Docker) |
| `REDIS_URL` | No | - | Redis connection URL (required if events enabled, set automatically in Docker) |
| `REDIS_STREAM_PREFIX` | No | `tiger:events` | Redis stream key prefix |
| `REDIS_STREAM_MAXLEN` | No | `10000` | Max entries per Redis stream |

### Docker Volumes

| Mount | Purpose |
|-------|---------|
| `./secrets/private.pem:/secrets/private.pem:ro` | RSA private key (read-only) |
| `tiger-state:/data/state` | Persistent state (daily P&L tracking, duplicate order detection) |
| `redis-data:/data` | Persistent Redis data (event streams) |

## Local Development (without Docker)

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install dependencies
uv sync

# Run the server (stdio transport)
uv run --env-file .env python -m tiger_mcp

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
