"""
MySQL数据库适配器 - 支持MySQL和MariaDB
使用aiomysql提供异步操作支持
设计原则：保持灵活性，避免硬编码
"""

import aiomysql
from typing import Any, Dict, List, Optional
from .base import DatabaseAdapter
from ..types.core_types import AbortSignal
from ..utils.type_converter import convert_rows_to_serializable


class MySQLAdapter(DatabaseAdapter):
    """
    MySQL/MariaDB数据库适配器
    - 支持连接池
    - 智能SQL转换
    - 完整的元数据查询
    - 兼容MariaDB和各种MySQL变体
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化MySQL适配器
        
        参数:
            config: 数据库配置字典，支持多种格式
        """
        self.config = config
        self.connection = None
        self.pool = None
        self.dialect_parser = None  # 初始化为None，需要时才创建
        
        # 提取连接参数（支持多种配置格式）
        self.connection_params = self._prepare_connection_params(config)
        
    def _prepare_connection_params(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        准备连接参数，支持多种配置格式
        保持最大灵活性，让Agent可以用各种方式连接
        """
        params = {}
        
        # 基本连接参数映射（支持多种别名）
        param_mapping = {
            'host': ['host', 'hostname', 'server'],
            'port': ['port'],
            'user': ['user', 'username', 'uid'],
            'password': ['password', 'pwd', 'pass'],
            'db': ['database', 'db', 'dbname', 'schema'],
            'charset': ['charset', 'character_set'],
        }
        
        for target, sources in param_mapping.items():
            for source in sources:
                if source in config:
                    params[target] = config[source]
                    break
        
        # 默认值
        params.setdefault('host', 'localhost')
        params.setdefault('port', 3306)
        params.setdefault('charset', 'utf8mb4')
        params.setdefault('autocommit', False)
        
        # 处理额外参数
        extra_params = config.get('params', {})
        for key, value in extra_params.items():
            if key not in params:
                params[key] = value
        
        # 连接池配置
        if 'pool_size' in config:
            params['minsize'] = config.get('pool_min', 1)
            params['maxsize'] = config.get('pool_size', 10)
        
        return params
        
    async def connect(self) -> None:
        """建立MySQL连接"""
        try:
            # 优先使用连接池
            if 'maxsize' in self.connection_params:
                self.pool = await aiomysql.create_pool(**self.connection_params)
                # 从池中获取一个连接用于基本操作
                self.connection = await self.pool.acquire()
            else:
                # 单个连接
                self.connection = await aiomysql.connect(**self.connection_params)
        except Exception as e:
            # 提供更友好的错误信息
            if "Can't connect" in str(e):
                raise Exception(
                    f"无法连接到MySQL服务器 {self.connection_params.get('host')}:{self.connection_params.get('port')}. "
                    f"请检查: 1) MySQL服务是否运行 2) 主机和端口是否正确 3) 防火墙设置"
                )
            elif "Access denied" in str(e):
                raise Exception(
                    f"MySQL认证失败: 用户 '{self.connection_params.get('user')}' 被拒绝访问. "
                    f"请检查用户名和密码是否正确"
                )
            else:
                raise Exception(f"MySQL连接失败: {str(e)}")
            
    async def disconnect(self) -> None:
        """关闭MySQL连接"""
        if self.connection:
            if self.pool:
                # 释放连接回池
                self.pool.release(self.connection)
                self.pool.close()
                await self.pool.wait_closed()
            else:
                self.connection.close()
            self.connection = None
            self.pool = None
            
    async def execute_query(
        self, 
        sql: str, 
        params: Optional[Dict[str, Any]] = None,
        signal: Optional[AbortSignal] = None
    ) -> Dict[str, Any]:
        """执行查询并返回结果"""
        if not self.connection:
            raise Exception("Database not connected")
            
        async with self.connection.cursor(aiomysql.DictCursor) as cursor:
            try:
                # 检查中止信号
                if signal and signal.aborted:
                    raise Exception("Query aborted")
                
                # MySQL使用%s作为参数占位符
                if params:
                    await cursor.execute(sql, list(params.values()))
                else:
                    await cursor.execute(sql)
                
                # 获取所有结果
                rows = await cursor.fetchall()
                
                # 获取列信息
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                # 转换为可序列化的类型
                serializable_rows = convert_rows_to_serializable(rows)
                
                return {
                    "columns": columns,
                    "rows": serializable_rows,
                    "row_count": len(rows)
                }
                
            except Exception as e:
                raise Exception(f"Query execution failed: {str(e)}")
            
    async def execute_command(
        self, 
        sql: str, 
        params: Optional[Dict[str, Any]] = None,
        signal: Optional[AbortSignal] = None
    ) -> Dict[str, Any]:
        """执行命令（INSERT、UPDATE、DELETE等）"""
        if not self.connection:
            raise Exception("Database not connected")
            
        async with self.connection.cursor() as cursor:
            try:
                if signal and signal.aborted:
                    raise Exception("Command aborted")
                
                if params:
                    await cursor.execute(sql, list(params.values()))
                else:
                    await cursor.execute(sql)
                
                # MySQL需要显式提交
                await self.connection.commit()
                
                return {
                    "affected_rows": cursor.rowcount,
                    "last_insert_id": cursor.lastrowid
                }
                
            except Exception as e:
                # 发生错误时回滚
                await self.connection.rollback()
                raise Exception(f"Command execution failed: {str(e)}")
            
    async def get_schema_info(self, schema_name: Optional[str] = None) -> Dict[str, Any]:
        """获取数据库结构信息"""
        try:
            # 获取当前数据库
            if not schema_name:
                result = await self.execute_query("SELECT DATABASE() as db")
                schema_name = result["rows"][0]["db"] if result["rows"] else None
            
            # 获取所有表和视图
            tables_query = """
                SELECT 
                    TABLE_NAME as name,
                    TABLE_TYPE as type,
                    TABLE_COMMENT as comment,
                    ENGINE as engine,
                    TABLE_ROWS as estimated_rows
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s
                ORDER BY TABLE_NAME
            """
            
            result = await self.execute_query(tables_query, {"schema": schema_name})
            tables_info = result["rows"]
            
            # 组织结果
            schema_info = {
                "database_name": schema_name,
                "tables": {},
                "views": {},
                "total_tables": 0,
                "total_views": 0
            }
            
            for table in tables_info:
                table_name = table["name"]
                if table["type"] == "BASE TABLE":
                    schema_info["tables"][table_name] = {
                        "name": table_name,
                        "engine": table["engine"],
                        "comment": table["comment"],
                        "estimated_rows": table["estimated_rows"]
                    }
                    schema_info["total_tables"] += 1
                elif table["type"] == "VIEW":
                    schema_info["views"][table_name] = {
                        "name": table_name,
                        "comment": table["comment"]
                    }
                    schema_info["total_views"] += 1
            
            # 获取数据库大小
            size_query = """
                SELECT 
                    SUM(DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024 as size_mb
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s
            """
            size_result = await self.execute_query(size_query, {"schema": schema_name})
            if size_result["rows"] and size_result["rows"][0]["size_mb"]:
                schema_info["size_mb"] = float(size_result["rows"][0]["size_mb"])
            
            return {
                "success": True,
                "schema": schema_info
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表结构信息"""
        try:
            # 获取列信息
            columns_query = """
                SELECT 
                    COLUMN_NAME as name,
                    DATA_TYPE as base_type,
                    COLUMN_TYPE as full_type,
                    IS_NULLABLE as nullable,
                    COLUMN_DEFAULT as default_value,
                    COLUMN_KEY as key_type,
                    EXTRA as extra,
                    COLUMN_COMMENT as comment
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """
            
            columns_result = await self.execute_query(columns_query, {"table": table_name})
            
            columns = []
            for col in columns_result["rows"]:
                columns.append({
                    "name": col["name"],
                    "type": col["full_type"],
                    "nullable": col["nullable"] == "YES",
                    "default": col["default_value"],
                    "primary_key": col["key_type"] == "PRI",
                    "unique": col["key_type"] == "UNI",
                    "auto_increment": "auto_increment" in col["extra"],
                    "comment": col["comment"]
                })
            
            # 获取索引信息
            index_query = """
                SELECT DISTINCT
                    INDEX_NAME as name,
                    NON_UNIQUE = 0 as is_unique,
                    INDEX_TYPE as type
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = %s
                AND INDEX_NAME != 'PRIMARY'
            """
            
            index_result = await self.execute_query(index_query, {"table": table_name})
            
            indexes = []
            for idx in index_result["rows"]:
                indexes.append({
                    "name": idx["name"],
                    "unique": bool(idx["is_unique"]),
                    "type": idx["type"]
                })
            
            # 获取外键信息
            fk_query = """
                SELECT 
                    CONSTRAINT_NAME as name,
                    COLUMN_NAME as column_name,
                    REFERENCED_TABLE_NAME as ref_table,
                    REFERENCED_COLUMN_NAME as ref_column
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = %s
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """
            
            fk_result = await self.execute_query(fk_query, {"table": table_name})
            
            foreign_keys = []
            for fk in fk_result["rows"]:
                foreign_keys.append({
                    "name": fk["name"],
                    "column": fk["column_name"],
                    "referenced_table": fk["ref_table"],
                    "referenced_column": fk["ref_column"]
                })
            
            return {
                "name": table_name,
                "columns": columns,
                "indexes": indexes,
                "foreign_keys": foreign_keys,
                "column_count": len(columns)
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def parse_sql(self, sql: str) -> Dict[str, Any]:
        """解析SQL语句 - MySQL特定"""
        try:
            # 尝试使用方言解析器（如果可用）
            if self.dialect_parser is None:
                try:
                    from .dialect_parser import SQLDialectParser, DatabaseDialect
                    self.dialect_parser = SQLDialectParser(self.config)
                    parsed = self.dialect_parser.parse_sql(sql, DatabaseDialect.MYSQL)
                    # 转换 ParsedSQL 对象为期望的字典格式
                    base_result = {
                        'sql_type': parsed.operation_type,
                        'tables': parsed.tables,
                        'has_limit': any('LIMIT' in cond.upper() for cond in parsed.conditions),
                        'has_where': bool(parsed.conditions),
                        'error_message': parsed.error_message
                    }
                except Exception:
                    # 如果解析器不可用或失败，使用备用方案
                    base_result = self._simple_parse_sql(sql)
            else:
                # 使用已有的解析器
                parsed = self.dialect_parser.parse_sql(sql, DatabaseDialect.MYSQL)
                base_result = {
                    'sql_type': parsed.operation_type,
                    'tables': parsed.tables,
                    'has_limit': any('LIMIT' in cond.upper() for cond in parsed.conditions),
                    'has_where': bool(parsed.conditions),
                    'error_message': parsed.error_message
                }
        except Exception:
            # 最终备用方案
            base_result = self._simple_parse_sql(sql)
        
        # 添加MySQL特定信息
        base_result["dialect_features"] = {
            "supports_limit": True,
            "supports_offset": True,
            "limit_syntax": "LIMIT offset, count",
            "supports_replace": True,  # MySQL支持REPLACE INTO
            "supports_on_duplicate_key": True,  # 支持ON DUPLICATE KEY UPDATE
            "supports_full_outer_join": False,  # MySQL不支持FULL OUTER JOIN
            "case_sensitive_identifiers": False,  # 标识符默认不区分大小写
            "quote_character": "`"  # 使用反引号引用标识符
        }
        
        return base_result
    
    def _simple_parse_sql(self, sql: str) -> Dict[str, Any]:
        """简单的SQL解析备用方案"""
        sql_stripped = sql.strip()
        sql_upper = sql_stripped.upper()
        
        # 使用正则表达式获取第一个SQL关键词
        import re
        match = re.match(r'^\s*(WITH\s+.*?\s+AS\s*\(.*?\)\s*)?(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|SHOW|DESCRIBE|DESC|EXPLAIN|ANALYZE|SET|USE|GRANT|REVOKE|CALL|EXECUTE|TRUNCATE|REPLACE)', sql_upper)
        
        sql_type = match.group(2) if match else 'UNKNOWN'
        
        return {
            'sql_type': sql_type,
            'tables': [],  # 简化实现
            'has_limit': bool(re.search(r'\bLIMIT\b', sql_upper)),
            'has_where': bool(re.search(r'\bWHERE\b', sql_upper)),
            'error_message': None
        }
    
    def get_dialect(self) -> str:
        """获取数据库方言"""
        return "mysql"
        
    async def get_version(self) -> Optional[str]:
        """获取MySQL版本信息"""
        try:
            result = await self.execute_query("SELECT VERSION() as version")
            if result['rows']:
                version = result['rows'][0]['version']
                # 判断是MySQL还是MariaDB
                if 'MariaDB' in version:
                    return f"MariaDB {version}"
                else:
                    return f"MySQL {version}"
        except Exception:
            pass
        return None
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            await self.execute_query("SELECT 1")
            return True
        except Exception:
            return False
    
    # 事务管理
    async def begin_transaction(self) -> None:
        """开始事务"""
        if not self.connection:
            raise Exception("Database not connected")
        await self.connection.begin()
        
    async def commit(self) -> None:
        """提交事务"""
        if not self.connection:
            raise Exception("Database not connected")
        await self.connection.commit()
        
    async def rollback(self) -> None:
        """回滚事务"""
        if not self.connection:
            raise Exception("Database not connected")
        await self.connection.rollback()