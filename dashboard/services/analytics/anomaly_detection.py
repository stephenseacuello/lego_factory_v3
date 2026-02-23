"""
Anomaly Detection

Real-time anomaly detection for manufacturing operations
using statistical and machine learning methods.

Reference: Six Sigma, SPC (Statistical Process Control)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import math
import statistics

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of anomalies."""
    POINT = "point"              # Single outlier
    CONTEXTUAL = "contextual"    # Abnormal in context
    COLLECTIVE = "collective"    # Group anomaly
    TREND = "trend"              # Trend shift
    LEVEL_SHIFT = "level_shift"  # Sudden level change
    SEASONALITY = "seasonality"  # Seasonal deviation


class DetectionMethod(Enum):
    """Anomaly detection methods."""
    Z_SCORE = "z_score"
    IQR = "iqr"
    MOVING_AVERAGE = "moving_average"
    EWMA = "ewma"
    ISOLATION_FOREST = "isolation_forest"
    DBSCAN = "dbscan"
    CONTROL_CHART = "control_chart"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AnomalyAlert:
    """Anomaly detection alert."""
    alert_id: str
    anomaly_type: AnomalyType
    severity: AlertSeverity
    value: float
    expected_value: float
    deviation: float
    threshold: float
    timestamp: str
    metric_name: str
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "type": self.anomaly_type.value,
            "severity": self.severity.value,
            "value": round(self.value, 4),
            "expected": round(self.expected_value, 4),
            "deviation": round(self.deviation, 4),
            "threshold": round(self.threshold, 4),
            "timestamp": self.timestamp,
            "metric": self.metric_name,
            "context": self.context
        }


@dataclass
class ControlLimits:
    """SPC Control chart limits."""
    ucl: float  # Upper Control Limit
    lcl: float  # Lower Control Limit
    center: float
    usl: Optional[float] = None  # Upper Spec Limit
    lsl: Optional[float] = None  # Lower Spec Limit
    
    def is_in_control(self, value: float) -> bool:
        return self.lcl <= value <= self.ucl
    
    def is_in_spec(self, value: float) -> bool:
        if self.usl is None and self.lsl is None:
            return True
        if self.usl is not None and value > self.usl:
            return False
        if self.lsl is not None and value < self.lsl:
            return False
        return True


