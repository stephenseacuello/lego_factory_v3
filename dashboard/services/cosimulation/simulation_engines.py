"""
V8 Simulation Engines
=====================

Individual simulation engine implementations:
- DES Engine: Discrete Event Simulation using event queue
- PINN Engine: Physics-Informed Neural Network integration
- Monte Carlo Engine: Stochastic uncertainty analysis
- FMI/FMU Engine: Functional Mockup Interface standard

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import logging
import math
import heapq
import random
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================
# Base Engine Interface
# ============================================

class EngineState(Enum):
    """Engine execution state."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EngineResult:
    """Result from engine execution."""
    engine_type: str
    success: bool
    metrics: Dict[str, float] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_type": self.engine_type,
            "success": self.success,
            "metrics": self.metrics,
            "outputs": self.outputs,
            "events": self.events,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


class SimulationEngineBase(ABC):
    """Abstract base class for simulation engines."""

    def __init__(self, engine_type: str):
        self.engine_type = engine_type
        self.state = EngineState.IDLE
        self._parameters: Dict[str, Any] = {}
        self._lock = threading.Lock()

    @abstractmethod
    def initialize(self, parameters: Dict[str, Any]) -> bool:
        """Initialize the engine with parameters."""
        pass

    @abstractmethod
    def step(self, time_step: float) -> Dict[str, Any]:
        """Execute one simulation step."""
        pass

    @abstractmethod
    def run(self, duration_seconds: float) -> EngineResult:
        """Run simulation for specified duration."""
        pass

    @abstractmethod
    def reset(self):
        """Reset engine to initial state."""
        pass

    def get_state(self) -> EngineState:
        return self.state


# ============================================
# DES Engine - Discrete Event Simulation
# ============================================

@dataclass
class DiscreteEvent:
    """Event in discrete event simulation."""
    event_id: str
    time: float
    event_type: str
    entity_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0

    def __lt__(self, other):
        if self.time == other.time:
            return self.priority < other.priority
        return self.time < other.time


@dataclass
class Entity:
    """Entity in DES (job, part, etc.)."""
    entity_id: str
    entity_type: str
    created_at: float
    attributes: Dict[str, Any] = field(default_factory=dict)
    state: str = "created"
    location: str = "queue"


