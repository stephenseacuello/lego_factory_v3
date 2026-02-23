"""
Factory Model - Discrete Event Simulation

LegoMCP World-Class Manufacturing System v5.0
Phase 18: DES Simulation

Provides factory simulation capabilities:
- Work center modeling
- Queue and buffer simulation
- Resource utilization analysis
- Bottleneck identification
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
import uuid
import heapq


class ResourceState(Enum):
    """States for factory resources."""
    IDLE = "idle"
    BUSY = "busy"
    BLOCKED = "blocked"
    DOWN = "down"
    SETUP = "setup"
    STARVED = "starved"


class EventType(Enum):
    """Types of simulation events."""
    ARRIVAL = "arrival"
    DEPARTURE = "departure"
    BREAKDOWN = "breakdown"
    REPAIR = "repair"
    SETUP_START = "setup_start"
    SETUP_END = "setup_end"


@dataclass(order=True)
class SimEvent:
    """A simulation event."""
    time: float
    event_type: EventType = field(compare=False)
    resource_id: str = field(compare=False)
    job_id: Optional[str] = field(compare=False, default=None)
    data: Dict = field(compare=False, default_factory=dict)


@dataclass
class WorkCenter:
    """A work center in the factory model."""
    id: str
    name: str
    capacity: int = 1
    processing_time_mean: float = 10.0  # minutes
    processing_time_std: float = 2.0
    setup_time: float = 5.0
    mtbf: float = 480.0  # Mean time between failures (minutes)
    mttr: float = 30.0   # Mean time to repair (minutes)
    state: ResourceState = ResourceState.IDLE
    queue: List[str] = field(default_factory=list)
    current_job: Optional[str] = None
    utilization: float = 0.0
    jobs_completed: int = 0


@dataclass
class Job:
    """A job flowing through the factory."""
    id: str
    part_id: str
    routing: List[str]  # Work center IDs in order
    current_step: int = 0
    arrival_time: float = 0.0
    completion_time: Optional[float] = None
    wait_times: Dict[str, float] = field(default_factory=dict)
    process_times: Dict[str, float] = field(default_factory=dict)


@dataclass
class SimulationResult:
    """Results from a factory simulation run."""
    simulation_id: str
    duration_minutes: float
    jobs_completed: int
    jobs_in_progress: int
    throughput_per_hour: float
    average_cycle_time: float
    average_wait_time: float
    resource_utilization: Dict[str, float]
    bottleneck_resource: str
    queue_statistics: Dict[str, Dict[str, float]]
    events_processed: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


class FactoryModel:
    """
    Discrete Event Simulation model of a manufacturing facility.

    Simulates job flow through work centers with queues, setups,
    breakdowns, and variable processing times.
    """

    def __init__(self):
        self.work_centers: Dict[str, WorkCenter] = {}
        self.jobs: Dict[str, Job] = {}
        self.event_queue: List[SimEvent] = []
        self.current_time: float = 0.0
        self.statistics: Dict[str, Dict] = {}
        self._setup_default_factory()

    def _setup_default_factory(self):
        """Set up a default LEGO brick manufacturing line."""
        self.work_centers = {
            'PRINT-01': WorkCenter(
                id='PRINT-01',
                name='3D Printer 1',
                capacity=1,
                processing_time_mean=45.0,
                processing_time_std=10.0,
                setup_time=5.0,
                mtbf=480.0,
                mttr=30.0,
            ),
            'PRINT-02': WorkCenter(
                id='PRINT-02',
                name='3D Printer 2',
                capacity=1,
                processing_time_mean=45.0,
                processing_time_std=10.0,
                setup_time=5.0,
                mtbf=480.0,
                mttr=30.0,
            ),
            'INSPECT-01': WorkCenter(
                id='INSPECT-01',
                name='Inspection Station',
                capacity=1,
                processing_time_mean=5.0,
                processing_time_std=1.0,
                setup_time=0.5,
                mtbf=960.0,
                mttr=15.0,
            ),
            'FINISH-01': WorkCenter(
                id='FINISH-01',
                name='Finishing Station',
                capacity=2,
                processing_time_mean=10.0,
                processing_time_std=3.0,
                setup_time=2.0,
                mtbf=720.0,
                mttr=20.0,
            ),
            'PACK-01': WorkCenter(
                id='PACK-01',
                name='Packaging',
                capacity=1,
                processing_time_mean=3.0,
                processing_time_std=0.5,
                setup_time=1.0,
                mtbf=1440.0,
                mttr=10.0,
            ),
        }

        # Initialize statistics
        for wc_id in self.work_centers:
            self.statistics[wc_id] = {
                'busy_time': 0.0,
                'idle_time': 0.0,
                'blocked_time': 0.0,
                'down_time': 0.0,
                'queue_lengths': [],
                'wait_times': [],
            }

    def add_work_center(self, work_center: WorkCenter):
        """Add a work center to the model."""
        self.work_centers[work_center.id] = work_center
        self.statistics[work_center.id] = {
            'busy_time': 0.0,
            'idle_time': 0.0,
            'blocked_time': 0.0,
            'down_time': 0.0,
            'queue_lengths': [],
            'wait_times': [],
        }

    def schedule_event(self, event: SimEvent):
        """Schedule an event in the simulation."""
        heapq.heappush(self.event_queue, event)

    def run_simulation(
        self,
        duration_minutes: float = 480.0,
        arrival_rate: float = 0.1,
        routing: Optional[List[str]] = None
    ) -> SimulationResult:
        """
        Run the factory simulation.

        Args:
            duration_minutes: Simulation duration
            arrival_rate: Job arrivals per minute
            routing: Default routing for jobs

        Returns:
            Simulation results
        """
        import random

        # Reset state
        self.current_time = 0.0
        self.event_queue = []
        self.jobs = {}

        if routing is None:
            routing = ['PRINT-01', 'INSPECT-01', 'FINISH-01', 'PACK-01']

        # Schedule initial arrivals
        next_arrival = random.expovariate(arrival_rate)
        job_count = 0

        while next_arrival < duration_minutes:
            job_id = f"JOB-{job_count:04d}"
            job = Job(
                id=job_id,
                part_id=f"BRICK-{random.randint(1, 100):03d}",
                routing=routing.copy(),
                arrival_time=next_arrival,
            )
            self.jobs[job_id] = job

            self.schedule_event(SimEvent(
                time=next_arrival,
                event_type=EventType.ARRIVAL,
                resource_id=routing[0],
                job_id=job_id,
            ))

            next_arrival += random.expovariate(arrival_rate)
            job_count += 1

        # Schedule random breakdowns
        for wc_id, wc in self.work_centers.items():
            next_breakdown = random.expovariate(1.0 / wc.mtbf)
            while next_breakdown < duration_minutes:
                self.schedule_event(SimEvent(
                    time=next_breakdown,
                    event_type=EventType.BREAKDOWN,
                    resource_id=wc_id,
                ))
                # Schedule repair
                repair_time = next_breakdown + random.expovariate(1.0 / wc.mttr)
                self.schedule_event(SimEvent(
                    time=repair_time,
                    event_type=EventType.REPAIR,
                    resource_id=wc_id,
                ))
                next_breakdown = repair_time + random.expovariate(1.0 / wc.mtbf)

        # Process events
        events_processed = 0
        while self.event_queue and self.current_time < duration_minutes:
            event = heapq.heappop(self.event_queue)
            self._update_statistics(event.time)
            self.current_time = event.time
            self._process_event(event)
            events_processed += 1

        # Calculate results
        return self._calculate_results(duration_minutes, events_processed)

    def _process_event(self, event: SimEvent):
        """Process a simulation event."""
        import random

        wc = self.work_centers.get(event.resource_id)
        if not wc:
            return

        if event.event_type == EventType.ARRIVAL:
            job = self.jobs.get(event.job_id)
            if not job:
                return

            if wc.state == ResourceState.IDLE and wc.current_job is None:
                # Start processing immediately
                wc.state = ResourceState.BUSY
                wc.current_job = event.job_id

                # Schedule departure
                process_time = max(1, random.gauss(
                    wc.processing_time_mean,
                    wc.processing_time_std
                ))
                job.process_times[wc.id] = process_time

                self.schedule_event(SimEvent(
                    time=self.current_time + process_time,
                    event_type=EventType.DEPARTURE,
                    resource_id=wc.id,
                    job_id=event.job_id,
                ))
            else:
                # Add to queue
                wc.queue.append(event.job_id)
                job.wait_times[wc.id] = self.current_time

        elif event.event_type == EventType.DEPARTURE:
            job = self.jobs.get(event.job_id)
            if not job:
                return

            wc.jobs_completed += 1
            wc.current_job = None

            # Move to next step
            job.current_step += 1
            if job.current_step < len(job.routing):
                next_wc = job.routing[job.current_step]
                self.schedule_event(SimEvent(
                    time=self.current_time,
                    event_type=EventType.ARRIVAL,
                    resource_id=next_wc,
                    job_id=job.id,
                ))
            else:
                job.completion_time = self.current_time

            # Start next job from queue
            if wc.queue and wc.state != ResourceState.DOWN:
                next_job_id = wc.queue.pop(0)
                next_job = self.jobs.get(next_job_id)
                if next_job:
                    # Record wait time
                    if wc.id in next_job.wait_times:
                        wait_start = next_job.wait_times[wc.id]
                        self.statistics[wc.id]['wait_times'].append(
                            self.current_time - wait_start
                        )

                    wc.current_job = next_job_id
                    wc.state = ResourceState.BUSY

                    process_time = max(1, random.gauss(
                        wc.processing_time_mean,
                        wc.processing_time_std
                    ))
                    next_job.process_times[wc.id] = process_time

                    self.schedule_event(SimEvent(
                        time=self.current_time + process_time,
                        event_type=EventType.DEPARTURE,
                        resource_id=wc.id,
                        job_id=next_job_id,
                    ))
            else:
                wc.state = ResourceState.IDLE

        elif event.event_type == EventType.BREAKDOWN:
            wc.state = ResourceState.DOWN

        elif event.event_type == EventType.REPAIR:
            if wc.queue:
                wc.state = ResourceState.BUSY
            else:
                wc.state = ResourceState.IDLE

    def _update_statistics(self, new_time: float):
        """Update time-based statistics."""
        delta = new_time - self.current_time

        for wc_id, wc in self.work_centers.items():
            stats = self.statistics[wc_id]

            if wc.state == ResourceState.BUSY:
                stats['busy_time'] += delta
            elif wc.state == ResourceState.IDLE:
                stats['idle_time'] += delta
            elif wc.state == ResourceState.BLOCKED:
                stats['blocked_time'] += delta
            elif wc.state == ResourceState.DOWN:
                stats['down_time'] += delta

            stats['queue_lengths'].append(len(wc.queue))

    def _calculate_results(
        self,
        duration: float,
        events_processed: int
    ) -> SimulationResult:
        """Calculate simulation results."""
        completed_jobs = [
            j for j in self.jobs.values()
            if j.completion_time is not None
        ]

        # Calculate cycle times
        cycle_times = [
            j.completion_time - j.arrival_time
            for j in completed_jobs
        ]

        # Calculate utilization
        utilization = {}
        for wc_id, stats in self.statistics.items():
            total_time = stats['busy_time'] + stats['idle_time'] + stats['down_time']
            if total_time > 0:
                utilization[wc_id] = stats['busy_time'] / total_time
            else:
                utilization[wc_id] = 0.0

        # Find bottleneck (highest utilization)
        bottleneck = max(utilization, key=utilization.get) if utilization else 'N/A'

        # Queue statistics
        queue_stats = {}
        for wc_id, stats in self.statistics.items():
            queues = stats['queue_lengths']
            waits = stats['wait_times']
            queue_stats[wc_id] = {
                'avg_queue_length': sum(queues) / len(queues) if queues else 0,
                'max_queue_length': max(queues) if queues else 0,
                'avg_wait_time': sum(waits) / len(waits) if waits else 0,
            }

        return SimulationResult(
            simulation_id=str(uuid.uuid4()),
            duration_minutes=duration,
            jobs_completed=len(completed_jobs),
            jobs_in_progress=len(self.jobs) - len(completed_jobs),
            throughput_per_hour=(len(completed_jobs) / duration) * 60,
            average_cycle_time=sum(cycle_times) / len(cycle_times) if cycle_times else 0,
            average_wait_time=sum(
                sum(s['wait_times']) for s in self.statistics.values()
            ) / max(1, sum(len(s['wait_times']) for s in self.statistics.values())),
            resource_utilization=utilization,
            bottleneck_resource=bottleneck,
            queue_statistics=queue_stats,
            events_processed=events_processed,
        )


# Singleton instance
_factory_model: Optional[FactoryModel] = None


def get_factory_model() -> FactoryModel:
    """Get or create the factory model instance."""
    global _factory_model
    if _factory_model is None:
        _factory_model = FactoryModel()
    return _factory_model
