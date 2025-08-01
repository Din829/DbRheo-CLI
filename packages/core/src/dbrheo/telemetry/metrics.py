"""
DatabaseMetrics - 性能指标收集系统
基于OpenTelemetry Metrics实现，完全对齐Gemini CLI的指标机制
"""

import time
import logging
from typing import Optional, Dict, Any, List
from collections import defaultdict, deque
from dataclasses import dataclass, field

# 有条件导入OpenTelemetry Metrics
try:
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    OTEL_METRICS_AVAILABLE = True
except ImportError:
    OTEL_METRICS_AVAILABLE = False

from ..config.base import DatabaseConfig


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


class DatabaseMetrics:
    """
    数据库Agent性能指标收集系统
    - 完全对齐Gemini CLI的指标机制
    - 支持OpenTelemetry Metrics集成
    - 提供内存缓存和批量导出
    - 支持降级模式（未安装OpenTelemetry时）
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.service_name = config.get("service_name", "database-agent")
        self.enabled = config.get("metrics_enabled", True)
        
        # 内存指标存储（降级模式）
        self.counters: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.gauges: Dict[str, float] = {}
        
        # 初始化OpenTelemetry指标
        self.meter = self._setup_meter() if self.enabled else None
        self._otel_instruments = {}
        
    def _setup_meter(self):
        """设置OpenTelemetry指标收集器"""
        if not OTEL_METRICS_AVAILABLE:
            logging.warning("OpenTelemetry Metrics not available, using memory storage")
            return None
            
        try:
            # 设置指标提供者
            otlp_endpoint = self.config.get("otel_exporter_otlp_endpoint")
            if otlp_endpoint:
                exporter = OTLPMetricExporter(endpoint=otlp_endpoint)
                reader = PeriodicExportingMetricReader(exporter, export_interval_millis=5000)
                provider = MeterProvider(metric_readers=[reader])
                metrics.set_meter_provider(provider)
                
            # 创建指标收集器
            return metrics.get_meter(self.service_name)
            
        except Exception as e:
            logging.error(f"Failed to setup metrics: {e}")
            return None
            
    def counter(self, name: str, description: str = "") -> 'Counter':
        """创建计数器指标"""
        return Counter(self, name, description)
        
    def histogram(self, name: str, description: str = "") -> 'Histogram':
        """创建直方图指标"""
        return Histogram(self, name, description)
        
    def gauge(self, name: str, description: str = "") -> 'Gauge':
        """创建仪表盘指标"""
        return Gauge(self, name, description)
        
    def _get_or_create_counter(self, name: str, description: str):
        """获取或创建OpenTelemetry计数器"""
        if not self.meter:
            return None
            
        if name not in self._otel_instruments:
            self._otel_instruments[name] = self.meter.create_counter(
                name=name,
                description=description
            )
        return self._otel_instruments[name]
        
    def _get_or_create_histogram(self, name: str, description: str):
        """获取或创建OpenTelemetry直方图"""
        if not self.meter:
            return None
            
        if name not in self._otel_instruments:
            self._otel_instruments[name] = self.meter.create_histogram(
                name=name,
                description=description
            )
        return self._otel_instruments[name]
        
    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取指标摘要（用于健康检查和调试）"""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histogram_counts": {k: len(v) for k, v in self.histograms.items()},
            "enabled": self.enabled,
            "otel_available": OTEL_METRICS_AVAILABLE and self.meter is not None
        }


class Counter:
    """计数器指标"""
    
    def __init__(self, metrics: DatabaseMetrics, name: str, description: str):
        self.metrics = metrics
        self.name = name
        self.description = description
        self._otel_counter = metrics._get_or_create_counter(name, description)
        
    def increment(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """增加计数器值"""
        if not self.metrics.enabled:
            return
            
        # 内存存储
        key = f"{self.name}:{labels}" if labels else self.name
        self.metrics.counters[key] += value
        
        # OpenTelemetry
        if self._otel_counter:
            self._otel_counter.add(value, labels or {})


class Histogram:
    """直方图指标"""
    
    def __init__(self, metrics: DatabaseMetrics, name: str, description: str):
        self.metrics = metrics
        self.name = name
        self.description = description
        self._otel_histogram = metrics._get_or_create_histogram(name, description)
        
    def record(self, value: float, labels: Optional[Dict[str, str]] = None):
        """记录直方图值"""
        if not self.metrics.enabled:
            return
            
        # 内存存储
        key = f"{self.name}:{labels}" if labels else self.name
        self.metrics.histograms[key].append(MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels or {}
        ))
        
        # OpenTelemetry
        if self._otel_histogram:
            self._otel_histogram.record(value, labels or {})


class Gauge:
    """仪表盘指标"""
    
    def __init__(self, metrics: DatabaseMetrics, name: str, description: str):
        self.metrics = metrics
        self.name = name
        self.description = description
        
    def set(self, value: float, labels: Optional[Dict[str, str]] = None):
        """设置仪表盘值"""
        if not self.metrics.enabled:
            return
            
        # 内存存储
        key = f"{self.name}:{labels}" if labels else self.name
        self.metrics.gauges[key] = value
        
        # 注意：OpenTelemetry的Gauge需要通过回调函数实现，这里简化处理
