"""
Advanced Scheduling Module
==========================

LegoMCP PhD-Level Manufacturing Platform
Part of the Advanced Scheduling Research (Phase 2)

This module provides world-class production scheduling capabilities using
multiple optimization approaches. Manufacturing scheduling is NP-hard,
requiring sophisticated algorithms for real-world performance.

Scheduling Problem Types:
-------------------------

1. **Job Shop Scheduling** (JSP):
   - Each job has ordered sequence of operations
   - Each operation requires specific machine
   - Classic manufacturing scheduling problem

2. **Flexible Job Shop** (FJSP):
   - Operations can run on alternative machines
   - Machine selection adds complexity
   - More realistic for modern manufacturing

3. **Flow Shop**:
   - All jobs follow same machine sequence
   - Common in assembly lines
   - Special case of job shop

4. **Resource-Constrained Project Scheduling** (RCPSP):
   - Limited resources shared across projects
   - Complex precedence constraints
   - Extensions: multi-mode, multi-skill

Optimization Approaches:
------------------------

1. **Constraint Programming (CP-SAT)**:
   - Google OR-Tools solver
   - Optimal for small/medium problems
   - Handles complex constraints naturally
   - Best for: Feasibility, exact solutions

2. **Multi-Objective (NSGA-II/III)**:
   - Evolutionary algorithm
   - Pareto-optimal solutions
   - Multiple conflicting objectives
   - Best for: Trade-off analysis

3. **Reinforcement Learning (RL)**:
   - Learns dispatching policy from experience
   - Adapts to changing conditions
   - Real-time decision making
   - Best for: Dynamic environments

4. **Greedy/Priority Dispatching**:
   - Fast heuristic approaches
   - SPT, EDD, FIFO, etc.
   - Good baseline solutions
   - Best for: Quick estimates

Scheduling Objectives:
----------------------
- **Makespan**: Total completion time
- **Tardiness**: Lateness penalties
- **Energy**: Power consumption
- **Quality Risk**: FMEA-based risk score
- **Throughput**: Units per time
- **Margin**: Profitability

Constraint Types:
-----------------
- **Precedence**: Operation ordering
- **Resource Capacity**: Machine limits
- **Time Windows**: Due dates, release times
- **Setup Times**: Changeover matrices
- **Alternative Resources**: Machine flexibility
- **Maintenance Windows**: Downtime slots
- **Skill Requirements**: Operator capabilities
- **Calendar**: Working hours, shifts

Example Usage:
--------------
    from services.scheduling import (
        SchedulerFactory,
        SchedulerType,
        SchedulingProblem,
        Job,
        Operation,
        Machine,
    )

    # Define problem
    machines = [Machine(id="M1"), Machine(id="M2")]
    jobs = [
        Job(id="J1", operations=[
            Operation(id="O1", machine_id="M1", duration=10),
            Operation(id="O2", machine_id="M2", duration=5),
        ]),
        Job(id="J2", operations=[
            Operation(id="O3", machine_id="M2", duration=8),
            Operation(id="O4", machine_id="M1", duration=7),
        ]),
    ]

    problem = SchedulingProblem(jobs=jobs, machines=machines)

    # Solve with different approaches
    factory = SchedulerFactory()

    # Optimal solution with CP-SAT
    cp_scheduler = factory.create(SchedulerType.CP_SAT)
    cp_schedule = cp_scheduler.solve(problem, time_limit=60)

    # Multi-objective with NSGA-II
    nsga_scheduler = factory.create(SchedulerType.NSGA2)
    pareto_front = nsga_scheduler.solve(problem, generations=100)

    # Real-time dispatching with RL
    rl_dispatcher = factory.create(SchedulerType.RL)
    next_operation = rl_dispatcher.dispatch(current_state)

Research Contributions:
-----------------------
- Quantum-classical hybrid scheduling (quantum/)
- Novel RL architectures for dispatching
- NSGA-III with sustainability objectives
- Hierarchical scheduling decomposition

References:
-----------
- Pinedo, M. (2016). Scheduling: Theory, Algorithms, and Systems
- Deb, K. et al. (2002). A Fast and Elitist Multiobjective Genetic Algorithm
- Mnih, V. et al. (2015). Human-level control through deep reinforcement learning
- Laborie, P. et al. (2018). IBM ILOG CP Optimizer for Scheduling

Author: LegoMCP Team
Version: 2.0.0
"""

