"""
Schedule Decision Dispatcher
=============================
Validates and executes scheduling decisions with support for
shadow mode and canary deployments.

Features:
- Decision validation against constraints
- Shadow mode (log but don't execute)
- Canary routing (X% to new policy)
- Violation tracking and alerting
- Decision audit trail

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
from enum import Enum

from services.scheduling.policy_interface import (
    SchedulingPolicy,
    ScheduleState,
    ScheduleDecision,
    Job,
    Machine,
    JobStatus,
    MachineStatus,
    get_policy
)

logger = logging.getLogger(__name__)


class ViolationType(str, Enum):
    """Types of constraint violations."""
    MACHINE_UNAVAILABLE = "machine_unavailable"
    MACHINE_BUSY = "machine_busy"
    TOOLING_NOT_READY = "tooling_not_ready"
    CAPABILITY_MISMATCH = "capability_mismatch"
    WIP_LIMIT_EXCEEDED = "wip_limit_exceeded"
    QUALITY_HOLD = "quality_hold"
    MAINTENANCE_SCHEDULED = "maintenance_scheduled"
    MATERIAL_SHORTAGE = "material_shortage"
    OPERATOR_UNAVAILABLE = "operator_unavailable"
    INVALID_JOB = "invalid_job"
    INVALID_MACHINE = "invalid_machine"
    CONSTRAINT_VIOLATION = "constraint_violation"


@dataclass
class DispatchResult:
    """Result of processing a scheduling decision."""
    decision_id: str
    accepted: bool
    executed: bool = False
    shadow: bool = False
    violations: List[str] = field(default_factory=list)
    reason: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionAuditEntry:
    """Audit trail entry for a scheduling decision."""
    decision_id: str
    policy_name: str
    policy_version: str
    job_id: str
    machine_id: str
    start_time: float
    result: DispatchResult
    state_snapshot: Optional[Dict] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "job_id": self.job_id,
            "machine_id": self.machine_id,
            "start_time": self.start_time,
            "result": self.result.to_dict(),
            "timestamp": self.timestamp
        }


class ScheduleDispatcher:
    """
    Validates and executes scheduling decisions.

    Supports:
    - Constraint validation before execution
    - Shadow mode for logging without execution
    - Canary deployment with configurable traffic split
    - Decision audit trail
    """

    def __init__(
        self,
        shadow_mode: bool = False,
        baseline_policy_name: str = "edd",
        wip_limit_per_machine: int = 5,
        audit_dir: Optional[str] = None
    ):
        """
        Initialize dispatcher.

        Args:
            shadow_mode: If True, log decisions but don't execute
            baseline_policy_name: Fallback policy name
            wip_limit_per_machine: Max WIP items per machine
            audit_dir: Directory for audit logs
        """
        self.shadow_mode = shadow_mode
        self.baseline_policy_name = baseline_policy_name
        self.wip_limit_per_machine = wip_limit_per_machine

        self.audit_dir = audit_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "dispatch_audit"
        )
        os.makedirs(self.audit_dir, exist_ok=True)

        self._lock = threading.Lock()
        self._audit_log: List[DecisionAuditEntry] = []
        self._violation_counts: Dict[str, int] = {}

        # Canary configuration
        self._canary_enabled = False
        self._canary_policy_name: Optional[str] = None
        self._canary_percentage = 0.0
        self._canary_counter = 0

        # State tracking
        self._machine_wip: Dict[str, List[str]] = {}  # machine_id -> [job_ids]
        self._quality_holds: set = set()  # job_ids with quality hold
        self._maintenance_windows: Dict[str, List[tuple]] = {}  # machine_id -> [(start, end)]

        # Callbacks
        self._execution_callback: Optional[Callable[[ScheduleDecision], bool]] = None
        self._violation_callback: Optional[Callable[[ScheduleDecision, List[str]], None]] = None

        logger.info(
            f"Dispatcher initialized (shadow_mode={shadow_mode}, "
            f"baseline={baseline_policy_name})"
        )

    # =========================================================================
    # Configuration
    # =========================================================================

    def set_shadow_mode(self, enabled: bool) -> None:
        """Enable or disable shadow mode."""
        self.shadow_mode = enabled
        logger.info(f"Shadow mode {'enabled' if enabled else 'disabled'}")

    def enable_canary(
        self,
        policy_name: str,
        percentage: float = 0.1
    ) -> None:
        """
        Enable canary deployment for a policy.

        Args:
            policy_name: Policy to route canary traffic to
            percentage: Fraction of jobs to route (0.0-1.0)
        """
        if percentage < 0 or percentage > 1:
            raise ValueError("Canary percentage must be between 0.0 and 1.0")

        # Verify policy exists
        get_policy(policy_name)

        self._canary_enabled = True
        self._canary_policy_name = policy_name
        self._canary_percentage = percentage
        self._canary_counter = 0

        logger.info(
            f"Canary enabled: {percentage*100:.0f}% traffic to '{policy_name}'"
        )

    def disable_canary(self) -> None:
        """Disable canary deployment."""
        self._canary_enabled = False
        self._canary_policy_name = None
        self._canary_percentage = 0.0
        logger.info("Canary disabled")

    def set_execution_callback(
        self,
        callback: Callable[[ScheduleDecision], bool]
    ) -> None:
        """
        Set callback for executing decisions.

        Args:
            callback: Function that executes a decision, returns success
        """
        self._execution_callback = callback

    def set_violation_callback(
        self,
        callback: Callable[[ScheduleDecision, List[str]], None]
    ) -> None:
        """
        Set callback for violation alerts.

        Args:
            callback: Function called with decision and violation list
        """
        self._violation_callback = callback

    # =========================================================================
    # State Management
    # =========================================================================

    def add_quality_hold(self, job_id: str) -> None:
        """Add quality hold for a job."""
        self._quality_holds.add(job_id)
        logger.info(f"Quality hold added for job {job_id}")

    def remove_quality_hold(self, job_id: str) -> None:
        """Remove quality hold for a job."""
        self._quality_holds.discard(job_id)
        logger.info(f"Quality hold removed for job {job_id}")

    def add_maintenance_window(
        self,
        machine_id: str,
        start_time: float,
        end_time: float
    ) -> None:
        """Add maintenance window for a machine."""
        if machine_id not in self._maintenance_windows:
            self._maintenance_windows[machine_id] = []
        self._maintenance_windows[machine_id].append((start_time, end_time))
        logger.info(f"Maintenance window added for {machine_id}: {start_time}-{end_time}")

    def update_machine_wip(self, machine_id: str, job_ids: List[str]) -> None:
        """Update WIP for a machine."""
        self._machine_wip[machine_id] = job_ids

    def job_completed(self, machine_id: str, job_id: str) -> None:
        """Mark a job as completed on a machine."""
        if machine_id in self._machine_wip:
            if job_id in self._machine_wip[machine_id]:
                self._machine_wip[machine_id].remove(job_id)

    # =========================================================================
    # Decision Processing
    # =========================================================================

    def process_decision(
        self,
        decision: ScheduleDecision,
        state: ScheduleState
    ) -> DispatchResult:
        """
        Process a scheduling decision.

        Validates constraints, and either executes or logs (shadow mode).

        Args:
            decision: Scheduling decision to process
            state: Current shop floor state

        Returns:
            DispatchResult with outcome
        """
        decision_id = f"{decision.job_id}-{decision.machine_id}-{int(time.time()*1000)}"

        # 1. Validate constraints
        violations = self._validate(decision, state)

        if violations:
            result = DispatchResult(
                decision_id=decision_id,
                accepted=False,
                violations=violations,
                reason="; ".join(violations)
            )

            # Track violation counts
            with self._lock:
                for v in violations:
                    self._violation_counts[v] = self._violation_counts.get(v, 0) + 1

            # Notify callback
            if self._violation_callback:
                try:
                    self._violation_callback(decision, violations)
                except Exception as e:
                    logger.warning(f"Violation callback error: {e}")

            self._record_audit(decision, result)
            return result

        # 2. Handle shadow mode
        if self.shadow_mode:
            result = DispatchResult(
                decision_id=decision_id,
                accepted=True,
                shadow=True
            )
            logger.debug(f"Shadow decision logged: {decision.job_id} -> {decision.machine_id}")
            self._record_audit(decision, result)
            return result

        # 3. Execute decision
        executed = self._execute(decision)

        result = DispatchResult(
            decision_id=decision_id,
            accepted=True,
            executed=executed
        )

        # Update WIP tracking
        if executed:
            if decision.machine_id not in self._machine_wip:
                self._machine_wip[decision.machine_id] = []
            self._machine_wip[decision.machine_id].append(decision.job_id)

        self._record_audit(decision, result)
        return result

    def process_decisions(
        self,
        decisions: List[ScheduleDecision],
        state: ScheduleState
    ) -> List[DispatchResult]:
        """
        Process multiple scheduling decisions.

        Args:
            decisions: List of decisions to process
            state: Current shop floor state

        Returns:
            List of DispatchResults
        """
        results = []
        for decision in decisions:
            result = self.process_decision(decision, state)
            results.append(result)

            # Update state for subsequent validations
            if result.executed:
                # Job is now assigned, mark as in-progress for next iteration
                for job in state.jobs:
                    if job.job_id == decision.job_id:
                        job.status = JobStatus.IN_PROGRESS
                        break

        return results

    def should_use_canary(self) -> bool:
        """
        Determine if next job should use canary policy.

        Uses deterministic counter-based selection.

        Returns:
            True if canary policy should be used
        """
        if not self._canary_enabled:
            return False

        self._canary_counter += 1
        threshold = int(1.0 / self._canary_percentage) if self._canary_percentage > 0 else 0

        if threshold > 0 and self._canary_counter >= threshold:
            self._canary_counter = 0
            return True

        return False

    def get_active_policy_name(self) -> str:
        """Get the currently active policy name (considering canary)."""
        if self.should_use_canary():
            return self._canary_policy_name
        return self.baseline_policy_name

    # =========================================================================
    # Validation
    # =========================================================================

    def _validate(
        self,
        decision: ScheduleDecision,
        state: ScheduleState
    ) -> List[str]:
        """
        Validate a decision against constraints.

        Args:
            decision: Decision to validate
            state: Current state

        Returns:
            List of violation strings (empty if valid)
        """
        violations = []

        # Find job and machine
        job = next((j for j in state.jobs if j.job_id == decision.job_id), None)
        machine = next((m for m in state.machines if m.machine_id == decision.machine_id), None)

        if not job:
            violations.append(ViolationType.INVALID_JOB.value)
            return violations

        if not machine:
            violations.append(ViolationType.INVALID_MACHINE.value)
            return violations

        # Machine availability
        if machine.status == MachineStatus.OFFLINE:
            violations.append(ViolationType.MACHINE_UNAVAILABLE.value)
        elif machine.status == MachineStatus.MAINTENANCE:
            violations.append(ViolationType.MAINTENANCE_SCHEDULED.value)
        elif machine.status == MachineStatus.BUSY:
            violations.append(ViolationType.MACHINE_BUSY.value)

        # Capability match
        if job.required_machine_types:
            if machine.machine_type not in job.required_machine_types:
                violations.append(ViolationType.CAPABILITY_MISMATCH.value)

        # WIP limit
        current_wip = len(self._machine_wip.get(decision.machine_id, []))
        if current_wip >= self.wip_limit_per_machine:
            violations.append(ViolationType.WIP_LIMIT_EXCEEDED.value)

        # Quality hold
        if decision.job_id in self._quality_holds:
            violations.append(ViolationType.QUALITY_HOLD.value)

        # Maintenance window check
        if decision.machine_id in self._maintenance_windows:
            for start, end in self._maintenance_windows[decision.machine_id]:
                if start <= decision.start_time <= end:
                    violations.append(ViolationType.MAINTENANCE_SCHEDULED.value)
                    break

        return violations

    # =========================================================================
    # Execution
    # =========================================================================

    def _execute(self, decision: ScheduleDecision) -> bool:
        """
        Execute a scheduling decision.

        Args:
            decision: Decision to execute

        Returns:
            True if execution succeeded
        """
        if self._execution_callback:
            try:
                return self._execution_callback(decision)
            except Exception as e:
                logger.error(f"Execution callback failed: {e}")
                return False

        # Default: just log
        logger.info(
            f"Executing decision: {decision.job_id} -> {decision.machine_id} "
            f"at {decision.start_time}"
        )
        return True

    # =========================================================================
    # Audit & Metrics
    # =========================================================================

    def _record_audit(
        self,
        decision: ScheduleDecision,
        result: DispatchResult
    ) -> None:
        """Record decision to audit log."""
        entry = DecisionAuditEntry(
            decision_id=result.decision_id,
            policy_name=decision.policy_name,
            policy_version=decision.policy_version,
            job_id=decision.job_id,
            machine_id=decision.machine_id,
            start_time=decision.start_time,
            result=result
        )

        with self._lock:
            self._audit_log.append(entry)

            # Keep last 10000 entries in memory
            if len(self._audit_log) > 10000:
                self._audit_log = self._audit_log[-10000:]

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit entries."""
        with self._lock:
            entries = self._audit_log[-limit:]
            return [e.to_dict() for e in entries]

    def get_violation_stats(self) -> Dict[str, int]:
        """Get violation counts by type."""
        with self._lock:
            return dict(self._violation_counts)

    def get_acceptance_rate(self, window_size: int = 100) -> float:
        """
        Get decision acceptance rate.

        Args:
            window_size: Number of recent decisions to consider

        Returns:
            Acceptance rate (0.0-1.0)
        """
        with self._lock:
            recent = self._audit_log[-window_size:]
            if not recent:
                return 1.0
            accepted = sum(1 for e in recent if e.result.accepted)
            return accepted / len(recent)

    def save_audit_log(self, filename: Optional[str] = None) -> str:
        """
        Save audit log to file.

        Args:
            filename: Optional filename (default: timestamped)

        Returns:
            Path to saved file
        """
        if not filename:
            filename = f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = os.path.join(self.audit_dir, filename)

        with self._lock:
            entries = [e.to_dict() for e in self._audit_log]

        with open(filepath, 'w') as f:
            json.dump(entries, f, indent=2)

        logger.info(f"Audit log saved to {filepath}")
        return filepath

    def get_status(self) -> Dict[str, Any]:
        """Get dispatcher status."""
        with self._lock:
            return {
                "shadow_mode": self.shadow_mode,
                "baseline_policy": self.baseline_policy_name,
                "canary_enabled": self._canary_enabled,
                "canary_policy": self._canary_policy_name,
                "canary_percentage": self._canary_percentage,
                "wip_limit_per_machine": self.wip_limit_per_machine,
                "total_decisions": len(self._audit_log),
                "acceptance_rate": self.get_acceptance_rate(),
                "violation_counts": dict(self._violation_counts),
                "machines_with_wip": len(self._machine_wip),
                "quality_holds": len(self._quality_holds)
            }


# =============================================================================
# Singleton Instance
# =============================================================================

_dispatcher: Optional[ScheduleDispatcher] = None
_lock = threading.Lock()


def get_dispatcher(
    shadow_mode: bool = False,
    baseline_policy: str = "edd"
) -> ScheduleDispatcher:
    """Get or create dispatcher singleton."""
    global _dispatcher
    with _lock:
        if _dispatcher is None:
            _dispatcher = ScheduleDispatcher(
                shadow_mode=shadow_mode,
                baseline_policy_name=baseline_policy
            )
        return _dispatcher
