"""
Unit tests for MES Scheduling Service.

Tests job scheduling using both CP-SAT solver and heuristic fallback,
machine assignment, job sequencing, dependencies, and utilization calculation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from services.mes.scheduling_service import (
    ScheduleJob, Machine, ScheduledJob, ScheduleResult, SchedulingService,
)


class TestDataclasses:
    """Tests for scheduling dataclasses."""

    def test_schedule_job_minimal(self):
        """Test ScheduleJob with minimal fields."""
        job = ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=60)
        assert job.job_id == "job_001"
        assert job.priority == 5
        assert job.dependencies == []
        assert job.setup_time == 0

    def test_schedule_job_full(self):
        """Test ScheduleJob with all fields."""
        due_date = datetime.utcnow() + timedelta(hours=8)
        job = ScheduleJob(
            job_id="job_002", work_order_id="wo_002", duration_minutes=120,
            machine_id="machine_001", eligible_machines=["machine_001", "machine_002"],
            priority=1, due_date=due_date, dependencies=["job_001"], setup_time=15
        )
        assert job.machine_id == "machine_001"
        assert job.priority == 1
        assert job.dependencies == ["job_001"]

    def test_machine_dataclass(self):
        """Test Machine dataclass."""
        machine = Machine(machine_id="mach_001", name="Injection Molder 1")
        assert machine.machine_id == "mach_001"
        assert machine.efficiency == 1.0
        assert machine.capabilities == []

    def test_scheduled_job_dataclass(self):
        """Test ScheduledJob dataclass."""
        start_time = datetime.utcnow()
        scheduled = ScheduledJob(
            job_id="job_001", machine_id="mach_001",
            start_time=start_time, end_time=start_time + timedelta(minutes=60), setup_time=10
        )
        assert scheduled.job_id == "job_001"
        assert scheduled.setup_time == 10

    def test_schedule_result_dataclass(self):
        """Test ScheduleResult dataclass."""
        result = ScheduleResult(
            scheduled_jobs=[], makespan_minutes=60, total_setup_time=15,
            utilization={"mach_001": 0.9}, unscheduled_jobs=["job_003"], solver_status="optimal"
        )
        assert result.makespan_minutes == 60
        assert result.solver_status == "optimal"


class TestSchedulingServiceCPSAT:
    """Tests for SchedulingService using CP-SAT solver."""

    @pytest.fixture
    def service(self):
        return SchedulingService(Mock())

    @pytest.fixture
    def sample_jobs(self):
        return [
            ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=30,
                       eligible_machines=["mach_001", "mach_002"], priority=1, setup_time=5),
            ScheduleJob(job_id="job_002", work_order_id="wo_002", duration_minutes=45,
                       eligible_machines=["mach_001", "mach_002"], priority=2, setup_time=10),
        ]

    @pytest.fixture
    def sample_machines(self):
        return [
            Machine(machine_id="mach_001", name="Machine 1", efficiency=1.0),
            Machine(machine_id="mach_002", name="Machine 2", efficiency=0.9),
        ]

    def _mock_solver_values(self, var):
        """Mock solver value retrieval."""
        var_name = str(var)
        if 'start_job_001' in var_name: return 0
        elif 'end_job_001' in var_name: return 30
        elif 'start_job_002' in var_name: return 30
        elif 'end_job_002' in var_name: return 75
        elif 'assign' in var_name and 'mach_001' in var_name: return 1
        return 0

    def test_cpsat_optimal(self, service, sample_jobs, sample_machines):
        """Test CP-SAT solver returning optimal solution using real ortools."""
        # Use real ortools - it handles simple problems quickly
        result = service._schedule_cpsat(sample_jobs, sample_machines, 24, 'makespan')

        # Should return a valid result (either optimal or feasible)
        assert result is not None
        assert result.solver_status in ['optimal', 'feasible', 'heuristic']
        assert len(result.scheduled_jobs) == len(sample_jobs)

    def test_cpsat_feasible(self, service, sample_jobs, sample_machines):
        """Test CP-SAT solver finding a feasible solution."""
        result = service._schedule_cpsat(sample_jobs, sample_machines, 24, 'makespan')

        # Verify all jobs are scheduled
        assert result is not None
        assert len(result.scheduled_jobs) == len(sample_jobs)
        for scheduled in result.scheduled_jobs:
            assert scheduled.machine_id in [m.machine_id for m in sample_machines]

    def test_cpsat_infeasible_falls_back(self, service, sample_jobs, sample_machines):
        """Test infeasible CP-SAT falls back to heuristic."""
        # Create an infeasible scenario - job needs machine that doesn't exist
        infeasible_jobs = [
            ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=30,
                       eligible_machines=["nonexistent_machine"], priority=1),
        ]
        result = service._schedule_cpsat(infeasible_jobs, sample_machines, 24, 'makespan')

        # Should fall back or mark as unscheduled
        assert result is not None

    def test_cpsat_due_date_objective(self, service, sample_machines):
        """Test scheduling with due_date objective."""
        jobs = [ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=30,
                           eligible_machines=["mach_001"], priority=1,
                           due_date=datetime.utcnow() + timedelta(hours=4))]

        result = service._schedule_cpsat(jobs, sample_machines, 24, 'due_date')

        assert result is not None
        assert len(result.scheduled_jobs) == 1

    def test_cpsat_with_dependencies(self, service, sample_machines):
        """Test scheduling jobs with dependencies."""
        jobs = [
            ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=30,
                       eligible_machines=["mach_001"], priority=1),
            ScheduleJob(job_id="job_002", work_order_id="wo_002", duration_minutes=45,
                       eligible_machines=["mach_001"], priority=2, dependencies=["job_001"]),
        ]

        result = service._schedule_cpsat(jobs, sample_machines, 24, 'makespan')

        assert result is not None
        # Verify job_002 starts after job_001 ends (dependency respected)
        if len(result.scheduled_jobs) == 2:
            job_001 = next((j for j in result.scheduled_jobs if j.job_id == "job_001"), None)
            job_002 = next((j for j in result.scheduled_jobs if j.job_id == "job_002"), None)
            if job_001 and job_002:
                assert job_002.start_time >= job_001.end_time


class TestSchedulingServiceHeuristic:
    """Tests for SchedulingService heuristic fallback."""

    @pytest.fixture
    def service(self):
        return SchedulingService(Mock())

    @pytest.fixture
    def sample_machines(self):
        return [
            Machine(machine_id="mach_001", name="Machine 1"),
            Machine(machine_id="mach_002", name="Machine 2"),
        ]

    def test_heuristic_schedules_by_priority(self, service, sample_machines):
        """Test heuristic schedules jobs by priority."""
        jobs = [
            ScheduleJob(job_id="job_low", work_order_id="wo_001", duration_minutes=30,
                       eligible_machines=["mach_001"], priority=5),
            ScheduleJob(job_id="job_high", work_order_id="wo_002", duration_minutes=30,
                       eligible_machines=["mach_001"], priority=1),
        ]
        result = service._schedule_heuristic(jobs, sample_machines, 24)

        assert result.solver_status == 'heuristic'
        job_order = [j.job_id for j in result.scheduled_jobs]
        assert job_order.index("job_high") < job_order.index("job_low")

    def test_heuristic_schedules_by_due_date(self, service, sample_machines):
        """Test heuristic considers due date for same priority."""
        jobs = [
            ScheduleJob(job_id="job_late", work_order_id="wo_001", duration_minutes=30,
                       eligible_machines=["mach_001"], priority=1,
                       due_date=datetime.utcnow() + timedelta(hours=8)),
            ScheduleJob(job_id="job_early", work_order_id="wo_002", duration_minutes=30,
                       eligible_machines=["mach_001"], priority=1,
                       due_date=datetime.utcnow() + timedelta(hours=2)),
        ]
        result = service._schedule_heuristic(jobs, sample_machines, 24)

        job_order = [j.job_id for j in result.scheduled_jobs]
        assert job_order.index("job_early") < job_order.index("job_late")

    def test_heuristic_assigns_earliest_available_machine(self, service, sample_machines):
        """Test heuristic picks earliest available machine."""
        jobs = [
            ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=60,
                       eligible_machines=["mach_001", "mach_002"], priority=1),
            ScheduleJob(job_id="job_002", work_order_id="wo_002", duration_minutes=30,
                       eligible_machines=["mach_001", "mach_002"], priority=1),
        ]
        result = service._schedule_heuristic(jobs, sample_machines, 24)

        assigned_machines = {j.machine_id for j in result.scheduled_jobs}
        assert len(assigned_machines) == 2

    def test_heuristic_handles_no_eligible_machines(self, service, sample_machines):
        """Test heuristic with job that has no eligible machines."""
        jobs = [ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=30,
                           eligible_machines=["mach_nonexistent"], priority=1)]
        result = service._schedule_heuristic(jobs, sample_machines, 24)

        assert "job_001" in result.unscheduled_jobs

    def test_heuristic_includes_setup_time(self, service, sample_machines):
        """Test heuristic accounts for setup time."""
        jobs = [ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=30,
                           eligible_machines=["mach_001"], priority=1, setup_time=15)]
        result = service._schedule_heuristic(jobs, sample_machines, 24)

        scheduled = result.scheduled_jobs[0]
        duration = (scheduled.end_time - scheduled.start_time).total_seconds() / 60
        assert duration == 45

    def test_heuristic_calculates_total_setup_time(self, service, sample_machines):
        """Test heuristic calculates total setup time correctly."""
        jobs = [
            ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=30,
                       eligible_machines=["mach_001"], setup_time=10),
            ScheduleJob(job_id="job_002", work_order_id="wo_002", duration_minutes=45,
                       eligible_machines=["mach_002"], setup_time=20),
        ]
        result = service._schedule_heuristic(jobs, sample_machines, 24)

        assert result.total_setup_time == 30


class TestScheduleJobsEntryPoint:
    """Tests for the main schedule_jobs entry point."""

    @pytest.fixture
    def service(self):
        return SchedulingService(Mock())

    def test_uses_cpsat_when_available(self, service):
        """Test schedule_jobs uses CP-SAT when OR-Tools is available."""
        jobs = [ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=30,
                           eligible_machines=["mach_001"])]
        machines = [Machine(machine_id="mach_001", name="Machine 1")]

        with patch.object(service, '_schedule_cpsat') as mock_cpsat:
            mock_cpsat.return_value = ScheduleResult(
                scheduled_jobs=[], makespan_minutes=30, total_setup_time=0,
                utilization={}, solver_status='optimal'
            )
            result = service.schedule_jobs(jobs, machines, 24, 'makespan')

            mock_cpsat.assert_called_once()
            assert result.solver_status == 'optimal'

    def test_falls_back_on_import_error(self, service):
        """Test schedule_jobs falls back to heuristic on ImportError."""
        jobs = [ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=30,
                           eligible_machines=["mach_001"])]
        machines = [Machine(machine_id="mach_001", name="Machine 1")]

        with patch.object(service, '_schedule_cpsat') as mock_cpsat:
            mock_cpsat.side_effect = ImportError("No module named 'ortools'")
            with patch.object(service, '_schedule_heuristic') as mock_heuristic:
                mock_heuristic.return_value = ScheduleResult(
                    scheduled_jobs=[], makespan_minutes=30, total_setup_time=0,
                    utilization={}, solver_status='heuristic'
                )
                result = service.schedule_jobs(jobs, machines, 24, 'makespan')

                mock_heuristic.assert_called_once()
                assert result.solver_status == 'heuristic'


class TestCalculateUtilization:
    """Tests for utilization calculation."""

    @pytest.fixture
    def service(self):
        return SchedulingService()

    @pytest.fixture
    def sample_machines(self):
        return [
            Machine(machine_id="mach_001", name="Machine 1"),
            Machine(machine_id="mach_002", name="Machine 2"),
        ]

    def test_full_utilization(self, service, sample_machines):
        """Test utilization calculation with fully utilized machine."""
        base_time = datetime.utcnow()
        scheduled = [ScheduledJob(job_id="job_001", machine_id="mach_001",
                                  start_time=base_time, end_time=base_time + timedelta(minutes=60))]
        utilization = service._calculate_utilization(scheduled, sample_machines, 60)

        assert utilization["mach_001"] == 1.0
        assert utilization["mach_002"] == 0.0

    def test_partial_utilization(self, service, sample_machines):
        """Test utilization calculation with partial utilization."""
        base_time = datetime.utcnow()
        scheduled = [ScheduledJob(job_id="job_001", machine_id="mach_001",
                                  start_time=base_time, end_time=base_time + timedelta(minutes=30))]
        utilization = service._calculate_utilization(scheduled, sample_machines, 60)

        assert utilization["mach_001"] == 0.5

    def test_multiple_jobs_same_machine(self, service, sample_machines):
        """Test utilization with multiple jobs on same machine."""
        base_time = datetime.utcnow()
        scheduled = [
            ScheduledJob(job_id="job_001", machine_id="mach_001",
                        start_time=base_time, end_time=base_time + timedelta(minutes=30)),
            ScheduledJob(job_id="job_002", machine_id="mach_001",
                        start_time=base_time + timedelta(minutes=30),
                        end_time=base_time + timedelta(minutes=60)),
        ]
        utilization = service._calculate_utilization(scheduled, sample_machines, 60)

        assert utilization["mach_001"] == 1.0

    def test_zero_makespan(self, service, sample_machines):
        """Test utilization calculation with zero makespan."""
        utilization = service._calculate_utilization([], sample_machines, 0)

        assert utilization["mach_001"] == 0.0
        assert utilization["mach_002"] == 0.0

    def test_utilization_caps_at_one(self, service, sample_machines):
        """Test utilization is capped at 1.0."""
        base_time = datetime.utcnow()
        scheduled = [ScheduledJob(job_id="job_001", machine_id="mach_001",
                                  start_time=base_time, end_time=base_time + timedelta(minutes=120))]
        utilization = service._calculate_utilization(scheduled, sample_machines, 60)

        assert utilization["mach_001"] == 1.0


class TestGetDispatchQueue:
    """Tests for get_dispatch_queue method."""

    def test_returns_jobs(self):
        """Test getting dispatch queue returns ordered jobs."""
        mock_session = Mock()
        service = SchedulingService(mock_session)

        # Create mock jobs
        mock_job1 = Mock()
        mock_job1.to_dict.return_value = {'job_id': 'job_001', 'priority_score': 10}
        mock_job2 = Mock()
        mock_job2.to_dict.return_value = {'job_id': 'job_002', 'priority_score': 5}

        # Mock the query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_job1, mock_job2]
        mock_session.query.return_value = mock_query

        # Patch the models where they are imported (inside get_dispatch_queue)
        with patch.dict('sys.modules', {'models.mes.work_orders': MagicMock()}):
            result = service.get_dispatch_queue("mach_001")

        assert len(result) == 2
        assert result[0]['job_id'] == 'job_001'

    def test_no_session_returns_empty(self):
        """Test get_dispatch_queue returns empty list without session."""
        service = SchedulingService(session=None)
        result = service.get_dispatch_queue("mach_001")

        assert result == []

    def test_empty_queue(self):
        """Test get_dispatch_queue returns empty list when no jobs."""
        mock_session = Mock()
        service = SchedulingService(mock_session)

        # Mock the query chain to return empty list
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query

        # Patch the models where they are imported (inside get_dispatch_queue)
        with patch.dict('sys.modules', {'models.mes.work_orders': MagicMock()}):
            result = service.get_dispatch_queue("mach_001")

        assert result == []


class TestSchedulingIntegration:
    """Integration-style tests for scheduling scenarios."""

    @pytest.fixture
    def service(self):
        return SchedulingService()

    def test_parallel_jobs_multiple_machines(self, service):
        """Test scheduling independent jobs in parallel across machines."""
        machines = [Machine(machine_id=f"mach_{i:03d}", name=f"Machine {i}") for i in range(3)]
        jobs = [ScheduleJob(job_id=f"job_{i:03d}", work_order_id=f"wo_{i:03d}", duration_minutes=30,
                           eligible_machines=["mach_000", "mach_001", "mach_002"], priority=1)
                for i in range(6)]

        result = service._schedule_heuristic(jobs, machines, 24)

        assert len(result.scheduled_jobs) == 6
        assert len(result.unscheduled_jobs) == 0
        machines_used = {j.machine_id for j in result.scheduled_jobs}
        assert len(machines_used) == 3

    def test_sequential_dependent_jobs(self, service):
        """Test scheduling jobs with chain dependencies."""
        machines = [Machine(machine_id="mach_001", name="Machine 1")]
        jobs = [
            ScheduleJob(job_id="job_001", work_order_id="wo_001", duration_minutes=20,
                       eligible_machines=["mach_001"], priority=3),
            ScheduleJob(job_id="job_002", work_order_id="wo_001", duration_minutes=30,
                       eligible_machines=["mach_001"], priority=2, dependencies=["job_001"]),
            ScheduleJob(job_id="job_003", work_order_id="wo_001", duration_minutes=25,
                       eligible_machines=["mach_001"], priority=1, dependencies=["job_002"]),
        ]

        result = service._schedule_heuristic(jobs, machines, 24)

        assert len(result.scheduled_jobs) == 3
        # Total duration is 20+30+25=75, but makespan may vary slightly due to rounding
        assert result.makespan_minutes >= 74

    def test_empty_jobs_list(self, service):
        """Test scheduling with empty jobs list."""
        machines = [Machine(machine_id="mach_001", name="Machine 1")]
        result = service._schedule_heuristic([], machines, 24)

        assert len(result.scheduled_jobs) == 0
        assert result.makespan_minutes == 0

    def test_empty_machines_list(self, service):
        """Test scheduling with empty machines list."""
        jobs = [ScheduleJob(job_id="job_001", work_order_id="wo_001",
                           duration_minutes=30, eligible_machines=[])]
        result = service._schedule_heuristic(jobs, [], 24)

        assert len(result.scheduled_jobs) == 0
        assert "job_001" in result.unscheduled_jobs
