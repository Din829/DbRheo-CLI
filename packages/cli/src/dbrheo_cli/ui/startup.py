"""
DbRheo 启动画面
使用 rich-gradient 实现优雅的渐变效果
"""

import os
from typing import Optional, List, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.columns import Columns

from .ascii_art import select_logo, get_logo_width, LONG_LOGO, EXTRA_LARGE_LOGO
from ..i18n import _
from ..app.config import CLIConfig

# 尝试导入 rich-gradient，提供优雅降级
try:
    from rich_gradient import Gradient
    GRADIENT_AVAILABLE = True
except ImportError:
    GRADIENT_AVAILABLE = False

# 颜色主题
DBRHEO_GRADIENT_COLORS = ["#000033", "#001155", "#0033AA", "#0055FF", "#3377FF"]  # 蓝黑渐变
TIPS_COLOR = "#8899AA"  # 提示文字颜色


class StartupScreen:
    """启动画面管理器"""
    
    def __init__(self, config: CLIConfig, console: Console):
        self.config = config
        self.console = console
        self.terminal_width = console.width
        
    def display(self, version: str = "0.2.0", show_tips: bool = True, 
                custom_message: Optional[str] = None, logo_style: str = "italic"):
        """
        显示启动画面
        
        Args:
            version: 版本号
            show_tips: 是否显示使用提示
            custom_message: 自定义消息（如警告）
            logo_style: logo 风格 - "default", "italic", "extra"
        """
        # 选择合适的 logo
        logo = select_logo(self.terminal_width, style=logo_style)
        
        # 显示 logo（带渐变效果）
        self._display_logo(logo)
        
        # 显示版本信息
        self._display_version(version)
        
        # 显示使用提示
        if show_tips:
            self._display_tips()
            
        # 显示自定义消息（如工作目录警告）
        if custom_message:
            self._display_custom_message(custom_message)
            
        # 添加底部间距
        self.console.print()
        
    def _display_logo(self, logo: str):
        """显示带渐变效果的 logo"""
        if GRADIENT_AVAILABLE and not self.config.no_color:
            # 使用 rich-gradient 实现渐变
            gradient_logo = Gradient(
                logo.strip(),
                colors=DBRHEO_GRADIENT_COLORS,
                justify="left"  # 改为左对齐
            )
            self.console.print(gradient_logo)
        else:
            # 降级方案：使用简单的蓝色
            self.console.print(
                Text(logo.strip(), style="bold blue"),
                justify="left"  # 改为左对齐
            )
            
    def _display_version(self, version: str):
        """显示版本信息"""
        version_text = f"v{version}"
        if GRADIENT_AVAILABLE and not self.config.no_color:
            version_gradient = Gradient(
                version_text,
                colors=DBRHEO_GRADIENT_COLORS[::-1],  # 反向渐变
                justify="right"
            )
            self.console.print(version_gradient)
        else:
            self.console.print(
                Text(version_text, style="dim cyan"),
                justify="right"
            )
            
    def _display_tips(self):
        """显示使用提示"""
        tips = [
            _('startup_tip_1'),
            _('startup_tip_2'),
            _('startup_tip_3'),
            _('startup_tip_4'),
            _('startup_tip_5'),
            _('startup_tip_6')
        ]
            
        self.console.print()
        self.console.print(_('startup_tips_title'), style=f"bold {TIPS_COLOR}")
        for tip in tips:
            self.console.print(f"  {tip}", style=TIPS_COLOR)
            
    def _display_custom_message(self, message: str):
        """显示自定义消息（如警告框）"""
        self.console.print()
        panel = Panel(
            message,
            border_style="yellow",
            padding=(0, 2)
        )
        self.console.print(panel)
        


def create_minimal_startup(console: Console, version: str = "0.2.0"):
    """创建最小化的启动信息（用于 --quiet 模式）"""
    console.print(f"[bold blue]DbRheo[/bold blue] v{version}")


def create_rainbow_logo(logo: str) -> Optional[str]:
    """创建彩虹效果的 logo（特殊场合使用）"""
    if not GRADIENT_AVAILABLE:
        return None
        
    try:
        rainbow_logo = Gradient(
            logo.strip(),
            rainbow=True,
            justify="center"
        )
        return rainbow_logo
    except:
        return None