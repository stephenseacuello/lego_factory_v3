"""
V8 Performance Metrics Collector
=================================

Real-time performance metrics collection and aggregation for:
- API response times
- Service latencies
- Resource utilization
- Throughput metrics
- Error rates
- Queue depths

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import logging
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MetricCategory(Enum):
    """Performance metric categories"""
    API = "api"
    SERVICE = "service"
    DATABASE = "database"
    EQUIPMENT = "equipment"
    QUEUE = "queue"
    RESOURCE = "resource"
    WEBSOCKET = "websocket"
    SIMULATION = "simulation"


class AggregationType(Enum):
    """Metric aggregation types"""
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    COUNT = "count"
    P50 = "p50"
    P90 = "p90"
    P95 = "p95"
    P99 = "p99"
    RATE = "rate"


@dataclass
class MetricSample:
    """Single metric sample"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricDefinition:
    """Definition of a tracked metric"""
    name: str
    category: MetricCategory
    description: str
    unit: str
    aggregations: List[AggregationType]
    retention_minutes: int = 60
    alert_threshold: Optional[float] = None
    alert_comparison: str = "gt"  # gt, lt, eq


@dataclass
class MetricSummary:
    """Aggregated metric summary"""
    name: str
    category: str
    period_start: datetime
    period_end: datetime
    sample_count: int
    values: Dict[str, float]  # aggregation_type -> value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "sample_count": self.sample_count,
            "values": self.values
        }


@dataclass
class PerformanceReport:
    """Performance report for dashboard"""
    generated_at: datetime
    period_minutes: int
    metrics: Dict[str, MetricSummary]
    alerts: List[Dict[str, Any]]
    health_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "period_minutes": self.period_minutes,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "alerts": self.alerts,
            "health_score": self.health_score
        }


