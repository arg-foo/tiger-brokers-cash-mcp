# Non-Functional Requirements Checklist

Use this checklist when writing acceptance criteria to ensure comprehensive coverage of non-functional requirements (NFRs). Not all categories apply to every task - select what's relevant.

## Testing

### Unit Tests
- [ ] Test happy path scenarios
- [ ] Test edge cases and boundary conditions
- [ ] Test error conditions
- [ ] Mock external dependencies
- [ ] Achieve meaningful code coverage (typically >80%)
- [ ] Fast execution (<1s per test suite)

### Integration Tests
- [ ] Test end-to-end workflows
- [ ] Use real database (test instance)
- [ ] Verify API contracts
- [ ] Test authentication/authorization
- [ ] Test pagination
- [ ] Test data validation

### Property-Based Tests (if applicable)
- [ ] Test with generated inputs
- [ ] Verify invariants hold

### Performance Tests (if applicable)
- [ ] Load testing for throughput
- [ ] Stress testing for breaking points
- [ ] Benchmark critical paths

## Performance

### Latency
- [ ] Define acceptable response time (e.g., p50, p95, p99)
- [ ] Target typically: <50ms API, <10ms query
- [ ] Measure and verify actual performance

### Throughput
- [ ] Define expected requests per second
- [ ] Support concurrent requests
- [ ] Handle burst traffic

### Efficiency
- [ ] Use appropriate indexes
- [ ] Avoid N+1 queries
- [ ] Minimize database round-trips
- [ ] Query plan avoids sequential scans
- [ ] Batch operations where possible

### Scalability
- [ ] Design for horizontal scaling
- [ ] Avoid single points of contention
- [ ] Connection pooling configured

### Caching (if applicable)
- [ ] Cache hit rate target (e.g., >80%)
- [ ] TTL configured appropriately
- [ ] Cache invalidation strategy
- [ ] Cache key design prevents collisions

## Observability

### Logging
- [ ] Log all requests with unique request ID
- [ ] Log errors with full context (stack trace, parameters)
- [ ] Use structured logging (JSON)
- [ ] Appropriate log levels (DEBUG, INFO, WARNING, ERROR)
- [ ] No sensitive data in logs (passwords, keys, PII)
- [ ] Logs include timing information
- [ ] Correlation IDs for distributed tracing

### Metrics
- [ ] Track request count by endpoint/status
- [ ] Track request latency (histogram with percentiles)
- [ ] Track error rates
- [ ] Track business metrics (e.g., search results count)
- [ ] Track resource utilization (DB pool, cache, memory)
- [ ] Metrics have appropriate labels (not too high cardinality)

### Error Handling
- [ ] All exceptions caught at appropriate level
- [ ] User-facing error messages are clear and actionable
- [ ] Internal error details hidden from users
- [ ] Errors logged with full context
- [ ] Appropriate HTTP status codes
- [ ] Standardized error response format
- [ ] Retry logic for transient failures (if applicable)
- [ ] Circuit breaker for failing dependencies (if applicable)

### Monitoring/Alerting (for production systems)
- [ ] Health check endpoint
- [ ] Ready/liveness probes
- [ ] Alert rules defined
- [ ] Runbook for on-call
- [ ] SLO/SLA defined

## Security

### Authentication
- [ ] API key/token required
- [ ] Invalid credentials return 401
- [ ] Credentials not logged

### Authorization
- [ ] Proper access control checks
- [ ] Return 403 for forbidden resources
- [ ] No privilege escalation possible

### Input Validation
- [ ] All inputs validated before use
- [ ] Type checking via Pydantic/schemas
- [ ] Range/format validation
- [ ] Reject malformed requests with 400
- [ ] SQL injection prevented (parameterized queries)
- [ ] XSS prevention (if rendering HTML)
- [ ] Command injection prevented (if executing commands)

