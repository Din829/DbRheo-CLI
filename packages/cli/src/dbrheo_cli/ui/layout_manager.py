"""
布局管理器 - 可选的底部固定输入框实现
最小侵入性设计：完全可选，不影响现有功能
"""

import asyncio
import os
from typing import Optional, Callable, Any
from dataclasses import dataclass

try:
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout import Layout, HSplit, Window, Dimension
    from prompt_toolkit.widgets import TextArea
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.shortcuts import print_formatted_text
    from prompt_toolkit.output import create_output
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

from .console import console
from ..app.config import CLIConfig


@dataclass
class LayoutConfig:
    """布局配置 - 灵活可配置"""
    enabled: bool = False                    # 是否启用新布局
    input_height_min: int = 3               # 输入区最小高度
    input_height_max: int = 10              # 输入区最大高度  
    history_max_lines: int = 1000           # 历史消息最大行数
    auto_scroll: bool = True                # 自动滚动
    show_separator: bool = True             # 显示分隔线
    
    @classmethod
    def from_env(cls) -> 'LayoutConfig':
        """从环境变量读取配置 - 灵活配置"""
        return cls(
            enabled=os.getenv('DBRHEO_ENHANCED_LAYOUT', 'false').lower() == 'true',  # 紧急回滚：默认禁用
            input_height_min=int(os.getenv('DBRHEO_INPUT_HEIGHT_MIN', '3')),
            input_height_max=int(os.getenv('DBRHEO_INPUT_HEIGHT_MAX', '10')),
            history_max_lines=int(os.getenv('DBRHEO_HISTORY_MAX_LINES', '1000')),
            auto_scroll=os.getenv('DBRHEO_AUTO_SCROLL', 'true').lower() == 'true',
            show_separator=os.getenv('DBRHEO_SHOW_SEPARATOR', 'true').lower() == 'true'
        )


