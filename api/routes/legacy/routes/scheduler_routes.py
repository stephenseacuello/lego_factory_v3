"""
Scheduler API Routes for Flask CNC SCADA
=========================================
REST API for job scheduling with 9 algorithm support.

Endpoints:
    POST   /api/scheduler/schedule         - Schedule jobs with chosen algorithm
    GET    /api/scheduler/algorithms       - List available algorithms
    GET    /api/scheduler/algorithms/<id>  - Get algorithm details
    POST   /api/scheduler/recommend        - Get algorithm recommendation
    POST   /api/scheduler/compare          - Compare multiple algorithms
    GET    /api/scheduler/gantt/<run_id>   - Get Gantt chart data
    GET    /api/scheduler/runs             - List schedule runs
    GET    /api/scheduler/runs/<id>        - Get schedule run details
"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError

from services.scheduling import (
    get_unified_scheduler,
    get_algorithm_registry,
    ScheduleRequest,
    ScheduleJob,
    ScheduleMachine,
    SchedulingAlgorithm,
)
from services.auth_service import require_auth, require_role
from database import get_session, ScheduleRun, ScheduleSlot

logger = logging.getLogger(__name__)

bp = Blueprint('scheduler', __name__, url_prefix='/api/scheduler')


# ============================================================================
# Schedule Run Persistence Helpers
# ============================================================================

def _persist_schedule_run(
    algorithm: str,
    jobs_scheduled: int,
    machines_used: int,
    makespan: float,
    total_tardiness: float,
    total_flow_time: float,
    utilization: float,
    computation_time_ms: float,
    parameters: Dict[str, Any] = None,
    metrics: Dict[str, Any] = None,
    scheduled_jobs: List[Dict] = None,
) -> Optional[str]:
    """
    Persist a schedule run to PostgreSQL.

    Returns:
        Schedule run ID if successful, None otherwise
    """
    try:
        with get_session() as session:
            # Deactivate previous active schedules
            session.query(ScheduleRun).filter(
                ScheduleRun.is_active == True
            ).update({'is_active': False})

            # Create new schedule run
            schedule_run = ScheduleRun(
                id=uuid.uuid4(),
                algorithm=algorithm,
                algorithm_version="1.0",
                parameters=parameters or {},
                jobs_scheduled=jobs_scheduled,
                machines_used=machines_used,
                makespan=makespan,
                total_tardiness=total_tardiness,
                total_flow_time=total_flow_time,
                utilization=utilization,
                metrics=metrics or {},
                is_active=True,
                computation_time_ms=int(computation_time_ms),
            )
            session.add(schedule_run)
            session.flush()  # Get the ID

            # Add schedule slots for each job
            if scheduled_jobs:
                for i, job in enumerate(scheduled_jobs):
                    # Create a slot for each scheduled job
                    slot = ScheduleSlot(
                        id=uuid.uuid4(),
                        schedule_run_id=schedule_run.id,
                        machine_id=job.get('machine_id', 'tinyg-1'),
                        job_id=uuid.uuid4(),  # Placeholder - would link to actual job
                        scheduled_start=datetime.now() + timedelta(
                            seconds=job.get('start_time', i * 300)
                        ),
                        scheduled_end=datetime.now() + timedelta(
                            seconds=job.get('end_time', (i + 1) * 300)
                        ),
                        sequence_number=i + 1,
                        is_locked=False,
                    )
                    session.add(slot)

            logger.info(f"Persisted schedule run {schedule_run.id} with {jobs_scheduled} jobs")
            return str(schedule_run.id)

    except SQLAlchemyError as e:
        logger.error(f"Failed to persist schedule run: {e}")
        return None


def _get_schedule_run(run_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a schedule run from PostgreSQL.

    Returns:
        Schedule run dict if found, None otherwise
    """
    try:
        with get_session() as session:
            schedule_run = session.query(ScheduleRun).filter(
                ScheduleRun.id == uuid.UUID(run_id)
            ).first()

            if not schedule_run:
                return None

            # Get slots for this run
            slots = session.query(ScheduleSlot).filter(
                ScheduleSlot.schedule_run_id == schedule_run.id
            ).order_by(ScheduleSlot.sequence_number).all()

            return {
                'id': str(schedule_run.id),
                'algorithm': schedule_run.algorithm,
                'algorithm_version': schedule_run.algorithm_version,
                'parameters': schedule_run.parameters,
                'jobs_scheduled': schedule_run.jobs_scheduled,
                'machines_used': schedule_run.machines_used,
                'makespan': schedule_run.makespan,
                'total_tardiness': schedule_run.total_tardiness,
                'total_flow_time': schedule_run.total_flow_time,
                'utilization': schedule_run.utilization,
                'metrics': schedule_run.metrics,
                'is_active': schedule_run.is_active,
                'computation_time_ms': schedule_run.computation_time_ms,
                'created_at': schedule_run.created_at.isoformat() if schedule_run.created_at else None,
                'slots': [
                    {
                        'id': str(slot.id),
                        'machine_id': slot.machine_id,
                        'scheduled_start': slot.scheduled_start.isoformat() if slot.scheduled_start else None,
                        'scheduled_end': slot.scheduled_end.isoformat() if slot.scheduled_end else None,
                        'sequence_number': slot.sequence_number,
                        'is_locked': slot.is_locked,
                    }
                    for slot in slots
                ],
            }

    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get schedule run {run_id}: {e}")
        return None


