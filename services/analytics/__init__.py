"""
Analytics Services for Flask CNC SCADA
======================================
Time accuracy tracking, ML prediction, data alignment, and workflow analytics.

Provides:
- Time accuracy tracking (estimated vs actual)
- Machine learning prediction for job times
- Data alignment across multiple sources for correlation analysis
- Statistical process control (SPC)
- Predictive maintenance indicators

Usage:
    from services.analytics import get_time_accuracy_tracker, get_ml_predictor

    tracker = get_time_accuracy_tracker()
    tracker.record_completion(job_id, estimated_sec=300, actual_sec=285)

    predictor = get_ml_predictor()
    estimated = predictor.predict_time(gcode_features)

    # Data alignment for correlation analysis
    from services.analytics import get_data_alignment_service

    service = get_data_alignment_service()
    aligned = service.align_time_series([series1, series2], method='interpolate')
    indicators = service.find_leading_indicators(target, candidates, max_lag=60)
"""

from services.analytics.time_accuracy import (
    TimeAccuracyTracker,
    get_time_accuracy_tracker,
)
from services.analytics.ml_predictor import (
    MLTimePredictor,
    get_ml_predictor,
)
from services.analytics.data_alignment_service import (
    DataAlignmentService,
    get_data_alignment_service,
    InterpolationMethod,
    AlignmentMethod,
    AlignmentQualityReport,
    ClockDriftReport,
    LagCorrelationResult,
    LeadingIndicator,
)

__all__ = [
    "TimeAccuracyTracker",
    "get_time_accuracy_tracker",
    "MLTimePredictor",
    "get_ml_predictor",
    "DataAlignmentService",
    "get_data_alignment_service",
    "InterpolationMethod",
    "AlignmentMethod",
    "AlignmentQualityReport",
    "ClockDriftReport",
    "LagCorrelationResult",
    "LeadingIndicator",
]
