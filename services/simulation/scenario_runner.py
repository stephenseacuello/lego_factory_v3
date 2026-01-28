"""
LEGO Factory v3 - Scenario Runner
==================================
Runs Monte Carlo simulations and algorithm comparisons.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

logger = logging.getLogger(__name__)


def _run_single_replication(args: tuple) -> Dict[str, Any]:
    """
    Run a single simulation replication.

    Designed to be called in separate process.
    """
    schedule, machines, config_dict, seed = args

    # Import here to avoid pickling issues
    from services.simulation.des_engine import DiscreteEventSimulator, SimConfig

    # Reconstruct config with seed
    config = SimConfig(
        start_time=datetime.fromisoformat(config_dict['start_time']),
        duration_hours=config_dict['duration_hours'],
        enable_breakdowns=config_dict.get('enable_breakdowns', True),
        enable_quality_defects=config_dict.get('enable_quality_defects', True),
        enable_material_shortages=config_dict.get('enable_material_shortages', True),
        enable_setup_variability=config_dict.get('enable_setup_variability', True),
        enable_process_variability=config_dict.get('enable_process_variability', True),
        random_seed=seed,
    )

    simulator = DiscreteEventSimulator(config)
    result = simulator.run(schedule, machines)

    return result.to_dict()


def run_scenario(
    schedule: List[Dict[str, Any]],
    machines: List[Dict[str, Any]],
    n_replications: int = 100,
    seed: int = 42,
    duration_hours: float = 168.0,
    enable_breakdowns: bool = True,
    enable_quality_defects: bool = True,
    enable_material_shortages: bool = True,
    parallel: bool = True,
    max_workers: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run Monte Carlo simulation scenario.

    Args:
        schedule: Job schedule to simulate
        machines: Machine definitions
        n_replications: Number of simulation runs
        seed: Base random seed
        duration_hours: Simulation duration
        enable_breakdowns: Enable random breakdowns
        enable_quality_defects: Enable random defects
        enable_material_shortages: Enable material shortages
        parallel: Run replications in parallel
        max_workers: Max parallel workers (default: CPU count)

    Returns:
        Dict with aggregated results and statistics
    """
    from services.simulation.des_engine import DiscreteEventSimulator, SimConfig
    from services.simulation.sim_reporter import SimReporter

    logger.info(f"Running scenario with {n_replications} replications")

    # Prepare config dict for serialization
    config_dict = {
        'start_time': datetime.utcnow().isoformat(),
        'duration_hours': duration_hours,
        'enable_breakdowns': enable_breakdowns,
        'enable_quality_defects': enable_quality_defects,
        'enable_material_shortages': enable_material_shortages,
        'enable_setup_variability': True,
        'enable_process_variability': True,
    }

    results = []

    if parallel and n_replications > 1:
        # Parallel execution
        workers = max_workers or min(multiprocessing.cpu_count(), n_replications)

        # Prepare arguments for each replication
        args_list = [
            (schedule, machines, config_dict, seed + i)
            for i in range(n_replications)
        ]

        try:
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(_run_single_replication, args) for args in args_list]

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Replication failed: {e}")
        except Exception as e:
            logger.warning(f"Parallel execution failed, falling back to serial: {e}")
            parallel = False

    if not parallel or not results:
        # Serial execution
        for i in range(n_replications):
            config = SimConfig(
                start_time=datetime.utcnow(),
                duration_hours=duration_hours,
                enable_breakdowns=enable_breakdowns,
                enable_quality_defects=enable_quality_defects,
                enable_material_shortages=enable_material_shortages,
                random_seed=seed + i,
            )

            simulator = DiscreteEventSimulator(config)
            result = simulator.run(schedule, machines)
            results.append(result)

    logger.info(f"Completed {len(results)} replications")

    # Convert dict results back to SimResult for aggregation
    from services.simulation.des_engine import SimResult, SimConfig

    sim_results = []
    for r in results:
        if isinstance(r, dict):
            # Reconstruct SimResult from dict
            sim_results.append(_dict_to_sim_result(r, config_dict))
        else:
            sim_results.append(r)

    # Aggregate results
    reporter = SimReporter()
    aggregated = reporter.aggregate_replications(sim_results)

    # Calculate statistics
    import numpy as np

    makespans = [r['actual_makespan_mins'] if isinstance(r, dict) else r.actual_makespan_mins for r in results]
    tardiness_vals = [r['total_tardiness_mins'] if isinstance(r, dict) else r.total_tardiness_mins for r in results]

    return {
        'n_replications': len(results),
        'seed': seed,
        'statistics': {
            name: {
                'mean': summary.mean,
                'std': summary.std,
                'ci95': (summary.ci95_lower, summary.ci95_upper),
                'min': summary.min,
                'max': summary.max,
            }
            for name, summary in aggregated.items()
        },
        'makespan_distribution': {
            'values': makespans,
            'mean': float(np.mean(makespans)),
            'std': float(np.std(makespans)),
        },
        'tardiness_distribution': {
            'values': tardiness_vals,
            'mean': float(np.mean(tardiness_vals)),
            'std': float(np.std(tardiness_vals)),
        },
        'individual_results': [r if isinstance(r, dict) else r.to_dict() for r in results[:10]],  # First 10 for detail
    }