class AnomalyDetector:
    """
    Manufacturing Anomaly Detection System.
    
    Implements multiple detection methods:
    - Statistical (Z-score, IQR)
    - Time-series (EWMA, Moving Average)
    - SPC Control Charts
    
    Usage:
        >>> detector = AnomalyDetector()
        >>> alerts = detector.detect(data, method=DetectionMethod.EWMA)
    """
    
    def __init__(
        self,
        z_threshold: float = 3.0,
        iqr_multiplier: float = 1.5,
        ewma_lambda: float = 0.2
    ):
        self.z_threshold = z_threshold
        self.iqr_multiplier = iqr_multiplier
        self.ewma_lambda = ewma_lambda
        self._alert_counter = 0
        logger.info("AnomalyDetector initialized")
    
    def detect(
        self,
        data: List[float],
        method: DetectionMethod = DetectionMethod.Z_SCORE,
        metric_name: str = "metric",
        context: Optional[Dict[str, Any]] = None
    ) -> List[AnomalyAlert]:
        """Detect anomalies in data."""
        if len(data) < 3:
            return []
        
        if method == DetectionMethod.Z_SCORE:
            return self._detect_zscore(data, metric_name, context)
        elif method == DetectionMethod.IQR:
            return self._detect_iqr(data, metric_name, context)
        elif method == DetectionMethod.MOVING_AVERAGE:
            return self._detect_moving_average(data, metric_name, context)
        elif method == DetectionMethod.EWMA:
            return self._detect_ewma(data, metric_name, context)
        elif method == DetectionMethod.CONTROL_CHART:
            return self._detect_control_chart(data, metric_name, context)
        else:
            return self._detect_zscore(data, metric_name, context)
    
    def calculate_control_limits(
        self,
        data: List[float],
        sigma_level: float = 3.0,
        usl: Optional[float] = None,
        lsl: Optional[float] = None
    ) -> ControlLimits:
        """Calculate SPC control limits."""
        if len(data) < 2:
            raise ValueError("Need at least 2 data points")
        
        mean = statistics.mean(data)
        std = statistics.stdev(data)
        
        return ControlLimits(
            ucl=mean + sigma_level * std,
            lcl=mean - sigma_level * std,
            center=mean,
            usl=usl,
            lsl=lsl
        )
    
    def calculate_cpk(
        self,
        data: List[float],
        usl: float,
        lsl: float
    ) -> Dict[str, float]:
        """
        Calculate Process Capability Index (Cpk).
        
        Reference: Six Sigma methodology
        """
        if len(data) < 2:
            return {"cpk": 0, "cp": 0, "cpu": 0, "cpl": 0}
        
        mean = statistics.mean(data)
        std = statistics.stdev(data)
        
        if std == 0:
            return {"cpk": float('inf'), "cp": float('inf'), "cpu": float('inf'), "cpl": float('inf')}
        
        cp = (usl - lsl) / (6 * std)
        cpu = (usl - mean) / (3 * std)
        cpl = (mean - lsl) / (3 * std)
        cpk = min(cpu, cpl)
        
        return {
            "cpk": round(cpk, 4),
            "cp": round(cp, 4),
            "cpu": round(cpu, 4),
            "cpl": round(cpl, 4),
            "mean": round(mean, 4),
            "std": round(std, 4),
            "interpretation": self._interpret_cpk(cpk)
        }
    
    def detect_western_electric_rules(
        self,
        data: List[float],
        limits: ControlLimits
    ) -> List[Dict[str, Any]]:
        """
        Apply Western Electric rules for SPC.
        
        Rules:
        1. One point beyond 3σ
        2. Two of three consecutive points beyond 2σ
        3. Four of five consecutive points beyond 1σ
        4. Eight consecutive points on one side of center
        """
        violations = []
        n = len(data)
        
        one_sigma = (limits.ucl - limits.center) / 3
        two_sigma = 2 * one_sigma
        
        for i in range(n):
            val = data[i]
            
            # Rule 1: Beyond 3σ
            if val > limits.ucl or val < limits.lcl:
                violations.append({
                    "rule": 1,
                    "index": i,
                    "value": val,
                    "description": "Point beyond 3σ limit"
                })
            
            # Rule 2: 2 of 3 beyond 2σ
            if i >= 2:
                window = data[i-2:i+1]
                beyond_2sigma = sum(
                    1 for v in window
                    if v > limits.center + two_sigma or v < limits.center - two_sigma
                )
                if beyond_2sigma >= 2:
                    violations.append({
                        "rule": 2,
                        "index": i,
                        "value": val,
                        "description": "2 of 3 points beyond 2σ"
                    })
            
            # Rule 3: 4 of 5 beyond 1σ
            if i >= 4:
                window = data[i-4:i+1]
                beyond_1sigma = sum(
                    1 for v in window
                    if v > limits.center + one_sigma or v < limits.center - one_sigma
                )
                if beyond_1sigma >= 4:
                    violations.append({
                        "rule": 3,
                        "index": i,
                        "value": val,
                        "description": "4 of 5 points beyond 1σ"
                    })
            
            # Rule 4: 8 consecutive on one side
            if i >= 7:
                window = data[i-7:i+1]
                all_above = all(v > limits.center for v in window)
                all_below = all(v < limits.center for v in window)
                if all_above or all_below:
                    violations.append({
                        "rule": 4,
                        "index": i,
                        "value": val,
                        "description": "8 consecutive points on one side"
                    })
        
        return violations
    
    def _detect_zscore(
        self,
        data: List[float],
        metric_name: str,
        context: Optional[Dict[str, Any]]
    ) -> List[AnomalyAlert]:
        """Detect anomalies using Z-score method."""
        alerts = []
        mean = statistics.mean(data)
        std = statistics.stdev(data)
        
        if std == 0:
            return alerts
        
        for i, value in enumerate(data):
            z = abs((value - mean) / std)
            if z > self.z_threshold:
                alerts.append(self._create_alert(
                    anomaly_type=AnomalyType.POINT,
                    value=value,
                    expected=mean,
                    deviation=z,
                    threshold=self.z_threshold,
                    metric_name=metric_name,
                    context=context
                ))
        
        return alerts
    
    def _detect_iqr(
        self,
        data: List[float],
        metric_name: str,
        context: Optional[Dict[str, Any]]
    ) -> List[AnomalyAlert]:
        """Detect anomalies using IQR method."""
        alerts = []
        sorted_data = sorted(data)
        n = len(sorted_data)
        
        q1 = sorted_data[n // 4]
        q3 = sorted_data[3 * n // 4]
        iqr = q3 - q1
        
        lower_bound = q1 - self.iqr_multiplier * iqr
        upper_bound = q3 + self.iqr_multiplier * iqr
        median = sorted_data[n // 2]
        
        for value in data:
            if value < lower_bound or value > upper_bound:
                deviation = abs(value - median) / (iqr if iqr > 0 else 1)
                alerts.append(self._create_alert(
                    anomaly_type=AnomalyType.POINT,
                    value=value,
                    expected=median,
                    deviation=deviation,
                    threshold=self.iqr_multiplier,
                    metric_name=metric_name,
                    context=context
                ))
        
        return alerts
    
    def _detect_moving_average(
        self,
        data: List[float],
        metric_name: str,
        context: Optional[Dict[str, Any]],
        window: int = 5
    ) -> List[AnomalyAlert]:
        """Detect anomalies using moving average."""
        alerts = []
        n = len(data)
        
        if n < window:
            return alerts
        
        for i in range(window, n):
            ma = sum(data[i-window:i]) / window
            ma_std = statistics.stdev(data[i-window:i]) if window > 1 else 0
            
            if ma_std > 0:
                z = abs((data[i] - ma) / ma_std)
                if z > self.z_threshold:
                    alerts.append(self._create_alert(
                        anomaly_type=AnomalyType.CONTEXTUAL,
                        value=data[i],
                        expected=ma,
                        deviation=z,
                        threshold=self.z_threshold,
                        metric_name=metric_name,
                        context=context
                    ))
        
        return alerts
    
    def _detect_ewma(
        self,
        data: List[float],
        metric_name: str,
        context: Optional[Dict[str, Any]]
    ) -> List[AnomalyAlert]:
        """Detect anomalies using EWMA (Exponentially Weighted Moving Average)."""
        alerts = []
        n = len(data)
        
        if n < 2:
            return alerts
        
        ewma = data[0]
        ewma_var = 0
        lambda_ = self.ewma_lambda
        
        for i in range(1, n):
            # Update EWMA
            ewma = lambda_ * data[i] + (1 - lambda_) * ewma
            
            # Update variance estimate
            ewma_var = lambda_ * (data[i] - ewma) ** 2 + (1 - lambda_) * ewma_var
            ewma_std = math.sqrt(ewma_var)
            
            if ewma_std > 0:
                z = abs((data[i] - ewma) / ewma_std)
                if z > self.z_threshold:
                    alerts.append(self._create_alert(
                        anomaly_type=AnomalyType.CONTEXTUAL,
                        value=data[i],
                        expected=ewma,
                        deviation=z,
                        threshold=self.z_threshold,
                        metric_name=metric_name,
                        context=context
                    ))
        
        return alerts
    
    def _detect_control_chart(
        self,
        data: List[float],
        metric_name: str,
        context: Optional[Dict[str, Any]]
    ) -> List[AnomalyAlert]:
        """Detect anomalies using control chart limits."""
        alerts = []
        limits = self.calculate_control_limits(data)
        
        for value in data:
            if not limits.is_in_control(value):
                deviation = abs(value - limits.center) / ((limits.ucl - limits.center) / 3)
                alerts.append(self._create_alert(
                    anomaly_type=AnomalyType.POINT,
                    value=value,
                    expected=limits.center,
                    deviation=deviation,
                    threshold=3.0,
                    metric_name=metric_name,
                    context=context
                ))
        
        return alerts
    
    def _create_alert(
        self,
        anomaly_type: AnomalyType,
        value: float,
        expected: float,
        deviation: float,
        threshold: float,
        metric_name: str,
        context: Optional[Dict[str, Any]]
    ) -> AnomalyAlert:
        """Create an anomaly alert."""
        self._alert_counter += 1
        
        # Determine severity
        if deviation > threshold * 2:
            severity = AlertSeverity.CRITICAL
        elif deviation > threshold * 1.5:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO
        
        return AnomalyAlert(
            alert_id=f"ANOM-{self._alert_counter:06d}",
            anomaly_type=anomaly_type,
            severity=severity,
            value=value,
            expected_value=expected,
            deviation=deviation,
            threshold=threshold,
            timestamp=datetime.utcnow().isoformat() + "Z",
            metric_name=metric_name,
            context=context or {}
        )
    
    def _interpret_cpk(self, cpk: float) -> str:
        """Interpret Cpk value."""
        if cpk >= 2.0:
            return "Excellent (Six Sigma)"
        elif cpk >= 1.67:
            return "Very Good"
        elif cpk >= 1.33:
            return "Good"
        elif cpk >= 1.0:
            return "Capable"
        elif cpk >= 0.67:
            return "Marginal"
        else:
            return "Incapable"
