"""
GetTableDetailsTool - 获取单表详细结构工具
一步获取指定表的完整schema信息，解决Agent需要多次查询的痛点
"""

from typing import Dict, Any, Optional, Union, List
from ..types.tool_types import ToolResult
from ..types.core_types import AbortSignal
from .base import DatabaseTool
from ..config.base import DatabaseConfig


class GetTableDetailsTool(DatabaseTool):
    """
    获取单个表的详细结构信息
    解决Agent需要执行多次SQL才能获取完整表信息的痛点
    一步返回：列信息、约束、索引、外键、统计等完整信息
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        
        super().__init__(
            name="get_table_details",
            display_name=self._('table_details_tool_name', default="表结构详情") if i18n else "表结构详情",
            description="Get complete table schema in one step: columns, constraints, indexes, foreign keys, and statistics. No need for multiple queries.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table to inspect"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database connection name (optional, uses default)"
                    },
                    "include_stats": {
                        "type": "boolean",
                        "description": "Include table statistics (row count, size)",
                        "default": True
                    },
                    "include_sample_data": {
                        "type": "boolean",
                        "description": "Include a few sample rows",
                        "default": False
                    },
                    "sample_size": {
                        "type": "integer",
                        "description": "Number of sample rows to include",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 3
                    }
                },
                "required": ["table_name"]
            },
            is_output_markdown=True,
            can_update_output=False,
            should_summarize_display=False,
            i18n=i18n  # 传递i18n给基类
        )
        self.config = config
        
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        table_name = params.get("table_name", "").strip()
        if not table_name:
            return self._('table_details_name_empty', default="Table name cannot be empty")
            
        # 基本的表名验证（防止SQL注入）
        if any(char in table_name for char in [';', '--', '/*', '*/', '\n', '\r']):
            return self._('table_details_invalid_name', default="Invalid table name: contains forbidden characters")
            
        return None
        
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        table_name = params.get("table_name", "")
        include_stats = params.get("include_stats", True)
        include_sample = params.get("include_sample_data", False)
        
        desc = self._('table_details_get_description', default="获取表结构详情: {table_name}", table_name=table_name)
        extras = []
        if include_stats:
            extras.append(self._('table_details_stats_info', default="统计信息"))
        if include_sample:
            extras.append(self._('table_details_sample_data', default="样本数据"))
        if extras:
            extras_str = ', '.join(extras)
            desc += self._('table_details_include_extras', default=" (包含: {extras})", extras=extras_str)
            
        return desc
        
    async def should_confirm_execute(self, params: Dict[str, Any], signal: AbortSignal) -> Union[bool, Any]:
        """获取表结构是安全操作，不需要确认"""
        return False
        
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """执行获取表详情"""
        table_name = params.get("table_name", "").strip()
        database = params.get("database")
        include_stats = params.get("include_stats", True)
        include_sample = params.get("include_sample_data", False)
        sample_size = params.get("sample_size", 3)
        
        try:
            # 获取数据库适配器
            from ..adapters.adapter_factory import get_adapter
            adapter = await get_adapter(self.config, database)
            
            # 连接数据库
            await adapter.connect()
            
            try:
                # 检查表是否存在
                schema_result = await adapter.get_schema_info()
                
                if not schema_result.get('success', True):
                    raise Exception(schema_result.get('error', 'Failed to get schema info'))
                
                schema_info = schema_result.get('schema', {})
                tables = schema_info.get('tables', {})
                
                if table_name not in tables:
                    # 尝试不区分大小写匹配
                    table_name_lower = table_name.lower()
                    found_table = None
                    for t in tables:
                        if t.lower() == table_name_lower:
                            found_table = t
                            break
                            
                    if not found_table:
                        # 提供相似表名建议
                        suggestions = self._find_similar_tables(table_name, list(tables.keys()))
                        error_msg = self._('table_details_table_not_found', default="表 '{table_name}' 不存在", table_name=table_name)
                        if suggestions:
                            suggestions_str = ', '.join(suggestions[:3])
                            error_msg += self._('table_details_suggestions', default="。您是否想查看: {suggestions}", suggestions=suggestions_str)
                        return ToolResult(error=error_msg)
                    else:
                        table_name = found_table
                
                # 获取表的详细信息
                table_info = await adapter.get_table_info(table_name)
                
                # 获取额外信息
                extra_info = {}
                
                # 获取统计信息（如果需要）
                if include_stats:
                    stats = await self._get_table_statistics(adapter, table_name)
                    extra_info['statistics'] = stats
                    
                # 获取样本数据（如果需要）
                if include_sample:
                    samples = await self._get_sample_data(adapter, table_name, sample_size)
                    extra_info['sample_data'] = samples
                    
                # 格式化结果
                return self._format_result(table_name, table_info, extra_info, adapter.get_dialect())
                
            finally:
                # 确保断开连接
                await adapter.disconnect()
                
        except Exception as e:
            return ToolResult(
                error=f"Failed to get table details: {str(e)}"
            )
            
    def _find_similar_tables(self, target: str, tables: List[str]) -> List[str]:
        """查找相似的表名（简单的编辑距离）"""
        suggestions = []
        target_lower = target.lower()
        
        for table in tables:
            table_lower = table.lower()
            # 简单的相似度检查
            if target_lower in table_lower or table_lower in target_lower:
                suggestions.append(table)
            elif abs(len(target) - len(table)) <= 3:
                # 长度相近的也考虑
                suggestions.append(table)
                
        return suggestions[:5]  # 最多返回5个建议
        
    async def _get_table_statistics(self, adapter, table_name: str) -> Dict[str, Any]:
        """获取表统计信息"""
        try:
            # 获取行数
            count_sql = f"SELECT COUNT(*) as row_count FROM {table_name}"
            result = await adapter.execute_query(count_sql)
            row_count = result['rows'][0]['row_count'] if result['rows'] else 0
            
            stats = {
                'row_count': row_count
            }
            
            # 某些数据库可能支持获取表大小
            # 这里根据不同的数据库方言实现不同的逻辑
            dialect = adapter.get_dialect().lower()
            if dialect == 'sqlite':
                # SQLite没有直接的表大小查询
                stats['size_info'] = 'Size information not available for SQLite'
            elif dialect == 'mysql':
                # MySQL可以从information_schema获取
                size_sql = f"""
                SELECT 
                    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb
                FROM information_schema.TABLES 
                WHERE table_schema = DATABASE() 
                AND table_name = '{table_name}'
                """
                try:
                    size_result = await adapter.execute_query(size_sql)
                    if size_result['rows']:
                        stats['size_mb'] = size_result['rows'][0]['size_mb']
                except:
                    pass
                    
            return stats
            
        except Exception as e:
            return {'error': str(e)}
            
    async def _get_sample_data(self, adapter, table_name: str, limit: int) -> List[Dict[str, Any]]:
        """获取样本数据"""
        try:
            sample_sql = f"SELECT * FROM {table_name} LIMIT {limit}"
            result = await adapter.execute_query(sample_sql)
            return result.get('rows', [])
        except Exception as e:
            return []
            
    def _format_result(
        self, 
        table_name: str, 
        table_info: Dict[str, Any], 
        extra_info: Dict[str, Any],
        dialect: str
    ) -> ToolResult:
        """格式化结果输出"""
        # 提取信息
        columns = table_info.get('columns', [])
        primary_key = table_info.get('primary_key', [])
        foreign_keys = table_info.get('foreign_keys', [])
        indexes = table_info.get('indexes', [])
        constraints = table_info.get('constraints', [])
        
        # 为LLM准备完整信息
        llm_content = {
            'table_name': table_name,
            'database_dialect': dialect,
            'columns': columns,
            'primary_key': primary_key,
            'foreign_keys': foreign_keys,
            'indexes': indexes,
            'constraints': constraints,
            **extra_info
        }
        
        # 为显示准备格式化输出
        display_lines = [
            self._('table_details_table_title', default="📊 表: {table_name}", table_name=table_name),
            self._('table_details_db_type', default="🗄️ 数据库类型: {dialect}", dialect=dialect),
            ""
        ]
        
        # 列信息
        display_lines.append(self._('table_details_columns_info', default="📋 列信息:"))
        for col in columns:
            col_name = col.get('name', 'unknown')
            col_type = col.get('type', 'unknown')
            nullable = "NULL" if col.get('nullable', True) else "NOT NULL"
            default = col.get('default')
            
            col_desc = f"  - {col_name}: {col_type} {nullable}"
            if default is not None:
                col_desc += f" DEFAULT {default}"
            if col.get('comment'):
                col_desc += f" -- {col['comment']}"
                
            display_lines.append(col_desc)
            
        # 主键
        if primary_key:
            display_lines.append("")
            display_lines.append(self._('table_details_primary_key', default="🔑 主键: {keys}", keys=', '.join(primary_key)))
            
        # 外键
        if foreign_keys:
            display_lines.append("")
            display_lines.append(self._('table_details_foreign_keys', default="🔗 外键:"))
            for fk in foreign_keys:
                fk_name = fk.get('name', 'unnamed')
                fk_column = fk.get('column')
                ref_table = fk.get('referenced_table')
                ref_column = fk.get('referenced_column')
                display_lines.append(
                    f"  - {fk_name}: {fk_column} -> {ref_table}.{ref_column}"
                )
                
        # 索引
        if indexes:
            display_lines.append("")
            display_lines.append(self._('table_details_indexes', default="📍 索引:"))
            for idx in indexes:
                idx_name = idx.get('name', 'unnamed')
                idx_columns = idx.get('columns', [])
                idx_unique = " (UNIQUE)" if idx.get('unique') else ""
                display_lines.append(
                    f"  - {idx_name}: {', '.join(idx_columns)}{idx_unique}"
                )
                
        # 统计信息
        stats = extra_info.get('statistics', {})
        if stats and 'row_count' in stats:
            display_lines.append("")
            display_lines.append(self._('table_details_statistics', default="📈 统计信息:"))
            display_lines.append(self._('table_details_row_count', default="  - 行数: {count:,}", count=stats['row_count']))
            if 'size_mb' in stats:
                display_lines.append(self._('table_details_size', default="  - 大小: {size} MB", size=stats['size_mb']))
                
        # 样本数据
        samples = extra_info.get('sample_data', [])
        if samples:
            display_lines.append("")
            display_lines.append(self._('table_details_sample_data_title', default="🔍 样本数据:"))
            for i, row in enumerate(samples, 1):
                # 只显示前几个字段，避免太长
                sample_fields = []
                for k, v in list(row.items())[:5]:
                    sample_fields.append(f"{k}={v}")
                display_lines.append(f"  Row {i}: {', '.join(sample_fields)}")
                if len(row) > 5:
                    display_lines.append(f"         ... and {len(row) - 5} more fields")
                    
        summary = self._('table_details_summary', default="获取表 {table_name} 的完整结构信息", table_name=table_name)
        
        return ToolResult(
            summary=summary,
            llm_content=llm_content,
            return_display="\n".join(display_lines)
        )