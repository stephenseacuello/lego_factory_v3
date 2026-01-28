"""
LEGO Factory v3 - Predictive Manufacturing Intelligence
========================================================

Machine learning-powered predictive analytics for manufacturing operations.
Provides real-time predictions with explainable AI (XAI) for operator trust.

Prediction Capabilities
-----------------------
**Cycle Time Prediction** (CycleTimePredictor):
    - Estimates machining time from G-code analysis
    - Features: tool changes, rapid moves, feedrates, complexity
    - Accuracy: Typically within 5-10% of actual
    - Used for: Scheduling, capacity planning, quoting

**Tool Wear Prediction** (ToolWearPredictor):
    - Predicts remaining useful life (RUL) of cutting tools
    - Features: Vibration, spindle load, cutting time, material
    - Wear levels: New, Good, Moderate, Replace Soon, Critical
    - Used for: Tool change scheduling, quality assurance

**Quality Forecasting** (QualityForecaster):
    - Predicts quality outcomes before part completion
    - Features: Process parameters, tool condition, material lot
    - Risk levels: Low, Medium, High, Critical
    - Used for: Proactive intervention, scrap reduction

**Predictive Maintenance** (MaintenancePredictor):
    - Forecasts equipment maintenance needs
    - Types: Preventive, Condition-based, Corrective
    - Features: Sensor data, cycle counts, operating hours
    - Used for: Maintenance scheduling, downtime reduction

AI Explainability
-----------------
All predictions include explanations via PredictionExplainer:
    - Feature contributions (which inputs drove the prediction)
    - Confidence intervals and uncertainty quantification
    - Natural language explanations for operators
    - SHAP-style feature importance visualization

Architecture
------------
The predictive pipeline follows a standard pattern:

    Raw Data → Feature Store → ML Model → Prediction → Explanation
                    ↓
              Feature Config (normalization, aggregation)

Models support both:
    - Online inference: Real-time predictions during machining
    - Batch inference: Historical analysis and model training

Integration with Claude AI:
    - Natural language query of predictions
    - Conversational explanation of model decisions
    - Recommendation synthesis across multiple predictors

Example:
    from services.predictive import (
        get_predictive_service, ToolWearPredictor, PredictionExplainer
    )

    # Get singleton service
    svc = get_predictive_service()

    # Predict tool wear
    wear = await svc.predict_tool_wear(
        tool_id="T001",
        features={"vibration_rms": 0.45, "spindle_load": 72.5}
    )
    print(f"Condition: {wear.condition.name}")  # e.g., "MODERATE"
    print(f"RUL: {wear.remaining_life_minutes} min")

    # Get explanation
    explainer = PredictionExplainer()
    explanation = explainer.explain(wear)
    for contrib in explanation.contributions:
        print(f"  {contrib.feature}: {contrib.impact:+.2f}")
"""

from .feature_store import (
    FeatureStore,
    FeatureConfig,
    FeatureVector,
    FeatureType,
)

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
    QualityRisk,
    QualityFactor,
)

from .maintenance_predictor import (
    MaintenancePredictor,
    MaintenancePrediction,
    MaintenanceType,
    MaintenancePriority,
    MaintenanceSchedule,
)

from .explainer import (
    PredictionExplainer,
    Explanation,
    FeatureContribution,
)

from .model_trainer import (
    ModelTrainer,
    TrainingConfig,
    TrainingResult,
    ModelMetrics,
)

from .predictive_service import (
    PredictiveService,
    PredictiveConfig,
    get_predictive_service,
    configure_predictive_service,
)

__all__ = [
    # Feature store
    "FeatureStore",
    "FeatureConfig",
    "FeatureVector",
    "FeatureType",
    # Cycle time
    "CycleTimePredictor",
    "CycleTimePrediction",
    "GCodeFeatures",
    # Tool wear
    "ToolWearPredictor",
    "ToolWearPrediction",
    "ToolCondition",
    "WearLevel",
    # Quality
    "QualityForecaster",
    "QualityPrediction",
    "QualityRisk",
    "QualityFactor",
    # Maintenance
    "MaintenancePredictor",
    "MaintenancePrediction",
    "MaintenanceType",
    "MaintenancePriority",
    "MaintenanceSchedule",
    # Explainer
    "PredictionExplainer",
    "Explanation",
    "FeatureContribution",
    # Training
    "ModelTrainer",
    "TrainingConfig",
    "TrainingResult",
    "ModelMetrics",
    # Main service
    "PredictiveService",
    "PredictiveConfig",
    "get_predictive_service",
    "configure_predictive_service",
]
