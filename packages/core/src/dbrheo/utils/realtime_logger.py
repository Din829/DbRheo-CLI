"""
实时日志系统 - 独立窗口显示Agent对话和工具调用
灵活设计，支持多种输出方式和过滤级别
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from pathlib import Path
import threading
from queue import Queue, Empty
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


class LogLevel(Enum):
    """日志级别"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class LogEventType(Enum):
    """日志事件类型"""
    CONVERSATION = "conversation"      # 对话记录
    TOOL_CALL = "tool_call"           # 工具调用
    TOOL_RESULT = "tool_result"       # 工具结果
    SYSTEM = "system"                 # 系统信息
    ERROR = "error"                   # 错误信息
    NETWORK = "network"               # 网络请求
    PERFORMANCE = "performance"       # 性能指标


@dataclass
class LogEvent:
    """日志事件"""
    timestamp: float = field(default_factory=time.time)
    event_type: LogEventType = LogEventType.SYSTEM
    level: LogLevel = LogLevel.INFO
    source: str = ""                  # 事件来源（如 "DatabaseChat", "SQLTool"）
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def formatted_time(self) -> str:
        """格式化的时间戳"""
        return datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S.%f")[:-3]


class LogOutput(ABC):
    """日志输出接口 - 支持多种输出方式"""
    
    @abstractmethod
    async def write(self, event: LogEvent) -> None:
        """写入日志事件"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """关闭输出"""
        pass


class TerminalLogOutput(LogOutput):
    """终端输出 - 在独立终端窗口显示"""
    
    def __init__(self, title: str = "DbRheo Realtime Logger"):
        self.title = title
        self.is_running = True
        
    async def write(self, event: LogEvent) -> None:
        """写入到终端"""
        # 根据事件类型使用不同的颜色
        color_map = {
            LogEventType.CONVERSATION: "\033[36m",  # 青色
            LogEventType.TOOL_CALL: "\033[33m",     # 黄色
            LogEventType.TOOL_RESULT: "\033[32m",   # 绿色
            LogEventType.ERROR: "\033[31m",         # 红色
            LogEventType.SYSTEM: "\033[90m",        # 灰色
            LogEventType.NETWORK: "\033[35m",       # 紫色
            LogEventType.PERFORMANCE: "\033[34m",   # 蓝色
        }
        
        color = color_map.get(event.event_type, "\033[0m")
        reset = "\033[0m"
        
        # 格式化输出
        output = f"{color}[{event.formatted_time}] [{event.event_type.value}] {event.source}{reset}"
        if event.message:
            output += f" - {event.message}"
        
        # 如果有额外数据，缩进显示
        if event.data:
            for key, value in event.data.items():
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value, ensure_ascii=False, indent=2)
                    lines = value_str.split('\n')
                    output += f"\n  {key}:"
                    for line in lines:
                        output += f"\n    {line}"
                else:
                    output += f"\n  {key}: {value}"
        
        print(output)
        
    async def close(self) -> None:
        """关闭终端输出"""
        self.is_running = False


class FileLogOutput(LogOutput):
    """文件输出 - 保存到日志文件"""
    
    def __init__(self, file_path: str = "dbrheo_realtime.log", max_size: int = 10 * 1024 * 1024):
        self.file_path = Path(file_path)
        self.max_size = max_size
        self.file = None
        self._ensure_file()
        
    def _ensure_file(self):
        """确保日志文件存在"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(self.file_path, 'a', encoding='utf-8')
        
    async def write(self, event: LogEvent) -> None:
        """写入到文件"""
        # 检查文件大小，如果太大则轮转
        if self.file_path.stat().st_size > self.max_size:
            self.file.close()
            # 重命名旧文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.file_path.with_suffix(f'.{timestamp}.log')
            self.file_path.rename(backup_path)
            self._ensure_file()
        
        # 写入JSON格式
        log_entry = {
            "timestamp": event.timestamp,
            "time": event.formatted_time,
            "type": event.event_type.value,
            "level": event.level.name,
            "source": event.source,
            "message": event.message,
            "data": event.data
        }
        
        self.file.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        self.file.flush()
        
    async def close(self) -> None:
        """关闭文件"""
        if self.file:
            self.file.close()


