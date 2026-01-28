"""
LEGO Factory v3 - Simulation API
=================================
REST API endpoints for discrete-event simulation.
"""

import logging
from datetime import datetime
from typing import Optional
import uuid

from flask import Blueprint, jsonify, request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

simulation_api = Blueprint('simulation_api', __name__, url_prefix='/api/simulation')


class SimulationRunRequest(BaseModel):
    """Request for running a simulation."""
    schedule_id: Optional[str] = None
    algorithm: str = 'cpsat'
    job_set: Optional[list] = None
    n_replications: int = Field(default=10, ge=1, le=500)
    duration_hours: float = Field(default=168.0, ge=1, le=720)
    seed: Optional[int] = None
    enable_breakdowns: bool = True
    enable_quality_defects: bool = True
    enable_material_shortages: bool = True


class AlgorithmCompareRequest(BaseModel):
    """Request for algorithm comparison."""
    algorithms: list = Field(default=['cpsat', 'spt', 'edd', 'wspt'])
    job_set: Optional[list] = None
    n_replications: int = Field(default=30, ge=1, le=200)
    seed: Optional[int] = None


# In-memory cache for simulation results
_simulation_cache = {}


@simulation_api.route('/run', methods=['POST'])
def run_simulation():
    """
    Run a discrete-event simulation.

    Body:
        schedule_id: Optional schedule ID to simulate
        algorithm: Algorithm to use for scheduling
        job_set: Optional list of jobs (if no schedule_id)
        n_replications: Number of Monte Carlo replications
        duration_hours: Simulation duration
        seed: Random seed for reproducibility
        enable_*: Flags for stochastic events

    Returns:
        run_id: ID to retrieve results
        status: 'running' or 'completed'
    """
    try:
        data = request.get_json() or {}

        # Generate run ID
        run_id = str(uuid.uuid4())[:8]

        # Get jobs and machines
        jobs, machines = _get_simulation_inputs(data)

        if not jobs:
            return jsonify({'error': 'No jobs to simulate'}), 400

        # Run simulation
        from services.simulation.scenario_runner import run_scenario

        n_reps = min(data.get('n_replications', 10), 100)  # Cap at 100 for API
        seed = data.get('seed', 42)
        duration = data.get('duration_hours', 168.0)

        # Generate schedule based on algorithm
        algorithm = data.get('algorithm', 'cpsat')
        schedule = _generate_schedule_for_sim(jobs, machines, algorithm)

        result = run_scenario(
            schedule=schedule,
            machines=machines,
            n_replications=n_reps,
            seed=seed,
            duration_hours=duration,
            enable_breakdowns=data.get('enable_breakdowns', True),
            enable_quality_defects=data.get('enable_quality_defects', True),
            enable_material_shortages=data.get('enable_material_shortages', True),
            parallel=n_reps > 5,
        )

        # Cache result
        _simulation_cache[run_id] = {
            'status': 'completed',
            'result': result,
            'created_at': datetime.utcnow().isoformat(),
            'algorithm': algorithm,
            'n_replications': n_reps,
        }

        return jsonify({
            'run_id': run_id,
            'status': 'completed',
            'summary': {
                'n_replications': result['n_replications'],
                'makespan_mean': result['statistics'].get('makespan', {}).get('mean'),
                'makespan_ci95': result['statistics'].get('makespan', {}).get('ci95'),
                'tardiness_mean': result['statistics'].get('tardiness', {}).get('mean'),
                'utilization_mean': result['statistics'].get('utilization', {}).get('mean'),
            }
        })

    except Exception as e:
        logger.error(f"Simulation run failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@simulation_api.route('/results/<run_id>', methods=['GET'])
def get_simulation_results(run_id: str):
    """
    Get results from a simulation run.

    Args:
        run_id: Simulation run ID

    Returns:
        Full simulation results
    """
    cached = _simulation_cache.get(run_id)
    if not cached:
        return jsonify({'error': 'Run not found'}), 404

    return jsonify({
        'run_id': run_id,
        'status': cached['status'],
        'algorithm': cached.get('algorithm'),
        'n_replications': cached.get('n_replications'),
        'created_at': cached.get('created_at'),
        'result': cached['result'],
    })


@simulation_api.route('/compare', methods=['POST'])
def compare_algorithms():
    """
    Compare scheduling algorithms using Monte Carlo simulation.

    Body:
        algorithms: List of algorithm names
        job_set: Optional job set
        n_replications: Replications per algorithm

    Returns:
        Comparison results with statistics
    """
    try:
        data = request.get_json() or {}

        algorithms = data.get('algorithms', ['cpsat', 'spt', 'edd', 'wspt'])
        n_reps = min(data.get('n_replications', 30), 50)  # Cap for API
        seed = data.get('seed', 42)

        # Get jobs and machines
        jobs, machines = _get_simulation_inputs(data)

        if not jobs:
            return jsonify({'error': 'No jobs to compare'}), 400

        # Run comparison
        from services.simulation.scenario_runner import compare_algorithms as run_compare

        result = run_compare(
            jobs=jobs,
            machines=machines,
            algorithms=algorithms,
            n_replications=n_reps,
            seed=seed,
        )

        return jsonify({
            'algorithms': result['algorithms'],
            'n_replications': result['n_replications'],
            'comparison': result['comparison'],
            'winner': result['winner'],
            'details': {
                algo: {
                    'makespan': res['statistics'].get('makespan', {}),
                    'tardiness': res['statistics'].get('tardiness', {}),
                    'utilization': res['statistics'].get('utilization', {}),
                }
                for algo, res in result['results'].items()
            }
        })

    except Exception as e:
        logger.error(f"Algorithm comparison failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@simulation_api.route('/quick-run', methods=['POST'])
def quick_simulation():
    """
    Run a quick single-replication simulation.

    Useful for testing and quick estimates.
    """
    try:
        data = request.get_json() or {}

        jobs, machines = _get_simulation_inputs(data)

        if not jobs:
            return jsonify({'error': 'No jobs to simulate'}), 400

        # Generate schedule
        algorithm = data.get('algorithm', 'spt')
        schedule = _generate_schedule_for_sim(jobs, machines, algorithm)

        # Run single simulation
        from services.simulation.des_engine import DiscreteEventSimulator, SimConfig
        from services.simulation.sim_reporter import SimReporter

        config = SimConfig(
            start_time=datetime.utcnow(),
            duration_hours=data.get('duration_hours', 168.0),
            enable_breakdowns=data.get('enable_breakdowns', True),
            enable_quality_defects=data.get('enable_quality_defects', True),
            enable_material_shortages=data.get('enable_material_shortages', True),
            random_seed=data.get('seed', 42),
        )

        simulator = DiscreteEventSimulator(config)
        result = simulator.run(schedule, machines)

        reporter = SimReporter()
        report = reporter.generate_report(result)

        return jsonify({
            'status': 'completed',
            'summary': report['summary'],
            'machine_analysis': report['machine_analysis'],
            'job_analysis': {
                'on_time_rate': report['job_analysis']['on_time_rate'],
                'late_count': report['job_analysis']['late_count'],
            },
            'recommendations': report['recommendations'],
        })

    except Exception as e:
        logger.error(f"Quick simulation failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@simulation_api.route('/parameters', methods=['GET'])
def get_simulation_parameters():
    """Get current simulation parameters."""
    try:
        from services.simulation.stochastic_models import load_simulation_params

        params = load_simulation_params()

        return jsonify({
            'machines': params.get('machines', {}),
            'global': params.get('global', {}),
            'scenarios': params.get('scenarios', {}),
        })

    except Exception as e:
        logger.error(f"Failed to get parameters: {e}")
        return jsonify({'error': str(e)}), 500


@simulation_api.route('/machines', methods=['GET'])
def get_simulation_machines():
    """Get available machines for simulation."""
    try:
        machines = _get_default_machines()
        return jsonify({'machines': machines})
    except Exception as e:
        logger.error(f"Failed to get machines: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Live Simulation Endpoints
# =============================================================================

@simulation_api.route('/live/start', methods=['POST'])
def start_live_simulation():
    """
    Start a live (accelerated real-time) simulation.

    Body:
        schedule_id: Optional schedule ID
        speed_factor: Speed multiplier (1-1000, default 60)
        duration_hours: Simulation duration
        enable_breakdowns: Enable random breakdowns
        enable_defects: Enable quality defects
        enable_shortages: Enable material shortages

    Returns:
        sim_id: Live simulation ID
        status: 'running'
    """
    try:
        data = request.get_json() or {}

        # Check if already running
        from services.simulation.live_simulator import get_active_simulator
        active = get_active_simulator()
        if active and active.is_running:
            return jsonify({
                'error': 'Simulation already running',
                'sim_id': active.sim_id,
            }), 409

        # Get inputs
        jobs, machines = _get_simulation_inputs(data)
        if not jobs:
            return jsonify({'error': 'No jobs to simulate'}), 400

        # Generate schedule
        algorithm = data.get('algorithm', 'spt')
        schedule = _generate_schedule_for_sim(jobs, machines, algorithm)

        # Configure and start
        from services.simulation.live_simulator import LiveSimConfig, start_live_simulation as start_sim

        config = LiveSimConfig(
            schedule_id=data.get('schedule_id', 'live'),
            speed_factor=min(1000, max(1, data.get('speed_factor', 60))),
            duration_hours=data.get('duration_hours', 168.0),
            enable_breakdowns=data.get('enable_breakdowns', True),
            enable_defects=data.get('enable_defects', True),
            enable_shortages=data.get('enable_shortages', True),
        )

        simulator = start_sim(schedule, machines, config)

        return jsonify({
            'sim_id': simulator.sim_id,
            'status': 'running',
            'speed_factor': config.speed_factor,
            'start_time': simulator.sim_time.isoformat(),
        })

    except Exception as e:
        logger.error(f"Failed to start live simulation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@simulation_api.route('/live/pause', methods=['POST'])
def pause_live_simulation():
    """Pause the running live simulation."""
    try:
        from services.simulation.live_simulator import get_active_simulator

        simulator = get_active_simulator()
        if not simulator or not simulator.is_running:
            return jsonify({'error': 'No simulation running'}), 404

        simulator.pause()

        return jsonify({
            'sim_id': simulator.sim_id,
            'status': 'paused',
            'sim_time': simulator.sim_time.isoformat(),
        })

    except Exception as e:
        logger.error(f"Failed to pause simulation: {e}")
        return jsonify({'error': str(e)}), 500


@simulation_api.route('/live/resume', methods=['POST'])
def resume_live_simulation():
    """Resume a paused live simulation."""
    try:
        from services.simulation.live_simulator import get_active_simulator

        simulator = get_active_simulator()
        if not simulator:
            return jsonify({'error': 'No simulation active'}), 404

        simulator.resume()

        return jsonify({
            'sim_id': simulator.sim_id,
            'status': 'running',
            'sim_time': simulator.sim_time.isoformat(),
        })

    except Exception as e:
        logger.error(f"Failed to resume simulation: {e}")
        return jsonify({'error': str(e)}), 500


@simulation_api.route('/live/stop', methods=['POST'])
def stop_live_simulation():
    """Stop the live simulation."""
    try:
        from services.simulation.live_simulator import get_active_simulator, stop_live_simulation as stop_sim

        simulator = get_active_simulator()
        if not simulator:
            return jsonify({'error': 'No simulation active'}), 404

        summary = simulator.get_state()
        stop_sim()

        return jsonify({
            'status': 'stopped',
            'summary': summary,
        })

    except Exception as e:
        logger.error(f"Failed to stop simulation: {e}")
        return jsonify({'error': str(e)}), 500


@simulation_api.route('/live/speed', methods=['PUT'])
def set_live_simulation_speed():
    """
    Change live simulation speed.

    Body:
        factor: New speed factor (1-1000)
    """
    try:
        data = request.get_json() or {}
        factor = data.get('factor', 60)

        from services.simulation.live_simulator import get_active_simulator

        simulator = get_active_simulator()
        if not simulator or not simulator.is_running:
            return jsonify({'error': 'No simulation running'}), 404

        simulator.set_speed(factor)

        return jsonify({
            'sim_id': simulator.sim_id,
            'speed_factor': simulator.speed_factor,
        })

    except Exception as e:
        logger.error(f"Failed to set speed: {e}")
        return jsonify({'error': str(e)}), 500


@simulation_api.route('/live/state', methods=['GET'])
def get_live_simulation_state():
    """Get current live simulation state."""
    try:
        from services.simulation.live_simulator import get_active_simulator

        simulator = get_active_simulator()
        if not simulator:
            # Check persistent state
            from services.simulation.sim_state import SimulationState
            state = SimulationState.get_active()
            if state:
                return jsonify(state)
            return jsonify({'status': 'no_simulation'})

        return jsonify(simulator.get_state())

    except Exception as e:
        logger.error(f"Failed to get state: {e}")
        return jsonify({'error': str(e)}), 500


@simulation_api.route('/live/inject', methods=['POST'])
def inject_simulation_event():
    """
    Inject a manual event into the simulation.

    Body:
        event_type: Event type (breakdown, quality_defect, material_shortage)
        machine_id: Target machine
        data: Optional event data
    """
    try:
        data = request.get_json() or {}

        event_type = data.get('event_type')
        machine_id = data.get('machine_id')

        if not event_type or not machine_id:
            return jsonify({'error': 'event_type and machine_id required'}), 400

        from services.simulation.live_simulator import get_active_simulator

        simulator = get_active_simulator()
        if not simulator or not simulator.is_running:
            return jsonify({'error': 'No simulation running'}), 404

        simulator.inject_event(event_type, machine_id, data.get('data'))

        return jsonify({
            'status': 'injected',
            'event_type': event_type,
            'machine_id': machine_id,
            'sim_time': simulator.sim_time.isoformat(),
        })

    except Exception as e:
        logger.error(f"Failed to inject event: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Helper Functions
# =============================================================================

def _get_simulation_inputs(data: dict):
    """Get jobs and machines for simulation from request data or database."""
    jobs = data.get('job_set', [])
    machines = data.get('machines', [])

    # If no jobs provided, try to get from database
    if not jobs:
        jobs = _get_jobs_from_db()

    # If no machines provided, use defaults
    if not machines:
        machines = _get_default_machines()

    return jobs, machines


def _get_jobs_from_db():
    """Get pending/queued jobs from database."""
    try:
        from database import db
        from models.mes.work_orders import Job, JobStatus

        jobs = db.session.query(Job).filter(
            Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.PAUSED])
        ).all()

        return [
            {
                'job_id': j.job_id,
                'work_order_id': str(j.work_order_id),
                'processing_time_mins': j.runtime_data.get('estimated_duration_mins', 30) if j.runtime_data else 30,
                'setup_time_mins': j.runtime_data.get('setup_time_mins', 5) if j.runtime_data else 5,
                'material_type': j.runtime_data.get('material_type') if j.runtime_data else None,
                'priority': j.priority_score or 5,
                'due_date': j.due_date.isoformat() if j.due_date else None,
                'eligible_machines': j.runtime_data.get('eligible_machines', []) if j.runtime_data else [],
            }
            for j in jobs
        ]
    except Exception as e:
        logger.warning(f"Could not get jobs from DB: {e}")
        return _get_sample_jobs()


def _get_sample_jobs():
    """Get sample jobs for testing."""
    from datetime import timedelta

    base_time = datetime.utcnow()

    return [
        {
            'job_id': f'JOB-{i:03d}',
            'work_order_id': f'WO-{(i // 3) + 1:03d}',
            'processing_time_mins': 30 + (i % 4) * 15,
            'setup_time_mins': 5 + (i % 3) * 2,
            'material_type': ['PLA', 'ABS', 'PETG'][i % 3],
            'priority': 3 + (i % 5),
            'due_date': (base_time + timedelta(hours=24 + i * 2)).isoformat(),
            'eligible_machines': ['bambu-ps1', 'bambu-ps2', 'prusa-mk4-1', 'prusa-mk4-2'],
        }
        for i in range(15)
    ]


def _get_default_machines():
    """Get default machine definitions."""
    return [
        {'machine_id': 'bambu-ps1', 'type': 'FDM', 'power_watts': 150},
        {'machine_id': 'bambu-ps2', 'type': 'FDM', 'power_watts': 150},
        {'machine_id': 'prusa-mk4-1', 'type': 'FDM', 'power_watts': 100},
        {'machine_id': 'prusa-mk4-2', 'type': 'FDM', 'power_watts': 100},
        {'machine_id': 'formlabs-3l', 'type': 'SLA', 'power_watts': 200},
        {'machine_id': 'bantam-explorer', 'type': 'CNC', 'power_watts': 500},
        {'machine_id': 'nomad-883', 'type': 'CNC', 'power_watts': 300},
        {'machine_id': 'k40-laser', 'type': 'Laser', 'power_watts': 800},
        {'machine_id': 'emblaser-2', 'type': 'Laser', 'power_watts': 400},
        {'machine_id': 'assembly-1', 'type': 'Assembly', 'power_watts': 50},
        {'machine_id': 'inspection-1', 'type': 'Inspection', 'power_watts': 30},
    ]


def _generate_schedule_for_sim(jobs, machines, algorithm):
    """Generate schedule using specified algorithm."""
    from services.simulation.scenario_runner import _generate_schedule
    return _generate_schedule(jobs, machines, algorithm)
