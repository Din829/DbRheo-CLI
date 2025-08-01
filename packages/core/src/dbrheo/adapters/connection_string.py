"""
连接字符串解析器 - 智能识别各种数据库连接格式
支持多种格式，让Agent能灵活连接数据库
设计原则：灵活性优先，避免硬编码
"""

import re
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs, unquote


class ConnectionStringParser:
    """
    通用连接字符串解析器
    支持多种格式：
    - 标准URL格式：mysql://user:pass@host:port/database
    - JDBC格式：jdbc:postgresql://host:port/database
    - ODBC格式：Driver={SQL Server};Server=host;Database=db;
    - 键值对格式：host=localhost;port=5432;database=mydb;
    """
    
    # 数据库类型映射（灵活识别各种别名）
    DB_TYPE_ALIASES = {
        'mysql': ['mysql', 'mariadb', 'aurora-mysql'],
        'postgresql': ['postgresql', 'postgres', 'pg', 'pgsql', 'aurora-postgresql'],
        'sqlite': ['sqlite', 'sqlite3'],
        'sqlserver': ['sqlserver', 'mssql', 'sql-server', 'ms-sql-server', 'sql_server'],
        'oracle': ['oracle', 'ora', 'orcl'],
        'db2': ['db2', 'ibm-db2', 'ibmdb2'],
        'clickhouse': ['clickhouse', 'ch'],
        'mongodb': ['mongodb', 'mongo'],  # 预留NoSQL支持
    }
    
    @classmethod
    def parse(cls, connection_string: str) -> Dict[str, Any]:
        """
        智能解析连接字符串
        返回标准化的连接配置
        
        Args:
            connection_string: 各种格式的连接字符串
            
        Returns:
            标准化的连接配置字典
        """
        connection_string = connection_string.strip()
        
        # 尝试多种解析方法
        # 1. 先尝试URL格式（最常见）
        result = cls._parse_url_format(connection_string)
        if result:
            return result
            
        # 2. 尝试JDBC格式
        result = cls._parse_jdbc_format(connection_string)
        if result:
            return result
            
        # 3. 尝试键值对格式
        result = cls._parse_key_value_format(connection_string)
        if result:
            return result
            
        # 4. 尝试ODBC格式
        result = cls._parse_odbc_format(connection_string)
        if result:
            return result
            
        # 如果都失败，返回原始字符串让适配器自己处理
        return {
            'type': 'unknown',
            'connection_string': connection_string,
            'raw': True
        }
    
    @classmethod
    def _parse_url_format(cls, connection_string: str) -> Optional[Dict[str, Any]]:
        """解析URL格式：mysql://user:pass@host:port/database?param=value"""
        try:
            # 处理特殊的SQLite格式
            if connection_string.startswith('sqlite:///'):
                return {
                    'type': 'sqlite',
                    'database': connection_string.replace('sqlite:///', ''),
                    'is_memory': connection_string == 'sqlite:///:memory:'
                }
            
            parsed = urlparse(connection_string)
            if not parsed.scheme:
                return None
                
            # 识别数据库类型
            db_type = cls._normalize_db_type(parsed.scheme)
            if not db_type:
                return None
                
            config = {
                'type': db_type,
                'host': parsed.hostname or 'localhost',
                'port': parsed.port or cls._get_default_port(db_type),
                'database': parsed.path.lstrip('/') if parsed.path else None,
                'username': unquote(parsed.username) if parsed.username else None,
                'password': unquote(parsed.password) if parsed.password else None,
            }
            
            # 解析查询参数
            if parsed.query:
                params = parse_qs(parsed.query)
                # 展平单值参数
                config['params'] = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
            else:
                config['params'] = {}
                
            return config
            
        except Exception:
            return None
    
    @classmethod
    def _parse_jdbc_format(cls, connection_string: str) -> Optional[Dict[str, Any]]:
        """解析JDBC格式：jdbc:postgresql://host:port/database"""
        if not connection_string.startswith('jdbc:'):
            return None
            
        # 去掉jdbc:前缀，使用URL解析
        url_part = connection_string[5:]
        return cls._parse_url_format(url_part)
    
    @classmethod
    def _parse_key_value_format(cls, connection_string: str) -> Optional[Dict[str, Any]]:
        """解析键值对格式：host=localhost;port=5432;database=mydb;user=postgres;password=pass"""
        # 支持分号或空格分隔
        if '=' not in connection_string:
            return None
            
        config = {}
        # 支持多种分隔符
        pairs = re.split(r'[;&\s]+', connection_string)
        
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                key = key.strip().lower()
                value = value.strip()
                
                # 映射常见的键名变体
                if key in ['host', 'server', 'hostname']:
                    config['host'] = value
                elif key in ['port']:
                    config['port'] = int(value)
                elif key in ['database', 'db', 'dbname', 'initial catalog']:
                    config['database'] = value
                elif key in ['user', 'username', 'uid', 'user id']:
                    config['username'] = value
                elif key in ['password', 'pwd', 'pass']:
                    config['password'] = value
                elif key in ['driver', 'provider']:
                    # 从驱动名推断数据库类型
                    db_type = cls._infer_type_from_driver(value)
                    if db_type:
                        config['type'] = db_type
                else:
                    # 保存其他参数
                    if 'params' not in config:
                        config['params'] = {}
                    config['params'][key] = value
        
        # 如果没有明确的类型，尝试从其他信息推断
        if 'type' not in config:
            config['type'] = cls._infer_db_type(config)
            
        return config if config.get('type') else None
    
    @classmethod
    def _parse_odbc_format(cls, connection_string: str) -> Optional[Dict[str, Any]]:
        """解析ODBC格式：Driver={SQL Server};Server=host;Database=db;"""
        # ODBC格式通常包含Driver=
        if 'Driver=' not in connection_string and 'driver=' not in connection_string:
            return None
            
        # 提取大括号中的内容
        connection_string = re.sub(r'\{([^}]+)\}', r'\1', connection_string)
        
        # 使用键值对解析
        return cls._parse_key_value_format(connection_string)
    
    @classmethod
    def _normalize_db_type(cls, db_type: str) -> Optional[str]:
        """标准化数据库类型名称"""
        db_type = db_type.lower()
        
        # 去除常见前缀
        for prefix in ['jdbc:', 'odbc:']:
            if db_type.startswith(prefix):
                db_type = db_type[len(prefix):]
        
        # 查找匹配的标准类型
        for standard_type, aliases in cls.DB_TYPE_ALIASES.items():
            if db_type in aliases:
                return standard_type
                
        return None
    
    @classmethod
    def _get_default_port(cls, db_type: str) -> int:
        """获取数据库默认端口"""
        default_ports = {
            'mysql': 3306,
            'postgresql': 5432,
            'sqlserver': 1433,
            'oracle': 1521,
            'db2': 50000,
            'clickhouse': 9000,
            'mongodb': 27017,
        }
        return default_ports.get(db_type, 0)
    
    @classmethod
    def _infer_type_from_driver(cls, driver: str) -> Optional[str]:
        """从驱动名称推断数据库类型"""
        driver = driver.lower()
        
        driver_mapping = {
            'sql server': 'sqlserver',
            'mysql': 'mysql',
            'postgresql': 'postgresql',
            'psql': 'postgresql',
            'oracle': 'oracle',
            'db2': 'db2',
            'sqlite': 'sqlite',
        }
        
        for key, db_type in driver_mapping.items():
            if key in driver:
                return db_type
                
        return None
    
    @classmethod
    def _infer_db_type(cls, config: Dict[str, Any]) -> Optional[str]:
        """从配置信息推断数据库类型"""
        # 从端口推断
        port = config.get('port')
        if port:
            port_mapping = {
                3306: 'mysql',
                5432: 'postgresql',
                1433: 'sqlserver',
                1521: 'oracle',
                50000: 'db2',
            }
            db_type = port_mapping.get(port)
            if db_type:
                return db_type
        
        # 从文件扩展名推断（SQLite）
        database = config.get('database', '')
        if database.endswith(('.db', '.sqlite', '.sqlite3')):
            return 'sqlite'
            
        return None
    
    @classmethod
    def build_connection_string(cls, config: Dict[str, Any]) -> str:
        """
        从配置构建标准连接字符串
        这是parse的反向操作
        """
        db_type = config.get('type', 'unknown')
        
        if db_type == 'sqlite':
            database = config.get('database', ':memory:')
            return f"sqlite:///{database}"
        
        # 构建标准URL格式
        parts = [f"{db_type}://"]
        
        # 用户名和密码
        if config.get('username'):
            parts.append(config['username'])
            if config.get('password'):
                parts.append(f":{config['password']}")
            parts.append('@')
        
        # 主机和端口
        host = config.get('host', 'localhost')
        port = config.get('port')
        parts.append(host)
        if port and port != cls._get_default_port(db_type):
            parts.append(f":{port}")
        
        # 数据库名
        if config.get('database'):
            parts.append(f"/{config['database']}")
        
        # 查询参数
        params = config.get('params', {})
        if params:
            param_str = '&'.join(f"{k}={v}" for k, v in params.items())
            parts.append(f"?{param_str}")
        
        return ''.join(parts)