"""
Analytics Engine

Core analytics processing engine for manufacturing data.
Supports real-time queries, aggregations, and time-series analysis.

Reference: ISO 22400 (KPIs for Manufacturing Operations)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
import statistics
import json

logger = logging.getLogger(__name__)


class AggregationType(Enum):
    """Aggregation function types."""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    MEDIAN = "median"
    STDDEV = "stddev"
    PERCENTILE = "percentile"
    RATE = "rate"
    DELTA = "delta"


class TimeGranularity(Enum):
    """Time granularity for aggregations."""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


@dataclass
class AnalyticsQuery:
    """Analytics query specification."""
    metrics: List[str]
    dimensions: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    aggregation: AggregationType = AggregationType.SUM
    granularity: Optional[TimeGranularity] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 1000
    order_by: Optional[str] = None
    order_desc: bool = True


@dataclass
class AnalyticsResult:
    """Analytics query result."""
    query: AnalyticsQuery
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self.data,
            "metadata": self.metadata,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp,
            "row_count": len(self.data)
        }


@dataclass
class TimeSeriesPoint:
    """Single point in a time series."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


class AnalyticsEngine:
    """
    Manufacturing Analytics Engine.
    
    Provides real-time analytics processing for:
    - Production metrics (OEE, throughput, cycle time)
    - Quality metrics (defect rates, SPC)
    - Equipment metrics (utilization, MTBF, MTTR)
    - Resource metrics (labor, materials)
    
    Usage:
        >>> engine = AnalyticsEngine()
        >>> query = AnalyticsQuery(
        ...     metrics=["production_count"],
        ...     dimensions=["work_center"],
        ...     aggregation=AggregationType.SUM
        ... )
        >>> result = engine.execute(query)
    """
    
    def __init__(self):
        self._data_sources: Dict[str, Callable] = {}
        self._cache: Dict[str, Any] = {}
        self._aggregators: Dict[AggregationType, Callable] = {
            AggregationType.SUM: sum,
            AggregationType.AVG: statistics.mean,
            AggregationType.MIN: min,
            AggregationType.MAX: max,
            AggregationType.COUNT: len,
            AggregationType.MEDIAN: statistics.median,
            AggregationType.STDDEV: lambda x: statistics.stdev(x) if len(x) > 1 else 0,
        }
        logger.info("AnalyticsEngine initialized")
    
    def register_data_source(
        self,
        name: str,
        fetcher: Callable[[AnalyticsQuery], List[Dict[str, Any]]]
    ) -> None:
        """Register a data source for analytics."""
        self._data_sources[name] = fetcher
        logger.info(f"Data source registered: {name}")
    
    def execute(self, query: AnalyticsQuery) -> AnalyticsResult:
        """Execute an analytics query."""
        start = datetime.utcnow()
        
        try:
            # Fetch raw data
            raw_data = self._fetch_data(query)
            
            # Apply filters
            filtered_data = self._apply_filters(raw_data, query.filters)
            
            # Group by dimensions
            grouped_data = self._group_by_dimensions(filtered_data, query.dimensions)
            
            # Apply aggregation
            aggregated_data = self._aggregate(grouped_data, query.metrics, query.aggregation)
            
            # Apply time granularity if specified
            if query.granularity:
                aggregated_data = self._apply_time_granularity(
                    aggregated_data, query.granularity
                )
            
            # Sort and limit
            result_data = self._sort_and_limit(
                aggregated_data, query.order_by, query.order_desc, query.limit
            )
            
            execution_time = (datetime.utcnow() - start).total_seconds() * 1000
            
            return AnalyticsResult(
                query=query,
                data=result_data,
                metadata={
                    "total_rows": len(result_data),
                    "dimensions": query.dimensions,
                    "aggregation": query.aggregation.value
                },
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            logger.error(f"Analytics query failed: {e}")
            raise
    
    def _fetch_data(self, query: AnalyticsQuery) -> List[Dict[str, Any]]:
        """Fetch data from registered sources."""
        all_data = []
        for source_name, fetcher in self._data_sources.items():
            try:
                data = fetcher(query)
                all_data.extend(data)
            except Exception as e:
                logger.warning(f"Data source {source_name} failed: {e}")
        return all_data
    
    def _apply_filters(
        self,
        data: List[Dict[str, Any]],
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply filters to data."""
        if not filters:
            return data
        
        result = []
        for row in data:
            match = True
            for key, value in filters.items():
                if isinstance(value, list):
                    if row.get(key) not in value:
                        match = False
                        break
                elif isinstance(value, dict):
                    # Range filters: {"gte": 10, "lte": 100}
                    row_val = row.get(key)
                    if "gte" in value and row_val < value["gte"]:
                        match = False
                    if "lte" in value and row_val > value["lte"]:
                        match = False
                    if "gt" in value and row_val <= value["gt"]:
                        match = False
                    if "lt" in value and row_val >= value["lt"]:
                        match = False
                else:
                    if row.get(key) != value:
                        match = False
                        break
            if match:
                result.append(row)
        return result
    
    def _group_by_dimensions(
        self,
        data: List[Dict[str, Any]],
        dimensions: List[str]
    ) -> Dict[tuple, List[Dict[str, Any]]]:
        """Group data by dimensions."""
        if not dimensions:
            return {(): data}
        
        groups: Dict[tuple, List[Dict[str, Any]]] = {}
        for row in data:
            key = tuple(row.get(dim) for dim in dimensions)
            if key not in groups:
                groups[key] = []
            groups[key].append(row)
        return groups
    
    def _aggregate(
        self,
        grouped_data: Dict[tuple, List[Dict[str, Any]]],
        metrics: List[str],
        aggregation: AggregationType
    ) -> List[Dict[str, Any]]:
        """Apply aggregation to grouped data."""
        aggregator = self._aggregators.get(aggregation)
        if not aggregator:
            raise ValueError(f"Unsupported aggregation: {aggregation}")
        
        results = []
        for group_key, rows in grouped_data.items():
            result_row = {}
            
            # Add dimension values
            if group_key:
                for i, dim_val in enumerate(group_key):
                    result_row[f"dim_{i}"] = dim_val
            
            # Aggregate metrics
            for metric in metrics:
                values = [r.get(metric, 0) for r in rows if r.get(metric) is not None]
                if values:
                    if aggregation == AggregationType.COUNT:
                        result_row[metric] = len(values)
                    else:
                        result_row[metric] = aggregator(values)
                else:
                    result_row[metric] = 0
            
            results.append(result_row)
        
        return results
    
    def _apply_time_granularity(
        self,
        data: List[Dict[str, Any]],
        granularity: TimeGranularity
    ) -> List[Dict[str, Any]]:
        """Apply time bucketing."""
        # Implementation would bucket by time periods
        return data
    
    def _sort_and_limit(
        self,
        data: List[Dict[str, Any]],
        order_by: Optional[str],
        order_desc: bool,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Sort and limit results."""
        if order_by:
            data.sort(key=lambda x: x.get(order_by, 0), reverse=order_desc)
        return data[:limit]
    
    def calculate_oee(
        self,
        availability: float,
        performance: float,
        quality: float
    ) -> Dict[str, float]:
        """
        Calculate Overall Equipment Effectiveness.
        
        OEE = Availability × Performance × Quality
        
        Reference: ISO 22400-2
        """
        oee = availability * performance * quality
        return {
            "availability": round(availability, 4),
            "performance": round(performance, 4),
            "quality": round(quality, 4),
            "oee": round(oee, 4),
            "oee_percent": round(oee * 100, 2)
        }
    
    def calculate_throughput(
        self,
        units_produced: int,
        time_period_hours: float
    ) -> Dict[str, float]:
        """Calculate production throughput."""
        if time_period_hours <= 0:
            return {"units_per_hour": 0, "units_per_day": 0}
        
        uph = units_produced / time_period_hours
        return {
            "units_produced": units_produced,
            "time_period_hours": time_period_hours,
            "units_per_hour": round(uph, 2),
            "units_per_day": round(uph * 24, 2),
            "units_per_shift": round(uph * 8, 2)
        }
    
    def calculate_cycle_time(
        self,
        processing_times: List[float]
    ) -> Dict[str, float]:
        """Calculate cycle time statistics."""
        if not processing_times:
            return {}
        
        return {
            "avg_cycle_time": round(statistics.mean(processing_times), 3),
            "min_cycle_time": round(min(processing_times), 3),
            "max_cycle_time": round(max(processing_times), 3),
            "median_cycle_time": round(statistics.median(processing_times), 3),
            "std_dev": round(statistics.stdev(processing_times), 3) if len(processing_times) > 1 else 0,
            "sample_count": len(processing_times)
        }
