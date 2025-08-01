"""
CLI配置管理
保持灵活性，避免硬编码，支持运行时配置
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass

from ..constants import ENV_VARS, DEFAULTS


@dataclass
class CLIConfig:
    """
    CLI专用配置
    - 命令行参数
    - 显示设置
    - 用户偏好
    """
    # 数据库配置
    db_file: Optional[str] = None
    
    # 显示配置
    no_color: bool = False
    page_size: int = DEFAULTS['PAGE_SIZE']
    max_width: int = DEFAULTS['MAX_WIDTH']
    
    # 配置文件
    config_file: Optional[str] = None
    
    # 历史记录
    history_file: str = os.path.expanduser(DEFAULTS['HISTORY_FILE'])
    max_history: int = DEFAULTS['MAX_HISTORY']
    
    # 调试选项
    show_thoughts: bool = False  # 是否显示AI思考过程
    show_tool_details: bool = True  # 是否显示工具执行详情
    
    # 布局选项 - 新增但保持向后兼容
    enhanced_layout: bool = False  # 是否使用增强布局（底部固定输入框）
    
    def __post_init__(self):
        """初始化后处理，确保配置的合理性"""
        # 确保历史文件目录存在
        history_dir = os.path.dirname(self.history_file)
        if history_dir and not os.path.exists(history_dir):
            os.makedirs(history_dir, exist_ok=True)
        
        # 从环境变量更新配置（环境变量优先级低于命令行参数）
        if not self.db_file and ENV_VARS['DB_FILE'] in os.environ:
            self.db_file = os.environ[ENV_VARS['DB_FILE']]
        
        if ENV_VARS['NO_COLOR'] in os.environ:
            self.no_color = os.environ[ENV_VARS['NO_COLOR']].lower() == 'true'
        
        if ENV_VARS['PAGE_SIZE'] in os.environ:
            try:
                self.page_size = int(os.environ[ENV_VARS['PAGE_SIZE']])
            except ValueError:
                pass
        
        if ENV_VARS['SHOW_THOUGHTS'] in os.environ:
            self.show_thoughts = os.environ[ENV_VARS['SHOW_THOUGHTS']].lower() == 'true'
        
        if ENV_VARS['MAX_WIDTH'] in os.environ:
            try:
                self.max_width = int(os.environ[ENV_VARS['MAX_WIDTH']])
            except ValueError:
                pass
        
        if ENV_VARS['MAX_HISTORY'] in os.environ:
            try:
                self.max_history = int(os.environ[ENV_VARS['MAX_HISTORY']])
            except ValueError:
                pass
        
        if ENV_VARS['HISTORY_FILE'] in os.environ:
            self.history_file = os.path.expanduser(os.environ[ENV_VARS['HISTORY_FILE']])
        
        # 增强布局选项 - 从环境变量读取
        if 'DBRHEO_ENHANCED_LAYOUT' in os.environ:
            self.enhanced_layout = os.environ['DBRHEO_ENHANCED_LAYOUT'].lower() == 'true'
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'db_file': self.db_file,
            'no_color': self.no_color,
            'page_size': self.page_size,
            'max_width': self.max_width,
            'config_file': self.config_file,
            'history_file': self.history_file,
            'max_history': self.max_history,
            'show_thoughts': self.show_thoughts,
            'show_tool_details': self.show_tool_details,
            'enhanced_layout': self.enhanced_layout
        }
    
    def update_runtime(self, key: str, value: Any):
        """
        运行时更新配置
        支持动态修改配置而不需要重启
        """
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            raise ValueError(f"Unknown configuration key: {key}")
    
    def get_display_config(self) -> Dict[str, Any]:
        """获取显示相关的配置"""
        return {
            'no_color': self.no_color,
            'page_size': self.page_size,
            'max_width': self.max_width,
            'show_thoughts': self.show_thoughts,
            'show_tool_details': self.show_tool_details
        }