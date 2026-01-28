"""
Unified Scheduler for Flask CNC SCADA
=====================================
Single interface to all 9 scheduling algorithms.

Algorithms:
- FIFO, EDD, SPT, CR (via scheduler_service)
- WSPT, SETUP_MIN (new implementations)
- GENETIC, SA (metaheuristics)
- ORTOOLS (CP-SAT solver)

Usage:
    from services.scheduling.unified_scheduler import get_unified_scheduler

    scheduler = get_unified_scheduler()
    response = scheduler.schedule(request)
"""

import logging
import time
import random
import math
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import copy

from config import get_config
from services.scheduling.algorithm_registry import get_algorithm_registry, AlgorithmCategory

logger = logging.getLogger(__name__)
config = get_config()


class SchedulingAlgorithm(Enum):
    """Available scheduling algorithms."""
    FIFO = "FIFO"
    EDD = "EDD"
    SPT = "SPT"
    CR = "CR"
    WSPT = "WSPT"
    SETUP_MIN = "SETUP_MIN"
    GENETIC = "GENETIC"
    SA = "SA"
    ORTOOLS = "ORTOOLS"


@dataclass
class ScheduleResource:
    """Resource constraint (tools, operators, materials)."""
    id: str
    name: str
    resource_type: str  # "tool", "operator", "material"
    capacity: int = 1  # Available quantity
    available_from: int = 0
    available_until: int = 480


@dataclass
class ScheduleJob:
    """Job to be scheduled."""
    id: str
    name: str
    processing_time: int  # Total processing time in minutes
    due_date: Optional[int] = None  # Minutes from schedule start
    priority: int = 5  # 1-10, lower = higher priority
    release_date: int = 0  # Earliest start time
    setup_group: Optional[str] = None  # For setup minimization
    weight: Optional[float] = None  # Custom weight for WSPT
    machine_id: Optional[str] = None  # Preferred/required machine
    operations: List[Dict] = field(default_factory=list)
    # NEW: Dependencies and resources
    dependencies: List[str] = field(default_factory=list)  # Job IDs that must complete first
    required_resources: List[str] = field(default_factory=list)  # Resource IDs needed
    estimated_scrap_rate: float = 0.0  # Expected scrap percentage (0-1)


@dataclass
class ScheduleMachine:
    """Machine resource."""
    id: str
    name: str
    available_from: int = 0
    available_until: int = 480  # 8 hour shift default


@dataclass
class ScheduleRequest:
    """Request for scheduling."""
    jobs: List[ScheduleJob]
    machines: List[ScheduleMachine]
    algorithm: SchedulingAlgorithm = SchedulingAlgorithm.EDD
    parameters: Dict[str, Any] = field(default_factory=dict)
    objective: str = "makespan"  # makespan, tardiness, weighted_tardiness
    resources: List[ScheduleResource] = field(default_factory=list)  # Additional resources


@dataclass
class ScheduledJob:
    """A scheduled job result."""
    job_id: str
    job_name: str
    machine_id: str
    start_time: int
    end_time: int
    processing_time: int
    setup_time: int = 0
    tardiness: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "machine_id": self.machine_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "processing_time": self.processing_time,
            "setup_time": self.setup_time,
            "tardiness": self.tardiness,
        }


@dataclass
class ScheduleResponse:
    """Response from scheduling."""
    success: bool
    algorithm: str
    scheduled_jobs: List[ScheduledJob] = field(default_factory=list)
    makespan: int = 0
    total_tardiness: int = 0
    total_flow_time: int = 0
    utilization: float = 0.0
    solve_time_ms: float = 0.0
    status: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "algorithm": self.algorithm,
            "scheduled_jobs": [j.to_dict() for j in self.scheduled_jobs],
            "metrics": {
                "makespan": self.makespan,
                "makespan_hours": round(self.makespan / 60, 2),
                "total_tardiness": self.total_tardiness,
                "total_flow_time": self.total_flow_time,
                "utilization": round(self.utilization * 100, 1),
            },
            "solve_time_ms": round(self.solve_time_ms, 2),
            "status": self.status,
            "error": self.error,
        }

    def to_gantt_data(self, start_datetime: Optional[datetime] = None) -> List[Dict]:
        """Convert to Gantt chart format."""
        from datetime import timedelta
        if start_datetime is None:
            start_datetime = datetime.now().replace(hour=6, minute=0, second=0)

        gantt = []
        for job in self.scheduled_jobs:
            gantt.append({
                "Task": job.job_name,
                "Resource": job.machine_id,
                "Start": (start_datetime + timedelta(minutes=job.start_time)).isoformat(),
                "End": (start_datetime + timedelta(minutes=job.end_time)).isoformat(),
                "Duration": job.processing_time,
            })
        return gantt


