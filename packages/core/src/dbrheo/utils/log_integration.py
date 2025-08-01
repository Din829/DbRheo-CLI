"""
日志系统集成 - 将实时日志集成到DbRheo的各个组件
"""

from typing import Dict, Any, Optional
from functools import wraps
import asyncio

from .realtime_logger import (
    get_logger, log_conversation, log_tool_call, 
    log_tool_result, log_error, log_system
)


def log_chat_interaction(func):
    """装饰器 - 记录Chat交互（支持异步生成器）"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        # 记录用户输入
        if args and isinstance(args[0], list):
            messages = args[0]
            for msg in messages:
                if isinstance(msg, dict) and 'text' in msg:
                    log_conversation("User", msg['text'])
        elif args and isinstance(args[0], str):
            log_conversation("User", args[0])
        
        try:
            # 执行原函数 - 返回异步生成器
            async for chunk in func(self, *args, **kwargs):
                yield chunk
            
            # 记录AI响应（在生成器完成后）
            if hasattr(self, 'history') and self.history:
                last_response = None
                for item in reversed(self.history):
                    if item.get('role') == 'model':
                        last_response = item
                        break
                        
                if last_response:
                    model_text = ""
                    for part in last_response.get('parts', []):
                        if isinstance(part, dict) and 'text' in part:
                            model_text += part['text']
                    if model_text:
                        log_conversation("Agent", model_text)
            
        except Exception as e:
            log_error(self.__class__.__name__, str(e))
            raise
    
    return wrapper


def log_tool_execution(func):
    """装饰器 - 记录工具执行"""
    @wraps(func)
    async def wrapper(self, params: Dict[str, Any], *args, **kwargs):
        tool_name = getattr(self, 'name', self.__class__.__name__)
        
        # 获取call_id
        call_id = ""
        if len(args) >= 2 and hasattr(args[1], 'get'):
            call_id = args[1].get('call_id', '')
        
        # 记录工具调用
        log_tool_call(tool_name, params, call_id)
        
        try:
            # 执行工具
            result = await func(self, params, *args, **kwargs)
            
            # 记录结果
            success = True
            result_summary = None
            
            if hasattr(result, 'error') and result.error:
                success = False
                result_summary = result.error
            elif hasattr(result, 'summary'):
                result_summary = result.summary
            elif hasattr(result, 'llm_content'):
                result_summary = result.llm_content[:200] + "..." if len(result.llm_content) > 200 else result.llm_content
            else:
                result_summary = str(result)[:200]
            
            log_tool_result(tool_name, result_summary, success, call_id)
            
            return result
        except Exception as e:
            log_tool_result(tool_name, str(e), False, call_id)
            raise
    
    return wrapper


def log_scheduler_activity(func):
    """装饰器 - 记录调度器活动"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            result = await func(self, *args, **kwargs)
            
            # 记录调度状态变化
            if hasattr(self, 'tool_calls'):
                for call_id, call_state in self.tool_calls.items():
                    state = call_state.get('state', 'unknown')
                    tool_name = call_state.get('name', 'unknown')
                    log_system(f"Tool {tool_name} state: {state}", call_id=call_id)
            
            return result
        except Exception as e:
            log_error("Scheduler", str(e))
            raise
    
    return wrapper


class LoggingMixin:
    """日志混入类 - 为类添加日志功能"""
    
    def log_info(self, message: str, **kwargs):
        """记录信息"""
        log_system(f"[{self.__class__.__name__}] {message}", **kwargs)
    
    def log_error(self, message: str, **kwargs):
        """记录错误"""
        log_error(self.__class__.__name__, message, **kwargs)
    
    def log_performance(self, metric: str, value: float, unit: str = "ms", **kwargs):
        """记录性能指标"""
        from .realtime_logger import get_logger, LogEvent, LogEventType
        get_logger().log_performance(f"{self.__class__.__name__}.{metric}", value, unit, **kwargs)


# 快速集成函数
def integrate_logging():
    """快速集成日志到现有组件"""
    # 改为最小侵入性方式：不使用装饰器，因为装饰器会改变异步生成器的行为
    # 日志记录已经直接添加到 chat.py 和 scheduler.py 中
    log_system("实时日志系统已启用（非侵入模式）", source="LogIntegration")


# 环境变量控制的自动集成
import os
if os.environ.get('DBRHEO_ENABLE_REALTIME_LOG', '').lower() == 'true':
    integrate_logging()
    log_system("实时日志系统已自动启用", source="Environment")