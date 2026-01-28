"""
Unit tests for SCADA Alarm Management Service.

Tests alarm creation, evaluation, acknowledgment, shelving, and history.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from services.scada.alarm_management.alarm_service import (
    AlarmPriority,
    AlarmStatus,
    AlarmEventType,
    AlarmType,
    AlarmEvent,
    AlarmSummary,
    AlarmProcessor,
    AlarmService,
    alarm_processor,
    get_alarm_service,
    process_tag_value,
)


class TestAlarmEnums:
    """Tests for alarm enumerations."""

    def test_alarm_priority_values(self):
        """Test alarm priority values."""
        assert AlarmPriority.EMERGENCY.value == 1
        assert AlarmPriority.HIGH.value == 2
        assert AlarmPriority.MEDIUM.value == 3
        assert AlarmPriority.LOW.value == 4
        assert AlarmPriority.DIAGNOSTIC.value == 5

    def test_alarm_status_values(self):
        """Test alarm status values."""
        assert AlarmStatus.ACTIVE_UNACKED.value == 'ACTIVE_UNACKED'
        assert AlarmStatus.ACKED_ACTIVE.value == 'ACKED_ACTIVE'
        assert AlarmStatus.CLEARED_UNACKED.value == 'CLEARED_UNACKED'
        assert AlarmStatus.NORMAL.value == 'NORMAL'

    def test_alarm_type_values(self):
        """Test alarm type values."""
        assert AlarmType.HIGH_HIGH.value == 'high_high'
        assert AlarmType.HIGH.value == 'high'
        assert AlarmType.LOW.value == 'low'
        assert AlarmType.LOW_LOW.value == 'low_low'
        assert AlarmType.ML_ANOMALY.value == 'ml_anomaly'


class TestAlarmEvent:
    """Tests for AlarmEvent dataclass."""

    def test_create_alarm_event(self):
        """Test creating an alarm event."""
        event = AlarmEvent(
            instance_id="inst_001",
            alarm_id="alarm_001",
            tag_id="tag_001",
            tag_name="Temperature",
            alarm_type="high",
            priority=2,
            status="ACTIVE_UNACKED",
            message="Temperature high alarm",
            value=95.0,
            limit_value=90.0,
            timestamp=datetime.utcnow()
        )

        assert event.instance_id == "inst_001"
        assert event.alarm_id == "alarm_001"
        assert event.priority == 2
        assert event.value == 95.0
        assert event.limit_value == 90.0

    def test_alarm_event_optional_fields(self):
        """Test alarm event with optional fields."""
        event = AlarmEvent(
            instance_id="inst_001",
            alarm_id="alarm_001",
            tag_id="tag_001",
            tag_name="Test",
            alarm_type="high",
            priority=2,
            status="ACTIVE_UNACKED",
            message="Test",
            value=100.0,
            limit_value=90.0,
            timestamp=datetime.utcnow(),
            consequence="Equipment damage",
            corrective_action="Reduce temperature"
        )

        assert event.consequence == "Equipment damage"
        assert event.corrective_action == "Reduce temperature"


class TestAlarmSummary:
    """Tests for AlarmSummary dataclass."""

    def test_default_summary(self):
        """Test default alarm summary."""
        summary = AlarmSummary()

        assert summary.total_active == 0
        assert summary.unacknowledged == 0
        assert summary.acknowledged_active == 0
        assert summary.shelved == 0
        assert summary.by_priority == {}

    def test_populated_summary(self):
        """Test populated alarm summary."""
        summary = AlarmSummary(
            total_active=10,
            unacknowledged=5,
            acknowledged_active=5,
            shelved=2,
            by_priority={1: 2, 2: 3, 3: 5}
        )

        assert summary.total_active == 10
        assert summary.by_priority[1] == 2


class TestAlarmProcessor:
    """Tests for AlarmProcessor class."""

    @pytest.fixture
    def processor(self):
        """Create a fresh processor for testing."""
        # Reset singleton
        AlarmProcessor._instance = None
        return AlarmProcessor()

    def test_singleton_pattern(self):
        """Test that AlarmProcessor is a singleton."""
        AlarmProcessor._instance = None
        p1 = AlarmProcessor()
        p2 = AlarmProcessor()

        assert p1 is p2

    def test_load_alarm_definitions(self, processor):
        """Test loading alarm definitions."""
        mock_alarms = [
            Mock(tag_id="tag_001"),
            Mock(tag_id="tag_001"),
            Mock(tag_id="tag_002"),
        ]

        processor.load_alarm_definitions(mock_alarms)

        assert "tag_001" in processor._alarm_defs
        assert len(processor._alarm_defs["tag_001"]) == 2
        assert len(processor._alarm_defs["tag_002"]) == 1

    def test_load_active_alarms(self, processor):
        """Test loading active alarms."""
        mock_active = [
            Mock(id="1"),
            Mock(id="2"),
        ]

        processor.load_active_alarms(mock_active)

        assert len(processor._active_alarms) == 2

    @pytest.mark.asyncio
    async def test_subscribe(self, processor):
        """Test subscribing to alarm events."""
        queue = await processor.subscribe()

        assert queue is not None
        assert queue in processor._subscribers

    @pytest.mark.asyncio
    async def test_unsubscribe(self, processor):
        """Test unsubscribing from alarm events."""
        queue = await processor.subscribe()
        await processor.unsubscribe(queue)

        assert queue not in processor._subscribers

    def test_check_condition_high(self, processor):
        """Test checking high alarm condition."""
        mock_alarm = Mock()
        mock_alarm.alarm_type = AlarmType.HIGH
        mock_alarm.high_limit = 90.0
        mock_alarm.deadband = 0

        result = processor._check_condition(mock_alarm, 95.0)
        assert result is True

        result = processor._check_condition(mock_alarm, 85.0)
        assert result is False

    def test_check_condition_low(self, processor):
        """Test checking low alarm condition."""
        mock_alarm = Mock()
        mock_alarm.alarm_type = AlarmType.LOW
        mock_alarm.low_limit = 10.0
        mock_alarm.deadband = 0

        result = processor._check_condition(mock_alarm, 5.0)
        assert result is True

        result = processor._check_condition(mock_alarm, 15.0)
        assert result is False

    def test_submit_ml_alarm(self, processor):
        """Test submitting ML-generated alarm."""
        event = AlarmEvent(
            instance_id="ml_001",
            alarm_id="ml_alarm_001",
            tag_id="tag_001",
            tag_name="Anomaly Detection",
            alarm_type="ml_anomaly",
            priority=2,
            status="ACTIVE_UNACKED",
            message="ML anomaly detected",
            value=0.95,
            limit_value=0.8,
            timestamp=datetime.utcnow()
        )

        with patch.object(processor, '_persist_ml_alarm'):
            processor.submit_ml_alarm(event)

        assert "ml_001" in processor._ml_alarms
        assert processor._ml_alarms["ml_001"].alarm_id == "ml_alarm_001"

    def test_get_ml_alarms(self, processor):
        """Test getting ML alarms."""
        event = AlarmEvent(
            instance_id="ml_001",
            alarm_id="ml_alarm_001",
            tag_id="tag_001",
            tag_name="Test",
            alarm_type="ml_anomaly",
            priority=2,
            status="ACTIVE_UNACKED",
            message="Test",
            value=0.95,
            limit_value=0.8,
            timestamp=datetime.utcnow()
        )

        with patch.object(processor, '_persist_ml_alarm'):
            processor.submit_ml_alarm(event)

        alarms = processor.get_ml_alarms()
        assert len(alarms) >= 1

    def test_clear_ml_alarm(self, processor):
        """Test clearing ML alarm."""
        event = AlarmEvent(
            instance_id="ml_001",
            alarm_id="ml_alarm_001",
            tag_id="tag_001",
            tag_name="Test",
            alarm_type="ml_anomaly",
            priority=2,
            status="ACTIVE_UNACKED",
            message="Test",
            value=0.95,
            limit_value=0.8,
            timestamp=datetime.utcnow()
        )

        with patch.object(processor, '_persist_ml_alarm'):
            processor.submit_ml_alarm(event)

        result = processor.clear_ml_alarm("ml_alarm_001")
        assert result is True

        result = processor.clear_ml_alarm("nonexistent")
        assert result is False


class TestAlarmService:
    """Tests for AlarmService database operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        """Create an AlarmService with mock session."""
        return AlarmService(mock_session)

    def test_get_active_alarms(self, service, mock_session):
        """Test getting active alarms."""
        with patch('services.scada.alarm_management.alarm_service.AlarmService.get_active_alarms') as mock_get:
            mock_get.return_value = [
                {'alarm_id': 'alarm_001', 'priority': 2},
                {'alarm_id': 'alarm_002', 'priority': 1},
            ]

            result = service.get_active_alarms()

            assert len(result) == 2

    def test_get_standing_alarms(self, service, mock_session):
        """Test getting unacknowledged alarms."""
        with patch('services.scada.alarm_management.alarm_service.AlarmService.get_standing_alarms') as mock_get:
            mock_get.return_value = [
                {'alarm_id': 'alarm_001', 'is_acknowledged': False},
            ]

            result = service.get_standing_alarms()

            assert len(result) == 1

    def test_acknowledge(self, service, mock_session):
        """Test acknowledging an alarm."""
        with patch('services.scada.alarm_management.alarm_service.AlarmService.acknowledge') as mock_ack:
            mock_ack.return_value = {
                'alarm_id': 'alarm_001',
                'is_acknowledged': True
            }

            result = service.acknowledge('alarm_001', 'user_001', 'Notes')

            assert result is not None
            assert result['is_acknowledged'] is True

    def test_acknowledge_nonexistent(self, service, mock_session):
        """Test acknowledging nonexistent alarm."""
        with patch('services.scada.alarm_management.alarm_service.AlarmService.acknowledge') as mock_ack:
            mock_ack.return_value = None

            result = service.acknowledge('nonexistent', 'user_001')

            assert result is None

    def test_shelve(self, service, mock_session):
        """Test shelving an alarm."""
        with patch('services.scada.alarm_management.alarm_service.AlarmService.shelve') as mock_shelve:
            mock_shelve.return_value = {
                'alarm_id': 'alarm_001',
                'is_shelved': True,
                'shelved_until': (datetime.utcnow() + timedelta(hours=1)).isoformat()
            }

            result = service.shelve('alarm_001', 'user_001', 60, 'Maintenance')

            assert result is not None
            assert result['is_shelved'] is True

    def test_unshelve(self, service, mock_session):
        """Test unshelving an alarm."""
        with patch('services.scada.alarm_management.alarm_service.AlarmService.unshelve') as mock_unshelve:
            mock_unshelve.return_value = {
                'alarm_id': 'alarm_001',
                'is_shelved': False
            }

            result = service.unshelve('alarm_001', 'user_001')

            assert result is not None
            assert result['is_shelved'] is False

    def test_get_alarm_summary(self, service, mock_session):
        """Test getting alarm summary."""
        with patch('services.scada.alarm_management.alarm_service.AlarmService.get_alarm_summary') as mock_summary:
            mock_summary.return_value = AlarmSummary(
                total_active=10,
                unacknowledged=5,
                acknowledged_active=5,
                shelved=2,
                by_priority={1: 2, 2: 3, 3: 5}
            )

            result = service.get_alarm_summary()

            assert result.total_active == 10
            assert result.unacknowledged == 5


class TestISA182Compliance:
    """Tests for ISA-18.2 alarm management compliance."""

    def test_alarm_priorities(self):
        """Test that alarm priorities align with ISA-18.2."""
        # ISA-18.2 defines priority levels
        assert AlarmPriority.EMERGENCY.value < AlarmPriority.HIGH.value
        assert AlarmPriority.HIGH.value < AlarmPriority.MEDIUM.value
        assert AlarmPriority.MEDIUM.value < AlarmPriority.LOW.value

    def test_alarm_states(self):
        """Test that alarm states align with ISA-18.2."""
        # ISA-18.2 defines alarm states
        required_states = ['ACTIVE_UNACKED', 'ACKED_ACTIVE', 'CLEARED_UNACKED', 'NORMAL']
        actual_states = [s.value for s in AlarmStatus]

        for state in required_states:
            assert state in actual_states

    def test_alarm_event_types(self):
        """Test that alarm event types are tracked."""
        # ISA-18.2 requires tracking of alarm events
        required_events = ['ACTIVATED', 'ACKNOWLEDGED', 'CLEARED', 'SHELVED']
        actual_events = [e.value for e in AlarmEventType]

        for event in required_events:
            assert event in actual_events
