"""
LEGO Factory v3 - Historian Service (PostgreSQL + TimescaleDB)
==============================================================
High-speed time-series data collection, storage, and retrieval.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from collections import deque
import threading
import time

import pandas as pd
import numpy as np
from sqlalchemy import text, select, and_
from sqlalchemy.orm import Session

from config.database import get_engine
from config.settings import get_config
from config.logging_config import get_structured_logger, log_operation_start, log_operation_end

logger = get_structured_logger(__name__)


@dataclass
class HistorianValue:
    """Single historian data point"""
    tag_id: str
    time: datetime
    value: float
    quality: int = 192
    source: str = None


@dataclass
class HistorianConfig:
    """Historian configuration"""
    buffer_size: int = 10000
    flush_interval_seconds: float = 1.0
    compression_deviation: float = 0.01  # 1% default
    chunk_interval: str = '7 days'
    compress_after: str = '7 days'
    retain_for: str = '2 years'


class SwingingDoorCompressor:
    """
    Swinging Door Trending compression algorithm.
    Reduces data volume while preserving significant changes.
    """

    def __init__(self, deviation: float = 0.01):
        self.deviation = deviation
        self._last_stored: Dict[str, HistorianValue] = {}
        self._pivot: Dict[str, HistorianValue] = {}
        self._slope_high: Dict[str, float] = {}
        self._slope_low: Dict[str, float] = {}

    def should_store(self, tag_id: str, value: HistorianValue) -> bool:
        """
        Determine if a value should be stored based on compression algorithm.
        Returns True if the value represents a significant change.
        """
        if tag_id not in self._last_stored:
            self._last_stored[tag_id] = value
            self._pivot[tag_id] = value
            return True

        pivot = self._pivot[tag_id]

        # Calculate compression deviation in absolute terms
        abs_deviation = abs(pivot.value * self.deviation) if pivot.value != 0 else self.deviation

        # Time difference
        dt = (value.time - pivot.time).total_seconds()
        if dt <= 0:
            return False

        # Calculate slopes
        slope = (value.value - pivot.value) / dt

        if tag_id not in self._slope_high:
            self._slope_high[tag_id] = (value.value + abs_deviation - pivot.value) / dt
            self._slope_low[tag_id] = (value.value - abs_deviation - pivot.value) / dt
            return False

        # Check if value is outside the swinging door
        high_bound = pivot.value + self._slope_high[tag_id] * dt
        low_bound = pivot.value + self._slope_low[tag_id] * dt

        if value.value > high_bound + abs_deviation or value.value < low_bound - abs_deviation:
            result_value = self._last_stored[tag_id]
            self._pivot[tag_id] = result_value
            self._last_stored[tag_id] = value
            self._slope_high[tag_id] = (value.value + abs_deviation - result_value.value) / dt
            self._slope_low[tag_id] = (value.value - abs_deviation - result_value.value) / dt
            return True

        # Update slopes to narrow the door
        new_slope_high = (value.value + abs_deviation - pivot.value) / dt
        new_slope_low = (value.value - abs_deviation - pivot.value) / dt

        self._slope_high[tag_id] = min(self._slope_high[tag_id], new_slope_high)
        self._slope_low[tag_id] = max(self._slope_low[tag_id], new_slope_low)

        self._last_stored[tag_id] = value
        return False

    def flush(self, tag_id: str) -> Optional[HistorianValue]:
        """Flush last value for a tag"""
        return self._last_stored.pop(tag_id, None)


class HistorianWriter:
    """
    High-speed data writer with buffering and compression.
    Thread-safe for concurrent writes.
    """

    _instance = None

    def __new__(cls, config: HistorianConfig = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: HistorianConfig = None):
        if self._initialized:
            return

        self.config = config or HistorianConfig()
        self._buffer: deque = deque(maxlen=self.config.buffer_size * 2)
        self._lock = threading.Lock()
        self._compressor = SwingingDoorCompressor(self.config.compression_deviation)
        self._running = False
        self._flush_thread: Optional[threading.Thread] = None
        self._write_count = 0
        self._compressed_count = 0
        self._initialized = True

    def start(self):
        """Start the background flush thread"""
        if self._running:
            return

        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
        logger.info(
            "Historian writer started",
            extra={
                'event': 'historian_started',
                'buffer_size': self.config.buffer_size,
                'flush_interval': self.config.flush_interval_seconds,
                'compression_deviation': self.config.compression_deviation,
            }
        )

    def stop(self):
        """Stop the writer and flush remaining data"""
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=5)
        self._flush_to_db()
        logger.info(
            "Historian writer stopped",
            extra={
                'event': 'historian_stopped',
                'total_writes': self._write_count,
                'compressed_count': self._compressed_count,
                'compression_ratio': round(
                    self._compressed_count / max(1, self._write_count + self._compressed_count),
                    4
                ),
            }
        )

    def write(self, tag_id: str, value: float, timestamp: datetime = None,
              quality: int = 192, source: str = None, compress: bool = True):
        """
        Write a single value to the historian.
        """
        timestamp = timestamp or datetime.utcnow()

        hv = HistorianValue(
            tag_id=tag_id,
            time=timestamp,
            value=value,
            quality=quality,
            source=source
        )

        # Apply compression
        if compress:
            if not self._compressor.should_store(tag_id, hv):
                self._compressed_count += 1
                return

        with self._lock:
            self._buffer.append(hv)
            self._write_count += 1

            # Flush if buffer is getting full
            if len(self._buffer) >= self.config.buffer_size:
                self._flush_to_db()

    def write_batch(self, values: List[Dict[str, Any]], compress: bool = True):
        """Write multiple values at once."""
        for v in values:
            self.write(
                tag_id=v['tag_id'],
                value=v['value'],
                timestamp=v.get('timestamp'),
                quality=v.get('quality', 192),
                source=v.get('source'),
                compress=compress
            )

    def _flush_loop(self):
        """Background thread that periodically flushes buffer"""
        while self._running:
            time.sleep(self.config.flush_interval_seconds)
            self._flush_to_db()

    def _flush_to_db(self):
        """Flush buffer to database"""
        with self._lock:
            if not self._buffer:
                return

            values_to_write = list(self._buffer)
            self._buffer.clear()

        if not values_to_write:
            return

        try:
            engine = get_engine()
            with engine.connect() as conn:
                insert_data = []
                for hv in values_to_write:
                    insert_data.append({
                        'time': hv.time,
                        'tag_id': hv.tag_id,
                        'value_numeric': hv.value,
                        'quality': hv.quality,
                        'source': hv.source
                    })

                conn.execute(
                    text("""
                        INSERT INTO tag_values (time, tag_id, value_numeric, quality, source)
                        VALUES (:time, :tag_id, :value_numeric, :quality, :source)
                    """),
                    insert_data
                )
                conn.commit()

            logger.debug(
                "Flushed values to historian",
                extra={
                    'event': 'historian_flush',
                    'values_count': len(values_to_write),
                    'buffer_remaining': len(self._buffer),
                }
            )

        except Exception as e:
            logger.error(
                "Error flushing to historian",
                extra={
                    'event': 'historian_flush_error',
                    'error': str(e),
                    'values_count': len(values_to_write),
                },
                exc_info=True
            )
            # Re-add to buffer for retry
            with self._lock:
                for hv in values_to_write:
                    self._buffer.appendleft(hv)

    def get_stats(self) -> Dict[str, Any]:
        """Get writer statistics"""
        return {
            'buffer_size': len(self._buffer),
            'total_writes': self._write_count,
            'compressed_count': self._compressed_count,
            'compression_ratio': self._compressed_count / max(1, self._write_count + self._compressed_count)
        }


class HistorianReader:
    """Query historical data with support for aggregation and interpolation."""

    def __init__(self, session: Session = None):
        self.session = session

    def get_raw(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        limit: int = 100000
    ) -> pd.DataFrame:
        """Get raw historical values."""
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT time, tag_id, value_numeric as value, quality
                    FROM tag_values
                    WHERE tag_id = ANY(:tag_ids)
                      AND time >= :start
                      AND time <= :end
                    ORDER BY time
                    LIMIT :limit
                """),
                {
                    'tag_ids': tag_ids,
                    'start': start,
                    'end': end,
                    'limit': limit
                }
            )

            df = pd.DataFrame(result.fetchall(), columns=['time', 'tag_id', 'value', 'quality'])

        return df

    def get_aggregated(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        bucket: str = '1 minute',
        agg: str = 'avg'
    ) -> pd.DataFrame:
        """Get aggregated historical values using TimescaleDB time_bucket."""
        agg_func = {
            'avg': 'AVG(value_numeric)',
            'min': 'MIN(value_numeric)',
            'max': 'MAX(value_numeric)',
            'sum': 'SUM(value_numeric)',
            'count': 'COUNT(*)',
            'first': 'FIRST(value_numeric, time)',
            'last': 'LAST(value_numeric, time)'
        }.get(agg, 'AVG(value_numeric)')

        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(f"""
                    SELECT
                        time_bucket(:bucket, time) AS bucket,
                        tag_id,
                        {agg_func} AS value
                    FROM tag_values
                    WHERE tag_id = ANY(:tag_ids)
                      AND time >= :start
                      AND time <= :end
                    GROUP BY bucket, tag_id
                    ORDER BY bucket, tag_id
                """),
                {
                    'bucket': bucket,
                    'tag_ids': tag_ids,
                    'start': start,
                    'end': end
                }
            )

            df = pd.DataFrame(result.fetchall(), columns=['bucket', 'tag_id', 'value'])

        return df

    def get_trend(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        max_points: int = 1000
    ) -> pd.DataFrame:
        """Get downsampled trend data for visualization."""
        duration = (end - start).total_seconds()

        # Calculate appropriate bucket size
        if duration <= 3600:  # 1 hour
            bucket = '1 second'
        elif duration <= 86400:  # 1 day
            bucket = '1 minute'
        elif duration <= 604800:  # 1 week
            bucket = '5 minutes'
        elif duration <= 2592000:  # 30 days
            bucket = '1 hour'
        else:
            bucket = '1 day'

        return self.get_aggregated(tag_ids, start, end, bucket, 'avg')

    def get_statistics(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """Get statistics for tags over a time period."""
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT
                        tag_id,
                        COUNT(*) as count,
                        AVG(value_numeric) as avg,
                        MIN(value_numeric) as min,
                        MAX(value_numeric) as max,
                        STDDEV(value_numeric) as stddev,
                        MIN(time) as first_time,
                        MAX(time) as last_time
                    FROM tag_values
                    WHERE tag_id = ANY(:tag_ids)
                      AND time >= :start
                      AND time <= :end
                    GROUP BY tag_id
                """),
                {
                    'tag_ids': tag_ids,
                    'start': start,
                    'end': end
                }
            )

            columns = ['tag_id', 'count', 'avg', 'min', 'max', 'stddev',
                       'first_time', 'last_time']
            df = pd.DataFrame(result.fetchall(), columns=columns)

        return df


class HistorianExporter:
    """Export historical data to various formats"""

    def __init__(self):
        self.reader = HistorianReader()

    def export_csv(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        output_path: str,
        aggregation: str = None,
        bucket: str = '1 minute'
    ) -> str:
        """Export to CSV file"""
        if aggregation:
            df = self.reader.get_aggregated(tag_ids, start, end, bucket, aggregation)
        else:
            df = self.reader.get_raw(tag_ids, start, end)

        df.to_csv(output_path, index=False)
        logger.info(
            "Exported historian data to CSV",
            extra={
                'event': 'historian_export',
                'format': 'csv',
                'rows': len(df),
                'output_path': output_path,
                'tag_count': len(tag_ids),
            }
        )
        return output_path

    def export_parquet(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        output_path: str
    ) -> str:
        """Export to Parquet file"""
        df = self.reader.get_raw(tag_ids, start, end)
        df.to_parquet(output_path, index=False)
        logger.info(
            "Exported historian data to Parquet",
            extra={
                'event': 'historian_export',
                'format': 'parquet',
                'rows': len(df),
                'output_path': output_path,
                'tag_count': len(tag_ids),
            }
        )
        return output_path

    def export_npz(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        output_path: str
    ) -> str:
        """Export to NPZ format for ML training."""
        df = self.reader.get_raw(tag_ids, start, end)

        if df.empty:
            np.savez(output_path, timestamps=np.array([]), tag_ids=np.array([]), values=np.array([]))
            return output_path

        # Pivot to wide format
        pivot = df.pivot(index='time', columns='tag_id', values='value')

        np.savez(
            output_path,
            timestamps=pivot.index.values.astype('datetime64[ns]'),
            tag_ids=pivot.columns.values,
            values=pivot.values
        )

        logger.info(
            "Exported historian data to NPZ",
            extra={
                'event': 'historian_export',
                'format': 'npz',
                'rows': len(pivot),
                'output_path': output_path,
                'tag_count': len(tag_ids),
            }
        )
        return output_path


# Global historian writer instance
historian_writer = HistorianWriter()


def start_historian():
    """Start the historian writer"""
    historian_writer.start()


def stop_historian():
    """Stop the historian writer"""
    historian_writer.stop()


def write_to_historian(tag_id: str, value: float, timestamp: datetime = None,
                       quality: int = 192, source: str = None):
    """Write a value to the historian"""
    historian_writer.write(tag_id, value, timestamp, quality, source)


def read_from_historian(
    tag_ids: List[str],
    start: datetime,
    end: datetime,
    aggregation: str = None,
    bucket: str = '1 minute'
) -> pd.DataFrame:
    """Read from historian"""
    reader = HistorianReader()
    if aggregation:
        return reader.get_aggregated(tag_ids, start, end, bucket, aggregation)
    return reader.get_raw(tag_ids, start, end)


def get_historian_stats() -> Dict[str, Any]:
    """Get historian writer statistics"""
    return historian_writer.get_stats()
