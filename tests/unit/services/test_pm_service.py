"""
Unit tests for CMMS Preventive Maintenance (PM) Service.

Tests PM schedule creation, retrieval, updating, work order generation,
and compliance metrics for both CALENDAR and METER trigger types.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock

from services.cmms.maintenance_service import PMService, get_pm_service


class TestPMServiceInit:
    """Tests for PMService initialization."""

    def test_init_with_session(self):
        """Test PMService initialization with a session."""
        mock_session = Mock()
        service = PMService(mock_session)
        assert service.session is mock_session

    def test_get_pm_service_with_session(self):
        """Test get_pm_service factory function with session."""
        mock_session = Mock()
        service = get_pm_service(mock_session)
        assert isinstance(service, PMService)
        assert service.session is mock_session


class TestCreatePMSchedule:
    """Tests for PM schedule creation."""

    @pytest.fixture
    def mock_session(self):
        session = Mock()
        session.add = Mock()
        session.flush = Mock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        return PMService(mock_session)

    @pytest.fixture
    def mock_asset(self):
        asset = Mock()
        asset.id = 1
        asset.asset_id = "ASSET-001"
        return asset

    def test_create_calendar_based_pm_schedule(self, service, mock_session, mock_asset):
        """Test creating a calendar-based PM schedule."""
        # Setup the query chain to return the mock asset
        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        # Patch the PMSchedule class where it's imported (inside the method)
        with patch.dict('sys.modules', {}):
            # We need to mock the model import that happens inside the method
            mock_pm_instance = Mock()
            mock_pm_instance.pm_id = 'PM-12345678'
            mock_pm_instance.to_dict.return_value = {
                'pm_id': 'PM-12345678',
                'name': 'Weekly Lubrication',
                'trigger_type': 'calendar',
                'frequency_days': 7
            }

            with patch('models.cmms.maintenance.PMSchedule', return_value=mock_pm_instance):
                result = service.create_pm_schedule({
                    'asset_id': 'ASSET-001',
                    'name': 'Weekly Lubrication',
                    'trigger_type': 'calendar',
                    'frequency_days': 7,
                })

                assert result['pm_id'] == 'PM-12345678'
                assert result['trigger_type'] == 'calendar'
                mock_session.add.assert_called_once()

    def test_create_meter_based_pm_schedule(self, service, mock_session, mock_asset):
        """Test creating a meter-based PM schedule."""
        mock_meter = Mock()
        mock_meter.id = 10
        mock_meter.meter_id = 'METER-001'

        # Setup query to return asset first, then meter
        call_count = [0]
        def query_side_effect(*args):
            mock_query = Mock()
            mock_filter = Mock()
            mock_query.filter.return_value = mock_filter
            if call_count[0] == 0:
                mock_filter.first.return_value = mock_asset
            else:
                mock_filter.first.return_value = mock_meter
            call_count[0] += 1
            return mock_query

        mock_session.query.side_effect = query_side_effect

        mock_pm_instance = Mock()
        mock_pm_instance.to_dict.return_value = {
            'pm_id': 'PM-METER001',
            'trigger_type': 'meter',
            'meter_interval': 500
        }

        with patch('models.cmms.maintenance.PMSchedule', return_value=mock_pm_instance):
            result = service.create_pm_schedule({
                'asset_id': 'ASSET-001',
                'name': 'Oil Change',
                'trigger_type': 'meter',
                'meter_id': 'METER-001',
                'meter_interval': 500,
            })

            assert result['trigger_type'] == 'meter'
            assert result['meter_interval'] == 500

    def test_create_pm_schedule_asset_not_found(self, service, mock_session):
        """Test creating PM schedule with nonexistent asset."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError) as exc_info:
            service.create_pm_schedule({'asset_id': 'NONEXISTENT', 'name': 'Test'})
        assert "Asset NONEXISTENT not found" in str(exc_info.value)

    def test_create_pm_schedule_with_checklist(self, service, mock_session, mock_asset):
        """Test creating PM schedule with checklist items."""
        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        mock_pm_instance = Mock()
        mock_pm_instance.to_dict.return_value = {
            'pm_id': 'PM-CHECKLIST',
            'checklist': ['Check oil', 'Inspect belts']
        }

        with patch('models.cmms.maintenance.PMSchedule', return_value=mock_pm_instance):
            result = service.create_pm_schedule({
                'asset_id': 'ASSET-001',
                'name': 'Inspection',
                'checklist': ['Check oil', 'Inspect belts']
            })
            assert len(result['checklist']) == 2


