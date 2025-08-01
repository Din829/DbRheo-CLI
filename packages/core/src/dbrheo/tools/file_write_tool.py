"""
文件写入工具 - 支持数据库查询结果导出、报告生成等
借鉴Gemini CLI的确认机制和安全设计
"""

import os
import json
import csv
import yaml
import asyncio
import aiofiles
import difflib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass

from ..types.tool_types import ToolResult
from ..types.core_types import AbortSignal
from ..types.file_types import (
    FileFormat, ApprovalMode, FileWriteConfirmationDetails,
    FileOperationResult, StreamingConfig
)
from .base import DatabaseTool
from ..config.base import DatabaseConfig


class FileWriteTool(DatabaseTool):
    """
    增强的文件写入工具，支持：
    - 多种文件格式（CSV、JSON、Excel、SQL等）
    - 流式写入大数据
    - 智能确认机制（借鉴Gemini CLI）
    - 数据库查询结果导出
    - 进度反馈和错误恢复
    """
    
    # 支持的文件格式和扩展名映射
    FORMAT_EXTENSIONS = {
        FileFormat.CSV: ['.csv', '.tsv'],
        FileFormat.JSON: ['.json', '.jsonl'],
        FileFormat.EXCEL: ['.xlsx', '.xls'],
        FileFormat.SQL: ['.sql'],
        FileFormat.MARKDOWN: ['.md', '.markdown'],
        FileFormat.TEXT: ['.txt', '.log'],
        FileFormat.PARQUET: ['.parquet'],
        FileFormat.YAML: ['.yaml', '.yml'],
        FileFormat.XML: ['.xml']
    }
    
    # 最大文件大小限制（100MB）
    MAX_FILE_SIZE = 100 * 1024 * 1024
    
    def __init__(self, config: DatabaseConfig, i18n=None):
        # 先保存i18n实例，以便在初始化时使用
        self._i18n = i18n
        
        super().__init__(
            name="write_file",
            display_name=self._('file_write_tool_name', default="文件写入") if i18n else "文件写入",
            description="Writes files with intelligent format detection and automatic error recovery. Creates directories when needed, handles format conversions, and ensures reliable file operations with comprehensive progress feedback.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute file path to write. Must be within allowed directories."
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write. For structured data, provide JSON string."
                    },
                    "format": {
                        "type": "string",
                        "enum": [f.value for f in FileFormat],
                        "description": "Output format. Auto-detected from extension if not specified."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["overwrite", "append", "create_new"],
                        "description": "Write mode. 'create_new' fails if file exists.",
                        "default": "overwrite"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (auto for system default). Common: utf-8, cp932 (Japanese), gbk (Chinese)",
                        "default": "auto"
                    },
                    "compression": {
                        "type": "string",
                        "enum": ["none", "gzip", "bz2", "xz"],
                        "description": "Compression type",
                        "default": "none"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata like source SQL, tables, etc.",
                        "properties": {
                            "source_sql": {"type": "string"},
                            "source_tables": {"type": "array", "items": {"type": "string"}},
                            "row_count": {"type": "integer"},
                            "created_by": {"type": "string"}
                        }
                    }
                },
                "required": ["path", "content"]
            },
            is_output_markdown=True,
            can_update_output=True,
            should_summarize_display=True,
            i18n=i18n  # 传递i18n给基类
        )
        
        self.config = config
        
        # 审批模式，默认手动
        self.approval_mode = ApprovalMode(config.get("file_approval_mode", "manual"))
        
        # 动态检测系统并设置灵活的访问权限
        default_paths = self._get_system_paths(config)
        self.allowed_paths = config.get("file_allowed_paths", default_paths)
        
        # 流式处理配置
        self.streaming_config = StreamingConfig(
            chunk_size=config.get("file_streaming_chunk_size", 10000),
            memory_limit_mb=config.get("file_memory_limit_mb", 100),
            enable_compression=config.get("file_enable_compression", True)
        )
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        path = params.get("path", "")
        if not path:
            return self._('file_write_path_empty', default="File path cannot be empty")
        
        # 必须是绝对路径
        if not os.path.isabs(path):
            return self._('file_write_path_not_absolute', default="Path must be absolute")
        
        # 内容不能为空（除非是创建空文件）
        content = params.get("content")
        if content is None:
            return self._('file_write_content_none', default="Content cannot be None")
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        path = Path(params.get("path", ""))
        mode = params.get("mode", "overwrite")
        # 处理格式参数
        format_param = params.get("format")
        if format_param and isinstance(format_param, str):
            format_str = format_param.upper()
        else:
            format = format_param if format_param else self._detect_format(path)
            format_str = format.value.upper() if isinstance(format, FileFormat) else str(format).upper()
        
        action = {
            "overwrite": self._('file_write_action_overwrite', default="写入"),
            "append": self._('file_write_action_append', default="追加到"),
            "create_new": self._('file_write_action_create', default="创建")
        }.get(mode, self._('file_write_action_overwrite', default="写入"))
        
        return self._('file_write_description', default="{action}{format}文件: {filename}", action=action, format=format_str, filename=path.name)
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> Union[bool, FileWriteConfirmationDetails]:
        """智能确认机制 - 借鉴Gemini CLI设计"""
        
        # 自动模式检查
        if self.approval_mode in [ApprovalMode.AUTO_WRITE, ApprovalMode.AUTO_ALL]:
            return False
        
        path = Path(params["path"]).resolve()
        content = params["content"]
        mode = params.get("mode", "overwrite")
        # 处理格式参数
        format_param = params.get("format")
        if format_param and isinstance(format_param, str):
            try:
                format = FileFormat(format_param.lower())
            except ValueError:
                format = self._detect_format(path)
        else:
            format = format_param if format_param else self._detect_format(path)
        
        # 检查路径安全性
        if not self._is_path_allowed(path):
            # 始终需要确认危险路径
            return self._create_confirmation_details(
                path, content, mode, format,
                title=self._('file_write_dangerous_path', default="⚠️ 危险路径: {path}", path=path),
                risk_level="high"
            )
        
        # 如果文件存在，生成diff
        file_diff = None
        if path.exists() and mode == "overwrite":
            try:
                existing_content = path.read_text(encoding=params.get("encoding", "utf-8"))
                file_diff = self._generate_diff(existing_content, content, path.name)
            except:
                file_diff = self._('file_write_cannot_read_existing', default="[无法读取现有文件内容]")
        
        # 获取元数据
        metadata = params.get("metadata", {})
        
        return FileWriteConfirmationDetails(
            title=self._get_confirmation_title(path, mode, format),
            file_path=str(path),
            file_diff=file_diff,
            content_preview=self._preview_content(content, format),
            estimated_size=self._format_size(len(content.encode('utf-8'))),
            format=format,
            data_source_sql=metadata.get("source_sql"),
            affected_tables=metadata.get("source_tables"),
            row_count=metadata.get("row_count"),
            allow_overwrite=(mode == "overwrite"),
            append_mode=(mode == "append")
        )
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """执行文件写入"""
        start_time = datetime.now()
        path = Path(params["path"]).resolve()
        content = params["content"]
        mode = params.get("mode", "overwrite")
        # 处理格式参数：可能是字符串（用户输入）或 FileFormat 枚举（自动检测）
        format_param = params.get("format")
        if format_param:
            # 如果用户提供了格式，转换为枚举
            if isinstance(format_param, str):
                try:
                    format = FileFormat(format_param.lower())
                except ValueError:
                    return ToolResult(
                        error=self._('file_write_invalid_format', default="Invalid format: {format}. Supported formats: {supported}", format=format_param, supported=', '.join([f.value for f in FileFormat]))
                    )
            else:
                format = format_param
        else:
            # 自动检测格式
            format = self._detect_format(path)
        
        encoding_param = params.get("encoding", "auto")
        compression = params.get("compression", "none")
        
        # 处理编码 - 支持自动检测
        if encoding_param == "auto":
            try:
                from ..utils.encoding_utils import get_system_encoding
                encoding = get_system_encoding()
            except:
                encoding = "utf-8"
        else:
            encoding = encoding_param
        
        try:
            # 路径安全检查
            if not self._is_path_allowed(path):
                return ToolResult(
                    error=self._('file_write_access_denied', default="Access denied: {path} is outside allowed directories", path=path)
                )
            
            # 创建目录（如果不存在）
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 检查模式
            if mode == "create_new" and path.exists():
                return ToolResult(
                    error=self._('file_write_already_exists', default="File already exists: {path}", path=path)
                )
            
            # 流式反馈开始
            if update_output:
                update_output(self._('file_write_progress', default="📝 正在写入{format}文件...\n📁 路径: {path}\n📊 大小: {size}", format=format.value.upper(), path=path, size=self._format_size(len(content.encode('utf-8')))))
            
            # 根据格式处理内容
            formatted_content = await self._format_content(content, format)
            
            # 写入文件
            if compression != "none":
                bytes_written = await self._write_compressed(path, formatted_content, compression, mode)
            else:
                bytes_written = await self._write_normal(path, formatted_content, encoding, mode)
            
            # 计算执行时间
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # 构建结果
            operation_result = FileOperationResult(
                success=True,
                file_path=str(path),
                operation="append" if mode == "append" else "write",
                bytes_processed=bytes_written,
                lines_processed=formatted_content.count('\n') + 1,
                duration_ms=duration_ms,
                format=format,
                encoding=encoding,
                compression=compression if compression != "none" else None
            )
            
            # 返回分层结果
            return self._create_success_result(operation_result, params)
            
        except Exception as e:
            return ToolResult(
                error=self._('file_write_failed', default="Failed to write file: {error}", error=str(e)),
                llm_content=self._('file_write_failed_llm', default="Error writing to {path}: {error}\nType: {type}", path=path, error=str(e), type=type(e).__name__)
            )
    
    # === 私有方法 ===
    
    def _is_path_allowed(self, path: Path) -> bool:
        """检查路径是否在允许的目录内"""
        for allowed_path in self.allowed_paths:
            allowed = Path(allowed_path).resolve()
            try:
                path.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False
    
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
    
    def _detect_format(self, path: Path) -> FileFormat:
        """智能检测文件格式 - 不仅依赖扩展名"""
        ext = path.suffix.lower()
        
        # 首先尝试扩展名匹配
        for format, extensions in self.FORMAT_EXTENSIONS.items():
            if ext in extensions:
                return format
        
        # 如果没有扩展名或未知扩展名，基于路径名称智能推测
        name_lower = path.name.lower()
        if 'data' in name_lower or 'export' in name_lower:
            return FileFormat.CSV  # 数据导出默认CSV
        elif 'report' in name_lower:
            return FileFormat.MARKDOWN  # 报告默认Markdown
        elif 'script' in name_lower:
            return FileFormat.SQL  # 脚本默认SQL
        
        # 默认为文本格式
        return FileFormat.TEXT
    
    def _generate_diff(self, old_content: str, new_content: str, filename: str) -> str:
        """生成Unified Diff格式的差异 - 借鉴Gemini CLI"""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=self._('file_write_diff_current', default="{filename} (当前)", filename=filename),
            tofile=self._('file_write_diff_proposed', default="{filename} (提议)", filename=filename),
            lineterm=''
        )
        
        return ''.join(diff)
    
    def _preview_content(self, content: str, format: FileFormat) -> str:
        """生成内容预览"""
        max_preview = 500
        
        if format == FileFormat.JSON:
            try:
                data = json.loads(content)
                preview = json.dumps(data, indent=2, ensure_ascii=False)[:max_preview]
            except:
                preview = content[:max_preview]
        elif format == FileFormat.CSV:
            lines = content.split('\n')[:10]
            preview = '\n'.join(lines)
        else:
            preview = content[:max_preview]
        
        if len(content) > max_preview:
            preview += self._('file_write_content_truncated', default="\n... [剩余内容省略]")
        
        return preview
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def _get_confirmation_title(self, path: Path, mode: str, format: FileFormat) -> str:
        """生成确认标题"""
        # 更灵活的标题生成，避免硬编码中文
        if mode == "overwrite" and path.exists():
            return self._('file_write_confirm_overwrite', default="Confirm overwriting {filename}", filename=path.name)
        elif mode == "append":
            return self._('file_write_confirm_append', default="Confirm appending to {filename}", filename=path.name)
        else:
            return self._('file_write_confirm_create', default="Confirm creating {filename}", filename=path.name)
    
    async def _format_content(self, content: str, format: FileFormat) -> str:
        """根据格式智能处理内容"""
        if format == FileFormat.JSON:
            # 美化JSON
            try:
                data = json.loads(content)
                return json.dumps(data, indent=2, ensure_ascii=False)
            except:
                return content
        
        elif format == FileFormat.SQL:
            # 添加SQL注释头
            header = self._('file_write_sql_header', default="-- Generated by DbRheo at {timestamp}\n-- {separator}\n\n", timestamp=datetime.now().isoformat(), separator="=" * 50)
            return header + content
        
        elif format == FileFormat.MARKDOWN:
            # 确保标题格式正确
            if not content.startswith('#'):
                return self._('file_write_markdown_header', default="# Data Export Report\n\nGenerated at: {timestamp}\n\n{content}", timestamp=datetime.now().isoformat(), content=content)
            return content
        
        return content
    
    async def _write_normal(self, path: Path, content: str, encoding: str, mode: str) -> int:
        """普通文件写入"""
        file_mode = 'a' if mode == "append" else 'w'
        
        async with aiofiles.open(path, mode=file_mode, encoding=encoding) as f:
            await f.write(content)
        
        return len(content.encode(encoding))
    
    async def _write_compressed(self, path: Path, content: str, compression: str, mode: str) -> int:
        """压缩文件写入"""
        import gzip
        import bz2
        import lzma
        
        # 添加压缩扩展名
        compressed_path = path.with_suffix(path.suffix + f'.{compression}')
        
        # 选择压缩方法
        compress_func = {
            'gzip': gzip.compress,
            'bz2': bz2.compress,
            'xz': lzma.compress
        }.get(compression, gzip.compress)
        
        # 压缩内容
        compressed_data = compress_func(content.encode('utf-8'))
        
        # 写入文件
        file_mode = 'ab' if mode == "append" else 'wb'
        async with aiofiles.open(compressed_path, mode=file_mode) as f:
            await f.write(compressed_data)
        
        return len(compressed_data)
    
    def _create_success_result(self, result: FileOperationResult, params: Dict[str, Any]) -> ToolResult:
        """创建成功结果"""
        path = Path(result.file_path)
        metadata = params.get("metadata", {})
        
        # 构建摘要
        summary_parts = [
            f"Wrote {self._format_size(result.bytes_processed)}",
            f"to {path.name}"
        ]
        if result.compression:
            summary_parts.append(self._('file_write_compression_note', default="(压缩: {compression})", compression=result.compression))
        summary = " ".join(summary_parts)
        
        # 构建 LLM 内容
        llm_content = f"""File successfully written:
- Path: {result.file_path}
- Format: {result.format.value if result.format else 'unknown'}
- Size: {self._format_size(result.bytes_processed)}
- Lines: {result.lines_processed}
- Duration: {result.duration_ms:.1f}ms"""
        
        if metadata.get("source_sql"):
            llm_content += f"\n- Source: SQL query"
            if metadata.get("row_count"):
                llm_content += f"\n- Rows exported: {metadata['row_count']}"
        
        # 构建用户展示
        icon = {
            FileFormat.CSV: '📊',
            FileFormat.JSON: '📋',
            FileFormat.SQL: '🗄️',
            FileFormat.MARKDOWN: '📝',
            FileFormat.EXCEL: '📊'
        }.get(result.format, '📄')
        
        display_lines = [
            self._('file_write_written', default="{icon} 已写入 {filename}", icon=icon, filename=path.name),
            self._('file_write_size', default="💾 大小: {size}", size=self._format_size(result.bytes_processed)),
            self._('file_write_location', default="📁 位置: {location}", location=path.parent)
        ]
        
        if result.compression:
            display_lines.append(self._('file_write_compression', default="🗜️ 压缩: {compression}", compression=result.compression))
        
        if result.duration_ms and result.duration_ms > 1000:
            duration_sec = result.duration_ms/1000
            display_lines.append(self._('file_write_duration', default="⏱️ 耗时: {duration:.1f}秒", duration=duration_sec))
        
        return ToolResult(
            summary=summary,
            llm_content=llm_content,
            return_display="\n".join(display_lines)
        )
    
    def _create_confirmation_details(
        self,
        path: Path,
        content: str,
        mode: str,
        format: FileFormat,
        title: str,
        risk_level: str = "normal"
    ) -> FileWriteConfirmationDetails:
        """创建确认详情"""
        return FileWriteConfirmationDetails(
            title=title,
            file_path=str(path),
            content_preview=self._preview_content(content, format),
            estimated_size=self._format_size(len(content.encode('utf-8'))),
            format=format,
            allow_overwrite=(mode == "overwrite"),
            append_mode=(mode == "append")
        )
