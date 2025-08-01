"""
Rich Console封装
全局Console实例和输出配置管理
"""

from rich.console import Console as RichConsole
from rich.theme import Theme
import sys
import locale


# 定义简洁的主题（仅5种颜色）
db_theme = Theme({
    "default": "default",
    "success": "green",
    "error": "red",
    "warning": "yellow", 
    "info": "cyan"
})

# 智能检测终端编码
def _detect_console_settings():
    """检测终端编码和兼容性设置"""
    settings = {
        'theme': db_theme,
        'force_terminal': True  # 默认强制终端模式
    }
    
    try:
        # Windows 控制台特殊处理
        if sys.platform == 'win32':
            import ctypes
            # 获取控制台输出代码页
            codepage = ctypes.windll.kernel32.GetConsoleOutputCP()
            
            # 日语系统（cp932）或其他非UTF-8系统
            if codepage != 65001:  # 65001 是 UTF-8
                settings['legacy_windows'] = True
                # 可选：记录检测到的编码
                import os
                os.environ.setdefault('DBRHEO_CONSOLE_ENCODING', f'cp{codepage}')
        else:
            # Unix/Linux 使用 locale
            encoding = locale.getpreferredencoding()
            if encoding and not encoding.lower().startswith('utf'):
                # 非UTF-8系统，可能需要特殊处理
                import os
                os.environ.setdefault('DBRHEO_CONSOLE_ENCODING', encoding)
    except:
        # 检测失败时使用默认设置
        pass
        
    return settings

# 创建全局Console实例（智能配置）
console = RichConsole(**_detect_console_settings())


def set_no_color(no_color: bool):
    """设置是否禁用颜色"""
    global console
    if no_color:
        console = RichConsole(no_color=True)
    else:
        # 使用智能配置
        console = RichConsole(**_detect_console_settings())