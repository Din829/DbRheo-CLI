"""
DatabaseAdapter基类 - 数据库适配器基础接口
提供统一的数据库操作接口，支持多数据库方言
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncIterator, TYPE_CHECKING
from ..types.core_types import AbortSignal
from .dialect_parser import SQLDialectParser, DatabaseDialect

if TYPE_CHECKING:
    from .transaction_manager import DatabaseTransactionManager


class DatabaseAdapter(ABC):
    """
    数据库适配器基类
    - 统一的数据库操作接口
    - 连接管理抽象
    - 方言转换接口
    """
    
    def __init__(self, connection_string: str, **kwargs):
        self.connection_string = connection_string
        self.config = kwargs
        self.transaction_manager: Optional["DatabaseTransactionManager"] = None
        self.dialect_parser: Optional[SQLDialectParser] = None
        
    @abstractmethod
    async def connect(self) -> None:
        """建立数据库连接"""
        pass
        
    @abstractmethod
    async def disconnect(self) -> None:
        """关闭数据库连接"""
        pass
        
    @abstractmethod
    async def execute_query(
        self, 
        sql: str, 
        params: Optional[Dict[str, Any]] = None,
        signal: Optional[AbortSignal] = None
    ) -> Dict[str, Any]:
        """执行查询并返回结果"""
        pass
        
    @abstractmethod
    async def execute_command(
        self, 
        sql: str, 
        params: Optional[Dict[str, Any]] = None,
        signal: Optional[AbortSignal] = None
    ) -> Dict[str, Any]:
        """执行命令（INSERT、UPDATE、DELETE等）"""
        pass
        
    @abstractmethod
    async def get_schema_info(self, schema_name: Optional[str] = None) -> Dict[str, Any]:
        """获取数据库结构信息"""
        pass
        
    @abstractmethod
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表结构信息"""
        pass
        
    @abstractmethod
    async def parse_sql(self, sql: str) -> Dict[str, Any]:
        """解析SQL语句"""
        pass
        
    @abstractmethod
    def get_dialect(self) -> str:
        """获取数据库方言"""
        pass
        
    async def apply_limit_if_needed(self, sql: str, limit: int) -> str:
        """
        智能地应用LIMIT子句（如果需要）
        基于SQL解析而非硬编码字符串匹配
        默认实现，子类可以覆盖以提供更智能的处理
        """
        # 解析SQL以检查是否已经有LIMIT
        try:
            parsed_info = await self.parse_sql(sql)
            sql_type = parsed_info.get('sql_type', '').upper()
            
            # 只对SELECT查询应用LIMIT
            # 支持适配器返回的各种SELECT标识方式
            if sql_type not in ['SELECT', 'QUERY']:
                return sql
                
            # 检查是否已经包含LIMIT（通过SQL解析而非字符串匹配）
            if parsed_info.get('has_limit', False):
                # 已经有LIMIT，不重复添加
                return sql
            else:
                # 添加LIMIT子句，让子类决定具体的SQL语法
                return self._append_limit_clause(sql, limit)
                
        except Exception:
            # 解析失败，使用保守的字符串检查作为后备
            # 但这应该是异常情况
            if 'LIMIT' not in sql.upper():
                return self._append_limit_clause(sql, limit)
            return sql
            
    def _append_limit_clause(self, sql: str, limit: int) -> str:
        """
        添加LIMIT子句的默认实现
        子类可以覆盖以处理特定方言的语法
        """
        # 移除末尾的分号（如果有）
        sql = sql.rstrip().rstrip(';')
        return f"{sql} LIMIT {limit}"
        
    async def health_check(self) -> bool:
        """连接健康检查"""
        try:
            await self.execute_query("SELECT 1")
            return True
        except:
            return False
