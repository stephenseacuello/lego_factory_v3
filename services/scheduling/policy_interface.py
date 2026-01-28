"""
Scheduling Policy Interface
============================
Standard API for all scheduling policies.

This module defines the canonical interface for scheduling algorithms,
enabling rapid experimentation from algorithm idea to production.

Workflow: Implement → Simulate → Shadow → Canary → Promote → Monitor

Author: Flask CNC SCADA System
"""

import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from enum import Enum


class JobStatus(str, Enum):
    """Job status in the scheduling system."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    QUALITY_HOLD = "quality_hold"


class MachineStatus(str, Enum):
    """Machine availability status."""
    AVAILABLE = "available"
    BUSY = "busy"
    SETUP = "setup"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"
    ALARM = "alarm"


@dataclass
class Job:
    """Job to be scheduled."""
    job_id: str
    work_order_id: str
    part_number: str
    quantity: int = 1
    priority: int = 5  # 1=highest, 10=lowest
    due_date: Optional[float] = None  # Unix timestamp
    release_date: Optional[float] = None  # Earliest start
    status: JobStatus = JobStatus.PENDING

    # Processing requirements
    processing_time_min: float = 0.0
    setup_time_min: float = 0.0
    setup_group: str = ""  # For sequence-dependent setup
    required_machine_types: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)

    # Operations (for multi-operation jobs)
    operations: List[Dict[str, Any]] = field(default_factory=list)
    current_operation: int = 0

    # Tracking
    assigned_machine: Optional[str] = None
    scheduled_start: Optional[float] = None
    actual_start: Optional[float] = None
    actual_end: Optional[float] = None

    @property
    def remaining_time(self) -> float:
        """Estimated remaining processing time."""
        return self.processing_time_min

    @property
    def slack_time(self) -> Optional[float]:
        """Time until due date minus remaining processing time."""
        if self.due_date is None:
            return None
        now = datetime.now().timestamp()
        return (self.due_date - now) / 60 - self.remaining_time

    @property
    def is_late(self) -> bool:
        """Check if job is past due date."""
        if self.due_date is None:
            return False
        return datetime.now().timestamp() > self.due_date


@dataclass
class Machine:
    """Machine available for scheduling."""
    machine_id: str
    machine_type: str  # "tinyg", "grbl", "laser"
    status: MachineStatus = MachineStatus.AVAILABLE
    capabilities: List[str] = field(default_factory=list)

    # Current state
    current_job: Optional[str] = None
    queue_depth: int = 0
    available_at: Optional[float] = None  # When it will be free

    # Performance metrics
    utilization_1h: float = 0.0
    utilization_24h: float = 0.0
    oee_score: float = 0.0
    mtbf_hours: float = 100.0
    mttr_hours: float = 1.0

    # Setup tracking
    current_setup_group: str = ""
    setup_matrix: Dict[str, float] = field(default_factory=dict)

    def can_process(self, job: Job) -> bool:
        """Check if machine can process job."""
        if job.required_machine_types and self.machine_type not in job.required_machine_types:
            return False
        if job.required_capabilities:
            return all(cap in self.capabilities for cap in job.required_capabilities)
        return True

    def get_setup_time(self, job: Job) -> float:
        """Get setup time for job considering current setup."""
        if job.setup_group == self.current_setup_group:
            return 0.0
        return self.setup_matrix.get(job.setup_group, job.setup_time_min)


@dataclass
class WIPItem:
    """Work in progress item."""
    job_id: str
    machine_id: str
    operation_id: str
    started_at: float
    estimated_completion: float
    progress_percent: float = 0.0


@dataclass
class Calendar:
    """Shift/maintenance calendar."""
    calendar_id: str
    name: str
    shifts: List[Dict[str, Any]] = field(default_factory=list)
    breaks: List[Dict[str, Any]] = field(default_factory=list)
    maintenance_windows: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ScheduleConstraints:
    """Hard constraints for scheduling."""
    max_wip_per_machine: int = 5
    max_total_wip: int = 50
    sequence_dependent_setups: bool = True
    respect_due_dates: bool = True
    respect_release_dates: bool = True
    maintenance_window_hard: bool = True


@dataclass
class ScheduleState:
    """
    Canonical state for scheduling decisions.

    Represents the complete shop floor state at a point in time,
    used as input to all scheduling policies.
    """
    jobs: List[Job]
    machines: List[Machine]
    wip: List[WIPItem]
    calendars: Dict[str, Calendar] = field(default_factory=dict)
    setup_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    constraints: ScheduleConstraints = field(default_factory=ScheduleConstraints)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    @property
    def pending_jobs(self) -> List[Job]:
        """Get jobs waiting to be scheduled."""
        return [j for j in self.jobs if j.status == JobStatus.PENDING]

    @property
    def available_machines(self) -> List[Machine]:
        """Get machines available for new jobs."""
        return [m for m in self.machines if m.status == MachineStatus.AVAILABLE]

    @property
    def total_wip(self) -> int:
        """Total work in progress count."""
        return len(self.wip)


@dataclass
class ScheduleDecision:
    """
    Single scheduling decision.

    Represents assignment of a job to a machine at a specific time.
    """
    decision_id: str
    job_id: str
    machine_id: str
    start_time: float
    priority: int = 5

    # Policy metadata
    policy_name: str = ""
    policy_version: str = ""
    confidence: float = 1.0

    # Explainability
    features_used: Dict[str, float] = field(default_factory=dict)
    reasoning: str = ""

    # Tracking
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    executed: bool = False
    shadow_mode: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "job_id": self.job_id,
            "machine_id": self.machine_id,
            "start_time": self.start_time,
            "priority": self.priority,
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "confidence": self.confidence,
            "features_used": self.features_used,
            "reasoning": self.reasoning,
            "created_at": self.created_at,
            "executed": self.executed,
            "shadow_mode": self.shadow_mode
        }


class SchedulingPolicy(ABC):
    """
    Base interface for all scheduling policies.

    All scheduling algorithms must implement this interface to be
    compatible with the experimentation framework.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Policy name (e.g., 'FIFO', 'SPT', 'EDD')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Policy version (semver format)."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of the policy."""
        return ""

    @abstractmethod
    def suggest_schedule(self, state: ScheduleState) -> List[ScheduleDecision]:
        """
        Generate scheduling decisions for current state.

        Args:
            state: Current shop floor state

        Returns:
            List of scheduling decisions (job assignments)
        """
        ...

    def get_metadata(self) -> Dict[str, Any]:
        """Get policy metadata for tracking."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "git_sha": self._get_git_sha()
        }

    def _get_git_sha(self) -> str:
        """Get current git commit SHA."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    def _generate_decision_id(self) -> str:
        """Generate unique decision ID."""
        import uuid
        return f"{self.name}-{uuid.uuid4().hex[:8]}"


# =============================================================================
# Policy Registration
# =============================================================================

_registered_policies: Dict[str, type] = {}


def register_policy(name: str):
    """Decorator to register a policy class."""
    def decorator(cls):
        _registered_policies[name] = cls
        return cls
    return decorator


def get_policy(name: str, **kwargs) -> SchedulingPolicy:
    """Get policy instance by name."""
    if name not in _registered_policies:
        raise ValueError(f"Unknown policy: {name}. Available: {list(_registered_policies.keys())}")
    return _registered_policies[name](**kwargs)


def list_policies() -> List[str]:
    """List all registered policy names."""
    return list(_registered_policies.keys())
