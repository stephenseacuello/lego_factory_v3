"""
Scheduling Objectives - Multi-Objective Optimization

LegoMCP World-Class Manufacturing System v5.0
Phase 12: Advanced Scheduling Algorithms

Defines scheduling objectives for multi-objective optimization:
- Makespan (total schedule duration)
- Tardiness (late delivery penalties)
- Energy consumption
- Quality risk (from FMEA)
- Cost and margin
- Utilization
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import math


class ObjectiveDirection(str, Enum):
    """Optimization direction for objectives."""
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class SchedulingObjective(str, Enum):
    """Standard scheduling objectives."""
    MAKESPAN = "makespan"                   # Total schedule duration
    TOTAL_TARDINESS = "total_tardiness"     # Sum of late deliveries
    MAX_TARDINESS = "max_tardiness"         # Maximum lateness
    WEIGHTED_TARDINESS = "weighted_tardiness"  # Priority-weighted tardiness
    TOTAL_FLOWTIME = "total_flowtime"       # Sum of completion times
    ENERGY = "energy"                       # Total energy consumption
    QUALITY_RISK = "quality_risk"           # FMEA-based risk score
    COST = "cost"                           # Total production cost
    MARGIN = "margin"                       # Total profit margin
    UTILIZATION = "utilization"             # Machine utilization
    SETUP_TIME = "setup_time"               # Total setup time
    WIP = "wip"                             # Work in process
    CARBON = "carbon"                       # Carbon footprint


@dataclass
class ObjectiveWeight:
    """Weight configuration for an objective."""
    objective: SchedulingObjective
    weight: float = 1.0
    direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE
    target: Optional[float] = None  # Target value for goal programming
    penalty_factor: float = 1.0     # Penalty for constraint violations


@dataclass
class ObjectiveSet:
    """
    Set of objective values for a schedule solution.

    Used for Pareto-based multi-objective optimization
    and solution comparison.
    """
    makespan: float = 0.0
    total_tardiness: float = 0.0
    max_tardiness: float = 0.0
    weighted_tardiness: float = 0.0
    total_flowtime: float = 0.0
    energy_kwh: float = 0.0
    quality_risk: float = 0.0
    total_cost: float = 0.0
    total_margin: float = 0.0
    avg_utilization: float = 0.0
    total_setup_time: float = 0.0
    avg_wip: float = 0.0
    carbon_kg: float = 0.0

    # Computed metrics
    on_time_percentage: float = 0.0
    jobs_on_time: int = 0
    jobs_late: int = 0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'makespan': self.makespan,
            'total_tardiness': self.total_tardiness,
            'max_tardiness': self.max_tardiness,
            'weighted_tardiness': self.weighted_tardiness,
            'total_flowtime': self.total_flowtime,
            'energy_kwh': self.energy_kwh,
            'quality_risk': self.quality_risk,
            'total_cost': self.total_cost,
            'total_margin': self.total_margin,
            'avg_utilization': self.avg_utilization,
            'total_setup_time': self.total_setup_time,
            'avg_wip': self.avg_wip,
            'carbon_kg': self.carbon_kg,
            'on_time_percentage': self.on_time_percentage,
            'jobs_on_time': self.jobs_on_time,
            'jobs_late': self.jobs_late,
        }

    def get_value(self, objective: SchedulingObjective) -> float:
        """Get value for a specific objective."""
        mapping = {
            SchedulingObjective.MAKESPAN: self.makespan,
            SchedulingObjective.TOTAL_TARDINESS: self.total_tardiness,
            SchedulingObjective.MAX_TARDINESS: self.max_tardiness,
            SchedulingObjective.WEIGHTED_TARDINESS: self.weighted_tardiness,
            SchedulingObjective.TOTAL_FLOWTIME: self.total_flowtime,
            SchedulingObjective.ENERGY: self.energy_kwh,
            SchedulingObjective.QUALITY_RISK: self.quality_risk,
            SchedulingObjective.COST: self.total_cost,
            SchedulingObjective.MARGIN: self.total_margin,
            SchedulingObjective.UTILIZATION: self.avg_utilization,
            SchedulingObjective.SETUP_TIME: self.total_setup_time,
            SchedulingObjective.WIP: self.avg_wip,
            SchedulingObjective.CARBON: self.carbon_kg,
        }
        return mapping.get(objective, 0.0)

    def weighted_sum(self, weights: List[ObjectiveWeight]) -> float:
        """Calculate weighted sum of objectives."""
        total = 0.0
        for w in weights:
            value = self.get_value(w.objective)
            if w.direction == ObjectiveDirection.MAXIMIZE:
                value = -value  # Negate for maximization
            total += w.weight * value
        return total

    def dominates(self, other: 'ObjectiveSet', objectives: List[SchedulingObjective]) -> bool:
        """
        Check if this solution dominates another (Pareto dominance).

        A solution dominates if it's at least as good on all objectives
        and strictly better on at least one.
        """
        dominated = False
        at_least_as_good = True

        for obj in objectives:
            self_val = self.get_value(obj)
            other_val = other.get_value(obj)

            if self_val > other_val:  # Assuming minimization
                at_least_as_good = False
            elif self_val < other_val:
                dominated = True

        return at_least_as_good and dominated

    def distance_to_ideal(
        self,
        ideal: 'ObjectiveSet',
        objectives: List[SchedulingObjective],
        normalize: bool = True
    ) -> float:
        """Calculate Euclidean distance to ideal point."""
        distance = 0.0
        for obj in objectives:
            self_val = self.get_value(obj)
            ideal_val = ideal.get_value(obj)
            diff = self_val - ideal_val
            if normalize and ideal_val != 0:
                diff = diff / abs(ideal_val)
            distance += diff ** 2
        return math.sqrt(distance)


class ObjectiveCalculator:
    """
    Calculate objective values from a schedule.

    Provides methods to evaluate schedule quality
    across all objectives.
    """

    def __init__(
        self,
        energy_rate_kwh: float = 0.15,  # $/kWh
        carbon_rate_kg_per_kwh: float = 0.4,  # kg CO2/kWh
    ):
        self.energy_rate = energy_rate_kwh
        self.carbon_rate = carbon_rate_kg_per_kwh

    def calculate_makespan(
        self,
        operations: List[Dict[str, Any]]
    ) -> float:
        """Calculate schedule makespan (total duration)."""
        if not operations:
            return 0.0
        return max(op.get('end_time', 0) for op in operations)

    def calculate_tardiness(
        self,
        jobs: List[Dict[str, Any]],
        operations: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate tardiness metrics for jobs."""
        total = 0.0
        max_tard = 0.0
        weighted = 0.0
        on_time = 0
        late = 0

        for job in jobs:
            job_id = job.get('id')
            due_date = job.get('due_date', float('inf'))
            priority = job.get('priority', 1)

            # Find completion time
            job_ops = [op for op in operations if op.get('job_id') == job_id]
            if job_ops:
                completion = max(op.get('end_time', 0) for op in job_ops)
                tardiness = max(0, completion - due_date)

                total += tardiness
                max_tard = max(max_tard, tardiness)
                weighted += priority * tardiness

                if tardiness > 0:
                    late += 1
                else:
                    on_time += 1

        total_jobs = len(jobs)
        return {
            'total_tardiness': total,
            'max_tardiness': max_tard,
            'weighted_tardiness': weighted,
            'jobs_on_time': on_time,
            'jobs_late': late,
            'on_time_percentage': (on_time / total_jobs * 100) if total_jobs > 0 else 100.0
        }

    def calculate_energy(
        self,
        operations: List[Dict[str, Any]],
        machines: Dict[str, Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate energy consumption."""
        total_energy = 0.0

        for op in operations:
            machine_id = op.get('machine_id')
            duration = op.get('end_time', 0) - op.get('start_time', 0)

            if machine_id in machines:
                power_kw = machines[machine_id].get('power_kw', 1.0)
                energy_kwh = power_kw * (duration / 60)  # Assuming duration in minutes
                total_energy += energy_kwh

        return {
            'energy_kwh': total_energy,
            'energy_cost': total_energy * self.energy_rate,
            'carbon_kg': total_energy * self.carbon_rate
        }

    def calculate_utilization(
        self,
        operations: List[Dict[str, Any]],
        machines: Dict[str, Dict[str, Any]],
        makespan: float
    ) -> Dict[str, float]:
        """Calculate machine utilization."""
        if makespan == 0:
            return {'avg_utilization': 0.0, 'machine_utilization': {}}

        machine_busy = {m: 0.0 for m in machines}

        for op in operations:
            machine_id = op.get('machine_id')
            if machine_id in machine_busy:
                duration = op.get('end_time', 0) - op.get('start_time', 0)
                machine_busy[machine_id] += duration

        utilizations = {
            m: (busy / makespan * 100) for m, busy in machine_busy.items()
        }

        avg_util = sum(utilizations.values()) / len(utilizations) if utilizations else 0.0

        return {
            'avg_utilization': avg_util,
            'machine_utilization': utilizations
        }

    def calculate_full_objectives(
        self,
        jobs: List[Dict[str, Any]],
        operations: List[Dict[str, Any]],
        machines: Dict[str, Dict[str, Any]]
    ) -> ObjectiveSet:
        """Calculate all objectives for a schedule."""
        makespan = self.calculate_makespan(operations)
        tardiness = self.calculate_tardiness(jobs, operations)
        energy = self.calculate_energy(operations, machines)
        utilization = self.calculate_utilization(operations, machines, makespan)

        # Calculate cost and margin
        total_cost = sum(op.get('cost', 0) for op in operations) + energy['energy_cost']
        total_revenue = sum(job.get('revenue', 0) for job in jobs)
        total_margin = total_revenue - total_cost

        # Calculate flowtime
        total_flowtime = 0.0
        for job in jobs:
            job_id = job.get('id')
            job_ops = [op for op in operations if op.get('job_id') == job_id]
            if job_ops:
                release = min(op.get('start_time', 0) for op in job_ops)
                completion = max(op.get('end_time', 0) for op in job_ops)
                total_flowtime += completion - release

        return ObjectiveSet(
            makespan=makespan,
            total_tardiness=tardiness['total_tardiness'],
            max_tardiness=tardiness['max_tardiness'],
            weighted_tardiness=tardiness['weighted_tardiness'],
            total_flowtime=total_flowtime,
            energy_kwh=energy['energy_kwh'],
            carbon_kg=energy['carbon_kg'],
            total_cost=total_cost,
            total_margin=total_margin,
            avg_utilization=utilization['avg_utilization'],
            on_time_percentage=tardiness['on_time_percentage'],
            jobs_on_time=tardiness['jobs_on_time'],
            jobs_late=tardiness['jobs_late'],
        )
