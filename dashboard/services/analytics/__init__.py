"""
Analytics Services

Advanced analytics for manufacturing intelligence,
predictive insights, and decision support.

Features:
- Real-time analytics engine
- Predictive analytics
- Anomaly detection
- Pattern recognition
- Business intelligence dashboards
"""

from .analytics_engine import (
    AnalyticsEngine,
    AnalyticsQuery,
    AnalyticsResult,
    AggregationType,
)
from .predictive_analytics import (
    PredictiveModel,
    ForecastResult,
    TrendAnalysis,
    SeasonalDecomposition,
)
from .anomaly_detection import (
    AnomalyDetector,
    AnomalyType,
    AnomalyAlert,
    DetectionMethod,
)
from .pattern_recognition import (
    PatternMatcher,
    PatternType,
    MatchResult,
)
from .kpi_dashboard import (
    KPIDashboard,
    KPIMetric,
    DashboardWidget,
)

__all__ = [
    "AnalyticsEngine",
    "AnalyticsQuery",
    "AnalyticsResult",
    "AggregationType",
    "PredictiveModel",
    "ForecastResult",
    "TrendAnalysis",
    "SeasonalDecomposition",
    "AnomalyDetector",
    "AnomalyType",
    "AnomalyAlert",
    "DetectionMethod",
    "PatternMatcher",
    "PatternType",
    "MatchResult",
    "KPIDashboard",
    "KPIMetric",
    "DashboardWidget",
]
