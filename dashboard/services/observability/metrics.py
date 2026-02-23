"""
Prometheus Metrics Collection

Implements manufacturing-specific metrics following
Prometheus best practices and naming conventions.

Reference: Prometheus Best Practices, OpenMetrics Specification
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from datetime import datetime
from enum import Enum
from collections import defaultdict
import functools
import re

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Prometheus metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricValue:
    """Single metric value with labels."""
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[float] = None


class Counter:
    """
    Prometheus Counter metric.

    A counter is a cumulative metric that only increases.
    """

    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None
    ):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, value: float = 1.0, **labels) -> None:
        """Increment the counter."""
        if value < 0:
            raise ValueError("Counter can only be incremented")
        key = self._labels_key(labels)
        with self._lock:
            self._values[key] += value

    def labels(self, **labels) -> "LabeledCounter":
        """Get counter with specific labels."""
        return LabeledCounter(self, labels)

    def _labels_key(self, labels: Dict[str, str]) -> tuple:
        """Create hashable key from labels."""
        return tuple(sorted(labels.items()))

    def collect(self) -> List[MetricValue]:
        """Collect all metric values."""
        with self._lock:
            return [
                MetricValue(value=v, labels=dict(k))
                for k, v in self._values.items()
            ]


class LabeledCounter:
    """Counter bound to specific labels."""

    def __init__(self, counter: Counter, labels: Dict[str, str]):
        self._counter = counter
        self._labels = labels

    def inc(self, value: float = 1.0) -> None:
        self._counter.inc(value, **self._labels)


class Gauge:
    """
    Prometheus Gauge metric.

    A gauge can go up and down.
    """

    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None
    ):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def set(self, value: float, **labels) -> None:
        """Set the gauge value."""
        key = self._labels_key(labels)
        with self._lock:
            self._values[key] = value

    def inc(self, value: float = 1.0, **labels) -> None:
        """Increment the gauge."""
        key = self._labels_key(labels)
        with self._lock:
            self._values[key] += value

    def dec(self, value: float = 1.0, **labels) -> None:
        """Decrement the gauge."""
        key = self._labels_key(labels)
        with self._lock:
            self._values[key] -= value

    def labels(self, **labels) -> "LabeledGauge":
        """Get gauge with specific labels."""
        return LabeledGauge(self, labels)

    def _labels_key(self, labels: Dict[str, str]) -> tuple:
        """Create hashable key from labels."""
        return tuple(sorted(labels.items()))

    def collect(self) -> List[MetricValue]:
        """Collect all metric values."""
        with self._lock:
            return [
                MetricValue(value=v, labels=dict(k))
                for k, v in self._values.items()
            ]


class LabeledGauge:
    """Gauge bound to specific labels."""

    def __init__(self, gauge: Gauge, labels: Dict[str, str]):
        self._gauge = gauge
        self._labels = labels

    def set(self, value: float) -> None:
        self._gauge.set(value, **self._labels)

    def inc(self, value: float = 1.0) -> None:
        self._gauge.inc(value, **self._labels)

    def dec(self, value: float = 1.0) -> None:
        self._gauge.dec(value, **self._labels)


class Histogram:
    """
    Prometheus Histogram metric.

    Buckets observations into configurable ranges.
    """

    DEFAULT_BUCKETS = (
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")
    )

    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        buckets: Optional[Tuple[float, ...]] = None
    ):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._bucket_counts: Dict[tuple, Dict[float, int]] = defaultdict(
            lambda: {b: 0 for b in self.buckets}
        )
        self._sums: Dict[tuple, float] = defaultdict(float)
        self._counts: Dict[tuple, int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, value: float, **labels) -> None:
        """Observe a value."""
        key = self._labels_key(labels)
        with self._lock:
            self._sums[key] += value
            self._counts[key] += 1
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[key][bucket] += 1

    def labels(self, **labels) -> "LabeledHistogram":
        """Get histogram with specific labels."""
        return LabeledHistogram(self, labels)

    def time(self, **labels):
        """Context manager for timing operations."""
        return HistogramTimer(self, labels)

    def _labels_key(self, labels: Dict[str, str]) -> tuple:
        """Create hashable key from labels."""
        return tuple(sorted(labels.items()))

    def collect(self) -> List[MetricValue]:
        """Collect all metric values."""
        results = []
        with self._lock:
            for key in self._bucket_counts:
                labels = dict(key)
                # Bucket values
                for bucket, count in self._bucket_counts[key].items():
                    bucket_labels = {**labels, "le": str(bucket)}
                    results.append(MetricValue(value=count, labels=bucket_labels))
                # Sum
                results.append(MetricValue(
                    value=self._sums[key],
                    labels={**labels, "_metric": "sum"}
                ))
                # Count
                results.append(MetricValue(
                    value=self._counts[key],
                    labels={**labels, "_metric": "count"}
                ))
        return results


class LabeledHistogram:
    """Histogram bound to specific labels."""

    def __init__(self, histogram: Histogram, labels: Dict[str, str]):
        self._histogram = histogram
        self._labels = labels

    def observe(self, value: float) -> None:
        self._histogram.observe(value, **self._labels)

    def time(self):
        return HistogramTimer(self._histogram, self._labels)


class HistogramTimer:
    """Context manager for timing with histograms."""

    def __init__(self, histogram: Histogram, labels: Dict[str, str]):
        self._histogram = histogram
        self._labels = labels
        self._start: Optional[float] = None

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._start is not None:
            duration = time.time() - self._start
            self._histogram.observe(duration, **self._labels)


class Summary:
    """
    Prometheus Summary metric.

    Calculates streaming quantiles.
    """

    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        quantiles: Optional[List[float]] = None,
        max_age: float = 600.0
    ):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self.quantiles = quantiles or [0.5, 0.9, 0.99]
        self.max_age = max_age
        self._observations: Dict[tuple, List[Tuple[float, float]]] = defaultdict(list)
        self._lock = threading.Lock()

    def observe(self, value: float, **labels) -> None:
        """Observe a value."""
        key = self._labels_key(labels)
        now = time.time()
        with self._lock:
            # Prune old observations
            cutoff = now - self.max_age
            self._observations[key] = [
                (t, v) for t, v in self._observations[key] if t > cutoff
            ]
            self._observations[key].append((now, value))

    def labels(self, **labels) -> "LabeledSummary":
        """Get summary with specific labels."""
        return LabeledSummary(self, labels)

    def _labels_key(self, labels: Dict[str, str]) -> tuple:
        return tuple(sorted(labels.items()))

    def _calculate_quantile(self, values: List[float], q: float) -> float:
        """Calculate a quantile."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * q)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def collect(self) -> List[MetricValue]:
        """Collect all metric values."""
        results = []
        with self._lock:
            for key, observations in self._observations.items():
                labels = dict(key)
                values = [v for _, v in observations]

                # Quantiles
                for q in self.quantiles:
                    q_labels = {**labels, "quantile": str(q)}
                    results.append(MetricValue(
                        value=self._calculate_quantile(values, q),
                        labels=q_labels
                    ))

                # Sum and count
                results.append(MetricValue(
                    value=sum(values),
                    labels={**labels, "_metric": "sum"}
                ))
                results.append(MetricValue(
                    value=len(values),
                    labels={**labels, "_metric": "count"}
                ))
        return results


