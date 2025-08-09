"""
MCP (Model Context Protocol) integration for DbRheo.

This module provides a flexible adapter system to integrate MCP servers
and their tools into the DbRheo database agent system.

Key components:
- MCPConfig: Configuration management for MCP servers
- MCPClientManager: Manages MCP client connections
- MCPToolAdapter: Adapts MCP tools to DbRheo tool interface
- MCPConverter: Handles format conversion between models
"""

from .mcp_config import MCPConfig, MCPServerConfig
from .mcp_client import MCPClientManager, MCPServerStatus, MCP_AVAILABLE
from .mcp_adapter import MCPToolAdapter
from .mcp_converter import MCPConverter
from .mcp_registry import MCPRegistry

__all__ = [
    'MCPConfig',
    'MCPServerConfig',
    'MCPClientManager',
    'MCPServerStatus',
    'MCP_AVAILABLE',
    'MCPToolAdapter',
    'MCPConverter',
    'MCPRegistry',
]