def _dict_to_sim_result(d: Dict, config_dict: Dict):
    """Convert dict back to SimResult."""
    from services.simulation.des_engine import SimResult, SimConfig

    config = SimConfig(
        start_time=datetime.fromisoformat(config_dict['start_time']),
        duration_hours=config_dict['duration_hours'],
    )

    return SimResult(
        sim_id=d.get('sim_id', ''),
        config=config,
        actual_makespan_mins=d.get('actual_makespan_mins', 0),
        planned_makespan_mins=d.get('planned_makespan_mins', 0),
        total_tardiness_mins=d.get('total_tardiness_mins', 0),
        jobs_completed=d.get('jobs_completed', 0),
        jobs_failed=d.get('jobs_failed', 0),
        total_breakdowns=d.get('total_breakdowns', 0),
        total_defects=d.get('total_defects', 0),
        total_shortages=d.get('total_shortages', 0),
        machine_utilization=d.get('machine_utilization', {}),
        machine_stats={},
        job_results=[],
        event_log=[],
        avg_wip=d.get('avg_wip', 0),
        schedule_adherence=d.get('schedule_adherence', 0),
    )


def compare_algorithms(
    jobs: List[Dict[str, Any]],
    machines: List[Dict[str, Any]],
    algorithms: List[str],
    n_replications: int = 50,
    seed: int = 42,
    duration_hours: float = 168.0,
) -> Dict[str, Any]:
    """
    Compare scheduling algorithms using Monte Carlo simulation.

    Args:
        jobs: Jobs to schedule
        machines: Machine definitions
        algorithms: List of algorithm names to compare
        n_replications: Replications per algorithm
        seed: Base random seed

    Returns:
        Comparison results dict
    """
    from services.simulation.sim_reporter import SimReporter

    logger.info(f"Comparing algorithms: {algorithms}")

    results = {}
    schedules = {}

    # Generate schedule for each algorithm
    for algo in algorithms:
        try:
            schedule = _generate_schedule(jobs, machines, algo)
            schedules[algo] = schedule
        except Exception as e:
            logger.error(f"Failed to generate schedule for {algo}: {e}")
            continue

    # Run simulations for each algorithm
    for algo, schedule in schedules.items():
        logger.info(f"Running simulations for {algo}")

        scenario_result = run_scenario(
            schedule=schedule,
            machines=machines,
            n_replications=n_replications,
            seed=seed,
            duration_hours=duration_hours,
            parallel=True,
        )

        results[algo] = scenario_result

    # Format comparison
    reporter = SimReporter()

    # Build comparison table
    comparison_data = {}
    for algo, result in results.items():
        comparison_data[algo] = result['statistics']

    return {
        'algorithms': algorithms,
        'n_replications': n_replications,
        'results': results,
        'comparison': _format_comparison(comparison_data),
        'winner': _determine_winner(comparison_data),
    }


