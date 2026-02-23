"""
A/B Testing Analysis for Manufacturing Experiments.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Platform Infrastructure

Provides statistical analysis for A/B tests in manufacturing:
- Sample size calculation
- Statistical significance testing
- Effect size estimation
- Sequential analysis for early stopping
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import math
import uuid


class TestType(Enum):
    """Type of A/B test."""
    TWO_SAMPLE = "two_sample"
    PAIRED = "paired"
    MULTI_VARIANT = "multi_variant"
    SEQUENTIAL = "sequential"


class MetricType(Enum):
    """Type of metric being tested."""
    CONTINUOUS = "continuous"  # e.g., print time, temperature
    BINARY = "binary"  # e.g., pass/fail, defect/no-defect
    COUNT = "count"  # e.g., defect count per batch
    RATIO = "ratio"  # e.g., yield rate


class TestStatus(Enum):
    """Status of an A/B test."""
    DESIGN = "design"
    RUNNING = "running"
    STOPPED_EARLY = "stopped_early"
    COMPLETED = "completed"
    INCONCLUSIVE = "inconclusive"


@dataclass
class ABTestConfig:
    """Configuration for an A/B test."""
    test_id: str
    name: str
    description: str
    test_type: TestType
    metric_type: MetricType

    # Statistical parameters
    alpha: float = 0.05  # Type I error rate
    power: float = 0.80  # 1 - Type II error rate
    minimum_detectable_effect: float = 0.1  # MDE as proportion

    # Sample allocation
    control_ratio: float = 0.5  # Proportion in control group

    # Sequential testing (optional)
    enable_sequential: bool = False
    max_sample_size: Optional[int] = None
    interim_analyses: int = 5

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"
    tags: List[str] = field(default_factory=list)


@dataclass
class ABTestResult:
    """Results from an A/B test analysis."""
    test_id: str
    status: TestStatus

    # Sample information
    control_n: int
    treatment_n: int

    # Effect estimates
    control_mean: float
    treatment_mean: float
    absolute_effect: float
    relative_effect: float

    # Statistical inference
    test_statistic: float
    p_value: float
    confidence_interval: Tuple[float, float]
    is_significant: bool

    # Effect size
    cohens_d: Optional[float] = None

    # Sequential analysis (if applicable)
    stopped_early: bool = False
    stopping_reason: Optional[str] = None

    # Metadata
    analyzed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_id": self.test_id,
            "status": self.status.value,
            "control_n": self.control_n,
            "treatment_n": self.treatment_n,
            "control_mean": self.control_mean,
            "treatment_mean": self.treatment_mean,
            "absolute_effect": self.absolute_effect,
            "relative_effect": self.relative_effect,
            "test_statistic": self.test_statistic,
            "p_value": self.p_value,
            "confidence_interval": self.confidence_interval,
            "is_significant": self.is_significant,
            "cohens_d": self.cohens_d,
            "stopped_early": self.stopped_early,
            "stopping_reason": self.stopping_reason,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


@dataclass
class SequentialBoundary:
    """Boundary for sequential testing."""
    analysis_number: int
    information_fraction: float
    upper_boundary: float  # Reject null (effect exists)
    lower_boundary: float  # Accept null (no effect)
    futility_boundary: Optional[float] = None


class ABTestAnalyzer:
    """
    A/B Test Analyzer for manufacturing experiments.

    Features:
    - Classical hypothesis testing (t-test, z-test, chi-square)
    - Sequential analysis with O'Brien-Fleming boundaries
    - Effect size calculation
    - Sample size determination
    - Multiple comparison correction
    """

    def __init__(self):
        self.active_tests: Dict[str, ABTestConfig] = {}
        self.results_history: List[ABTestResult] = []

    def create_test(
        self,
        name: str,
        description: str,
        metric_type: MetricType,
        minimum_detectable_effect: float,
        alpha: float = 0.05,
        power: float = 0.80,
        test_type: TestType = TestType.TWO_SAMPLE,
        enable_sequential: bool = False,
        created_by: str = "system",
        tags: Optional[List[str]] = None,
    ) -> ABTestConfig:
        """Create a new A/B test configuration."""
        config = ABTestConfig(
            test_id=str(uuid.uuid4()),
            name=name,
            description=description,
            test_type=test_type,
            metric_type=metric_type,
            alpha=alpha,
            power=power,
            minimum_detectable_effect=minimum_detectable_effect,
            enable_sequential=enable_sequential,
            created_by=created_by,
            tags=tags or [],
        )

        self.active_tests[config.test_id] = config
        return config

    def calculate_sample_size(
        self,
        metric_type: MetricType,
        baseline_rate: float,
        minimum_detectable_effect: float,
        alpha: float = 0.05,
        power: float = 0.80,
        control_ratio: float = 0.5,
    ) -> Dict[str, int]:
        """
        Calculate required sample size for A/B test.

        Args:
            metric_type: Type of metric
            baseline_rate: Baseline conversion/mean
            minimum_detectable_effect: Minimum effect to detect (relative)
            alpha: Significance level
            power: Statistical power
            control_ratio: Proportion in control group

        Returns:
            Dictionary with sample sizes for control and treatment
        """
        # Z-scores for alpha and power
        z_alpha = self._z_score(1 - alpha / 2)
        z_beta = self._z_score(power)

        if metric_type == MetricType.BINARY:
            # Sample size for proportion test
            p1 = baseline_rate
            p2 = baseline_rate * (1 + minimum_detectable_effect)

            pooled_p = (p1 + p2) / 2

            n = (
                (z_alpha * math.sqrt(2 * pooled_p * (1 - pooled_p)) +
                 z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
            ) / ((p2 - p1) ** 2)

        elif metric_type == MetricType.CONTINUOUS:
            # Sample size for means test (assuming equal variance)
            effect_size = minimum_detectable_effect  # Cohen's d
            n = 2 * ((z_alpha + z_beta) / effect_size) ** 2

        else:
            # Default formula
            n = 2 * ((z_alpha + z_beta) / minimum_detectable_effect) ** 2

        n = math.ceil(n)

        # Adjust for unequal allocation
        k = control_ratio / (1 - control_ratio)
        n_control = math.ceil(n * (1 + 1/k) / 2)
        n_treatment = math.ceil(n * (1 + k) / 2)

        return {
            "control": n_control,
            "treatment": n_treatment,
            "total": n_control + n_treatment,
        }

    def analyze(
        self,
        test_id: str,
        control_data: List[float],
        treatment_data: List[float],
    ) -> ABTestResult:
        """
        Analyze A/B test results.

        Args:
            test_id: Test configuration ID
            control_data: Observations from control group
            treatment_data: Observations from treatment group

        Returns:
            ABTestResult with statistical analysis
        """
        config = self.active_tests.get(test_id)
        if not config:
            raise ValueError(f"Test {test_id} not found")

        # Calculate statistics
        control_n = len(control_data)
        treatment_n = len(treatment_data)
        control_mean = sum(control_data) / control_n if control_n > 0 else 0
        treatment_mean = sum(treatment_data) / treatment_n if treatment_n > 0 else 0

        absolute_effect = treatment_mean - control_mean
        relative_effect = absolute_effect / control_mean if control_mean != 0 else 0

        # Perform appropriate test
        if config.metric_type == MetricType.BINARY:
            result = self._proportion_test(
                control_data, treatment_data, config.alpha
            )
        else:
            result = self._t_test(
                control_data, treatment_data, config.alpha
            )

        # Calculate effect size (Cohen's d)
        cohens_d = self._calculate_cohens_d(control_data, treatment_data)

        # Determine status
        if result["p_value"] < config.alpha:
            status = TestStatus.COMPLETED
            is_significant = True
        else:
            status = TestStatus.INCONCLUSIVE
            is_significant = False

        test_result = ABTestResult(
            test_id=test_id,
            status=status,
            control_n=control_n,
            treatment_n=treatment_n,
            control_mean=control_mean,
            treatment_mean=treatment_mean,
            absolute_effect=absolute_effect,
            relative_effect=relative_effect,
            test_statistic=result["test_statistic"],
            p_value=result["p_value"],
            confidence_interval=result["confidence_interval"],
            is_significant=is_significant,
            cohens_d=cohens_d,
        )

        self.results_history.append(test_result)
        return test_result

    def analyze_sequential(
        self,
        test_id: str,
        control_data: List[float],
        treatment_data: List[float],
        analysis_number: int,
    ) -> ABTestResult:
        """
        Perform sequential analysis with early stopping.

        Uses O'Brien-Fleming spending function for alpha adjustment.
        """
        config = self.active_tests.get(test_id)
        if not config or not config.enable_sequential:
            raise ValueError(f"Sequential testing not enabled for {test_id}")

        # Calculate information fraction
        current_n = len(control_data) + len(treatment_data)
        max_n = config.max_sample_size or current_n * 2
        info_fraction = current_n / max_n

        # Get spending function boundary
        boundary = self._obrien_fleming_boundary(
            config.alpha,
            analysis_number,
            config.interim_analyses,
            info_fraction,
        )

        # Perform analysis
        result = self.analyze(test_id, control_data, treatment_data)

        # Check against boundaries
        z_score = abs(result.test_statistic)

        if z_score > boundary.upper_boundary:
            result.status = TestStatus.STOPPED_EARLY
            result.stopped_early = True
            result.stopping_reason = "Efficacy boundary crossed"
        elif boundary.futility_boundary and z_score < boundary.futility_boundary:
            result.status = TestStatus.STOPPED_EARLY
            result.stopped_early = True
            result.stopping_reason = "Futility boundary crossed"

        return result

    def _t_test(
        self,
        control: List[float],
        treatment: List[float],
        alpha: float,
    ) -> Dict[str, Any]:
        """Two-sample t-test for continuous outcomes."""
        n1, n2 = len(control), len(treatment)
        mean1 = sum(control) / n1
        mean2 = sum(treatment) / n2

        # Variance calculation
        var1 = sum((x - mean1) ** 2 for x in control) / (n1 - 1) if n1 > 1 else 0
        var2 = sum((x - mean2) ** 2 for x in treatment) / (n2 - 1) if n2 > 1 else 0

        # Pooled standard error (Welch's t-test)
        se = math.sqrt(var1 / n1 + var2 / n2) if (var1 + var2) > 0 else 1

        # Test statistic
        t_stat = (mean2 - mean1) / se if se > 0 else 0

        # Degrees of freedom (Welch-Satterthwaite)
        if var1 > 0 and var2 > 0:
            df = ((var1/n1 + var2/n2) ** 2) / (
                (var1/n1) ** 2 / (n1-1) + (var2/n2) ** 2 / (n2-1)
            )
        else:
            df = n1 + n2 - 2

        # P-value approximation (using normal for large samples)
        p_value = 2 * (1 - self._normal_cdf(abs(t_stat)))

        # Confidence interval
        z_crit = self._z_score(1 - alpha / 2)
        ci_lower = (mean2 - mean1) - z_crit * se
        ci_upper = (mean2 - mean1) + z_crit * se

        return {
            "test_statistic": t_stat,
            "p_value": p_value,
            "confidence_interval": (ci_lower, ci_upper),
        }

    def _proportion_test(
        self,
        control: List[float],
        treatment: List[float],
        alpha: float,
    ) -> Dict[str, Any]:
        """Two-proportion z-test for binary outcomes."""
        n1, n2 = len(control), len(treatment)
        p1 = sum(control) / n1 if n1 > 0 else 0
        p2 = sum(treatment) / n2 if n2 > 0 else 0

        # Pooled proportion
        pooled_p = (sum(control) + sum(treatment)) / (n1 + n2)

        # Standard error
        se = math.sqrt(pooled_p * (1 - pooled_p) * (1/n1 + 1/n2)) if pooled_p > 0 else 1

        # Test statistic
        z_stat = (p2 - p1) / se if se > 0 else 0

        # P-value
        p_value = 2 * (1 - self._normal_cdf(abs(z_stat)))

        # Confidence interval for difference
        se_diff = math.sqrt(p1 * (1-p1) / n1 + p2 * (1-p2) / n2)
        z_crit = self._z_score(1 - alpha / 2)
        ci_lower = (p2 - p1) - z_crit * se_diff
        ci_upper = (p2 - p1) + z_crit * se_diff

        return {
            "test_statistic": z_stat,
            "p_value": p_value,
            "confidence_interval": (ci_lower, ci_upper),
        }

    def _calculate_cohens_d(
        self,
        control: List[float],
        treatment: List[float],
    ) -> float:
        """Calculate Cohen's d effect size."""
        n1, n2 = len(control), len(treatment)
        mean1 = sum(control) / n1 if n1 > 0 else 0
        mean2 = sum(treatment) / n2 if n2 > 0 else 0

        var1 = sum((x - mean1) ** 2 for x in control) / (n1 - 1) if n1 > 1 else 0
        var2 = sum((x - mean2) ** 2 for x in treatment) / (n2 - 1) if n2 > 1 else 0

        # Pooled standard deviation
        pooled_sd = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))

        if pooled_sd == 0:
            return 0.0

        return (mean2 - mean1) / pooled_sd

    def _obrien_fleming_boundary(
        self,
        alpha: float,
        analysis_number: int,
        total_analyses: int,
        info_fraction: float,
    ) -> SequentialBoundary:
        """Calculate O'Brien-Fleming spending function boundary."""
        # O'Brien-Fleming boundary approximation
        z_alpha = self._z_score(1 - alpha / 2)
        boundary = z_alpha / math.sqrt(info_fraction) if info_fraction > 0 else z_alpha

        # Futility boundary (optional)
        futility = 0.5 if info_fraction > 0.5 else None

        return SequentialBoundary(
            analysis_number=analysis_number,
            information_fraction=info_fraction,
            upper_boundary=boundary,
            lower_boundary=-boundary,
            futility_boundary=futility,
        )

    def _z_score(self, p: float) -> float:
        """Approximate z-score for probability p."""
        # Rational approximation to inverse normal CDF
        if p <= 0:
            return -4.0
        if p >= 1:
            return 4.0

        if p < 0.5:
            return -self._z_score(1 - p)

        t = math.sqrt(-2 * math.log(1 - p))
        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308

        return t - (c0 + c1*t + c2*t*t) / (1 + d1*t + d2*t*t + d3*t*t*t)

    def _normal_cdf(self, x: float) -> float:
        """Approximate normal CDF."""
        # Error function approximation
        a1, a2, a3, a4, a5 = (
            0.254829592, -0.284496736, 1.421413741,
            -1.453152027, 1.061405429
        )
        p = 0.3275911

        sign = 1 if x >= 0 else -1
        x = abs(x) / math.sqrt(2)

        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5*t + a4)*t) + a3)*t + a2)*t + a1) * t * math.exp(-x*x)

        return 0.5 * (1.0 + sign * y)

    def multiple_comparison_correction(
        self,
        p_values: List[float],
        method: str = "bonferroni",
    ) -> List[float]:
        """
        Correct p-values for multiple comparisons.

        Methods:
        - bonferroni: Bonferroni correction
        - holm: Holm-Bonferroni step-down
        - bh: Benjamini-Hochberg FDR
        """
        n = len(p_values)

        if method == "bonferroni":
            return [min(p * n, 1.0) for p in p_values]

        elif method == "holm":
            # Sort p-values with indices
            indexed = sorted(enumerate(p_values), key=lambda x: x[1])
            corrected = [0.0] * n

            for i, (idx, p) in enumerate(indexed):
                corrected[idx] = min(p * (n - i), 1.0)

            return corrected

        elif method == "bh":
            # Benjamini-Hochberg
            indexed = sorted(enumerate(p_values), key=lambda x: x[1])
            corrected = [0.0] * n

            for i, (idx, p) in enumerate(indexed):
                corrected[idx] = min(p * n / (i + 1), 1.0)

            # Enforce monotonicity
            for i in range(n - 2, -1, -1):
                corrected[i] = min(corrected[i], corrected[i + 1])

            return corrected

        else:
            raise ValueError(f"Unknown correction method: {method}")


# Convenience functions
def calculate_sample_size(
    baseline_rate: float,
    minimum_detectable_effect: float,
    metric_type: MetricType = MetricType.CONTINUOUS,
    alpha: float = 0.05,
    power: float = 0.80,
) -> Dict[str, int]:
    """Calculate required sample size for A/B test."""
    analyzer = ABTestAnalyzer()
    return analyzer.calculate_sample_size(
        metric_type=metric_type,
        baseline_rate=baseline_rate,
        minimum_detectable_effect=minimum_detectable_effect,
        alpha=alpha,
        power=power,
    )


def run_ab_test(
    control_data: List[float],
    treatment_data: List[float],
    metric_type: MetricType = MetricType.CONTINUOUS,
    alpha: float = 0.05,
) -> ABTestResult:
    """Quick A/B test analysis."""
    analyzer = ABTestAnalyzer()
    config = analyzer.create_test(
        name="Quick Test",
        description="Ad-hoc A/B test",
        metric_type=metric_type,
        minimum_detectable_effect=0.1,
        alpha=alpha,
    )
    return analyzer.analyze(config.test_id, control_data, treatment_data)
