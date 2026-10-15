"""Entrypoint for running ATP MCP server via `python -m app.mcp`."""

import asyncio
from app.mcp.server import atp_mcp_server

if __name__ == "__main__":
    asyncio.run(atp_mcp_server.run_stdio())
