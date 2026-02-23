"""
Hypothesis Testing - Statistical significance testing.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
import math
import logging

logger = logging.getLogger(__name__)


class TestType(Enum):
    """Type of statistical test."""
    T_TEST = "t_test"
    PAIRED_T_TEST = "paired_t_test"
    WELCH_T_TEST = "welch_t_test"
    MANN_WHITNEY = "mann_whitney"
    ANOVA = "anova"
    CHI_SQUARE = "chi_square"


@dataclass
class TestResult:
    """Result of hypothesis test."""
    test_type: TestType
    statistic: float
    p_value: float
    significant: bool
    alpha: float
    effect_size: Optional[float] = None
    confidence_interval: Optional[Tuple[float, float]] = None
    interpretation: str = ""


class HypothesisTester:
    """
    Statistical hypothesis testing for manufacturing experiments.

    Features:
    - T-tests (independent, paired, Welch's)
    - Non-parametric alternatives
    - Effect size calculation
    - Confidence intervals
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def t_test(self,
              group1: List[float],
              group2: List[float],
              paired: bool = False,
              equal_var: bool = True) -> TestResult:
        """
        Perform t-test between two groups.

        Args:
            group1: First group measurements
            group2: Second group measurements
            paired: Whether samples are paired
            equal_var: Assume equal variances

        Returns:
            Test result
        """
        n1, n2 = len(group1), len(group2)

        if n1 < 2 or n2 < 2:
            raise ValueError("Each group must have at least 2 samples")

        mean1 = sum(group1) / n1
        mean2 = sum(group2) / n2

        var1 = sum((x - mean1) ** 2 for x in group1) / (n1 - 1)
        var2 = sum((x - mean2) ** 2 for x in group2) / (n2 - 1)

        if paired:
            if n1 != n2:
                raise ValueError("Paired t-test requires equal sample sizes")

            # Paired t-test
            differences = [a - b for a, b in zip(group1, group2)]
            mean_diff = sum(differences) / n1
            var_diff = sum((d - mean_diff) ** 2 for d in differences) / (n1 - 1)

            se = math.sqrt(var_diff / n1)
            t_stat = mean_diff / se if se > 0 else 0
            df = n1 - 1
            test_type = TestType.PAIRED_T_TEST

        elif equal_var:
            # Independent t-test with pooled variance
            pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
            se = math.sqrt(pooled_var * (1/n1 + 1/n2))
            t_stat = (mean1 - mean2) / se if se > 0 else 0
            df = n1 + n2 - 2
            test_type = TestType.T_TEST

        else:
            # Welch's t-test
            se = math.sqrt(var1/n1 + var2/n2)
            t_stat = (mean1 - mean2) / se if se > 0 else 0

            # Welch-Satterthwaite degrees of freedom
            num = (var1/n1 + var2/n2) ** 2
            denom = (var1/n1)**2 / (n1-1) + (var2/n2)**2 / (n2-1)
            df = num / denom if denom > 0 else n1 + n2 - 2
            test_type = TestType.WELCH_T_TEST

        # Calculate p-value using t-distribution approximation
        p_value = self._t_distribution_pvalue(abs(t_stat), df)

        # Effect size (Cohen's d)
        pooled_std = math.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))
        effect_size = (mean1 - mean2) / pooled_std if pooled_std > 0 else 0

        # Confidence interval for difference
        t_crit = self._t_critical(df, self.alpha)
        diff = mean1 - mean2
        margin = t_crit * se
        ci = (diff - margin, diff + margin)

        significant = p_value < self.alpha

        interpretation = self._interpret_t_test(
            significant, effect_size, mean1, mean2, p_value
        )

        return TestResult(
            test_type=test_type,
            statistic=t_stat,
            p_value=p_value,
            significant=significant,
            alpha=self.alpha,
            effect_size=effect_size,
            confidence_interval=ci,
            interpretation=interpretation
        )

    def one_sample_t_test(self,
                         data: List[float],
                         population_mean: float) -> TestResult:
        """
        Test if sample mean differs from population mean.

        Args:
            data: Sample data
            population_mean: Hypothesized population mean

        Returns:
            Test result
        """
        n = len(data)
        if n < 2:
            raise ValueError("Need at least 2 samples")

        sample_mean = sum(data) / n
        sample_var = sum((x - sample_mean) ** 2 for x in data) / (n - 1)
        sample_std = math.sqrt(sample_var)

        se = sample_std / math.sqrt(n)
        t_stat = (sample_mean - population_mean) / se if se > 0 else 0
        df = n - 1

        p_value = self._t_distribution_pvalue(abs(t_stat), df)
        significant = p_value < self.alpha

        # Confidence interval
        t_crit = self._t_critical(df, self.alpha)
        margin = t_crit * se
        ci = (sample_mean - margin, sample_mean + margin)

        # Effect size
        effect_size = (sample_mean - population_mean) / sample_std if sample_std > 0 else 0

        interpretation = (
            f"Sample mean ({sample_mean:.4f}) is "
            f"{'significantly' if significant else 'not significantly'} "
            f"different from {population_mean:.4f} (p={p_value:.4f})"
        )

        return TestResult(
            test_type=TestType.T_TEST,
            statistic=t_stat,
            p_value=p_value,
            significant=significant,
            alpha=self.alpha,
            effect_size=effect_size,
            confidence_interval=ci,
            interpretation=interpretation
        )

    def anova(self, *groups: List[float]) -> TestResult:
        """
        One-way ANOVA for comparing multiple groups.

        Args:
            groups: Multiple groups of measurements

        Returns:
            Test result
        """
        k = len(groups)
        if k < 2:
            raise ValueError("ANOVA requires at least 2 groups")

        # Calculate means
        group_means = [sum(g) / len(g) for g in groups]
        group_sizes = [len(g) for g in groups]
        n_total = sum(group_sizes)
        grand_mean = sum(sum(g) for g in groups) / n_total

        # Between-group variance (SSB)
        ssb = sum(
            n * (mean - grand_mean) ** 2
            for n, mean in zip(group_sizes, group_means)
        )

        # Within-group variance (SSW)
        ssw = sum(
            sum((x - mean) ** 2 for x in group)
            for group, mean in zip(groups, group_means)
        )

        # Degrees of freedom
        df_between = k - 1
        df_within = n_total - k

        # Mean squares
        msb = ssb / df_between if df_between > 0 else 0
        msw = ssw / df_within if df_within > 0 else 0

        # F statistic
        f_stat = msb / msw if msw > 0 else 0

        # P-value (using F-distribution approximation)
        p_value = self._f_distribution_pvalue(f_stat, df_between, df_within)
        significant = p_value < self.alpha

        # Effect size (eta-squared)
        ss_total = ssb + ssw
        effect_size = ssb / ss_total if ss_total > 0 else 0

        interpretation = (
            f"{'Significant' if significant else 'No significant'} difference "
            f"between groups (F={f_stat:.4f}, p={p_value:.4f}, η²={effect_size:.4f})"
        )

        return TestResult(
            test_type=TestType.ANOVA,
            statistic=f_stat,
            p_value=p_value,
            significant=significant,
            alpha=self.alpha,
            effect_size=effect_size,
            interpretation=interpretation
        )

    def chi_square_test(self,
                       observed: List[int],
                       expected: Optional[List[float]] = None) -> TestResult:
        """
        Chi-square goodness of fit test.

        Args:
            observed: Observed frequencies
            expected: Expected frequencies (uniform if None)

        Returns:
            Test result
        """
        n = len(observed)
        total = sum(observed)

        if expected is None:
            expected = [total / n] * n

        if len(expected) != n:
            raise ValueError("Observed and expected must have same length")

        # Chi-square statistic
        chi_sq = sum(
            (o - e) ** 2 / e
            for o, e in zip(observed, expected)
            if e > 0
        )

        df = n - 1

        # P-value (using chi-square distribution approximation)
        p_value = self._chi_square_pvalue(chi_sq, df)
        significant = p_value < self.alpha

        # Cramér's V effect size
        effect_size = math.sqrt(chi_sq / (total * (n - 1))) if total > 0 and n > 1 else 0

        interpretation = (
            f"{'Significant' if significant else 'No significant'} deviation "
            f"from expected (χ²={chi_sq:.4f}, df={df}, p={p_value:.4f})"
        )

        return TestResult(
            test_type=TestType.CHI_SQUARE,
            statistic=chi_sq,
            p_value=p_value,
            significant=significant,
            alpha=self.alpha,
            effect_size=effect_size,
            interpretation=interpretation
        )

    def _t_distribution_pvalue(self, t: float, df: float) -> float:
        """Approximate p-value from t-distribution (two-tailed)."""
        # Simple approximation using normal distribution for large df
        if df > 30:
            # Use normal approximation
            return 2 * (1 - self._normal_cdf(abs(t)))

        # Approximation for t-distribution
        x = df / (df + t * t)
        return self._regularized_beta(x, df/2, 0.5)

    def _t_critical(self, df: float, alpha: float) -> float:
        """Approximate critical t-value."""
        # Simple approximation
        if df > 30:
            return 1.96 if alpha == 0.05 else 2.576
        # Rough approximation for smaller df
        return 2.0 + 3.0 / df

    def _f_distribution_pvalue(self, f: float, df1: float, df2: float) -> float:
        """Approximate p-value from F-distribution."""
        x = df2 / (df2 + df1 * f)
        return self._regularized_beta(x, df2/2, df1/2)

    def _chi_square_pvalue(self, chi_sq: float, df: int) -> float:
        """Approximate p-value from chi-square distribution."""
        # Wilson-Hilferty transformation
        if df > 0 and chi_sq > 0:
            z = ((chi_sq / df) ** (1/3) - (1 - 2/(9*df))) / math.sqrt(2/(9*df))
            return 1 - self._normal_cdf(z)
        return 1.0

    def _normal_cdf(self, x: float) -> float:
        """Standard normal CDF approximation."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _regularized_beta(self, x: float, a: float, b: float) -> float:
        """Regularized incomplete beta function approximation."""
        # Simple approximation
        if x <= 0:
            return 0
        if x >= 1:
            return 1
        # Linear interpolation for rough approximation
        return x ** a * (1 - x) ** b / (a * b)

    def _interpret_t_test(self,
                         significant: bool,
                         effect_size: float,
                         mean1: float,
                         mean2: float,
                         p_value: float) -> str:
        """Generate interpretation of t-test result."""
        effect_label = "negligible"
        if abs(effect_size) >= 0.8:
            effect_label = "large"
        elif abs(effect_size) >= 0.5:
            effect_label = "medium"
        elif abs(effect_size) >= 0.2:
            effect_label = "small"

        if significant:
            direction = "higher" if mean1 > mean2 else "lower"
            return (
                f"Group 1 (M={mean1:.4f}) is significantly {direction} than "
                f"Group 2 (M={mean2:.4f}), with a {effect_label} effect "
                f"(d={effect_size:.4f}, p={p_value:.4f})"
            )
        else:
            return (
                f"No significant difference between Group 1 (M={mean1:.4f}) "
                f"and Group 2 (M={mean2:.4f}) (p={p_value:.4f})"
            )
