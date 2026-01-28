"""
LEGO Factory v3 - Anomaly Detection to Alarm Integration Tests
==============================================================
Integration tests demonstrating the complete flow from tag value
through anomaly detection to ISA-18.2 alarm generation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import uuid

from services.ml.anomaly.anomaly_types import (
    AnomalySeverity,
    AnomalyCategory,
    AnomalyType,
    AnomalyResult,
    AnomalyConfig,
    ThresholdConfig,
)
from services.ml.anomaly.anomaly_detection_service import (
    AnomalyDetectionService,
    anomaly_detection_service,
)
from services.ml.anomaly.alarm_integration import (
    generate_alarm_from_anomaly,
    SEVERITY_TO_PRIORITY,
    CATEGORY_TO_ALARM_TYPE,
)
from services.ml.anomaly.realtime_hook import (
    RealtimeAnomalyHook,
    HookConfig,
    TagValueEvent,
)


class TestAnomalyToAlarmFlow:
    """
    Integration tests for the complete flow:
    Tag value -> Anomaly Detection -> ISA-18.2 Alarm Generation
    """

    @pytest.fixture
    def detection_service(self):
        """Create a fresh anomaly detection service for testing."""
        # Create a new instance for testing (bypass singleton)
        service = AnomalyDetectionService.__new__(AnomalyDetectionService)
        service._initialized = False
        service.__init__()

        # Configure for testing
        config = AnomalyConfig(
            enabled=True,
            window_size=50,
            min_samples=10,
            generate_alarms=True,
            alarm_cooldown_seconds=0,  # No cooldown for testing
            use_threshold_detection=True,
            use_statistical_detection=True,
        )
        service.configure(config)

        return service

    @pytest.fixture
    def sample_anomaly_result(self):
        """Create a sample anomaly result for testing."""
        return AnomalyResult(
            anomaly_id=str(uuid.uuid4()),
            tag_id="TAG-TEMP-001",
            tag_name="Extruder Temperature",
            is_anomaly=True,
            anomaly_score=0.85,
            severity=AnomalySeverity.HIGH,
            category=AnomalyCategory.OUT_OF_RANGE,
            detection_type=AnomalyType.THRESHOLD_HIGH,
            value=95.5,
            expected_value=75.0,
            threshold_violated=90.0,
            timestamp=datetime.utcnow(),
            message="Extruder Temperature value 95.5 exceeded threshold 90.0",
            confidence=0.95,
        )

    def test_severity_to_priority_mapping(self):
        """Verify severity levels map correctly to ISA-18.2 priorities."""
        assert SEVERITY_TO_PRIORITY[AnomalySeverity.CRITICAL] == 1  # EMERGENCY
        assert SEVERITY_TO_PRIORITY[AnomalySeverity.HIGH] == 2      # HIGH
        assert SEVERITY_TO_PRIORITY[AnomalySeverity.MEDIUM] == 3    # MEDIUM
        assert SEVERITY_TO_PRIORITY[AnomalySeverity.LOW] == 4       # LOW
        assert SEVERITY_TO_PRIORITY[AnomalySeverity.INFO] == 4      # LOW

    def test_category_to_alarm_type_mapping(self):
        """Verify anomaly categories map to appropriate alarm types."""
        assert CATEGORY_TO_ALARM_TYPE[AnomalyCategory.SPIKE] == 'rate_of_change'
        assert CATEGORY_TO_ALARM_TYPE[AnomalyCategory.DRIFT] == 'deviation'
        assert CATEGORY_TO_ALARM_TYPE[AnomalyCategory.OUT_OF_RANGE] == 'high'
        assert CATEGORY_TO_ALARM_TYPE[AnomalyCategory.PATTERN] == 'ml_anomaly'
        assert CATEGORY_TO_ALARM_TYPE[AnomalyCategory.FLATLINE] == 'bad_quality'

    @patch('services.ml.anomaly.alarm_integration.alarm_processor')
    def test_generate_alarm_from_anomaly(self, mock_processor, sample_anomaly_result):
        """Test alarm generation from anomaly result."""
        alarm_data = generate_alarm_from_anomaly(sample_anomaly_result)

        assert alarm_data is not None
        assert alarm_data['tag_id'] == sample_anomaly_result.tag_id
        assert alarm_data['tag_name'] == sample_anomaly_result.tag_name
        assert alarm_data['priority'] == 2  # HIGH severity -> priority 2
        assert alarm_data['value'] == sample_anomaly_result.value
        assert alarm_data['anomaly_score'] == sample_anomaly_result.anomaly_score
        assert alarm_data['anomaly_category'] == AnomalyCategory.OUT_OF_RANGE.value
        assert 'alarm_id' in alarm_data
        assert 'message' in alarm_data

        # Verify alarm was submitted to processor
        mock_processor.submit_ml_alarm.assert_called_once()

    @patch('services.ml.anomaly.alarm_integration.alarm_processor')
    def test_alarm_priority_based_on_severity(self, mock_processor):
        """Test that alarm priority correctly reflects anomaly severity."""
        severities = [
            (AnomalySeverity.CRITICAL, 1),
            (AnomalySeverity.HIGH, 2),
            (AnomalySeverity.MEDIUM, 3),
            (AnomalySeverity.LOW, 4),
        ]

        for severity, expected_priority in severities:
            anomaly = AnomalyResult(
                tag_id="TAG-001",
                tag_name="Test Tag",
                is_anomaly=True,
                anomaly_score=0.9,
                severity=severity,
                category=AnomalyCategory.OUT_OF_RANGE,
                detection_type=AnomalyType.THRESHOLD_HIGH,
                value=100.0,
                timestamp=datetime.utcnow(),
            )

            alarm_data = generate_alarm_from_anomaly(anomaly)

            assert alarm_data['priority'] == expected_priority, \
                f"Severity {severity.name} should map to priority {expected_priority}"

    @patch('services.ml.anomaly.alarm_integration.alarm_processor')
    def test_alarm_type_determination_out_of_range_high(self, mock_processor):
        """Test alarm type for high out-of-range anomalies."""
        anomaly = AnomalyResult(
            tag_id="TAG-001",
            tag_name="Test Tag",
            is_anomaly=True,
            anomaly_score=0.9,
            severity=AnomalySeverity.CRITICAL,
            category=AnomalyCategory.OUT_OF_RANGE,
            detection_type=AnomalyType.THRESHOLD_HIGH,
            value=100.0,
            expected_value=50.0,  # Value is above expected
            timestamp=datetime.utcnow(),
        )

        alarm_data = generate_alarm_from_anomaly(anomaly)

        # Critical high should be 'high_high'
        assert alarm_data['alarm_type'] == 'high_high'

    @patch('services.ml.anomaly.alarm_integration.alarm_processor')
    def test_alarm_type_determination_out_of_range_low(self, mock_processor):
        """Test alarm type for low out-of-range anomalies."""
        anomaly = AnomalyResult(
            tag_id="TAG-001",
            tag_name="Test Tag",
            is_anomaly=True,
            anomaly_score=0.9,
            severity=AnomalySeverity.CRITICAL,
            category=AnomalyCategory.OUT_OF_RANGE,
            detection_type=AnomalyType.THRESHOLD_LOW,
            value=10.0,
            expected_value=50.0,  # Value is below expected
            timestamp=datetime.utcnow(),
        )

        alarm_data = generate_alarm_from_anomaly(anomaly)

        # Critical low should be 'low_low'
        assert alarm_data['alarm_type'] == 'low_low'


class TestRealtimeHookAlarmGeneration:
    """Test alarm generation through the real-time hook."""

    @pytest.fixture
    def hook(self):
        """Create a fresh realtime hook for testing."""
        hook = RealtimeAnomalyHook.__new__(RealtimeAnomalyHook)
        hook._initialized = False
        hook.__init__()

        # Configure for testing
        config = HookConfig(
            enabled=True,
            generate_alarms=True,
            min_severity_for_alarm=AnomalySeverity.MEDIUM,
            min_severity_for_callback=AnomalySeverity.LOW,
        )
        hook.configure(config)

        return hook

    @patch('services.ml.anomaly.realtime_hook.generate_alarm_from_anomaly')
    @patch('services.ml.anomaly.realtime_hook.anomaly_detection_service')
    def test_alarm_generated_on_anomaly_detection(
        self, mock_detection_service, mock_generate_alarm, hook
    ):
        """Test that alarms are generated when anomalies are detected."""
        # Create a mock anomaly result
        mock_result = AnomalyResult(
            tag_id="TAG-001",
            tag_name="Test Tag",
            is_anomaly=True,
            anomaly_score=0.85,
            severity=AnomalySeverity.HIGH,  # Above min_severity_for_alarm
            category=AnomalyCategory.OUT_OF_RANGE,
            detection_type=AnomalyType.THRESHOLD_HIGH,
            value=100.0,
            timestamp=datetime.utcnow(),
        )

        mock_detection_service.detect_realtime.return_value = mock_result
        mock_generate_alarm.return_value = {'alarm_id': 'TEST-001'}

        # Process a value
        hook._detection_service = mock_detection_service
        result = hook.process("TAG-001", 100.0, tag_name="Test Tag")

        # Verify alarm generation was called
        mock_generate_alarm.assert_called_once_with(mock_result)
        assert hook._stats['alarms_generated'] == 1

    @patch('services.ml.anomaly.realtime_hook.generate_alarm_from_anomaly')
    @patch('services.ml.anomaly.realtime_hook.anomaly_detection_service')
    def test_no_alarm_below_severity_threshold(
        self, mock_detection_service, mock_generate_alarm, hook
    ):
        """Test that alarms are not generated for low severity anomalies."""
        # Create a low severity anomaly
        mock_result = AnomalyResult(
            tag_id="TAG-001",
            tag_name="Test Tag",
            is_anomaly=True,
            anomaly_score=0.55,
            severity=AnomalySeverity.LOW,  # Below min_severity_for_alarm (MEDIUM)
            category=AnomalyCategory.OUT_OF_RANGE,
            detection_type=AnomalyType.THRESHOLD_HIGH,
            value=80.0,
            timestamp=datetime.utcnow(),
        )

        mock_detection_service.detect_realtime.return_value = mock_result

        # Process a value
        hook._detection_service = mock_detection_service
        result = hook.process("TAG-001", 80.0, tag_name="Test Tag")

        # Verify alarm generation was NOT called
        mock_generate_alarm.assert_not_called()
        assert hook._stats['alarms_generated'] == 0

    @patch('services.ml.anomaly.realtime_hook.generate_alarm_from_anomaly')
    @patch('services.ml.anomaly.realtime_hook.anomaly_detection_service')
    def test_alarm_disabled_in_config(
        self, mock_detection_service, mock_generate_alarm, hook
    ):
        """Test that alarms are not generated when disabled in config."""
        # Disable alarm generation
        hook._config.generate_alarms = False

        mock_result = AnomalyResult(
            tag_id="TAG-001",
            tag_name="Test Tag",
            is_anomaly=True,
            anomaly_score=0.95,
            severity=AnomalySeverity.CRITICAL,
            category=AnomalyCategory.OUT_OF_RANGE,
            detection_type=AnomalyType.THRESHOLD_HIGH,
            value=150.0,
            timestamp=datetime.utcnow(),
        )

        mock_detection_service.detect_realtime.return_value = mock_result

        # Process a value
        hook._detection_service = mock_detection_service
        result = hook.process("TAG-001", 150.0, tag_name="Test Tag")

        # Verify alarm generation was NOT called
        mock_generate_alarm.assert_not_called()

    def test_hook_stats_include_alarm_info(self, hook):
        """Test that hook stats include alarm generation information."""
        stats = hook.get_stats()

        assert 'alarms_generated' in stats
        assert 'config' in stats
        assert 'generate_alarms' in stats['config']
        assert 'min_severity_for_alarm' in stats['config']


class TestEndToEndFlow:
    """End-to-end integration tests showing complete flow."""

    @patch('services.ml.anomaly.alarm_integration.alarm_processor')
    def test_complete_flow_threshold_violation(self, mock_processor):
        """
        Test complete flow: tag value -> anomaly detection -> alarm.

        Simulates a real scenario where a temperature sensor exceeds
        its configured threshold, triggering an ISA-18.2 alarm.
        """
        # 1. Configure anomaly detection for the tag
        detection_service = AnomalyDetectionService.__new__(AnomalyDetectionService)
        detection_service._initialized = False
        detection_service.__init__()

        config = AnomalyConfig(
            enabled=True,
            window_size=50,
            min_samples=5,
            generate_alarms=True,
            alarm_cooldown_seconds=0,
            use_threshold_detection=True,
        )
        detection_service.configure(config)

        # Set threshold for the tag
        tag_config = ThresholdConfig(
            high=85.0,
            high_high=95.0,
            low=15.0,
            low_low=5.0,
        )
        config.set_tag_config("TAG-TEMP-001", tag_config)
        detection_service.configure(config)

        # 2. Simulate normal values to build baseline
        for i in range(10):
            detection_service.detect_realtime(
                tag_id="TAG-TEMP-001",
                value=50.0 + (i % 5),  # Normal values around 50
                timestamp=datetime.utcnow() - timedelta(seconds=10-i),
                tag_name="Extruder Temperature"
            )

        # 3. Process a threshold-violating value
        result = detection_service.detect_realtime(
            tag_id="TAG-TEMP-001",
            value=96.0,  # Above high_high threshold
            timestamp=datetime.utcnow(),
            tag_name="Extruder Temperature"
        )

        # 4. Verify anomaly was detected
        assert result is not None
        assert result.is_anomaly is True
        assert result.severity >= AnomalySeverity.HIGH
        assert result.category == AnomalyCategory.OUT_OF_RANGE

        # 5. Generate alarm
        alarm_data = generate_alarm_from_anomaly(result)

        # 6. Verify alarm properties
        assert alarm_data is not None
        assert alarm_data['tag_id'] == "TAG-TEMP-001"
        assert alarm_data['priority'] in [1, 2]  # HIGH or EMERGENCY
        assert alarm_data['value'] == 96.0
        assert 'threshold' in alarm_data['message'].lower() or '96' in alarm_data['message']

        # 7. Verify alarm was submitted to processor
        mock_processor.submit_ml_alarm.assert_called()

    @patch('services.ml.anomaly.alarm_integration.alarm_processor')
    def test_complete_flow_statistical_anomaly(self, mock_processor):
        """
        Test complete flow for statistical (z-score) anomaly detection.

        Simulates detecting an outlier based on statistical deviation.
        """
        detection_service = AnomalyDetectionService.__new__(AnomalyDetectionService)
        detection_service._initialized = False
        detection_service.__init__()

        config = AnomalyConfig(
            enabled=True,
            window_size=100,
            min_samples=30,
            generate_alarms=True,
            alarm_cooldown_seconds=0,
            use_statistical_detection=True,
            zscore_threshold=3.0,
        )
        detection_service.configure(config)

        # Build baseline with normal values (mean=50, std~5)
        import random
        random.seed(42)
        for i in range(50):
            value = 50.0 + random.gauss(0, 5)
            detection_service.detect_realtime(
                tag_id="TAG-PRESSURE-001",
                value=value,
                timestamp=datetime.utcnow() - timedelta(seconds=50-i),
                tag_name="Mold Pressure"
            )

        # Process a statistical outlier (more than 3 sigma)
        result = detection_service.detect_realtime(
            tag_id="TAG-PRESSURE-001",
            value=80.0,  # Way above mean of 50
            timestamp=datetime.utcnow(),
            tag_name="Mold Pressure"
        )

        # Verify anomaly was detected
        assert result is not None
        assert result.is_anomaly is True

        # Generate alarm
        alarm_data = generate_alarm_from_anomaly(result)

        assert alarm_data is not None
        assert alarm_data['tag_id'] == "TAG-PRESSURE-001"
        mock_processor.submit_ml_alarm.assert_called()


class TestAlarmProcessorIntegration:
    """Test integration with the alarm processor."""

    def test_alarm_processor_receives_ml_alarm(self):
        """Test that the alarm processor correctly receives ML alarms."""
        from services.scada.alarm_management.alarm_service import (
            AlarmProcessor,
            AlarmEvent,
            AlarmStatus,
        )

        # Create processor instance
        processor = AlarmProcessor.__new__(AlarmProcessor)
        processor._alarm_defs = {}
        processor._active_alarms = {}
        processor._pending_activations = {}
        processor._pending_clears = {}
        processor._subscribers = []
        processor._ml_alarms = {}

        # Create alarm event
        alarm_event = AlarmEvent(
            instance_id=str(uuid.uuid4()),
            alarm_id="ML_ANOMALY_TAG-001_out_of_range",
            tag_id="TAG-001",
            tag_name="Test Sensor",
            alarm_type="ml_anomaly",
            priority=2,
            status=AlarmStatus.ACTIVE_UNACKED.value,
            message="ML anomaly detected: out of range",
            value=100.0,
            limit_value=90.0,
            timestamp=datetime.utcnow(),
            consequence="Production quality at risk",
            corrective_action="Check sensor and process parameters",
        )

        # Mock database interaction
        with patch.object(processor, '_persist_ml_alarm'):
            with patch('services.scada.alarm_management.alarm_service._emit_alarm_event'):
                processor.submit_ml_alarm(alarm_event)

        # Verify alarm was stored
        assert len(processor._ml_alarms) == 1
        stored_alarm = list(processor._ml_alarms.values())[0]
        assert stored_alarm.alarm_id == alarm_event.alarm_id
        assert stored_alarm.tag_id == "TAG-001"
        assert stored_alarm.priority == 2

    def test_get_ml_alarms(self):
        """Test retrieving active ML alarms."""
        from services.scada.alarm_management.alarm_service import (
            AlarmProcessor,
            AlarmEvent,
            AlarmStatus,
        )

        processor = AlarmProcessor.__new__(AlarmProcessor)
        processor._ml_alarms = {}

        # Add some alarms
        for i in range(3):
            alarm = AlarmEvent(
                instance_id=str(uuid.uuid4()),
                alarm_id=f"ML_ANOMALY_TAG-{i}",
                tag_id=f"TAG-{i}",
                tag_name=f"Sensor {i}",
                alarm_type="ml_anomaly",
                priority=2,
                status=AlarmStatus.ACTIVE_UNACKED.value,
                message=f"Anomaly on sensor {i}",
                value=100.0 + i,
                limit_value=90.0,
                timestamp=datetime.utcnow(),
            )
            processor._ml_alarms[alarm.instance_id] = alarm

        # Retrieve alarms
        alarms = processor.get_ml_alarms()

        assert len(alarms) == 3
        tag_ids = [a.tag_id for a in alarms]
        assert "TAG-0" in tag_ids
        assert "TAG-1" in tag_ids
        assert "TAG-2" in tag_ids

    def test_clear_ml_alarm(self):
        """Test clearing an ML alarm."""
        from services.scada.alarm_management.alarm_service import (
            AlarmProcessor,
            AlarmEvent,
            AlarmStatus,
        )

        processor = AlarmProcessor.__new__(AlarmProcessor)
        processor._ml_alarms = {}

        instance_id = str(uuid.uuid4())
        alarm = AlarmEvent(
            instance_id=instance_id,
            alarm_id="ML_ANOMALY_TAG-001",
            tag_id="TAG-001",
            tag_name="Test Sensor",
            alarm_type="ml_anomaly",
            priority=2,
            status=AlarmStatus.ACTIVE_UNACKED.value,
            message="Anomaly detected",
            value=100.0,
            limit_value=90.0,
            timestamp=datetime.utcnow(),
        )
        processor._ml_alarms[instance_id] = alarm

        # Clear the alarm
        with patch('services.scada.alarm_management.alarm_service._emit_alarm_event'):
            result = processor.clear_ml_alarm("ML_ANOMALY_TAG-001")

        assert result is True
        assert len(processor._ml_alarms) == 0

    def test_clear_nonexistent_alarm(self):
        """Test clearing a non-existent alarm returns False."""
        from services.scada.alarm_management.alarm_service import AlarmProcessor

        processor = AlarmProcessor.__new__(AlarmProcessor)
        processor._ml_alarms = {}

        result = processor.clear_ml_alarm("NONEXISTENT_ALARM")

        assert result is False


# Example usage demonstrating the complete integration
def demo_integration_flow():
    """
    Demonstration of the complete integration flow.

    This function shows how the components work together:

    1. A tag value arrives (e.g., from OPC-UA, MQTT, or historian)
    2. The realtime hook processes the value
    3. Anomaly detection identifies if it's anomalous
    4. If anomalous, an ISA-18.2 alarm is generated
    5. The alarm is submitted to the alarm processor
    6. The alarm is persisted and broadcast via WebSocket

    Usage example:

        from services.ml.anomaly.realtime_hook import realtime_hook

        # Configure threshold for a tag
        from services.ml.anomaly.anomaly_detection_service import anomaly_detection_service
        from services.ml.anomaly.anomaly_types import ThresholdConfig

        config = anomaly_detection_service.config
        config.set_tag_config("TAG-TEMP-001", ThresholdConfig(
            high=85.0,
            high_high=95.0,
            low=15.0,
            low_low=5.0,
        ))
        anomaly_detection_service.configure(config)

        # Process incoming values
        # When value exceeds threshold, alarm is automatically generated
        result = realtime_hook.process(
            tag_id="TAG-TEMP-001",
            value=96.0,  # Exceeds high_high
            tag_name="Extruder Temperature"
        )

        # Check stats
        stats = realtime_hook.get_stats()
        print(f"Anomalies detected: {stats['anomalies_detected']}")
        print(f"Alarms generated: {stats['alarms_generated']}")
    """
    pass  # This is just documentation