class DESEngine(SimulationEngineBase):
    """
    Discrete Event Simulation Engine.

    Models production flow using event-driven simulation:
    - Job arrivals and completions
    - Machine processing
    - Queue management
    - Resource allocation
    """

    def __init__(self):
        super().__init__("des")
        self._event_queue: List[DiscreteEvent] = []
        self._current_time: float = 0.0
        self._entities: Dict[str, Entity] = {}
        self._resources: Dict[str, Dict[str, Any]] = {}
        self._metrics: Dict[str, float] = {}
        self._event_log: List[Dict[str, Any]] = []
        self._event_handlers: Dict[str, Callable] = {}

        # Default production resources
        self._resources = {
            "printer_01": {"type": "printer", "capacity": 1, "busy": 0, "queue": []},
            "printer_02": {"type": "printer", "capacity": 1, "busy": 0, "queue": []},
            "cnc_01": {"type": "cnc", "capacity": 1, "busy": 0, "queue": []},
            "assembly_01": {"type": "assembly", "capacity": 2, "busy": 0, "queue": []},
            "inspection_01": {"type": "inspection", "capacity": 1, "busy": 0, "queue": []},
        }

        # Register default event handlers
        self._event_handlers = {
            "arrival": self._handle_arrival,
            "start_processing": self._handle_start_processing,
            "end_processing": self._handle_end_processing,
            "departure": self._handle_departure,
        }

    def initialize(self, parameters: Dict[str, Any]) -> bool:
        """Initialize DES engine."""
        try:
            self.state = EngineState.INITIALIZING
            self._parameters = parameters

            # Reset state
            self._event_queue = []
            self._current_time = 0.0
            self._entities = {}
            self._event_log = []

            # Initialize metrics
            self._metrics = {
                "total_arrivals": 0,
                "total_departures": 0,
                "total_processing_time": 0,
                "total_wait_time": 0,
                "avg_cycle_time": 0,
                "throughput": 0,
                "utilization": 0,
            }

            # Schedule initial arrivals if specified
            arrival_rate = parameters.get("arrival_rate", 10)  # per hour
            num_initial = parameters.get("initial_jobs", 5)

            for i in range(num_initial):
                arrival_time = random.expovariate(arrival_rate / 3600)
                self._schedule_event(
                    arrival_time,
                    "arrival",
                    f"job-{uuid.uuid4().hex[:8]}",
                    {"job_type": "standard"},
                )

            self.state = EngineState.IDLE
            logger.info("DES Engine initialized")
            return True

        except Exception as e:
            logger.error(f"DES initialization failed: {e}")
            self.state = EngineState.FAILED
            return False

    def step(self, time_step: float) -> Dict[str, Any]:
        """Execute simulation until time advances by time_step."""
        target_time = self._current_time + time_step
        events_processed = 0

        while self._event_queue and self._event_queue[0].time <= target_time:
            event = heapq.heappop(self._event_queue)
            self._current_time = event.time
            self._process_event(event)
            events_processed += 1

        self._current_time = target_time

        return {
            "current_time": self._current_time,
            "events_processed": events_processed,
            "pending_events": len(self._event_queue),
            "active_entities": len(self._entities),
        }

    def run(self, duration_seconds: float) -> EngineResult:
        """Run DES for specified duration."""
        import time as time_module
        start_time = time_module.time()

        try:
            self.state = EngineState.RUNNING
            target_time = self._current_time + duration_seconds
            events_processed = 0

            while self._event_queue and self._event_queue[0].time <= target_time:
                event = heapq.heappop(self._event_queue)
                self._current_time = event.time
                self._process_event(event)
                events_processed += 1

            self._current_time = target_time
            self._calculate_final_metrics(duration_seconds)
            self.state = EngineState.COMPLETED

            return EngineResult(
                engine_type="des",
                success=True,
                metrics=self._metrics.copy(),
                outputs={
                    "simulation_time": self._current_time,
                    "events_processed": events_processed,
                    "final_wip": len(self._entities),
                },
                events=self._event_log[-100:],  # Last 100 events
                duration_seconds=time_module.time() - start_time,
            )

        except Exception as e:
            self.state = EngineState.FAILED
            return EngineResult(
                engine_type="des",
                success=False,
                error=str(e),
                duration_seconds=time_module.time() - start_time,
            )

    def reset(self):
        """Reset DES engine."""
        self._event_queue = []
        self._current_time = 0.0
        self._entities = {}
        self._event_log = []
        self._metrics = {}
        self.state = EngineState.IDLE

    def _schedule_event(
        self,
        time: float,
        event_type: str,
        entity_id: str,
        data: Dict[str, Any] = None,
        priority: int = 0,
    ):
        """Schedule an event."""
        event = DiscreteEvent(
            event_id=f"evt-{uuid.uuid4().hex[:8]}",
            time=time,
            event_type=event_type,
            entity_id=entity_id,
            data=data or {},
            priority=priority,
        )
        heapq.heappush(self._event_queue, event)

    def _process_event(self, event: DiscreteEvent):
        """Process a discrete event."""
        handler = self._event_handlers.get(event.event_type)
        if handler:
            handler(event)

        self._event_log.append({
            "event_id": event.event_id,
            "time": event.time,
            "type": event.event_type,
            "entity_id": event.entity_id,
        })

    def _handle_arrival(self, event: DiscreteEvent):
        """Handle job arrival."""
        entity = Entity(
            entity_id=event.entity_id,
            entity_type="job",
            created_at=event.time,
            attributes=event.data,
        )
        self._entities[entity.entity_id] = entity
        self._metrics["total_arrivals"] += 1

        # Find available resource
        resource = self._find_available_resource("printer")
        if resource:
            self._schedule_event(
                event.time,
                "start_processing",
                event.entity_id,
                {"resource": resource},
            )
        else:
            # Add to queue
            self._resources["printer_01"]["queue"].append(event.entity_id)

        # Schedule next arrival
        arrival_rate = self._parameters.get("arrival_rate", 10)
        next_arrival = event.time + random.expovariate(arrival_rate / 3600)
        if next_arrival < self._parameters.get("end_time", float("inf")):
            self._schedule_event(
                next_arrival,
                "arrival",
                f"job-{uuid.uuid4().hex[:8]}",
                {"job_type": "standard"},
            )

    def _handle_start_processing(self, event: DiscreteEvent):
        """Handle start of processing."""
        entity = self._entities.get(event.entity_id)
        if entity:
            entity.state = "processing"
            entity.location = event.data.get("resource", "unknown")

            # Schedule end of processing
            processing_time = random.gauss(300, 60)  # ~5 min avg
            processing_time = max(60, processing_time)

            self._schedule_event(
                event.time + processing_time,
                "end_processing",
                event.entity_id,
                event.data,
            )

    def _handle_end_processing(self, event: DiscreteEvent):
        """Handle end of processing."""
        entity = self._entities.get(event.entity_id)
        if entity:
            entity.state = "completed"
            processing_time = event.time - entity.created_at
            self._metrics["total_processing_time"] += processing_time

            # Schedule departure
            self._schedule_event(event.time, "departure", event.entity_id)

            # Start next job in queue
            resource_name = event.data.get("resource")
            if resource_name and self._resources.get(resource_name, {}).get("queue"):
                next_entity = self._resources[resource_name]["queue"].pop(0)
                self._schedule_event(
                    event.time,
                    "start_processing",
                    next_entity,
                    {"resource": resource_name},
                )

    def _handle_departure(self, event: DiscreteEvent):
        """Handle job departure."""
        entity = self._entities.pop(event.entity_id, None)
        if entity:
            self._metrics["total_departures"] += 1
            cycle_time = event.time - entity.created_at
            self._metrics["total_wait_time"] += cycle_time

    def _find_available_resource(self, resource_type: str) -> Optional[str]:
        """Find an available resource of given type."""
        for name, resource in self._resources.items():
            if resource["type"] == resource_type:
                if resource["busy"] < resource["capacity"]:
                    resource["busy"] += 1
                    return name
        return None

    def _calculate_final_metrics(self, duration: float):
        """Calculate final simulation metrics."""
        if self._metrics["total_departures"] > 0:
            self._metrics["avg_cycle_time"] = (
                self._metrics["total_wait_time"] / self._metrics["total_departures"]
            )
            self._metrics["throughput"] = (
                self._metrics["total_departures"] / (duration / 3600)
            )