### Data Protection
- [ ] Sensitive data encrypted at rest
- [ ] Sensitive data encrypted in transit (HTTPS)
- [ ] No secrets in source code
- [ ] No PII in logs
- [ ] Secure password hashing (if applicable)

### Rate Limiting (if applicable)
- [ ] Prevent abuse via rate limiting
- [ ] Return 429 when rate limit exceeded
- [ ] Rate limit by API key/user/IP

### Dependency Security
- [ ] Dependencies pinned to specific versions
- [ ] Known vulnerabilities checked (dependabot, safety)
- [ ] Minimal permissions for service accounts

## Documentation

### Code Documentation
- [ ] Docstrings for all public functions/classes
- [ ] Type hints for parameters and returns
- [ ] Inline comments for complex logic
- [ ] Architecture decisions recorded (ADRs if applicable)

### API Documentation
- [ ] OpenAPI/Swagger docs auto-generated
- [ ] All endpoints documented
- [ ] Request/response schemas defined
- [ ] Query parameters described
- [ ] Error responses documented
- [ ] Example requests provided

### Usage Documentation
- [ ] README updated if applicable
- [ ] Setup/installation instructions
- [ ] Environment variables documented
- [ ] Configuration options explained

### Operational Documentation
- [ ] Deployment instructions
- [ ] Rollback procedure
- [ ] Monitoring dashboard
- [ ] Troubleshooting guide

## Reliability

### Error Recovery
- [ ] Graceful degradation when dependencies fail
- [ ] Retry logic with exponential backoff
- [ ] Idempotent operations
- [ ] Transaction rollback on failure

### Data Integrity
- [ ] Database constraints enforced
- [ ] Foreign key relationships defined
- [ ] Validation at database level
- [ ] Atomic operations where required

### Availability
- [ ] No single points of failure
- [ ] Failover mechanisms
- [ ] Health checks
- [ ] Graceful shutdown

## Maintainability

### Code Quality
- [ ] Follows project style guide
- [ ] Linter passes (pylint, flake8, mypy)
- [ ] Formatter applied (black, prettier)
- [ ] No code duplication
- [ ] Functions are small and focused
- [ ] Clear variable/function names

### Testability
- [ ] Dependencies injectable
- [ ] Side effects isolated
- [ ] Pure functions where possible
- [ ] Easy to mock/stub

### Modularity
- [ ] Clear separation of concerns
- [ ] Well-defined interfaces
- [ ] Loose coupling
- [ ] High cohesion

## Compliance (if applicable)

### Legal/Regulatory
- [ ] GDPR compliance (data privacy)
- [ ] CCPA compliance (California privacy)
- [ ] HIPAA compliance (healthcare)
- [ ] SOC 2 requirements met
- [ ] PCI DSS compliance (payment data)

### Accessibility (for UIs)
- [ ] WCAG 2.1 AA compliance
- [ ] Screen reader compatible
- [ ] Keyboard navigation

## How to Use This Checklist

1. **Review each category** - Consider if it applies to your task
2. **Select relevant items** - Not all apply to every task
3. **Adapt to context** - Modify criteria to fit specific requirements
4. **Be realistic** - Balance thoroughness with task complexity

### Task Type Guidelines

**Small tasks (1-4 hours)**:
- Focus on: Testing, basic observability, code quality
- Skip: Extensive metrics, complex monitoring, load testing

**Medium tasks (4-8 hours)**:
- Include: Testing, performance targets, observability, security basics
- Consider: Metrics, alerting rules

**Large tasks (8-16 hours)**:
- Comprehensive coverage across all applicable categories
- Include: Full testing suite, detailed metrics, security review, documentation

**Infrastructure tasks**:
- Emphasize: Performance, security, observability, reliability

**API tasks**:
- Emphasize: Testing, documentation, performance, security

**ETL/Data tasks**:
- Emphasize: Data integrity, performance, error recovery, observability

**Frontend tasks**:
- Emphasize: Testing, accessibility, performance, user experience
