"""
V8 Prometheus Metrics Exporter
==============================

Exports manufacturing metrics in Prometheus format:
- OEE metrics (Availability, Performance, Quality)
- Equipment status and utilization
- Job throughput and cycle times
- Alert counts and response times
- API latency and request rates
- System resource utilization
- Custom business metrics

Endpoints:
- /metrics - Prometheus scrape endpoint

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================
# Metric Types
# ============================================

class MetricType(Enum):
    """Prometheus metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


# ============================================
# Data Classes
# ============================================

@dataclass
class MetricDefinition:
    """Definition of a Prometheus metric."""
    name: str
    metric_type: MetricType
    help_text: str
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None  # For histograms

    def format_help(self) -> str:
        return f"# HELP {self.name} {self.help_text}"

    def format_type(self) -> str:
        return f"# TYPE {self.name} {self.metric_type.value}"


@dataclass
class MetricValue:
    """A metric value with labels."""
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[datetime] = None

    def format_labels(self) -> str:
        if not self.labels:
            return ""
        label_pairs = [f'{k}="{v}"' for k, v in sorted(self.labels.items())]
        return "{" + ",".join(label_pairs) + "}"


@dataclass
class HistogramValue:
    """Histogram metric value."""
    buckets: Dict[float, int] = field(default_factory=dict)
    sum_value: float = 0.0
    count: int = 0
    labels: Dict[str, str] = field(default_factory=dict)


# ============================================
# Prometheus Exporter
# ============================================

