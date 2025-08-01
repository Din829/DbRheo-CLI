"""
流式输出组件
处理Agent的流式响应：
- TextBuffer: 文本缓冲管理
- StreamDisplay: 流式显示控制
- MarkdownRenderer: Markdown渲染

对应Gemini CLI的流式处理和Markdown显示逻辑。
"""

import asyncio
from typing import Optional
from rich.markdown import Markdown
from rich.syntax import Syntax

from .console import console
from ..app.config import CLIConfig


class StreamDisplay:
    """
    流式显示控制器
    管理AI响应的流式输出，避免闪烁
    """
    
    def __init__(self, config: CLIConfig):
        self.config = config
        self.buffer = []
        self.is_streaming = False
        self.current_line = ""
        
        # 代码块检测状态
        self.in_code_block = False
        self.code_language = ""
        self.code_buffer = []
        self.pending_content = ""  # 缓存未处理的内容
        
        # 可配置的显示选项
        self.code_theme = getattr(config, 'code_theme', 'monokai')
        self.show_line_numbers = getattr(config, 'show_line_numbers', {'python': True})
        self.special_languages = getattr(config, 'special_languages', {})
        
    async def add_content(self, content: str):
        """添加内容到流式显示"""
        if not self.is_streaming:
            self.is_streaming = True
            # 显示AI响应前缀
            console.print("● ", end='')
        
        # 累积待处理的内容
        self.pending_content += content
        
        # 处理完整的行
        while '\n' in self.pending_content:
            line_end = self.pending_content.index('\n')
            line = self.pending_content[:line_end]
            self.pending_content = self.pending_content[line_end + 1:]
            
            # 处理单行
            await self._process_line(line + '\n')
        
        # 如果不在代码块中，直接输出剩余内容
        if not self.in_code_block and self.pending_content:
            console.print(self.pending_content, end='')
            self.pending_content = ""
        
        # 确保控制台刷新
        try:
            import sys
            sys.stdout.flush()
        except:
            pass
    
    async def _process_line(self, line: str):
        """处理单行内容"""
        # 调试信息
        from dbrheo.utils.debug_logger import DebugLogger, log_info
        if DebugLogger.should_log("DEBUG"):
            log_info("StreamDisplay", f"Processing line: {repr(line[:50])}")
        
        # 检测代码块开始
        if line.strip().startswith('```') and not self.in_code_block:
            # 提取语言标识
            language = line.strip()[3:].strip()
            self.code_language = self._normalize_language(language)
            self.in_code_block = True
            self.code_buffer = []
            
            if DebugLogger.should_log("DEBUG"):
                log_info("StreamDisplay", f"Code block started, language: {self.code_language}")
            
            # 如果语言标识为空但下一行可能是语言标识，不立即返回
            if not language and line.strip() == '```':
                # 可能是独立的```行，语言在下一行
                pass
            return
        
        # 检测代码块结束
        if line.strip() == '```' and self.in_code_block:
            self.in_code_block = False
            # 渲染代码块
            self._render_code_block()
            self.code_buffer = []
            self.code_language = ""
            return
        
        # 在代码块中
        if self.in_code_block:
            self.code_buffer.append(line.rstrip('\n'))
        else:
            # 普通文本
            console.print(line, end='')
    
    def _normalize_language(self, language: str) -> str:
        """标准化语言标识"""
        # 映射常见的语言别名
        language_map = {
            'sql': 'sql',
            'mysql': 'sql',
            'postgresql': 'sql',
            'sqlite': 'sql',
            'py': 'python',
            'python3': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'sh': 'bash',
            'shell': 'bash',
            'yml': 'yaml',
        }
        
        lang_lower = language.lower()
        return language_map.get(lang_lower, lang_lower)
    
    def _render_code_block(self):
        """渲染代码块"""
        if not self.code_buffer:
            return
        
        code_content = '\n'.join(self.code_buffer)
        
        # 检查是否需要特殊处理
        if self.code_language in self.special_languages:
            special_title = self.special_languages[self.code_language]
            console.print(f"\n[bold cyan]{special_title}[/bold cyan]")
            
        # 添加一点空白
        console.print()
        
        # 使用Rich的Syntax组件进行代码高亮
        try:
            # 检查是否需要显示行号
            show_lines = self.show_line_numbers.get(self.code_language, False)
            
            syntax = Syntax(
                code_content,
                self.code_language or "text",
                theme=self.code_theme,
                line_numbers=show_lines,
                word_wrap=True
            )
            console.print(syntax)
            console.print()  # 代码块后添加空行
                
        except Exception:
            # 如果渲染失败，使用普通格式
            console.print(f"```{self.code_language}")
            console.print(code_content)
            console.print("```\n")
    
    async def finish(self):
        """结束流式显示"""
        if self.is_streaming:
            # 处理剩余的内容
            if self.pending_content:
                if self.in_code_block:
                    # 如果还在代码块中，添加到缓冲区并渲染
                    self.code_buffer.append(self.pending_content)
                    self._render_code_block()
                else:
                    console.print(self.pending_content, end='')
            
            # 确保最后有换行
            console.print()
            
            # 重置状态
            self.is_streaming = False
            self.current_line = ""
            self.pending_content = ""
            self.in_code_block = False
            self.code_buffer = []
            self.code_language = ""
    
    def finish_sync(self):
        """同步版本的结束流式显示"""
        if self.is_streaming:
            # 处理剩余的内容
            if self.pending_content:
                if self.in_code_block:
                    self.code_buffer.append(self.pending_content)
                    self._render_code_block()
                else:
                    console.print(self.pending_content, end='')
            
            console.print()
            
            # 重置状态
            self.is_streaming = False
            self.current_line = ""
            self.pending_content = ""
            self.in_code_block = False
            self.code_buffer = []
            self.code_language = ""


class MarkdownRenderer:
    """
    简单的Markdown渲染器
    仅处理代码块高亮，保持简洁
    """
    
    @staticmethod
    def render_code_block(code: str, language: str = "text"):
        """渲染代码块"""
        try:
            syntax = Syntax(code, language, theme="monokai", line_numbers=False)
            console.print(syntax)
        except Exception:
            # 如果语言不支持，使用纯文本
            console.print(f"```{language}\n{code}\n```")
    
    @staticmethod
    def render_table(headers: list, rows: list):
        """使用Rich Table渲染表格"""
        from rich.table import Table
        
        table = Table(show_header=True, header_style="bold")
        
        # 添加列
        for header in headers:
            table.add_column(header)
        
        # 添加行
        for row in rows:
            table.add_row(*row)
        
        console.print(table)