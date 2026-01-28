"""
LEGO Factory v3 - Data Alignment Service
=========================================
Aligns timestamps across multiple data sources for correlation analysis.

Features:
- Time series alignment with multiple interpolation methods
- Multi-source data alignment (historian, sensors, machine events)
- Correlation support with lag analysis
- Data quality assessment and clock drift detection
- Export functions for ML training and analytics

Usage:
    from services.analytics import get_data_alignment_service

    service = get_data_alignment_service()

    # Align multiple time series
    aligned = service.align_time_series([series1, series2], method='interpolate')

    # Prepare for correlation analysis
    corr_matrix = service.prepare_correlation_matrix(aligned)

    # Find leading indicators
    indicators = service.find_leading_indicators(target, candidates, max_lag=60)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple, Union, Literal
from dataclasses import dataclass, field
from enum import Enum
import io

import pandas as pd
import numpy as np
from scipy import interpolate as scipy_interpolate
from scipy import signal
from scipy import stats

from config.logging_config import get_structured_logger, log_operation_start, log_operation_end

logger = get_structured_logger(__name__)


class InterpolationMethod(str, Enum):
    """Supported interpolation methods for gap filling."""
    LINEAR = 'linear'
    PREVIOUS = 'previous'
    NEXT = 'next'
    SPLINE = 'spline'
    NEAREST = 'nearest'
    ZERO = 'zero'


class AlignmentMethod(str, Enum):
    """Methods for aligning multiple time series."""
    INTERPOLATE = 'interpolate'
    FORWARD_FILL = 'ffill'
    BACKWARD_FILL = 'bfill'
    NEAREST = 'nearest'


@dataclass
class AlignmentQualityReport:
    """Report on data alignment quality."""
    total_points: int = 0
    missing_points: int = 0
    filled_points: int = 0
    outlier_count: int = 0
    gap_count: int = 0
    max_gap_duration_sec: float = 0.0
    avg_gap_duration_sec: float = 0.0
    data_coverage_percent: float = 0.0
    quality_score: float = 0.0
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_points": self.total_points,
            "missing_points": self.missing_points,
            "filled_points": self.filled_points,
            "outlier_count": self.outlier_count,
            "gap_count": self.gap_count,
            "max_gap_duration_sec": round(self.max_gap_duration_sec, 2),
            "avg_gap_duration_sec": round(self.avg_gap_duration_sec, 2),
            "data_coverage_percent": round(self.data_coverage_percent, 2),
            "quality_score": round(self.quality_score, 4),
            "issues": self.issues,
        }


@dataclass
class ClockDriftReport:
    """Report on clock drift between data sources."""
    source_a: str
    source_b: str
    estimated_drift_sec: float
    confidence: float
    sample_count: int
    method: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "source_a": self.source_a,
            "source_b": self.source_b,
            "estimated_drift_sec": round(self.estimated_drift_sec, 4),
            "confidence": round(self.confidence, 4),
            "sample_count": self.sample_count,
            "method": self.method,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class LagCorrelationResult:
    """Result of lag correlation analysis."""
    optimal_lag: int
    max_correlation: float
    lag_range: Tuple[int, int]
    correlations: List[Tuple[int, float]]
    significance: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "optimal_lag": self.optimal_lag,
            "max_correlation": round(self.max_correlation, 4),
            "lag_range": self.lag_range,
            "top_correlations": [
                {"lag": lag, "correlation": round(corr, 4)}
                for lag, corr in sorted(self.correlations, key=lambda x: abs(x[1]), reverse=True)[:10]
            ],
            "significance": round(self.significance, 4),
        }


@dataclass
class LeadingIndicator:
    """A leading indicator for a target series."""
    series_name: str
    optimal_lag: int
    correlation: float
    significance: float
    lead_time_sec: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "series_name": self.series_name,
            "optimal_lag": self.optimal_lag,
            "correlation": round(self.correlation, 4),
            "significance": round(self.significance, 4),
            "lead_time_sec": round(self.lead_time_sec, 2),
        }


class DataAlignmentService:
    """
    Service for aligning timestamps across multiple data sources.

    Provides functionality for:
    - Aligning multiple time series to common timestamps
    - Resampling data to target frequencies
    - Filling gaps with various interpolation methods
    - Correlation analysis with lag detection
    - Data quality assessment
    - Clock drift detection and correction
    - Export for ML training and analytics
    """

    def __init__(
        self,
        default_interpolation: InterpolationMethod = InterpolationMethod.LINEAR,
        outlier_threshold: float = 3.0,
        max_gap_fill_sec: float = 300.0,
    ):
        """
        Initialize the Data Alignment Service.

        Args:
            default_interpolation: Default interpolation method for gap filling
            outlier_threshold: Number of standard deviations for outlier detection
            max_gap_fill_sec: Maximum gap duration (seconds) to fill via interpolation
        """
        self.default_interpolation = default_interpolation
        self.outlier_threshold = outlier_threshold
        self.max_gap_fill_sec = max_gap_fill_sec
        self._historian_reader = None

        logger.info(
            "DataAlignmentService initialized",
            extra={
                'event': 'service_initialized',
                'default_interpolation': default_interpolation.value,
                'outlier_threshold': outlier_threshold,
                'max_gap_fill_sec': max_gap_fill_sec,
            }
        )

    # =========================================================================
    # Time Series Alignment Methods
    # =========================================================================

    def align_time_series(
        self,
        series_list: List[pd.DataFrame],
        method: Union[str, AlignmentMethod] = AlignmentMethod.INTERPOLATE,
        target_timestamps: Optional[pd.DatetimeIndex] = None,
        tolerance: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Align multiple time series to common timestamps.

        Args:
            series_list: List of DataFrames with datetime index and value columns
            method: Alignment method ('interpolate', 'ffill', 'bfill', 'nearest')
            target_timestamps: Optional target timestamps to align to
            tolerance: Optional tolerance for merge_asof (e.g., '1s', '100ms')

        Returns:
            DataFrame with aligned time series, all columns sharing common index

        Raises:
            ValueError: If series_list is empty or series have incompatible formats
        """
        start_time = log_operation_start(
            logger, "align_time_series",
            series_count=len(series_list), method=str(method)
        )

        if not series_list:
            raise ValueError("series_list cannot be empty")

        method = AlignmentMethod(method) if isinstance(method, str) else method

        try:
            # Ensure all series have datetime index
            processed_series = []
            for i, df in enumerate(series_list):
                if not isinstance(df.index, pd.DatetimeIndex):
                    if 'time' in df.columns:
                        df = df.set_index('time')
                    elif 'timestamp' in df.columns:
                        df = df.set_index('timestamp')
                    else:
                        raise ValueError(
                            f"Series {i} must have datetime index or 'time'/'timestamp' column"
                        )
                processed_series.append(df.sort_index())

            # Determine target timestamps
            if target_timestamps is None:
                # Find union of all timestamps
                all_timestamps = pd.DatetimeIndex([])
                for df in processed_series:
                    all_timestamps = all_timestamps.union(df.index)
                target_timestamps = all_timestamps.sort_values()

            # Align each series to target timestamps
            aligned_frames = []
            for i, df in enumerate(processed_series):
                aligned = self._align_single_series(
                    df, target_timestamps, method, tolerance
                )
                # Prefix column names if needed to avoid conflicts
                if len(processed_series) > 1:
                    aligned.columns = [f"series_{i}_{col}" if not col.startswith(f"series_{i}_") else col
                                       for col in aligned.columns]
                aligned_frames.append(aligned)

            # Combine all aligned series
            result = pd.concat(aligned_frames, axis=1)
            result = result.loc[target_timestamps]

            log_operation_end(
                logger, "align_time_series", start_time,
                result_shape=result.shape, method=method.value
            )

            return result

        except Exception as e:
            log_operation_end(logger, "align_time_series", start_time, success=False, error=str(e))
            raise

    def _align_single_series(
        self,
        series: pd.DataFrame,
        target_timestamps: pd.DatetimeIndex,
        method: AlignmentMethod,
        tolerance: Optional[str],
    ) -> pd.DataFrame:
        """Align a single series to target timestamps."""
        if method == AlignmentMethod.INTERPOLATE:
            # Reindex and interpolate
            combined_index = series.index.union(target_timestamps)
            reindexed = series.reindex(combined_index)
            interpolated = reindexed.interpolate(method='time')
            return interpolated.loc[target_timestamps]

        elif method == AlignmentMethod.FORWARD_FILL:
            reindexed = series.reindex(target_timestamps, method='ffill')
            return reindexed

        elif method == AlignmentMethod.BACKWARD_FILL:
            reindexed = series.reindex(target_timestamps, method='bfill')
            return reindexed

        elif method == AlignmentMethod.NEAREST:
            reindexed = series.reindex(target_timestamps, method='nearest')
            return reindexed

        else:
            raise ValueError(f"Unknown alignment method: {method}")

    def resample_to_frequency(
        self,
        series: pd.DataFrame,
        target_freq: str,
        agg_func: str = 'mean',
        fill_method: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Resample time series data to a target frequency.

        Args:
            series: DataFrame with datetime index
            target_freq: Target frequency string (e.g., '1s', '1min', '1h', '100ms')
            agg_func: Aggregation function ('mean', 'median', 'max', 'min', 'sum', 'first', 'last')
            fill_method: Optional method to fill NaN after resampling ('ffill', 'bfill', 'interpolate')

        Returns:
            Resampled DataFrame at target frequency
        """
        start_time = log_operation_start(
            logger, "resample_to_frequency",
            target_freq=target_freq, agg_func=agg_func
        )

        try:
            # Ensure datetime index
            if not isinstance(series.index, pd.DatetimeIndex):
                if 'time' in series.columns:
                    series = series.set_index('time')
                elif 'timestamp' in series.columns:
                    series = series.set_index('timestamp')

            # Map frequency aliases
            freq_map = {
                '1s': '1s', '1sec': '1s', '1second': '1s',
                '1m': '1min', '1min': '1min', '1minute': '1min',
                '1h': '1h', '1hr': '1h', '1hour': '1h',
                '100ms': '100ms', '500ms': '500ms',
            }
            freq = freq_map.get(target_freq.lower(), target_freq)

            # Resample with aggregation
            resampler = series.resample(freq)

            agg_map = {
                'mean': resampler.mean,
                'median': resampler.median,
                'max': resampler.max,
                'min': resampler.min,
                'sum': resampler.sum,
                'first': resampler.first,
                'last': resampler.last,
                'std': resampler.std,
                'count': resampler.count,
            }

            if agg_func not in agg_map:
                raise ValueError(f"Unknown aggregation function: {agg_func}")

            result = agg_map[agg_func]()

            # Fill NaN values if requested
            if fill_method:
                if fill_method == 'interpolate':
                    result = result.interpolate(method='time')
                elif fill_method == 'ffill':
                    result = result.ffill()
                elif fill_method == 'bfill':
                    result = result.bfill()

            log_operation_end(
                logger, "resample_to_frequency", start_time,
                input_shape=series.shape, output_shape=result.shape
            )

            return result

        except Exception as e:
            log_operation_end(logger, "resample_to_frequency", start_time, success=False, error=str(e))
            raise

    def fill_gaps(
        self,
        series: pd.DataFrame,
        method: Union[str, InterpolationMethod] = InterpolationMethod.LINEAR,
        max_gap: Optional[int] = None,
        limit_direction: str = 'both',
    ) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """
        Fill missing values in time series using various interpolation methods.

        Args:
            series: DataFrame with datetime index and potentially missing values
            method: Interpolation method ('linear', 'previous', 'next', 'spline', 'nearest', 'zero')
            max_gap: Maximum number of consecutive NaNs to fill (None = unlimited)
            limit_direction: Direction for limit ('forward', 'backward', 'both')

        Returns:
            Tuple of (filled DataFrame, dict with fill statistics)
        """
        start_time = log_operation_start(logger, "fill_gaps", method=str(method))

        method = InterpolationMethod(method) if isinstance(method, str) else method

        try:
            result = series.copy()
            stats = {
                'original_nan_count': int(series.isna().sum().sum()),
                'filled_count': 0,
                'remaining_nan_count': 0,
            }

            if stats['original_nan_count'] == 0:
                log_operation_end(logger, "fill_gaps", start_time, no_gaps_found=True)
                return result, stats

            # Apply interpolation based on method
            if method == InterpolationMethod.LINEAR:
                result = result.interpolate(
                    method='time', limit=max_gap, limit_direction=limit_direction
                )
            elif method == InterpolationMethod.PREVIOUS:
                result = result.ffill(limit=max_gap)
            elif method == InterpolationMethod.NEXT:
                result = result.bfill(limit=max_gap)
            elif method == InterpolationMethod.SPLINE:
                # Spline interpolation for smoother curves
                for col in result.columns:
                    if result[col].isna().any():
                        valid_mask = ~result[col].isna()
                        if valid_mask.sum() >= 4:  # Need at least 4 points for cubic spline
                            valid_idx = result.index[valid_mask]
                            valid_vals = result.loc[valid_mask, col]

                            # Convert datetime to numeric for spline
                            x_numeric = (valid_idx - valid_idx[0]).total_seconds()
                            all_x = (result.index - valid_idx[0]).total_seconds()

                            try:
                                spline = scipy_interpolate.UnivariateSpline(
                                    x_numeric, valid_vals, s=0, k=3
                                )
                                result[col] = spline(all_x)
                            except Exception:
                                # Fall back to linear if spline fails
                                result[col] = result[col].interpolate(method='time')

            elif method == InterpolationMethod.NEAREST:
                result = result.interpolate(method='nearest', limit=max_gap)
            elif method == InterpolationMethod.ZERO:
                result = result.fillna(0)

            stats['remaining_nan_count'] = int(result.isna().sum().sum())
            stats['filled_count'] = stats['original_nan_count'] - stats['remaining_nan_count']

            log_operation_end(
                logger, "fill_gaps", start_time,
                filled_count=stats['filled_count'], method=method.value
            )

            return result, stats

        except Exception as e:
            log_operation_end(logger, "fill_gaps", start_time, success=False, error=str(e))
            raise

    # =========================================================================
    # Multi-Source Alignment Methods
    # =========================================================================

    def align_historian_data(
        self,
        tag_ids: List[str],
        start_time: datetime,
        end_time: datetime,
        resolution: str = '1s',
        interpolation: str = 'linear',
    ) -> pd.DataFrame:
        """
        Align data from historian tags to common timestamps.

        Args:
            tag_ids: List of historian tag IDs to align
            start_time: Start of time range
            end_time: End of time range
            resolution: Target time resolution (e.g., '1s', '100ms', '1min')
            interpolation: Interpolation method for alignment

        Returns:
            DataFrame with aligned historian data, one column per tag
        """
        start = log_operation_start(
            logger, "align_historian_data",
            tag_count=len(tag_ids), resolution=resolution
        )

        try:
            # Lazy import to avoid circular dependencies
            from services.scada.historian.historian_service import HistorianReader

            reader = HistorianReader()

            # Get raw data for all tags
            raw_data = reader.get_raw(tag_ids, start_time, end_time)

            if raw_data.empty:
                logger.warning("No historian data found for specified tags and time range")
                return pd.DataFrame()

            # Pivot to wide format (one column per tag)
            pivoted = raw_data.pivot_table(
                index='time', columns='tag_id', values='value', aggfunc='mean'
            )

            # Generate target timestamps at specified resolution
            target_index = pd.date_range(start=start_time, end=end_time, freq=resolution)

            # Align to target timestamps
            aligned = self._align_single_series(
                pivoted, target_index,
                AlignmentMethod(interpolation) if interpolation in ['ffill', 'bfill', 'nearest']
                else AlignmentMethod.INTERPOLATE,
                None
            )

            # Flatten column names
            aligned.columns = [str(col) for col in aligned.columns]

            log_operation_end(
                logger, "align_historian_data", start,
                result_shape=aligned.shape, tag_count=len(tag_ids)
            )

            return aligned

        except Exception as e:
            log_operation_end(logger, "align_historian_data", start, success=False, error=str(e))
            raise

    def align_sensor_data(
        self,
        sensor_ids: List[str],
        timestamps: pd.DatetimeIndex,
        sensor_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> pd.DataFrame:
        """
        Align real-time sensor data to specified timestamps.

        Args:
            sensor_ids: List of sensor IDs to align
            timestamps: Target timestamps to align to
            sensor_data: Optional dict mapping sensor_id to DataFrame with sensor readings
                         If not provided, will attempt to fetch from sensor acquisition service

        Returns:
            DataFrame with aligned sensor data
        """
        start = log_operation_start(
            logger, "align_sensor_data",
            sensor_count=len(sensor_ids), timestamp_count=len(timestamps)
        )

        try:
            if sensor_data is None:
                # Attempt to fetch sensor data from acquisition service
                try:
                    from services.scada.sensor_acquisition.sensor_acquisition_service import (
                        get_sensor_buffer
                    )
                    sensor_data = {}
                    for sensor_id in sensor_ids:
                        buffer = get_sensor_buffer(sensor_id)
                        if buffer is not None:
                            sensor_data[sensor_id] = buffer
                except ImportError:
                    raise ValueError(
                        "sensor_data must be provided if sensor_acquisition_service is not available"
                    )

            # Process each sensor's data
            aligned_frames = []
            for sensor_id in sensor_ids:
                if sensor_id not in sensor_data:
                    logger.warning(f"No data found for sensor: {sensor_id}")
                    # Create empty series
                    empty_df = pd.DataFrame(
                        {sensor_id: np.nan}, index=timestamps
                    )
                    aligned_frames.append(empty_df)
                    continue

                df = sensor_data[sensor_id]
                if not isinstance(df.index, pd.DatetimeIndex):
                    if 'time' in df.columns:
                        df = df.set_index('time')
                    elif 'timestamp' in df.columns:
                        df = df.set_index('timestamp')

                # Align to target timestamps
                aligned = self._align_single_series(
                    df, timestamps, AlignmentMethod.INTERPOLATE, None
                )
                # Rename columns to include sensor_id
                aligned.columns = [f"{sensor_id}_{col}" for col in aligned.columns]
                aligned_frames.append(aligned)

            result = pd.concat(aligned_frames, axis=1)

            log_operation_end(
                logger, "align_sensor_data", start,
                result_shape=result.shape
            )

            return result

        except Exception as e:
            log_operation_end(logger, "align_sensor_data", start, success=False, error=str(e))
            raise

    def align_machine_events(
        self,
        machine_id: str,
        event_types: List[str],
        time_range: Tuple[datetime, datetime],
        sensor_data: Optional[pd.DataFrame] = None,
        resolution: str = '1s',
    ) -> pd.DataFrame:
        """
        Align machine events with sensor data for correlation analysis.

        Args:
            machine_id: Machine identifier
            event_types: List of event types to include (e.g., ['alarm', 'state_change', 'fault'])
            time_range: Tuple of (start_time, end_time)
            sensor_data: Optional DataFrame with sensor data to align events with
            resolution: Target time resolution

        Returns:
            DataFrame with event indicators and aligned sensor data
        """
        start = log_operation_start(
            logger, "align_machine_events",
            machine_id=machine_id, event_types=event_types
        )

        try:
            start_time, end_time = time_range

            # Generate target timestamps
            target_index = pd.date_range(start=start_time, end=end_time, freq=resolution)

            # Try to fetch machine events
            events_df = pd.DataFrame(index=target_index)

            try:
                from services.scada.alarm_management.alarm_management_service import (
                    get_alarm_history
                )

                if 'alarm' in event_types or 'fault' in event_types:
                    alarms = get_alarm_history(machine_id, start_time, end_time)
                    if alarms:
                        # Create alarm indicator column
                        alarm_times = [a['timestamp'] for a in alarms if 'timestamp' in a]
                        events_df['alarm_active'] = 0
                        for alarm_time in alarm_times:
                            if isinstance(alarm_time, str):
                                alarm_time = pd.to_datetime(alarm_time)
                            nearest_idx = target_index.get_indexer([alarm_time], method='nearest')[0]
                            if 0 <= nearest_idx < len(target_index):
                                events_df.iloc[nearest_idx, events_df.columns.get_loc('alarm_active')] = 1

            except ImportError:
                logger.debug("Alarm management service not available")

            try:
                from services.scada.machine_control.machine_control_service import (
                    get_machine_state_history
                )

                if 'state_change' in event_types:
                    states = get_machine_state_history(machine_id, start_time, end_time)
                    if states:
                        # Create state indicator columns
                        for state in set(s.get('state') for s in states if 'state' in s):
                            events_df[f'state_{state}'] = 0

                        for state_record in states:
                            state_time = state_record.get('timestamp')
                            state_value = state_record.get('state')
                            if state_time and state_value:
                                if isinstance(state_time, str):
                                    state_time = pd.to_datetime(state_time)
                                nearest_idx = target_index.get_indexer([state_time], method='nearest')[0]
                                if 0 <= nearest_idx < len(target_index):
                                    col_name = f'state_{state_value}'
                                    if col_name in events_df.columns:
                                        events_df.iloc[nearest_idx, events_df.columns.get_loc(col_name)] = 1

            except ImportError:
                logger.debug("Machine control service not available")

            # Merge with sensor data if provided
            if sensor_data is not None:
                if not isinstance(sensor_data.index, pd.DatetimeIndex):
                    if 'time' in sensor_data.columns:
                        sensor_data = sensor_data.set_index('time')
                    elif 'timestamp' in sensor_data.columns:
                        sensor_data = sensor_data.set_index('timestamp')

                # Align sensor data to target timestamps
                aligned_sensors = self._align_single_series(
                    sensor_data, target_index, AlignmentMethod.INTERPOLATE, None
                )
                events_df = pd.concat([events_df, aligned_sensors], axis=1)

            log_operation_end(
                logger, "align_machine_events", start,
                result_shape=events_df.shape, event_columns=list(events_df.columns)
            )

            return events_df

        except Exception as e:
            log_operation_end(logger, "align_machine_events", start, success=False, error=str(e))
            raise

    # =========================================================================
    # Correlation Support Methods
    # =========================================================================

    def prepare_correlation_matrix(
        self,
        aligned_data: pd.DataFrame,
        method: str = 'pearson',
        min_periods: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Prepare aligned data for correlation analysis.

        Args:
            aligned_data: DataFrame with aligned time series
            method: Correlation method ('pearson', 'kendall', 'spearman')
            min_periods: Minimum number of observations required for valid correlation

        Returns:
            Correlation matrix as DataFrame
        """
        start = log_operation_start(logger, "prepare_correlation_matrix", method=method)

        try:
            # Remove columns with all NaN or constant values
            valid_columns = []
            for col in aligned_data.columns:
                if aligned_data[col].notna().sum() > 1:
                    if aligned_data[col].std() > 0:
                        valid_columns.append(col)

            filtered_data = aligned_data[valid_columns]

            if filtered_data.empty:
                logger.warning("No valid columns for correlation analysis")
                return pd.DataFrame()

            # Calculate correlation matrix
            corr_matrix = filtered_data.corr(method=method, min_periods=min_periods)

            log_operation_end(
                logger, "prepare_correlation_matrix", start,
                matrix_shape=corr_matrix.shape, method=method
            )

            return corr_matrix

        except Exception as e:
            log_operation_end(logger, "prepare_correlation_matrix", start, success=False, error=str(e))
            raise

    def calculate_lag_correlation(
        self,
        series1: pd.Series,
        series2: pd.Series,
        max_lag: int,
        normalize: bool = True,
    ) -> LagCorrelationResult:
        """
        Find optimal lag between two time series for maximum correlation.

        Args:
            series1: First time series
            series2: Second time series (will be shifted)
            max_lag: Maximum lag to consider (positive and negative)
            normalize: Whether to normalize correlation values

        Returns:
            LagCorrelationResult with optimal lag and correlation values
        """
        start = log_operation_start(logger, "calculate_lag_correlation", max_lag=max_lag)

        try:
            # Ensure series are 1D
            if isinstance(series1, pd.DataFrame):
                series1 = series1.iloc[:, 0]
            if isinstance(series2, pd.DataFrame):
                series2 = series2.iloc[:, 0]

            # Drop NaN values
            valid_mask = ~(series1.isna() | series2.isna())
            s1 = series1[valid_mask].values
            s2 = series2[valid_mask].values

            if len(s1) < max_lag * 2:
                raise ValueError(
                    f"Series length ({len(s1)}) must be at least 2x max_lag ({max_lag * 2})"
                )

            # Normalize if requested
            if normalize:
                s1 = (s1 - np.mean(s1)) / (np.std(s1) + 1e-10)
                s2 = (s2 - np.mean(s2)) / (np.std(s2) + 1e-10)

            # Calculate cross-correlation
            correlations = []
            for lag in range(-max_lag, max_lag + 1):
                if lag < 0:
                    corr = np.corrcoef(s1[:lag], s2[-lag:])[0, 1]
                elif lag > 0:
                    corr = np.corrcoef(s1[lag:], s2[:-lag])[0, 1]
                else:
                    corr = np.corrcoef(s1, s2)[0, 1]

                if not np.isnan(corr):
                    correlations.append((lag, corr))

            if not correlations:
                raise ValueError("Could not calculate any valid correlations")

            # Find optimal lag
            optimal_lag, max_corr = max(correlations, key=lambda x: abs(x[1]))

            # Calculate significance (using Fisher z-transformation)
            n = len(s1) - abs(optimal_lag)
            if n > 3:
                z = np.arctanh(max_corr)
                se = 1 / np.sqrt(n - 3)
                significance = 2 * (1 - stats.norm.cdf(abs(z) / se))
            else:
                significance = 1.0

            result = LagCorrelationResult(
                optimal_lag=optimal_lag,
                max_correlation=max_corr,
                lag_range=(-max_lag, max_lag),
                correlations=correlations,
                significance=significance,
            )

            log_operation_end(
                logger, "calculate_lag_correlation", start,
                optimal_lag=optimal_lag, max_correlation=round(max_corr, 4)
            )

            return result

        except Exception as e:
            log_operation_end(logger, "calculate_lag_correlation", start, success=False, error=str(e))
            raise

    def find_leading_indicators(
        self,
        target_series: pd.Series,
        candidate_series: Dict[str, pd.Series],
        max_lag: int,
        min_correlation: float = 0.3,
        sample_interval_sec: float = 1.0,
    ) -> List[LeadingIndicator]:
        """
        Find series that lead (predict) changes in the target series.

        Args:
            target_series: Target series to predict
            candidate_series: Dict mapping names to candidate series
            max_lag: Maximum lag to consider (in samples)
            min_correlation: Minimum absolute correlation to be considered leading
            sample_interval_sec: Time interval between samples in seconds

        Returns:
            List of LeadingIndicator objects, sorted by correlation strength
        """
        start = log_operation_start(
            logger, "find_leading_indicators",
            candidate_count=len(candidate_series), max_lag=max_lag
        )

        try:
            indicators = []

            for name, candidate in candidate_series.items():
                try:
                    result = self.calculate_lag_correlation(
                        target_series, candidate, max_lag
                    )

                    # Only consider negative lags (candidate leads target)
                    if result.optimal_lag < 0 and abs(result.max_correlation) >= min_correlation:
                        lead_time = abs(result.optimal_lag) * sample_interval_sec
                        indicators.append(LeadingIndicator(
                            series_name=name,
                            optimal_lag=result.optimal_lag,
                            correlation=result.max_correlation,
                            significance=result.significance,
                            lead_time_sec=lead_time,
                        ))

                except Exception as e:
                    logger.debug(f"Failed to analyze candidate {name}: {e}")
                    continue

            # Sort by absolute correlation strength
            indicators.sort(key=lambda x: abs(x.correlation), reverse=True)

            log_operation_end(
                logger, "find_leading_indicators", start,
                indicators_found=len(indicators)
            )

            return indicators

        except Exception as e:
            log_operation_end(logger, "find_leading_indicators", start, success=False, error=str(e))
            raise

    # =========================================================================
    # Data Quality Methods
    # =========================================================================

    def assess_alignment_quality(
        self,
        aligned_data: pd.DataFrame,
        expected_freq: Optional[str] = None,
    ) -> AlignmentQualityReport:
        """
        Assess the quality of aligned data.

        Args:
            aligned_data: DataFrame with aligned time series
            expected_freq: Expected data frequency (e.g., '1s', '100ms')

        Returns:
            AlignmentQualityReport with quality metrics
        """
        start = log_operation_start(logger, "assess_alignment_quality")

        try:
            report = AlignmentQualityReport()

            if aligned_data.empty:
                report.issues.append("Empty dataset")
                return report

            report.total_points = aligned_data.shape[0] * aligned_data.shape[1]
            report.missing_points = int(aligned_data.isna().sum().sum())

            # Calculate data coverage
            report.data_coverage_percent = (
                (report.total_points - report.missing_points) / report.total_points * 100
                if report.total_points > 0 else 0
            )

            # Detect gaps in time index
            if isinstance(aligned_data.index, pd.DatetimeIndex) and len(aligned_data.index) > 1:
                time_diffs = pd.Series(aligned_data.index).diff().dt.total_seconds()

                if expected_freq:
                    expected_interval = pd.Timedelta(expected_freq).total_seconds()
                else:
                    expected_interval = time_diffs.median()

                # Identify gaps (significantly larger than expected interval)
                gap_threshold = expected_interval * 2
                gaps = time_diffs[time_diffs > gap_threshold]

                report.gap_count = len(gaps)
                if len(gaps) > 0:
                    report.max_gap_duration_sec = float(gaps.max())
                    report.avg_gap_duration_sec = float(gaps.mean())

            # Detect outliers per column
            outlier_count = 0
            for col in aligned_data.select_dtypes(include=[np.number]).columns:
                col_data = aligned_data[col].dropna()
                if len(col_data) > 10:
                    z_scores = np.abs(stats.zscore(col_data))
                    outlier_count += int(np.sum(z_scores > self.outlier_threshold))

            report.outlier_count = outlier_count

            # Calculate overall quality score (0-1)
            coverage_score = report.data_coverage_percent / 100
            gap_penalty = min(1.0, report.gap_count / max(1, len(aligned_data)) * 10)
            outlier_penalty = min(1.0, report.outlier_count / max(1, report.total_points) * 100)

            report.quality_score = max(0, coverage_score - gap_penalty * 0.3 - outlier_penalty * 0.2)

            # Generate issues list
            if report.data_coverage_percent < 90:
                report.issues.append(f"Low data coverage: {report.data_coverage_percent:.1f}%")
            if report.gap_count > 0:
                report.issues.append(f"Found {report.gap_count} gaps in data")
            if report.outlier_count > report.total_points * 0.01:
                report.issues.append(f"High outlier count: {report.outlier_count}")

            log_operation_end(
                logger, "assess_alignment_quality", start,
                quality_score=round(report.quality_score, 4),
                issues_count=len(report.issues)
            )

            return report

        except Exception as e:
            log_operation_end(logger, "assess_alignment_quality", start, success=False, error=str(e))
            raise

    def detect_clock_drift(
        self,
        sources: Dict[str, pd.DataFrame],
        reference_source: Optional[str] = None,
        correlation_threshold: float = 0.7,
    ) -> List[ClockDriftReport]:
        """
        Detect clock drift between multiple data sources.

        Args:
            sources: Dict mapping source names to DataFrames with datetime index
            reference_source: Name of reference source (uses first if not specified)
            correlation_threshold: Minimum correlation for reliable drift estimation

        Returns:
            List of ClockDriftReport for each source pair
        """
        start = log_operation_start(
            logger, "detect_clock_drift",
            source_count=len(sources)
        )

        try:
            reports = []

            if len(sources) < 2:
                logger.warning("Need at least 2 sources to detect clock drift")
                return reports

            source_names = list(sources.keys())
            if reference_source is None:
                reference_source = source_names[0]

            ref_data = sources[reference_source]
            if not isinstance(ref_data.index, pd.DatetimeIndex):
                raise ValueError(f"Reference source {reference_source} must have datetime index")

            # Compare each source to reference
            for source_name in source_names:
                if source_name == reference_source:
                    continue

                source_data = sources[source_name]
                if not isinstance(source_data.index, pd.DatetimeIndex):
                    logger.warning(f"Skipping {source_name}: no datetime index")
                    continue

                try:
                    # Find overlapping time range
                    overlap_start = max(ref_data.index.min(), source_data.index.min())
                    overlap_end = min(ref_data.index.max(), source_data.index.max())

                    if overlap_start >= overlap_end:
                        logger.warning(f"No overlap between {reference_source} and {source_name}")
                        continue

                    # Get common columns
                    common_cols = set(ref_data.columns) & set(source_data.columns)
                    if not common_cols:
                        # Try correlation on first numeric column of each
                        ref_col = ref_data.select_dtypes(include=[np.number]).columns[0]
                        src_col = source_data.select_dtypes(include=[np.number]).columns[0]
                    else:
                        ref_col = src_col = list(common_cols)[0]

                    # Align data
                    ref_aligned = ref_data.loc[overlap_start:overlap_end, ref_col]
                    src_aligned = source_data.loc[overlap_start:overlap_end, src_col]

                    # Estimate drift using cross-correlation
                    max_drift_samples = min(100, len(ref_aligned) // 4)
                    lag_result = self.calculate_lag_correlation(
                        ref_aligned, src_aligned, max_drift_samples
                    )

                    # Convert lag to seconds
                    if len(ref_aligned) > 1:
                        sample_interval = (
                            (ref_aligned.index[-1] - ref_aligned.index[0]).total_seconds()
                            / (len(ref_aligned) - 1)
                        )
                    else:
                        sample_interval = 1.0

                    drift_sec = lag_result.optimal_lag * sample_interval

                    report = ClockDriftReport(
                        source_a=reference_source,
                        source_b=source_name,
                        estimated_drift_sec=drift_sec,
                        confidence=abs(lag_result.max_correlation),
                        sample_count=len(ref_aligned),
                        method='cross_correlation',
                    )
                    reports.append(report)

                except Exception as e:
                    logger.warning(f"Failed to analyze drift for {source_name}: {e}")
                    continue

            log_operation_end(
                logger, "detect_clock_drift", start,
                reports_generated=len(reports)
            )

            return reports

        except Exception as e:
            log_operation_end(logger, "detect_clock_drift", start, success=False, error=str(e))
            raise

    def correct_timestamps(
        self,
        data: pd.DataFrame,
        offset: Union[float, timedelta],
    ) -> pd.DataFrame:
        """
        Apply timestamp corrections to data.

        Args:
            data: DataFrame with datetime index
            offset: Time offset to apply (seconds as float or timedelta)

        Returns:
            DataFrame with corrected timestamps
        """
        start = log_operation_start(logger, "correct_timestamps")

        try:
            result = data.copy()

            # Convert offset to timedelta if needed
            if isinstance(offset, (int, float)):
                offset = timedelta(seconds=offset)

            # Apply offset to index
            if isinstance(result.index, pd.DatetimeIndex):
                result.index = result.index + offset
            else:
                raise ValueError("DataFrame must have DatetimeIndex")

            log_operation_end(
                logger, "correct_timestamps", start,
                offset_sec=offset.total_seconds()
            )

            return result

        except Exception as e:
            log_operation_end(logger, "correct_timestamps", start, success=False, error=str(e))
            raise

    # =========================================================================
    # Export Functions
    # =========================================================================

    def export_aligned_data(
        self,
        aligned_data: pd.DataFrame,
        output_path: str,
        format: Literal['npz', 'npy', 'pickle'] = 'npz',
        include_metadata: bool = True,
    ) -> str:
        """
        Export aligned data for ML training.

        Args:
            aligned_data: DataFrame with aligned time series
            output_path: Path for output file
            format: Output format ('npz', 'npy', 'pickle')
            include_metadata: Whether to include metadata (column names, timestamps)

        Returns:
            Path to exported file
        """
        start = log_operation_start(
            logger, "export_aligned_data",
            format=format, output_path=output_path
        )

        try:
            if format == 'npz':
                save_dict = {
                    'values': aligned_data.values,
                }
                if include_metadata:
                    save_dict['columns'] = np.array(aligned_data.columns.tolist())
                    if isinstance(aligned_data.index, pd.DatetimeIndex):
                        save_dict['timestamps'] = aligned_data.index.values.astype('datetime64[ns]')
                    else:
                        save_dict['index'] = np.array(aligned_data.index.tolist())

                np.savez(output_path, **save_dict)

            elif format == 'npy':
                np.save(output_path, aligned_data.values)

            elif format == 'pickle':
                aligned_data.to_pickle(output_path)

            else:
                raise ValueError(f"Unsupported format: {format}")

            log_operation_end(
                logger, "export_aligned_data", start,
                format=format, rows=len(aligned_data), columns=len(aligned_data.columns)
            )

            return output_path

        except Exception as e:
            log_operation_end(logger, "export_aligned_data", start, success=False, error=str(e))
            raise

    def export_for_analytics(
        self,
        aligned_data: pd.DataFrame,
        output_path: str,
        format: Literal['parquet', 'csv', 'feather', 'json'] = 'parquet',
        compression: Optional[str] = 'snappy',
    ) -> str:
        """
        Export aligned data for analytics tools.

        Args:
            aligned_data: DataFrame with aligned time series
            output_path: Path for output file
            format: Output format ('parquet', 'csv', 'feather', 'json')
            compression: Compression method (for parquet: 'snappy', 'gzip', 'brotli', None)

        Returns:
            Path to exported file
        """
        start = log_operation_start(
            logger, "export_for_analytics",
            format=format, output_path=output_path
        )

        try:
            # Reset index to make timestamp a column
            export_data = aligned_data.reset_index()
            if 'index' in export_data.columns:
                export_data = export_data.rename(columns={'index': 'timestamp'})

            if format == 'parquet':
                export_data.to_parquet(
                    output_path,
                    index=False,
                    compression=compression,
                )

            elif format == 'csv':
                export_data.to_csv(output_path, index=False)

            elif format == 'feather':
                export_data.to_feather(output_path)

            elif format == 'json':
                export_data.to_json(
                    output_path,
                    orient='records',
                    date_format='iso',
                )

            else:
                raise ValueError(f"Unsupported format: {format}")

            log_operation_end(
                logger, "export_for_analytics", start,
                format=format, rows=len(aligned_data)
            )

            return output_path

        except Exception as e:
            log_operation_end(logger, "export_for_analytics", start, success=False, error=str(e))
            raise


# Global service instance
_data_alignment_service: Optional[DataAlignmentService] = None


def get_data_alignment_service(
    default_interpolation: InterpolationMethod = InterpolationMethod.LINEAR,
    outlier_threshold: float = 3.0,
    max_gap_fill_sec: float = 300.0,
) -> DataAlignmentService:
    """
    Get global Data Alignment Service instance.

    Args:
        default_interpolation: Default interpolation method
        outlier_threshold: Standard deviations for outlier detection
        max_gap_fill_sec: Maximum gap duration to fill

    Returns:
        DataAlignmentService instance
    """
    global _data_alignment_service
    if _data_alignment_service is None:
        _data_alignment_service = DataAlignmentService(
            default_interpolation=default_interpolation,
            outlier_threshold=outlier_threshold,
            max_gap_fill_sec=max_gap_fill_sec,
        )
    return _data_alignment_service
