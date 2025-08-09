"""
MCP configuration management for DbRheo.

Handles loading and managing MCP server configurations from multiple sources
with proper layering and environment variable substitution.
"""

import os
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import json
import yaml
from ...config.base import DatabaseConfig
from ...telemetry.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""
    
    # For stdio transport
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None
    
    # For SSE transport
    url: Optional[str] = None
    
    # For streamable HTTP transport
    http_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    
    # For WebSocket transport (future)
    tcp: Optional[str] = None
    
    # Common configuration
    timeout: Optional[int] = None  # milliseconds
    trust: bool = False  # whether to skip confirmation
    
    # Tool filtering
    include_tools: Optional[List[str]] = None
    exclude_tools: Optional[List[str]] = None
    
    # Metadata
    description: Optional[str] = None
    enabled: bool = True
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        # Ensure at least one transport method is specified
        transports = [self.command, self.url, self.http_url, self.tcp]
        if not any(transports):
            raise ValueError(
                "MCP server configuration must specify at least one transport: "
                "command (stdio), url (SSE), http_url (HTTP), or tcp (WebSocket)"
            )
        
        # Apply environment variable substitution
        self._substitute_env_vars()
    
    def _substitute_env_vars(self):
        """Substitute environment variables in configuration values."""
        self.command = self._substitute_string(self.command)
        self.url = self._substitute_string(self.url)
        self.http_url = self._substitute_string(self.http_url)
        self.cwd = self._substitute_string(self.cwd)
        self.description = self._substitute_string(self.description)
        
        if self.args:
            self.args = [self._substitute_string(arg) for arg in self.args]
        
        if self.env:
            self.env = {
                key: self._substitute_string(value)
                for key, value in self.env.items()
            }
        
        if self.headers:
            self.headers = {
                key: self._substitute_string(value)
                for key, value in self.headers.items()
            }
    
    def _substitute_string(self, value: Optional[str]) -> Optional[str]:
        """Substitute environment variables in a string."""
        if value is None:
            return None
        
        # Pattern to match ${VAR} or $VAR
        pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
        
        def replacer(match):
            var_name = match.group(1) or match.group(2)
            return os.getenv(var_name, match.group(0))
        
        return re.sub(pattern, replacer, value)


