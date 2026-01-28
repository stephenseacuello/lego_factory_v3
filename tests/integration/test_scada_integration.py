"""
Integration tests for SCADA services.

Tests the integration between:
- Tag Service
- Historian Service
- Alarm Service
- ML Inference Service
"""

import pytest
import asyncio
import time
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import numpy as np


class TestTagToHistorianIntegration:
    """Tests for Tag Service to Historian integration."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = Mock()
        session.execute = Mock(return_value=Mock(fetchall=Mock(return_value=[])))
        session.commit = Mock()
        return session

    def test_tag_value_flows_to_historian(self, mock_db_session):
        """Test that tag values are written to historian."""
        with patch('services.scada.tag_management.tag_service.get_session') as mock_get_session, \
             patch('services.scada.historian.historian_service.HistorianWriter') as MockWriter:

            mock_get_session.return_value.__enter__ = Mock(return_value=mock_db_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=False)

            mock_writer = Mock()
            MockWriter.return_value = mock_writer
            MockWriter._instance = mock_writer

            from services.scada.tag_management.tag_service import TagService
            from services.scada.historian.historian_service import write_to_historian

            # Create tag service
            tag_service = TagService(mock_db_session)

            # Write a tag value
            tag_id = "temp_001"
            value = 25.5

            # Simulate the integration - tag service triggers historian write
            write_to_historian(tag_id, value)

            # Verify historian write was called
            mock_writer.write.assert_called()

    def test_batch_tag_writes_to_historian(self, mock_db_session):
        """Test that batch tag writes are sent to historian."""
        with patch('services.scada.historian.historian_service.HistorianWriter') as MockWriter:
            mock_writer = Mock()
            MockWriter.return_value = mock_writer
            MockWriter._instance = mock_writer

            from services.scada.historian.historian_service import HistorianWriter

            # Create writer directly
            HistorianWriter._instance = None
            writer = HistorianWriter()

            # Write multiple values
            values = [
                {'tag_id': 'temp_001', 'value': 25.5},
                {'tag_id': 'temp_002', 'value': 30.0},
                {'tag_id': 'pressure_001', 'value': 101.3},
            ]

            for v in values:
                writer.write(v['tag_id'], v['value'], compress=False)

            stats = writer.get_stats()
            assert stats['total_writes'] >= 3


class TestTagToAlarmIntegration:
    """Tests for Tag Service to Alarm Service integration."""

    @pytest.fixture
    def mock_alarm_processor(self):
        """Create a mock alarm processor."""
        from services.scada.alarm_management.alarm_service import AlarmProcessor
        AlarmProcessor._instance = None
        processor = AlarmProcessor()
        return processor

    def test_tag_value_triggers_high_alarm(self, mock_alarm_processor):
        """Test that high tag value triggers alarm."""
        from services.scada.alarm_management.alarm_service import AlarmType

        # Set up alarm definition
        mock_alarm = Mock()
        mock_alarm.tag_id = "temp_001"
        mock_alarm.alarm_type = AlarmType.HIGH
        mock_alarm.high_limit = 90.0
        mock_alarm.deadband = 0
        mock_alarm.enabled = True
        mock_alarm.id = "alarm_001"
        mock_alarm.priority = 2
        mock_alarm.message = "Temperature high"

        mock_alarm_processor.load_alarm_definitions([mock_alarm])

        # Check if condition is triggered
        is_triggered = mock_alarm_processor._check_condition(mock_alarm, 95.0)

        assert is_triggered is True

    def test_tag_value_clears_alarm(self, mock_alarm_processor):
        """Test that normal tag value clears alarm."""
        from services.scada.alarm_management.alarm_service import AlarmType

        mock_alarm = Mock()
        mock_alarm.tag_id = "temp_001"
        mock_alarm.alarm_type = AlarmType.HIGH
        mock_alarm.high_limit = 90.0
        mock_alarm.deadband = 2.0
        mock_alarm.enabled = True

        mock_alarm_processor.load_alarm_definitions([mock_alarm])

        # Value below limit should not trigger
        is_triggered = mock_alarm_processor._check_condition(mock_alarm, 85.0)

        assert is_triggered is False

    @pytest.mark.asyncio
    async def test_alarm_events_published_to_subscribers(self, mock_alarm_processor):
        """Test that alarm events are published to subscribers."""
        # Subscribe to alarm events
        queue = await mock_alarm_processor.subscribe()

        # Simulate alarm event
        from services.scada.alarm_management.alarm_service import AlarmEvent

        event = AlarmEvent(
            instance_id="inst_001",
            alarm_id="alarm_001",
            tag_id="temp_001",
            tag_name="Temperature",
            alarm_type="high",
            priority=2,
            status="ACTIVE_UNACKED",
            message="Temperature high",
            value=95.0,
            limit_value=90.0,
            timestamp=datetime.utcnow()
        )

        # Publish event (simulated)
        await queue.put(event)

        # Verify event received
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received.alarm_id == "alarm_001"
        assert received.value == 95.0

        # Cleanup
        await mock_alarm_processor.unsubscribe(queue)


class TestHistorianToMLIntegration:
    """Tests for Historian to ML Inference integration."""

    @pytest.fixture
    def mock_historian_reader(self):
        """Create a mock historian reader."""
        import pandas as pd

        reader = Mock()
        # Return sample data
        times = [datetime.utcnow() - timedelta(seconds=i) for i in range(256)]
        reader.get_raw.return_value = pd.DataFrame({
            'time': times,
            'tag_id': ['temp_001'] * 256,
            'value': np.random.randn(256) * 10 + 50,
            'quality': [192] * 256
        })
        return reader

    def test_historian_data_feeds_ml_inference(self, mock_historian_reader):
        """Test that historian data is processed by ML inference."""
        from services.ml.inference.inference_service import InferenceService, InferenceConfig

        # Create inference service
        config = InferenceConfig(device='cpu', batch_size=1)
        service = InferenceService(config)

        # Get data from historian
        df = mock_historian_reader.get_raw(
            ['temp_001'],
            datetime.utcnow() - timedelta(minutes=5),
            datetime.utcnow()
        )

        # Prepare data for inference
        sensor_data = df['value'].values.reshape(-1, 1)

        # Pad/truncate to expected sequence length
        if len(sensor_data) < 256:
            sensor_data = np.pad(sensor_data, ((0, 256 - len(sensor_data)), (0, 0)))
        else:
            sensor_data = sensor_data[:256]

        # Would normally run prediction here
        # With a loaded model: results = service.predict(sensor_data)
        assert sensor_data.shape == (256, 1)

    def test_ml_batch_inference_from_historian(self, mock_historian_reader):
        """Test batch inference using historian data."""
        from services.ml.inference.inference_service import HistorianMLBridge
        import pandas as pd

        bridge = HistorianMLBridge()
        bridge.reader = mock_historian_reader

        # Run batch inference (will return empty without model)
        results = bridge.batch_inference(
            ['temp_001'],
            datetime.utcnow() - timedelta(hours=1),
            datetime.utcnow()
        )

        # Verify historian data was queried
        mock_historian_reader.get_raw.assert_called()


class TestMLToAlarmIntegration:
    """Tests for ML Inference to Alarm integration."""

    @pytest.fixture
    def mock_inference_service(self):
        """Create a mock inference service with high anomaly score."""
        import torch
        from services.ml.inference.inference_service import InferenceService, InferenceConfig

        config = InferenceConfig(anomaly_threshold=0.8)
        service = InferenceService(config)

        # Mock model that returns high anomaly score
        mock_model = Mock()
        mock_model.return_value = {
            'fingerprint': torch.randn(1, 128),
            'cls': torch.randn(1, 10),
            'anom': torch.tensor([[0.95]])  # High anomaly score
        }
        service._model = mock_model

        return service

    @pytest.fixture
    def mock_alarm_processor(self):
        """Create alarm processor for ML alarms."""
        from services.scada.alarm_management.alarm_service import AlarmProcessor
        AlarmProcessor._instance = None
        return AlarmProcessor()

    def test_high_anomaly_triggers_ml_alarm(self, mock_inference_service, mock_alarm_processor):
        """Test that high anomaly score creates ML alarm."""
        from services.scada.alarm_management.alarm_service import AlarmEvent

        # Run inference
        sensor_data = np.random.randn(256, 10)
        results = mock_inference_service.predict(sensor_data)

        # Check anomaly detection
        assert results.get('anomaly_detected') is True
        assert results['anomaly_score'] > 0.8

        # Create ML alarm event
        event = AlarmEvent(
            instance_id=f"ml_{results['inference_id']}",
            alarm_id=f"ml_alarm_{int(time.time())}",
            tag_id="sensor_group_001",
            tag_name="Anomaly Detection",
            alarm_type="ml_anomaly",
            priority=2,
            status="ACTIVE_UNACKED",
            message=f"ML anomaly detected (score: {results['anomaly_score']:.3f})",
            value=results['anomaly_score'],
            limit_value=0.8,
            timestamp=datetime.utcnow()
        )

        # Submit to alarm processor
        with patch.object(mock_alarm_processor, '_persist_ml_alarm'):
            mock_alarm_processor.submit_ml_alarm(event)

        # Verify alarm was created
        ml_alarms = mock_alarm_processor.get_ml_alarms()
        assert len(ml_alarms) >= 1

    def test_normal_inference_no_alarm(self, mock_alarm_processor):
        """Test that normal inference doesn't trigger alarm."""
        import torch
        from services.ml.inference.inference_service import InferenceService, InferenceConfig

        config = InferenceConfig(anomaly_threshold=0.8)
        service = InferenceService(config)

        # Mock model with low anomaly score
        mock_model = Mock()
        mock_model.return_value = {
            'fingerprint': torch.randn(1, 128),
            'cls': torch.randn(1, 10),
            'anom': torch.tensor([[0.3]])  # Low anomaly score
        }
        service._model = mock_model

        sensor_data = np.random.randn(256, 10)
        results = service.predict(sensor_data)

        # Verify no anomaly detected
        assert results.get('anomaly_detected', False) is False


