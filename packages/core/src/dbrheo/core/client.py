"""
DatabaseClient - 主控制器
负责会话管理和递归逻辑，完全对齐Gemini CLI的Client设计
"""

import asyncio
from typing import AsyncIterator, Optional, List
from typing import List, Dict, Any
from ..types.core_types import PartListUnion, AbortSignal, Content
from ..config.base import DatabaseConfig
from .chat import DatabaseChat
from ..utils.debug_logger import DebugLogger, log_info
from .turn import DatabaseTurn
from .scheduler import DatabaseToolScheduler


class DatabaseClient:
    """
    数据库Agent主控制器
    - 会话管理和递归逻辑（send_message_stream）
    - 历史压缩检查和触发（try_compress_chat）
    - next_speaker判断协调（check_next_speaker）
    - 工具调度器集成
    - 配置和环境管理
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.chat = DatabaseChat(config)
        # 保存已完成的工具调用
        self.completed_tool_calls = []
        # 创建调度器时设置回调
        self.tool_scheduler = DatabaseToolScheduler(
            config,
            on_all_tools_complete=self._on_tools_complete
        )
        self.session_turn_count = 0
        
    def _on_tools_complete(self, completed_calls):
        """工具执行完成的回调处理"""
        # 保存已完成的工具调用
        self.completed_tool_calls = completed_calls
        if DebugLogger.should_log("DEBUG"):
            log_info("Client", f"Received {len(completed_calls)} completed tool calls from scheduler")
        
        # 不要在这里处理！让主流程来处理
        # 否则会导致等待循环看不到completed_tool_calls
        
    def _process_completed_tools(self):
        """
        处理已完成的工具调用，将function response添加到历史
        
        这个方法被设计为可以多次调用而不会重复处理：
        - 从self.completed_tool_calls获取待处理的工具
        - 处理后立即清空self.completed_tool_calls
        - 这样即使在确认流程中也能确保function response被正确添加
        
        解决的问题：
        1. 确认流程导致的function response丢失
        2. ESC终止可能导致的function response未处理
        3. 任何其他导致正常流程被中断的情况
        """
        # 获取待处理的工具调用
        completed_tools = self.completed_tool_calls
        if not completed_tools:
            return  # 没有待处理的工具
            
        # 立即清空，避免重复处理
        self.completed_tool_calls = []
        
        if DebugLogger.should_log("DEBUG"):
            log_info("Client", f"_process_completed_tools处理 {len(completed_tools)} 个工具")
        
        # 收集工具响应
        function_responses = []
        for tool_call in completed_tools:
            if hasattr(tool_call, 'response') and tool_call.response:
                # response_parts已经是functionResponse格式
                # 重要：进行深度克隆，确保没有 protobuf 对象
                cloned_response = self.chat._safe_clone(tool_call.response.response_parts)
                function_responses.append(cloned_response)
                # 在VERBOSE模式下显示详细的functionResponse
                if DebugLogger.should_log("DEBUG") and DebugLogger.get_rules()["show_raw_chunks"]:
                    log_info("Client", f"Tool response: {tool_call.response.response_parts}")
                    
        if function_responses:
            if DebugLogger.should_log("DEBUG"):
                log_info("Client", f"收集到 {len(function_responses)} 个工具响应")
            
            # 将工具响应添加到历史记录
            # Gemini API要求function响应使用'user'角色
            function_content = {
                'role': 'user',
                'parts': function_responses
            }
            self.chat.add_history(function_content)
            
            if DebugLogger.should_log("DEBUG"):
                log_info("Client", f"function_content已添加到历史（通过_process_completed_tools）")
            
            DebugLogger.log_client_event("history_update", len(self.chat.get_history()))
            
            # 在VERBOSE模式下显示最新的历史记录
            if DebugLogger.should_log("DEBUG") and DebugLogger.get_rules()["show_raw_chunks"]:
                history = self.chat.get_history()
                if history:
                    log_info("Client", f"Latest history entry: {history[-1]}")
                    
    async def send_message_stream(
        self, 
        request: PartListUnion, 
        signal: AbortSignal,
        prompt_id: str,
        turns: int = 100,
        original_model: Optional[str] = None
    ) -> AsyncIterator[dict]:
        """
        核心递归逻辑 - 与Gemini CLI完全一致
        处理用户消息并返回流式响应
        """
        # 在开始新的消息流之前，确保之前的function response被处理
        # 这解决了确认流程和ESC终止可能导致的function response丢失问题
        self._process_completed_tools()
        
        self.session_turn_count += 1
        
        # 1. 会话级别限制检查
        max_session_turns = self.config.get("max_session_turns", 100)
        if max_session_turns > 0 and self.session_turn_count > max_session_turns:
            yield {"type": "max_session_turns"}
            return
            
        # 确保turns不超过最大值，防止无限循环
        bounded_turns = min(turns, 100)
        if not bounded_turns:
            return
            
        # 跟踪原始模型，检测模型切换
        initial_model = original_model or self.config.get_model()
        
        # 2. 历史压缩检查（数据库Agent简化版）
        compressed = await self.try_compress_chat(prompt_id)
        if compressed:
            yield {"type": "chat_compressed", "value": compressed}
            
        # 3. 执行当前Turn（只收集工具调用）
        turn = DatabaseTurn(self.chat, prompt_id)
        async for event in turn.run(request, signal):
            yield event
            
        # 4. 工具执行（如果有待执行的工具）
        if turn.pending_tool_calls:
            DebugLogger.log_client_event("tools_found", len(turn.pending_tool_calls))
            
            # 执行工具（异步，不等待完成）
            await self.tool_scheduler.schedule(turn.pending_tool_calls, signal)
            
            # 工具执行是异步的，这里只是启动了执行
            # 真正的完成处理在 _on_tools_complete 回调中
            # 为了确保工具执行完成，我们需要等待回调被触发
            
            # 等待工具执行完成（通过检查 completed_tool_calls）
            # 重要：如果有工具在等待确认，不应该阻塞等待
            import asyncio
            
            # 检查是否有工具在等待确认
            has_awaiting_approval = any(
                call.status == 'awaiting_approval' 
                for call in self.tool_scheduler.tool_calls
            )
            
            if has_awaiting_approval:
                # 有工具等待确认，立即返回让用户可以输入
                log_info("Client", "工具等待确认中，返回用户界面")
                # 生成一个等待确认的事件
                yield {
                    "type": "AwaitingConfirmation",
                    "value": "有操作需要确认，请查看上方提示"
                }
                return  # 结束这次消息流，让用户可以输入确认命令
            
            # 没有等待确认的工具，正常等待执行完成
            max_wait = 30  # 最多等待30秒
            poll_interval = 0.1
            waited = 0
            
            while waited < max_wait and not self.completed_tool_calls:
                await asyncio.sleep(poll_interval)
                waited += poll_interval
                
            if waited >= max_wait and not self.completed_tool_calls:
                log_info("Client", f"Warning: Waited {max_wait}s but no tools completed")
            
            DebugLogger.log_client_event("execution_complete", {"count": len(self.tool_scheduler.tool_calls)})
            
            # 检查是否有已完成的工具需要处理
            # 先保存引用，避免被清空
            has_completed_tools = len(self.completed_tool_calls) > 0
            
            # 尝试处理已完成的工具（新增的灵活处理机制）
            # 这确保即使在等待期间有新的工具完成，也会被处理
            self._process_completed_tools()
            
            # 如果_process_completed_tools已经处理了工具，我们需要继续对话
            if has_completed_tools:
                log_info("Client", "工具已通过_process_completed_tools处理，发送Please continue")
                DebugLogger.log_client_event("recursion_start", None)
                
                # 按照设计文档，工具执行后应该添加 "Please continue." 让模型继续
                async for event in self.send_message_stream(
                    [{"text": "Please continue."}],
                    signal,
                    prompt_id,
                    bounded_turns - 1,
                    initial_model
                ):
                    yield event
                return
            
            # 原有逻辑保持不变（作为后备机制）
            # 这个分支理论上不应该被执行到，因为_process_completed_tools已经处理了
            completed_tools = self.completed_tool_calls
            # 清空保存的调用，避免重复处理
            self.completed_tool_calls = []
            
            # 精简工具执行日志
            if DebugLogger.should_log("DEBUG"):
                for tool_call in completed_tools:
                    DebugLogger.log_scheduler_event("tool_complete", {"name": tool_call.request.name, "status": tool_call.status})
            
            # 收集工具响应并添加到历史（原有逻辑）
            if completed_tools:
                function_responses = []
                for tool_call in completed_tools:
                    if hasattr(tool_call, 'response') and tool_call.response:
                        # response_parts已经是functionResponse格式
                        # 重要：进行深度克隆，确保没有 protobuf 对象
                        cloned_response = self.chat._safe_clone(tool_call.response.response_parts)
                        function_responses.append(cloned_response)
                        # 在VERBOSE模式下显示详细的functionResponse
                        if DebugLogger.should_log("DEBUG") and DebugLogger.get_rules()["show_raw_chunks"]:
                            log_info("Client", f"Tool response: {tool_call.response.response_parts}")
                        
                if function_responses:
                    if DebugLogger.should_log("DEBUG"):
                        log_info("Client", f"收集到 {len(function_responses)} 个工具响应")
                    
                    # 将工具响应添加到历史记录
                    # Gemini API要求function响应使用'user'角色
                    function_content = {
                        'role': 'user',
                        'parts': function_responses
                    }
                    self.chat.add_history(function_content)
                    
                    DebugLogger.log_client_event("history_update", len(self.chat.get_history()))
                    
                    # 在VERBOSE模式下显示最新的历史记录
                    if DebugLogger.should_log("DEBUG") and DebugLogger.get_rules()["show_raw_chunks"]:
                        history = self.chat.get_history()
                        if history:
                            log_info("Client", f"Latest history entry: {history[-1]}")
                    
                    # 调度器会自动在 _check_and_notify_completion 中清理状态
                    # 不需要手动清理 self.tool_scheduler.tool_calls
                    
                    DebugLogger.log_client_event("recursion_start", None)
                    
                    # 按照设计文档，工具执行后应该添加 "Please continue." 让模型继续
                    # 这符合 Gemini CLI 的设计模式
                    async for event in self.send_message_stream(
                        [{"text": "Please continue."}],  # 添加 Please continue.
                        signal,
                        prompt_id,
                        bounded_turns - 1,
                        initial_model
                    ):
                        yield event
                    return
            
        # 5. 递归决策（只在没有待执行工具且未中止时判断）
        if not turn.pending_tool_calls and signal and not signal.aborted:
            # 检查模型是否被切换（防止降级后的意外递归）
            current_model = self.config.get_model()
            if current_model != initial_model:
                return
                
            # AI自主判断下一步
            from .next_speaker import check_next_speaker
            next_speaker_check = await check_next_speaker(self.chat, self, signal)
            if next_speaker_check and next_speaker_check.get('next_speaker') == 'model':
                # 递归调用：添加"Please continue."并继续
                next_request = [{'text': 'Please continue.'}]
                async for event in self.send_message_stream(
                    next_request,
                    signal,
                    prompt_id,
                    bounded_turns - 1,
                    initial_model
                ):
                    yield event
        
    async def try_compress_chat(self, prompt_id: str, force: bool = False):
        """
        历史压缩 - 数据库Agent简化版本
        数据库Agent通常不需要历史压缩，返回None即可
        """
        # 数据库Agent特性：不需要复杂的历史压缩
        # 原因：
        # 1. 任务驱动的对话模式，不是长时间连续对话
        # 2. 数据库结构信息相对固定，不需要压缩
        # 3. 操作通常是短期任务，不太可能触发token限制
        return None
        
    async def generate_json(
        self,
        contents: List[Content],
        schema: Dict[str, Any],
        signal: AbortSignal,
        system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成JSON响应 - 用于next_speaker判断等结构化输出
        """
        from ..services.llm_factory import create_llm_service
        
        # 创建临时的LLM服务（根据配置自动选择）
        gemini_service = create_llm_service(self.config)
        
        # 调用服务生成JSON
        return await gemini_service.generate_json(
            contents,
            schema,
            signal,
            system_instruction
        )
