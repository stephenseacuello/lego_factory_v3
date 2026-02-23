"""
Digital Twin Engine - Core engine for managing digital twin instances.

ISO 23247 Digital Twin Domain Implementation:
- Twin instance lifecycle management
- State machine for operational states
- Behavior model execution (PINN, hybrid, rules)
- Real-time simulation and prediction
- Event-driven updates
- Multi-client synchronization

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import uuid
import logging
import asyncio
import threading
import queue
import json
import time
import numpy as np

from .ome_registry import (
    ObservableManufacturingElement,
    OMERegistry,
    OMEType,
    OMELifecycleState,
    get_ome_registry,
    DynamicAttributes
)

logger = logging.getLogger(__name__)


class TwinType(Enum):
    """Types of digital twin instances."""
    MONITORING = "monitoring"      # Real-time observation
    SIMULATION = "simulation"      # What-if analysis
    PREDICTIVE = "predictive"      # Failure/quality prediction
    OPTIMIZATION = "optimization"  # Process optimization
    TRAINING = "training"          # Operator training


class TwinState(Enum):
    """Operational states for a digital twin instance."""
    INITIALIZING = "initializing"
    SYNCING = "syncing"
    ACTIVE = "active"
    PAUSED = "paused"
    SIMULATING = "simulating"
    ERROR = "error"
    STOPPED = "stopped"


class SyncMode(Enum):
    """Synchronization modes between physical and digital."""
    REALTIME = "realtime"        # Continuous sync (<1s latency)
    PERIODIC = "periodic"        # Interval-based sync
    ON_DEMAND = "on_demand"      # Manual sync
    PLAYBACK = "playback"        # Historical replay


@dataclass
class SimulationConfig:
    """Configuration for simulation runs."""
    duration_seconds: float = 3600.0
    time_scale: float = 1.0  # 1.0 = real-time, 10.0 = 10x faster
    initial_state: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    record_interval_seconds: float = 1.0
    random_seed: Optional[int] = None


@dataclass
class SimulationResult:
    """Results from a simulation run."""
    simulation_id: str
    twin_id: str
    started_at: datetime
    completed_at: datetime
    duration_simulated: float
    final_state: Dict[str, Any]
    time_series: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    events: List[Dict[str, Any]]
    warnings: List[str]


@dataclass
class PredictionResult:
    """Results from predictive analytics."""
    prediction_type: str  # failure, quality, rul, throughput
    value: Any
    confidence: float  # 0-1
    prediction_time: datetime
    valid_until: datetime
    contributing_factors: List[Dict[str, Any]]
    recommendations: List[str]


class BehaviorModelInterface(ABC):
    """Abstract interface for behavior models."""

    @abstractmethod
    def predict(self, state: Dict[str, Any], dt: float) -> Dict[str, Any]:
        """Predict next state given current state and time delta."""
        pass

    @abstractmethod
    def get_constraints(self) -> List[Dict[str, Any]]:
        """Get physics/operational constraints."""
        pass


class RuleBasedModel(BehaviorModelInterface):
    """Simple rule-based behavior model."""

    def __init__(self, rules: List[Dict[str, Any]] = None):
        self.rules = rules or []

    def predict(self, state: Dict[str, Any], dt: float) -> Dict[str, Any]:
        new_state = state.copy()

        for rule in self.rules:
            condition = rule.get('condition', {})
            action = rule.get('action', {})

            if self._evaluate_condition(state, condition):
                self._apply_action(new_state, action)

        return new_state

    def _evaluate_condition(self, state: Dict, condition: Dict) -> bool:
        for key, check in condition.items():
            value = state.get(key)
            if isinstance(check, dict):
                if 'gt' in check and not (value > check['gt']):
                    return False
                if 'lt' in check and not (value < check['lt']):
                    return False
                if 'eq' in check and not (value == check['eq']):
                    return False
            elif value != check:
                return False
        return True

    def _apply_action(self, state: Dict, action: Dict):
        for key, value in action.items():
            state[key] = value

    def get_constraints(self) -> List[Dict[str, Any]]:
        return []

    def add_rule(self, condition: Dict, action: Dict, priority: int = 0):
        self.rules.append({
            'condition': condition,
            'action': action,
            'priority': priority
        })
        self.rules.sort(key=lambda r: r.get('priority', 0), reverse=True)


class PhysicsModel(BehaviorModelInterface):
    """Physics-based behavior model for manufacturing equipment."""

    def __init__(self, model_params: Dict[str, Any] = None):
        self.params = model_params or {}

        # Default physics parameters
        self.thermal_conductivity = self.params.get('thermal_conductivity', 0.1)
        self.cooling_rate = self.params.get('cooling_rate', 0.05)
        self.heating_rate = self.params.get('heating_rate', 0.2)
        self.ambient_temp = self.params.get('ambient_temp', 22.0)

    def predict(self, state: Dict[str, Any], dt: float) -> Dict[str, Any]:
        new_state = state.copy()

        # Temperature dynamics
        temps = state.get('temperatures', {})
        new_temps = {}

        for sensor, temp in temps.items():
            target = state.get('target_temperatures', {}).get(sensor, self.ambient_temp)
            heating = state.get('heating_active', False)

            if heating and temp < target:
                # Heating phase
                new_temp = temp + self.heating_rate * dt
                new_temp = min(new_temp, target)
            else:
                # Cooling toward ambient
                delta = temp - self.ambient_temp
                new_temp = temp - self.cooling_rate * delta * dt

            new_temps[sensor] = round(new_temp, 2)

        new_state['temperatures'] = new_temps

        # Position dynamics (linear interpolation toward target)
        positions = state.get('positions', {})
        targets = state.get('target_positions', {})
        speed = state.get('speed', 50.0)  # mm/s

        new_positions = {}
        for axis, pos in positions.items():
            target = targets.get(axis, pos)
            delta = target - pos
            max_move = speed * dt

            if abs(delta) <= max_move:
                new_positions[axis] = target
            else:
                new_positions[axis] = pos + (max_move if delta > 0 else -max_move)
            new_positions[axis] = round(new_positions[axis], 3)

        new_state['positions'] = new_positions

        # Power consumption estimation
        if state.get('status') == 'printing':
            # Base power + heating + motion
            base_power = 50  # watts
            heating_power = 200 if any(h for h in temps.values() if h > 40) else 0
            motion_power = 30 if any(
                p != targets.get(a, p) for a, p in positions.items()
            ) else 0
            new_state['power_consumption_watts'] = base_power + heating_power + motion_power
        else:
            new_state['power_consumption_watts'] = 10  # Standby

        return new_state

    def get_constraints(self) -> List[Dict[str, Any]]:
        return [
            {'type': 'temperature', 'max': 300, 'min': -10, 'unit': 'celsius'},
            {'type': 'position', 'max_speed': 200, 'unit': 'mm/s'},
            {'type': 'power', 'max': 500, 'unit': 'watts'}
        ]


@dataclass
class DigitalTwinInstance:
    """
    A digital twin instance for a specific OME.

    This is the runtime representation of a digital twin that:
    - Tracks current state
    - Executes behavior models
    - Handles synchronization with physical equipment
    - Provides prediction and simulation
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ome_id: str = ""
    twin_type: TwinType = TwinType.MONITORING
    state: TwinState = TwinState.INITIALIZING

    # Synchronization
    sync_mode: SyncMode = SyncMode.REALTIME
    sync_interval_ms: int = 1000
    last_sync_at: Optional[datetime] = None
    sync_lag_ms: float = 0.0

    # State data
    current_state: Dict[str, Any] = field(default_factory=dict)
    state_history: List[Dict[str, Any]] = field(default_factory=list)
    max_history_size: int = 10000

    # Behavior model
    behavior_model: Optional[BehaviorModelInterface] = None
    model_type: str = "none"

    # Predictions
    predictions: Dict[str, PredictionResult] = field(default_factory=dict)
    prediction_valid_seconds: int = 300

    # Event handlers
    on_state_change: Optional[Callable] = None
    on_alarm: Optional[Callable] = None
    on_prediction: Optional[Callable] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1

    # Performance metrics
    updates_per_second: float = 0.0
    total_updates: int = 0
    error_count: int = 0

    def update_state(self, new_data: Dict[str, Any], source: str = "sensor") -> bool:
        """Update twin state with new data."""
        try:
            old_state = self.current_state.copy()
            self.current_state.update(new_data)
            self.current_state['_last_update'] = datetime.utcnow().isoformat()
            self.current_state['_source'] = source

            # Track history
            self._add_to_history(self.current_state)

            self.updated_at = datetime.utcnow()
            self.total_updates += 1

            # Call event handler
            if self.on_state_change:
                self.on_state_change(self.id, old_state, self.current_state)

            return True

        except Exception as e:
            logger.error(f"Twin {self.id} state update error: {e}")
            self.error_count += 1
            return False

    def step(self, dt: float = 1.0) -> Dict[str, Any]:
        """Advance simulation by time step using behavior model."""
        if not self.behavior_model:
            return self.current_state

        try:
            predicted_state = self.behavior_model.predict(self.current_state, dt)
            self.update_state(predicted_state, source="simulation")
            return predicted_state
        except Exception as e:
            logger.error(f"Twin {self.id} simulation step error: {e}")
            self.error_count += 1
            return self.current_state

    def predict_future(self, horizon_seconds: float, steps: int = 100) -> List[Dict[str, Any]]:
        """Predict future states over given horizon."""
        if not self.behavior_model:
            return []

        dt = horizon_seconds / steps
        predictions = []
        state = self.current_state.copy()

        for i in range(steps):
            state = self.behavior_model.predict(state, dt)
            predictions.append({
                'time_offset': (i + 1) * dt,
                'state': state.copy()
            })

        return predictions

    def _add_to_history(self, state: Dict[str, Any]):
        """Add state to history with size limit."""
        self.state_history.append({
            'timestamp': datetime.utcnow().isoformat(),
            'state': state.copy()
        })

        if len(self.state_history) > self.max_history_size:
            self.state_history = self.state_history[-self.max_history_size:]

    def get_state_at(self, timestamp: datetime) -> Optional[Dict[str, Any]]:
        """Get state at specific timestamp from history."""
        for entry in reversed(self.state_history):
            entry_time = datetime.fromisoformat(entry['timestamp'])
            if entry_time <= timestamp:
                return entry['state']
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'ome_id': self.ome_id,
            'twin_type': self.twin_type.value,
            'state': self.state.value,
            'sync_mode': self.sync_mode.value,
            'sync_interval_ms': self.sync_interval_ms,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'sync_lag_ms': self.sync_lag_ms,
            'current_state': self.current_state,
            'model_type': self.model_type,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'version': self.version,
            'updates_per_second': self.updates_per_second,
            'total_updates': self.total_updates,
            'error_count': self.error_count
        }