def _generate_schedule(
    jobs: List[Dict[str, Any]],
    machines: List[Dict[str, Any]],
    algorithm: str
) -> List[Dict[str, Any]]:
    """
    Generate schedule using specified algorithm.

    Args:
        jobs: Jobs to schedule
        machines: Available machines
        algorithm: Algorithm name

    Returns:
        Schedule as list of job assignments
    """
    from datetime import timedelta

    # Try to use actual scheduling service
    try:
        from services.scheduling.unified_scheduler import UnifiedScheduler

        scheduler = UnifiedScheduler()
        result = scheduler.schedule(
            jobs=jobs,
            machines=machines,
            algorithm=algorithm,
        )

        if hasattr(result, 'schedule'):
            return result.schedule
        elif isinstance(result, list):
            return result
    except Exception as e:
        logger.warning(f"Unified scheduler not available: {e}")

    # Fallback: simple dispatching based on algorithm
    start_time = datetime.utcnow()
    schedule = []
    machine_end_times = {m['machine_id']: start_time for m in machines}

    # Sort jobs based on algorithm
    if algorithm == 'spt':
        sorted_jobs = sorted(jobs, key=lambda j: j.get('processing_time_mins', 30))
    elif algorithm == 'edd':
        sorted_jobs = sorted(jobs, key=lambda j: j.get('due_date') or datetime.max)
    elif algorithm == 'wspt':
        sorted_jobs = sorted(
            jobs,
            key=lambda j: (j.get('priority', 5) / max(1, j.get('processing_time_mins', 30))),
            reverse=True
        )
    else:
        sorted_jobs = jobs.copy()

    # Assign jobs to machines
    for job in sorted_jobs:
        job_id = job.get('job_id') or job.get('id')
        duration = job.get('processing_time_mins', 30)
        eligible = job.get('eligible_machines', [m['machine_id'] for m in machines])

        # Find machine with earliest availability
        best_machine = None
        best_end = datetime.max

        for machine_id in eligible:
            if machine_id in machine_end_times:
                if machine_end_times[machine_id] < best_end:
                    best_end = machine_end_times[machine_id]
                    best_machine = machine_id

        if best_machine:
            job_start = machine_end_times[best_machine]
            job_end = job_start + timedelta(minutes=duration)

            schedule.append({
                'job_id': job_id,
                'machine_id': best_machine,
                'start': job_start,
                'end': job_end,
                'work_order_id': job.get('work_order_id', ''),
                'processing_time_mins': duration,
                'setup_time_mins': job.get('setup_time_mins', 5),
                'material_type': job.get('material_type'),
                'priority': job.get('priority', 5),
                'due_date': job.get('due_date'),
            })

            machine_end_times[best_machine] = job_end

    return schedule


def _format_comparison(data: Dict[str, Dict]) -> Dict[str, Any]:
    """Format comparison data as table."""
    kpis = ['makespan', 'tardiness', 'utilization', 'schedule_adherence']
    rows = []

    for algo, stats in data.items():
        row = {'algorithm': algo}
        for kpi in kpis:
            if kpi in stats:
                s = stats[kpi]
                row[kpi] = s['mean']
                row[f'{kpi}_ci'] = s.get('ci95', (s['mean'], s['mean']))
        rows.append(row)

    return {
        'kpis': kpis,
        'rows': rows,
    }


def _determine_winner(data: Dict[str, Dict]) -> Dict[str, str]:
    """Determine best algorithm for each metric."""
    winners = {}

    # Makespan: lower is better
    if all('makespan' in stats for stats in data.values()):
        best_algo = min(data.keys(), key=lambda a: data[a]['makespan']['mean'])
        winners['makespan'] = best_algo

    # Tardiness: lower is better
    if all('tardiness' in stats for stats in data.values()):
        best_algo = min(data.keys(), key=lambda a: data[a]['tardiness']['mean'])
        winners['tardiness'] = best_algo

    # Utilization: higher is better
    if all('utilization' in stats for stats in data.values()):
        best_algo = max(data.keys(), key=lambda a: data[a]['utilization']['mean'])
        winners['utilization'] = best_algo

    # Schedule adherence: higher is better
    if all('schedule_adherence' in stats for stats in data.values()):
        best_algo = max(data.keys(), key=lambda a: data[a]['schedule_adherence']['mean'])
        winners['schedule_adherence'] = best_algo

    # Overall winner: most wins
    win_counts = {}
    for winner in winners.values():
        win_counts[winner] = win_counts.get(winner, 0) + 1

    if win_counts:
        winners['overall'] = max(win_counts.keys(), key=lambda a: win_counts[a])

    return winners
