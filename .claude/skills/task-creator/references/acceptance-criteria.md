# Writing Effective Acceptance Criteria

Acceptance criteria define what "done" means for a task. They should be specific, testable, and cover both functional and non-functional requirements.

## Structure

```markdown
## Acceptance Criteria

### Functional Requirements
- [ ] [Feature-specific deliverable]
- [ ] [Another feature deliverable]

### Non-Functional Requirements
- [ ] **Testing**: [Test requirements]
- [ ] **Performance**: [Performance targets]
- [ ] **Observability**: [Logging/monitoring]
- [ ] **Security**: [Security requirements]
- [ ] **Documentation**: [Docs requirements]
```

## Functional Requirements

Functional requirements describe **what the system does** - specific features, behaviors, and deliverables.

### Categories

**1. Code Deliverables**
- Files/modules implemented
- Classes/functions created
- Schemas defined

Examples:
- `api/v1/nearby.py` implements GET `/nearby` endpoint
- `db/queries/search.py` contains `search_nearby()` function
- `RestaurantListItem` Pydantic model defined

**2. API Contracts**
- Endpoints exposed
- Request/response formats
- Status codes returned
- Query parameters validated

Examples:
- Endpoint accepts `lat`, `lng`, `radius` parameters
- Response matches `SearchResponse` schema
- Returns 400 for invalid coordinates
- Returns 401 for missing API key

**3. Data Operations**
- Database tables created/modified
- Queries implemented
- Indexes created
- Data transformations

Examples:
- Query uses PostGIS ST_DWithin for radius search
- Results sorted by distance
- Returns total count and has_more flag
- Supports pagination with limit/offset

**4. Integration Points**
- Module dependencies wired correctly
- Configuration loaded
- External services integrated
- Events/hooks triggered

Examples:
- Router registered in FastAPI app
- Database connection injected via dependencies
- Redis cache checked before database query
- Metrics recorded after each search

**5. Edge Cases Handled**
- Empty results
- Invalid input
- Boundary conditions
- Error scenarios

Examples:
- Returns empty list when no restaurants found
- Handles coordinates at poles/date line
- Validates radius doesn't exceed maximum
- Gracefully handles database timeout

## Non-Functional Requirements

Non-functional requirements describe **how well the system works** - quality attributes like performance, security, and maintainability.

### Testing

What tests prove the functionality works?

**Unit Tests**:
- Test individual functions in isolation
- Mock external dependencies
- Cover edge cases

**Integration Tests**:
- Test end-to-end flows
- Use real database (test instance)
- Verify API contracts

Examples:
- Unit tests for geometry encoding/decoding
- Integration test for successful nearby search
- Test validation error for invalid latitude
- Test unauthorized error when API key missing
- Test pagination works correctly

### Performance

What are the speed and efficiency requirements?

Consider:
- Response time / latency
- Throughput (requests per second)
- Database query time
- Memory usage
- Caching effectiveness

Examples:
- Endpoint responds in <50ms at p95
- Database query uses spatial index
- Supports 100 concurrent requests
- Query plan avoids sequential scans
- Cache TTL set to 5 minutes

### Observability

How do you know if the system is working?

**Logging**:
- Request/response logging
- Error logging with context
- Audit trails

**Metrics**:
- Business metrics (searches, results)
- Performance metrics (latency, errors)
- Resource metrics (DB connections, cache)

**Error Handling**:
- Exceptions caught and logged
- User-friendly error messages
- Internal errors hidden

Examples:
- All requests logged with request ID
- Errors include stack traces and context
- Metrics track search latency by type
- Database errors return generic 500 message
- Log includes lat/lng for debugging

### Security

How is the system protected?

Consider:
- Authentication
- Authorization
- Input validation
- Data protection
- Rate limiting

Examples:
- API key required via X-API-Key header
- Lat/lng validated within valid ranges
- SQL injection prevented (parameterized queries)
- No sensitive data in logs
- Rate limiting applied per API key

### Documentation

How will others understand and use this?

**Code Documentation**:
- Docstrings for public functions
- Type hints
- Inline comments for complex logic

**API Documentation**:
- OpenAPI/Swagger docs
- Example requests/responses
- Error codes documented

**Usage Documentation**:
- README updates
- Architecture decision records
- Runbooks for operations

Examples:
- OpenAPI docs auto-generated from Pydantic models
- Endpoint includes description and parameter docs
- Example curl request in task notes
- Error response formats documented
- Complex spatial query logic commented

## Writing Guidelines

### Be Specific

❌ Bad: "Endpoint works correctly"
✅ Good: "Endpoint returns 200 status with valid SearchResponse body"

❌ Bad: "Good performance"
✅ Good: "Query completes in <10ms at p95"

❌ Bad: "Has tests"
✅ Good: "Unit tests cover encode/decode geometry with 100% coverage"

### Be Testable

Every criterion should be objectively verifiable:

✅ "Returns 401 when X-API-Key header is missing" - Can test this
✅ "Log entry includes request_id field" - Can verify in logs
✅ "Response includes pagination.has_more field" - Can check response

### Use Action Verbs

- Implements, creates, exposes, returns, handles, validates, logs, documents

### Include Quantities

- "Responds in <50ms" not "responds quickly"
- "100% test coverage" not "good test coverage"
- "Handles up to 5000m radius" not "handles large radius"

## Example: Complete Acceptance Criteria

```markdown
## Acceptance Criteria

### Functional Requirements
- [ ] `api/v1/search.py` implements GET `/search` endpoint
- [ ] Accepts query parameters: `q`, `lat`, `lng`, `radius`, `cuisine`, `price_level`
- [ ] Returns `SearchResponse` with restaurants, pagination, and query metadata
- [ ] Filters by cuisine when provided (supports multiple via comma separation)
- [ ] Filters by price level when provided (1-4 scale)
- [ ] Combines filters with AND logic
- [ ] Returns 400 for invalid parameters with detailed error message
- [ ] Returns 401 for missing/invalid API key
- [ ] Handles edge case: no results found (returns empty list, not error)
- [ ] Handles edge case: query string with special characters

### Non-Functional Requirements
- [ ] **Testing**: Integration tests cover successful search, validation errors, auth errors
- [ ] **Testing**: Unit tests for query builder with various filter combinations
- [ ] **Performance**: Endpoint responds in <100ms at p95 for typical queries
- [ ] **Performance**: Database query uses GIN index for full-text search
- [ ] **Performance**: Results limited to max 100 per request
- [ ] **Observability**: Logs each request with query parameters and result count
- [ ] **Observability**: Logs filter parsing errors with original query string
- [ ] **Observability**: Metrics track search latency and result count distribution
- [ ] **Security**: All query parameters validated with Pydantic before use
- [ ] **Security**: Prevents SQL injection via parameterized queries
- [ ] **Documentation**: OpenAPI docs include all parameters and response examples
- [ ] **Documentation**: Error response codes documented (400, 401, 500)
```

## Common Pitfalls

1. **Too vague**: "Works correctly" - What does "works" mean specifically?

2. **Missing NFRs**: Only listing functional requirements - Don't forget testing, performance, security

3. **Not testable**: "Code is clean" - How do you verify this objectively?

4. **Implementation details**: "Uses asyncpg.fetch()" - Acceptance criteria should focus on outcomes, not how to implement

5. **Duplicate with description**: Repeating what's already in the description - Acceptance criteria should be more specific
