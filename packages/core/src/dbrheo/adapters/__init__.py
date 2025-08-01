"""
数据库适配器系统 - 支持多数据库方言和连接管理
提供统一的数据库操作接口，支持MySQL、PostgreSQL、SQLite等
"""

from .base import DatabaseAdapter
from .connection_manager import DatabaseConnectionManager

__all__ = [
    "DatabaseAdapter",
    "DatabaseConnectionManager"
]
