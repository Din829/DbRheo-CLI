"""
输入处理器
处理用户输入，包括命令解析、特殊按键处理等。
"""

import sys
import asyncio
from typing import Optional

from ..ui.console import console
from ..app.config import CLIConfig
from ..i18n import _

# 尝试导入增强输入组件（可选功能）
try:
    from ..ui.simple_multiline_input import EnhancedInputHandler
    ENHANCED_INPUT_AVAILABLE = True
except ImportError:
    ENHANCED_INPUT_AVAILABLE = False


class InputHandler:
    """
    用户输入处理器
    - 获取用户输入
    - 处理特殊按键
    - 管理输入历史（通过readline）
    """
    
    def __init__(self, config: CLIConfig):
        self.config = config
        
        # 初始化增强输入处理器（如果可用）
        self.enhanced_handler = None
        if ENHANCED_INPUT_AVAILABLE:
            try:
                self.enhanced_handler = EnhancedInputHandler(config, console)
                from dbrheo.utils.debug_logger import log_info
                log_info("InputHandler", "Enhanced input mode available")
            except Exception as e:
                # 初始化失败，使用传统模式
                self.enhanced_handler = None
                from dbrheo.utils.debug_logger import log_info
                log_info("InputHandler", f"Enhanced input initialization failed: {e}")
        
    async def get_input(self) -> str:
        """
        异步获取用户输入
        使用asyncio兼容的方式读取输入
        """
        # 优先使用增强输入（如果可用）
        if self.enhanced_handler:
            try:
                return await self.enhanced_handler.get_input()
            except Exception as e:
                # 增强输入失败，回退到传统模式
                from dbrheo.utils.debug_logger import log_info
                log_info("InputHandler", f"Enhanced input failed, falling back: {e}")
                self.enhanced_handler = None
        
        # 使用传统输入模式
        loop = asyncio.get_event_loop()
        
        try:
            # 在线程池中执行input
            user_input = await loop.run_in_executor(
                None, 
                self._blocking_input
            )
            return user_input.strip()
        except EOFError:
            # Ctrl+D
            raise
        except KeyboardInterrupt:
            # Ctrl+C
            raise
    
    def _blocking_input(self) -> str:
        """阻塞式输入（在线程池中执行）"""
        try:
            # 添加分隔线，让输入区域更明显
            if not hasattr(self, '_first_input'):
                self._first_input = False
            else:
                console.print()  # 简洁的空行分隔
            
            # 获取输入
            if self.config.no_color:
                first_line = input("> ")
            else:
                # 使用Rich的prompt功能
                first_line = console.input("[bold cyan]>[/bold cyan] ")
            
            # 检查是否进入多行模式
            # 支持 ``` 或 <<< 作为多行输入标记
            if first_line.strip() in ['```', '<<<']:
                console.print(f"[dim]{_('multiline_mode_hint')}[/dim]")
                lines = []
                while True:
                    try:
                        if self.config.no_color:
                            line = input("... ")
                        else:
                            line = console.input("[dim]...[/dim] ")
                        
                        if line.strip() in ['```', '<<<']:
                            break
                        lines.append(line)
                    except EOFError:
                        break
                return "\n".join(lines)
            
            return first_line
        except KeyboardInterrupt:
            # 在input时按Ctrl+C
            raise
        except EOFError:
            # Ctrl+D
            raise