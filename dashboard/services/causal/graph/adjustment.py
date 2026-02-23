"""
Adjustment Sets - Covariate adjustment for causal inference.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


@dataclass
class AdjustmentResult:
    """Result of adjustment set computation."""
    valid: bool
    adjustment_set: Set[str]
    criterion: str
    blocked_paths: int
    total_paths: int


class BackdoorCriterion:
    """
    Backdoor criterion implementation.

    A set Z satisfies the backdoor criterion relative to (X, Y) if:
    1. Z does not contain any descendant of X
    2. Z blocks every path between X and Y that contains an arrow into X
    """

    def __init__(self, dag: Any):
        self.dag = dag

    def is_valid_adjustment(self,
                           treatment: str,
                           outcome: str,
                           adjustment: Set[str]) -> AdjustmentResult:
        """
        Check if adjustment set satisfies backdoor criterion.

        Args:
            treatment: Treatment variable
            outcome: Outcome variable
            adjustment: Proposed adjustment set

        Returns:
            Validation result
        """
        # Condition 1: No descendants of treatment
        treatment_descendants = self.dag.get_descendants(treatment)
        if adjustment & treatment_descendants:
            return AdjustmentResult(
                valid=False,
                adjustment_set=adjustment,
                criterion="backdoor",
                blocked_paths=0,
                total_paths=0
            )

        # Condition 2: Blocks all backdoor paths
        backdoor_paths = self.dag.find_backdoor_paths(treatment, outcome)

        if not backdoor_paths:
            return AdjustmentResult(
                valid=True,
                adjustment_set=adjustment,
                criterion="backdoor",
                blocked_paths=0,
                total_paths=0
            )

        blocked = 0
        for path in backdoor_paths:
            if self._path_blocked(path, adjustment):
                blocked += 1

        valid = blocked == len(backdoor_paths)

        return AdjustmentResult(
            valid=valid,
            adjustment_set=adjustment,
            criterion="backdoor",
            blocked_paths=blocked,
            total_paths=len(backdoor_paths)
        )

    def _path_blocked(self, path: List[str], conditioning: Set[str]) -> bool:
        """Check if path is blocked by conditioning set."""
        for node in path[1:-1]:  # Exclude endpoints
            if node in conditioning:
                return True
        return False

    def find_minimal_adjustment(self,
                               treatment: str,
                               outcome: str) -> Optional[Set[str]]:
        """Find minimal valid adjustment set."""
        treatment_descendants = self.dag.get_descendants(treatment)
        all_nodes = set(n.name for n in self.dag.get_nodes())

        # Candidates: not treatment, outcome, or descendant of treatment
        candidates = all_nodes - {treatment, outcome} - treatment_descendants

        # Only observed
        candidates = {
            c for c in candidates
            if self.dag.get_node(c) and self.dag.get_node(c).observed
        }

        # Try increasingly larger sets
        for size in range(len(candidates) + 1):
            for subset in self._combinations(candidates, size):
                result = self.is_valid_adjustment(treatment, outcome, subset)
                if result.valid:
                    return subset

        return None

    def find_all_valid_adjustments(self,
                                  treatment: str,
                                  outcome: str,
                                  max_size: int = 5) -> List[Set[str]]:
        """Find all valid adjustment sets up to max_size."""
        treatment_descendants = self.dag.get_descendants(treatment)
        all_nodes = set(n.name for n in self.dag.get_nodes())

        candidates = all_nodes - {treatment, outcome} - treatment_descendants
        candidates = {
            c for c in candidates
            if self.dag.get_node(c) and self.dag.get_node(c).observed
        }

        valid_sets = []

        for size in range(min(max_size + 1, len(candidates) + 1)):
            for subset in self._combinations(candidates, size):
                result = self.is_valid_adjustment(treatment, outcome, subset)
                if result.valid:
                    valid_sets.append(subset)

        return valid_sets

    def _combinations(self, items: Set[str], size: int):
        """Generate combinations."""
        items_list = list(items)
        n = len(items_list)

        if size > n:
            return

        if size == 0:
            yield set()
            return

        indices = list(range(size))
        yield set(items_list[i] for i in indices)

        while True:
            for i in reversed(range(size)):
                if indices[i] != i + n - size:
                    break
            else:
                return

            indices[i] += 1
            for j in range(i + 1, size):
                indices[j] = indices[j - 1] + 1
            yield set(items_list[i] for i in indices)


class FrontdoorCriterion:
    """
    Frontdoor criterion implementation.

    A set M satisfies the frontdoor criterion relative to (X, Y) if:
    1. M intercepts all directed paths from X to Y
    2. There is no unblocked backdoor path from X to M
    3. All backdoor paths from M to Y are blocked by X
    """

    def __init__(self, dag: Any):
        self.dag = dag

    def is_valid_mediator_set(self,
                             treatment: str,
                             outcome: str,
                             mediators: Set[str]) -> AdjustmentResult:
        """
        Check if mediator set satisfies frontdoor criterion.

        Args:
            treatment: Treatment variable
            outcome: Outcome variable
            mediators: Proposed mediator set

        Returns:
            Validation result
        """
        # Condition 1: Intercepts all directed paths
        directed_paths = self.dag.find_all_paths(treatment, outcome)

        if not directed_paths:
            return AdjustmentResult(
                valid=False,
                adjustment_set=mediators,
                criterion="frontdoor",
                blocked_paths=0,
                total_paths=0
            )

        intercepted = 0
        for path in directed_paths:
            path_nodes = set(path[1:-1])  # Exclude treatment and outcome
            if path_nodes & mediators:
                intercepted += 1

        if intercepted != len(directed_paths):
            return AdjustmentResult(
                valid=False,
                adjustment_set=mediators,
                criterion="frontdoor",
                blocked_paths=intercepted,
                total_paths=len(directed_paths)
            )

        # Condition 2: No unblocked backdoor from treatment to mediators
        for m in mediators:
            backdoor_t_m = self.dag.find_backdoor_paths(treatment, m)
            if backdoor_t_m:
                return AdjustmentResult(
                    valid=False,
                    adjustment_set=mediators,
                    criterion="frontdoor",
                    blocked_paths=0,
                    total_paths=len(backdoor_t_m)
                )

        # Condition 3: Backdoor from mediators to outcome blocked by treatment
        for m in mediators:
            backdoor_m_y = self.dag.find_backdoor_paths(m, outcome)
            for path in backdoor_m_y:
                if treatment not in path:
                    return AdjustmentResult(
                        valid=False,
                        adjustment_set=mediators,
                        criterion="frontdoor",
                        blocked_paths=0,
                        total_paths=len(backdoor_m_y)
                    )

        return AdjustmentResult(
            valid=True,
            adjustment_set=mediators,
            criterion="frontdoor",
            blocked_paths=len(directed_paths),
            total_paths=len(directed_paths)
        )

    def find_mediator_set(self,
                         treatment: str,
                         outcome: str) -> Optional[Set[str]]:
        """Find valid mediator set for frontdoor adjustment."""
        directed_paths = self.dag.find_all_paths(treatment, outcome)

        if not directed_paths:
            return None

        # Collect all intermediate nodes
        intermediate = set()
        for path in directed_paths:
            intermediate.update(path[1:-1])

        # Only observed nodes
        intermediate = {
            m for m in intermediate
            if self.dag.get_node(m) and self.dag.get_node(m).observed
        }

        if not intermediate:
            return None

        # Check if full set works
        result = self.is_valid_mediator_set(treatment, outcome, intermediate)
        if result.valid:
            return intermediate

        # Try subsets
        for size in range(len(intermediate), 0, -1):
            for subset in self._combinations(intermediate, size):
                result = self.is_valid_mediator_set(treatment, outcome, subset)
                if result.valid:
                    return subset

        return None

    def _combinations(self, items: Set[str], size: int):
        """Generate combinations."""
        items_list = list(items)
        n = len(items_list)

        if size > n:
            return

        indices = list(range(size))
        yield set(items_list[i] for i in indices)

        while True:
            for i in reversed(range(size)):
                if indices[i] != i + n - size:
                    break
            else:
                return

            indices[i] += 1
            for j in range(i + 1, size):
                indices[j] = indices[j - 1] + 1
            yield set(items_list[i] for i in indices)


class AdjustmentSets:
    """
    Unified interface for finding adjustment sets.
    """

    def __init__(self, dag: Any):
        self.dag = dag
        self.backdoor = BackdoorCriterion(dag)
        self.frontdoor = FrontdoorCriterion(dag)

    def find_adjustment_set(self,
                           treatment: str,
                           outcome: str,
                           method: str = "auto") -> Optional[Set[str]]:
        """
        Find valid adjustment set using specified method.

        Args:
            treatment: Treatment variable
            outcome: Outcome variable
            method: "backdoor", "frontdoor", or "auto"

        Returns:
            Valid adjustment set or None
        """
        if method == "backdoor":
            return self.backdoor.find_minimal_adjustment(treatment, outcome)
        elif method == "frontdoor":
            return self.frontdoor.find_mediator_set(treatment, outcome)
        else:  # auto
            # Try backdoor first
            backdoor_set = self.backdoor.find_minimal_adjustment(treatment, outcome)
            if backdoor_set is not None:
                return backdoor_set

            # Try frontdoor
            frontdoor_set = self.frontdoor.find_mediator_set(treatment, outcome)
            return frontdoor_set

    def get_adjustment_formula(self,
                              treatment: str,
                              outcome: str,
                              adjustment_set: Set[str],
                              method: str) -> str:
        """Get formula for adjustment."""
        if method == "backdoor":
            if not adjustment_set:
                return f"P({outcome}|do({treatment})) = P({outcome}|{treatment})"

            z = ", ".join(sorted(adjustment_set))
            return f"P({outcome}|do({treatment})) = Σ_z P({outcome}|{treatment}, {z}) P({z})"

        elif method == "frontdoor":
            m = ", ".join(sorted(adjustment_set))
            return (
                f"P({outcome}|do({treatment})) = "
                f"Σ_m P({m}|{treatment}) Σ_t P({outcome}|{m}, {treatment}=t) P({treatment}=t)"
            )

        return "Unknown method"
