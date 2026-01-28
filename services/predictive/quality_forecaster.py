"""
Quality Forecaster for CNC Manufacturing.

Predicts part quality outcomes based on:
- Process parameters
- Sensor data during cutting
- Historical quality data
- Material properties
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from enum import Enum
import math

logger = logging.getLogger(__name__)


class QualityRisk(Enum):
    """Quality risk levels."""
    LOW = "low"           # <10% defect probability
    MODERATE = "moderate" # 10-30% defect probability
    HIGH = "high"         # 30-60% defect probability
    CRITICAL = "critical" # >60% defect probability


@dataclass
class QualityFactor:
    """A factor affecting quality prediction."""
    name: str
    value: float
    weight: float
    contribution: float  # Contribution to overall score
    status: str  # ok, warning, critical
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "weight": self.weight,
            "contribution": self.contribution,
            "status": self.status,
            "recommendation": self.recommendation,
        }


@dataclass
class QualityPrediction:
    """Quality prediction result."""
    quality_score: float  # 0-100
    defect_probability: float  # 0-1
    risk_level: QualityRisk
    confidence: float  # 0-1

    # Dimensional accuracy prediction
    dimensional_accuracy: float = 0.0  # 0-100
    surface_finish_score: float = 0.0  # 0-100
    tolerance_pass_probability: float = 0.0  # 0-1

    # Contributing factors
    factors: List[QualityFactor] = field(default_factory=list)

    # Specific risks
    chatter_risk: float = 0.0
    thermal_distortion_risk: float = 0.0
    tool_deflection_risk: float = 0.0
    surface_roughness_risk: float = 0.0

    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    parameter_adjustments: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    predicted_at: datetime = field(default_factory=datetime.now)
    model_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "quality_score": self.quality_score,
            "defect_probability": self.defect_probability,
            "risk_level": self.risk_level.value,
            "confidence": self.confidence,
            "details": {
                "dimensional_accuracy": self.dimensional_accuracy,
                "surface_finish_score": self.surface_finish_score,
                "tolerance_pass_probability": self.tolerance_pass_probability,
            },
            "risks": {
                "chatter": self.chatter_risk,
                "thermal_distortion": self.thermal_distortion_risk,
                "tool_deflection": self.tool_deflection_risk,
                "surface_roughness": self.surface_roughness_risk,
            },
            "factors": [f.to_dict() for f in self.factors],
            "recommendations": self.recommendations,
            "parameter_adjustments": self.parameter_adjustments,
            "predicted_at": self.predicted_at.isoformat(),
        }


@dataclass
class ProcessParameters:
    """Current process parameters."""
    # Cutting parameters
    spindle_speed: float = 0.0  # rpm
    feed_rate: float = 0.0  # mm/min
    depth_of_cut: float = 0.0  # mm
    width_of_cut: float = 0.0  # mm

    # Tool parameters
    tool_diameter: float = 0.0  # mm
    tool_length: float = 0.0  # mm
    tool_wear_percentage: float = 0.0

    # Material
    material: str = "aluminum"
    material_hardness: float = 0.0  # HRC

    # Sensor readings
    spindle_load: float = 0.0  # %
    vibration: float = 0.0  # g
    temperature: float = 0.0  # °C
    coolant_flow: float = 0.0  # L/min

    # Historical context
    historical_scrap_rate: float = 0.0  # %
    similar_job_quality_avg: float = 0.0  # 0-100


class QualityForecaster:
    """
    Forecasts part quality during CNC machining.

    Uses multiple indicators:
    - Process parameter stability
    - Sensor signal analysis
    - Historical quality data
    - Physics-based quality models
    """

    # Optimal parameter ranges by material
    OPTIMAL_PARAMS = {
        "aluminum": {
            "surface_speed": (150, 300),  # m/min
            "chip_load": (0.05, 0.15),  # mm/tooth
            "doc_ratio": (0.5, 2.0),  # depth/diameter
        },
        "steel": {
            "surface_speed": (60, 120),
            "chip_load": (0.03, 0.10),
            "doc_ratio": (0.3, 1.5),
        },
        "stainless": {
            "surface_speed": (40, 80),
            "chip_load": (0.02, 0.08),
            "doc_ratio": (0.3, 1.0),
        },
        "brass": {
            "surface_speed": (100, 200),
            "chip_load": (0.05, 0.12),
            "doc_ratio": (0.5, 2.0),
        },
        "plastic": {
            "surface_speed": (200, 500),
            "chip_load": (0.08, 0.20),
            "doc_ratio": (1.0, 3.0),
        },
    }

    # Surface finish factors
    SURFACE_FINISH_FACTORS = {
        "feed_rate": 0.3,
        "tool_wear": 0.25,
        "vibration": 0.25,
        "spindle_speed": 0.2,
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        use_ml: bool = False,
    ):
        """
        Initialize quality forecaster.

        Args:
            model_path: Path to ML model
            use_ml: Whether to use ML predictions
        """
        self.model_path = model_path
        self.use_ml = use_ml
        self._model = None

        # Quality history for calibration
        self._quality_history: List[Dict[str, Any]] = []

        if use_ml and model_path:
            self._load_model()

    def _load_model(self):
        """Load ML model from disk."""
        try:
            import joblib
            self._model = joblib.load(f"{self.model_path}/quality_model.pkl")
            logger.info("Loaded quality forecasting ML model")
        except Exception as e:
            logger.warning(f"Could not load ML model: {e}")
            self.use_ml = False

    def predict(
        self,
        params: ProcessParameters,
        target_tolerance: float = 0.05,  # mm
        target_surface_finish: float = 1.6,  # Ra µm
    ) -> QualityPrediction:
        """
        Predict quality for current process parameters.

        Args:
            params: Current process parameters
            target_tolerance: Target dimensional tolerance (mm)
            target_surface_finish: Target surface finish (Ra µm)

        Returns:
            Quality prediction
        """
        factors = []
        recommendations = []
        parameter_adjustments = {}

        # Analyze cutting parameters
        param_score, param_factors = self._analyze_cutting_parameters(params)
        factors.extend(param_factors)

        # Analyze tool condition
        tool_score, tool_factors = self._analyze_tool_condition(params)
        factors.extend(tool_factors)

        # Analyze sensor signals
        sensor_score, sensor_factors = self._analyze_sensor_signals(params)
        factors.extend(sensor_factors)

        # Calculate specific risks
        chatter_risk = self._calculate_chatter_risk(params)
        thermal_risk = self._calculate_thermal_risk(params)
        deflection_risk = self._calculate_tool_deflection_risk(params)
        roughness_risk = self._calculate_surface_roughness_risk(
            params, target_surface_finish
        )

        # Calculate dimensional accuracy
        dimensional_accuracy = self._predict_dimensional_accuracy(
            params, target_tolerance, deflection_risk, thermal_risk
        )

        # Calculate surface finish score
        surface_finish_score = self._predict_surface_finish(
            params, target_surface_finish, roughness_risk
        )

        # Combine scores with weights
        quality_score = (
            param_score * 0.30 +
            tool_score * 0.25 +
            sensor_score * 0.25 +
            dimensional_accuracy * 0.10 +
            surface_finish_score * 0.10
        )

        # Calculate defect probability
        risk_scores = [chatter_risk, thermal_risk, deflection_risk, roughness_risk]
        max_risk = max(risk_scores)
        avg_risk = sum(risk_scores) / len(risk_scores)

        defect_probability = self._calculate_defect_probability(
            quality_score, max_risk, avg_risk
        )

        # Determine risk level
        risk_level = self._determine_risk_level(defect_probability)

        # Calculate tolerance pass probability
        tolerance_pass_prob = 1.0 - (defect_probability * 0.7 + deflection_risk * 0.3)

        # Generate recommendations
        recommendations, adjustments = self._generate_recommendations(
            params, factors, chatter_risk, thermal_risk, deflection_risk, roughness_risk
        )

        # Calculate confidence
        confidence = self._calculate_confidence(params)

        return QualityPrediction(
            quality_score=quality_score,
            defect_probability=defect_probability,
            risk_level=risk_level,
            confidence=confidence,
            dimensional_accuracy=dimensional_accuracy,
            surface_finish_score=surface_finish_score,
            tolerance_pass_probability=max(0, min(1, tolerance_pass_prob)),
            factors=factors,
            chatter_risk=chatter_risk,
            thermal_distortion_risk=thermal_risk,
            tool_deflection_risk=deflection_risk,
            surface_roughness_risk=roughness_risk,
            recommendations=recommendations,
            parameter_adjustments=adjustments,
        )

    def _analyze_cutting_parameters(
        self,
        params: ProcessParameters,
    ) -> Tuple[float, List[QualityFactor]]:
        """Analyze cutting parameters for quality impact."""
        factors = []
        score = 100.0

        material = params.material.lower()
        optimal = self.OPTIMAL_PARAMS.get(material, self.OPTIMAL_PARAMS["aluminum"])

        # Calculate surface speed
        if params.tool_diameter > 0 and params.spindle_speed > 0:
            surface_speed = (
                math.pi * params.tool_diameter * params.spindle_speed / 1000
            )  # m/min

            min_speed, max_speed = optimal["surface_speed"]
            if min_speed <= surface_speed <= max_speed:
                status = "ok"
                contribution = 0
            elif surface_speed < min_speed * 0.8 or surface_speed > max_speed * 1.2:
                status = "critical"
                score -= 20
                contribution = -20
            else:
                status = "warning"
                score -= 10
                contribution = -10

            factors.append(QualityFactor(
                name="surface_speed",
                value=surface_speed,
                weight=0.3,
                contribution=contribution,
                status=status,
                recommendation=f"Optimal range: {min_speed}-{max_speed} m/min",
            ))

        # Check feed rate appropriateness
        if params.feed_rate > 0 and params.spindle_speed > 0:
            # Simplified chip load calculation (assuming 4 flutes)
            flutes = 4
            chip_load = params.feed_rate / (params.spindle_speed * flutes)

            min_chip, max_chip = optimal.get("chip_load", (0.03, 0.15))
            if min_chip <= chip_load <= max_chip:
                status = "ok"
                contribution = 0
            elif chip_load < min_chip * 0.5 or chip_load > max_chip * 1.5:
                status = "critical"
                score -= 15
                contribution = -15
            else:
                status = "warning"
                score -= 8
                contribution = -8

            factors.append(QualityFactor(
                name="chip_load",
                value=chip_load,
                weight=0.25,
                contribution=contribution,
                status=status,
                recommendation=f"Optimal range: {min_chip}-{max_chip} mm/tooth",
            ))

        # Check depth of cut ratio
        if params.depth_of_cut > 0 and params.tool_diameter > 0:
            doc_ratio = params.depth_of_cut / params.tool_diameter

            min_ratio, max_ratio = optimal.get("doc_ratio", (0.3, 2.0))
            if min_ratio <= doc_ratio <= max_ratio:
                status = "ok"
                contribution = 0
            elif doc_ratio > max_ratio * 1.5:
                status = "critical"
                score -= 20
                contribution = -20
            elif doc_ratio > max_ratio:
                status = "warning"
                score -= 10
                contribution = -10
            else:
                status = "ok"
                contribution = 0

            factors.append(QualityFactor(
                name="depth_of_cut_ratio",
                value=doc_ratio,
                weight=0.2,
                contribution=contribution,
                status=status,
                recommendation=f"Optimal DOC/diameter ratio: {min_ratio}-{max_ratio}",
            ))

        return max(0, min(100, score)), factors

    def _analyze_tool_condition(
        self,
        params: ProcessParameters,
    ) -> Tuple[float, List[QualityFactor]]:
        """Analyze tool condition impact on quality."""
        factors = []
        score = 100.0

        wear = params.tool_wear_percentage

        if wear < 30:
            status = "ok"
            contribution = 0
        elif wear < 60:
            status = "warning"
            score -= 15
            contribution = -15
        elif wear < 80:
            status = "warning"
            score -= 30
            contribution = -30
        else:
            status = "critical"
            score -= 50
            contribution = -50

        factors.append(QualityFactor(
            name="tool_wear",
            value=wear,
            weight=0.4,
            contribution=contribution,
            status=status,
            recommendation="Replace tool when wear >70%" if wear > 60 else "",
        ))

        # Tool length ratio (long tools = more deflection)
        if params.tool_diameter > 0 and params.tool_length > 0:
            length_ratio = params.tool_length / params.tool_diameter

            if length_ratio < 4:
                status = "ok"
                contribution = 0
            elif length_ratio < 6:
                status = "warning"
                score -= 10
                contribution = -10
            else:
                status = "critical"
                score -= 25
                contribution = -25

            factors.append(QualityFactor(
                name="tool_length_ratio",
                value=length_ratio,
                weight=0.3,
                contribution=contribution,
                status=status,
                recommendation="Consider shorter tool or reduced DOC" if length_ratio > 5 else "",
            ))

        return max(0, min(100, score)), factors

    def _analyze_sensor_signals(
        self,
        params: ProcessParameters,
    ) -> Tuple[float, List[QualityFactor]]:
        """Analyze sensor signals for quality impact."""
        factors = []
        score = 100.0

        # Vibration analysis
        if params.vibration > 0:
            if params.vibration < 0.5:
                status = "ok"
                contribution = 0
            elif params.vibration < 1.0:
                status = "warning"
                score -= 15
                contribution = -15
            elif params.vibration < 2.0:
                status = "warning"
                score -= 30
                contribution = -30
            else:
                status = "critical"
                score -= 50
                contribution = -50

            factors.append(QualityFactor(
                name="vibration",
                value=params.vibration,
                weight=0.35,
                contribution=contribution,
                status=status,
                recommendation="Reduce vibration: check tool, reduce speed, verify workholding",
            ))

        # Spindle load analysis
        if params.spindle_load > 0:
            if params.spindle_load < 60:
                status = "ok"
                contribution = 0
            elif params.spindle_load < 80:
                status = "ok"
                contribution = 0  # Optimal range
            elif params.spindle_load < 100:
                status = "warning"
                score -= 15
                contribution = -15
            else:
                status = "critical"
                score -= 35
                contribution = -35

            factors.append(QualityFactor(
                name="spindle_load",
                value=params.spindle_load,
                weight=0.25,
                contribution=contribution,
                status=status,
                recommendation="Reduce feed or DOC" if params.spindle_load > 90 else "",
            ))

        # Temperature analysis
        if params.temperature > 0:
            if params.temperature < 40:
                status = "ok"
                contribution = 0
            elif params.temperature < 60:
                status = "ok"
                contribution = 0
            elif params.temperature < 80:
                status = "warning"
                score -= 10
                contribution = -10
            else:
                status = "critical"
                score -= 25
                contribution = -25

            factors.append(QualityFactor(
                name="temperature",
                value=params.temperature,
                weight=0.2,
                contribution=contribution,
                status=status,
                recommendation="Check coolant flow" if params.temperature > 70 else "",
            ))

        return max(0, min(100, score)), factors

    def _calculate_chatter_risk(self, params: ProcessParameters) -> float:
        """Calculate risk of chatter/vibration defects."""
        risk = 0.0

        # Vibration is primary indicator
        if params.vibration > 2.0:
            risk += 0.6
        elif params.vibration > 1.0:
            risk += 0.3
        elif params.vibration > 0.5:
            risk += 0.1

        # High spindle speed increases risk
        if params.spindle_speed > 15000:
            risk += 0.2

        # Long tools increase risk
        if params.tool_diameter > 0 and params.tool_length > 0:
            if params.tool_length / params.tool_diameter > 6:
                risk += 0.3
            elif params.tool_length / params.tool_diameter > 4:
                risk += 0.15

        return min(1.0, risk)

    def _calculate_thermal_risk(self, params: ProcessParameters) -> float:
        """Calculate risk of thermal distortion."""
        risk = 0.0

        # High temperature
        if params.temperature > 80:
            risk += 0.4
        elif params.temperature > 60:
            risk += 0.2

        # Low coolant flow increases risk
        if params.coolant_flow < 2.0:
            risk += 0.3
        elif params.coolant_flow < 5.0:
            risk += 0.1

        # High spindle load generates heat
        if params.spindle_load > 90:
            risk += 0.2

        return min(1.0, risk)

    def _calculate_tool_deflection_risk(self, params: ProcessParameters) -> float:
        """Calculate risk of tool deflection affecting accuracy."""
        risk = 0.0

        if params.tool_diameter > 0:
            # Length to diameter ratio
            if params.tool_length > 0:
                ratio = params.tool_length / params.tool_diameter
                if ratio > 6:
                    risk += 0.5
                elif ratio > 4:
                    risk += 0.25
                elif ratio > 3:
                    risk += 0.1

            # Small diameter tools deflect more
            if params.tool_diameter < 3:
                risk += 0.2
            elif params.tool_diameter < 6:
                risk += 0.1

        # High cutting forces (from load)
        if params.spindle_load > 80:
            risk += 0.2

        # Depth of cut impact
        if params.depth_of_cut > params.tool_diameter * 0.5:
            risk += 0.15

        return min(1.0, risk)

    def _calculate_surface_roughness_risk(
        self,
        params: ProcessParameters,
        target_ra: float,
    ) -> float:
        """Calculate risk of not meeting surface finish target."""
        risk = 0.0

        # Tool wear increases roughness
        if params.tool_wear_percentage > 70:
            risk += 0.4
        elif params.tool_wear_percentage > 50:
            risk += 0.2

        # Vibration causes poor finish
        if params.vibration > 1.0:
            risk += 0.3
        elif params.vibration > 0.5:
            risk += 0.15

        # Feed rate impacts finish (theoretical Ra = f²/8r)
        # Higher feed = rougher finish
        if params.feed_rate > 500:
            risk += 0.2
        elif params.feed_rate > 300:
            risk += 0.1

        # Tight finish requirements are harder
        if target_ra < 0.8:
            risk += 0.2
        elif target_ra < 1.6:
            risk += 0.1

        return min(1.0, risk)

    def _predict_dimensional_accuracy(
        self,
        params: ProcessParameters,
        target_tolerance: float,
        deflection_risk: float,
        thermal_risk: float,
    ) -> float:
        """Predict dimensional accuracy score."""
        score = 100.0

        # Deflection impact
        score -= deflection_risk * 30

        # Thermal impact
        score -= thermal_risk * 20

        # Tool wear impact
        if params.tool_wear_percentage > 60:
            score -= (params.tool_wear_percentage - 60) * 0.5

        # Tighter tolerances are harder to hold
        if target_tolerance < 0.01:
            score -= 15
        elif target_tolerance < 0.025:
            score -= 8

        return max(0, min(100, score))

    def _predict_surface_finish(
        self,
        params: ProcessParameters,
        target_ra: float,
        roughness_risk: float,
    ) -> float:
        """Predict surface finish score."""
        score = 100.0

        # Roughness risk is primary factor
        score -= roughness_risk * 40

        # Tool wear impact
        if params.tool_wear_percentage > 50:
            score -= (params.tool_wear_percentage - 50) * 0.4

        # Vibration impact
        if params.vibration > 0.5:
            score -= params.vibration * 10

        return max(0, min(100, score))

    def _calculate_defect_probability(
        self,
        quality_score: float,
        max_risk: float,
        avg_risk: float,
    ) -> float:
        """Calculate overall defect probability."""
        # Base probability from quality score
        base_prob = (100 - quality_score) / 100

        # Risk adjustment
        risk_factor = (max_risk * 0.6 + avg_risk * 0.4)

        # Combined probability
        probability = base_prob * 0.5 + risk_factor * 0.5

        return min(1.0, max(0.0, probability))

    def _determine_risk_level(self, defect_probability: float) -> QualityRisk:
        """Determine quality risk level from defect probability."""
        if defect_probability < 0.1:
            return QualityRisk.LOW
        elif defect_probability < 0.3:
            return QualityRisk.MODERATE
        elif defect_probability < 0.6:
            return QualityRisk.HIGH
        else:
            return QualityRisk.CRITICAL

    def _generate_recommendations(
        self,
        params: ProcessParameters,
        factors: List[QualityFactor],
        chatter_risk: float,
        thermal_risk: float,
        deflection_risk: float,
        roughness_risk: float,
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Generate quality improvement recommendations."""
        recommendations = []
        adjustments = {}

        # Address critical factors
        for factor in factors:
            if factor.status == "critical" and factor.recommendation:
                recommendations.append(factor.recommendation)

        # Chatter mitigation
        if chatter_risk > 0.5:
            recommendations.append("High chatter risk: reduce spindle speed by 10-15%")
            adjustments["spindle_speed"] = params.spindle_speed * 0.88

        # Thermal mitigation
        if thermal_risk > 0.5:
            recommendations.append("Thermal risk: increase coolant flow or reduce cutting speed")
            adjustments["feed_rate"] = params.feed_rate * 0.9

        # Deflection mitigation
        if deflection_risk > 0.5:
            recommendations.append("Deflection risk: reduce depth of cut or use shorter tool")
            adjustments["depth_of_cut"] = params.depth_of_cut * 0.75

        # Roughness mitigation
        if roughness_risk > 0.5:
            recommendations.append("Surface finish risk: reduce feed rate or replace worn tool")
            adjustments["feed_rate"] = params.feed_rate * 0.85

        # Tool wear recommendation
        if params.tool_wear_percentage > 70:
            recommendations.append("Tool wear >70%: schedule replacement before next part")

        return recommendations, adjustments

    def _calculate_confidence(self, params: ProcessParameters) -> float:
        """Calculate prediction confidence."""
        confidence = 0.75  # Base confidence

        # More sensor data = higher confidence
        sensors_available = sum([
            params.vibration > 0,
            params.spindle_load > 0,
            params.temperature > 0,
            params.coolant_flow > 0,
        ])
        confidence += sensors_available * 0.05

        # Historical data improves confidence
        if params.historical_scrap_rate > 0:
            confidence += 0.05

        if params.similar_job_quality_avg > 0:
            confidence += 0.05

        return min(0.95, confidence)

    def record_actual_quality(
        self,
        prediction: QualityPrediction,
        actual_quality: float,
        defect_occurred: bool,
    ):
        """
        Record actual quality outcome for model calibration.

        Args:
            prediction: The prediction that was made
            actual_quality: Actual measured quality score
            defect_occurred: Whether a defect was found
        """
        self._quality_history.append({
            "timestamp": datetime.now().isoformat(),
            "predicted_score": prediction.quality_score,
            "actual_score": actual_quality,
            "predicted_defect_prob": prediction.defect_probability,
            "defect_occurred": defect_occurred,
        })

        # Keep last 1000 records
        if len(self._quality_history) > 1000:
            self._quality_history = self._quality_history[-1000:]

    def get_model_accuracy(self) -> Dict[str, float]:
        """Get model accuracy metrics from history."""
        if len(self._quality_history) < 10:
            return {"available": False, "reason": "insufficient data"}

        # Calculate metrics
        score_errors = []
        correct_defect_predictions = 0

        for record in self._quality_history:
            error = abs(record["predicted_score"] - record["actual_score"])
            score_errors.append(error)

            predicted_defect = record["predicted_defect_prob"] > 0.5
            if predicted_defect == record["defect_occurred"]:
                correct_defect_predictions += 1

        return {
            "available": True,
            "samples": len(self._quality_history),
            "mean_absolute_error": sum(score_errors) / len(score_errors),
            "defect_prediction_accuracy": correct_defect_predictions / len(self._quality_history),
        }
