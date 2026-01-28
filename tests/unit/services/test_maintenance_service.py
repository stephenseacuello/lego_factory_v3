"""
Unit tests for CMMS Maintenance Service.

Tests work order lifecycle, task management, labor/material recording,
and backlog summary reporting.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from services.cmms.maintenance_service import MaintenanceService, get_maintenance_service


class TestMaintenanceServiceInit:
    """Tests for MaintenanceService initialization."""

    def test_init_with_session(self):
        """Test initializing MaintenanceService with a session."""
        mock_session = Mock()
        service = MaintenanceService(mock_session)
        assert service.session is mock_session

    def test_get_maintenance_service_with_session(self):
        """Test get_maintenance_service helper with provided session."""
        mock_session = Mock()
        service = get_maintenance_service(mock_session)
        assert isinstance(service, MaintenanceService)
        assert service.session is mock_session


class TestCreateWorkOrder:
    """Tests for work order creation."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = Mock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create a MaintenanceService with mock session."""
        return MaintenanceService(mock_session)

    @pytest.fixture
    def valid_wo_data(self):
        """Valid work order creation data."""
        return {
            'asset_id': 'AST-001',
            'description': 'Replace worn bearing on conveyor motor',
            'wo_type': 'corrective',
            'priority': 'high',
            'problem_code': 'MECH-001',
            'assigned_to': 'tech_001',
            'estimated_hours': 4.0,
        }

    def test_create_work_order_success(self, service, mock_session, valid_wo_data):
        """Test successful work order creation."""
        mock_asset = Mock(id=1)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        mock_wo = Mock()
        mock_wo.wo_number = 'MWO-001'
        mock_wo.to_dict.return_value = {'wo_number': 'MWO-001', 'status': 'draft'}

        with patch('models.cmms.maintenance.MaintenanceWorkOrder', return_value=mock_wo):
            result = service.create_work_order(valid_wo_data)

        assert result is not None
        assert result['wo_number'] == 'MWO-001'
        mock_session.add.assert_called_once_with(mock_wo)
        mock_session.flush.assert_called_once()

    def test_create_work_order_asset_not_found(self, service, mock_session, valid_wo_data):
        """Test work order creation with nonexistent asset."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Asset .* not found"):
            service.create_work_order(valid_wo_data)


class TestGetWorkOrder:
    """Tests for retrieving work orders."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MaintenanceService(mock_session)

    def test_get_work_order_exists(self, service, mock_session):
        """Test getting an existing work order."""
        mock_wo = Mock()
        mock_wo.to_dict.return_value = {'wo_number': 'MWO-001', 'status': 'draft'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        result = service.get_work_order('MWO-001')

        assert result is not None
        assert result['wo_number'] == 'MWO-001'

    def test_get_work_order_not_found(self, service, mock_session):
        """Test getting a nonexistent work order."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.get_work_order('NONEXISTENT')

        assert result is None


class TestGetWorkOrders:
    """Tests for listing work orders with filters."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MaintenanceService(mock_session)

    def test_get_work_orders_no_filters(self, service, mock_session):
        """Test getting work orders without filters."""
        mock_wo1, mock_wo2 = Mock(), Mock()
        mock_wo1.to_dict.return_value = {'wo_number': 'MWO-001'}
        mock_wo2.to_dict.return_value = {'wo_number': 'MWO-002'}

        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = [mock_wo1, mock_wo2]
        mock_session.query.return_value = query_mock

        result = service.get_work_orders()

        assert len(result) == 2

    def test_get_work_orders_filter_by_status(self, service, mock_session):
        """Test filtering work orders by status."""
        mock_wo = Mock()
        mock_wo.to_dict.return_value = {'wo_number': 'MWO-001', 'status': 'in_progress'}

        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = [mock_wo]
        mock_session.query.return_value = query_mock

        result = service.get_work_orders(status='in_progress')

        assert len(result) == 1

    def test_get_work_orders_with_pagination(self, service, mock_session):
        """Test work orders pagination."""
        mock_wos = [Mock() for _ in range(3)]
        for i, wo in enumerate(mock_wos):
            wo.to_dict.return_value = {'wo_number': f'MWO-00{i}'}

        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = mock_wos
        mock_session.query.return_value = query_mock

        result = service.get_work_orders(limit=3, offset=0)

        assert len(result) == 3


class TestUpdateWorkOrder:
    """Tests for updating work orders."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MaintenanceService(mock_session)

    def test_update_work_order_success(self, service, mock_session):
        """Test successful work order update."""
        mock_wo = Mock()
        mock_wo.to_dict.return_value = {'wo_number': 'MWO-001', 'description': 'Updated'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        result = service.update_work_order('MWO-001', {'description': 'Updated'})

        assert result is not None
        mock_session.flush.assert_called()

    def test_update_work_order_not_found(self, service, mock_session):
        """Test updating nonexistent work order."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.update_work_order('NONEXISTENT', {'description': 'Updated'})

        assert result is None


class TestWorkOrderLifecycle:
    """Tests for work order lifecycle methods (start, complete)."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MaintenanceService(mock_session)

    def test_start_work_order_success(self, service, mock_session):
        """Test starting a work order."""
        mock_wo = Mock()
        mock_wo.to_dict.return_value = {'wo_number': 'MWO-001', 'status': 'in_progress'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        result = service.start_work_order('MWO-001', 'tech_001')

        assert result is not None

    def test_start_work_order_not_found(self, service, mock_session):
        """Test starting nonexistent work order."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.start_work_order('NONEXISTENT', 'tech_001')

        assert result is None

    def test_complete_work_order_success(self, service, mock_session):
        """Test completing a work order."""
        mock_wo = Mock()
        mock_wo.labor = []
        mock_wo.materials = []
        mock_wo.downtime_start = None
        mock_wo.downtime_end = None
        mock_wo.pm_schedule_id = None
        mock_wo.to_dict.return_value = {'wo_number': 'MWO-001', 'status': 'completed'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        result = service.complete_work_order(
            'MWO-001', completion_notes='Done', actual_hours=3.5, user_id='tech_001'
        )

        assert result is not None
        mock_session.flush.assert_called()

    def test_complete_work_order_not_found(self, service, mock_session):
        """Test completing nonexistent work order."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.complete_work_order('NONEXISTENT')

        assert result is None

    def test_complete_work_order_calculates_costs(self, service, mock_session):
        """Test that completing work order calculates labor and material costs."""
        mock_labor = Mock(total_cost=150.00)
        mock_material = Mock(total_cost=75.00)

        mock_wo = Mock()
        mock_wo.labor = [mock_labor]
        mock_wo.materials = [mock_material]
        mock_wo.downtime_start = None
        mock_wo.downtime_end = None
        mock_wo.pm_schedule_id = None
        mock_wo.to_dict.return_value = {'wo_number': 'MWO-001'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        service.complete_work_order('MWO-001')

        assert mock_wo.actual_labor_cost == 150.00
        assert mock_wo.actual_material_cost == 75.00

    def test_complete_work_order_calculates_downtime(self, service, mock_session):
        """Test that completing work order calculates downtime hours."""
        mock_wo = Mock()
        mock_wo.labor = []
        mock_wo.materials = []
        mock_wo.downtime_start = datetime(2026, 1, 21, 8, 0, 0)
        mock_wo.downtime_end = datetime(2026, 1, 21, 12, 0, 0)
        mock_wo.pm_schedule_id = None
        mock_wo.to_dict.return_value = {'wo_number': 'MWO-001'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        service.complete_work_order('MWO-001')

        assert mock_wo.downtime_hours == 4.0

    def test_complete_work_order_updates_pm_schedule(self, service, mock_session):
        """Test that completing PM work order updates PM schedule."""
        mock_pm = Mock()
        mock_pm.calculate_next_due.return_value = datetime(2026, 2, 21)

        mock_wo = Mock()
        mock_wo.labor = []
        mock_wo.materials = []
        mock_wo.downtime_start = None
        mock_wo.downtime_end = None
        mock_wo.pm_schedule_id = 'PM-001'
        mock_wo.pm_schedule = mock_pm
        mock_wo.to_dict.return_value = {'wo_number': 'MWO-001'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        service.complete_work_order('MWO-001')

        mock_pm.calculate_next_due.assert_called_once()


class TestTaskManagement:
    """Tests for work order task management."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MaintenanceService(mock_session)

    def test_add_task_success(self, service, mock_session):
        """Test adding a task to work order."""
        mock_wo = Mock(id=1)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        mock_task = Mock()
        mock_task.to_dict.return_value = {'id': 'task_001', 'name': 'Isolate power'}

        with patch('models.cmms.maintenance.WorkOrderTask', return_value=mock_task):
            result = service.add_task('MWO-001', {
                'name': 'Isolate power',
                'sequence': 10,
                'lockout_required': True,
            })

        assert result is not None
        mock_session.add.assert_called_once()

    def test_add_task_work_order_not_found(self, service, mock_session):
        """Test adding task to nonexistent work order."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.add_task('NONEXISTENT', {'name': 'Test task'})

        assert result is None

    def test_complete_task_success(self, service, mock_session):
        """Test completing a task."""
        mock_task = Mock()
        mock_task.to_dict.return_value = {'id': 'task_001', 'is_completed': True}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_task

        result = service.complete_task('task_001', 'tech_001', actual_minutes=10)

        assert result is not None
        assert mock_task.is_completed is True
        mock_session.flush.assert_called()

    def test_complete_task_not_found(self, service, mock_session):
        """Test completing nonexistent task."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.complete_task('NONEXISTENT', 'tech_001')

        assert result is None


class TestLaborRecording:
    """Tests for labor recording on work orders."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MaintenanceService(mock_session)

    def test_record_labor_success(self, service, mock_session):
        """Test successful labor recording."""
        mock_wo = Mock(id=1, actual_hours=0)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        mock_labor = Mock(regular_hours=4.0, overtime_hours=0)
        mock_labor.to_dict.return_value = {'worker_id': 'tech_001', 'regular_hours': 4.0}

        with patch('models.cmms.maintenance.WorkOrderLabor', return_value=mock_labor):
            result = service.record_labor('MWO-001', {
                'worker_id': 'tech_001',
                'regular_hours': 4.0,
                'hourly_rate': 45.00,
            })

        assert result is not None
        mock_labor.calculate_cost.assert_called_once()
        mock_session.add.assert_called_once()

    def test_record_labor_work_order_not_found(self, service, mock_session):
        """Test recording labor on nonexistent work order."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.record_labor('NONEXISTENT', {'worker_id': 'tech_001'})

        assert result is None

    def test_record_labor_updates_work_order_hours(self, service, mock_session):
        """Test that recording labor updates work order actual hours."""
        mock_wo = Mock(id=1, actual_hours=2.0)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        mock_labor = Mock(regular_hours=4.0, overtime_hours=1.0)
        mock_labor.to_dict.return_value = {'worker_id': 'tech_001'}

        with patch('models.cmms.maintenance.WorkOrderLabor', return_value=mock_labor):
            service.record_labor('MWO-001', {'worker_id': 'tech_001'})

        assert mock_wo.actual_hours == 7.0  # 2.0 + 4.0 + 1.0


class TestMaterialRecording:
    """Tests for material usage recording on work orders."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MaintenanceService(mock_session)

    def test_record_material_success(self, service, mock_session):
        """Test successful material recording."""
        mock_wo = Mock(id=1)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        mock_material = Mock()
        mock_material.to_dict.return_value = {'spare_id': 'SPR-001', 'quantity_used': 2}

        with patch('models.cmms.maintenance.WorkOrderMaterial', return_value=mock_material):
            result = service.record_material('MWO-001', {
                'spare_id': 'SPR-001',
                'description': 'Ball bearing 6205-2RS',
                'quantity_used': 2,
                'unit_cost': 25.00,
            })

        assert result is not None
        mock_material.calculate_cost.assert_called_once()
        mock_session.add.assert_called_once()

    def test_record_material_work_order_not_found(self, service, mock_session):
        """Test recording material on nonexistent work order."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.record_material('NONEXISTENT', {'description': 'Part'})

        assert result is None


class TestBacklogSummary:
    """Tests for backlog summary reporting."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MaintenanceService(mock_session)

    def test_get_backlog_summary(self, service, mock_session):
        """Test getting backlog summary."""
        # Create mock results for status counts
        status_item_1 = Mock()
        status_item_1.status = Mock(value='draft')
        status_item_2 = Mock()
        status_item_2.status = Mock(value='in_progress')
        status_result = [(status_item_1, 5), (status_item_2, 3)]

        # Create mock results for priority counts
        priority_item_1 = Mock()
        priority_item_1.priority = Mock(value='high')
        priority_item_2 = Mock()
        priority_item_2.priority = Mock(value='medium')
        priority_result = [(priority_item_1, 4), (priority_item_2, 4)]

        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.group_by.return_value = query_mock
        query_mock.all.side_effect = [status_result, priority_result]
        query_mock.scalar.side_effect = [3, 45.0]
        mock_session.query.return_value = query_mock

        result = service.get_backlog_summary()

        assert result is not None
        assert isinstance(result, dict)
        assert 'by_status' in result
        assert 'by_priority' in result
        assert 'overdue_count' in result
        assert 'total_estimated_hours' in result


class TestWorkOrderWorkflow:
    """Integration-style tests for complete work order workflows."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MaintenanceService(mock_session)

    def test_corrective_maintenance_workflow(self, service, mock_session):
        """Test complete corrective maintenance workflow."""
        mock_asset = Mock(id=1)
        mock_wo = Mock(id=1, actual_hours=0, labor=[], materials=[],
                       downtime_start=None, downtime_end=None, pm_schedule_id=None)
        mock_wo.wo_number = 'MWO-001'
        mock_wo.to_dict.return_value = {'wo_number': 'MWO-001', 'status': 'draft'}

        # For create_work_order - asset lookup returns mock_asset
        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        # Create work order
        with patch('models.cmms.maintenance.MaintenanceWorkOrder', return_value=mock_wo):
            wo = service.create_work_order({
                'asset_id': 'AST-001',
                'description': 'Emergency pump repair',
                'wo_type': 'corrective',
                'priority': 'emergency',
            })
        assert wo is not None

        # Start work order - now returns the work order for update
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo
        started = service.start_work_order('MWO-001', 'tech_001')
        assert started is not None

        # Complete work order
        completed = service.complete_work_order('MWO-001', 'Pump seal replaced', 2.5)
        assert completed is not None

    def test_preventive_maintenance_workflow(self, service, mock_session):
        """Test preventive maintenance workflow with tasks."""
        mock_pm = Mock()
        mock_pm.calculate_next_due.return_value = datetime(2026, 2, 21)

        mock_wo = Mock(id=1, actual_hours=0, labor=[], materials=[],
                       downtime_start=None, downtime_end=None,
                       pm_schedule_id='PM-001', pm_schedule=mock_pm)
        mock_wo.wo_number = 'MWO-PM-001'
        mock_wo.to_dict.return_value = {'wo_number': 'MWO-PM-001', 'wo_type': 'preventive'}

        mock_asset = Mock(id=1)

        # For create_work_order - asset lookup
        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        # Create PM work order
        with patch('models.cmms.maintenance.MaintenanceWorkOrder', return_value=mock_wo):
            wo = service.create_work_order({
                'asset_id': 'AST-001',
                'description': 'Monthly lubrication PM',
                'wo_type': 'preventive',
            })
        assert wo is not None

        # Add task - now query returns the work order
        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo
        mock_task = Mock()
        mock_task.to_dict.return_value = {'id': 'task_001', 'name': 'Check oil'}

        with patch('models.cmms.maintenance.WorkOrderTask', return_value=mock_task):
            task = service.add_task('MWO-PM-001', {'name': 'Check oil', 'sequence': 10})
        assert task is not None

        # Complete and verify PM schedule updated
        service.complete_work_order('MWO-PM-001')
        mock_pm.calculate_next_due.assert_called()
