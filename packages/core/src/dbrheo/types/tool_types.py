"""
工具相关类型定义 - 完全对齐Gemini CLI的工具系统
包括工具结果、确认机制、状态管理等类型
"""

from typing import Union, Optional, Dict, List, Any, Callable
from dataclasses import dataclass
from enum import Enum
from .core_types import PartListUnion


@dataclass
class ToolResult:
    """
    工具执行结果 - 完全对齐Gemini CLI的ToolResult
    """
    summary: Optional[str] = None           # 可选的简短摘要
    llm_content: str = ""                   # LLM看到的内容
    return_display: Optional[str] = None    # 用户看到的格式化内容
    error: Optional[str] = None             # 错误信息


@dataclass
class ToolCallRequestInfo:
    """工具调用请求信息 - 对应Gemini CLI的ToolCallRequestInfo"""
    call_id: str                            # 对应callId
    name: str                               # 工具名称
    args: Dict[str, Any]                    # 工具参数
    is_client_initiated: bool = False       # 对应isClientInitiated
    prompt_id: str = ""                     # 对应prompt_id


@dataclass
class ToolCallResponseInfo:
    """工具调用响应信息"""
    call_id: str                            # 对应callId
    response_parts: PartListUnion           # 对应responseParts
    result_display: Optional[str] = None    # 对应resultDisplay
    error: Optional[Exception] = None       # 错误信息


class DatabaseConfirmationOutcome(Enum):
    """确认结果 - 完全对齐Gemini CLI的ToolConfirmationOutcome"""
    PROCEED_ONCE = "proceed_once"
    PROCEED_ALWAYS = "proceed_always"
    PROCEED_ALWAYS_SERVER = "proceed_always_server"  # 数据库服务器级总是允许
    PROCEED_ALWAYS_TOOL = "proceed_always_tool"      # 工具级总是允许
    MODIFY_WITH_EDITOR = "modify_with_editor"        # 编辑器修改SQL
    CANCEL = "cancel"


@dataclass
class DatabaseConfirmationDetails:
    """数据库确认详情基类"""
    type: str
    title: str
    on_confirm: Optional[Callable] = None


@dataclass
class SQLExecuteConfirmationDetails:
    """SQL执行确认 - 对应Gemini CLI的ToolExecuteConfirmationDetails"""
    title: str                              # 必需字段
    sql_query: str                          # 对应command字段
    root_operation: str                     # 对应rootCommand字段
    type: str = 'sql_execute'               # 默认值字段放后面
    risk_assessment: Optional[Dict[str, Any]] = None  # 风险评估详情
    estimated_impact: Optional[int] = None
    on_confirm: Optional[Callable] = None


# 工具调用状态类型（完全对齐Gemini CLI的状态机）
@dataclass
class ValidatingToolCall:
    request: Optional[ToolCallRequestInfo] = None
    tool: Optional[Any] = None  # DatabaseTool类型
    status: str = 'validating'
    start_time: Optional[float] = None


@dataclass
class ScheduledToolCall:
    request: Optional[ToolCallRequestInfo] = None
    tool: Optional[Any] = None
    status: str = 'scheduled'
    start_time: Optional[float] = None


@dataclass
class ExecutingToolCall:
    request: Optional[ToolCallRequestInfo] = None
    tool: Optional[Any] = None
    status: str = 'executing'
    live_output: Optional[str] = None
    start_time: Optional[float] = None


@dataclass
class SuccessfulToolCall:
    request: Optional[ToolCallRequestInfo] = None
    tool: Optional[Any] = None
    response: Optional[ToolCallResponseInfo] = None
    status: str = 'success'
    duration_ms: Optional[float] = None


@dataclass
class ErroredToolCall:
    request: Optional[ToolCallRequestInfo] = None
    response: Optional[ToolCallResponseInfo] = None
    status: str = 'error'
    duration_ms: Optional[float] = None


@dataclass
class CancelledToolCall:
    request: Optional[ToolCallRequestInfo] = None
    tool: Optional[Any] = None
    response: Optional[ToolCallResponseInfo] = None
    status: str = 'cancelled'
    duration_ms: Optional[float] = None


@dataclass
class WaitingToolCall:
    request: Optional[ToolCallRequestInfo] = None
    tool: Optional[Any] = None
    confirmation_details: Optional[DatabaseConfirmationDetails] = None
    status: str = 'awaiting_approval'
    start_time: Optional[float] = None


# 完整的状态联合类型（与Gemini CLI完全一致）
ToolCall = Union[
    ValidatingToolCall,
    ScheduledToolCall,
    ExecutingToolCall,
    SuccessfulToolCall,
    ErroredToolCall,
    CancelledToolCall,
    WaitingToolCall
]
