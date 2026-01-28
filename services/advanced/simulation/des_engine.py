"""
Discrete Event Simulation Engine

LegoMCP World-Class Manufacturing System v5.0
Phase 18: Discrete Event Simulation (DES)

Full factory simulation for:
- Capacity planning
- What-if scenarios
- Schedule validation
- Bottleneck analysis
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4
import heapq
import random

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Simulation event types."""
    JOB_ARRIVAL = "job_arrival"
    JOB_START = "job_start"
    JOB_COMPLETE = "job_complete"
    MACHINE_DOWN = "machine_down"
    MACHINE_UP = "machine_up"
    SHIFT_START = "shift_start"
    SHIFT_END = "shift_end"


@dataclass
class SimEvent:
    """A simulation event."""
    time: float  # Simulation time
    event_type: EventType
    entity_id: str
    data: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other):
        return self.time < other.time


@dataclass
class SimJob:
    """A job in the simulation."""
    job_id: str
    part_id: str
    quantity: int
    priority: int = 1
    due_date: Optional[float] = None

    # Timing
    arrival_time: float = 0.0
    start_time: Optional[float] = None
    completion_time: Optional[float] = None

    # Processing
    processing_time: float = 60.0  # Minutes
    setup_time: float = 10.0
    assigned_machine: Optional[str] = None

    # Status
    is_complete: bool = False
    is_late: bool = False
    wait_time: float = 0.0
    flow_time: float = 0.0

    def complete(self, time: float) -> None:
        """Mark job as complete."""
        self.completion_time = time
        self.is_complete = True
        if self.start_time:
            self.flow_time = time - self.arrival_time
            self.wait_time = self.start_time - self.arrival_time
        if self.due_date and time > self.due_date:
            self.is_late = True


@dataclass
class SimMachine:
    """A machine in the simulation."""
    machine_id: str
    name: str
    capacity_per_hour: float = 10.0

    # State
    is_available: bool = True
    is_down: bool = False
    current_job: Optional[str] = None

    # Reliability
    mtbf_hours: float = 100.0  # Mean time between failures
    mttr_hours: float = 2.0  # Mean time to repair

    # Statistics
    busy_time: float = 0.0
    idle_time: float = 0.0
    downtime: float = 0.0
    jobs_completed: int = 0

    def utilization(self, total_time: float) -> float:
        """Calculate utilization percentage."""
        if total_time <= 0:
            return 0.0
        return (self.busy_time / total_time) * 100


@dataclass
class SimulationResults:
    """Results from a simulation run."""
    simulation_id: str
    scenario_name: str
    duration_simulated: float  # Minutes

    # Job metrics
    total_jobs: int = 0
    completed_jobs: int = 0
    late_jobs: int = 0
    avg_flow_time: float = 0.0
    avg_wait_time: float = 0.0
    max_wait_time: float = 0.0

    # Machine metrics
    machine_utilization: Dict[str, float] = field(default_factory=dict)
    avg_utilization: float = 0.0
    bottleneck_machine: Optional[str] = None

    # Throughput
    throughput_per_hour: float = 0.0
    makespan: float = 0.0

    # Quality (if simulated)
    simulated_defect_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'simulation_id': self.simulation_id,
            'scenario_name': self.scenario_name,
            'duration_simulated': self.duration_simulated,
            'total_jobs': self.total_jobs,
            'completed_jobs': self.completed_jobs,
            'late_jobs': self.late_jobs,
            'late_percent': (self.late_jobs / self.total_jobs * 100) if self.total_jobs > 0 else 0,
            'avg_flow_time': self.avg_flow_time,
            'avg_wait_time': self.avg_wait_time,
            'machine_utilization': self.machine_utilization,
            'avg_utilization': self.avg_utilization,
            'bottleneck_machine': self.bottleneck_machine,
            'throughput_per_hour': self.throughput_per_hour,
            'makespan': self.makespan,
        }