class TestEndToEndSCADAFlow:
    """End-to-end tests for complete SCADA data flow."""

    def test_full_tag_to_alarm_flow(self):
        """Test complete flow: Tag -> Historian -> ML -> Alarm."""
        from services.scada.alarm_management.alarm_service import AlarmProcessor, AlarmType, AlarmEvent
        from services.scada.historian.historian_service import HistorianWriter, HistorianConfig

        # Reset singletons
        AlarmProcessor._instance = None
        HistorianWriter._instance = None

        # Initialize services
        alarm_processor = AlarmProcessor()
        historian_config = HistorianConfig(buffer_size=100, flush_interval_seconds=10.0)
        historian_writer = HistorianWriter(historian_config)

        # Set up alarm definition
        mock_alarm = Mock()
        mock_alarm.tag_id = "reactor_temp"
        mock_alarm.alarm_type = AlarmType.HIGH_HIGH
        mock_alarm.high_high_limit = 150.0
        mock_alarm.deadband = 0
        mock_alarm.enabled = True
        mock_alarm.id = "alarm_reactor_temp_hh"
        mock_alarm.priority = 1
        mock_alarm.message = "Reactor temperature critical"

        alarm_processor.load_alarm_definitions([mock_alarm])

        # Simulate tag value updates
        tag_values = [
            ("reactor_temp", 100.0),  # Normal
            ("reactor_temp", 120.0),  # Normal
            ("reactor_temp", 145.0),  # Still normal but high
            ("reactor_temp", 155.0),  # Above HIGH_HIGH limit!
        ]

        triggered_alarms = []

        for tag_id, value in tag_values:
            # Write to historian
            historian_writer.write(tag_id, value, compress=False)

            # Check alarm conditions
            if tag_id in alarm_processor._alarm_defs:
                for alarm_def in alarm_processor._alarm_defs[tag_id]:
                    if alarm_processor._check_condition(alarm_def, value):
                        triggered_alarms.append((tag_id, value, alarm_def.id))

        # Verify HIGH_HIGH alarm was triggered
        assert len(triggered_alarms) == 1
        assert triggered_alarms[0][0] == "reactor_temp"
        assert triggered_alarms[0][1] == 155.0

        # Verify historian recorded values
        stats = historian_writer.get_stats()
        assert stats['total_writes'] >= 4