class PrometheusExporter:
    """Prometheus metrics exporter."""

    _instance: Optional[PrometheusExporter] = None
    _lock = threading.Lock()

    # Default histogram buckets
    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    OEE_BUCKETS = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0]

    def __init__(self):
        self._metrics: Dict[str, MetricDefinition] = {}
        self._counters: Dict[Tuple[str, ...], float] = defaultdict(float)
        self._gauges: Dict[Tuple[str, ...], float] = {}
        self._histograms: Dict[Tuple[str, ...], HistogramValue] = {}
        self._collectors: List[Callable[[], List[str]]] = []
        self._lock = threading.Lock()

        # Register default metrics
        self._register_default_metrics()

        logger.info("Prometheus exporter initialized")

    @classmethod
    def get_instance(cls) -> PrometheusExporter:
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _register_default_metrics(self):
        """Register default manufacturing metrics."""
        # OEE Metrics
        self.register_metric(MetricDefinition(
            name="lego_oee_availability",
            metric_type=MetricType.GAUGE,
            help_text="Equipment availability ratio (0-1)",
            labels=["equipment_id", "line"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_oee_performance",
            metric_type=MetricType.GAUGE,
            help_text="Equipment performance ratio (0-1)",
            labels=["equipment_id", "line"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_oee_quality",
            metric_type=MetricType.GAUGE,
            help_text="Quality ratio (0-1)",
            labels=["equipment_id", "line"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_oee_overall",
            metric_type=MetricType.GAUGE,
            help_text="Overall Equipment Effectiveness (0-1)",
            labels=["equipment_id", "line"]
        ))

        # Equipment metrics
        self.register_metric(MetricDefinition(
            name="lego_equipment_status",
            metric_type=MetricType.GAUGE,
            help_text="Equipment status (1=running, 0=stopped, -1=error)",
            labels=["equipment_id", "equipment_type", "line"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_equipment_utilization",
            metric_type=MetricType.GAUGE,
            help_text="Equipment utilization percentage",
            labels=["equipment_id", "line"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_equipment_temperature_celsius",
            metric_type=MetricType.GAUGE,
            help_text="Equipment temperature in Celsius",
            labels=["equipment_id", "sensor"]
        ))

        # Job metrics
        self.register_metric(MetricDefinition(
            name="lego_jobs_total",
            metric_type=MetricType.COUNTER,
            help_text="Total jobs processed",
            labels=["status", "job_type"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_job_cycle_time_seconds",
            metric_type=MetricType.HISTOGRAM,
            help_text="Job cycle time in seconds",
            labels=["job_type"],
            buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
        ))

        self.register_metric(MetricDefinition(
            name="lego_parts_produced_total",
            metric_type=MetricType.COUNTER,
            help_text="Total parts produced",
            labels=["part_type", "line"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_defects_total",
            metric_type=MetricType.COUNTER,
            help_text="Total defects detected",
            labels=["defect_type", "line", "severity"]
        ))

        # Alert metrics
        self.register_metric(MetricDefinition(
            name="lego_alerts_total",
            metric_type=MetricType.COUNTER,
            help_text="Total alerts generated",
            labels=["severity", "source", "type"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_alerts_active",
            metric_type=MetricType.GAUGE,
            help_text="Currently active alerts",
            labels=["severity"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_alert_response_time_seconds",
            metric_type=MetricType.HISTOGRAM,
            help_text="Alert response time in seconds",
            labels=["severity"],
            buckets=[30, 60, 120, 300, 600, 1800, 3600, 7200]
        ))

        # API metrics
        self.register_metric(MetricDefinition(
            name="lego_http_requests_total",
            metric_type=MetricType.COUNTER,
            help_text="Total HTTP requests",
            labels=["method", "endpoint", "status_code"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_http_request_duration_seconds",
            metric_type=MetricType.HISTOGRAM,
            help_text="HTTP request duration in seconds",
            labels=["method", "endpoint"],
            buckets=self.DEFAULT_BUCKETS
        ))

        # Simulation metrics
        self.register_metric(MetricDefinition(
            name="lego_simulations_total",
            metric_type=MetricType.COUNTER,
            help_text="Total simulations run",
            labels=["mode", "status"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_simulation_duration_seconds",
            metric_type=MetricType.HISTOGRAM,
            help_text="Simulation duration in seconds",
            labels=["mode"],
            buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600]
        ))

        # Action metrics
        self.register_metric(MetricDefinition(
            name="lego_actions_total",
            metric_type=MetricType.COUNTER,
            help_text="Total actions processed",
            labels=["category", "status"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_action_execution_time_seconds",
            metric_type=MetricType.HISTOGRAM,
            help_text="Action execution time in seconds",
            labels=["category"],
            buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 120]
        ))

        # System metrics
        self.register_metric(MetricDefinition(
            name="lego_system_cpu_usage",
            metric_type=MetricType.GAUGE,
            help_text="System CPU usage percentage"
        ))

        self.register_metric(MetricDefinition(
            name="lego_system_memory_usage",
            metric_type=MetricType.GAUGE,
            help_text="System memory usage percentage"
        ))

        self.register_metric(MetricDefinition(
            name="lego_system_disk_usage",
            metric_type=MetricType.GAUGE,
            help_text="System disk usage percentage"
        ))

        # WebSocket metrics
        self.register_metric(MetricDefinition(
            name="lego_websocket_connections",
            metric_type=MetricType.GAUGE,
            help_text="Active WebSocket connections"
        ))

        self.register_metric(MetricDefinition(
            name="lego_websocket_messages_total",
            metric_type=MetricType.COUNTER,
            help_text="Total WebSocket messages",
            labels=["direction", "event_type"]
        ))

        # ROS2 metrics
        self.register_metric(MetricDefinition(
            name="lego_ros2_nodes_active",
            metric_type=MetricType.GAUGE,
            help_text="Active ROS2 nodes"
        ))

        self.register_metric(MetricDefinition(
            name="lego_ros2_topics_published",
            metric_type=MetricType.COUNTER,
            help_text="Total ROS2 topics published",
            labels=["topic"]
        ))

        # Workflow metrics
        self.register_metric(MetricDefinition(
            name="lego_workflows_active",
            metric_type=MetricType.GAUGE,
            help_text="Active workflows",
            labels=["status"]
        ))

        self.register_metric(MetricDefinition(
            name="lego_workflow_duration_seconds",
            metric_type=MetricType.HISTOGRAM,
            help_text="Workflow execution duration",
            labels=["workflow_type"],
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400]
        ))

    # ============================================
    # Metric Registration
    # ============================================

    def register_metric(self, definition: MetricDefinition):
        """Register a new metric definition."""
        self._metrics[definition.name] = definition

    def register_collector(self, collector: Callable[[], List[str]]):
        """Register a custom collector function."""
        self._collectors.append(collector)

    # ============================================
    # Counter Operations
    # ============================================

    def inc_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        labels = labels or {}
        key = self._make_key(name, labels)

        with self._lock:
            self._counters[key] += value

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value."""
        labels = labels or {}
        key = self._make_key(name, labels)
        return self._counters.get(key, 0.0)

    # ============================================
    # Gauge Operations
    # ============================================

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric value."""
        labels = labels or {}
        key = self._make_key(name, labels)

        with self._lock:
            self._gauges[key] = value

    def inc_gauge(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a gauge metric."""
        labels = labels or {}
        key = self._make_key(name, labels)

        with self._lock:
            self._gauges[key] = self._gauges.get(key, 0.0) + value

    def dec_gauge(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Decrement a gauge metric."""
        self.inc_gauge(name, -value, labels)

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current gauge value."""
        labels = labels or {}
        key = self._make_key(name, labels)
        return self._gauges.get(key, 0.0)

    # ============================================
    # Histogram Operations
    # ============================================

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram observation."""
        labels = labels or {}
        key = self._make_key(name, labels)

        metric_def = self._metrics.get(name)
        buckets = metric_def.buckets if metric_def else self.DEFAULT_BUCKETS

        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = HistogramValue(
                    buckets={b: 0 for b in buckets},
                    labels=labels
                )

            hist = self._histograms[key]
            hist.sum_value += value
            hist.count += 1

            for bucket in buckets:
                if value <= bucket:
                    hist.buckets[bucket] += 1

    # ============================================
    # Helper Methods
    # ============================================

    def _make_key(self, name: str, labels: Dict[str, str]) -> Tuple[str, ...]:
        """Create a unique key for metric + labels."""
        label_items = tuple(sorted(labels.items()))
        return (name,) + label_items

    def _parse_key(self, key: Tuple[str, ...]) -> Tuple[str, Dict[str, str]]:
        """Parse a key back into name and labels."""
        name = key[0]
        labels = dict(key[1:]) if len(key) > 1 else {}
        return name, labels

    def _format_metric_line(self, name: str, value: float, labels: Dict[str, str]) -> str:
        """Format a single metric line."""
        if labels:
            label_str = "{" + ",".join(f'{k}="{v}"' for k, v in sorted(labels.items())) + "}"
            return f"{name}{label_str} {value}"
        return f"{name} {value}"

    # ============================================
    # Export
    # ============================================

    def export(self) -> str:
        """Export all metrics in Prometheus text format."""
        lines = []

        # Collect metrics from services
        self._collect_service_metrics()

        # Group metrics by name
        with self._lock:
            # Export counters
            for key, value in self._counters.items():
                name, labels = self._parse_key(key)
                if name in self._metrics:
                    metric_def = self._metrics[name]
                    if not any(l.startswith(f"# HELP {name}") for l in lines):
                        lines.append(metric_def.format_help())
                        lines.append(metric_def.format_type())
                    lines.append(self._format_metric_line(name, value, labels))

            # Export gauges
            for key, value in self._gauges.items():
                name, labels = self._parse_key(key)
                if name in self._metrics:
                    metric_def = self._metrics[name]
                    if not any(l.startswith(f"# HELP {name}") for l in lines):
                        lines.append(metric_def.format_help())
                        lines.append(metric_def.format_type())
                    lines.append(self._format_metric_line(name, value, labels))

            # Export histograms
            exported_histograms = set()
            for key, hist in self._histograms.items():
                name, labels = self._parse_key(key)
                if name in self._metrics and name not in exported_histograms:
                    metric_def = self._metrics[name]
                    lines.append(metric_def.format_help())
                    lines.append(metric_def.format_type())
                    exported_histograms.add(name)

                # Export bucket lines
                for bucket, count in sorted(hist.buckets.items()):
                    bucket_labels = dict(labels)
                    bucket_labels["le"] = str(bucket)
                    lines.append(self._format_metric_line(f"{name}_bucket", count, bucket_labels))

                # Export +Inf bucket
                inf_labels = dict(labels)
                inf_labels["le"] = "+Inf"
                lines.append(self._format_metric_line(f"{name}_bucket", hist.count, inf_labels))

                # Export sum and count
                lines.append(self._format_metric_line(f"{name}_sum", hist.sum_value, labels))
                lines.append(self._format_metric_line(f"{name}_count", hist.count, labels))

        # Run custom collectors
        for collector in self._collectors:
            try:
                collector_lines = collector()
                lines.extend(collector_lines)
            except Exception as e:
                logger.error(f"Collector failed: {e}")

        return "\n".join(lines) + "\n"

    def _collect_service_metrics(self):
        """Collect metrics from various services."""
        try:
            self._collect_system_metrics()
        except Exception as e:
            logger.debug(f"System metrics collection failed: {e}")

        try:
            self._collect_alert_metrics()
        except Exception as e:
            logger.debug(f"Alert metrics collection failed: {e}")

        try:
            self._collect_equipment_metrics()
        except Exception as e:
            logger.debug(f"Equipment metrics collection failed: {e}")

    def _collect_system_metrics(self):
        """Collect system resource metrics."""
        import psutil

        self.set_gauge("lego_system_cpu_usage", psutil.cpu_percent())
        self.set_gauge("lego_system_memory_usage", psutil.virtual_memory().percent)
        self.set_gauge("lego_system_disk_usage", psutil.disk_usage('/').percent)

    def _collect_alert_metrics(self):
        """Collect alert metrics from alert manager."""
        try:
            from services.command_center import AlertManager

            manager = AlertManager()
            summary = manager.get_summary()

            for severity, count in summary.by_severity.items():
                self.set_gauge(
                    "lego_alerts_active",
                    count,
                    {"severity": severity}
                )
        except Exception:
            pass

    def _collect_equipment_metrics(self):
        """Collect equipment metrics from ROS2."""
        try:
            from services.command_center import get_ros2_command_center

            ros2 = get_ros2_command_center()
            data = ros2.get_dashboard_data()

            self.set_gauge("lego_ros2_nodes_active", data.get("equipment_count", 0))
        except Exception:
            pass


# ============================================
# Flask Blueprint
# ============================================

from flask import Blueprint, Response

metrics_bp = Blueprint('metrics', __name__)


@metrics_bp.route('/metrics')
def prometheus_metrics():
    """Prometheus scrape endpoint."""
    exporter = get_prometheus_exporter()
    metrics_text = exporter.export()

    return Response(
        metrics_text,
        mimetype='text/plain; version=0.0.4; charset=utf-8'
    )


# ============================================
# Singleton Accessor
# ============================================

_exporter: Optional[PrometheusExporter] = None


def get_prometheus_exporter() -> PrometheusExporter:
    """Get Prometheus exporter singleton."""
    global _exporter
    if _exporter is None:
        _exporter = PrometheusExporter.get_instance()
    return _exporter


# ============================================
# Convenience Functions
# ============================================

def record_request(method: str, endpoint: str, status_code: int, duration: float):
    """Record an HTTP request metric."""
    exporter = get_prometheus_exporter()
    exporter.inc_counter(
        "lego_http_requests_total",
        labels={"method": method, "endpoint": endpoint, "status_code": str(status_code)}
    )
    exporter.observe_histogram(
        "lego_http_request_duration_seconds",
        duration,
        labels={"method": method, "endpoint": endpoint}
    )


def record_job(job_type: str, status: str, cycle_time: Optional[float] = None):
    """Record a job metric."""
    exporter = get_prometheus_exporter()
    exporter.inc_counter(
        "lego_jobs_total",
        labels={"status": status, "job_type": job_type}
    )
    if cycle_time is not None:
        exporter.observe_histogram(
            "lego_job_cycle_time_seconds",
            cycle_time,
            labels={"job_type": job_type}
        )


def record_oee(equipment_id: str, line: str, availability: float, performance: float, quality: float):
    """Record OEE metrics."""
    exporter = get_prometheus_exporter()
    labels = {"equipment_id": equipment_id, "line": line}

    exporter.set_gauge("lego_oee_availability", availability, labels)
    exporter.set_gauge("lego_oee_performance", performance, labels)
    exporter.set_gauge("lego_oee_quality", quality, labels)
    exporter.set_gauge("lego_oee_overall", availability * performance * quality, labels)


def record_alert(severity: str, source: str, alert_type: str):
    """Record an alert metric."""
    exporter = get_prometheus_exporter()
    exporter.inc_counter(
        "lego_alerts_total",
        labels={"severity": severity, "source": source, "type": alert_type}
    )


def record_simulation(mode: str, status: str, duration: Optional[float] = None):
    """Record a simulation metric."""
    exporter = get_prometheus_exporter()
    exporter.inc_counter(
        "lego_simulations_total",
        labels={"mode": mode, "status": status}
    )
    if duration is not None:
        exporter.observe_histogram(
            "lego_simulation_duration_seconds",
            duration,
            labels={"mode": mode}
        )


def record_action(category: str, status: str, execution_time: Optional[float] = None):
    """Record an action metric."""
    exporter = get_prometheus_exporter()
    exporter.inc_counter(
        "lego_actions_total",
        labels={"category": category, "status": status}
    )
    if execution_time is not None:
        exporter.observe_histogram(
            "lego_action_execution_time_seconds",
            execution_time,
            labels={"category": category}
        )


# ============================================
# Flask Middleware
# ============================================

class PrometheusMiddleware:
    """Flask middleware for automatic request metrics."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        start_time = time.time()
        method = environ.get('REQUEST_METHOD', 'GET')
        path = environ.get('PATH_INFO', '/')

        def custom_start_response(status, headers, exc_info=None):
            duration = time.time() - start_time
            status_code = status.split(' ')[0]
            record_request(method, path, int(status_code), duration)
            return start_response(status, headers, exc_info)

        return self.app(environ, custom_start_response)
