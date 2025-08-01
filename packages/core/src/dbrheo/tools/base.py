"""
DatabaseTool基类 - 工具基类和接口定义
完全对齐Gemini CLI的Tool接口，支持确认机制和流式输出
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, Callable, Union, Dict, Any
from ..types.core_types import AbortSignal
from ..types.tool_types import ToolResult, DatabaseConfirmationDetails

TParams = TypeVar('TParams')
TResult = TypeVar('TResult', bound='ToolResult')


class DatabaseTool(ABC, Generic[TParams, TResult]):
    """
    数据库工具基础接口 - 完全对齐Gemini CLI的Tool接口
    - DatabaseTool抽象基类（完全对齐Gemini CLI）
    - ToolResult、ToolCallRequestInfo等类型定义
    - 确认机制接口定义（DatabaseConfirmationOutcome）
    """
    
    def __init__(
        self,
        name: str,                          # 工具内部名称
        display_name: str,                  # 显示名称（对应displayName）
        description: str,                   # 工具功能描述
        parameter_schema: Dict[str, Any],   # JSON Schema（对应parameterSchema）
        is_output_markdown: bool = False,   # 输出格式（对应isOutputMarkdown）
        can_update_output: bool = False,    # 流式输出支持（对应canUpdateOutput）
        summarizer: Optional[Callable] = None,
        should_summarize_display: bool = False,  # 对应shouldSummarizeDisplay
        i18n: Optional[Any] = None          # 可选的i18n实例
    ):
        self.name = name
        self.display_name = display_name
        self.description = description
        self._parameter_schema = parameter_schema
        self.is_output_markdown = is_output_markdown
        self.can_update_output = can_update_output
        self.summarizer = summarizer
        self.should_summarize_display = should_summarize_display
        self._i18n = i18n  # 保存i18n实例
        
    @property
    def parameter_schema(self) -> Dict[str, Any]:
        """获取参数schema - 与Gemini CLI保持一致"""
        return self._parameter_schema
        
    @property
    def schema(self) -> Dict[str, Any]:
        """生成函数声明 - 与Gemini CLI一致"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._parameter_schema
        }
    
    def _normalize_param(self, value):
        """
        标准化参数值，处理 protobuf 对象
        将 RepeatedComposite 等 protobuf 类型转换为普通 Python 类型
        """
        # 处理 protobuf 的 RepeatedComposite 类型
        if hasattr(value, '__iter__') and hasattr(value, '_values'):
            # RepeatedComposite 有 _values 属性
            return list(value)
        
        # 处理其他 protobuf 集合类型
        if hasattr(value, '__class__') and 'Repeated' in str(type(value)):
            return list(value)
        
        # 检查是否是其他 protobuf 对象
        if hasattr(value, '_pb') or 'google' in str(type(value).__module__):
            # 尝试转换为基本类型
            if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                return list(value)
            elif hasattr(value, '__dict__'):
                return dict(value)
            else:
                return str(value)
        
        # 普通类型直接返回
        return value
    
    def _normalize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化所有参数，确保兼容性
        工具可以选择性调用此方法来避免类型问题
        """
        if not isinstance(params, dict):
            return params
        
        normalized = {}
        for key, value in params.items():
            normalized[key] = self._normalize_param(value)
        
        return normalized
        
    @abstractmethod
    def validate_tool_params(self, params: TParams) -> Optional[str]:
        """验证参数，返回错误信息或None"""
        pass
        
    @abstractmethod
    def get_description(self, params: TParams) -> str:
        """获取执行描述"""
        pass
        
    @abstractmethod
    async def should_confirm_execute(
        self,
        params: TParams,
        signal: AbortSignal
    ) -> Union[bool, DatabaseConfirmationDetails]:
        """检查是否需要确认 - 与Gemini CLI的shouldConfirmExecute完全一致"""
        pass
        
    @abstractmethod
    async def execute(
        self,
        params: TParams,
        signal: AbortSignal,
        update_output: Optional[Callable[[str], None]] = None
    ) -> TResult:
        """执行工具 - 与Gemini CLI的execute方法签名完全一致"""
        pass
    
    def _(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        """
        获取国际化文本，如果没有i18n则返回默认文本
        保持最小侵入性：只在有i18n时才使用，否则返回默认值
        
        参数:
            key: i18n键
            default: 自定义默认文本（优先使用）
            **kwargs: 格式化参数
        """
        # 默认文本映射（保持向后兼容）
        default_texts = {
            # database_connect_tool
            'db_connect_success': '数据库连接成功!',
            'db_connect_alias': '连接别名',
            'db_connect_type': '数据库类型',
            'db_connect_version': '版本',
            'db_connect_status': '状态',
            'db_connect_active': '已设为当前活动连接',
            'db_connect_host': '主机',
            'db_connect_port': '端口',
            'db_connect_database': '数据库',
            'db_connect_error': '连接失败',
            'db_test_success': '连接测试成功!',
            'db_test_failed': '连接测试失败',
            'db_supported_types': '支持的数据库类型',
            'db_available': '可用的数据库:',
            'db_need_driver': '需要安装驱动的数据库:',
            'db_connection_examples': '连接字符串示例:',
            
            # schema_discovery
            'schema_discovery_summary': '{db_type} {version} 数据库，包含{count}个表',
            'schema_discovery_objects': '数据库对象列表:',
            'schema_table_count': '表 ({count}个)',
            'schema_view_count': '视图 ({count}个)',
            'schema_total_size': '总大小',
            
            # file_read_tool
            'file_read_lines_read': '读取了 {count} 行',
            'file_read_sql_found': '发现SQL文件，包含 {count} 条语句',
            'file_read_json_found': '发现JSON文件，包含 {count} 个对象',
            'file_read_csv_found': '发现CSV文件，包含 {columns} 列，{rows} 行数据',
            'file_read_sql_content': 'SQL脚本内容:\n\n{content}',
            'file_read_more_content': '\n\n[文件还有更多内容，使用offset和limit参数分页读取]',
            'file_read_yaml_display': '📄 {filename}\n📊 {keys_info}\n📏 行数: {lines}',
            
            # table_details_tool
            'table_details_tool_name': '表结构详情',
            'table_details_get_description': '获取表结构详情: {table_name}',
            'table_details_stats_info': '统计信息',
            'table_details_sample_data': '样本数据',
            'table_details_include_extras': ' (包含: {extras})',
            'table_details_table_title': '📊 表: {table_name}',
            'table_details_db_type': '🗄️ 数据库类型: {dialect}',
            'table_details_columns_info': '📋 列信息:',
            'table_details_primary_key': '🔑 主键: {keys}',
            'table_details_foreign_keys': '🔗 外键:',
            'table_details_indexes': '📍 索引:',
            'table_details_statistics': '📈 统计信息:',
            'table_details_row_count': '  - 行数: {count:,}',
            'table_details_size': '  - 大小: {size} MB',
            'table_details_sample_data_title': '🔍 样本数据:',
            'table_details_summary': '获取表 {table_name} 的完整结构信息',
            'table_details_table_not_found': "表 '{table_name}' 不存在",
            'table_details_suggestions': '。您是否想查看: {suggestions}',
            'table_details_name_empty': 'Table name cannot be empty',
            'table_details_invalid_name': 'Invalid table name: contains forbidden characters',
            
            # file_write_tool
            'file_write_tool_name': '文件写入',
            'file_write_written': '{icon} 已写入 {filename}',
            'file_write_size': '💾 大小: {size}',
            'file_write_location': '📁 位置: {location}',
            'file_write_compression': '🗜️ 压缩: {compression}',
            'file_write_duration': '⏱️ 耗时: {duration:.1f}秒',
            'file_write_path_empty': 'File path cannot be empty',
            'file_write_path_not_absolute': 'Path must be absolute',
            'file_write_content_none': 'Content cannot be None',
            'file_write_action_overwrite': '写入',
            'file_write_action_append': '追加到',
            'file_write_action_create': '创建',
            'file_write_description': '{action}{format}文件: {filename}',
            'file_write_dangerous_path': '⚠️ 危险路径: {path}',
            'file_write_cannot_read_existing': '[无法读取现有文件内容]',
            'file_write_invalid_format': 'Invalid format: {format}. Supported formats: {supported}',
            'file_write_access_denied': 'Access denied: {path} is outside allowed directories',
            'file_write_already_exists': 'File already exists: {path}',
            'file_write_progress': '📝 正在写入{format}文件...\n📁 路径: {path}\n📊 大小: {size}',
            'file_write_failed': 'Failed to write file: {error}',
            'file_write_failed_llm': 'Error writing to {path}: {error}\nType: {type}',
            'file_write_diff_current': '{filename} (当前)',
            'file_write_diff_proposed': '{filename} (提议)',
            'file_write_content_truncated': '\n... [剩余内容省略]',
            'file_write_confirm_overwrite': 'Confirm overwriting {filename}',
            'file_write_confirm_append': 'Confirm appending to {filename}',
            'file_write_confirm_create': 'Confirm creating {filename}',
            'file_write_sql_header': '-- Generated by DbRheo at {timestamp}\n-- {separator}\n\n',
            'file_write_markdown_header': '# Data Export Report\n\nGenerated at: {timestamp}\n\n{content}',
            'file_write_compression_note': '(压缩: {compression})',
            
            # database_connect_tool补充
            'db_connect_need_connection_string': 'connect和test操作需要提供connection_string',
            'db_connect_need_database_name': 'switch操作需要提供database_name',
            'db_connect_action_connect': '连接到数据库: {cs}',
            'db_connect_action_test': '测试数据库连接',
            'db_connect_action_list': '列出支持的数据库类型',
            'db_connect_action_switch': '切换到数据库: {database_name}',
            'db_connect_action_default': '数据库操作',
            'db_connect_tool_name': '数据库连接器',
            'db_connect_checking_types': '🔍 检查支持的数据库类型...',
            'db_connect_driver_ready': '✅ **{type}** - 驱动已安装，可以使用',
            'db_connect_connecting': '🔗 正在连接数据库...',
            'db_connect_overview': '**数据库概览**:',
            'db_connect_found_types': '找到{count}个可用数据库类型',
            'db_connect_detected_type': '📊 检测到数据库类型: {type}',
            'db_connect_test_success_summary': '连接测试成功',
            'db_connect_test_failed_summary': '连接测试失败',
            'db_connect_switched_to_conn': '已切换到连接: {name}',
            'db_connect_switched_to_conn_display': '✅ 已切换到数据库连接: {name}',
            'db_connect_switched_to_config': '已切换到配置的数据库: {name}',
            'db_connect_switched_to_db_display': '✅ 已切换到数据库: {name}',
            'db_connect_not_found_header': '❌ 未找到数据库连接: {name}',
            'db_connect_not_found_error': '未找到数据库连接: {name}',
            'db_connect_found_connections': '找到 {count} 个活动连接',
            'db_connect_testing': '🔌 测试数据库连接...',
            'db_connect_active_connections': '**活动连接**:',
            
            # sql_tool
            'sql_tool_name': 'SQL执行器',
            'sql_empty_error': 'SQL语句不能为空',
            'sql_exec_description': '执行SQL操作: {sql}',
            'sql_confirm_title': '确认执行{operation}操作',
            'sql_mode_execute': '正在执行SQL查询...',
            'sql_mode_validate': '正在验证SQL语法...',
            'sql_mode_dry_run': '正在预演SQL执行（不会提交）...',
            'sql_processing': '处理中...',
            'sql_validate_disabled_error': 'validate模式已被禁用。建议使用dry_run模式进行安全的SQL预演，或直接执行让数据库引擎验证语法。',
            'sql_feature_disabled': '功能已禁用',
            'sql_validate_disabled_llm': 'validate模式已禁用。请使用dry_run进行预演。',
            'sql_executing_query': '执行查询中...',
            'sql_query_success': '查询成功，返回{count}行数据',
            'sql_executing_command': '执行命令中...',
            'sql_execution_failed': 'SQL执行失败: {error}',
            'sql_exec_failed_summary': 'SQL执行失败',
            'sql_query_no_data': '查询完成，无数据返回。\n执行时间: {time:.2f}秒',
            'sql_query_result_header': '查询返回 {count} 行数据（执行时间: {time:.2f}秒）\n',
            'sql_more_rows': '\n... 还有 {count} 行数据未显示',
            'sql_op_insert': '插入',
            'sql_op_update': '更新',
            'sql_op_delete': '删除',
            'sql_op_create': '创建',
            'sql_op_alter': '修改',
            'sql_op_drop': '删除',
            'sql_op_dml': '数据操作',
            'sql_op_ddl': '结构定义',
            'sql_op_generic': '{type}操作',
            'sql_command_success_rows': '{operation}成功，影响{rows}行',
            'sql_command_success': '{operation}成功',
            'sql_execution_time': '执行时间: {time:.2f}秒',
            'sql_affected_rows': '影响行数: {rows}',
            'sql_table_case_mismatch': '表名大小写不匹配: \'{table}\' 应该是 \'{correct}\'',
            'sql_table_not_found_suggest': '表 \'{table}\' 不存在。您是否想用: {suggestions}',
            'sql_table_not_found': '表 \'{table}\' 不存在',
            'sql_sqlite_no_describe': 'SQLite不支持DESCRIBE，请使用 PRAGMA table_info(表名)',
            'sql_sqlite_no_show_columns': 'SQLite不支持SHOW COLUMNS，请使用 PRAGMA table_info(表名)',
            'sql_sqlite_no_show_tables': 'SQLite不支持SHOW TABLES，请使用 SELECT name FROM sqlite_master WHERE type="table"',
            'sql_mysql_no_pragma': 'MySQL不支持PRAGMA，请使用 DESCRIBE 或 SHOW COLUMNS',
            'sql_unknown_type': '无法识别的SQL语句类型',
            'sql_dangerous_no_where': '⚠️ 危险: {type}操作没有WHERE条件，将影响所有数据',
            'sql_estimated_impact': '预计将影响 {count} 行数据',
            'sql_validation_failed_status': '❌ 验证失败',
            'sql_validation_failed_summary': 'SQL验证失败: {count}个错误',
            'sql_validation_warning_status': '⚠️ 验证通过（有警告）',
            'sql_validation_warning_summary': 'SQL验证通过，但有{count}个警告',
            'sql_validation_pass_status': '✅ 验证通过',
            'sql_validation_pass_summary': 'SQL验证通过，语法正确',
            'sql_errors_label': '错误:',
            'sql_warnings_label': '警告:',
            'sql_info_label': '信息:',
            'sql_type_label': 'SQL类型: {type}',
            'sql_dialect_label': '数据库方言: {dialect}',
            'sql_validation_error': '验证过程出错: {error}',
            'sql_validation_failed': '验证失败',
            'sql_validation_error_display': '❌ 验证过程出错: {error}',
            'sql_dry_run_no_transaction': '当前数据库不支持事务，无法执行dry_run模式',
            'sql_dry_run_unavailable': 'Dry run不可用',
            'sql_dry_run_query_success': '[DRY RUN] 查询成功，返回{count}行数据',
            'sql_dry_run_mode_prefix': '🔍 DRY RUN 模式',
            'sql_dry_run_mode_rollback': '🔍 DRY RUN 模式（已回滚）',
            'sql_dry_run_rollback_notice': '✅ 所有更改已回滚，数据库未被修改',
            'sql_dry_run_summary_rollback': '[DRY RUN] {summary}（已回滚）',
            'sql_dry_run_failed_error': 'Dry run执行失败: {error}',
            'sql_dry_run_failed_summary': 'Dry run失败',
            'sql_dry_run_failed_display': '❌ Dry run执行失败: {error}',
            
            # risk_evaluator
            'risk_dangerous_pattern': '检测到危险操作模式: {pattern}',
            'risk_high_operation': '高风险操作：可能导致数据永久丢失',
            'risk_no_where': '缺少WHERE条件：可能影响所有数据',
            'risk_multiple_tables': '涉及多个表({count}个)：操作复杂度较高',
            'risk_large_table': '大表操作({table})：可能影响性能',
            'risk_foreign_key': '可能影响外键约束关系',
            'risk_full_scan': '可能导致全表扫描',
            'risk_complex_join': '复杂JOIN操作({count}个)：可能影响性能',
            'risk_sql_injection': '检测到潜在SQL注入模式',
            'risk_recommend_test': '建议在测试环境中先验证此操作',
            'risk_recommend_where': '建议添加WHERE条件限制影响范围',
            'risk_recommend_backup': '建议先创建数据备份',
            'risk_recommend_index': '建议添加适当的索引或WHERE条件',
            
            # database_export_tool
            'export_tool_name': '数据导出',
            'export_sql_empty': 'SQL query cannot be empty',
            'export_path_empty': 'Output path cannot be empty',
            'export_path_not_allowed': 'Export not allowed to: {path}',
            'export_path_invalid': 'Invalid output path: {error}',
            'export_format_unsupported': 'Unsupported file format: {format}',
            'export_description': '导出查询结果到 {format} 文件: {filename}',
            'export_confirm_overwrite_title': '确认覆盖文件',
            'export_confirm_overwrite_message': '文件 {filename} 已存在，是否覆盖？',
            'export_confirm_overwrite_details': '完整路径: {path}',
            'export_progress': '正在导出数据到 {format} 格式...\n文件: {filename}',
            'export_failed_error': 'Export failed: {error}',
            'export_failed_summary': '导出失败',
            'export_failed_display': '❌ 导出失败: {error}',
            'export_rows_progress': '已导出 {count:,} 行...',
            'export_csv_success': '成功导出 {count:,} 行数据到 CSV 文件',
            'export_csv_success_display': '✅ 导出成功\n📄 文件: {filename}\n📊 格式: CSV\n📏 行数: {rows:,}\n💾 大小: {size}',
            'export_csv_failed': 'CSV export failed: {error}',
            'export_csv_failed_summary': 'CSV导出失败',
            'export_json_success': '成功导出 {count:,} 行数据到 JSON 文件',
            'export_json_success_display': '✅ 导出成功\n📄 文件: {filename}\n📊 格式: JSON\n📏 行数: {rows:,}\n💾 大小: {size}',
            'export_json_failed': 'JSON export failed: {error}',
            'export_json_failed_summary': 'JSON导出失败',
            'export_excel_missing_lib': 'Excel export requires \'openpyxl\' package. Please install it: pip install openpyxl',
            'export_excel_missing_lib_summary': '缺少Excel支持库',
            'export_excel_success': '成功导出 {count:,} 行数据到 Excel 文件',
            'export_excel_success_display': '✅ 导出成功\n📄 文件: {filename}\n📊 格式: Excel\n📏 行数: {rows:,}\n💾 大小: {size}',
            'export_excel_failed': 'Excel export failed: {error}',
            'export_excel_failed_summary': 'Excel导出失败',
            'export_sql_header_1': '-- Exported from DbRheo on {date}\n',
            'export_sql_header_2': '-- Original query: {sql}\n\n',
            'export_sql_success': '成功导出 {count:,} 行数据到 SQL 文件',
            'export_sql_success_display': '✅ 导出成功\n📄 文件: {filename}\n📊 格式: SQL INSERT\n📏 行数: {rows:,}\n💾 大小: {size}',
            'export_sql_failed': 'SQL export failed: {error}',
            'export_sql_failed_summary': 'SQL导出失败',
            
            # schema_discovery
            'schema_tool_name': '表发现工具',
            'schema_get_tables': '获取数据库表名',
            'schema_pattern_suffix': '（匹配模式: {pattern}）',
            'schema_include_views_suffix': '，包含视图',
            'schema_get_error': '获取表名失败: {error}',
            'schema_get_failed': '获取表名失败',
            'schema_summary_with_version': '{type} {version} 数据库，包含{count}个表',
            'schema_summary': '{type} 数据库，包含{count}个表',
            'schema_db_name': '🗄️ 数据库名: {name}\n',
            'schema_tips_prefix': '💡 提示: ',
            'schema_objects_list': '📋 数据库对象列表:',
            'schema_table_label': '表',
            'schema_view_label': '视图',
            'schema_type_count': '{type} ({count}个):',
            'schema_more_items': '  ... 还有 {count} 个',
            'schema_tip_sqlite': '使用PRAGMA table_info(table)查看表结构，不支持DESCRIBE',
            'schema_tip_mysql': '支持DESCRIBE table或SHOW COLUMNS FROM table查看表结构',
            'schema_tip_postgresql': '使用\\d table查看表结构，支持INFORMATION_SCHEMA',
            'schema_tip_oracle': '使用DESC table查看表结构，注意大小写敏感',
            'schema_tip_sqlserver': '使用sp_help \'table\'查看表结构',
            'schema_dialect_default': '数据库方言: {dialect}',
            
            # file_read_tool
            'file_read_tool_name': '文件读取',
            'file_read_path_empty': 'File path cannot be empty',
            'file_read_path_not_absolute': 'Path must be absolute',
            'file_read_description': '读取文件: {filename}',
            'file_read_offset_suffix': ' (从第{line}行开始)',
            'file_read_limit_suffix': ' (限制{limit}行)',
            'file_read_access_denied': 'Access denied: {path} is outside allowed directories.\n\nAllowed directories:\n{dirs}\n\nPlease check the file path format and try again with a path within the allowed directories.',
            'file_read_not_found': 'File not found: {path}',
            'file_read_not_file': 'Path is not a file: {path}',
            'file_read_too_large': 'File too large: {size} bytes (max: {max} bytes)',
            'file_read_failed': 'Failed to read file: {error}',
            'file_read_failed_llm': 'Error reading {path}: {error}',
            'file_read_failed_display': '❌ 读取文件失败: {error}',
            'file_read_image_summary': '读取图片文件: {filename}',
            'file_read_image_llm': '[图片文件: {filename}, 类型: {type}, 大小: {size}]',
            'file_read_image_display': '🖼️ {filename}\n📊 类型: {type}\n💾 大小: {size}',
            'file_read_image_failed': 'Failed to read image: {error}',
            'file_read_binary_summary': '二进制文件: {filename}',
            'file_read_binary_llm': '[二进制文件: {filename}, 类型: {type}, 大小: {size} 字节]',
            'file_read_binary_display': '🔒 二进制文件\n📄 {filename}\n📊 类型: {type}\n💾 大小: {size}',
            'file_read_unknown_type': '未知',
            'file_read_line_truncated': '... [截断]\n',
            'file_read_offset_out_of_range': '[文件只有 {total} 行，但请求从第 {line} 行开始读取]\n',
            'file_read_sql_summary': '读取SQL脚本: {filename} ({lines}行)',
            'file_read_partial_suffix': ' [部分内容]',
            'file_read_sql_statements': '📊 语句数: ~{count}',
            'file_read_sql_types': '📝 类型: {types}',
            'file_read_unknown': '未知',
            'file_read_has_more': '⚠️ 文件还有更多内容',
            'file_read_file_size': '💾 文件大小: {size}',
            'file_read_json_partial': '读取JSON文件: {filename} ({lines}行) [部分内容]',
            'file_read_json_partial_llm': 'JSON文件部分内容:\n\n{content}\n\n[文件被截断，完整解析需要读取全部内容]',
            'file_read_json_partial_display': '📄 {filename}\n📏 已读取: {lines}行\n⚠️ 内容被截断，无法解析结构',
            'file_read_json_summary': '读取JSON文件: {filename}',
            'file_read_json_llm': 'JSON内容:\n\n{content}',
            'file_read_json_display': '📄 {filename}\n📊 结构: {structure}...\n📏 行数: {lines}',
            'file_read_json_invalid': '无效的JSON文件',
            'file_read_json_error_llm': 'JSON解析错误 {filename}: {error}\n\n内容:\n{content}',
            'file_read_json_error_display': '❌ JSON解析错误: {error}',
            'file_read_yaml_partial': '读取YAML文件: {filename} ({lines}行) [部分内容]',
            'file_read_yaml_partial_llm': 'YAML文件部分内容:\n\n{content}\n\n[文件被截断，完整解析需要读取全部内容]',
            'file_read_yaml_partial_display': '📄 {filename}\n📏 已读取: {lines}行\n⚠️ 内容被截断，无法解析结构',
            'file_read_yaml_unknown_structure': '未知结构',
            'file_read_yaml_top_keys': '顶级键: {keys}',
            'file_read_yaml_more_keys': ' ... (共{count}个)',
            'file_read_yaml_array': '数组，包含{count}个元素',
            'file_read_yaml_summary': '读取YAML配置文件: {filename}',
            'file_read_yaml_llm': 'YAML内容:\n\n{content}',
            'file_read_yaml_invalid': '无效的YAML文件',
            'file_read_yaml_error_llm': 'YAML解析错误 {filename}: {error}\n\n内容:\n{content}',
            'file_read_yaml_error_display': '❌ YAML解析错误: {error}',
            'file_read_csv_summary': '读取CSV文件: {filename} ({rows}行数据)',
            'file_read_csv_llm': 'CSV文件内容:\n\n{content}',
            'file_read_more_data_hint': '\n\n[文件还有更多数据，使用offset和limit参数分页读取]',
            'file_read_csv_columns': '📊 列数: {count}',
            'file_read_csv_headers': '📋 列名: {headers}{more}',
            'file_read_csv_rows': '📏 数据行: {count}',
            'file_read_more_data': '⚠️ 文件还有更多数据',
            'file_read_csv_empty': '空CSV文件',
            'file_read_csv_empty_llm': '空CSV文件: {filename}',
            'file_read_csv_empty_display': '📄 空CSV文件',
            'file_read_text_read': '读取 {filename}',
            'file_read_text_from_line': '从第 {line} 行',
            'file_read_text_lines': '{lines} 行',
            'file_read_text_partial': '部分内容',
            'file_read_from_line_context': '从第 {line} 行开始',
            'file_read_has_more_context': '文件有更多内容',
            'file_read_partial_content': '[文件部分内容: {context}]\n\n{content}',
            'file_read_use_pagination': '\n[使用 offset 和 limit 参数可以读取更多内容]',
            'file_read_start_from': '📖 从第 {line} 行开始',
            'file_read_lines_count': '📏 读取了 {lines} 行',
            'file_read_encoding': '🔤 编码: {encoding}',
            
            # database_connect_tool补充的硬编码文本
            'db_connect_unknown_action': '未知操作: {action}',
            'db_connect_operation_failed': '操作失败',
            'db_connect_error_info': '错误信息',
            'db_connect_possible_reasons': '可能的原因',
            'db_connect_reason_service_not_started': '数据库服务未启动',
            'db_connect_reason_wrong_params': '连接参数错误（主机、端口、用户名、密码）',
            'db_connect_reason_network_issue': '网络连接问题',
            'db_connect_reason_driver_not_installed': '数据库驱动未安装',
            'db_connect_suggestions': '建议',
            'db_connect_suggestion_check_service': '检查数据库服务状态',
            'db_connect_suggestion_verify_string': '验证连接字符串格式',
            'db_connect_suggestion_check_firewall': '确认防火墙设置',
            'db_connect_suggestion_list_drivers': '使用 action=\'list\' 查看需要安装的驱动',
            'db_connect_unknown_version': '未知',
            'db_connect_important_note': '重要：使用SQL工具时，请在database参数中使用别名 \'{alias}\'',
            'db_connect_example_usage': '示例: sql_execute(sql="SELECT * FROM users", database="{alias}")',
            'db_connect_table_count_label': '表数量',
            'db_connect_view_count_label': '视图数量',
            'db_connect_size_label': '数据库大小',
            'db_connect_already_connected': '已连接到{db_type}数据库',
            'db_connect_memory_db_comment': '# 内存数据库',
            'db_connect_failed': '连接失败',
            'db_connect_failed_error': '连接失败: {error}',
            'db_connect_switch_failed': '切换失败',
            'db_connect_configured_databases': '配置的数据库',
            'db_connect_no_connections': '无',
            'db_connect_local_connections': '本地连接',
            'db_connect_global_connections': '全局注册连接',
            'db_connect_no_active_connections': '没有活动的数据库连接',
            'db_connect_use_connect_hint': '使用 action=\'connect\' 创建新连接',
            'db_connect_active_db_connections': '活动数据库连接',
            
            # file_write_tool补充的硬编码文本
            'file_write_file_description': '{action}{format}文件: {filename}',
            'file_write_file_exists': 'File already exists: {path}',
            'file_write_writing_progress': '写入中... ({percent}%)',
            'file_write_appending_progress': '追加中... ({percent}%)',
            'file_write_creating_progress': '创建中... ({percent}%)',
            'file_write_write_failed': 'Failed to write file: {error}',
            'file_write_current_file': '{filename} (当前)',
            'file_write_proposed_file': '{filename} (提议)',
            'file_write_wrote_size': 'Wrote {size}',
            'file_write_to_file': 'to {filename}',
            'file_write_compressed': '(压缩: {compression})',
            'file_write_success_display': '{icon} 已写入 {filename}',
            'file_write_success_size': '💾 大小: {size}',
            'file_write_success_location': '📁 位置: {location}',
            'file_write_success_compression': '🗜️ 压缩: {compression}',
            'file_write_success_duration': '⏱️ 耗时: {duration:.1f}秒',
            
            # table_details_tool补充的硬编码文本
            'table_details_failed': 'Failed to get table details: {error}',
            'table_details_sqlite_size_unavailable': 'Size information not available for SQLite',
            
            # code_execution_tool
            'code_exec_tool_name': '代码执行器',
            'code_exec_python_desc': 'Python代码（数据分析、自动化脚本）',
            'code_exec_js_desc': 'JavaScript代码（Node.js环境）',
            'code_exec_shell_desc': 'Shell脚本（系统命令、文件操作）',
            'code_exec_sql_desc': 'SQL脚本（直接执行）',
            'code_exec_empty': '代码不能为空',
            'code_exec_unsupported_lang': '不支持的语言：{language}。支持的语言：{supported}',
            'code_exec_invalid_timeout': '超时时间必须在1-300秒之间',
            'code_exec_description': '执行{language}代码：{preview}...',
            'code_exec_danger_pattern': '包含危险操作：{pattern}',
            'code_exec_lang_danger': '包含{language}危险操作：{pattern}',
            'code_exec_confirm_title': '确认执行{language}代码',
            'code_exec_danger_detected': '检测到潜在危险操作',
            'code_exec_preview': '\n\n代码预览：\n{code}...',
            'code_exec_running': '🚀 正在执行{language}代码...\n```{language}\n{code}\n```',
            'code_exec_success_summary': '{language}代码执行成功',
            'code_exec_failed_summary': '{language}代码执行失败：{error_type}',
            'code_exec_exception': '代码执行异常：{error}\n{trace}',
            'code_exec_failed': '代码执行失败',
            'code_exec_failed_display': '❌ 执行失败\n\n{error}',
            'code_exec_context_comment': '# 自动注入的上下文',
            'code_exec_sql_result_comment': '# SQL查询结果',
            'code_exec_dataframe_comment': '# 如果是表格数据，自动转换为DataFrame',
            'code_exec_user_code_sep': '\n\n# 用户代码\n',
            'code_exec_js_context_comment': '// 自动注入的上下文',
            'code_exec_js_sql_comment': '// SQL查询结果',
            'code_exec_js_user_code_sep': '\n\n// 用户代码\n',
            'code_exec_lang_not_supported': '不支持的语言：{language}',
            'code_exec_output_truncated': '\n... [输出被截断]',
            'code_exec_error_truncated': '\n... [错误输出被截断]',
            'code_exec_timeout': '执行超时（{timeout}秒）',
            'code_exec_success_title': '✅ {language}代码执行成功',
            'code_exec_time': '⏱️ 执行时间：{time:.2f}秒',
            'code_exec_stdout_title': '### 标准输出：',
            'code_exec_stderr_title': '### 标准错误：',
            'code_exec_failed_title': '❌ {language}代码执行失败',
            'code_exec_error_title': '### 错误信息：',
            'code_exec_error_unknown': '未知错误',
            'code_exec_error_unknown_suggest': '检查代码逻辑',
            'code_exec_error_syntax': '语法错误',
            'code_exec_error_syntax_suggest': '检查代码语法：括号匹配、缩进、冒号等',
            'code_exec_error_name': '变量未定义',
            'code_exec_error_name_suggest': '检查变量名拼写或在使用前先定义变量',
            'code_exec_error_module': '模块导入错误',
            'code_exec_error_module_suggest': '检查模块名称或使用内置模块（如pandas、numpy、matplotlib）',
            'code_exec_error_timeout_type': '执行超时',
            'code_exec_error_timeout_suggest': '优化代码性能或增加超时时间',
            'code_exec_error_runtime': '运行时错误',
            'code_exec_error_runtime_suggest': '检查错误信息，修复相应的逻辑问题',
            
            # web_search_tool
            'web_search_tool_name': '网络搜索',
            'web_search_no_desc': 'No description available',
            'web_search_query_empty': 'Search query cannot be empty',
            'web_search_description': 'Search web for: {query}... (max {max_results} results)',
            'web_search_searching': '🔍 Searching with {backend}: {query}...',
            'web_search_fallback': '🔄 Trying fallback search...',
            'web_search_no_results': 'No results found',
            'web_search_no_results_llm': "No search results found for '{query}' using {backend}",
            'web_search_no_results_display': 'No results found',
            'web_search_found_results': "Found {count} results for '{query}'",
            'web_search_failed': 'Search failed using {backend}: {error}',
            'web_search_failed_display': 'Search failed',
            'web_search_results_header': "Web search results for '{query}':\n\n",
            'web_search_result_url': '   URL: {url}\n',
            'web_search_result_summary': '   Summary: {summary}\n',
            'web_search_results_footer': '\nBased on these search results, I can provide relevant information about the query.',
            'web_search_no_results_text': 'No search results found.',
            'web_search_display_header': '🔍 Search Results (via {backend}):\n',
            
            # web_fetch_tool
            'web_fetch_tool_name': '网页内容获取',
            'web_fetch_no_urls': 'No URLs found in prompt or urls parameter',
            'web_fetch_too_many_urls': 'Too many URLs (max {max})',
            'web_fetch_invalid_url': 'Invalid URL: {url}',
            'web_fetch_desc_single': '获取网页内容: {url}...',
            'web_fetch_desc_multiple': '获取 {count} 个网页的内容',
            'web_fetch_confirm_private': '访问内网地址需要确认',
            'web_fetch_risk_private': '访问内部网络资源',
            'web_fetch_no_urls_error': 'No URLs found to fetch',
            'web_fetch_progress': '🌐 获取网页 {current}/{total}: {url}',
            'web_fetch_all_failed': 'Failed to fetch any content',
            'web_fetch_summary': '获取了 {count} 个网页的内容',
            'web_fetch_summary_errors': '，{count} 个失败',
            'web_fetch_content_truncated': '\n... [内容已截断]',
            'web_fetch_results_header': '🌐 网页内容获取结果:\n',
            'web_fetch_success_count': '✅ 成功获取: {count} 个网页',
            'web_fetch_fail_count': '❌ 获取失败: {count} 个网页',
            'web_fetch_preview': '   预览: {content}\n',
            'web_fetch_error_line': '   错误: {error}\n',
            
            # directory_list_tool
            'dir_list_tool_name': '目录浏览',
            'dir_list_path_empty': 'Directory path cannot be empty',
            'dir_list_access_denied': 'Access denied: {path} is outside allowed directories',
            'dir_list_invalid_path': 'Invalid path: {error}',
            'dir_list_invalid_pattern': 'Invalid pattern: must not contain path separators',
            'dir_list_description': '列出目录: {path}',
            'dir_list_pattern_suffix': ' (匹配: {pattern})',
            'dir_list_recursive_suffix': ' [递归]',
            'dir_list_access_denied_detail': 'Access denied: {path} is outside allowed directories.\n\nAllowed directories:\n{dirs}\n\nPlease check the directory path format and try again with a path within the allowed directories.',
            'dir_list_not_found': 'Directory not found: {path}',
            'dir_list_not_directory': 'Path is not a directory: {path}',
            'dir_list_failed': 'Failed to list directory: {error}',
            'dir_list_base_path': '📁 {path}',
            'dir_list_summary': '📊 {dirs} directories, {files} files',
            'dir_list_truncated': '⚠️ Showing first {showing} of {total} items',
            'dir_list_result_summary': '列出 {path} 中的 {count} 个项目',
            'dir_list_total_suffix': ' (共 {total} 个)',
            
            # ShellTool相关的中文默认文本
            'shell_tool_name': 'Shell执行器',
            'shell_confirm_title': '确认执行Shell命令',
            'shell_command_empty': '命令不能为空',
            'shell_command_substitution': '出于安全考虑，不允许使用 $() 命令替换',
            'shell_absolute_path': '工作目录不能是绝对路径，必须相对于项目根目录',
            'shell_dir_not_exist': '目录不存在: {dir}',
            'shell_path_not_dir': '路径不是目录: {dir}',
            'shell_dir_validation_failed': '目录验证失败: {error}',
            'shell_invalid_timeout': '超时时间必须在1-300秒之间',
            'shell_desc_with_description': '执行Shell命令: {desc}',
            'shell_desc_with_command': '执行Shell命令: {cmd}',
            'shell_decode_success': '使用编码 {encoding} 成功解码输出',
            'shell_command_substitution_reason': '出于安全考虑，不允许使用 $() 命令替换',
            'shell_command_blacklisted': '命令 \'{command}\' 被配置禁止执行',
            'shell_command_not_whitelisted': '严格模式下，命令 \'{command}\' 不在允许列表中',
            'shell_db_command_reason': '数据库管理命令，通常安全',
            'shell_safe_command_reason': '常见的只读系统命令',
            'shell_needs_confirmation_reason': '需要用户确认的系统命令',
            'shell_executing': '🔧 执行Shell命令{desc}\n```bash\n{command}\n```',
            'shell_blocked_summary': '命令被安全策略阻止',
            'shell_security_check_failed': '❌ 安全检查失败: {reason}',
            'shell_execution_exception': 'Shell命令执行异常: {error}',
            'shell_failed_summary': '执行失败',
            'shell_failed_display': '❌ 执行失败\n\n{error}',
            'shell_stream_output': '📤 输出:\n```\n{text}\n```',
            'shell_stream_error': '📤 错误输出:\n```\n{text}\n```',
            'shell_timeout_message': '执行超时 {timeout}秒',
            'shell_truncated_lines': '中间{truncated}行被省略，共{total}行',
            'shell_stderr_truncated': '错误输出被部分省略',
            'shell_execution_error': '执行异常: {error}',
            'shell_success_title': '✅ Shell命令执行成功',
            'shell_execution_time': '⏱️ 执行时间: {time:.2f}秒',
            'shell_stdout_header': '### 标准输出:',
            'shell_stderr_header': '### 标准错误:',
            'shell_success_summary': 'Shell命令执行成功 (退出码: {code})',
            'shell_failed_title': '❌ Shell命令执行失败',
            'shell_exit_code': '🔢 退出码: {code}',
            'shell_error_header': '### 错误信息:',
            'shell_failed_summary_detail': 'Shell命令执行失败 (退出码: {code})',
            
            # WebSearchTool相关的中文默认文本
            
            # SchemaDiscoveryTool相关的中文默认文本
            'schema_tool_description': '快速获取数据库架构信息。功能：列出所有表名、按pattern过滤、包含视图选项、支持schema/database切换。比直接SQL更简洁高效。',
            'schema_tip_sqlserver': 'Use sp_help \'table\' to view table structure',
            
            # RiskEvaluator相关的中文默认文本
            
            # 更多默认文本会根据需要添加
        }
        
        if self._i18n:
            # 检查i18n是否有get方法（支持字典和对象两种形式）
            text = None
            if isinstance(self._i18n, dict) and 'get' in self._i18n:
                # 字典形式的i18n适配器
                text = self._i18n['get'](key, **kwargs)
            elif hasattr(self._i18n, 'get'):
                # 对象形式的i18n
                text = self._i18n.get(key, **kwargs)
            
            if text is not None:
                # 如果i18n返回的是key本身（说明没找到翻译），则使用默认值
                if text == key:
                    if default is not None:
                        text = default
                        # 手动格式化默认文本
                        for k, v in kwargs.items():
                            text = text.replace(f'{{{k}}}', str(v))
                    else:
                        text = default_texts.get(key, key)
                        # 手动格式化默认文本
                        for k, v in kwargs.items():
                            text = text.replace(f'{{{k}}}', str(v))
                return text
        
        # 使用优先级：自定义默认值 > 内置默认文本 > key本身
        if default is not None:
            text = default
        else:
            text = default_texts.get(key, key)
        
        # 简单的格式化
        for k, v in kwargs.items():
            text = text.replace(f'{{{k}}}', str(v))
        
        return text
