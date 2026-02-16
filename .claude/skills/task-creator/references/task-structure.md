# Task Document Structure

This guide explains each section of a TASK document and how to write effective content for each.

## Complete Template

```markdown
# TASK-XXX: [Title]

## Task ID
TASK-XXX

## Status
PENDING

## Title
[Short, action-oriented title]

## Description
[1-3 paragraphs explaining what this task accomplishes and why it's needed]

## Acceptance Criteria
### Functional Requirements
- [ ] [Specific deliverable or feature]
- [ ] [Another deliverable]

### Non-Functional Requirements
- [ ] **Testing**: [Test requirements]
- [ ] **Performance**: [Performance requirements]
- [ ] **Observability**: [Logging/monitoring requirements]
- [ ] **Security**: [Security requirements if applicable]
- [ ] **Documentation**: [Documentation requirements]

## Dependencies
- TASK-XXX: [Dependency description]

## Technical Notes
[Detailed implementation guidance, code examples, design decisions]

### [Section 1]
[Details, code snippets]

### [Section 2]
[More details]

### Implementation Hints
1. [Helpful tip]
2. [Another tip]

## Estimated Complexity
**[Small/Medium/Large]** ([X-Y hours])

## References
- [Design doc references]
- [External documentation links]
```

## Section Guidelines

### Task ID & Status
- **Task ID**: TASK-XXX format with zero-padded 3-digit number
- **Status**: One of: PENDING, IN_PROGRESS, COMPLETED, BLOCKED

### Title
- Action-oriented (verb + noun)
- Concise (under 60 characters)
- Examples:
  - "Implement GET /api/v1/nearby Endpoint"
  - "Create asyncpg Connection Pool"
  - "Add Prometheus Metrics"

### Description
- 1-3 paragraphs explaining:
  - What this task accomplishes
  - Why it's needed (context)
  - How it fits into the larger system
- Avoid implementation details (save for Technical Notes)

### Acceptance Criteria
Two main subsections:

**Functional Requirements** - Feature-specific deliverables:
- Specific files/modules implemented
- Endpoints created
- Database schemas defined
- API contracts met
- Features working as specified

**Non-Functional Requirements** - Quality attributes:
- **Testing**: Unit tests, integration tests, test coverage
- **Performance**: Latency targets, throughput requirements
- **Observability**: Logging, metrics, error handling
- **Security**: Authentication, authorization, input validation
- **Documentation**: OpenAPI docs, code comments, usage examples

Write as checkboxes for tracking progress.

### Dependencies
- List other TASK-XXX tasks that must complete first
- Include brief description of why the dependency exists
- Format: `TASK-XXX: [Short description]`

### Technical Notes
The most detailed section containing:
- Complete code examples (copy-pasteable)
- File structure and organization
- Design decisions and rationale
- Integration points with other modules
- Example requests/responses for APIs
- Database schemas and queries
- Test cases
- Implementation hints and gotchas

Use subsections to organize content:
- File-specific sections (e.g., "### api/v1/nearby.py")
- Integration sections (e.g., "### FastAPI Integration")
- Testing sections (e.g., "### Test Cases")
- Example sections (e.g., "### Example Request/Response")
- Tips section (e.g., "### Implementation Hints")

### Estimated Complexity
Three levels:
- **Small**: 1-4 hours - Simple, straightforward tasks
- **Medium**: 4-8 hours - Moderate complexity, some unknowns
- **Large**: 8-16 hours - Complex, multiple components, high risk

### References
- Links to design documents
- External documentation (libraries, APIs)
- Related RFCs or specs
- Relevant discussions or issues

## Tips for Writing Good Tasks

1. **Be specific in acceptance criteria** - "Endpoint returns 200 status" is better than "Endpoint works"

2. **Include code examples** - Show exactly what the implementation should look like

3. **Think about the next developer** - Write technical notes that would help someone unfamiliar with the codebase

4. **Balance detail with brevity** - Provide enough detail to implement without reading other docs, but don't duplicate entire design documents

5. **Make it testable** - Acceptance criteria should be objectively verifiable

6. **Consider dependencies early** - Understanding dependencies helps with scheduling

7. **Update as you go** - If you discover something during implementation, update the task document
