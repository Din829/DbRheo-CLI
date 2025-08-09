"""
MCP format converter for multi-model support.

Handles conversion between Gemini, Claude, and OpenAI formats for MCP tools.
"""

from typing import Dict, Any, List, Optional
from ...telemetry.logger import get_logger

logger = get_logger(__name__)


class MCPConverter:
    """
    Converts MCP tool formats between different LLM services.
    
    Since Gemini has native support, we primarily convert from
    Gemini format to Claude and OpenAI formats.
    """
    
    @staticmethod
    def convert_tool_declaration(
        tool_schema: Dict[str, Any],
        target_format: str = "gemini"
    ) -> Dict[str, Any]:
        """
        Convert tool declaration to target format.
        
        Args:
            tool_schema: Tool schema in Gemini format
            target_format: Target format (gemini, claude, openai)
            
        Returns:
            Converted tool declaration
        """
        if target_format == "gemini":
            # Already in Gemini format
            return tool_schema
        elif target_format == "claude":
            return MCPConverter._to_claude_format(tool_schema)
        elif target_format == "openai":
            return MCPConverter._to_openai_format(tool_schema)
        else:
            logger.warning(f"Unknown target format: {target_format}")
            return tool_schema
    
    @staticmethod
    def _to_claude_format(tool_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Gemini tool schema to Claude format.
        
        Claude expects:
        {
            "name": "tool_name",
            "description": "description",
            "input_schema": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
        """
        return {
            "name": tool_schema.get("name", ""),
            "description": tool_schema.get("description", ""),
            "input_schema": tool_schema.get("parameters", {
                "type": "object",
                "properties": {}
            })
        }
    
    @staticmethod
    def _to_openai_format(tool_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Gemini tool schema to OpenAI format.
        
        OpenAI expects:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "description",
                "parameters": {
                    "type": "object",
                    "properties": {...},
                    "required": [...]
                }
            }
        }
        """
        return {
            "type": "function",
            "function": {
                "name": tool_schema.get("name", ""),
                "description": tool_schema.get("description", ""),
                "parameters": tool_schema.get("parameters", {
                    "type": "object",
                    "properties": {}
                })
            }
        }
    
    @staticmethod
    def convert_tool_call(
        call_data: Dict[str, Any],
        source_format: str,
        target_format: str
    ) -> Dict[str, Any]:
        """
        Convert tool call between formats.
        
        Args:
            call_data: Tool call data
            source_format: Source format
            target_format: Target format
            
        Returns:
            Converted tool call
        """
        if source_format == target_format:
            return call_data
        
        # First normalize to Gemini format
        if source_format == "claude":
            normalized = MCPConverter._claude_call_to_gemini(call_data)
        elif source_format == "openai":
            normalized = MCPConverter._openai_call_to_gemini(call_data)
        else:
            normalized = call_data
        
        # Then convert to target format
        if target_format == "claude":
            return MCPConverter._gemini_call_to_claude(normalized)
        elif target_format == "openai":
            return MCPConverter._gemini_call_to_openai(normalized)
        else:
            return normalized
    
    @staticmethod
    def _claude_call_to_gemini(call_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Claude tool_use to Gemini function_call.
        
        Claude format:
        {
            "type": "tool_use",
            "id": "call_id",
            "name": "tool_name",
            "input": {...}
        }
        
        Gemini format:
        {
            "id": "call_id",
            "name": "tool_name",
            "args": {...}
        }
        """
        return {
            "id": call_data.get("id", ""),
            "name": call_data.get("name", ""),
            "args": call_data.get("input", {})
        }
    
    @staticmethod
    def _openai_call_to_gemini(call_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI tool_call to Gemini function_call.
        
        OpenAI format:
        {
            "id": "call_id",
            "type": "function",
            "function": {
                "name": "tool_name",
                "arguments": "json_string"
            }
        }
        
        Gemini format:
        {
            "id": "call_id",
            "name": "tool_name",
            "args": {...}
        }
        """
        import json
        
        function_data = call_data.get("function", {})
        args_str = function_data.get("arguments", "{}")
        
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse OpenAI arguments: {args_str}")
            args = {}
        
        return {
            "id": call_data.get("id", ""),
            "name": function_data.get("name", ""),
            "args": args
        }
    
    @staticmethod
    def _gemini_call_to_claude(call_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Gemini function_call to Claude tool_use."""
        return {
            "type": "tool_use",
            "id": call_data.get("id", ""),
            "name": call_data.get("name", ""),
            "input": call_data.get("args", {})
        }
    
    @staticmethod
    def _gemini_call_to_openai(call_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Gemini function_call to OpenAI tool_call."""
        import json
        
        return {
            "id": call_data.get("id", ""),
            "type": "function",
            "function": {
                "name": call_data.get("name", ""),
                "arguments": json.dumps(call_data.get("args", {}))
            }
        }
    
    @staticmethod
    def convert_tool_result(
        result_data: Dict[str, Any],
        source_format: str,
        target_format: str
    ) -> Dict[str, Any]:
        """
        Convert tool result between formats.
        
        Args:
            result_data: Tool result data
            source_format: Source format
            target_format: Target format
            
        Returns:
            Converted tool result
        """
        if source_format == target_format:
            return result_data
        
        # Normalize to Gemini format first
        if source_format == "claude":
            normalized = MCPConverter._claude_result_to_gemini(result_data)
        elif source_format == "openai":
            normalized = MCPConverter._openai_result_to_gemini(result_data)
        else:
            normalized = result_data
        
        # Convert to target format
        if target_format == "claude":
            return MCPConverter._gemini_result_to_claude(normalized)
        elif target_format == "openai":
            return MCPConverter._gemini_result_to_openai(normalized)
        else:
            return normalized
    
    @staticmethod
    def _claude_result_to_gemini(result_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Claude tool_result to Gemini function_response.
        
        Claude format:
        {
            "type": "tool_result",
            "tool_use_id": "call_id",
            "content": "result"
        }
        
        Gemini format:
        {
            "functionResponse": {
                "id": "call_id",
                "response": {"output": "result"}
            }
        }
        """
        content = result_data.get("content", "")
        
        # Handle different content types
        if isinstance(content, dict):
            response = content
        else:
            response = {"output": content}
        
        return {
            "functionResponse": {
                "id": result_data.get("tool_use_id", ""),
                "response": response
            }
        }
    
    @staticmethod
    def _openai_result_to_gemini(result_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI tool message to Gemini function_response.
        
        OpenAI format:
        {
            "role": "tool",
            "tool_call_id": "call_id",
            "content": "result"
        }
        
        Gemini format:
        {
            "functionResponse": {
                "id": "call_id",
                "response": {"output": "result"}
            }
        }
        """
        content = result_data.get("content", "")
        
        # Handle different content types
        if isinstance(content, dict):
            response = content
        else:
            response = {"output": content}
        
        return {
            "functionResponse": {
                "id": result_data.get("tool_call_id", ""),
                "response": response
            }
        }
    
    @staticmethod
    def _gemini_result_to_claude(result_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Gemini function_response to Claude tool_result."""
        func_response = result_data.get("functionResponse", {})
        response = func_response.get("response", {})
        
        # Extract content from response
        if isinstance(response, dict) and "output" in response:
            content = response["output"]
        else:
            content = response
        
        return {
            "type": "tool_result",
            "tool_use_id": func_response.get("id", ""),
            "content": content
        }
    
    @staticmethod
    def _gemini_result_to_openai(result_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Gemini function_response to OpenAI tool message."""
        func_response = result_data.get("functionResponse", {})
        response = func_response.get("response", {})
        
        # Extract content from response
        if isinstance(response, dict) and "output" in response:
            content = response["output"]
        else:
            content = str(response)
        
        return {
            "role": "tool",
            "tool_call_id": func_response.get("id", ""),
            "content": content
        }
    
    @staticmethod
    def sanitize_parameters(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sanitize parameters for compatibility across all models.
        
        Args:
            params: Parameters to sanitize
            
        Returns:
            Sanitized parameters
        """
        if not params:
            return {"type": "object", "properties": {}}
        
        # Deep copy to avoid modifying original
        import copy
        sanitized = copy.deepcopy(params)
        
        def _sanitize_schema(schema: Any, visited: set = None) -> Any:
            """Recursively sanitize schema object."""
            if visited is None:
                visited = set()
            
            # Handle circular references
            if id(schema) in visited:
                return schema
            visited.add(id(schema))
            
            if not isinstance(schema, dict):
                return schema
            
            # Remove problematic fields
            if 'anyOf' in schema and 'default' in schema:
                # Remove default when anyOf is present (Gemini issue)
                del schema['default']
            
            # Sanitize format field for strings
            if schema.get('type') == 'string' and 'format' in schema:
                allowed_formats = ['enum', 'date-time']
                if schema['format'] not in allowed_formats:
                    del schema['format']
            
            # Recursively sanitize nested schemas
            for key in ['anyOf', 'oneOf', 'allOf']:
                if key in schema and isinstance(schema[key], list):
                    schema[key] = [_sanitize_schema(item, visited) for item in schema[key]]
            
            if 'items' in schema:
                schema['items'] = _sanitize_schema(schema['items'], visited)
            
            if 'properties' in schema and isinstance(schema['properties'], dict):
                for prop_name, prop_schema in schema['properties'].items():
                    schema['properties'][prop_name] = _sanitize_schema(prop_schema, visited)
            
            return schema
        
        return _sanitize_schema(sanitized)