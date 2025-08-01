"""
数据库适配器工厂 - 灵活的适配器创建和管理
支持动态注册、连接字符串解析、自动驱动检测
设计原则：避免硬编码，保持最大灵活性
"""

import asyncio
import importlib
import inspect
from typing import Optional, Dict, Any, Type, Union, Callable
from ..config.base import DatabaseConfig
from .base import DatabaseAdapter
from .sqlite_adapter import SQLiteAdapter
from .connection_string import ConnectionStringParser
from ..utils.debug_logger import log_info


# 适配器注册表（避免硬编码）
_adapter_registry: Dict[str, Type[DatabaseAdapter]] = {}

# 适配器实例缓存
_adapter_cache: Dict[str, DatabaseAdapter] = {}

# 活动连接缓存（供database_connect_tool使用）
_active_connections: Dict[str, DatabaseAdapter] = {}

# 驱动检测函数注册表
_driver_checkers: Dict[str, Callable[[], bool]] = {}


def register_adapter(db_type: str, adapter_class: Type[DatabaseAdapter], 
                    driver_checker: Optional[Callable[[], bool]] = None):
    """
    注册数据库适配器
    
    Args:
        db_type: 数据库类型标识
        adapter_class: 适配器类
        driver_checker: 检查驱动是否可用的函数
    """
    _adapter_registry[db_type] = adapter_class
    if driver_checker:
        _driver_checkers[db_type] = driver_checker


def _check_driver_available(db_type: str) -> tuple[bool, str]:
    """
    检查数据库驱动是否可用
    
    Returns:
        (是否可用, 错误信息或建议)
    """
    if db_type in _driver_checkers:
        try:
            # 调用检查函数，确保返回bool而不是模块对象
            result = _driver_checkers[db_type]()
            # 如果检查函数错误地返回了模块对象，转换为True
            if result is not None and not isinstance(result, bool):
                return True, ""
            return bool(result), ""
        except Exception as e:
            return False, str(e)
    
    # 默认驱动检查
    driver_packages = {
        'mysql': ['aiomysql', 'mysql-connector-python', 'pymysql'],
        'postgresql': ['asyncpg', 'psycopg', 'psycopg2'],
        'sqlserver': ['pyodbc', 'pymssql'],
        'oracle': ['cx_Oracle', 'oracledb'],
        'db2': ['ibm_db', 'ibm_db_sa'],
    }
    
    if db_type in driver_packages:
        packages = driver_packages[db_type]
        for package in packages:
            try:
                importlib.import_module(package.replace('-', '_'))
                return True, ""
            except ImportError:
                continue
        
        # 提供友好的安装建议
        suggestions = " 或 ".join([f"pip install {pkg}" for pkg in packages[:2]])
        return False, f"未找到{db_type}驱动，请安装: {suggestions}"
    
    return True, ""  # 未知类型，假设可用


def register_active_connection(alias: str, adapter: DatabaseAdapter):
    """注册活动连接（供database_connect_tool使用）"""
    global _active_connections
    log_info("AdapterFactory", f"register_active_connection: alias={alias}, _active_connections type={type(_active_connections)}")
    if _active_connections is None:
        log_info("AdapterFactory", "_active_connections was None, initializing to empty dict")
        _active_connections = {}
    _active_connections[alias] = adapter
    log_info("AdapterFactory", f"Successfully registered connection: {alias}, total connections: {list(_active_connections.keys())}")


def get_active_connection(alias: str) -> Optional[DatabaseAdapter]:
    """获取活动连接"""
    global _active_connections
    log_info("AdapterFactory", f"get_active_connection: alias={alias}, _active_connections type={type(_active_connections)}")
    if _active_connections is None:
        log_info("AdapterFactory", "_active_connections was None, initializing to empty dict")
        _active_connections = {}
    log_info("AdapterFactory", f"Current active connections: {list(_active_connections.keys())}")
    result = _active_connections.get(alias)
    log_info("AdapterFactory", f"Found connection for {alias}: {result is not None}")
    return result


