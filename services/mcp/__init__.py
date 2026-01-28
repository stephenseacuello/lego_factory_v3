"""
LEGO Factory v3 - MCP Services
==============================
Model Context Protocol server with 50+ tools.
"""

from services.mcp.server import MCPServer, get_mcp_server

__all__ = [
    'MCPServer',
    'get_mcp_server',
]
