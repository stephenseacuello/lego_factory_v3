"""
Power Analysis - Sample size calculation.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum
import math
import logging

logger = logging.getLogger(__name__)


class EffectSizeType(Enum):
    """Type of effect size measure."""
    COHENS_D = "cohens_d"
    COHENS_F = "cohens_f"
    ODDS_RATIO = "odds_ratio"
    CORRELATION = "correlation"


@dataclass
class SampleSizeResult:
    """Result of sample size calculation."""
    required_n: int
    per_group_n: int
    num_groups: int
    effect_size: float
    alpha: float
    power: float
    test_type: str
    recommendation: str


class PowerAnalyzer:
    """
    Statistical power analysis and sample size calculation.

    Features:
    - Sample size for t-tests
    - Sample size for ANOVA
    - Sample size for proportions
    - Sensitivity analysis
    """

    def __init__(self, alpha: float = 0.05, power: float = 0.80):
        self.alpha = alpha
        self.power = power

    def sample_size_t_test(self,
                          effect_size: float,
                          ratio: float = 1.0,
                          paired: bool = False) -> SampleSizeResult:
        """
        Calculate required sample size for t-test.

        Args:
            effect_size: Expected Cohen's d
            ratio: Ratio of group sizes (n2/n1)
            paired: Whether test is paired

        Returns:
            Sample size result
        """
        if effect_size <= 0:
            raise ValueError("Effect size must be positive")

        # Get z-values
        z_alpha = self._z_value(1 - self.alpha / 2)
        z_beta = self._z_value(self.power)

        if paired:
            # Paired t-test
            n = math.ceil(((z_alpha + z_beta) ** 2) / (effect_size ** 2))
            total_n = n
            per_group = n
            num_groups = 1
        else:
            # Independent t-test
            factor = (1 + 1/ratio) if ratio != 1 else 2
            n1 = math.ceil(factor * ((z_alpha + z_beta) ** 2) / (effect_size ** 2))
            n2 = math.ceil(n1 * ratio)
            total_n = n1 + n2
            per_group = n1
            num_groups = 2

        recommendation = self._generate_recommendation(
            total_n, effect_size, "t-test"
        )

        return SampleSizeResult(
            required_n=total_n,
            per_group_n=per_group,
            num_groups=num_groups,
            effect_size=effect_size,
            alpha=self.alpha,
            power=self.power,
            test_type="paired t-test" if paired else "independent t-test",
            recommendation=recommendation
        )

    def sample_size_anova(self,
                         effect_size: float,
                         num_groups: int) -> SampleSizeResult:
        """
        Calculate required sample size for one-way ANOVA.

        Args:
            effect_size: Expected Cohen's f
            num_groups: Number of groups

        Returns:
            Sample size result
        """
        if effect_size <= 0:
            raise ValueError("Effect size must be positive")
        if num_groups < 2:
            raise ValueError("ANOVA requires at least 2 groups")

        # Get z-values
        z_alpha = self._z_value(1 - self.alpha / 2)
        z_beta = self._z_value(self.power)

        # Per-group sample size approximation
        # n = (z_α + z_β)² * (1 + (k-1)*ρ) / (k * f²)
        # Simplified approximation
        lambda_nc = effect_size ** 2  # Non-centrality parameter per observation

        per_group = math.ceil(
            ((z_alpha + z_beta) ** 2) / lambda_nc * (1 + 1 / (num_groups - 1))
        )
        per_group = max(per_group, 5)  # Minimum per group

        total_n = per_group * num_groups

        recommendation = self._generate_recommendation(
            total_n, effect_size, "ANOVA"
        )

        return SampleSizeResult(
            required_n=total_n,
            per_group_n=per_group,
            num_groups=num_groups,
            effect_size=effect_size,
            alpha=self.alpha,
            power=self.power,
            test_type=f"one-way ANOVA ({num_groups} groups)",
            recommendation=recommendation
        )

    def sample_size_proportion(self,
                              p1: float,
                              p2: float,
                              ratio: float = 1.0) -> SampleSizeResult:
        """
        Calculate required sample size for comparing two proportions.

        Args:
            p1: Expected proportion in group 1
            p2: Expected proportion in group 2
            ratio: Ratio of group sizes

        Returns:
            Sample size result
        """
        if not (0 < p1 < 1) or not (0 < p2 < 1):
            raise ValueError("Proportions must be between 0 and 1")

        z_alpha = self._z_value(1 - self.alpha / 2)
        z_beta = self._z_value(self.power)

        # Effect size (Cohen's h)
        h = 2 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))
        effect_size = abs(h)

        # Sample size calculation
        p_pooled = (p1 + p2 * ratio) / (1 + ratio)
        q_pooled = 1 - p_pooled

        numerator = (z_alpha * math.sqrt((1 + ratio) * p_pooled * q_pooled) +
                    z_beta * math.sqrt(p1 * (1-p1) + p2 * (1-p2) / ratio)) ** 2
        denominator = (p1 - p2) ** 2

        n1 = math.ceil(numerator / denominator) if denominator > 0 else 100
        n2 = math.ceil(n1 * ratio)
        total_n = n1 + n2

        recommendation = self._generate_recommendation(
            total_n, effect_size, "proportion comparison"
        )

        return SampleSizeResult(
            required_n=total_n,
            per_group_n=n1,
            num_groups=2,
            effect_size=effect_size,
            alpha=self.alpha,
            power=self.power,
            test_type="two-proportion test",
            recommendation=recommendation
        )

    def sample_size_correlation(self,
                               expected_r: float) -> SampleSizeResult:
        """
        Calculate required sample size for correlation test.

        Args:
            expected_r: Expected correlation coefficient

        Returns:
            Sample size result
        """
        if not (-1 < expected_r < 1) or expected_r == 0:
            raise ValueError("Correlation must be between -1 and 1, non-zero")

        z_alpha = self._z_value(1 - self.alpha / 2)
        z_beta = self._z_value(self.power)

        # Fisher's z transformation
        z_r = 0.5 * math.log((1 + abs(expected_r)) / (1 - abs(expected_r)))

        # Sample size
        n = math.ceil(((z_alpha + z_beta) / z_r) ** 2 + 3)

        recommendation = self._generate_recommendation(
            n, abs(expected_r), "correlation"
        )

        return SampleSizeResult(
            required_n=n,
            per_group_n=n,
            num_groups=1,
            effect_size=abs(expected_r),
            alpha=self.alpha,
            power=self.power,
            test_type="correlation test",
            recommendation=recommendation
        )

    def sensitivity_analysis(self,
                            sample_size: int,
                            test_type: str = "t_test") -> float:
        """
        Calculate minimum detectable effect size given sample size.

        Args:
            sample_size: Available sample size
            test_type: Type of test

        Returns:
            Minimum detectable effect size
        """
        z_alpha = self._z_value(1 - self.alpha / 2)
        z_beta = self._z_value(self.power)

        if test_type == "t_test":
            # Independent t-test with equal groups
            per_group = sample_size // 2
            d = (z_alpha + z_beta) * math.sqrt(2 / per_group)
        elif test_type == "paired":
            d = (z_alpha + z_beta) / math.sqrt(sample_size)
        elif test_type == "correlation":
            # Approximate
            d = (z_alpha + z_beta) / math.sqrt(sample_size - 3)
        else:
            d = (z_alpha + z_beta) / math.sqrt(sample_size)

        return d

    def post_hoc_power(self,
                      n: int,
                      effect_size: float,
                      test_type: str = "t_test") -> float:
        """
        Calculate achieved power given sample size and effect size.

        Args:
            n: Sample size
            effect_size: Observed effect size
            test_type: Type of test

        Returns:
            Achieved power
        """
        z_alpha = self._z_value(1 - self.alpha / 2)

        if test_type == "t_test":
            per_group = n // 2
            z_beta = effect_size * math.sqrt(per_group / 2) - z_alpha
        elif test_type == "paired":
            z_beta = effect_size * math.sqrt(n) - z_alpha
        else:
            z_beta = effect_size * math.sqrt(n) - z_alpha

        # Convert z_beta to power
        power = self._normal_cdf(z_beta)
        return min(max(power, 0), 1)

    def _z_value(self, percentile: float) -> float:
        """Get z-value for given percentile using approximation."""
        if percentile <= 0 or percentile >= 1:
            raise ValueError("Percentile must be between 0 and 1")

        # Approximation of inverse normal CDF
        if percentile > 0.5:
            return -self._z_value(1 - percentile)

        t = math.sqrt(-2 * math.log(percentile))
        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308

        return t - (c0 + c1*t + c2*t*t) / (1 + d1*t + d2*t*t + d3*t*t*t)

    def _normal_cdf(self, x: float) -> float:
        """Standard normal CDF approximation."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _generate_recommendation(self,
                                n: int,
                                effect_size: float,
                                test_type: str) -> str:
        """Generate sample size recommendation."""
        effect_label = "large"
        if effect_size < 0.2:
            effect_label = "very small"
        elif effect_size < 0.5:
            effect_label = "small to medium"
        elif effect_size < 0.8:
            effect_label = "medium to large"

        feasibility = "feasible"
        if n > 500:
            feasibility = "challenging"
        elif n > 1000:
            feasibility = "difficult"

        return (
            f"To detect a {effect_label} effect (d={effect_size:.2f}) with "
            f"{self.power*100:.0f}% power at α={self.alpha}, collect at least "
            f"{n} samples. This is {feasibility} for typical manufacturing studies."
        )
