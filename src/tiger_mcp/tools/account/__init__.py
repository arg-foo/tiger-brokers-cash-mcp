"""Account tools package for the Tiger Brokers MCP server.

Importing this module registers the account tool handlers with the
FastMCP server instance.  Call ``init(client)`` during server startup
to provide the ``TigerClient`` dependency.
"""

from tiger_mcp.tools.account.tools import init

__all__ = ["init"]
