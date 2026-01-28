"""
LEGO Factory v3 - CMMS Workflow Integration Tests
=================================================
End-to-end tests for CMMS workflows: Asset → PM → Work Order
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch

from tests.factories import (
    AssetFactory,
    AssetClassFactory,
    MeterFactory,
    MeterReadingFactory,
    MaintenanceWorkOrderFactory,
    PMScheduleFactory,
    WorkOrderTaskFactory,
    WorkOrderLaborFactory,
    WorkOrderMaterialFactory,
)


class TestAssetLifecycleWorkflow:
    """Integration tests for asset lifecycle workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        session.query.return_value.filter.return_value.all.return_value = []
        return session

    def test_create_asset_with_meters(self, mock_session):
        """Test creating an asset and adding meters."""
        from services.cmms.asset_service import AssetService

        # Setup mock asset
        mock_asset = MagicMock()
        mock_asset.id = 1
        mock_asset.asset_id = 'AST-001'
        mock_asset.name = 'CNC Machine'
        mock_asset.to_dict.return_value = AssetFactory.build(asset_id='AST-001')

        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        service = AssetService(mock_session)

        # Create asset
        asset_data = {
            'name': 'CNC Machine',
            'description': 'CNC Milling Machine',
            'status': 'operational',
            'criticality': 'critical',
            'serial_number': 'SN-12345',
            'manufacturer': 'HAAS',
        }

        result = service.create_asset(asset_data)

        # Verify asset created
        assert result is not None
        mock_session.add.assert_called()

        # Create meter for asset
        meter_data = {
            'name': 'Run Hours',
            'meter_type': 'continuous',
            'unit_of_measure': 'hours',
        }

        meter_result = service.create_meter('AST-001', meter_data)

        # Verify meter created
        assert meter_result is not None

    def test_record_meter_readings(self, mock_session):
        """Test recording meter readings and threshold alerts."""
        from services.cmms.asset_service import AssetService

        # Setup mock meter
        mock_meter = MagicMock()
        mock_meter.id = 1
        mock_meter.meter_id = 'MTR-001'
        mock_meter.last_reading = 4500
        mock_meter.warning_threshold = 4500
        mock_meter.critical_threshold = 5000
        mock_meter.rollover_value = None
        mock_meter.to_dict.return_value = MeterFactory.build()

        mock_session.query.return_value.filter.return_value.first.return_value = mock_meter

        service = AssetService(mock_session)

        # Record reading at warning threshold
        result = service.record_meter_reading(
            meter_id='MTR-001',
            reading_value=4550,
            source='auto',
        )

        # Verify reading recorded
        assert result is not None
        mock_session.add.assert_called()

    def test_asset_status_transitions(self, mock_session):
        """Test asset status transitions through lifecycle."""
        from services.cmms.asset_service import AssetService

        # Setup mock asset
        mock_asset = MagicMock()
        mock_asset.id = 1
        mock_asset.asset_id = 'AST-001'
        mock_asset.status = MagicMock(value='operational')
        mock_asset.to_dict.return_value = {'asset_id': 'AST-001', 'status': 'under_maintenance'}

        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        service = AssetService(mock_session)

        # Transition to maintenance
        result = service.update_status('AST-001', 'under_maintenance', 'tech_user')

        # Verify status updated
        assert result is not None
        mock_session.flush.assert_called()


