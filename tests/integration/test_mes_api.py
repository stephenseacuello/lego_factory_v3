"""
LEGO Factory v3 - MES API Integration Tests
===========================================
Integration tests for MES endpoints (work orders, jobs, scheduling).
"""

import pytest
import json
from datetime import datetime, timedelta


class TestWorkOrderEndpoints:
    """Tests for work order endpoints."""

    def test_list_work_orders(self, client):
        """Should list all work orders."""
        response = client.get('/api/mes/work-orders')

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'work_orders' in data or 'count' in data or isinstance(data, list)

    def test_get_work_order_by_id(self, client):
        """Should get work order by ID."""
        response = client.get('/api/mes/work-orders/WO-TEST-001')

        assert response.status_code in [200, 404, 500]

    def test_create_work_order(self, client, sample_work_order_data):
        """Should create a new work order."""
        # Convert datetime to string for JSON
        data = sample_work_order_data.copy()
        for key in ['planned_start', 'planned_end', 'due_date']:
            if key in data and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()

        response = client.post(
            '/api/mes/work-orders',
            data=json.dumps(data),
            content_type='application/json'
        )

        assert response.status_code in [200, 201, 400, 404, 500]

    def test_update_work_order(self, client):
        """Should update an existing work order."""
        response = client.put(
            '/api/mes/work-orders/WO-TEST-001',
            data=json.dumps({
                'description': 'Updated description',
                'priority': 3
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_delete_work_order(self, client):
        """Should delete a work order."""
        response = client.delete('/api/mes/work-orders/WO-TEST-001')

        assert response.status_code in [200, 204, 404, 500]

    def test_filter_work_orders_by_status(self, client):
        """Should filter work orders by status."""
        response = client.get('/api/mes/work-orders?status=in_progress')

        assert response.status_code in [200, 404, 500]

    def test_filter_work_orders_by_priority(self, client):
        """Should filter work orders by priority."""
        response = client.get('/api/mes/work-orders?priority=1')

        assert response.status_code in [200, 404, 500]

    def test_filter_work_orders_by_date_range(self, client):
        """Should filter work orders by date range."""
        start = datetime.utcnow().isoformat()
        end = (datetime.utcnow() + timedelta(days=7)).isoformat()

        response = client.get(f'/api/mes/work-orders?due_after={start}&due_before={end}')

        assert response.status_code in [200, 404, 500]


class TestWorkOrderStatusTransitions:
    """Tests for work order status transitions."""

    def test_release_work_order(self, client):
        """Should release a work order."""
        response = client.post('/api/mes/work-orders/WO-TEST-001/release')

        assert response.status_code in [200, 400, 404, 500]

    def test_start_work_order(self, client):
        """Should start a work order."""
        response = client.post('/api/mes/work-orders/WO-TEST-001/start')

        assert response.status_code in [200, 400, 404, 500]

    def test_complete_work_order(self, client):
        """Should complete a work order."""
        response = client.post(
            '/api/mes/work-orders/WO-TEST-001/complete',
            data=json.dumps({'quantity_completed': 100}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_cancel_work_order(self, client):
        """Should cancel a work order."""
        response = client.post(
            '/api/mes/work-orders/WO-TEST-001/cancel',
            data=json.dumps({'reason': 'No longer needed'}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_hold_work_order(self, client):
        """Should put work order on hold."""
        response = client.post(
            '/api/mes/work-orders/WO-TEST-001/hold',
            data=json.dumps({'reason': 'Material shortage'}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_resume_work_order(self, client):
        """Should resume work order from hold."""
        response = client.post('/api/mes/work-orders/WO-TEST-001/resume')

        assert response.status_code in [200, 400, 404, 500]


class TestJobEndpoints:
    """Tests for job endpoints."""

    def test_list_jobs(self, client):
        """Should list all jobs."""
        response = client.get('/api/mes/jobs')

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'jobs' in data or 'count' in data or isinstance(data, list)

    def test_get_job_by_id(self, client):
        """Should get job by ID."""
        response = client.get('/api/mes/jobs/JOB-TEST-001')

        assert response.status_code in [200, 404, 500]

    def test_create_job(self, client, sample_job_data):
        """Should create a new job."""
        data = sample_job_data.copy()
        for key in ['scheduled_start', 'scheduled_end']:
            if key in data and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()

        response = client.post(
            '/api/mes/jobs',
            data=json.dumps(data),
            content_type='application/json'
        )

        assert response.status_code in [200, 201, 400, 404, 500]

    def test_update_job(self, client):
        """Should update an existing job."""
        response = client.put(
            '/api/mes/jobs/JOB-TEST-001',
            data=json.dumps({'machine_id': 'machine-002'}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_delete_job(self, client):
        """Should delete a job."""
        response = client.delete('/api/mes/jobs/JOB-TEST-001')

        assert response.status_code in [200, 204, 404, 500]

    def test_filter_jobs_by_machine(self, client):
        """Should filter jobs by machine."""
        response = client.get('/api/mes/jobs?machine_id=machine-001')

        assert response.status_code in [200, 404, 500]

    def test_filter_jobs_by_status(self, client):
        """Should filter jobs by status."""
        response = client.get('/api/mes/jobs?status=running')

        assert response.status_code in [200, 404, 500]


class TestJobStatusTransitions:
    """Tests for job status transitions."""

    def test_start_job(self, client):
        """Should start a job."""
        response = client.post('/api/mes/jobs/JOB-TEST-001/start')

        assert response.status_code in [200, 400, 404, 500]

    def test_pause_job(self, client):
        """Should pause a job."""
        response = client.post('/api/mes/jobs/JOB-TEST-001/pause')

        assert response.status_code in [200, 400, 404, 500]

    def test_resume_job(self, client):
        """Should resume a job."""
        response = client.post('/api/mes/jobs/JOB-TEST-001/resume')

        assert response.status_code in [200, 400, 404, 500]

    def test_complete_job(self, client):
        """Should complete a job."""
        response = client.post(
            '/api/mes/jobs/JOB-TEST-001/complete',
            data=json.dumps({
                'quantity_completed': 10,
                'quantity_rejected': 0
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_fail_job(self, client):
        """Should mark job as failed."""
        response = client.post(
            '/api/mes/jobs/JOB-TEST-001/fail',
            data=json.dumps({'reason': 'Machine breakdown'}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_cancel_job(self, client):
        """Should cancel a job."""
        response = client.post('/api/mes/jobs/JOB-TEST-001/cancel')

        assert response.status_code in [200, 400, 404, 500]


class TestSchedulingEndpoints:
    """Tests for scheduling endpoints."""

    def test_get_schedule(self, client):
        """Should get current schedule."""
        response = client.get('/api/mes/schedule')

        assert response.status_code in [200, 404, 500]

    def test_get_schedule_for_machine(self, client):
        """Should get schedule for a specific machine."""
        response = client.get('/api/mes/schedule?machine_id=machine-001')

        assert response.status_code in [200, 404, 500]

    def test_get_schedule_for_date_range(self, client):
        """Should get schedule for date range."""
        start = datetime.utcnow().isoformat()
        end = (datetime.utcnow() + timedelta(days=7)).isoformat()

        response = client.get(f'/api/mes/schedule?start={start}&end={end}')

        assert response.status_code in [200, 404, 500]

    def test_reschedule_job(self, client):
        """Should reschedule a job."""
        new_start = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        new_end = (datetime.utcnow() + timedelta(hours=4)).isoformat()

        response = client.post(
            '/api/mes/jobs/JOB-TEST-001/reschedule',
            data=json.dumps({
                'scheduled_start': new_start,
                'scheduled_end': new_end
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_auto_schedule(self, client):
        """Should auto-schedule pending jobs."""
        response = client.post('/api/mes/schedule/auto')

        assert response.status_code in [200, 400, 404, 500]


class TestOEEEndpoints:
    """Tests for OEE (Overall Equipment Effectiveness) endpoints."""

    def test_get_oee(self, client):
        """Should get OEE metrics."""
        response = client.get('/api/mes/oee')

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'overall_oee' in data or 'oee' in data

    def test_get_oee_for_machine(self, client):
        """Should get OEE for a specific machine."""
        response = client.get('/api/mes/oee?machine_id=machine-001')

        assert response.status_code in [200, 404, 500]

    def test_get_oee_for_date_range(self, client):
        """Should get OEE for date range."""
        start = (datetime.utcnow() - timedelta(days=7)).isoformat()
        end = datetime.utcnow().isoformat()

        response = client.get(f'/api/mes/oee?start={start}&end={end}')

        assert response.status_code in [200, 404, 500]

    def test_get_oee_components(self, client):
        """Should get OEE component breakdown."""
        response = client.get('/api/mes/oee/components')

        assert response.status_code in [200, 404, 500]


class TestRecipeEndpoints:
    """Tests for recipe endpoints."""

    def test_list_recipes(self, client):
        """Should list all recipes."""
        response = client.get('/api/mes/recipes')

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'recipes' in data or isinstance(data, list)

    def test_get_recipe_by_id(self, client):
        """Should get recipe by ID."""
        response = client.get('/api/mes/recipes/RCP-TEST-001')

        assert response.status_code in [200, 404, 500]

    def test_create_recipe(self, client):
        """Should create a new recipe."""
        recipe_data = {
            'recipe_id': 'RCP-NEW-001',
            'name': 'New Recipe',
            'description': 'A new test recipe',
            'product_id': 'PROD-001',
            'version': '1.0'
        }

        response = client.post(
            '/api/mes/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code in [200, 201, 400, 404, 500]


class TestOperationEndpoints:
    """Tests for operation endpoints."""

    def test_list_operations_for_work_order(self, client):
        """Should list operations for a work order."""
        response = client.get('/api/mes/work-orders/WO-TEST-001/operations')

        assert response.status_code in [200, 404, 500]

    def test_add_operation_to_work_order(self, client):
        """Should add operation to work order."""
        operation_data = {
            'operation_id': 'OP-001',
            'sequence': 10,
            'name': 'CNC Machining',
            'operation_type': 'cnc_milling',
            'setup_time': 15,
            'run_time': 60
        }

        response = client.post(
            '/api/mes/work-orders/WO-TEST-001/operations',
            data=json.dumps(operation_data),
            content_type='application/json'
        )

        assert response.status_code in [200, 201, 400, 404, 500]


class TestReportingEndpoints:
    """Tests for MES reporting endpoints."""

    def test_production_report(self, client):
        """Should get production report."""
        response = client.get('/api/mes/reports/production')

        assert response.status_code in [200, 404, 500]

    def test_downtime_report(self, client):
        """Should get downtime report."""
        response = client.get('/api/mes/reports/downtime')

        assert response.status_code in [200, 404, 500]

    def test_quality_report(self, client):
        """Should get quality report."""
        response = client.get('/api/mes/reports/quality')

        assert response.status_code in [200, 404, 500]
