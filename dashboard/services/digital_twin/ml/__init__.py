"""
Digital Twin ML Module - Predictive Analytics & Physics-Informed Learning.

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Failure prediction
- Remaining Useful Life (RUL) estimation
- Anomaly detection
- Feature engineering
- Physics-Informed Neural Networks (PINN)
- Manufacturing physics constraints
- Hybrid physics + data-driven models

Research Value:
- Novel PINN approach for FDM printing process
- Physics-constrained quality prediction
- Hybrid modeling for sparse data scenarios
"""

from .failure_predictor import (
    FailurePredictor,
    FailurePrediction,
    PredictorConfig,
    get_failure_predictor,
)

from .rul_estimator import (
    RULEstimator,
    RULEstimate,
    RULConfig,
    DegradationModel,
    get_rul_estimator,
)

from .anomaly_detector import (
    AnomalyDetector,
    AnomalyResult,
    AnomalyConfig,
    AnomalyType,
    get_anomaly_detector,
)

# Physics-Informed ML imports (lazy to avoid missing dependencies)
try:
    from .pinn_model import (
        PhysicsInformedNN,
        PINNTrainer,
        PINNLayer,
        ThermalPINN,
        MechanicalPINN,
        FDMProcessPINN,
    )
    from .physics_constraints import (
        PhysicsConstraint,
        ThermalConstraints,
        MechanicalConstraints,
        FluidConstraints,
        ManufacturingConstraints,
        ConstraintEnforcer,
    )
    from .hybrid_model import (
        HybridModel,
        PhysicsDataFusion,
        ResidualPhysicsNet,
        EnsembleHybridModel,
        UncertaintyQuantifier,
    )
    _PINN_AVAILABLE = True
except ImportError:
    _PINN_AVAILABLE = False


__all__ = [
    # Failure Predictor
    "FailurePredictor",
    "FailurePrediction",
    "PredictorConfig",
    "get_failure_predictor",
    # RUL Estimator
    "RULEstimator",
    "RULEstimate",
    "RULConfig",
    "DegradationModel",
    "get_rul_estimator",
    # Anomaly Detector
    "AnomalyDetector",
    "AnomalyResult",
    "AnomalyConfig",
    "AnomalyType",
    "get_anomaly_detector",
    # PINN
    'PhysicsInformedNN',
    'PINNTrainer',
    'PINNLayer',
    'ThermalPINN',
    'MechanicalPINN',
    'FDMProcessPINN',
    # Constraints
    'PhysicsConstraint',
    'ThermalConstraints',
    'MechanicalConstraints',
    'FluidConstraints',
    'ManufacturingConstraints',
    'ConstraintEnforcer',
    # Hybrid
    'HybridModel',
    'PhysicsDataFusion',
    'ResidualPhysicsNet',
    'EnsembleHybridModel',
    'UncertaintyQuantifier',
]