class WebSocketLogOutput(LogOutput):
    """WebSocket输出 - 用于Web界面实时显示"""
    
    def __init__(self, websocket_url: str = "ws://localhost:8765"):
        self.url = websocket_url
        self.ws = None
        # TODO: 实现WebSocket连接
        
    async def write(self, event: LogEvent) -> None:
        """通过WebSocket发送"""
        # TODO: 实现WebSocket发送
        pass
        
    async def close(self) -> None:
        """关闭WebSocket连接"""
        if self.ws:
            await self.ws.close()


class RealtimeLogger:
    """实时日志记录器 - 灵活的日志系统"""
    
    def __init__(self):
        self.outputs: List[LogOutput] = []
        self.filters: List[Callable[[LogEvent], bool]] = []
        self.min_level = LogLevel.DEBUG
        self.enabled_types = set(LogEventType)
        self.queue = Queue()
        self.worker_thread = None
        self.is_running = False
        
    def add_output(self, output: LogOutput):
        """添加输出目标"""
        self.outputs.append(output)
        return self
        
    def add_filter(self, filter_func: Callable[[LogEvent], bool]):
        """添加过滤器"""
        self.filters.append(filter_func)
        return self
        
    def set_min_level(self, level: LogLevel):
        """设置最小日志级别"""
        self.min_level = level
        return self
        
    def enable_types(self, *types: LogEventType):
        """启用特定类型的日志"""
        self.enabled_types = set(types)
        return self
        
    def disable_types(self, *types: LogEventType):
        """禁用特定类型的日志"""
        for t in types:
            self.enabled_types.discard(t)
        return self
        
    def log(self, event: LogEvent):
        """记录日志事件"""
        # 检查是否应该记录
        if event.level.value < self.min_level.value:
            return
            
        if event.event_type not in self.enabled_types:
            return
            
        # 应用过滤器
        for filter_func in self.filters:
            if not filter_func(event):
                return
                
        # 加入队列
        self.queue.put(event)
        
    def log_conversation(self, role: str, content: str, **kwargs):
        """记录对话"""
        self.log(LogEvent(
            event_type=LogEventType.CONVERSATION,
            source="Conversation",
            message=f"{role}: {content[:100]}..." if len(content) > 100 else f"{role}: {content}",
            data={"role": role, "content": content, **kwargs}
        ))
        
    def log_tool_call(self, tool_name: str, params: Dict[str, Any], call_id: str = ""):
        """记录工具调用"""
        # 标准化参数，避免 protobuf 对象序列化错误
        safe_params = self._make_json_serializable(params)
        
        self.log(LogEvent(
            event_type=LogEventType.TOOL_CALL,
            source=f"Tool:{tool_name}",
            message=f"Calling {tool_name}",
            data={"tool": tool_name, "params": safe_params, "call_id": call_id}
        ))
        
    def log_tool_result(self, tool_name: str, result: Any, success: bool = True, call_id: str = ""):
        """记录工具结果"""
        self.log(LogEvent(
            event_type=LogEventType.TOOL_RESULT,
            level=LogLevel.INFO if success else LogLevel.ERROR,
            source=f"Tool:{tool_name}",
            message=f"{tool_name} {'succeeded' if success else 'failed'}",
            data={"tool": tool_name, "result": str(result)[:500], "success": success, "call_id": call_id}
        ))
        
    def log_error(self, source: str, error: str, **kwargs):
        """记录错误"""
        self.log(LogEvent(
            event_type=LogEventType.ERROR,
            level=LogLevel.ERROR,
            source=source,
            message=error,
            data=kwargs
        ))
        
    def log_system(self, message: str, **kwargs):
        """记录系统信息"""
        self.log(LogEvent(
            event_type=LogEventType.SYSTEM,
            source="System",
            message=message,
            data=kwargs
        ))
        
    def log_network(self, method: str, url: str, status: Optional[int] = None, **kwargs):
        """记录网络请求"""
        self.log(LogEvent(
            event_type=LogEventType.NETWORK,
            source="Network",
            message=f"{method} {url} -> {status or 'pending'}",
            data={"method": method, "url": url, "status": status, **kwargs}
        ))
        
    def log_performance(self, metric: str, value: float, unit: str = "ms", **kwargs):
        """记录性能指标"""
        self.log(LogEvent(
            event_type=LogEventType.PERFORMANCE,
            source="Performance",
            message=f"{metric}: {value}{unit}",
            data={"metric": metric, "value": value, "unit": unit, **kwargs}
        ))
        
    async def _worker(self):
        """后台工作线程 - 处理日志队列"""
        while self.is_running:
            try:
                # 使用更短的超时，提高响应性
                event = self.queue.get(timeout=0.1)
                # 写入所有输出
                for output in self.outputs:
                    try:
                        await output.write(event)
                    except Exception as e:
                        print(f"Log output error: {e}")
            except Empty:
                # 队列为空时短暂休息，让出CPU
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"Logger error: {e}")
                # 发生错误时短暂休息，避免紧密循环
                await asyncio.sleep(0.1)
    
    def _make_json_serializable(self, obj):
        """
        将对象转换为 JSON 可序列化的格式
        处理 protobuf 对象和其他不可序列化类型
        """
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        
        # 处理 protobuf 集合类型
        if hasattr(obj, '__iter__') and hasattr(obj, '_values'):
            return list(obj)
        
        if hasattr(obj, '__class__') and 'Repeated' in str(type(obj)):
            return list(obj)
        
        # 处理字典
        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        
        # 处理列表/元组
        if isinstance(obj, (list, tuple)):
            return [self._make_json_serializable(item) for item in obj]
        
        # 处理其他 protobuf 对象
        if hasattr(obj, '_pb') or 'google' in str(type(obj).__module__):
            if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
                return list(obj)
            elif hasattr(obj, '__dict__'):
                return {k: self._make_json_serializable(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
            else:
                return str(obj)
        
        # 其他类型转为字符串
        try:
            # 尝试直接序列化
            import json
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)
                
    def start(self):
        """启动日志系统"""
        if not self.is_running:
            self.is_running = True
            # 在独立线程中运行异步工作器
            def run_async_worker():
                asyncio.run(self._worker())
            self.worker_thread = threading.Thread(target=run_async_worker)
            self.worker_thread.start()
            
    def stop(self):
        """停止日志系统"""
        self.is_running = False
        if self.worker_thread and self.worker_thread.is_alive():
            # 设置超时，避免无限等待
            self.worker_thread.join(timeout=2.0)
            if self.worker_thread.is_alive():
                # 如果线程仍然活着，记录警告但不阻塞
                print("⚠️  日志系统线程未能在2秒内停止")
        
        # 尝试关闭所有输出，但不阻塞
        try:
            # 创建新的事件循环来运行清理任务
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._close_outputs())
            loop.close()
        except Exception:
            # 如果清理失败，继续退出
            pass
        
    async def _close_outputs(self):
        """关闭所有输出"""
        for output in self.outputs:
            await output.close()


# 全局日志实例
_logger: Optional[RealtimeLogger] = None


def get_logger() -> RealtimeLogger:
    """获取全局日志实例"""
    global _logger
    if _logger is None:
        _logger = RealtimeLogger()
        # 默认配置
        _logger.add_output(TerminalLogOutput())
        _logger.add_output(FileLogOutput())
        _logger.start()
    return _logger


# 便捷函数
def log_conversation(role: str, content: str, **kwargs):
    """记录对话"""
    get_logger().log_conversation(role, content, **kwargs)
    
def log_tool_call(tool_name: str, params: Dict[str, Any], call_id: str = ""):
    """记录工具调用"""
    get_logger().log_tool_call(tool_name, params, call_id)
    
def log_tool_result(tool_name: str, result: Any, success: bool = True, call_id: str = ""):
    """记录工具结果"""
    get_logger().log_tool_result(tool_name, result, success, call_id)
    
def log_error(source: str, error: str, **kwargs):
    """记录错误"""
    get_logger().log_error(source, error, **kwargs)
    
def log_system(message: str, **kwargs):
    """记录系统信息"""
    get_logger().log_system(message, **kwargs)