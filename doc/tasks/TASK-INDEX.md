# Tiger MCP Server - Task Index

## Overview

12 tasks across 6 phases to implement a Tiger Brokers MCP server for spot stock trading with cash account safety enforcement.

## Task Summary

| Task | Phase | Title | Complexity | Status | Dependencies |
|------|-------|-------|------------|--------|--------------|
| TASK-001 | 1 | Project Scaffolding | Small | pending | - |
| TASK-002 | 1 | Configuration Module | Small | pending | TASK-001 |
| TASK-003 | 1 | Server Skeleton | Small | pending | TASK-001, TASK-002 |
| TASK-004 | 2 | Tiger API Client | Medium | pending | TASK-001, TASK-002 |
| TASK-005 | 3 | Daily State Tracker | Small | pending | TASK-001, TASK-002 |
| TASK-006 | 3 | Pre-Trade Safety Checks | Medium | pending | TASK-002, TASK-005 |
| TASK-007 | 4 | Account Tools (4 tools) | Medium | pending | TASK-003, TASK-004 |
| TASK-008 | 4 | Market Data Tools (3 tools) | Small | pending | TASK-003, TASK-004 |
| TASK-009 | 5 | Order Query Tools (2 tools) | Small | pending | TASK-003, TASK-004 |
| TASK-010 | 5 | Order Execution Tools (2 tools) | Large | pending | TASK-004, TASK-005, TASK-006 |
| TASK-011 | 5 | Order Management Tools (3 tools) | Medium | pending | TASK-003, TASK-004, TASK-006 |
| TASK-012 | 6 | Integration & Verification | Small | pending | TASK-007..011 |

## Dependency Graph

```
TASK-001 (Scaffolding)
  ├── TASK-002 (Config)
  │     ├── TASK-003 (Server) ──────────┐
  │     │                               │
  │     ├── TASK-004 (API Client) ──────┤
  │     │     ├── TASK-007 (Account)    ├── TASK-012 (Integration)
  │     │     ├── TASK-008 (Market)     │
  │     │     ├── TASK-009 (Order Query)│
  │     │     ├── TASK-010 (Order Exec) │
  │     │     └── TASK-011 (Order Mgmt) │
  │     │                               │
  │     ├── TASK-005 (State) ───────────┘
  │     └── TASK-006 (Safety)
  │           ├── TASK-010
  │           └── TASK-011
```

## Phases

### Phase 1: Scaffolding (TASK-001, 002, 003)
Foundation: project structure, configuration, server skeleton.

### Phase 2: API Client (TASK-004)
Single integration point with Tiger Brokers SDK.

### Phase 3: Safety Layer (TASK-005, 006)
Cash account enforcement: state tracking + 6 pre-trade checks.

### Phase 4: Account & Market Data Tools (TASK-007, 008)
7 read-only tools for account info and market data.

### Phase 5: Order Tools (TASK-009, 010, 011)
7 tools for order querying, execution, and management.

### Phase 6: Integration (TASK-012)
Final assembly, MCP registration, end-to-end verification.

## Tool Count by Task

| Task | Tools |
|------|-------|
| TASK-007 | `get_account_summary`, `get_buying_power`, `get_positions`, `get_transaction_history` |
| TASK-008 | `get_stock_quote`, `get_stock_quotes`, `get_stock_bars` |
| TASK-009 | `get_open_orders`, `get_order_detail` |
| TASK-010 | `preview_stock_order`, `place_stock_order` |
| TASK-011 | `modify_order`, `cancel_order`, `cancel_all_orders` |
| **Total** | **14 tools** |
