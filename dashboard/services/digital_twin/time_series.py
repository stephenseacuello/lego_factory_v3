"""
Time Series Adapter - InfluxDB Integration for Digital Twin

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- InfluxDB client wrapper
- Telemetry data storage
- Time-series queries
- Aggregation and downsampling
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
import threading
from collections import defaultdict
import statistics


class AggregationType(Enum):
    """Aggregation types for queries."""
    MEAN = "mean"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    FIRST = "first"
    LAST = "last"
    MEDIAN = "median"
    STDDEV = "stddev"
    SPREAD = "spread"  # max - min


class TimeUnit(Enum):
    """Time units for queries."""
    SECOND = "s"
    MINUTE = "m"
    HOUR = "h"
    DAY = "d"
    WEEK = "w"


@dataclass
class DataPoint:
    """A single time-series data point."""
    measurement: str
    tags: Dict[str, str]
    fields: Dict[str, Union[float, int, str, bool]]
    timestamp: datetime

    def to_line_protocol(self) -> str:
        """Convert to InfluxDB line protocol."""
        # Measurement
        line = self.measurement

        # Tags
        if self.tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(self.tags.items()))
            line += f",{tag_str}"

        # Fields
        field_parts = []
        for k, v in self.fields.items():
            if isinstance(v, str):
                field_parts.append(f'{k}="{v}"')
            elif isinstance(v, bool):
                field_parts.append(f"{k}={str(v).lower()}")
            elif isinstance(v, int):
                field_parts.append(f"{k}={v}i")
            else:
                field_parts.append(f"{k}={v}")

        line += f" {','.join(field_parts)}"

        # Timestamp (nanoseconds)
        ts_ns = int(self.timestamp.timestamp() * 1e9)
        line += f" {ts_ns}"

        return line


@dataclass
class QueryResult:
    """Result of a time-series query."""
    measurement: str
    tags: Dict[str, str]
    columns: List[str]
    values: List[List[Any]]
    start_time: datetime
    end_time: datetime

    def to_dataframe(self) -> Dict[str, List[Any]]:
        """Convert to DataFrame-like dict."""
        result = {col: [] for col in self.columns}
        for row in self.values:
            for i, val in enumerate(row):
                result[self.columns[i]].append(val)
        return result


@dataclass
class TimeSeriesConfig:
    """Time series adapter configuration."""
    url: str = "http://localhost:8086"
    org: str = "legomcp"
    bucket: str = "manufacturing"
    token: str = ""  # Set via environment
    batch_size: int = 1000
    flush_interval_seconds: float = 1.0
    enable_compression: bool = True
    retention_days: int = 30
    default_precision: str = "ns"


@dataclass
class RetentionPolicy:
    """Retention policy for data."""
    name: str
    duration: str  # e.g., "30d", "1w"
    replication: int = 1
    shard_duration: str = "1h"
    is_default: bool = False


class TimeSeriesAdapter:
    """
    InfluxDB time-series adapter for Digital Twin telemetry.

    Features:
    - Buffered writes for efficiency
    - Query builder for complex queries
    - Downsampling and aggregation
    - Retention policy management
    """

    def __init__(self, config: Optional[TimeSeriesConfig] = None):
        """
        Initialize time series adapter.

        Args:
            config: Adapter configuration
        """
        self.config = config or TimeSeriesConfig()

        # Write buffer
        self._write_buffer: List[DataPoint] = []
        self._buffer_lock = threading.Lock()

        # Client placeholder (real implementation uses influxdb_client)
        self._client = None
        self._write_api = None
        self._query_api = None

        # In-memory storage for testing/fallback
        self._memory_store: Dict[str, List[DataPoint]] = defaultdict(list)

        # Statistics
        self._stats = {
            "points_written": 0,
            "points_queried": 0,
            "flush_count": 0,
            "errors": 0,
        }

        # Background flush thread
        self._flush_thread: Optional[threading.Thread] = None
        self._running = False

    def connect(self) -> bool:
        """
        Connect to InfluxDB.

        Returns:
            Connection success
        """
        try:
            # In real implementation:
            # from influxdb_client import InfluxDBClient
            # self._client = InfluxDBClient(
            #     url=self.config.url,
            #     token=self.config.token,
            #     org=self.config.org
            # )
            # self._write_api = self._client.write_api()
            # self._query_api = self._client.query_api()

            # Using memory store for now
            self._running = True
            self._start_flush_thread()
            return True

        except Exception as e:
            self._stats["errors"] += 1
            return False

    def disconnect(self):
        """Disconnect from InfluxDB."""
        self._running = False
        self.flush()

        if self._client:
            self._client.close()

    def write(
        self,
        measurement: str,
        fields: Dict[str, Union[float, int, str, bool]],
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Write a data point.

        Args:
            measurement: Measurement name
            fields: Field values
            tags: Tag values
            timestamp: Point timestamp (now if None)

        Returns:
            Write success
        """
        point = DataPoint(
            measurement=measurement,
            tags=tags or {},
            fields=fields,
            timestamp=timestamp or datetime.utcnow(),
        )

        with self._buffer_lock:
            self._write_buffer.append(point)

            if len(self._write_buffer) >= self.config.batch_size:
                self._flush_buffer()

        return True

    def write_points(self, points: List[DataPoint]) -> bool:
        """Write multiple points."""
        with self._buffer_lock:
            self._write_buffer.extend(points)

            if len(self._write_buffer) >= self.config.batch_size:
                self._flush_buffer()

        return True

    def flush(self):
        """Flush write buffer."""
        with self._buffer_lock:
            self._flush_buffer()

    def query(
        self,
        measurement: str,
        start: datetime,
        end: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None,
        fields: Optional[List[str]] = None,
        aggregation: Optional[AggregationType] = None,
        window: Optional[Tuple[int, TimeUnit]] = None,
        limit: Optional[int] = None
    ) -> QueryResult:
        """
        Query time-series data.

        Args:
            measurement: Measurement to query
            start: Start time
            end: End time (now if None)
            tags: Tag filters
            fields: Fields to return
            aggregation: Aggregation type
            window: Aggregation window (value, unit)
            limit: Maximum points

        Returns:
            Query result
        """
        end = end or datetime.utcnow()

        self._stats["points_queried"] += 1

        # Query from memory store
        points = self._memory_store.get(measurement, [])

        # Filter by time range
        filtered = [
            p for p in points
            if start <= p.timestamp <= end
        ]

        # Filter by tags
        if tags:
            filtered = [
                p for p in filtered
                if all(p.tags.get(k) == v for k, v in tags.items())
            ]

        # Sort by timestamp
        filtered.sort(key=lambda p: p.timestamp)

        # Apply aggregation if specified
        if aggregation and window:
            filtered = self._aggregate_points(
                filtered, aggregation, window, fields
            )

        # Apply limit
        if limit:
            filtered = filtered[:limit]

        # Build result
        if not filtered:
            return QueryResult(
                measurement=measurement,
                tags=tags or {},
                columns=["time"] + (fields or ["value"]),
                values=[],
                start_time=start,
                end_time=end,
            )

        # Extract columns from first point
        sample_fields = list(filtered[0].fields.keys()) if filtered else []
        columns = ["time"] + (fields or sample_fields)

        values = []
        for p in filtered:
            row = [p.timestamp.isoformat()]
            for col in columns[1:]:
                row.append(p.fields.get(col))
            values.append(row)

        return QueryResult(
            measurement=measurement,
            tags=tags or {},
            columns=columns,
            values=values,
            start_time=start,
            end_time=end,
        )

    def query_last(
        self,
        measurement: str,
        tags: Optional[Dict[str, str]] = None,
        field: str = "value"
    ) -> Optional[Tuple[datetime, Any]]:
        """
        Get last value for a measurement.

        Args:
            measurement: Measurement name
            tags: Tag filters
            field: Field to return

        Returns:
            (timestamp, value) or None
        """
        points = self._memory_store.get(measurement, [])

        if tags:
            points = [
                p for p in points
                if all(p.tags.get(k) == v for k, v in tags.items())
            ]

        if not points:
            return None

        latest = max(points, key=lambda p: p.timestamp)
        return (latest.timestamp, latest.fields.get(field))

    def query_aggregated(
        self,
        measurement: str,
        start: datetime,
        end: Optional[datetime] = None,
        aggregation: AggregationType = AggregationType.MEAN,
        window_minutes: int = 5,
        tags: Optional[Dict[str, str]] = None,
        field: str = "value"
    ) -> List[Dict[str, Any]]:
        """
        Query aggregated data.

        Args:
            measurement: Measurement name
            start: Start time
            end: End time
            aggregation: Aggregation type
            window_minutes: Window size in minutes
            tags: Tag filters
            field: Field to aggregate

        Returns:
            List of aggregated values
        """
        end = end or datetime.utcnow()

        result = self.query(
            measurement=measurement,
            start=start,
            end=end,
            tags=tags,
            fields=[field],
            aggregation=aggregation,
            window=(window_minutes, TimeUnit.MINUTE),
        )

        aggregated = []
        for row in result.values:
            aggregated.append({
                "time": row[0],
                field: row[1] if len(row) > 1 else None,
            })

        return aggregated

    def delete(
        self,
        measurement: str,
        start: datetime,
        end: datetime,
        tags: Optional[Dict[str, str]] = None
    ) -> int:
        """
        Delete data points.

        Args:
            measurement: Measurement name
            start: Start time
            end: End time
            tags: Tag filters

        Returns:
            Number of points deleted
        """
        points = self._memory_store.get(measurement, [])
        original_count = len(points)

        def should_keep(p: DataPoint) -> bool:
            if not (start <= p.timestamp <= end):
                return True
            if tags and not all(p.tags.get(k) == v for k, v in tags.items()):
                return True
            return False

        self._memory_store[measurement] = [p for p in points if should_keep(p)]

        return original_count - len(self._memory_store[measurement])

    def create_retention_policy(self, policy: RetentionPolicy) -> bool:
        """Create a retention policy."""
        # In real implementation, this creates an InfluxDB retention policy
        return True

    def downsample(
        self,
        measurement: str,
        source_window: Tuple[int, TimeUnit],
        target_window: Tuple[int, TimeUnit],
        aggregation: AggregationType = AggregationType.MEAN,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> int:
        """
        Downsample data to a coarser resolution.

        Args:
            measurement: Measurement name
            source_window: Source resolution
            target_window: Target resolution
            aggregation: Aggregation type
            start: Start time
            end: End time

        Returns:
            Number of points created
        """
        end = end or datetime.utcnow()
        start = start or (end - timedelta(days=7))

        # Query data
        result = self.query(
            measurement=measurement,
            start=start,
            end=end,
            aggregation=aggregation,
            window=target_window,
        )

        # Write to downsampled measurement
        downsampled_measurement = f"{measurement}_downsampled"

        for row in result.values:
            self.write(
                measurement=downsampled_measurement,
                fields={"value": row[1]} if len(row) > 1 else {},
                timestamp=datetime.fromisoformat(row[0]),
            )

        return len(result.values)

    def get_measurements(self) -> List[str]:
        """Get list of measurements."""
        return list(self._memory_store.keys())

    def get_tag_keys(self, measurement: str) -> List[str]:
        """Get tag keys for a measurement."""
        points = self._memory_store.get(measurement, [])
        keys = set()
        for p in points:
            keys.update(p.tags.keys())
        return list(keys)

    def get_tag_values(self, measurement: str, tag_key: str) -> List[str]:
        """Get tag values for a key."""
        points = self._memory_store.get(measurement, [])
        values = set()
        for p in points:
            if tag_key in p.tags:
                values.add(p.tags[tag_key])
        return list(values)

    def get_field_keys(self, measurement: str) -> List[str]:
        """Get field keys for a measurement."""
        points = self._memory_store.get(measurement, [])
        keys = set()
        for p in points:
            keys.update(p.fields.keys())
        return list(keys)

    def get_statistics(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        total_points = sum(len(pts) for pts in self._memory_store.values())

        return {
            **self._stats,
            "buffer_size": len(self._write_buffer),
            "measurements": len(self._memory_store),
            "total_points_stored": total_points,
            "connected": self._running,
        }

    def _flush_buffer(self):
        """Flush write buffer to storage."""
        if not self._write_buffer:
            return

        points_to_flush = self._write_buffer.copy()
        self._write_buffer.clear()

        for point in points_to_flush:
            self._memory_store[point.measurement].append(point)

        self._stats["points_written"] += len(points_to_flush)
        self._stats["flush_count"] += 1

    def _start_flush_thread(self):
        """Start background flush thread."""
        def flush_loop():
            import time
            while self._running:
                time.sleep(self.config.flush_interval_seconds)
                self.flush()

        self._flush_thread = threading.Thread(target=flush_loop, daemon=True)
        self._flush_thread.start()

    def _aggregate_points(
        self,
        points: List[DataPoint],
        aggregation: AggregationType,
        window: Tuple[int, TimeUnit],
        fields: Optional[List[str]]
    ) -> List[DataPoint]:
        """Aggregate points over time windows."""
        if not points:
            return []

        # Calculate window duration
        value, unit = window
        if unit == TimeUnit.SECOND:
            delta = timedelta(seconds=value)
        elif unit == TimeUnit.MINUTE:
            delta = timedelta(minutes=value)
        elif unit == TimeUnit.HOUR:
            delta = timedelta(hours=value)
        elif unit == TimeUnit.DAY:
            delta = timedelta(days=value)
        else:
            delta = timedelta(weeks=value)

        # Group points by window
        windows: Dict[datetime, List[DataPoint]] = defaultdict(list)

        for point in points:
            # Calculate window start
            ts = point.timestamp
            window_start = datetime(
                ts.year, ts.month, ts.day, ts.hour, ts.minute
            )
            # Round to window
            seconds_into_day = (ts - datetime(ts.year, ts.month, ts.day)).total_seconds()
            window_seconds = delta.total_seconds()
            window_num = int(seconds_into_day // window_seconds)
            window_start = datetime(ts.year, ts.month, ts.day) + timedelta(seconds=window_num * window_seconds)

            windows[window_start].append(point)

        # Aggregate each window
        aggregated = []

        for window_time, window_points in sorted(windows.items()):
            agg_fields = {}

            # Get all field keys
            all_fields = fields or list(set(
                k for p in window_points for k in p.fields.keys()
            ))

            for field_key in all_fields:
                values = [
                    p.fields.get(field_key)
                    for p in window_points
                    if field_key in p.fields and isinstance(p.fields[field_key], (int, float))
                ]

                if not values:
                    continue

                if aggregation == AggregationType.MEAN:
                    agg_fields[field_key] = statistics.mean(values)
                elif aggregation == AggregationType.SUM:
                    agg_fields[field_key] = sum(values)
                elif aggregation == AggregationType.MIN:
                    agg_fields[field_key] = min(values)
                elif aggregation == AggregationType.MAX:
                    agg_fields[field_key] = max(values)
                elif aggregation == AggregationType.COUNT:
                    agg_fields[field_key] = len(values)
                elif aggregation == AggregationType.FIRST:
                    agg_fields[field_key] = values[0]
                elif aggregation == AggregationType.LAST:
                    agg_fields[field_key] = values[-1]
                elif aggregation == AggregationType.MEDIAN:
                    agg_fields[field_key] = statistics.median(values)
                elif aggregation == AggregationType.STDDEV:
                    agg_fields[field_key] = statistics.stdev(values) if len(values) > 1 else 0
                elif aggregation == AggregationType.SPREAD:
                    agg_fields[field_key] = max(values) - min(values)

            if agg_fields:
                aggregated.append(DataPoint(
                    measurement=window_points[0].measurement,
                    tags=window_points[0].tags,
                    fields=agg_fields,
                    timestamp=window_time,
                ))

        return aggregated


class TelemetryWriter:
    """Convenience class for writing telemetry data."""

    def __init__(self, adapter: TimeSeriesAdapter, twin_id: str):
        """
        Initialize telemetry writer.

        Args:
            adapter: Time series adapter
            twin_id: Digital twin ID
        """
        self.adapter = adapter
        self.twin_id = twin_id

    def write_sensor(
        self,
        sensor_id: str,
        sensor_type: str,
        value: float,
        unit: str,
        quality: str = "good"
    ):
        """Write sensor reading."""
        self.adapter.write(
            measurement="sensor_readings",
            tags={
                "twin_id": self.twin_id,
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
                "unit": unit,
            },
            fields={
                "value": value,
                "quality": quality,
            },
        )

    def write_status(
        self,
        component: str,
        status: str,
        details: Optional[str] = None
    ):
        """Write status update."""
        fields = {"status": status}
        if details:
            fields["details"] = details

        self.adapter.write(
            measurement="status_updates",
            tags={
                "twin_id": self.twin_id,
                "component": component,
            },
            fields=fields,
        )

    def write_metric(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """Write custom metric."""
        base_tags = {"twin_id": self.twin_id}
        if tags:
            base_tags.update(tags)

        self.adapter.write(
            measurement=metric_name,
            tags=base_tags,
            fields={"value": value},
        )

    def write_event(
        self,
        event_type: str,
        severity: str,
        message: str
    ):
        """Write event."""
        self.adapter.write(
            measurement="events",
            tags={
                "twin_id": self.twin_id,
                "event_type": event_type,
                "severity": severity,
            },
            fields={
                "message": message,
            },
        )


# Singleton instance
_time_series_adapter: Optional[TimeSeriesAdapter] = None


def get_time_series_adapter() -> TimeSeriesAdapter:
    """Get or create the time series adapter instance."""
    global _time_series_adapter
    if _time_series_adapter is None:
        _time_series_adapter = TimeSeriesAdapter()
        _time_series_adapter.connect()
    return _time_series_adapter
