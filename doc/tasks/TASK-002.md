# TASK-002: Configuration Module

## Status: COMPLETED

## Phase: 1 - Scaffolding

## Description
Implement `src/tiger_mcp/config.py` to load all configuration from environment variables with validation, defaults, and typed access. This is the central configuration for credentials, safety limits, and file paths.

## Acceptance Criteria

### Functional
- `config.py` defines a configuration class/dataclass with:
  - `tiger_id: str` (required, from `TIGER_ID`)
  - `tiger_account: str` (required, from `TIGER_ACCOUNT`)
  - `private_key_path: Path` (required, from `TIGER_PRIVATE_KEY_PATH`)
  - `sandbox: bool` (default `True`, from `TIGER_SANDBOX`)
  - `max_order_value: float` (default `0` = no limit, from `TIGER_MAX_ORDER_VALUE`)
  - `daily_loss_limit: float` (default `0` = no limit, from `TIGER_DAILY_LOSS_LIMIT`)
  - `max_position_pct: float` (default `0` = no limit, from `TIGER_MAX_POSITION_PCT`)
  - `state_dir: Path` (default `~/.tiger-mcp/state/`)
- Validates that required fields are non-empty
- Validates `private_key_path` exists on disk
- Validates numeric fields are non-negative
- Raises clear error messages on invalid configuration
- Factory function or classmethod to load from environment

### Non-Functional
- Unit tests covering: valid config, missing required vars, invalid values, defaults
- All tests pass

## Dependencies
- TASK-001 (project scaffolding)

## Technical Notes
- Use `dataclasses` or `pydantic` (prefer dataclasses to keep deps minimal)
- `sandbox=True` by default is a critical safety default - never change this
- `0` means "no limit" for safety values, not "zero allowed"

## Complexity: Small
