"""
DbRheo数据库Agent核心包
导出主要API供外部使用 - 基于Gemini CLI架构设计
"""

# 核心组件
from .core.client import DatabaseClient
from .core.chat import DatabaseChat
from .core.turn import DatabaseTurn
from .core.scheduler import DatabaseToolScheduler
from .core.prompts import DatabasePromptManager

# 工具系统
from .tools.sql_tool import SQLTool
from .tools.schema_discovery import SchemaDiscoveryTool
from .tools.registry import DatabaseToolRegistry
from .tools.base import DatabaseTool
from .tools.risk_evaluator import DatabaseRiskEvaluator

# 适配器
from .adapters.base import DatabaseAdapter
from .adapters.connection_manager import DatabaseConnectionManager
from .adapters.sqlite_adapter import SQLiteAdapter
from .adapters.transaction_manager import DatabaseTransactionManager
from .adapters.dialect_parser import SQLDialectParser

# 服务层
from .services.gemini_service_new import GeminiService

# 监控遥测
from .telemetry.tracer import DatabaseTracer
from .telemetry.metrics import DatabaseMetrics
from .telemetry.logger import DatabaseLogger

# 配置
from .config.base import DatabaseConfig

# 工具函数
from .utils.retry import with_retry, RetryConfig
from .utils.errors import DatabaseAgentError, ToolExecutionError

# 类型定义
from .types.core_types import *
from .types.tool_types import *

# API
from .api.app import create_app

__version__ = "1.0.0"
__all__ = [
    # 核心组件
    "DatabaseClient",
    "DatabaseChat",
    "DatabaseTurn",
    "DatabaseToolScheduler",
    "DatabasePromptManager",

    # 工具系统
    "SQLTool",
    "SchemaDiscoveryTool",
    "DatabaseToolRegistry",
    "DatabaseTool",
    "DatabaseRiskEvaluator",

    # 适配器
    "DatabaseAdapter",
    "DatabaseConnectionManager",
    "SQLiteAdapter",
    "DatabaseTransactionManager",
    "SQLDialectParser",

    # 服务层
    "GeminiService",

    # 监控遥测
    "DatabaseTracer",
    "DatabaseMetrics",
    "DatabaseLogger",

    # 配置
    "DatabaseConfig",

    # 工具函数
    "with_retry",
    "RetryConfig",
    "DatabaseAgentError",
    "ToolExecutionError",

    # API
    "create_app"
]
