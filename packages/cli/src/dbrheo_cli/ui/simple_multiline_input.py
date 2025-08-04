"""
简单的多行输入实现
不使用 Rich Live，而是基于传统的控制台输入
支持更自然的多行编辑体验
"""

import os
import sys
import re
import select
import time
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ..app.config import CLIConfig
from ..i18n import _


class SimpleMultilineInput:
    """
    简单的多行输入处理器
    使用更自然的方式支持多行输入
    """
    
    def __init__(self, config: CLIConfig, console: Console):
        self.config = config
        self.console = console
        
        # 多行输入配置
        self.multiline_enabled = os.getenv('DBRHEO_MULTILINE_ENABLED', 'true').lower() == 'true'
        self.multiline_indicator = os.getenv('DBRHEO_MULTILINE_INDICATOR', '...')
        self.max_display_lines = int(os.getenv('DBRHEO_MAX_DISPLAY_LINES', '10'))
        
        # 多行模式配置
        self.multiline_end_mode = os.getenv('DBRHEO_MULTILINE_END_MODE', 'empty_line')
        self.auto_multiline = os.getenv('DBRHEO_AUTO_MULTILINE', 'true').lower() == 'true'
        
        # SQL关键字检测（用于自动多行）
        sql_keywords_env = os.getenv('DBRHEO_SQL_KEYWORDS', 'SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,DROP,WITH')
        self.sql_keywords = [kw.strip() for kw in sql_keywords_env.split(',')]
        
        # 多行触发标记
        triggers_env = os.getenv('DBRHEO_MULTILINE_TRIGGERS', 'triple_quote_double,triple_quote_single,backticks,angle_brackets')
        trigger_map = {
            'triple_quote_double': '"""',
            'triple_quote_single': "'''",
            'backticks': '```',
            'angle_brackets': '<<<'
        }
        trigger_names = [name.strip() for name in triggers_env.split(',')]
        self.multiline_triggers = [trigger_map.get(name, name) for name in trigger_names]
        
    def get_multiline_input(self, prompt: str = "> ") -> str:
        """
        获取多行输入 - 智能检测粘贴内容
        支持以下方式：
        1. 自动检测多行粘贴并包装为三引号块
        2. 使用三引号标记多行块
        3. SQL语句自动识别为多行
        4. 行尾加 \ 继续输入
        """
        if not self.multiline_enabled:
            prompt_style = os.getenv('DBRHEO_PROMPT_STYLE', '[bold cyan]{prompt}[/bold cyan]')
            return self.console.input(prompt_style.format(prompt=prompt))
        
        # 获取第一行输入
        prompt_style = os.getenv('DBRHEO_PROMPT_STYLE', '[bold cyan]{prompt}[/bold cyan]')
        
        # Windows平台提示（仅在启用剪贴板检测时显示）
        if (sys.platform.startswith('win') and not self._is_wsl() and 
            os.getenv('DBRHEO_CLIPBOARD_DETECTION', 'true').lower() == 'true' and
            os.getenv('DBRHEO_SHOW_CLIPBOARD_HINT', 'true').lower() == 'true'):
            hint_text = os.getenv('DBRHEO_CLIPBOARD_HINT_TEXT', _('clipboard_hint'))
            self.console.print(f"[dim]{hint_text}[/dim]")
        
        first_line = self.console.input(prompt_style.format(prompt=prompt))
        
        # Windows平台特殊处理：空行或特定触发符时检查剪贴板
        if sys.platform.startswith('win') and not self._is_wsl():
            clipboard_trigger = os.getenv('DBRHEO_CLIPBOARD_TRIGGER', 'empty').lower()
            trigger_chars = os.getenv('DBRHEO_CLIPBOARD_TRIGGER_CHARS', '').split(',')
            
            should_check_clipboard = False
            
            if clipboard_trigger == 'empty' and first_line.strip() == '':
                # 空行触发
                should_check_clipboard = True
            elif clipboard_trigger == 'chars' and first_line.strip() in trigger_chars:
                # 特定字符触发
                should_check_clipboard = True
            elif clipboard_trigger == 'both' and (first_line.strip() == '' or first_line.strip() in trigger_chars):
                # 两者都可触发
                should_check_clipboard = True
            
            if should_check_clipboard:
                clipboard_content = self._get_clipboard_content()
                if clipboard_content and '\n' in clipboard_content:
                    # 获取配置：是否自动添加三引号
                    auto_wrap = os.getenv('DBRHEO_CLIPBOARD_AUTO_WRAP', 'true').lower() == 'true'
                    wrap_marker = os.getenv('DBRHEO_CLIPBOARD_WRAP_MARKER', "'''")
                    
                    clipboard_hint = os.getenv('DBRHEO_CLIPBOARD_HINT', '[dim]📋 检测到剪贴板中的多行内容[/dim]')
                    self.console.print(clipboard_hint)
                    
                    if auto_wrap and wrap_marker in self.multiline_triggers:
                        # 自动包装成三引号块
                        wrapped_hint = os.getenv('DBRHEO_WRAPPED_HINT', '[dim]自动使用 {marker} 包装内容[/dim]')
                        self.console.print(wrapped_hint.format(marker=wrap_marker))
                        
                        # 显示预览
                        show_preview = os.getenv('DBRHEO_SHOW_PASTE_PREVIEW', 'true').lower() == 'true'
                        if show_preview:
                            self.display_multiline_preview(clipboard_content)
                        
                        return clipboard_content
                    else:
                        # 不自动包装，按原有逻辑处理
                        lines = clipboard_content.split('\n')
                        return '\n'.join(lines)
        
        # 🚀 原有逻辑：自动检测多行粘贴（Linux/WSL）
        paste_lines = self._detect_multiline_paste()
        if paste_lines:
            paste_hint = os.getenv('DBRHEO_PASTE_HINT')
            if paste_hint:
                # 用户自定义了提示文本，使用用户的设置
                self.console.print(paste_hint)
            else:
                # 使用i18n的默认提示
                self.console.print(f'[dim]🔍 {_("multiline_detected")}[/dim]')
            
            all_lines = [first_line] + paste_lines
            content = '\n'.join(all_lines)
            
            # 显示预览（可配置）
            show_preview = os.getenv('DBRHEO_SHOW_PASTE_PREVIEW', 'true').lower() == 'true'
            if show_preview:
                self.display_multiline_preview(content)
            
            return content
        
        # 检查是否是多行触发标记
        if first_line.strip() in self.multiline_triggers:
            return self._block_multiline_input(first_line.strip())
        
        # 检查是否以反斜杠结尾（手动续行）
        if first_line.endswith('\\'):
            return self._manual_multiline_input([first_line[:-1]])
        
        # 自动检测SQL语句
        if self.auto_multiline and self._is_sql_start(first_line):
            sql_hint = os.getenv('DBRHEO_SQL_HINT')
            if sql_hint:
                self.console.print(sql_hint)
            else:
                self.console.print(f'[dim]{_("sql_detected_hint")}[/dim]')
            return self._manual_multiline_input([first_line], sql_mode=True)
        
        # 检查是否是未闭合的引号或括号
        if self.auto_multiline and self._has_unclosed_delimiter(first_line):
            unclosed_hint = os.getenv('DBRHEO_UNCLOSED_HINT')
            if unclosed_hint:
                self.console.print(unclosed_hint)
            else:
                self.console.print(f'[dim]{_("unclosed_delimiter_hint")}[/dim]')
            return self._manual_multiline_input([first_line], auto_mode=True)
        
        # 否则返回单行
        return first_line
    
    def _detect_multiline_paste(self) -> List[str]:
        """
        检测是否有多行粘贴内容
        使用多重策略提高稳定性
        """
        paste_enabled = os.getenv('DBRHEO_AUTO_PASTE_DETECTION', 'true').lower() == 'true'
        if not paste_enabled:
            return []
            
        paste_lines = []
        
        try:
            # 方法1：使用select检测（Unix/Linux/WSL）
            if hasattr(select, 'select'):
                # 多次短暂检测，提高准确性
                initial_timeout = 0.02  # 20ms初始检测
                continuous_timeout = 0.05  # 50ms连续检测
                
                # 第一次检测：用短超时检查是否有内容
                readable, _, _ = select.select([sys.stdin], [], [], initial_timeout)
                if not readable:
                    return []  # 没有即时内容，不是粘贴
                
                # 有内容，继续读取
                max_lines = int(os.getenv('DBRHEO_MAX_PASTE_LINES', '100'))  # 限制最大行数
                read_count = 0
                
                while read_count < max_lines:
                    readable, _, _ = select.select([sys.stdin], [], [], continuous_timeout)
                    if readable:
                        try:
                            line = sys.stdin.readline()
                            if line:
                                # 保留原始内容，只移除末尾的\n
                                line = line.rstrip('\n')
                                paste_lines.append(line)
                                read_count += 1
                            else:
                                break  # EOF
                        except:
                            break
                    else:
                        break  # 超时结束
                
                # 只有多于1行才认为是粘贴
                if len(paste_lines) < int(os.getenv('DBRHEO_MIN_PASTE_LINES', '2')):
                    paste_lines = []  # 单行不认为粘贴
            
            # 方法2：Windows下使用剪贴板检测
            elif sys.platform.startswith('win') and not self._is_wsl():
                # Windows原生环境下尝试剪贴板检测
                clipboard_enabled = os.getenv('DBRHEO_CLIPBOARD_DETECTION', 'true').lower() == 'true'
                if clipboard_enabled:
                    clipboard_content = self._get_clipboard_content()
                    if clipboard_content and '\n' in clipboard_content:
                        # 将剪贴板内容分割成行
                        paste_lines = clipboard_content.split('\n')
                        # 移除空的末尾行
                        while paste_lines and paste_lines[-1] == '':
                            paste_lines.pop()
                        
                        # 只有多于最小行数才认为是需要处理的多行内容
                        min_lines = int(os.getenv('DBRHEO_MIN_PASTE_LINES', '2'))
                        if len(paste_lines) < min_lines:
                            paste_lines = []
                    
        except Exception as e:
            # 如果检测失败，记录错误但不影响正常流程
            if os.getenv('DBRHEO_DEBUG_PASTE', 'false').lower() == 'true':
                # 只在调试模式下显示错误，且过滤掉常见的套接字错误
                if "10038" not in str(e):  # Windows套接字错误
                    self.console.print(f"[dim]{_('paste_detect_error', error=e)}[/dim]")
        
        return paste_lines
    
    def _get_clipboard_content(self) -> Optional[str]:
        """
        获取剪贴板内容（Windows平台）
        使用tkinter实现，无需额外依赖
        如果失败则返回None，不影响正常流程
        """
        # 功能开关：允许完全禁用剪贴板访问
        if os.getenv('DBRHEO_DISABLE_CLIPBOARD_ACCESS', 'false').lower() == 'true':
            return None
            
        try:
            # 配置项：选择剪贴板获取方法
            clipboard_method = os.getenv('DBRHEO_CLIPBOARD_METHOD', 'tkinter').lower()
            
            if clipboard_method == 'tkinter':
                try:
                    # 延迟导入，避免在不需要时加载
                    import tkinter as tk
                except ImportError:
                    # tkinter不可用（某些精简的Python安装可能没有）
                    if os.getenv('DBRHEO_DEBUG_PASTE', 'false').lower() == 'true':
                        self.console.print(f"[dim]{_('tkinter_unavailable')}[/dim]")
                    return None
                
                # 创建隐藏的窗口
                try:
                    root = tk.Tk()
                    root.withdraw()  # 隐藏窗口
                    root.update()  # 处理待定事件，避免某些环境下的问题
                except Exception as e:
                    # 窗口创建失败（可能在无GUI环境）
                    if os.getenv('DBRHEO_DEBUG_PASTE', 'false').lower() == 'true':
                        self.console.print(f"[dim]{_('tkinter_window_error', error=type(e).__name__)}[/dim]")
                    return None
                
                try:
                    # 获取剪贴板内容
                    content = root.clipboard_get()
                    root.quit()  # 先退出主循环
                    root.destroy()  # 再销毁窗口
                    return content
                except tk.TclError:
                    # 剪贴板为空或包含非文本内容
                    root.quit()
                    root.destroy()
                    return None
                except Exception as e:
                    # 其他错误
                    try:
                        root.quit()
                        root.destroy()
                    except:
                        pass
                    if os.getenv('DBRHEO_DEBUG_PASTE', 'false').lower() == 'true':
                        self.console.print(f"[dim]{_('clipboard_read_error', error=type(e).__name__)}[/dim]")
                    return None
            
            # 可以在这里添加其他方法（如pyperclip）的支持
            # elif clipboard_method == 'pyperclip':
            #     try:
            #         import pyperclip
            #         return pyperclip.paste()
            #     except:
            #         return None
            
            return None
            
        except Exception as e:
            # 任何未预期的错误都静默处理，不影响正常功能
            if os.getenv('DBRHEO_DEBUG_PASTE', 'false').lower() == 'true':
                self.console.print(f"[dim]{_('clipboard_error', error=type(e).__name__, details=str(e)[:50])}[/dim]")
            return None
    
    def _is_wsl(self) -> bool:
        """
        检测是否在WSL环境中运行
        """
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False
    
    def _is_sql_start(self, line: str) -> bool:
        """
        检测是否是SQL语句的开始
        """
        upper_line = line.strip().upper()
        return any(upper_line.startswith(keyword) for keyword in self.sql_keywords)
    
    def _has_unclosed_delimiter(self, text: str) -> bool:
        """
        检查是否有未闭合的引号或括号
        """
        # 简单的括号/引号平衡检查
        delimiters = {
            '(': ')',
            '[': ']',
            '{': '}',
            '"': '"',
            "'": "'"
        }
        
        stack = []
        in_string = None
        
        for char in text:
            if in_string:
                if char == in_string and text[text.index(char)-1:text.index(char)] != '\\':
                    in_string = None
            elif char in ['"', "'"]:
                in_string = char
            elif char in delimiters:
                stack.append(char)
            elif char in delimiters.values():
                if stack and delimiters[stack[-1]] == char:
                    stack.pop()
        
        return bool(stack) or in_string is not None
    
    def _block_multiline_input(self, marker: str) -> str:
        """
        块式多行输入（使用标记）
        """
        lines = []
        continuation_style = os.getenv('DBRHEO_CONTINUATION_STYLE', '[dim]{indicator}[/dim] ')
        continuation_prompt = continuation_style.format(indicator=self.multiline_indicator)
        
        block_hint = os.getenv('DBRHEO_BLOCK_HINT')
        if block_hint:
            self.console.print(block_hint)
        else:
            self.console.print(f'[dim]{_("multiline_traditional_hint")}[/dim]')
        
        try:
            while True:
                line = self.console.input(continuation_prompt)
                if line.strip() == marker:
                    break
                lines.append(line)
        except (EOFError, KeyboardInterrupt):
            if lines:
                return '\n'.join(lines)
            else:
                raise
        
        # 显示预览
        if len(lines) > 1:
            self.display_multiline_preview('\n'.join(lines))
        
        return '\n'.join(lines)
    
    def _manual_multiline_input(self, initial_lines: List[str], sql_mode: bool = False, auto_mode: bool = False) -> str:
        """
        手动多行输入模式
        """
        lines = initial_lines
        continuation_style = os.getenv('DBRHEO_CONTINUATION_STYLE', '[dim]{indicator}[/dim] ')
        continuation_prompt = continuation_style.format(indicator=self.multiline_indicator)
        empty_line_count = 0
        
        # 根据模式显示不同提示
        if sql_mode:
            # SQL模式：分号或空行结束
            end_hint = _('end_hint_semicolon_or_empty')
        elif auto_mode:
            # 自动模式：闭合引号/括号后空行结束
            end_hint = _('end_hint_complete_statement')
        else:
            # 手动模式
            end_hint = _('end_hint_empty_line') if self.multiline_end_mode == 'empty_line' else _('end_hint_double_empty')
            self.console.print(f"[dim]{_('multiline_manual_hint', end_hint=end_hint)}[/dim]")
        
        try:
            while True:
                line = self.console.input(continuation_prompt)
                
                # SQL模式特殊处理
                if sql_mode and line.rstrip().endswith(';'):
                    lines.append(line)
                    break
                
                # 检查是否需要继续
                if line.endswith('\\'):
                    # 移除末尾的反斜杠并继续
                    lines.append(line[:-1])
                    empty_line_count = 0
                elif line.strip() == '':
                    # 空行处理
                    if auto_mode:
                        # 自动模式下，检查是否所有括号/引号都已闭合
                        full_text = '\n'.join(lines + [line])
                        if not self._has_unclosed_delimiter(full_text):
                            break
                        else:
                            lines.append(line)
                    elif self.multiline_end_mode == 'double_empty':
                        empty_line_count += 1
                        if empty_line_count >= 2:
                            break
                        else:
                            lines.append(line)
                    else:
                        # 单空行结束
                        break
                else:
                    # 普通行
                    lines.append(line)
                    empty_line_count = 0
                        
        except (EOFError, KeyboardInterrupt):
            if lines:
                return '\n'.join(lines)
            else:
                raise
        
        # 显示预览（如果有多行）
        if len(lines) > 1:
            self.display_multiline_preview('\n'.join(lines))
        
        return '\n'.join(lines)
    
    def display_multiline_preview(self, text: str):
        """
        显示多行文本预览
        用于确认输入内容
        """
        if not text or '\n' not in text:
            return
            
        lines = text.split('\n')
        if len(lines) <= 1:
            return
            
        # 创建预览面板
        preview_lines = lines[:self.max_display_lines]
        if len(lines) > self.max_display_lines:
            preview_lines.append(f"... 还有 {len(lines) - self.max_display_lines} 行 ...")
        
        preview_text = Text()
        for i, line in enumerate(preview_lines):
            if i > 0:
                preview_text.append('\n')
            preview_text.append(line)
        
        panel = Panel(
            preview_text,
            title=_('multiline_preview_title'),
            border_style="dim",
            padding=(0, 1)
        )
        
        self.console.print(panel)


