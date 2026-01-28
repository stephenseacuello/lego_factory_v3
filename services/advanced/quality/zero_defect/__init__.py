"""
Zero-Defect Quality Control - In-Process Quality Assurance

LegoMCP World-Class Manufacturing System v5.0
Phase 21: Zero-Defect Manufacturing

Advanced quality control for achieving near-zero defects:
- Predictive quality models
- In-process intervention
- Automatic correction
- Process fingerprinting
- Virtual metrology
- Golden batch comparison

Target: <10 DPMO (approaching Six Sigma)
"""

from .predictive_quality import (
    PredictiveQualityModel,
    QualityPrediction,
    InterventionDecision,
)

from .in_process_control import (
    InProcessController,
    LayerAnalysis,
    ParameterAdjustment,
)

from .process_fingerprint import (
    ProcessFingerprint,
    FingerprintMatcher,
    DriftAnalysis,
)

from .virtual_metrology import (
    VirtualMetrology,
    PredictedDimensions,
)

__all__ = [
    # Predictive
    'PredictiveQualityModel',
    'QualityPrediction',
    'InterventionDecision',

    # In-Process
    'InProcessController',
    'LayerAnalysis',
    'ParameterAdjustment',

    # Fingerprinting
    'ProcessFingerprint',
    'FingerprintMatcher',
    'DriftAnalysis',

    # Virtual Metrology
    'VirtualMetrology',
    'PredictedDimensions',
]
