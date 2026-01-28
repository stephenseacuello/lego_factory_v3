"""
Scheduling Package for Flask CNC SCADA
======================================
Unified scheduling interface supporting all 9 algorithms plus
experimentation framework for policy development and testing.

Algorithms:
- FIFO: First In First Out
- EDD: Earliest Due Date
- SPT: Shortest Processing Time
- CR: Critical Ratio
- WSPT: Weighted Shortest Processing Time
- SetupMin: Minimize Setup/Changeover Time
- Genetic: Genetic Algorithm (metaheuristic)
- SA: Simulated Annealing (metaheuristic)
- ORTools: Google OR-Tools CP-SAT Solver

Experimentation Framework Workflow:
1. IMPLEMENT - Create policy using SchedulingPolicy interface
2. SIMULATE  - Run offline on recorded/synthetic data
3. SHADOW    - Enable shadow mode on live stream
4. CANARY    - Route X% of jobs to new policy
5. PROMOTE   - Make default if stable
6. MONITOR   - Continuous KPI monitoring with auto-rollback

Author: Flask CNC SCADA System
"""

# Unified scheduler (existing)
from services.scheduling.unified_scheduler import (
    UnifiedScheduler,
    SchedulingAlgorithm,
    ScheduleRequest,
    ScheduleJob,
    ScheduleMachine,
    ScheduleResponse,
    get_unified_scheduler,
)
from services.scheduling.algorithm_registry import (
    AlgorithmRegistry,
    AlgorithmInfo,
    get_algorithm_registry,
)

# Policy-based experimentation framework
from services.scheduling.policy_interface import (
    SchedulingPolicy,
    ScheduleState,
    ScheduleDecision,
    Job,
    Machine,
    WIPItem,
    JobStatus,
    MachineStatus,
    ScheduleConstraints,
    register_policy,
    get_policy,
    list_policies
)

from services.scheduling.experiment_runner import (
    ExperimentRunner,
    ExperimentConfig,
    ExperimentResult,
    KPIs,
    SchedulingSimulator,
    get_experiment_runner
)

# Import policies to register them
from services.scheduling.policies import (
    FIFOPolicy,
    SPTPolicy,
    EDDPolicy
)

__all__ = [
    # Unified scheduler
    "UnifiedScheduler",
    "SchedulingAlgorithm",
    "ScheduleRequest",
    "ScheduleJob",
    "ScheduleMachine",
    "ScheduleResponse",
    "get_unified_scheduler",
    "AlgorithmRegistry",
    "AlgorithmInfo",
    "get_algorithm_registry",

    # Policy interface
    "SchedulingPolicy",
    "ScheduleState",
    "ScheduleDecision",
    "Job",
    "Machine",
    "WIPItem",
    "JobStatus",
    "MachineStatus",
    "ScheduleConstraints",
    "register_policy",
    "get_policy",
    "list_policies",

    # Experiment framework
    "ExperimentRunner",
    "ExperimentConfig",
    "ExperimentResult",
    "KPIs",
    "SchedulingSimulator",
    "get_experiment_runner",

    # Built-in policies
    "FIFOPolicy",
    "SPTPolicy",
    "EDDPolicy"
]