def _list_schedule_runs(
    limit: int = 20,
    algorithm: str = None,
    active_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    List schedule runs from PostgreSQL.

    Returns:
        List of schedule run dicts
    """
    try:
        with get_session() as session:
            query = session.query(ScheduleRun)

            if algorithm:
                query = query.filter(ScheduleRun.algorithm == algorithm)

            if active_only:
                query = query.filter(ScheduleRun.is_active == True)

            runs = query.order_by(
                ScheduleRun.created_at.desc()
            ).limit(limit).all()

            return [
                {
                    'id': str(run.id),
                    'algorithm': run.algorithm,
                    'jobs_scheduled': run.jobs_scheduled,
                    'machines_used': run.machines_used,
                    'makespan': run.makespan,
                    'total_tardiness': run.total_tardiness,
                    'utilization': run.utilization,
                    'is_active': run.is_active,
                    'computation_time_ms': run.computation_time_ms,
                    'created_at': run.created_at.isoformat() if run.created_at else None,
                }
                for run in runs
            ]

    except SQLAlchemyError as e:
        logger.error(f"Failed to list schedule runs: {e}")
        return []


# ============================================================================
# Algorithm Endpoints
# ============================================================================

@bp.route('/algorithms', methods=['GET'])
@require_auth
def list_algorithms():
    """
    List all available scheduling algorithms.

    Query Parameters:
        - category: Filter by category (dispatching, metaheuristic, optimization)

    Response:
        - 200: List of algorithms with metadata
    """
    registry = get_algorithm_registry()
    category = request.args.get('category')

    if category:
        from services.scheduling.algorithm_registry import AlgorithmCategory
        try:
            cat_enum = AlgorithmCategory(category.lower())
            algorithms = registry.list_by_category(cat_enum)
        except ValueError:
            return jsonify({'error': f'Invalid category: {category}'}), 400
    else:
        algorithms = registry.list_all()

    return jsonify({
        'algorithms': [algo.to_dict() for algo in algorithms],
        'total': len(algorithms),
        'categories': ['dispatching', 'metaheuristic', 'optimization']
    })


@bp.route('/algorithms/<algorithm_id>', methods=['GET'])
@require_auth
def get_algorithm(algorithm_id: str):
    """
    Get details for a specific algorithm.

    Response:
        - 200: Algorithm details
        - 404: Algorithm not found
    """
    registry = get_algorithm_registry()
    algo = registry.get(algorithm_id)

    if not algo:
        return jsonify({'error': f'Algorithm not found: {algorithm_id}'}), 404

    return jsonify({'algorithm': algo.to_dict()})


@bp.route('/recommend', methods=['POST'])
@require_auth
def recommend_algorithm():
    """
    Get algorithm recommendation based on problem characteristics.

    Request JSON:
        {
            "job_count": 50,
            "machine_count": 3,
            "has_due_dates": true,
            "has_priorities": true,
            "has_setup_times": false,
            "time_limit_sec": 60
        }

    Response:
        - 200: List of recommended algorithms (best first)
    """
    data = request.get_json() or {}

    job_count = data.get('job_count', 10)
    machine_count = data.get('machine_count', 1)
    has_due_dates = data.get('has_due_dates', True)
    has_priorities = data.get('has_priorities', True)
    has_setup_times = data.get('has_setup_times', False)
    time_limit_sec = data.get('time_limit_sec', 60.0)

    registry = get_algorithm_registry()
    recommendations = registry.recommend(
        job_count=job_count,
        machine_count=machine_count,
        has_due_dates=has_due_dates,
        has_priorities=has_priorities,
        has_setup_times=has_setup_times,
        time_limit_sec=time_limit_sec,
    )

    return jsonify({
        'recommendations': [algo.to_dict() for algo in recommendations],
        'problem_characteristics': {
            'job_count': job_count,
            'machine_count': machine_count,
            'has_due_dates': has_due_dates,
            'has_priorities': has_priorities,
            'has_setup_times': has_setup_times,
            'time_limit_sec': time_limit_sec,
        }
    })


# ============================================================================
# Scheduling Endpoints
# ============================================================================

@bp.route('/schedule', methods=['POST'])
@require_auth
@require_role('operator')
def schedule_jobs():
    """
    Schedule jobs using specified algorithm.

    Request JSON:
        {
            "algorithm": "GENETIC",
            "jobs": [
                {
                    "id": "job-001",
                    "processing_time": 300,
                    "priority": 2,
                    "due_date": "2025-01-15T10:00:00",
                    "setup_time": 60,
                    "material_type": "aluminum",
                    "work_order_id": "WO-2025-001",
                    "operation_id": "op-001"
                }
            ],
            "machines": [
                {
                    "id": "tinyg-1",
                    "name": "TinyG Mill",
                    "available_from": "2025-01-15T08:00:00"
                }
            ],
            "parameters": {
                "population_size": 50,
                "generations": 100
            }
        }

    Response:
        - 200: Schedule result with assignments
        - 400: Invalid request
        - 500: Scheduling failed
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    # Validate required fields
    if 'jobs' not in data or not data['jobs']:
        return jsonify({'error': 'jobs array is required'}), 400

    # Parse algorithm
    algorithm_str = data.get('algorithm', 'FIFO').upper()
    try:
        algorithm = SchedulingAlgorithm(algorithm_str)
    except ValueError:
        valid = [a.value for a in SchedulingAlgorithm]
        return jsonify({
            'error': f'Invalid algorithm: {algorithm_str}',
            'valid_algorithms': valid
        }), 400

    # Parse jobs
    jobs = []
    for job_data in data['jobs']:
        try:
            job = _parse_job(job_data)
            jobs.append(job)
        except ValueError as e:
            return jsonify({'error': f'Invalid job data: {e}'}), 400

    # Parse machines (optional - defaults to single machine)
    machines = []
    for machine_data in data.get('machines', []):
        try:
            machine = _parse_machine(machine_data)
            machines.append(machine)
        except ValueError as e:
            return jsonify({'error': f'Invalid machine data: {e}'}), 400

    if not machines:
        machines = [ScheduleMachine(
            id='tinyg-1',
            name='TinyG Default',
            available_from=time.time()
        )]

    # Build request
    schedule_request = ScheduleRequest(
        jobs=jobs,
        machines=machines,
        algorithm=algorithm,
        parameters=data.get('parameters', {}),
    )

    # Run scheduling
    scheduler = get_unified_scheduler()
    response = scheduler.schedule(schedule_request)

    if not response.success:
        return jsonify({
            'error': 'Scheduling failed',
            'message': response.error_message
        }), 500

    # Persist schedule run to PostgreSQL
    run_id = _persist_schedule_run(
        algorithm=algorithm.value,
        jobs_scheduled=len(response.scheduled_jobs),
        machines_used=len(response.machines_used),
        makespan=response.makespan,
        total_tardiness=response.total_tardiness,
        total_flow_time=response.total_flow_time,
        utilization=response.utilization,
        computation_time_ms=response.computation_time_ms,
        parameters=data.get('parameters', {}),
        metrics={
            'avg_tardiness': response.avg_tardiness,
            'max_tardiness': response.max_tardiness,
            'on_time_jobs': response.on_time_jobs,
            'late_jobs': response.late_jobs,
        },
        scheduled_jobs=response.scheduled_jobs,
    )

    # Build response
    return jsonify({
        'success': True,
        'run_id': run_id,
        'schedule': response.to_dict(),
        'summary': {
            'algorithm': algorithm.value,
            'jobs_scheduled': len(response.scheduled_jobs),
            'machines_used': len(response.machines_used),
            'makespan_sec': response.makespan,
            'total_tardiness_sec': response.total_tardiness,
            'computation_time_ms': round(response.computation_time_ms, 2),
        }
    })


@bp.route('/compare', methods=['POST'])
@require_auth
@require_role('operator')
def compare_algorithms():
    """
    Compare multiple algorithms on the same problem.

    Request JSON:
        {
            "algorithms": ["FIFO", "EDD", "SPT", "GENETIC"],
            "jobs": [...],
            "machines": [...],
            "parameters": {
                "GENETIC": {"generations": 50},
                "SA": {"initial_temp": 500}
            }
        }

    Response:
        - 200: Comparison results with rankings
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    algorithms_str = data.get('algorithms', ['FIFO', 'EDD', 'SPT'])
    if not algorithms_str:
        return jsonify({'error': 'algorithms array is required'}), 400

    # Parse algorithms
    algorithms = []
    for algo_str in algorithms_str:
        try:
            algorithms.append(SchedulingAlgorithm(algo_str.upper()))
        except ValueError:
            return jsonify({'error': f'Invalid algorithm: {algo_str}'}), 400

    # Parse jobs and machines
    jobs = []
    for job_data in data.get('jobs', []):
        try:
            jobs.append(_parse_job(job_data))
        except ValueError as e:
            return jsonify({'error': f'Invalid job: {e}'}), 400

    if not jobs:
        return jsonify({'error': 'jobs array is required'}), 400

    machines = []
    for machine_data in data.get('machines', []):
        try:
            machines.append(_parse_machine(machine_data))
        except ValueError as e:
            return jsonify({'error': f'Invalid machine: {e}'}), 400

    if not machines:
        machines = [ScheduleMachine(
            id='tinyg-1',
            name='TinyG Default',
            available_from=time.time()
        )]

    # Run all algorithms
    scheduler = get_unified_scheduler()
    algo_params = data.get('parameters', {})
    results = []

    for algorithm in algorithms:
        params = algo_params.get(algorithm.value, {})

        schedule_request = ScheduleRequest(
            jobs=jobs.copy(),  # Copy to avoid mutation
            machines=machines.copy(),
            algorithm=algorithm,
            parameters=params,
        )

        response = scheduler.schedule(schedule_request)

        results.append({
            'algorithm': algorithm.value,
            'success': response.success,
            'makespan': response.makespan,
            'total_tardiness': response.total_tardiness,
            'avg_tardiness': response.avg_tardiness,
            'max_tardiness': response.max_tardiness,
            'on_time_jobs': response.on_time_jobs,
            'late_jobs': response.late_jobs,
            'computation_time_ms': response.computation_time_ms,
            'error': response.error_message,
        })

    # Rank by makespan (lower is better)
    successful = [r for r in results if r['success']]
    successful.sort(key=lambda r: r['makespan'])

    for i, r in enumerate(successful):
        r['rank_by_makespan'] = i + 1

    # Rank by tardiness
    successful_copy = successful.copy()
    successful_copy.sort(key=lambda r: r['total_tardiness'])
    for i, r in enumerate(successful_copy):
        r['rank_by_tardiness'] = i + 1

    return jsonify({
        'comparison': results,
        'best_makespan': successful[0]['algorithm'] if successful else None,
        'best_tardiness': successful_copy[0]['algorithm'] if successful_copy else None,
        'job_count': len(jobs),
        'machine_count': len(machines),
    })


# ============================================================================
# Gantt Chart & Visualization
# ============================================================================

@bp.route('/gantt/<run_id>', methods=['GET'])
@require_auth
def get_gantt_data(run_id: str):
    """
    Get Gantt chart data for a schedule run.

    Response format optimized for common Gantt chart libraries.

    Response:
        - 200: Gantt chart data
        - 404: Schedule run not found
    """
    # Query schedule run from PostgreSQL
    run = _get_schedule_run(run_id)

    if not run:
        return jsonify({'error': f'Schedule run not found: {run_id}'}), 404

    # Build Gantt data from slots
    machines = {}
    jobs = []

    for slot in run.get('slots', []):
        machine_id = slot['machine_id']
        if machine_id not in machines:
            machines[machine_id] = {
                'id': machine_id,
                'name': machine_id.replace('-', ' ').title()
            }

        jobs.append({
            'id': slot['id'],
            'machine_id': machine_id,
            'start': slot['scheduled_start'],
            'end': slot['scheduled_end'],
            'sequence': slot['sequence_number'],
            'status': 'locked' if slot['is_locked'] else 'scheduled',
            'color': '#F44336' if slot['is_locked'] else '#4CAF50',
        })

    # Calculate time range
    if jobs:
        starts = [j['start'] for j in jobs if j['start']]
        ends = [j['end'] for j in jobs if j['end']]
        time_range = {
            'start': min(starts) if starts else datetime.now().isoformat(),
            'end': max(ends) if ends else (datetime.now() + timedelta(hours=8)).isoformat(),
        }
    else:
        time_range = {
            'start': datetime.now().isoformat(),
            'end': (datetime.now() + timedelta(hours=8)).isoformat(),
        }

    gantt_data = {
        'run_id': run_id,
        'algorithm': run.get('algorithm'),
        'machines': list(machines.values()),
        'jobs': jobs,
        'time_range': time_range,
        'metrics': {
            'makespan': run.get('makespan'),
            'utilization': run.get('utilization'),
            'tardiness': run.get('total_tardiness'),
        }
    }

    return jsonify({'gantt': gantt_data})


@bp.route('/gantt/live', methods=['GET'])
@require_auth
def get_live_gantt():
    """
    Get live Gantt chart showing current execution state.

    Combines scheduled jobs with actual execution progress.

    Response:
        - 200: Live Gantt data with execution status
    """
    from services.execution import get_job_executor
    from services.gcode_service import get_gcode_service, JobStatus

    gcode_service = get_gcode_service()
    executor = get_job_executor()

    # Get all relevant jobs
    queued = gcode_service.get_all_jobs(status=JobStatus.QUEUED)
    running = gcode_service.get_all_jobs(status=JobStatus.RUNNING)

    # Active executions
    active = executor.get_active_jobs()

    gantt_jobs = []

    # Add running jobs
    for job in running:
        ctx = executor.get_job_context(job.id)
        progress = 0
        if ctx:
            progress = (ctx.metrics.lines_executed / max(ctx.metrics.total_lines, 1)) * 100

        gantt_jobs.append({
            'id': job.id,
            'name': job.filename,
            'machine_id': job.machine_id or 'tinyg-1',
            'start': job.started_at.isoformat() if job.started_at else None,
            'end': None,  # Still running
            'progress': progress,
            'status': 'running',
            'color': '#2196F3',
        })

    # Add queued jobs (estimated start times)
    estimated_start = datetime.now()
    for job in sorted(queued, key=lambda j: j.priority.value):
        duration = timedelta(seconds=job.metadata.estimated_time_sec or 300)

        gantt_jobs.append({
            'id': job.id,
            'name': job.filename,
            'machine_id': 'tinyg-1',
            'start': estimated_start.isoformat(),
            'end': (estimated_start + duration).isoformat(),
            'progress': 0,
            'status': 'queued',
            'color': '#9E9E9E',
        })

        estimated_start = estimated_start + duration

    return jsonify({
        'gantt': {
            'jobs': gantt_jobs,
            'machines': [{'id': 'tinyg-1', 'name': 'TinyG Mill'}],
            'now': datetime.now().isoformat(),
        }
    })


# ============================================================================
# Schedule Runs History
# ============================================================================

@bp.route('/runs', methods=['GET'])
@require_auth
def list_schedule_runs():
    """
    List recent schedule runs.

    Query Parameters:
        - limit: Maximum number of runs (default 20)
        - algorithm: Filter by algorithm
        - active: If 'true', only show active schedule

    Response:
        - 200: List of schedule runs
    """
    limit = request.args.get('limit', 20, type=int)
    algorithm = request.args.get('algorithm')
    active_only = request.args.get('active', '').lower() == 'true'

    runs = _list_schedule_runs(
        limit=limit,
        algorithm=algorithm,
        active_only=active_only,
    )

    return jsonify({
        'runs': runs,
        'total': len(runs),
        'filters': {
            'limit': limit,
            'algorithm': algorithm,
            'active_only': active_only,
        }
    })


@bp.route('/runs/<run_id>', methods=['GET'])
@require_auth
def get_schedule_run(run_id: str):
    """
    Get details for a specific schedule run.

    Response:
        - 200: Schedule run details
        - 404: Run not found
    """
    run = _get_schedule_run(run_id)

    if not run:
        return jsonify({'error': f'Schedule run not found: {run_id}'}), 404

    return jsonify({'run': run})


@bp.route('/runs/<run_id>', methods=['DELETE'])
@require_auth
@require_role('admin')
def delete_schedule_run(run_id: str):
    """
    Delete a schedule run and its slots.

    Response:
        - 200: Deletion successful
        - 404: Run not found
    """
    try:
        with get_session() as session:
            schedule_run = session.query(ScheduleRun).filter(
                ScheduleRun.id == uuid.UUID(run_id)
            ).first()

            if not schedule_run:
                return jsonify({'error': f'Schedule run not found: {run_id}'}), 404

            # Slots are cascade deleted
            session.delete(schedule_run)
            logger.info(f"Deleted schedule run {run_id}")

            return jsonify({
                'success': True,
                'message': f'Schedule run {run_id} deleted'
            })

    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to delete schedule run {run_id}: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/runs/active', methods=['GET'])
@require_auth
def get_active_schedule():
    """
    Get the currently active schedule.

    Response:
        - 200: Active schedule details
        - 404: No active schedule
    """
    runs = _list_schedule_runs(limit=1, active_only=True)

    if not runs:
        return jsonify({
            'active': None,
            'message': 'No active schedule found'
        }), 404

    run_id = runs[0]['id']
    run = _get_schedule_run(run_id)

    return jsonify({
        'active': run,
        'run_id': run_id
    })


@bp.route('/runs/<run_id>/activate', methods=['POST'])
@require_auth
@require_role('operator')
def activate_schedule_run(run_id: str):
    """
    Set a schedule run as the active schedule.

    Response:
        - 200: Activation successful
        - 404: Run not found
    """
    try:
        with get_session() as session:
            schedule_run = session.query(ScheduleRun).filter(
                ScheduleRun.id == uuid.UUID(run_id)
            ).first()

            if not schedule_run:
                return jsonify({'error': f'Schedule run not found: {run_id}'}), 404

            # Deactivate all other schedules
            session.query(ScheduleRun).filter(
                ScheduleRun.is_active == True
            ).update({'is_active': False})

            # Activate this one
            schedule_run.is_active = True
            logger.info(f"Activated schedule run {run_id}")

            return jsonify({
                'success': True,
                'message': f'Schedule run {run_id} is now active',
                'run_id': run_id
            })

    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to activate schedule run {run_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Quick Schedule from Queue
# ============================================================================

@bp.route('/schedule-queue', methods=['POST'])
@require_auth
@require_role('operator')
def schedule_from_queue():
    """
    Schedule all queued jobs using specified algorithm.

    This is a convenience endpoint that pulls jobs directly from
    the G-code queue and schedules them.

    Request JSON:
        {
            "algorithm": "EDD",
            "parameters": {}
        }

    Response:
        - 200: Schedule result
        - 204: No jobs in queue
    """
    from services.gcode_service import get_gcode_service, JobStatus

    data = request.get_json() or {}

    # Get algorithm
    algorithm_str = data.get('algorithm', 'FIFO').upper()
    try:
        algorithm = SchedulingAlgorithm(algorithm_str)
    except ValueError:
        return jsonify({'error': f'Invalid algorithm: {algorithm_str}'}), 400

    # Get queued jobs
    gcode_service = get_gcode_service()
    queued_jobs = gcode_service.get_all_jobs(status=JobStatus.QUEUED)

    if not queued_jobs:
        return '', 204

    # Convert to ScheduleJob format
    schedule_jobs = []
    for job in queued_jobs:
        schedule_jobs.append(ScheduleJob(
            id=job.id,
            processing_time=job.metadata.estimated_time_sec or 300,
            priority=job.priority.value,
            due_date=job.due_date.timestamp() if job.due_date else None,
            work_order_id=job.work_order_id,
            operation_id=job.operation_id,
        ))

    # Default machine
    machines = [ScheduleMachine(
        id='tinyg-1',
        name='TinyG Mill',
        available_from=time.time(),
    )]

    # Schedule
    schedule_request = ScheduleRequest(
        jobs=schedule_jobs,
        machines=machines,
        algorithm=algorithm,
        parameters=data.get('parameters', {}),
    )

    scheduler = get_unified_scheduler()
    response = scheduler.schedule(schedule_request)

    if not response.success:
        return jsonify({
            'error': 'Scheduling failed',
            'message': response.error_message
        }), 500

    # Persist schedule run
    run_id = _persist_schedule_run(
        algorithm=algorithm.value,
        jobs_scheduled=len(response.scheduled_jobs),
        machines_used=len(response.machines_used),
        makespan=response.makespan,
        total_tardiness=response.total_tardiness,
        total_flow_time=response.total_flow_time,
        utilization=response.utilization,
        computation_time_ms=response.computation_time_ms,
        parameters=data.get('parameters', {}),
        scheduled_jobs=response.scheduled_jobs,
    )

    return jsonify({
        'success': True,
        'run_id': run_id,
        'algorithm': algorithm.value,
        'jobs_scheduled': len(response.scheduled_jobs),
        'makespan_sec': response.makespan,
        'schedule': response.to_dict(),
    })


# ============================================================================
# OEE-Aware Scheduling (Multi-Machine)
# ============================================================================

@bp.route('/schedule-oee', methods=['POST'])
@require_auth
@require_role('operator')
def schedule_with_oee():
    """
    Schedule jobs using OEE-aware machine selection.

    This endpoint assigns jobs to machines based on a fitness score that
    considers OEE scores, utilization, capability, and queue time.

    Fitness = (oee_weight × OEE_score) +
              (utilization_weight × (1 - utilization)) +
              (capability_weight × capability_match) +
              (queue_weight × (1 - normalized_queue_time))

    Request JSON:
        {
            "jobs": [...],
            "machines": [...],
            "weights": {
                "oee": 0.4,
                "utilization": 0.3,
                "capability": 0.2,
                "queue": 0.1
            }
        }

    Response:
        - 200: Schedule with OEE-based assignments
        - 400: Invalid request
        - 500: Scheduling failed
    """
    from services.scheduler_service import get_scheduler_service, Job, Operation, Machine

    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    if 'jobs' not in data or not data['jobs']:
        return jsonify({'error': 'jobs array is required'}), 400

    # Parse weights
    weights = data.get('weights', {})
    oee_weight = weights.get('oee', 0.4)
    utilization_weight = weights.get('utilization', 0.3)
    capability_weight = weights.get('capability', 0.2)
    queue_weight = weights.get('queue', 0.1)

    # Parse jobs into scheduler format
    scheduler_jobs = []
    for job_data in data['jobs']:
        try:
            # Build operations list (single operation per job for simple case)
            machine_id = job_data.get('machine_id', 'tinyg-1')
            processing_time = int(job_data.get('processing_time', 300) / 60)  # Convert to minutes
            setup_time = int(job_data.get('setup_time', 0) / 60)

            operations = [Operation(
                id=f"{job_data['id']}_op1",
                name=job_data.get('name', job_data['id']),
                machine_id=machine_id,
                processing_time=processing_time,
                setup_time=setup_time
            )]

            due_date = None
            if 'due_date' in job_data and job_data['due_date']:
                if isinstance(job_data['due_date'], str):
                    due_dt = datetime.fromisoformat(job_data['due_date'].replace('Z', '+00:00'))
                    due_date = int((due_dt - datetime.now()).total_seconds() / 60)
                else:
                    due_date = int(job_data['due_date'] / 60)

            scheduler_jobs.append(Job(
                id=job_data['id'],
                name=job_data.get('name', job_data['id']),
                operations=operations,
                priority=int(job_data.get('priority', 5)),
                due_date=due_date,
                release_date=0
            ))
        except (KeyError, ValueError) as e:
            return jsonify({'error': f'Invalid job data: {e}'}), 400

    # Parse machines
    scheduler_machines = []
    for machine_data in data.get('machines', []):
        try:
            available_from = 0
            if 'available_from' in machine_data and machine_data['available_from']:
                if isinstance(machine_data['available_from'], str):
                    avail_dt = datetime.fromisoformat(machine_data['available_from'].replace('Z', '+00:00'))
                    available_from = int((avail_dt - datetime.now()).total_seconds() / 60)
                    available_from = max(0, available_from)  # Don't go negative
                else:
                    available_from = int(machine_data['available_from'] / 60)

            scheduler_machines.append(Machine(
                id=machine_data['id'],
                name=machine_data.get('name', machine_data['id']),
                available_from=available_from,
                available_until=480  # 8-hour shift default
            ))
        except (KeyError, ValueError) as e:
            return jsonify({'error': f'Invalid machine data: {e}'}), 400

    # Default machines if none provided
    if not scheduler_machines:
        from services.machine_manager import get_machine_manager
        manager = get_machine_manager()
        for machine in manager.list_machines():
            scheduler_machines.append(Machine(
                id=machine.machine_id,
                name=machine.name,
                available_from=0,
                available_until=480
            ))

        # Fallback if no machines registered
        if not scheduler_machines:
            scheduler_machines = [Machine(
                id='tinyg-1',
                name='TinyG Default',
                available_from=0,
                available_until=480
            )]

    # Run OEE-aware scheduling
    scheduler = get_scheduler_service()
    result = scheduler.schedule_with_oee(
        jobs=scheduler_jobs,
        machines=scheduler_machines,
        oee_weight=oee_weight,
        utilization_weight=utilization_weight,
        capability_weight=capability_weight,
        queue_weight=queue_weight
    )

    if not result.success:
        return jsonify({
            'error': 'Scheduling failed',
            'message': result.status
        }), 500

    # Get fitness scores for transparency
    fitness_scores = scheduler.get_machine_fitness_scores(
        scheduler_machines,
        oee_weight=oee_weight,
        utilization_weight=utilization_weight,
        capability_weight=capability_weight,
        queue_weight=queue_weight
    )

    return jsonify({
        'success': True,
        'algorithm': 'oee_aware',
        'schedule': result.to_dict(),
        'gantt': result.to_gantt_data(),
        'machine_fitness': fitness_scores,
        'weights': {
            'oee': oee_weight,
            'utilization': utilization_weight,
            'capability': capability_weight,
            'queue': queue_weight
        },
        'summary': {
            'jobs_scheduled': len(result.tasks),
            'machines_used': len(result.by_machine),
            'makespan_min': result.makespan,
            'makespan_hours': round(result.makespan / 60, 2),
            'computation_time_ms': round(result.solve_time_ms, 2)
        }
    })


@bp.route('/machine-fitness', methods=['GET'])
@require_auth
def get_machine_fitness():
    """
    Get current fitness scores for all machines.

    Useful for displaying machine selection reasoning in UI.

    Query Parameters:
        - oee_weight: Weight for OEE (default 0.4)
        - utilization_weight: Weight for utilization (default 0.3)
        - capability_weight: Weight for capability (default 0.2)
        - queue_weight: Weight for queue time (default 0.1)

    Response:
        - 200: Fitness scores for each machine
    """
    from services.scheduler_service import get_scheduler_service, Machine
    from services.machine_manager import get_machine_manager

    oee_weight = request.args.get('oee_weight', 0.4, type=float)
    utilization_weight = request.args.get('utilization_weight', 0.3, type=float)
    capability_weight = request.args.get('capability_weight', 0.2, type=float)
    queue_weight = request.args.get('queue_weight', 0.1, type=float)

    # Get machines from manager
    manager = get_machine_manager()
    machines = []
    for machine in manager.list_machines():
        machines.append(Machine(
            id=machine.machine_id,
            name=machine.name,
            available_from=0,
            available_until=480
        ))

    if not machines:
        machines = [Machine(id='tinyg-1', name='TinyG Default', available_from=0, available_until=480)]

    scheduler = get_scheduler_service()
    fitness_scores = scheduler.get_machine_fitness_scores(
        machines,
        oee_weight=oee_weight,
        utilization_weight=utilization_weight,
        capability_weight=capability_weight,
        queue_weight=queue_weight
    )

    return jsonify({
        'success': True,
        'fitness_scores': fitness_scores,
        'weights': {
            'oee': oee_weight,
            'utilization': utilization_weight,
            'capability': capability_weight,
            'queue': queue_weight
        }
    })


# ============================================================================
# Helper Functions
# ============================================================================

def _parse_job(data: Dict[str, Any]) -> ScheduleJob:
    """Parse job data from request JSON."""
    if 'id' not in data:
        raise ValueError('Job id is required')

    due_date = None
    if 'due_date' in data and data['due_date']:
        if isinstance(data['due_date'], str):
            due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00')).timestamp()
        else:
            due_date = float(data['due_date'])

    return ScheduleJob(
        id=data['id'],
        processing_time=float(data.get('processing_time', 300)),
        priority=int(data.get('priority', 2)),
        due_date=due_date,
        setup_time=float(data.get('setup_time', 0)),
        material_type=data.get('material_type'),
        work_order_id=data.get('work_order_id'),
        operation_id=data.get('operation_id'),
    )


def _parse_machine(data: Dict[str, Any]) -> ScheduleMachine:
    """Parse machine data from request JSON."""
    if 'id' not in data:
        raise ValueError('Machine id is required')

    available_from = time.time()
    if 'available_from' in data and data['available_from']:
        if isinstance(data['available_from'], str):
            available_from = datetime.fromisoformat(
                data['available_from'].replace('Z', '+00:00')
            ).timestamp()
        else:
            available_from = float(data['available_from'])

    return ScheduleMachine(
        id=data['id'],
        name=data.get('name', data['id']),
        available_from=available_from,
        capabilities=data.get('capabilities', []),
    )


# ============================================================================
# Advanced Schedulers (Predictive, Energy-Aware, Maintenance)
# ============================================================================

@bp.route('/schedule-predictive', methods=['POST'])
@require_auth
@require_role('operator')
def schedule_predictive_reactive():
    """
    Predictive-Reactive scheduling with buffer insertion and disruption handling.

    Creates an initial schedule with safety buffers, then supports
    rescheduling strategies when disruptions occur.

    Request JSON:
        {
            "jobs": [...],
            "machines": [...],
            "buffer_factor": 0.1,  // 10% safety buffer
            "strategy": "partial_regeneration"  // rescheduling strategy
        }

    Strategies:
        - right_shift: Simple delay propagation
        - partial_regeneration: Reschedule from disruption point
        - complete_regeneration: Full reschedule
        - match_up: Find rejoin point
        - affected_operations: Only reschedule impacted tasks

    Response:
        - 200: Schedule with buffers and metrics
    """
    from services.advanced_scheduler_service import get_predictive_scheduler

    data = request.get_json() or {}

    if 'jobs' not in data or not data['jobs']:
        return jsonify({'error': 'jobs array is required'}), 400

    buffer_factor = data.get('buffer_factor', 0.1)
    strategy = data.get('strategy', 'partial_regeneration')

    # Parse jobs
    jobs = []
    for job_data in data.get('jobs', []):
        jobs.append({
            'id': job_data['id'],
            'name': job_data.get('name', job_data['id']),
            'processing_time': job_data.get('processing_time', 300),
            'priority': job_data.get('priority', 5),
            'due_date': job_data.get('due_date'),
            'machine_id': job_data.get('machine_id'),
            'dependencies': job_data.get('dependencies', []),
        })

    # Parse machines
    machines = []
    for machine_data in data.get('machines', []):
        machines.append({
            'id': machine_data['id'],
            'name': machine_data.get('name', machine_data['id']),
            'available_from': machine_data.get('available_from', 0),
            'available_until': machine_data.get('available_until', 480),
        })

    if not machines:
        from services.machine_manager import get_machine_manager
        manager = get_machine_manager()
        for machine in manager.list_machines():
            machines.append({
                'id': machine.machine_id,
                'name': machine.name,
                'available_from': 0,
                'available_until': 480,
            })

    try:
        scheduler = get_predictive_scheduler()
        result = scheduler.create_schedule(
            jobs=jobs,
            machines=machines,
            buffer_factor=buffer_factor,
            strategy=strategy
        )

        return jsonify({
            'success': True,
            'algorithm': 'predictive_reactive',
            'strategy': strategy,
            'buffer_factor': buffer_factor,
            'schedule': result.get('schedule', []),
            'metrics': result.get('metrics', {}),
            'stability': result.get('stability', {}),
        })
    except Exception as e:
        logger.error(f"Predictive scheduling error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/schedule-energy', methods=['POST'])
@require_auth
@require_role('operator')
def schedule_energy_aware():
    """
    Energy-aware scheduling considering time-of-use rates and peak demand.

    Schedules jobs to minimize energy costs by:
    - Shifting flexible jobs to off-peak hours
    - Managing peak demand charges
    - Considering machine startup/shutdown costs

    Request JSON:
        {
            "jobs": [...],
            "machines": [...],
            "rates": {
                "off_peak": 0.08,   // $/kWh (10pm-6am)
                "mid_peak": 0.12,   // $/kWh (6am-2pm, 6pm-10pm)
                "on_peak": 0.20    // $/kWh (2pm-6pm)
            },
            "demand_charge": 15.0,  // $/kW peak
            "max_demand_kw": 50.0
        }

    Response:
        - 200: Energy-optimized schedule with cost breakdown
    """
    from services.advanced_scheduler_service import get_energy_scheduler

    data = request.get_json() or {}

    if 'jobs' not in data or not data['jobs']:
        return jsonify({'error': 'jobs array is required'}), 400

    # Parse energy rates
    rates = data.get('rates', {
        'off_peak': 0.08,
        'mid_peak': 0.12,
        'on_peak': 0.20
    })
    demand_charge = data.get('demand_charge', 15.0)
    max_demand = data.get('max_demand_kw', 50.0)

    # Parse jobs
    jobs = []
    for job_data in data.get('jobs', []):
        jobs.append({
            'id': job_data['id'],
            'name': job_data.get('name', job_data['id']),
            'processing_time': job_data.get('processing_time', 300),
            'power_kw': job_data.get('power_kw', 2.0),  # Power consumption
            'priority': job_data.get('priority', 5),
            'due_date': job_data.get('due_date'),
            'flexible': job_data.get('flexible', True),  # Can be shifted
        })

    # Parse machines with power profiles
    machines = []
    for machine_data in data.get('machines', []):
        machines.append({
            'id': machine_data['id'],
            'name': machine_data.get('name', machine_data['id']),
            'idle_power_kw': machine_data.get('idle_power_kw', 0.5),
            'startup_energy_kwh': machine_data.get('startup_energy_kwh', 0.2),
        })

    if not machines:
        from services.machine_manager import get_machine_manager
        manager = get_machine_manager()
        for machine in manager.list_machines():
            machines.append({
                'id': machine.machine_id,
                'name': machine.name,
                'idle_power_kw': 0.5,
                'startup_energy_kwh': 0.2,
            })

    try:
        scheduler = get_energy_scheduler()
        result = scheduler.create_schedule(
            jobs=jobs,
            machines=machines,
            rates=rates,
            demand_charge=demand_charge,
            max_demand_kw=max_demand
        )

        return jsonify({
            'success': True,
            'algorithm': 'energy_aware',
            'schedule': result.get('schedule', []),
            'energy_cost': result.get('total_cost', 0),
            'demand_cost': result.get('demand_cost', 0),
            'consumption_cost': result.get('consumption_cost', 0),
            'peak_demand_kw': result.get('peak_demand', 0),
            'total_kwh': result.get('total_kwh', 0),
            'hourly_usage': result.get('hourly_usage', []),
        })
    except Exception as e:
        logger.error(f"Energy-aware scheduling error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/schedule-maintenance', methods=['POST'])
@require_auth
@require_role('operator')
def schedule_with_maintenance():
    """
    Maintenance-integrated scheduling that coordinates PM with production.

    Schedules production jobs while respecting maintenance windows and
    finding opportunistic slots for flexible maintenance tasks.

    Request JSON:
        {
            "jobs": [...],
            "machines": [...],
            "maintenance": [
                {
                    "id": "pm-001",
                    "machine_id": "machine-01",
                    "type": "preventive",  // lubrication, inspection, calibration
                    "duration": 30,
                    "window_start": 0,
                    "window_end": 480,
                    "flexible": true
                }
            ]
        }

    Response:
        - 200: Integrated schedule with maintenance slots
    """
    from services.advanced_scheduler_service import get_maintenance_scheduler

    data = request.get_json() or {}

    if 'jobs' not in data or not data['jobs']:
        return jsonify({'error': 'jobs array is required'}), 400

    # Parse jobs
    jobs = []
    for job_data in data.get('jobs', []):
        jobs.append({
            'id': job_data['id'],
            'name': job_data.get('name', job_data['id']),
            'processing_time': job_data.get('processing_time', 300),
            'priority': job_data.get('priority', 5),
            'due_date': job_data.get('due_date'),
            'machine_id': job_data.get('machine_id'),
        })

    # Parse machines
    machines = []
    for machine_data in data.get('machines', []):
        machines.append({
            'id': machine_data['id'],
            'name': machine_data.get('name', machine_data['id']),
            'available_from': machine_data.get('available_from', 0),
            'available_until': machine_data.get('available_until', 480),
        })

    if not machines:
        from services.machine_manager import get_machine_manager
        manager = get_machine_manager()
        for machine in manager.list_machines():
            machines.append({
                'id': machine.machine_id,
                'name': machine.name,
                'available_from': 0,
                'available_until': 480,
            })

    # Parse maintenance tasks
    maintenance = []
    for maint_data in data.get('maintenance', []):
        maintenance.append({
            'id': maint_data['id'],
            'machine_id': maint_data['machine_id'],
            'type': maint_data.get('type', 'preventive'),
            'duration': maint_data.get('duration', 30),
            'window_start': maint_data.get('window_start', 0),
            'window_end': maint_data.get('window_end', 480),
            'flexible': maint_data.get('flexible', True),
        })

    try:
        scheduler = get_maintenance_scheduler()
        result = scheduler.create_schedule(
            jobs=jobs,
            machines=machines,
            maintenance_tasks=maintenance
        )

        return jsonify({
            'success': True,
            'algorithm': 'maintenance_integrated',
            'production_schedule': result.get('production_schedule', []),
            'maintenance_schedule': result.get('maintenance_schedule', []),
            'makespan': result.get('makespan', 0),
            'maintenance_utilization': result.get('maintenance_utilization', 0),
        })
    except Exception as e:
        logger.error(f"Maintenance scheduling error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/handle-disruption', methods=['POST'])
@require_auth
@require_role('operator')
def handle_disruption():
    """
    Handle a disruption event and reschedule affected jobs.

    Supports real-time rescheduling when:
    - Machine breaks down
    - Urgent job arrives
    - Processing delays occur
    - Job is cancelled

    Request JSON:
        {
            "disruption_type": "breakdown",  // breakdown, urgent_job, delay, cancellation
            "machine_id": "machine-01",      // affected machine
            "job_id": "job-005",             // affected job (optional)
            "delay_minutes": 30,             // for delay disruptions
            "strategy": "partial_regeneration",
            "current_schedule": [...]        // current schedule state
        }

    Response:
        - 200: Rescheduled jobs with impact analysis
    """
    from services.advanced_scheduler_service import get_predictive_scheduler

    data = request.get_json() or {}

    disruption_type = data.get('disruption_type')
    if not disruption_type:
        return jsonify({'error': 'disruption_type is required'}), 400

    machine_id = data.get('machine_id')
    job_id = data.get('job_id')
    delay_minutes = data.get('delay_minutes', 0)
    strategy = data.get('strategy', 'partial_regeneration')
    current_schedule = data.get('current_schedule', [])

    try:
        scheduler = get_predictive_scheduler()
        result = scheduler.handle_disruption(
            disruption_type=disruption_type,
            machine_id=machine_id,
            job_id=job_id,
            delay_minutes=delay_minutes,
            strategy=strategy,
            current_schedule=current_schedule
        )

        return jsonify({
            'success': True,
            'disruption_type': disruption_type,
            'strategy_used': strategy,
            'rescheduled': result.get('rescheduled', []),
            'affected_jobs': result.get('affected_jobs', []),
            'new_makespan': result.get('new_makespan', 0),
            'deviation_from_original': result.get('deviation', 0),
            'rescheduling_count': result.get('rescheduling_count', 0),
        })
    except Exception as e:
        logger.error(f"Disruption handling error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/schedule-with-dependencies', methods=['POST'])
@require_auth
@require_role('operator')
def schedule_with_dependencies():
    """
    Schedule jobs with dependency constraints.

    Jobs can specify predecessor jobs that must complete before they start.
    Supports assembly sequences and multi-step manufacturing.

    Request JSON:
        {
            "jobs": [
                {
                    "id": "job-001",
                    "name": "Part A",
                    "processing_time": 60,
                    "dependencies": []
                },
                {
                    "id": "job-002",
                    "name": "Part B",
                    "processing_time": 45,
                    "dependencies": []
                },
                {
                    "id": "job-003",
                    "name": "Assembly",
                    "processing_time": 30,
                    "dependencies": ["job-001", "job-002"]
                }
            ],
            "machines": [...],
            "algorithm": "EDD",
            "resources": [
                {
                    "id": "operator-1",
                    "name": "Skilled Operator",
                    "resource_type": "operator",
                    "capacity": 1
                }
            ]
        }

    Response:
        - 200: Schedule respecting dependencies
    """
    from services.scheduling import (
        get_unified_scheduler,
        ScheduleRequest,
        ScheduleJob,
        ScheduleMachine,
        ScheduleResource,
        SchedulingAlgorithm,
    )

    data = request.get_json() or {}

    if 'jobs' not in data or not data['jobs']:
        return jsonify({'error': 'jobs array is required'}), 400

    # Parse algorithm
    algorithm_str = data.get('algorithm', 'EDD').upper()
    try:
        algorithm = SchedulingAlgorithm(algorithm_str)
    except ValueError:
        return jsonify({'error': f'Invalid algorithm: {algorithm_str}'}), 400

    # Parse jobs with dependencies
    jobs = []
    for job_data in data.get('jobs', []):
        jobs.append(ScheduleJob(
            id=job_data['id'],
            name=job_data.get('name', job_data['id']),
            processing_time=job_data.get('processing_time', 300),
            priority=job_data.get('priority', 5),
            due_date=job_data.get('due_date'),
            release_date=job_data.get('release_date', 0),
            machine_id=job_data.get('machine_id'),
            setup_group=job_data.get('setup_group'),
            dependencies=job_data.get('dependencies', []),
            required_resources=job_data.get('required_resources', []),
        ))

    # Parse machines
    machines = []
    for machine_data in data.get('machines', []):
        machines.append(ScheduleMachine(
            id=machine_data['id'],
            name=machine_data.get('name', machine_data['id']),
            available_from=machine_data.get('available_from', 0),
            available_until=machine_data.get('available_until', 480),
        ))

    if not machines:
        from services.machine_manager import get_machine_manager
        manager = get_machine_manager()
        for machine in manager.list_machines():
            machines.append(ScheduleMachine(
                id=machine.machine_id,
                name=machine.name,
                available_from=0,
                available_until=480,
            ))

    # Parse resources
    resources = []
    for res_data in data.get('resources', []):
        resources.append(ScheduleResource(
            id=res_data['id'],
            name=res_data.get('name', res_data['id']),
            resource_type=res_data.get('resource_type', 'tool'),
            capacity=res_data.get('capacity', 1),
        ))

    # Create request
    schedule_request = ScheduleRequest(
        jobs=jobs,
        machines=machines,
        algorithm=algorithm,
        parameters=data.get('parameters', {}),
        resources=resources,
    )

    # Schedule
    scheduler = get_unified_scheduler()
    response = scheduler.schedule(schedule_request)

    if not response.success:
        return jsonify({
            'error': 'Scheduling failed',
            'message': response.error
        }), 500

    # Build dependency graph visualization
    dep_graph = {}
    for job in jobs:
        dep_graph[job.id] = {
            'name': job.name,
            'dependencies': job.dependencies,
            'dependents': []
        }
    for job in jobs:
        for dep_id in job.dependencies:
            if dep_id in dep_graph:
                dep_graph[dep_id]['dependents'].append(job.id)

    return jsonify({
        'success': True,
        'algorithm': algorithm.value,
        'schedule': response.to_dict(),
        'gantt': response.to_gantt_data(),
        'dependency_graph': dep_graph,
        'resources_used': [r.id for r in resources],
        'summary': {
            'jobs_scheduled': len(response.scheduled_jobs),
            'makespan': response.makespan,
            'total_tardiness': response.total_tardiness,
            'utilization': response.utilization,
        }
    })


# ============================================================================
# Real-Time Rescheduling Triggers
# ============================================================================

@bp.route('/triggers/rules', methods=['GET'])
@require_auth
def get_trigger_rules():
    """
    Get all rescheduling trigger rules.

    Response:
        - 200: Dictionary of trigger rules
    """
    from services.scheduling_trigger_service import get_scheduling_trigger_service
    service = get_scheduling_trigger_service()

    return jsonify({
        'rules': service.get_rules(),
    })


@bp.route('/triggers/rules/<trigger_type>', methods=['PUT'])
@require_auth
@require_role('admin')
def update_trigger_rule(trigger_type: str):
    """
    Update a trigger rule configuration.

    Request JSON:
        {
            "enabled": true,
            "strategy": "partial_regeneration",
            "delay_threshold_minutes": 15,
            "cooldown_seconds": 60,
            "notify_only": false
        }

    Response:
        - 200: Updated rule
        - 400: Invalid trigger type
    """
    from services.scheduling_trigger_service import (
        get_scheduling_trigger_service,
        TriggerType,
        ReschedulingStrategy,
    )

    data = request.get_json() or {}

    # Validate trigger type
    try:
        trigger = TriggerType(trigger_type)
    except ValueError:
        valid = [t.value for t in TriggerType]
        return jsonify({
            'error': f'Invalid trigger type: {trigger_type}',
            'valid_types': valid
        }), 400

    # Validate strategy if provided
    if 'strategy' in data:
        try:
            data['strategy'] = ReschedulingStrategy(data['strategy'])
        except ValueError:
            valid = [s.value for s in ReschedulingStrategy]
            return jsonify({
                'error': f"Invalid strategy: {data['strategy']}",
                'valid_strategies': valid
            }), 400

    service = get_scheduling_trigger_service()
    service.update_rule(trigger, **data)

    return jsonify({
        'success': True,
        'rule': service.get_rules().get(trigger_type),
    })


@bp.route('/triggers/history', methods=['GET'])
@require_auth
def get_trigger_history():
    """
    Get recent trigger event history.

    Query Parameters:
        - limit: Maximum number of events (default 20)

    Response:
        - 200: List of trigger events
    """
    from services.scheduling_trigger_service import get_scheduling_trigger_service

    limit = request.args.get('limit', 20, type=int)
    service = get_scheduling_trigger_service()

    return jsonify({
        'events': service.get_event_history(limit=limit),
        'total': len(service.get_event_history(limit=1000)),
    })


@bp.route('/triggers/fire', methods=['POST'])
@require_auth
@require_role('operator')
def fire_manual_trigger():
    """
    Manually fire a trigger event (for testing or manual intervention).

    Request JSON:
        {
            "trigger_type": "machine_breakdown",
            "machine_id": "machine-01",
            "job_id": null,
            "data": {"reason": "Spindle overheated"}
        }

    Response:
        - 200: Trigger event result
        - 400: Invalid trigger type
    """
    from services.scheduling_trigger_service import (
        get_scheduling_trigger_service,
        TriggerType,
    )

    data = request.get_json() or {}

    trigger_type_str = data.get('trigger_type')
    if not trigger_type_str:
        return jsonify({'error': 'trigger_type is required'}), 400

    try:
        trigger_type = TriggerType(trigger_type_str)
    except ValueError:
        valid = [t.value for t in TriggerType]
        return jsonify({
            'error': f'Invalid trigger type: {trigger_type_str}',
            'valid_types': valid
        }), 400

    service = get_scheduling_trigger_service()
    event = service.fire_trigger(
        trigger_type=trigger_type,
        machine_id=data.get('machine_id'),
        job_id=data.get('job_id'),
        data=data.get('data', {}),
    )

    if not event:
        return jsonify({
            'success': False,
            'message': 'Trigger was ignored (disabled, in cooldown, or below threshold)'
        })

    return jsonify({
        'success': True,
        'event': event.to_dict(),
    })


@bp.route('/triggers/breakdown', methods=['POST'])
@require_auth
@require_role('operator')
def report_machine_breakdown():
    """
    Report a machine breakdown for rescheduling.

    Request JSON:
        {
            "machine_id": "machine-01",
            "reason": "Spindle motor failure"
        }

    Response:
        - 200: Trigger event result
        - 400: Missing machine_id
    """
    from services.scheduling_trigger_service import get_scheduling_trigger_service

    data = request.get_json() or {}

    machine_id = data.get('machine_id')
    if not machine_id:
        return jsonify({'error': 'machine_id is required'}), 400

    service = get_scheduling_trigger_service()
    event = service.on_machine_breakdown(
        machine_id=machine_id,
        reason=data.get('reason'),
    )

    if not event:
        return jsonify({
            'success': False,
            'message': 'Breakdown trigger ignored (in cooldown or disabled)'
        })

    return jsonify({
        'success': True,
        'event': event.to_dict(),
        'message': f'Breakdown reported for {machine_id}'
    })


@bp.route('/triggers/recovery', methods=['POST'])
@require_auth
@require_role('operator')
def report_machine_recovery():
    """
    Report a machine recovery after breakdown.

    Request JSON:
        {
            "machine_id": "machine-01"
        }

    Response:
        - 200: Trigger event result
        - 400: Missing machine_id
    """
    from services.scheduling_trigger_service import get_scheduling_trigger_service

    data = request.get_json() or {}

    machine_id = data.get('machine_id')
    if not machine_id:
        return jsonify({'error': 'machine_id is required'}), 400

    service = get_scheduling_trigger_service()
    event = service.on_machine_recovered(machine_id=machine_id)

    if not event:
        return jsonify({
            'success': False,
            'message': 'Recovery trigger ignored (in cooldown or disabled)'
        })

    return jsonify({
        'success': True,
        'event': event.to_dict(),
        'message': f'Recovery reported for {machine_id}'
    })


@bp.route('/triggers/delay', methods=['POST'])
@require_auth
@require_role('operator')
def report_job_delay():
    """
    Report a job delay for potential rescheduling.

    Request JSON:
        {
            "job_id": "job-001",
            "delay_minutes": 30,
            "machine_id": "machine-01"
        }

    Response:
        - 200: Trigger event result
        - 400: Missing required fields
    """
    from services.scheduling_trigger_service import get_scheduling_trigger_service

    data = request.get_json() or {}

    job_id = data.get('job_id')
    delay_minutes = data.get('delay_minutes')

    if not job_id:
        return jsonify({'error': 'job_id is required'}), 400
    if delay_minutes is None:
        return jsonify({'error': 'delay_minutes is required'}), 400

    service = get_scheduling_trigger_service()
    event = service.on_job_delay(
        job_id=job_id,
        delay_minutes=int(delay_minutes),
        machine_id=data.get('machine_id'),
    )

    if not event:
        return jsonify({
            'success': False,
            'message': f'Delay of {delay_minutes}m below threshold or trigger disabled'
        })

    return jsonify({
        'success': True,
        'event': event.to_dict(),
        'message': f'Delay of {delay_minutes}m reported for {job_id}'
    })


@bp.route('/triggers/urgent', methods=['POST'])
@require_auth
@require_role('operator')
def add_urgent_job():
    """
    Add an urgent job that requires immediate scheduling attention.

    Request JSON:
        {
            "job_id": "job-urgent-001",
            "priority": 1
        }

    Response:
        - 200: Trigger event result
        - 400: Missing job_id
    """
    from services.scheduling_trigger_service import get_scheduling_trigger_service

    data = request.get_json() or {}

    job_id = data.get('job_id')
    if not job_id:
        return jsonify({'error': 'job_id is required'}), 400

    service = get_scheduling_trigger_service()
    event = service.on_urgent_job(
        job_id=job_id,
        priority=data.get('priority', 1),
    )

    if not event:
        return jsonify({
            'success': False,
            'message': 'Urgent job trigger ignored (in cooldown or disabled)'
        })

    return jsonify({
        'success': True,
        'event': event.to_dict(),
        'message': f'Urgent job {job_id} added'
    })


# ============================================================================
# Policy Experimentation Framework
# ============================================================================

@bp.route('/experiments/policies', methods=['GET'])
@require_auth
def list_scheduling_policies():
    """
    List all available scheduling policies for experimentation.

    Response:
        - 200: List of registered policies with metadata
    """
    from services.scheduling.policy_interface import list_policies

    policies = list_policies()

    return jsonify({
        'policies': policies,
        'total': len(policies)
    })


@bp.route('/experiments/run', methods=['POST'])
@require_auth
@require_role('operator')
def run_scheduling_experiment():
    """
    Run a scheduling policy experiment.

    Request JSON:
        {
            "policy_name": "spt",
            "policy_params": {},
            "baseline_policy": "edd",
            "horizon_hours": 24,
            "seed": 42,
            "objective_weights": {
                "makespan": 0.2,
                "tardiness": 0.4,
                "changeovers": 0.2,
                "utilization": 0.2
            }
        }

    Response:
        - 200: Experiment results with KPIs and comparison
        - 400: Invalid request
        - 500: Experiment failed
    """
    from services.scheduling.experiment_runner import (
        get_experiment_runner,
        ExperimentConfig
    )

    data = request.get_json() or {}

    policy_name = data.get('policy_name', 'fifo')

    try:
        config = ExperimentConfig(
            policy_name=policy_name,
            policy_params=data.get('policy_params', {}),
            baseline_policy=data.get('baseline_policy', 'edd'),
            horizon_hours=data.get('horizon_hours', 24.0),
            seed=data.get('seed', 42),
            objective_weights=data.get('objective_weights', {
                "makespan": 0.2,
                "tardiness": 0.4,
                "changeovers": 0.2,
                "utilization": 0.2
            })
        )

        runner = get_experiment_runner()
        result = runner.run_experiment(config)

        return jsonify({
            'success': True,
            'experiment_id': result.experiment_id,
            'policy_name': result.policy_name,
            'policy_version': result.policy_version,
            'kpis': result.kpis.to_dict(),
            'baseline_kpis': result.baseline_kpis.to_dict() if result.baseline_kpis else None,
            'improvement': result.improvement,
            'duration_seconds': result.duration_seconds,
            'artifacts_path': result.artifacts_path
        })

    except ValueError as e:
        return jsonify({'error': f'Invalid configuration: {e}'}), 400
    except Exception as e:
        logger.error(f"Experiment failed: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/experiments/compare', methods=['POST'])
@require_auth
@require_role('operator')
def compare_scheduling_policies():
    """
    Compare multiple scheduling policies on the same dataset.

    Request JSON:
        {
            "policies": ["fifo", "spt", "edd"],
            "horizon_hours": 24,
            "seed": 42
        }

    Response:
        - 200: Comparison results for all policies
    """
    from services.scheduling.experiment_runner import (
        get_experiment_runner,
        ExperimentConfig
    )

    data = request.get_json() or {}

    policies = data.get('policies', ['fifo', 'spt', 'edd'])
    if not policies:
        return jsonify({'error': 'policies array is required'}), 400

    try:
        config = ExperimentConfig(
            horizon_hours=data.get('horizon_hours', 24.0),
            seed=data.get('seed', 42)
        )

        runner = get_experiment_runner()
        results = runner.compare_policies(policies, config)

        # Build comparison summary
        comparison = []
        for policy_name, result in results.items():
            comparison.append({
                'policy': policy_name,
                'experiment_id': result.experiment_id,
                'kpis': result.kpis.to_dict(),
                'improvement': result.improvement,
                'duration_seconds': result.duration_seconds
            })

        # Rank by makespan
        comparison.sort(key=lambda x: x['kpis']['makespan'])
        for i, c in enumerate(comparison):
            c['rank_by_makespan'] = i + 1

        # Rank by tardiness
        comparison_copy = sorted(comparison, key=lambda x: x['kpis']['total_tardiness'])
        for i, c in enumerate(comparison_copy):
            next((x for x in comparison if x['policy'] == c['policy']), {})['rank_by_tardiness'] = i + 1

        return jsonify({
            'success': True,
            'comparison': comparison,
            'best_makespan': comparison[0]['policy'] if comparison else None,
            'best_tardiness': comparison_copy[0]['policy'] if comparison_copy else None
        })

    except Exception as e:
        logger.error(f"Policy comparison failed: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/experiments', methods=['GET'])
@require_auth
def list_experiments():
    """
    List recent experiments.

    Query Parameters:
        - limit: Maximum number of experiments (default 50)

    Response:
        - 200: List of experiment results
    """
    from services.scheduling.experiment_runner import get_experiment_runner

    limit = request.args.get('limit', 50, type=int)

    runner = get_experiment_runner()
    experiments = runner.list_experiments(limit=limit)

    return jsonify({
        'experiments': experiments,
        'total': len(experiments)
    })


@bp.route('/experiments/<experiment_id>', methods=['GET'])
@require_auth
def get_experiment(experiment_id: str):
    """
    Get details for a specific experiment.

    Response:
        - 200: Experiment details
        - 404: Experiment not found
    """
    from services.scheduling.experiment_runner import get_experiment_runner

    runner = get_experiment_runner()
    result = runner.get_experiment(experiment_id)

    if not result:
        return jsonify({'error': f'Experiment not found: {experiment_id}'}), 404

    return jsonify({
        'experiment': result.to_dict()
    })


# ============================================================================
# Dispatcher & Shadow Mode
# ============================================================================

@bp.route('/dispatcher/status', methods=['GET'])
@require_auth
def get_dispatcher_status():
    """
    Get dispatcher status including shadow mode and canary configuration.

    Response:
        - 200: Dispatcher status
    """
    from services.scheduling.dispatcher import get_dispatcher

    dispatcher = get_dispatcher()
    status = dispatcher.get_status()

    return jsonify({
        'status': status
    })


@bp.route('/dispatcher/shadow', methods=['POST'])
@require_auth
@require_role('admin')
def set_shadow_mode():
    """
    Enable or disable shadow mode.

    Request JSON:
        {
            "enabled": true
        }

    Response:
        - 200: Shadow mode updated
    """
    from services.scheduling.dispatcher import get_dispatcher

    data = request.get_json() or {}
    enabled = data.get('enabled', False)

    dispatcher = get_dispatcher()
    dispatcher.set_shadow_mode(enabled)

    return jsonify({
        'success': True,
        'shadow_mode': enabled
    })


@bp.route('/dispatcher/canary', methods=['POST'])
@require_auth
@require_role('admin')
def configure_canary():
    """
    Enable canary deployment for a policy.

    Request JSON:
        {
            "policy_name": "spt",
            "percentage": 0.1
        }

    Response:
        - 200: Canary configured
        - 400: Invalid configuration
    """
    from services.scheduling.dispatcher import get_dispatcher

    data = request.get_json() or {}

    policy_name = data.get('policy_name')
    percentage = data.get('percentage', 0.1)

    if not policy_name:
        return jsonify({'error': 'policy_name is required'}), 400

    try:
        dispatcher = get_dispatcher()
        dispatcher.enable_canary(policy_name, percentage)

        return jsonify({
            'success': True,
            'canary_policy': policy_name,
            'percentage': percentage
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/dispatcher/canary', methods=['DELETE'])
@require_auth
@require_role('admin')
def disable_canary():
    """
    Disable canary deployment.

    Response:
        - 200: Canary disabled
    """
    from services.scheduling.dispatcher import get_dispatcher

    dispatcher = get_dispatcher()
    dispatcher.disable_canary()

    return jsonify({
        'success': True,
        'message': 'Canary deployment disabled'
    })


@bp.route('/dispatcher/audit', methods=['GET'])
@require_auth
def get_dispatcher_audit():
    """
    Get dispatcher audit log.

    Query Parameters:
        - limit: Maximum entries (default 100)

    Response:
        - 200: Audit log entries
    """
    from services.scheduling.dispatcher import get_dispatcher

    limit = request.args.get('limit', 100, type=int)

    dispatcher = get_dispatcher()
    audit = dispatcher.get_audit_log(limit=limit)
    violations = dispatcher.get_violation_stats()
    acceptance_rate = dispatcher.get_acceptance_rate()

    return jsonify({
        'audit_log': audit,
        'violation_stats': violations,
        'acceptance_rate': acceptance_rate,
        'total_entries': len(audit)
    })


# ============================================================================
# Rollback Manager
# ============================================================================

@bp.route('/rollback/status', methods=['GET'])
@require_auth
def get_rollback_status():
    """
    Get rollback manager status.

    Response:
        - 200: Rollback manager status
    """
    from services.scheduling.rollback_manager import get_rollback_manager

    manager = get_rollback_manager()
    status = manager.get_status()
    policies = manager.get_all_policies()

    return jsonify({
        'status': status,
        'tracked_policies': policies
    })


@bp.route('/rollback/canary', methods=['POST'])
@require_auth
@require_role('admin')
def start_policy_canary():
    """
    Start canary deployment for a policy with rollback monitoring.

    Request JSON:
        {
            "policy_name": "spt",
            "percentage": 0.1
        }

    Response:
        - 200: Canary started
    """
    from services.scheduling.rollback_manager import get_rollback_manager

    data = request.get_json() or {}

    policy_name = data.get('policy_name')
    percentage = data.get('percentage', 0.1)

    if not policy_name:
        return jsonify({'error': 'policy_name is required'}), 400

    manager = get_rollback_manager()
    success = manager.start_canary(policy_name, percentage)

    if success:
        return jsonify({
            'success': True,
            'policy': policy_name,
            'percentage': percentage,
            'status': 'canary'
        })
    else:
        return jsonify({'error': 'Failed to start canary'}), 500


@bp.route('/rollback/promote/<policy_name>', methods=['POST'])
@require_auth
@require_role('admin')
def promote_policy(policy_name: str):
    """
    Promote a canary policy to active.

    Response:
        - 200: Policy promoted
        - 400: Cannot promote (insufficient samples or not in canary)
    """
    from services.scheduling.rollback_manager import get_rollback_manager

    manager = get_rollback_manager()
    success = manager.promote_policy(policy_name)

    if success:
        return jsonify({
            'success': True,
            'message': f'Policy {policy_name} promoted to active',
            'active_policy': manager.get_active_policy()
        })
    else:
        return jsonify({
            'error': f'Cannot promote {policy_name}',
            'message': 'Insufficient samples or policy not in canary status'
        }), 400


@bp.route('/rollback/history', methods=['GET'])
@require_auth
def get_rollback_history():
    """
    Get rollback event history.

    Query Parameters:
        - limit: Maximum events (default 20)

    Response:
        - 200: Rollback events
    """
    from services.scheduling.rollback_manager import get_rollback_manager

    limit = request.args.get('limit', 20, type=int)

    manager = get_rollback_manager()
    history = manager.get_rollback_history(limit=limit)

    return jsonify({
        'rollback_events': history,
        'total': len(history)
    })


@bp.route('/rollback/thresholds', methods=['GET'])
@require_auth
def get_rollback_thresholds():
    """
    Get current regression thresholds.

    Response:
        - 200: Threshold configuration
    """
    from services.scheduling.rollback_manager import get_rollback_manager

    manager = get_rollback_manager()
    status = manager.get_status()

    return jsonify({
        'thresholds': status.get('thresholds', {}),
        'regression_threshold': status.get('regression_threshold'),
        'min_samples': status.get('min_samples'),
        'evaluation_window': status.get('evaluation_window')
    })


@bp.route('/rollback/thresholds/<metric>', methods=['PUT'])
@require_auth
@require_role('admin')
def set_rollback_threshold(metric: str):
    """
    Set regression threshold for a specific metric.

    Request JSON:
        {
            "threshold": 0.15
        }

    Response:
        - 200: Threshold updated
    """
    from services.scheduling.rollback_manager import get_rollback_manager

    data = request.get_json() or {}
    threshold = data.get('threshold')

    if threshold is None:
        return jsonify({'error': 'threshold is required'}), 400

    manager = get_rollback_manager()
    manager.set_threshold(metric, float(threshold))

    return jsonify({
        'success': True,
        'metric': metric,
        'threshold': threshold
    })


# ============================================================================
# Feature Store
# ============================================================================

@bp.route('/features/schema', methods=['GET'])
@require_auth
def get_feature_schema():
    """
    Get the feature schema with all available features.

    Response:
        - 200: Feature definitions by category
    """
    from services.scheduling.feature_store import get_feature_store

    store = get_feature_store()
    features = store.get_feature_names()
    version = store.get_version()

    return jsonify({
        'version': version,
        'features': features,
        'job_features': len(features.get('job', [])),
        'machine_features': len(features.get('machine', [])),
        'system_features': len(features.get('system', []))
    })