class UnifiedScheduler:
    """
    Unified scheduler supporting all 9 algorithms.

    Provides a single interface to:
    - Dispatching rules (FIFO, EDD, SPT, CR, WSPT, SETUP_MIN)
    - Metaheuristics (GENETIC, SA)
    - Optimization (ORTOOLS)
    """

    def __init__(self):
        """Initialize unified scheduler."""
        self._registry = get_algorithm_registry()
        self._scheduler_service = None  # Lazy load existing scheduler

        logger.info("UnifiedScheduler initialized")

    @property
    def scheduler_service(self):
        """Get existing scheduler service for OR-Tools."""
        if self._scheduler_service is None:
            from services.scheduler_service import get_scheduler_service
            self._scheduler_service = get_scheduler_service()
        return self._scheduler_service

    def schedule(self, request: ScheduleRequest) -> ScheduleResponse:
        """
        Execute scheduling with the specified algorithm.

        Args:
            request: ScheduleRequest with jobs, machines, and algorithm

        Returns:
            ScheduleResponse with results
        """
        start_time = time.time()

        try:
            # Route to appropriate algorithm
            if request.algorithm == SchedulingAlgorithm.FIFO:
                response = self._schedule_fifo(request)
            elif request.algorithm == SchedulingAlgorithm.EDD:
                response = self._schedule_edd(request)
            elif request.algorithm == SchedulingAlgorithm.SPT:
                response = self._schedule_spt(request)
            elif request.algorithm == SchedulingAlgorithm.CR:
                response = self._schedule_cr(request)
            elif request.algorithm == SchedulingAlgorithm.WSPT:
                response = self._schedule_wspt(request)
            elif request.algorithm == SchedulingAlgorithm.SETUP_MIN:
                response = self._schedule_setup_min(request)
            elif request.algorithm == SchedulingAlgorithm.GENETIC:
                response = self._schedule_genetic(request)
            elif request.algorithm == SchedulingAlgorithm.SA:
                response = self._schedule_sa(request)
            elif request.algorithm == SchedulingAlgorithm.ORTOOLS:
                response = self._schedule_ortools(request)
            else:
                return ScheduleResponse(
                    success=False,
                    algorithm=request.algorithm.value,
                    error=f"Unknown algorithm: {request.algorithm}",
                )

            response.solve_time_ms = (time.time() - start_time) * 1000
            return response

        except Exception as e:
            logger.error(f"Scheduling error: {e}")
            return ScheduleResponse(
                success=False,
                algorithm=request.algorithm.value,
                solve_time_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    def compare_algorithms(
        self,
        request: ScheduleRequest,
        algorithms: Optional[List[SchedulingAlgorithm]] = None,
    ) -> Dict[str, ScheduleResponse]:
        """
        Compare multiple algorithms on the same problem.

        Args:
            request: Base scheduling request
            algorithms: Algorithms to compare (all if None)

        Returns:
            Dict mapping algorithm name to response
        """
        if algorithms is None:
            algorithms = list(SchedulingAlgorithm)

        results = {}
        for algo in algorithms:
            req = ScheduleRequest(
                jobs=request.jobs,
                machines=request.machines,
                algorithm=algo,
                parameters=request.parameters,
                objective=request.objective,
            )
            results[algo.value] = self.schedule(req)

        return results

    # =========================================================================
    # Dispatching Rules
    # =========================================================================

    def _schedule_fifo(self, request: ScheduleRequest) -> ScheduleResponse:
        """First In First Out scheduling."""
        return self._apply_dispatching_rule(
            request,
            sort_key=lambda j: 0,  # Keep original order
            algorithm_name="FIFO",
        )

    def _schedule_edd(self, request: ScheduleRequest) -> ScheduleResponse:
        """Earliest Due Date scheduling."""
        return self._apply_dispatching_rule(
            request,
            sort_key=lambda j: j.due_date if j.due_date else float('inf'),
            algorithm_name="EDD",
        )

    def _schedule_spt(self, request: ScheduleRequest) -> ScheduleResponse:
        """Shortest Processing Time scheduling."""
        return self._apply_dispatching_rule(
            request,
            sort_key=lambda j: j.processing_time,
            algorithm_name="SPT",
        )

    def _schedule_cr(self, request: ScheduleRequest) -> ScheduleResponse:
        """Critical Ratio scheduling."""
        def critical_ratio(job):
            if not job.due_date:
                return float('inf')
            time_remaining = max(1, job.due_date)
            work_remaining = max(1, job.processing_time)
            return time_remaining / work_remaining

        return self._apply_dispatching_rule(
            request,
            sort_key=critical_ratio,
            algorithm_name="CR",
        )

    def _schedule_wspt(self, request: ScheduleRequest) -> ScheduleResponse:
        """Weighted Shortest Processing Time scheduling."""
        def wspt_ratio(job):
            # Weight from priority (higher priority = higher weight)
            weight = job.weight if job.weight else (11 - job.priority)
            processing = max(1, job.processing_time)
            return -weight / processing  # Negative for descending order

        return self._apply_dispatching_rule(
            request,
            sort_key=wspt_ratio,
            algorithm_name="WSPT",
        )

    def _schedule_setup_min(self, request: ScheduleRequest) -> ScheduleResponse:
        """Setup Time Minimization scheduling."""
        # Group jobs by setup_group and schedule groups together
        groups = defaultdict(list)
        for job in request.jobs:
            group = job.setup_group or job.id  # Default to job ID if no group
            groups[group].append(job)

        # Sort within groups by processing time
        sorted_jobs = []
        for group_jobs in groups.values():
            group_jobs.sort(key=lambda j: j.processing_time)
            sorted_jobs.extend(group_jobs)

        # Create new request with sorted jobs
        sorted_request = ScheduleRequest(
            jobs=[ScheduleJob(**{k: getattr(j, k) for k in ['id', 'name', 'processing_time', 'due_date', 'priority', 'release_date', 'setup_group', 'weight', 'machine_id', 'operations']}) for j in sorted_jobs],
            machines=request.machines,
            algorithm=request.algorithm,
        )

        return self._apply_dispatching_rule(
            sorted_request,
            sort_key=lambda j: 0,  # Already sorted
            algorithm_name="SETUP_MIN",
        )

    def _apply_dispatching_rule(
        self,
        request: ScheduleRequest,
        sort_key,
        algorithm_name: str,
    ) -> ScheduleResponse:
        """Apply a dispatching rule to schedule jobs with dependency support."""
        # Build dependency graph
        job_map = {j.id: j for j in request.jobs}
        job_end_times: Dict[str, int] = {}  # Track when each job completes

        # Topological sort respecting dependencies
        sorted_jobs = self._topological_sort_with_priority(request.jobs, sort_key)

        # Resource tracking
        resources = {r.id: r for r in request.resources}
        resource_usage: Dict[str, List[Tuple[int, int]]] = defaultdict(list)  # [(start, end), ...]

        # Simple single-machine or multi-machine assignment
        machines = {m.id: m for m in request.machines}
        machine_times = {m.id: m.available_from for m in request.machines}

        scheduled = []
        total_flow_time = 0
        total_tardiness = 0

        for job in sorted_jobs:
            # Calculate earliest start based on dependencies
            dep_end_time = 0
            for dep_id in job.dependencies:
                if dep_id in job_end_times:
                    dep_end_time = max(dep_end_time, job_end_times[dep_id])

            # Find best machine (earliest available)
            machine_id = job.machine_id
            if not machine_id or machine_id not in machines:
                machine_id = min(machine_times, key=machine_times.get)

            # Start time considers: machine availability, release date, and dependencies
            start = max(machine_times[machine_id], job.release_date, dep_end_time)

            # Check resource availability
            for res_id in job.required_resources:
                if res_id in resources:
                    res = resources[res_id]
                    # Find earliest slot where resource is free
                    start = self._find_resource_slot(
                        resource_usage[res_id],
                        start,
                        job.processing_time,
                        res.capacity
                    )

            end = start + job.processing_time

            # Track resource usage
            for res_id in job.required_resources:
                resource_usage[res_id].append((start, end))

            # Calculate tardiness
            tardiness = 0
            if job.due_date and end > job.due_date:
                tardiness = end - job.due_date

            scheduled.append(ScheduledJob(
                job_id=job.id,
                job_name=job.name,
                machine_id=machine_id,
                start_time=start,
                end_time=end,
                processing_time=job.processing_time,
                tardiness=tardiness,
            ))

            job_end_times[job.id] = end
            machine_times[machine_id] = end
            total_flow_time += end
            total_tardiness += tardiness

        makespan = max(s.end_time for s in scheduled) if scheduled else 0

        # Calculate utilization
        total_available = sum(
            (m.available_until - m.available_from) for m in request.machines
        )
        total_processing = sum(j.processing_time for j in request.jobs)
        utilization = total_processing / total_available if total_available > 0 else 0

        return ScheduleResponse(
            success=True,
            algorithm=algorithm_name,
            scheduled_jobs=scheduled,
            makespan=makespan,
            total_tardiness=total_tardiness,
            total_flow_time=total_flow_time,
            utilization=utilization,
            status="completed",
        )

    def _topological_sort_with_priority(
        self,
        jobs: List[ScheduleJob],
        sort_key
    ) -> List[ScheduleJob]:
        """
        Topological sort that respects dependencies while using priority within levels.

        Jobs are sorted so that dependencies come before dependents,
        and within each "level" jobs are sorted by the dispatching rule.
        """
        job_map = {j.id: j for j in jobs}
        in_degree = {j.id: 0 for j in jobs}
        dependents = defaultdict(list)

        # Build graph
        for job in jobs:
            for dep_id in job.dependencies:
                if dep_id in job_map:
                    in_degree[job.id] += 1
                    dependents[dep_id].append(job.id)

        # Kahn's algorithm with priority queue
        result = []
        ready = [j for j in jobs if in_degree[j.id] == 0]

        while ready:
            # Sort ready jobs by dispatching rule
            ready.sort(key=sort_key)

            # Take the highest priority job
            job = ready.pop(0)
            result.append(job)

            # Update in-degrees
            for dep_id in dependents[job.id]:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    ready.append(job_map[dep_id])

        # Check for cycles
        if len(result) != len(jobs):
            logger.warning("Dependency cycle detected, falling back to sort_key order")
            return sorted(jobs, key=sort_key)

        return result

    def _find_resource_slot(
        self,
        usage: List[Tuple[int, int]],
        earliest_start: int,
        duration: int,
        capacity: int
    ) -> int:
        """Find earliest time slot where resource is available."""
        if capacity <= 0:
            return earliest_start

        # Sort usage by start time
        usage.sort(key=lambda x: x[0])

        # Count concurrent usage at each point
        current = earliest_start
        while True:
            # Count how many jobs use this resource at 'current'
            concurrent = sum(1 for s, e in usage if s <= current < e)
            if concurrent < capacity:
                return current
            # Find next end time after current
            next_ends = [e for s, e in usage if e > current]
            if not next_ends:
                return current
            current = min(next_ends)

    # =========================================================================
    # Metaheuristics
    # =========================================================================

    def _schedule_genetic(self, request: ScheduleRequest) -> ScheduleResponse:
        """Genetic Algorithm scheduling."""
        params = request.parameters
        population_size = params.get("population_size", 50)
        generations = params.get("generations", 100)
        mutation_rate = params.get("mutation_rate", 0.1)
        crossover_rate = params.get("crossover_rate", 0.8)

        jobs = request.jobs
        n = len(jobs)

        if n == 0:
            return ScheduleResponse(success=True, algorithm="GENETIC", status="no_jobs")

        # Initialize population (random permutations)
        population = [random.sample(range(n), n) for _ in range(population_size)]

        def fitness(chromosome):
            """Calculate fitness (lower is better - makespan)."""
            return self._evaluate_schedule(chromosome, request)

        # Evolve
        for gen in range(generations):
            # Evaluate fitness
            fitness_scores = [(chrom, fitness(chrom)) for chrom in population]
            fitness_scores.sort(key=lambda x: x[1])

            # Selection - keep top 50%
            survivors = [f[0] for f in fitness_scores[:population_size // 2]]

            # Create new population
            new_population = survivors.copy()

            while len(new_population) < population_size:
                # Select parents
                parent1, parent2 = random.sample(survivors, 2)

                # Crossover
                if random.random() < crossover_rate:
                    child = self._order_crossover(parent1, parent2)
                else:
                    child = parent1.copy()

                # Mutation
                if random.random() < mutation_rate:
                    self._swap_mutation(child)

                new_population.append(child)

            population = new_population

        # Get best solution
        best_chromosome = min(population, key=fitness)
        return self._chromosome_to_response(best_chromosome, request, "GENETIC")

    def _schedule_sa(self, request: ScheduleRequest) -> ScheduleResponse:
        """Simulated Annealing scheduling."""
        params = request.parameters
        initial_temp = params.get("initial_temp", 1000.0)
        cooling_rate = params.get("cooling_rate", 0.995)
        min_temp = params.get("min_temp", 0.1)

        jobs = request.jobs
        n = len(jobs)

        if n == 0:
            return ScheduleResponse(success=True, algorithm="SA", status="no_jobs")

        # Initial solution
        current = list(range(n))
        random.shuffle(current)
        current_cost = self._evaluate_schedule(current, request)

        best = current.copy()
        best_cost = current_cost

        temp = initial_temp

        while temp > min_temp:
            # Generate neighbor (swap two random jobs)
            neighbor = current.copy()
            i, j = random.sample(range(n), 2)
            neighbor[i], neighbor[j] = neighbor[j], neighbor[i]

            neighbor_cost = self._evaluate_schedule(neighbor, request)

            # Accept or reject
            delta = neighbor_cost - current_cost
            if delta < 0 or random.random() < math.exp(-delta / temp):
                current = neighbor
                current_cost = neighbor_cost

                if current_cost < best_cost:
                    best = current.copy()
                    best_cost = current_cost

            temp *= cooling_rate

        return self._chromosome_to_response(best, request, "SA")

    def _evaluate_schedule(self, chromosome: List[int], request: ScheduleRequest) -> float:
        """Evaluate a chromosome (job ordering) - returns makespan."""
        jobs = [request.jobs[i] for i in chromosome]
        machines = {m.id: m for m in request.machines}
        machine_times = {m.id: m.available_from for m in request.machines}

        makespan = 0
        for job in jobs:
            machine_id = job.machine_id
            if not machine_id or machine_id not in machines:
                machine_id = min(machine_times, key=machine_times.get)

            start = max(machine_times[machine_id], job.release_date)
            end = start + job.processing_time
            machine_times[machine_id] = end
            makespan = max(makespan, end)

        return makespan

    def _order_crossover(self, parent1: List[int], parent2: List[int]) -> List[int]:
        """Order crossover (OX) for permutation chromosomes."""
        n = len(parent1)
        start, end = sorted(random.sample(range(n), 2))

        child = [-1] * n
        child[start:end] = parent1[start:end]

        remaining = [x for x in parent2 if x not in child]
        pos = 0
        for i in range(n):
            if child[i] == -1:
                child[i] = remaining[pos]
                pos += 1

        return child

    def _swap_mutation(self, chromosome: List[int]):
        """In-place swap mutation."""
        n = len(chromosome)
        i, j = random.sample(range(n), 2)
        chromosome[i], chromosome[j] = chromosome[j], chromosome[i]

    def _chromosome_to_response(
        self,
        chromosome: List[int],
        request: ScheduleRequest,
        algorithm: str,
    ) -> ScheduleResponse:
        """Convert chromosome to ScheduleResponse."""
        jobs = [request.jobs[i] for i in chromosome]
        machines = {m.id: m for m in request.machines}
        machine_times = {m.id: m.available_from for m in request.machines}

        scheduled = []
        total_tardiness = 0
        total_flow_time = 0

        for job in jobs:
            machine_id = job.machine_id
            if not machine_id or machine_id not in machines:
                machine_id = min(machine_times, key=machine_times.get)

            start = max(machine_times[machine_id], job.release_date)
            end = start + job.processing_time

            tardiness = 0
            if job.due_date and end > job.due_date:
                tardiness = end - job.due_date

            scheduled.append(ScheduledJob(
                job_id=job.id,
                job_name=job.name,
                machine_id=machine_id,
                start_time=start,
                end_time=end,
                processing_time=job.processing_time,
                tardiness=tardiness,
            ))

            machine_times[machine_id] = end
            total_flow_time += end
            total_tardiness += tardiness

        makespan = max(s.end_time for s in scheduled) if scheduled else 0

        total_available = sum(
            (m.available_until - m.available_from) for m in request.machines
        )
        total_processing = sum(j.processing_time for j in request.jobs)
        utilization = total_processing / total_available if total_available > 0 else 0

        return ScheduleResponse(
            success=True,
            algorithm=algorithm,
            scheduled_jobs=scheduled,
            makespan=makespan,
            total_tardiness=total_tardiness,
            total_flow_time=total_flow_time,
            utilization=utilization,
            status="completed",
        )

    # =========================================================================
    # OR-Tools Integration
    # =========================================================================

    def _schedule_ortools(self, request: ScheduleRequest) -> ScheduleResponse:
        """Use OR-Tools CP-SAT solver via existing scheduler service."""
        try:
            from services.scheduler_service import (
                Job as SchedulerJob,
                Operation,
                Machine,
                ObjectiveType,
            )

            # Convert to scheduler service format
            scheduler_jobs = []
            for job in request.jobs:
                ops = [Operation(
                    id=f"{job.id}_op",
                    name=job.name,
                    machine_id=job.machine_id or (request.machines[0].id if request.machines else "m1"),
                    processing_time=job.processing_time,
                )]
                scheduler_jobs.append(SchedulerJob(
                    id=job.id,
                    name=job.name,
                    operations=ops,
                    priority=job.priority,
                    due_date=job.due_date,
                    release_date=job.release_date,
                ))

            machines = [Machine(
                id=m.id,
                name=m.name,
                available_from=m.available_from,
                available_until=m.available_until,
            ) for m in request.machines]

            # Map objective
            objective_map = {
                "makespan": ObjectiveType.MAKESPAN,
                "tardiness": ObjectiveType.TARDINESS,
                "weighted_tardiness": ObjectiveType.WEIGHTED_TARDINESS,
            }
            objective = objective_map.get(request.objective, ObjectiveType.MAKESPAN)

            # Run optimization
            result = self.scheduler_service.optimize_schedule(
                scheduler_jobs,
                machines,
                objective,
            )

            # Convert result
            scheduled = []
            for task in result.tasks:
                scheduled.append(ScheduledJob(
                    job_id=task.job_id,
                    job_name=task.job_name,
                    machine_id=task.machine_id,
                    start_time=task.start_time,
                    end_time=task.end_time,
                    processing_time=task.duration,
                    setup_time=task.setup_time,
                ))

            return ScheduleResponse(
                success=result.success,
                algorithm="ORTOOLS",
                scheduled_jobs=scheduled,
                makespan=result.makespan,
                solve_time_ms=result.solve_time_ms,
                status=result.status,
            )

        except Exception as e:
            logger.error(f"OR-Tools scheduling error: {e}")
            # Fallback to EDD
            return self._schedule_edd(request)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_algorithms(self) -> List[Dict[str, Any]]:
        """Get list of available algorithms with metadata."""
        return [algo.to_dict() for algo in self._registry.list_all()]

    def recommend_algorithm(
        self,
        job_count: int,
        machine_count: int,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Get algorithm recommendations for a problem."""
        recommendations = self._registry.recommend(
            job_count=job_count,
            machine_count=machine_count,
            **kwargs,
        )
        return [algo.to_dict() for algo in recommendations]


# Global scheduler instance
_unified_scheduler: Optional[UnifiedScheduler] = None


def get_unified_scheduler() -> UnifiedScheduler:
    """Get global unified scheduler instance."""
    global _unified_scheduler
    if _unified_scheduler is None:
        _unified_scheduler = UnifiedScheduler()
    return _unified_scheduler
