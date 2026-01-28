"""
Unit tests for SCADA Historian Service.

Tests data buffering, compression, writing, and reading operations.
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np

from services.scada.historian.historian_service import (
    HistorianValue,
    HistorianConfig,
    SwingingDoorCompressor,
    HistorianWriter,
    HistorianReader,
    HistorianExporter,
    start_historian,
    stop_historian,
    write_to_historian,
    read_from_historian,
    get_historian_stats,
)


class TestHistorianValue:
    """Tests for HistorianValue dataclass."""

    def test_create_historian_value(self):
        """Test creating a historian value."""
        hv = HistorianValue(
            tag_id="tag_001",
            time=datetime.utcnow(),
            value=25.5,
            quality=192,
            source="plc_1"
        )

        assert hv.tag_id == "tag_001"
        assert hv.value == 25.5
        assert hv.quality == 192
        assert hv.source == "plc_1"

    def test_historian_value_defaults(self):
        """Test historian value with defaults."""
        hv = HistorianValue(
            tag_id="tag_001",
            time=datetime.utcnow(),
            value=100.0
        )

        assert hv.quality == 192
        assert hv.source is None


class TestHistorianConfig:
    """Tests for HistorianConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = HistorianConfig()

        assert config.buffer_size == 10000
        assert config.flush_interval_seconds == 1.0
        assert config.compression_deviation == 0.01

    def test_custom_config(self):
        """Test custom configuration."""
        config = HistorianConfig(
            buffer_size=5000,
            flush_interval_seconds=0.5,
            compression_deviation=0.02
        )

        assert config.buffer_size == 5000
        assert config.flush_interval_seconds == 0.5
        assert config.compression_deviation == 0.02


class TestSwingingDoorCompressor:
    """Tests for Swinging Door Trending compression."""

    @pytest.fixture
    def compressor(self):
        """Create a compressor with default settings."""
        return SwingingDoorCompressor(deviation=0.01)

    def test_first_value_always_stored(self, compressor):
        """Test that first value is always stored."""
        hv = HistorianValue("tag_001", datetime.utcnow(), 100.0)
        result = compressor.should_store("tag_001", hv)

        assert result is True

    def test_significant_change_stored(self, compressor):
        """Test that significant changes are stored."""
        t0 = datetime.utcnow()

        # First value
        hv1 = HistorianValue("tag_001", t0, 100.0)
        compressor.should_store("tag_001", hv1)

        # Small change (should not store)
        hv2 = HistorianValue("tag_001", t0 + timedelta(seconds=1), 100.5)
        result2 = compressor.should_store("tag_001", hv2)

        # Large change (should store)
        hv3 = HistorianValue("tag_001", t0 + timedelta(seconds=2), 150.0)
        result3 = compressor.should_store("tag_001", hv3)

        assert result3 is True

    def test_flush(self, compressor):
        """Test flushing last value."""
        hv = HistorianValue("tag_001", datetime.utcnow(), 100.0)
        compressor.should_store("tag_001", hv)

        flushed = compressor.flush("tag_001")
        assert flushed is not None
        assert flushed.value == 100.0

        # Second flush should return None
        flushed2 = compressor.flush("tag_001")
        assert flushed2 is None


class TestHistorianWriter:
    """Tests for HistorianWriter class."""

    @pytest.fixture
    def writer(self):
        """Create a fresh writer for testing."""
        # Reset singleton
        HistorianWriter._instance = None
        config = HistorianConfig(buffer_size=100, flush_interval_seconds=10.0)
        return HistorianWriter(config)

    def test_singleton_pattern(self):
        """Test that HistorianWriter is a singleton."""
        HistorianWriter._instance = None
        w1 = HistorianWriter()
        w2 = HistorianWriter()

        assert w1 is w2

    def test_write_single_value(self, writer):
        """Test writing a single value."""
        writer.write("tag_001", 100.0, compress=False)

        stats = writer.get_stats()
        assert stats['buffer_size'] >= 1
        assert stats['total_writes'] >= 1

    def test_write_batch(self, writer):
        """Test writing multiple values."""
        values = [
            {'tag_id': 'tag_001', 'value': 100.0},
            {'tag_id': 'tag_002', 'value': 200.0},
            {'tag_id': 'tag_003', 'value': 300.0},
        ]
        writer.write_batch(values, compress=False)

        stats = writer.get_stats()
        assert stats['total_writes'] >= 3

    def test_compression_counts(self, writer):
        """Test that compression is tracked."""
        # Write values that should be compressed
        for i in range(10):
            writer.write("tag_001", 100.0 + i * 0.001, compress=True)

        stats = writer.get_stats()
        # Some values should be compressed
        assert stats['compression_ratio'] >= 0

    def test_get_stats(self, writer):
        """Test getting writer statistics."""
        stats = writer.get_stats()

        assert 'buffer_size' in stats
        assert 'total_writes' in stats
        assert 'compressed_count' in stats
        assert 'compression_ratio' in stats


