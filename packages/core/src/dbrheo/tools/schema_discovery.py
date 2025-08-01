"""
SchemaDiscoveryTool - 数据库结构探索工具
渐进式、上下文感知的数据库结构探索，支持智能探索策略
"""

from typing import Optional, Callable, Union, Dict, Any, List
from .base import DatabaseTool
from ..types.core_types import AbortSignal
from ..types.tool_types import ToolResult, DatabaseConfirmationDetails
from ..config.base import DatabaseConfig


class SchemaDiscoveryTool(DatabaseTool):
    """
    快速表发现工具 - 获取数据库中的表名列表
    作为 SHOW TABLES 的便捷替代，减少Agent输入
    Agent可以选择使用此工具或直接使用sql_execute
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        
        super().__init__(
            name="schema_discovery",
            display_name=self._('schema_tool_name', default="表发现工具") if i18n else "表发现工具",
            description=self._('schema_tool_description', default="快速获取数据库架构信息。功能：列出所有表名、按pattern过滤、包含视图选项、支持schema/database切换。比直接SQL更简洁高效。") if i18n else "快速获取数据库架构信息。功能：列出所有表名、按pattern过滤、包含视图选项、支持schema/database切换。比直接SQL更简洁高效。",
            parameter_schema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Optional table name pattern matching, supports wildcards (e.g. 'user%' matches all tables starting with user)"
                    },
                    "include_views": {
                        "type": "boolean",
                        "description": "Whether to include views, default is false"
                    },
                    "database": {
                        "type": "string",
                        "description": "Target database connection name (optional, uses default connection)"
                    }
                },
                "required": []  # 所有参数都是可选的
            },
            is_output_markdown=True,
            can_update_output=False,
            should_summarize_display=False,
            i18n=i18n  # 传递i18n给基类
        )
        self.config = config
        
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """参数验证 - 所有参数都是可选的"""
        # 不需要验证，所有参数都是可选的
        return None
        
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取执行描述"""
        pattern = params.get("pattern")
        include_views = params.get("include_views", False)
        
        desc = self._('schema_get_tables', default="Get database tables")
        if pattern:
            desc += self._('schema_pattern_suffix', default=" (pattern: {pattern})", pattern=pattern)
        if include_views:
            desc += self._('schema_include_views_suffix', default=", including views")
            
        return desc
        
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> Union[bool, DatabaseConfirmationDetails]:
        """获取表名是安全操作，无需确认"""
        return False
        
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """获取表名列表"""
        pattern = params.get("pattern")
        include_views = params.get("include_views", False)
        database = params.get("database")
        
        try:
            # 获取数据库适配器
            from ..adapters.adapter_factory import get_adapter
            adapter = await get_adapter(self.config, database)
            
            # 连接数据库
            await adapter.connect()
            
            try:
                # 获取完整的数据库信息，让Agent能够自主判断数据库类型
                schema_result = await adapter.get_schema_info()
                
                if not schema_result.get('success', True):
                    raise Exception(schema_result.get('error', 'Failed to get schema info'))
                
                schema_info = schema_result.get('schema', {})
                
                # 提取数据库元信息
                # 安全地获取版本信息（如果是async方法）
                version = None
                if hasattr(adapter, 'get_version'):
                    try:
                        version_result = adapter.get_version()
                        if hasattr(version_result, '__await__'):
                            # 是async方法
                            version = await version_result
                        else:
                            # 是同步方法
                            version = version_result
                    except Exception:
                        version = None
                        
                database_info = {
                    'type': adapter.get_dialect(),  # 让适配器告诉我们方言
                    'name': schema_info.get('database_name'),
                    'version': version,
                    'dialect': adapter.get_dialect(),
                    'supports_transactions': getattr(adapter, 'supports_transactions', True),
                    'system_info': {
                        'total_tables': schema_info.get('total_tables', 0),
                        'total_views': schema_info.get('total_views', 0)
                    }
                }
                
                # 提取表信息
                tables = []
                
                # 处理表
                for table_name, table_info in schema_info.get('tables', {}).items():
                    if pattern and not self._match_pattern(table_name, pattern):
                        continue
                    tables.append({'name': table_name, 'type': 'table'})
                    
                # 处理视图（如果需要）
                if include_views:
                    for view_name, view_info in schema_info.get('views', {}).items():
                        if pattern and not self._match_pattern(view_name, pattern):
                            continue
                        tables.append({'name': view_name, 'type': 'view'})
                
                # 返回包含完整数据库信息的结果
                return self._format_result(tables, database_info)
                
            finally:
                # 确保断开连接
                await adapter.disconnect()
                
        except Exception as e:
            error_msg = self._('schema_get_error', default="Failed to get table names: {error}", error=str(e))
            return ToolResult(
                summary=self._('schema_get_failed', default="Failed to get table names"),
                llm_content=error_msg,
                return_display=error_msg,
                error=str(e)
            )
            
    def _match_pattern(self, name: str, pattern: str) -> bool:
        """简单的模式匹配实现"""
        import fnmatch
        return fnmatch.fnmatch(name.lower(), pattern.replace('*', '?').lower())
        
    def _format_result(self, tables: List[Dict[str, str]], database_info: Optional[Dict[str, Any]] = None) -> ToolResult:
        """统一的结果格式化 - 包含完整数据库信息"""
        table_count = len(tables)
        
        # 获取数据库信息
        db_type = database_info.get('type', 'Unknown') if database_info else 'Unknown'
        db_version = database_info.get('version', '') if database_info else ''
        db_name = database_info.get('name', '') if database_info else ''
        dialect = database_info.get('dialect', db_type) if database_info else db_type
        
        # 生成改进的summary - 让关键信息更突出
        if db_version:
            summary = self._('schema_summary_with_version', default="{type} {version} database, contains {count} tables", type=db_type, version=db_version, count=table_count)
        else:
            summary = self._('schema_summary', default="{type} database, contains {count} tables", type=db_type, count=table_count)
        
        if table_count == 0:
            # 即使没有表，也要提供数据库类型信息
            llm_content = {
                'tables': [],
                'count': 0,
                'database_type': db_type,
                'database_version': db_version,
                'database_name': db_name,
                'sql_dialect': dialect,
                'dialect_tips': self._get_dialect_tips(dialect)
            }
            display = f"📊 {summary}\n"
            display += self._('schema_db_name', default="🗄️ Database name: {name}\n", name=db_name) if db_name else ""
            display += "\n" + self._('schema_tips_prefix', default="💡 Tips: ") + self._get_dialect_tips(dialect)
        else:
            # 为LLM准备完整信息，让Agent能够自主判断数据库类型和特性
            table_names = [t['name'] for t in tables]
            llm_content = {
                'tables': table_names,
                'count': table_count,
                'table_details': tables,  # 包含类型信息
                'database_type': db_type,
                'database_version': db_version,
                'database_name': db_name,
                'sql_dialect': dialect,
                'supports_transactions': database_info.get('supports_transactions', True) if database_info else True,
                'system_tables_info': database_info.get('system_info') if database_info else None,
                'dialect_tips': self._get_dialect_tips(dialect),
                'feature_support': self._get_feature_support(dialect)
            }
            
            # 为显示准备格式化输出
            display_lines = [
                f"📊 {summary}"
            ]
            
            # 添加数据库详细信息
            if db_name:
                display_lines.append(self._('schema_db_name', default="🗄️ Database name: {name}", name=db_name))
                
            # 添加方言提示
            dialect_tips = self._get_dialect_tips(dialect)
            if dialect_tips:
                display_lines.append("\n" + self._('schema_tips_prefix', default="💡 Tips: ") + dialect_tips)
                
            display_lines.append("")  # 空行分隔
            display_lines.append(self._('schema_objects_list', default="📋 Database objects list:"))
            
            # 按类型分组显示
            tables_by_type = {}
            for table in tables:
                table_type = table.get('type', 'table')
                if table_type not in tables_by_type:
                    tables_by_type[table_type] = []
                tables_by_type[table_type].append(table['name'])
                
            for table_type, names in tables_by_type.items():
                type_label = self._('schema_table_label', default="Tables") if table_type == 'table' else self._('schema_view_label', default="Views") if table_type == 'view' else table_type
                display_lines.append("\n" + self._('schema_type_count', default="{type} ({count}):", type=type_label, count=len(names)))
                # 只显示前10个，避免列表太长
                for name in names[:10]:
                    display_lines.append(f"  - {name}")
                if len(names) > 10:
                    display_lines.append(self._('schema_more_items', default="  ... {count} more", count=len(names) - 10))
                
            display = "\n".join(display_lines)
            
        return ToolResult(
            summary=summary,
            llm_content=llm_content,
            return_display=display
        )
    
    def _get_dialect_tips(self, dialect: str) -> str:
        """根据数据库方言提供使用提示"""
        dialect_lower = dialect.lower() if dialect else ''
        
        tips_map = {
            'sqlite': self._('schema_tip_sqlite', default="Use PRAGMA table_info(table) to view table structure, DESCRIBE not supported"),
            'mysql': self._('schema_tip_mysql', default="Use DESCRIBE table or SHOW COLUMNS FROM table to view table structure"),
            'postgresql': self._('schema_tip_postgresql', default="Use \\d table to view table structure, supports INFORMATION_SCHEMA"),
            'postgres': self._('schema_tip_postgresql', default="Use \\d table to view table structure, supports INFORMATION_SCHEMA"),
            'oracle': self._('schema_tip_oracle', default="Use DESC table to view table structure, case sensitive"),
            'sqlserver': self._('schema_tip_sqlserver', default="Use sp_help 'table' to view table structure"),
            'mssql': self._('schema_tip_sqlserver', default="Use sp_help 'table' to view table structure")
        }
        
        return tips_map.get(dialect_lower, self._('schema_dialect_default', default="Database dialect: {dialect}", dialect=dialect))
    
    def _get_feature_support(self, dialect: str) -> Dict[str, bool]:
        """获取数据库特性支持情况"""
        dialect_lower = dialect.lower() if dialect else ''
        
        # 默认特性支持
        default_features = {
            'transactions': True,
            'foreign_keys': True,
            'views': True,
            'stored_procedures': True,
            'triggers': True,
            'full_text_search': False,
            'json_support': False,
            'window_functions': True
        }
        
        # 根据方言调整
        feature_map = {
            'sqlite': {
                'stored_procedures': False,
                'full_text_search': True,  # FTS扩展
                'json_support': True        # JSON1扩展
            },
            'mysql': {
                'full_text_search': True,
                'json_support': True
            },
            'postgresql': {
                'full_text_search': True,
                'json_support': True
            }
        }
        
        features = default_features.copy()
        if dialect_lower in feature_map:
            features.update(feature_map[dialect_lower])
            
        return features
