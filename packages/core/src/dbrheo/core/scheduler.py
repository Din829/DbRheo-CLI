"""
DatabaseToolScheduler - 工具调度器
管理工具从验证到执行的完整生命周期，完全对齐Gemini CLI设计
"""

import asyncio
import time
from typing import List, Optional, Dict, Any, Callable
from ..types.core_types import AbortSignal
from ..types.tool_types import (
    ToolCallRequestInfo, ToolCall, ToolCallResponseInfo,
    ValidatingToolCall, ScheduledToolCall, ExecutingToolCall,
    SuccessfulToolCall, ErroredToolCall, CancelledToolCall, WaitingToolCall
)
from ..config.base import DatabaseConfig
from ..utils.debug_logger import DebugLogger, log_info

# 导入实时日志系统（如果启用）
import os
if os.getenv('DBRHEO_ENABLE_REALTIME_LOG') == 'true':
    try:
        from ..utils.realtime_logger import log_tool_call, log_tool_result, log_system
        REALTIME_LOG_ENABLED = True
    except ImportError:
        REALTIME_LOG_ENABLED = False
else:
    REALTIME_LOG_ENABLED = False


class DatabaseToolScheduler:
    """
    数据库工具调度器 - 完全对齐Gemini CLI设计
    - 工具状态机管理（ValidatingToolCall等7种状态）
    - 并发工具执行控制
    - 确认流程协调
    - UI回调接口
    """
    
    def __init__(self, config: DatabaseConfig, **callbacks):
        self.config = config
        self.tool_calls: List[ToolCall] = []
        self.tool_registry = None  # 将在初始化时设置
        
        # UI回调接口
        self.output_update_handler = callbacks.get('output_update_handler')
        self.on_all_tools_complete = callbacks.get('on_all_tools_complete')
        self.on_tool_calls_update = callbacks.get('on_tool_calls_update')
        
    async def schedule(self, requests: List[ToolCallRequestInfo], signal: AbortSignal):
        """
        调度工具执行 - 与Gemini CLI完全一致
        处理工具验证、确认、执行的完整流程
        """
        if self._is_running():
            raise Exception("Cannot schedule new tool calls while others are running")
            
        # 1. 批量创建工具调用
        # 使用已经初始化的 tool_registry（最小侵入性）
        tool_registry = self.tool_registry
        if not tool_registry:
            # 兼容性：如果没有设置 tool_registry，创建新的
            from ..tools.registry import DatabaseToolRegistry
            tool_registry = DatabaseToolRegistry(self.config)
        
        new_tool_calls = []
        for request in requests:
            tool = tool_registry.get_tool(request.name)
            if not tool:
                # 创建错误状态的工具调用
                error_function_response = {
                    'functionResponse': {
                        'id': request.call_id,
                        'name': request.name,
                        'response': {'error': f"Tool '{request.name}' not found in registry"}
                    }
                }
                
                error_call = ErroredToolCall(
                    request=request,
                    response=ToolCallResponseInfo(
                        call_id=request.call_id,
                        response_parts=error_function_response,
                        error=Exception(f"Tool '{request.name}' not found in registry")
                    ),
                    status='error',
                    duration_ms=0
                )
                new_tool_calls.append(error_call)
                continue
                
            # 创建验证状态的工具调用
            validating_call = ValidatingToolCall(
                request=request,
                tool=tool,
                status='validating',
                start_time=time.time()
            )
            new_tool_calls.append(validating_call)
            
        self.tool_calls.extend(new_tool_calls)
        self._notify_tool_calls_update()
        
        # 2. 验证和确认流程
        for tool_call in new_tool_calls:
            if tool_call.status != 'validating':
                continue
                
            try:
                # 检查是否需要确认
                confirmation_details = await tool_call.tool.should_confirm_execute(
                    tool_call.request.args, signal
                )
                
                if confirmation_details:
                    # 需要确认，设置为等待状态
                    self._set_status(tool_call.request.call_id, 'awaiting_approval', confirmation_details)
                else:
                    # 不需要确认，设置为已调度状态
                    self._set_status(tool_call.request.call_id, 'scheduled')
                    
            except Exception as e:
                # 验证失败，设置为错误状态
                error_function_response = {
                    'functionResponse': {
                        'id': tool_call.request.call_id,
                        'name': tool_call.request.name,
                        'response': {'error': f"Validation failed: {str(e)}"}
                    }
                }
                
                error_response = ToolCallResponseInfo(
                    call_id=tool_call.request.call_id,
                    response_parts=error_function_response,
                    error=e
                )
                self._set_status(tool_call.request.call_id, 'error', error_response)
                
        # 3. 执行调度
        await self._attempt_execution_of_scheduled_calls(signal)
        
    async def _attempt_execution_of_scheduled_calls(self, signal: AbortSignal):
        """
        尝试执行所有已调度的工具调用
        """
        DebugLogger.log_scheduler_event("execution_start", len(self.tool_calls))
        log_info("Scheduler", f"_attempt_execution_of_scheduled_calls: {len(self.tool_calls)} tools total")
        
        # 调试：打印所有工具的状态
        for idx, tc in enumerate(self.tool_calls):
            log_info("Scheduler", f"  Tool[{idx}] {tc.request.name} - {tc.request.call_id} - status: {tc.status}")
        
        scheduled_count = sum(1 for tc in self.tool_calls if tc.status == 'scheduled')
        log_info("Scheduler", f"Found {scheduled_count} scheduled tools to execute")
        
        for tool_call in self.tool_calls:
            if tool_call.status == 'scheduled':
                # 工具执行开始日志在VERBOSE模式显示
                if DebugLogger.get_rules()["show_tool_calls"]:
                    log_info("Scheduler", f"执行工具: {tool_call.request.name}")
                
                # 实时日志记录工具调用
                if REALTIME_LOG_ENABLED:
                    log_tool_call(tool_call.request.name, tool_call.request.args, tool_call.request.call_id)
                
                try:
                    # 设置为执行状态
                    self._set_status(tool_call.request.call_id, 'executing')
                    
                    # 执行工具
                    result = await tool_call.tool.execute(
                        tool_call.request.args,
                        signal,
                        self._create_output_updater(tool_call.request.call_id)
                    )
                    
                    # 使用统一的结果处理，确保Agent收到完整信息
                    from ..utils.function_response import convert_to_function_response
                    log_info("Scheduler", f"🔍 DEBUG: 即将调用convert_to_function_response")
                    log_info("Scheduler", f"🔍 DEBUG: tool_name={tool_call.request.name}")
                    log_info("Scheduler", f"🔍 DEBUG: call_id={tool_call.request.call_id}")
                    log_info("Scheduler", f"🔍 DEBUG: result类型: {type(result)}")
                    log_info("Scheduler", f"🔍 DEBUG: result内容概览: {repr(str(result)[:200])}")
                    
                    function_response = convert_to_function_response(
                        tool_call.request.name,
                        tool_call.request.call_id,
                        result  # 传递完整的ToolResult对象
                    )
                    log_info("Scheduler", f"🔍 DEBUG: convert_to_function_response返回: {repr(function_response)}")
                    
                    # 检查执行结果是否包含错误
                    if result.error:
                        # 有错误但仍然传递完整的工具结果
                        error_response = ToolCallResponseInfo(
                            call_id=tool_call.request.call_id,
                            response_parts=function_response,
                            result_display=result.return_display,
                            error=Exception(result.error)
                        )
                        self._set_status(tool_call.request.call_id, 'error', error_response)
                        
                        # 实时日志记录工具失败
                        if REALTIME_LOG_ENABLED:
                            log_tool_result(tool_call.request.name, result.error, False, tool_call.request.call_id)
                    else:
                        # 创建成功响应
                        response = ToolCallResponseInfo(
                            call_id=tool_call.request.call_id,
                            response_parts=function_response,  # 使用转换后的格式
                            result_display=result.return_display
                        )
                        
                        DebugLogger.log_scheduler_event("tool_complete", {
                            "name": tool_call.request.name,
                            "response": function_response
                        })
                        
                        self._set_status(tool_call.request.call_id, 'success', response)
                        
                        # 实时日志记录工具成功
                        if REALTIME_LOG_ENABLED:
                            log_tool_result(tool_call.request.name, result.summary or result.llm_content, True, tool_call.request.call_id)
                    
                except Exception as e:
                    # 执行失败，设置为错误状态
                    # 创建错误的functionResponse
                    error_function_response = {
                        'functionResponse': {
                            'id': tool_call.request.call_id,
                            'name': tool_call.request.name,
                            'response': {'error': str(e)}
                        }
                    }
                    
                    error_response = ToolCallResponseInfo(
                        call_id=tool_call.request.call_id,
                        response_parts=error_function_response,
                        error=e
                    )
                    self._set_status(tool_call.request.call_id, 'error', error_response)
                    
                    # 实时日志记录工具失败
                    if REALTIME_LOG_ENABLED:
                        log_tool_result(tool_call.request.name, str(e), False, tool_call.request.call_id)
                    
        # 移除这里的检查，让 _set_status 中的检查负责
        # 这里调用太早了，工具可能还在执行中
                
    def _create_output_updater(self, call_id: str):
        """
        创建输出更新器，用于流式输出
        """
        def update_output(output: str):
            if self.output_update_handler:
                self.output_update_handler(call_id, output)
        return update_output
        
    def _is_running(self) -> bool:
        """检查是否有工具正在运行"""
        return any(call.status in ['executing', 'awaiting_approval'] 
                  for call in self.tool_calls)
                  
    def _notify_tool_calls_update(self):
        """通知UI工具调用状态更新"""
        from ..utils.debug_logger import log_info
        log_info("Scheduler", f"🔄 _notify_tool_calls_update - Scheduler ID: {id(self)}, tool_calls ID: {id(self.tool_calls)}, count: {len(self.tool_calls)}")
        if self.on_tool_calls_update:
            self.on_tool_calls_update(self.tool_calls)
            
    async def handle_confirmation_response(
        self,
        call_id: str,
        outcome: str,  # 使用字符串避免导入循环
        signal: AbortSignal,
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        处理用户对工具确认的响应
        参考 Gemini CLI 的 handleConfirmationResponse 实现
        
        Args:
            call_id: 工具调用ID
            outcome: 确认结果 ('proceed_once', 'cancel', 'modify_with_editor'等)
            signal: 中止信号
            payload: 额外的数据（如修改后的SQL）
        """
        # 找到等待确认的工具调用
        from ..utils.debug_logger import log_info
        log_info("Scheduler", f"🔍 handle_confirmation_response called for {call_id} with outcome: {outcome}")
        log_info("Scheduler", f"🔍 Scheduler instance ID: {id(self)}")
        log_info("Scheduler", f"🔍 Current tool_calls count: {len(self.tool_calls)}")
        log_info("Scheduler", f"🔍 tool_calls list ID: {id(self.tool_calls)}")
        
        for idx, call in enumerate(self.tool_calls):
            log_info("Scheduler", f"  Tool[{idx}]: {call.request.name} - {call.request.call_id} - status: {call.status}")
        
        tool_call = None
        for call in self.tool_calls:
            if call.request.call_id == call_id and call.status == 'awaiting_approval':
                tool_call = call
                break
                
        if not tool_call:
            log_info("Scheduler", f"Tool call {call_id} not found or not awaiting approval in {len(self.tool_calls)} tools")
            return
            
        log_info("Scheduler", f"Found tool {tool_call.request.name} for confirmation")
            
        # 根据用户响应处理
        if outcome == 'cancel' or signal.aborted:
            # 用户取消或信号中止
            cancel_response = ToolCallResponseInfo(
                call_id=call_id,
                response_parts={'text': 'User cancelled the operation'},
                result_display='操作已被用户取消'
            )
            self._set_status(call_id, 'cancelled', cancel_response)
            
        elif outcome == 'modify_with_editor' and payload:
            # 用户修改了SQL（或其他参数）
            # 更新工具调用的参数
            if hasattr(tool_call, 'request'):
                # 创建新的请求，保留原有信息但更新参数
                tool_call.request.args.update(payload)
            # 设置为scheduled状态，准备执行
            self._set_status(call_id, 'scheduled')
            
        elif outcome in ['proceed_once', 'proceed_always', 'proceed_always_server', 'proceed_always_tool']:
            # 用户批准执行
            log_info("Scheduler", f"Setting tool {call_id} to scheduled status")
            self._set_status(call_id, 'scheduled')
            
            # TODO: 处理"总是允许"的情况
            # proceed_always_server: 对该数据库服务器的所有操作
            # proceed_always_tool: 对该工具的所有操作
            # 这需要在配置或上下文中记录用户偏好
            
        # 尝试执行所有已调度的工具
        log_info("Scheduler", f"Attempting to execute scheduled tools after confirmation")
        await self._attempt_execution_of_scheduled_calls(signal)
    
    async def _wait_for_completion(self):
        """
        等待所有工具执行完成
        使用轮询机制，避免死锁
        """
        max_wait = 30  # 最多等待30秒
        poll_interval = 0.1  # 每100ms检查一次
        waited = 0
        
        while waited < max_wait:
            # 检查是否所有工具都完成了
            all_complete = all(
                call.status in ['success', 'error', 'cancelled']
                for call in self.tool_calls
            )
            
            if all_complete or len(self.tool_calls) == 0:
                # 所有工具已完成或没有工具
                return
                
            # 等待一小段时间
            await asyncio.sleep(poll_interval)
            waited += poll_interval
            
        # 超时警告
        if self.tool_calls:
            from ..utils.debug_logger import log_info
            log_info("Scheduler", f"Warning: Waited {max_wait}s but {len(self.tool_calls)} tools still not complete")
    
    def _check_and_notify_completion(self):
        """
        检查所有工具调用是否完成，如果完成则清理状态并通知
        参考 Gemini CLI 的 checkAndNotifyCompletion 实现
        """
        from ..utils.debug_logger import log_info
        log_info("Scheduler", f"_check_and_notify_completion called with {len(self.tool_calls)} tools")
        
        if len(self.tool_calls) == 0:
            log_info("Scheduler", "No tools to check")
            return
            
        # 打印所有工具的状态
        for idx, call in enumerate(self.tool_calls):
            log_info("Scheduler", f"  Tool[{idx}]: {call.request.name} - status: {call.status}")
        
        # 检查是否所有调用都处于终止状态
        all_calls_terminal = all(
            call.status in ['success', 'error', 'cancelled']
            for call in self.tool_calls
        )
        
        # 检查是否有工具正在等待确认
        has_awaiting_approval = any(
            call.status == 'awaiting_approval'
            for call in self.tool_calls
        )
        
        # 添加额外的检查：是否有执行中的工具
        has_executing = any(
            call.status == 'executing'
            for call in self.tool_calls
        )
        
        log_info("Scheduler", f"all_calls_terminal: {all_calls_terminal}, has_awaiting_approval: {has_awaiting_approval}, has_executing: {has_executing}")
        
        # 只有当所有工具都完成且没有等待确认或执行中的工具时才清理
        if len(self.tool_calls) > 0 and all_calls_terminal and not has_awaiting_approval and not has_executing:
            # 保存完成的调用列表
            completed_calls = list(self.tool_calls)
            
            # 清空工具调用列表 - 这是关键！
            import traceback
            log_info("Scheduler", "🚨 CLEARING tool_calls - conditions met:")
            log_info("Scheduler", f"  len(tool_calls): {len(self.tool_calls)}")
            log_info("Scheduler", f"  all_calls_terminal: {all_calls_terminal}")
            log_info("Scheduler", f"  has_awaiting_approval: {has_awaiting_approval}")
            log_info("Scheduler", f"  has_executing: {has_executing}")
            log_info("Scheduler", "🚨 CLEARING tool_calls - stack trace:")
            for line in traceback.format_stack():
                log_info("Scheduler", f"  {line.strip()}")
            self.tool_calls = []
        else:
            # 添加不清理的原因日志
            log_info("Scheduler", "⭕ NOT clearing tool_calls - conditions:")
            log_info("Scheduler", f"  len(tool_calls): {len(self.tool_calls)}")
            log_info("Scheduler", f"  all_calls_terminal: {all_calls_terminal}")
            log_info("Scheduler", f"  has_awaiting_approval: {has_awaiting_approval}")
            log_info("Scheduler", f"  has_executing: {has_executing}")
            log_info("Scheduler", f"  condition result: {len(self.tool_calls) > 0 and all_calls_terminal and not has_awaiting_approval and not has_executing}")
            
        # 继续原有逻辑（只有清理时才执行）
        if len(self.tool_calls) == 0 and 'completed_calls' in locals():
            # 记录日志  
            from ..utils.debug_logger import DebugLogger, log_info
            log_info("Scheduler", f"All {len(completed_calls)} tool calls completed, clearing state")
            
            # 在VERBOSE模式下显示清理前的工具响应
            if DebugLogger.should_log("DEBUG") and DebugLogger.get_rules()["show_raw_chunks"]:
                for call in completed_calls:
                    if hasattr(call, 'response') and call.response:
                        log_info("Scheduler", f"Completed tool {call.request.name} response: {call.response.response_parts}")
            
            # 执行完成回调
            if self.on_all_tools_complete:
                self.on_all_tools_complete(completed_calls)
                
            # 通知状态更新
            self._notify_tool_calls_update()
            
    def _set_status(self, call_id: str, status: str, details: Any = None):
        """
        更新工具调用状态 - 实现状态机转换
        """
        import time
        
        log_info("Scheduler", f"_set_status: {call_id} -> {status}")
        
        for i, tool_call in enumerate(self.tool_calls):
            if tool_call.request.call_id != call_id:
                continue
                
            log_info("Scheduler", f"Found tool at index {i}: {tool_call.request.name} - current status: {tool_call.status}")
                
            # 不允许从终止状态转换
            if tool_call.status in ['success', 'error', 'cancelled']:
                continue
                
            # 获取已有属性
            existing_start_time = getattr(tool_call, 'start_time', None)
            existing_tool = getattr(tool_call, 'tool', None)
            
            # 根据新状态创建新对象
            if status == 'scheduled':
                new_call = ScheduledToolCall(
                    request=tool_call.request,
                    tool=existing_tool,
                    status='scheduled',
                    start_time=existing_start_time
                )
            elif status == 'executing':
                new_call = ExecutingToolCall(
                    request=tool_call.request,
                    tool=existing_tool,
                    status='executing',
                    start_time=existing_start_time
                )
            elif status == 'awaiting_approval':
                new_call = WaitingToolCall(
                    request=tool_call.request,
                    tool=existing_tool,
                    confirmation_details=details,
                    status='awaiting_approval',
                    start_time=existing_start_time
                )
            elif status == 'success':
                duration = time.time() - existing_start_time if existing_start_time else 0
                new_call = SuccessfulToolCall(
                    request=tool_call.request,
                    tool=existing_tool,
                    response=details,
                    status='success',
                    duration_ms=duration * 1000
                )
            elif status == 'error':
                duration = time.time() - existing_start_time if existing_start_time else 0
                new_call = ErroredToolCall(
                    request=tool_call.request,
                    response=details,
                    status='error',
                    duration_ms=duration * 1000
                )
            elif status == 'cancelled':
                duration = time.time() - existing_start_time if existing_start_time else 0
                new_call = CancelledToolCall(
                    request=tool_call.request,
                    tool=existing_tool,
                    response=details,
                    status='cancelled',
                    duration_ms=duration * 1000
                )
            else:
                continue
                
            # 更新数组
            self.tool_calls[i] = new_call
            break
            
        self._notify_tool_calls_update()
        
        # 每次状态更新后检查是否所有工具都完成了
        # 这是Gemini CLI的关键机制，确保及时清理状态
        self._check_and_notify_completion()