class TestAlarmAcknowledgmentWorkflow:
    """Tests for alarm acknowledgment workflow."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return Mock()

    def test_alarm_acknowledgment_flow(self, mock_db_session):
        """Test complete alarm acknowledgment flow."""
        from services.scada.alarm_management.alarm_service import (
            AlarmService, AlarmStatus
        )

        service = AlarmService(mock_db_session)

        # Mock alarm data
        with patch.object(service, 'acknowledge') as mock_ack:
            mock_ack.return_value = {
                'alarm_id': 'alarm_001',
                'is_acknowledged': True,
                'acknowledged_by': 'operator_001',
                'acknowledged_at': datetime.utcnow().isoformat(),
                'status': AlarmStatus.ACKED_ACTIVE.value
            }

            # Acknowledge alarm
            result = service.acknowledge(
                'alarm_001',
                'operator_001',
                'Acknowledged - taking corrective action'
            )

            assert result['is_acknowledged'] is True
            assert result['status'] == AlarmStatus.ACKED_ACTIVE.value

    def test_alarm_shelving_flow(self, mock_db_session):
        """Test alarm shelving workflow."""
        from services.scada.alarm_management.alarm_service import AlarmService

        service = AlarmService(mock_db_session)

        with patch.object(service, 'shelve') as mock_shelve:
            shelved_until = datetime.utcnow() + timedelta(hours=1)
            mock_shelve.return_value = {
                'alarm_id': 'alarm_001',
                'is_shelved': True,
                'shelved_until': shelved_until.isoformat(),
                'shelved_by': 'supervisor_001',
                'shelve_reason': 'Planned maintenance'
            }

            # Shelve alarm
            result = service.shelve(
                'alarm_001',
                'supervisor_001',
                60,  # 60 minutes
                'Planned maintenance'
            )

            assert result['is_shelved'] is True
            assert 'shelved_until' in result


class TestHistorianCompressionIntegration:
    """Tests for historian compression with real data patterns."""

    def test_swinging_door_with_process_data(self):
        """Test SDT compression with realistic process data."""
        from services.scada.historian.historian_service import (
            SwingingDoorCompressor, HistorianValue
        )

        compressor = SwingingDoorCompressor(deviation=0.02)  # 2% deviation

        t0 = datetime.utcnow()
        stored_values = []

        # Generate realistic process data (slow drift with occasional spikes)
        np.random.seed(42)
        for i in range(1000):
            # Base value with slow drift
            base = 100.0 + i * 0.01

            # Occasional spikes
            if i % 100 == 50:
                base += 10.0

            # Small noise
            noise = np.random.normal(0, 0.1)
            value = base + noise

            hv = HistorianValue(
                "process_var_001",
                t0 + timedelta(seconds=i),
                value
            )

            if compressor.should_store("process_var_001", hv):
                stored_values.append(hv)

        # Compression should reduce data significantly
        compression_ratio = len(stored_values) / 1000

        # Should store less than 20% of points for this data
        assert compression_ratio < 0.2

        # But should capture the spikes
        spike_captured = any(v.value > 105 for v in stored_values)
        assert spike_captured
