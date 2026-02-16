"""Entry point for ``python -m tiger_mcp``.

Also serves as the target for the ``tiger-mcp`` console script defined
in ``pyproject.toml``.
"""

from __future__ import annotations

import asyncio

from tiger_mcp.server import main


def run() -> None:
    """Synchronous wrapper that runs the async ``main()`` entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
