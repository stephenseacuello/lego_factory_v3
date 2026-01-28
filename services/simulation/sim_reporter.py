"""
LEGO Factory v3 - Simulation Reporter
======================================
Generates reports from simulation results.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class KPISummary:
    """Summary statistics for a KPI across replications."""
    mean: float
    std: float
    min: float
    max: float
    ci95_lower: float
    ci95_upper: float


class SimReporter:
    """
    Generates reports from simulation results.

    Supports single-run and multi-replication analysis.
    """

    def __init__(self):
        pass

    def generate_report(self, sim_result) -> Dict[str, Any]:
        """
        Generate report from a single simulation result.

        Args:
            sim_result: SimResult from DES engine

        Returns:
            Formatted report dict
        """
        return {
            'summary': self._generate_summary(sim_result),
            'machine_analysis': self._analyze_machines(sim_result),
            'job_analysis': self._analyze_jobs(sim_result),
            'event_analysis': self._analyze_events(sim_result),
            'recommendations': self._generate_recommendations(sim_result),
        }

    def _generate_summary(self, result) -> Dict[str, Any]:
        """Generate executive summary."""
        # Calculate schedule variance
        makespan_variance = 0.0
        if result.planned_makespan_mins > 0:
            makespan_variance = (
                (result.actual_makespan_mins - result.planned_makespan_mins) /
                result.planned_makespan_mins * 100
            )

        # Average utilization
        avg_utilization = (
            sum(result.machine_utilization.values()) /
            len(result.machine_utilization) if result.machine_utilization else 0
        )

        return {
            'sim_id': result.sim_id,
            'planned_makespan_mins': result.planned_makespan_mins,
            'actual_makespan_mins': result.actual_makespan_mins,
            'makespan_variance_pct': makespan_variance,
            'total_tardiness_mins': result.total_tardiness_mins,
            'jobs_completed': result.jobs_completed,
            'jobs_failed': result.jobs_failed,
            'completion_rate': result.jobs_completed / (result.jobs_completed + result.jobs_failed) if (result.jobs_completed + result.jobs_failed) > 0 else 0,
            'avg_utilization': avg_utilization,
            'total_breakdowns': result.total_breakdowns,
            'total_defects': result.total_defects,
            'total_shortages': result.total_shortages,
            'avg_wip': result.avg_wip,
            'schedule_adherence': result.schedule_adherence,
        }

    def _analyze_machines(self, result) -> Dict[str, Any]:
        """Analyze machine performance."""
        machines = []
        bottleneck = None
        max_util = 0

        for machine_id, stats in result.machine_stats.items():
            machine_info = {
                'machine_id': machine_id,
                'utilization': stats['utilization'],
                'running_time_mins': stats['running_time_mins'],
                'setup_time_mins': stats['setup_time_mins'],
                'breakdown_time_mins': stats['breakdown_time_mins'],
                'breakdown_count': stats['breakdown_count'],
                'jobs_completed': stats['jobs_completed'],
                'availability': 1 - (stats['breakdown_time_mins'] / (stats['running_time_mins'] + stats['setup_time_mins'] + stats['breakdown_time_mins'])) if (stats['running_time_mins'] + stats['setup_time_mins'] + stats['breakdown_time_mins']) > 0 else 1,
            }
            machines.append(machine_info)

            if stats['utilization'] > max_util:
                max_util = stats['utilization']
                bottleneck = machine_id

        # Sort by utilization
        machines.sort(key=lambda x: x['utilization'], reverse=True)

        return {
            'machines': machines,
            'bottleneck': bottleneck,
            'bottleneck_utilization': max_util,
        }

    def _analyze_jobs(self, result) -> Dict[str, Any]:
        """Analyze job performance."""
        on_time = 0
        late = 0
        total_delay = 0.0
        job_details = []

        for job in result.job_results:
            actual_end = job.get('actual_end')
            planned_end = job.get('planned_end')

            if actual_end and planned_end:
                actual_dt = datetime.fromisoformat(actual_end) if isinstance(actual_end, str) else actual_end
                planned_dt = datetime.fromisoformat(planned_end) if isinstance(planned_end, str) else planned_end

                delay_mins = (actual_dt - planned_dt).total_seconds() / 60
                if delay_mins <= 0:
                    on_time += 1
                else:
                    late += 1
                    total_delay += delay_mins

                job_details.append({
                    'job_id': job['job_id'],
                    'status': job['status'],
                    'planned_duration': job.get('planned_duration_mins', 0),
                    'actual_duration': job.get('actual_duration_mins', 0),
                    'delay_mins': max(0, delay_mins),
                    'defects': job.get('defect_count', 0),
                })

        return {
            'on_time_count': on_time,
            'late_count': late,
            'on_time_rate': on_time / (on_time + late) if (on_time + late) > 0 else 0,
            'avg_delay_mins': total_delay / late if late > 0 else 0,
            'job_details': job_details[:20],  # Top 20 for brevity
        }

    def _analyze_events(self, result) -> Dict[str, Any]:
        """Analyze simulation events."""
        event_counts = {}
        breakdown_machines = []
        defect_jobs = []

        for event in result.event_log:
            event_type = event['event_type']
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

            if event_type == 'breakdown' and event.get('machine_id'):
                breakdown_machines.append(event['machine_id'])
            elif event_type == 'quality_defect' and event.get('job_id'):
                defect_jobs.append(event['job_id'])

        # Breakdown frequency by machine
        breakdown_freq = {}
        for m in breakdown_machines:
            breakdown_freq[m] = breakdown_freq.get(m, 0) + 1

        return {
            'event_counts': event_counts,
            'breakdown_frequency': breakdown_freq,
            'defect_jobs': list(set(defect_jobs)),
            'total_events': len(result.event_log),
        }

    def _generate_recommendations(self, result) -> List[str]:
        """Generate actionable recommendations."""
        recs = []

        # Utilization recommendations
        for machine_id, util in result.machine_utilization.items():
            if util > 0.9:
                recs.append(f"Machine {machine_id} is at {util:.0%} utilization - consider load balancing")
            elif util < 0.3:
                recs.append(f"Machine {machine_id} is underutilized at {util:.0%} - review job routing")

        # Breakdown recommendations
        for machine_id, stats in result.machine_stats.items():
            if stats['breakdown_count'] > 2:
                recs.append(f"Machine {machine_id} had {stats['breakdown_count']} breakdowns - consider preventive maintenance")

        # Tardiness recommendations
        if result.total_tardiness_mins > 60:
            recs.append(f"Total tardiness of {result.total_tardiness_mins:.0f} mins - review schedule or capacity")

        # Schedule adherence
        if result.schedule_adherence < 0.8:
            recs.append(f"Schedule adherence at {result.schedule_adherence:.0%} - schedule may be too aggressive")

        return recs

    def aggregate_replications(self, results: List) -> Dict[str, KPISummary]:
        """
        Aggregate statistics across multiple replications.

        Args:
            results: List of SimResult from multiple runs

        Returns:
            Dict of KPI name -> KPISummary
        """
        import numpy as np

        if not results:
            return {}

        # Extract KPIs from all results
        makespans = [r.actual_makespan_mins for r in results]
        tardiness = [r.total_tardiness_mins for r in results]
        utilizations = [
            sum(r.machine_utilization.values()) / len(r.machine_utilization)
            for r in results if r.machine_utilization
        ]
        breakdowns = [r.total_breakdowns for r in results]
        defects = [r.total_defects for r in results]
        adherence = [r.schedule_adherence for r in results]

        kpis = {
            'makespan': makespans,
            'tardiness': tardiness,
            'utilization': utilizations,
            'breakdowns': breakdowns,
            'defects': defects,
            'schedule_adherence': adherence,
        }

        summaries = {}
        for name, values in kpis.items():
            if not values:
                continue

            arr = np.array(values)
            n = len(arr)

            # 95% CI using t-distribution
            from scipy import stats as scipy_stats
            if n > 1:
                ci = scipy_stats.t.interval(0.95, n-1, loc=np.mean(arr), scale=scipy_stats.sem(arr))
            else:
                ci = (arr[0], arr[0])

            summaries[name] = KPISummary(
                mean=float(np.mean(arr)),
                std=float(np.std(arr, ddof=1)) if n > 1 else 0.0,
                min=float(np.min(arr)),
                max=float(np.max(arr)),
                ci95_lower=float(ci[0]),
                ci95_upper=float(ci[1]),
            )

        return summaries

    def format_comparison_table(
        self,
        algorithm_results: Dict[str, Dict[str, KPISummary]]
    ) -> Dict[str, Any]:
        """
        Format algorithm comparison as table.

        Args:
            algorithm_results: Dict of algorithm name -> KPI summaries

        Returns:
            Formatted table dict
        """
        rows = []
        kpi_names = ['makespan', 'tardiness', 'utilization', 'schedule_adherence']

        for algo, summaries in algorithm_results.items():
            row = {'algorithm': algo}
            for kpi in kpi_names:
                if kpi in summaries:
                    s = summaries[kpi]
                    row[kpi] = f"{s.mean:.1f} ({s.ci95_lower:.1f}-{s.ci95_upper:.1f})"
                    row[f"{kpi}_mean"] = s.mean
                    row[f"{kpi}_ci"] = (s.ci95_lower, s.ci95_upper)
            rows.append(row)

        return {
            'headers': ['algorithm'] + kpi_names,
            'rows': rows,
        }