class DESEngine:
    """
    Discrete Event Simulation Engine.

    Simulates factory operations for planning and analysis.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # Simulation state
        self._current_time: float = 0.0
        self._event_queue: List[SimEvent] = []
        self._machines: Dict[str, SimMachine] = {}
        self._jobs: Dict[str, SimJob] = {}
        self._completed_jobs: List[SimJob] = []

        # Queues
        self._job_queue: List[str] = []

        # Random seed
        self._seed = config.get('seed', 42) if config else 42
        random.seed(self._seed)

    def add_machine(self, machine: SimMachine) -> None:
        """Add a machine to the simulation."""
        self._machines[machine.machine_id] = machine

    def schedule_event(self, event: SimEvent) -> None:
        """Schedule an event."""
        heapq.heappush(self._event_queue, event)

    def schedule_job_arrival(
        self,
        job_id: str,
        part_id: str,
        quantity: int,
        arrival_time: float,
        processing_time: float,
        due_date: Optional[float] = None,
    ) -> None:
        """Schedule a job arrival."""
        job = SimJob(
            job_id=job_id,
            part_id=part_id,
            quantity=quantity,
            arrival_time=arrival_time,
            processing_time=processing_time,
            due_date=due_date,
        )
        self._jobs[job_id] = job

        self.schedule_event(SimEvent(
            time=arrival_time,
            event_type=EventType.JOB_ARRIVAL,
            entity_id=job_id,
        ))

    def run(
        self,
        duration: float,
        scenario_name: str = "default",
    ) -> SimulationResults:
        """
        Run the simulation.

        Args:
            duration: Simulation duration in minutes
            scenario_name: Name of scenario

        Returns:
            SimulationResults
        """
        self._current_time = 0.0
        end_time = duration

        logger.info(f"Starting simulation: {scenario_name}, duration={duration} min")

        while self._event_queue and self._current_time < end_time:
            event = heapq.heappop(self._event_queue)
            self._current_time = event.time

            if self._current_time > end_time:
                break

            self._process_event(event)

        # Calculate results
        results = self._calculate_results(scenario_name, duration)

        logger.info(
            f"Simulation complete: {results.completed_jobs} jobs, "
            f"avg utilization={results.avg_utilization:.1f}%"
        )

        return results

    def _process_event(self, event: SimEvent) -> None:
        """Process a simulation event."""
        if event.event_type == EventType.JOB_ARRIVAL:
            self._handle_job_arrival(event)
        elif event.event_type == EventType.JOB_START:
            self._handle_job_start(event)
        elif event.event_type == EventType.JOB_COMPLETE:
            self._handle_job_complete(event)
        elif event.event_type == EventType.MACHINE_DOWN:
            self._handle_machine_down(event)
        elif event.event_type == EventType.MACHINE_UP:
            self._handle_machine_up(event)

    def _handle_job_arrival(self, event: SimEvent) -> None:
        """Handle job arrival."""
        job_id = event.entity_id
        self._job_queue.append(job_id)
        self._try_start_job()

    def _handle_job_start(self, event: SimEvent) -> None:
        """Handle job start."""
        job_id = event.entity_id
        job = self._jobs.get(job_id)
        machine_id = event.data.get('machine_id')
        machine = self._machines.get(machine_id)

        if not job or not machine:
            return

        job.start_time = self._current_time
        job.assigned_machine = machine_id
        machine.current_job = job_id
        machine.is_available = False

        # Schedule completion
        completion_time = self._current_time + job.setup_time + job.processing_time

        self.schedule_event(SimEvent(
            time=completion_time,
            event_type=EventType.JOB_COMPLETE,
            entity_id=job_id,
            data={'machine_id': machine_id},
        ))

    def _handle_job_complete(self, event: SimEvent) -> None:
        """Handle job completion."""
        job_id = event.entity_id
        job = self._jobs.get(job_id)
        machine_id = event.data.get('machine_id')
        machine = self._machines.get(machine_id)

        if not job or not machine:
            return

        job.complete(self._current_time)
        self._completed_jobs.append(job)

        # Update machine stats
        machine.current_job = None
        machine.is_available = True
        machine.jobs_completed += 1
        machine.busy_time += job.setup_time + job.processing_time

        # Try to start next job
        self._try_start_job()

    def _handle_machine_down(self, event: SimEvent) -> None:
        """Handle machine breakdown."""
        machine_id = event.entity_id
        machine = self._machines.get(machine_id)

        if not machine:
            return

        machine.is_down = True
        machine.is_available = False

        # Schedule repair
        repair_time = random.expovariate(1 / (machine.mttr_hours * 60))
        self.schedule_event(SimEvent(
            time=self._current_time + repair_time,
            event_type=EventType.MACHINE_UP,
            entity_id=machine_id,
        ))

    def _handle_machine_up(self, event: SimEvent) -> None:
        """Handle machine repair complete."""
        machine_id = event.entity_id
        machine = self._machines.get(machine_id)

        if not machine:
            return

        machine.is_down = False
        if not machine.current_job:
            machine.is_available = True

        self._try_start_job()

    def _try_start_job(self) -> None:
        """Try to start a job from the queue."""
        if not self._job_queue:
            return

        # Find available machine
        available_machine = None
        for machine in self._machines.values():
            if machine.is_available and not machine.is_down:
                available_machine = machine
                break

        if not available_machine:
            return

        job_id = self._job_queue.pop(0)

        self.schedule_event(SimEvent(
            time=self._current_time,
            event_type=EventType.JOB_START,
            entity_id=job_id,
            data={'machine_id': available_machine.machine_id},
        ))

    def _calculate_results(
        self,
        scenario_name: str,
        duration: float,
    ) -> SimulationResults:
        """Calculate simulation results."""
        results = SimulationResults(
            simulation_id=str(uuid4()),
            scenario_name=scenario_name,
            duration_simulated=duration,
            total_jobs=len(self._jobs),
            completed_jobs=len(self._completed_jobs),
        )

        if self._completed_jobs:
            results.late_jobs = sum(1 for j in self._completed_jobs if j.is_late)
            results.avg_flow_time = sum(j.flow_time for j in self._completed_jobs) / len(self._completed_jobs)
            results.avg_wait_time = sum(j.wait_time for j in self._completed_jobs) / len(self._completed_jobs)
            results.max_wait_time = max(j.wait_time for j in self._completed_jobs)

            completion_times = [j.completion_time for j in self._completed_jobs if j.completion_time]
            if completion_times:
                results.makespan = max(completion_times)

            results.throughput_per_hour = len(self._completed_jobs) / (duration / 60)

        # Machine utilization
        max_util = 0.0
        bottleneck = None

        for machine_id, machine in self._machines.items():
            util = machine.utilization(duration)
            results.machine_utilization[machine_id] = util
            if util > max_util:
                max_util = util
                bottleneck = machine_id

        if results.machine_utilization:
            results.avg_utilization = sum(results.machine_utilization.values()) / len(results.machine_utilization)
        results.bottleneck_machine = bottleneck

        return results

    def reset(self) -> None:
        """Reset simulation state."""
        self._current_time = 0.0
        self._event_queue = []
        self._jobs = {}
        self._completed_jobs = []
        self._job_queue = []

        for machine in self._machines.values():
            machine.is_available = True
            machine.is_down = False
            machine.current_job = None
            machine.busy_time = 0.0
            machine.idle_time = 0.0
            machine.downtime = 0.0
            machine.jobs_completed = 0

    def what_if(
        self,
        base_jobs: List[Dict[str, Any]],
        scenarios: List[Dict[str, Any]],
        duration: float,
    ) -> List[SimulationResults]:
        """
        Run what-if scenario analysis.

        Args:
            base_jobs: Base job list
            scenarios: List of scenario modifications
            duration: Simulation duration

        Returns:
            Results for each scenario
        """
        results = []

        for scenario in scenarios:
            self.reset()

            # Apply scenario modifications
            # (Add machines, modify processing times, etc.)

            for i, job_spec in enumerate(base_jobs):
                self.schedule_job_arrival(
                    job_id=f"job_{i}",
                    part_id=job_spec.get('part_id', 'part'),
                    quantity=job_spec.get('quantity', 1),
                    arrival_time=job_spec.get('arrival_time', i * 10),
                    processing_time=job_spec.get('processing_time', 30),
                )

            result = self.run(duration, scenario.get('name', 'unnamed'))
            results.append(result)

        return results
