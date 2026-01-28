"""
Historian Service (PostgreSQL + TimescaleDB)
High-speed time-series data collection, storage, and retrieval.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
import logging
from collections import deque
import threading
import time

import pandas as pd
import numpy as np
from sqlalchemy import text, select, and_
from sqlalchemy.orm import Session

from config.database import (
    engine, get_session, create_hypertable, 
    add_compression_policy, add_retention_policy
)
from models.scada.models import Tag, TagValue

logger = logging.getLogger(__name__)


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
        self.deviation = deviation  # Relative deviation (e.g., 0.01 = 1%)
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
            # First value - always store
            self._last_stored[tag_id] = value
            self._pivot[tag_id] = value
            return True
        
        pivot = self._pivot[tag_id]
        last = self._last_stored[tag_id]
        
        # Calculate compression deviation in absolute terms
        abs_deviation = abs(pivot.value * self.deviation) if pivot.value != 0 else self.deviation
        
        # Time difference
        dt = (value.time - pivot.time).total_seconds()
        if dt <= 0:
            return False
        
        # Calculate slopes
        slope = (value.value - pivot.value) / dt
        
        if tag_id not in self._slope_high:
            # Initialize slopes
            self._slope_high[tag_id] = (value.value + abs_deviation - pivot.value) / dt
            self._slope_low[tag_id] = (value.value - abs_deviation - pivot.value) / dt
            return False
        
        # Check if value is outside the swinging door
        high_bound = pivot.value + self._slope_high[tag_id] * dt
        low_bound = pivot.value + self._slope_low[tag_id] * dt
        
        if value.value > high_bound + abs_deviation or value.value < low_bound - abs_deviation:
            # Value outside bounds - store last value and reset
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
    
    def __init__(self, config: HistorianConfig = None):
        self.config = config or HistorianConfig()
        self._buffer: deque = deque(maxlen=self.config.buffer_size * 2)
        self._lock = threading.Lock()
        self._compressor = SwingingDoorCompressor(self.config.compression_deviation)
        self._running = False
        self._flush_thread: Optional[threading.Thread] = None
        self._write_count = 0
        self._compressed_count = 0
    
    def start(self):
        """Start the background flush thread"""
        if self._running:
            return
        
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
        logger.info("Historian writer started")
    
    def stop(self):
        """Stop the writer and flush remaining data"""
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=5)
        self._flush_to_db()
        logger.info(f"Historian writer stopped. Total writes: {self._write_count}, compressed: {self._compressed_count}")
    
    def write(self, tag_id: str, value: float, timestamp: datetime = None,
              quality: int = 192, source: str = None, compress: bool = True):
        """
        Write a single value to the historian.
        
        Args:
            tag_id: Tag identifier
            value: Numeric value
            timestamp: Time of value (default: now)
            quality: OPC quality code (192 = good)
            source: Source identifier
            compress: Whether to apply compression
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
        """
        Write multiple values at once.
        
        Args:
            values: List of dicts with tag_id, value, timestamp, quality, source
            compress: Whether to apply compression
        """
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
            with engine.connect() as conn:
                # Build bulk insert
                insert_data = []
                for hv in values_to_write:
                    insert_data.append({
                        'time': hv.time,
                        'tag_id': hv.tag_id,
                        'value_numeric': hv.value,
                        'quality': hv.quality,
                        'source': hv.source
                    })
                
                # Use COPY for fastest inserts (via executemany)
                conn.execute(
                    text("""
                        INSERT INTO tag_values (time, tag_id, value_numeric, quality, source)
                        VALUES (:time, :tag_id, :value_numeric, :quality, :source)
                    """),
                    insert_data
                )
                conn.commit()
                
            logger.debug(f"Flushed {len(values_to_write)} values to historian")
            
        except Exception as e:
            logger.error(f"Error flushing to historian: {e}")
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
    """
    Query historical data with support for aggregation and interpolation.
    """
    
    def __init__(self, session: Session = None):
        self.session = session
    
    def get_raw(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        limit: int = 100000
    ) -> pd.DataFrame:
        """
        Get raw historical values.
        
        Returns DataFrame with columns: time, tag_id, value, quality
        """
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
        """
        Get aggregated historical values using TimescaleDB time_bucket.
        
        Args:
            tag_ids: List of tag IDs
            start: Start time
            end: End time
            bucket: Time bucket size (e.g., '1 minute', '1 hour', '1 day')
            agg: Aggregation function (avg, min, max, sum, count, first, last)
        
        Returns DataFrame with columns: bucket, tag_id, value
        """
        agg_func = {
            'avg': 'AVG(value_numeric)',
            'min': 'MIN(value_numeric)',
            'max': 'MAX(value_numeric)',
            'sum': 'SUM(value_numeric)',
            'count': 'COUNT(*)',
            'first': 'FIRST(value_numeric, time)',
            'last': 'LAST(value_numeric, time)'
        }.get(agg, 'AVG(value_numeric)')
        
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
    
    def get_interpolated(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        interval_seconds: int = 60,
        method: str = 'linear'
    ) -> pd.DataFrame:
        """
        Get interpolated values at fixed intervals.
        
        Args:
            tag_ids: List of tag IDs
            start: Start time
            end: End time
            interval_seconds: Interval between points
            method: Interpolation method (linear, previous, next)
        """
        # Get raw data
        raw = self.get_raw(tag_ids, start, end)
        
        if raw.empty:
            return pd.DataFrame(columns=['time', 'tag_id', 'value'])
        
        # Create time index
        time_index = pd.date_range(start=start, end=end, freq=f'{interval_seconds}s')
        
        result_dfs = []
        for tag_id in tag_ids:
            tag_data = raw[raw['tag_id'] == tag_id].copy()
            if tag_data.empty:
                continue
            
            tag_data = tag_data.set_index('time')
            
            # Reindex to regular intervals
            tag_data = tag_data.reindex(tag_data.index.union(time_index))
            
            # Interpolate
            if method == 'linear':
                tag_data['value'] = tag_data['value'].interpolate(method='linear')
            elif method == 'previous':
                tag_data['value'] = tag_data['value'].ffill()
            elif method == 'next':
                tag_data['value'] = tag_data['value'].bfill()
            
            # Select only the regular interval times
            tag_data = tag_data.loc[time_index]
            tag_data['tag_id'] = tag_id
            tag_data = tag_data.reset_index().rename(columns={'index': 'time'})
            
            result_dfs.append(tag_data[['time', 'tag_id', 'value']])
        
        if not result_dfs:
            return pd.DataFrame(columns=['time', 'tag_id', 'value'])
        
        return pd.concat(result_dfs, ignore_index=True)
    
    def get_trend(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        max_points: int = 1000
    ) -> pd.DataFrame:
        """
        Get downsampled trend data for visualization.
        Automatically selects appropriate bucket size based on time range.
        """
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
        """
        Get statistics for tags over a time period.
        """
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
                        FIRST(value_numeric, time) as first_value,
                        LAST(value_numeric, time) as last_value,
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
                       'first_value', 'last_value', 'first_time', 'last_time']
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
        logger.info(f"Exported {len(df)} rows to {output_path}")
        return output_path
    
    def export_parquet(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        output_path: str
    ) -> str:
        """Export to Parquet file (efficient for large datasets)"""
        df = self.reader.get_raw(tag_ids, start, end)
        df.to_parquet(output_path, index=False)
        logger.info(f"Exported {len(df)} rows to {output_path}")
        return output_path
    
    def export_npz(
        self,
        tag_ids: List[str],
        start: datetime,
        end: datetime,
        output_path: str,
        interval_seconds: int = None
    ) -> str:
        """
        Export to NPZ format for ML training.
        Creates aligned arrays suitable for fingerprinting model.
        """
        if interval_seconds:
            df = self.reader.get_interpolated(tag_ids, start, end, interval_seconds)
        else:
            df = self.reader.get_raw(tag_ids, start, end)
        
        # Pivot to wide format
        pivot = df.pivot(index='time', columns='tag_id', values='value')
        
        # Save as NPZ
        np.savez(
            output_path,
            timestamps=pivot.index.values.astype('datetime64[ns]'),
            tag_ids=pivot.columns.values,
            values=pivot.values
        )
        
        logger.info(f"Exported {len(pivot)} rows to {output_path}")
        return output_path


