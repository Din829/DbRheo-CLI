"""
MCP registry for integrating MCP tools with DbRheo tool system.

This registry manages the discovery, registration, and lifecycle of MCP tools.
"""

import asyncio
from typing import Dict, List, Optional, Set
from ...config.base import DatabaseConfig
from ...tools.registry import DatabaseToolRegistry, ToolCapability
from ...telemetry.logger import get_logger
from .mcp_config import MCPConfig, MCPServerConfig
from .mcp_client import MCPClientManager, MCPServerStatus
from .mcp_adapter import MCPToolAdapter

logger = get_logger(__name__)


class MCPRegistry:
    """
    Registry for MCP tools in DbRheo.
    
    This class manages the integration of MCP tools with the existing
    DbRheo tool registry, ensuring minimal invasiveness while providing
    full flexibility.
    """
    
    # Default priority for MCP tools (lower than core tools)
    DEFAULT_MCP_PRIORITY = 60
    
    def __init__(self, db_config: DatabaseConfig):
        """
        Initialize the MCP registry.
        
        Args:
            db_config: Database configuration
        """
        self.db_config = db_config
        self.mcp_config = MCPConfig(db_config)
        self.client_manager = MCPClientManager()
        self.registered_tools: Dict[str, MCPToolAdapter] = {}
        self._initialized = False
    
    async def initialize(self, tool_registry: DatabaseToolRegistry):
        """
        Initialize the MCP registry and discover tools.
        
        Args:
            tool_registry: The main tool registry to register MCP tools with
        """
        if self._initialized:
            logger.debug("MCP registry already initialized")
            return
        
        try:
            # Get all configured servers
            servers = self.mcp_config.get_all_servers()
            
            if not servers:
                logger.info("No MCP servers configured")
                self._initialized = True
                return
            
            logger.info(f"Initializing {len(servers)} MCP servers...")
            
            # Connect and discover tools from all servers
            await self.client_manager.discover_all_servers(servers)
            
            # Register discovered tools
            await self._register_discovered_tools(tool_registry)
            
            self._initialized = True
            logger.info("MCP registry initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP registry: {e}", exc_info=True)
            # Don't fail the entire system if MCP fails
            self._initialized = True
    
    async def _register_discovered_tools(self, tool_registry: DatabaseToolRegistry):
        """
        Register all discovered MCP tools with the main tool registry.
        
        Args:
            tool_registry: The main tool registry
        """
        total_registered = 0
        
        for server_name, tools in self.client_manager.get_all_tools().items():
            server_config = self.mcp_config.get_server(server_name)
            
            for tool_info in tools:
                try:
                    # Apply include/exclude filters
                    if not self._should_include_tool(
                        tool_info.original_name,
                        server_config
                    ):
                        logger.debug(
                            f"Skipping filtered tool '{tool_info.original_name}' "
                            f"from '{server_name}'"
                        )
                        continue
                    
                    # Create adapter
                    adapter = MCPToolAdapter(
                        tool_info=tool_info,
                        client_manager=self.client_manager,
                        trust=server_config.trust if server_config else False
                    )
                    
                    # Determine capabilities
                    capabilities = adapter.get_capability_hints()
                    
                    # Add standard MCP capabilities
                    capabilities.add(ToolCapability.EXTERNAL)
                    
                    # Register with tool registry
                    tool_registry.register_tool(
                        tool=adapter,
                        capabilities=capabilities,
                        tags={"mcp", "external", server_name},
                        priority=self.DEFAULT_MCP_PRIORITY,
                        metadata={
                            "mcp_server": server_name,
                            "mcp_tool": tool_info.original_name
                        }
                    )
                    
                    # Track registered tool
                    self.registered_tools[tool_info.name] = adapter
                    total_registered += 1
                    
                    logger.debug(
                        f"Registered MCP tool '{tool_info.name}' from '{server_name}'"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Failed to register tool '{tool_info.name}' "
                        f"from '{server_name}': {e}"
                    )
        
        logger.info(f"Registered {total_registered} MCP tools")
    
    def _should_include_tool(
        self,
        tool_name: str,
        server_config: Optional[MCPServerConfig]
    ) -> bool:
        """
        Check if a tool should be included based on filters.
        
        Args:
            tool_name: Original tool name
            server_config: Server configuration
            
        Returns:
            True if tool should be included
        """
        if not server_config:
            return True
        
        # Check exclude list first
        if server_config.exclude_tools:
            if tool_name in server_config.exclude_tools:
                return False
        
        # Check include list
        if server_config.include_tools:
            # If include list exists, tool must be in it
            return tool_name in server_config.include_tools
        
        # No filters, include by default
        return True
    
    async def refresh(self, tool_registry: DatabaseToolRegistry):
        """
        Refresh MCP tools by re-discovering from all servers.
        
        Args:
            tool_registry: The main tool registry
        """
        logger.info("Refreshing MCP tools...")
        
        # Unregister existing MCP tools
        self._unregister_all_tools(tool_registry)
        
        # Re-initialize
        self._initialized = False
        await self.initialize(tool_registry)
    
    def _unregister_all_tools(self, tool_registry: DatabaseToolRegistry):
        """
        Unregister all MCP tools from the registry.
        
        Args:
            tool_registry: The main tool registry
        """
        for tool_name in list(self.registered_tools.keys()):
            try:
                # Remove from main registry
                # Note: This assumes the registry has an unregister method
                # If not, we'll need to track and filter tools differently
                if hasattr(tool_registry, 'unregister_tool'):
                    tool_registry.unregister_tool(tool_name)
                
                # Remove from our tracking
                del self.registered_tools[tool_name]
                
            except Exception as e:
                logger.error(f"Failed to unregister tool '{tool_name}': {e}")
        
        logger.debug(f"Unregistered all MCP tools")
    
    async def add_server(
        self,
        name: str,
        config: MCPServerConfig,
        tool_registry: DatabaseToolRegistry
    ):
        """
        Add a new MCP server at runtime.
        
        Args:
            name: Server name
            config: Server configuration
            tool_registry: The main tool registry
        """
        logger.info(f"Adding MCP server '{name}'...")
        
        # Add to configuration
        self.mcp_config.add_server(name, config)
        
        # Connect and discover
        connected = await self.client_manager.connect_server(name, config)
        
        if connected:
            # Get tools (already discovered during connect)
            tools = self.client_manager.get_server_tools(name)
            
            if tools:
                # Register tools
                await self._register_discovered_tools(tool_registry)
                logger.info(f"Added {len(tools)} tools from '{name}'")
            else:
                logger.warning(f"No tools found on server '{name}'")
        else:
            logger.error(f"Failed to connect to server '{name}'")
    
    async def remove_server(
        self,
        name: str,
        tool_registry: DatabaseToolRegistry
    ):
        """
        Remove an MCP server and its tools.
        
        Args:
            name: Server name
            tool_registry: The main tool registry
        """
        logger.info(f"Removing MCP server '{name}'...")
        
        # Unregister tools from this server
        tools_to_remove = [
            tool_name for tool_name, adapter in self.registered_tools.items()
            if adapter.tool_info.server_name == name
        ]
        
        for tool_name in tools_to_remove:
            try:
                if hasattr(tool_registry, 'unregister_tool'):
                    tool_registry.unregister_tool(tool_name)
                del self.registered_tools[tool_name]
            except Exception as e:
                logger.error(f"Failed to unregister tool '{tool_name}': {e}")
        
        # Disconnect from server
        await self.client_manager.disconnect_server(name)
        
        # Remove from configuration
        self.mcp_config.remove_server(name)
        
        logger.info(f"Removed server '{name}' and {len(tools_to_remove)} tools")
    
    def get_server_status(self, name: str) -> MCPServerStatus:
        """Get the status of an MCP server."""
        return self.client_manager.get_status(name)
    
    def get_all_server_statuses(self) -> Dict[str, MCPServerStatus]:
        """Get all server statuses."""
        return self.client_manager.get_all_statuses()
    
    def get_server_tools(self, name: str) -> List[MCPToolAdapter]:
        """Get all tools from a specific server."""
        return [
            adapter for adapter in self.registered_tools.values()
            if adapter.tool_info.server_name == name
        ]
    
    def get_tool_by_name(self, name: str) -> Optional[MCPToolAdapter]:
        """Get a specific MCP tool by name."""
        return self.registered_tools.get(name)
    
    async def cleanup(self):
        """Clean up all MCP resources."""
        logger.info("Cleaning up MCP registry...")
        
        # Disconnect all clients
        await self.client_manager.disconnect_all()
        
        # Clear registered tools
        self.registered_tools.clear()
        
        self._initialized = False
        logger.info("MCP registry cleaned up")