class EnhancedLayoutManager:
    """
    增强布局管理器
    设计原则：
    1. 最小侵入性：完全可选，fallback到传统模式
    2. 灵活性：高度可配置，适应不同需求
    3. 解决痛点：底部固定输入，并发输入输出
    """
    
    def __init__(self, config: CLIConfig):
        self.config = config
        self.layout_config = LayoutConfig.from_env()
        self.app: Optional[Application] = None
        self.history_content = []
        self.input_callback: Optional[Callable[[str], Any]] = None
        self.is_running = False
        
        # 检查prompt-toolkit可用性
        self.available = PROMPT_TOOLKIT_AVAILABLE and self.layout_config.enabled
        
        if self.available:
            self._setup_layout()
    
    def is_available(self) -> bool:
        """检查增强布局是否可用"""
        return self.available
    
    def _setup_layout(self):
        """设置布局 - 参考Gemini CLI但适配我们的需求"""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return
            
        # 历史消息区域
        self.history_area = Window(
            content=self._create_history_content(),
            wrap_lines=True
        )
        
        # 分隔线（可配置）
        separator = None
        if self.layout_config.show_separator:
            separator = Window(
                height=Dimension.exact(1),
                content=self._create_separator_content()
            )
        
        # 输入区域
        self.input_area = TextArea(
            multiline=True,
            wrap_lines=True,
            prompt='> '
        )
        
        # 构建布局
        layout_components = [self.history_area]
        if separator:
            layout_components.append(separator)
        layout_components.append(self.input_area)
        
        layout = Layout(HSplit(layout_components))
        
        # 设置快捷键
        bindings = self._create_key_bindings()
        
        # 创建应用
        self.app = Application(
            layout=layout,
            key_bindings=bindings,
            full_screen=True,
            mouse_support=True
        )
    
    def _create_history_content(self):
        """创建历史内容显示"""
        from prompt_toolkit.formatted_text import FormattedText
        
        def get_formatted_text():
            """动态获取格式化的历史内容"""
            if not self.history_content:
                return FormattedText([('class:dim', '等待对话开始...')])
            
            # 限制历史长度，避免内存问题
            recent_history = self.history_content[-self.layout_config.history_max_lines:]
            return FormattedText(recent_history)
        
        from prompt_toolkit.layout.controls import FormattedTextControl
        return FormattedTextControl(get_formatted_text)
    
    def _create_separator_content(self):
        """创建分隔线内容"""
        from prompt_toolkit.layout.controls import FormattedTextControl
        
        def get_separator():
            # 动态计算分隔线长度
            try:
                width = self.app.output.get_size().columns if self.app else 80
                return FormattedText([('class:separator', '─' * width)])
            except:
                return FormattedText([('class:separator', '─' * 80)])
        
        return FormattedTextControl(get_separator)
    
    def _create_key_bindings(self):
        """创建快捷键绑定 - 参考Gemini CLI的交互模式"""
        bindings = KeyBindings()
        
        @bindings.add('c-c')  # Ctrl+C
        def _(event):
            """优雅退出"""
            self.stop()
        
        @bindings.add('c-d')  # Ctrl+D  
        def _(event):
            """EOF退出"""
            self.stop()
        
        @bindings.add('enter', eager=True)
        def _(event):
            """提交输入"""
            text = self.input_area.text.strip()
            if text and self.input_callback:
                # 清空输入框
                self.input_area.text = ''
                # 异步调用回调
                asyncio.create_task(self._handle_input(text))
        
        @bindings.add('escape')
        def _(event):
            """ESC键 - 清空当前输入或退出"""
            if self.input_area.text:
                self.input_area.text = ''
            else:
                self.stop()
        
        return bindings
    
    async def _handle_input(self, text: str):
        """处理用户输入 - 异步不阻塞"""
        if self.input_callback:
            try:
                await self.input_callback(text)
            except Exception as e:
                self.add_message(f"错误: {e}", style='class:error')
    
    def add_message(self, message: str, style: str = 'class:default'):
        """添加消息到历史区域"""
        self.history_content.append((style, message + '\n'))
        
        # 自动滚动到底部
        if self.layout_config.auto_scroll and self.app:
            # 触发重绘
            self.app.invalidate()
    
    def add_rich_content(self, rich_content):
        """添加Rich渲染的内容 - 保持现有渲染能力"""
        from io import StringIO
        from rich.console import Console
        
        # 将Rich内容渲染为文本
        buffer = StringIO()
        temp_console = Console(file=buffer, force_terminal=True, width=80)
        temp_console.print(rich_content)
        content = buffer.getvalue()
        
        self.add_message(content)
    
    async def run_async(self, input_callback: Callable[[str], Any]):
        """异步运行布局管理器"""
        if not self.available:
            raise RuntimeError("增强布局不可用，请检查prompt-toolkit安装")
        
        self.input_callback = input_callback
        self.is_running = True
        
        try:
            await self.app.run_async()
        finally:
            self.is_running = False
    
    def stop(self):
        """停止应用"""
        if self.app and self.is_running:
            self.app.exit()
    
    def update_display(self):
        """更新显示 - 用于流式输出"""
        if self.app and self.is_running:
            self.app.invalidate()


# 工厂函数 - 最小侵入性集成点
def create_layout_manager(config: CLIConfig) -> Optional[EnhancedLayoutManager]:
    """
    创建布局管理器
    返回None表示使用传统模式，返回实例表示使用增强模式
    """
    manager = EnhancedLayoutManager(config)
    return manager if manager.is_available() else None


# 后备方案 - 确保100%兼容性
class FallbackLayoutManager:
    """后备布局管理器 - 维持现有行为"""
    
    def __init__(self, config: CLIConfig):
        self.config = config
    
    def is_available(self) -> bool:
        return True
    
    def add_message(self, message: str, style: str = 'class:default'):
        """使用现有console输出"""
        console.print(message)
    
    def add_rich_content(self, rich_content):
        """使用现有Rich渲染"""
        console.print(rich_content)
    
    async def run_async(self, input_callback):
        """使用传统输入模式"""
        from ..handlers.input_handler import InputHandler
        input_handler = InputHandler(self.config)
        
        while True:
            try:
                user_input = await input_handler.get_input()
                await input_callback(user_input)
            except (EOFError, KeyboardInterrupt):
                break
    
    def stop(self):
        pass
    
    def update_display(self):
        pass