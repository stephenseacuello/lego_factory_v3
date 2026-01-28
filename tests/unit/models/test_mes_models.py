"""
LEGO Factory v3 - MES Models Unit Tests
=======================================
"""

import pytest
from datetime import datetime, timedelta


class TestWorkOrderModel:
    """Tests for WorkOrder model."""

    def test_create_work_order(self, db_session, sample_work_order_data):
        """Test creating a work order."""
        from models.mes.work_orders import WorkOrder

        wo = WorkOrder(**sample_work_order_data)
        db_session.add(wo)
        db_session.flush()

        assert wo.id is not None
        assert wo.work_order_id == 'WO-TEST-001'
        assert wo.quantity_ordered == 100
        assert wo.quantity_completed == 0

    def test_work_order_to_dict(self, db_session, sample_work_order_data):
        """Test work order serialization."""
        from models.mes.work_orders import WorkOrder

        wo = WorkOrder(**sample_work_order_data)
        db_session.add(wo)
        db_session.flush()

        data = wo.to_dict()

        assert 'work_order_id' in data
        assert 'status' in data
        assert 'quantity_ordered' in data

    def test_work_order_status_values(self, db_session, sample_work_order_data):
        """Test work order status transitions."""
        from models.mes.work_orders import WorkOrder, WorkOrderStatus

        wo = WorkOrder(**sample_work_order_data)
        db_session.add(wo)
        db_session.flush()

        # Test status can be changed
        wo.status = WorkOrderStatus.RELEASED
        db_session.flush()
        assert wo.status == WorkOrderStatus.RELEASED

        wo.status = WorkOrderStatus.IN_PROGRESS
        db_session.flush()
        assert wo.status == WorkOrderStatus.IN_PROGRESS


class TestJobModel:
    """Tests for Job model."""

    def test_create_job(self, db_session, sample_work_order_data):
        """Test creating a job."""
        from models.mes.work_orders import WorkOrder, Job, JobStatus

        wo = WorkOrder(**sample_work_order_data)
        db_session.add(wo)
        db_session.flush()

        job = Job(
            job_id='JOB-TEST-001',
            work_order_id=wo.id,
            machine_id='test_machine',
            status=JobStatus.PENDING,
            quantity_planned=10,
        )
        db_session.add(job)
        db_session.flush()

        assert job.id is not None
        assert job.job_id == 'JOB-TEST-001'
        assert job.status == JobStatus.PENDING


class TestOperationModel:
    """Tests for Operation model."""

    def test_create_operation(self, db_session, sample_work_order_data):
        """Test creating an operation."""
        from models.mes.work_orders import WorkOrder, Operation, OperationType

        wo = WorkOrder(**sample_work_order_data)
        db_session.add(wo)
        db_session.flush()

        op = Operation(
            work_order_id=wo.id,
            operation_id='OP-001',
            sequence=10,
            operation_type=OperationType.PRINTING_FDM,
            name='Print Part',
            run_time=60,
        )
        db_session.add(op)
        db_session.flush()

        assert op.id is not None
        assert op.sequence == 10


class TestWorkerModel:
    """Tests for Worker model."""

    def test_create_worker(self, db_session):
        """Test creating a worker."""
        from models.mes.labor import Worker, WorkerStatus

        worker = Worker(
            worker_id='EMP-TEST-001',
            first_name='Test',
            last_name='Worker',
            email='test@example.com',
            department='Production',
            status=WorkerStatus.ACTIVE,
        )
        db_session.add(worker)
        db_session.flush()

        assert worker.id is not None
        assert worker.worker_id == 'EMP-TEST-001'
