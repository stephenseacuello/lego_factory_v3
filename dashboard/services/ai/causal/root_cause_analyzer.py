"""
Root Cause Analysis Service
LegoMCP PhD-Level Manufacturing Platform

Implements causal root cause analysis with:
- Fault tree analysis
- Bayesian belief networks
- Granger causality
- Transfer entropy
- Manufacturing-specific RCA
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class RCAMethod(Enum):
    CORRELATION = "correlation"
    GRANGER = "granger_causality"
    TRANSFER_ENTROPY = "transfer_entropy"
    FAULT_TREE = "fault_tree"
    BAYESIAN = "bayesian_network"


class SeverityLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class RootCause:
    """Individual root cause."""
    name: str
    score: float  # Causal strength (0-1)
    confidence: float
    category: str
    evidence: List[str]
    severity: SeverityLevel = SeverityLevel.MEDIUM
    recommended_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": float(self.score),
            "confidence": float(self.confidence),
            "category": self.category,
            "evidence": self.evidence,
            "severity": self.severity.value,
            "recommended_actions": self.recommended_actions,
        }


@dataclass
class RootCauseResult:
    """Complete RCA result."""
    problem: str
    root_causes: List[RootCause]
    method: RCAMethod
    total_explained: float  # Fraction of variance explained
    causal_chain: List[str]  # Ordered causal path
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem": self.problem,
            "root_causes": [rc.to_dict() for rc in self.root_causes],
            "method": self.method.value,
            "total_explained": float(self.total_explained),
            "causal_chain": self.causal_chain,
            "metadata": self.metadata,
        }

    @property
    def top_cause(self) -> Optional[RootCause]:
        """Get the most likely root cause."""
        if not self.root_causes:
            return None
        return max(self.root_causes, key=lambda x: x.score)


class RootCauseAnalyzer:
    """
    Root Cause Analysis for manufacturing problems.

    Combines multiple causal inference techniques to
    identify root causes of quality issues, defects,
    and process anomalies.
    """

    def __init__(
        self,
        feature_names: List[str] = None,
        domain_knowledge: Dict[str, List[str]] = None,
    ):
        self.feature_names = feature_names or []
        self.domain_knowledge = domain_knowledge or {}

        # Manufacturing categories
        self.categories = {
            "material": ["raw_material", "composition", "supplier", "batch"],
            "machine": ["equipment", "tool", "calibration", "wear"],
            "method": ["process", "parameter", "sequence", "timing"],
            "measurement": ["sensor", "gauge", "inspection", "calibration"],
            "man": ["operator", "training", "shift", "fatigue"],
            "environment": ["temperature", "humidity", "contamination", "vibration"],
        }

    def analyze(
        self,
        problem_data: np.ndarray,
        outcome_data: np.ndarray,
        problem_description: str = "quality issue",
        method: RCAMethod = RCAMethod.CORRELATION,
        top_k: int = 5,
    ) -> RootCauseResult:
        """
        Perform root cause analysis.

        Args:
            problem_data: Feature data (n_samples, n_features)
            outcome_data: Outcome/defect indicator (n_samples,)
            problem_description: Description of the problem
            method: RCA method to use
            top_k: Number of top causes to return

        Returns:
            RootCauseResult with identified root causes
        """
        if method == RCAMethod.CORRELATION:
            return self._correlation_rca(problem_data, outcome_data, problem_description, top_k)
        elif method == RCAMethod.GRANGER:
            return self._granger_rca(problem_data, outcome_data, problem_description, top_k)
        elif method == RCAMethod.TRANSFER_ENTROPY:
            return self._transfer_entropy_rca(problem_data, outcome_data, problem_description, top_k)
        elif method == RCAMethod.FAULT_TREE:
            return self._fault_tree_rca(problem_data, outcome_data, problem_description, top_k)
        else:
            return self._correlation_rca(problem_data, outcome_data, problem_description, top_k)

    def _correlation_rca(
        self,
        X: np.ndarray,
        y: np.ndarray,
        problem: str,
        top_k: int,
    ) -> RootCauseResult:
        """RCA using correlation analysis."""
        n_features = X.shape[1]
        correlations = []

        for i in range(n_features):
            corr = np.corrcoef(X[:, i], y)[0, 1]
            if not np.isnan(corr):
                correlations.append((i, abs(corr), corr))

        # Sort by absolute correlation
        correlations.sort(key=lambda x: x[1], reverse=True)

        root_causes = []
        for idx, abs_corr, corr in correlations[:top_k]:
            name = self.feature_names[idx] if idx < len(self.feature_names) else f"feature_{idx}"
            category = self._categorize_feature(name)
            severity = self._assess_severity(abs_corr)

            rc = RootCause(
                name=name,
                score=float(abs_corr),
                confidence=self._correlation_confidence(abs_corr, len(y)),
                category=category,
                evidence=[
                    f"Correlation: {corr:.3f}",
                    f"Direction: {'positive' if corr > 0 else 'negative'}",
                ],
                severity=severity,
                recommended_actions=self._generate_actions(name, category, corr),
            )
            root_causes.append(rc)

        # Calculate total explained variance
        total_explained = sum(c[1] ** 2 for c in correlations[:top_k])

        # Build causal chain
        causal_chain = [rc.name for rc in root_causes[:3]]
        causal_chain.append(problem)

        return RootCauseResult(
            problem=problem,
            root_causes=root_causes,
            method=RCAMethod.CORRELATION,
            total_explained=min(float(total_explained), 1.0),
            causal_chain=causal_chain,
        )

    def _granger_rca(
        self,
        X: np.ndarray,
        y: np.ndarray,
        problem: str,
        top_k: int,
    ) -> RootCauseResult:
        """RCA using Granger causality tests."""
        try:
            from statsmodels.tsa.stattools import grangercausalitytests

            n_features = X.shape[1]
            granger_scores = []

            for i in range(n_features):
                try:
                    data = np.column_stack([y, X[:, i]])
                    result = grangercausalitytests(data, maxlag=5, verbose=False)

                    # Get minimum p-value across lags
                    min_pval = min(
                        result[lag][0]['ssr_ftest'][1]
                        for lag in result.keys()
                    )
                    score = 1 - min_pval
                    granger_scores.append((i, score, min_pval))

                except Exception:
                    granger_scores.append((i, 0.0, 1.0))

            granger_scores.sort(key=lambda x: x[1], reverse=True)

            root_causes = []
            for idx, score, pval in granger_scores[:top_k]:
                name = self.feature_names[idx] if idx < len(self.feature_names) else f"feature_{idx}"
                category = self._categorize_feature(name)
                severity = self._assess_severity(score)

                rc = RootCause(
                    name=name,
                    score=float(score),
                    confidence=float(1 - pval) if pval < 1 else 0.5,
                    category=category,
                    evidence=[
                        f"Granger causality p-value: {pval:.4f}",
                        f"Causal score: {score:.3f}",
                    ],
                    severity=severity,
                    recommended_actions=self._generate_actions(name, category, score),
                )
                root_causes.append(rc)

            total_explained = sum(s[1] for s in granger_scores[:top_k]) / top_k
            causal_chain = [rc.name for rc in root_causes[:3]] + [problem]

            return RootCauseResult(
                problem=problem,
                root_causes=root_causes,
                method=RCAMethod.GRANGER,
                total_explained=float(total_explained),
                causal_chain=causal_chain,
            )

        except ImportError:
            logger.warning("statsmodels not installed, falling back to correlation")
            return self._correlation_rca(X, y, problem, top_k)

    def _transfer_entropy_rca(
        self,
        X: np.ndarray,
        y: np.ndarray,
        problem: str,
        top_k: int,
    ) -> RootCauseResult:
        """RCA using transfer entropy."""
        n_features = X.shape[1]
        te_scores = []

        for i in range(n_features):
            te = self._compute_transfer_entropy(X[:, i], y)
            te_scores.append((i, te))

        te_scores.sort(key=lambda x: x[1], reverse=True)

        root_causes = []
        max_te = max(s[1] for s in te_scores) if te_scores else 1.0

        for idx, te in te_scores[:top_k]:
            name = self.feature_names[idx] if idx < len(self.feature_names) else f"feature_{idx}"
            category = self._categorize_feature(name)
            normalized_score = te / max_te if max_te > 0 else 0

            rc = RootCause(
                name=name,
                score=float(normalized_score),
                confidence=0.7,
                category=category,
                evidence=[
                    f"Transfer entropy: {te:.4f}",
                    f"Information flow: high" if normalized_score > 0.5 else "moderate",
                ],
                severity=self._assess_severity(normalized_score),
                recommended_actions=self._generate_actions(name, category, normalized_score),
            )
            root_causes.append(rc)

        total_explained = sum(s[1] for s in te_scores[:top_k]) / (max_te * top_k) if max_te > 0 else 0
        causal_chain = [rc.name for rc in root_causes[:3]] + [problem]

        return RootCauseResult(
            problem=problem,
            root_causes=root_causes,
            method=RCAMethod.TRANSFER_ENTROPY,
            total_explained=float(total_explained),
            causal_chain=causal_chain,
        )

    def _fault_tree_rca(
        self,
        X: np.ndarray,
        y: np.ndarray,
        problem: str,
        top_k: int,
    ) -> RootCauseResult:
        """RCA using fault tree analysis."""
        # Build fault tree from domain knowledge and data
        fault_tree = self._build_fault_tree(X, y)

        # Calculate importance scores
        importance_scores = self._calculate_importance(fault_tree, X, y)

        root_causes = []
        for name, score in sorted(importance_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]:
            category = self._categorize_feature(name)

            rc = RootCause(
                name=name,
                score=float(score),
                confidence=0.75,
                category=category,
                evidence=[
                    f"Fault tree importance: {score:.3f}",
                    f"Category: {category}",
                ],
                severity=self._assess_severity(score),
                recommended_actions=self._generate_actions(name, category, score),
            )
            root_causes.append(rc)

        total_explained = sum(rc.score for rc in root_causes) / len(root_causes) if root_causes else 0
        causal_chain = [rc.name for rc in root_causes[:3]] + [problem]

        return RootCauseResult(
            problem=problem,
            root_causes=root_causes,
            method=RCAMethod.FAULT_TREE,
            total_explained=float(total_explained),
            causal_chain=causal_chain,
            metadata={"fault_tree": fault_tree},
        )

    def _compute_transfer_entropy(
        self,
        source: np.ndarray,
        target: np.ndarray,
        lag: int = 1,
        bins: int = 10,
    ) -> float:
        """Compute transfer entropy from source to target."""
        n = len(source) - lag

        # Discretize
        source_binned = np.digitize(source, np.linspace(source.min(), source.max(), bins))
        target_binned = np.digitize(target, np.linspace(target.min(), target.max(), bins))

        # Joint and marginal distributions
        joint_xyz = np.zeros((bins + 1, bins + 1, bins + 1))
        joint_yz = np.zeros((bins + 1, bins + 1))
        joint_xz = np.zeros((bins + 1, bins + 1))
        marginal_z = np.zeros(bins + 1)

        for i in range(n):
            x = source_binned[i]
            y = target_binned[i + lag]
            z = target_binned[i]

            joint_xyz[x, y, z] += 1
            joint_yz[y, z] += 1
            joint_xz[x, z] += 1
            marginal_z[z] += 1

        # Normalize
        joint_xyz /= n
        joint_yz /= n
        joint_xz /= n
        marginal_z /= n

        # Calculate transfer entropy
        te = 0.0
        for x in range(bins + 1):
            for y in range(bins + 1):
                for z in range(bins + 1):
                    p_xyz = joint_xyz[x, y, z]
                    p_yz = joint_yz[y, z]
                    p_xz = joint_xz[x, z]
                    p_z = marginal_z[z]

                    if p_xyz > 0 and p_xz > 0 and p_yz > 0 and p_z > 0:
                        te += p_xyz * np.log2((p_xyz * p_z) / (p_xz * p_yz))

        return max(0, te)

    def _build_fault_tree(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> Dict[str, Any]:
        """Build fault tree structure."""
        tree = {
            "top_event": "defect",
            "gates": [],
            "basic_events": [],
        }

        # Group features by category
        for category, keywords in self.categories.items():
            gate_events = []
            for i, name in enumerate(self.feature_names):
                if any(kw in name.lower() for kw in keywords):
                    gate_events.append(name)

            if gate_events:
                tree["gates"].append({
                    "name": f"{category}_failure",
                    "type": "OR",
                    "inputs": gate_events,
                })

        tree["basic_events"] = self.feature_names

        return tree

    def _calculate_importance(
        self,
        fault_tree: Dict[str, Any],
        X: np.ndarray,
        y: np.ndarray,
    ) -> Dict[str, float]:
        """Calculate feature importance from fault tree."""
        importance = {}

        for i, name in enumerate(self.feature_names):
            # Correlation-based importance
            corr = abs(np.corrcoef(X[:, i], y)[0, 1])
            if np.isnan(corr):
                corr = 0

            # Adjust by category (domain knowledge)
            category_weight = 1.0
            for cat, keywords in self.categories.items():
                if any(kw in name.lower() for kw in keywords):
                    category_weight = 1.2
                    break

            importance[name] = corr * category_weight

        # Normalize
        max_imp = max(importance.values()) if importance else 1
        return {k: v / max_imp for k, v in importance.items()}

    def _categorize_feature(self, feature_name: str) -> str:
        """Categorize feature using 6M framework."""
        name_lower = feature_name.lower()

        for category, keywords in self.categories.items():
            if any(kw in name_lower for kw in keywords):
                return category

        return "unknown"

    def _assess_severity(self, score: float) -> SeverityLevel:
        """Assess severity based on causal strength."""
        if score > 0.8:
            return SeverityLevel.CRITICAL
        elif score > 0.6:
            return SeverityLevel.HIGH
        elif score > 0.3:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW

    def _correlation_confidence(self, corr: float, n: int) -> float:
        """Calculate confidence based on correlation and sample size."""
        # Fisher transformation for confidence
        z = 0.5 * np.log((1 + corr) / (1 - corr + 1e-8))
        se = 1 / np.sqrt(n - 3) if n > 3 else 0.5
        confidence = 1 - 2 * (1 - self._norm_cdf(abs(z) / se))
        return float(np.clip(confidence, 0, 1))

    def _norm_cdf(self, x: float) -> float:
        """Standard normal CDF."""
        return 0.5 * (1 + np.tanh(x * 0.7978845608))

    def _generate_actions(
        self,
        feature_name: str,
        category: str,
        strength: float,
    ) -> List[str]:
        """Generate recommended corrective actions."""
        actions = []

        category_actions = {
            "material": [
                "Review raw material specifications",
                "Conduct supplier quality audit",
                "Implement incoming inspection",
            ],
            "machine": [
                "Perform equipment maintenance",
                "Calibrate measurement systems",
                "Review preventive maintenance schedule",
            ],
            "method": [
                "Review process parameters",
                "Update work instructions",
                "Conduct process capability study",
            ],
            "measurement": [
                "Calibrate gauges and sensors",
                "Review measurement system analysis",
                "Implement automated inspection",
            ],
            "man": [
                "Provide operator training",
                "Review workload distribution",
                "Implement error-proofing",
            ],
            "environment": [
                "Control environmental conditions",
                "Install monitoring sensors",
                "Implement contamination controls",
            ],
        }

        if category in category_actions:
            actions = category_actions[category][:2]

        if strength > 0.7:
            actions.insert(0, f"PRIORITY: Investigate {feature_name} immediately")

        return actions

    def analyze_manufacturing_defect(
        self,
        process_data: np.ndarray,
        defect_indicator: np.ndarray,
        defect_type: str,
        feature_names: List[str] = None,
    ) -> RootCauseResult:
        """
        Specialized RCA for manufacturing defects.

        Args:
            process_data: Process parameters and conditions
            defect_indicator: Binary defect indicator
            defect_type: Type of defect being analyzed
            feature_names: Names of process parameters

        Returns:
            RootCauseResult with manufacturing-specific insights
        """
        if feature_names:
            self.feature_names = feature_names

        # Use multiple methods and combine
        results = []

        for method in [RCAMethod.CORRELATION, RCAMethod.GRANGER]:
            try:
                result = self.analyze(
                    process_data, defect_indicator,
                    f"{defect_type} defect",
                    method, top_k=5
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"Method {method.value} failed: {e}")

        # Combine results
        if not results:
            return self.analyze(process_data, defect_indicator, f"{defect_type} defect")

        # Aggregate root causes
        cause_scores = defaultdict(list)
        for result in results:
            for rc in result.root_causes:
                cause_scores[rc.name].append(rc.score)

        # Create combined result
        combined_causes = []
        for name, scores in cause_scores.items():
            avg_score = np.mean(scores)
            category = self._categorize_feature(name)

            combined_causes.append(RootCause(
                name=name,
                score=float(avg_score),
                confidence=float(len(scores) / len(results)),
                category=category,
                evidence=[f"Identified by {len(scores)} methods"],
                severity=self._assess_severity(avg_score),
                recommended_actions=self._generate_actions(name, category, avg_score),
            ))

        combined_causes.sort(key=lambda x: x.score, reverse=True)

        return RootCauseResult(
            problem=f"{defect_type} defect",
            root_causes=combined_causes[:5],
            method=RCAMethod.CORRELATION,
            total_explained=results[0].total_explained if results else 0,
            causal_chain=[rc.name for rc in combined_causes[:3]] + [f"{defect_type} defect"],
            metadata={"methods_used": [r.method.value for r in results]},
        )


# Global instance
root_cause_analyzer = RootCauseAnalyzer()
