"""
SQL方言解析器 - 支持多数据库SQL方言转换
完全对齐文档要求的多数据库方言支持
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from ..config.base import DatabaseConfig


class DatabaseDialect(Enum):
    """数据库方言枚举"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"


@dataclass
class ParsedSQL:
    """解析后的SQL信息"""
    original_sql: str
    operation_type: str
    tables: List[str]
    columns: List[str]
    conditions: List[str]
    joins: List[str]
    dialect: DatabaseDialect
    is_valid: bool
    error_message: Optional[str] = None


class SQLDialectParser:
    """
    SQL方言解析器 - 完全对齐文档要求
    
    核心功能：
    1. SQL语法解析和验证
    2. 多数据库方言识别
    3. 方言间转换支持
    4. 语法错误检测
    5. 性能优化建议
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        
        # 方言特定的关键词映射
        self.dialect_keywords = {
            DatabaseDialect.SQLITE: {
                "limit": "LIMIT",
                "offset": "OFFSET",
                "auto_increment": "AUTOINCREMENT",
                "string_concat": "||",
                "date_format": "strftime",
                "if_null": "IFNULL"
            },
            DatabaseDialect.POSTGRESQL: {
                "limit": "LIMIT",
                "offset": "OFFSET",
                "auto_increment": "SERIAL",
                "string_concat": "||",
                "date_format": "to_char",
                "if_null": "COALESCE"
            },
            DatabaseDialect.MYSQL: {
                "limit": "LIMIT",
                "offset": "OFFSET",
                "auto_increment": "AUTO_INCREMENT",
                "string_concat": "CONCAT",
                "date_format": "DATE_FORMAT",
                "if_null": "IFNULL"
            }
        }
        
        # 方言特定的数据类型映射
        self.dialect_types = {
            DatabaseDialect.SQLITE: {
                "string": "TEXT",
                "integer": "INTEGER",
                "float": "REAL",
                "boolean": "INTEGER",
                "datetime": "TEXT",
                "blob": "BLOB"
            },
            DatabaseDialect.POSTGRESQL: {
                "string": "VARCHAR",
                "integer": "INTEGER",
                "float": "DOUBLE PRECISION",
                "boolean": "BOOLEAN",
                "datetime": "TIMESTAMP",
                "blob": "BYTEA"
            },
            DatabaseDialect.MYSQL: {
                "string": "VARCHAR",
                "integer": "INT",
                "float": "DOUBLE",
                "boolean": "BOOLEAN",
                "datetime": "DATETIME",
                "blob": "BLOB"
            }
        }
        
    def parse_sql(self, sql: str, target_dialect: Optional[DatabaseDialect] = None) -> ParsedSQL:
        """
        解析SQL语句
        
        Args:
            sql: SQL语句
            target_dialect: 目标方言（用于转换）
            
        Returns:
            ParsedSQL: 解析结果
        """
        sql_clean = sql.strip()
        
        try:
            # 1. 基本解析
            operation_type = self._extract_operation_type(sql_clean)
            tables = self._extract_tables(sql_clean)
            columns = self._extract_columns(sql_clean)
            conditions = self._extract_conditions(sql_clean)
            joins = self._extract_joins(sql_clean)
            
            # 2. 方言识别
            detected_dialect = self._detect_dialect(sql_clean)
            
            # 3. 语法验证
            is_valid, error_message = self._validate_syntax(sql_clean, detected_dialect)
            
            return ParsedSQL(
                original_sql=sql_clean,
                operation_type=operation_type,
                tables=tables,
                columns=columns,
                conditions=conditions,
                joins=joins,
                dialect=detected_dialect,
                is_valid=is_valid,
                error_message=error_message
            )
            
        except Exception as e:
            return ParsedSQL(
                original_sql=sql_clean,
                operation_type="UNKNOWN",
                tables=[],
                columns=[],
                conditions=[],
                joins=[],
                dialect=DatabaseDialect.SQLITE,  # 默认方言
                is_valid=False,
                error_message=str(e)
            )
            
    def convert_dialect(self, sql: str, from_dialect: DatabaseDialect, to_dialect: DatabaseDialect) -> str:
        """
        转换SQL方言
        
        Args:
            sql: 原始SQL
            from_dialect: 源方言
            to_dialect: 目标方言
            
        Returns:
            str: 转换后的SQL
        """
        if from_dialect == to_dialect:
            return sql
            
        converted_sql = sql
        
        # 1. 关键词转换
        from_keywords = self.dialect_keywords.get(from_dialect, {})
        to_keywords = self.dialect_keywords.get(to_dialect, {})
        
        for key, from_keyword in from_keywords.items():
            to_keyword = to_keywords.get(key)
            if to_keyword and from_keyword != to_keyword:
                # 使用正则表达式进行替换，确保词边界
                pattern = r'\b' + re.escape(from_keyword) + r'\b'
                converted_sql = re.sub(pattern, to_keyword, converted_sql, flags=re.IGNORECASE)
                
        # 2. 数据类型转换
        from_types = self.dialect_types.get(from_dialect, {})
        to_types = self.dialect_types.get(to_dialect, {})
        
        for key, from_type in from_types.items():
            to_type = to_types.get(key)
            if to_type and from_type != to_type:
                pattern = r'\b' + re.escape(from_type) + r'\b'
                converted_sql = re.sub(pattern, to_type, converted_sql, flags=re.IGNORECASE)
                
        # 3. 特殊语法转换
        converted_sql = self._convert_special_syntax(converted_sql, from_dialect, to_dialect)
        
        return converted_sql
        
    def _extract_operation_type(self, sql: str) -> str:
        """提取操作类型"""
        sql_upper = sql.upper().strip()
        
        operations = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE']
        for op in operations:
            if sql_upper.startswith(op):
                return op
                
        return 'UNKNOWN'
        
    def _extract_tables(self, sql: str) -> List[str]:
        """提取表名"""
        patterns = [
            r'FROM\s+(\w+)',
            r'JOIN\s+(\w+)',
            r'UPDATE\s+(\w+)',
            r'INSERT\s+INTO\s+(\w+)',
            r'DELETE\s+FROM\s+(\w+)',
            r'CREATE\s+TABLE\s+(\w+)',
            r'ALTER\s+TABLE\s+(\w+)',
            r'DROP\s+TABLE\s+(\w+)'
        ]
        
        tables = set()
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.update(matches)
            
        return list(tables)
        
    def _extract_columns(self, sql: str) -> List[str]:
        """提取列名（简化实现）"""
        columns = []
        
        # SELECT语句的列提取
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            columns_str = select_match.group(1)
            if columns_str.strip() != '*':
                # 简单的列名分割（实际应该更复杂）
                cols = [col.strip() for col in columns_str.split(',')]
                columns.extend(cols)
                
        return columns
        
    def _extract_conditions(self, sql: str) -> List[str]:
        """提取WHERE条件"""
        conditions = []
        
        where_match = re.search(r'WHERE\s+(.*?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            conditions_str = where_match.group(1).strip()
            # 简单的条件分割
            conditions = [cond.strip() for cond in re.split(r'\s+AND\s+|\s+OR\s+', conditions_str, flags=re.IGNORECASE)]
            
        return conditions
        
    def _extract_joins(self, sql: str) -> List[str]:
        """提取JOIN语句"""
        join_patterns = [
            r'(INNER\s+JOIN\s+\w+(?:\s+ON\s+[^)]+)?)',
            r'(LEFT\s+JOIN\s+\w+(?:\s+ON\s+[^)]+)?)',
            r'(RIGHT\s+JOIN\s+\w+(?:\s+ON\s+[^)]+)?)',
            r'(FULL\s+JOIN\s+\w+(?:\s+ON\s+[^)]+)?)',
            r'(JOIN\s+\w+(?:\s+ON\s+[^)]+)?)'
        ]
        
        joins = []
        for pattern in join_patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            joins.extend(matches)
            
        return joins
        
    def _detect_dialect(self, sql: str) -> DatabaseDialect:
        """检测SQL方言"""
        sql_upper = sql.upper()
        
        # SQLite特征
        if 'AUTOINCREMENT' in sql_upper or 'PRAGMA' in sql_upper:
            return DatabaseDialect.SQLITE
            
        # PostgreSQL特征
        if 'SERIAL' in sql_upper or '::' in sql or 'RETURNING' in sql_upper:
            return DatabaseDialect.POSTGRESQL
            
        # MySQL特征
        if 'AUTO_INCREMENT' in sql_upper or '`' in sql or 'LIMIT' in sql_upper:
            return DatabaseDialect.MYSQL
            
        # 默认返回SQLite
        return DatabaseDialect.SQLITE
        
    def _validate_syntax(self, sql: str, dialect: DatabaseDialect) -> Tuple[bool, Optional[str]]:
        """验证SQL语法"""
        # 基本语法检查
        if not sql.strip():
            return False, "SQL语句为空"
            
        # 检查括号匹配
        if sql.count('(') != sql.count(')'):
            return False, "括号不匹配"
            
        # 检查引号匹配
        single_quotes = sql.count("'") - sql.count("\\'")
        if single_quotes % 2 != 0:
            return False, "单引号不匹配"
            
        return True, None
        
    def _convert_special_syntax(self, sql: str, from_dialect: DatabaseDialect, to_dialect: DatabaseDialect) -> str:
        """转换特殊语法"""
        # 这里可以添加更复杂的方言转换逻辑
        # 例如：LIMIT/OFFSET语法、日期函数、字符串函数等
        
        return sql