class EnhancedInputHandler:
    """
    增强的输入处理器
    在传统输入基础上添加多行支持
    """
    
    def __init__(self, config: CLIConfig, console: Console):
        self.config = config
        self.console = console
        self.multiline_input = SimpleMultilineInput(config, console)
        
        # 检查是否启用增强输入
        self.enhanced_enabled = os.getenv('DBRHEO_ENHANCED_INPUT', 'true').lower() == 'true'
        
        # Token警告阈值（可配置）
        self.token_warning_threshold = int(os.getenv('DBRHEO_TOKEN_WARNING_THRESHOLD', '300000'))
        
    async def get_input(self) -> str:
        """
        异步获取用户输入
        支持单行和多行模式
        """
        import asyncio
        
        # 在线程池中执行阻塞的输入操作
        loop = asyncio.get_event_loop()
        
        try:
            user_input = await loop.run_in_executor(
                None,
                self._blocking_input
            )
            return user_input.strip()
        except (EOFError, KeyboardInterrupt):
            raise
    
    def _blocking_input(self) -> str:
        """阻塞式输入（在线程池中执行）"""
        try:
            # 添加空行分隔
            if not hasattr(self, '_first_input'):
                self._first_input = False
            else:
                self.console.print()  # 简洁的空行分隔
            
            # 检查并显示token警告
            self._check_and_show_token_warning()
            
            # 根据配置选择输入方式
            if self.enhanced_enabled:
                # 使用增强的多行输入
                return self.multiline_input.get_multiline_input()
            else:
                # 使用传统的单行输入（支持 ``` 标记）
                return self._traditional_multiline_input()
                
        except (KeyboardInterrupt, EOFError):
            raise
    
    def _traditional_multiline_input(self) -> str:
        """传统的多行输入（使用 ``` 或 <<< 标记）"""
        first_line = self.console.input("[bold cyan]>[/bold cyan] ")
        
        # 检查是否进入多行模式
        if first_line.strip() in ['```', '<<<']:
            self.console.print(f"[dim]{_('multiline_traditional_hint')}[/dim]")
            lines = []
            while True:
                try:
                    line = self.console.input("[dim]...[/dim] ")
                    if line.strip() in ['```', '<<<']:
                        break
                    lines.append(line)
                except EOFError:
                    break
            return "\n".join(lines)
        
        return first_line
    
    def _check_and_show_token_warning(self):
        """
        检查token使用量并显示token警告
        最小侵入性设计：只在需要时显示，不影响正常流程
        """
        try:
            # 尝试从多个来源获取client实例（最小侵入性）
            client = None
            
            # 方法1: 从配置中获取
            if hasattr(self.config, '_client'):
                client = self.config._client
            
            # 方法52: 从全局主模块获取
            if not client:
                import sys
                main_module = sys.modules.get('__main__')
                if hasattr(main_module, 'cli'):
                    cli = getattr(main_module, 'cli')
                    if hasattr(cli, 'client'):
                        client = cli.client
            
            # 检查token统计
            if client and hasattr(client, 'token_statistics'):
                summary = client.token_statistics.get_summary()
                total_tokens = summary.get('total_tokens', 0)
                
                # 超过阈值时显示警告
                if total_tokens > self.token_warning_threshold:
                    # 使用i18n系统获取本地化的警告文本
                    from ..i18n import _
                    warning_text = _('token_usage_warning', tokens=total_tokens)
                    
                    # 使用浅黄色显示警告
                    self.console.print(f"[yellow dim]{warning_text}[/yellow dim]")
                        
        except Exception:
            # 忽略所有错误，不影响正常输入
            pass