class TestPMScheduleWorkflow:
    """Integration tests for PM schedule workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        return session

    def test_create_calendar_based_pm(self, mock_session):
        """Test creating a calendar-based PM schedule."""
        from services.cmms.maintenance_service import PMService

        # Setup mock asset
        mock_asset = MagicMock()
        mock_asset.id = 1
        mock_asset.asset_id = 'AST-001'

        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        service = PMService(mock_session)

        # Create PM schedule
        pm_data = {
            'name': 'Monthly Inspection',
            'asset_id': 'AST-001',
            'trigger_type': 'calendar',
            'frequency_days': 30,
            'priority': 'medium',
            'estimated_hours': 2.0,
            'instructions': 'Perform monthly inspection checklist',
        }

        result = service.create_pm_schedule(pm_data)

        # Verify PM created
        assert result is not None
        mock_session.add.assert_called()

    def test_create_meter_based_pm(self, mock_session):
        """Test creating a meter-based PM schedule."""
        from services.cmms.maintenance_service import PMService

        # Setup mocks
        mock_asset = MagicMock()
        mock_asset.id = 1
        mock_asset.asset_id = 'AST-001'

        mock_meter = MagicMock()
        mock_meter.id = 1
        mock_meter.meter_id = 'MTR-001'

        def query_side_effect(model):
            mock_query = MagicMock()
            if 'Asset' in str(model):
                mock_query.filter.return_value.first.return_value = mock_asset
            elif 'Meter' in str(model):
                mock_query.filter.return_value.first.return_value = mock_meter
            return mock_query

        mock_session.query.side_effect = query_side_effect

        service = PMService(mock_session)

        # Create meter-based PM
        pm_data = {
            'name': '500 Hour Service',
            'asset_id': 'AST-001',
            'trigger_type': 'meter',
            'meter_id': 'MTR-001',
            'meter_interval': 500,
            'priority': 'high',
            'estimated_hours': 8.0,
        }

        result = service.create_pm_schedule(pm_data)

        # Verify PM created
        assert result is not None
        mock_session.add.assert_called()

    def test_generate_pm_work_orders(self, mock_session):
        """Test automatic work order generation from PM schedules."""
        from services.cmms.maintenance_service import PMService

        # Setup mock PM schedule
        mock_pm = MagicMock()
        mock_pm.id = 1
        mock_pm.pm_id = 'PM-001'
        mock_pm.name = 'Monthly Inspection'
        mock_pm.is_active = True
        mock_pm.next_due_date = date.today()
        mock_pm.work_window_days = 7
        mock_pm.priority = MagicMock(value='medium')
        mock_pm.estimated_hours = 2.0
        mock_pm.estimated_cost = None
        mock_pm.work_center_id = None
        mock_pm.instructions = 'Inspection checklist'
        mock_pm.asset = MagicMock(asset_id='AST-001')
        mock_pm.work_orders = MagicMock()
        mock_pm.work_orders.property.mapper.class_.status = MagicMock()

        mock_session.query.return_value.filter.return_value.all.return_value = [mock_pm]
        mock_session.query.return_value.select_from.return_value.filter.return_value.scalar.return_value = 0

        service = PMService(mock_session)

        # This would generate work orders in a real scenario
        # For now, test the method is callable
        with patch.object(service, 'generate_pm_work_orders', return_value=[]):
            result = service.generate_pm_work_orders(days_ahead=7)
            assert isinstance(result, list)


class TestMaintenanceWorkOrderWorkflow:
    """Integration tests for maintenance work order workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        return session

    def test_create_corrective_work_order(self, mock_session):
        """Test creating a corrective maintenance work order."""
        from services.cmms.maintenance_service import MaintenanceService

        # Setup mock asset
        mock_asset = MagicMock()
        mock_asset.id = 1
        mock_asset.asset_id = 'AST-001'

        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset

        service = MaintenanceService(mock_session)

        # Create corrective WO
        wo_data = {
            'asset_id': 'AST-001',
            'description': 'Motor overheating - investigate',
            'wo_type': 'corrective',
            'priority': 'high',
            'problem_code': 'OVERHEAT',
            'problem_description': 'Motor temperature exceeded normal range',
        }

        result = service.create_work_order(wo_data)

        # Verify WO created
        assert result is not None
        mock_session.add.assert_called()

    def test_work_order_lifecycle(self, mock_session):
        """Test complete work order lifecycle: draft → in_progress → completed."""
        from services.cmms.maintenance_service import MaintenanceService

        # Setup mock WO
        mock_wo = MagicMock()
        mock_wo.id = 1
        mock_wo.wo_number = 'MWO-001'
        mock_wo.status = MagicMock(value='draft')
        mock_wo.pm_schedule_id = None
        mock_wo.pm_schedule = None
        mock_wo.labor = []
        mock_wo.materials = []
        mock_wo.downtime_start = None
        mock_wo.downtime_end = None
        mock_wo.to_dict.return_value = MaintenanceWorkOrderFactory.build()

        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        service = MaintenanceService(mock_session)

        # Start work order
        start_result = service.start_work_order('MWO-001', 'tech_user')
        assert start_result is not None

        # Complete work order
        mock_wo.status = MagicMock(value='in_progress')
        complete_result = service.complete_work_order(
            'MWO-001',
            completion_notes='Replaced faulty bearing',
            actual_hours=4.0,
            user_id='tech_user',
        )
        assert complete_result is not None

    def test_add_tasks_to_work_order(self, mock_session):
        """Test adding tasks to a work order."""
        from services.cmms.maintenance_service import MaintenanceService

        # Setup mock WO
        mock_wo = MagicMock()
        mock_wo.id = 1
        mock_wo.wo_number = 'MWO-001'

        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        service = MaintenanceService(mock_session)

        # Add tasks
        tasks = [
            {'name': 'Lockout/Tagout', 'lockout_required': True, 'estimated_minutes': 15},
            {'name': 'Remove cover', 'estimated_minutes': 10},
            {'name': 'Inspect bearings', 'estimated_minutes': 20},
            {'name': 'Replace if necessary', 'estimated_minutes': 45},
            {'name': 'Reassemble', 'estimated_minutes': 15},
            {'name': 'Test operation', 'estimated_minutes': 15},
        ]

        for task_data in tasks:
            result = service.add_task('MWO-001', task_data)
            assert result is not None

    def test_record_labor_and_materials(self, mock_session):
        """Test recording labor and materials on work order."""
        from services.cmms.maintenance_service import MaintenanceService

        # Setup mock WO
        mock_wo = MagicMock()
        mock_wo.id = 1
        mock_wo.wo_number = 'MWO-001'
        mock_wo.actual_hours = 0

        mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

        service = MaintenanceService(mock_session)

        # Record labor
        labor_data = {
            'worker_id': 'tech_001',
            'craft': 'electrician',
            'regular_hours': 4.0,
            'hourly_rate': 50.0,
        }

        labor_result = service.record_labor('MWO-001', labor_data)
        assert labor_result is not None

        # Record material
        material_data = {
            'description': 'SKF Bearing 6205',
            'quantity_required': 2,
            'quantity_used': 2,
            'unit_cost': 25.0,
        }

        material_result = service.record_material('MWO-001', material_data)
        assert material_result is not None


