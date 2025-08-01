"""
SQLTool - 核心SQL执行工具
智能SQL执行和风险评估，支持多数据库方言和流式输出
"""

from typing import Optional, Callable, Union, Dict, Any, List
import time
from .base import DatabaseTool
from .risk_evaluator import DatabaseRiskEvaluator, RiskLevel
from ..types.core_types import AbortSignal
from ..types.tool_types import ToolResult, DatabaseConfirmationDetails, SQLExecuteConfirmationDetails
from ..config.base import DatabaseConfig
from ..utils.debug_logger import log_info


class SQLTool(DatabaseTool):
    """
    核心SQL执行工具 - 智能化数据库操作
    - 智能SQL执行和风险评估
    - 多数据库方言支持
    - 流式输出和进度更新（can_update_output）
    - 事务管理集成
    """
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        
        super().__init__(
            name="sql_execute",
            display_name=self._('sql_tool_name', default='SQL执行器') if i18n else "SQL执行器",
            description="Executes SQL queries with intelligent error recovery and dialect adaptation. Automatically analyzes syntax issues, corrects common errors, and handles various database systems with comprehensive result formatting.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "要执行的SQL语句，支持多行和复杂查询"
                    },
                    "database": {
                        "type": "string",
                        "description": "数据库连接别名或连接字符串。使用database_connect创建的别名(如'ai_support_db_conn')或直接传入连接字符串"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["execute", "validate", "dry_run"],  # validate已禁用但保留以兼容
                        "description": "执行模式: execute(执行), dry_run(预演但不提交)",  # validate已移除
                        "default": "execute"
                    },
                    "explain": {
                        "type": "boolean",
                        "description": "是否显示执行计划分析（默认为false）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "查询结果行数限制（可选）。Agent可根据查询需求自主决定合适的限制值。"
                    }
                },
                "required": ["sql"]
            },
            is_output_markdown=True,  # 支持表格和代码高亮
            can_update_output=True,   # 支持流式执行进度
            should_summarize_display=True,
            i18n=i18n  # 传递i18n给基类
        )
        self.config = config
        self.risk_evaluator = DatabaseRiskEvaluator(config, i18n)
        
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """三层验证：语法 + 安全 + 权限"""
        sql = params.get("sql", "").strip()
        if not sql:
            return self._('sql_empty_error', default='SQL语句不能为空')
            
        # TODO: 实现完整的验证逻辑
        # 1. 语法验证
        # 2. 安全验证  
        # 3. 权限验证
        
        return None
        
    def get_description(self, params: Dict[str, Any]) -> str:
        """生成执行描述"""
        sql = params.get("sql", "").strip()
        return self._('sql_exec_description', default='执行SQL操作: {sql}', sql=f"{sql[:50]}...")
        
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> Union[bool, DatabaseConfirmationDetails]:
        """智能确认机制 - 基于多维度风险评估"""
        sql = params.get("sql", "").strip()
        mode = params.get("mode", "execute")
        
        # validate和dry_run模式不需要确认（因为不会真正修改数据）
        if mode in ["validate", "dry_run"]:
            return False

        # 执行风险评估
        risk_assessment = self.risk_evaluator.evaluate_sql_risk(sql)

        # 如果不需要确认，直接返回False
        if not risk_assessment.requires_confirmation:
            return False

        # 创建确认详情
        return SQLExecuteConfirmationDetails(
            title=self._('sql_confirm_title', default='确认执行{operation}操作', operation=risk_assessment.operation_type),
            sql_query=sql,
            root_operation=risk_assessment.operation_type,
            risk_assessment={
                "level": risk_assessment.level.value,
                "score": risk_assessment.score,
                "reasons": risk_assessment.reasons,
                "recommendations": risk_assessment.recommendations,
                "estimated_impact": risk_assessment.estimated_impact,
                "affected_tables": risk_assessment.affected_tables
            },
            estimated_impact=len(risk_assessment.affected_tables)
        )
        
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """执行SQL查询 - 支持execute/validate/dry_run模式"""
        sql = params.get("sql", "").strip()
        database = params.get("database")  # 可选的数据库选择
        mode = params.get("mode", "execute")
        explain = params.get("explain", False)
        limit = params.get("limit")
        
        # 根据模式显示不同的提示
        mode_display = {
            "execute": self._('sql_mode_execute', default='正在执行SQL查询...'),
            "validate": self._('sql_mode_validate', default='正在验证SQL语法...'),  # DEPRECATED: 已禁用
            "dry_run": self._('sql_mode_dry_run', default='正在预演SQL执行（不会提交）...')
        }
        
        if update_output:
            update_output(f"{mode_display.get(mode, self._('sql_processing', default='处理中...'))}\n```sql\n{sql[:200]}{'...' if len(sql) > 200 else ''}\n```")
            
        try:
            # 获取数据库适配器
            log_info("SQLTool", f"Getting adapter for database={database}")
            from ..adapters.adapter_factory import get_adapter
            # Agent调试: database参数 = {database}
            adapter = await get_adapter(self.config, database)
            log_info("SQLTool", f"Successfully got adapter: {adapter}")
            
            # 连接数据库
            await adapter.connect()
            
            try:
                # 如果是验证模式，返回禁用提示
                if mode == "validate":
                    # DEPRECATED: validate模式已被禁用 - 2025-07-20
                    # 原因：基础的语法检查不如大模型智能，且容易给用户错误的安全感
                    # 建议：使用dry_run模式进行安全的SQL预演，或让Agent直接分析SQL
                    return ToolResult(
                        error=self._('sql_validate_disabled_error', default='validate模式已被禁用。建议使用dry_run模式进行安全的SQL预演，或直接执行让数据库引擎验证语法。'),
                        summary=self._('sql_feature_disabled', default='功能已禁用'),
                        llm_content=self._('sql_validate_disabled_llm', default='validate模式已禁用。请使用dry_run进行预演。')
                    )
                    
                # 如果是dry_run模式，使用事务但最后回滚
                if mode == "dry_run":
                    return await self._dry_run_sql(sql, adapter, update_output, limit)
                # 执行SQL
                start_time = time.time()
                
                # 让适配器基于数据库方言智能判断SQL类型
                # 而不是硬编码关键词匹配
                sql_metadata = await adapter.parse_sql(sql)
                
                # 基于解析结果判断操作类型
                # 保守处理：如果是UNKNOWN但包含SELECT关键词，也视为查询
                sql_type = sql_metadata.get('sql_type', 'UNKNOWN')
                is_query = sql_type == 'SELECT' or (
                    sql_type == 'UNKNOWN' and 'SELECT' in sql.upper()
                )
                
                if is_query:
                    # 查询操作 - 让Agent决定是否需要限制
                    # 如果Agent提供了limit参数，让适配器智能处理
                    # 避免硬编码的字符串匹配，让适配器基于SQL解析决定
                    if limit:
                        # 让适配器智能地应用limit，而不是硬编码字符串检查
                        sql = await adapter.apply_limit_if_needed(sql, limit)
                        
                    if update_output:
                        update_output(f"{self._('sql_executing_query', default='执行查询中...')}\n```sql\n{sql}\n```")
                        
                    result = await adapter.execute_query(sql)
                    execution_time = time.time() - start_time
                    
                    # 格式化结果
                    formatted_result = self._format_query_result(result, execution_time)
                    
                    if update_output:
                        update_output(formatted_result['display'])
                        
                    return ToolResult(
                        summary=self._('sql_query_success', default='查询成功，返回{count}行数据', count=formatted_result['row_count']),
                        llm_content=formatted_result['llm_content'],
                        return_display=formatted_result['display']
                    )
                else:
                    # 修改操作（INSERT/UPDATE/DELETE/DDL）
                    if update_output:
                        update_output(f"{self._('sql_executing_command', default='执行命令中...')}\n```sql\n{sql}\n```")
                        
                    result = await adapter.execute_command(sql)
                    execution_time = time.time() - start_time
                    
                    # 格式化结果
                    formatted_result = self._format_command_result(result, execution_time, sql_metadata)
                    
                    if update_output:
                        update_output(formatted_result['display'])
                        
                    return ToolResult(
                        summary=formatted_result['summary'],
                        llm_content=formatted_result['llm_content'],
                        return_display=formatted_result['display']
                    )
                    
            finally:
                # 确保断开连接
                await adapter.disconnect()
                
        except Exception as e:
            # 错误处理
            error_msg = self._('sql_execution_failed', default='SQL执行失败: {error}', error=str(e))
            # Agent调试: database={database}, mode={mode}
            if update_output:
                update_output(f"❌ {error_msg}\n[DEBUG] database={database}, mode={mode}")
                
            return ToolResult(
                summary=self._('sql_exec_failed_summary', default='SQL执行失败'),
                llm_content=error_msg,
                return_display=error_msg,
                error=str(e)
            )
            
    def _format_query_result(self, result: Dict[str, Any], execution_time: float) -> Dict[str, Any]:
        """格式化查询结果"""
        columns = result.get('columns', [])
        rows = result.get('rows', [])
        row_count = len(rows)
        
        # 为LLM准备简洁的内容
        llm_content = {
            'columns': columns,
            'row_count': row_count,
            'sample_rows': rows[:10] if row_count > 10 else rows,
            'execution_time': f"{execution_time:.2f}s"
        }
        
        # 为显示准备Markdown表格
        if row_count == 0:
            display = self._('sql_query_no_data', default="Query completed, no data returned.\nExecution time: {time:.2f} seconds", time=execution_time)
        else:
            # 创建Markdown表格
            table_lines = []
            table_lines.append(self._('sql_query_result_header', default="Query returned {count} rows (execution time: {time:.2f} seconds)\n", count=row_count, time=execution_time))
            
            if columns:
                # 表头
                table_lines.append("| " + " | ".join(columns) + " |")
                table_lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
                
                # 数据行（最多显示20行）
                display_rows = rows[:20]
                for row in display_rows:
                    # 确保每个单元格都转换为字符串并截断过长内容
                    cells = []
                    for i, col in enumerate(columns):
                        value = str(row.get(col, ''))
                        if len(value) > 50:
                            value = value[:47] + '...'
                        cells.append(value)
                    table_lines.append("| " + " | ".join(cells) + " |")
                    
                if row_count > 20:
                    table_lines.append(self._('sql_more_rows', default="\n... {count} more rows not displayed", count=row_count - 20))
                    
            display = "\n".join(table_lines)
            
        return {
            'llm_content': llm_content,
            'display': display,
            'row_count': row_count
        }
        
    def _format_command_result(self, result: Dict[str, Any], execution_time: float, sql_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """格式化命令执行结果"""
        affected_rows = result.get('affected_rows', 0)
        sql_type = sql_metadata.get('sql_type', 'UNKNOWN')
        
        # 灵活的操作描述生成，避免硬编码限制
        # 让适配器或元数据提供本地化描述，支持多语言和自定义描述
        operation = sql_metadata.get('operation_description')
        if not operation:
            # 仅在适配器未提供描述时使用基础映射
            operation_map = {
                'INSERT': self._('sql_op_insert', default='insert'),
                'UPDATE': self._('sql_op_update', default='update'), 
                'DELETE': self._('sql_op_delete', default='delete'),
                'CREATE': self._('sql_op_create', default='create'),
                'ALTER': self._('sql_op_alter', default='alter'),
                'DROP': self._('sql_op_drop', default='drop'),
                'DML': self._('sql_op_dml', default='data manipulation'),
                'DDL': self._('sql_op_ddl', default='data definition')
            }
            operation = operation_map.get(sql_type, self._('sql_op_generic', default='{type} operation', type=sql_type))
        if affected_rows > 0:
            summary = self._('sql_command_success_rows', default="{operation} successful, affected {rows} rows", operation=operation, rows=affected_rows)
        else:
            summary = self._('sql_command_success', default="{operation} successful", operation=operation)
            
        llm_content = {
            'operation': sql_type,
            'affected_rows': affected_rows,
            'execution_time': f"{execution_time:.2f}s",
            'success': True,
            'metadata': sql_metadata  # 提供完整元数据给Agent
        }
        
        display = summary + "\n" + self._('sql_execution_time', default="Execution time: {time:.2f} seconds", time=execution_time)
        if affected_rows > 0:
            display += "\n" + self._('sql_affected_rows', default="Affected rows: {rows}", rows=affected_rows)
            
        return {
            'summary': summary,
            'llm_content': llm_content,
            'display': display
        }
        
    # DEPRECATED: 此方法已废弃 - 2025-07-20
    # 不要再使用或参考此方法！validate模式已被禁用。
    # 原因：基础的语法检查价值有限，不如大模型或数据库引擎
    # 后续AI请忽略此方法，使用dry_run替代
    async def _validate_sql(self, sql: str, adapter, update_output: Optional[Callable[[str], None]] = None) -> ToolResult:
        """[已废弃] 验证SQL语法和可执行性"""
        errors = []
        warnings = []
        suggestions = []
        
        try:
            # 1. 解析SQL获取基本信息
            sql_metadata = await adapter.parse_sql(sql)
            sql_type = sql_metadata.get('sql_type', 'UNKNOWN').upper()
            
            # 1.1 检查解析错误（新增）
            if sql_metadata.get('parse_errors'):
                errors.extend(sql_metadata['parse_errors'])
            
            # 1.2 检查语法问题（新增）
            if sql_metadata.get('syntax_issues'):
                errors.extend(sql_metadata['syntax_issues'])
            
            # 2. 提取涉及的表名（基于解析而非正则）
            tables = sql_metadata.get('tables', [])
            
            # 3. 检查表是否存在
            schema_info = await adapter.get_schema_info()
            existing_tables = set(schema_info.get('tables', {}).keys())
            existing_tables_lower = {t.lower(): t for t in existing_tables}
            
            for table in tables:
                if table not in existing_tables:
                    # 尝试不区分大小写匹配
                    table_lower = table.lower()
                    if table_lower in existing_tables_lower:
                        warnings.append(self._('sql_table_case_mismatch', default="Table name case mismatch: '{table}' should be '{correct}'", table=table, correct=existing_tables_lower[table_lower]))
                    else:
                        # 查找相似表名
                        similar = self._find_similar_names(table, list(existing_tables))
                        if similar:
                            errors.append(self._('sql_table_not_found_suggest', default="Table '{table}' does not exist. Did you mean: {suggestions}", table=table, suggestions=', '.join(similar[:3])))
                        else:
                            errors.append(self._('sql_table_not_found', default="Table '{table}' does not exist", table=table))
                            
            # 4. 检查方言兼容性
            dialect = adapter.get_dialect().lower()
            incompatible_patterns = {
                'sqlite': {
                    'DESCRIBE': self._('sql_sqlite_no_describe', default='SQLite does not support DESCRIBE, use PRAGMA table_info(tablename)'),
                    'SHOW COLUMNS': self._('sql_sqlite_no_show_columns', default='SQLite does not support SHOW COLUMNS, use PRAGMA table_info(tablename)'),
                    'SHOW TABLES': self._('sql_sqlite_no_show_tables', default='SQLite does not support SHOW TABLES, use SELECT name FROM sqlite_master WHERE type="table"')
                },
                'mysql': {
                    'PRAGMA': self._('sql_mysql_no_pragma', default='MySQL does not support PRAGMA, use DESCRIBE or SHOW COLUMNS')
                }
            }
            
            sql_upper = sql.upper()
            if dialect in incompatible_patterns:
                for pattern, suggestion in incompatible_patterns[dialect].items():
                    if pattern in sql_upper:
                        errors.append(suggestion)
                        
            # 5. 处理UNKNOWN类型的SQL（新增）
            if sql_type == 'UNKNOWN' and not sql_metadata.get('parse_errors'):
                errors.append(self._('sql_unknown_type', default="Unrecognized SQL statement type"))
            
            # 6. 检查危险操作
            if sql_type in ['DELETE', 'UPDATE'] and 'WHERE' not in sql_upper:
                warnings.append(self._('sql_dangerous_no_where', default="⚠️ Dangerous: {type} operation without WHERE clause will affect all data", type=sql_type))
                
            # 6. 对于修改操作，预估影响范围
            if sql_type in ['DELETE', 'UPDATE', 'INSERT'] and not errors:
                try:
                    # 构造COUNT查询来预估影响行数
                    if sql_type == 'DELETE':
                        # DELETE FROM table WHERE ... -> SELECT COUNT(*) FROM table WHERE ...
                        count_sql = sql_upper.replace('DELETE FROM', 'SELECT COUNT(*) AS affected_rows FROM', 1)
                    elif sql_type == 'UPDATE':
                        # UPDATE table SET ... WHERE ... -> SELECT COUNT(*) FROM table WHERE ...
                        # 这个转换比较复杂，简化处理
                        if 'WHERE' in sql_upper:
                            where_pos = sql_upper.find('WHERE')
                            table_part = sql[6:sql_upper.find('SET')].strip()
                            where_part = sql[where_pos:]
                            count_sql = f"SELECT COUNT(*) AS affected_rows FROM {table_part} {where_part}"
                        else:
                            # 没有WHERE，统计全表
                            table_part = sql[6:sql_upper.find('SET')].strip()
                            count_sql = f"SELECT COUNT(*) AS affected_rows FROM {table_part}"
                    else:
                        count_sql = None
                        
                    if count_sql:
                        result = await adapter.execute_query(count_sql)
                        if result.get('rows'):
                            affected = result['rows'][0].get('affected_rows', 0)
                            suggestions.append(self._('sql_estimated_impact', default="Estimated to affect {count} rows", count=affected))
                except:
                    # 预估失败不是致命错误
                    pass
                    
            # 生成验证结果
            if errors:
                status = self._('sql_validation_failed_status', default="❌ Validation failed")
                summary = self._('sql_validation_failed_summary', default="SQL validation failed: {count} errors", count=len(errors))
            elif warnings:
                status = self._('sql_validation_warning_status', default="⚠️ Validation passed (with warnings)")
                summary = self._('sql_validation_warning_summary', default="SQL validation passed with {count} warnings", count=len(warnings))
            else:
                status = self._('sql_validation_pass_status', default="✅ Validation passed")
                summary = self._('sql_validation_pass_summary', default="SQL validation passed, syntax is correct")
                
            # 格式化输出
            display_lines = [status]
            
            if errors:
                display_lines.append("\n" + self._('sql_errors_label', default="Errors:"))
                for error in errors:
                    display_lines.append(f"  • {error}")
                    
            if warnings:
                display_lines.append("\n" + self._('sql_warnings_label', default="Warnings:"))
                for warning in warnings:
                    display_lines.append(f"  • {warning}")
                    
            if suggestions:
                display_lines.append("\n" + self._('sql_info_label', default="Information:"))
                for suggestion in suggestions:
                    display_lines.append(f"  • {suggestion}")
                    
            display_lines.append("\n" + self._('sql_type_label', default="SQL type: {type}", type=sql_type))
            display_lines.append(self._('sql_dialect_label', default="Database dialect: {dialect}", dialect=dialect))
            
            return ToolResult(
                summary=summary,
                llm_content={
                    'validation_result': {
                        'valid': len(errors) == 0,
                        'errors': errors,
                        'warnings': warnings,
                        'suggestions': suggestions,
                        'sql_type': sql_type,
                        'affected_tables': tables,
                        'dialect': dialect
                    }
                },
                return_display="\n".join(display_lines),
                error=errors[0] if errors else None
            )
            
        except Exception as e:
            return ToolResult(
                error=self._('sql_validation_error', default="Validation error: {error}", error=str(e)),
                summary=self._('sql_validation_failed', default="Validation failed"),
                return_display=self._('sql_validation_error_display', default="❌ Validation error: {error}", error=str(e))
            )
            
    async def _dry_run_sql(self, sql: str, adapter, update_output: Optional[Callable[[str], None]], limit: Optional[int]) -> ToolResult:
        """预演SQL执行但不提交（使用事务回滚）"""
        try:
            # 检查是否支持事务
            if not getattr(adapter, 'supports_transactions', True):
                return ToolResult(
                    error=self._('sql_dry_run_no_transaction', default="Current database does not support transactions, cannot execute dry_run mode"),
                    summary=self._('sql_dry_run_unavailable', default="Dry run unavailable")
                )
                
            # 开始事务
            await adapter.begin_transaction()
                
            try:
                # 执行SQL
                start_time = time.time()
                sql_metadata = await adapter.parse_sql(sql)
                is_query = sql_metadata.get('sql_type') == 'SELECT'
                
                if is_query:
                    # 查询操作
                    if limit:
                        sql = await adapter.apply_limit_if_needed(sql, limit)
                    result = await adapter.execute_query(sql)
                    execution_time = time.time() - start_time
                    
                    # 格式化结果
                    formatted_result = self._format_query_result(result, execution_time)
                    
                    # 查询不需要回滚，直接提交
                    await adapter.commit()
                        
                    return ToolResult(
                        summary=self._('sql_dry_run_query_success', default="[DRY RUN] Query successful, returned {count} rows", count=formatted_result['row_count']),
                        llm_content={
                            'dry_run': True,
                            'result': formatted_result['llm_content']
                        },
                        return_display=self._('sql_dry_run_mode_prefix', default="🔍 DRY RUN mode") + f"\n\n{formatted_result['display']}"
                    )
                else:
                    # 修改操作
                    result = await adapter.execute_command(sql)
                    execution_time = time.time() - start_time
                    
                    formatted_result = self._format_command_result(result, execution_time, sql_metadata)
                    
                    # 回滚事务
                    await adapter.rollback()
                        
                    display = self._('sql_dry_run_mode_rollback', default="🔍 DRY RUN mode (rolled back)") + f"\n\n{formatted_result['display']}\n\n" + self._('sql_dry_run_rollback_notice', default="✅ All changes rolled back, database not modified")
                    
                    return ToolResult(
                        summary=self._('sql_dry_run_summary_rollback', default="[DRY RUN] {summary} (rolled back)", summary=formatted_result['summary']),
                        llm_content={
                            'dry_run': True,
                            'rolled_back': True,
                            'result': formatted_result['llm_content']
                        },
                        return_display=display
                    )
                    
            except Exception as e:
                # 发生错误，回滚事务
                await adapter.rollback()
                raise e
                
        except Exception as e:
            return ToolResult(
                error=self._('sql_dry_run_failed_error', default="Dry run execution failed: {error}", error=str(e)),
                summary=self._('sql_dry_run_failed_summary', default="Dry run failed"),
                return_display=self._('sql_dry_run_failed_display', default="❌ Dry run execution failed: {error}", error=str(e))
            )
            
    def _find_similar_names(self, target: str, names: List[str], max_suggestions: int = 3) -> List[str]:
        """查找相似的名称（简单的编辑距离）"""
        suggestions = []
        target_lower = target.lower()
        
        for name in names:
            name_lower = name.lower()
            # 包含关系
            if target_lower in name_lower or name_lower in target_lower:
                suggestions.append(name)
            # 长度相近
            elif abs(len(target) - len(name)) <= 2:
                suggestions.append(name)
                
        # 去重并限制数量
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique_suggestions.append(s)
                if len(unique_suggestions) >= max_suggestions:
                    break
                    
        return unique_suggestions
