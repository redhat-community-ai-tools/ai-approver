#!/usr/bin/env python3
"""
Test script for MCP connection
"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from smolagents import MCPClient
from config import MCP_SERVERS


def test_mcp_connection():
    """Test MCP connection and list available tools"""
    print("Testing MCP Connection...")

    mcp_config = {
        "url": MCP_SERVERS["kubernetes"]["url"],
        "transport": "streamable-http",
    }

    print(f"MCP Server URL: {mcp_config['url']}")

    try:
        with MCPClient(mcp_config) as tools:
            print("✅ Successfully connected to MCP server!")
            print(f"📋 Available tools: {len(tools)}")

            for i, tool in enumerate(tools):
                print(f"  {i + 1}. {tool.name}: {tool.description}")

    except Exception as e:
        print(f"❌ MCP connection failed: {e}")


if __name__ == "__main__":
    test_mcp_connection()
