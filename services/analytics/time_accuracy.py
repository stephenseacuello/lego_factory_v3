"""
Time Accuracy Tracking Service
==============================
Tracks estimated vs actual job times for continuous improvement.

Features:
- Per-job time accuracy recording
- Aggregate statistics by operation type
- Trend analysis over time
- Correction factor calculation
- Event publishing for feedback loop

Usage:
    from services.analytics import get_time_accuracy_tracker

    tracker = get_time_accuracy_tracker()

    # Record job completion
    tracker.record_completion(
        job_id="job-001",
        estimated_sec=300,
        actual_sec=285,
        metadata={"operation": "roughing", "material": "aluminum"}
    )

    # Get accuracy statistics
    stats = tracker.get_statistics()
    correction = tracker.get_correction_factor("roughing")
"""

import logging
import time
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import statistics

from config import get_config
from services.integration.event_dispatcher import get_event_dispatcher, EventType

logger = logging.getLogger(__name__)
config = get_config()


@dataclass
class TimeRecord:
    """Record of a single job's time accuracy."""
    job_id: str
    estimated_sec: float
    actual_sec: float
    error_sec: float
    error_percent: float
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "estimated_sec": round(self.estimated_sec, 2),
            "actual_sec": round(self.actual_sec, 2),
            "error_sec": round(self.error_sec, 2),
            "error_percent": round(self.error_percent, 2),
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class AccuracyStatistics:
    """Aggregate statistics for time accuracy."""
    sample_count: int = 0
    mean_error_sec: float = 0.0
    mean_error_percent: float = 0.0
    std_dev_sec: float = 0.0
    std_dev_percent: float = 0.0
    max_overestimate_percent: float = 0.0
    max_underestimate_percent: float = 0.0
    correction_factor: float = 1.0
    on_time_rate: float = 0.0  # Within ±10% of estimate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "mean_error_sec": round(self.mean_error_sec, 2),
            "mean_error_percent": round(self.mean_error_percent, 2),
            "std_dev_sec": round(self.std_dev_sec, 2),
            "std_dev_percent": round(self.std_dev_percent, 2),
            "max_overestimate_percent": round(self.max_overestimate_percent, 2),
            "max_underestimate_percent": round(self.max_underestimate_percent, 2),
            "correction_factor": round(self.correction_factor, 4),
            "on_time_rate": round(self.on_time_rate * 100, 1),
        }