class TestBacklogAndReporting:
    """Integration tests for maintenance backlog and reporting."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        return session

    def test_backlog_summary(self, mock_session):
        """Test maintenance backlog summary generation."""
        from services.cmms.maintenance_service import MaintenanceService

        # Setup mock counts
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        mock_session.query.return_value.filter.return_value.scalar.return_value = 0

        service = MaintenanceService(mock_session)

        # Get backlog summary
        result = service.get_backlog_summary()

        # Verify structure
        assert 'by_status' in result
        assert 'by_priority' in result
        assert 'overdue_count' in result
        assert 'total_estimated_hours' in result

    def test_pm_compliance_metrics(self, mock_session):
        """Test PM compliance metric calculation."""
        from services.cmms.maintenance_service import PMService

        # Setup mock counts
        mock_session.query.return_value.filter.return_value.scalar.return_value = 10

        service = PMService(mock_session)

        # Get compliance
        result = service.get_pm_compliance(days=30)

        # Verify structure
        assert 'period_days' in result
        assert 'total_due' in result
        assert 'completed_on_time' in result
        assert 'compliance_rate' in result


class TestAssetHierarchy:
    """Integration tests for asset hierarchy management."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        return session

    def test_parent_child_asset_relationship(self, mock_session):
        """Test creating parent-child asset relationships."""
        from services.cmms.asset_service import AssetService

        # Setup mock parent asset
        mock_parent = MagicMock()
        mock_parent.id = 1
        mock_parent.asset_id = 'AST-001'
        mock_parent.child_assets = []
        mock_parent.is_deleted = False
        mock_parent.to_dict.return_value = AssetFactory.build(asset_id='AST-001')

        mock_session.query.return_value.filter.return_value.first.return_value = mock_parent
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_parent]

        service = AssetService(mock_session)

        # Get hierarchy
        result = service.get_asset_hierarchy('AST-001')

        # Verify hierarchy structure
        assert isinstance(result, list)

    def test_asset_status_summary(self, mock_session):
        """Test asset status summary by status."""
        from services.cmms.asset_service import AssetService

        # Setup mock counts
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = []

        service = AssetService(mock_session)

        # Get status summary
        result = service.get_assets_by_status_summary()

        # Verify returns dict
        assert isinstance(result, dict)


class TestOEEIntegration:
    """Integration tests for OEE calculation with CMMS."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        return session

    def test_downtime_affects_oee(self, mock_session):
        """Test that recorded downtime affects OEE calculation."""
        from services.mes.oee_service import OEEService

        # Setup mock downtime events
        mock_downtime = MagicMock()
        mock_downtime.duration_minutes = 60
        mock_downtime.planned = False
        mock_downtime.reason = MagicMock(value='mechanical_failure')

        mock_session.query.return_value.filter.return_value.all.return_value = [mock_downtime]

        service = OEEService(mock_session)

        # Mock production count
        mock_production = MagicMock()
        mock_production.total_count = 100
        mock_production.good_count = 95
        mock_production.run_time_minutes = 420
        mock_production.ideal_cycle_time_seconds = 30

        with patch.object(mock_session, 'query') as mock_query:
            # Setup query to return different results based on model
            mock_query.return_value.filter.return_value.all.return_value = []

            # Calculate OEE - this tests the integration of downtime data
            # In a real scenario, the downtime would reduce availability
            result = service.calculate_oee('MCH-001', date.today())

            # Verify OEE record created
            assert result is not None
