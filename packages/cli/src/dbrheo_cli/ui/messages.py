"""
消息显示组件
定义各种消息类型的显示方式：
- UserMessage: 用户输入消息
- AgentMessage: AI响应消息
- SystemMessage: 系统消息
- ErrorMessage: 错误消息

对应Gemini CLI的各种Message组件。
"""

from typing import Optional
from .console import console
from ..i18n import _


# 消息前缀定义（便于后续自定义）
MESSAGE_PREFIXES = {
    'user': '> ',
    'agent': '',
    'system': '# ',
    'error': '✗ ',
    'tool': '  → '
}


def show_user_message(message: str):
    """显示用户消息"""
    prefix = MESSAGE_PREFIXES['user']
    console.print(f"\n[bold]{prefix}{message}[/bold]")
    console.print()  # 添加空行


def show_agent_message(message: str, end: str = '\n'):
    """显示AI响应消息"""
    # Agent消息无前缀，直接显示
    console.print(message, end=end)


def show_system_message(message: str):
    """显示系统消息"""
    prefix = MESSAGE_PREFIXES['system']
    console.print(f"[dim]{prefix}{message}[/dim]")


def show_tool_call(tool_name: str):
    """显示工具调用提示"""
    console.print(f"\n[cyan][{_('tool_executing', tool_name=tool_name)}][/cyan]", end='')


def show_error_message(message: str):
    """显示错误消息"""
    prefix = MESSAGE_PREFIXES['error']
    console.print(f"[error]{prefix}{message}[/error]")


def show_tool_message(tool_name: str, message: str):
    """显示工具消息"""
    prefix = MESSAGE_PREFIXES['tool']
    console.print(f"[info]{prefix}[{tool_name}] {message}[/info]")