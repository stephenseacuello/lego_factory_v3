"""
Scheduling Experiment Runner
=============================
Framework for running and comparing scheduling experiments.

Workflow:
1. IMPLEMENT - Create policy using SchedulingPolicy interface
2. SIMULATE  - Run offline on recorded/synthetic data
3. SHADOW    - Enable shadow mode on live stream
4. CANARY    - Route X% of jobs to new policy
5. PROMOTE   - Make default if stable
6. MONITOR   - Continuous KPI monitoring with auto-rollback

Author: Flask CNC SCADA System
"""

import os
import json
import time
import uuid
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

from services.scheduling.policy_interface import (
    SchedulingPolicy,
    ScheduleState,
    ScheduleDecision,
    Job,
    Machine,
    WIPItem,
    JobStatus,
    MachineStatus,
    get_policy,
    list_policies
)

logger = logging.getLogger(__name__)


@dataclass
class KPIs:
    """Key Performance Indicators for scheduling evaluation."""
    makespan: float = 0.0  # Total time to complete all jobs
    total_tardiness: float = 0.0  # Sum of lateness for late jobs
    max_tardiness: float = 0.0  # Maximum lateness
    num_late_jobs: int = 0
    avg_flow_time: float = 0.0  # Average time in system
    avg_waiting_time: float = 0.0
    machine_utilization: float = 0.0  # Average utilization
    total_setup_time: float = 0.0
    num_changeovers: int = 0
    throughput: float = 0.0  # Jobs per hour

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentConfig:
    """Configuration for a scheduling experiment."""
    experiment_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    policy_name: str = "fifo"
    policy_params: Dict[str, Any] = field(default_factory=dict)
    baseline_policy: str = "edd"  # Compare against this
    dataset: str = "synthetic"  # "recorded_YYYYMM" or "synthetic_<scenario>"
    horizon_hours: float = 24.0
    seed: int = 42
    objective_weights: Dict[str, float] = field(default_factory=lambda: {
        "makespan": 0.2,
        "tardiness": 0.4,
        "changeovers": 0.2,
        "utilization": 0.2
    })

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentResult:
    """Results from a scheduling experiment."""
    experiment_id: str
    policy_name: str
    policy_version: str
    config: ExperimentConfig
    kpis: KPIs
    baseline_kpis: Optional[KPIs] = None
    improvement: Dict[str, float] = field(default_factory=dict)
    decisions: List[Dict] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)
    artifacts_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "config": self.config.to_dict(),
            "kpis": self.kpis.to_dict(),
            "baseline_kpis": self.baseline_kpis.to_dict() if self.baseline_kpis else None,
            "improvement": self.improvement,
            "num_decisions": len(self.decisions),
            "violations": self.violations,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp,
            "artifacts_path": self.artifacts_path
        }


