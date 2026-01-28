"""
Adaptive Quality Gate - Dynamic quality thresholds.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 4: Closed-Loop Learning
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QualityDecision(Enum):
    """Quality gate decision."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    HOLD = "hold"
    REWORK = "rework"


@dataclass
class QualityThreshold:
    """Quality threshold configuration."""
    metric: str
    lower_limit: float
    upper_limit: float
    target: float
    warning_margin: float = 0.1
    adaptive: bool = True


@dataclass
class QualityResult:
    """Result of quality gate evaluation."""
    decision: QualityDecision
    metrics: Dict[str, float]
    violations: List[str]
    warnings: List[str]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AdaptiveQualityGate:
    """
    Adaptive quality gate with dynamic thresholds.

    Features:
    - Multi-metric evaluation
    - Dynamic threshold adjustment
    - Statistical process control
    - Learning from production data
    """

    def __init__(self):
        self._thresholds: Dict[str, QualityThreshold] = {}
        self._history: List[Dict[str, float]] = []
        self._decision_history: List[QualityResult] = []
        self._adaptation_rate = 0.1
        self._load_default_thresholds()

    def _load_default_thresholds(self) -> None:
        """Load default quality thresholds."""
        # Dimensional accuracy
        self._thresholds["dimensional_accuracy"] = QualityThreshold(
            metric="dimensional_accuracy",
            lower_limit=0.95,
            upper_limit=1.0,
            target=0.99,
            warning_margin=0.02
        )

        # Surface roughness
        self._thresholds["surface_roughness"] = QualityThreshold(
            metric="surface_roughness",
            lower_limit=0.0,
            upper_limit=1.6,
            target=0.8,
            warning_margin=0.2
        )

        # Clutch power (LEGO specific)
        self._thresholds["clutch_force"] = QualityThreshold(
            metric="clutch_force",
            lower_limit=1.0,
            upper_limit=3.0,
            target=2.0,
            warning_margin=0.3
        )

        # Layer adhesion
        self._thresholds["layer_adhesion"] = QualityThreshold(
            metric="layer_adhesion",
            lower_limit=0.8,
            upper_limit=1.0,
            target=0.95,
            warning_margin=0.05
        )

        # Defect count
        self._thresholds["defect_count"] = QualityThreshold(
            metric="defect_count",
            lower_limit=0.0,
            upper_limit=3.0,
            target=0.0,
            warning_margin=1.0
        )

    def set_threshold(self,
                     metric: str,
                     lower: float,
                     upper: float,
                     target: float,
                     warning_margin: float = 0.1,
                     adaptive: bool = True) -> None:
        """Set threshold for a metric."""
        self._thresholds[metric] = QualityThreshold(
            metric=metric,
            lower_limit=lower,
            upper_limit=upper,
            target=target,
            warning_margin=warning_margin,
            adaptive=adaptive
        )

    def evaluate(self, measurements: Dict[str, float]) -> QualityResult:
        """
        Evaluate measurements against quality thresholds.

        Args:
            measurements: Metric measurements

        Returns:
            Quality decision result
        """
        violations = []
        warnings = []
        confidences = []

        for metric, value in measurements.items():
            if metric not in self._thresholds:
                continue

            threshold = self._thresholds[metric]

            # Check for violations
            if value < threshold.lower_limit:
                violations.append(f"{metric}: {value:.3f} < {threshold.lower_limit:.3f}")
            elif value > threshold.upper_limit:
                violations.append(f"{metric}: {value:.3f} > {threshold.upper_limit:.3f}")

            # Check for warnings
            elif value < threshold.lower_limit + threshold.warning_margin:
                warnings.append(f"{metric}: approaching lower limit")
            elif value > threshold.upper_limit - threshold.warning_margin:
                warnings.append(f"{metric}: approaching upper limit")

            # Calculate confidence based on distance from target
            target_dist = abs(value - threshold.target)
            range_size = threshold.upper_limit - threshold.lower_limit
            conf = max(0, 1 - (target_dist / (range_size / 2)))
            confidences.append(conf)

        # Determine decision
        if violations:
            decision = QualityDecision.FAIL
        elif warnings:
            decision = QualityDecision.WARNING
        else:
            decision = QualityDecision.PASS

        confidence = sum(confidences) / len(confidences) if confidences else 1.0

        result = QualityResult(
            decision=decision,
            metrics=measurements,
            violations=violations,
            warnings=warnings,
            confidence=confidence
        )

        # Record history
        self._history.append(measurements)
        self._decision_history.append(result)

        # Adapt thresholds if enabled
        self._adapt_thresholds(measurements)

        logger.info(f"Quality gate: {decision.value} (confidence: {confidence:.2f})")
        return result

    def _adapt_thresholds(self, measurements: Dict[str, float]) -> None:
        """Adapt thresholds based on production data."""
        if len(self._history) < 30:
            return  # Need enough data

        for metric, value in measurements.items():
            if metric not in self._thresholds:
                continue

            threshold = self._thresholds[metric]
            if not threshold.adaptive:
                continue

            # Get recent values
            recent = [h.get(metric) for h in self._history[-30:] if metric in h]
            if not recent:
                continue

            # Calculate statistics
            import statistics
            mean = statistics.mean(recent)
            stdev = statistics.stdev(recent) if len(recent) > 1 else 0

            # Adjust warning margins based on process capability
            # If process is stable, tighten margins
            if stdev > 0:
                capability = (threshold.upper_limit - threshold.lower_limit) / (6 * stdev)

                if capability > 2.0:
                    # Very capable process - tighten warnings
                    new_margin = threshold.warning_margin * (1 - self._adaptation_rate)
                elif capability < 1.0:
                    # Not capable - loosen warnings
                    new_margin = threshold.warning_margin * (1 + self._adaptation_rate)
                else:
                    new_margin = threshold.warning_margin

                threshold.warning_margin = max(0.01, min(0.5, new_margin))

    def get_process_capability(self, metric: str) -> Dict[str, float]:
        """Calculate process capability indices."""
        if metric not in self._thresholds:
            return {}

        threshold = self._thresholds[metric]

        recent = [h.get(metric) for h in self._history[-100:] if metric in h]
        if len(recent) < 10:
            return {'error': 'Insufficient data'}

        import statistics
        mean = statistics.mean(recent)
        stdev = statistics.stdev(recent) if len(recent) > 1 else 0.001

        USL = threshold.upper_limit
        LSL = threshold.lower_limit

        # Cp - Process capability
        Cp = (USL - LSL) / (6 * stdev) if stdev > 0 else float('inf')

        # Cpk - Process capability index
        Cpu = (USL - mean) / (3 * stdev) if stdev > 0 else float('inf')
        Cpl = (mean - LSL) / (3 * stdev) if stdev > 0 else float('inf')
        Cpk = min(Cpu, Cpl)

        # Pp, Ppk - Process performance (using overall variation)
        Pp = Cp
        Ppk = Cpk

        return {
            'Cp': Cp,
            'Cpk': Cpk,
            'Pp': Pp,
            'Ppk': Ppk,
            'mean': mean,
            'stdev': stdev,
            'n_samples': len(recent)
        }

    def get_spc_status(self, metric: str) -> Dict[str, Any]:
        """Get statistical process control status."""
        recent = [h.get(metric) for h in self._history[-30:] if metric in h]
        if len(recent) < 10:
            return {'status': 'insufficient_data'}

        import statistics
        mean = statistics.mean(recent)
        stdev = statistics.stdev(recent) if len(recent) > 1 else 0

        # Control limits (3-sigma)
        UCL = mean + 3 * stdev
        LCL = mean - 3 * stdev

        # Warning limits (2-sigma)
        UWL = mean + 2 * stdev
        LWL = mean - 2 * stdev

        latest = recent[-1]

        # Check for out-of-control conditions
        out_of_control = False
        patterns = []

        if latest > UCL or latest < LCL:
            out_of_control = True
            patterns.append("Point outside control limits")

        # Check for run of 7 above/below mean
        if len(recent) >= 7:
            last_7 = recent[-7:]
            if all(v > mean for v in last_7):
                patterns.append("7 points above mean")
            elif all(v < mean for v in last_7):
                patterns.append("7 points below mean")

        # Check for trend
        if len(recent) >= 6:
            last_6 = recent[-6:]
            increasing = all(last_6[i] < last_6[i+1] for i in range(5))
            decreasing = all(last_6[i] > last_6[i+1] for i in range(5))
            if increasing or decreasing:
                patterns.append("Trending pattern detected")

        return {
            'status': 'out_of_control' if out_of_control else 'in_control',
            'mean': mean,
            'stdev': stdev,
            'UCL': UCL,
            'LCL': LCL,
            'UWL': UWL,
            'LWL': LWL,
            'latest_value': latest,
            'patterns': patterns
        }

    def get_decision_history(self,
                            limit: int = 100,
                            decision_filter: Optional[QualityDecision] = None) -> List[QualityResult]:
        """Get decision history."""
        history = self._decision_history[-limit:]

        if decision_filter:
            history = [r for r in history if r.decision == decision_filter]

        return history

    def get_statistics(self) -> Dict[str, Any]:
        """Get quality gate statistics."""
        if not self._decision_history:
            return {'total_evaluations': 0}

        decision_counts = {}
        for result in self._decision_history:
            d = result.decision.value
            decision_counts[d] = decision_counts.get(d, 0) + 1

        total = len(self._decision_history)

        return {
            'total_evaluations': total,
            'decision_counts': decision_counts,
            'pass_rate': decision_counts.get('pass', 0) / total,
            'fail_rate': decision_counts.get('fail', 0) / total,
            'warning_rate': decision_counts.get('warning', 0) / total,
            'average_confidence': sum(r.confidence for r in self._decision_history) / total
        }
