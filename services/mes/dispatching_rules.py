"""
LEGO Factory v3 - Priority Dispatching Rules
=============================================
Dispatching rules for MESA-11 Operations/Detail Scheduling function.
Implements SPT, EDD, Critical Ratio, WSPT, and composite rules.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DispatchCandidate:
    """A job candidate for dispatching."""
    job_id: str
    machine_id: str
    processing_time_mins: float
    setup_time_mins: float
    due_date: Optional[datetime]
    priority: int  # Higher = more important
    remaining_operations: int
    total_remaining_time: float
    material_type: Optional[str] = None
    current_material_on_machine: Optional[str] = None

    @property
    def total_time(self) -> float:
        """Total time including setup."""
        return self.processing_time_mins + self.setup_time_mins


class DispatchRule(ABC):
    """Base class for dispatching rules."""

    name: str = "base"
    description: str = "Base dispatch rule"

    @abstractmethod
    def score(self, candidate: DispatchCandidate, current_time: datetime) -> float:
        """
        Calculate dispatch priority score for a candidate.
        Higher score = higher priority for dispatch.

        Args:
            candidate: Job candidate to score
            current_time: Current simulation/real time

        Returns:
            Priority score (higher = more urgent)
        """
        pass

    def rank_candidates(
        self,
        candidates: List[DispatchCandidate],
        current_time: datetime
    ) -> List[Tuple[DispatchCandidate, float]]:
        """
        Rank all candidates by their dispatch score.

        Returns:
            List of (candidate, score) tuples sorted by score descending
        """
        scored = [(c, self.score(c, current_time)) for c in candidates]
        return sorted(scored, key=lambda x: x[1], reverse=True)

    def select_best(
        self,
        candidates: List[DispatchCandidate],
        current_time: datetime
    ) -> Optional[DispatchCandidate]:
        """Select the best candidate to dispatch."""
        if not candidates:
            return None
        ranked = self.rank_candidates(candidates, current_time)
        return ranked[0][0] if ranked else None


class SPTRule(DispatchRule):
    """
    Shortest Processing Time (SPT) Rule.
    Prioritizes jobs with shortest processing time.
    Minimizes average flow time and WIP.
    """

    name = "spt"
    description = "Shortest Processing Time - minimizes average flow time"

    def score(self, candidate: DispatchCandidate, current_time: datetime) -> float:
        # Inverse of processing time - shorter jobs get higher scores
        if candidate.total_time <= 0:
            return float('inf')
        return 1.0 / candidate.total_time


class LPTRule(DispatchRule):
    """
    Longest Processing Time (LPT) Rule.
    Prioritizes jobs with longest processing time.
    Can be useful for load balancing.
    """

    name = "lpt"
    description = "Longest Processing Time - useful for load balancing"

    def score(self, candidate: DispatchCandidate, current_time: datetime) -> float:
        return candidate.total_time


class EDDRule(DispatchRule):
    """
    Earliest Due Date (EDD) Rule.
    Prioritizes jobs with earliest due dates.
    Minimizes maximum lateness.
    """

    name = "edd"
    description = "Earliest Due Date - minimizes maximum lateness"

    def score(self, candidate: DispatchCandidate, current_time: datetime) -> float:
        if candidate.due_date is None:
            # No due date = lowest priority
            return float('-inf')

        # Earlier due date = higher score (negative time to due)
        time_to_due = (candidate.due_date - current_time).total_seconds() / 60.0
        return -time_to_due  # Negative so earlier dates get higher scores


class CriticalRatioRule(DispatchRule):
    """
    Critical Ratio (CR) Rule.
    CR = (Due Date - Now) / Remaining Processing Time

    CR < 1: Job is behind schedule (urgent)
    CR = 1: Job is on schedule
    CR > 1: Job is ahead of schedule

    Prioritizes jobs with lowest CR (most behind).
    """

    name = "cr"
    description = "Critical Ratio - prioritizes jobs behind schedule"

    def score(self, candidate: DispatchCandidate, current_time: datetime) -> float:
        if candidate.due_date is None:
            return float('-inf')

        time_to_due = (candidate.due_date - current_time).total_seconds() / 60.0
        remaining_time = candidate.total_remaining_time if candidate.total_remaining_time > 0 else candidate.total_time

        if remaining_time <= 0:
            return float('inf') if time_to_due > 0 else float('-inf')

        cr = time_to_due / remaining_time

        # Lower CR = higher priority (more urgent)
        # Return negative CR so lower CR gets higher score
        return -cr


class WSPTRule(DispatchRule):
    """
    Weighted Shortest Processing Time (WSPT) Rule.
    Score = Priority / Processing Time

    Balances job importance with processing efficiency.
    Minimizes weighted completion time.
    """

    name = "wspt"
    description = "Weighted SPT - balances priority with processing time"

    def score(self, candidate: DispatchCandidate, current_time: datetime) -> float:
        if candidate.total_time <= 0:
            return float('inf') * candidate.priority

        return candidate.priority / candidate.total_time


class SlackTimeRule(DispatchRule):
    """
    Slack Time Rule.
    Slack = Due Date - Now - Remaining Processing Time

    Prioritizes jobs with least slack (tightest schedule).
    """

    name = "slack"
    description = "Slack Time - prioritizes jobs with tightest schedules"

    def score(self, candidate: DispatchCandidate, current_time: datetime) -> float:
        if candidate.due_date is None:
            return float('-inf')

        time_to_due = (candidate.due_date - current_time).total_seconds() / 60.0
        remaining_time = candidate.total_remaining_time if candidate.total_remaining_time > 0 else candidate.total_time

        slack = time_to_due - remaining_time

        # Lower slack = higher priority
        return -slack


class FIFORule(DispatchRule):
    """
    First In First Out (FIFO) Rule.
    Processes jobs in arrival order.
    Requires arrival_time in candidate data.
    """

    name = "fifo"
    description = "First In First Out - processes in arrival order"

    def score(self, candidate: DispatchCandidate, current_time: datetime) -> float:
        # Use job_id as proxy for arrival order (assumes sequential IDs)
        # In production, would use actual arrival timestamp
        try:
            # Extract numeric portion of job_id
            numeric = ''.join(filter(str.isdigit, candidate.job_id))
            return -int(numeric) if numeric else 0
        except:
            return 0


class SetupMinimizationRule(DispatchRule):
    """
    Setup Time Minimization Rule.
    Prioritizes jobs that require no setup change (same material).
    """

    name = "setup_min"
    description = "Setup Minimization - reduces changeover time"

    def score(self, candidate: DispatchCandidate, current_time: datetime) -> float:
        # If same material as current, no setup needed
        if (candidate.material_type and
            candidate.material_type == candidate.current_material_on_machine):
            return 1000.0 + (1.0 / max(candidate.processing_time_mins, 0.1))

        # Otherwise, penalize by setup time
        return 1.0 / max(candidate.total_time, 0.1)


class CompositeRule(DispatchRule):
    """
    Composite Rule combining multiple rules with weights.
    Score = sum(weight_i * normalized_score_i)
    """

    name = "composite"
    description = "Weighted combination of multiple rules"

    def __init__(self, rules_weights: Dict[str, float]):
        """
        Args:
            rules_weights: Dict mapping rule name to weight
                          e.g., {'spt': 0.3, 'edd': 0.5, 'wspt': 0.2}
        """
        self.rules: List[Tuple[DispatchRule, float]] = []

        rule_map = {
            'spt': SPTRule(),
            'lpt': LPTRule(),
            'edd': EDDRule(),
            'cr': CriticalRatioRule(),
            'wspt': WSPTRule(),
            'slack': SlackTimeRule(),
            'fifo': FIFORule(),
            'setup_min': SetupMinimizationRule(),
        }

        for rule_name, weight in rules_weights.items():
            if rule_name in rule_map:
                self.rules.append((rule_map[rule_name], weight))

        # Normalize weights
        total_weight = sum(w for _, w in self.rules)
        if total_weight > 0:
            self.rules = [(r, w/total_weight) for r, w in self.rules]

    def score(self, candidate: DispatchCandidate, current_time: datetime) -> float:
        if not self.rules:
            return 0.0

        total_score = 0.0
        for rule, weight in self.rules:
            rule_score = rule.score(candidate, current_time)
            # Clamp infinite scores
            if rule_score == float('inf'):
                rule_score = 1e10
            elif rule_score == float('-inf'):
                rule_score = -1e10
            total_score += weight * rule_score

        return total_score


# =============================================================================
# Dispatching Service Functions
# =============================================================================

AVAILABLE_RULES: Dict[str, type] = {
    'spt': SPTRule,
    'lpt': LPTRule,
    'edd': EDDRule,
    'cr': CriticalRatioRule,
    'wspt': WSPTRule,
    'slack': SlackTimeRule,
    'fifo': FIFORule,
    'setup_min': SetupMinimizationRule,
}


def get_dispatch_rule(rule_name: str, **kwargs) -> DispatchRule:
    """
    Get a dispatch rule by name.

    Args:
        rule_name: Name of the rule ('spt', 'edd', 'cr', 'wspt', 'composite')
        **kwargs: Additional arguments (for composite rule, pass rules_weights)

    Returns:
        Instantiated dispatch rule
    """
    if rule_name == 'composite':
        rules_weights = kwargs.get('rules_weights', {'spt': 0.5, 'edd': 0.5})
        return CompositeRule(rules_weights)

    rule_class = AVAILABLE_RULES.get(rule_name.lower())
    if rule_class:
        return rule_class()

    logger.warning(f"Unknown dispatch rule '{rule_name}', defaulting to SPT")
    return SPTRule()


def dispatch_next_job(
    machine_id: str,
    candidate_jobs: List[Dict[str, Any]],
    rule_name: str = 'spt',
    current_time: Optional[datetime] = None,
    current_material: Optional[str] = None,
    **kwargs
) -> Optional[Dict[str, Any]]:
    """
    Select the next job to dispatch to a machine using specified rule.

    Args:
        machine_id: Target machine ID
        candidate_jobs: List of job dicts with keys:
                       job_id, processing_time_mins, setup_time_mins,
                       due_date, priority, remaining_operations,
                       total_remaining_time, material_type
        rule_name: Dispatch rule to use
        current_time: Current time (defaults to now)
        current_material: Currently loaded material on machine
        **kwargs: Additional rule parameters

    Returns:
        Selected job dict or None if no candidates
    """
    if not candidate_jobs:
        return None

    current_time = current_time or datetime.utcnow()
    rule = get_dispatch_rule(rule_name, **kwargs)

    # Convert to DispatchCandidate objects
    candidates = []
    for job in candidate_jobs:
        due_date = job.get('due_date')
        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))

        candidates.append(DispatchCandidate(
            job_id=job['job_id'],
            machine_id=machine_id,
            processing_time_mins=job.get('processing_time_mins', 0),
            setup_time_mins=job.get('setup_time_mins', 0),
            due_date=due_date,
            priority=job.get('priority', 1),
            remaining_operations=job.get('remaining_operations', 1),
            total_remaining_time=job.get('total_remaining_time', job.get('processing_time_mins', 0)),
            material_type=job.get('material_type'),
            current_material_on_machine=current_material,
        ))

    # Select best candidate
    best = rule.select_best(candidates, current_time)

    if best:
        # Return the original job dict
        for job in candidate_jobs:
            if job['job_id'] == best.job_id:
                return job

    return None


def rank_jobs_by_rule(
    candidate_jobs: List[Dict[str, Any]],
    rule_name: str = 'spt',
    current_time: Optional[datetime] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Rank all jobs according to dispatch rule.

    Returns:
        Jobs sorted by dispatch priority (highest first)
    """
    if not candidate_jobs:
        return []

    current_time = current_time or datetime.utcnow()
    rule = get_dispatch_rule(rule_name, **kwargs)

    # Convert to candidates and score
    job_scores = []
    for job in candidate_jobs:
        due_date = job.get('due_date')
        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))

        candidate = DispatchCandidate(
            job_id=job['job_id'],
            machine_id=job.get('machine_id', ''),
            processing_time_mins=job.get('processing_time_mins', 0),
            setup_time_mins=job.get('setup_time_mins', 0),
            due_date=due_date,
            priority=job.get('priority', 1),
            remaining_operations=job.get('remaining_operations', 1),
            total_remaining_time=job.get('total_remaining_time', job.get('processing_time_mins', 0)),
            material_type=job.get('material_type'),
        )

        score = rule.score(candidate, current_time)
        job_scores.append((job, score))

    # Sort by score descending
    job_scores.sort(key=lambda x: x[1], reverse=True)

    return [job for job, _ in job_scores]


def compare_dispatch_rules(
    candidate_jobs: List[Dict[str, Any]],
    rules: Optional[List[str]] = None,
    current_time: Optional[datetime] = None,
) -> Dict[str, List[str]]:
    """
    Compare how different rules would order the same jobs.

    Returns:
        Dict mapping rule name to ordered list of job IDs
    """
    rules = rules or list(AVAILABLE_RULES.keys())
    current_time = current_time or datetime.utcnow()

    results = {}
    for rule_name in rules:
        ranked = rank_jobs_by_rule(candidate_jobs, rule_name, current_time)
        results[rule_name] = [job['job_id'] for job in ranked]

    return results


def get_rule_descriptions() -> Dict[str, str]:
    """Get descriptions of all available dispatch rules."""
    return {
        name: cls().description
        for name, cls in AVAILABLE_RULES.items()
    }
