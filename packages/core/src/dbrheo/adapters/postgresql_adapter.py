"""
PostgreSQL数据库适配器 - 支持PostgreSQL及其衍生版本
使用asyncpg提供高性能异步操作
设计原则：充分利用PostgreSQL的高级特性，保持灵活性
"""

import asyncpg
import json
from typing import Any, Dict, List, Optional, Union
from .base import DatabaseAdapter
from ..types.core_types import AbortSignal
from ..utils.type_converter import convert_to_serializable


class PostgreSQLAdapter(DatabaseAdapter):
    """
    PostgreSQL数据库适配器
    - 使用asyncpg高性能驱动
    - 支持PostgreSQL高级特性（JSON、数组、自定义类型等）
    - 智能连接池管理
    - 完整的元数据查询
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化PostgreSQL适配器
        
        参数:
            config: 数据库配置字典
        """
        self.config = config
        self.connection = None
        self.pool = None
        self.dialect_parser = None  # 初始化为None，需要时才创建
        
        # 准备连接参数
        self.connection_params = self._prepare_connection_params(config)
        
    def _prepare_connection_params(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        准备连接参数，支持多种配置格式
        asyncpg使用不同的参数名称
        """
        params = {}
        
        # asyncpg的参数映射
        param_mapping = {
            'host': ['host', 'hostname', 'server'],
            'port': ['port'],
            'user': ['user', 'username', 'uid'],
            'password': ['password', 'pwd', 'pass'],
            'database': ['database', 'db', 'dbname'],
            'ssl': ['ssl', 'sslmode'],
        }
        
        for target, sources in param_mapping.items():
            for source in sources:
                if source in config:
                    value = config[source]
                    # 处理SSL模式
                    if target == 'ssl' and isinstance(value, str):
                        # 转换sslmode为bool
                        value = value not in ['disable', 'allow', 'prefer']
                    params[target] = value
                    break
        
        # 默认值
        params.setdefault('host', 'localhost')
        params.setdefault('port', 5432)
        
        # 处理额外参数
        extra_params = config.get('params', {})
        
        # PostgreSQL特定参数
        pg_params = ['statement_timeout', 'command_timeout', 'server_settings']
        for param in pg_params:
            if param in extra_params:
                params[param] = extra_params[param]
        
        # 连接池配置
        if 'pool_size' in config:
            params['min_size'] = config.get('pool_min', 1)
            params['max_size'] = config.get('pool_size', 10)
        
        return params
        
    async def connect(self) -> None:
        """建立PostgreSQL连接"""
        try:
            # 判断是否使用连接池
            if 'max_size' in self.connection_params:
                pool_params = self.connection_params.copy()
                # asyncpg的连接池参数名称不同
                pool_params['min_size'] = pool_params.pop('min_size', 1)
                pool_params['max_size'] = pool_params.pop('max_size', 10)
                
                self.pool = await asyncpg.create_pool(**pool_params)
                # 从池中获取连接
                self.connection = await self.pool.acquire()
            else:
                # 单个连接
                self.connection = await asyncpg.connect(**self.connection_params)
                
        except Exception as e:
            # 提供友好的错误信息
            error_str = str(e)
            if "could not connect" in error_str or "Connection refused" in error_str:
                raise Exception(
                    f"无法连接到PostgreSQL服务器 {self.connection_params.get('host')}:{self.connection_params.get('port')}. "
                    f"请检查: 1) PostgreSQL服务是否运行 2) 主机和端口是否正确 3) pg_hba.conf配置"
                )
            elif "authentication failed" in error_str or "password authentication failed" in error_str:
                raise Exception(
                    f"PostgreSQL认证失败: 用户 '{self.connection_params.get('user')}' 认证失败. "
                    f"请检查用户名和密码是否正确"
                )
            elif "database" in error_str and "does not exist" in error_str:
                raise Exception(
                    f"数据库 '{self.connection_params.get('database')}' 不存在. "
                    f"请先创建数据库或连接到已存在的数据库"
                )
            else:
                raise Exception(f"PostgreSQL连接失败: {error_str}")
            
    async def disconnect(self) -> None:
        """关闭PostgreSQL连接"""
        if self.connection:
            if self.pool:
                # 释放连接回池
                await self.pool.release(self.connection)
                await self.pool.close()
            else:
                await self.connection.close()
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
            
        try:
            # 检查中止信号
            if signal and signal.aborted:
                raise Exception("Query aborted")
            
            # PostgreSQL使用$1, $2等作为参数占位符
            if params:
                # 转换参数格式
                values = list(params.values())
                # 替换SQL中的参数占位符
                for i, (key, value) in enumerate(params.items(), 1):
                    sql = sql.replace(f":{key}", f"${i}")
                    sql = sql.replace(f"%({key})s", f"${i}")
                
                rows = await self.connection.fetch(sql, *values)
            else:
                rows = await self.connection.fetch(sql)
            
            # asyncpg返回Record对象，需要转换
            result_rows = []
            columns = []
            
            if rows:
                # 获取列名
                columns = list(rows[0].keys())
                # 转换每一行
                for row in rows:
                    result_rows.append(dict(row))
            
            # 转换为可序列化的类型
            serializable_rows = [convert_to_serializable(row) for row in result_rows]
            
            return {
                "columns": columns,
                "rows": serializable_rows,
                "row_count": len(result_rows)
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
            
        try:
            if signal and signal.aborted:
                raise Exception("Command aborted")
            
            # 参数处理
            if params:
                values = list(params.values())
                for i, (key, value) in enumerate(params.items(), 1):
                    sql = sql.replace(f":{key}", f"${i}")
                    sql = sql.replace(f"%({key})s", f"${i}")
                
                result = await self.connection.execute(sql, *values)
            else:
                result = await self.connection.execute(sql)
            
            # 解析受影响的行数
            # PostgreSQL返回格式如 "UPDATE 5"
            affected_rows = 0
            if result:
                parts = result.split()
                if len(parts) >= 2 and parts[-1].isdigit():
                    affected_rows = int(parts[-1])
            
            # PostgreSQL没有lastrowid概念，但可以使用RETURNING子句
            return {
                "affected_rows": affected_rows,
                "last_insert_id": None  # 需要使用RETURNING id获取
            }
            
        except Exception as e:
            raise Exception(f"Command execution failed: {str(e)}")
            
    async def get_schema_info(self, schema_name: Optional[str] = None) -> Dict[str, Any]:
        """获取数据库结构信息"""
        try:
            # 默认使用public schema
            if not schema_name:
                schema_name = 'public'
            
            # 获取所有表
            tables_query = """
                SELECT 
                    schemaname,
                    tablename as name,
                    tableowner as owner,
                    hasindexes,
                    hastriggers
                FROM pg_catalog.pg_tables
                WHERE schemaname = $1
                ORDER BY tablename
            """
            
            tables_result = await self.execute_query(tables_query, {"schema": schema_name})
            
            # 获取所有视图
            views_query = """
                SELECT 
                    schemaname,
                    viewname as name,
                    viewowner as owner,
                    definition
                FROM pg_catalog.pg_views
                WHERE schemaname = $1
                ORDER BY viewname
            """
            
            views_result = await self.execute_query(views_query, {"schema": schema_name})
            
            # 获取数据库大小
            size_query = """
                SELECT pg_database_size(current_database()) / 1024 / 1024 as size_mb
            """
            size_result = await self.execute_query(size_query)
            
            # 组织结果
            schema_info = {
                "database_name": self.connection_params.get('database'),
                "schema_name": schema_name,
                "tables": {},
                "views": {},
                "total_tables": 0,
                "total_views": 0
            }
            
            # 处理表信息
            for table in tables_result["rows"]:
                table_name = table["name"]
                # 获取表的行数估计
                count_query = f"""
                    SELECT reltuples::BIGINT as estimated_rows
                    FROM pg_class
                    WHERE oid = '{schema_name}.{table_name}'::regclass
                """
                try:
                    count_result = await self.execute_query(count_query)
                    estimated_rows = count_result["rows"][0]["estimated_rows"] if count_result["rows"] else 0
                except:
                    estimated_rows = 0
                
                schema_info["tables"][table_name] = {
                    "name": table_name,
                    "owner": table["owner"],
                    "has_indexes": table["hasindexes"],
                    "has_triggers": table["hastriggers"],
                    "estimated_rows": estimated_rows
                }
                schema_info["total_tables"] += 1
            
            # 处理视图信息
            for view in views_result["rows"]:
                view_name = view["name"]
                schema_info["views"][view_name] = {
                    "name": view_name,
                    "owner": view["owner"],
                    "definition": view["definition"][:200] + "..." if len(view["definition"]) > 200 else view["definition"]
                }
                schema_info["total_views"] += 1
            
            # 添加数据库大小
            if size_result["rows"]:
                schema_info["size_mb"] = float(size_result["rows"][0]["size_mb"])
            
            # 获取可用的扩展
            extensions_query = """
                SELECT extname, extversion 
                FROM pg_extension 
                ORDER BY extname
            """
            extensions_result = await self.execute_query(extensions_query)
            schema_info["extensions"] = [
                f"{ext['extname']} v{ext['extversion']}" 
                for ext in extensions_result["rows"]
            ]
            
            return {
                "success": True,
                "schema": schema_info
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    async def get_table_info(self, table_name: str, schema_name: str = 'public') -> Dict[str, Any]:
        """获取表结构信息"""
        try:
            # 获取列信息
            columns_query = """
                SELECT 
                    a.attname as name,
                    pg_catalog.format_type(a.atttypid, a.atttypmod) as type,
                    NOT a.attnotnull as nullable,
                    pg_get_expr(d.adbin, d.adrelid) as default_value,
                    col_description(a.attrelid, a.attnum) as comment
                FROM pg_attribute a
                LEFT JOIN pg_attrdef d ON a.attrelid = d.adrelid AND a.attnum = d.adnum
                WHERE a.attrelid = $1::regclass
                AND a.attnum > 0 
                AND NOT a.attisdropped
                ORDER BY a.attnum
            """
            
            full_table_name = f"{schema_name}.{table_name}"
            columns_result = await self.execute_query(columns_query, {"table": full_table_name})
            
            # 获取主键信息
            pk_query = """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = $1::regclass
                AND i.indisprimary
            """
            pk_result = await self.execute_query(pk_query, {"table": full_table_name})
            pk_columns = {row["attname"] for row in pk_result["rows"]}
            
            # 获取唯一约束
            unique_query = """
                SELECT a.attname, i.indisunique
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = $1::regclass
                AND i.indisunique AND NOT i.indisprimary
            """
            unique_result = await self.execute_query(unique_query, {"table": full_table_name})
            unique_columns = {row["attname"] for row in unique_result["rows"]}
            
            # 组织列信息
            columns = []
            for col in columns_result["rows"]:
                col_info = {
                    "name": col["name"],
                    "type": col["type"],
                    "nullable": col["nullable"],
                    "default": col["default_value"],
                    "primary_key": col["name"] in pk_columns,
                    "unique": col["name"] in unique_columns,
                    "comment": col["comment"]
                }
                
                # 检查是否是自增列
                if col["default_value"] and "nextval" in str(col["default_value"]):
                    col_info["auto_increment"] = True
                else:
                    col_info["auto_increment"] = False
                
                columns.append(col_info)
            
            # 获取索引信息
            index_query = """
                SELECT 
                    i.relname as name,
                    ix.indisunique as is_unique,
                    am.amname as type
                FROM pg_class t
                JOIN pg_index ix ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_am am ON i.relam = am.oid
                WHERE t.relname = $1
                AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = $2)
                AND NOT ix.indisprimary
            """
            
            index_result = await self.execute_query(
                index_query, 
                {"table": table_name, "schema": schema_name}
            )
            
            indexes = []
            for idx in index_result["rows"]:
                indexes.append({
                    "name": idx["name"],
                    "unique": idx["is_unique"],
                    "type": idx["type"]
                })
            
            # 获取外键信息
            fk_query = """
                SELECT
                    conname as name,
                    a1.attname as column_name,
                    cl2.relname as ref_table,
                    a2.attname as ref_column
                FROM pg_constraint con
                JOIN pg_class cl1 ON con.conrelid = cl1.oid
                JOIN pg_class cl2 ON con.confrelid = cl2.oid
                JOIN pg_attribute a1 ON a1.attrelid = con.conrelid AND a1.attnum = ANY(con.conkey)
                JOIN pg_attribute a2 ON a2.attrelid = con.confrelid AND a2.attnum = ANY(con.confkey)
                WHERE con.contype = 'f'
                AND cl1.relname = $1
                AND cl1.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = $2)
            """
            
            fk_result = await self.execute_query(
                fk_query, 
                {"table": table_name, "schema": schema_name}
            )
            
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
                "schema": schema_name,
                "columns": columns,
                "indexes": indexes,
                "foreign_keys": foreign_keys,
                "column_count": len(columns)
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def parse_sql(self, sql: str) -> Dict[str, Any]:
        """解析SQL语句 - PostgreSQL特定"""
        try:
            # 尝试使用方言解析器（如果可用）
            if self.dialect_parser is None:
                try:
                    from .dialect_parser import SQLDialectParser, DatabaseDialect
                    self.dialect_parser = SQLDialectParser(self.config)
                    parsed = self.dialect_parser.parse_sql(sql, DatabaseDialect.POSTGRESQL)
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
                parsed = self.dialect_parser.parse_sql(sql, DatabaseDialect.POSTGRESQL)
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
        
        # 添加PostgreSQL特定信息
        base_result["dialect_features"] = {
            "supports_limit": True,
            "supports_offset": True,
            "limit_syntax": "LIMIT count OFFSET offset",
            "supports_returning": True,  # 支持RETURNING子句
            "supports_arrays": True,  # 支持数组类型
            "supports_json": True,  # 原生JSON支持
            "supports_full_outer_join": True,  # 支持FULL OUTER JOIN
            "supports_window_functions": True,  # 窗口函数
            "case_sensitive_identifiers": True,  # 标识符区分大小写（带引号时）
            "quote_character": '"'  # 使用双引号引用标识符
        }
        
        return base_result
    
    def _simple_parse_sql(self, sql: str) -> Dict[str, Any]:
        """简单的SQL解析备用方案"""
        sql_stripped = sql.strip()
        sql_upper = sql_stripped.upper()
        
        # 使用正则表达式获取第一个SQL关键词，支持PostgreSQL特有的命令
        import re
        match = re.match(r'^\s*(WITH\s+.*?\s+AS\s*\(.*?\)\s*)?(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|COPY|VACUUM|ANALYZE|EXPLAIN|GRANT|REVOKE|BEGIN|COMMIT|ROLLBACK|SAVEPOINT|SET|RESET|SHOW|DO|CALL|COMMENT|CLUSTER|REINDEX|REFRESH)', sql_upper)
        
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
        return "postgresql"
        
    async def get_version(self) -> Optional[str]:
        """获取PostgreSQL版本信息"""
        try:
            result = await self.execute_query("SELECT version()")
            if result['rows']:
                version = result['rows'][0]['version']
                # 提取版本号
                import re
                match = re.search(r'PostgreSQL (\d+\.\d+)', version)
                if match:
                    return f"PostgreSQL {match.group(1)}"
                return version
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
        # asyncpg使用transaction上下文管理器
        self._transaction = self.connection.transaction()
        await self._transaction.start()
        
    async def commit(self) -> None:
        """提交事务"""
        if hasattr(self, '_transaction'):
            await self._transaction.commit()
            delattr(self, '_transaction')
        
    async def rollback(self) -> None:
        """回滚事务"""
        if hasattr(self, '_transaction'):
            await self._transaction.rollback()
            delattr(self, '_transaction')