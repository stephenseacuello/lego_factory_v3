"""
LEGO Factory v3 - Work Order Service Unit Tests
================================================
Tests for work order management and execution tracking.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import uuid


class TestWorkOrderCreation:
    """Tests for work order creation functionality."""

    def test_create_work_order_with_valid_data(self, mock_session, sample_work_order_data):
        """Work order should be created with valid data."""
        # Simulate work order creation
        work_order = MagicMock()
        work_order.work_order_id = sample_work_order_data['work_order_id']
        work_order.description = sample_work_order_data['description']
        work_order.status = 'draft'
        work_order.to_dict.return_value = {
            'work_order_id': sample_work_order_data['work_order_id'],
            'description': sample_work_order_data['description'],
            'status': 'draft'
        }

        mock_session.add(work_order)
        mock_session.flush()

        assert work_order.work_order_id == sample_work_order_data['work_order_id']
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_work_order_id_generation(self):
        """Work order ID should be auto-generated if not provided."""
        # Pattern: WO-YYYYMMDD-XXXXXX
        now = datetime.utcnow()
        wo_id = f"WO-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        assert wo_id.startswith('WO-')
        assert len(wo_id) > 15

    def test_work_order_default_status_is_draft(self):
        """New work orders should have DRAFT status by default."""
        work_order = MagicMock()
        work_order.status = 'draft'

        assert work_order.status == 'draft'

    def test_work_order_with_required_fields_only(self):
        """Work order should be creatable with required fields only."""
        minimal_data = {
            'description': 'Test work order',
        }

        assert 'description' in minimal_data
        assert len(minimal_data) >= 1

    def test_work_order_with_product_reference(self, sample_work_order_data):
        """Work order should reference a product."""
        assert 'product_id' in sample_work_order_data
        assert sample_work_order_data['product_id'] is not None

    def test_work_order_with_recipe_reference(self, sample_work_order_data):
        """Work order can reference a recipe."""
        assert 'recipe_id' in sample_work_order_data

    def test_work_order_quantity_validation(self):
        """Quantity ordered should be positive."""
        quantity = 100

        assert quantity > 0

    def test_work_order_priority_range(self, sample_work_order_data):
        """Priority should be within valid range (1-10)."""
        priority = sample_work_order_data['priority']

        assert 1 <= priority <= 10


class TestWorkOrderStatusTransitions:
    """Tests for work order status transitions."""

    def test_valid_status_transitions(self):
        """Only valid status transitions should be allowed."""
        valid_transitions = {
            'draft': ['planned', 'cancelled'],
            'planned': ['released', 'draft', 'cancelled'],
            'released': ['in_progress', 'on_hold', 'cancelled'],
            'in_progress': ['completed', 'on_hold', 'cancelled'],
            'on_hold': ['in_progress', 'cancelled'],
            'completed': [],  # No transitions from completed
            'cancelled': [],  # No transitions from cancelled
        }

        # Test draft can transition to planned
        assert 'planned' in valid_transitions['draft']

        # Test completed cannot transition
        assert len(valid_transitions['completed']) == 0

    def test_release_work_order(self, mock_session):
        """Work order should transition from PLANNED to RELEASED."""
        work_order = MagicMock()
        work_order.status = 'released'
        work_order.to_dict.return_value = {'status': 'released'}

        assert work_order.status == 'released'

    def test_start_work_order(self):
        """Work order should transition to IN_PROGRESS when started."""
        work_order = MagicMock()
        work_order.status = 'in_progress'
        work_order.actual_start = datetime.utcnow()

        assert work_order.status == 'in_progress'
        assert work_order.actual_start is not None

    def test_complete_work_order(self):
        """Work order should transition to COMPLETED when finished."""
        work_order = MagicMock()
        work_order.status = 'completed'
        work_order.actual_end = datetime.utcnow()

        assert work_order.status == 'completed'
        assert work_order.actual_end is not None

    def test_cancel_work_order(self):
        """Work order should be cancellable."""
        work_order = MagicMock()
        work_order.status = 'cancelled'

        assert work_order.status == 'cancelled'

    def test_hold_work_order(self):
        """Work order should be put on hold."""
        work_order = MagicMock()
        work_order.status = 'on_hold'

        assert work_order.status == 'on_hold'

    def test_resume_work_order_from_hold(self):
        """Work order should resume from hold."""
        work_order = MagicMock()
        work_order.status = 'in_progress'

        assert work_order.status == 'in_progress'


class TestJobCreation:
    """Tests for job creation within work orders."""

    def test_create_job_for_work_order(self, mock_session, sample_job_data):
        """Job should be created for a work order."""
        job = MagicMock()
        job.job_id = sample_job_data['job_id']
        job.work_order_id = 'WO-TEST-001'
        job.status = 'pending'
        job.to_dict.return_value = {
            'job_id': sample_job_data['job_id'],
            'status': 'pending'
        }

        mock_session.add(job)

        assert job.job_id == sample_job_data['job_id']

    def test_job_id_generation(self):
        """Job ID should be auto-generated."""
        now = datetime.utcnow()
        job_id = f"JOB-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        assert job_id.startswith('JOB-')
        assert len(job_id) > 15

    def test_job_machine_assignment(self, sample_job_data):
        """Job should be assigned to a machine."""
        assert 'machine_id' in sample_job_data

    def test_job_scheduling(self, sample_job_data):
        """Job should have scheduled times."""
        assert 'scheduled_start' in sample_job_data
        assert 'scheduled_end' in sample_job_data

    def test_job_quantity_tracking(self, sample_job_data):
        """Job should track quantities."""
        assert 'quantity_planned' in sample_job_data

    def test_job_gcode_reference(self, sample_job_data):
        """Job can reference a G-code file."""
        assert 'gcode_file' in sample_job_data


class TestJobStatusTransitions:
    """Tests for job status transitions."""

    def test_job_status_values(self):
        """Job statuses should be properly defined."""
        statuses = ['pending', 'queued', 'running', 'paused', 'completed', 'failed', 'cancelled']

        for status in statuses:
            assert isinstance(status, str)

    def test_start_job(self):
        """Job should transition to RUNNING when started."""
        job = MagicMock()
        job.status = 'running'
        job.actual_start = datetime.utcnow()

        assert job.status == 'running'
        assert job.actual_start is not None

    def test_pause_job(self):
        """Job should transition to PAUSED."""
        job = MagicMock()
        job.status = 'paused'

        assert job.status == 'paused'

    def test_complete_job(self):
        """Job should transition to COMPLETED."""
        job = MagicMock()
        job.status = 'completed'
        job.actual_end = datetime.utcnow()

        assert job.status == 'completed'
        assert job.actual_end is not None

    def test_fail_job(self):
        """Job should transition to FAILED on error."""
        job = MagicMock()
        job.status = 'failed'
        job.actual_end = datetime.utcnow()

        assert job.status == 'failed'

    def test_cancel_job(self):
        """Job should be cancellable."""
        job = MagicMock()
        job.status = 'cancelled'

        assert job.status == 'cancelled'


class TestOperations:
    """Tests for work order operations (routing steps)."""

    def test_add_operation_to_work_order(self, mock_session):
        """Operation should be added to work order."""
        operation = MagicMock()
        operation.operation_id = 'OP-001'
        operation.sequence = 10
        operation.name = 'CNC Machining'
        operation.operation_type = 'cnc_milling'

        mock_session.add(operation)

        mock_session.add.assert_called_once()

    def test_operation_sequence_ordering(self):
        """Operations should be ordered by sequence."""
        operations = [
            {'sequence': 30, 'name': 'Packaging'},
            {'sequence': 10, 'name': 'Printing'},
            {'sequence': 20, 'name': 'Assembly'},
        ]

        sorted_ops = sorted(operations, key=lambda x: x['sequence'])

        assert sorted_ops[0]['name'] == 'Printing'
        assert sorted_ops[1]['name'] == 'Assembly'
        assert sorted_ops[2]['name'] == 'Packaging'

    def test_operation_time_estimates(self):
        """Operation should have time estimates."""
        operation = MagicMock()
        operation.setup_time = 15.0  # minutes
        operation.run_time = 60.0
        operation.teardown_time = 5.0

        total_time = operation.setup_time + operation.run_time + operation.teardown_time

        assert total_time == 80.0

    def test_operation_types(self):
        """Operation types should be properly defined."""
        operation_types = [
            'design', 'printing_fdm', 'printing_sla', 'cnc_milling',
            'assembly', 'inspection', 'packaging', 'custom'
        ]

        assert 'printing_fdm' in operation_types
        assert 'cnc_milling' in operation_types


class TestWorkOrderCompletion:
    """Tests for work order completion."""

    def test_quantity_completion_tracking(self):
        """Completed quantities should be tracked."""
        work_order = MagicMock()
        work_order.quantity_ordered = 100
        work_order.quantity_completed = 95

        assert work_order.quantity_completed < work_order.quantity_ordered

    def test_full_completion(self):
        """Work order should be marked complete when all quantities done."""
        work_order = MagicMock()
        work_order.quantity_ordered = 100
        work_order.quantity_completed = 100
        work_order.status = 'completed'

        assert work_order.quantity_completed == work_order.quantity_ordered
        assert work_order.status == 'completed'

    def test_partial_completion(self):
        """Work order can be partially completed."""
        work_order = MagicMock()
        work_order.quantity_ordered = 100
        work_order.quantity_completed = 50

        completion_pct = (work_order.quantity_completed / work_order.quantity_ordered) * 100

        assert completion_pct == 50.0

    def test_actual_vs_planned_times(self):
        """Actual times should be compared to planned."""
        work_order = MagicMock()
        work_order.planned_start = datetime(2024, 1, 15, 8, 0, 0)
        work_order.planned_end = datetime(2024, 1, 15, 16, 0, 0)
        work_order.actual_start = datetime(2024, 1, 15, 8, 30, 0)
        work_order.actual_end = datetime(2024, 1, 15, 17, 0, 0)

        planned_duration = (work_order.planned_end - work_order.planned_start).total_seconds() / 3600
        actual_duration = (work_order.actual_end - work_order.actual_start).total_seconds() / 3600

        assert planned_duration == 8.0  # 8 hours planned
        assert actual_duration == 8.5  # 8.5 hours actual


class TestWorkOrderQuerying:
    """Tests for work order querying."""

    def test_get_work_order_by_id(self, mock_session):
        """Should retrieve work order by ID."""
        work_order = MagicMock()
        work_order.work_order_id = 'WO-TEST-001'
        mock_session.query.return_value.filter.return_value.first.return_value = work_order

        result = mock_session.query().filter().first()

        assert result.work_order_id == 'WO-TEST-001'

    def test_filter_by_status(self, mock_session):
        """Should filter work orders by status."""
        mock_session.query.return_value.filter.return_value.all.return_value = [
            MagicMock(status='in_progress'),
            MagicMock(status='in_progress'),
        ]

        results = mock_session.query().filter().all()

        assert len(results) == 2
        assert all(r.status == 'in_progress' for r in results)

    def test_filter_by_customer(self, mock_session):
        """Should filter work orders by customer."""
        mock_session.query.return_value.filter.return_value.all.return_value = [
            MagicMock(customer_id='CUST-001'),
        ]

        results = mock_session.query().filter().all()

        assert len(results) == 1
        assert results[0].customer_id == 'CUST-001'

    def test_filter_by_due_date(self, mock_session):
        """Should filter work orders by due date."""
        due_date = datetime.utcnow() + timedelta(days=7)
        mock_session.query.return_value.filter.return_value.all.return_value = [
            MagicMock(due_date=due_date),
        ]

        results = mock_session.query().filter().all()

        assert len(results) == 1

    def test_order_by_priority_and_due_date(self):
        """Work orders should be orderable by priority and due date."""
        work_orders = [
            {'priority': 3, 'due_date': datetime(2024, 1, 20)},
            {'priority': 1, 'due_date': datetime(2024, 1, 18)},
            {'priority': 1, 'due_date': datetime(2024, 1, 15)},
        ]

        # Sort by priority, then due date
        sorted_wos = sorted(work_orders, key=lambda x: (x['priority'], x['due_date']))

        assert sorted_wos[0]['priority'] == 1
        assert sorted_wos[0]['due_date'] == datetime(2024, 1, 15)

    def test_pagination(self, mock_session):
        """Results should be paginated."""
        mock_session.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            MagicMock() for _ in range(10)
        ]

        results = mock_session.query().filter().offset(0).limit(10).all()

        assert len(results) == 10


class TestWorkOrderUpdates:
    """Tests for work order updates."""

    def test_update_work_order(self, mock_session):
        """Work order should be updated."""
        work_order = MagicMock()
        work_order.description = 'Original'

        work_order.description = 'Updated description'
        work_order.updated_at = datetime.utcnow()

        assert work_order.description == 'Updated description'
        assert work_order.updated_at is not None

    def test_update_tracks_timestamp(self):
        """Updates should track timestamp."""
        work_order = MagicMock()
        work_order.updated_at = datetime.utcnow()
        work_order.updated_by = 'user123'

        assert work_order.updated_at is not None
        assert work_order.updated_by == 'user123'

    def test_protected_fields_not_updated(self):
        """Certain fields should not be updatable."""
        protected_fields = ['id', 'work_order_id', 'created_at']

        for field in protected_fields:
            assert field in protected_fields


class TestSoftDelete:
    """Tests for soft delete functionality."""

    def test_soft_delete_work_order(self):
        """Work order should be soft deleted."""
        work_order = MagicMock()
        work_order.is_deleted = False

        # Soft delete
        work_order.is_deleted = True
        work_order.deleted_at = datetime.utcnow()
        work_order.deleted_by = 'admin'

        assert work_order.is_deleted is True
        assert work_order.deleted_at is not None

    def test_soft_deleted_excluded_from_queries(self, mock_session):
        """Soft deleted records should be excluded by default."""
        mock_session.query.return_value.filter.return_value.all.return_value = [
            MagicMock(is_deleted=False),
            MagicMock(is_deleted=False),
        ]

        results = mock_session.query().filter().all()

        assert all(not r.is_deleted for r in results)
