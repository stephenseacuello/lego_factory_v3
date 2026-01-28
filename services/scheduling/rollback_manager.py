"""
Scheduling Policy Rollback Manager
===================================
Automatic rollback on policy degradation with support for
canary deployments and A/B testing.

Features:
- Continuous KPI monitoring
- Automatic rollback on regression
- Configurable regression thresholds
- Policy promotion workflow
- Alert integration

Author: Flask CNC SCADA System
"""

import os
import json
import time
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class PolicyStatus(str, Enum):
    """Policy deployment status."""
    BASELINE = "baseline"
    CANARY = "canary"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"
    DISABLED = "disabled"


@dataclass
class KPISnapshot:
    """Snapshot of KPIs at a point in time."""
    timestamp: float
    policy_name: str
    makespan: float = 0.0
    total_tardiness: float = 0.0
    num_late_jobs: int = 0
    avg_flow_time: float = 0.0
    machine_utilization: float = 0.0
    num_violations: int = 0
    throughput: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RollbackEvent:
    """Record of a rollback event."""
    timestamp: float
    from_policy: str
    to_policy: str
    reason: str
    kpi_before: Dict[str, float]
    kpi_baseline: Dict[str, float]
    regression_detected: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyRecord:
    """Tracking record for a policy."""
    policy_name: str
    status: PolicyStatus
    canary_start: Optional[float] = None
    canary_percentage: float = 0.0
    jobs_processed: int = 0
    violations: int = 0
    kpi_history: List[KPISnapshot] = field(default_factory=list)
    promoted_at: Optional[float] = None
    rolled_back_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_name": self.policy_name,
            "status": self.status.value,
            "canary_start": self.canary_start,
            "canary_percentage": self.canary_percentage,
            "jobs_processed": self.jobs_processed,
            "violations": self.violations,
            "kpi_snapshots": len(self.kpi_history),
            "promoted_at": self.promoted_at,
            "rolled_back_at": self.rolled_back_at
        }


