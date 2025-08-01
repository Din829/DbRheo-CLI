"""
核心类型定义 - 完全对齐Gemini CLI
基于Gemini CLI的TypeScript类型定义转换为Python
"""

from typing import Union, Optional, Dict, List, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class Part:
    """
    对应Gemini CLI的Part类型
    支持文本、内联数据、函数调用和函数响应
    """
    text: Optional[str] = None
    inline_data: Optional[Dict[str, str]] = None  # {mimeType: str, data: str}
    file_data: Optional[Dict[str, str]] = None    # {mimeType: str, fileUri: str}
    function_call: Optional[Dict[str, Any]] = None
    function_response: Optional[Dict[str, Any]] = None
    # Gemini特有的扩展字段
    video_metadata: Optional[Dict[str, Any]] = None   # 对应videoMetadata
    thought: Optional[str] = None                     # 对应thought
    code_execution_result: Optional[Dict[str, Any]] = None  # 对应codeExecutionResult
    executable_code: Optional[Dict[str, Any]] = None  # 对应executableCode


# 完全对齐Gemini CLI的PartListUnion定义
PartListUnion = Union[str, Part, List[Part]]


@dataclass
class Content:
    """对应Gemini API的Content类型"""
    role: str  # 'user' | 'model' | 'function'
    parts: List[Part]


class AbortSignal(ABC):
    """
    中止信号接口 - 对应JavaScript的AbortSignal
    用于取消长时间运行的操作
    """
    
    @property
    @abstractmethod
    def aborted(self) -> bool:
        """是否已中止"""
        pass
        
    @abstractmethod
    def abort(self):
        """中止操作"""
        pass


class SimpleAbortSignal(AbortSignal):
    """简单的中止信号实现"""
    
    def __init__(self):
        self._aborted = False
        
    @property
    def aborted(self) -> bool:
        return self._aborted
        
    def abort(self):
        self._aborted = True
    
    def reset(self):
        """重置中止状态"""
        self._aborted = False