class LabeledSummary:
    """Summary bound to specific labels."""

    def __init__(self, summary: Summary, labels: Dict[str, str]):
        self._summary = summary
        self._labels = labels

    def observe(self, value: float) -> None:
        self._summary.observe(value, **self._labels)


class MetricsCollector:
    """
    Central metrics registry and collector.

    Provides Prometheus-compatible metrics exposition.

    Usage:
        >>> collector = MetricsCollector()
        >>> counter = collector.counter("requests_total", "Total requests")
        >>> counter.inc()
        >>> print(collector.exposition())
    """

    def __init__(self, namespace: str = "lego_mcp"):
        """
        Initialize metrics collector.

        Args:
            namespace: Prefix for all metrics
        """
        self.namespace = namespace
        self._metrics: Dict[str, Union[Counter, Gauge, Histogram, Summary]] = {}
        self._lock = threading.Lock()

        logger.info(f"MetricsCollector initialized: namespace={namespace}")

    def _full_name(self, name: str) -> str:
        """Get full metric name with namespace."""
        return f"{self.namespace}_{name}"

    def counter(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None
    ) -> Counter:
        """Create or get a counter metric."""
        full_name = self._full_name(name)
        with self._lock:
            if full_name not in self._metrics:
                self._metrics[full_name] = Counter(full_name, description, labels)
            return self._metrics[full_name]

    def gauge(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None
    ) -> Gauge:
        """Create or get a gauge metric."""
        full_name = self._full_name(name)
        with self._lock:
            if full_name not in self._metrics:
                self._metrics[full_name] = Gauge(full_name, description, labels)
            return self._metrics[full_name]

    def histogram(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        buckets: Optional[Tuple[float, ...]] = None
    ) -> Histogram:
        """Create or get a histogram metric."""
        full_name = self._full_name(name)
        with self._lock:
            if full_name not in self._metrics:
                self._metrics[full_name] = Histogram(
                    full_name, description, labels, buckets
                )
            return self._metrics[full_name]

    def summary(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        quantiles: Optional[List[float]] = None
    ) -> Summary:
        """Create or get a summary metric."""
        full_name = self._full_name(name)
        with self._lock:
            if full_name not in self._metrics:
                self._metrics[full_name] = Summary(
                    full_name, description, labels, quantiles
                )
            return self._metrics[full_name]

    def exposition(self) -> str:
        """
        Generate Prometheus exposition format output.

        Returns:
            Prometheus metrics in text exposition format
        """
        lines = []

        with self._lock:
            for name, metric in self._metrics.items():
                # HELP line
                lines.append(f"# HELP {name} {metric.description}")

                # TYPE line
                if isinstance(metric, Counter):
                    lines.append(f"# TYPE {name} counter")
                elif isinstance(metric, Gauge):
                    lines.append(f"# TYPE {name} gauge")
                elif isinstance(metric, Histogram):
                    lines.append(f"# TYPE {name} histogram")
                elif isinstance(metric, Summary):
                    lines.append(f"# TYPE {name} summary")

                # Values
                for value in metric.collect():
                    if value.labels:
                        label_str = ",".join(
                            f'{k}="{v}"' for k, v in value.labels.items()
                            if not k.startswith("_")
                        )
                        metric_suffix = value.labels.get("_metric", "")
                        if metric_suffix:
                            lines.append(f"{name}_{metric_suffix}{{{label_str}}} {value.value}")
                        elif "le" in value.labels:
                            lines.append(f"{name}_bucket{{{label_str}}} {value.value}")
                        elif "quantile" in value.labels:
                            lines.append(f"{name}{{{label_str}}} {value.value}")
                        else:
                            lines.append(f"{name}{{{label_str}}} {value.value}")
                    else:
                        lines.append(f"{name} {value.value}")

                lines.append("")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._metrics.clear()


