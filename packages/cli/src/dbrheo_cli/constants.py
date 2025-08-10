"""
常量定义
集中管理所有硬编码的值，便于配置和修改
"""

import os


# 环境变量名称
ENV_VARS = {
    'DEBUG_LEVEL': 'DBRHEO_DEBUG_LEVEL',
    'DEBUG_VERBOSITY': 'DBRHEO_DEBUG_VERBOSITY',
    'ENABLE_LOG': 'DBRHEO_ENABLE_REALTIME_LOG',
    'DB_FILE': 'DBRHEO_DB_FILE',
    'NO_COLOR': 'DBRHEO_NO_COLOR',
    'PAGE_SIZE': 'DBRHEO_PAGE_SIZE',
    'SHOW_THOUGHTS': 'DBRHEO_SHOW_THOUGHTS',
    'MAX_WIDTH': 'DBRHEO_MAX_WIDTH',
    'MAX_HISTORY': 'DBRHEO_MAX_HISTORY',
    'HISTORY_FILE': 'DBRHEO_HISTORY_FILE',
    'MODEL': 'DBRHEO_MODEL'  # 模型选择
}

# 默认配置值
DEFAULTS = {
    'PAGE_SIZE': 50,
    'MAX_WIDTH': 120,
    'MAX_HISTORY': 1000,
    'HISTORY_FILE': '~/.dbrheo_history',
    'SESSION_ID_PREFIX': 'cli_session',
    'DEBUG_LEVEL': 'ERROR',  # 默认只显示错误
    'DEBUG_VERBOSITY': 'MINIMAL'  # 最小详细程度
}

# 命令定义
COMMANDS = {
    'EXIT': ['/exit', '/quit'],
    'HELP': ['/help'],
    'CLEAR': ['/clear'],
    'DEBUG': ['/debug'],
    'LANG': ['/lang', '/language'],
    'MODEL': ['/model'],  # 模型切换
    'TOKEN': ['/token'],  # Token 统计
    'DATABASE': ['/database', '/db'],  # 数据库连接
    'MCP': ['/mcp']  # MCP 服务器管理
}

# 确认关键词
CONFIRMATION_WORDS = {
    'CONFIRM': ['1', 'confirm', 'y', 'yes'],
    'CANCEL': ['2', 'cancel', 'n', 'no'],
    'CONFIRM_ALL': ['confirm all']
}

# 系统命令（跨平台）
SYSTEM_COMMANDS = {
    'CLEAR': 'clear' if os.name == 'posix' else 'cls'
}

# 调试级别范围
DEBUG_LEVEL_RANGE = (0, 5)

# 文件路径
PATHS = {
    'SRC_ROOT': lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
}

# 支持的模型列表
SUPPORTED_MODELS = {
    'gemini': 'Gemini 2.5 Flash',
    'claude': 'Claude Sonnet 4',
    'sonnet3.7': 'Claude 3.7',
    'gpt': 'GPT-4.1',
    'gpt-mini': 'GPT-5 Mini'
}