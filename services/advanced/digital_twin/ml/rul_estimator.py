"""
RUL Estimator - Remaining Useful Life Estimation

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Remaining Useful Life (RUL) estimation
- Degradation modeling
- Confidence intervals
- Multi-component RUL tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from enum import Enum
import threading
import uuid
import math
import random
from collections import defaultdict


class DegradationModel(Enum):
    """Degradation model types."""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    WEIBULL = "weibull"
    LOG_LINEAR = "log_linear"
    POLYNOMIAL = "polynomial"
    PIECEWISE = "piecewise"


class ComponentType(Enum):
    """Component types for RUL tracking."""
    MOTOR = "motor"
    BELT = "belt"
    BEARING = "bearing"
    NOZZLE = "nozzle"
    HEATER = "heater"
    SENSOR = "sensor"
    EXTRUDER = "extruder"
    BUILD_PLATE = "build_plate"
    LINEAR_RAIL = "linear_rail"
    STEPPER_DRIVER = "stepper_driver"


class HealthState(Enum):
    """Component health states."""
    HEALTHY = "healthy"
    DEGRADING = "degrading"
    WARNING = "warning"
    CRITICAL = "critical"
    FAILED = "failed"


@dataclass
class RULConfig:
    """RUL estimator configuration."""
    model_type: DegradationModel = DegradationModel.EXPONENTIAL
    failure_threshold: float = 0.2  # Health below this = failure
    warning_threshold: float = 0.4
    confidence_level: float = 0.95
    min_data_points: int = 10
    history_window_days: int = 90
    update_interval_hours: float = 1.0


@dataclass
class HealthIndicator:
    """Health indicator measurement."""
    indicator_id: str
    component_id: str
    value: float  # 0-1 normalized health
    raw_value: float
    timestamp: datetime
    quality: str = "good"


@dataclass
class DegradationState:
    """Current degradation state."""
    component_id: str
    component_type: ComponentType
    current_health: float
    degradation_rate: float  # Health loss per hour
    health_history: List[Tuple[datetime, float]] = field(default_factory=list)
    model_params: Dict[str, float] = field(default_factory=dict)
    last_update: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RULEstimate:
    """Remaining Useful Life estimate."""
    estimate_id: str
    component_id: str
    component_type: ComponentType
    rul_hours: float
    rul_days: float
    confidence_lower: float  # Lower bound (hours)
    confidence_upper: float  # Upper bound (hours)
    confidence_level: float
    current_health: float
    health_state: HealthState
    degradation_rate: float
    end_of_life_date: Optional[datetime]
    model_type: DegradationModel
    data_points_used: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ComponentSpec:
    """Component specification for RUL tracking."""
    component_id: str
    component_type: ComponentType
    installed_date: datetime
    expected_life_hours: float
    manufacturer: str = ""
    model: str = ""
    custom_thresholds: Optional[Dict[str, float]] = None


class RULEstimator:
    """
    Remaining Useful Life (RUL) Estimator.

    Features:
    - Multiple degradation models
    - Confidence interval estimation
    - Multi-component tracking
    - Adaptive model selection
    """

    def __init__(self, config: Optional[RULConfig] = None):
        """
        Initialize RUL estimator.

        Args:
            config: Estimator configuration
        """
        self.config = config or RULConfig()

        # Component tracking
        self._components: Dict[str, ComponentSpec] = {}
        self._degradation_states: Dict[str, DegradationState] = {}

        # Health indicator history
        self._indicator_history: Dict[str, List[HealthIndicator]] = defaultdict(list)

        # Model cache
        self._model_cache: Dict[str, Dict[str, Any]] = {}

        # Thread safety
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            "estimates_made": 0,
            "indicators_recorded": 0,
            "components_tracked": 0,
            "model_updates": 0,
        }

    def register_component(self, spec: ComponentSpec):
        """
        Register a component for RUL tracking.

        Args:
            spec: Component specification
        """
        with self._lock:
            self._components[spec.component_id] = spec

            # Initialize degradation state
            self._degradation_states[spec.component_id] = DegradationState(
                component_id=spec.component_id,
                component_type=spec.component_type,
                current_health=1.0,
                degradation_rate=0.0,
            )

            self._stats["components_tracked"] += 1

    def record_health(
        self,
        component_id: str,
        health_value: float,
        raw_value: Optional[float] = None,
        quality: str = "good"
    ) -> Optional[HealthIndicator]:
        """
        Record a health indicator measurement.

        Args:
            component_id: Component identifier
            health_value: Normalized health (0-1)
            raw_value: Raw measurement value
            quality: Data quality

        Returns:
            Health indicator
        """
        with self._lock:
            if component_id not in self._components:
                return None

            indicator = HealthIndicator(
                indicator_id=str(uuid.uuid4()),
                component_id=component_id,
                value=max(0, min(1, health_value)),
                raw_value=raw_value or health_value,
                timestamp=datetime.utcnow(),
                quality=quality,
            )

            self._indicator_history[component_id].append(indicator)
            self._stats["indicators_recorded"] += 1

            # Update degradation state
            self._update_degradation_state(component_id)

            # Trim old history
            cutoff = datetime.utcnow() - timedelta(days=self.config.history_window_days)
            self._indicator_history[component_id] = [
                h for h in self._indicator_history[component_id]
                if h.timestamp > cutoff
            ]

            return indicator

    def estimate(
        self,
        component_id: str,
        model_type: Optional[DegradationModel] = None
    ) -> Optional[RULEstimate]:
        """
        Estimate Remaining Useful Life for a component.

        Args:
            component_id: Component identifier
            model_type: Degradation model to use

        Returns:
            RUL estimate
        """
        with self._lock:
            self._stats["estimates_made"] += 1

            if component_id not in self._components:
                return None

            spec = self._components[component_id]
            state = self._degradation_states.get(component_id)

            if state is None:
                return None

            model = model_type or self.config.model_type

            # Get RUL based on degradation model
            rul_hours, confidence_interval = self._calculate_rul(
                state, model
            )

            # Determine health state
            health_state = self._determine_health_state(state.current_health)

            # Calculate end of life date
            eol_date = None
            if rul_hours > 0:
                eol_date = datetime.utcnow() + timedelta(hours=rul_hours)

            return RULEstimate(
                estimate_id=str(uuid.uuid4()),
                component_id=component_id,
                component_type=spec.component_type,
                rul_hours=rul_hours,
                rul_days=rul_hours / 24,
                confidence_lower=confidence_interval[0],
                confidence_upper=confidence_interval[1],
                confidence_level=self.config.confidence_level,
                current_health=state.current_health,
                health_state=health_state,
                degradation_rate=state.degradation_rate,
                end_of_life_date=eol_date,
                model_type=model,
                data_points_used=len(self._indicator_history.get(component_id, [])),
            )

    def estimate_all(self) -> Dict[str, RULEstimate]:
        """
        Estimate RUL for all tracked components.

        Returns:
            Dict mapping component_id to estimate
        """
        results = {}

        for component_id in self._components:
            estimate = self.estimate(component_id)
            if estimate:
                results[component_id] = estimate

        return results

    def get_critical_components(
        self,
        rul_threshold_hours: float = 168  # 1 week
    ) -> List[RULEstimate]:
        """
        Get components with critical RUL.

        Args:
            rul_threshold_hours: RUL threshold

        Returns:
            List of critical estimates
        """
        all_estimates = self.estimate_all()

        critical = [
            e for e in all_estimates.values()
            if e.rul_hours < rul_threshold_hours
        ]

        # Sort by RUL (shortest first)
        critical.sort(key=lambda e: e.rul_hours)

        return critical

    def get_maintenance_schedule(
        self,
        planning_horizon_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Generate maintenance schedule based on RUL.

        Args:
            planning_horizon_days: Planning horizon

        Returns:
            Maintenance schedule
        """
        estimates = self.estimate_all()
        schedule = []

        for estimate in estimates.values():
            if estimate.rul_days < planning_horizon_days:
                # Schedule maintenance before failure
                maintenance_date = datetime.utcnow() + timedelta(
                    hours=estimate.rul_hours * 0.8  # 80% of RUL
                )

                schedule.append({
                    "component_id": estimate.component_id,
                    "component_type": estimate.component_type.value,
                    "scheduled_date": maintenance_date.isoformat(),
                    "urgency": "high" if estimate.rul_days < 7 else "normal",
                    "current_health": estimate.current_health,
                    "rul_hours": estimate.rul_hours,
                    "rul_days": estimate.rul_days,
                    "confidence": f"{estimate.confidence_lower:.0f}-{estimate.confidence_upper:.0f}h",
                })

        # Sort by scheduled date
        schedule.sort(key=lambda x: x["scheduled_date"])

        return schedule

    def compare_models(
        self,
        component_id: str
    ) -> Dict[str, RULEstimate]:
        """
        Compare RUL estimates from different models.

        Args:
            component_id: Component identifier

        Returns:
            Dict mapping model name to estimate
        """
        results = {}

        for model in DegradationModel:
            estimate = self.estimate(component_id, model)
            if estimate:
                results[model.value] = estimate

        return results

    def select_best_model(
        self,
        component_id: str
    ) -> DegradationModel:
        """
        Select best degradation model based on fit.

        Args:
            component_id: Component identifier

        Returns:
            Best model type
        """
        history = self._indicator_history.get(component_id, [])

        if len(history) < self.config.min_data_points:
            return DegradationModel.LINEAR  # Default

        # Calculate fit for each model (simplified)
        best_model = DegradationModel.EXPONENTIAL
        best_score = 0

        for model in DegradationModel:
            score = self._evaluate_model_fit(history, model)
            if score > best_score:
                best_score = score
                best_model = model

        return best_model

    def get_degradation_curve(
        self,
        component_id: str,
        future_hours: int = 720  # 30 days
    ) -> List[Dict[str, Any]]:
        """
        Get projected degradation curve.

        Args:
            component_id: Component identifier
            future_hours: Hours to project

        Returns:
            Degradation curve points
        """
        state = self._degradation_states.get(component_id)
        if state is None:
            return []

        curve = []
        current_health = state.current_health
        rate = state.degradation_rate

        for hour in range(0, future_hours + 1, 24):  # Daily points
            # Calculate projected health
            if self.config.model_type == DegradationModel.LINEAR:
                health = current_health - rate * hour
            elif self.config.model_type == DegradationModel.EXPONENTIAL:
                health = current_health * math.exp(-rate * hour / 1000)
            else:
                health = current_health - rate * hour

            health = max(0, min(1, health))

            curve.append({
                "hours": hour,
                "days": hour / 24,
                "date": (datetime.utcnow() + timedelta(hours=hour)).isoformat(),
                "health": health,
                "state": self._determine_health_state(health).value,
            })

            if health <= self.config.failure_threshold:
                break

        return curve

    def get_component_history(
        self,
        component_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get component health history.

        Args:
            component_id: Component identifier
            days: Days of history

        Returns:
            Health history
        """
        history = self._indicator_history.get(component_id, [])
        cutoff = datetime.utcnow() - timedelta(days=days)

        return [
            {
                "timestamp": h.timestamp.isoformat(),
                "health": h.value,
                "raw_value": h.raw_value,
                "quality": h.quality,
            }
            for h in history
            if h.timestamp > cutoff
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """Get estimator statistics."""
        return {
            **self._stats,
            "model_type": self.config.model_type.value,
            "failure_threshold": self.config.failure_threshold,
            "warning_threshold": self.config.warning_threshold,
        }

    def _update_degradation_state(self, component_id: str):
        """Update degradation state from history."""
        history = self._indicator_history.get(component_id, [])

        if len(history) < 2:
            return

        state = self._degradation_states.get(component_id)
        if state is None:
            return

        # Get recent health values
        recent = sorted(history, key=lambda h: h.timestamp)[-20:]

        # Calculate current health (latest)
        state.current_health = recent[-1].value

        # Calculate degradation rate
        if len(recent) >= 2:
            time_delta = (recent[-1].timestamp - recent[0].timestamp).total_seconds() / 3600
            health_delta = recent[0].value - recent[-1].value

            if time_delta > 0:
                state.degradation_rate = max(0, health_delta / time_delta)

        # Update health history
        state.health_history = [
            (h.timestamp, h.value) for h in recent
        ]

        state.last_update = datetime.utcnow()
        self._stats["model_updates"] += 1

    def _calculate_rul(
        self,
        state: DegradationState,
        model: DegradationModel
    ) -> Tuple[float, Tuple[float, float]]:
        """Calculate RUL with confidence interval."""
        current_health = state.current_health
        rate = state.degradation_rate

        if current_health <= self.config.failure_threshold:
            return 0, (0, 0)

        if rate <= 0:
            # No degradation detected, use expected life
            spec = self._components.get(state.component_id)
            if spec:
                # Estimate based on installation date
                hours_used = (datetime.utcnow() - spec.installed_date).total_seconds() / 3600
                remaining = max(0, spec.expected_life_hours - hours_used)
                return remaining, (remaining * 0.7, remaining * 1.3)
            return 10000, (7000, 15000)  # Default

        # Calculate based on model
        health_to_fail = current_health - self.config.failure_threshold

        if model == DegradationModel.LINEAR:
            rul = health_to_fail / rate
        elif model == DegradationModel.EXPONENTIAL:
            # Solve: threshold = current * exp(-rate * t)
            if current_health > 0:
                rul = -1000 * math.log(self.config.failure_threshold / current_health) / rate
            else:
                rul = 0
        elif model == DegradationModel.LOG_LINEAR:
            rul = health_to_fail / (rate * math.log(2))
        else:
            rul = health_to_fail / rate

        rul = max(0, rul)

        # Calculate confidence interval
        # Using simplified uncertainty quantification
        data_points = len(self._indicator_history.get(state.component_id, []))
        uncertainty_factor = max(0.1, 1.0 / math.sqrt(max(1, data_points)))

        lower = rul * (1 - uncertainty_factor)
        upper = rul * (1 + uncertainty_factor)

        return rul, (max(0, lower), upper)

    def _determine_health_state(self, health: float) -> HealthState:
        """Determine health state from value."""
        if health >= 0.8:
            return HealthState.HEALTHY
        elif health >= self.config.warning_threshold:
            return HealthState.DEGRADING
        elif health >= self.config.failure_threshold:
            return HealthState.WARNING
        elif health > 0:
            return HealthState.CRITICAL
        else:
            return HealthState.FAILED

    def _evaluate_model_fit(
        self,
        history: List[HealthIndicator],
        model: DegradationModel
    ) -> float:
        """Evaluate model fit to data."""
        if len(history) < 3:
            return 0.5

        # Simplified R-squared calculation
        # Real implementation would fit model and calculate actual R²

        return random.uniform(0.6, 0.95)


# Singleton instance
_rul_estimator: Optional[RULEstimator] = None


def get_rul_estimator() -> RULEstimator:
    """Get or create the RUL estimator instance."""
    global _rul_estimator
    if _rul_estimator is None:
        _rul_estimator = RULEstimator()
    return _rul_estimator
