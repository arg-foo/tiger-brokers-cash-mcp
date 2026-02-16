---
name: task-creator
description: "Create structured TASK documentation in doc/tasks/ directory. Use when the user requests to: (1) create a new task, (2) document a requirement as a task, (3) generate task documentation, (4) create a TASK-XXX document. Tasks follow a standard format with Task ID, Description, Acceptance Criteria (functional and non-functional), Dependencies, Technical Notes, and Complexity estimation."
---

# Task Creator

Create comprehensive TASK documentation following the project's standard format.

## Workflow

### 1. Understand Requirements

Gather information needed to create the task:

- **What** needs to be implemented (features, functionality)
- **Why** it's needed (business value, context)
- **Dependencies** on other tasks
- **Technical approach** (if known)
- **Complexity** estimate (Small/Medium/Large)

Ask clarifying questions if requirements are vague or incomplete.

### 2. Generate Task ID

Run the script to get the next available task number:

```bash
python3 .claude/skills/task-creator/scripts/get_next_task_id.py
```

This automatically scans `doc/tasks/` and returns the next sequential ID (e.g., TASK-029).

### 3. Structure the Task

Create a task document with these sections:

**Required sections:**
- Task ID and Status
- Title (action-oriented, <60 chars)
- Description (1-3 paragraphs: what, why, context)
- Acceptance Criteria (functional + non-functional)
- Dependencies (TASK-XXX references)
- Technical Notes (detailed implementation guidance)
- Estimated Complexity
- References

See `references/task-structure.md` for detailed section guidelines.

### 4. Write Acceptance Criteria

This is the most important section. Include both:

**Functional Requirements** - What the system does:
- Files/modules implemented
- API contracts met
- Data operations
- Edge cases handled

**Non-Functional Requirements** - How well it works:
- **Testing**: Unit tests, integration tests, coverage
- **Performance**: Latency targets, efficiency requirements
- **Observability**: Logging, metrics, error handling
- **Security**: Authentication, validation, data protection
- **Documentation**: API docs, code comments, examples

See `references/acceptance-criteria.md` for detailed guidance.
Use `references/nfr-checklist.md` for systematic NFR coverage.

### 5. Add Technical Notes

Provide detailed implementation guidance:
- Complete code examples (copy-pasteable)
- File organization and structure
- Integration points
- Example requests/responses (for APIs)
- Database schemas/queries
- Test cases
- Implementation hints and gotchas

Make this section detailed enough that someone unfamiliar with the codebase can implement it.

### 6. Set Complexity and Dependencies

**Complexity levels:**
- **Small** (1-4 hours): Simple, straightforward
- **Medium** (4-8 hours): Moderate complexity, some unknowns
- **Large** (8-16 hours): Complex, multiple components

**Dependencies:**
List tasks that must complete first. Format: `TASK-XXX: [description]`

### 7. Create the File

Write to `doc/tasks/TASK-XXX-[descriptive-name].md`

Use kebab-case for the descriptive name (e.g., `TASK-029-api-authentication.md`).

### 8. Update TASK-INDEX.md

Add the new task to the TASK-INDEX.md file using the update script:

```bash
python3 .claude/skills/task-creator/scripts/update_task_index.py \
  --task-id TASK-XXX \
  --title "Task Title" \
  --filename "TASK-XXX-descriptive-name.md" \
  --complexity "Medium" \
  --hours "4-6h" \
  --dependencies "TASK-008, TASK-009" \
  --phase 3
```

**Phase selection:**
- **Phase 1**: Core Infrastructure (database, API scaffold, core endpoints)
- **Phase 2**: ETL Pipeline (data processing, Celery, Redis)
- **Phase 3**: Production Readiness (auth, metrics, Docker, testing)

The script will:
- Add the task to the appropriate phase table
- Update summary statistics (total tasks, complexity distribution)
- Update phase total hours

## Quick Reference

### Task Template Structure

```markdown
# TASK-XXX: [Title]

## Task ID
TASK-XXX

## Status
PENDING

## Title
[Action-oriented title]

## Description
[What, why, and context]

## Acceptance Criteria

### Functional Requirements
- [ ] [Specific deliverable]
- [ ] [Another deliverable]

### Non-Functional Requirements
- [ ] **Testing**: [Test requirements]
- [ ] **Performance**: [Performance targets]
- [ ] **Observability**: [Logging/monitoring]
- [ ] **Security**: [Security requirements]
- [ ] **Documentation**: [Docs requirements]

## Dependencies
- TASK-XXX: [Dependency description]

## Technical Notes

### [Section 1]
[Code examples, details]

### Implementation Hints
1. [Helpful tip]

## Estimated Complexity
**[Small/Medium/Large]** ([X-Y hours])

## References
- [Design doc references]
- [External links]
```

### NFR Categories Checklist

For each task, consider:

- **Testing**: Unit, integration, coverage
- **Performance**: Latency, throughput, efficiency
- **Observability**: Logging, metrics, error handling
- **Security**: Auth, validation, data protection
- **Documentation**: API docs, code docs, examples
- **Reliability**: Error recovery, data integrity
- **Maintainability**: Code quality, testability

Not all apply to every task - select what's relevant.

## Reference Files

- **task-structure.md**: Detailed explanation of each section and writing guidelines
- **acceptance-criteria.md**: How to write effective functional and non-functional requirements
- **nfr-checklist.md**: Comprehensive checklist for systematic NFR coverage

Load reference files as needed:
- Read `task-structure.md` when unsure about section content or structure
- Read `acceptance-criteria.md` when writing acceptance criteria
- Read `nfr-checklist.md` for comprehensive NFR coverage (especially for Medium/Large tasks)

## Tips

1. **Be specific** - "Endpoint returns 200 with SearchResponse body" vs "Endpoint works"

2. **Include code examples** - Show exactly what the implementation should look like

3. **Think about the next developer** - Provide enough detail to implement without external docs

4. **Make it testable** - Every criterion should be objectively verifiable

5. **Balance detail with brevity** - Detailed Technical Notes, but don't duplicate entire design docs

6. **Consider task size**:
   - Small tasks: Focus on testing, basic observability, code quality
   - Medium tasks: Add performance targets, security basics, metrics
   - Large tasks: Comprehensive coverage across all categories
