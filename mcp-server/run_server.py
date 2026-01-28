#!/usr/bin/env python3
"""
MCP Server runner script for Claude Desktop integration.
"""
import sys
import os

# Add the mcp-server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run
from src.server import run

if __name__ == "__main__":
    run()
