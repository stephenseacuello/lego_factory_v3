"""
Scheduling Feature Store
=========================
Versioned feature store for reproducible scheduling experiments.

Provides canonical feature computation for:
- Job-level features
- Machine-level features
- System-level features

All features are versioned for reproducibility across experiments.

Author: Flask CNC SCADA System
"""

import time
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import statistics

from services.scheduling.policy_interface import (
    ScheduleState,
    Job,
    Machine,
    WIPItem,
    JobStatus,
    MachineStatus
)

logger = logging.getLogger(__name__)

# Feature store version - increment when feature definitions change
FEATURE_VERSION = "1.0.0"


@dataclass
class FeatureVector:
    """
    Complete feature vector for scheduling decisions.

    Contains all computed features organized by category.
    """
    version: str = FEATURE_VERSION
    timestamp: float = field(default_factory=time.time)

    # Job features (keyed by job_id)
    job_features: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Machine features (keyed by machine_id)
    machine_features: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # System-wide features
    system_features: Dict[str, float] = field(default_factory=dict)

    # Feature hash for reproducibility verification
    feature_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "job_features": self.job_features,
            "machine_features": self.machine_features,
            "system_features": self.system_features,
            "feature_hash": self.feature_hash
        }

    def get_job_feature(self, job_id: str, feature: str) -> Optional[float]:
        """Get a specific job feature."""
        return self.job_features.get(job_id, {}).get(feature)

    def get_machine_feature(self, machine_id: str, feature: str) -> Optional[float]:
        """Get a specific machine feature."""
        return self.machine_features.get(machine_id, {}).get(feature)


