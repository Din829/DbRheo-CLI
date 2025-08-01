"""
工具处理器
处理工具调用相关的事件，包括状态更新、确认流程等。
对应Gemini CLI的useReactToolScheduler。
"""

from typing import Dict, List, Any, Optional
from dbrheo.utils.debug_logger import DebugLogger, log_info
from dbrheo.types.core_types import AbortSignal

from ..ui.console import console
from ..ui.tools import show_tool_status, show_confirmation_prompt
from ..i18n import _
from ..constants import CONFIRMATION_WORDS
from ..app.config import CLIConfig


class ToolHandler:
    """
    工具调用处理器
    - 监听工具状态更新
    - 管理确认流程
    - 处理工具结果
    """
    
    def __init__(self, scheduler, config: CLIConfig):
        self.scheduler = scheduler
        self.config = config
        self.pending_confirmations = {}  # call_id -> tool_info
        
    def on_tools_update(self, tool_calls: List[Any]):
        """工具状态更新回调"""
        # 添加调试日志
        if DebugLogger.should_log("DEBUG"):
            log_info("ToolHandler", f"on_tools_update called with {len(tool_calls)} tools")
            
        for call in tool_calls:
            # 工具调用是对象，不是字典
            call_id = getattr(call.request, 'call_id', '') if hasattr(call, 'request') else ''
            status = getattr(call, 'status', '')
            name = getattr(call.request, 'name', 'unknown') if hasattr(call, 'request') else 'unknown'
            
            # 调试日志：显示实际的状态值
            if DebugLogger.should_log("DEBUG"):
                log_info("ToolHandler", f"Tool {name} (id: {call_id}) status: {status}")
            
            # 显示工具状态
            if self.config.show_tool_details:
                show_tool_status(name, status)
            
            # 在scheduled状态时显示工具参数（如果不需要确认）
            if status == 'scheduled' and hasattr(call, 'request') and hasattr(call.request, 'args'):
                args = getattr(call.request, 'args', {})
                # 只显示代码相关的参数
                for key, value in args.items():
                    if key.lower() in ['code', 'sql', 'query', 'script', 'command']:
                        console.print(f"\n[dim]{_('executing_code', param_key=key)}[/dim]")
                        # 使用语法高亮显示
                        from rich.syntax import Syntax
                        lang_map = {'sql': 'sql', 'query': 'sql', 'code': 'python', 'script': 'bash', 'command': 'bash'}
                        lang = lang_map.get(key.lower(), 'text')
                        syntax = Syntax(str(value), lang, theme="monokai", line_numbers=False, word_wrap=True)
                        console.print(syntax)
                        console.print()
            
            # 如果是等待确认状态，记录并显示确认提示
            if status == 'awaiting_approval' and call_id not in self.pending_confirmations:
                self.pending_confirmations[call_id] = call
                self._show_confirmation_for_tool(call)
            
            # 处理已完成的工具
            elif status in ['success', 'error', 'cancelled']:
                # 如果工具还在待确认列表中，移除它
                if call_id in self.pending_confirmations:
                    del self.pending_confirmations[call_id]
                
                # 显示工具执行结果（无论是否在待确认列表中）
                if status == 'success':
                    # 工具成功完成
                    if DebugLogger.should_log("INFO"):
                        log_info("ToolHandler", f"Tool {name} completed successfully")
                    # 显示成功消息
                    console.print(f"[green]{_('tool_success', name=name)}[/green]")
                    
                    # 显示工具执行结果（如果有的话）
                    if hasattr(call, 'response') and call.response:
                        result_display = getattr(call.response, 'result_display', None)
                        if result_display:
                            self._display_tool_result(name, result_display)
                elif status == 'error':
                    # 工具执行失败 - 错误信息在response.error中
                    error_msg = 'Unknown error'
                    if hasattr(call, 'response') and call.response:
                        if hasattr(call.response, 'error') and call.response.error:
                            error_msg = str(call.response.error)
                        elif hasattr(call.response, 'response_parts') and call.response.response_parts:
                            # 尝试从functionResponse中提取错误
                            response_parts = call.response.response_parts
                            if isinstance(response_parts, dict) and 'functionResponse' in response_parts:
                                func_resp = response_parts['functionResponse']
                                if 'response' in func_resp and 'error' in func_resp['response']:
                                    error_msg = func_resp['response']['error']
                    console.print(f"[red]{_('tool_failed_with_error', name=name, error=error_msg)}[/red]")
                elif status == 'cancelled':
                    # 工具被取消
                    console.print(f"[yellow]{_('tool_cancelled', name=name)}[/yellow]")
    
    def _show_confirmation_for_tool(self, tool_call: Any):
        """显示单个工具的确认提示"""
        # 从对象中获取属性
        name = getattr(tool_call.request, 'name', 'unknown') if hasattr(tool_call, 'request') else 'unknown'
        args = getattr(tool_call.request, 'args', {}) if hasattr(tool_call, 'request') else {}
        
        # 获取确认信息
        confirmation_details = getattr(tool_call, 'confirmation_details', None)
        if confirmation_details:
            risk_level = getattr(confirmation_details, 'risk_level', 'low')
            risk_description = getattr(confirmation_details, 'description', '')
        else:
            risk_level = 'low'
            risk_description = ''
        
        # 显示确认提示
        show_confirmation_prompt(name, args, risk_level, risk_description)
    
    def has_pending_confirmations(self) -> bool:
        """是否有待确认的工具"""
        return len(self.pending_confirmations) > 0
    
    async def handle_confirmation_input(self, user_input: str, signal: AbortSignal) -> bool:
        """
        处理用户确认输入
        返回True表示已处理确认，False表示不是确认命令
        """
        # 处理全角数字转换（日语输入法）
        fullwidth_to_halfwidth = str.maketrans('１２３４５６７８９０', '1234567890')
        normalized_input = user_input.translate(fullwidth_to_halfwidth)
        
        input_lower = normalized_input.strip().lower()
        
        # 检查是否是确认命令
        if input_lower in CONFIRMATION_WORDS['CONFIRM']:
            # 确认执行
            await self._confirm_all_tools('proceed_once', signal)
            return True
        elif input_lower in CONFIRMATION_WORDS['CANCEL']:
            # 取消执行
            await self._confirm_all_tools('cancel', signal)
            return True
        elif input_lower in CONFIRMATION_WORDS['CONFIRM_ALL']:
            # 确认所有
            await self._confirm_all_tools('proceed_always', signal)
            return True
        
        # 不是确认命令
        return False
    
    async def _confirm_all_tools(self, outcome: str, signal: AbortSignal):
        """确认或拒绝所有待确认的工具"""
        if not self.pending_confirmations:
            return
        
        # 显示确认结果
        if outcome == 'proceed_once':
            console.print(f"[green]{_('tool_confirmed')}[/green]")
        elif outcome == 'cancel':
            console.print(f"[red]{_('tool_rejected')}[/red]")
        elif outcome == 'proceed_always':
            console.print(f"[green]{_('tool_confirmed_all')}[/green]")
        
        # 处理每个待确认的工具
        for call_id, tool_call in list(self.pending_confirmations.items()):
            try:
                await self.scheduler.handle_confirmation_response(
                    call_id, outcome, signal
                )
                if DebugLogger.should_log("DEBUG"):
                    log_info("ToolHandler", f"Confirmed tool {call_id} with outcome: {outcome}")
            except Exception as e:
                console.print(f"[error]{_('tool_error', error=e)}[/error]")
        
        # 清空待确认列表
        self.pending_confirmations.clear()
    
    def _display_tool_result(self, tool_name: str, result_display: str):
        """显示工具执行结果"""
        if not result_display or not result_display.strip():
            return
        
        # 检测是否包含Markdown表格（通用检测，不限于SQL）
        if self._contains_markdown_table(result_display):
            self._display_table_result(result_display)
        else:
            # 非表格结果，直接显示
            console.print(f"\n[bold]{_('execution_result')}[/bold]")
            console.print(result_display)
    
    def _contains_markdown_table(self, text: str) -> bool:
        """检测文本是否包含Markdown表格"""
        lines = text.strip().split('\n')
        for i in range(len(lines) - 1):
            if '|' in lines[i] and i + 1 < len(lines) and '---' in lines[i + 1] and '|' in lines[i + 1]:
                return True
        return False
    
    def _display_table_result(self, result_display: str):
        """专业地显示包含表格的结果"""
        console.print(f"\n[bold cyan]{_('execution_result')}[/bold cyan]")
        
        # 先提取首行信息（如："查询返回 X 行数据（执行时间: X.XX秒）"）
        lines = result_display.strip().split('\n')
        header_info = ""
        table_start = 0
        
        # 查找表格开始的位置
        for i, line in enumerate(lines):
            if '|' in line and i + 1 < len(lines) and '---' in lines[i + 1]:
                header_info = '\n'.join(lines[:i]).strip()
                table_start = i
                break
        
        # 显示头部信息
        if header_info:
            console.print(f"[dim]{header_info}[/dim]\n")
        
        # 检查是否是Markdown表格
        if table_start < len(lines) - 2 and '|' in lines[table_start] and '|' in lines[table_start + 1] and '---' in lines[table_start + 1]:
            # 解析Markdown表格
            try:
                # 提取表头
                headers = [h.strip() for h in lines[table_start].split('|') if h.strip()]
                
                # 提取数据行
                data_rows = []
                footer_info = ""
                for i in range(table_start + 2, len(lines)):  # 跳过表头和分隔线
                    line = lines[i]
                    if '|' in line:
                        row = [cell.strip() for cell in line.split('|') if cell.strip()]
                        if len(row) == len(headers):
                            data_rows.append(row)
                    else:
                        # 非表格行，可能是脚注信息
                        footer_info = '\n'.join(lines[i:]).strip()
                        break
                
                # 使用Rich Table显示
                from rich.table import Table
                
                # 创建表格
                table = Table(show_header=True, header_style="bold magenta")
                
                # 添加列
                for header in headers:
                    table.add_column(header)
                
                # 添加行（可配置最大显示行数）
                max_rows = getattr(self.config, 'max_table_rows', 20)
                for i, row in enumerate(data_rows[:max_rows]):
                    table.add_row(*row)
                
                # 显示表格
                console.print(table)
                
                # 如果有更多行，显示提示
                if len(data_rows) > max_rows:
                    console.print(f"\n[dim]{_('rows_truncated', count=len(data_rows) - max_rows)}[/dim]")
                
                # 显示脚注信息（如果有）
                if footer_info:
                    console.print(f"\n[dim]{footer_info}[/dim]")
                elif data_rows:  # 只有在有数据时才显示总行数
                    console.print(f"\n[dim]{_('total_rows', count=len(data_rows))}[/dim]")
                
            except Exception as e:
                # 如果解析失败，直接显示原始内容
                if DebugLogger.should_log("DEBUG"):
                    log_info("ToolHandler", f"Failed to parse table: {e}")
                console.print(result_display)
        else:
            # 不是表格格式，直接显示
            console.print(result_display)
    
    def cleanup(self):
        """清理资源"""
        self.pending_confirmations.clear()