async def get_adapter(
    config_or_connection_string: Union[DatabaseConfig, str, Dict[str, Any]], 
    database_name: Optional[str] = None
) -> DatabaseAdapter:
    """
    获取数据库适配器实例 - 支持多种输入格式
    
    参数:
        config_or_connection_string: 
            - DatabaseConfig对象（传统方式）
            - 连接字符串（Agent友好）
            - 配置字典（灵活方式）
        database_name: 可选的数据库名称（仅用于DatabaseConfig方式）
        
    返回:
        DatabaseAdapter实例
    """
    # 0. 首先检查是否有活动连接（database_connect_tool创建的）
    log_info("AdapterFactory", f"get_adapter called with: config_type={type(config_or_connection_string)}, database_name={database_name}")
    if isinstance(config_or_connection_string, DatabaseConfig) and database_name:
        # 先检查是否是活动连接的别名
        active_adapter = get_active_connection(database_name)
        if active_adapter:
            log_info("AdapterFactory", f"Found active adapter for {database_name}")
            return active_adapter
        else:
            log_info("AdapterFactory", f"No active adapter found for {database_name}, will try other methods")
        
        # 检查是否是连接字符串（让Agent可以直接使用）
        if "://" in database_name or "=" in database_name:
            # 这是一个连接字符串，不是别名
            try:
                parser = ConnectionStringParser()
                connection_config = parser.parse(database_name)
                # 创建新的适配器
                db_type = connection_config.get('type', 'sqlite').lower()
                available, error_msg = _check_driver_available(db_type)
                if not available:
                    raise RuntimeError(f"数据库驱动不可用: {error_msg}")
                adapter = await _create_adapter(db_type, connection_config)
                # 缓存适配器
                _adapter_cache[database_name] = adapter
                return adapter
            except Exception as e:
                # 如果解析失败，继续原来的逻辑
                pass
    
    # 1. 解析输入，获取标准化配置
    if isinstance(config_or_connection_string, str):
        # Agent传入连接字符串
        parser = ConnectionStringParser()
        connection_config = parser.parse(config_or_connection_string)
        cache_key = config_or_connection_string
    elif isinstance(config_or_connection_string, dict):
        # 直接传入配置字典
        connection_config = config_or_connection_string
        cache_key = f"{connection_config.get('type')}:{connection_config.get('host')}:{connection_config.get('database')}"
    else:
        # 传统的DatabaseConfig方式
        config = config_or_connection_string
        connection_config = _get_connection_config(config, database_name)
        cache_key = f"{database_name or 'default'}:{connection_config.get('type')}:{connection_config.get('database')}"
    
    # 2. 检查缓存
    if cache_key in _adapter_cache:
        adapter = _adapter_cache[cache_key]
        # 验证连接是否仍然有效
        try:
            if hasattr(adapter, 'health_check'):
                await adapter.health_check()
            return adapter
        except Exception:
            # 连接失效，删除缓存
            del _adapter_cache[cache_key]
    
    # 3. 确定数据库类型
    db_type = connection_config.get('type', 'sqlite').lower()
    
    # 4. 检查驱动可用性
    available, error_msg = _check_driver_available(db_type)
    if not available:
        raise RuntimeError(f"数据库驱动不可用: {error_msg}")
    
    # 5. 创建适配器
    adapter = await _create_adapter(db_type, connection_config)
    
    # 6. 缓存适配器
    _adapter_cache[cache_key] = adapter
    
    return adapter


async def _create_adapter(db_type: str, connection_config: Dict[str, Any]) -> DatabaseAdapter:
    """
    创建适配器实例
    """
    # 优先使用注册的适配器
    if db_type in _adapter_registry:
        adapter_class = _adapter_registry[db_type]
        return adapter_class(connection_config)
    
    # 动态加载适配器（如果存在）
    try:
        module_name = f".{db_type}_adapter"
        module = importlib.import_module(module_name, package='dbrheo.adapters')
        
        # 查找适配器类
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, DatabaseAdapter) and 
                obj != DatabaseAdapter):
                return obj(connection_config)
                
    except ImportError:
        pass
    
    # 最后尝试通用适配器（如果实现了的话）
    if hasattr(DatabaseAdapter, 'create_generic'):
        return DatabaseAdapter.create_generic(db_type, connection_config)
    
    raise ValueError(
        f"不支持的数据库类型: {db_type}。"
        f"已注册的类型: {', '.join(_adapter_registry.keys())}"
    )


