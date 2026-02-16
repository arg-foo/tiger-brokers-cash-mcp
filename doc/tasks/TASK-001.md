# TASK-001: Project Scaffolding

## Status: COMPLETED

## Phase: 1 - Scaffolding

## Description
Create the full project directory structure, `pyproject.toml` with hatchling build system, `.gitignore`, `.env.example`, and empty `__init__.py` files for all packages.

## Acceptance Criteria

### Functional
- Directory structure matches design doc exactly:
  - `src/tiger_mcp/` with `__init__.py` (containing `__version__`)
  - `src/tiger_mcp/api/` with `__init__.py`
  - `src/tiger_mcp/safety/` with `__init__.py`
  - `src/tiger_mcp/tools/` with `__init__.py`
  - `src/tiger_mcp/tools/account/` with `__init__.py`
  - `src/tiger_mcp/tools/orders/` with `__init__.py`
  - `src/tiger_mcp/tools/market_data/` with `__init__.py`
  - `tests/` with `conftest.py`
  - `tests/tools/` directory
- `pyproject.toml` configured with:
  - `hatchling` build backend
  - Python `>=3.12`
  - All production dependencies: `mcp>=1.20,<2.0`, `tigeropen>=3.5,<4.0`, `pandas>=2.1,<3.0`, `structlog>=24.0,<26.0`, `orjson>=3.9,<4.0`
  - All dev dependencies: `pytest>=8.0,<9.0`, `pytest-asyncio>=0.23,<1.0`, `pytest-cov>=5.0,<6.0`, `pytest-timeout>=2.2,<3.0`, `respx>=0.21,<1.0`, `ruff>=0.8,<1.0`, `mypy>=1.7,<2.0`
  - Entry point: `tiger-mcp = "tiger_mcp.__main__:main"`
- `.env.example` with all env vars documented (TIGER_ID, TIGER_ACCOUNT, TIGER_PRIVATE_KEY_PATH, TIGER_SANDBOX, TIGER_MAX_ORDER_VALUE, TIGER_DAILY_LOSS_LIMIT, TIGER_MAX_POSITION_PCT)
- `.gitignore` with Python, uv, IDE, `.env` patterns

### Non-Functional
- `uv sync` completes successfully
- `uv run ruff check src/ tests/` passes with no errors

## Dependencies
- None (first task)

## Technical Notes
- Use `hatchling` as the build backend (not setuptools)
- Package uses `src/` layout
- Python version constraint: `>=3.12`

## Complexity: Small
