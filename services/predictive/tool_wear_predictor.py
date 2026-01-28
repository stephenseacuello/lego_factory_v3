"""
Tool Wear Predictor for CNC Manufacturing.

Predicts tool wear and remaining useful life based on:
- Cutting time and distance
- Material properties
- Sensor data (vibration, load, temperature)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import math

logger = logging.getLogger(__name__)


class WearLevel(Enum):
    """Tool wear levels."""
    NEW = "new"           # 0-10% wear
    GOOD = "good"         # 10-40% wear
    MODERATE = "moderate" # 40-70% wear
    HIGH = "high"         # 70-90% wear
    CRITICAL = "critical" # 90-100% wear
    WORN_OUT = "worn_out" # >100% wear


@dataclass
class ToolCondition:
    """Current condition of a tool."""
    tool_id: str
    tool_type: str  # endmill, drill, etc.
    diameter: float  # mm
    material: str  # carbide, hss, etc.
    flutes: int = 4

    # Usage metrics
    total_runtime_minutes: float = 0.0
    total_cut_distance_mm: float = 0.0
    total_parts_cut: int = 0

    # Manufacturer limits
    rated_life_minutes: float = 120.0
    rated_cut_distance_mm: float = 50000.0

    # Current readings
    current_vibration: float = 0.0  # g
    current_load: float = 0.0  # %
    current_temperature: float = 0.0  # °C

    # Last materials cut
    last_material: str = "aluminum"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_id": self.tool_id,
            "tool_type": self.tool_type,
            "diameter": self.diameter,
            "material": self.material,
            "flutes": self.flutes,
            "usage": {
                "runtime_minutes": self.total_runtime_minutes,
                "cut_distance_mm": self.total_cut_distance_mm,
                "parts_cut": self.total_parts_cut,
            },
            "rated_life": {
                "minutes": self.rated_life_minutes,
                "cut_distance_mm": self.rated_cut_distance_mm,
            },
            "current_readings": {
                "vibration_g": self.current_vibration,
                "load_percent": self.current_load,
                "temperature_c": self.current_temperature,
            },
        }


@dataclass
class ToolWearPrediction:
    """Tool wear prediction result."""
    tool_id: str
    wear_percentage: float  # 0-100+
    wear_level: WearLevel
    remaining_life_minutes: float
    remaining_life_parts: int
    confidence: float  # 0-1

    # Risk assessment
    risk_score: float = 0.0  # 0-10
    failure_probability: float = 0.0  # 0-1

    # Contributing factors
    time_based_wear: float = 0.0
    distance_based_wear: float = 0.0
    sensor_based_wear: float = 0.0
    material_adjustment: float = 0.0

    # Recommendations
    action_required: str = "none"  # none, monitor, plan_replacement, replace_now
    recommended_replacement_date: Optional[datetime] = None
    notes: List[str] = field(default_factory=list)

    # Metadata
    predicted_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_id": self.tool_id,
            "wear": {
                "percentage": self.wear_percentage,
                "level": self.wear_level.value,
                "remaining_life_minutes": self.remaining_life_minutes,
                "remaining_life_parts": self.remaining_life_parts,
            },
            "confidence": self.confidence,
            "risk": {
                "score": self.risk_score,
                "failure_probability": self.failure_probability,
            },
            "factors": {
                "time_based": self.time_based_wear,
                "distance_based": self.distance_based_wear,
                "sensor_based": self.sensor_based_wear,
                "material_adjustment": self.material_adjustment,
            },
            "recommendation": {
                "action": self.action_required,
                "replacement_date": (
                    self.recommended_replacement_date.isoformat()
                    if self.recommended_replacement_date else None
                ),
                "notes": self.notes,
            },
            "predicted_at": self.predicted_at.isoformat(),
        }


class ToolWearPredictor:
    """
    Predicts tool wear and remaining useful life.

    Uses multiple signals:
    - Time-based: Runtime vs rated life
    - Distance-based: Cut distance vs rated distance
    - Sensor-based: Vibration, load, temperature trends
    - Material-based: Adjustment for material hardness
    """

    # Material wear multipliers
    MATERIAL_WEAR_FACTORS = {
        "aluminum": 1.0,
        "brass": 1.2,
        "plastic": 0.5,
        "wood": 0.3,
        "steel": 2.5,
        "stainless": 3.0,
        "titanium": 5.0,
        "inconel": 6.0,
        "cast iron": 2.0,
        "hardened steel": 4.0,
    }

    # Tool material durability
    TOOL_MATERIAL_FACTORS = {
        "hss": 1.0,
        "high speed steel": 1.0,
        "carbide": 3.0,
        "ceramic": 4.0,
        "cbn": 5.0,  # Cubic boron nitride
        "diamond": 8.0,
        "pcd": 7.0,  # Polycrystalline diamond
    }

    # Vibration thresholds (g)
    VIBRATION_THRESHOLDS = {
        "normal": 0.5,
        "elevated": 1.0,
        "warning": 2.0,
        "critical": 3.0,
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        use_ml: bool = False,
    ):
        """
        Initialize tool wear predictor.

        Args:
            model_path: Path to ML model
            use_ml: Whether to use ML predictions
        """
        self.model_path = model_path
        self.use_ml = use_ml
        self._model = None

        # Tool history for trend analysis
        self._tool_history: Dict[str, List[Dict[str, Any]]] = {}

        if use_ml and model_path:
            self._load_model()

    def _load_model(self):
        """Load ML model from disk."""
        try:
            import joblib
            self._model = joblib.load(f"{self.model_path}/tool_wear_model.pkl")
            logger.info("Loaded tool wear ML model")
        except Exception as e:
            logger.warning(f"Could not load ML model: {e}")
            self.use_ml = False

    def predict(
        self,
        condition: ToolCondition,
        upcoming_job_minutes: float = 0.0,
        upcoming_material: Optional[str] = None,
    ) -> ToolWearPrediction:
        """
        Predict tool wear and remaining life.

        Args:
            condition: Current tool condition
            upcoming_job_minutes: Duration of upcoming job
            upcoming_material: Material of upcoming job

        Returns:
            Tool wear prediction
        """
        notes = []

        # Get material factors
        work_material = upcoming_material or condition.last_material
        material_factor = self.MATERIAL_WEAR_FACTORS.get(
            work_material.lower(), 1.0
        )
        tool_material_factor = self.TOOL_MATERIAL_FACTORS.get(
            condition.material.lower(), 1.0
        )

        # Effective wear factor
        effective_factor = material_factor / tool_material_factor

        # Calculate time-based wear
        adjusted_runtime = condition.total_runtime_minutes * effective_factor
        time_wear = (adjusted_runtime / condition.rated_life_minutes) * 100

        # Calculate distance-based wear
        adjusted_distance = condition.total_cut_distance_mm * effective_factor
        distance_wear = (adjusted_distance / condition.rated_cut_distance_mm) * 100

        # Calculate sensor-based wear adjustment
        sensor_wear = self._calculate_sensor_wear(condition)

        # Combine wear estimates
        # Weight: 30% time, 40% distance, 30% sensor
        combined_wear = (
            time_wear * 0.3 +
            distance_wear * 0.4 +
            sensor_wear * 0.3
        )

        # Apply material adjustment
        material_adjustment = (effective_factor - 1.0) * 10

        # Final wear percentage
        wear_percentage = combined_wear + material_adjustment

        # Determine wear level
        wear_level = self._get_wear_level(wear_percentage)

        # Calculate remaining life
        if wear_percentage >= 100:
            remaining_minutes = 0.0
        else:
            remaining_percentage = 100 - wear_percentage
            remaining_minutes = (
                remaining_percentage / 100 *
                condition.rated_life_minutes /
                effective_factor
            )

        # Estimate remaining parts
        if condition.total_parts_cut > 0:
            avg_runtime_per_part = (
                condition.total_runtime_minutes / condition.total_parts_cut
            )
            remaining_parts = int(remaining_minutes / max(1, avg_runtime_per_part))
        else:
            remaining_parts = int(remaining_minutes / 5)  # Assume 5 min per part

        # Calculate risk score
        risk_score = self._calculate_risk_score(
            wear_percentage, condition, upcoming_job_minutes
        )

        # Calculate failure probability
        failure_probability = self._calculate_failure_probability(
            wear_percentage, sensor_wear
        )

        # Determine action
        action, replacement_date = self._determine_action(
            wear_percentage,
            remaining_minutes,
            risk_score,
            upcoming_job_minutes,
        )

        # Generate notes
        if wear_level == WearLevel.CRITICAL:
            notes.append("Tool near end of life - replacement recommended")
        elif wear_level == WearLevel.HIGH:
            notes.append("Monitor closely - plan replacement soon")

        if condition.current_vibration > self.VIBRATION_THRESHOLDS["warning"]:
            notes.append(f"High vibration detected: {condition.current_vibration:.2f}g")

        if condition.current_load > 80:
            notes.append(f"High spindle load: {condition.current_load:.1f}%")

        if upcoming_job_minutes > remaining_minutes * 0.8:
            notes.append("May not complete upcoming job - consider replacement")

        # Calculate confidence
        confidence = self._calculate_confidence(condition)

        return ToolWearPrediction(
            tool_id=condition.tool_id,
            wear_percentage=wear_percentage,
            wear_level=wear_level,
            remaining_life_minutes=remaining_minutes,
            remaining_life_parts=remaining_parts,
            confidence=confidence,
            risk_score=risk_score,
            failure_probability=failure_probability,
            time_based_wear=time_wear,
            distance_based_wear=distance_wear,
            sensor_based_wear=sensor_wear,
            material_adjustment=material_adjustment,
            action_required=action,
            recommended_replacement_date=replacement_date,
            notes=notes,
        )

    def _calculate_sensor_wear(self, condition: ToolCondition) -> float:
        """Calculate wear estimate from sensor data."""
        sensor_wear = 0.0

        # Vibration contribution
        if condition.current_vibration > 0:
            if condition.current_vibration > self.VIBRATION_THRESHOLDS["critical"]:
                sensor_wear += 40
            elif condition.current_vibration > self.VIBRATION_THRESHOLDS["warning"]:
                sensor_wear += 25
            elif condition.current_vibration > self.VIBRATION_THRESHOLDS["elevated"]:
                sensor_wear += 15
            elif condition.current_vibration > self.VIBRATION_THRESHOLDS["normal"]:
                sensor_wear += 5

        # Load contribution
        if condition.current_load > 0:
            if condition.current_load > 100:
                sensor_wear += 30
            elif condition.current_load > 80:
                sensor_wear += 20
            elif condition.current_load > 60:
                sensor_wear += 10

        # Temperature contribution (if significantly elevated)
        if condition.current_temperature > 100:
            sensor_wear += (condition.current_temperature - 100) * 0.5

        return sensor_wear

    def _get_wear_level(self, wear_percentage: float) -> WearLevel:
        """Determine wear level from percentage."""
        if wear_percentage < 10:
            return WearLevel.NEW
        elif wear_percentage < 40:
            return WearLevel.GOOD
        elif wear_percentage < 70:
            return WearLevel.MODERATE
        elif wear_percentage < 90:
            return WearLevel.HIGH
        elif wear_percentage < 100:
            return WearLevel.CRITICAL
        else:
            return WearLevel.WORN_OUT

    def _calculate_risk_score(
        self,
        wear_percentage: float,
        condition: ToolCondition,
        upcoming_minutes: float,
    ) -> float:
        """
        Calculate risk score (0-10).

        Higher risk for:
        - High wear combined with long upcoming job
        - Elevated sensor readings
        - Critical operations
        """
        risk = 0.0

        # Base risk from wear
        risk += (wear_percentage / 100) * 5

        # Risk from sensor readings
        if condition.current_vibration > self.VIBRATION_THRESHOLDS["warning"]:
            risk += 2
        elif condition.current_vibration > self.VIBRATION_THRESHOLDS["elevated"]:
            risk += 1

        if condition.current_load > 80:
            risk += 1.5

        # Risk from upcoming workload
        remaining_capacity = 100 - wear_percentage
        if upcoming_minutes > 0:
            # Estimate wear from upcoming job
            upcoming_wear = (
                upcoming_minutes / condition.rated_life_minutes * 100
            )
            if upcoming_wear > remaining_capacity:
                risk += 2  # Won't complete job

        return min(10, risk)

    def _calculate_failure_probability(
        self,
        wear_percentage: float,
        sensor_wear: float,
    ) -> float:
        """
        Calculate probability of catastrophic failure.

        Uses logistic function to model increasing failure probability.
        """
        # Combined wear indicator
        combined = (wear_percentage * 0.7) + (sensor_wear * 0.3)

        # Logistic function: probability increases sharply after 80%
        k = 0.1  # Steepness
        x0 = 85  # Midpoint
        probability = 1 / (1 + math.exp(-k * (combined - x0)))

        return min(1.0, probability)

    def _determine_action(
        self,
        wear_percentage: float,
        remaining_minutes: float,
        risk_score: float,
        upcoming_minutes: float,
    ) -> Tuple[str, Optional[datetime]]:
        """Determine recommended action and replacement date."""
        now = datetime.now()

        if wear_percentage >= 100 or risk_score >= 9:
            return "replace_now", now

        if wear_percentage >= 90 or risk_score >= 7:
            # Plan replacement within shift
            return "plan_replacement", now + timedelta(hours=4)

        if wear_percentage >= 70 or risk_score >= 5:
            # Plan replacement within day
            return "plan_replacement", now + timedelta(hours=8)

        if wear_percentage >= 50:
            # Monitor and plan ahead
            replacement_hours = remaining_minutes / 60
            return "monitor", now + timedelta(hours=replacement_hours)

        return "none", None

    def _calculate_confidence(self, condition: ToolCondition) -> float:
        """Calculate prediction confidence."""
        confidence = 0.8  # Base confidence

        # Higher confidence with more usage data
        if condition.total_parts_cut > 50:
            confidence += 0.1
        elif condition.total_parts_cut < 5:
            confidence -= 0.2

        # Lower confidence without sensor data
        if condition.current_vibration == 0 and condition.current_load == 0:
            confidence -= 0.15

        return max(0.4, min(1.0, confidence))

    def record_observation(
        self,
        tool_id: str,
        vibration: float,
        load: float,
        temperature: float,
        runtime_delta: float = 0.0,
    ):
        """
        Record a sensor observation for trend analysis.

        Args:
            tool_id: Tool identifier
            vibration: Current vibration (g)
            load: Current load (%)
            temperature: Current temperature (°C)
            runtime_delta: Additional runtime since last observation
        """
        observation = {
            "timestamp": datetime.now().isoformat(),
            "vibration": vibration,
            "load": load,
            "temperature": temperature,
            "runtime_delta": runtime_delta,
        }

        if tool_id not in self._tool_history:
            self._tool_history[tool_id] = []

        self._tool_history[tool_id].append(observation)

        # Keep last 1000 observations
        if len(self._tool_history[tool_id]) > 1000:
            self._tool_history[tool_id] = self._tool_history[tool_id][-1000:]

    def get_trend(
        self,
        tool_id: str,
        window_minutes: int = 60,
    ) -> Dict[str, Any]:
        """
        Get sensor trends for a tool.

        Returns:
            Trend analysis including direction and rate of change
        """
        if tool_id not in self._tool_history:
            return {"available": False}

        history = self._tool_history[tool_id]
        cutoff = datetime.now() - timedelta(minutes=window_minutes)

        # Filter to window
        recent = [
            obs for obs in history
            if datetime.fromisoformat(obs["timestamp"]) >= cutoff
        ]

        if len(recent) < 3:
            return {"available": False, "reason": "insufficient data"}

        # Calculate trends
        vibrations = [obs["vibration"] for obs in recent]
        loads = [obs["load"] for obs in recent]
        temps = [obs["temperature"] for obs in recent]

        def trend_direction(values: List[float]) -> str:
            if len(values) < 2:
                return "stable"
            start_avg = sum(values[:len(values)//3]) / (len(values)//3)
            end_avg = sum(values[-len(values)//3:]) / (len(values)//3)
            diff = end_avg - start_avg
            if diff > 0.1 * start_avg:
                return "increasing"
            elif diff < -0.1 * start_avg:
                return "decreasing"
            return "stable"

        return {
            "available": True,
            "observations": len(recent),
            "vibration": {
                "current": vibrations[-1],
                "min": min(vibrations),
                "max": max(vibrations),
                "avg": sum(vibrations) / len(vibrations),
                "trend": trend_direction(vibrations),
            },
            "load": {
                "current": loads[-1],
                "min": min(loads),
                "max": max(loads),
                "avg": sum(loads) / len(loads),
                "trend": trend_direction(loads),
            },
            "temperature": {
                "current": temps[-1],
                "min": min(temps),
                "max": max(temps),
                "avg": sum(temps) / len(temps),
                "trend": trend_direction(temps),
            },
        }

    def batch_predict(
        self,
        tools: List[ToolCondition],
    ) -> Dict[str, ToolWearPrediction]:
        """
        Predict wear for multiple tools.

        Returns:
            Dict mapping tool_id to prediction
        """
        results = {}
        for condition in tools:
            results[condition.tool_id] = self.predict(condition)
        return results

    def get_replacement_schedule(
        self,
        predictions: Dict[str, ToolWearPrediction],
    ) -> List[Dict[str, Any]]:
        """
        Generate a tool replacement schedule from predictions.

        Returns:
            Sorted list of recommended replacements
        """
        schedule = []

        for tool_id, pred in predictions.items():
            if pred.action_required != "none":
                schedule.append({
                    "tool_id": tool_id,
                    "action": pred.action_required,
                    "wear_percentage": pred.wear_percentage,
                    "risk_score": pred.risk_score,
                    "recommended_date": pred.recommended_replacement_date,
                    "remaining_life_minutes": pred.remaining_life_minutes,
                })

        # Sort by urgency (action type, then risk score)
        action_priority = {
            "replace_now": 0,
            "plan_replacement": 1,
            "monitor": 2,
        }
        schedule.sort(key=lambda x: (
            action_priority.get(x["action"], 3),
            -x["risk_score"]
        ))

        return schedule
