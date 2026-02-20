# TASK-013: Paper Account End-to-End Testing

## Task ID
TASK-013

## Status
PENDING

## Title
Test MCP Server with Tiger Brokers Paper Account

## Description
All 14 MCP tools have been implemented and verified with unit tests using mocked responses. The next critical step is to validate the server against a real Tiger Brokers paper (simulation) trading account to confirm that:

1. Authentication and API connectivity work with real credentials.
2. All read-only tools (account, market data, order queries) return expected data shapes.
3. Order execution tools (preview, place, modify, cancel) function correctly in a live sandbox.
4. Safety checks (cash-account enforcement, day-trade limits, buying power) behave correctly with real account state.

This is a manual testing task that requires a funded Tiger Brokers paper account and valid API credentials (private key, tiger ID, account ID).

## Acceptance Criteria

### Functional Requirements
- [ ] Obtain or verify access to a Tiger Brokers paper trading account
- [ ] Configure `.env` with real paper account credentials (tiger_id, private_key, account)
- [ ] Start MCP server and confirm successful connection to Tiger API
- [ ] Test all 4 account tools: `get_account_summary`, `get_buying_power`, `get_positions`, `get_transaction_history`
- [ ] Test all 3 market data tools: `get_stock_quote`, `get_stock_quotes`, `get_stock_bars`
- [ ] Test order query tools: `get_open_orders`, `get_order_detail`
- [ ] Place a paper trade using `preview_stock_order` then `place_stock_order`
- [ ] Modify a pending order using `modify_order`
- [ ] Cancel an order using `cancel_order`
- [ ] Test `cancel_all_orders` with multiple pending orders
- [ ] Verify safety checks trigger correctly (e.g., reject short sells, enforce buying power limits)
- [ ] Document any discrepancies between mocked test responses and real API responses

### Non-Functional Requirements
- [ ] **Security**: Ensure credentials are never committed to git (`.env` in `.gitignore`)
- [ ] **Documentation**: Record test results and any API response shape differences
- [ ] **Reliability**: Confirm error handling works for real API errors (invalid symbol, market closed, etc.)

## Dependencies
- TASK-012: Integration & Verification (COMPLETED)

## Technical Notes

### Setup Steps
1. Sign up for Tiger Brokers paper trading account at developer portal
2. Generate API credentials (RSA private key, tiger_id)
3. Note your paper account ID
4. Create `.env` file:
   ```
   TIGER_ID=your_tiger_id
   TIGER_PRIVATE_KEY=path/to/private_key.pem
   TIGER_ACCOUNT=your_paper_account_id
   ```
   > **Note:** There is no `TIGER_ENVIRONMENT` flag. Paper vs. live accounts are
   > determined entirely by the `TIGER_ACCOUNT` value. Both account types use
   > the same production API endpoint.
5. Start server: `uv run python -m tiger_mcp`

### Test Sequence
Run tools in this order to build on results:
1. `get_account_summary` — verify account connects
2. `get_buying_power` — note available cash
3. `get_stock_quote` symbol=AAPL — verify market data
4. `get_stock_quotes` symbols=["AAPL","MSFT"] — verify batch quotes
5. `get_stock_bars` symbol=AAPL period=day limit=5 — verify historical data
6. `preview_stock_order` symbol=AAPL action=BUY quantity=1 order_type=LIMIT limit_price=<current_price> — verify preview
7. `place_stock_order` with same params — place real paper order
8. `get_open_orders` — verify order appears
9. `get_order_detail` order_id=<from_step_7> — verify detail
10. `modify_order` order_id=<from_step_7> limit_price=<adjusted> — modify if still open
11. `cancel_order` order_id=<from_step_7> — cancel if still open
12. Place 2+ orders, then `cancel_all_orders` — verify bulk cancel
13. `get_positions` — check post-trade positions
14. `get_transaction_history` — check trade history

### Known Considerations
- Paper account may have limited market hours; some tests may need to run during US market hours
- Tiger API sandbox may have different rate limits than production
- RSA key format must match what Tiger SDK expects (PKCS#1 or PKCS#8)

## Estimated Complexity
**Medium** (4-8 hours)

Manual testing with real API; depends on account setup time and market hours.

## References
- [Tiger Open API Documentation](https://quant.itigerup.com/openapi/en/python/overview/introduction.html)
- Project README for server startup instructions