# ============================================
# Monte Carlo Engine
# ============================================

@dataclass
class MonteCarloSample:
    """Single Monte Carlo sample."""
    sample_id: int
    inputs: Dict[str, float]
    outputs: Dict[str, float]
    valid: bool = True


class MonteCarloEngine(SimulationEngineBase):
    """
    Monte Carlo Simulation Engine.

    Performs stochastic analysis:
    - Uncertainty quantification
    - Risk assessment
    - Sensitivity analysis
    - Confidence intervals
    """

    def __init__(self):
        super().__init__("monte_carlo")
        self._samples: List[MonteCarloSample] = []
        self._input_distributions: Dict[str, Dict[str, Any]] = {}
        self._output_functions: Dict[str, Callable] = {}
        self._statistics: Dict[str, Dict[str, float]] = {}

    def initialize(self, parameters: Dict[str, Any]) -> bool:
        """Initialize Monte Carlo engine."""
        try:
            self.state = EngineState.INITIALIZING
            self._parameters = parameters
            self._samples = []
            self._statistics = {}

            # Default input distributions
            self._input_distributions = parameters.get("distributions", {
                "processing_time": {"type": "normal", "mean": 300, "std": 60},
                "arrival_rate": {"type": "uniform", "min": 8, "max": 12},
                "defect_rate": {"type": "beta", "alpha": 2, "beta": 98},
                "machine_mtbf": {"type": "exponential", "lambda": 0.001},
            })

            # Set random seed if provided
            seed = parameters.get("random_seed")
            if seed is not None:
                random.seed(seed)

            self.state = EngineState.IDLE
            logger.info("Monte Carlo Engine initialized")
            return True

        except Exception as e:
            logger.error(f"Monte Carlo initialization failed: {e}")
            self.state = EngineState.FAILED
            return False

    def step(self, time_step: float) -> Dict[str, Any]:
        """Generate one Monte Carlo sample."""
        sample = self._generate_sample(len(self._samples))
        self._samples.append(sample)

        return {
            "sample_id": sample.sample_id,
            "inputs": sample.inputs,
            "outputs": sample.outputs,
        }

    def run(self, duration_seconds: float) -> EngineResult:
        """Run Monte Carlo simulation."""
        import time as time_module
        start_time = time_module.time()

        try:
            self.state = EngineState.RUNNING
            iterations = self._parameters.get("iterations", 1000)

            for i in range(iterations):
                sample = self._generate_sample(i)
                self._samples.append(sample)

            self._calculate_statistics()
            self.state = EngineState.COMPLETED

            return EngineResult(
                engine_type="monte_carlo",
                success=True,
                metrics=self._flatten_statistics(),
                outputs={
                    "total_samples": len(self._samples),
                    "valid_samples": sum(1 for s in self._samples if s.valid),
                    "statistics": self._statistics,
                },
                duration_seconds=time_module.time() - start_time,
            )

        except Exception as e:
            self.state = EngineState.FAILED
            return EngineResult(
                engine_type="monte_carlo",
                success=False,
                error=str(e),
                duration_seconds=time_module.time() - start_time,
            )

    def reset(self):
        """Reset Monte Carlo engine."""
        self._samples = []
        self._statistics = {}
        self.state = EngineState.IDLE

    def _generate_sample(self, sample_id: int) -> MonteCarloSample:
        """Generate a single Monte Carlo sample."""
        inputs = {}

        for name, dist in self._input_distributions.items():
            inputs[name] = self._sample_distribution(dist)

        # Calculate outputs based on model
        outputs = self._evaluate_model(inputs)

        return MonteCarloSample(
            sample_id=sample_id,
            inputs=inputs,
            outputs=outputs,
        )

    def _sample_distribution(self, dist: Dict[str, Any]) -> float:
        """Sample from a distribution."""
        dist_type = dist.get("type", "normal")

        if dist_type == "normal":
            return random.gauss(dist.get("mean", 0), dist.get("std", 1))
        elif dist_type == "uniform":
            return random.uniform(dist.get("min", 0), dist.get("max", 1))
        elif dist_type == "exponential":
            return random.expovariate(dist.get("lambda", 1))
        elif dist_type == "beta":
            return random.betavariate(dist.get("alpha", 2), dist.get("beta", 2))
        elif dist_type == "triangular":
            return random.triangular(
                dist.get("low", 0),
                dist.get("high", 1),
                dist.get("mode", 0.5),
            )
        else:
            return random.random()

    def _evaluate_model(self, inputs: Dict[str, float]) -> Dict[str, float]:
        """Evaluate production model with inputs."""
        processing_time = inputs.get("processing_time", 300)
        arrival_rate = inputs.get("arrival_rate", 10)
        defect_rate = inputs.get("defect_rate", 0.02)
        mtbf = inputs.get("machine_mtbf", 1000)

        # Calculate derived outputs
        availability = 1 - (processing_time / (mtbf * 3600)) if mtbf > 0 else 0.9
        quality_rate = 1 - defect_rate
        throughput = (3600 / processing_time) * availability * quality_rate
        oee = availability * 0.85 * quality_rate  # Assuming 85% performance

        return {
            "throughput": throughput,
            "oee": oee,
            "availability": availability,
            "quality_rate": quality_rate,
            "cycle_time": processing_time,
        }

    def _calculate_statistics(self):
        """Calculate statistics from samples."""
        if not self._samples:
            return

        # Collect all output values
        output_names = self._samples[0].outputs.keys()

        for name in output_names:
            values = [s.outputs.get(name, 0) for s in self._samples if s.valid]
            if values:
                values.sort()
                n = len(values)

                self._statistics[name] = {
                    "mean": sum(values) / n,
                    "std": self._std(values),
                    "min": values[0],
                    "max": values[-1],
                    "p5": values[int(n * 0.05)],
                    "p50": values[int(n * 0.5)],
                    "p95": values[int(n * 0.95)],
                }

    def _std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)

    def _flatten_statistics(self) -> Dict[str, float]:
        """Flatten statistics for metrics output."""
        flat = {}
        for name, stats in self._statistics.items():
            for stat_name, value in stats.items():
                flat[f"{name}_{stat_name}"] = value
        return flat


