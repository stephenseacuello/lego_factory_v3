"""
LEGO Factory v3 - Live Simulation Mode
========================================
Real-time accelerated simulation with WebSocket updates for Gantt visualization.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
import uuid

logger = logging.getLogger(__name__)


@dataclass
class LiveSimConfig:
    """Configuration for live simulation."""
    schedule_id: str
    speed_factor: float = 60.0  # 60x = 1 sim minute per real second
    start_time: datetime = None
    duration_hours: float = 168.0
    enable_breakdowns: bool = True
    enable_defects: bool = True
    enable_shortages: bool = True


class LiveSimulator:
    """
    Live simulator that runs in accelerated real-time.

    Updates job states in database and emits WebSocket events
    for real-time Gantt chart updates.
    """

    def __init__(self, config: LiveSimConfig = None):
        self.config = config or LiveSimConfig(schedule_id='default')
        self.sim_id = str(uuid.uuid4())[:8]

        # State
        self._running = False
        self._paused = False
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially

        self._speed_factor = self.config.speed_factor
        self._sim_clock = config.start_time or datetime.utcnow()
        self._real_start_time = None

        # Thread
        self._thread: Optional[threading.Thread] = None

        # DES engine
        self._simulator = None
        self._event_queue = None

        # Statistics
        self.events_processed = 0
        self.jobs_completed = 0
        self.breakdowns = 0
        self.defects = 0

        # Callbacks
        self._on_event: Optional[Callable] = None
        self._on_job_update: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def sim_time(self) -> datetime:
        return self._sim_clock

    @property
    def speed_factor(self) -> float:
        return self._speed_factor

    def start(
        self,
        schedule: list,
        machines: list,
        on_event: Callable = None,
        on_job_update: Callable = None,
        on_complete: Callable = None
    ):
        """
        Start live simulation.

        Args:
            schedule: Job schedule to simulate
            machines: Machine definitions
            on_event: Callback for simulation events
            on_job_update: Callback for job status changes
            on_complete: Callback when simulation completes
        """
        if self._running:
            logger.warning("Simulation already running")
            return

        self._on_event = on_event
        self._on_job_update = on_job_update
        self._on_complete = on_complete

        self._stop_event.clear()
        self._pause_event.set()
        self._running = True
        self._paused = False
        self._real_start_time = time.time()

        # Initialize DES engine
        from services.simulation.des_engine import (
            DiscreteEventSimulator, SimConfig, EventQueue
        )

        sim_config = SimConfig(
            start_time=self.config.start_time or datetime.utcnow(),
            duration_hours=self.config.duration_hours,
            enable_breakdowns=self.config.enable_breakdowns,
            enable_quality_defects=self.config.enable_defects,
            enable_material_shortages=self.config.enable_shortages,
            random_seed=int(time.time()),
        )

        self._simulator = DiscreteEventSimulator(sim_config)
        self._simulator._initialize_machines(machines)
        self._simulator._initialize_jobs(schedule)
        self._simulator._schedule_initial_events(schedule)

        if self.config.enable_breakdowns:
            self._simulator._schedule_breakdown_events()

        self._event_queue = self._simulator.event_queue
        self._sim_clock = sim_config.start_time

        # Update state
        from services.simulation.sim_state import SimulationState
        SimulationState.create(self.sim_id, {
            'status': 'running',
            'sim_clock': self._sim_clock.isoformat(),
            'speed_factor': self._speed_factor,
            'events_processed': 0,
        })

        # Start thread
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        logger.info(f"Live simulation {self.sim_id} started at {self._speed_factor}x speed")

        # Emit start event
        self._emit_event('sim_started', {
            'sim_id': self.sim_id,
            'speed_factor': self._speed_factor,
            'start_time': self._sim_clock.isoformat(),
        })

    def _run_loop(self):
        """Main simulation loop running in separate thread."""
        end_time = self._sim_clock + timedelta(hours=self.config.duration_hours)

        while not self._stop_event.is_set():
            # Wait if paused
            self._pause_event.wait()

            if self._stop_event.is_set():
                break

            # Get next event
            if self._event_queue.is_empty():
                break

            next_event = self._event_queue.peek()
            if not next_event:
                break

            # Stop if past end time
            if next_event.timestamp > end_time:
                break

            # Calculate real-time delay
            sim_delta = (next_event.timestamp - self._sim_clock).total_seconds()
            real_delay = sim_delta / self._speed_factor

            # Wait with interruptible sleep
            if real_delay > 0:
                if self._stop_event.wait(timeout=real_delay):
                    break  # Stop requested during wait

            # Check pause again
            self._pause_event.wait()

            if self._stop_event.is_set():
                break

            # Process event
            event = self._event_queue.pop()
            if event:
                self._sim_clock = event.timestamp
                self._process_event(event)
                self.events_processed += 1

                # Update state
                self._update_state()

                # Emit clock tick periodically
                if self.events_processed % 5 == 0:
                    self._emit_clock_tick()

        # Simulation complete
        self._running = False
        self._emit_event('sim_complete', self._get_summary())

        if self._on_complete:
            self._on_complete(self._get_summary())

        logger.info(f"Live simulation {self.sim_id} completed")

    def _process_event(self, event):
        """Process simulation event and emit updates."""
        from services.simulation.des_engine import EventType

        # Let DES engine handle the logic
        self._simulator._process_event(event)

        # Emit event to WebSocket
        event_data = {
            'event_type': event.event_type.value,
            'machine_id': event.machine_id,
            'job_id': event.job_id,
            'sim_time': self._sim_clock.isoformat(),
            'data': event.data,
        }
        self._emit_event('sim_event', event_data)

        # Handle specific events
        if event.event_type == EventType.JOB_COMPLETE:
            self.jobs_completed += 1
            job = self._simulator.jobs.get(event.job_id)
            if job:
                self._update_job_in_db(job)
                if self._on_job_update:
                    self._on_job_update(event.job_id, 'completed', self._sim_clock)

        elif event.event_type == EventType.JOB_START:
            job = self._simulator.jobs.get(event.job_id)
            if job:
                self._update_job_in_db(job)
                if self._on_job_update:
                    self._on_job_update(event.job_id, 'running', self._sim_clock)

        elif event.event_type == EventType.BREAKDOWN:
            self.breakdowns += 1
            self._emit_event('sim_machine_update', {
                'machine_id': event.machine_id,
                'status': 'breakdown',
                'sim_time': self._sim_clock.isoformat(),
            })

        elif event.event_type == EventType.REPAIR_COMPLETE:
            self._emit_event('sim_machine_update', {
                'machine_id': event.machine_id,
                'status': 'idle',
                'sim_time': self._sim_clock.isoformat(),
            })

        elif event.event_type == EventType.QUALITY_DEFECT:
            self.defects += 1

        # Callback
        if self._on_event:
            self._on_event(event)

    def _update_job_in_db(self, job):
        """Update job status in database for Gantt refresh."""
        try:
            from database import db
            from models.mes.work_orders import Job, JobStatus

            db_job = db.session.query(Job).filter(Job.job_id == job.job_id).first()
            if db_job:
                if job.status == 'running':
                    db_job.status = JobStatus.RUNNING
                    db_job.actual_start = job.actual_start
                elif job.status == 'completed':
                    db_job.status = JobStatus.COMPLETED
                    db_job.actual_end = job.actual_end

                db.session.commit()
        except Exception as e:
            logger.debug(f"Could not update job in DB: {e}")

    def _emit_event(self, event_name: str, data: dict):
        """Emit event to WebSocket clients."""
        try:
            from services.websocket.socket_service import emit_to_namespace
            emit_to_namespace(event_name, data, namespace='/simulation')
        except Exception as e:
            logger.debug(f"Could not emit event: {e}")

    def _emit_clock_tick(self):
        """Emit simulation clock tick."""
        self._emit_event('sim_clock_tick', {
            'sim_time': self._sim_clock.isoformat(),
            'speed_factor': self._speed_factor,
            'events_processed': self.events_processed,
            'jobs_completed': self.jobs_completed,
        })

    def _update_state(self):
        """Update persistent simulation state."""
        try:
            from services.simulation.sim_state import SimulationState
            SimulationState.update(self.sim_id, {
                'sim_clock': self._sim_clock.isoformat(),
                'events_processed': self.events_processed,
                'jobs_completed': self.jobs_completed,
                'breakdowns': self.breakdowns,
                'defects': self.defects,
            })
        except Exception as e:
            logger.debug(f"Could not update state: {e}")

    def _get_summary(self) -> dict:
        """Get simulation summary."""
        return {
            'sim_id': self.sim_id,
            'final_time': self._sim_clock.isoformat(),
            'events_processed': self.events_processed,
            'jobs_completed': self.jobs_completed,
            'breakdowns': self.breakdowns,
            'defects': self.defects,
            'duration_real_seconds': time.time() - self._real_start_time if self._real_start_time else 0,
        }

    def pause(self):
        """Pause the simulation."""
        if not self._running:
            return

        self._pause_event.clear()
        self._paused = True

        self._emit_event('sim_paused', {
            'sim_time': self._sim_clock.isoformat(),
        })

        try:
            from services.simulation.sim_state import SimulationState
            SimulationState.update(self.sim_id, {'status': 'paused'})
        except:
            pass

        logger.info(f"Simulation {self.sim_id} paused")

    def resume(self):
        """Resume the simulation."""
        if not self._running:
            return

        self._pause_event.set()
        self._paused = False

        self._emit_event('sim_resumed', {
            'sim_time': self._sim_clock.isoformat(),
        })

        try:
            from services.simulation.sim_state import SimulationState
            SimulationState.update(self.sim_id, {'status': 'running'})
        except:
            pass

        logger.info(f"Simulation {self.sim_id} resumed")

    def stop(self):
        """Stop the simulation."""
        self._stop_event.set()
        self._pause_event.set()  # Unblock if paused
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._emit_event('sim_stopped', self._get_summary())

        try:
            from services.simulation.sim_state import SimulationState
            SimulationState.update(self.sim_id, {'status': 'stopped'})
        except:
            pass

        logger.info(f"Simulation {self.sim_id} stopped")

    def set_speed(self, factor: float):
        """Change simulation speed."""
        if factor < 1:
            factor = 1
        elif factor > 1000:
            factor = 1000

        old_factor = self._speed_factor
        self._speed_factor = factor

        self._emit_event('sim_speed_changed', {
            'old_factor': old_factor,
            'new_factor': factor,
        })

        try:
            from services.simulation.sim_state import SimulationState
            SimulationState.update(self.sim_id, {'speed_factor': factor})
        except:
            pass

        logger.info(f"Simulation speed changed: {old_factor}x -> {factor}x")

    def inject_event(self, event_type: str, machine_id: str, data: dict = None):
        """
        Inject a manual event into the simulation.

        Used for user-triggered breakdowns, shortages, etc.
        """
        if not self._running:
            return

        from services.simulation.des_engine import SimEvent, EventType

        try:
            event_enum = EventType(event_type)
        except ValueError:
            logger.warning(f"Unknown event type: {event_type}")
            return

        event = SimEvent(
            timestamp=self._sim_clock,
            event_type=event_enum,
            machine_id=machine_id,
            data=data or {},
            priority=-1,  # High priority
        )

        self._event_queue.push(event)

        self._emit_event('sim_event_injected', {
            'event_type': event_type,
            'machine_id': machine_id,
            'sim_time': self._sim_clock.isoformat(),
        })

        logger.info(f"Injected event {event_type} for machine {machine_id}")

    def get_state(self) -> dict:
        """Get current simulation state."""
        return {
            'sim_id': self.sim_id,
            'running': self._running,
            'paused': self._paused,
            'sim_time': self._sim_clock.isoformat(),
            'speed_factor': self._speed_factor,
            'events_processed': self.events_processed,
            'jobs_completed': self.jobs_completed,
            'breakdowns': self.breakdowns,
            'defects': self.defects,
        }


# Global instance for singleton pattern
_active_simulator: Optional[LiveSimulator] = None


def get_active_simulator() -> Optional[LiveSimulator]:
    """Get the currently active live simulator."""
    global _active_simulator
    return _active_simulator


def start_live_simulation(
    schedule: list,
    machines: list,
    config: LiveSimConfig = None
) -> LiveSimulator:
    """
    Start a new live simulation.

    Stops any existing simulation first.
    """
    global _active_simulator

    # Stop existing
    if _active_simulator and _active_simulator.is_running:
        _active_simulator.stop()

    # Create new
    _active_simulator = LiveSimulator(config)
    _active_simulator.start(schedule, machines)

    return _active_simulator


def stop_live_simulation():
    """Stop the active live simulation."""
    global _active_simulator

    if _active_simulator:
        _active_simulator.stop()
        _active_simulator = None
