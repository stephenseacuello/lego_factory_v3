"""
Unit tests for OEE (Overall Equipment Effectiveness) Service.

Tests downtime recording, production counting, OEE calculation, and Pareto analysis.
OEE = Availability x Performance x Quality
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, MagicMock, patch

from services.mes.oee_service import OEEService, calculate_oee, get_oee_dashboard
from models.mes.oee import DowntimeReason, DowntimeEvent, ProductionCount, OEERecord


class TestDowntimeReason:
    """Tests for DowntimeReason enumeration."""

    def test_downtime_reason_values(self):
        """Test that all downtime reason codes exist."""
        assert DowntimeReason.SETUP.value == 'setup'
        assert DowntimeReason.CHANGEOVER.value == 'changeover'
        assert DowntimeReason.MAINTENANCE_PLANNED.value == 'maintenance_planned'
        assert DowntimeReason.MAINTENANCE_UNPLANNED.value == 'maintenance_unplanned'

    def test_downtime_reason_3d_printing_specific(self):
        """Test 3D printing specific downtime reasons."""
        assert DowntimeReason.FILAMENT_CHANGE.value == 'filament_change'
        assert DowntimeReason.BED_ADHESION.value == 'bed_adhesion'
        assert DowntimeReason.NOZZLE_CLOG.value == 'nozzle_clog'


class TestOEEService:
    """Tests for OEEService class methods."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = Mock()
        session.add = Mock()
        session.flush = Mock()
        session.query = Mock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create an OEEService with mock session."""
        return OEEService(mock_session)

    def test_record_downtime_with_end_time(self, service, mock_session):
        """Test recording a downtime event with known end time."""
        result = service.record_downtime(
            machine_id='PRINTER_01',
            reason='maintenance_unplanned',
            start_time=datetime(2026, 1, 20, 8, 0),
            end_time=datetime(2026, 1, 20, 8, 30)
        )

        # Verify session.add was called with a DowntimeEvent
        mock_session.add.assert_called_once()
        added_event = mock_session.add.call_args[0][0]
        assert isinstance(added_event, DowntimeEvent)
        assert added_event.machine_id == 'PRINTER_01'
        assert added_event.duration_minutes == 30.0
        assert added_event.planned is False
        mock_session.flush.assert_called_once()

    def test_record_planned_downtime(self, service, mock_session):
        """Test recording planned maintenance downtime."""
        result = service.record_downtime(
            machine_id='PRINTER_01',
            reason='maintenance_planned',
            start_time=datetime(2026, 1, 20, 6, 0),
            end_time=datetime(2026, 1, 20, 7, 0),
            planned=True
        )

        added_event = mock_session.add.call_args[0][0]
        assert added_event.planned is True
        assert added_event.duration_minutes == 60.0

    def test_record_downtime_without_end_time(self, service, mock_session):
        """Test recording a downtime event without end time (ongoing)."""
        result = service.record_downtime(
            machine_id='PRINTER_01',
            reason='nozzle_clog',
            start_time=datetime(2026, 1, 20, 10, 0)
        )

        added_event = mock_session.add.call_args[0][0]
        assert added_event.end_time is None
        assert added_event.duration_minutes is None

    def test_end_downtime_success(self, service, mock_session):
        """Test ending an active downtime event."""
        # Create a mock event that will be returned by the query
        mock_event = Mock()
        mock_event.start_time = datetime(2026, 1, 20, 10, 0, 0)
        mock_event.to_dict.return_value = {'id': 'event_001', 'duration_minutes': 45.0}

        # Setup query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = mock_event
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query

        result = service.end_downtime('event_001', datetime(2026, 1, 20, 10, 45, 0))

        assert result is not None
        assert mock_event.end_time == datetime(2026, 1, 20, 10, 45, 0)
        assert mock_event.duration_minutes == 45.0
        mock_session.flush.assert_called_once()

    def test_end_downtime_not_found(self, service, mock_session):
        """Test ending a nonexistent downtime event."""
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query

        result = service.end_downtime('nonexistent_event')
        assert result is None

    def test_record_production(self, service, mock_session):
        """Test recording production counts."""
        result = service.record_production(
            machine_id='PRINTER_01',
            shift_date=date(2026, 1, 20),
            total_count=100,
            good_count=95,
            reject_count=3,
            rework_count=2
        )

        mock_session.add.assert_called_once()
        added_count = mock_session.add.call_args[0][0]
        assert isinstance(added_count, ProductionCount)
        assert added_count.total_count == 100
        assert added_count.good_count == 95
        assert added_count.reject_count == 3
        assert added_count.rework_count == 2
        mock_session.flush.assert_called_once()

    def test_calculate_oee_world_class(self, service, mock_session):
        """Test OEE calculation with world-class results (85%+)."""
        # Mock production data
        mock_production = Mock()
        mock_production.total_count = 100
        mock_production.good_count = 99
        mock_production.run_time_minutes = 480
        mock_production.ideal_cycle_time_seconds = 60

        # Setup query to return no downtime and production data
        call_count = [0]

        def mock_query_side_effect(model):
            mock_q = Mock()
            mock_filter = Mock()
            if call_count[0] == 0:
                # First query: downtime events (empty)
                mock_filter.all.return_value = []
            else:
                # Second query: production counts
                mock_filter.all.return_value = [mock_production]
            mock_q.filter.return_value = mock_filter
            call_count[0] += 1
            return mock_q

        mock_session.query.side_effect = mock_query_side_effect

        result = service.calculate_oee('PRINTER_01', date(2026, 1, 20))

        # Verify OEE record was added
        mock_session.add.assert_called_once()
        added_record = mock_session.add.call_args[0][0]
        assert isinstance(added_record, OEERecord)
        assert added_record.total_count == 100
        assert added_record.good_count == 99

    def test_calculate_oee_with_unplanned_downtime(self, service, mock_session):
        """Test OEE calculation with unplanned downtime affecting availability."""
        # Mock downtime event
        mock_downtime = Mock()
        mock_downtime.duration_minutes = 60
        mock_downtime.planned = False
        mock_downtime.reason = DowntimeReason.MAINTENANCE_UNPLANNED

        # Mock production data
        mock_production = Mock()
        mock_production.total_count = 80
        mock_production.good_count = 76
        mock_production.run_time_minutes = 420
        mock_production.ideal_cycle_time_seconds = 60

        call_count = [0]

        def mock_query_side_effect(model):
            mock_q = Mock()
            mock_filter = Mock()
            if call_count[0] == 0:
                mock_filter.all.return_value = [mock_downtime]
            else:
                mock_filter.all.return_value = [mock_production]
            mock_q.filter.return_value = mock_filter
            call_count[0] += 1
            return mock_q

        mock_session.query.side_effect = mock_query_side_effect

        result = service.calculate_oee('PRINTER_01', date(2026, 1, 20))

        added_record = mock_session.add.call_args[0][0]
        assert added_record.unplanned_downtime == 60
        # Operating time should be reduced by unplanned downtime
        assert added_record.operating_time == 480 - 60  # 420 minutes

    def test_calculate_oee_with_planned_downtime(self, service, mock_session):
        """Test OEE calculation with planned downtime."""
        mock_downtime = Mock()
        mock_downtime.duration_minutes = 30
        mock_downtime.planned = True
        mock_downtime.reason = DowntimeReason.MAINTENANCE_PLANNED

        mock_production = Mock()
        mock_production.total_count = 90
        mock_production.good_count = 88
        mock_production.run_time_minutes = 450
        mock_production.ideal_cycle_time_seconds = 60

        call_count = [0]

        def mock_query_side_effect(model):
            mock_q = Mock()
            mock_filter = Mock()
            if call_count[0] == 0:
                mock_filter.all.return_value = [mock_downtime]
            else:
                mock_filter.all.return_value = [mock_production]
            mock_q.filter.return_value = mock_filter
            call_count[0] += 1
            return mock_q

        mock_session.query.side_effect = mock_query_side_effect

        result = service.calculate_oee('PRINTER_01', date(2026, 1, 20))

        added_record = mock_session.add.call_args[0][0]
        assert added_record.planned_downtime == 30

    def test_calculate_oee_with_changeover(self, service, mock_session):
        """Test OEE calculation with changeover time."""
        mock_downtime = Mock()
        mock_downtime.duration_minutes = 20
        mock_downtime.planned = False
        mock_downtime.reason = DowntimeReason.CHANGEOVER

        mock_production = Mock()
        mock_production.total_count = 95
        mock_production.good_count = 93
        mock_production.run_time_minutes = 460
        mock_production.ideal_cycle_time_seconds = 60

        call_count = [0]

        def mock_query_side_effect(model):
            mock_q = Mock()
            mock_filter = Mock()
            if call_count[0] == 0:
                mock_filter.all.return_value = [mock_downtime]
            else:
                mock_filter.all.return_value = [mock_production]
            mock_q.filter.return_value = mock_filter
            call_count[0] += 1
            return mock_q

        mock_session.query.side_effect = mock_query_side_effect

        result = service.calculate_oee('PRINTER_01', date(2026, 1, 20))

        added_record = mock_session.add.call_args[0][0]
        assert added_record.changeover_time == 20

    def test_calculate_oee_zero_production(self, service, mock_session):
        """Test OEE calculation with no production."""
        call_count = [0]

        def mock_query_side_effect(model):
            mock_q = Mock()
            mock_filter = Mock()
            mock_filter.all.return_value = []
            mock_q.filter.return_value = mock_filter
            call_count[0] += 1
            return mock_q

        mock_session.query.side_effect = mock_query_side_effect

        result = service.calculate_oee('PRINTER_01', date(2026, 1, 20))

        added_record = mock_session.add.call_args[0][0]
        assert added_record.total_count == 0
        assert added_record.good_count == 0

    def test_get_oee_history(self, service, mock_session):
        """Test retrieving OEE history for a date range."""
        mock_record1 = Mock()
        mock_record1.to_dict.return_value = {'record_date': '2026-01-18', 'oee': 75.0}
        mock_record2 = Mock()
        mock_record2.to_dict.return_value = {'record_date': '2026-01-20', 'oee': 82.0}

        mock_query = Mock()
        mock_filter = Mock()
        mock_order = Mock()
        mock_order.all.return_value = [mock_record1, mock_record2]
        mock_filter.order_by.return_value = mock_order
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query

        result = service.get_oee_history('PRINTER_01', date(2026, 1, 18), date(2026, 1, 20))

        assert len(result) == 2
        assert result[0]['oee'] == 75.0
        assert result[1]['oee'] == 82.0

    def test_get_oee_history_empty(self, service, mock_session):
        """Test retrieving OEE history with no records."""
        mock_query = Mock()
        mock_filter = Mock()
        mock_order = Mock()
        mock_order.all.return_value = []
        mock_filter.order_by.return_value = mock_order
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query

        result = service.get_oee_history('PRINTER_01', date(2026, 1, 1), date(2026, 1, 7))
        assert result == []

    def test_get_downtime_pareto(self, service, mock_session):
        """Test downtime Pareto analysis."""
        mock_result1 = Mock()
        mock_result1.reason = DowntimeReason.NOZZLE_CLOG
        mock_result1.count = 10
        mock_result1.total_minutes = 300.0

        mock_result2 = Mock()
        mock_result2.reason = DowntimeReason.MATERIAL
        mock_result2.count = 8
        mock_result2.total_minutes = 180.0

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_group = Mock()
        mock_order = Mock()
        mock_order.all.return_value = [mock_result1, mock_result2]
        mock_group.order_by.return_value = mock_order
        mock_query.group_by.return_value = mock_group
        mock_session.query.return_value = mock_query

        result = service.get_downtime_pareto('PRINTER_01', date(2026, 1, 1), date(2026, 1, 31))

        assert len(result) == 2
        assert result[0]['reason'] == 'nozzle_clog'
        assert result[0]['total_minutes'] == 300.0
        assert result[1]['reason'] == 'material'

    def test_get_downtime_pareto_no_filters(self, service, mock_session):
        """Test downtime Pareto analysis without any filters."""
        mock_result = Mock()
        mock_result.reason = DowntimeReason.SETUP
        mock_result.count = 5
        mock_result.total_minutes = 100.0

        mock_query = Mock()
        mock_group = Mock()
        mock_order = Mock()
        mock_order.all.return_value = [mock_result]
        mock_group.order_by.return_value = mock_order
        mock_query.group_by.return_value = mock_group
        mock_session.query.return_value = mock_query

        result = service.get_downtime_pareto()

        assert len(result) == 1
        assert result[0]['reason'] == 'setup'


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_calculate_oee_function(self):
        """Test module-level calculate_oee function."""
        with patch('services.mes.oee_service.get_db_session') as mock_get_session:
            mock_session = Mock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            # Setup query mocks for the OEEService.calculate_oee call
            call_count = [0]

            def mock_query_side_effect(model):
                mock_q = Mock()
                mock_filter = Mock()
                mock_filter.all.return_value = []
                mock_q.filter.return_value = mock_filter
                call_count[0] += 1
                return mock_q

            mock_session.query.side_effect = mock_query_side_effect
            mock_session.add = Mock()
            mock_session.flush = Mock()

            result = calculate_oee('PRINTER_01', date(2026, 1, 20))

            # Verify result is a dict from OEERecord.to_dict()
            assert isinstance(result, dict)
            mock_session.add.assert_called_once()

    def test_get_oee_dashboard(self):
        """Test OEE dashboard data retrieval."""
        with patch('services.mes.oee_service.get_db_session') as mock_get_session:
            mock_session = Mock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            mock_record1 = Mock()
            mock_record1.oee = 0.80
            mock_record1.availability = 0.90
            mock_record1.performance = 0.92
            mock_record1.quality = 0.97

            mock_record2 = Mock()
            mock_record2.oee = 0.85
            mock_record2.availability = 0.92
            mock_record2.performance = 0.95
            mock_record2.quality = 0.98

            mock_query = Mock()
            mock_filter = Mock()
            mock_filter.filter.return_value = mock_filter
            mock_filter.all.return_value = [mock_record1, mock_record2]
            mock_query.filter.return_value = mock_filter
            mock_session.query.return_value = mock_query

            result = get_oee_dashboard(machine_ids=['PRINTER_01'], days=7)

            assert 'average_oee' in result
            assert result['record_count'] == 2
            # Average OEE should be (0.80 + 0.85) / 2 * 100 = 82.5
            assert result['average_oee'] == 82.5

    def test_get_oee_dashboard_empty(self):
        """Test OEE dashboard with no records."""
        with patch('services.mes.oee_service.get_db_session') as mock_get_session:
            mock_session = Mock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            mock_query = Mock()
            mock_filter = Mock()
            mock_filter.all.return_value = []
            mock_query.filter.return_value = mock_filter
            mock_session.query.return_value = mock_query

            result = get_oee_dashboard()

            assert result['average_oee'] == 0
            assert result['average_availability'] == 0
            assert result['average_performance'] == 0
            assert result['average_quality'] == 0


class TestOEECalculationLogic:
    """Tests for OEE calculation formula verification."""

    def test_oee_formula_components(self):
        """Test that OEE = Availability x Performance x Quality."""
        record = OEERecord()
        record.scheduled_time = 480
        record.operating_time = 432  # 90% availability
        record.total_count = 100
        record.good_count = 95
        record.ideal_cycle_time = 60
        record.calculate_oee()

        assert abs(record.availability - 0.9) < 0.001
        assert abs(record.quality - 0.95) < 0.001
        assert record.oee == record.availability * record.performance * record.quality

    def test_oee_zero_scheduled_time(self):
        """Test OEE with zero scheduled time."""
        record = OEERecord()
        record.scheduled_time = 0
        record.operating_time = 0
        record.total_count = 0
        record.good_count = 0
        record.calculate_oee()

        assert record.availability == 0
        assert record.oee == 0

    def test_oee_perfect_conditions(self):
        """Test OEE under perfect theoretical conditions."""
        record = OEERecord()
        record.scheduled_time = 480
        record.operating_time = 480
        record.total_count = 480
        record.good_count = 480
        record.ideal_cycle_time = 60
        record.calculate_oee()

        assert record.availability == 1.0
        assert record.quality == 1.0
        assert record.performance == 1.0
        assert record.oee == 1.0

    def test_oee_performance_capped_at_100(self):
        """Test that performance is capped at 100%."""
        record = OEERecord()
        record.scheduled_time = 480
        record.operating_time = 480
        record.total_count = 1000  # Producing faster than ideal
        record.good_count = 1000
        record.ideal_cycle_time = 60
        record.calculate_oee()

        assert record.performance <= 1.0

    def test_oee_zero_total_count(self):
        """Test OEE with zero production."""
        record = OEERecord()
        record.scheduled_time = 480
        record.operating_time = 480
        record.total_count = 0
        record.good_count = 0
        record.ideal_cycle_time = 60
        record.calculate_oee()

        assert record.quality == 0
        assert record.performance == 0
        assert record.oee == 0


class TestDowntimeClassification:
    """Tests for downtime classification and impact on OEE."""

    def test_planned_vs_unplanned_distinction(self):
        """Test that planned and unplanned downtime reasons are valid."""
        planned = [DowntimeReason.MAINTENANCE_PLANNED, DowntimeReason.CHANGEOVER]
        unplanned = [DowntimeReason.MAINTENANCE_UNPLANNED, DowntimeReason.NOZZLE_CLOG]
        for reason in planned + unplanned:
            assert isinstance(reason, DowntimeReason)

    def test_changeover_time_tracking(self):
        """Test that changeover time is tracked for SMED analysis."""
        changeover_reasons = [DowntimeReason.SETUP, DowntimeReason.CHANGEOVER]
        for reason in changeover_reasons:
            assert reason.value in ['setup', 'changeover']

    def test_all_downtime_reasons_have_values(self):
        """Test that all downtime reasons have string values."""
        for reason in DowntimeReason:
            assert isinstance(reason.value, str)
            assert len(reason.value) > 0

    def test_3d_printing_specific_reasons(self):
        """Test 3D printing specific downtime categories."""
        printing_reasons = [
            DowntimeReason.FILAMENT_CHANGE,
            DowntimeReason.BED_ADHESION,
            DowntimeReason.NOZZLE_CLOG,
            DowntimeReason.LAYER_SHIFT,
        ]
        for reason in printing_reasons:
            assert isinstance(reason, DowntimeReason)
