"""
Uncertainty Quantification Module
=================================

LegoMCP PhD-Level Manufacturing Platform
Part of the Advanced AI/ML Operations (Phase 8.2)

This module provides comprehensive uncertainty estimation for manufacturing
AI predictions, enabling:

1. **Reliable Decision Making**: Know when to trust model predictions
2. **Risk Assessment**: Quantify prediction confidence for quality control
3. **Active Learning**: Identify samples needing human review
4. **Safety-Critical Applications**: Ensure predictions meet reliability thresholds

Supported Methods:
------------------
- **MC Dropout**: Monte Carlo Dropout for Bayesian approximation
- **Deep Ensemble**: Multiple models for robust uncertainty
- **Conformal Prediction**: Distribution-free prediction intervals
- **Temperature Scaling**: Calibrated classification probabilities

Manufacturing Use Cases:
------------------------
- Defect detection confidence scoring
- Predictive maintenance uncertainty bounds
- Quality prediction reliability assessment
- Process parameter optimization with confidence

Example Usage:
--------------
    from services.ai.uncertainty import (
        UncertaintyEstimator,
        UncertaintyMethod,
    )

    # Initialize estimator
    estimator = UncertaintyEstimator()

    # Estimate uncertainty using MC Dropout
    result = estimator.estimate(
        model=quality_model,
        inputs=sensor_data,
        method=UncertaintyMethod.MC_DROPOUT,
        confidence_level=0.95,
    )

    # Check prediction reliability
    reliable_mask = result.is_reliable

    # Get confidence intervals
    lower, upper = result.confidence_lower, result.confidence_upper

References:
-----------
- Gal & Ghahramani (2016): "Dropout as a Bayesian Approximation"
- Lakshminarayanan et al. (2017): "Simple and Scalable Predictive Uncertainty"
- Vovk et al. (2005): "Algorithmic Learning in a Random World" (Conformal)
- Guo et al. (2017): "On Calibration of Modern Neural Networks"

Author: LegoMCP Team
Version: 2.0.0
"""

from .uncertainty_estimator import (
    # Core estimator interface
    UncertaintyEstimator,
    UncertaintyEstimatorBase,

    # Result container
    UncertaintyResult,

    # Available methods
    UncertaintyMethod,

    # Individual estimators
    MCDropout,
    DeepEnsemble,
    ConformalPredictor,
    TemperatureScaling,

    # Global instance for convenience
    uncertainty_estimator,
)

__all__ = [
    # Main interface
    "UncertaintyEstimator",
    "UncertaintyEstimatorBase",
    "UncertaintyResult",
    "UncertaintyMethod",

    # Estimator implementations
    "MCDropout",
    "DeepEnsemble",
    "ConformalPredictor",
    "TemperatureScaling",

    # Convenience instance
    "uncertainty_estimator",
]

__version__ = "2.0.0"
__author__ = "LegoMCP Team"
