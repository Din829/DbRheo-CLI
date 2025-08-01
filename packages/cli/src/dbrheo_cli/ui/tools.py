"""
工具显示组件
显示工具执行状态、参数、结果等：
- ToolStatus: 工具状态指示器
- ToolResult: 工具结果展示
- ToolConfirmation: 确认对话框

对应Gemini CLI的ToolMessage和ToolConfirmationMessage。
"""

from typing import Dict, Any, Optional
import json
from .console import console
from ..i18n import _


def get_status_indicator(status: str) -> str:
    """获取状态指示器"""
    # 映射后端实际的状态值到显示文本
    status_map = {
        # 后端状态 -> i18n key
        'validating': 'status_pending',
        'scheduled': 'status_pending',
        'awaiting_approval': 'status_confirm',
        'executing': 'status_running',
        'success': 'status_success',
        'error': 'status_error',
        'cancelled': 'status_cancelled',
        # 兼容前端可能的状态名
        'pending': 'status_pending',
        'approved': 'status_approved',
        'completed': 'status_success',
        'failed': 'status_error',
        'rejected': 'status_cancelled'
    }
    return _(status_map.get(status, 'status_unknown'))

# 风险级别颜色
RISK_COLORS = {
    'low': 'green',
    'medium': 'yellow',
    'high': 'red'
}


def show_tool_status(tool_name: str, status: str):
    """显示工具状态"""
    indicator = get_status_indicator(status)
    
    # 根据状态选择颜色
    if status in ['success', 'completed', 'approved']:
        color = 'success'
    elif status in ['error', 'failed', 'rejected', 'cancelled']:
        color = 'error'
    elif status in ['executing']:
        color = 'info'
    elif status in ['awaiting_approval']:
        color = 'warning'
    elif status in ['validating', 'scheduled', 'pending']:
        color = 'dim'
    else:
        color = 'dim'
    
    console.print(f"[{color}]{indicator} {tool_name}[/{color}]")


def show_tool_result(tool_name: str, result: Any):
    """显示工具执行结果"""
    console.print(f"\n[info]→ [{tool_name}] {_('tool_result')}:[/info]")
    
    # 根据结果类型进行不同的显示
    if isinstance(result, dict):
        # JSON格式化显示
        try:
            result_str = json.dumps(result, indent=2, ensure_ascii=False)
            console.print(result_str)
        except:
            console.print(str(result))
    elif isinstance(result, list):
        # 列表显示
        for item in result[:10]:  # 最多显示10项
            console.print(f"  • {item}")
        if len(result) > 10:
            console.print(f"  {_('more_items', count=len(result) - 10)}")
    else:
        # 普通文本
        console.print(str(result))


def show_confirmation_prompt(tool_name: str, args: Dict[str, Any], 
                           risk_level: str = 'low', 
                           risk_description: str = ''):
    """显示工具确认提示"""
    from rich.panel import Panel
    from rich.text import Text
    from rich.columns import Columns
    
    console.print()
    
    # 构建确认内容
    content_lines = []
    
    # 添加风险级别
    risk_color = RISK_COLORS.get(risk_level, 'yellow')
    content_lines.append(f"{_('risk_level')}: [{risk_color}]{risk_level.upper()}[/{risk_color}]")
    
    # 添加风险描述
    if risk_description:
        content_lines.append(f"{_('risk_description')}: {risk_description}")
    
    # 添加参数
    if args:
        content_lines.append(f"\n{_('parameters')}:")
        for key, value in args.items():
            value_str = str(value)
            
            # 对于代码相关的参数，使用语法高亮而不是截断
            if key.lower() in ['code', 'sql', 'query', 'script', 'command']:
                content_lines.append(f"  • {key}:")
                
                # 检测语言类型
                if key.lower() in ['sql', 'query']:
                    lang = 'sql'
                elif key.lower() == 'code':
                    lang = 'python'  # 默认Python
                elif key.lower() in ['script', 'command']:
                    lang = 'bash'
                else:
                    lang = 'text'
                
                # 使用语法高亮显示代码
                from rich.syntax import Syntax
                syntax = Syntax(value_str, lang, theme="monokai", line_numbers=False, word_wrap=True)
                # 将语法高亮对象转为字符串添加到内容中
                import io
                from rich.console import Console as TempConsole
                buffer = io.StringIO()
                temp_console = TempConsole(file=buffer, force_terminal=True)
                temp_console.print(syntax)
                content_lines.append(buffer.getvalue().rstrip())
            else:
                # 其他参数可以截断
                if len(value_str) > 200:
                    value_str = value_str[:197] + "..."
                content_lines.append(f"  • {key}: {value_str}")
    
    # 创建主内容面板
    main_content = "\n".join(content_lines)
    
    # 根据风险级别选择边框颜色
    border_color = RISK_COLORS.get(risk_level, 'yellow')
    
    # 创建并显示主面板
    main_panel = Panel(
        main_content,
        title=f"[bold]{_('tool_confirm_title', tool_name=tool_name)}[/bold]",
        border_style=border_color,
        padding=(1, 2)
    )
    console.print(main_panel)
    
    # 显示操作选项（带框）
    options_content = [
        f"[green]1[/green] / confirm - {_('confirm_execute')}",
        f"[red]2[/red] / cancel  - {_('cancel_execute')}",
        f"confirm all    - {_('confirm_all_tools')}"
    ]
    
    options_panel = Panel(
        "\n".join(options_content),
        title=f"[bold]{_('please_input')}[/bold]",
        subtitle=f"[dim]{_('input_halfwidth_hint')}[/dim]",
        border_style="cyan",
        padding=(0, 2)
    )
    console.print(options_panel)
    console.print()


def show_tool_error(tool_name: str, error: str):
    """显示工具错误"""
    console.print(f"[error]✗ [{tool_name}] {_('tool_failed', error=error)}[/error]")