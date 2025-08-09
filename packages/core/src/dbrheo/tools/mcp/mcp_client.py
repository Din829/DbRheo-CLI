"""
MCP client management for DbRheo - Updated for MCP SDK 1.12.4

This version uses the new async context manager pattern from MCP SDK 1.0+
"""

import asyncio
import os
import re
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from contextlib import AsyncExitStack

from ...telemetry.logger import get_logger
from .mcp_config import MCPServerConfig

logger = get_logger(__name__)

# Check if MCP SDK is available
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError as e:
    MCP_AVAILABLE = False
    logger.info(f"MCP SDK not installed or import failed: {e}. MCP features will be disabled.")
    # Define dummy classes for type hints
    class ClientSession: pass
    class StdioServerParameters: pass


class MCPServerStatus(Enum):
    """Status of an MCP server connection."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPToolInfo:
    """Information about a discovered MCP tool."""
    name: str  # Sanitized name for use in the system
    display_name: str  # Original name for display
    description: str
    parameters: Dict[str, Any]
    server_name: str
    original_name: str  # Original tool name from the server


@dataclass
class MCPServerConnection:
    """Holds connection info for an MCP server."""
    name: str
    config: MCPServerConfig
    session: Optional[ClientSession] = None
    exit_stack: Optional[AsyncExitStack] = None
    status: MCPServerStatus = MCPServerStatus.DISCONNECTED
    tools: List[MCPToolInfo] = None
    
    def __post_init__(self):
        if self.tools is None:
            self.tools = []


class MCPClientManager:
    """
    Manages MCP client connections and tool discovery.
    
    This version is designed for MCP SDK 1.0+ which uses async context managers.
    """
    
    def __init__(self):
        """Initialize the MCP client manager."""
        self.servers: Dict[str, MCPServerConnection] = {}
        self.status_listeners: List[Callable[[str, MCPServerStatus], None]] = []
        
        # Check if MCP is available
        if not MCP_AVAILABLE:
            logger.warning(
                "MCP SDK is not installed. Install with: pip install mcp"
            )
    
    def add_status_listener(self, listener: Callable[[str, MCPServerStatus], None]):
        """Add a listener for server status changes."""
        self.status_listeners.append(listener)
    
    def _update_status(self, server_name: str, status: MCPServerStatus):
        """Update server status and notify listeners."""
        if server_name in self.servers:
            self.servers[server_name].status = status
            
        for listener in self.status_listeners:
            try:
                listener(server_name, status)
            except Exception as e:
                logger.error(f"Error in status listener: {e}")
    
    def get_status(self, server_name: str) -> MCPServerStatus:
        """Get the current status of a server."""
        if server_name in self.servers:
            return self.servers[server_name].status
        return MCPServerStatus.DISCONNECTED
    
    def get_all_statuses(self) -> Dict[str, MCPServerStatus]:
        """Get all server statuses."""
        return {name: conn.status for name, conn in self.servers.items()}
    
    async def connect_server(self, server_name: str, config: MCPServerConfig) -> bool:
        """
        Connect to a single MCP server.
        
        Args:
            server_name: Name of the server
            config: Server configuration
            
        Returns:
            True if connection successful, False otherwise
        """
        if not MCP_AVAILABLE:
            logger.warning(f"Cannot connect to {server_name}: MCP SDK not available")
            return False
        
        # Only stdio transport is supported for now
        if not config.command:
            logger.error(f"Server {server_name} must have 'command' configuration")
            return False
        
        # Create or update server connection
        if server_name not in self.servers:
            self.servers[server_name] = MCPServerConnection(server_name, config)
        
        server_conn = self.servers[server_name]
        
        # Update status to connecting
        self._update_status(server_name, MCPServerStatus.CONNECTING)
        
        try:
            # Create server parameters
            params = StdioServerParameters(
                command=config.command,
                args=config.args or [],
                env={**os.environ, **(config.env or {})},
                cwd=config.cwd
            )
            
            # Create exit stack to manage async context
            server_conn.exit_stack = AsyncExitStack()
            
            # Enter stdio_client context
            transport = await server_conn.exit_stack.enter_async_context(
                stdio_client(params)
            )
            read_stream, write_stream = transport
            
            # Create and enter session context
            server_conn.session = await server_conn.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            
            # Initialize the session
            await server_conn.session.initialize()
            
            # Update status
            self._update_status(server_name, MCPServerStatus.CONNECTED)
            logger.info(f"Connected to MCP server '{server_name}'")
            
            # Discover tools
            await self._discover_tools(server_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{server_name}': {e}")
            self._update_status(server_name, MCPServerStatus.ERROR)
            
            # Clean up on failure
            await self.disconnect_server(server_name)
            return False
    
    async def _discover_tools(self, server_name: str):
        """Discover tools from a connected server."""
        server_conn = self.servers.get(server_name)
        if not server_conn or not server_conn.session:
            return
        
        try:
            # List available tools
            response = await server_conn.session.list_tools()
            
            if not response or not hasattr(response, 'tools'):
                logger.warning(f"No tools found on server '{server_name}'")
                return
            
            server_conn.tools = []
            for tool in response.tools:
                # Create tool info
                tool_info = MCPToolInfo(
                    name=self._sanitize_tool_name(tool.name, server_name),
                    display_name=f"{tool.name} ({server_name})",
                    description=tool.description or "",
                    parameters=self._convert_parameters(tool.inputSchema) if hasattr(tool, 'inputSchema') else {},
                    server_name=server_name,
                    original_name=tool.name
                )
                server_conn.tools.append(tool_info)
                logger.debug(f"Discovered tool '{tool.name}' from '{server_name}'")
            
            logger.info(f"Discovered {len(server_conn.tools)} tools from '{server_name}'")
            
        except Exception as e:
            logger.error(f"Failed to discover tools from '{server_name}': {e}")
    
    def _sanitize_tool_name(self, name: str, server_name: str) -> str:
        """Sanitize tool name for use in the system."""
        # Replace invalid characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
        
        # Add server prefix to avoid conflicts
        sanitized = f"{server_name}__{sanitized}"
        
        # Limit length
        if len(sanitized) > 63:
            sanitized = sanitized[:28] + '___' + sanitized[-32:]
        
        return sanitized
    
    def _convert_parameters(self, schema: Any) -> Dict[str, Any]:
        """Convert MCP parameter schema to internal format."""
        if not schema:
            return {"type": "object", "properties": {}}
        
        # Convert schema to dict if needed
        if hasattr(schema, '__dict__'):
            return schema.__dict__
        
        return schema
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Call a tool on an MCP server.
        
        Args:
            server_name: Name of the server
            tool_name: Original tool name
            parameters: Tool parameters
            
        Returns:
            Tool result or None if failed
        """
        server_conn = self.servers.get(server_name)
        if not server_conn or not server_conn.session:
            logger.error(f"Server '{server_name}' is not connected")
            return None
        
        try:
            result = await server_conn.session.call_tool(tool_name, parameters)
            return result
        except Exception as e:
            logger.error(f"Failed to call tool '{tool_name}' on '{server_name}': {e}")
            return None
    
    async def disconnect_server(self, server_name: str):
        """Disconnect from a server."""
        if server_name not in self.servers:
            return
        
        server_conn = self.servers[server_name]
        
        # Close the exit stack (this will close session and transport)
        if server_conn.exit_stack:
            try:
                await server_conn.exit_stack.aclose()
            except Exception as e:
                logger.error(f"Error closing server '{server_name}': {e}")
        
        # Update status
        self._update_status(server_name, MCPServerStatus.DISCONNECTED)
        
        # Clear connection info
        server_conn.session = None
        server_conn.exit_stack = None
        server_conn.tools = []
    
    async def disconnect_all(self):
        """Disconnect from all servers."""
        for server_name in list(self.servers.keys()):
            await self.disconnect_server(server_name)
    
    def get_server_tools(self, server_name: str) -> List[MCPToolInfo]:
        """Get tools from a specific server."""
        server_conn = self.servers.get(server_name)
        if server_conn:
            return server_conn.tools
        return []
    
    def get_all_tools(self) -> Dict[str, List[MCPToolInfo]]:
        """Get all discovered tools from all servers."""
        return {
            name: conn.tools 
            for name, conn in self.servers.items()
        }
    
    async def discover_all_servers(self, servers: Dict[str, MCPServerConfig]):
        """
        Connect and discover tools from multiple servers.
        
        Args:
            servers: Dictionary of server configurations
        """
        tasks = []
        for server_name, config in servers.items():
            tasks.append(self.connect_server(server_name, config))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any errors
        for server_name, result in zip(servers.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Failed to connect to '{server_name}': {result}")