class PerformanceCollector:
    """
    Centralized performance metrics collector.

    Collects, aggregates, and reports on system performance metrics
    with support for real-time monitoring and alerting.
    """

    _instance: Optional["PerformanceCollector"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "PerformanceCollector":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._metrics: Dict[str, MetricDefinition] = {}
        self._samples: Dict[str, deque] = {}
        self._alert_handlers: List[Callable[[str, float, float], None]] = []
        self._data_lock = threading.RLock()

        self._setup_default_metrics()
        self._initialized = True

        logger.info("PerformanceCollector initialized")

    def _setup_default_metrics(self) -> None:
        """Setup default V8 performance metrics."""

        # API metrics
        self.define_metric(
            name="api_response_time_ms",
            category=MetricCategory.API,
            description="API endpoint response time in milliseconds",
            unit="ms",
            aggregations=[
                AggregationType.AVG, AggregationType.P50,
                AggregationType.P95, AggregationType.P99,
                AggregationType.MAX
            ],
            alert_threshold=1000.0,
            alert_comparison="gt"
        )

        self.define_metric(
            name="api_requests_total",
            category=MetricCategory.API,
            description="Total API requests",
            unit="count",
            aggregations=[AggregationType.SUM, AggregationType.RATE]
        )

        self.define_metric(
            name="api_errors_total",
            category=MetricCategory.API,
            description="Total API errors",
            unit="count",
            aggregations=[AggregationType.SUM, AggregationType.RATE],
            alert_threshold=10.0,
            alert_comparison="gt"
        )

        # Service metrics
        self.define_metric(
            name="service_latency_ms",
            category=MetricCategory.SERVICE,
            description="Service call latency",
            unit="ms",
            aggregations=[
                AggregationType.AVG, AggregationType.P95,
                AggregationType.MAX
            ],
            alert_threshold=500.0,
            alert_comparison="gt"
        )

        # Database metrics
        self.define_metric(
            name="db_query_time_ms",
            category=MetricCategory.DATABASE,
            description="Database query execution time",
            unit="ms",
            aggregations=[
                AggregationType.AVG, AggregationType.P95,
                AggregationType.MAX
            ],
            alert_threshold=200.0,
            alert_comparison="gt"
        )

        self.define_metric(
            name="db_connections_active",
            category=MetricCategory.DATABASE,
            description="Active database connections",
            unit="count",
            aggregations=[AggregationType.AVG, AggregationType.MAX],
            alert_threshold=50.0,
            alert_comparison="gt"
        )

        # Equipment metrics
        self.define_metric(
            name="equipment_cycle_time_ms",
            category=MetricCategory.EQUIPMENT,
            description="Equipment cycle time",
            unit="ms",
            aggregations=[
                AggregationType.AVG, AggregationType.MIN,
                AggregationType.MAX
            ]
        )

        self.define_metric(
            name="equipment_utilization_pct",
            category=MetricCategory.EQUIPMENT,
            description="Equipment utilization percentage",
            unit="%",
            aggregations=[AggregationType.AVG, AggregationType.MIN],
            alert_threshold=30.0,
            alert_comparison="lt"
        )

        # Queue metrics
        self.define_metric(
            name="queue_depth",
            category=MetricCategory.QUEUE,
            description="Message queue depth",
            unit="count",
            aggregations=[AggregationType.AVG, AggregationType.MAX],
            alert_threshold=1000.0,
            alert_comparison="gt"
        )

        self.define_metric(
            name="queue_processing_time_ms",
            category=MetricCategory.QUEUE,
            description="Queue message processing time",
            unit="ms",
            aggregations=[AggregationType.AVG, AggregationType.P95]
        )

        # Resource metrics
        self.define_metric(
            name="cpu_usage_pct",
            category=MetricCategory.RESOURCE,
            description="CPU usage percentage",
            unit="%",
            aggregations=[AggregationType.AVG, AggregationType.MAX],
            alert_threshold=90.0,
            alert_comparison="gt"
        )

        self.define_metric(
            name="memory_usage_pct",
            category=MetricCategory.RESOURCE,
            description="Memory usage percentage",
            unit="%",
            aggregations=[AggregationType.AVG, AggregationType.MAX],
            alert_threshold=85.0,
            alert_comparison="gt"
        )

        # WebSocket metrics
        self.define_metric(
            name="websocket_connections",
            category=MetricCategory.WEBSOCKET,
            description="Active WebSocket connections",
            unit="count",
            aggregations=[AggregationType.AVG, AggregationType.MAX]
        )

        self.define_metric(
            name="websocket_messages_per_sec",
            category=MetricCategory.WEBSOCKET,
            description="WebSocket messages per second",
            unit="msg/s",
            aggregations=[AggregationType.AVG, AggregationType.MAX]
        )

        # Simulation metrics
        self.define_metric(
            name="simulation_time_ratio",
            category=MetricCategory.SIMULATION,
            description="Simulation time / wall time ratio",
            unit="ratio",
            aggregations=[AggregationType.AVG, AggregationType.MIN]
        )

        self.define_metric(
            name="simulation_iterations_per_sec",
            category=MetricCategory.SIMULATION,
            description="Simulation iterations per second",
            unit="iter/s",
            aggregations=[AggregationType.AVG, AggregationType.MAX]
        )

    def define_metric(
        self,
        name: str,
        category: MetricCategory,
        description: str,
        unit: str,
        aggregations: List[AggregationType],
        retention_minutes: int = 60,
        alert_threshold: Optional[float] = None,
        alert_comparison: str = "gt"
    ) -> None:
        """Define a new metric to track."""
        with self._data_lock:
            self._metrics[name] = MetricDefinition(
                name=name,
                category=category,
                description=description,
                unit=unit,
                aggregations=aggregations,
                retention_minutes=retention_minutes,
                alert_threshold=alert_threshold,
                alert_comparison=alert_comparison
            )
            # Calculate max samples based on retention (1 sample/second max)
            max_samples = retention_minutes * 60
            self._samples[name] = deque(maxlen=max_samples)

    def record(
        self,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a metric sample."""
        with self._data_lock:
            if metric_name not in self._metrics:
                logger.warning(f"Unknown metric: {metric_name}")
                return

            sample = MetricSample(
                timestamp=datetime.now(),
                value=value,
                labels=labels or {}
            )
            self._samples[metric_name].append(sample)

            # Check for alerts
            metric_def = self._metrics[metric_name]
            if metric_def.alert_threshold is not None:
                self._check_alert(metric_name, value, metric_def)

    def _check_alert(
        self,
        metric_name: str,
        value: float,
        metric_def: MetricDefinition
    ) -> None:
        """Check if value triggers an alert."""
        threshold = metric_def.alert_threshold
        triggered = False

        if metric_def.alert_comparison == "gt" and value > threshold:
            triggered = True
        elif metric_def.alert_comparison == "lt" and value < threshold:
            triggered = True
        elif metric_def.alert_comparison == "eq" and value == threshold:
            triggered = True

        if triggered:
            for handler in self._alert_handlers:
                try:
                    handler(metric_name, value, threshold)
                except Exception as e:
                    logger.error(f"Alert handler error: {e}")

    def _calculate_percentile(
        self,
        values: List[float],
        percentile: float
    ) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def _aggregate(
        self,
        samples: List[MetricSample],
        aggregation: AggregationType,
        period_seconds: float = 60.0
    ) -> float:
        """Aggregate samples according to type."""
        if not samples:
            return 0.0

        values = [s.value for s in samples]

        if aggregation == AggregationType.AVG:
            return statistics.mean(values)
        elif aggregation == AggregationType.MIN:
            return min(values)
        elif aggregation == AggregationType.MAX:
            return max(values)
        elif aggregation == AggregationType.SUM:
            return sum(values)
        elif aggregation == AggregationType.COUNT:
            return len(values)
        elif aggregation == AggregationType.P50:
            return self._calculate_percentile(values, 50)
        elif aggregation == AggregationType.P90:
            return self._calculate_percentile(values, 90)
        elif aggregation == AggregationType.P95:
            return self._calculate_percentile(values, 95)
        elif aggregation == AggregationType.P99:
            return self._calculate_percentile(values, 99)
        elif aggregation == AggregationType.RATE:
            return sum(values) / period_seconds if period_seconds > 0 else 0.0

        return 0.0

    def get_summary(
        self,
        metric_name: str,
        period_minutes: int = 5
    ) -> Optional[MetricSummary]:
        """Get aggregated summary for a metric."""
        with self._data_lock:
            if metric_name not in self._metrics:
                return None

            metric_def = self._metrics[metric_name]
            cutoff = datetime.now() - timedelta(minutes=period_minutes)
            samples = [
                s for s in self._samples[metric_name]
                if s.timestamp >= cutoff
            ]

            if not samples:
                return MetricSummary(
                    name=metric_name,
                    category=metric_def.category.value,
                    period_start=cutoff,
                    period_end=datetime.now(),
                    sample_count=0,
                    values={}
                )

            values = {}
            period_seconds = period_minutes * 60
            for agg in metric_def.aggregations:
                values[agg.value] = round(
                    self._aggregate(samples, agg, period_seconds), 3
                )

            return MetricSummary(
                name=metric_name,
                category=metric_def.category.value,
                period_start=min(s.timestamp for s in samples),
                period_end=max(s.timestamp for s in samples),
                sample_count=len(samples),
                values=values
            )

    def get_category_summaries(
        self,
        category: MetricCategory,
        period_minutes: int = 5
    ) -> Dict[str, MetricSummary]:
        """Get summaries for all metrics in a category."""
        summaries = {}
        with self._data_lock:
            for name, metric_def in self._metrics.items():
                if metric_def.category == category:
                    summary = self.get_summary(name, period_minutes)
                    if summary:
                        summaries[name] = summary
        return summaries

    def generate_report(
        self,
        period_minutes: int = 15
    ) -> PerformanceReport:
        """Generate comprehensive performance report."""
        metrics = {}
        alerts = []

        with self._data_lock:
            for name in self._metrics:
                summary = self.get_summary(name, period_minutes)
                if summary and summary.sample_count > 0:
                    metrics[name] = summary

                    # Check for threshold violations in summary
                    metric_def = self._metrics[name]
                    if metric_def.alert_threshold is not None:
                        avg_value = summary.values.get("avg", 0)
                        if (
                            (metric_def.alert_comparison == "gt" and avg_value > metric_def.alert_threshold) or
                            (metric_def.alert_comparison == "lt" and avg_value < metric_def.alert_threshold)
                        ):
                            alerts.append({
                                "metric": name,
                                "value": avg_value,
                                "threshold": metric_def.alert_threshold,
                                "comparison": metric_def.alert_comparison
                            })

        # Calculate health score (0-100)
        health_score = self._calculate_health_score(metrics, alerts)

        return PerformanceReport(
            generated_at=datetime.now(),
            period_minutes=period_minutes,
            metrics=metrics,
            alerts=alerts,
            health_score=health_score
        )

    def _calculate_health_score(
        self,
        metrics: Dict[str, MetricSummary],
        alerts: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall health score."""
        if not metrics:
            return 100.0

        # Start with 100, deduct for alerts
        score = 100.0

        # Each alert reduces score
        alert_penalty = min(len(alerts) * 10, 50)
        score -= alert_penalty

        # Check key metrics for degradation
        key_metrics = [
            ("api_response_time_ms", 500, "p95"),
            ("service_latency_ms", 200, "p95"),
            ("cpu_usage_pct", 80, "avg"),
            ("memory_usage_pct", 80, "avg")
        ]

        for metric_name, warning_threshold, agg_type in key_metrics:
            if metric_name in metrics:
                value = metrics[metric_name].values.get(agg_type, 0)
                if value > warning_threshold:
                    degradation = (value - warning_threshold) / warning_threshold * 10
                    score -= min(degradation, 15)

        return max(0.0, min(100.0, round(score, 1)))

    def register_alert_handler(
        self,
        handler: Callable[[str, float, float], None]
    ) -> None:
        """Register handler for metric alerts."""
        self._alert_handlers.append(handler)

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get metrics formatted for dashboard display."""
        report = self.generate_report(period_minutes=5)

        # Group by category
        by_category = {}
        for name, summary in report.metrics.items():
            cat = summary.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(summary.to_dict())

        return {
            "generated_at": report.generated_at.isoformat(),
            "health_score": report.health_score,
            "alert_count": len(report.alerts),
            "alerts": report.alerts,
            "by_category": by_category,
            "summary": {
                "total_metrics": len(report.metrics),
                "categories": list(by_category.keys())
            }
        }

    def list_metrics(self) -> List[Dict[str, Any]]:
        """List all defined metrics."""
        with self._data_lock:
            return [
                {
                    "name": m.name,
                    "category": m.category.value,
                    "description": m.description,
                    "unit": m.unit,
                    "aggregations": [a.value for a in m.aggregations],
                    "has_alert": m.alert_threshold is not None
                }
                for m in self._metrics.values()
            ]


# Singleton accessor
_collector_instance: Optional[PerformanceCollector] = None


def get_performance_collector() -> PerformanceCollector:
    """Get singleton PerformanceCollector instance."""
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = PerformanceCollector()
    return _collector_instance


# Context manager for timing operations
class TimedOperation:
    """Context manager for recording operation timing."""

    def __init__(
        self,
        metric_name: str,
        labels: Optional[Dict[str, str]] = None
    ):
        self.metric_name = metric_name
        self.labels = labels
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.perf_counter() - self.start_time) * 1000
        get_performance_collector().record(
            self.metric_name,
            elapsed_ms,
            self.labels
        )
        return False


# Convenience functions
def record_api_time(endpoint: str, method: str, duration_ms: float) -> None:
    """Record API response time."""
    get_performance_collector().record(
        "api_response_time_ms",
        duration_ms,
        {"endpoint": endpoint, "method": method}
    )


def record_api_request(endpoint: str, method: str, status_code: int) -> None:
    """Record API request."""
    get_performance_collector().record(
        "api_requests_total",
        1,
        {"endpoint": endpoint, "method": method, "status": str(status_code)}
    )
    if status_code >= 400:
        get_performance_collector().record(
            "api_errors_total",
            1,
            {"endpoint": endpoint, "status": str(status_code)}
        )


def record_service_latency(service: str, operation: str, latency_ms: float) -> None:
    """Record service call latency."""
    get_performance_collector().record(
        "service_latency_ms",
        latency_ms,
        {"service": service, "operation": operation}
    )


def record_db_query(query_type: str, duration_ms: float) -> None:
    """Record database query time."""
    get_performance_collector().record(
        "db_query_time_ms",
        duration_ms,
        {"query_type": query_type}
    )
