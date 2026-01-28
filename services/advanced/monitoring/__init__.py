"""
V8 Monitoring Services
======================

Real-time monitoring, metrics collection, and alerting
for manufacturing operations.

Features:
- Prometheus metrics export
- Equipment health monitoring
- Production KPI tracking
- Alert management
- Dashboard integration
- V8 Performance metrics collection
- Prometheus exporter for Kubernetes

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from .metrics_exporter import (
    MetricsExporter,
    MetricDefinition as MetricType,  # Alias for compatibility
)
# Placeholder classes for compatibility
MetricLabel = dict
ProductionMetrics = dict
EquipmentMetrics = dict
QualityMetrics = dict
from .performance_collector import (
    PerformanceCollector,
    MetricCategory,
    AggregationType,
    MetricSummary,
    PerformanceReport,
    TimedOperation,
    get_performance_collector,
    record_api_time,
    record_api_request,
    record_service_latency,
    record_db_query,
)
from .prometheus_exporter import (
    PrometheusExporter,
    MetricDefinition,
    metrics_bp,
    get_prometheus_exporter,
    record_request,
    record_job,
    record_oee,
    record_alert,
    record_simulation,
    record_action,
    PrometheusMiddleware,
)

__all__ = [
    # Metrics Exporter
    "MetricsExporter",
    "MetricType",
    "MetricLabel",
    "ProductionMetrics",
    "EquipmentMetrics",
    "QualityMetrics",
    # V8 Performance Collector
    "PerformanceCollector",
    "MetricCategory",
    "AggregationType",
    "MetricSummary",
    "PerformanceReport",
    "TimedOperation",
    "get_performance_collector",
    "record_api_time",
    "record_api_request",
    "record_service_latency",
    "record_db_query",
    # V8 Prometheus Exporter
    "PrometheusExporter",
    "MetricDefinition",
    "metrics_bp",
    "get_prometheus_exporter",
    "record_request",
    "record_job",
    "record_oee",
    "record_alert",
    "record_simulation",
    "record_action",
    "PrometheusMiddleware",
]

__version__ = "8.0.0"