def _get_connection_config(config: DatabaseConfig, database_name: Optional[str]) -> Dict[str, Any]:
    """
    从DatabaseConfig获取连接配置
    """
    if database_name:
        # 尝试多种配置路径
        paths = [
            f"databases.{database_name}",
            f"database.{database_name}",
            database_name
        ]
        
        for path in paths:
            connection_config = config.get(path)
            if connection_config:
                break
        else:
            # 如果是连接别名形式（如 xxx_conn），提供更友好的错误信息
            if database_name.endswith('_conn') or database_name.endswith('_db'):
                raise ValueError(f"未找到数据库配置: {database_name}。请先使用 database_connect 工具建立连接，或直接提供连接字符串。")
            else:
                raise ValueError(f"未找到数据库配置: {database_name}")
    else:
        # 使用默认连接
        default_db = config.get("default_database", "default")
        connection_config = config.get(f"databases.{default_db}")
        
        if not connection_config:
            # 尝试直接的database_url
            db_url = config.get("database_url")
            if db_url:
                parser = ConnectionStringParser()
                connection_config = parser.parse(db_url)
            else:
                # 最后的默认配置
                connection_config = {
                    "type": "sqlite",
                    "database": config.get("database_path", ":memory:")
                }
    
    return connection_config


def clear_adapter_cache():
    """清除适配器缓存"""
    global _adapter_cache
    # 尝试优雅关闭所有连接
    for adapter in _adapter_cache.values():
        try:
            if hasattr(adapter, 'disconnect'):
                # 同步关闭，避免异步上下文问题
                import asyncio
                if asyncio.iscoroutinefunction(adapter.disconnect):
                    asyncio.create_task(adapter.disconnect())
        except Exception:
            pass
    
    _adapter_cache = {}


def list_supported_databases() -> Dict[str, Dict[str, Any]]:
    """
    列出所有支持的数据库类型和状态
    Agent可以调用此方法了解可用的数据库
    """
    result = {}
    
    # 已注册的适配器
    for db_type in _adapter_registry:
        available, msg = _check_driver_available(db_type)
        result[db_type] = {
            'registered': True,
            'driver_available': available,
            'message': msg
        }
    
    # 内置支持但未注册的
    builtin_types = ['sqlite', 'mysql', 'postgresql', 'sqlserver', 'oracle']
    for db_type in builtin_types:
        if db_type not in result:
            available, msg = _check_driver_available(db_type)
            result[db_type] = {
                'registered': False,
                'driver_available': available,
                'message': msg
            }
    
    return result


# 注册内置适配器
register_adapter('sqlite', SQLiteAdapter)

# 注册新实现的适配器
try:
    from .mysql_adapter import MySQLAdapter
    # 驱动检查函数必须返回bool，不能返回模块对象
    def check_mysql_driver():
        try:
            importlib.import_module('aiomysql')
            return True
        except ImportError:
            return False
    
    register_adapter('mysql', MySQLAdapter, check_mysql_driver)
    register_adapter('mariadb', MySQLAdapter, check_mysql_driver)
except ImportError:
    pass

try:
    from .postgresql_adapter import PostgreSQLAdapter
    # 驱动检查函数必须返回bool
    def check_pg_driver():
        try:
            importlib.import_module('asyncpg')
            return True
        except ImportError:
            return False
    
    register_adapter('postgresql', PostgreSQLAdapter, check_pg_driver)
    register_adapter('postgres', PostgreSQLAdapter, check_pg_driver)
    register_adapter('pg', PostgreSQLAdapter, check_pg_driver)
except ImportError:
    pass