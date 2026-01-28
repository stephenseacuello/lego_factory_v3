"""
Main Predictive Service for CNC SCADA.

Integrates all predictive components:
- Cycle time prediction
- Tool wear prediction
- Quality forecasting
- Maintenance prediction
- AI-powered explanations
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime

from .feature_store import FeatureStore, FeatureConfig, FeatureVector
from .cycle_time_predictor import (
    CycleTimePredictor,
    CycleTimePrediction,
    GCodeFeatures,
)
from .tool_wear_predictor import (
    ToolWearPredictor,
    ToolWearPrediction,
    ToolCondition,
    WearLevel,
)
from .quality_forecaster import (
    QualityForecaster,
    QualityPrediction,
    ProcessParameters,
)
from .maintenance_predictor import (
    MaintenancePredictor,
    MaintenancePrediction,
    MachineState,
)
from .explainer import PredictionExplainer, Explanation
from .model_trainer import ModelTrainer, TrainingConfig, TrainingResult

logger = logging.getLogger(__name__)


@dataclass
class PredictiveConfig:
    """Predictive service configuration."""
    # API keys
    anthropic_api_key: Optional[str] = None

    # Model paths
    model_base_path: str = "./models"
    cycle_time_model_path: Optional[str] = None
    tool_wear_model_path: Optional[str] = None
    quality_model_path: Optional[str] = None
    maintenance_model_path: Optional[str] = None

    # Feature toggles
    enabled: bool = True
    enable_cycle_time: bool = True
    enable_tool_wear: bool = True
    enable_quality: bool = True
    enable_maintenance: bool = True
    enable_explanations: bool = True

    # ML settings
    use_ml_models: bool = False  # Use ML models if available
    fallback_to_analytical: bool = True

    # Feature store settings
    feature_config: FeatureConfig = field(default_factory=FeatureConfig)

    # Training settings
    training_config: TrainingConfig = field(default_factory=TrainingConfig)


class PredictiveService:
    """
    Main predictive manufacturing intelligence service.

    Provides unified interface for all prediction types with
    AI-powered explanations.
    """

    def __init__(self, config: Optional[PredictiveConfig] = None):
        """Initialize predictive service."""
        self.config = config or PredictiveConfig()

        # Initialize feature store
        self.feature_store = FeatureStore(self.config.feature_config)

        # Initialize predictors
        self.cycle_time_predictor = CycleTimePredictor(
            model_path=self.config.cycle_time_model_path,
            use_ml=self.config.use_ml_models,
        )
        self.tool_wear_predictor = ToolWearPredictor(
            model_path=self.config.tool_wear_model_path,
            use_ml=self.config.use_ml_models,
        )
        self.quality_forecaster = QualityForecaster(
            model_path=self.config.quality_model_path,
            use_ml=self.config.use_ml_models,
        )
        self.maintenance_predictor = MaintenancePredictor(
            model_path=self.config.maintenance_model_path,
            use_ml=self.config.use_ml_models,
        )

        # Initialize explainer
        self.explainer = PredictionExplainer(
            anthropic_api_key=self.config.anthropic_api_key,
        )

        # Initialize trainer
        self.config.training_config.save_path = self.config.model_base_path
        self.trainer = ModelTrainer(self.config.training_config)

        # Prediction history
        self._prediction_history: List[Dict[str, Any]] = []

    # =========================================================================
    # Cycle Time Prediction
    # =========================================================================

    async def predict_cycle_time(
        self,
        gcode: str,
        material: str = "aluminum",
        machine_type: str = "mill",
        rapid_rate: float = 5000.0,
        include_explanation: bool = True,
    ) -> Dict[str, Any]:
        """
        Predict cycle time for a G-code program.

        Args:
            gcode: G-code program text
            material: Workpiece material
            machine_type: Type of CNC machine
            rapid_rate: Machine rapid traverse rate (mm/min)
            include_explanation: Whether to include AI explanation

        Returns:
            Dict with prediction and explanation
        """
        if not self.config.enable_cycle_time:
            return {"error": "Cycle time prediction is disabled"}

        # Extract features
        features = self.cycle_time_predictor.extract_features(gcode)

        # Make prediction
        prediction = self.cycle_time_predictor.predict(
            gcode, material, machine_type, rapid_rate
        )

        result = {
            "prediction": prediction.to_dict(),
            "features": features.to_dict(),
        }

        # Add explanation if requested
        if include_explanation and self.config.enable_explanations:
            explanation = await self.explainer.explain_cycle_time(
                predicted_seconds=prediction.predicted_seconds,
                confidence=prediction.confidence,
                features=features.to_dict(),
                breakdown={
                    "cut_time": prediction.cut_time_seconds,
                    "rapid_time": prediction.rapid_time_seconds,
                    "tool_change_time": prediction.tool_change_seconds,
                    "spindle_time": prediction.spindle_time_seconds,
                    "overhead": prediction.overhead_seconds,
                },
                material=material,
                machine_type=machine_type,
            )
            result["explanation"] = explanation.to_dict()

        # Store in history
        self._record_prediction("cycle_time", result)

        return result

    # =========================================================================
    # Tool Wear Prediction
    # =========================================================================

    async def predict_tool_wear(
        self,
        tool_condition: ToolCondition,
        upcoming_job_minutes: float = 0.0,
        upcoming_material: Optional[str] = None,
        include_explanation: bool = True,
    ) -> Dict[str, Any]:
        """
        Predict tool wear and remaining life.

        Args:
            tool_condition: Current tool condition
            upcoming_job_minutes: Duration of upcoming job
            upcoming_material: Material of upcoming job
            include_explanation: Whether to include AI explanation

        Returns:
            Dict with prediction and explanation
        """
        if not self.config.enable_tool_wear:
            return {"error": "Tool wear prediction is disabled"}

        # Make prediction
        prediction = self.tool_wear_predictor.predict(
            tool_condition,
            upcoming_job_minutes,
            upcoming_material,
        )

        result = {
            "prediction": prediction.to_dict(),
            "tool_info": tool_condition.to_dict(),
        }

        # Add explanation if requested
        if include_explanation and self.config.enable_explanations:
            explanation = await self.explainer.explain_tool_wear(
                wear_percentage=prediction.wear_percentage,
                remaining_life_minutes=prediction.remaining_life_minutes,
                factors={
                    "time_based": prediction.time_based_wear,
                    "distance_based": prediction.distance_based_wear,
                    "sensor_based": prediction.sensor_based_wear,
                    "material_adjustment": prediction.material_adjustment,
                },
                tool_info=tool_condition.to_dict(),
                material=upcoming_material or tool_condition.last_material,
            )
            result["explanation"] = explanation.to_dict()

        # Store in history
        self._record_prediction("tool_wear", result)

        return result

    def predict_tool_wear_batch(
        self,
        tools: List[ToolCondition],
    ) -> Dict[str, ToolWearPrediction]:
        """
        Predict wear for multiple tools.

        Returns:
            Dict mapping tool_id to prediction
        """
        return self.tool_wear_predictor.batch_predict(tools)

    def get_tool_replacement_schedule(
        self,
        predictions: Dict[str, ToolWearPrediction],
    ) -> List[Dict[str, Any]]:
        """Generate tool replacement schedule from predictions."""
        return self.tool_wear_predictor.get_replacement_schedule(predictions)

    # =========================================================================
    # Quality Prediction
    # =========================================================================

    async def predict_quality(
        self,
        process_params: ProcessParameters,
        target_tolerance: float = 0.05,
        target_surface_finish: float = 1.6,
        include_explanation: bool = True,
    ) -> Dict[str, Any]:
        """
        Predict part quality.

        Args:
            process_params: Current process parameters
            target_tolerance: Target dimensional tolerance (mm)
            target_surface_finish: Target surface finish (Ra µm)
            include_explanation: Whether to include AI explanation

        Returns:
            Dict with prediction and explanation
        """
        if not self.config.enable_quality:
            return {"error": "Quality prediction is disabled"}

        # Make prediction
        prediction = self.quality_forecaster.predict(
            process_params,
            target_tolerance,
            target_surface_finish,
        )

        result = {
            "prediction": prediction.to_dict(),
            "parameters": {
                "spindle_speed": process_params.spindle_speed,
                "feed_rate": process_params.feed_rate,
                "depth_of_cut": process_params.depth_of_cut,
                "material": process_params.material,
                "tool_wear": process_params.tool_wear_percentage,
            },
        }

        # Add explanation if requested
        if include_explanation and self.config.enable_explanations:
            explanation = await self.explainer.explain_quality(
                quality_score=prediction.quality_score,
                defect_probability=prediction.defect_probability,
                risk_factors={
                    "chatter": prediction.chatter_risk,
                    "thermal_distortion": prediction.thermal_distortion_risk,
                    "tool_deflection": prediction.tool_deflection_risk,
                    "surface_roughness": prediction.surface_roughness_risk,
                },
                process_params=result["parameters"],
            )
            result["explanation"] = explanation.to_dict()

        # Store in history
        self._record_prediction("quality", result)

        return result

    # =========================================================================
    # Maintenance Prediction
    # =========================================================================

    async def predict_maintenance(
        self,
        machine_state: MachineState,
        planning_horizon_days: int = 30,
        include_explanation: bool = True,
    ) -> Dict[str, Any]:
        """
        Predict maintenance needs.

        Args:
            machine_state: Current machine state
            planning_horizon_days: Days to plan ahead
            include_explanation: Whether to include AI explanation

        Returns:
            Dict with prediction and explanation
        """
        if not self.config.enable_maintenance:
            return {"error": "Maintenance prediction is disabled"}

        # Make prediction
        prediction = self.maintenance_predictor.predict(
            machine_state,
            planning_horizon_days,
        )

        result = {
            "prediction": prediction.to_dict(),
            "machine_id": machine_state.machine_id,
        }

        # Add explanation if requested
        if include_explanation and self.config.enable_explanations:
            explanation = await self.explainer.explain_maintenance(
                health_score=prediction.health_score,
                failure_risk=prediction.failure_risk,
                days_until_maintenance=prediction.days_until_maintenance,
                component_health=prediction.component_health,
                anomalies=prediction.anomalies,
            )
            result["explanation"] = explanation.to_dict()

        # Store in history
        self._record_prediction("maintenance", result)

        return result

    # =========================================================================
    # Feature Store Operations
    # =========================================================================

    def extract_gcode_features(self, gcode: str) -> Dict[str, Any]:
        """Extract features from G-code for storage or analysis."""
        return self.feature_store.extract_gcode_features(gcode)

    def store_feature_vector(
        self,
        features: Dict[str, Any],
        entity_id: str,
        entity_type: str,
    ):
        """Store a feature vector for later use."""
        vector = FeatureVector(
            features=features,
            entity_id=entity_id,
            entity_type=entity_type,
        )
        self.feature_store.store_vector(vector)

    def get_feature_history(
        self,
        entity_id: str,
        entity_type: str = "",
        limit: int = 100,
    ) -> List[FeatureVector]:
        """Get feature history for an entity."""
        return self.feature_store.get_history(entity_id, entity_type, limit=limit)

    # =========================================================================
    # Model Training
    # =========================================================================

    def train_cycle_time_model(
        self,
        training_data: List[Dict[str, Any]],
        feature_columns: Optional[List[str]] = None,
    ) -> TrainingResult:
        """Train a cycle time prediction model."""
        if feature_columns is None:
            feature_columns = [
                "line_count", "move_count", "cut_count", "rapid_count",
                "arc_count", "tool_changes", "total_distance", "cut_distance",
                "rapid_distance", "avg_feed_rate", "max_feed_rate", "max_depth",
            ]
        return self.trainer.train_cycle_time_model(
            training_data, feature_columns
        )

    def train_tool_wear_model(
        self,
        training_data: List[Dict[str, Any]],
        feature_columns: Optional[List[str]] = None,
    ) -> TrainingResult:
        """Train a tool wear prediction model."""
        if feature_columns is None:
            feature_columns = [
                "runtime_minutes", "cut_distance_mm", "parts_cut",
                "vibration", "load", "temperature", "material_factor",
            ]
        return self.trainer.train_tool_wear_model(
            training_data, feature_columns
        )

    def train_quality_model(
        self,
        training_data: List[Dict[str, Any]],
        feature_columns: Optional[List[str]] = None,
    ) -> TrainingResult:
        """Train a quality prediction model."""
        if feature_columns is None:
            feature_columns = [
                "spindle_speed", "feed_rate", "depth_of_cut", "width_of_cut",
                "tool_diameter", "tool_wear", "vibration", "spindle_load",
                "temperature", "coolant_flow",
            ]
        return self.trainer.train_quality_model(
            training_data, feature_columns
        )

    def train_maintenance_model(
        self,
        training_data: List[Dict[str, Any]],
        feature_columns: Optional[List[str]] = None,
    ) -> TrainingResult:
        """Train a maintenance prediction model."""
        if feature_columns is None:
            feature_columns = [
                "runtime_hours", "runtime_since_maintenance", "power_cycles",
                "spindle_vibration", "x_vibration", "y_vibration", "z_vibration",
                "spindle_temperature", "alarm_count", "servo_errors",
            ]
        return self.trainer.train_maintenance_model(
            training_data, feature_columns
        )

    def get_available_models(self) -> List[Dict[str, Any]]:
        """List available trained models."""
        return self.trainer.get_available_models()

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _record_prediction(self, prediction_type: str, result: Dict[str, Any]):
        """Record a prediction for history tracking."""
        self._prediction_history.append({
            "type": prediction_type,
            "timestamp": datetime.now().isoformat(),
            "result_summary": {
                "prediction_type": prediction_type,
                "success": "error" not in result,
            },
        })

        # Keep history manageable
        if len(self._prediction_history) > 1000:
            self._prediction_history = self._prediction_history[-1000:]

    def get_prediction_history(
        self,
        prediction_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get prediction history."""
        history = self._prediction_history

        if prediction_type:
            history = [h for h in history if h["type"] == prediction_type]

        return history[-limit:]

    def is_available(self) -> Dict[str, bool]:
        """Check which prediction features are available."""
        return {
            "cycle_time": self.config.enable_cycle_time,
            "tool_wear": self.config.enable_tool_wear,
            "quality": self.config.enable_quality,
            "maintenance": self.config.enable_maintenance,
            "explanations": (
                self.config.enable_explanations and
                self.config.anthropic_api_key is not None
            ),
            "ml_models": self.config.use_ml_models,
        }

    def get_service_status(self) -> Dict[str, Any]:
        """Get overall service status."""
        return {
            "enabled": self.config.enabled,
            "features": self.is_available(),
            "models_loaded": {
                "cycle_time": self.cycle_time_predictor._model is not None,
                "tool_wear": self.tool_wear_predictor._model is not None,
                "quality": self.quality_forecaster._model is not None,
                "maintenance": self.maintenance_predictor._model is not None,
            },
            "predictions_made": len(self._prediction_history),
            "feature_store": {
                "features_registered": len(self.feature_store._definitions),
                "cache_size": len(self.feature_store._cache),
            },
        }


# Module-level instance
_predictive_service: Optional[PredictiveService] = None


def get_predictive_service() -> PredictiveService:
    """Get the global predictive service instance."""
    global _predictive_service
    if _predictive_service is None:
        _predictive_service = PredictiveService()
    return _predictive_service


def configure_predictive_service(config: PredictiveConfig) -> PredictiveService:
    """Configure the global predictive service instance."""
    global _predictive_service
    _predictive_service = PredictiveService(config)
    return _predictive_service