class SchedulingSimulator:
    """
    Discrete-event simulator for scheduling policy evaluation.

    Provides deterministic replay of shop floor scenarios
    for policy comparison.
    """

    def __init__(self, seed: int = 42):
        """
        Initialize simulator.

        Args:
            seed: Random seed for reproducibility
        """
        import random
        self.rng = random.Random(seed)
        self.seed = seed

    def generate_synthetic_state(
        self,
        num_jobs: int = 20,
        num_machines: int = 3,
        machine_types: List[str] = None
    ) -> ScheduleState:
        """
        Generate synthetic shop floor state for testing.

        Args:
            num_jobs: Number of jobs to generate
            num_machines: Number of machines
            machine_types: Types of machines

        Returns:
            ScheduleState with synthetic data
        """
        machine_types = machine_types or ["tinyg", "grbl", "laser"]
        now = time.time()

        # Generate machines
        machines = []
        for i in range(num_machines):
            m_type = machine_types[i % len(machine_types)]
            machines.append(Machine(
                machine_id=f"machine-{i+1:02d}",
                machine_type=m_type,
                status=MachineStatus.AVAILABLE,
                capabilities=[m_type, "standard"],
                utilization_1h=self.rng.uniform(0.3, 0.8),
                utilization_24h=self.rng.uniform(0.4, 0.7),
                oee_score=self.rng.uniform(0.6, 0.9)
            ))

        # Generate jobs
        jobs = []
        for i in range(num_jobs):
            processing_time = self.rng.uniform(5, 60)  # 5-60 minutes
            setup_time = self.rng.uniform(2, 15)
            due_offset = self.rng.uniform(1, 24) * 3600  # 1-24 hours from now

            jobs.append(Job(
                job_id=f"job-{i+1:03d}",
                work_order_id=f"wo-{i+1:03d}",
                part_number=f"part-{self.rng.randint(1, 10):03d}",
                quantity=self.rng.randint(1, 10),
                priority=self.rng.randint(1, 10),
                due_date=now + due_offset,
                release_date=now - self.rng.uniform(0, 3600),  # Released in past hour
                status=JobStatus.PENDING,
                processing_time_min=processing_time,
                setup_time_min=setup_time,
                setup_group=f"group-{self.rng.randint(1, 3)}",
                required_machine_types=[self.rng.choice(machine_types)]
            ))

        return ScheduleState(
            jobs=jobs,
            machines=machines,
            wip=[],
            timestamp=now
        )

    def run(
        self,
        policy: SchedulingPolicy,
        state: ScheduleState,
        horizon_hours: float = 24.0
    ) -> tuple:
        """
        Run simulation with given policy.

        Args:
            policy: Scheduling policy to evaluate
            state: Initial shop floor state
            horizon_hours: Simulation horizon

        Returns:
            Tuple of (KPIs, decisions_list)
        """
        # Simple simulation: assign all pending jobs and calculate KPIs
        decisions = policy.suggest_schedule(state)
        now = state.timestamp

        # Track metrics
        completed_jobs = []
        total_flow_time = 0.0
        total_waiting_time = 0.0
        total_tardiness = 0.0
        max_tardiness = 0.0
        late_count = 0
        changeovers = 0
        total_setup = 0.0

        # Simulate execution (simplified)
        machine_available_at = {m.machine_id: now for m in state.machines}
        machine_last_setup = {m.machine_id: "" for m in state.machines}

        for decision in decisions:
            job = next((j for j in state.jobs if j.job_id == decision.job_id), None)
            if not job:
                continue

            machine_id = decision.machine_id
            start_time = max(machine_available_at[machine_id], decision.start_time)

            # Setup time
            setup_time = 0
            if machine_last_setup[machine_id] != job.setup_group:
                setup_time = job.setup_time_min
                changeovers += 1
                total_setup += setup_time

            # Completion time
            completion_time = start_time + (setup_time + job.processing_time_min) * 60

            # Update machine availability
            machine_available_at[machine_id] = completion_time
            machine_last_setup[machine_id] = job.setup_group

            # Calculate metrics
            flow_time = (completion_time - (job.release_date or now)) / 60
            waiting_time = (start_time - (job.release_date or now)) / 60
            total_flow_time += flow_time
            total_waiting_time += max(0, waiting_time)

            # Tardiness
            if job.due_date:
                tardiness = max(0, (completion_time - job.due_date) / 60)
                total_tardiness += tardiness
                max_tardiness = max(max_tardiness, tardiness)
                if tardiness > 0:
                    late_count += 1

            completed_jobs.append({
                "job_id": job.job_id,
                "start": start_time,
                "end": completion_time,
                "tardiness": tardiness if job.due_date else 0
            })

        # Calculate final KPIs
        num_completed = len(completed_jobs)
        makespan = (max(j["end"] for j in completed_jobs) - now) / 60 if completed_jobs else 0

        # Machine utilization
        horizon_seconds = horizon_hours * 3600
        total_processing = sum(
            (j.processing_time_min + j.setup_time_min) * 60
            for j in state.jobs if j.job_id in [d.job_id for d in decisions]
        )
        utilization = total_processing / (len(state.machines) * horizon_seconds) if state.machines else 0

        kpis = KPIs(
            makespan=makespan,
            total_tardiness=total_tardiness,
            max_tardiness=max_tardiness,
            num_late_jobs=late_count,
            avg_flow_time=total_flow_time / num_completed if num_completed else 0,
            avg_waiting_time=total_waiting_time / num_completed if num_completed else 0,
            machine_utilization=min(1.0, utilization),
            total_setup_time=total_setup,
            num_changeovers=changeovers,
            throughput=num_completed / horizon_hours if horizon_hours > 0 else 0
        )

        return kpis, [d.to_dict() for d in decisions]