class TestGetPMSchedule:
    """Tests for PM schedule retrieval."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return PMService(mock_session)

    def test_get_pm_schedule_found(self, service, mock_session):
        """Test getting an existing PM schedule."""
        mock_pm = Mock()
        mock_pm.to_dict.return_value = {'pm_id': 'PM-001', 'name': 'Weekly Check'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_pm

        result = service.get_pm_schedule("PM-001")
        assert result['pm_id'] == 'PM-001'

    def test_get_pm_schedule_not_found(self, service, mock_session):
        """Test getting a nonexistent PM schedule."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.get_pm_schedule("NONEXISTENT")
        assert result is None


class TestGetPMSchedules:
    """Tests for PM schedule listing with filters."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return PMService(mock_session)

    def _setup_query_mock(self, mock_session, results):
        """Helper to set up the chained query mock."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = results
        mock_session.query.return_value = mock_query
        return mock_query

    def test_get_pm_schedules_all(self, service, mock_session):
        """Test getting all PM schedules."""
        mock_pms = [
            Mock(to_dict=Mock(return_value={'pm_id': 'PM-0'})),
            Mock(to_dict=Mock(return_value={'pm_id': 'PM-1'}))
        ]
        self._setup_query_mock(mock_session, mock_pms)

        result = service.get_pm_schedules()
        assert len(result) == 2

    def test_get_pm_schedules_active_only(self, service, mock_session):
        """Test filtering PM schedules by active status."""
        mock_pm = Mock(to_dict=Mock(return_value={'pm_id': 'PM-001', 'is_active': True}))
        self._setup_query_mock(mock_session, [mock_pm])

        result = service.get_pm_schedules(is_active=True)
        assert len(result) == 1

    def test_get_pm_schedules_by_asset(self, service, mock_session):
        """Test filtering PM schedules by asset ID."""
        mock_asset = Mock()
        mock_asset.id = 1

        mock_pm = Mock(to_dict=Mock(return_value={'pm_id': 'PM-001'}))

        # First query returns the asset, second query chain returns the PM schedules
        call_count = [0]
        def query_side_effect(*args):
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query

            if call_count[0] == 0:
                # First call is for PMSchedule.is_deleted filter
                mock_query.all.return_value = [mock_pm]
            else:
                # Second call is for Asset lookup
                mock_query.first.return_value = mock_asset

            call_count[0] += 1
            return mock_query

        mock_session.query.side_effect = query_side_effect

        result = service.get_pm_schedules(asset_id='ASSET-001')
        assert len(result) == 1

    def test_get_pm_schedules_due_within_days(self, service, mock_session):
        """Test filtering PM schedules due within specified days."""
        mock_pm = Mock(to_dict=Mock(return_value={'pm_id': 'PM-001'}))
        self._setup_query_mock(mock_session, [mock_pm])

        result = service.get_pm_schedules(due_within_days=7)
        assert len(result) == 1


