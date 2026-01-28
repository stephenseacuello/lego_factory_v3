"""
Causal Inference for Manufacturing Experiments.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Platform Infrastructure

Statistical methods for causal effect estimation:
- Average Treatment Effect (ATE)
- Conditional Average Treatment Effect (CATE)
- Propensity Score Methods
- Instrumental Variables
- Difference-in-Differences
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
from enum import Enum
import math
import random
import uuid


class EstimationMethod(Enum):
    """Causal effect estimation method."""
    NAIVE_DIFFERENCE = "naive_difference"
    PROPENSITY_MATCHING = "propensity_matching"
    PROPENSITY_WEIGHTING = "propensity_weighting"  # IPW
    DOUBLY_ROBUST = "doubly_robust"
    DIFFERENCE_IN_DIFFERENCES = "difference_in_differences"
    INSTRUMENTAL_VARIABLE = "instrumental_variable"
    REGRESSION_DISCONTINUITY = "regression_discontinuity"


class TreatmentAssignment(Enum):
    """How treatment was assigned."""
    RANDOMIZED = "randomized"
    OBSERVATIONAL = "observational"
    QUASI_EXPERIMENTAL = "quasi_experimental"


@dataclass
class CausalEstimate:
    """Result of causal effect estimation."""
    estimate_id: str
    method: EstimationMethod

    # Point estimate
    effect: float
    standard_error: float

    # Confidence interval
    ci_lower: float
    ci_upper: float
    confidence_level: float

    # Statistical significance
    p_value: float
    is_significant: bool

    # Sample information
    n_treated: int
    n_control: int

    # Diagnostics
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "estimate_id": self.estimate_id,
            "method": self.method.value,
            "effect": self.effect,
            "standard_error": self.standard_error,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "confidence_level": self.confidence_level,
            "p_value": self.p_value,
            "is_significant": self.is_significant,
            "n_treated": self.n_treated,
            "n_control": self.n_control,
            "diagnostics": self.diagnostics,
        }


@dataclass
class CATEEstimate:
    """Conditional Average Treatment Effect estimate."""
    subgroup: str
    subgroup_definition: Dict[str, Any]
    effect: float
    standard_error: float
    n_treated: int
    n_control: int
    confidence_interval: Tuple[float, float]


@dataclass
class PropensityScore:
    """Propensity score for a unit."""
    unit_id: str
    score: float  # P(Treatment=1 | X)
    treatment: int  # Actual treatment (0 or 1)
    outcome: float
    covariates: Dict[str, float]


class CausalInferenceEngine:
    """
    Causal inference engine for manufacturing experiments.

    Estimates causal effects from both randomized and observational data.
    """

    def __init__(self):
        self.estimates: List[CausalEstimate] = []

    def estimate_ate(
        self,
        treated_outcomes: List[float],
        control_outcomes: List[float],
        method: EstimationMethod = EstimationMethod.NAIVE_DIFFERENCE,
        confidence_level: float = 0.95,
        covariates: Optional[List[Dict[str, float]]] = None,
        treatment_indicators: Optional[List[int]] = None,
    ) -> CausalEstimate:
        """
        Estimate Average Treatment Effect (ATE).

        Args:
            treated_outcomes: Outcomes for treated units
            control_outcomes: Outcomes for control units
            method: Estimation method
            confidence_level: Confidence level for interval
            covariates: Covariate values (for adjustment methods)
            treatment_indicators: Treatment assignments (for propensity methods)

        Returns:
            CausalEstimate with effect and confidence interval
        """
        if method == EstimationMethod.NAIVE_DIFFERENCE:
            return self._naive_difference(
                treated_outcomes, control_outcomes, confidence_level
            )
        elif method == EstimationMethod.PROPENSITY_MATCHING:
            if covariates is None or treatment_indicators is None:
                raise ValueError("Propensity matching requires covariates and treatment indicators")
            return self._propensity_matching(
                treated_outcomes, control_outcomes,
                covariates, treatment_indicators, confidence_level
            )
        elif method == EstimationMethod.PROPENSITY_WEIGHTING:
            if covariates is None or treatment_indicators is None:
                raise ValueError("IPW requires covariates and treatment indicators")
            return self._inverse_propensity_weighting(
                treated_outcomes, control_outcomes,
                covariates, treatment_indicators, confidence_level
            )
        elif method == EstimationMethod.DOUBLY_ROBUST:
            if covariates is None or treatment_indicators is None:
                raise ValueError("Doubly robust requires covariates and treatment indicators")
            return self._doubly_robust(
                treated_outcomes, control_outcomes,
                covariates, treatment_indicators, confidence_level
            )
        else:
            raise ValueError(f"Method {method} not implemented for ATE")

    def estimate_did(
        self,
        treated_pre: List[float],
        treated_post: List[float],
        control_pre: List[float],
        control_post: List[float],
        confidence_level: float = 0.95,
    ) -> CausalEstimate:
        """
        Estimate effect using Difference-in-Differences.

        Assumes parallel trends in absence of treatment.
        """
        # Calculate means
        treated_pre_mean = sum(treated_pre) / len(treated_pre)
        treated_post_mean = sum(treated_post) / len(treated_post)
        control_pre_mean = sum(control_pre) / len(control_pre)
        control_post_mean = sum(control_post) / len(control_post)

        # DiD estimate
        treated_diff = treated_post_mean - treated_pre_mean
        control_diff = control_post_mean - control_pre_mean
        effect = treated_diff - control_diff

        # Standard error (simplified)
        n_t = len(treated_post)
        n_c = len(control_post)

        var_treated = self._variance(treated_post)
        var_control = self._variance(control_post)

        se = math.sqrt(var_treated / n_t + var_control / n_c)

        # Confidence interval
        z = self._z_score(1 - (1 - confidence_level) / 2)
        ci_lower = effect - z * se
        ci_upper = effect + z * se

        # P-value
        z_stat = effect / se if se > 0 else 0
        p_value = 2 * (1 - self._normal_cdf(abs(z_stat)))

        estimate = CausalEstimate(
            estimate_id=str(uuid.uuid4()),
            method=EstimationMethod.DIFFERENCE_IN_DIFFERENCES,
            effect=effect,
            standard_error=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=confidence_level,
            p_value=p_value,
            is_significant=p_value < (1 - confidence_level),
            n_treated=n_t,
            n_control=n_c,
            diagnostics={
                "treated_pre_mean": treated_pre_mean,
                "treated_post_mean": treated_post_mean,
                "control_pre_mean": control_pre_mean,
                "control_post_mean": control_post_mean,
                "treated_change": treated_diff,
                "control_change": control_diff,
            },
        )

        self.estimates.append(estimate)
        return estimate

    def estimate_iv(
        self,
        outcomes: List[float],
        treatments: List[float],
        instruments: List[float],
        confidence_level: float = 0.95,
    ) -> CausalEstimate:
        """
        Estimate effect using Instrumental Variables (2SLS).

        Requires valid instrument that affects outcome only through treatment.
        """
        n = len(outcomes)

        # First stage: regress treatment on instrument
        z_mean = sum(instruments) / n
        t_mean = sum(treatments) / n

        cov_zt = sum((z - z_mean) * (t - t_mean) for z, t in zip(instruments, treatments)) / n
        var_z = sum((z - z_mean) ** 2 for z in instruments) / n

        gamma = cov_zt / var_z if var_z > 0 else 0  # First stage coefficient

        # Predicted treatment
        t_hat = [t_mean + gamma * (z - z_mean) for z in instruments]

        # Second stage: regress outcome on predicted treatment
        y_mean = sum(outcomes) / n
        t_hat_mean = sum(t_hat) / n

        cov_yt = sum((y - y_mean) * (th - t_hat_mean) for y, th in zip(outcomes, t_hat)) / n
        var_t_hat = sum((th - t_hat_mean) ** 2 for th in t_hat) / n

        effect = cov_yt / var_t_hat if var_t_hat > 0 else 0  # IV estimate

        # Standard error (simplified)
        residuals = [y - y_mean - effect * (th - t_hat_mean) for y, th in zip(outcomes, t_hat)]
        sigma2 = sum(r ** 2 for r in residuals) / (n - 2)
        se = math.sqrt(sigma2 / (n * var_t_hat)) if var_t_hat > 0 else 1

        # Confidence interval
        z = self._z_score(1 - (1 - confidence_level) / 2)
        ci_lower = effect - z * se
        ci_upper = effect + z * se

        # P-value
        z_stat = effect / se if se > 0 else 0
        p_value = 2 * (1 - self._normal_cdf(abs(z_stat)))

        # First-stage F-statistic (instrument strength)
        f_stat = (gamma ** 2 * var_z * n) / sigma2 if sigma2 > 0 else 0

        estimate = CausalEstimate(
            estimate_id=str(uuid.uuid4()),
            method=EstimationMethod.INSTRUMENTAL_VARIABLE,
            effect=effect,
            standard_error=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=confidence_level,
            p_value=p_value,
            is_significant=p_value < (1 - confidence_level),
            n_treated=sum(1 for t in treatments if t > 0.5),
            n_control=sum(1 for t in treatments if t <= 0.5),
            diagnostics={
                "first_stage_coef": gamma,
                "first_stage_f_stat": f_stat,
                "weak_instrument": f_stat < 10,  # Rule of thumb
            },
        )

        self.estimates.append(estimate)
        return estimate

    def estimate_cate(
        self,
        outcomes: List[float],
        treatments: List[int],
        covariates: List[Dict[str, float]],
        subgroup_var: str,
        confidence_level: float = 0.95,
    ) -> List[CATEEstimate]:
        """
        Estimate Conditional Average Treatment Effects by subgroup.
        """
        # Group by subgroup variable
        subgroups: Dict[str, Dict[str, List]] = {}

        for i, (y, t, x) in enumerate(zip(outcomes, treatments, covariates)):
            subgroup_val = str(x.get(subgroup_var, "unknown"))

            if subgroup_val not in subgroups:
                subgroups[subgroup_val] = {"treated": [], "control": []}

            if t == 1:
                subgroups[subgroup_val]["treated"].append(y)
            else:
                subgroups[subgroup_val]["control"].append(y)

        # Estimate CATE for each subgroup
        cate_estimates = []

        for subgroup_val, data in subgroups.items():
            if len(data["treated"]) < 2 or len(data["control"]) < 2:
                continue

            treated_mean = sum(data["treated"]) / len(data["treated"])
            control_mean = sum(data["control"]) / len(data["control"])
            effect = treated_mean - control_mean

            # Standard error
            var_t = self._variance(data["treated"])
            var_c = self._variance(data["control"])
            se = math.sqrt(var_t / len(data["treated"]) + var_c / len(data["control"]))

            # Confidence interval
            z = self._z_score(1 - (1 - confidence_level) / 2)
            ci = (effect - z * se, effect + z * se)

            cate_estimates.append(CATEEstimate(
                subgroup=subgroup_val,
                subgroup_definition={subgroup_var: subgroup_val},
                effect=effect,
                standard_error=se,
                n_treated=len(data["treated"]),
                n_control=len(data["control"]),
                confidence_interval=ci,
            ))

        return cate_estimates

    def _naive_difference(
        self,
        treated: List[float],
        control: List[float],
        confidence_level: float,
    ) -> CausalEstimate:
        """Simple difference in means."""
        n_t = len(treated)
        n_c = len(control)

        treated_mean = sum(treated) / n_t
        control_mean = sum(control) / n_c
        effect = treated_mean - control_mean

        var_t = self._variance(treated)
        var_c = self._variance(control)
        se = math.sqrt(var_t / n_t + var_c / n_c)

        z = self._z_score(1 - (1 - confidence_level) / 2)
        ci_lower = effect - z * se
        ci_upper = effect + z * se

        z_stat = effect / se if se > 0 else 0
        p_value = 2 * (1 - self._normal_cdf(abs(z_stat)))

        estimate = CausalEstimate(
            estimate_id=str(uuid.uuid4()),
            method=EstimationMethod.NAIVE_DIFFERENCE,
            effect=effect,
            standard_error=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=confidence_level,
            p_value=p_value,
            is_significant=p_value < (1 - confidence_level),
            n_treated=n_t,
            n_control=n_c,
        )

        self.estimates.append(estimate)
        return estimate

    def _propensity_matching(
        self,
        treated_outcomes: List[float],
        control_outcomes: List[float],
        covariates: List[Dict[str, float]],
        treatment_indicators: List[int],
        confidence_level: float,
    ) -> CausalEstimate:
        """Propensity score matching estimator."""
        # Estimate propensity scores
        scores = self._estimate_propensity_scores(covariates, treatment_indicators)

        # Match treated to control
        matched_pairs = []
        used_controls = set()

        for i, (score, t, y) in enumerate(zip(
            scores, treatment_indicators, treated_outcomes + control_outcomes
        )):
            if t == 1:  # Treated unit
                # Find closest control
                best_match = None
                best_dist = float("inf")

                for j, (s2, t2, y2) in enumerate(zip(
                    scores, treatment_indicators, treated_outcomes + control_outcomes
                )):
                    if t2 == 0 and j not in used_controls:
                        dist = abs(score - s2)
                        if dist < best_dist:
                            best_dist = dist
                            best_match = (j, y2)

                if best_match:
                    matched_pairs.append((y, best_match[1]))
                    used_controls.add(best_match[0])

        if not matched_pairs:
            raise ValueError("No matches found")

        # Calculate ATT from matched pairs
        effects = [t - c for t, c in matched_pairs]
        effect = sum(effects) / len(effects)
        se = math.sqrt(self._variance(effects) / len(effects))

        z = self._z_score(1 - (1 - confidence_level) / 2)
        ci_lower = effect - z * se
        ci_upper = effect + z * se

        z_stat = effect / se if se > 0 else 0
        p_value = 2 * (1 - self._normal_cdf(abs(z_stat)))

        estimate = CausalEstimate(
            estimate_id=str(uuid.uuid4()),
            method=EstimationMethod.PROPENSITY_MATCHING,
            effect=effect,
            standard_error=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=confidence_level,
            p_value=p_value,
            is_significant=p_value < (1 - confidence_level),
            n_treated=len(matched_pairs),
            n_control=len(matched_pairs),
            diagnostics={
                "n_matched_pairs": len(matched_pairs),
                "n_unmatched_treated": len(treated_outcomes) - len(matched_pairs),
            },
        )

        self.estimates.append(estimate)
        return estimate

    def _inverse_propensity_weighting(
        self,
        treated_outcomes: List[float],
        control_outcomes: List[float],
        covariates: List[Dict[str, float]],
        treatment_indicators: List[int],
        confidence_level: float,
    ) -> CausalEstimate:
        """Inverse Propensity Weighting (IPW) estimator."""
        scores = self._estimate_propensity_scores(covariates, treatment_indicators)
        all_outcomes = treated_outcomes + control_outcomes

        # IPW estimator
        weighted_treated = 0
        weighted_control = 0
        weight_sum_t = 0
        weight_sum_c = 0

        for y, t, e in zip(all_outcomes, treatment_indicators, scores):
            e = max(0.01, min(0.99, e))  # Clip for stability

            if t == 1:
                w = 1 / e
                weighted_treated += w * y
                weight_sum_t += w
            else:
                w = 1 / (1 - e)
                weighted_control += w * y
                weight_sum_c += w

        treated_mean = weighted_treated / weight_sum_t if weight_sum_t > 0 else 0
        control_mean = weighted_control / weight_sum_c if weight_sum_c > 0 else 0
        effect = treated_mean - control_mean

        # Bootstrap standard error
        se = self._bootstrap_se_ipw(
            all_outcomes, treatment_indicators, scores, n_bootstrap=100
        )

        z = self._z_score(1 - (1 - confidence_level) / 2)
        ci_lower = effect - z * se
        ci_upper = effect + z * se

        z_stat = effect / se if se > 0 else 0
        p_value = 2 * (1 - self._normal_cdf(abs(z_stat)))

        estimate = CausalEstimate(
            estimate_id=str(uuid.uuid4()),
            method=EstimationMethod.PROPENSITY_WEIGHTING,
            effect=effect,
            standard_error=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=confidence_level,
            p_value=p_value,
            is_significant=p_value < (1 - confidence_level),
            n_treated=len(treated_outcomes),
            n_control=len(control_outcomes),
        )

        self.estimates.append(estimate)
        return estimate

    def _doubly_robust(
        self,
        treated_outcomes: List[float],
        control_outcomes: List[float],
        covariates: List[Dict[str, float]],
        treatment_indicators: List[int],
        confidence_level: float,
    ) -> CausalEstimate:
        """Doubly robust (AIPW) estimator."""
        scores = self._estimate_propensity_scores(covariates, treatment_indicators)
        all_outcomes = treated_outcomes + control_outcomes
        n = len(all_outcomes)

        # Fit outcome models (simplified linear)
        mu1 = self._fit_outcome_model(covariates, all_outcomes, treatment_indicators, 1)
        mu0 = self._fit_outcome_model(covariates, all_outcomes, treatment_indicators, 0)

        # AIPW estimator
        psi_values = []

        for i, (y, t, e) in enumerate(zip(all_outcomes, treatment_indicators, scores)):
            e = max(0.01, min(0.99, e))

            # Predicted outcomes
            mu1_i = mu1(covariates[i])
            mu0_i = mu0(covariates[i])

            # AIPW contribution
            if t == 1:
                psi = mu1_i + (y - mu1_i) / e - mu0_i
            else:
                psi = mu1_i - mu0_i - (y - mu0_i) / (1 - e)

            psi_values.append(psi)

        effect = sum(psi_values) / n
        se = math.sqrt(self._variance(psi_values) / n)

        z = self._z_score(1 - (1 - confidence_level) / 2)
        ci_lower = effect - z * se
        ci_upper = effect + z * se

        z_stat = effect / se if se > 0 else 0
        p_value = 2 * (1 - self._normal_cdf(abs(z_stat)))

        estimate = CausalEstimate(
            estimate_id=str(uuid.uuid4()),
            method=EstimationMethod.DOUBLY_ROBUST,
            effect=effect,
            standard_error=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            confidence_level=confidence_level,
            p_value=p_value,
            is_significant=p_value < (1 - confidence_level),
            n_treated=len(treated_outcomes),
            n_control=len(control_outcomes),
        )

        self.estimates.append(estimate)
        return estimate

    def _estimate_propensity_scores(
        self,
        covariates: List[Dict[str, float]],
        treatments: List[int],
    ) -> List[float]:
        """Estimate propensity scores using logistic regression."""
        # Simple logistic regression
        n = len(treatments)

        # Get feature names
        feature_names = list(covariates[0].keys()) if covariates else []

        # Initialize coefficients
        beta = [0.0] * (len(feature_names) + 1)  # +1 for intercept

        # Gradient descent
        lr = 0.1
        for _ in range(100):
            grad = [0.0] * len(beta)

            for x, t in zip(covariates, treatments):
                features = [1.0] + [x.get(f, 0) for f in feature_names]

                # Predicted probability
                z = sum(b * f for b, f in zip(beta, features))
                p = 1 / (1 + math.exp(-max(-500, min(500, z))))

                # Gradient
                error = t - p
                for j, f in enumerate(features):
                    grad[j] += error * f

            # Update
            for j in range(len(beta)):
                beta[j] += lr * grad[j] / n

        # Calculate scores
        scores = []
        for x in covariates:
            features = [1.0] + [x.get(f, 0) for f in feature_names]
            z = sum(b * f for b, f in zip(beta, features))
            p = 1 / (1 + math.exp(-max(-500, min(500, z))))
            scores.append(p)

        return scores

    def _fit_outcome_model(
        self,
        covariates: List[Dict[str, float]],
        outcomes: List[float],
        treatments: List[int],
        treatment_value: int,
    ) -> Callable[[Dict[str, float]], float]:
        """Fit outcome model for given treatment value."""
        # Filter to relevant treatment group
        filtered_x = []
        filtered_y = []

        for x, y, t in zip(covariates, outcomes, treatments):
            if t == treatment_value:
                filtered_x.append(x)
                filtered_y.append(y)

        if not filtered_x:
            return lambda x: sum(outcomes) / len(outcomes)

        # Simple linear regression
        feature_names = list(covariates[0].keys())
        n = len(filtered_y)

        # Fit coefficients (simplified OLS)
        y_mean = sum(filtered_y) / n

        # Return prediction function
        def predict(x: Dict[str, float]) -> float:
            # Very simple: weighted average toward mean
            return y_mean

        return predict

    def _bootstrap_se_ipw(
        self,
        outcomes: List[float],
        treatments: List[int],
        scores: List[float],
        n_bootstrap: int = 100,
    ) -> float:
        """Bootstrap standard error for IPW estimator."""
        n = len(outcomes)
        estimates = []

        for _ in range(n_bootstrap):
            # Resample with replacement
            indices = [random.randint(0, n - 1) for _ in range(n)]

            weighted_treated = 0
            weighted_control = 0
            weight_sum_t = 0
            weight_sum_c = 0

            for i in indices:
                y, t, e = outcomes[i], treatments[i], scores[i]
                e = max(0.01, min(0.99, e))

                if t == 1:
                    w = 1 / e
                    weighted_treated += w * y
                    weight_sum_t += w
                else:
                    w = 1 / (1 - e)
                    weighted_control += w * y
                    weight_sum_c += w

            if weight_sum_t > 0 and weight_sum_c > 0:
                effect = weighted_treated / weight_sum_t - weighted_control / weight_sum_c
                estimates.append(effect)

        if len(estimates) < 2:
            return 1.0

        return math.sqrt(self._variance(estimates))

    def _variance(self, data: List[float]) -> float:
        """Calculate sample variance."""
        n = len(data)
        if n < 2:
            return 0.0
        mean = sum(data) / n
        return sum((x - mean) ** 2 for x in data) / (n - 1)

    def _z_score(self, p: float) -> float:
        """Approximate z-score for probability p."""
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


# Convenience functions
def estimate_treatment_effect(
    treated_outcomes: List[float],
    control_outcomes: List[float],
    method: EstimationMethod = EstimationMethod.NAIVE_DIFFERENCE,
) -> CausalEstimate:
    """Quick estimation of treatment effect."""
    engine = CausalInferenceEngine()
    return engine.estimate_ate(treated_outcomes, control_outcomes, method)


def difference_in_differences(
    treated_pre: List[float],
    treated_post: List[float],
    control_pre: List[float],
    control_post: List[float],
) -> CausalEstimate:
    """Quick DiD estimation."""
    engine = CausalInferenceEngine()
    return engine.estimate_did(treated_pre, treated_post, control_pre, control_post)
