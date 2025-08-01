"""
DatabaseTracer - 分布式追踪系统
基于OpenTelemetry实现，完全对齐Gemini CLI的追踪机制
"""

import os
import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextlib import contextmanager

# 有条件导入OpenTelemetry，允许在没有安装的情况下降级
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    
from ..config.base import DatabaseConfig


class DatabaseTracer:
    """
    数据库Agent分布式追踪系统
    - 完全对齐Gemini CLI的追踪机制
    - 支持OpenTelemetry集成
    - 提供装饰器和上下文管理器API
    - 支持降级模式（未安装OpenTelemetry时）
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.service_name = config.get("service_name", "database-agent")
        self.enabled = config.get("telemetry_enabled", True)
        
        # 初始化追踪器
        self.tracer = self._setup_tracer() if self.enabled else None
        
    def _setup_tracer(self):
        """设置OpenTelemetry追踪器"""
        if not OTEL_AVAILABLE:
            logging.warning("OpenTelemetry not available, tracing disabled")
            return None
            
        try:
            # 设置追踪提供者
            provider = TracerProvider()
            trace.set_tracer_provider(provider)
            
            # 配置导出器
            otlp_endpoint = self.config.get("otel_exporter_otlp_endpoint")
            if otlp_endpoint:
                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                span_processor = BatchSpanProcessor(otlp_exporter)
                provider.add_span_processor(span_processor)
                
            # 创建追踪器
            return trace.get_tracer(self.service_name)
            
        except Exception as e:
            logging.error(f"Failed to setup tracer: {e}")
            return None
            
    def trace(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        追踪装饰器 - 完全对齐Gemini CLI的trace装饰器
        用于追踪函数执行
        """
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not self.enabled or not self.tracer:
                    return await func(*args, **kwargs)
                    
                with self.tracer.start_as_current_span(name, attributes=attributes):
                    return await func(*args, **kwargs)
                    
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                if not self.enabled or not self.tracer:
                    return func(*args, **kwargs)
                    
                with self.tracer.start_as_current_span(name, attributes=attributes):
                    return func(*args, **kwargs)
                    
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator
        
    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        追踪上下文管理器 - 完全对齐Gemini CLI的withSpan
        用于追踪代码块执行
        """
        if not self.enabled or not self.tracer:
            yield
            return
            
        with self.tracer.start_as_current_span(name, attributes=attributes):
            yield
            
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """向当前span添加事件"""
        if not self.enabled or not self.tracer:
            return
            
        current_span = trace.get_current_span()
        if current_span:
            current_span.add_event(name, attributes=attributes)
            
    def set_attribute(self, key: str, value: Any):
        """设置当前span的属性"""
        if not self.enabled or not self.tracer:
            return
            
        current_span = trace.get_current_span()
        if current_span:
            current_span.set_attribute(key, value)
            
    def record_exception(self, exception: Exception):
        """记录异常"""
        if not self.enabled or not self.tracer:
            return
            
        current_span = trace.get_current_span()
        if current_span:
            current_span.record_exception(exception)
