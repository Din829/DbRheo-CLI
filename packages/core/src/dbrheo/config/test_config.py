"""
TestDatabaseConfig - 测试专用配置类
继承DatabaseConfig但支持运行时配置覆盖，保持灵活性原则
"""

from typing import Any, Dict, Optional
from pathlib import Path
from .base import DatabaseConfig, ConfigSource


class TestConfigSource(ConfigSource):
    """测试配置源 - 最高优先级，用于测试时覆盖配置"""
    
    def __init__(self, test_config: Dict[str, Any]):
        self._test_config = test_config
        
    def get(self, key: str) -> Optional[Any]:
        return self._test_config.get(key)
        
    def get_all(self) -> Dict[str, Any]:
        return self._test_config.copy()


class TestDatabaseConfig(DatabaseConfig):
    """
    测试专用配置类
    - 继承完整的分层配置系统
    - 支持运行时测试配置覆盖
    - 提供便捷的测试数据库设置API
    - 保持与Gemini CLI设计原则的完全对齐
    """
    
    def __init__(self, workspace_root: Optional[Path] = None, test_overrides: Optional[Dict[str, Any]] = None):
        """
        初始化测试配置
        
        参数:
            workspace_root: 工作区根目录
            test_overrides: 测试覆盖配置，具有最高优先级
        """
        # 先调用父类初始化
        super().__init__(workspace_root)
        
        # 如果有测试覆盖配置，添加到配置源列表的最前面（最高优先级）
        if test_overrides:
            self._test_overrides = test_overrides
            # 将测试配置源插入到最前面
            self.config_sources.insert(0, TestConfigSource(test_overrides))
        else:
            self._test_overrides = {}
    
    def set_test_database(self, database_name: str, database_config: Dict[str, Any]) -> None:
        """
        设置测试数据库配置
        
        参数:
            database_name: 数据库名称（如 'default', 'test'）
            database_config: 数据库配置字典，包含type, database等
            
        示例:
            config.set_test_database('default', {
                'type': 'sqlite',
                'database': '/path/to/test.db'
            })
        """
        if 'databases' not in self._test_overrides:
            self._test_overrides['databases'] = {}
            
        self._test_overrides['databases'][database_name] = database_config
        
        # 更新配置源
        if self.config_sources and isinstance(self.config_sources[0], TestConfigSource):
            # 更新现有的测试配置源
            self.config_sources[0] = TestConfigSource(self._test_overrides)
        else:
            # 插入新的测试配置源
            self.config_sources.insert(0, TestConfigSource(self._test_overrides))
    
    def set_test_config(self, key: str, value: Any) -> None:
        """
        设置任意测试配置
        
        参数:
            key: 配置键，支持嵌套（用.分隔）
            value: 配置值
            
        示例:
            config.set_test_config('model', 'gemini-2.5-flash')
            config.set_test_config('databases.test.type', 'sqlite')
        """
        keys = key.split('.')
        current = self._test_overrides
        
        # 创建嵌套结构
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # 设置最终值
        current[keys[-1]] = value
        
        # 更新配置源
        if self.config_sources and isinstance(self.config_sources[0], TestConfigSource):
            self.config_sources[0] = TestConfigSource(self._test_overrides)
        else:
            self.config_sources.insert(0, TestConfigSource(self._test_overrides))
    
    def get_test_overrides(self) -> Dict[str, Any]:
        """获取当前的测试覆盖配置（用于调试）"""
        return self._test_overrides.copy()
    
    def clear_test_overrides(self) -> None:
        """清除所有测试覆盖配置"""
        self._test_overrides.clear()
        # 移除测试配置源
        if self.config_sources and isinstance(self.config_sources[0], TestConfigSource):
            self.config_sources.pop(0)
    
    @classmethod
    def create_with_sqlite_database(cls, db_path: str, database_name: str = 'default') -> 'TestDatabaseConfig':
        """
        便捷方法：创建带有SQLite数据库的测试配置
        
        参数:
            db_path: SQLite数据库文件路径
            database_name: 数据库名称
            
        返回:
            配置好的TestDatabaseConfig实例
        """
        config = cls()
        config.set_test_database(database_name, {
            'type': 'sqlite',
            'database': db_path
        })
        return config
    
    @classmethod
    def create_with_memory_database(cls, database_name: str = 'default') -> 'TestDatabaseConfig':
        """
        便捷方法：创建带有内存SQLite数据库的测试配置
        
        参数:
            database_name: 数据库名称
            
        返回:
            配置好的TestDatabaseConfig实例
        """
        config = cls()
        config.set_test_database(database_name, {
            'type': 'sqlite',
            'database': ':memory:'
        })
        return config