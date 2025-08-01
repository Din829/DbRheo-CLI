"""
DbRheo ASCII 艺术标志
提供响应式的启动画面展示
"""

# DbRheo 短版本 (适合窄终端)
SHORT_LOGO = r"""
 ____  _     ____  _               
|  _ \| |__ |  _ \| |__   ___  ___ 
| | | | '_ \| |_) | '_ \ / _ \/ _ \
| |_| | |_) |  _ <| | | |  __/ (_) |
|____/|_.__/|_| \_\_| |_|\___|\___/ 
"""

# DbRheo 长版本 (适合宽终端) - 超大尺寸
LONG_LOGO = r"""
██████╗ ██████╗ ██████╗ ██╗  ██╗███████╗ ██████╗      ██████╗██╗     ██╗
██╔══██╗██╔══██╗██╔══██╗██║  ██║██╔════╝██╔═══██╗    ██╔════╝██║     ██║
██║  ██║██████╔╝██████╔╝███████║█████╗  ██║   ██║    ██║     ██║     ██║
██║  ██║██╔══██╗██╔══██╗██╔══██║██╔══╝  ██║   ██║    ██║     ██║     ██║
██████╔╝██████╔╝██║  ██║██║  ██║███████╗╚██████╔╝    ╚██████╗███████╗██║
╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝      ╚═════╝╚══════╝╚═╝
"""

# DbRheo 倾斜版本 (斜体效果)
ITALIC_LOGO = r"""
    ____  __   ____  __                 _______   __    ____
   / __ \/ /_ / __ \/ /_  ___  ____    / ____/ | / /   /  _/
  / / / / __ \/ /_/ / __ \/ _ \/ __ \  / /   / |/ /    / /  
 / /_/ / /_/ / _, _/ / / /  __/ /_/ / / /___/ /| /   _/ /   
/_____/_.___/_/ |_/_/ /_/\___/\____/  \____/_/ |_/  /___/   
"""

# DbRheo 超大版本 (非倾斜，更粗更大)
EXTRA_LARGE_LOGO = r"""
███████╗ ██████╗  ██████╗  ██╗  ██╗ ███████╗  ██████╗       ██████╗ ██╗      ██╗
██╔═══██╗██╔══██╗ ██╔══██╗ ██║  ██║ ██╔════╝ ██╔═══██╗     ██╔════╝ ██║      ██║
██║   ██║██████╔╝ ██████╔╝ ███████║ █████╗   ██║   ██║     ██║      ██║      ██║
██║   ██║██╔══██╗ ██╔══██╗ ██╔══██║ ██╔══╝   ██║   ██║     ██║      ██║      ██║
███████╔╝██████╔╝ ██║  ██║ ██║  ██║ ███████╗ ╚██████╔╝     ╚██████╗ ███████╗ ██║
╚══════╝ ╚═════╝  ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚══════╝  ╚═════╝       ╚═════╝ ╚══════╝ ╚═╝
"""

# DbRheo 超大版本 (适合很宽的终端)
EXTRA_LOGO = r"""
·▄▄▄▄  ▄▄▄▄· ▄▄▄   ▄ .▄▄▄▄ .       
██▪ ██ ▐█ ▀█▪▀▄ █·██▪▐█▀▄.▀·▪     
▐█· ▐█▌▐█▀▀█▄▐▀▀▄ ██▀▐█▐▀▀▪▄ ▄█▀▄ 
██. ██ ██▄▪▐█▐█•█▌██▌▐▀▐█▄▄▌▐█▌.▐▌
▀▀▀▀▀• ·▀▀▀▀ .▀  ▀▀▀▀ ▀ ▀▀▀  ▀█▄▀▪
    Database Intelligence Assistant
"""

# 3D 风格版本 (特殊场合使用)
LOGO_3D = r"""
    ___  __   ___  __             
   / _ \/ /  / _ \/ /  ___ ___    
  / // / _ \/ , _/ _ \/ -_) _ \   
 /____/_.__/_/|_/_//_/\__/\___/   
 D a t a b a s e   A g e n t      
"""

def get_logo_width(logo: str) -> int:
    """计算 ASCII 艺术的宽度"""
    lines = logo.strip().split('\n')
    return max(len(line) for line in lines) if lines else 0

def select_logo(terminal_width: int, style: str = "default") -> str:
    """
    根据终端宽度和风格选择合适的 logo
    
    Args:
        terminal_width: 终端宽度
        style: 风格选择 - "default", "italic", "extra"
    """
    # 获取各版本宽度
    long_width = get_logo_width(LONG_LOGO)
    italic_width = get_logo_width(ITALIC_LOGO)
    extra_width = get_logo_width(EXTRA_LARGE_LOGO)
    short_width = get_logo_width(SHORT_LOGO)
    
    # 根据风格和宽度选择
    if style == "italic":
        if terminal_width >= italic_width + 10:
            return ITALIC_LOGO
        else:
            return SHORT_LOGO
    elif style == "extra":
        if terminal_width >= extra_width + 10:
            return EXTRA_LARGE_LOGO
        else:
            return ITALIC_LOGO
    else:  # default
        # 优先使用长版本
        if terminal_width >= long_width + 10:
            return LONG_LOGO
        elif terminal_width >= short_width + 10:
            return SHORT_LOGO
        else:
            # 如果终端太窄，返回最简单的文字
            return "\n DbRheo CLI \n"