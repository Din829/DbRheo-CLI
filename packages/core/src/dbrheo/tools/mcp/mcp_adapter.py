"""
MCP tool adapter for DbRheo.

Adapts MCP tools to the DbRheo tool interface, ensuring compatibility
with the existing tool system.
"""

from typing import Dict, Any, Optional, Union
from ...tools.base import DatabaseTool, ToolResult, DatabaseConfirmationDetails
from ...types.core_types import AbortSignal
from ...telemetry.logger import get_logger
from .mcp_client import MCPClientManager, MCPToolInfo

logger = get_logger(__name__)


class MCPToolAdapter(DatabaseTool):
    """
    Adapter that wraps an MCP tool as a DbRheo DatabaseTool.
    
    This adapter ensures MCP tools can be used seamlessly within
    the DbRheo tool system, maintaining compatibility with all
    existing features like confirmation, risk assessment, etc.
    """
    
    # Static allowlist for trusted servers/tools
    _trusted_servers = set()
    _trusted_tools = set()
    
    def __init__(
        self,
        tool_info: MCPToolInfo,
        client_manager: MCPClientManager,
        trust: bool = False
    ):
        """
        Initialize the MCP tool adapter.
        
        Args:
            tool_info: Information about the MCP tool
            client_manager: MCP client manager for executing tools
            trust: Whether this tool should skip confirmation
        """
        self.tool_info = tool_info
        self.client_manager = client_manager
        self.trust = trust
        
        # Initialize base class
        super().__init__(
            name=tool_info.name,
            display_name=tool_info.display_name,
            description=self._enhance_description(tool_info.description),
            parameter_schema=tool_info.parameters,
            # MCP tools typically return structured data
            is_output_markdown=False,
            # MCP tools don't support streaming updates
            can_update_output=False
        )
    
    def _enhance_description(self, original_desc: str) -> str:
        """
        Enhance the tool description with MCP-specific information.
        
        Args:
            original_desc: Original tool description
            
        Returns:
            Enhanced description
        """
        server_name = self.tool_info.server_name
        enhanced = original_desc or "No description provided"
        
        # Add MCP context
        enhanced += f"\n\n[MCP Tool from '{server_name}' server]"
        enhanced += f"\nOriginal name: {self.tool_info.original_name}"
        
        return enhanced
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """
        Get execution description for the tool.
        
        Args:
            params: Tool parameters
            
        Returns:
            Description of what the tool will do
        """
        # Format parameter string
        param_str = ""
        if params:
            param_items = []
            for key, value in params.items():
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                param_items.append(f"{key}={value_str}")
            param_str = " with " + ", ".join(param_items)
        
        return f"Execute MCP tool '{self.tool_info.original_name}'{param_str}"
    
    async def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """
        Validate tool parameters.
        
        Args:
            params: Tool parameters to validate
            
        Returns:
            Error message if validation fails, None otherwise
        """
        # Basic validation - check required parameters
        schema = self.parameter_schema
        if isinstance(schema, dict):
            required = schema.get('required', [])
            properties = schema.get('properties', {})
            
            # Check required parameters
            for param in required:
                if param not in params:
                    return f"Missing required parameter: {param}"
            
            # Validate parameter types if schema defines them
            for param_name, param_value in params.items():
                if param_name in properties:
                    prop_schema = properties[param_name]
                    expected_type = prop_schema.get('type')
                    
                    if expected_type:
                        if not self._check_type(param_value, expected_type):
                            return (
                                f"Parameter '{param_name}' has invalid type. "
                                f"Expected: {expected_type}"
                            )
        
        return None
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if a value matches the expected type."""
        type_map = {
            'string': str,
            'number': (int, float),
            'integer': int,
            'boolean': bool,
            'array': list,
            'object': dict
        }
        
        expected = type_map.get(expected_type)
        if expected:
            return isinstance(value, expected)
        
        return True  # Unknown type, assume valid
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> Union[bool, DatabaseConfirmationDetails]:
        """
        Determine if execution should be confirmed.
        
        Args:
            params: Tool parameters
            signal: Abort signal
            
        Returns:
            False if no confirmation needed, confirmation details otherwise
        """
        # Check if tool is trusted
        if self.trust:
            return False
        
        # Check static allowlists
        server_key = self.tool_info.server_name
        tool_key = f"{server_key}.{self.tool_info.original_name}"
        
        if server_key in self._trusted_servers or tool_key in self._trusted_tools:
            return False
        
        # Create confirmation details for untrusted tools
        # Use a simple confirmation approach
        confirmation = DatabaseConfirmationDetails(
            type="mcp_execute",
            title=(
                f"Confirm MCP Tool: {self.tool_info.display_name}\n"
                f"Server: {self.tool_info.server_name}\n"
                f"Tool: {self.tool_info.original_name}\n"
                f"Parameters: {params}"
            )
        )
        
        # Set callback to handle trust decisions
        confirmation.on_confirm = lambda outcome: self._handle_trust_decision(
            outcome,
            server_key,
            tool_key
        )
        
        return confirmation
    
    def _handle_trust_decision(
        self,
        outcome: str,
        server_key: str,
        tool_key: str
    ):
        """Handle user's trust decision."""
        if outcome == "always_server":
            self._trusted_servers.add(server_key)
            logger.info(f"Trusted MCP server: {server_key}")
        elif outcome == "always_tool":
            self._trusted_tools.add(tool_key)
            logger.info(f"Trusted MCP tool: {tool_key}")
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[callable] = None
    ) -> ToolResult:
        """
        Execute the MCP tool.
        
        Args:
            params: Tool parameters
            signal: Abort signal
            update_output: Callback for output updates (not used for MCP)
            
        Returns:
            Tool execution result
        """
        try:
            # Check if aborted
            if signal and signal.aborted:
                return ToolResult(
                    error="Execution aborted",
                    llm_content="Execution was aborted by user"
                )
            
            # Call the MCP tool
            result = await self.client_manager.call_tool(
                server_name=self.tool_info.server_name,
                tool_name=self.tool_info.original_name,
                parameters=params
            )
            
            # Check if call failed completely
            if result is None:
                error_msg = f"Failed to call MCP tool '{self.tool_info.original_name}'"
                logger.error(error_msg)
                return ToolResult(
                    error=error_msg,
                    llm_content=error_msg
                )
            
            # Handle CallToolResult object (from MCP SDK)
            # The result is a CallToolResult with 'content' and potentially 'isError' attributes
            content_parts = []
            is_error = False
            
            if hasattr(result, 'content'):
                # Process content array
                for item in result.content:
                    if hasattr(item, 'type') and hasattr(item, 'text'):
                        if item.type == 'text':
                            content_parts.append(item.text)
                    elif hasattr(item, '__dict__'):
                        # Fallback for other content types
                        content_parts.append(str(item))
            
            if hasattr(result, 'isError'):
                is_error = result.isError
            
            content_str = '\n'.join(content_parts) if content_parts else "Tool executed successfully"
            
            # Return appropriate result
            if is_error:
                return ToolResult(
                    error=content_str,
                    llm_content=f"MCP tool error: {content_str}"
                )
            else:
                return ToolResult(
                    summary=f"MCP tool '{self.tool_info.original_name}' executed",
                    llm_content=content_str,
                    return_display=content_str
                )
            
        except Exception as e:
            logger.error(
                f"Error executing MCP tool '{self.tool_info.name}': {e}",
                exc_info=True
            )
            return ToolResult(
                error=str(e),
                llm_content=f"Error executing MCP tool: {e}"
            )
    
    def get_capability_hints(self) -> set:
        """
        Get capability hints for this tool.
        
        Returns:
            Set of capability hints
        """
        # MCP tools are external by nature
        capabilities = {'EXTERNAL', 'MCP'}
        
        # Try to infer capabilities from tool name or description
        name_lower = self.tool_info.original_name.lower()
        desc_lower = (self.tool_info.description or '').lower()
        
        # File system related
        if any(word in name_lower or word in desc_lower 
               for word in ['file', 'read', 'write', 'directory', 'path']):
            capabilities.add('FILE_OPERATION')
        
        # Database related
        if any(word in name_lower or word in desc_lower
               for word in ['sql', 'query', 'database', 'table', 'schema']):
            capabilities.add('QUERY')
        
        # Web related
        if any(word in name_lower or word in desc_lower
               for word in ['http', 'api', 'web', 'url', 'fetch', 'request']):
            capabilities.add('WEB_ACCESS')
        
        # Code execution
        if any(word in name_lower or word in desc_lower
               for word in ['execute', 'run', 'eval', 'compile']):
            capabilities.add('CODE_EXECUTION')
        
        return capabilities
    
    @classmethod
    def reset_trust(cls):
        """Reset all trust decisions."""
        cls._trusted_servers.clear()
        cls._trusted_tools.clear()
        logger.info("Reset all MCP trust decisions")