"""
Prometheus Metrics Exporter
LegoMCP PhD-Level Manufacturing Platform

Exports manufacturing metrics to Prometheus for monitoring:
- OEE (Overall Equipment Effectiveness)
- Production throughput
- Quality metrics
- ML model performance
- API latency
- System health
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, Info,
        generate_latest, CONTENT_TYPE_LATEST,
        CollectorRegistry, multiprocess, REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


# Custom registry for LegoMCP metrics
if PROMETHEUS_AVAILABLE:
    LEGOMCP_REGISTRY = CollectorRegistry()
else:
    LEGOMCP_REGISTRY = None


@dataclass
class MetricDefinition:
    """Definition of a Prometheus metric."""
    name: str
    description: str
    metric_type: str  # counter, gauge, histogram, summary
    labels: list = field(default_factory=list)
    buckets: tuple = None  # For histograms


class MetricsExporter:
    """
    Prometheus metrics exporter for manufacturing operations.

    Provides comprehensive monitoring of:
    - Manufacturing KPIs (OEE, throughput, quality)
    - ML model performance
    - API performance
    - System resources
    - Business metrics
    """

    def __init__(self, registry=None):
        self.registry = registry or LEGOMCP_REGISTRY
        self._metrics: Dict[str, Any] = {}
        self._initialized = False

        if PROMETHEUS_AVAILABLE:
            self._initialize_metrics()

    def _initialize_metrics(self):
        """Initialize all Prometheus metrics."""
        if self._initialized:
            return

        # =====================================================================
        # MANUFACTURING METRICS
        # =====================================================================

        # OEE Metrics
        self._metrics["oee_availability"] = Gauge(
            "legomcp_oee_availability",
            "Equipment availability rate (0-1)",
            ["equipment_id", "cell"],
            registry=self.registry,
        )

        self._metrics["oee_performance"] = Gauge(
            "legomcp_oee_performance",
            "Equipment performance rate (0-1)",
            ["equipment_id", "cell"],
            registry=self.registry,
        )

        self._metrics["oee_quality"] = Gauge(
            "legomcp_oee_quality",
            "Equipment quality rate (0-1)",
            ["equipment_id", "cell"],
            registry=self.registry,
        )

        self._metrics["oee_overall"] = Gauge(
            "legomcp_oee_overall",
            "Overall Equipment Effectiveness (0-1)",
            ["equipment_id", "cell"],
            registry=self.registry,
        )

        # Production Metrics
        self._metrics["parts_produced_total"] = Counter(
            "legomcp_parts_produced_total",
            "Total parts produced",
            ["equipment_id", "product_id", "cell"],
            registry=self.registry,
        )

        self._metrics["defects_total"] = Counter(
            "legomcp_defects_total",
            "Total defects detected",
            ["equipment_id", "defect_type", "severity"],
            registry=self.registry,
        )

        self._metrics["cycle_time_seconds"] = Histogram(
            "legomcp_cycle_time_seconds",
            "Production cycle time in seconds",
            ["equipment_id", "operation"],
            buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
            registry=self.registry,
        )

        self._metrics["downtime_seconds_total"] = Counter(
            "legomcp_downtime_seconds_total",
            "Total equipment downtime in seconds",
            ["equipment_id", "reason"],
            registry=self.registry,
        )

        self._metrics["work_orders_total"] = Counter(
            "legomcp_work_orders_total",
            "Total work orders",
            ["status"],
            registry=self.registry,
        )

        self._metrics["work_orders_active"] = Gauge(
            "legomcp_work_orders_active",
            "Currently active work orders",
            ["priority"],
            registry=self.registry,
        )

        # Energy Metrics
        self._metrics["energy_consumption_kwh"] = Counter(
            "legomcp_energy_consumption_kwh_total",
            "Total energy consumption in kWh",
            ["equipment_id", "source"],
            registry=self.registry,
        )

        self._metrics["power_usage_kw"] = Gauge(
            "legomcp_power_usage_kw",
            "Current power usage in kW",
            ["equipment_id"],
            registry=self.registry,
        )

        self._metrics["carbon_emissions_kg"] = Counter(
            "legomcp_carbon_emissions_kg_total",
            "Total carbon emissions in kg CO2e",
            ["scope", "category"],
            registry=self.registry,
        )

        # =====================================================================
        # ML MODEL METRICS
        # =====================================================================

        self._metrics["ml_predictions_total"] = Counter(
            "legomcp_ml_predictions_total",
            "Total ML predictions made",
            ["model_name", "model_version"],
            registry=self.registry,
        )

        self._metrics["ml_prediction_latency_seconds"] = Histogram(
            "legomcp_ml_prediction_latency_seconds",
            "ML prediction latency in seconds",
            ["model_name"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1),
            registry=self.registry,
        )

        self._metrics["ml_prediction_confidence"] = Histogram(
            "legomcp_ml_prediction_confidence",
            "ML prediction confidence score",
            ["model_name"],
            buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99),
            registry=self.registry,
        )

        self._metrics["ml_model_accuracy"] = Gauge(
            "legomcp_ml_model_accuracy",
            "Current model accuracy",
            ["model_name", "model_version"],
            registry=self.registry,
        )

        self._metrics["ml_drift_score"] = Gauge(
            "legomcp_ml_drift_score",
            "Model drift score (0-1)",
            ["model_name", "drift_type"],
            registry=self.registry,
        )

        # =====================================================================
        # API METRICS
        # =====================================================================

        self._metrics["http_requests_total"] = Counter(
            "legomcp_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
            registry=self.registry,
        )

        self._metrics["http_request_duration_seconds"] = Histogram(
            "legomcp_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
            registry=self.registry,
        )

        self._metrics["http_request_size_bytes"] = Histogram(
            "legomcp_http_request_size_bytes",
            "HTTP request size in bytes",
            ["method", "endpoint"],
            buckets=(100, 1000, 10000, 100000, 1000000),
            registry=self.registry,
        )

        self._metrics["websocket_connections"] = Gauge(
            "legomcp_websocket_connections",
            "Active WebSocket connections",
            ["namespace"],
            registry=self.registry,
        )

        # =====================================================================
        # QUALITY METRICS
        # =====================================================================

        self._metrics["spc_control_violations"] = Counter(
            "legomcp_spc_control_violations_total",
            "Total SPC control violations",
            ["parameter", "rule"],
            registry=self.registry,
        )

        self._metrics["quality_score"] = Gauge(
            "legomcp_quality_score",
            "Current quality score (0-100)",
            ["cell", "product"],
            registry=self.registry,
        )

        self._metrics["inspection_duration_seconds"] = Histogram(
            "legomcp_inspection_duration_seconds",
            "Quality inspection duration",
            ["inspection_type"],
            buckets=(1, 5, 10, 30, 60, 120, 300),
            registry=self.registry,
        )

        # =====================================================================
        # SYSTEM METRICS
        # =====================================================================

        self._metrics["service_info"] = Info(
            "legomcp_service",
            "Service information",
            registry=self.registry,
        )

        self._metrics["database_connections"] = Gauge(
            "legomcp_database_connections",
            "Active database connections",
            ["pool"],
            registry=self.registry,
        )

        self._metrics["redis_connections"] = Gauge(
            "legomcp_redis_connections",
            "Active Redis connections",
            registry=self.registry,
        )

        self._metrics["task_queue_size"] = Gauge(
            "legomcp_task_queue_size",
            "Number of tasks in queue",
            ["queue_name"],
            registry=self.registry,
        )

        self._metrics["scheduler_jobs_active"] = Gauge(
            "legomcp_scheduler_jobs_active",
            "Active scheduler jobs",
            registry=self.registry,
        )

        self._initialized = True
        logger.info("Prometheus metrics initialized")

    # =========================================================================
    # MANUFACTURING METRIC METHODS
    # =========================================================================

    def record_oee(
        self,
        equipment_id: str,
        availability: float,
        performance: float,
        quality: float,
        cell: str = "default",
    ):
        """Record OEE metrics for equipment."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["oee_availability"].labels(
            equipment_id=equipment_id, cell=cell
        ).set(availability)

        self._metrics["oee_performance"].labels(
            equipment_id=equipment_id, cell=cell
        ).set(performance)

        self._metrics["oee_quality"].labels(
            equipment_id=equipment_id, cell=cell
        ).set(quality)

        oee = availability * performance * quality
        self._metrics["oee_overall"].labels(
            equipment_id=equipment_id, cell=cell
        ).set(oee)

    def record_production(
        self,
        equipment_id: str,
        parts: int,
        defects: int = 0,
        cycle_time: float = None,
        product_id: str = "unknown",
        cell: str = "default",
    ):
        """Record production metrics."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["parts_produced_total"].labels(
            equipment_id=equipment_id,
            product_id=product_id,
            cell=cell,
        ).inc(parts)

        if defects > 0:
            self._metrics["defects_total"].labels(
                equipment_id=equipment_id,
                defect_type="general",
                severity="medium",
            ).inc(defects)

        if cycle_time is not None:
            self._metrics["cycle_time_seconds"].labels(
                equipment_id=equipment_id,
                operation="production",
            ).observe(cycle_time)

    def record_defect(
        self,
        equipment_id: str,
        defect_type: str,
        severity: str = "medium",
    ):
        """Record a defect detection."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["defects_total"].labels(
            equipment_id=equipment_id,
            defect_type=defect_type,
            severity=severity,
        ).inc()

    def record_downtime(
        self,
        equipment_id: str,
        seconds: float,
        reason: str = "unplanned",
    ):
        """Record equipment downtime."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["downtime_seconds_total"].labels(
            equipment_id=equipment_id,
            reason=reason,
        ).inc(seconds)

    def record_energy(
        self,
        equipment_id: str,
        kwh: float,
        source: str = "grid",
        carbon_kg: float = None,
    ):
        """Record energy consumption."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["energy_consumption_kwh"].labels(
            equipment_id=equipment_id,
            source=source,
        ).inc(kwh)

        if carbon_kg is not None:
            self._metrics["carbon_emissions_kg"].labels(
                scope="2",
                category="electricity",
            ).inc(carbon_kg)

    # =========================================================================
    # ML METRIC METHODS
    # =========================================================================

    def record_ml_prediction(
        self,
        model_name: str,
        latency_seconds: float,
        confidence: float,
        model_version: str = "latest",
    ):
        """Record ML prediction metrics."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["ml_predictions_total"].labels(
            model_name=model_name,
            model_version=model_version,
        ).inc()

        self._metrics["ml_prediction_latency_seconds"].labels(
            model_name=model_name,
        ).observe(latency_seconds)

        self._metrics["ml_prediction_confidence"].labels(
            model_name=model_name,
        ).observe(confidence)

    def set_ml_accuracy(
        self,
        model_name: str,
        accuracy: float,
        model_version: str = "latest",
    ):
        """Set current model accuracy."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["ml_model_accuracy"].labels(
            model_name=model_name,
            model_version=model_version,
        ).set(accuracy)

    def record_drift(
        self,
        model_name: str,
        drift_score: float,
        drift_type: str = "data",
    ):
        """Record model drift score."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["ml_drift_score"].labels(
            model_name=model_name,
            drift_type=drift_type,
        ).set(drift_score)

    # =========================================================================
    # API METRIC METHODS
    # =========================================================================

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration_seconds: float,
        request_size: int = 0,
    ):
        """Record HTTP request metrics."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["http_requests_total"].labels(
            method=method,
            endpoint=endpoint,
            status=str(status),
        ).inc()

        self._metrics["http_request_duration_seconds"].labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration_seconds)

        if request_size > 0:
            self._metrics["http_request_size_bytes"].labels(
                method=method,
                endpoint=endpoint,
            ).observe(request_size)

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def set_service_info(self, info: Dict[str, str]):
        """Set service info labels."""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics["service_info"].info(info)

    def get_metrics(self) -> bytes:
        """Get metrics in Prometheus format."""
        if not PROMETHEUS_AVAILABLE:
            return b"# Prometheus client not available\n"

        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """Get Prometheus content type."""
        if not PROMETHEUS_AVAILABLE:
            return "text/plain"
        return CONTENT_TYPE_LATEST


# Global instance
metrics = MetricsExporter()


# Decorators for automatic metric collection
def track_time(metric_name: str, labels: Dict[str, str] = None):
    """Decorator to track function execution time."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = f(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                if PROMETHEUS_AVAILABLE and metric_name in metrics._metrics:
                    metric = metrics._metrics[metric_name]
                    if labels:
                        metric.labels(**labels).observe(duration)
                    else:
                        metric.observe(duration)
        return wrapper
    return decorator


def count_calls(metric_name: str, labels: Dict[str, str] = None):
    """Decorator to count function calls."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if PROMETHEUS_AVAILABLE and metric_name in metrics._metrics:
                metric = metrics._metrics[metric_name]
                if labels:
                    metric.labels(**labels).inc()
                else:
                    metric.inc()
            return f(*args, **kwargs)
        return wrapper
    return decorator
