# ---- builder ----
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ src/
RUN uv sync --frozen --no-dev --no-editable

# ---- runtime ----
FROM python:3.12-slim-bookworm

RUN groupadd -g 1000 tiger && useradd -u 1000 -g tiger -m tiger

COPY --from=builder /app/.venv /app/.venv

# Create state directory for DailyState and TradePlanStore JSON files.
# Owned by tiger user so writes succeed when running as non-root.
RUN mkdir -p /data/state && chown tiger:tiger /data/state

ENV PATH="/app/.venv/bin:$PATH" \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    TIGER_STATE_DIR=/data/state

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

USER tiger
CMD ["python", "-m", "tiger_mcp"]