class TestUpdatePMSchedule:
    """Tests for PM schedule updates."""

    @pytest.fixture
    def mock_session(self):
        session = Mock()
        session.flush = Mock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        return PMService(mock_session)

    def test_update_pm_schedule_success(self, service, mock_session):
        """Test updating an existing PM schedule."""
        mock_pm = Mock()
        mock_pm.pm_id = "PM-001"
        mock_pm.frequency_days = 7
        mock_pm.to_dict.return_value = {'pm_id': 'PM-001', 'frequency_days': 14}

        mock_session.query.return_value.filter.return_value.first.return_value = mock_pm

        result = service.update_pm_schedule("PM-001", {'frequency_days': 14})

        assert result['frequency_days'] == 14
        mock_session.flush.assert_called_once()

    def test_update_pm_schedule_not_found(self, service, mock_session):
        """Test updating a nonexistent PM schedule."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.update_pm_schedule("NONEXISTENT", {})
        assert result is None

    def test_update_pm_schedule_deactivate(self, service, mock_session):
        """Test deactivating a PM schedule."""
        mock_pm = Mock()
        mock_pm.is_active = True
        mock_pm.to_dict.return_value = {'pm_id': 'PM-001', 'is_active': False}

        mock_session.query.return_value.filter.return_value.first.return_value = mock_pm

        result = service.update_pm_schedule("PM-001", {'is_active': False})
        assert result['is_active'] is False

    def test_update_pm_schedule_change_priority(self, service, mock_session):
        """Test updating PM schedule priority."""
        mock_pm = Mock()
        mock_pm.priority = 'medium'
        mock_pm.to_dict.return_value = {'pm_id': 'PM-001', 'priority': 'high'}

        mock_session.query.return_value.filter.return_value.first.return_value = mock_pm

        result = service.update_pm_schedule("PM-001", {'priority': 'high'})
        assert result['priority'] == 'high'


class TestGeneratePMWorkOrders:
    """Tests for PM work order generation."""

    @pytest.fixture
    def mock_session(self):
        session = Mock()
        session.add = Mock()
        session.flush = Mock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        return PMService(mock_session)

    def test_generate_pm_work_orders_success(self, service, mock_session):
        """Test generating work orders for due PMs."""
        # Create mock PM schedule
        mock_pm = Mock()
        mock_pm.id = 1
        mock_pm.pm_id = "PM-001"
        mock_pm.name = "Weekly Check"
        mock_pm.asset = Mock(asset_id="ASSET-001")
        mock_pm.priority = Mock(value='medium')
        mock_pm.next_due_date = date.today()
        mock_pm.work_window_days = 7
        mock_pm.estimated_hours = 2.0
        mock_pm.estimated_cost = None
        mock_pm.work_center_id = None
        mock_pm.instructions = "Check equipment"

        # Mock work_orders relationship for checking existing WOs
        mock_wo_class = Mock()
        mock_wo_class.status = Mock()
        mock_pm.work_orders = Mock()
        mock_pm.work_orders.property = Mock()
        mock_pm.work_orders.property.mapper = Mock()
        mock_pm.work_orders.property.mapper.class_ = mock_wo_class

        # Setup query mock
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_pm]
        mock_query.select_from.return_value.filter.return_value.scalar.return_value = 0
        mock_session.query.return_value = mock_query

        # Mock MaintenanceService.create_work_order
        with patch.object(service, 'session', mock_session):
            with patch('services.cmms.maintenance_service.MaintenanceService') as MockMaintService:
                mock_maint_instance = Mock()
                mock_maint_instance.create_work_order.return_value = {'wo_number': 'MWO-001'}
                MockMaintService.return_value = mock_maint_instance

                result = service.generate_pm_work_orders(days_ahead=7)

                assert isinstance(result, list)
                assert len(result) == 1
                assert result[0]['wo_number'] == 'MWO-001'

    def test_generate_pm_work_orders_no_due_pms(self, service, mock_session):
        """Test generating work orders when no PMs are due."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query

        result = service.generate_pm_work_orders(days_ahead=7)
        assert result == []

    def test_generate_pm_work_orders_skip_existing(self, service, mock_session):
        """Test that existing work orders are not duplicated."""
        # Create mock PM schedule
        mock_pm = Mock()
        mock_pm.id = 1
        mock_pm.pm_id = "PM-001"

        # Mock work_orders relationship
        mock_wo_class = Mock()
        mock_wo_class.status = Mock()
        mock_pm.work_orders = Mock()
        mock_pm.work_orders.property = Mock()
        mock_pm.work_orders.property.mapper = Mock()
        mock_pm.work_orders.property.mapper.class_ = mock_wo_class

        # Setup query mock - existing WO count returns 1 (WO already exists)
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_pm]
        mock_query.select_from.return_value.filter.return_value.scalar.return_value = 1
        mock_session.query.return_value = mock_query

        with patch('services.cmms.maintenance_service.MaintenanceService') as MockMaintService:
            mock_maint_instance = Mock()
            MockMaintService.return_value = mock_maint_instance

            result = service.generate_pm_work_orders(days_ahead=7)

            # No work orders should be created since one already exists
            mock_maint_instance.create_work_order.assert_not_called()
            assert result == []


