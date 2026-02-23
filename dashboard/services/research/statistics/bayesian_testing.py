"""
Bayesian Testing - Bayesian A/B testing and inference.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import math
import random
import logging

logger = logging.getLogger(__name__)


@dataclass
class BayesianResult:
    """Result of Bayesian analysis."""
    group_a_posterior: Tuple[float, float]  # (mean, std)
    group_b_posterior: Tuple[float, float]
    prob_b_better: float
    expected_lift: float
    credible_interval: Tuple[float, float]
    decision: str
    samples_needed: int


class BayesianTester:
    """
    Bayesian A/B testing and inference.

    Features:
    - Beta-Bernoulli model for proportions
    - Normal-Normal model for continuous data
    - Probability of being best
    - Expected loss calculation
    - Credible intervals
    """

    def __init__(self,
                 threshold: float = 0.95,
                 rope: float = 0.0):
        """
        Initialize Bayesian tester.

        Args:
            threshold: Decision threshold for probability
            rope: Region of Practical Equivalence width
        """
        self.threshold = threshold
        self.rope = rope

    def test_proportions(self,
                        successes_a: int,
                        trials_a: int,
                        successes_b: int,
                        trials_b: int,
                        prior_alpha: float = 1.0,
                        prior_beta: float = 1.0) -> BayesianResult:
        """
        Bayesian A/B test for proportions (conversion rates).

        Args:
            successes_a: Successes in group A
            trials_a: Total trials in group A
            successes_b: Successes in group B
            trials_b: Total trials in group B
            prior_alpha: Beta prior alpha (default: uniform)
            prior_beta: Beta prior beta

        Returns:
            Bayesian test result
        """
        # Posterior parameters (Beta-Bernoulli conjugate)
        alpha_a = prior_alpha + successes_a
        beta_a = prior_beta + trials_a - successes_a

        alpha_b = prior_alpha + successes_b
        beta_b = prior_beta + trials_b - successes_b

        # Posterior mean and variance
        mean_a = alpha_a / (alpha_a + beta_a)
        var_a = (alpha_a * beta_a) / ((alpha_a + beta_a) ** 2 * (alpha_a + beta_a + 1))

        mean_b = alpha_b / (alpha_b + beta_b)
        var_b = (alpha_b * beta_b) / ((alpha_b + beta_b) ** 2 * (alpha_b + beta_b + 1))

        # Monte Carlo estimation of P(B > A)
        n_samples = 10000
        prob_b_better = self._monte_carlo_beta_comparison(
            alpha_a, beta_a, alpha_b, beta_b, n_samples
        )

        # Expected lift
        expected_lift = (mean_b - mean_a) / mean_a if mean_a > 0 else 0

        # 95% credible interval for difference
        diff_samples = self._sample_beta_difference(
            alpha_a, beta_a, alpha_b, beta_b, n_samples
        )
        diff_samples.sort()
        ci_low = diff_samples[int(0.025 * n_samples)]
        ci_high = diff_samples[int(0.975 * n_samples)]

        # Decision
        decision = self._make_decision(prob_b_better, ci_low, ci_high)

        # Estimate samples needed
        samples_needed = self._estimate_samples_needed(
            mean_a, mean_b, trials_a, trials_b, prob_b_better
        )

        return BayesianResult(
            group_a_posterior=(mean_a, math.sqrt(var_a)),
            group_b_posterior=(mean_b, math.sqrt(var_b)),
            prob_b_better=prob_b_better,
            expected_lift=expected_lift,
            credible_interval=(ci_low, ci_high),
            decision=decision,
            samples_needed=samples_needed
        )

    def test_continuous(self,
                       data_a: List[float],
                       data_b: List[float],
                       prior_mean: float = 0.0,
                       prior_var: float = 1000.0) -> BayesianResult:
        """
        Bayesian A/B test for continuous data.

        Args:
            data_a: Measurements from group A
            data_b: Measurements from group B
            prior_mean: Prior mean (uninformative default)
            prior_var: Prior variance (large = uninformative)

        Returns:
            Bayesian test result
        """
        n_a = len(data_a)
        n_b = len(data_b)

        if n_a < 2 or n_b < 2:
            raise ValueError("Each group needs at least 2 samples")

        # Sample statistics
        mean_a = sum(data_a) / n_a
        var_a = sum((x - mean_a) ** 2 for x in data_a) / (n_a - 1)

        mean_b = sum(data_b) / n_b
        var_b = sum((x - mean_b) ** 2 for x in data_b) / (n_b - 1)

        # Posterior parameters (Normal-Normal conjugate)
        # Posterior mean
        post_mean_a = (prior_var * mean_a * n_a + var_a * prior_mean) / (prior_var * n_a + var_a)
        post_mean_b = (prior_var * mean_b * n_b + var_b * prior_mean) / (prior_var * n_b + var_b)

        # Posterior variance (simplified)
        post_var_a = var_a / n_a
        post_var_b = var_b / n_b

        # Monte Carlo estimation of P(B > A)
        n_samples = 10000
        samples_a = [random.gauss(post_mean_a, math.sqrt(post_var_a)) for _ in range(n_samples)]
        samples_b = [random.gauss(post_mean_b, math.sqrt(post_var_b)) for _ in range(n_samples)]

        prob_b_better = sum(b > a for a, b in zip(samples_a, samples_b)) / n_samples

        # Expected lift
        expected_lift = (post_mean_b - post_mean_a) / abs(post_mean_a) if post_mean_a != 0 else 0

        # 95% credible interval for difference
        diff_samples = [b - a for a, b in zip(samples_a, samples_b)]
        diff_samples.sort()
        ci_low = diff_samples[int(0.025 * n_samples)]
        ci_high = diff_samples[int(0.975 * n_samples)]

        # Decision
        decision = self._make_decision(prob_b_better, ci_low, ci_high)

        # Estimate samples needed
        samples_needed = self._estimate_samples_continuous(
            post_mean_a, post_mean_b, post_var_a, post_var_b, prob_b_better
        )

        return BayesianResult(
            group_a_posterior=(post_mean_a, math.sqrt(post_var_a)),
            group_b_posterior=(post_mean_b, math.sqrt(post_var_b)),
            prob_b_better=prob_b_better,
            expected_lift=expected_lift,
            credible_interval=(ci_low, ci_high),
            decision=decision,
            samples_needed=samples_needed
        )

    def _monte_carlo_beta_comparison(self,
                                    alpha_a: float,
                                    beta_a: float,
                                    alpha_b: float,
                                    beta_b: float,
                                    n_samples: int) -> float:
        """Monte Carlo estimation of P(B > A) for beta distributions."""
        count = 0
        for _ in range(n_samples):
            sample_a = self._sample_beta(alpha_a, beta_a)
            sample_b = self._sample_beta(alpha_b, beta_b)
            if sample_b > sample_a:
                count += 1
        return count / n_samples

    def _sample_beta_difference(self,
                               alpha_a: float,
                               beta_a: float,
                               alpha_b: float,
                               beta_b: float,
                               n_samples: int) -> List[float]:
        """Sample differences from beta posteriors."""
        return [
            self._sample_beta(alpha_b, beta_b) - self._sample_beta(alpha_a, beta_a)
            for _ in range(n_samples)
        ]

    def _sample_beta(self, alpha: float, beta: float) -> float:
        """Sample from beta distribution."""
        return random.betavariate(alpha, beta)

    def _make_decision(self,
                      prob_b_better: float,
                      ci_low: float,
                      ci_high: float) -> str:
        """Make decision based on posterior."""
        if prob_b_better >= self.threshold:
            if ci_low > self.rope:
                return f"B is significantly better (P={prob_b_better:.3f})"
            else:
                return f"B is likely better but effect may be small (P={prob_b_better:.3f})"
        elif prob_b_better <= 1 - self.threshold:
            if ci_high < -self.rope:
                return f"A is significantly better (P={1-prob_b_better:.3f})"
            else:
                return f"A is likely better but effect may be small (P={1-prob_b_better:.3f})"
        else:
            if ci_low > -self.rope and ci_high < self.rope:
                return "Practically equivalent (difference within ROPE)"
            else:
                return f"Inconclusive - need more data (P(B>A)={prob_b_better:.3f})"

    def _estimate_samples_needed(self,
                                mean_a: float,
                                mean_b: float,
                                n_a: int,
                                n_b: int,
                                current_prob: float) -> int:
        """Estimate additional samples needed for decision."""
        if current_prob >= self.threshold or current_prob <= 1 - self.threshold:
            return 0  # Already have decision

        # Simple heuristic based on current uncertainty
        effect_diff = abs(mean_b - mean_a)
        if effect_diff < 0.01:
            return 10000  # Very small effect, need many samples

        current_n = n_a + n_b
        prob_gap = abs(current_prob - 0.5)

        if prob_gap < 0.1:
            return current_n * 4  # Need ~4x more data
        elif prob_gap < 0.2:
            return current_n * 2
        else:
            return int(current_n * 0.5)

    def _estimate_samples_continuous(self,
                                    mean_a: float,
                                    mean_b: float,
                                    var_a: float,
                                    var_b: float,
                                    current_prob: float) -> int:
        """Estimate additional samples needed for continuous test."""
        if current_prob >= self.threshold or current_prob <= 1 - self.threshold:
            return 0

        effect_diff = abs(mean_b - mean_a)
        pooled_std = math.sqrt((var_a + var_b) / 2)

        if pooled_std > 0 and effect_diff > 0:
            effect_size = effect_diff / pooled_std
            # Rule of thumb: n ~ 16 / d^2 for 80% power
            return max(0, int(16 / (effect_size ** 2) * 2) - 1)

        return 100  # Default


class MultiArmedBandit:
    """
    Thompson Sampling for adaptive experimentation.

    Useful for:
    - Balancing exploration/exploitation
    - Minimizing regret during experiments
    - Real-time optimization
    """

    def __init__(self, n_arms: int):
        """
        Initialize bandit.

        Args:
            n_arms: Number of arms (variants)
        """
        self.n_arms = n_arms
        # Beta priors for each arm
        self.alpha = [1.0] * n_arms
        self.beta = [1.0] * n_arms
        self.pulls = [0] * n_arms
        self.rewards = [0.0] * n_arms

    def select_arm(self) -> int:
        """
        Select arm using Thompson Sampling.

        Returns:
            Selected arm index
        """
        samples = [
            random.betavariate(self.alpha[i], self.beta[i])
            for i in range(self.n_arms)
        ]
        return samples.index(max(samples))

    def update(self, arm: int, reward: float) -> None:
        """
        Update arm with observed reward.

        Args:
            arm: Arm index
            reward: Observed reward (0 or 1 for binary)
        """
        if reward > 0:
            self.alpha[arm] += 1
        else:
            self.beta[arm] += 1

        self.pulls[arm] += 1
        self.rewards[arm] += reward

    def get_stats(self) -> List[dict]:
        """Get statistics for all arms."""
        return [
            {
                'arm': i,
                'pulls': self.pulls[i],
                'total_reward': self.rewards[i],
                'mean_reward': self.rewards[i] / self.pulls[i] if self.pulls[i] > 0 else 0,
                'posterior_mean': self.alpha[i] / (self.alpha[i] + self.beta[i])
            }
            for i in range(self.n_arms)
        ]

    def get_best_arm(self) -> int:
        """Get arm with highest posterior mean."""
        means = [
            self.alpha[i] / (self.alpha[i] + self.beta[i])
            for i in range(self.n_arms)
        ]
        return means.index(max(means))
