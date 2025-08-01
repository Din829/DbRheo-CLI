"""
文件操作相关的类型定义
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
from .tool_types import DatabaseConfirmationDetails


class FileFormat(Enum):
    """支持的文件格式"""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    SQL = "sql"
    MARKDOWN = "markdown"
    TEXT = "text"
    PARQUET = "parquet"
    YAML = "yaml"
    XML = "xml"
    

class ApprovalMode(Enum):
    """文件操作的审批模式"""
    MANUAL = "manual"          # 每次都需要确认
    AUTO_READ = "auto_read"    # 自动允许读取
    AUTO_WRITE = "auto_write"  # 自动允许写入（危险）
    AUTO_ALL = "auto_all"      # 自动允许所有操作
    

@dataclass
class FileWriteConfirmationDetails(DatabaseConfirmationDetails):
    """文件写入确认详情"""
    type: str = "file_write"                 # 确认类型
    title: str = ""
    file_path: str = ""
    file_diff: Optional[str] = None         # diff格式的内容差异
    content_preview: Optional[str] = None    # 内容预览
    estimated_size: Optional[str] = None     # 预估文件大小
    format: Optional[FileFormat] = None      # 文件格式
    
    # 数据库相关的元信息
    data_source_sql: Optional[str] = None    # 数据来源SQL
    affected_tables: Optional[List[str]] = None  # 相关数据表
    row_count: Optional[int] = None          # 导出行数
    
    # 操作选项
    allow_overwrite: bool = True             # 是否允许覆盖
    append_mode: bool = False                # 是否为追加模式
    

@dataclass
class FileOperationResult:
    """文件操作结果的详细信息"""
    success: bool
    file_path: str
    operation: str  # read, write, append, delete
    
    # 统计信息
    bytes_processed: Optional[int] = None
    lines_processed: Optional[int] = None
    duration_ms: Optional[float] = None
    
    # 数据相关
    format: Optional[FileFormat] = None
    encoding: Optional[str] = None
    compression: Optional[str] = None  # gzip, bz2, etc
    
    # 错误信息
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    

@dataclass 
class StreamingConfig:
    """流式处理配置"""
    chunk_size: int = 10000          # 每批处理的行数
    memory_limit_mb: int = 100       # 内存限制（MB）
    progress_interval: int = 1000    # 进度更新间隔（行数）
    enable_compression: bool = True  # 是否启用压缩
    

@dataclass
class FileAnalysisResult:
    """文件分析结果"""
    file_path: str
    file_size: int
    line_count: Optional[int] = None
    
    # 格式信息
    detected_format: Optional[FileFormat] = None
    detected_encoding: Optional[str] = None
    has_header: Optional[bool] = None
    
    # CSV/表格特定
    column_count: Optional[int] = None
    column_names: Optional[List[str]] = None
    data_types: Optional[Dict[str, str]] = None
    null_counts: Optional[Dict[str, int]] = None
    
    # 内容摘要
    preview_lines: Optional[List[str]] = None
    sample_rows: Optional[List[Dict[str, Any]]] = None