class TimeAccuracyTracker:
    """
    Tracks and analyzes time estimation accuracy.

    Maintains history of estimated vs actual times for jobs,
    calculates correction factors, and provides statistical analysis.
    """

    def __init__(self, max_history: int = 10000):
        """
        Initialize time accuracy tracker.

        Args:
            max_history: Maximum number of records to keep
        """
        self._records: List[TimeRecord] = []
        self._max_history = max_history

        # Group records by category
        self._by_operation: Dict[str, List[TimeRecord]] = defaultdict(list)
        self._by_material: Dict[str, List[TimeRecord]] = defaultdict(list)
        self._by_tool: Dict[str, List[TimeRecord]] = defaultdict(list)

        # Event dispatcher
        self._dispatcher = get_event_dispatcher()

        logger.info("TimeAccuracyTracker initialized")

    def record_completion(
        self,
        job_id: str,
        estimated_sec: float,
        actual_sec: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TimeRecord:
        """
        Record a job completion with time data.

        Args:
            job_id: Job identifier
            estimated_sec: Estimated time in seconds
            actual_sec: Actual time in seconds
            metadata: Additional metadata (operation type, material, etc.)

        Returns:
            TimeRecord with calculated accuracy metrics
        """
        metadata = metadata or {}

        # Calculate error
        error_sec = actual_sec - estimated_sec
        error_percent = (error_sec / estimated_sec * 100) if estimated_sec > 0 else 0

        record = TimeRecord(
            job_id=job_id,
            estimated_sec=estimated_sec,
            actual_sec=actual_sec,
            error_sec=error_sec,
            error_percent=error_percent,
            timestamp=time.time(),
            metadata=metadata,
        )

        # Store record
        self._records.append(record)

        # Trim history if needed
        if len(self._records) > self._max_history:
            self._records = self._records[-self._max_history:]

        # Index by category
        if "operation" in metadata:
            self._by_operation[metadata["operation"]].append(record)
        if "material" in metadata:
            self._by_material[metadata["material"]].append(record)
        if "tool" in metadata:
            self._by_tool[str(metadata["tool"])].append(record)

        # Publish event
        self._dispatcher.publish(
            EventType.TIME_ACCURACY_RECORDED,
            record.to_dict()
        )

        logger.info(
            f"Time accuracy recorded: {job_id} - "
            f"Est: {estimated_sec:.0f}s, Act: {actual_sec:.0f}s, "
            f"Error: {error_percent:+.1f}%"
        )

        return record

    def get_statistics(
        self,
        time_window_hours: Optional[float] = None,
    ) -> AccuracyStatistics:
        """
        Calculate aggregate statistics.

        Args:
            time_window_hours: Optional time window in hours (None = all data)

        Returns:
            AccuracyStatistics with aggregate metrics
        """
        records = self._filter_by_time(self._records, time_window_hours)

        if not records:
            return AccuracyStatistics()

        return self._calculate_statistics(records)

    def get_statistics_by_operation(
        self,
        operation: str,
        time_window_hours: Optional[float] = None,
    ) -> AccuracyStatistics:
        """Get statistics for a specific operation type."""
        records = self._filter_by_time(
            self._by_operation.get(operation, []),
            time_window_hours
        )
        return self._calculate_statistics(records)

    def get_statistics_by_material(
        self,
        material: str,
        time_window_hours: Optional[float] = None,
    ) -> AccuracyStatistics:
        """Get statistics for a specific material type."""
        records = self._filter_by_time(
            self._by_material.get(material, []),
            time_window_hours
        )
        return self._calculate_statistics(records)

    def get_correction_factor(
        self,
        operation: Optional[str] = None,
        material: Optional[str] = None,
        time_window_hours: float = 168,  # 1 week
    ) -> float:
        """
        Calculate correction factor for future estimates.

        A correction factor > 1.0 means estimates are typically low.
        A correction factor < 1.0 means estimates are typically high.

        Args:
            operation: Filter by operation type
            material: Filter by material type
            time_window_hours: Time window for calculation

        Returns:
            Correction factor (multiply estimates by this value)
        """
        if operation:
            records = self._by_operation.get(operation, [])
        elif material:
            records = self._by_material.get(material, [])
        else:
            records = self._records

        records = self._filter_by_time(records, time_window_hours)

        if len(records) < 5:  # Need minimum samples
            return 1.0

        # Calculate ratio of actual to estimated
        ratios = [r.actual_sec / r.estimated_sec for r in records if r.estimated_sec > 0]

        if not ratios:
            return 1.0

        # Use median for robustness against outliers
        return statistics.median(ratios)

    def get_trend(
        self,
        days: int = 7,
        bucket_hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Get accuracy trend over time.

        Args:
            days: Number of days to analyze
            bucket_hours: Hours per bucket

        Returns:
            List of trend data points
        """
        cutoff = time.time() - (days * 24 * 3600)
        records = [r for r in self._records if r.timestamp >= cutoff]

        if not records:
            return []

        # Group by bucket
        bucket_size = bucket_hours * 3600
        buckets: Dict[int, List[TimeRecord]] = defaultdict(list)

        for record in records:
            bucket_idx = int(record.timestamp // bucket_size)
            buckets[bucket_idx].append(record)

        # Calculate stats for each bucket
        trend = []
        for bucket_idx in sorted(buckets.keys()):
            bucket_records = buckets[bucket_idx]
            stats = self._calculate_statistics(bucket_records)

            bucket_time = bucket_idx * bucket_size
            trend.append({
                "timestamp": bucket_time,
                "datetime": datetime.fromtimestamp(bucket_time).isoformat(),
                "sample_count": stats.sample_count,
                "mean_error_percent": stats.mean_error_percent,
                "on_time_rate": stats.on_time_rate,
            })

        return trend

    def get_recent_records(
        self,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get most recent time records."""
        recent = self._records[-limit:] if self._records else []
        return [r.to_dict() for r in reversed(recent)]

    def get_outliers(
        self,
        threshold_percent: float = 30.0,
        time_window_hours: Optional[float] = 24,
    ) -> List[Dict[str, Any]]:
        """
        Get jobs with significant estimation errors.

        Args:
            threshold_percent: Error threshold for outliers
            time_window_hours: Time window to search

        Returns:
            List of outlier records
        """
        records = self._filter_by_time(self._records, time_window_hours)

        outliers = [
            r for r in records
            if abs(r.error_percent) >= threshold_percent
        ]

        return [r.to_dict() for r in sorted(
            outliers,
            key=lambda r: abs(r.error_percent),
            reverse=True
        )]

    def _filter_by_time(
        self,
        records: List[TimeRecord],
        time_window_hours: Optional[float],
    ) -> List[TimeRecord]:
        """Filter records by time window."""
        if time_window_hours is None:
            return records

        cutoff = time.time() - (time_window_hours * 3600)
        return [r for r in records if r.timestamp >= cutoff]

    def _calculate_statistics(
        self,
        records: List[TimeRecord],
    ) -> AccuracyStatistics:
        """Calculate statistics for a set of records."""
        if not records:
            return AccuracyStatistics()

        errors_sec = [r.error_sec for r in records]
        errors_percent = [r.error_percent for r in records]

        # Calculate on-time rate (within ±10%)
        on_time = sum(1 for r in records if abs(r.error_percent) <= 10)
        on_time_rate = on_time / len(records)

        # Calculate correction factor
        ratios = [r.actual_sec / r.estimated_sec for r in records if r.estimated_sec > 0]
        correction_factor = statistics.median(ratios) if ratios else 1.0

        return AccuracyStatistics(
            sample_count=len(records),
            mean_error_sec=statistics.mean(errors_sec),
            mean_error_percent=statistics.mean(errors_percent),
            std_dev_sec=statistics.stdev(errors_sec) if len(errors_sec) > 1 else 0,
            std_dev_percent=statistics.stdev(errors_percent) if len(errors_percent) > 1 else 0,
            max_overestimate_percent=max(0, -min(errors_percent)),  # Negative error = overestimate
            max_underestimate_percent=max(0, max(errors_percent)),  # Positive error = underestimate
            correction_factor=correction_factor,
            on_time_rate=on_time_rate,
        )

    def export_data(self) -> Dict[str, Any]:
        """Export all data for backup/analysis."""
        return {
            "records": [r.to_dict() for r in self._records],
            "statistics": self.get_statistics().to_dict(),
            "by_operation": {
                op: len(records)
                for op, records in self._by_operation.items()
            },
            "by_material": {
                mat: len(records)
                for mat, records in self._by_material.items()
            },
            "exported_at": datetime.now().isoformat(),
        }


# Global tracker instance
_time_accuracy_tracker: Optional[TimeAccuracyTracker] = None


def get_time_accuracy_tracker() -> TimeAccuracyTracker:
    """Get global time accuracy tracker instance."""
    global _time_accuracy_tracker
    if _time_accuracy_tracker is None:
        _time_accuracy_tracker = TimeAccuracyTracker()
    return _time_accuracy_tracker