class RollbackManager:
    """
    Automatic rollback on policy degradation.

    Monitors KPIs from active policies and automatically
    rolls back to baseline if significant regression detected.
    """

    # Default regression thresholds (negative = worse)
    DEFAULT_THRESHOLDS = {
        "makespan": 0.1,           # 10% worse makespan triggers rollback
        "tardiness": 0.15,         # 15% worse tardiness
        "utilization": -0.1,       # 10% lower utilization
        "throughput": -0.1,        # 10% lower throughput
        "violations": 0.2          # 20% more violations
    }

    def __init__(
        self,
        baseline_policy_name: str = "edd",
        regression_threshold: float = 0.1,
        min_samples: int = 50,
        evaluation_window: int = 100,
        alert_callback: Optional[Callable[[str, Dict], None]] = None
    ):
        """
        Initialize rollback manager.

        Args:
            baseline_policy_name: Name of baseline policy to compare against
            regression_threshold: Default threshold for regression detection
            min_samples: Minimum samples before evaluating for rollback
            evaluation_window: Number of recent samples to evaluate
            alert_callback: Function to call on rollback (msg, details)
        """
        self.baseline_policy_name = baseline_policy_name
        self.regression_threshold = regression_threshold
        self.min_samples = min_samples
        self.evaluation_window = evaluation_window
        self.alert_callback = alert_callback

        self._lock = threading.Lock()
        self._policies: Dict[str, PolicyRecord] = {}
        self._rollback_events: List[RollbackEvent] = []
        self._active_policy: str = baseline_policy_name

        # KPI thresholds (can be customized per-metric)
        self._thresholds = dict(self.DEFAULT_THRESHOLDS)

        # Baseline KPI buffer
        self._baseline_kpis: deque = deque(maxlen=evaluation_window)

        # Initialize baseline policy record
        self._policies[baseline_policy_name] = PolicyRecord(
            policy_name=baseline_policy_name,
            status=PolicyStatus.BASELINE
        )

        logger.info(
            f"RollbackManager initialized (baseline={baseline_policy_name}, "
            f"threshold={regression_threshold})"
        )

    # =========================================================================
    # Configuration
    # =========================================================================

    def set_threshold(self, metric: str, threshold: float) -> None:
        """
        Set regression threshold for a specific metric.

        Args:
            metric: Metric name
            threshold: Threshold value (positive = must be lower, negative = must be higher)
        """
        self._thresholds[metric] = threshold
        logger.info(f"Threshold set: {metric} = {threshold}")

    def set_alert_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """Set callback for alerts."""
        self.alert_callback = callback

    # =========================================================================
    # Policy Management
    # =========================================================================

    def start_canary(
        self,
        policy_name: str,
        percentage: float = 0.1
    ) -> bool:
        """
        Start canary deployment for a policy.

        Args:
            policy_name: Policy to test
            percentage: Traffic percentage (0.0-1.0)

        Returns:
            True if canary started successfully
        """
        if percentage < 0 or percentage > 1:
            logger.error("Invalid canary percentage")
            return False

        with self._lock:
            record = PolicyRecord(
                policy_name=policy_name,
                status=PolicyStatus.CANARY,
                canary_start=time.time(),
                canary_percentage=percentage
            )
            self._policies[policy_name] = record

        logger.info(f"Canary started: {policy_name} at {percentage*100:.0f}%")
        return True

    def record_kpi(
        self,
        policy_name: str,
        kpi: KPISnapshot
    ) -> Optional[RollbackEvent]:
        """
        Record KPI snapshot for a policy.

        Evaluates for regression and may trigger rollback.

        Args:
            policy_name: Policy that produced this result
            kpi: KPI snapshot

        Returns:
            RollbackEvent if rollback triggered, None otherwise
        """
        with self._lock:
            if policy_name not in self._policies:
                self._policies[policy_name] = PolicyRecord(
                    policy_name=policy_name,
                    status=PolicyStatus.CANARY
                )

            record = self._policies[policy_name]
            record.kpi_history.append(kpi)
            record.jobs_processed += 1

            # Keep history bounded
            if len(record.kpi_history) > self.evaluation_window * 2:
                record.kpi_history = record.kpi_history[-self.evaluation_window:]

            # Track baseline KPIs
            if policy_name == self.baseline_policy_name:
                self._baseline_kpis.append(kpi)
                return None

            # Check for regression if enough samples
            if record.jobs_processed >= self.min_samples:
                rollback = self._evaluate_for_rollback(record)
                if rollback:
                    return rollback

        return None

    def record_violation(self, policy_name: str) -> None:
        """Record a constraint violation for a policy."""
        with self._lock:
            if policy_name in self._policies:
                self._policies[policy_name].violations += 1

    def promote_policy(self, policy_name: str) -> bool:
        """
        Promote a canary policy to active.

        Args:
            policy_name: Policy to promote

        Returns:
            True if promotion successful
        """
        with self._lock:
            if policy_name not in self._policies:
                logger.error(f"Policy not found: {policy_name}")
                return False

            record = self._policies[policy_name]

            if record.status != PolicyStatus.CANARY:
                logger.warning(f"Policy {policy_name} is not in canary status")
                return False

            # Check if ready for promotion
            if record.jobs_processed < self.min_samples:
                logger.warning(
                    f"Insufficient samples for promotion: {record.jobs_processed}/{self.min_samples}"
                )
                return False

            # Demote current active
            old_active = self._active_policy
            if old_active in self._policies:
                self._policies[old_active].status = PolicyStatus.BASELINE

            # Promote new policy
            record.status = PolicyStatus.PROMOTED
            record.promoted_at = time.time()
            self._active_policy = policy_name

            logger.info(f"Policy promoted: {policy_name} (replaced {old_active})")

            if self.alert_callback:
                self.alert_callback(
                    f"Policy {policy_name} promoted to active",
                    {"old_policy": old_active, "new_policy": policy_name}
                )

            return True

    def get_active_policy(self) -> str:
        """Get currently active policy name."""
        return self._active_policy

    # =========================================================================
    # Evaluation & Rollback
    # =========================================================================

    def _evaluate_for_rollback(self, record: PolicyRecord) -> Optional[RollbackEvent]:
        """
        Evaluate if a policy should be rolled back.

        Args:
            record: Policy record to evaluate

        Returns:
            RollbackEvent if rollback needed, None otherwise
        """
        if not self._baseline_kpis:
            return None

        # Get recent KPIs for this policy
        recent_kpis = record.kpi_history[-self.evaluation_window:]
        if len(recent_kpis) < self.min_samples:
            return None

        # Calculate average KPIs
        policy_avg = self._calculate_avg_kpis(recent_kpis)
        baseline_avg = self._calculate_avg_kpis(list(self._baseline_kpis))

        # Check each metric for regression
        regressions = {}

        # Makespan (lower is better)
        if baseline_avg["makespan"] > 0:
            regression = (policy_avg["makespan"] - baseline_avg["makespan"]) / baseline_avg["makespan"]
            if regression > self._thresholds.get("makespan", self.regression_threshold):
                regressions["makespan"] = regression

        # Tardiness (lower is better)
        if baseline_avg["tardiness"] > 0:
            regression = (policy_avg["tardiness"] - baseline_avg["tardiness"]) / baseline_avg["tardiness"]
            if regression > self._thresholds.get("tardiness", self.regression_threshold):
                regressions["tardiness"] = regression

        # Utilization (higher is better)
        if baseline_avg["utilization"] > 0:
            regression = (baseline_avg["utilization"] - policy_avg["utilization"]) / baseline_avg["utilization"]
            if regression > abs(self._thresholds.get("utilization", -self.regression_threshold)):
                regressions["utilization"] = regression

        # Throughput (higher is better)
        if baseline_avg["throughput"] > 0:
            regression = (baseline_avg["throughput"] - policy_avg["throughput"]) / baseline_avg["throughput"]
            if regression > abs(self._thresholds.get("throughput", -self.regression_threshold)):
                regressions["throughput"] = regression

        # Violations (lower is better)
        if baseline_avg["violations"] > 0:
            regression = (policy_avg["violations"] - baseline_avg["violations"]) / baseline_avg["violations"]
            if regression > self._thresholds.get("violations", self.regression_threshold):
                regressions["violations"] = regression

        # Trigger rollback if any significant regression
        if regressions:
            return self._trigger_rollback(record, policy_avg, baseline_avg, regressions)

        return None

    def _calculate_avg_kpis(self, kpis: List[KPISnapshot]) -> Dict[str, float]:
        """Calculate average KPIs from snapshots."""
        if not kpis:
            return {
                "makespan": 0,
                "tardiness": 0,
                "utilization": 0,
                "throughput": 0,
                "violations": 0
            }

        return {
            "makespan": sum(k.makespan for k in kpis) / len(kpis),
            "tardiness": sum(k.total_tardiness for k in kpis) / len(kpis),
            "utilization": sum(k.machine_utilization for k in kpis) / len(kpis),
            "throughput": sum(k.throughput for k in kpis) / len(kpis),
            "violations": sum(k.num_violations for k in kpis) / len(kpis)
        }

    def _trigger_rollback(
        self,
        record: PolicyRecord,
        policy_kpis: Dict[str, float],
        baseline_kpis: Dict[str, float],
        regressions: Dict[str, float]
    ) -> RollbackEvent:
        """
        Execute rollback for a policy.

        Args:
            record: Policy record to rollback
            policy_kpis: Current policy KPIs
            baseline_kpis: Baseline KPIs
            regressions: Detected regressions

        Returns:
            RollbackEvent describing the rollback
        """
        event = RollbackEvent(
            timestamp=time.time(),
            from_policy=record.policy_name,
            to_policy=self.baseline_policy_name,
            reason=f"Regression detected: {', '.join(regressions.keys())}",
            kpi_before=policy_kpis,
            kpi_baseline=baseline_kpis,
            regression_detected=regressions
        )

        # Update policy status
        record.status = PolicyStatus.ROLLED_BACK
        record.rolled_back_at = time.time()

        # If this was the active policy, switch to baseline
        if self._active_policy == record.policy_name:
            self._active_policy = self.baseline_policy_name
            logger.warning(f"Active policy rolled back to {self.baseline_policy_name}")

        self._rollback_events.append(event)

        logger.warning(
            f"ROLLBACK: {record.policy_name} -> {self.baseline_policy_name} "
            f"(regressions: {regressions})"
        )

        # Send alert
        if self.alert_callback:
            self.alert_callback(
                f"Policy rollback: {record.policy_name}",
                event.to_dict()
            )

        return event

    def evaluate_and_maybe_rollback(
        self,
        recent_kpis: Dict[str, float],
        policy_name: Optional[str] = None
    ) -> bool:
        """
        Evaluate recent KPIs and potentially trigger rollback.

        Simplified interface for external callers.

        Args:
            recent_kpis: Dict of metric -> value
            policy_name: Policy to evaluate (default: active policy)

        Returns:
            True if rollback was triggered
        """
        policy_name = policy_name or self._active_policy

        if policy_name == self.baseline_policy_name:
            return False

        # Create KPI snapshot
        kpi = KPISnapshot(
            timestamp=time.time(),
            policy_name=policy_name,
            makespan=recent_kpis.get("makespan", 0),
            total_tardiness=recent_kpis.get("tardiness", 0),
            machine_utilization=recent_kpis.get("utilization", 0),
            throughput=recent_kpis.get("throughput", 0),
            num_violations=int(recent_kpis.get("violations", 0))
        )

        event = self.record_kpi(policy_name, kpi)
        return event is not None

    # =========================================================================
    # Status & Reporting
    # =========================================================================

    def get_policy_status(self, policy_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific policy."""
        with self._lock:
            if policy_name in self._policies:
                return self._policies[policy_name].to_dict()
        return None

    def get_all_policies(self) -> List[Dict[str, Any]]:
        """Get status of all tracked policies."""
        with self._lock:
            return [p.to_dict() for p in self._policies.values()]

    def get_rollback_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent rollback events."""
        with self._lock:
            events = self._rollback_events[-limit:]
            return [e.to_dict() for e in events]

    def get_status(self) -> Dict[str, Any]:
        """Get overall rollback manager status."""
        with self._lock:
            return {
                "active_policy": self._active_policy,
                "baseline_policy": self.baseline_policy_name,
                "regression_threshold": self.regression_threshold,
                "min_samples": self.min_samples,
                "evaluation_window": self.evaluation_window,
                "tracked_policies": len(self._policies),
                "rollback_count": len(self._rollback_events),
                "baseline_samples": len(self._baseline_kpis),
                "thresholds": dict(self._thresholds)
            }

    def is_regression(
        self,
        current: Dict[str, float],
        baseline: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Check if current KPIs represent a regression from baseline.

        Args:
            current: Current KPIs
            baseline: Baseline KPIs

        Returns:
            Dict of metric -> regression percentage (empty if no regression)
        """
        regressions = {}

        for metric in ["makespan", "tardiness"]:
            if baseline.get(metric, 0) > 0:
                change = (current.get(metric, 0) - baseline.get(metric, 0)) / baseline.get(metric, 0)
                threshold = self._thresholds.get(metric, self.regression_threshold)
                if change > threshold:
                    regressions[metric] = change

        for metric in ["utilization", "throughput"]:
            if baseline.get(metric, 0) > 0:
                change = (baseline.get(metric, 0) - current.get(metric, 0)) / baseline.get(metric, 0)
                threshold = abs(self._thresholds.get(metric, -self.regression_threshold))
                if change > threshold:
                    regressions[metric] = change

        return regressions


# =============================================================================
# Singleton Instance
# =============================================================================

_rollback_manager: Optional[RollbackManager] = None
_lock = threading.Lock()


def get_rollback_manager(
    baseline_policy: str = "edd"
) -> RollbackManager:
    """Get or create rollback manager singleton."""
    global _rollback_manager
    with _lock:
        if _rollback_manager is None:
            _rollback_manager = RollbackManager(
                baseline_policy_name=baseline_policy
            )
        return _rollback_manager