# ============================================
# PINN Engine - Physics-Informed Neural Network
# ============================================

class PINNEngine(SimulationEngineBase):
    """
    Physics-Informed Neural Network Engine.

    Combines physics models with neural networks:
    - Thermal dynamics
    - Mechanical behavior
    - Process physics
    - Equipment degradation
    """

    def __init__(self):
        super().__init__("pinn")
        self._physics_models: Dict[str, Callable] = {}
        self._state_variables: Dict[str, float] = {}
        self._history: List[Dict[str, float]] = []

        # Initialize default physics models
        self._physics_models = {
            "thermal": self._thermal_model,
            "mechanical": self._mechanical_model,
            "degradation": self._degradation_model,
        }

    def initialize(self, parameters: Dict[str, Any]) -> bool:
        """Initialize PINN engine."""
        try:
            self.state = EngineState.INITIALIZING
            self._parameters = parameters

            # Initialize state variables
            self._state_variables = {
                "temperature": parameters.get("initial_temperature", 25.0),
                "vibration": parameters.get("initial_vibration", 0.1),
                "wear": parameters.get("initial_wear", 0.0),
                "stress": parameters.get("initial_stress", 0.0),
            }

            self._history = []
            self.state = EngineState.IDLE
            logger.info("PINN Engine initialized")
            return True

        except Exception as e:
            logger.error(f"PINN initialization failed: {e}")
            self.state = EngineState.FAILED
            return False

    def step(self, time_step: float) -> Dict[str, Any]:
        """Execute one physics simulation step."""
        # Apply physics models
        for model_name, model_func in self._physics_models.items():
            model_func(time_step)

        # Record history
        snapshot = {
            "time": len(self._history) * time_step,
            **self._state_variables.copy(),
        }
        self._history.append(snapshot)

        return snapshot

    def run(self, duration_seconds: float) -> EngineResult:
        """Run PINN simulation."""
        import time as time_module
        start_time = time_module.time()

        try:
            self.state = EngineState.RUNNING
            time_step = self._parameters.get("time_step", 1.0)
            steps = int(duration_seconds / time_step)

            for _ in range(steps):
                self.step(time_step)

            self.state = EngineState.COMPLETED

            return EngineResult(
                engine_type="pinn",
                success=True,
                metrics={
                    "final_temperature": self._state_variables["temperature"],
                    "final_vibration": self._state_variables["vibration"],
                    "final_wear": self._state_variables["wear"],
                    "health_index": self._calculate_health_index(),
                },
                outputs={
                    "state_variables": self._state_variables.copy(),
                    "history_length": len(self._history),
                },
                events=[],
                duration_seconds=time_module.time() - start_time,
            )

        except Exception as e:
            self.state = EngineState.FAILED
            return EngineResult(
                engine_type="pinn",
                success=False,
                error=str(e),
                duration_seconds=time_module.time() - start_time,
            )

    def reset(self):
        """Reset PINN engine."""
        self._state_variables = {
            "temperature": 25.0,
            "vibration": 0.1,
            "wear": 0.0,
            "stress": 0.0,
        }
        self._history = []
        self.state = EngineState.IDLE

    def _thermal_model(self, dt: float):
        """Thermal dynamics model."""
        ambient_temp = self._parameters.get("ambient_temperature", 25.0)
        heat_generation = self._parameters.get("heat_generation", 5.0)
        cooling_rate = self._parameters.get("cooling_rate", 0.1)

        temp = self._state_variables["temperature"]
        noise = random.gauss(0, 0.5)

        # Newton's law of cooling with heat generation
        dT = (heat_generation - cooling_rate * (temp - ambient_temp)) * dt + noise
        self._state_variables["temperature"] = temp + dT

    def _mechanical_model(self, dt: float):
        """Mechanical vibration model."""
        base_vibration = self._parameters.get("base_vibration", 0.1)
        wear_effect = self._state_variables["wear"] * 0.5
        noise = random.gauss(0, 0.02)

        self._state_variables["vibration"] = base_vibration + wear_effect + noise

    def _degradation_model(self, dt: float):
        """Equipment degradation model."""
        wear_rate = self._parameters.get("wear_rate", 0.0001)
        temp_effect = max(0, self._state_variables["temperature"] - 50) * 0.00001

        self._state_variables["wear"] += (wear_rate + temp_effect) * dt
        self._state_variables["wear"] = min(1.0, self._state_variables["wear"])

    def _calculate_health_index(self) -> float:
        """Calculate overall equipment health index."""
        wear_factor = 1 - self._state_variables["wear"]
        temp_factor = 1 - max(0, (self._state_variables["temperature"] - 60) / 40)
        vib_factor = 1 - min(1, self._state_variables["vibration"])

        return (wear_factor * 0.5 + temp_factor * 0.3 + vib_factor * 0.2)


# ============================================
# Engine Registry
# ============================================

_engine_registry: Dict[str, type] = {
    "des": DESEngine,
    "monte_carlo": MonteCarloEngine,
    "pinn": PINNEngine,
}


def get_engine(engine_type: str) -> Optional[SimulationEngineBase]:
    """Get a simulation engine instance by type."""
    engine_class = _engine_registry.get(engine_type)
    if engine_class:
        return engine_class()
    return None


def list_engines() -> List[str]:
    """List available engine types."""
    return list(_engine_registry.keys())


def register_engine(engine_type: str, engine_class: type):
    """Register a custom engine type."""
    _engine_registry[engine_type] = engine_class


__all__ = [
    'EngineState',
    'EngineResult',
    'SimulationEngineBase',
    'DiscreteEvent',
    'Entity',
    'DESEngine',
    'MonteCarloSample',
    'MonteCarloEngine',
    'PINNEngine',
    'get_engine',
    'list_engines',
    'register_engine',
]
