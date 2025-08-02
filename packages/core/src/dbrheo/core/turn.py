"""
DatabaseTurn - Turn系统实现
管理单个对话轮次，只收集工具调用不执行，完全对齐Gemini CLI
"""

from typing import List, AsyncIterator
from ..types.core_types import PartListUnion, AbortSignal
from ..types.tool_types import ToolCallRequestInfo
from .chat import DatabaseChat
from ..utils.debug_logger import DebugLogger


class DatabaseTurn:
    """
    管理单个对话轮次的执行 - 只收集，不执行
    - 单个对话轮次管理
    - 只收集工具调用，绝不执行（pending_tool_calls）
    - 流式响应处理
    - 事件生成和传递
    """
    
    def __init__(self, chat: DatabaseChat, prompt_id: str):
        self.chat = chat
        self.prompt_id = prompt_id
        self.pending_tool_calls: List[ToolCallRequestInfo] = []  # 只收集
        
    async def run(self, request: PartListUnion, signal: AbortSignal) -> AsyncIterator[dict]:
        """
        执行Turn - 收集工具调用但不执行
        严格遵循Gemini CLI的Turn执行模式
        """
        # 1. 发送请求到LLM（包含完整历史）
        response_stream = self.chat.send_message_stream(request, self.prompt_id)
        
        # 2. 流式处理响应，收集工具调用
        chunk_count = 0
        async for chunk in response_stream:
            chunk_count += 1
            # 使用优化的日志
            if DebugLogger.get_rules()["show_chunk_details"]:
                DebugLogger.log_turn_event("chunk_received", chunk)
            # 处理文本内容
            if chunk.get('text'):
                yield {'type': 'Content', 'value': chunk['text']}
                
            # 处理思维内容
            if chunk.get('thought'):
                yield {'type': 'Thought', 'value': chunk['thought']}
                
            # 处理工具调用
            if chunk.get('function_calls'):
                for call in chunk['function_calls']:
                    # 生成调用ID（如果没有提供）- 参考 Gemini CLI
                    import time
                    import random
                    call_id = call.get('id') or f"{call['name']}-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
                    
                    # 关键：只收集，不执行（与Gemini CLI完全一致）
                    tool_request = ToolCallRequestInfo(
                        call_id=call_id,
                        name=call['name'],
                        args=call['args'],
                        is_client_initiated=False,
                        prompt_id=self.prompt_id
                    )
                    self.pending_tool_calls.append(tool_request)
                    yield {'type': 'ToolCallRequest', 'value': tool_request}
                    DebugLogger.log_turn_event("tool_request", tool_request)
                    
            # 处理错误
            if chunk.get('type') == 'error':
                yield {'type': 'Error', 'value': chunk.get('error', 'Unknown error')}
            
            # 处理 token 使用信息 - 新增事件类型
            if chunk.get('token_usage'):
                # 添加调试日志
                DebugLogger.log_turn_event("token_usage", chunk['token_usage'])
                yield {'type': 'TokenUsage', 'value': chunk['token_usage']}
        
        DebugLogger.log_turn_event("summary", chunk_count)
        
        # 3. Turn结束，pending_tool_calls留给调度器处理
        # 绝不在Turn中执行工具！
