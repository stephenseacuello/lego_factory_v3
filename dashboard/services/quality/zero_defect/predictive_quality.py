"""
Predictive Quality - ML-Based Quality Prediction

LegoMCP World-Class Manufacturing System v5.0
Phase 21: Zero-Defect Manufacturing

Predicts quality outcomes before part completion:
- Defect probability prediction
- Dimensional accuracy forecasting
- Clutch power prediction (LEGO-specific)
- Surface quality grading
- Early intervention triggering
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


class DefectType(str, Enum):
    """Types of predicted defects."""
    NONE = "none"
    DIMENSIONAL = "dimensional"
    SURFACE = "surface"
    STRUCTURAL = "structural"
    CLUTCH_POWER = "clutch_power"
    WARPING = "warping"
    LAYER_ADHESION = "layer_adhesion"


class InterventionType(str, Enum):
    """Types of in-process interventions."""
    NONE = "none"
    ADJUST_TEMPERATURE = "adjust_temperature"
    ADJUST_SPEED = "adjust_speed"
    ADJUST_FLOW = "adjust_flow"
    PAUSE = "pause"
    STOP = "stop"


@dataclass
class ProcessSignals:
    """Real-time process signals for prediction."""
    timestamp: datetime
    machine_id: str
    job_id: str

    # Temperature signals
    nozzle_temp: float = 210.0
    bed_temp: float = 60.0
    ambient_temp: float = 25.0

    # Motion signals
    print_speed: float = 40.0
    acceleration: float = 1000.0
    layer_height: float = 0.12

    # Extrusion signals
    flow_rate: float = 100.0
    filament_diameter: float = 1.75
    pressure: Optional[float] = None

    # Environmental
    humidity: float = 50.0

    # Progress
    layer_number: int = 0
    total_layers: int = 100
    elapsed_time_seconds: float = 0.0

    # Derived features
    layer_time: float = 0.0
    cooling_time: float = 0.0

    def to_feature_vector(self) -> np.ndarray:
        """Convert to feature vector for ML model."""
        features = [
            self.nozzle_temp,
            self.bed_temp,
            self.ambient_temp,
            self.print_speed,
            self.acceleration,
            self.layer_height,
            self.flow_rate,
            self.filament_diameter,
            self.humidity,
            self.layer_number / max(1, self.total_layers),  # Progress
            self.layer_time,
            self.cooling_time,
            self.nozzle_temp - self.ambient_temp,  # Temp differential
            self.print_speed / 40.0,  # Normalized speed
        ]
        return np.array(features, dtype=np.float32)


@dataclass
class QualityPrediction:
    """Predicted quality outcome."""
    timestamp: datetime
    job_id: str
    layer_number: int

    # Defect prediction
    defect_probability: float  # 0-1
    predicted_defect_types: List[DefectType]
    defect_confidences: Dict[DefectType, float]

    # Dimensional prediction
    predicted_dimensions: Dict[str, float] = field(default_factory=dict)
    dimension_confidence: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    # LEGO-specific
    predicted_clutch_power: Optional[float] = None
    clutch_power_range: Optional[Tuple[float, float]] = None

    # Surface quality (1-5 scale)
    predicted_surface_grade: float = 5.0

    # Overall assessment
    pass_probability: float = 1.0
    risk_level: str = "low"  # low, medium, high, critical

    def should_intervene(self, threshold: float = 0.3) -> bool:
        """Check if intervention is recommended."""
        return self.defect_probability > threshold or self.risk_level in ('high', 'critical')


@dataclass
class InterventionDecision:
    """Decision about in-process intervention."""
    should_intervene: bool
    intervention_type: InterventionType
    parameters: Dict[str, Any]
    urgency: str  # immediate, soon, deferred
    rationale: str
    confidence: float


class PredictiveQualityModel:
    """
    ML-based predictive quality model.

    Predicts quality outcomes from real-time process signals
    to enable early intervention.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.config = config or {}
        self.model_path = model_path

        # Initialize models
        if SKLEARN_AVAILABLE:
            self.defect_classifier = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
            )
            self.dimension_regressor = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
            )
            self.scaler = StandardScaler()
            self._is_trained = False
        else:
            logger.warning("scikit-learn not available. Using rule-based prediction.")
            self._is_trained = False

        # Historical data for training
        self._training_data: List[Tuple[ProcessSignals, Dict[str, Any]]] = []

        # LEGO-specific thresholds
        self.CLUTCH_POWER_TARGET = 2.0  # Newtons
        self.CLUTCH_POWER_MIN = 1.0
        self.CLUTCH_POWER_MAX = 3.0

        # Defect detection thresholds
        self.DEFECT_PROB_THRESHOLD = 0.3
        self.HIGH_RISK_THRESHOLD = 0.6
        self.CRITICAL_THRESHOLD = 0.85

    def predict(self, signals: ProcessSignals) -> QualityPrediction:
        """Predict quality from current process signals."""
        if self._is_trained and SKLEARN_AVAILABLE:
            return self._ml_predict(signals)
        else:
            return self._rule_based_predict(signals)

    def _ml_predict(self, signals: ProcessSignals) -> QualityPrediction:
        """Use trained ML model for prediction."""
        features = signals.to_feature_vector().reshape(1, -1)
        features_scaled = self.scaler.transform(features)

        # Predict defect probability
        defect_proba = self.defect_classifier.predict_proba(features_scaled)[0]
        defect_prob = 1.0 - defect_proba[0]  # Probability of NOT no-defect

        # Predict dimensions
        predicted_dims = {}
        # Would have separate regressors for each dimension
        # For now, use nominal values

        return self._build_prediction(signals, defect_prob, predicted_dims)

    def _rule_based_predict(self, signals: ProcessSignals) -> QualityPrediction:
        """Rule-based prediction when ML model not available."""
        defect_prob = 0.0
        defect_types = []
        defect_confidences = {}

        # Temperature rules
        if signals.nozzle_temp < 195 or signals.nozzle_temp > 225:
            defect_prob += 0.3
            defect_types.append(DefectType.LAYER_ADHESION)
            defect_confidences[DefectType.LAYER_ADHESION] = 0.7

        # Speed rules
        if signals.print_speed > 60:
            defect_prob += 0.2
            defect_types.append(DefectType.SURFACE)
            defect_confidences[DefectType.SURFACE] = 0.6

        # Flow rate rules
        flow_deviation = abs(signals.flow_rate - 100) / 100
        if flow_deviation > 0.1:
            defect_prob += 0.25
            defect_types.append(DefectType.CLUTCH_POWER)
            defect_confidences[DefectType.CLUTCH_POWER] = 0.65

            if signals.flow_rate < 95:
                defect_types.append(DefectType.STRUCTURAL)
                defect_confidences[DefectType.STRUCTURAL] = 0.5

        # Humidity rules
        if signals.humidity > 70:
            defect_prob += 0.15
            # High humidity can cause stringing and poor adhesion

        # Layer height rules
        if signals.layer_height < 0.08 or signals.layer_height > 0.2:
            defect_prob += 0.1

        # Progress rules (early layers more critical)
        if signals.layer_number < 5:
            defect_prob *= 1.2  # First layers more critical

        # Predicted clutch power based on flow rate
        clutch_power = self._predict_clutch_power(signals)

        # Predicted dimensions
        predicted_dims = self._predict_dimensions(signals)

        # Surface grade based on speed and temperature
        surface_grade = self._predict_surface_grade(signals)

        # Determine risk level
        defect_prob = min(1.0, defect_prob)
        if defect_prob >= self.CRITICAL_THRESHOLD:
            risk_level = "critical"
        elif defect_prob >= self.HIGH_RISK_THRESHOLD:
            risk_level = "high"
        elif defect_prob >= self.DEFECT_PROB_THRESHOLD:
            risk_level = "medium"
        else:
            risk_level = "low"

        return QualityPrediction(
            timestamp=signals.timestamp,
            job_id=signals.job_id,
            layer_number=signals.layer_number,
            defect_probability=defect_prob,
            predicted_defect_types=defect_types,
            defect_confidences=defect_confidences,
            predicted_dimensions=predicted_dims,
            predicted_clutch_power=clutch_power,
            clutch_power_range=(clutch_power * 0.9, clutch_power * 1.1),
            predicted_surface_grade=surface_grade,
            pass_probability=1.0 - defect_prob,
            risk_level=risk_level,
        )

    def _predict_clutch_power(self, signals: ProcessSignals) -> float:
        """Predict clutch power based on process signals."""
        # Clutch power depends primarily on stud dimensions
        # which depend on flow rate and temperature

        base_clutch = self.CLUTCH_POWER_TARGET

        # Flow rate effect
        flow_factor = signals.flow_rate / 100.0
        if flow_factor > 1.05:
            # Over-extrusion → tighter fit
            base_clutch += (flow_factor - 1.0) * 2.0
        elif flow_factor < 0.95:
            # Under-extrusion → looser fit
            base_clutch -= (1.0 - flow_factor) * 3.0

        # Temperature effect
        if signals.nozzle_temp > 220:
            # Higher temp → more oozing → slightly larger studs
            base_clutch += 0.1
        elif signals.nozzle_temp < 200:
            # Lower temp → smaller studs
            base_clutch -= 0.2

        # Speed effect
        if signals.print_speed > 50:
            # Faster printing → less precise → variable
            base_clutch -= 0.1

        return max(0.5, min(4.0, base_clutch))

    def _predict_dimensions(self, signals: ProcessSignals) -> Dict[str, float]:
        """Predict key dimensions based on process signals."""
        # Nominal LEGO dimensions
        stud_diameter_nominal = 4.8  # mm
        stud_height_nominal = 1.8  # mm
        wall_thickness_nominal = 1.6  # mm

        # Calculate deviations based on process parameters
        flow_deviation = (signals.flow_rate - 100) / 100 * 0.05  # mm per 1%

        return {
            'stud_diameter': stud_diameter_nominal + flow_deviation,
            'stud_height': stud_height_nominal,
            'wall_thickness': wall_thickness_nominal + flow_deviation * 0.5,
        }

    def _predict_surface_grade(self, signals: ProcessSignals) -> float:
        """Predict surface quality grade (1-5)."""
        grade = 5.0

        # Speed penalty
        if signals.print_speed > 50:
            grade -= (signals.print_speed - 50) * 0.03

        # Layer height penalty
        if signals.layer_height > 0.15:
            grade -= (signals.layer_height - 0.15) * 10

        # Temperature penalty (outside optimal range)
        if signals.nozzle_temp < 200 or signals.nozzle_temp > 220:
            grade -= 0.3

        return max(1.0, min(5.0, grade))

    def _build_prediction(
        self,
        signals: ProcessSignals,
        defect_prob: float,
        predicted_dims: Dict[str, float]
    ) -> QualityPrediction:
        """Build prediction object from components."""
        defect_types = []
        if defect_prob > 0.3:
            defect_types.append(DefectType.DIMENSIONAL)

        risk_level = "low"
        if defect_prob >= self.CRITICAL_THRESHOLD:
            risk_level = "critical"
        elif defect_prob >= self.HIGH_RISK_THRESHOLD:
            risk_level = "high"
        elif defect_prob >= self.DEFECT_PROB_THRESHOLD:
            risk_level = "medium"

        return QualityPrediction(
            timestamp=signals.timestamp,
            job_id=signals.job_id,
            layer_number=signals.layer_number,
            defect_probability=defect_prob,
            predicted_defect_types=defect_types,
            defect_confidences={},
            predicted_dimensions=predicted_dims,
            predicted_clutch_power=self._predict_clutch_power(signals),
            pass_probability=1.0 - defect_prob,
            risk_level=risk_level,
        )

    def should_intervene(
        self,
        prediction: QualityPrediction
    ) -> InterventionDecision:
        """Decide if intervention is needed."""
        if prediction.risk_level == "critical":
            return InterventionDecision(
                should_intervene=True,
                intervention_type=InterventionType.STOP,
                parameters={},
                urgency="immediate",
                rationale=f"Critical defect risk ({prediction.defect_probability*100:.0f}%). Stop recommended.",
                confidence=0.95,
            )

        if prediction.risk_level == "high":
            # Determine best intervention based on predicted defects
            intervention, params, rationale = self._determine_intervention(prediction)

            return InterventionDecision(
                should_intervene=True,
                intervention_type=intervention,
                parameters=params,
                urgency="soon",
                rationale=rationale,
                confidence=0.85,
            )

        if prediction.risk_level == "medium":
            return InterventionDecision(
                should_intervene=True,
                intervention_type=InterventionType.ADJUST_SPEED,
                parameters={'speed_change_percent': -10},
                urgency="deferred",
                rationale="Elevated risk. Consider reducing speed for better quality.",
                confidence=0.70,
            )

        return InterventionDecision(
            should_intervene=False,
            intervention_type=InterventionType.NONE,
            parameters={},
            urgency="none",
            rationale="Process within acceptable parameters.",
            confidence=0.90,
        )

    def _determine_intervention(
        self,
        prediction: QualityPrediction
    ) -> Tuple[InterventionType, Dict[str, Any], str]:
        """Determine best intervention for high-risk prediction."""
        defect_types = prediction.predicted_defect_types

        if DefectType.LAYER_ADHESION in defect_types:
            return (
                InterventionType.ADJUST_TEMPERATURE,
                {'nozzle_temp_change': 5},
                "Layer adhesion risk. Increase nozzle temperature."
            )

        if DefectType.CLUTCH_POWER in defect_types:
            if prediction.predicted_clutch_power and prediction.predicted_clutch_power < 1.5:
                return (
                    InterventionType.ADJUST_FLOW,
                    {'flow_change_percent': 3},
                    "Clutch power too low. Increase flow rate."
                )
            elif prediction.predicted_clutch_power and prediction.predicted_clutch_power > 2.5:
                return (
                    InterventionType.ADJUST_FLOW,
                    {'flow_change_percent': -3},
                    "Clutch power too high. Decrease flow rate."
                )

        if DefectType.SURFACE in defect_types:
            return (
                InterventionType.ADJUST_SPEED,
                {'speed_change_percent': -15},
                "Surface quality risk. Reduce print speed."
            )

        # Default intervention
        return (
            InterventionType.PAUSE,
            {},
            "High defect risk. Pause for inspection."
        )

    def train(
        self,
        process_data: List[ProcessSignals],
        quality_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Train the predictive model on historical data."""
        if not SKLEARN_AVAILABLE:
            return {'error': 'scikit-learn not available'}

        if len(process_data) < 100:
            return {'error': 'Insufficient training data (need 100+ samples)'}

        # Prepare features and labels
        X = np.array([s.to_feature_vector() for s in process_data])
        y_defect = np.array([1 if r.get('has_defect', False) else 0 for r in quality_results])

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train classifier
        self.defect_classifier.fit(X_scaled, y_defect)

        self._is_trained = True

        # Return training metrics
        from sklearn.model_selection import cross_val_score
        scores = cross_val_score(self.defect_classifier, X_scaled, y_defect, cv=5)

        return {
            'samples_trained': len(process_data),
            'cv_accuracy': float(scores.mean()),
            'cv_std': float(scores.std()),
            'defect_rate': float(y_defect.mean()),
        }

    def add_training_sample(
        self,
        signals: ProcessSignals,
        actual_result: Dict[str, Any]
    ) -> None:
        """Add a sample for future training."""
        self._training_data.append((signals, actual_result))

    def get_model_info(self) -> Dict[str, Any]:
        """Get model information."""
        return {
            'is_trained': self._is_trained,
            'sklearn_available': SKLEARN_AVAILABLE,
            'training_samples': len(self._training_data),
            'thresholds': {
                'defect_prob': self.DEFECT_PROB_THRESHOLD,
                'high_risk': self.HIGH_RISK_THRESHOLD,
                'critical': self.CRITICAL_THRESHOLD,
            },
            'clutch_power_range': {
                'min': self.CLUTCH_POWER_MIN,
                'target': self.CLUTCH_POWER_TARGET,
                'max': self.CLUTCH_POWER_MAX,
            },
        }
