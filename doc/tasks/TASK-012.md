# TASK-012: Integration & Verification

## Status: pending

## Phase: 6 - Integration

## Description
Final integration: register all tool domains in the server, create `.mcp.json` for Claude Code registration, update `CLAUDE.md` with Tiger-specific instructions, and verify the complete system works end-to-end.

## Acceptance Criteria

### Functional
- `server.py` imports and registers all 14 tools from all 3 domains
- `.mcp.json` configured correctly:
  ```json
  {
    "mcpServers": {
      "tiger": {
        "command": "uv",
        "args": ["--directory", "/Users/zifcrypto/Desktop/tiger-brokers-cash-mcp", "run", "python", "-m", "tiger_mcp"],
        "env": { "TIGER_ID": "", "TIGER_ACCOUNT": "", "TIGER_PRIVATE_KEY_PATH": "", "TIGER_SANDBOX": "true" }
      }
    }
  }
  ```
- All 14 tools visible when server starts
- Tool names follow pattern: `get_account_summary`, `place_stock_order`, etc.

### Non-Functional
- `uv sync` succeeds
- `uv run python -m tiger_mcp --check` (or similar) starts and registers 14 tools
- `uv run pytest tests/ --cov=tiger_mcp` - all tests pass, >80% coverage
- `uv run ruff check src/ tests/` - no lint errors
- `uv run mypy src/` - no type errors (or documented exclusions)

## Dependencies
- TASK-007 (account tools)
- TASK-008 (market data tools)
- TASK-009 (order query tools)
- TASK-010 (order execution tools)
- TASK-011 (order management tools)

## Technical Notes
- This is the final assembly task - all pieces should be built and tested individually by now
- The `.mcp.json` path should match the actual project location
- Consider adding a `--check` CLI flag that starts the server, lists tools, then exits (useful for CI)
- CLAUDE.md should include usage patterns, safety warnings, and example workflows

## Complexity: Small
