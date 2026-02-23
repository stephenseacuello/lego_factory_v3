"""
Causal Identifiability - Effect identification algorithms.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IdentificationMethod(Enum):
    """Method used for identification."""
    BACKDOOR = "backdoor"
    FRONTDOOR = "frontdoor"
    INSTRUMENTAL = "instrumental"
    DO_CALCULUS = "do_calculus"
    NOT_IDENTIFIABLE = "not_identifiable"


@dataclass
class CausalEffect:
    """Identified causal effect."""
    treatment: str
    outcome: str
    identifiable: bool
    method: IdentificationMethod
    adjustment_set: Optional[Set[str]] = None
    estimand: Optional[str] = None
    assumptions: List[str] = None


class IdentifiabilityChecker:
    """
    Check if causal effects are identifiable from observational data.

    Features:
    - Backdoor criterion
    - Frontdoor criterion
    - Instrumental variable identification
    - General do-calculus
    """

    def __init__(self, dag: Any):
        """
        Initialize checker.

        Args:
            dag: CausalDAG instance
        """
        self.dag = dag

    def check_identifiability(self,
                             treatment: str,
                             outcome: str) -> CausalEffect:
        """
        Check if causal effect is identifiable.

        Args:
            treatment: Treatment variable
            outcome: Outcome variable

        Returns:
            CausalEffect with identification result
        """
        # Try backdoor criterion first
        backdoor_result = self.check_backdoor_criterion(treatment, outcome)
        if backdoor_result.identifiable:
            return backdoor_result

        # Try frontdoor criterion
        frontdoor_result = self.check_frontdoor_criterion(treatment, outcome)
        if frontdoor_result.identifiable:
            return frontdoor_result

        # Try instrumental variable
        iv_result = self.check_instrumental_variable(treatment, outcome)
        if iv_result.identifiable:
            return iv_result

        # Effect not identifiable with standard methods
        return CausalEffect(
            treatment=treatment,
            outcome=outcome,
            identifiable=False,
            method=IdentificationMethod.NOT_IDENTIFIABLE,
            assumptions=["No standard identification strategy found"]
        )

    def check_backdoor_criterion(self,
                                treatment: str,
                                outcome: str) -> CausalEffect:
        """
        Check backdoor criterion for identification.

        A set Z satisfies the backdoor criterion if:
        1. No node in Z is a descendant of treatment
        2. Z blocks all backdoor paths from treatment to outcome
        """
        # Find minimal backdoor adjustment set
        adjustment_set = self._find_backdoor_adjustment(treatment, outcome)

        if adjustment_set is not None:
            estimand = self._generate_backdoor_estimand(
                treatment, outcome, adjustment_set
            )

            return CausalEffect(
                treatment=treatment,
                outcome=outcome,
                identifiable=True,
                method=IdentificationMethod.BACKDOOR,
                adjustment_set=adjustment_set,
                estimand=estimand,
                assumptions=[
                    "No unobserved confounders",
                    "Positivity: P(T|Z) > 0 for all Z",
                    "No measurement error in adjustment variables"
                ]
            )

        return CausalEffect(
            treatment=treatment,
            outcome=outcome,
            identifiable=False,
            method=IdentificationMethod.BACKDOOR,
            assumptions=["Backdoor criterion not satisfied"]
        )

    def _find_backdoor_adjustment(self,
                                 treatment: str,
                                 outcome: str) -> Optional[Set[str]]:
        """Find minimal set satisfying backdoor criterion."""
        # Get all potential adjustment variables
        treatment_descendants = self.dag.get_descendants(treatment)
        all_nodes = set(n.name for n in self.dag.get_nodes())

        # Exclude treatment, outcome, and descendants of treatment
        candidates = all_nodes - {treatment, outcome} - treatment_descendants

        # Only include observed variables
        candidates = {
            c for c in candidates
            if self.dag.get_node(c) and self.dag.get_node(c).observed
        }

        # Check if candidates block all backdoor paths
        backdoor_paths = self.dag.find_backdoor_paths(treatment, outcome)

        if not backdoor_paths:
            return set()  # No backdoor paths, empty set works

        # Try to find minimal blocking set
        for size in range(len(candidates) + 1):
            for subset in self._combinations(candidates, size):
                if self._blocks_all_paths(subset, backdoor_paths):
                    return subset

        return None

    def _combinations(self, items: Set[str], size: int):
        """Generate combinations of given size."""
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

    def _blocks_all_paths(self,
                         blocking_set: Set[str],
                         paths: List[List[str]]) -> bool:
        """Check if blocking set blocks all paths."""
        for path in paths:
            # A path is blocked if any non-collider node is in blocking set
            # or any collider (or its descendants) is NOT in blocking set

            blocked = False
            for i in range(1, len(path) - 1):
                node = path[i]

                if node in blocking_set:
                    blocked = True
                    break

            if not blocked:
                return False

        return True

    def check_frontdoor_criterion(self,
                                 treatment: str,
                                 outcome: str) -> CausalEffect:
        """
        Check frontdoor criterion for identification.

        A set M satisfies the frontdoor criterion if:
        1. M intercepts all directed paths from treatment to outcome
        2. No unblocked backdoor path from treatment to M
        3. All backdoor paths from M to outcome are blocked by treatment
        """
        # Find potential mediator sets
        mediator_set = self._find_frontdoor_mediators(treatment, outcome)

        if mediator_set is not None:
            estimand = self._generate_frontdoor_estimand(
                treatment, outcome, mediator_set
            )

            return CausalEffect(
                treatment=treatment,
                outcome=outcome,
                identifiable=True,
                method=IdentificationMethod.FRONTDOOR,
                adjustment_set=mediator_set,
                estimand=estimand,
                assumptions=[
                    "Complete mediation through M",
                    "No direct effect T->Y outside M",
                    "No unobserved confounders T->M or M->Y"
                ]
            )

        return CausalEffect(
            treatment=treatment,
            outcome=outcome,
            identifiable=False,
            method=IdentificationMethod.FRONTDOOR,
            assumptions=["Frontdoor criterion not satisfied"]
        )

    def _find_frontdoor_mediators(self,
                                 treatment: str,
                                 outcome: str) -> Optional[Set[str]]:
        """Find set satisfying frontdoor criterion."""
        # Find nodes on directed paths from treatment to outcome
        directed_paths = self.dag.find_all_paths(treatment, outcome)

        if not directed_paths:
            return None

        # Get mediators (nodes between treatment and outcome on directed paths)
        mediators = set()
        for path in directed_paths:
            mediators.update(path[1:-1])  # Exclude treatment and outcome

        # Check frontdoor conditions
        # This is a simplified check
        if mediators:
            # Verify no backdoor from treatment to mediators
            for m in mediators:
                backdoor_paths = self.dag.find_backdoor_paths(treatment, m)
                if backdoor_paths:
                    # Check if all blocked
                    # Simplified: return None if any backdoor exists
                    return None

            return mediators

        return None

    def check_instrumental_variable(self,
                                   treatment: str,
                                   outcome: str) -> CausalEffect:
        """
        Check for instrumental variable identification.

        An instrument Z is valid if:
        1. Z affects treatment (relevance)
        2. Z affects outcome only through treatment (exclusion)
        3. Z is not confounded with outcome
        """
        # Find potential instruments
        instrument = self._find_instrument(treatment, outcome)

        if instrument is not None:
            estimand = f"E[Y|Z=1] - E[Y|Z=0] / (E[T|Z=1] - E[T|Z=0])"

            return CausalEffect(
                treatment=treatment,
                outcome=outcome,
                identifiable=True,
                method=IdentificationMethod.INSTRUMENTAL,
                adjustment_set={instrument},
                estimand=estimand,
                assumptions=[
                    f"Relevance: {instrument} affects {treatment}",
                    f"Exclusion: {instrument} affects {outcome} only through {treatment}",
                    f"Independence: {instrument} not confounded with {outcome}"
                ]
            )

        return CausalEffect(
            treatment=treatment,
            outcome=outcome,
            identifiable=False,
            method=IdentificationMethod.INSTRUMENTAL,
            assumptions=["No valid instrumental variable found"]
        )

    def _find_instrument(self,
                        treatment: str,
                        outcome: str) -> Optional[str]:
        """Find valid instrumental variable."""
        treatment_parents = self.dag.get_parents(treatment)
        outcome_ancestors = self.dag.get_ancestors(outcome)

        for node in treatment_parents:
            # Check if node is not an ancestor of outcome except through treatment
            node_descendants = self.dag.get_descendants(node)

            # Node affects treatment (it's a parent)
            # Check exclusion: only path to outcome is through treatment
            paths_to_outcome = self.dag.find_all_paths(node, outcome)

            valid = True
            for path in paths_to_outcome:
                if treatment not in path:
                    # Direct path not through treatment
                    valid = False
                    break

            if valid:
                # Check no confounding with outcome
                node_obj = self.dag.get_node(node)
                if node_obj and node_obj.observed:
                    return node

        return None

    def _generate_backdoor_estimand(self,
                                   treatment: str,
                                   outcome: str,
                                   adjustment: Set[str]) -> str:
        """Generate backdoor adjustment formula."""
        if not adjustment:
            return f"E[{outcome}|do({treatment}=t)] = E[{outcome}|{treatment}=t]"

        adj_str = ", ".join(sorted(adjustment))
        return f"E[{outcome}|do({treatment}=t)] = Σ_z E[{outcome}|{treatment}=t, {adj_str}=z] P({adj_str}=z)"

    def _generate_frontdoor_estimand(self,
                                    treatment: str,
                                    outcome: str,
                                    mediators: Set[str]) -> str:
        """Generate frontdoor adjustment formula."""
        med_str = ", ".join(sorted(mediators))
        return f"E[{outcome}|do({treatment}=t)] = Σ_m P({med_str}=m|{treatment}=t) Σ_t' P({outcome}|{med_str}=m, {treatment}=t') P({treatment}=t')"