class SchedulingFeatureStore:
    """
    Versioned feature store for reproducible experiments.

    Computes canonical features from ScheduleState for use by
    scheduling policies and ML models.
    """

    # =========================================================================
    # Feature Definitions
    # =========================================================================

    # Job-level features
    JOB_FEATURES = [
        "processing_time",      # Estimated processing time (minutes)
        "setup_time",           # Setup/changeover time (minutes)
        "due_date_offset",      # Time until due date (minutes, negative if past)
        "slack_time",           # Due date - (now + processing time)
        "priority",             # Job priority (1-10)
        "quantity",             # Number of parts
        "remaining_ops",        # Remaining operations count
        "total_work_content",   # Total time for all remaining ops
        "critical_ratio",       # (Due - Now) / Processing Time
        "wait_time",            # Time since release (minutes)
        "is_late",              # 1 if already past due, 0 otherwise
        "lateness",             # How late already (minutes, 0 if not late)
        "setup_group_encoded",  # Setup group as numeric
        "urgency_score"         # Composite urgency metric
    ]

    # Machine-level features
    MACHINE_FEATURES = [
        "utilization_1h",       # Utilization in last hour
        "utilization_24h",      # Utilization in last 24 hours
        "queue_depth",          # Number of jobs in queue
        "oee_score",            # Overall Equipment Effectiveness
        "mtbf",                 # Mean Time Between Failures (hours)
        "mttr",                 # Mean Time To Repair (hours)
        "availability",         # Current availability (0/1)
        "capability_match",     # Number of matching capabilities
        "current_load",         # Current processing load
        "changeover_cost",      # Expected changeover cost
        "last_setup_group"      # Last setup group (encoded)
    ]

    # System-wide features
    SYSTEM_FEATURES = [
        "wip_level",            # Total WIP items
        "wip_ratio",            # WIP / Total capacity
        "bottleneck_utilization",  # Utilization of bottleneck machine
        "shift_remaining",      # Minutes remaining in shift
        "jobs_due_today",       # Jobs due within 24h
        "jobs_overdue",         # Jobs already past due
        "total_tardiness",      # Sum of all tardiness
        "avg_machine_util",     # Average machine utilization
        "changeover_cost_total",# Total expected changeovers
        "system_load",          # Overall system load
        "queue_imbalance"       # Std dev of queue depths
    ]

    def __init__(self, shift_duration_hours: float = 8.0):
        """
        Initialize feature store.

        Args:
            shift_duration_hours: Standard shift duration for calculations
        """
        self.shift_duration_hours = shift_duration_hours
        self._setup_group_map: Dict[str, int] = {}
        self._next_setup_code = 1

        logger.info(f"FeatureStore initialized (version={FEATURE_VERSION})")

    def get_version(self) -> str:
        """Return feature schema version for reproducibility."""
        return FEATURE_VERSION

    # =========================================================================
    # Feature Computation
    # =========================================================================

    def compute_features(self, state: ScheduleState) -> FeatureVector:
        """
        Compute all features from current state.

        Args:
            state: Current shop floor state

        Returns:
            FeatureVector with all computed features
        """
        now = state.timestamp

        features = FeatureVector(timestamp=now)

        # Compute job features
        for job in state.jobs:
            features.job_features[job.job_id] = self._compute_job_features(job, now)

        # Compute machine features
        for machine in state.machines:
            features.machine_features[machine.machine_id] = self._compute_machine_features(
                machine, state, now
            )

        # Compute system features
        features.system_features = self._compute_system_features(state, now)

        # Compute hash for reproducibility verification
        features.feature_hash = self._compute_hash(features)

        return features

    def _compute_job_features(self, job: Job, now: float) -> Dict[str, float]:
        """Compute features for a single job."""
        features = {}

        # Basic attributes
        features["processing_time"] = job.processing_time_min
        features["setup_time"] = job.setup_time_min
        features["priority"] = float(job.priority)
        features["quantity"] = float(job.quantity)

        # Due date features
        if job.due_date:
            due_offset = (job.due_date - now) / 60  # minutes
            features["due_date_offset"] = due_offset
            features["slack_time"] = due_offset - job.processing_time_min
            features["is_late"] = 1.0 if due_offset < 0 else 0.0
            features["lateness"] = max(0, -due_offset)

            # Critical ratio: (Due - Now) / Processing Time
            if job.processing_time_min > 0:
                features["critical_ratio"] = due_offset / job.processing_time_min
            else:
                features["critical_ratio"] = float('inf') if due_offset > 0 else 0
        else:
            features["due_date_offset"] = float('inf')
            features["slack_time"] = float('inf')
            features["is_late"] = 0.0
            features["lateness"] = 0.0
            features["critical_ratio"] = float('inf')

        # Wait time since release
        if job.release_date:
            features["wait_time"] = (now - job.release_date) / 60
        else:
            features["wait_time"] = 0.0

        # Remaining operations (simplified: assume 1 if not specified)
        features["remaining_ops"] = 1.0
        features["total_work_content"] = job.processing_time_min

        # Setup group encoding
        if job.setup_group:
            if job.setup_group not in self._setup_group_map:
                self._setup_group_map[job.setup_group] = self._next_setup_code
                self._next_setup_code += 1
            features["setup_group_encoded"] = float(self._setup_group_map[job.setup_group])
        else:
            features["setup_group_encoded"] = 0.0

        # Urgency score: composite metric
        # Higher priority, lower slack, higher lateness = higher urgency
        urgency = (
            job.priority * 2.0 +
            (10.0 - min(10.0, features["slack_time"] / 60)) +  # Hours of slack
            features["lateness"] / 60 * 5.0  # Hours late, weighted
        )
        features["urgency_score"] = urgency

        return features

    def _compute_machine_features(
        self,
        machine: Machine,
        state: ScheduleState,
        now: float
    ) -> Dict[str, float]:
        """Compute features for a single machine."""
        features = {}

        # Utilization
        features["utilization_1h"] = machine.utilization_1h
        features["utilization_24h"] = machine.utilization_24h

        # Queue depth: count pending jobs for this machine type
        queue = [
            j for j in state.jobs
            if j.status == JobStatus.PENDING
            and (not j.required_machine_types or machine.machine_type in j.required_machine_types)
        ]
        features["queue_depth"] = float(len(queue))

        # OEE and reliability
        features["oee_score"] = machine.oee_score
        features["mtbf"] = machine.mtbf
        features["mttr"] = machine.mttr

        # Availability
        features["availability"] = 1.0 if machine.status == MachineStatus.AVAILABLE else 0.0

        # Capability match: how many capabilities this machine has
        features["capability_match"] = float(len(machine.capabilities))

        # Current load: WIP items on this machine
        wip_count = sum(1 for w in state.wip if w.machine_id == machine.machine_id)
        features["current_load"] = float(wip_count)

        # Changeover cost estimate (simplified)
        features["changeover_cost"] = 0.0  # Would need last job info

        # Last setup group (would need state tracking)
        features["last_setup_group"] = 0.0

        return features

    def _compute_system_features(self, state: ScheduleState, now: float) -> Dict[str, float]:
        """Compute system-wide features."""
        features = {}

        # WIP level
        features["wip_level"] = float(len(state.wip))

        # Total capacity estimate
        total_capacity = len(state.machines) * 5  # Assume 5 jobs per machine max
        features["wip_ratio"] = len(state.wip) / total_capacity if total_capacity > 0 else 0

        # Bottleneck utilization (highest utilized machine)
        if state.machines:
            utilizations = [m.utilization_1h for m in state.machines]
            features["bottleneck_utilization"] = max(utilizations)
            features["avg_machine_util"] = statistics.mean(utilizations)
        else:
            features["bottleneck_utilization"] = 0.0
            features["avg_machine_util"] = 0.0

        # Shift remaining (simplified: assume 8-hour shift starting at midnight)
        hour_of_day = (now % 86400) / 3600
        shift_end = 8.0  # 8 AM
        if hour_of_day < shift_end:
            shift_remaining = (shift_end - hour_of_day) * 60
        else:
            shift_remaining = self.shift_duration_hours * 60
        features["shift_remaining"] = shift_remaining

        # Jobs due analysis
        jobs_due_24h = 0
        jobs_overdue = 0
        total_tardiness = 0.0

        for job in state.jobs:
            if job.due_date and job.status == JobStatus.PENDING:
                time_to_due = (job.due_date - now) / 3600  # hours
                if time_to_due < 24:
                    jobs_due_24h += 1
                if time_to_due < 0:
                    jobs_overdue += 1
                    total_tardiness += abs(time_to_due) * 60  # minutes

        features["jobs_due_today"] = float(jobs_due_24h)
        features["jobs_overdue"] = float(jobs_overdue)
        features["total_tardiness"] = total_tardiness

        # System load
        pending_jobs = sum(1 for j in state.jobs if j.status == JobStatus.PENDING)
        features["system_load"] = pending_jobs / len(state.machines) if state.machines else 0

        # Queue imbalance (std dev of queue depths)
        if state.machines:
            queue_depths = []
            for machine in state.machines:
                queue = [
                    j for j in state.jobs
                    if j.status == JobStatus.PENDING
                    and (not j.required_machine_types or machine.machine_type in j.required_machine_types)
                ]
                queue_depths.append(len(queue))
            features["queue_imbalance"] = statistics.stdev(queue_depths) if len(queue_depths) > 1 else 0.0
        else:
            features["queue_imbalance"] = 0.0

        # Changeover cost total (would need more context)
        features["changeover_cost_total"] = 0.0

        return features

    def _compute_hash(self, features: FeatureVector) -> str:
        """Compute hash of feature vector for reproducibility."""
        # Create deterministic string representation
        content = f"v{features.version}:"
        content += str(sorted(features.system_features.items()))
        content += str(sorted(features.job_features.items()))
        content += str(sorted(features.machine_features.items()))

        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # =========================================================================
    # Feature Access
    # =========================================================================

    def get_job_ranking_features(
        self,
        features: FeatureVector,
        job_ids: List[str]
    ) -> Dict[str, List[float]]:
        """
        Get features suitable for job ranking/sorting.

        Args:
            features: Computed feature vector
            job_ids: List of job IDs to include

        Returns:
            Dict of feature_name -> [values for each job]
        """
        result = {f: [] for f in self.JOB_FEATURES}

        for job_id in job_ids:
            job_features = features.job_features.get(job_id, {})
            for f in self.JOB_FEATURES:
                result[f].append(job_features.get(f, 0.0))

        return result

    def get_machine_assignment_features(
        self,
        features: FeatureVector,
        job_id: str,
        machine_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Get features for job-machine assignment decisions.

        Args:
            features: Computed feature vector
            job_id: Job to assign
            machine_ids: Candidate machines

        Returns:
            Dict with job features and machine features for candidates
        """
        job_features = features.job_features.get(job_id, {})

        machine_candidates = []
        for mid in machine_ids:
            mf = features.machine_features.get(mid, {})
            machine_candidates.append({
                "machine_id": mid,
                "features": mf
            })

        return {
            "job_id": job_id,
            "job_features": job_features,
            "machine_candidates": machine_candidates,
            "system_features": features.system_features
        }

    def get_feature_names(self) -> Dict[str, List[str]]:
        """Get all feature names by category."""
        return {
            "job": self.JOB_FEATURES,
            "machine": self.MACHINE_FEATURES,
            "system": self.SYSTEM_FEATURES
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_feature_store: Optional[SchedulingFeatureStore] = None


def get_feature_store() -> SchedulingFeatureStore:
    """Get or create feature store singleton."""
    global _feature_store
    if _feature_store is None:
        _feature_store = SchedulingFeatureStore()
    return _feature_store
