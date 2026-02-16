# TASK-003: Server Skeleton

## Status: pending

## Phase: 1 - Scaffolding

## Description
Implement `src/tiger_mcp/server.py` with FastMCP server initialization, `src/tiger_mcp/__main__.py` as the entry point, and the tool domain registration pattern. The server should start, register itself, but have no tools yet (those come in later tasks).

## Acceptance Criteria

### Functional
- `server.py` creates a `FastMCP` server instance with name "tiger"
- `server.py` includes a `main()` async function that:
  - Loads configuration via `config.py`
  - Initializes structured logging (structlog to stderr)
  - Creates the server and runs it with stdio transport
- `__main__.py` calls `asyncio.run(main())` for `python -m tiger_mcp` invocation
- Server starts successfully in check mode (no crash on import)

### Non-Functional
- `uv run python -m tiger_mcp` starts without errors (when credentials are not required for startup)
- Structured logging outputs to stderr, not stdout (stdout is reserved for MCP transport)

## Dependencies
- TASK-001 (project scaffolding)
- TASK-002 (config module)

## Technical Notes
- FastMCP from `mcp` package: `from mcp.server.fastmcp import FastMCP`
- stdio transport: server reads/writes MCP JSON-RPC on stdin/stdout
- All log output MUST go to stderr to avoid corrupting the MCP transport
- Tool domains will be registered in later tasks by importing and calling registration functions
- Consider a lifespan context manager for client initialization/cleanup

## Complexity: Small
