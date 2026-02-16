---
name: task-tracker
description: "Track implementation task status in doc/tasks/. Use when: (1) starting work on a task ('work on TASK-007', 'start the asyncpg task'), (2) completing a task ('mark TASK-001 complete', 'finish TASK-003'), (3) checking task status. Updates both the task file and TASK-INDEX.md."
---

# Task Tracker

Track status of implementation tasks in `doc/tasks/`.

## Status Values

- `NOT_STARTED` - Initial state (default)
- `IN-PROGRESS` - Currently being worked on
- `COMPLETED` - Task finished

## When Starting a Task

1. **Update task file** - Add or update `## Status` section after `## Task ID`:

```markdown
## Task ID
TASK-007

## Status
IN-PROGRESS
```

2. **Update TASK-INDEX.md** - Add/update Status column in the task's row:

```markdown
| ID | Task | Complexity | Est. Hours | Dependencies | Status |
|----|------|------------|------------|--------------|--------|
| TASK-007 | [asyncpg Connection Pool](...) | Medium | 4-6h | TASK-001, TASK-002 | IN-PROGRESS |
```

## When Completing a Task

1. **Update task file** - Change status to `COMPLETED`
2. **Update TASK-INDEX.md** - Change status column to `COMPLETED`
3. **Clear context** - You MUST ALWAYS clear the context window automatically by running `/clear` command in claude code.

## First-Time Setup

If TASK-INDEX.md lacks a Status column, add `| Status |` to header and `|--------|` to separator, then add status to each row (default: empty or `NOT_STARTED`).
