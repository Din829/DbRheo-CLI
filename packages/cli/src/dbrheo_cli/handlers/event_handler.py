"""
事件处理器
负责处理send_message_stream产生的各种事件。
对应Gemini CLI的useGeminiStream中的事件处理逻辑。
"""

from typing import Dict, Any, Optional
from dbrheo.utils.debug_logger import DebugLogger, log_info

from ..ui.console import console
from ..ui.messages import show_agent_message, show_error_message, show_system_message, show_tool_call
from ..ui.streaming import StreamDisplay
from ..i18n import _
from ..app.config import CLIConfig


class EventHandler:
    """
    核心事件处理器
    处理所有从后端接收的事件类型
    支持传统console输出和增强布局管理器
    """
    
    def __init__(self, config: CLIConfig):
        self.config = config
        self.stream_display = StreamDisplay(config)
        self.display_target = None  # 可选的显示目标（布局管理器）
    
    def set_display_target(self, target):
        """设置显示目标 - 最小侵入性集成点"""
        self.display_target = target
        
    async def process(self, event: Dict[str, Any]):
        """处理单个事件"""
        event_type = event.get('type', '')
        value = event.get('value', '')
        
        if DebugLogger.should_log("DEBUG"):
            log_info("EventHandler", f"Processing event: {event_type}")
        
        # 根据事件类型分发处理
        if event_type == 'Content':
            await self._handle_content(value)
        elif event_type == 'Thought':
            await self._handle_thought(value)
        elif event_type == 'ToolCallRequest':
            await self._handle_tool_request(value)
        elif event_type == 'Error':
            await self._handle_error(value)
        elif event_type == 'AwaitingConfirmation':
            await self._handle_awaiting_confirmation(value)
        elif event_type == 'max_session_turns':
            await self._handle_max_turns(value)
        elif event_type == 'chat_compressed':
            await self._handle_chat_compressed(value)
        else:
            # 未知事件类型
            if DebugLogger.should_log("DEBUG"):
                log_info("EventHandler", f"Unknown event type: {event_type}")
    
    async def _handle_content(self, content: str):
        """处理AI响应内容"""
        # 调试：检查内容
        if DebugLogger.should_log("DEBUG"):
            log_info("EventHandler", f"Content received: {repr(content[:100])}")
        
        # 使用流式显示
        await self.stream_display.add_content(content)
    
    async def _handle_thought(self, thought: str):
        """处理AI思考过程"""
        if self.config.show_thoughts:
            console.print(f"[dim italic]{thought}[/dim italic]", end='')
    
    async def _handle_tool_request(self, tool_data: Any):
        """处理工具调用请求"""
        # tool_data 是一个对象，不是字典
        tool_name = getattr(tool_data, 'name', 'unknown')
        
        # 显示工具调用提示
        show_tool_call(tool_name)
        
        # 工具请求由tool_handler处理，这里只记录日志
        if DebugLogger.should_log("DEBUG"):
            log_info("EventHandler", f"Tool request: {tool_name}")
    
    async def _handle_error(self, error: str):
        """处理错误事件"""
        show_error_message(error)
    
    async def _handle_awaiting_confirmation(self, data: Any):
        """处理等待确认事件"""
        # 确认提示由tool_handler显示，这里只需要结束流式显示
        await self.stream_display.finish()
        if DebugLogger.should_log("DEBUG"):
            log_info("EventHandler", "Awaiting confirmation, breaking event loop")
    
    async def _handle_max_turns(self, data: Any):
        """处理达到最大会话轮数"""
        show_system_message(_('max_session_turns'))
    
    async def _handle_chat_compressed(self, data: Any):
        """处理会话压缩通知"""
        if DebugLogger.should_log("INFO"):
            show_system_message(_('chat_compressed'))
    
    def show_user_message(self, message: str):
        """显示用户消息"""
        # 先结束之前的流式显示
        self.stream_display.finish_sync()
        
        # 用户消息已经在输入时显示了，这里只需要添加空行
        console.print()  # 添加空行准备显示AI响应