"""
DatabaseExportTool - 智能数据导出工具
直接将SQL查询结果导出到文件，支持多种格式，解决Agent手动拼接数据的痛点
"""

import os
import csv
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from datetime import datetime
from ..types.tool_types import ToolResult
from ..types.core_types import AbortSignal
from .base import DatabaseTool
from ..config.base import DatabaseConfig


class DatabaseExportTool(DatabaseTool):
    """
    智能数据导出工具
    解决Agent需要手动拼接CSV/JSON的痛点
    支持直接从SQL查询导出到各种格式文件
    """
    
    # 默认批量大小
    DEFAULT_BATCH_SIZE = 1000
    MAX_BATCH_SIZE = 10000
    
    def _apply_pagination(self, sql: str, batch_size: int, offset: int) -> str:
        """智能应用分页，避免重复LIMIT"""
        sql_upper = sql.upper().strip()
        # 检查是否已经有LIMIT
        if 'LIMIT' in sql_upper:
            # 如果已经有LIMIT，不再添加
            # Agent可以看到: SQL已包含LIMIT，跳过分页
            return sql
        else:
            # 没有LIMIT，添加分页
            return f"{sql} LIMIT {batch_size} OFFSET {offset}"
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        
        super().__init__(
            name="export_data",
            display_name=self._('export_tool_name', default="Data Export") if i18n else "数据导出",
            description="Export SQL query results directly to files with streaming support for large datasets. Formats: CSV, JSON, Excel, SQL. Features: batch processing, custom delimiters, null handling, append mode.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQL query to export results from"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output file path (extension determines format: .csv, .json, .xlsx)"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["csv", "json", "excel", "sql"],
                        "description": "Export format (auto-detected from file extension if not specified)"
                    },
                    "database": {
                        "type": "string",
                        "description": "Database connection name (optional)"
                    },
                    "options": {
                        "type": "object",
                        "description": "Format-specific options",
                        "properties": {
                            "include_headers": {
                                "type": "boolean",
                                "description": "Include column headers (CSV/Excel)",
                                "default": True
                            },
                            "delimiter": {
                                "type": "string",
                                "description": "CSV delimiter",
                                "default": ","
                            },
                            "null_handling": {
                                "type": "string",
                                "enum": ["empty", "null", "NA", "NULL"],
                                "description": "How to represent NULL values",
                                "default": "empty"
                            },
                            "date_format": {
                                "type": "string",
                                "description": "Date format string",
                                "default": "%Y-%m-%d %H:%M:%S"
                            },
                            "batch_size": {
                                "type": "integer",
                                "description": "Batch size for streaming large datasets",
                                "minimum": 100,
                                "maximum": 10000,
                                "default": 1000
                            },
                            "encoding": {
                                "type": "string",
                                "description": "File encoding (auto for system default). Common: utf-8, cp932 (Japanese), gbk (Chinese)",
                                "default": "auto"
                            },
                            "json_indent": {
                                "type": "integer",
                                "description": "JSON indentation (0 for compact)",
                                "default": 2
                            },
                            "append": {
                                "type": "boolean",
                                "description": "Append to existing file instead of overwriting",
                                "default": False
                            }
                        }
                    }
                },
                "required": ["sql", "output_path"]
            },
            is_output_markdown=True,
            can_update_output=True,
            should_summarize_display=False,
            i18n=i18n  # 传递i18n给基类
        )
        self.config = config
        # 动态检测系统并设置灵活的导出路径权限
        default_paths = self._get_system_paths(config)
        self.allowed_export_paths = config.get("export_allowed_paths", default_paths)
        
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        sql = params.get("sql", "").strip()
        if not sql:
            return self._('export_sql_empty', default="SQL query cannot be empty")
            
        output_path = params.get("output_path", "").strip()
        if not output_path:
            return self._('export_path_empty', default="Output path cannot be empty")
            
        # 检查输出路径是否在允许范围内
        try:
            resolved_path = self._resolve_output_path(output_path)
            if not self._is_path_allowed(resolved_path):
                return self._('export_path_not_allowed', default="Export not allowed to: {path}", path=output_path)
        except Exception as e:
            return self._('export_path_invalid', default="Invalid output path: {error}", error=str(e))
            
        # 验证格式
        format_type = params.get("format")
        if not format_type:
            # 从文件扩展名推断
            ext = resolved_path.suffix.lower()[1:]  # 去掉点号
            if ext not in ["csv", "json", "xlsx", "xls", "sql"]:
                return self._('export_format_unsupported', default="Unsupported file format: {format}", format=ext)
                
        return None
        
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        output_path = params.get("output_path", "")
        format_type = params.get("format")
        
        if not format_type:
            # 从文件扩展名推断
            ext = Path(output_path).suffix.lower()[1:]
            format_type = ext
            
        return self._('export_description', default="Export query result to {format} file: {filename}", format=format_type.upper(), filename=Path(output_path).name)
        
    async def should_confirm_execute(self, params: Dict[str, Any], signal: AbortSignal) -> Union[bool, Any]:
        """检查是否需要确认"""
        output_path = params.get("output_path", "")
        options = params.get("options", {})
        append = options.get("append", False)
        
        # 如果文件存在且不是追加模式，需要确认
        try:
            resolved_path = self._resolve_output_path(output_path)
            if resolved_path.exists() and not append:
                return {
                    "title": self._('export_confirm_overwrite_title', default="Confirm file overwrite"),
                    "message": self._('export_confirm_overwrite_message', default="File {filename} already exists, overwrite?", filename=resolved_path.name),
                    "details": self._('export_confirm_overwrite_details', default="Full path: {path}", path=resolved_path)
                }
        except:
            pass
            
        return False
        
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """执行数据导出"""
        sql = params.get("sql", "").strip()
        output_path = params.get("output_path", "").strip()
        format_type = params.get("format")
        database = params.get("database")
        options = params.get("options", {})
        
        try:
            # 解析输出路径
            resolved_path = self._resolve_output_path(output_path)
            
            # 确保输出目录存在
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 推断格式
            if not format_type:
                ext = resolved_path.suffix.lower()[1:]
                format_map = {
                    "csv": "csv",
                    "json": "json",
                    "xlsx": "excel",
                    "xls": "excel",
                    "sql": "sql"
                }
                format_type = format_map.get(ext, "csv")
                
            if update_output:
                update_output(self._('export_progress', default="Exporting data to {format} format...\nFile: {filename}", format=format_type.upper(), filename=resolved_path.name))
                
            # 获取数据库适配器
            from ..adapters.adapter_factory import get_adapter
            adapter = await get_adapter(self.config, database)
            
            # 连接数据库
            await adapter.connect()
            
            try:
                # 执行导出
                if format_type == "csv":
                    result = await self._export_csv(sql, resolved_path, adapter, options, update_output)
                elif format_type == "json":
                    result = await self._export_json(sql, resolved_path, adapter, options, update_output)
                elif format_type == "excel":
                    result = await self._export_excel(sql, resolved_path, adapter, options, update_output)
                elif format_type == "sql":
                    result = await self._export_sql(sql, resolved_path, adapter, options, update_output)
                else:
                    return ToolResult(error=f"Unsupported format: {format_type}")
                    
                return result
                
            finally:
                # 确保断开连接
                await adapter.disconnect()
                
        except Exception as e:
            return ToolResult(
                error=self._('export_failed_error', default="Export failed: {error}", error=str(e)),
                summary=self._('export_failed_summary', default="Export failed"),
                return_display=self._('export_failed_display', default="❌ Export failed: {error}", error=str(e))
            )
            
    async def _export_csv(
        self, 
        sql: str, 
        output_path: Path, 
        adapter, 
        options: Dict[str, Any],
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """导出为CSV格式"""
        include_headers = options.get("include_headers", True)
        delimiter = options.get("delimiter", ",")
        null_handling = options.get("null_handling", "empty")
        encoding = self._get_encoding(options)
        batch_size = min(options.get("batch_size", self.DEFAULT_BATCH_SIZE), self.MAX_BATCH_SIZE)
        append = options.get("append", False)
        
        null_value = {
            "empty": "",
            "null": "null",
            "NA": "NA",
            "NULL": "NULL"
        }.get(null_handling, "")
        
        mode = 'a' if append else 'w'
        total_rows = 0
        
        try:
            with open(output_path, mode, newline='', encoding=encoding) as csvfile:
                writer = None
                
                # 流式处理大数据集
                offset = 0
                while True:
                    # 构造分页查询（智能处理已有的LIMIT）
                    paginated_sql = self._apply_pagination(sql, batch_size, offset)
                    result = await adapter.execute_query(paginated_sql)
                    
                    rows = result.get('rows', [])
                    columns = result.get('columns', [])
                    
                    if not rows:
                        break
                        
                    # 第一批数据时初始化writer
                    if writer is None:
                        writer = csv.DictWriter(
                            csvfile, 
                            fieldnames=columns,
                            delimiter=delimiter
                        )
                        # 写入表头（如果需要且不是追加模式）
                        if include_headers and not (append and output_path.stat().st_size > 0):
                            writer.writeheader()
                            
                    # 写入数据
                    for row in rows:
                        # 处理NULL值
                        processed_row = {}
                        for key, value in row.items():
                            if value is None:
                                processed_row[key] = null_value
                            else:
                                processed_row[key] = str(value)
                        writer.writerow(processed_row)
                        
                    total_rows += len(rows)
                    offset += batch_size
                    
                    if update_output and total_rows % (batch_size * 10) == 0:
                        update_output(self._('export_rows_progress', default="Exported {count:,} rows...", count=total_rows))
                        
                    # 如果返回的行数少于批量大小，说明已经到最后了
                    if len(rows) < batch_size:
                        break
                        
            # 获取文件大小
            file_size = output_path.stat().st_size
            
            return ToolResult(
                summary=self._('export_csv_success', default="Successfully exported {count:,} rows to CSV file", count=total_rows),
                llm_content={
                    'export_result': {
                        'format': 'csv',
                        'rows_exported': total_rows,
                        'file_path': str(output_path),
                        'file_size': file_size,
                        'options': options
                    }
                },
                return_display=self._('export_csv_success_display', default="✅ Export successful\n📄 File: {filename}\n📊 Format: CSV\n📏 Rows: {rows:,}\n💾 Size: {size}", filename=output_path.name, rows=total_rows, size=self._format_size(file_size))
            )
            
        except Exception as e:
            # Agent调试: 原SQL={sql[:50]}...
            return ToolResult(
                error=self._('export_csv_failed', default="CSV export failed: {error}", error=str(e)),
                summary=self._('export_csv_failed_summary', default="CSV export failed"),
                llm_content={"debug": {"original_sql": sql[:100], "error": str(e)}}
            )
            
    async def _export_json(
        self,
        sql: str,
        output_path: Path,
        adapter,
        options: Dict[str, Any],
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """导出为JSON格式"""
        indent = options.get("json_indent", 2)
        encoding = self._get_encoding(options)
        batch_size = min(options.get("batch_size", self.DEFAULT_BATCH_SIZE), self.MAX_BATCH_SIZE)
        append = options.get("append", False)
        date_format = options.get("date_format", "%Y-%m-%d %H:%M:%S")
        
        total_rows = 0
        all_data = [] if not append else None
        
        try:
            # 如果是追加模式，先读取现有数据
            if append and output_path.exists():
                with open(output_path, 'r', encoding=encoding) as f:
                    try:
                        all_data = json.load(f)
                        if not isinstance(all_data, list):
                            all_data = [all_data]
                    except:
                        all_data = []
            elif not append:
                all_data = []
                
            # 流式处理数据
            offset = 0
            while True:
                paginated_sql = self._apply_pagination(sql, batch_size, offset)
                result = await adapter.execute_query(paginated_sql)
                
                rows = result.get('rows', [])
                if not rows:
                    break
                    
                # 处理日期时间对象
                for row in rows:
                    for key, value in row.items():
                        if isinstance(value, datetime):
                            row[key] = value.strftime(date_format)
                            
                if all_data is not None:
                    all_data.extend(rows)
                else:
                    # 对于大数据集，使用流式JSON（每行一个JSON对象）
                    mode = 'a' if append else 'w'
                    with open(output_path, mode, encoding=encoding) as f:
                        for row in rows:
                            json.dump(row, f, ensure_ascii=False)
                            f.write('\n')
                            
                total_rows += len(rows)
                offset += batch_size
                
                if update_output and total_rows % (batch_size * 10) == 0:
                    update_output(self._('export_rows_progress', default="已导出 {count:,} 行...", count=total_rows))
                    
                if len(rows) < batch_size:
                    break
                    
            # 写入完整的JSON数组（如果不是流式）
            if all_data is not None:
                with open(output_path, 'w', encoding=encoding) as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=indent)
                    
            file_size = output_path.stat().st_size
            
            return ToolResult(
                summary=self._('export_json_success', default="Successfully exported {count:,} rows to JSON file", count=total_rows),
                llm_content={
                    'export_result': {
                        'format': 'json',
                        'rows_exported': total_rows,
                        'file_path': str(output_path),
                        'file_size': file_size,
                        'streaming': all_data is None
                    }
                },
                return_display=self._('export_json_success_display', default="✅ Export successful\n📄 File: {filename}\n📊 Format: JSON\n📏 Rows: {rows:,}\n💾 Size: {size}", filename=output_path.name, rows=total_rows, size=self._format_size(file_size))
            )
            
        except Exception as e:
            return ToolResult(
                error=self._('export_json_failed', default="JSON export failed: {error}", error=str(e)),
                summary=self._('export_json_failed_summary', default="JSON export failed")
            )
            
    async def _export_excel(
        self,
        sql: str,
        output_path: Path,
        adapter,
        options: Dict[str, Any],
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """导出为Excel格式"""
        try:
            # 尝试导入openpyxl
            try:
                import openpyxl
                from openpyxl import Workbook
            except ImportError:
                return ToolResult(
                    error=self._('export_excel_missing_lib', default="Excel export requires 'openpyxl' package. Please install it: pip install openpyxl"),
                    summary=self._('export_excel_missing_lib_summary', default="Missing Excel support library")
                )
                
            include_headers = options.get("include_headers", True)
            batch_size = min(options.get("batch_size", self.DEFAULT_BATCH_SIZE), self.MAX_BATCH_SIZE)
            
            # 创建工作簿
            wb = Workbook()
            ws = wb.active
            ws.title = "Query Results"
            
            total_rows = 0
            offset = 0
            headers_written = False
            
            # 流式处理数据
            while True:
                paginated_sql = self._apply_pagination(sql, batch_size, offset)
                result = await adapter.execute_query(paginated_sql)
                
                rows = result.get('rows', [])
                columns = result.get('columns', [])
                
                if not rows:
                    break
                    
                # 写入表头
                if include_headers and not headers_written:
                    ws.append(columns)
                    headers_written = True
                    
                # 写入数据
                for row in rows:
                    row_data = [row.get(col) for col in columns]
                    ws.append(row_data)
                    
                total_rows += len(rows)
                offset += batch_size
                
                if update_output and total_rows % (batch_size * 10) == 0:
                    update_output(self._('export_rows_progress', default="已导出 {count:,} 行...", count=total_rows))
                    
                if len(rows) < batch_size:
                    break
                    
            # 保存文件
            wb.save(output_path)
            file_size = output_path.stat().st_size
            
            return ToolResult(
                summary=self._('export_excel_success', default="Successfully exported {count:,} rows to Excel file", count=total_rows),
                llm_content={
                    'export_result': {
                        'format': 'excel',
                        'rows_exported': total_rows,
                        'file_path': str(output_path),
                        'file_size': file_size
                    }
                },
                return_display=self._('export_excel_success_display', default="✅ Export successful\n📄 File: {filename}\n📊 Format: Excel\n📏 Rows: {rows:,}\n💾 Size: {size}", filename=output_path.name, rows=total_rows, size=self._format_size(file_size))
            )
            
        except Exception as e:
            return ToolResult(
                error=self._('export_excel_failed', default="Excel export failed: {error}", error=str(e)),
                summary=self._('export_excel_failed_summary', default="Excel export failed")
            )
            
    async def _export_sql(
        self,
        sql: str,
        output_path: Path,
        adapter,
        options: Dict[str, Any],
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """导出为SQL INSERT语句"""
        encoding = self._get_encoding(options)
        batch_size = min(options.get("batch_size", self.DEFAULT_BATCH_SIZE), self.MAX_BATCH_SIZE)
        
        # 尝试从SQL中提取表名（简单实现）
        sql_upper = sql.upper()
        table_name = "exported_data"  # Default table name
        if "FROM" in sql_upper:
            from_pos = sql_upper.find("FROM")
            # 简单提取FROM后的第一个词作为表名
            after_from = sql[from_pos + 4:].strip()
            table_name = after_from.split()[0].strip('`"[]')
            
        total_rows = 0
        
        try:
            with open(output_path, 'w', encoding=encoding) as f:
                # 写入头部注释
                f.write(self._('export_sql_header_1', default="-- Exported from DbRheo on {date}\n", date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                f.write(self._('export_sql_header_2', default="-- Original query: {sql}\n\n", sql=sql))
                
                offset = 0
                while True:
                    paginated_sql = self._apply_pagination(sql, batch_size, offset)
                    result = await adapter.execute_query(paginated_sql)
                    
                    rows = result.get('rows', [])
                    columns = result.get('columns', [])
                    
                    if not rows:
                        break
                        
                    # 生成INSERT语句
                    for row in rows:
                        values = []
                        for col in columns:
                            value = row.get(col)
                            if value is None:
                                values.append("NULL")
                            elif isinstance(value, (int, float)):
                                values.append(str(value))
                            else:
                                # 转义单引号
                                escaped = str(value).replace("'", "''")
                                values.append(f"'{escaped}'")
                                
                        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(values)});\n"
                        f.write(insert_sql)
                        
                    total_rows += len(rows)
                    offset += batch_size
                    
                    if update_output and total_rows % (batch_size * 10) == 0:
                        update_output(self._('export_rows_progress', default="Exported {count:,} rows...", count=total_rows))
                        
                    if len(rows) < batch_size:
                        break
                        
            file_size = output_path.stat().st_size
            
            return ToolResult(
                summary=self._('export_sql_success', default="Successfully exported {count:,} rows to SQL file", count=total_rows),
                llm_content={
                    'export_result': {
                        'format': 'sql',
                        'rows_exported': total_rows,
                        'file_path': str(output_path),
                        'file_size': file_size,
                        'table_name': table_name
                    }
                },
                return_display=self._('export_sql_success_display', default="✅ Export successful\n📄 File: {filename}\n📊 Format: SQL INSERT\n📏 Rows: {rows:,}\n💾 Size: {size}", filename=output_path.name, rows=total_rows, size=self._format_size(file_size))
            )
            
        except Exception as e:
            return ToolResult(
                error=self._('export_sql_failed', default="SQL export failed: {error}", error=str(e)),
                summary=self._('export_sql_failed_summary', default="SQL export failed")
            )
    
    def _get_system_paths(self, config) -> list:
        """动态检测系统并返回合适的访问路径 - 真正的灵活性"""
        paths = []
        
        # 智能检测项目根目录（往上找到包含packages的目录）
        working_dir = Path(config.get_working_dir())
        current_dir = working_dir
        
        # 向上查找到项目根目录
        while current_dir.parent != current_dir:  # 没到根目录
            if (current_dir / 'packages').exists() or (current_dir / 'pyproject.toml').exists():
                paths.append(str(current_dir))
                break
            current_dir = current_dir.parent
        
        # 如果没找到项目根目录，至少包含工作目录
        paths.append(config.get_working_dir())
        
        # 用户主目录 - 跨平台通用
        home_dir = os.path.expanduser("~")
        if home_dir and os.path.exists(home_dir):
            paths.append(home_dir)
        
        # 根据系统平台动态添加根路径
        import platform
        system = platform.system().lower()
        
        if system == "windows":
            # Windows: 动态检测所有可用驱动器
            import string
            for drive in string.ascii_uppercase:
                drive_path = f"{drive}:\\"
                if os.path.exists(drive_path):
                    paths.append(drive_path)
        
        elif system == "darwin":  # macOS
            paths.extend([
                "/",              # 根目录
                "/Users",         # 用户目录
                "/Applications",  # 应用程序
                "/Volumes",       # 挂载点
            ])
        
        elif system == "linux":
            paths.extend([
                "/",              # 根目录
                "/home",          # 用户目录
                "/mnt",           # 挂载点 (WSL等)
                "/media",         # 媒体挂载
                "/opt",           # 可选软件
                "/tmp",           # 临时目录
            ])
        
        else:
            # 未知系统，使用通用路径
            if os.path.exists("/"):
                paths.append("/")
            # 尝试检测常见挂载点
            for mount_point in ["/mnt", "/media", "/Volumes"]:
                if os.path.exists(mount_point):
                    paths.append(mount_point)
        
        # 过滤掉不存在的路径，保留真实可访问的
        return [p for p in paths if os.path.exists(p)]
            
    def _resolve_output_path(self, path: str) -> Path:
        """解析输出路径"""
        p = Path(path)
        
        # 如果是相对路径，基于工作目录
        if not p.is_absolute():
            working_dir = Path(self.config.get_working_dir())
            p = working_dir / p
            
        return p.resolve()
        
    def _is_path_allowed(self, path: Path) -> bool:
        """检查路径是否在允许的导出目录内"""
        for allowed_path in self.allowed_export_paths:
            allowed = Path(allowed_path).resolve()
            try:
                path.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False
        
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def _get_encoding(self, options: Dict[str, Any]) -> str:
        """获取编码设置 - 支持自动检测"""
        encoding_param = options.get("encoding", "auto")
        
        if encoding_param == "auto":
            try:
                from ..utils.encoding_utils import get_system_encoding
                return get_system_encoding()
            except:
                return "utf-8"
        else:
            return encoding_param