# Objectives
from .objectives import (
    ObjectiveSet,
    SchedulingObjective,
    ObjectiveWeight,
    ObjectiveDirection,
    ObjectiveCalculator,
)

# Constraints
from .constraints import (
    SchedulingConstraint,
    ConstraintType,
    ConstraintPriority,
    ConstraintSet,
    ConstraintBuilder,
    PrecedenceConstraint,
    ResourceCapacityConstraint,
    TimeWindowConstraint,
    SetupTimeConstraint,
    SetupTimeMatrix,
    AlternativeMachineConstraint,
    MaintenanceWindowConstraint,
    SkillRequirementConstraint,
    CalendarConstraint,
    BatchConstraint,
)

# Core Scheduling
from .scheduler_factory import (
    SchedulerFactory,
    SchedulerType,
    ScheduleStatus,
    BaseScheduler,
    Schedule,
    ScheduledOperation,
    SchedulingProblem,
    Job,
    Operation,
    Machine,
    GreedyScheduler,
    PriorityDispatcher,
)

# Constraint Programming
from .cp_scheduler import (
    CPSATScheduler,
    CPSATConfig,
    CPSATSchedulerWithSetups,
    FlexibleJobShopScheduler,
)

# Multi-Objective Optimization
from .nsga2_scheduler import (
    NSGA2Scheduler,
    NSGA3Scheduler,
    NSGA2Config,
    ParetoFront,
    ParetoSolution,
)

# Reinforcement Learning
from .rl_dispatcher import (
    RLDispatcher,
    RLDispatchScheduler,
    RLConfig,
    DispatchRule,
    DispatchState,
    Experience,
    ReplayBuffer,
)

# Quantum Scheduling (experimental)
from .quantum import (
    QAOAScheduler,
    VQEScheduler,
    SimulatedQuantum,
)

# Advanced RL
from .advanced_rl import (
    PPOScheduler,
    SACScheduler,
    TD3Scheduler,
    HierarchicalScheduler,
)

__all__ = [
    # Objectives
    "ObjectiveSet",
    "SchedulingObjective",
    "ObjectiveWeight",
    "ObjectiveDirection",
    "ObjectiveCalculator",

    # Constraints
    "SchedulingConstraint",
    "ConstraintType",
    "ConstraintPriority",
    "ConstraintSet",
    "ConstraintBuilder",
    "PrecedenceConstraint",
    "ResourceCapacityConstraint",
    "TimeWindowConstraint",
    "SetupTimeConstraint",
    "SetupTimeMatrix",
    "AlternativeMachineConstraint",
    "MaintenanceWindowConstraint",
    "SkillRequirementConstraint",
    "CalendarConstraint",
    "BatchConstraint",

    # Core
    "SchedulerFactory",
    "SchedulerType",
    "ScheduleStatus",
    "BaseScheduler",
    "Schedule",
    "ScheduledOperation",
    "SchedulingProblem",
    "Job",
    "Operation",
    "Machine",
    "GreedyScheduler",
    "PriorityDispatcher",

    # CP-SAT
    "CPSATScheduler",
    "CPSATConfig",
    "CPSATSchedulerWithSetups",
    "FlexibleJobShopScheduler",

    # NSGA-II/III
    "NSGA2Scheduler",
    "NSGA3Scheduler",
    "NSGA2Config",
    "ParetoFront",
    "ParetoSolution",

    # RL
    "RLDispatcher",
    "RLDispatchScheduler",
    "RLConfig",
    "DispatchRule",
    "DispatchState",
    "Experience",
    "ReplayBuffer",

    # Quantum
    "QAOAScheduler",
    "VQEScheduler",
    "SimulatedQuantum",

    # Advanced RL
    "PPOScheduler",
    "SACScheduler",
    "TD3Scheduler",
    "HierarchicalScheduler",
]

__version__ = "2.0.0"
__author__ = "LegoMCP Team"