class ManufacturingMetrics:
    """
    Pre-defined manufacturing metrics.

    Follows manufacturing-specific semantic conventions
    for OEE, quality, and equipment metrics.
    """

    def __init__(self, collector: Optional[MetricsCollector] = None):
        """
        Initialize manufacturing metrics.

        Args:
            collector: Metrics collector instance
        """
        self.collector = collector or MetricsCollector()
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize all manufacturing metrics."""
        # Production metrics
        self.parts_produced = self.collector.counter(
            "parts_produced_total",
            "Total parts produced",
            labels=["equipment_id", "part_type", "quality"]
        )

        self.production_time = self.collector.histogram(
            "production_time_seconds",
            "Time to produce a part",
            labels=["equipment_id", "part_type"],
            buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600)
        )

        # Quality metrics
        self.quality_score = self.collector.gauge(
            "quality_score",
            "Quality score (0-100)",
            labels=["equipment_id", "measurement_type"]
        )

        self.defects_detected = self.collector.counter(
            "defects_detected_total",
            "Total defects detected",
            labels=["equipment_id", "defect_type", "severity"]
        )

        # Equipment metrics
        self.equipment_state = self.collector.gauge(
            "equipment_state",
            "Equipment state (1=running, 0=stopped, -1=fault)",
            labels=["equipment_id", "state"]
        )

        self.equipment_uptime = self.collector.counter(
            "equipment_uptime_seconds_total",
            "Total equipment uptime",
            labels=["equipment_id"]
        )

        self.equipment_downtime = self.collector.counter(
            "equipment_downtime_seconds_total",
            "Total equipment downtime",
            labels=["equipment_id", "reason"]
        )

        self.equipment_cycles = self.collector.counter(
            "equipment_cycles_total",
            "Total equipment cycles",
            labels=["equipment_id"]
        )

        # OEE metrics
        self.oee_availability = self.collector.gauge(
            "oee_availability",
            "OEE availability component (0-1)",
            labels=["equipment_id"]
        )

        self.oee_performance = self.collector.gauge(
            "oee_performance",
            "OEE performance component (0-1)",
            labels=["equipment_id"]
        )

        self.oee_quality = self.collector.gauge(
            "oee_quality",
            "OEE quality component (0-1)",
            labels=["equipment_id"]
        )

        self.oee_overall = self.collector.gauge(
            "oee_overall",
            "Overall Equipment Effectiveness (0-1)",
            labels=["equipment_id"]
        )

        # Material metrics
        self.material_consumed = self.collector.counter(
            "material_consumed_total",
            "Total material consumed",
            labels=["equipment_id", "material_type", "unit"]
        )

        self.material_waste = self.collector.counter(
            "material_waste_total",
            "Total material waste",
            labels=["equipment_id", "material_type", "unit"]
        )

        # Energy metrics
        self.energy_consumed = self.collector.counter(
            "energy_consumed_kwh_total",
            "Total energy consumed in kWh",
            labels=["equipment_id"]
        )

        # Job metrics
        self.jobs_started = self.collector.counter(
            "jobs_started_total",
            "Total jobs started",
            labels=["equipment_id", "job_type"]
        )

        self.jobs_completed = self.collector.counter(
            "jobs_completed_total",
            "Total jobs completed",
            labels=["equipment_id", "job_type", "status"]
        )

        self.job_duration = self.collector.histogram(
            "job_duration_seconds",
            "Job duration in seconds",
            labels=["equipment_id", "job_type"],
            buckets=(60, 300, 600, 1800, 3600, 7200, 14400, 28800)
        )

        # Sensor metrics
        self.temperature = self.collector.gauge(
            "temperature_celsius",
            "Temperature in Celsius",
            labels=["equipment_id", "sensor_id", "zone"]
        )

        self.pressure = self.collector.gauge(
            "pressure_bar",
            "Pressure in bar",
            labels=["equipment_id", "sensor_id"]
        )

        self.vibration = self.collector.gauge(
            "vibration_mm_per_sec",
            "Vibration velocity in mm/s",
            labels=["equipment_id", "axis"]
        )

        # Communication metrics
        self.messages_sent = self.collector.counter(
            "messages_sent_total",
            "Total messages sent",
            labels=["protocol", "destination"]
        )

        self.messages_received = self.collector.counter(
            "messages_received_total",
            "Total messages received",
            labels=["protocol", "source"]
        )

        self.message_latency = self.collector.histogram(
            "message_latency_seconds",
            "Message latency in seconds",
            labels=["protocol"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
        )

        logger.info("Manufacturing metrics initialized")

    def record_production(
        self,
        equipment_id: str,
        part_type: str,
        duration: float,
        is_good: bool
    ) -> None:
        """Record a production event."""
        quality = "good" if is_good else "reject"
        self.parts_produced.labels(
            equipment_id=equipment_id,
            part_type=part_type,
            quality=quality
        ).inc()
        self.production_time.labels(
            equipment_id=equipment_id,
            part_type=part_type
        ).observe(duration)

    def update_oee(
        self,
        equipment_id: str,
        availability: float,
        performance: float,
        quality: float
    ) -> None:
        """Update OEE metrics for equipment."""
        self.oee_availability.labels(equipment_id=equipment_id).set(availability)
        self.oee_performance.labels(equipment_id=equipment_id).set(performance)
        self.oee_quality.labels(equipment_id=equipment_id).set(quality)
        self.oee_overall.labels(equipment_id=equipment_id).set(
            availability * performance * quality
        )

    def record_equipment_state(
        self,
        equipment_id: str,
        state: str,
        value: int = 1
    ) -> None:
        """Record equipment state change."""
        self.equipment_state.labels(
            equipment_id=equipment_id,
            state=state
        ).set(value)

    def exposition(self) -> str:
        """Get Prometheus exposition format."""
        return self.collector.exposition()


# Global metrics instance
_global_metrics: Optional[ManufacturingMetrics] = None


def get_metrics() -> ManufacturingMetrics:
    """Get the global metrics instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = ManufacturingMetrics()
    return _global_metrics


def set_metrics(metrics: ManufacturingMetrics) -> None:
    """Set the global metrics instance."""
    global _global_metrics
    _global_metrics = metrics
