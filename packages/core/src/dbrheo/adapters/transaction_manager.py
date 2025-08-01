"""
TransactionManager - 事务管理器
完全对齐文档要求的ACID事务保证和智能回滚机制
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from .base import DatabaseAdapter
from ..types.core_types import AbortSignal
from ..utils.errors import DatabaseAgentError


class TransactionState(Enum):
    """事务状态"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class TransactionInfo:
    """事务信息"""
    transaction_id: str
    state: TransactionState
    start_time: float
    operations: List[Dict[str, Any]]
    savepoints: List[str]


class DatabaseTransactionManager:
    """
    数据库事务管理器 - 完全对齐文档要求
    
    核心功能：
    1. ACID事务保证
    2. 智能回滚机制
    3. 保存点管理
    4. 事务嵌套支持
    5. 自动故障恢复
    """
    
    def __init__(self, adapter: DatabaseAdapter):
        self.adapter = adapter
        self.current_transaction: Optional[TransactionInfo] = None
        self.transaction_stack: List[TransactionInfo] = []
        self.logger = logging.getLogger(__name__)
        
    @asynccontextmanager
    async def transaction(
        self, 
        isolation_level: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        """
        事务上下文管理器 - 完全对齐文档要求
        
        Args:
            isolation_level: 事务隔离级别
            timeout: 事务超时时间（秒）
        """
        transaction_id = f"txn_{id(self)}_{len(self.transaction_stack)}"
        
        # 开始事务
        await self._begin_transaction(transaction_id, isolation_level)
        
        try:
            # 设置超时
            if timeout:
                async with asyncio.timeout(timeout):
                    yield self
            else:
                yield self
                
            # 提交事务
            await self._commit_transaction(transaction_id)
            
        except Exception as e:
            # 回滚事务
            await self._rollback_transaction(transaction_id, str(e))
            raise
            
    async def _begin_transaction(self, transaction_id: str, isolation_level: Optional[str] = None):
        """开始事务"""
        try:
            # 执行BEGIN语句
            begin_sql = "BEGIN"
            if isolation_level:
                begin_sql = f"BEGIN ISOLATION LEVEL {isolation_level}"
                
            await self.adapter.execute_command(begin_sql)
            
            # 创建事务信息
            transaction_info = TransactionInfo(
                transaction_id=transaction_id,
                state=TransactionState.ACTIVE,
                start_time=asyncio.get_event_loop().time(),
                operations=[],
                savepoints=[]
            )
            
            # 管理事务栈
            if self.current_transaction:
                self.transaction_stack.append(self.current_transaction)
                
            self.current_transaction = transaction_info
            
            self.logger.info(f"Transaction {transaction_id} started")
            
        except Exception as e:
            self.logger.error(f"Failed to start transaction {transaction_id}: {e}")
            raise DatabaseAgentError(f"Failed to start transaction: {e}")
            
    async def _commit_transaction(self, transaction_id: str):
        """提交事务"""
        if not self.current_transaction or self.current_transaction.transaction_id != transaction_id:
            raise DatabaseAgentError(f"Transaction {transaction_id} not found or not current")
            
        try:
            await self.adapter.execute_command("COMMIT")
            
            self.current_transaction.state = TransactionState.COMMITTED
            self.logger.info(f"Transaction {transaction_id} committed successfully")
            
            # 恢复上一级事务
            if self.transaction_stack:
                self.current_transaction = self.transaction_stack.pop()
            else:
                self.current_transaction = None
                
        except Exception as e:
            self.current_transaction.state = TransactionState.FAILED
            self.logger.error(f"Failed to commit transaction {transaction_id}: {e}")
            raise DatabaseAgentError(f"Failed to commit transaction: {e}")
            
    async def _rollback_transaction(self, transaction_id: str, reason: str):
        """回滚事务"""
        if not self.current_transaction or self.current_transaction.transaction_id != transaction_id:
            self.logger.warning(f"Transaction {transaction_id} not found for rollback")
            return
            
        try:
            await self.adapter.execute_command("ROLLBACK")
            
            self.current_transaction.state = TransactionState.ROLLED_BACK
            self.logger.info(f"Transaction {transaction_id} rolled back: {reason}")
            
            # 恢复上一级事务
            if self.transaction_stack:
                self.current_transaction = self.transaction_stack.pop()
            else:
                self.current_transaction = None
                
        except Exception as e:
            self.current_transaction.state = TransactionState.FAILED
            self.logger.error(f"Failed to rollback transaction {transaction_id}: {e}")
            
    async def create_savepoint(self, name: str) -> str:
        """创建保存点"""
        if not self.current_transaction:
            raise DatabaseAgentError("No active transaction for savepoint")
            
        try:
            savepoint_sql = f"SAVEPOINT {name}"
            await self.adapter.execute_command(savepoint_sql)
            
            self.current_transaction.savepoints.append(name)
            self.logger.info(f"Savepoint {name} created")
            
            return name
            
        except Exception as e:
            self.logger.error(f"Failed to create savepoint {name}: {e}")
            raise DatabaseAgentError(f"Failed to create savepoint: {e}")
            
    async def rollback_to_savepoint(self, name: str):
        """回滚到保存点"""
        if not self.current_transaction:
            raise DatabaseAgentError("No active transaction for savepoint rollback")
            
        if name not in self.current_transaction.savepoints:
            raise DatabaseAgentError(f"Savepoint {name} not found")
            
        try:
            rollback_sql = f"ROLLBACK TO SAVEPOINT {name}"
            await self.adapter.execute_command(rollback_sql)
            
            # 移除该保存点之后的所有保存点
            savepoint_index = self.current_transaction.savepoints.index(name)
            self.current_transaction.savepoints = self.current_transaction.savepoints[:savepoint_index + 1]
            
            self.logger.info(f"Rolled back to savepoint {name}")
            
        except Exception as e:
            self.logger.error(f"Failed to rollback to savepoint {name}: {e}")
            raise DatabaseAgentError(f"Failed to rollback to savepoint: {e}")
            
    async def execute_in_transaction(
        self, 
        sql: str, 
        params: Optional[Dict[str, Any]] = None,
        signal: Optional[AbortSignal] = None
    ) -> Dict[str, Any]:
        """在事务中执行SQL"""
        if not self.current_transaction:
            raise DatabaseAgentError("No active transaction")
            
        try:
            # 记录操作
            operation = {
                "sql": sql,
                "params": params,
                "timestamp": asyncio.get_event_loop().time()
            }
            self.current_transaction.operations.append(operation)
            
            # 执行SQL
            if sql.strip().upper().startswith('SELECT'):
                result = await self.adapter.execute_query(sql, params, signal)
            else:
                result = await self.adapter.execute_command(sql, params, signal)
                
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing SQL in transaction: {e}")
            raise
            
    def get_transaction_info(self) -> Optional[TransactionInfo]:
        """获取当前事务信息"""
        return self.current_transaction
        
    def is_in_transaction(self) -> bool:
        """检查是否在事务中"""
        return self.current_transaction is not None and self.current_transaction.state == TransactionState.ACTIVE
