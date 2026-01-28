"""
FMEA Engine - Failure Mode and Effects Analysis.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

AI-enhanced FMEA with automatic RPN calculation.
"""

from .fmea_engine import FMEAEngine, FailureMode, FMEAAnalysis
from .dfmea import DesignFMEA
from .pfmea import ProcessFMEA
from .rpn_optimizer import RPNOptimizer
from .failure_mode_library import FailureModeLibrary, FailureCategory, ProcessType
from .severity_calculator import SeverityCalculator, SeverityAssessment
from .occurrence_predictor import OccurrencePredictor, OccurrencePrediction, OccurrenceFeatures
from .detection_analyzer import DetectionAnalyzer, DetectionAnalysis, DetectionControl
from .fmea_report_generator import FMEAReportGenerator, FMEAReport, FMEAEntry, ReportFormat

__all__ = [
    'FMEAEngine',
    'FailureMode',
    'FMEAAnalysis',
    'DesignFMEA',
    'ProcessFMEA',
    'RPNOptimizer',
    'FailureModeLibrary',
    'FailureCategory',
    'ProcessType',
    'SeverityCalculator',
    'SeverityAssessment',
    'OccurrencePredictor',
    'OccurrencePrediction',
    'OccurrenceFeatures',
    'DetectionAnalyzer',
    'DetectionAnalysis',
    'DetectionControl',
    'FMEAReportGenerator',
    'FMEAReport',
    'FMEAEntry',
    'ReportFormat',
]