class TwinEngine:
    """
    Core Digital Twin Engine managing all twin instances.

    Responsibilities:
    - Twin instance lifecycle management
    - State synchronization with physical equipment
    - Behavior model execution
    - Simulation orchestration
    - Prediction service
    - Event distribution to clients (Unity, dashboards)
    """

    def __init__(self, ome_registry: OMERegistry = None):
        self.registry = ome_registry or get_ome_registry()

        # Twin instances
        self._twins: Dict[str, DigitalTwinInstance] = {}
        self._ome_to_twins: Dict[str, List[str]] = {}  # ome_id -> list of twin_ids

        # Event listeners (for Unity, WebSocket clients, etc.)
        self._event_listeners: List[Callable] = []
        self._room_subscriptions: Dict[str, Set[str]] = {}  # room -> set of listener_ids

        # Simulation queue
        self._simulation_queue: queue.Queue = queue.Queue()
        self._active_simulations: Dict[str, Dict] = {}

        # Background sync thread
        self._sync_thread: Optional[threading.Thread] = None
        self._sync_running: bool = False
        self._sync_interval: float = 0.1  # 100ms default

        # Performance metrics
        self._metrics = {
            'twins_active': 0,
            'updates_per_second': 0,
            'simulations_running': 0,
            'total_events_emitted': 0
        }

        # Listen for OME registry events
        self.registry.add_event_listener(self._on_ome_event)

        logger.info("TwinEngine initialized")

    # ================== Twin Lifecycle ==================

    def create_twin(
        self,
        ome_id: str,
        twin_type: TwinType = TwinType.MONITORING,
        sync_mode: SyncMode = SyncMode.REALTIME,
        behavior_model: BehaviorModelInterface = None,
        initial_state: Dict[str, Any] = None
    ) -> DigitalTwinInstance:
        """Create a new digital twin instance for an OME."""
        ome = self.registry.get(ome_id)
        if not ome:
            raise ValueError(f"OME {ome_id} not found")

        twin = DigitalTwinInstance(
            ome_id=ome_id,
            twin_type=twin_type,
            sync_mode=sync_mode,
            behavior_model=behavior_model or PhysicsModel(),
            model_type="physics" if not behavior_model else getattr(behavior_model, 'model_type', 'custom')
        )

        # Initialize state from OME dynamic attributes
        twin.current_state = {
            'status': ome.dynamic_attributes.status,
            'temperatures': ome.dynamic_attributes.temperatures.copy(),
            'positions': ome.dynamic_attributes.positions.copy(),
            'speeds': ome.dynamic_attributes.speeds.copy(),
            'oee': ome.dynamic_attributes.oee,
            'health_score': ome.dynamic_attributes.health_score,
            'power_consumption_watts': ome.dynamic_attributes.power_consumption_watts,
            'current_job_id': ome.dynamic_attributes.current_job_id
        }

        if initial_state:
            twin.current_state.update(initial_state)

        twin.state = TwinState.SYNCING

        # Register twin
        self._twins[twin.id] = twin
        if ome_id not in self._ome_to_twins:
            self._ome_to_twins[ome_id] = []
        self._ome_to_twins[ome_id].append(twin.id)

        # Link twin to OME
        ome.twin_instance_ids.append(twin.id)

        # Transition to active
        twin.state = TwinState.ACTIVE
        twin.last_sync_at = datetime.utcnow()

        self._metrics['twins_active'] = len(self._twins)

        self._emit_event('twin_created', {
            'twin_id': twin.id,
            'ome_id': ome_id,
            'twin_type': twin_type.value
        })

        logger.info(f"Created twin {twin.id} for OME {ome_id}")

        return twin

    def get_twin(self, twin_id: str) -> Optional[DigitalTwinInstance]:
        """Get twin instance by ID."""
        return self._twins.get(twin_id)

    def get_twins_for_ome(self, ome_id: str) -> List[DigitalTwinInstance]:
        """Get all twin instances for an OME."""
        twin_ids = self._ome_to_twins.get(ome_id, [])
        return [self._twins[tid] for tid in twin_ids if tid in self._twins]

    def get_all_twins(self) -> List[DigitalTwinInstance]:
        """Get all twin instances."""
        return list(self._twins.values())

    def get_active_twins(self) -> List[DigitalTwinInstance]:
        """Get all active twin instances."""
        return [t for t in self._twins.values() if t.state == TwinState.ACTIVE]

    def delete_twin(self, twin_id: str) -> bool:
        """Delete a twin instance."""
        if twin_id not in self._twins:
            return False

        twin = self._twins[twin_id]

        # Remove from OME
        ome = self.registry.get(twin.ome_id)
        if ome and twin_id in ome.twin_instance_ids:
            ome.twin_instance_ids.remove(twin_id)

        # Remove from indexes
        if twin.ome_id in self._ome_to_twins:
            self._ome_to_twins[twin.ome_id].remove(twin_id)

        del self._twins[twin_id]

        self._metrics['twins_active'] = len(self._twins)

        self._emit_event('twin_deleted', {'twin_id': twin_id})

        logger.info(f"Deleted twin {twin_id}")

        return True

    def pause_twin(self, twin_id: str) -> bool:
        """Pause a twin instance."""
        twin = self._twins.get(twin_id)
        if not twin or twin.state != TwinState.ACTIVE:
            return False

        twin.state = TwinState.PAUSED
        self._emit_event('twin_paused', {'twin_id': twin_id})
        return True

    def resume_twin(self, twin_id: str) -> bool:
        """Resume a paused twin instance."""
        twin = self._twins.get(twin_id)
        if not twin or twin.state != TwinState.PAUSED:
            return False

        twin.state = TwinState.ACTIVE
        twin.last_sync_at = datetime.utcnow()
        self._emit_event('twin_resumed', {'twin_id': twin_id})
        return True

    # ================== State Synchronization ==================

    def sync_from_physical(self, ome_id: str, sensor_data: Dict[str, Any]) -> bool:
        """
        Sync physical sensor data to digital twin(s).

        This is the Physical -> Digital sync direction.
        """
        twins = self.get_twins_for_ome(ome_id)

        if not twins:
            logger.debug(f"No twins for OME {ome_id}, skipping sync")
            return False

        # Also update OME dynamic attributes
        ome = self.registry.get(ome_id)
        if ome:
            self.registry.update_dynamic_attributes(ome_id, sensor_data)

        for twin in twins:
            if twin.state == TwinState.ACTIVE and twin.sync_mode == SyncMode.REALTIME:
                sync_start = time.time()
                twin.update_state(sensor_data, source="physical")
                twin.sync_lag_ms = (time.time() - sync_start) * 1000
                twin.last_sync_at = datetime.utcnow()

        self._emit_event('state_synced', {
            'ome_id': ome_id,
            'twin_count': len(twins),
            'data': sensor_data
        })

        return True

    def sync_to_physical(self, twin_id: str, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send command from digital twin to physical equipment.

        This is the Digital -> Physical sync direction.
        Returns command result/acknowledgment.
        """
        twin = self._twins.get(twin_id)
        if not twin:
            return {'success': False, 'error': 'Twin not found'}

        if twin.state != TwinState.ACTIVE:
            return {'success': False, 'error': f'Twin not active: {twin.state.value}'}

        # Get OME to find physical equipment connection
        ome = self.registry.get(twin.ome_id)
        if not ome or ome.lifecycle_state != OMELifecycleState.ACTIVE:
            return {'success': False, 'error': 'OME not active'}

        # Here we would send command to actual equipment
        # For now, emit event for external handler
        self._emit_event('command_to_physical', {
            'twin_id': twin_id,
            'ome_id': twin.ome_id,
            'command': command,
            'timestamp': datetime.utcnow().isoformat()
        })

        # Optimistic update of twin state
        twin.update_state(command, source="command")

        return {'success': True, 'command': command}

    def start_sync_loop(self, interval_seconds: float = 0.1):
        """Start background synchronization loop."""
        if self._sync_running:
            return

        self._sync_interval = interval_seconds
        self._sync_running = True

        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()

        logger.info(f"Started sync loop with {interval_seconds}s interval")

    def stop_sync_loop(self):
        """Stop background synchronization loop."""
        self._sync_running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=2.0)

        logger.info("Stopped sync loop")

    def _sync_loop(self):
        """Background loop for periodic sync and simulation steps."""
        last_time = time.time()
        update_count = 0
        last_metric_time = time.time()

        while self._sync_running:
            try:
                current_time = time.time()
                dt = current_time - last_time
                last_time = current_time

                for twin in list(self._twins.values()):
                    if twin.state == TwinState.ACTIVE:
                        # For simulation-type twins, step the model
                        if twin.twin_type in [TwinType.SIMULATION, TwinType.PREDICTIVE]:
                            twin.step(dt)
                            update_count += 1

                        # Check periodic sync
                        if twin.sync_mode == SyncMode.PERIODIC:
                            if twin.last_sync_at:
                                elapsed_ms = (current_time - twin.last_sync_at.timestamp()) * 1000
                                if elapsed_ms >= twin.sync_interval_ms:
                                    # Emit sync request event
                                    self._emit_event('sync_requested', {
                                        'twin_id': twin.id,
                                        'ome_id': twin.ome_id
                                    })

                # Update metrics every second
                if current_time - last_metric_time >= 1.0:
                    self._metrics['updates_per_second'] = update_count
                    update_count = 0
                    last_metric_time = current_time

                time.sleep(self._sync_interval)

            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                time.sleep(1.0)

    # ================== Simulation ==================

    def run_simulation(
        self,
        twin_id: str,
        config: SimulationConfig
    ) -> SimulationResult:
        """Run a simulation on a twin instance."""
        twin = self._twins.get(twin_id)
        if not twin:
            raise ValueError(f"Twin {twin_id} not found")

        simulation_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        # Create simulation twin copy
        sim_twin = DigitalTwinInstance(
            id=simulation_id,
            ome_id=twin.ome_id,
            twin_type=TwinType.SIMULATION,
            state=TwinState.SIMULATING,
            behavior_model=twin.behavior_model,
            current_state=config.initial_state or twin.current_state.copy()
        )

        # Apply config parameters
        sim_twin.current_state.update(config.parameters)

        # Set random seed if provided
        if config.random_seed:
            np.random.seed(config.random_seed)

        # Run simulation
        time_series = []
        events = []
        warnings = []

        sim_time = 0.0
        dt = 1.0 / config.time_scale

        while sim_time < config.duration_seconds:
            # Step simulation
            old_state = sim_twin.current_state.copy()
            sim_twin.step(dt)
            sim_time += dt

            # Record at interval
            if len(time_series) == 0 or sim_time - time_series[-1].get('time', 0) >= config.record_interval_seconds:
                time_series.append({
                    'time': sim_time,
                    'state': sim_twin.current_state.copy()
                })

            # Check for events (alarms, thresholds)
            self._check_simulation_events(sim_twin, old_state, events, warnings, sim_time)

        completed_at = datetime.utcnow()

        # Calculate metrics
        metrics = self._calculate_simulation_metrics(time_series)

        result = SimulationResult(
            simulation_id=simulation_id,
            twin_id=twin_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_simulated=config.duration_seconds,
            final_state=sim_twin.current_state,
            time_series=time_series,
            metrics=metrics,
            events=events,
            warnings=warnings
        )

        self._emit_event('simulation_completed', {
            'simulation_id': simulation_id,
            'twin_id': twin_id,
            'duration': config.duration_seconds,
            'metrics': metrics
        })

        return result

    def _check_simulation_events(
        self,
        twin: DigitalTwinInstance,
        old_state: Dict,
        events: List,
        warnings: List,
        sim_time: float
    ):
        """Check for events during simulation."""
        # Temperature thresholds
        for sensor, temp in twin.current_state.get('temperatures', {}).items():
            old_temp = old_state.get('temperatures', {}).get(sensor, 0)

            if temp > 280 and old_temp <= 280:
                events.append({
                    'time': sim_time,
                    'type': 'alarm',
                    'message': f'{sensor} temperature exceeded 280°C',
                    'value': temp
                })
                warnings.append(f"High temperature warning at {sim_time:.1f}s")

            if temp > 300:
                warnings.append(f"Critical temperature ({temp}°C) at {sim_time:.1f}s")

        # Health score degradation
        health = twin.current_state.get('health_score', 100)
        old_health = old_state.get('health_score', 100)

        if health < 50 and old_health >= 50:
            events.append({
                'time': sim_time,
                'type': 'maintenance_due',
                'message': 'Health score below 50%',
                'value': health
            })

    def _calculate_simulation_metrics(self, time_series: List[Dict]) -> Dict[str, Any]:
        """Calculate summary metrics from simulation time series."""
        if not time_series:
            return {}

        temps = []
        powers = []
        oees = []

        for entry in time_series:
            state = entry.get('state', {})
            temps.extend(state.get('temperatures', {}).values())
            powers.append(state.get('power_consumption_watts', 0))
            if 'oee' in state:
                oees.append(state['oee'])

        return {
            'avg_temperature': sum(temps) / len(temps) if temps else 0,
            'max_temperature': max(temps) if temps else 0,
            'min_temperature': min(temps) if temps else 0,
            'total_energy_kwh': sum(powers) * len(time_series) / 3600000,
            'avg_oee': sum(oees) / len(oees) if oees else 0,
            'data_points': len(time_series)
        }

    # ================== Prediction ==================

    def predict_failure(self, twin_id: str, horizon_hours: float = 24) -> PredictionResult:
        """Predict failure probability within time horizon."""
        twin = self._twins.get(twin_id)
        if not twin:
            raise ValueError(f"Twin {twin_id} not found")

        # Get OME for additional context
        ome = self.registry.get(twin.ome_id)

        # Use behavior model for prediction if available
        future_states = twin.predict_future(horizon_hours * 3600, steps=100)

        # Analyze trends for failure indicators
        failure_probability = 0.0
        contributing_factors = []

        # Temperature trend
        if future_states:
            max_temp = max(
                max(s['state'].get('temperatures', {}).values() or [0])
                for s in future_states
            )
            if max_temp > 280:
                failure_probability += 0.3
                contributing_factors.append({
                    'factor': 'temperature_trend',
                    'severity': 'high',
                    'predicted_max': max_temp
                })

        # Health score trend
        current_health = twin.current_state.get('health_score', 100)
        if current_health < 70:
            failure_probability += 0.2
            contributing_factors.append({
                'factor': 'low_health_score',
                'severity': 'medium',
                'current_value': current_health
            })

        # RUL-based prediction
        rul = ome.dynamic_attributes.remaining_useful_life_hours if ome else None
        if rul and rul < horizon_hours:
            failure_probability += 0.4
            contributing_factors.append({
                'factor': 'rul_expiring',
                'severity': 'high',
                'hours_remaining': rul
            })

        # Normalize probability
        failure_probability = min(failure_probability, 1.0)

        # Generate recommendations
        recommendations = []
        if failure_probability > 0.7:
            recommendations.append("Schedule immediate maintenance")
        elif failure_probability > 0.4:
            recommendations.append("Plan maintenance within 24 hours")
        elif failure_probability > 0.2:
            recommendations.append("Monitor closely, consider preventive maintenance")

        result = PredictionResult(
            prediction_type='failure',
            value=failure_probability,
            confidence=0.85,  # Would come from ML model
            prediction_time=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(hours=1),
            contributing_factors=contributing_factors,
            recommendations=recommendations
        )

        # Cache prediction
        twin.predictions['failure'] = result

        self._emit_event('prediction_generated', {
            'twin_id': twin_id,
            'type': 'failure',
            'probability': failure_probability,
            'horizon_hours': horizon_hours
        })

        return result

    def predict_quality(self, twin_id: str, job_params: Dict[str, Any] = None) -> PredictionResult:
        """Predict quality outcome for a job."""
        twin = self._twins.get(twin_id)
        if not twin:
            raise ValueError(f"Twin {twin_id} not found")

        # Factors affecting quality
        quality_score = 100.0
        factors = []

        # Temperature stability
        temps = twin.current_state.get('temperatures', {})
        if temps:
            temp_variance = np.var(list(temps.values())) if len(temps) > 1 else 0
            if temp_variance > 5:
                quality_score -= 10
                factors.append({
                    'factor': 'temperature_variance',
                    'impact': -10,
                    'value': temp_variance
                })

        # Equipment health
        health = twin.current_state.get('health_score', 100)
        if health < 80:
            impact = (100 - health) * 0.2
            quality_score -= impact
            factors.append({
                'factor': 'equipment_health',
                'impact': -impact,
                'value': health
            })

        # Historical quality rate
        ome = self.registry.get(twin.ome_id)
        if ome:
            hist_quality = ome.dynamic_attributes.quality
            if hist_quality < 0.95:
                impact = (0.95 - hist_quality) * 100
                quality_score -= impact
                factors.append({
                    'factor': 'historical_quality',
                    'impact': -impact,
                    'value': hist_quality
                })

        quality_score = max(0, min(100, quality_score))

        recommendations = []
        if quality_score < 90:
            recommendations.append("Check and calibrate equipment before production")
        if any(f['factor'] == 'temperature_variance' for f in factors):
            recommendations.append("Allow temperature to stabilize before starting")

        result = PredictionResult(
            prediction_type='quality',
            value=quality_score / 100,  # As probability of good quality
            confidence=0.8,
            prediction_time=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(minutes=30),
            contributing_factors=factors,
            recommendations=recommendations
        )

        twin.predictions['quality'] = result

        return result

    def estimate_rul(self, twin_id: str) -> PredictionResult:
        """Estimate Remaining Useful Life for equipment."""
        twin = self._twins.get(twin_id)
        if not twin:
            raise ValueError(f"Twin {twin_id} not found")

        ome = self.registry.get(twin.ome_id)

        # Base RUL estimation
        current_health = twin.current_state.get('health_score', 100)

        # Simple linear degradation model
        # Assumes health degrades from 100 to 0 over 10000 hours
        base_rul_hours = (current_health / 100) * 10000

        # Adjust based on usage patterns
        cycles_total = ome.dynamic_attributes.cycles_total if ome else 0
        if cycles_total > 50000:
            base_rul_hours *= 0.8  # Heavy use adjustment

        factors = [
            {'factor': 'current_health', 'value': current_health},
            {'factor': 'total_cycles', 'value': cycles_total}
        ]

        recommendations = []
        if base_rul_hours < 100:
            recommendations.append("Critical: Schedule replacement immediately")
        elif base_rul_hours < 500:
            recommendations.append("Plan replacement in next maintenance window")
        elif base_rul_hours < 2000:
            recommendations.append("Order spare parts proactively")

        result = PredictionResult(
            prediction_type='rul',
            value=base_rul_hours,
            confidence=0.75,
            prediction_time=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(hours=24),
            contributing_factors=factors,
            recommendations=recommendations
        )

        twin.predictions['rul'] = result

        # Update OME
        if ome:
            ome.dynamic_attributes.remaining_useful_life_hours = base_rul_hours

        return result

    # ================== Event System ==================

    def add_event_listener(self, callback: Callable, rooms: List[str] = None):
        """Add event listener, optionally for specific rooms."""
        listener_id = str(uuid.uuid4())

        if rooms:
            for room in rooms:
                if room not in self._room_subscriptions:
                    self._room_subscriptions[room] = set()
                self._room_subscriptions[room].add(listener_id)

        self._event_listeners.append((listener_id, callback))
        return listener_id

    def remove_event_listener(self, listener_id: str):
        """Remove event listener."""
        self._event_listeners = [
            (lid, cb) for lid, cb in self._event_listeners if lid != listener_id
        ]
        for room in self._room_subscriptions.values():
            room.discard(listener_id)

    def _emit_event(self, event_type: str, data: Any, room: str = None):
        """Emit event to listeners."""
        event = {
            'type': event_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }

        self._metrics['total_events_emitted'] += 1

        for listener_id, callback in self._event_listeners:
            try:
                # If room specified, check subscription
                if room:
                    if listener_id not in self._room_subscriptions.get(room, set()):
                        continue
                callback(event)
            except Exception as e:
                logger.error(f"Event listener error: {e}")

    def _on_ome_event(self, event_type: str, data: Any):
        """Handle events from OME registry."""
        # Forward relevant events to twin engine listeners
        if event_type == 'ome_dynamic_updated':
            ome = data
            if isinstance(ome, ObservableManufacturingElement):
                # Sync to twins
                self.sync_from_physical(ome.id, ome.dynamic_attributes.to_dict())

    # ================== Unity Integration ==================

    def get_scene_state(self, namespace: str = "default") -> Dict[str, Any]:
        """Get complete scene state for Unity visualization."""
        scene_data = self.registry.get_unity_scene_data(namespace)

        # Add twin instance data
        twin_data = []
        for twin in self._twins.values():
            ome = self.registry.get(twin.ome_id)
            if ome and ome.namespace == namespace:
                twin_data.append({
                    'id': twin.id,
                    'ome_id': twin.ome_id,
                    'state': twin.state.value,
                    'sync_mode': twin.sync_mode.value,
                    'sync_lag_ms': twin.sync_lag_ms,
                    'current_state': twin.current_state,
                    'predictions': {
                        k: {
                            'type': v.prediction_type,
                            'value': v.value,
                            'confidence': v.confidence
                        }
                        for k, v in twin.predictions.items()
                    }
                })

        scene_data['twins'] = twin_data
        scene_data['engine_metrics'] = self._metrics

        return scene_data

    def get_delta_state(
        self,
        since_timestamp: datetime,
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """Get only changes since timestamp for efficient Unity updates."""
        changes = {
            'timestamp': datetime.utcnow().isoformat(),
            'since': since_timestamp.isoformat(),
            'equipment_updates': [],
            'twin_updates': [],
            'events': []
        }

        for twin in self._twins.values():
            if twin.updated_at > since_timestamp:
                ome = self.registry.get(twin.ome_id)
                if ome and ome.namespace == namespace:
                    changes['twin_updates'].append({
                        'twin_id': twin.id,
                        'ome_id': twin.ome_id,
                        'state': twin.current_state
                    })

        return changes

    # ================== Metrics ==================

    def get_metrics(self) -> Dict[str, Any]:
        """Get engine performance metrics."""
        return {
            **self._metrics,
            'twins_by_type': {
                tt.value: len([t for t in self._twins.values() if t.twin_type == tt])
                for tt in TwinType
            },
            'twins_by_state': {
                ts.value: len([t for t in self._twins.values() if t.state == ts])
                for ts in TwinState
            },
            'total_omes': len(self.registry.get_all()),
            'sync_running': self._sync_running
        }


# Singleton instance
_engine_instance: Optional[TwinEngine] = None


def get_twin_engine() -> TwinEngine:
    """Get the global TwinEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = TwinEngine()
    return _engine_instance
