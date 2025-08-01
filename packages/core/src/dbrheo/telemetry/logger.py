"""
DatabaseLogger - 结构化日志系统
完全对齐Gemini CLI的日志机制，支持结构化日志和OpenTelemetry集成
"""

import json
import logging
import sys
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from ..config.base import DatabaseConfig


class DatabaseLogger:
    """
    数据库Agent结构化日志系统
    - 完全对齐Gemini CLI的日志机制
    - 支持JSON格式和文本格式
    - 集成OpenTelemetry追踪信息
    - 支持多种输出目标
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.service_name = config.get("service_name", "database-agent")
        self.log_level = config.get("log_level", "INFO")
        self.log_format = config.get("log_format", "text")  # text | json
        
        # 设置日志器
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """设置日志器配置"""
        logger = logging.getLogger(self.service_name)
        logger.setLevel(getattr(logging, self.log_level.upper()))
        
        # 清除现有处理器
        logger.handlers.clear()
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, self.log_level.upper()))
        
        # 设置格式器
        if self.log_format == "json":
            formatter = JsonFormatter(self.service_name)
        else:
            formatter = TextFormatter()
            
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 文件处理器（如果配置了）
        log_file = self.config.get("log_file")
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(getattr(logging, self.log_level.upper()))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
        return logger
        
    def debug(self, message: str, **kwargs):
        """调试日志"""
        self._log(logging.DEBUG, message, **kwargs)
        
    def info(self, message: str, **kwargs):
        """信息日志"""
        self._log(logging.INFO, message, **kwargs)
        
    def warning(self, message: str, **kwargs):
        """警告日志"""
        self._log(logging.WARNING, message, **kwargs)
        
    def error(self, message: str, **kwargs):
        """错误日志"""
        self._log(logging.ERROR, message, **kwargs)
        
    def critical(self, message: str, **kwargs):
        """严重错误日志"""
        self._log(logging.CRITICAL, message, **kwargs)
        
    def _log(self, level: int, message: str, **kwargs):
        """内部日志方法"""
        # 添加追踪信息
        extra = {
            "service": self.service_name,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        
        # 添加OpenTelemetry追踪信息（如果可用）
        try:
            from opentelemetry import trace
            current_span = trace.get_current_span()
            if current_span:
                span_context = current_span.get_span_context()
                extra.update({
                    "trace_id": format(span_context.trace_id, "032x"),
                    "span_id": format(span_context.span_id, "016x")
                })
        except ImportError:
            pass
            
        self.logger.log(level, message, extra=extra)


class JsonFormatter(logging.Formatter):
    """JSON格式化器 - 完全对齐Gemini CLI的JSON日志格式"""
    
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name
        
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 添加额外字段
        if hasattr(record, 'service'):
            log_entry["service"] = record.service
        if hasattr(record, 'trace_id'):
            log_entry["trace_id"] = record.trace_id
        if hasattr(record, 'span_id'):
            log_entry["span_id"] = record.span_id
            
        # 添加其他自定义字段
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info', 'message', 'service', 
                          'timestamp', 'trace_id', 'span_id']:
                log_entry[key] = value
                
        return json.dumps(log_entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """文本格式化器 - 人类可读的日志格式"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
