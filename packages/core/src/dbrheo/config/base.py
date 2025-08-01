"""
DatabaseConfig - 分层配置系统
实现System > Workspace > User的配置优先级，完全对齐Gemini CLI设计
"""

import os
import re
import json
import yaml
from typing import Any, Optional, Dict, List, Union
from pathlib import Path
from abc import ABC, abstractmethod


class ConfigSource(ABC):
    """配置源基类"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """获取配置值"""
        pass
        
    @abstractmethod
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        pass


class SystemConfig(ConfigSource):
    """系统级配置 - 最高优先级"""
    
    def __init__(self):
        self._config = {}
        self._load_system_config()
        
    def _load_system_config(self):
        """加载系统级配置文件"""
        # 系统配置路径（优先级从高到低）
        config_paths = [
            Path("/etc/dbrheo/config.yaml"),
            Path("/etc/dbrheo/config.json"),
            Path.home() / ".config/dbrheo/system.yaml",
            Path.home() / ".config/dbrheo/system.json",
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        if config_path.suffix == '.yaml':
                            self._config = yaml.safe_load(f) or {}
                        else:
                            self._config = json.load(f)
                    break
                except Exception:
                    continue
                    
    def get(self, key: str) -> Optional[Any]:
        return self._config.get(key)
        
    def get_all(self) -> Dict[str, Any]:
        return self._config.copy()


class WorkspaceConfig(ConfigSource):
    """工作区级配置 - 项目级别"""
    
    def __init__(self, workspace_root: Optional[Path] = None):
        self._config = {}
        self._workspace_root = workspace_root or Path.cwd()
        self._load_workspace_config()
        
    def _load_workspace_config(self):
        """加载工作区配置文件"""
        # 向上查找配置文件
        current = self._workspace_root
        config_names = [".dbrheo.yaml", ".dbrheo.json", "dbrheo.config.yaml", "dbrheo.config.json"]
        
        while current != current.parent:
            for config_name in config_names:
                config_path = current / config_name
                if config_path.exists():
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            if config_path.suffix in ['.yaml', '.yml']:
                                self._config = yaml.safe_load(f) or {}
                            else:
                                self._config = json.load(f)
                        return
                    except Exception:
                        continue
            current = current.parent
                    
    def get(self, key: str) -> Optional[Any]:
        return self._config.get(key)
        
    def get_all(self) -> Dict[str, Any]:
        return self._config.copy()


class UserConfig(ConfigSource):
    """用户级配置 - 最低优先级"""
    
    def __init__(self):
        self._config = {}
        self._load_user_config()
        
    def _load_user_config(self):
        """加载用户配置文件"""
        config_paths = [
            Path.home() / ".dbrheo/config.yaml",
            Path.home() / ".dbrheo/config.json",
            Path.home() / ".config/dbrheo/config.yaml",
            Path.home() / ".config/dbrheo/config.json",
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        if config_path.suffix == '.yaml':
                            self._config = yaml.safe_load(f) or {}
                        else:
                            self._config = json.load(f)
                    break
                except Exception:
                    continue
                    
    def get(self, key: str) -> Optional[Any]:
        return self._config.get(key)
        
    def get_all(self) -> Dict[str, Any]:
        return self._config.copy()


class EnvironmentConfig(ConfigSource):
    """环境变量配置 - 特殊处理，可覆盖任何级别"""
    
    def __init__(self):
        self._env_mappings = {
            "DBRHEO_API_KEY": "google_api_key",
            "GOOGLE_API_KEY": "google_api_key",
            "ANTHROPIC_API_KEY": "anthropic_api_key",
            "CLAUDE_API_KEY": "claude_api_key",
            "OPENAI_API_KEY": "openai_api_key",
            "OPENAI_API_BASE": "openai_api_base",
            "DATABASE_AGENT_SYSTEM_MD": "system_prompt_override",
            "DBRHEO_DATABASE_URL": "database_url",
            "DATABASE_URL": "database_url",
            "DBRHEO_MODEL": "model",
            "DBRHEO_MAX_TURNS": "max_session_turns",
            "DBRHEO_COMPRESSION_THRESHOLD": "compression_threshold",
            "DBRHEO_AUTO_EXECUTE": "auto_execute_mode",
            "DBRHEO_ALLOW_DANGEROUS": "allow_dangerous_operations",
            "DBRHEO_HOST": "host",
            "DBRHEO_PORT": "port",
            "DBRHEO_DEBUG": "debug",
            "DBRHEO_LOG_LEVEL": "log_level",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "otlp_endpoint",
            "OTEL_SERVICE_NAME": "service_name",
            "ENABLE_CODE_EXECUTION": "enable_code_execution",
            "DBRHEO_ENABLE_CODE_EXECUTION": "enable_code_execution",
        }
        
    def get(self, key: str) -> Optional[Any]:
        # 先尝试直接匹配
        for env_key, config_key in self._env_mappings.items():
            if config_key == key:
                value = os.getenv(env_key)
                if value is not None:
                    return self._parse_value(value, config_key)
                    
        # 再尝试通用环境变量格式 DBRHEO_<KEY>
        env_key = f"DBRHEO_{key.upper()}"
        value = os.getenv(env_key)
        if value is not None:
            return self._parse_value(value, key)
            
        return None
        
    def get_all(self) -> Dict[str, Any]:
        config = {}
        for env_key, config_key in self._env_mappings.items():
            value = os.getenv(env_key)
            if value is not None:
                config[config_key] = self._parse_value(value, config_key)
        return config
        
    def _parse_value(self, value: str, key: str) -> Any:
        """解析环境变量值的类型"""
        # 布尔值
        if key in ["debug", "auto_execute_mode", "allow_dangerous_operations", "enable_code_execution"]:
            return value.lower() in ["true", "1", "yes", "on"]
            
        # 整数
        if key in ["port", "max_session_turns"]:
            try:
                return int(value)
            except ValueError:
                return value
                
        # 浮点数
        if key in ["compression_threshold"]:
            try:
                return float(value)
            except ValueError:
                return value
                
        return value


class DatabaseConfig:
    """
    分层配置系统（System > Workspace > User）
    完全对齐Gemini CLI的配置管理设计
    """
    
    def __init__(self, workspace_root: Optional[Path] = None):
        # 按优先级排列的配置源（高到低）
        self.config_sources: List[ConfigSource] = [
            EnvironmentConfig(),     # 环境变量最高优先级
            SystemConfig(),          # 系统级配置
            WorkspaceConfig(workspace_root),  # 工作区配置
            UserConfig(),            # 用户级配置
        ]
        
        # 加载默认配置
        self._defaults = self._load_defaults()
        
    def _load_defaults(self) -> Dict[str, Any]:
        """加载默认配置值"""
        return {
            # 基础配置
            "model": "gemini-2.5-flash",  # 默认使用最新的 Gemini 2.5 Flash
            "max_session_turns": 100,
            "compression_threshold": 0.7,
            "auto_execute_mode": False,
            "allow_dangerous_operations": False,
            
            # 服务器配置
            "host": "localhost",
            "port": 8000,
            "debug": False,
            "log_level": "INFO",
            
            # 数据库配置
            "default_database": "default",
            "database_url": "sqlite:///./default.db",
            "connection_pool_size": 10,
            "connection_timeout": 30,
            
            # 监控配置
            "otlp_endpoint": "http://localhost:4317",
            "service_name": "dbrheo",
            "enable_telemetry": True,
            
            # Agent行为配置
            "thinking_enabled": True,
            "auto_compress_history": True,
            "max_token_ratio": 0.7,
            "retry_max_attempts": 3,
            "retry_base_delay": 5000,
        }
        
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，按优先级查找
        支持嵌套键访问（用.分隔）和环境变量替换
        """
        # 支持嵌套键访问
        keys = key.split('.')
        
        # 按优先级查找配置
        for source in self.config_sources:
            value = self._get_nested(source.get_all(), keys)
            if value is not None:
                return self._substitute_vars(value)
                
        # 使用默认值
        value = self._get_nested(self._defaults, keys)
        if value is not None:
            return self._substitute_vars(value)
            
        return default
        
    def _get_nested(self, config: Dict[str, Any], keys: List[str]) -> Any:
        """获取嵌套配置值"""
        current = config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
        
    def _substitute_vars(self, value: Any) -> Any:
        """支持 ${VAR} 和 $VAR 格式的环境变量替换"""
        if not isinstance(value, str):
            return value
            
        # 递归替换，支持嵌套变量
        max_depth = 10
        depth = 0
        
        while '$' in value and depth < max_depth:
            old_value = value
            # 支持 ${VAR} 格式
            value = re.sub(
                r'\$\{([^}]+)\}',
                lambda m: os.environ.get(m.group(1), m.group(0)),
                value
            )
            # 支持 $VAR 格式
            value = re.sub(
                r'\$([A-Za-z_][A-Za-z0-9_]*)',
                lambda m: os.environ.get(m.group(1), m.group(0)),
                value
            )
            
            # 如果没有变化，退出循环
            if value == old_value:
                break
                
            depth += 1
            
        return value
        
    def get_all_sources(self) -> Dict[str, Dict[str, Any]]:
        """获取所有配置源的内容（用于调试）"""
        return {
            "environment": EnvironmentConfig().get_all(),
            "system": SystemConfig().get_all(),
            "workspace": WorkspaceConfig().get_all(),
            "user": UserConfig().get_all(),
            "defaults": self._defaults,
        }
        
    # 便捷方法
    def get_connection_string(self, db_name: str = "default") -> str:
        """获取数据库连接字符串"""
        if db_name == "default":
            return self.get("database_url", "sqlite:///./default.db")
        else:
            return self.get(f"databases.{db_name}.url", "")
            
    def get_working_dir(self) -> str:
        """获取工作目录"""
        return str(Path.cwd())
        
    def get_model(self) -> str:
        """获取当前使用的AI模型"""
        return self.get("model", "gemini-2.5-flash")
        
    def get_max_session_turns(self) -> int:
        """获取最大会话轮次"""
        return self.get("max_session_turns", 100)
        
    def is_debug(self) -> bool:
        """是否处于调试模式"""
        return self.get("debug", False)
        
    def allows_dangerous_operations(self) -> bool:
        """是否允许危险操作"""
        return self.get("allow_dangerous_operations", False)