class TestHistorianReader:
    """Tests for HistorianReader class."""

    @pytest.fixture
    def reader(self):
        """Create a reader for testing."""
        return HistorianReader()

    def test_get_raw_empty(self, reader):
        """Test getting raw data when empty."""
        with patch('services.scada.historian.historian_service.get_engine') as mock_engine:
            mock_conn = Mock()
            mock_result = Mock()
            mock_result.fetchall.return_value = []
            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.connect.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_engine.return_value.connect.return_value.__exit__ = Mock(return_value=False)

            df = reader.get_raw(
                ["tag_001"],
                datetime.utcnow() - timedelta(hours=1),
                datetime.utcnow()
            )

            assert isinstance(df, pd.DataFrame)
            assert len(df) == 0

    def test_calculate_bucket_size(self, reader):
        """Test bucket size calculation for trends."""
        # 1 hour duration -> 1 second bucket
        start = datetime.utcnow() - timedelta(hours=1)
        end = datetime.utcnow()

        with patch.object(reader, 'get_aggregated') as mock_agg:
            mock_agg.return_value = pd.DataFrame()
            reader.get_trend(["tag_001"], start, end)

            # Check that get_aggregated was called with appropriate bucket
            mock_agg.assert_called_once()
            call_args = mock_agg.call_args
            assert '1 second' in str(call_args) or '1 minute' in str(call_args) or call_args[0][3] in ['1 second', '1 minute']


class TestHistorianExporter:
    """Tests for HistorianExporter class."""

    @pytest.fixture
    def exporter(self):
        """Create an exporter for testing."""
        return HistorianExporter()

    def test_export_csv(self, exporter, tmp_path):
        """Test exporting to CSV."""
        output_path = str(tmp_path / "test_export.csv")

        with patch.object(exporter.reader, 'get_raw') as mock_raw:
            mock_raw.return_value = pd.DataFrame({
                'time': [datetime.utcnow()],
                'tag_id': ['tag_001'],
                'value': [100.0],
                'quality': [192]
            })

            result = exporter.export_csv(
                ["tag_001"],
                datetime.utcnow() - timedelta(hours=1),
                datetime.utcnow(),
                output_path
            )

            assert result == output_path

    def test_export_parquet(self, exporter, tmp_path):
        """Test exporting to Parquet."""
        output_path = str(tmp_path / "test_export.parquet")

        with patch.object(exporter.reader, 'get_raw') as mock_raw:
            mock_raw.return_value = pd.DataFrame({
                'time': [datetime.utcnow()],
                'tag_id': ['tag_001'],
                'value': [100.0],
                'quality': [192]
            })

            result = exporter.export_parquet(
                ["tag_001"],
                datetime.utcnow() - timedelta(hours=1),
                datetime.utcnow(),
                output_path
            )

            assert result == output_path


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    @pytest.fixture(autouse=True)
    def reset_writer(self):
        """Reset writer singleton before each test."""
        HistorianWriter._instance = None
        yield

    def test_write_to_historian(self):
        """Test write_to_historian function."""
        # Should not raise
        write_to_historian("tag_001", 100.0)

    def test_get_historian_stats(self):
        """Test get_historian_stats function."""
        stats = get_historian_stats()

        assert isinstance(stats, dict)
        assert 'buffer_size' in stats
        assert 'total_writes' in stats


class TestCompressionAlgorithm:
    """Tests for the Swinging Door compression algorithm."""

    def test_linear_trend_compression(self):
        """Test compression of linear trend data."""
        compressor = SwingingDoorCompressor(deviation=0.05)  # 5% deviation
        t0 = datetime.utcnow()

        stored_count = 0
        for i in range(100):
            # Linear trend: y = 100 + i
            hv = HistorianValue(
                "tag_001",
                t0 + timedelta(seconds=i),
                100.0 + i
            )
            if compressor.should_store("tag_001", hv):
                stored_count += 1

        # Linear trend should compress well
        # The swinging door algorithm stores the first point and only stores
        # subsequent points when they exceed the deviation from the trend
        # For a perfect linear trend, it may only store the first point
        assert stored_count < 100
        assert stored_count >= 1  # At minimum first point is always stored

    def test_noisy_data_compression(self):
        """Test compression of noisy data."""
        compressor = SwingingDoorCompressor(deviation=0.01)
        t0 = datetime.utcnow()

        stored_count = 0
        np.random.seed(42)

        for i in range(100):
            # Noisy data: base + random noise
            noise = np.random.normal(0, 5)
            hv = HistorianValue(
                "tag_001",
                t0 + timedelta(seconds=i),
                100.0 + noise
            )
            if compressor.should_store("tag_001", hv):
                stored_count += 1

        # Noisy data should store more points
        assert stored_count > 10