# =============================================================================
# INITIALIZATION
# =============================================================================

def initialize_historian():
    """Initialize historian tables and policies"""
    # Create hypertable
    create_hypertable('tag_values', 'time', '7 days')
    
    # Add compression
    add_compression_policy('tag_values', '7 days')
    
    # Add retention
    add_retention_policy('tag_values', '2 years')
    
    # Create continuous aggregates
    with engine.connect() as conn:
        try:
            # 1-minute aggregate
            conn.execute(text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS tag_values_1min
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('1 minute', time) AS bucket,
                    tag_id,
                    AVG(value_numeric) AS avg_value,
                    MIN(value_numeric) AS min_value,
                    MAX(value_numeric) AS max_value,
                    COUNT(*) AS sample_count
                FROM tag_values
                WHERE value_numeric IS NOT NULL
                GROUP BY bucket, tag_id;
            """))
            
            conn.execute(text("""
                SELECT add_continuous_aggregate_policy('tag_values_1min',
                    start_offset => INTERVAL '1 hour',
                    end_offset => INTERVAL '1 minute',
                    schedule_interval => INTERVAL '1 minute',
                    if_not_exists => TRUE
                );
            """))
            
            conn.commit()
            logger.info("Historian continuous aggregates created")
        except Exception as e:
            logger.warning(f"Could not create continuous aggregates: {e}")


# Global historian writer instance
historian_writer = HistorianWriter()


def start_historian():
    """Start the historian writer"""
    initialize_historian()
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
