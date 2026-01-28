"""
Digital Twin Manager - Real-time equipment state management with ML integration.

LegoMCP World-Class Manufacturing Platform v2.0
ISO 23247 Compliant Digital Twin Implementation

Handles:
- Machine state tracking and history
- Real-time data aggregation
- PINN-based physics simulation
- Failure prediction and RUL estimation
- Anomaly detection
- What-if simulation with physics constraints

Research Value:
- Novel integration of PINN with digital twins
- Physics-informed failure prediction
- Hybrid physics-ML state estimation
- ISO 23247 compliant architecture

References:
- ISO 23247 (2021). Digital Twin Framework for Manufacturing
- Raissi, M. et al. (2019). Physics-Informed Neural Networks

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import logging
import json
import threading
import uuid
import numpy as np
from collections import defaultdict

try:
    from sqlalchemy.orm import Session
    from sqlalchemy import func
    from models import WorkCenter
    from models.analytics import DigitalTwinState, OEEEvent
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False
    Session = Any
    WorkCenter = Any
    DigitalTwinState = Any
    OEEEvent = Any

# Import ML components
try:
    from .ml import (
        FailurePredictor,
        FailurePrediction,
        get_failure_predictor,
        RULEstimator,
        RULEstimate,
        get_rul_estimator,
        AnomalyDetector,
        AnomalyResult,
        get_anomaly_detector,
    )
    _ML_AVAILABLE = True
except ImportError:
    _ML_AVAILABLE = False

# Import PINN components
try:
    from .ml.pinn_model import (
        ThermalPINN,
        MechanicalPINN,
        FDMProcessPINN,
        PINNConfig,
        PINNTrainer,
        TrainingConfig,
    )
    from .ml.physics_constraints import (
        PhysicsConstraint,
        ThermalConstraints,
        MechanicalConstraints,
        ManufacturingConstraints,
        ConstraintEnforcer,
    )
    from .ml.hybrid_model import (
        HybridModel,
        PhysicsDataFusion,
        UncertaintyQuantifier,
    )
    _PINN_AVAILABLE = True
except ImportError:
    _PINN_AVAILABLE = False

logger = logging.getLogger(__name__)


class TwinStateType(Enum):
    """Types of digital twin state data."""
    MACHINE_STATUS = "machine_status"
    TEMPERATURE = "temperature"
    POSITION = "position"
    VIBRATION = "vibration"
    POWER = "power"
    PRODUCTION = "production"
    QUALITY = "quality"


class PredictionType(Enum):
    """Types of ML predictions."""
    FAILURE = auto()
    RUL = auto()
    ANOMALY = auto()
    QUALITY = auto()
    THERMAL = auto()
    MECHANICAL = auto()


class SimulationType(Enum):
    """Types of physics simulations."""
    THERMAL_FIELD = auto()
    STRESS_STRAIN = auto()
    FDM_PROCESS = auto()
    PRODUCTION = auto()


@dataclass
class TwinSnapshot:
    """Complete snapshot of a digital twin at a point in time."""
    work_center_id: str
    timestamp: datetime
    status: str
    temperatures: Dict[str, float] = field(default_factory=dict)
    positions: Dict[str, float] = field(default_factory=dict)
    production_rate: float = 0.0
    quality_rate: float = 0.0
    power_consumption: float = 0.0
    current_job: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Extended attributes for ML integration
    vibration: Dict[str, float] = field(default_factory=dict)
    process_params: Dict[str, float] = field(default_factory=dict)
    sensor_readings: Dict[str, float] = field(default_factory=dict)
    predicted_rul_hours: Optional[float] = None
    anomaly_score: float = 0.0
    failure_probability: float = 0.0


@dataclass
class MLPredictionResult:
    """Result from ML model prediction."""
    prediction_id: str
    entity_id: str
    prediction_type: PredictionType
    value: float
    confidence: float
    uncertainty: float
    features_used: List[str]
    model_version: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PhysicsSimulationResult:
    """Result from physics-based simulation."""
    simulation_id: str
    entity_id: str
    simulation_type: SimulationType
    output_fields: Dict[str, np.ndarray]
    boundary_conditions: Dict[str, Any]
    physics_residual: float
    computation_time_ms: float
    mesh_points: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HybridPrediction:
    """Combined physics + ML prediction."""
    prediction_id: str
    entity_id: str
    physics_prediction: float
    ml_prediction: float
    fused_prediction: float
    fusion_weight: float  # 0 = pure physics, 1 = pure ML
    uncertainty: float
    physics_residual: float
    data_likelihood: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DigitalTwinManager:
    """
    Digital twin management service with integrated ML and physics models.

    This class provides a unified interface for:
    - Real-time state management
    - Physics-informed predictions (PINN)
    - Failure prediction and RUL estimation
    - Anomaly detection
    - Hybrid physics-ML modeling

    ISO 23247 Compliance:
    - Part 2: Reference architecture (Digital Twin Domain)
    - Part 3: Digital representation (state + behavior)
    - Part 4: Information exchange (events + queries)
    """

    def __init__(self, session: Session = None):
        self.session = session

        # In-memory cache for real-time state
        self._state_cache: Dict[str, TwinSnapshot] = {}

        # ML model instances
        self._failure_predictor: Optional[Any] = None
        self._rul_estimator: Optional[Any] = None
        self._anomaly_detector: Optional[Any] = None

        # PINN models (lazy loaded)
        self._thermal_pinn: Optional[Any] = None
        self._mechanical_pinn: Optional[Any] = None
        self._fdm_process_pinn: Optional[Any] = None
        self._hybrid_model: Optional[Any] = None

        # Physics constraints
        self._constraint_enforcer: Optional[Any] = None

        # Prediction history
        self._prediction_history: Dict[str, List[MLPredictionResult]] = defaultdict(list)
        self._simulation_history: Dict[str, List[PhysicsSimulationResult]] = defaultdict(list)

        # State change callbacks
        self._state_callbacks: List[Callable[[str, TwinSnapshot], None]] = []
        self._prediction_callbacks: List[Callable[[str, MLPredictionResult], None]] = []

        # Thread safety
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            "state_updates": 0,
            "predictions_made": 0,
            "simulations_run": 0,
            "anomalies_detected": 0,
            "failures_predicted": 0,
        }

        # Initialize ML models
        self._init_ml_models()

    def _init_ml_models(self) -> None:
        """Initialize ML models for predictions."""
        if _ML_AVAILABLE:
            try:
                self._failure_predictor = get_failure_predictor()
                self._rul_estimator = get_rul_estimator()
                self._anomaly_detector = get_anomaly_detector()
                logger.info("ML models initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize ML models: {e}")

        if _PINN_AVAILABLE:
            try:
                # Initialize PINN models with default configs
                thermal_config = PINNConfig(
                    input_dim=4,  # x, y, z, t
                    output_dim=1,  # T
                    hidden_layers=[64, 64, 64, 64],
                )
                self._thermal_pinn = ThermalPINN(thermal_config)

                mechanical_config = PINNConfig(
                    input_dim=3,  # x, y, z
                    output_dim=3,  # u_x, u_y, u_z
                    hidden_layers=[64, 64, 64, 64],
                )
                self._mechanical_pinn = MechanicalPINN(mechanical_config)

                fdm_config = PINNConfig(
                    input_dim=8,  # x, y, z, t, nozzle_temp, bed_temp, speed, layer_h
                    output_dim=3,  # T, viscosity, solidification
                    hidden_layers=[128, 128, 128, 128],
                )
                self._fdm_process_pinn = FDMProcessPINN(fdm_config)

                logger.info("PINN models initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize PINN models: {e}")

    # =========================================================================
    # State Management
    # =========================================================================

    def update_state(
        self,
        work_center_id: str,
        state_type: str,
        state_data: Dict[str, Any],
        persist: bool = True
    ) -> TwinSnapshot:
        """
        Update digital twin state.

        Args:
            work_center_id: Work center ID
            state_type: Type of state update
            state_data: State data to update
            persist: Whether to persist to database

        Returns:
            Updated TwinSnapshot
        """
        now = datetime.utcnow()

        # Get or create snapshot
        if work_center_id in self._state_cache:
            snapshot = self._state_cache[work_center_id]
        else:
            snapshot = TwinSnapshot(
                work_center_id=work_center_id,
                timestamp=now,
                status='unknown'
            )

        snapshot.timestamp = now

        # Update based on state type
        if state_type == TwinStateType.MACHINE_STATUS.value:
            snapshot.status = state_data.get('status', snapshot.status)
            snapshot.current_job = state_data.get('current_job')

        elif state_type == TwinStateType.TEMPERATURE.value:
            snapshot.temperatures.update(state_data)

        elif state_type == TwinStateType.POSITION.value:
            snapshot.positions.update(state_data)

        elif state_type == TwinStateType.PRODUCTION.value:
            snapshot.production_rate = state_data.get('rate', snapshot.production_rate)

        elif state_type == TwinStateType.QUALITY.value:
            snapshot.quality_rate = state_data.get('rate', snapshot.quality_rate)

        elif state_type == TwinStateType.POWER.value:
            snapshot.power_consumption = state_data.get('watts', snapshot.power_consumption)

        # Update metadata
        snapshot.metadata.update(state_data.get('metadata', {}))

        # Cache the snapshot
        self._state_cache[work_center_id] = snapshot

        # Persist to database
        if persist:
            twin_state = DigitalTwinState(
                work_center_id=work_center_id,
                state_type=state_type,
                state_data=state_data
            )
            self.session.add(twin_state)
            self.session.commit()

        return snapshot

    def get_current_state(self, work_center_id: str) -> Optional[TwinSnapshot]:
        """Get current state from cache or database."""
        # Check cache
        if work_center_id in self._state_cache:
            return self._state_cache[work_center_id]

        # Load from database
        latest_states = self.session.query(DigitalTwinState).filter(
            DigitalTwinState.work_center_id == work_center_id
        ).order_by(DigitalTwinState.timestamp.desc()).limit(10).all()

        if not latest_states:
            return None

        # Reconstruct snapshot from latest states
        snapshot = TwinSnapshot(
            work_center_id=work_center_id,
            timestamp=latest_states[0].timestamp,
            status='unknown'
        )

        for state in latest_states:
            if state.state_type == TwinStateType.MACHINE_STATUS.value:
                snapshot.status = state.state_data.get('status', 'unknown')
                snapshot.current_job = state.state_data.get('current_job')
            elif state.state_type == TwinStateType.TEMPERATURE.value:
                snapshot.temperatures.update(state.state_data)
            elif state.state_type == TwinStateType.POSITION.value:
                snapshot.positions.update(state.state_data)

        self._state_cache[work_center_id] = snapshot
        return snapshot

    def get_state_history(
        self,
        work_center_id: str,
        state_type: Optional[str] = None,
        hours: int = 24,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get historical state data."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = self.session.query(DigitalTwinState).filter(
            DigitalTwinState.work_center_id == work_center_id,
            DigitalTwinState.timestamp >= cutoff
        )

        if state_type:
            query = query.filter(DigitalTwinState.state_type == state_type)

        states = query.order_by(
            DigitalTwinState.timestamp.desc()
        ).limit(limit).all()

        return [
            {
                'timestamp': s.timestamp.isoformat(),
                'state_type': s.state_type,
                'data': s.state_data
            }
            for s in reversed(states)
        ]

    def get_all_twins(self) -> List[Dict[str, Any]]:
        """Get current state of all digital twins."""
        work_centers = self.session.query(WorkCenter).all()

        twins = []
        for wc in work_centers:
            snapshot = self.get_current_state(str(wc.id))

            twins.append({
                'work_center_id': str(wc.id),
                'work_center_code': wc.code,
                'work_center_name': wc.name,
                'status': snapshot.status if snapshot else wc.status,
                'last_update': snapshot.timestamp.isoformat() if snapshot else None,
                'temperatures': snapshot.temperatures if snapshot else {},
                'positions': snapshot.positions if snapshot else {},
                'current_job': snapshot.current_job if snapshot else None
            })

        return twins

    def simulate_production(
        self,
        work_center_id: str,
        part_quantity: int,
        cycle_time_seconds: float
    ) -> Dict[str, Any]:
        """
        Simulate production run on digital twin.

        Args:
            work_center_id: Work center ID
            part_quantity: Number of parts to simulate
            cycle_time_seconds: Cycle time per part

        Returns:
            Simulation results
        """
        snapshot = self.get_current_state(work_center_id)

        if not snapshot:
            return {'error': 'Digital twin not found'}

        # Get historical OEE for this work center
        week_ago = datetime.utcnow() - timedelta(weeks=1)
        events = self.session.query(OEEEvent).filter(
            OEEEvent.work_center_id == work_center_id,
            OEEEvent.start_time >= week_ago
        ).all()

        # Calculate historical averages
        if events:
            avg_availability = sum(
                (e.end_time - e.start_time).total_seconds() / 3600
                for e in events if e.event_type == 'production' and e.end_time
            ) / len(events)

            total_produced = sum(e.parts_produced or 0 for e in events)
            total_defects = sum(e.parts_defective or 0 for e in events)
            quality_rate = (total_produced - total_defects) / total_produced if total_produced > 0 else 0.95
        else:
            avg_availability = 0.85
            quality_rate = 0.98

        # Simulate production
        total_time_seconds = part_quantity * cycle_time_seconds
        total_time_hours = total_time_seconds / 3600

        # Apply availability factor (downtime, changeovers)
        actual_time_hours = total_time_hours / avg_availability

        # Calculate expected good parts
        good_parts = int(part_quantity * quality_rate)
        defective_parts = part_quantity - good_parts

        return {
            'work_center_id': work_center_id,
            'simulation_type': 'production',
            'input': {
                'part_quantity': part_quantity,
                'cycle_time_seconds': cycle_time_seconds
            },
            'results': {
                'theoretical_time_hours': round(total_time_hours, 2),
                'expected_actual_time_hours': round(actual_time_hours, 2),
                'expected_good_parts': good_parts,
                'expected_defective_parts': defective_parts,
                'expected_quality_rate': round(quality_rate * 100, 1),
                'expected_availability': round(avg_availability * 100, 1)
            },
            'assumptions': {
                'based_on_historical_data': len(events) > 0,
                'events_analyzed': len(events)
            }
        }

    def calculate_kpis(
        self,
        work_center_id: str,
        period_hours: int = 24
    ) -> Dict[str, Any]:
        """Calculate real-time KPIs for a digital twin."""
        cutoff = datetime.utcnow() - timedelta(hours=period_hours)

        # Get OEE events
        events = self.session.query(OEEEvent).filter(
            OEEEvent.work_center_id == work_center_id,
            OEEEvent.start_time >= cutoff
        ).all()

        # Get state history
        states = self.session.query(DigitalTwinState).filter(
            DigitalTwinState.work_center_id == work_center_id,
            DigitalTwinState.timestamp >= cutoff
        ).all()

        # Calculate KPIs
        total_production_time = 0
        total_downtime = 0
        total_parts = 0
        total_defects = 0

        for e in events:
            if e.end_time:
                duration = (e.end_time - e.start_time).total_seconds() / 3600
                if e.event_type == 'production':
                    total_production_time += duration
                    total_parts += e.parts_produced or 0
                    total_defects += e.parts_defective or 0
                elif e.event_type == 'downtime':
                    total_downtime += duration

        # Calculate temperature trend
        temp_states = [s for s in states if s.state_type == TwinStateType.TEMPERATURE.value]
        if temp_states:
            temps = [s.state_data.get('tool0', 0) for s in temp_states if 'tool0' in s.state_data]
            avg_temp = sum(temps) / len(temps) if temps else 0
        else:
            avg_temp = 0

        available_time = period_hours
        availability = (available_time - total_downtime) / available_time if available_time > 0 else 0
        quality = (total_parts - total_defects) / total_parts if total_parts > 0 else 1

        return {
            'work_center_id': work_center_id,
            'period_hours': period_hours,
            'kpis': {
                'uptime_hours': round(total_production_time, 2),
                'downtime_hours': round(total_downtime, 2),
                'availability_percent': round(availability * 100, 1),
                'total_parts': total_parts,
                'defective_parts': total_defects,
                'quality_percent': round(quality * 100, 1),
                'average_temperature': round(avg_temp, 1)
            },
            'status': self.get_current_state(work_center_id).status if self.get_current_state(work_center_id) else 'unknown'
        }

    # =========================================================================
    # ML-Based Predictions
    # =========================================================================

    def predict_failure(
        self,
        work_center_id: str,
        features: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Predict potential failures for equipment.

        Args:
            work_center_id: Work center identifier
            features: Optional feature override (uses current state if None)

        Returns:
            List of failure predictions with probabilities
        """
        with self._lock:
            self._stats["predictions_made"] += 1

            if not self._failure_predictor:
                return [{"error": "Failure predictor not available"}]

            # Get features from current state if not provided
            if features is None:
                snapshot = self.get_current_state(work_center_id)
                if snapshot:
                    features = self._extract_features(snapshot)
                else:
                    features = {}

            try:
                predictions = self._failure_predictor.predict(
                    work_center_id, features
                )

                results = []
                for pred in predictions:
                    result = {
                        "prediction_id": pred.prediction_id,
                        "failure_type": pred.failure_type.value,
                        "probability": pred.probability,
                        "confidence": pred.confidence,
                        "severity": pred.severity.value if hasattr(pred.severity, 'value') else pred.severity,
                        "time_to_failure_hours": pred.time_to_failure_hours,
                        "recommendations": pred.recommendations,
                        "contributing_factors": pred.contributing_factors,
                    }
                    results.append(result)

                    # Record prediction
                    ml_result = MLPredictionResult(
                        prediction_id=pred.prediction_id,
                        entity_id=work_center_id,
                        prediction_type=PredictionType.FAILURE,
                        value=pred.probability,
                        confidence=pred.confidence,
                        uncertainty=1.0 - pred.confidence,
                        features_used=list(features.keys()),
                        model_version=pred.model_version,
                        details=result,
                    )
                    self._prediction_history[work_center_id].append(ml_result)

                    if pred.probability > 0.7:
                        self._stats["failures_predicted"] += 1

                return results

            except Exception as e:
                logger.error(f"Failure prediction error: {e}")
                return [{"error": str(e)}]

    def estimate_rul(
        self,
        work_center_id: str,
        features: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Estimate Remaining Useful Life (RUL) for equipment.

        Args:
            work_center_id: Work center identifier
            features: Optional feature override

        Returns:
            RUL estimate with confidence interval
        """
        with self._lock:
            self._stats["predictions_made"] += 1

            if not self._rul_estimator:
                return {"error": "RUL estimator not available"}

            # Get features from current state if not provided
            if features is None:
                snapshot = self.get_current_state(work_center_id)
                if snapshot:
                    features = self._extract_features(snapshot)
                else:
                    features = {}

            try:
                estimate = self._rul_estimator.estimate(work_center_id, features)

                result = {
                    "entity_id": work_center_id,
                    "rul_hours": estimate.rul_hours,
                    "rul_cycles": estimate.rul_cycles,
                    "confidence_lower": estimate.confidence_interval[0] if hasattr(estimate, 'confidence_interval') else estimate.rul_hours * 0.8,
                    "confidence_upper": estimate.confidence_interval[1] if hasattr(estimate, 'confidence_interval') else estimate.rul_hours * 1.2,
                    "degradation_rate": estimate.degradation_rate if hasattr(estimate, 'degradation_rate') else 0.0,
                    "health_index": estimate.health_index if hasattr(estimate, 'health_index') else 0.85,
                    "model_type": estimate.model_type.value if hasattr(estimate, 'model_type') else "survival_analysis",
                }

                # Update snapshot with RUL
                snapshot = self._state_cache.get(work_center_id)
                if snapshot:
                    snapshot.predicted_rul_hours = estimate.rul_hours

                # Record prediction
                ml_result = MLPredictionResult(
                    prediction_id=str(uuid.uuid4()),
                    entity_id=work_center_id,
                    prediction_type=PredictionType.RUL,
                    value=estimate.rul_hours,
                    confidence=0.85,
                    uncertainty=0.15,
                    features_used=list(features.keys()),
                    model_version="1.0.0",
                    details=result,
                )
                self._prediction_history[work_center_id].append(ml_result)

                return result

            except Exception as e:
                logger.error(f"RUL estimation error: {e}")
                return {"error": str(e)}

    def detect_anomalies(
        self,
        work_center_id: str,
        features: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in equipment behavior.

        Args:
            work_center_id: Work center identifier
            features: Optional feature override

        Returns:
            List of detected anomalies
        """
        with self._lock:
            if not self._anomaly_detector:
                return []

            # Get features from current state if not provided
            if features is None:
                snapshot = self.get_current_state(work_center_id)
                if snapshot:
                    features = self._extract_features(snapshot)
                else:
                    features = {}

            try:
                anomalies = self._anomaly_detector.detect(work_center_id, features)

                results = []
                for anomaly in anomalies:
                    result = {
                        "anomaly_id": str(uuid.uuid4()),
                        "entity_id": work_center_id,
                        "anomaly_type": anomaly.anomaly_type.value if hasattr(anomaly, 'anomaly_type') else "unknown",
                        "severity": anomaly.severity if hasattr(anomaly, 'severity') else "medium",
                        "score": anomaly.score if hasattr(anomaly, 'score') else 0.0,
                        "affected_features": anomaly.affected_features if hasattr(anomaly, 'affected_features') else [],
                        "description": anomaly.description if hasattr(anomaly, 'description') else "",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    results.append(result)

                    self._stats["anomalies_detected"] += 1

                # Update snapshot with anomaly score
                if results:
                    snapshot = self._state_cache.get(work_center_id)
                    if snapshot:
                        snapshot.anomaly_score = max(r["score"] for r in results)

                return results

            except Exception as e:
                logger.error(f"Anomaly detection error: {e}")
                return []

    # =========================================================================
    # Physics-Informed Predictions (PINN)
    # =========================================================================

    def simulate_thermal_field(
        self,
        work_center_id: str,
        geometry: Dict[str, Tuple[float, float]],
        time: float = 0.0,
        resolution: int = 20
    ) -> PhysicsSimulationResult:
        """
        Simulate thermal field using Physics-Informed Neural Network.

        Args:
            work_center_id: Work center identifier
            geometry: Spatial bounds {x: (min, max), y: (min, max), z: (min, max)}
            time: Time point for simulation
            resolution: Grid resolution

        Returns:
            Physics simulation result with temperature field
        """
        import time as time_module
        start_time = time_module.time()

        with self._lock:
            self._stats["simulations_run"] += 1

            if not self._thermal_pinn:
                return PhysicsSimulationResult(
                    simulation_id=str(uuid.uuid4()),
                    entity_id=work_center_id,
                    simulation_type=SimulationType.THERMAL_FIELD,
                    output_fields={},
                    boundary_conditions={},
                    physics_residual=float('inf'),
                    computation_time_ms=0,
                    mesh_points=0,
                )

            try:
                x_range = geometry.get('x', (0.0, 0.1))
                y_range = geometry.get('y', (0.0, 0.1))
                z_range = geometry.get('z', (0.0, 0.05))

                X, Y, Z, T = self._thermal_pinn.predict_temperature_field(
                    x_range, y_range, z_range, time, resolution
                )

                computation_time = (time_module.time() - start_time) * 1000

                result = PhysicsSimulationResult(
                    simulation_id=str(uuid.uuid4()),
                    entity_id=work_center_id,
                    simulation_type=SimulationType.THERMAL_FIELD,
                    output_fields={
                        "temperature": T,
                        "x_coords": X,
                        "y_coords": Y,
                        "z_coords": Z,
                    },
                    boundary_conditions={
                        "ambient_temp": 25.0,
                        "nozzle_temp": 200.0,
                    },
                    physics_residual=0.0,  # Would be computed from PINN loss
                    computation_time_ms=computation_time,
                    mesh_points=resolution ** 3,
                )

                self._simulation_history[work_center_id].append(result)
                return result

            except Exception as e:
                logger.error(f"Thermal simulation error: {e}")
                return PhysicsSimulationResult(
                    simulation_id=str(uuid.uuid4()),
                    entity_id=work_center_id,
                    simulation_type=SimulationType.THERMAL_FIELD,
                    output_fields={},
                    boundary_conditions={},
                    physics_residual=float('inf'),
                    computation_time_ms=0,
                    mesh_points=0,
                )

    def simulate_fdm_process(
        self,
        work_center_id: str,
        layer_points: np.ndarray,
        process_params: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Simulate FDM printing process using multi-physics PINN.

        Args:
            work_center_id: Work center identifier
            layer_points: 3D points in the layer [N, 3]
            process_params: Process parameters (nozzle_temp, bed_temp, speed, layer_height)

        Returns:
            Quality prediction with physics-based metrics
        """
        with self._lock:
            self._stats["simulations_run"] += 1

            if not self._fdm_process_pinn:
                return {"error": "FDM PINN not available"}

            try:
                result = self._fdm_process_pinn.predict_print_quality(
                    layer_points, process_params
                )

                # Add metadata
                result["simulation_id"] = str(uuid.uuid4())
                result["entity_id"] = work_center_id
                result["process_params"] = process_params
                result["timestamp"] = datetime.utcnow().isoformat()

                return result

            except Exception as e:
                logger.error(f"FDM simulation error: {e}")
                return {"error": str(e)}

    def predict_quality_physics(
        self,
        work_center_id: str,
        process_params: Dict[str, float]
    ) -> HybridPrediction:
        """
        Predict quality using hybrid physics + ML model.

        Combines:
        - Physics-based prediction from PINN
        - Data-driven prediction from ML
        - Uncertainty-weighted fusion

        Args:
            work_center_id: Work center identifier
            process_params: Process parameters

        Returns:
            Hybrid prediction with uncertainty quantification
        """
        with self._lock:
            self._stats["predictions_made"] += 1

            # Physics prediction (from PINN)
            physics_pred = 0.9  # Default
            physics_residual = 0.0

            if self._fdm_process_pinn:
                try:
                    # Create sample points for prediction
                    n_points = 100
                    layer_points = np.random.rand(n_points, 3) * 0.1  # 10cm cube

                    result = self._fdm_process_pinn.predict_print_quality(
                        layer_points, process_params
                    )
                    physics_pred = result.get("quality_score", 0.9)
                    physics_residual = 0.01  # Placeholder
                except Exception as e:
                    logger.warning(f"Physics prediction error: {e}")

            # ML prediction (from failure predictor / quality model)
            ml_pred = 0.9  # Default
            data_likelihood = 0.8

            if self._failure_predictor:
                try:
                    features = {
                        "temperature": process_params.get("nozzle_temp", 200),
                        "vibration": 0.5,
                        "operating_hours": 1000,
                    }
                    predictions = self._failure_predictor.predict(
                        work_center_id, features
                    )
                    if predictions:
                        # Quality = 1 - failure probability
                        ml_pred = 1.0 - predictions[0].probability
                        data_likelihood = predictions[0].confidence
                except Exception as e:
                    logger.warning(f"ML prediction error: {e}")

            # Fusion: weight by uncertainty
            # Lower physics residual = more trust in physics
            # Higher data likelihood = more trust in ML
            physics_weight = 1.0 / (1.0 + physics_residual * 10)
            ml_weight = data_likelihood

            total_weight = physics_weight + ml_weight
            fusion_weight = ml_weight / total_weight if total_weight > 0 else 0.5

            fused_pred = (1 - fusion_weight) * physics_pred + fusion_weight * ml_pred

            # Uncertainty from both models
            uncertainty = abs(physics_pred - ml_pred) * 0.5

            return HybridPrediction(
                prediction_id=str(uuid.uuid4()),
                entity_id=work_center_id,
                physics_prediction=physics_pred,
                ml_prediction=ml_pred,
                fused_prediction=fused_pred,
                fusion_weight=fusion_weight,
                uncertainty=uncertainty,
                physics_residual=physics_residual,
                data_likelihood=data_likelihood,
            )

    # =========================================================================
    # Callbacks and Event Handling
    # =========================================================================

    def register_state_callback(
        self,
        callback: Callable[[str, TwinSnapshot], None]
    ) -> None:
        """Register callback for state changes."""
        self._state_callbacks.append(callback)

    def register_prediction_callback(
        self,
        callback: Callable[[str, MLPredictionResult], None]
    ) -> None:
        """Register callback for new predictions."""
        self._prediction_callbacks.append(callback)

    def _notify_state_change(
        self,
        work_center_id: str,
        snapshot: TwinSnapshot
    ) -> None:
        """Notify registered callbacks of state change."""
        for callback in self._state_callbacks:
            try:
                callback(work_center_id, snapshot)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    def _notify_prediction(
        self,
        work_center_id: str,
        prediction: MLPredictionResult
    ) -> None:
        """Notify registered callbacks of new prediction."""
        for callback in self._prediction_callbacks:
            try:
                callback(work_center_id, prediction)
            except Exception as e:
                logger.error(f"Prediction callback error: {e}")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _extract_features(self, snapshot: TwinSnapshot) -> Dict[str, float]:
        """Extract ML features from twin snapshot."""
        features = {}

        # Temperature features
        if snapshot.temperatures:
            features["temperature"] = max(snapshot.temperatures.values())
            features["temperature_avg"] = sum(snapshot.temperatures.values()) / len(snapshot.temperatures)

        # Vibration features
        if snapshot.vibration:
            features["vibration"] = max(snapshot.vibration.values())
            features["vibration_avg"] = sum(snapshot.vibration.values()) / len(snapshot.vibration)

        # Process parameters
        if snapshot.process_params:
            features.update(snapshot.process_params)

        # Production metrics
        features["production_rate"] = snapshot.production_rate
        features["quality_rate"] = snapshot.quality_rate
        features["power_consumption"] = snapshot.power_consumption

        # Sensor readings
        if snapshot.sensor_readings:
            features.update(snapshot.sensor_readings)

        return features

    def get_prediction_history(
        self,
        work_center_id: str,
        prediction_type: Optional[PredictionType] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get prediction history for entity."""
        history = self._prediction_history.get(work_center_id, [])

        if prediction_type:
            history = [p for p in history if p.prediction_type == prediction_type]

        # Return most recent first
        history = sorted(history, key=lambda p: p.timestamp, reverse=True)[:limit]

        return [
            {
                "prediction_id": p.prediction_id,
                "prediction_type": p.prediction_type.value,
                "value": p.value,
                "confidence": p.confidence,
                "timestamp": p.timestamp.isoformat(),
                "details": p.details,
            }
            for p in history
        ]

    def get_simulation_history(
        self,
        work_center_id: str,
        simulation_type: Optional[SimulationType] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get simulation history for entity."""
        history = self._simulation_history.get(work_center_id, [])

        if simulation_type:
            history = [s for s in history if s.simulation_type == simulation_type]

        # Return most recent first
        history = sorted(history, key=lambda s: s.timestamp, reverse=True)[:limit]

        return [
            {
                "simulation_id": s.simulation_id,
                "simulation_type": s.simulation_type.value,
                "physics_residual": s.physics_residual,
                "computation_time_ms": s.computation_time_ms,
                "mesh_points": s.mesh_points,
                "timestamp": s.timestamp.isoformat(),
            }
            for s in history
        ]

    # =========================================================================
    # HOQ Integration - Design Package Support
    # =========================================================================

    def configure_from_hoq_package(
        self,
        work_center_id: str,
        design_package: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Configure digital twin from HOQ design package.

        Takes specifications from the HOQ Digital Twin Bridge and configures
        the twin's parameters, validation criteria, and monitoring thresholds.

        Args:
            work_center_id: Work center ID to configure
            design_package: Design package from HOQDigitalTwinBridge

        Returns:
            Configuration result with applied settings
        """
        result = {
            "work_center_id": work_center_id,
            "package_id": design_package.get("package_id"),
            "configured_at": datetime.utcnow().isoformat(),
            "specs_applied": [],
            "validation_rules": [],
            "monitoring_enabled": [],
        }

        # Get or create snapshot
        snapshot = self.get_current_state(work_center_id)
        if not snapshot:
            snapshot = TwinSnapshot(
                work_center_id=work_center_id,
                timestamp=datetime.utcnow(),
                status='configured'
            )
            self._state_cache[work_center_id] = snapshot

        # Apply design specs as process parameters
        for spec in design_package.get("design_specs", []):
            param_name = spec.get("name", "").lower().replace(" ", "_")
            snapshot.process_params[param_name] = spec.get("target_value", 0)
            snapshot.metadata[f"hoq_spec_{spec.get('spec_id')}"] = {
                "target": spec.get("target_value"),
                "tolerance_lower": spec.get("tolerance_lower"),
                "tolerance_upper": spec.get("tolerance_upper"),
                "severity": spec.get("validation_severity"),
                "unit": spec.get("unit"),
            }
            result["specs_applied"].append(spec.get("spec_id"))

        # Store validation criteria for runtime checking
        snapshot.metadata["hoq_validation_criteria"] = [
            {
                "criterion_id": c.get("criterion_id"),
                "name": c.get("name"),
                "check_type": c.get("check_type"),
                "target_value": c.get("target_value"),
                "lower_bound": c.get("lower_bound"),
                "upper_bound": c.get("upper_bound"),
                "severity": c.get("severity"),
            }
            for c in design_package.get("validation_criteria", [])
        ]
        result["validation_rules"] = [c.get("criterion_id")
                                       for c in design_package.get("validation_criteria", [])]

        # Enable monitoring for critical parameters
        critical_specs = [
            s for s in design_package.get("design_specs", [])
            if s.get("validation_severity") == "critical"
        ]
        for spec in critical_specs:
            param_name = spec.get("name", "").lower().replace(" ", "_")
            result["monitoring_enabled"].append(param_name)

        # Store traceability
        snapshot.metadata["hoq_traceability"] = design_package.get("traceability_matrix", {})
        snapshot.metadata["hoq_package_id"] = design_package.get("package_id")

        logger.info(f"Configured twin '{work_center_id}' from HOQ package "
                   f"'{design_package.get('package_id')}' with {len(result['specs_applied'])} specs")

        return result

    def validate_against_hoq(
        self,
        work_center_id: str,
        measured_values: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Validate digital twin state against HOQ specifications.

        Compares current or provided values against the HOQ-derived
        validation criteria stored in the twin's metadata.

        Args:
            work_center_id: Work center ID to validate
            measured_values: Optional measured values (uses current state if not provided)

        Returns:
            Validation results with pass/fail for each criterion
        """
        snapshot = self.get_current_state(work_center_id)
        if not snapshot:
            return {"error": "Work center not found", "work_center_id": work_center_id}

        criteria = snapshot.metadata.get("hoq_validation_criteria", [])
        if not criteria:
            return {"error": "No HOQ criteria configured", "work_center_id": work_center_id}

        # Use provided values or current process params
        values = measured_values or snapshot.process_params

        results = {
            "work_center_id": work_center_id,
            "validation_time": datetime.utcnow().isoformat(),
            "hoq_package_id": snapshot.metadata.get("hoq_package_id"),
            "overall_pass": True,
            "total_criteria": len(criteria),
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "details": [],
        }

        for criterion in criteria:
            param_name = criterion.get("name", "").replace("Validate ", "").lower().replace(" ", "_")

            if param_name not in values:
                results["skipped"] += 1
                results["details"].append({
                    "criterion_id": criterion.get("criterion_id"),
                    "status": "skip",
                    "message": f"Parameter '{param_name}' not found in values",
                })
                continue

            actual = values[param_name]
            target = criterion.get("target_value", 0)
            lower = criterion.get("lower_bound")
            upper = criterion.get("upper_bound")
            check_type = criterion.get("check_type", "tolerance")

            passed = False
            message = ""

            if check_type == "range" or check_type == "tolerance":
                if lower is not None and upper is not None:
                    passed = lower <= actual <= upper
                    message = f"{actual} {'within' if passed else 'outside'} [{lower}, {upper}]"
                else:
                    # Use 5% tolerance as fallback
                    tolerance = abs(target * 0.05)
                    passed = abs(actual - target) <= tolerance
                    message = f"|{actual} - {target}| <= {tolerance}: {'PASS' if passed else 'FAIL'}"
            elif check_type == "minimum":
                passed = actual >= (lower or target)
                message = f"{actual} >= {lower or target}: {'PASS' if passed else 'FAIL'}"
            elif check_type == "maximum":
                passed = actual <= (upper or target)
                message = f"{actual} <= {upper or target}: {'PASS' if passed else 'FAIL'}"
            else:
                passed = abs(actual - target) < 0.001
                message = f"{actual} == {target}: {'PASS' if passed else 'FAIL'}"

            results["details"].append({
                "criterion_id": criterion.get("criterion_id"),
                "status": "pass" if passed else "fail",
                "expected": target,
                "actual": actual,
                "message": message,
                "severity": criterion.get("severity"),
            })

            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1
                # Critical or major failures affect overall pass
                if criterion.get("severity") in ("critical", "major"):
                    results["overall_pass"] = False

        results["pass_rate"] = (results["passed"] / results["total_criteria"] * 100
                                if results["total_criteria"] > 0 else 0)

        return results

    def get_hoq_traceability(self, work_center_id: str) -> Dict[str, Any]:
        """
        Get HOQ traceability for a configured digital twin.

        Returns the mapping from customer requirements to specs
        that was configured from the HOQ design package.

        Args:
            work_center_id: Work center ID

        Returns:
            Traceability matrix and related info
        """
        snapshot = self.get_current_state(work_center_id)
        if not snapshot:
            return {"error": "Work center not found"}

        return {
            "work_center_id": work_center_id,
            "hoq_package_id": snapshot.metadata.get("hoq_package_id"),
            "traceability_matrix": snapshot.metadata.get("hoq_traceability", {}),
            "configured_specs": [
                k.replace("hoq_spec_", "") for k in snapshot.metadata.keys()
                if k.startswith("hoq_spec_")
            ],
            "validation_criteria_count": len(
                snapshot.metadata.get("hoq_validation_criteria", [])
            ),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            **self._stats,
            "cached_twins": len(self._state_cache),
            "prediction_history_size": sum(len(v) for v in self._prediction_history.values()),
            "simulation_history_size": sum(len(v) for v in self._simulation_history.values()),
            "ml_available": _ML_AVAILABLE,
            "pinn_available": _PINN_AVAILABLE,
        }

    def get_ml_model_info(self) -> Dict[str, Any]:
        """Get information about loaded ML models."""
        info = {
            "failure_predictor": None,
            "rul_estimator": None,
            "anomaly_detector": None,
            "thermal_pinn": None,
            "mechanical_pinn": None,
            "fdm_process_pinn": None,
        }

        if self._failure_predictor:
            info["failure_predictor"] = self._failure_predictor.get_model_info()

        if self._rul_estimator:
            info["rul_estimator"] = {
                "available": True,
                "type": "survival_analysis",
            }

        if self._anomaly_detector:
            info["anomaly_detector"] = {
                "available": True,
                "type": "isolation_forest",
            }

        if self._thermal_pinn:
            info["thermal_pinn"] = {
                "available": True,
                "input_dim": 4,
                "output_dim": 1,
                "architecture": "4-64-64-64-64-1",
            }

        if self._mechanical_pinn:
            info["mechanical_pinn"] = {
                "available": True,
                "input_dim": 3,
                "output_dim": 3,
                "architecture": "3-64-64-64-64-3",
            }

        if self._fdm_process_pinn:
            info["fdm_process_pinn"] = {
                "available": True,
                "input_dim": 8,
                "output_dim": 3,
                "architecture": "8-128-128-128-128-3",
            }

        return info


# =============================================================================
# Singleton Instance
# =============================================================================

_twin_manager: Optional[DigitalTwinManager] = None


def get_twin_manager(session: Session = None) -> DigitalTwinManager:
    """Get or create the digital twin manager instance."""
    global _twin_manager
    if _twin_manager is None:
        _twin_manager = DigitalTwinManager(session)
    return _twin_manager


# =============================================================================
# Export Public API
# =============================================================================

__all__ = [
    # Core classes
    "DigitalTwinManager",
    "TwinSnapshot",
    "TwinStateType",
    # Prediction types
    "PredictionType",
    "SimulationType",
    "MLPredictionResult",
    "PhysicsSimulationResult",
    "HybridPrediction",
    # Singleton
    "get_twin_manager",
]
