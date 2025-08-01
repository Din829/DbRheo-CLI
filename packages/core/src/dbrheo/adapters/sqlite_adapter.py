"""
SQLite数据库适配器 - MVP阶段的主要数据库支持
提供SQLite数据库的完整操作接口
"""

import sqlite3
import aiosqlite
from typing import Any, Dict, List, Optional
from .base import DatabaseAdapter
from ..types.core_types import AbortSignal
from ..utils.type_converter import convert_to_serializable


class SQLiteAdapter(DatabaseAdapter):
    """
    SQLite数据库适配器
    - 异步SQLite操作
    - 连接管理
    - 结构信息查询
    - SQL解析和验证
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化SQLite适配器
        
        参数:
            config: 数据库配置字典，包含:
                - database: 数据库路径
                - type: 数据库类型（应为'sqlite'）
        """
        self.config = config
        self.connection: Optional[aiosqlite.Connection] = None
        # 从配置中获取数据库路径
        self.db_path = config.get('database', ':memory:')
        # 事务管理状态
        self._in_transaction = False
        
    async def connect(self) -> None:
        """建立SQLite连接"""
        try:
            self.connection = await aiosqlite.connect(self.db_path)
            # 启用外键约束
            await self.connection.execute("PRAGMA foreign_keys = ON")
            await self.connection.commit()
        except Exception as e:
            raise Exception(f"Failed to connect to SQLite database: {e}")
            
    async def disconnect(self) -> None:
        """关闭SQLite连接"""
        if self.connection:
            await self.connection.close()
            self.connection = None
            
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
                
            cursor = await self.connection.execute(sql, params or {})
            rows = await cursor.fetchall()
            
            # 获取列名
            columns = [description[0] for description in cursor.description] if cursor.description else []
            
            # 转换为字典列表
            result_data = []
            for row in rows:
                result_data.append(dict(zip(columns, row)))
            
            # 转换为可序列化的类型
            serializable_data = [convert_to_serializable(row) for row in result_data]
                
            return {
                "columns": columns,
                "rows": serializable_data,
                "row_count": len(result_data)
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
                
            cursor = await self.connection.execute(sql, params or {})
            
            # 只有不在事务中时才自动提交
            if not self._in_transaction:
                await self.connection.commit()
            
            return {
                "affected_rows": cursor.rowcount,
                "last_insert_id": cursor.lastrowid
            }
            
        except Exception as e:
            # 只有不在事务中时才自动回滚
            if not self._in_transaction:
                await self.connection.rollback()
            raise Exception(f"Command execution failed: {str(e)}")
            
    async def get_schema_info(self, schema_name: Optional[str] = None) -> Dict[str, Any]:
        """获取数据库结构信息"""
        try:
            # SQLite中获取所有表
            tables_query = """
                SELECT name, type, sql 
                FROM sqlite_master 
                WHERE type IN ('table', 'view') 
                AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """
            
            result = await self.execute_query(tables_query)
            tables = result["rows"]
            
            # 获取每个表的详细信息
            schema_info = {
                "database_name": self.db_path,
                "tables": {},
                "views": {},
                "total_tables": 0,
                "total_views": 0
            }
            
            for table in tables:
                table_name = table["name"]
                table_type = table["type"]
                
                if table_type == "table":
                    schema_info["tables"][table_name] = await self.get_table_info(table_name)
                    schema_info["total_tables"] += 1
                elif table_type == "view":
                    schema_info["views"][table_name] = {
                        "name": table_name,
                        "definition": table["sql"]
                    }
                    schema_info["total_views"] += 1
                    
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
            columns_query = f"PRAGMA table_info({table_name})"
            columns_result = await self.execute_query(columns_query)
            
            columns = []
            for col in columns_result["rows"]:
                columns.append({
                    "name": col["name"],
                    "type": col["type"],
                    "nullable": not col["notnull"],
                    "default": col["dflt_value"],
                    "primary_key": bool(col["pk"])
                })
                
            # 获取外键信息
            fk_query = f"PRAGMA foreign_key_list({table_name})"
            fk_result = await self.execute_query(fk_query)
            
            foreign_keys = []
            for fk in fk_result["rows"]:
                foreign_keys.append({
                    "column": fk["from"],
                    "referenced_table": fk["table"],
                    "referenced_column": fk["to"]
                })
                    
            # 获取索引信息
            index_query = f"PRAGMA index_list({table_name})"
            index_result = await self.execute_query(index_query)
            
            indexes = []
            for idx in index_result["rows"]:
                indexes.append({
                    "name": idx["name"],
                    "unique": bool(idx["unique"])
                })
                    
            return {
                "name": table_name,
                "columns": columns,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
                "column_count": len(columns)
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def parse_sql(self, sql: str) -> Dict[str, Any]:
        """解析SQL语句 - 增强版，支持语法验证"""
        sql_stripped = sql.strip()
        sql_upper = sql_stripped.upper()
        
        # 初始化解析结果
        parse_errors = []
        syntax_issues = []
        sql_type = 'UNKNOWN'
        risk_level = 'medium'
        
        # 1. 尝试使用可选的sqlparse库进行精确解析
        try:
            import sqlparse
            parsed = sqlparse.parse(sql_stripped)
            if not parsed or not parsed[0].tokens:
                parse_errors.append("无法解析SQL语句：语句为空或格式不正确")
            else:
                # sqlparse成功，提取更准确的信息
                statement = parsed[0]
                # 获取第一个有意义的token
                first_token = None
                for token in statement.tokens:
                    if not token.is_whitespace:
                        first_token = str(token).upper()
                        break
                
                if first_token:
                    if first_token in ('SELECT', 'WITH'):
                        sql_type = 'SELECT'
                        risk_level = 'low'
                    elif first_token in ('INSERT', 'UPDATE', 'DELETE'):
                        sql_type = 'DML'
                        risk_level = 'medium'
                    elif first_token in ('CREATE', 'DROP', 'ALTER', 'TRUNCATE'):
                        sql_type = 'DDL'
                        risk_level = 'high'
                    elif first_token in ('EXPLAIN', 'SHOW', 'DESCRIBE', 'DESC', 'PRAGMA'):
                        sql_type = 'SELECT'  # 元数据查询也视为SELECT
                        risk_level = 'low'
                    elif first_token in ('VALUES', 'TABLE'):
                        sql_type = 'SELECT'  # VALUES和TABLE语法也返回结果集
                        risk_level = 'low'
                    elif first_token in ('ATTACH', 'DETACH'):
                        sql_type = 'DDL'  # 数据库附加操作
                        risk_level = 'medium'
                    elif first_token in ('BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT'):
                        sql_type = 'TRANSACTION'  # 事务控制
                        risk_level = 'low'
                    else:
                        sql_type = 'UNKNOWN'
                        # 检查是否是拼写错误
                        potential_errors = self._check_sql_typos(first_token)
                        if potential_errors:
                            parse_errors.extend(potential_errors)
        except ImportError:
            # sqlparse未安装，使用基础解析
            # 确定SQL类型
            if sql_upper.startswith(('SELECT', 'WITH')):
                sql_type = 'SELECT'
                risk_level = 'low'
            elif sql_upper.startswith(('INSERT', 'UPDATE', 'DELETE')):
                sql_type = 'DML'
                risk_level = 'medium'
            elif sql_upper.startswith(('CREATE', 'DROP', 'ALTER', 'TRUNCATE')):
                sql_type = 'DDL'
                risk_level = 'high'
            elif sql_upper.startswith(('EXPLAIN', 'SHOW', 'DESCRIBE', 'DESC', 'PRAGMA')):
                sql_type = 'SELECT'  # 元数据查询也视为SELECT
                risk_level = 'low'
            elif sql_upper.startswith(('VALUES', 'TABLE')):
                sql_type = 'SELECT'  # VALUES和TABLE语法也返回结果集
                risk_level = 'low'
            elif sql_upper.startswith(('ATTACH', 'DETACH')):
                sql_type = 'DDL'  # 数据库附加操作
                risk_level = 'medium'
            elif sql_upper.startswith(('BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT')):
                sql_type = 'TRANSACTION'  # 事务控制
                risk_level = 'low'
            else:
                # 对UNKNOWN类型做更智能的检测
                first_word = sql_upper.split()[0] if sql_upper.split() else ''
                potential_errors = self._check_sql_typos(first_word)
                if potential_errors:
                    parse_errors.extend(potential_errors)
        
        # 2. 基础语法检查（无论是否有sqlparse）
        if sql_type != 'UNKNOWN':
            syntax_issues = self._check_basic_syntax(sql_stripped, sql_type)
        
        # 智能检测LIMIT子句（避免工具层硬编码）
        has_limit = False
        if sql_type == 'SELECT':
            # 更精确的LIMIT检测，考虑SQL语法
            import re
            # 检测LIMIT子句，避免在字符串字面量中的误匹配
            limit_pattern = r'\bLIMIT\s+\d+\b'
            has_limit = bool(re.search(limit_pattern, sql_upper))
            
        return {
            "sql_type": sql_type,
            "risk_level": risk_level,
            "estimated_impact": self._estimate_impact(sql),
            "tables_involved": self._extract_table_names(sql),
            "has_limit": has_limit,  # 为工具层提供LIMIT检测信息
            "parse_errors": parse_errors,  # 新增：解析错误
            "syntax_issues": syntax_issues,  # 新增：语法问题
            "dialect_features": {
                "supports_limit": True,
                "supports_offset": True,
                "limit_syntax": "LIMIT n"
            }
        }
        
    def get_dialect(self) -> str:
        """获取数据库方言"""
        return "sqlite"
        
    async def get_version(self) -> Optional[str]:
        """获取SQLite版本信息"""
        try:
            if not self.connection:
                await self.connect()
            result = await self.execute_query("SELECT sqlite_version() as version")
            if result['rows']:
                return result['rows'][0]['version']
        except Exception:
            pass
        return None
        
    @property
    def supports_transactions(self) -> bool:
        """SQLite支持事务"""
        return True
        
    def get_table_list_query(self, include_views: bool = False, pattern: Optional[str] = None) -> str:
        """
        获取表列表的查询语句
        让适配器负责构建适合其方言的查询
        """
        query = """
            SELECT name, type 
            FROM sqlite_master 
            WHERE type = 'table'
        """
        
        if include_views:
            query = query.replace("type = 'table'", "type IN ('table', 'view')")
            
        if pattern:
            # 安全的模式匹配
            safe_pattern = pattern.replace("'", "''").replace('*', '%')
            query += f" AND name LIKE '{safe_pattern}'"
            
        query += " AND name NOT LIKE 'sqlite_%' ORDER BY name"
        return query
        
    def _estimate_impact(self, sql: str) -> str:
        """估算SQL影响范围"""
        sql_upper = sql.upper()
        if 'WHERE' not in sql_upper and any(op in sql_upper for op in ['UPDATE', 'DELETE']):
            return "high"  # 无WHERE条件的更新/删除
        elif 'DROP' in sql_upper or 'TRUNCATE' in sql_upper:
            return "high"
        else:
            return "low"
            
    def _extract_table_names(self, sql: str) -> List[str]:
        """提取SQL中涉及的表名（简单实现）"""
        # TODO: 实现更完善的SQL解析
        import re
        
        # 简单的表名提取
        patterns = [
            r'FROM\s+(\w+)',
            r'JOIN\s+(\w+)',
            r'UPDATE\s+(\w+)',
            r'INSERT\s+INTO\s+(\w+)',
            r'DELETE\s+FROM\s+(\w+)'
        ]
        
        tables = set()
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.update(matches)
            
        return list(tables)
    
    async def begin_transaction(self) -> None:
        """开始事务"""
        if not self.connection:
            raise Exception("Database not connected")
            
        if not self._in_transaction:
            # SQLite使用BEGIN来开始事务
            await self.connection.execute("BEGIN")
            self._in_transaction = True
            
    async def commit(self) -> None:
        """提交事务"""
        if not self.connection:
            raise Exception("Database not connected")
            
        if self._in_transaction:
            await self.connection.commit()
            self._in_transaction = False
            
    async def rollback(self) -> None:
        """回滚事务"""
        if not self.connection:
            raise Exception("Database not connected")
            
        if self._in_transaction:
            await self.connection.rollback()
            self._in_transaction = False
    
    def _check_sql_typos(self, word: str) -> List[str]:
        """检查常见的SQL关键字拼写错误"""
        errors = []
        common_typos = {
            'SELCT': 'SELECT',
            'SLECT': 'SELECT',
            'SEELCT': 'SELECT',
            'SELECTT': 'SELECT',
            'INSRT': 'INSERT',
            'INSER': 'INSERT',
            'INSERTT': 'INSERT',
            'UPDAE': 'UPDATE',
            'UPDAT': 'UPDATE',
            'UPDATEE': 'UPDATE',
            'DELTE': 'DELETE',
            'DELET': 'DELETE',
            'DELETEE': 'DELETE',
            'CRAETE': 'CREATE',
            'CREAT': 'CREATE',
            'CREATEE': 'CREATE',
            'DRPO': 'DROP',
            'DRP': 'DROP',
            'DROPP': 'DROP',
            'ALTR': 'ALTER',
            'ALTE': 'ALTER',
            'ALTERR': 'ALTER',
            'FORM': 'FROM',
            'FRM': 'FROM',
            'FROMM': 'FROM',
            'WHRE': 'WHERE',
            'WHER': 'WHERE',
            'WHEREE': 'WHERE',
            'JOIM': 'JOIN',
            'JION': 'JOIN',
            'JOINN': 'JOIN'
        }
        
        if word in common_typos:
            errors.append(f"可能的拼写错误：'{word}' 应该是 '{common_typos[word]}'")
        elif word and len(word) > 2:  # 对于较长的未知词，尝试找相似的SQL关键字
            sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 
                          'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'TABLE', 
                          'VALUES', 'SET', 'INTO', 'GROUP', 'ORDER', 'BY', 'HAVING']
            # 简单的编辑距离检查
            for keyword in sql_keywords:
                if self._is_similar(word, keyword):
                    errors.append(f"未识别的关键字 '{word}'，您是否想用 '{keyword}'？")
                    break
        
        return errors
    
    def _is_similar(self, word1: str, word2: str, threshold: int = 2) -> bool:
        """简单的相似度检查（编辑距离）"""
        if abs(len(word1) - len(word2)) > threshold:
            return False
        
        diff_count = 0
        min_len = min(len(word1), len(word2))
        
        for i in range(min_len):
            if word1[i] != word2[i]:
                diff_count += 1
                if diff_count > threshold:
                    return False
        
        diff_count += abs(len(word1) - len(word2))
        return diff_count <= threshold
    
    def _check_basic_syntax(self, sql: str, sql_type: str) -> List[str]:
        """基础语法检查"""
        issues = []
        sql_upper = sql.upper()
        
        if sql_type == 'SELECT':
            # 检查SELECT语句的基本结构
            if 'FROM' not in sql_upper:
                # 但是某些SELECT不需要FROM（如SELECT 1）
                if not any(x in sql_upper for x in ['DUAL', '1', '2', '3', 'VERSION()', 'DATABASE()']):
                    issues.append("SELECT语句缺少FROM子句")
        
        elif sql_type == 'INSERT':
            # INSERT必须有INTO
            if 'INTO' not in sql_upper:
                issues.append("INSERT语句缺少INTO关键字")
            # INSERT必须有VALUES或SELECT
            if 'VALUES' not in sql_upper and 'SELECT' not in sql_upper:
                issues.append("INSERT语句缺少VALUES子句或SELECT子句")
                
        elif sql_type == 'UPDATE':
            # UPDATE必须有SET
            if 'SET' not in sql_upper:
                issues.append("UPDATE语句缺少SET子句")
                
        elif sql_type == 'DELETE':
            # DELETE通常有FROM（但不是必须的）
            if 'FROM' not in sql_upper:
                # SQLite中DELETE可以不带FROM，所以这只是警告
                pass
        
        # 检查常见的语法错误
        # 检查括号匹配
        open_count = sql.count('(')
        close_count = sql.count(')')
        if open_count != close_count:
            issues.append(f"括号不匹配：{open_count}个左括号，{close_count}个右括号")
        
        # 检查引号匹配
        single_quotes = sql.count("'")
        if single_quotes % 2 != 0:
            issues.append("单引号不成对")
            
        double_quotes = sql.count('"')
        if double_quotes % 2 != 0:
            issues.append("双引号不成对")
        
        return issues
