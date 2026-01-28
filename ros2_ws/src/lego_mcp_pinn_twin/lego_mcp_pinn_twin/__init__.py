"""
LEGO MCP Physics-Informed Neural Network Digital Twin

ISO 23247 Compliant Digital Twin Implementation

This package provides:
- Physics-constrained neural network models
- Real-time state estimation with uncertainty
- Predictive maintenance via degradation modeling
- Causal discovery for root cause analysis
- Anomaly detection via physics violation

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                     PINN DIGITAL TWIN                        │
    ├─────────────────────────────────────────────────────────────┤
    │                                                              │
    │  ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐   │
    │  │   Physics   │   │   Neural    │   │   Uncertainty   │   │
    │  │    Loss     │ + │   Network   │ = │   Quantified    │   │
    │  │ (PDE/ODE)   │   │   (MLP)     │   │   Prediction    │   │
    │  └─────────────┘   └─────────────┘   └─────────────────┘   │
    │                                                              │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │                  MODEL COMPONENTS                    │   │
    │  ├─────────────────────────────────────────────────────┤   │
    │  │ • ThermalDynamicsPINN - Heat transfer physics       │   │
    │  │ • KinematicChainPINN - Robot kinematics/dynamics    │   │
    │  │ • MaterialFlowPINN - Manufacturing process flow     │   │
    │  │ • DegradationPINN - Equipment wear prediction       │   │
    │  └─────────────────────────────────────────────────────┘   │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘

Standards Compliance:
- ISO 23247-1: Digital Twin Framework
- ISO 23247-2: Reference Architecture
- ISO 23247-3: Digital Representation
- ISO 23247-4: Information Exchange
"""

__version__ = "1.0.0"
__author__ = "LEGO MCP Digital Twin Team"

from .models.base_pinn import BasePINN, PhysicsLoss
from .models.thermal_dynamics import ThermalDynamicsPINN
from .models.kinematic_chain import KinematicChainPINN
from .models.material_flow import MaterialFlowPINN
from .models.degradation_model import DegradationPINN
from .inference.realtime_predictor import RealtimePredictor
from .inference.uncertainty_quantifier import UncertaintyQuantifier
from .inference.anomaly_detector import PhysicsAnomalyDetector
from .training.physics_loss import PhysicsLossFunction
from .training.hybrid_trainer import HybridTrainer

__all__ = [
    "BasePINN",
    "PhysicsLoss",
    "ThermalDynamicsPINN",
    "KinematicChainPINN",
    "MaterialFlowPINN",
    "DegradationPINN",
    "RealtimePredictor",
    "UncertaintyQuantifier",
    "PhysicsAnomalyDetector",
    "PhysicsLossFunction",
    "HybridTrainer",
]