class ExperimentRunner:
    """
    CLI/REST interface for running policy experiments.

    Provides tools for:
    - Running single experiments
    - Comparing multiple policies
    - A/B testing
    - Artifact management
    """

    def __init__(self, artifacts_dir: str = None):
        """
        Initialize experiment runner.

        Args:
            artifacts_dir: Directory for storing experiment artifacts
        """
        self.artifacts_dir = artifacts_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "experiments"
        )
        os.makedirs(self.artifacts_dir, exist_ok=True)

        self._experiments: Dict[str, ExperimentResult] = {}
        self._lock = threading.Lock()

        logger.info(f"Experiment Runner initialized (artifacts: {self.artifacts_dir})")

    def run_experiment(self, config: ExperimentConfig) -> ExperimentResult:
        """
        Run a single scheduling experiment.

        Args:
            config: Experiment configuration

        Returns:
            ExperimentResult with KPIs and comparison
        """
        start_time = time.time()
        logger.info(f"Running experiment {config.experiment_id}: {config.policy_name}")

        # Load or generate data
        simulator = SchedulingSimulator(seed=config.seed)
        state = simulator.generate_synthetic_state(
            num_jobs=30,
            num_machines=3
        )

        # Load policy
        policy = get_policy(config.policy_name, **config.policy_params)

        # Run simulation
        kpis, decisions = simulator.run(policy, state, config.horizon_hours)

        # Run baseline for comparison
        baseline_kpis = None
        improvement = {}
        if config.baseline_policy:
            baseline_policy = get_policy(config.baseline_policy)
            baseline_kpis, _ = simulator.run(baseline_policy, state, config.horizon_hours)

            # Calculate improvement (positive = better)
            if baseline_kpis.makespan > 0:
                improvement["makespan"] = (baseline_kpis.makespan - kpis.makespan) / baseline_kpis.makespan
            if baseline_kpis.total_tardiness > 0:
                improvement["tardiness"] = (baseline_kpis.total_tardiness - kpis.total_tardiness) / baseline_kpis.total_tardiness
            if baseline_kpis.num_changeovers > 0:
                improvement["changeovers"] = (baseline_kpis.num_changeovers - kpis.num_changeovers) / baseline_kpis.num_changeovers
            if baseline_kpis.machine_utilization > 0:
                improvement["utilization"] = (kpis.machine_utilization - baseline_kpis.machine_utilization) / baseline_kpis.machine_utilization

        # Create result
        result = ExperimentResult(
            experiment_id=config.experiment_id,
            policy_name=policy.name,
            policy_version=policy.version,
            config=config,
            kpis=kpis,
            baseline_kpis=baseline_kpis,
            improvement=improvement,
            decisions=decisions,
            violations=[],
            duration_seconds=time.time() - start_time
        )

        # Save artifacts
        result.artifacts_path = self._save_artifacts(result)

        # Store result
        with self._lock:
            self._experiments[result.experiment_id] = result

        logger.info(f"Experiment {config.experiment_id} completed in {result.duration_seconds:.2f}s")
        return result

    def compare_policies(
        self,
        policy_names: List[str],
        config: Optional[ExperimentConfig] = None
    ) -> Dict[str, ExperimentResult]:
        """
        Compare multiple policies on same dataset.

        Args:
            policy_names: List of policy names to compare
            config: Base configuration (policy_name will be overridden)

        Returns:
            Dict of policy_name -> ExperimentResult
        """
        config = config or ExperimentConfig()
        results = {}

        for name in policy_names:
            policy_config = ExperimentConfig(
                experiment_id=f"{config.experiment_id}-{name}",
                policy_name=name,
                policy_params=config.policy_params,
                baseline_policy=config.baseline_policy,
                dataset=config.dataset,
                horizon_hours=config.horizon_hours,
                seed=config.seed,
                objective_weights=config.objective_weights
            )
            results[name] = self.run_experiment(policy_config)

        return results

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Get experiment result by ID."""
        with self._lock:
            return self._experiments.get(experiment_id)

    def list_experiments(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent experiments."""
        with self._lock:
            experiments = sorted(
                self._experiments.values(),
                key=lambda x: x.timestamp,
                reverse=True
            )[:limit]
            return [e.to_dict() for e in experiments]

    def _save_artifacts(self, result: ExperimentResult) -> str:
        """Save experiment artifacts to disk."""
        exp_dir = os.path.join(
            self.artifacts_dir,
            datetime.now().strftime("%Y%m%d"),
            result.experiment_id
        )
        os.makedirs(exp_dir, exist_ok=True)

        # Save result JSON
        result_path = os.path.join(exp_dir, "result.json")
        with open(result_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

        # Save decisions
        decisions_path = os.path.join(exp_dir, "decisions.json")
        with open(decisions_path, 'w') as f:
            json.dump(result.decisions, f, indent=2)

        return exp_dir


# =============================================================================
# Singleton Instance
# =============================================================================

_experiment_runner: Optional[ExperimentRunner] = None
_lock = threading.Lock()


def get_experiment_runner() -> ExperimentRunner:
    """Get or create experiment runner singleton."""
    global _experiment_runner
    with _lock:
        if _experiment_runner is None:
            _experiment_runner = ExperimentRunner()
        return _experiment_runner