class TestGetPMCompliance:
    """Tests for PM compliance metrics calculation."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return PMService(mock_session)

    def _setup_compliance_mock(self, mock_session, total_due, completed):
        """Helper to set up compliance query mocks."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.side_effect = [total_due, completed]
        mock_session.query.return_value = mock_query

    def test_get_pm_compliance_full(self, service, mock_session):
        """Test compliance calculation with 100% compliance."""
        self._setup_compliance_mock(mock_session, 10, 10)

        result = service.get_pm_compliance(days=30)

        assert result['period_days'] == 30
        assert result['total_due'] == 10
        assert result['completed_on_time'] == 10
        assert result['compliance_rate'] == 100.0

    def test_get_pm_compliance_partial(self, service, mock_session):
        """Test compliance calculation with partial compliance."""
        self._setup_compliance_mock(mock_session, 10, 7)

        result = service.get_pm_compliance(days=30)

        assert result['compliance_rate'] == 70.0

    def test_get_pm_compliance_zero_due(self, service, mock_session):
        """Test compliance calculation when no PMs were due."""
        self._setup_compliance_mock(mock_session, 0, 0)

        result = service.get_pm_compliance(days=30)

        assert result['compliance_rate'] == 0

    def test_get_pm_compliance_custom_days(self, service, mock_session):
        """Test compliance calculation with custom day range."""
        self._setup_compliance_mock(mock_session, 5, 4)

        result = service.get_pm_compliance(days=7)

        assert result['period_days'] == 7
        assert result['total_due'] == 5
        assert result['completed_on_time'] == 4
        assert result['compliance_rate'] == 80.0


class TestPMTriggerTypes:
    """Tests specific to PM trigger type handling."""

    @pytest.fixture
    def mock_session(self):
        session = Mock()
        session.add = Mock()
        session.flush = Mock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        return PMService(mock_session)

    @pytest.fixture
    def mock_asset(self):
        asset = Mock()
        asset.id = 1
        asset.asset_id = "ASSET-001"
        return asset

    def test_calendar_trigger_day_of_week(self, service, mock_session, mock_asset):
        """Test calendar trigger with specific day of week."""
        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        mock_pm_instance = Mock()
        mock_pm_instance.to_dict.return_value = {
            'pm_id': 'PM-DOW',
            'day_of_week': 1
        }

        with patch('models.cmms.maintenance.PMSchedule', return_value=mock_pm_instance):
            result = service.create_pm_schedule({
                'asset_id': 'ASSET-001',
                'name': 'Monday Maint',
                'day_of_week': 1
            })
            assert result['day_of_week'] == 1

    def test_calendar_trigger_day_of_month(self, service, mock_session, mock_asset):
        """Test calendar trigger with specific day of month."""
        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        mock_pm_instance = Mock()
        mock_pm_instance.to_dict.return_value = {
            'pm_id': 'PM-DOM',
            'day_of_month': 15
        }

        with patch('models.cmms.maintenance.PMSchedule', return_value=mock_pm_instance):
            result = service.create_pm_schedule({
                'asset_id': 'ASSET-001',
                'name': 'Mid-Month',
                'day_of_month': 15
            })
            assert result['day_of_month'] == 15

    def test_calendar_trigger_frequency_days(self, service, mock_session, mock_asset):
        """Test calendar trigger with frequency in days."""
        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        mock_pm_instance = Mock()
        mock_pm_instance.to_dict.return_value = {
            'pm_id': 'PM-FREQ',
            'frequency_days': 30,
            'trigger_type': 'calendar'
        }

        with patch('models.cmms.maintenance.PMSchedule', return_value=mock_pm_instance):
            result = service.create_pm_schedule({
                'asset_id': 'ASSET-001',
                'name': 'Monthly PM',
                'trigger_type': 'calendar',
                'frequency_days': 30
            })
            assert result['frequency_days'] == 30
            assert result['trigger_type'] == 'calendar'