class MCPConfig:
    """Manages MCP configuration for DbRheo."""
    
    # Default timeout for MCP operations (10 minutes)
    DEFAULT_TIMEOUT_MS = 10 * 60 * 1000
    
    def __init__(self, db_config: DatabaseConfig):
        """
        Initialize MCP configuration.
        
        Args:
            db_config: The main database configuration object
        """
        self.db_config = db_config
        self.servers: Dict[str, MCPServerConfig] = {}
        self._load_configurations()
    
    def _load_configurations(self):
        """Load MCP configurations from all sources."""
        # Load from multiple sources in priority order
        configs = []
        
        # 1. System level configuration
        system_config = self._load_from_file("/etc/dbrheo/mcp.yaml")
        if system_config:
            configs.append(("system", system_config))
        
        # 2. User level configuration
        user_config_path = Path.home() / ".dbrheo" / "mcp.yaml"
        user_config = self._load_from_file(str(user_config_path))
        if user_config:
            configs.append(("user", user_config))
        
        # 3. Workspace level configuration (including .dbrheo.json)
        # First try to find project root
        current_dir = Path.cwd()
        workspace_config = None
        
        # Search for config file in project root first
        for parent in [current_dir] + list(current_dir.parents):
            # Check if this is the project root
            if (parent / "pyproject.toml").exists() and (parent / "packages").exists():
                # Try config files in project root
                for config_name in [".dbrheo.json", ".dbrheo/mcp.yaml", "mcp.yaml"]:
                    config_path = parent / config_name
                    if config_path.exists():
                        workspace_config = self._load_from_file(str(config_path))
                        if workspace_config:
                            configs.append(("workspace", workspace_config))
                            break
                break
            # Special case: if we're in packages/cli, look in project root
            elif parent.name == "cli" and parent.parent.name == "packages":
                project_root = parent.parent.parent
                for config_name in [".dbrheo.json", ".dbrheo/mcp.yaml", "mcp.yaml"]:
                    config_path = project_root / config_name
                    if config_path.exists():
                        workspace_config = self._load_from_file(str(config_path))
                        if workspace_config:
                            configs.append(("workspace", workspace_config))
                            break
                break
        
        # If not found in project root, try current directory
        if not workspace_config:
            workspace_configs = [
                ".dbrheo.json",  # New JSON config file
                ".dbrheo/mcp.yaml",
                ".dbrheo.mcp.yaml",
                "mcp.yaml"
            ]
            for config_file in workspace_configs:
                workspace_config = self._load_from_file(config_file)
                if workspace_config:
                    configs.append(("workspace", workspace_config))
                    break
        
        # 4. Environment variable configuration
        env_config = self._load_from_env()
        if env_config:
            configs.append(("environment", env_config))
        
        # 5. Runtime configuration from DatabaseConfig
        runtime_config = self._load_from_runtime()
        if runtime_config:
            configs.append(("runtime", runtime_config))
        
        # Merge configurations (later sources override earlier ones)
        for source, config in configs:
            self._merge_config(config, source)
    
    def _load_from_file(self, path: str) -> Optional[Dict[str, Any]]:
        """Load MCP configuration from a YAML or JSON file."""
        file_path = Path(path)
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Try YAML first, then JSON
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError:
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse MCP config file: {path}")
                    return None
            
            if isinstance(data, dict) and 'mcp_servers' in data:
                return data['mcp_servers']
            
            return data
            
        except Exception as e:
            logger.warning(f"Error loading MCP config from {path}: {e}")
            return None
    
    def _load_from_env(self) -> Optional[Dict[str, Any]]:
        """Load MCP configuration from environment variables."""
        env_json = os.getenv('DBRHEO_MCP_SERVERS')
        if not env_json:
            return None
        
        try:
            return json.loads(env_json)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse DBRHEO_MCP_SERVERS: {e}")
            return None
    
    def _load_from_runtime(self) -> Optional[Dict[str, Any]]:
        """Load MCP configuration from runtime config."""
        # Check if DatabaseConfig has MCP servers configured
        runtime_config = {}
        
        # Try to get from test config first (highest priority)
        test_config = self.db_config.get_test_config('mcp_servers')
        if test_config:
            runtime_config = test_config
        
        # Check for mcp_server_command (single server mode)
        mcp_command = self.db_config.get_test_config('mcp_server_command')
        if mcp_command and isinstance(mcp_command, str):
            # Parse command into command and args
            import shlex
            parts = shlex.split(mcp_command)
            if parts:
                runtime_config['mcp'] = {
                    'command': parts[0],
                    'args': parts[1:] if len(parts) > 1 else []
                }
        
        return runtime_config if runtime_config else None
    
    def _merge_config(self, config: Dict[str, Any], source: str):
        """Merge configuration from a source into the current configuration."""
        if not config:
            return
        
        for server_name, server_config in config.items():
            if not isinstance(server_config, dict):
                logger.warning(
                    f"Invalid MCP server config for '{server_name}' from {source}"
                )
                continue
            
            try:
                # Convert dict to MCPServerConfig
                mcp_config = MCPServerConfig(**server_config)
                
                # Only add if enabled
                if mcp_config.enabled:
                    self.servers[server_name] = mcp_config
                    logger.debug(
                        f"Loaded MCP server '{server_name}' from {source}"
                    )
                elif server_name in self.servers:
                    # Remove if explicitly disabled
                    del self.servers[server_name]
                    logger.debug(
                        f"Disabled MCP server '{server_name}' from {source}"
                    )
                    
            except (TypeError, ValueError) as e:
                logger.warning(
                    f"Failed to load MCP server '{server_name}' from {source}: {e}"
                )
    
    def get_server(self, name: str) -> Optional[MCPServerConfig]:
        """Get configuration for a specific MCP server."""
        return self.servers.get(name)
    
    def get_all_servers(self) -> Dict[str, MCPServerConfig]:
        """Get all MCP server configurations."""
        return self.servers.copy()
    
    def add_server(self, name: str, config: MCPServerConfig):
        """Add or update an MCP server configuration at runtime."""
        self.servers[name] = config
        logger.info(f"Added MCP server '{name}' at runtime")
        # Save to persistent storage
        self._save_to_json()
    
    def remove_server(self, name: str) -> bool:
        """Remove an MCP server configuration."""
        if name in self.servers:
            del self.servers[name]
            logger.info(f"Removed MCP server '{name}'")
            # Save to persistent storage
            self._save_to_json()
            return True
        return False
    
    def _save_to_json(self):
        """Save current configuration to .dbrheo.json file."""
        # Find the project root by looking for .dbrheo.json upwards
        current_dir = Path.cwd()
        config_file = None
        
        # Search for project root (where pyproject.toml or packages/ exists)
        for parent in [current_dir] + list(current_dir.parents):
            # Check if this is the project root
            if (parent / "pyproject.toml").exists() and (parent / "packages").exists():
                # This is definitely the project root
                config_file = parent / ".dbrheo.json"
                break
            # Also check if we're inside packages/cli and need to go up
            elif parent.name == "cli" and parent.parent.name == "packages":
                # Go up to project root
                config_file = parent.parent.parent / ".dbrheo.json"
                break
        
        # Fallback to current directory if no project root found
        if config_file is None:
            config_file = Path.cwd() / ".dbrheo.json"
        
        try:
            # Load existing config or create new one
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}
            
            # Convert MCPServerConfig objects to dictionaries
            mcp_servers = {}
            for name, config in self.servers.items():
                server_dict = {
                    'command': config.command,
                    'args': config.args,
                    'env': config.env,
                    'cwd': config.cwd,
                    'url': config.url,
                    'http_url': config.http_url,
                    'headers': config.headers,
                    'tcp': config.tcp,
                    'timeout': config.timeout,
                    'trust': config.trust,
                    'include_tools': config.include_tools,
                    'exclude_tools': config.exclude_tools,
                    'description': config.description,
                    'enabled': config.enabled
                }
                # Remove None values to keep config clean
                server_dict = {k: v for k, v in server_dict.items() if v is not None}
                mcp_servers[name] = server_dict
            
            # Update MCP servers in config
            data['mcp_servers'] = mcp_servers
            
            # Write back to file
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved MCP configuration to {config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save MCP configuration: {e}")
    
    def is_enabled(self, name: str) -> bool:
        """Check if an MCP server is enabled."""
        server = self.servers.get(name)
        return server.enabled if server else False