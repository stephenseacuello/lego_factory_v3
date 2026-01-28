"""
HTN Planner - Hierarchical Task Network Planning.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework

Enables complex multi-step manufacturing planning with
agent collaboration through task decomposition.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum
import uuid
import logging
import copy

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks in HTN."""
    PRIMITIVE = "primitive"    # Directly executable
    COMPOUND = "compound"      # Requires decomposition
    GOAL = "goal"              # State-based goal


@dataclass
class Condition:
    """Precondition or effect."""
    predicate: str
    args: Tuple[str, ...]
    negated: bool = False

    def evaluate(self, state: Dict[str, Any]) -> bool:
        """Evaluate condition against state."""
        key = f"{self.predicate}({','.join(self.args)})"
        result = state.get(key, False)
        return not result if self.negated else result

    def apply(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Apply effect to state."""
        key = f"{self.predicate}({','.join(self.args)})"
        new_state = state.copy()
        new_state[key] = not self.negated
        return new_state


@dataclass
class Task:
    """
    Task in the HTN planning hierarchy.

    Can be primitive (directly executable) or compound (requires decomposition).
    """
    name: str
    task_type: TaskType
    parameters: Dict[str, Any] = field(default_factory=dict)
    preconditions: List[Condition] = field(default_factory=list)
    effects: List[Condition] = field(default_factory=list)
    agent_type: Optional[str] = None
    priority: int = 5
    duration_estimate: float = 0.0  # seconds
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def check_preconditions(self, state: Dict[str, Any]) -> bool:
        """Check if all preconditions are satisfied."""
        return all(c.evaluate(state) for c in self.preconditions)

    def apply_effects(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all effects to state."""
        new_state = state.copy()
        for effect in self.effects:
            new_state = effect.apply(new_state)
        return new_state


@dataclass
class Method:
    """
    Decomposition method for compound tasks.

    Specifies how to break down a compound task into subtasks.
    """
    name: str
    task_name: str  # Compound task this method decomposes
    preconditions: List[Condition] = field(default_factory=list)
    subtasks: List[Task] = field(default_factory=list)
    ordered: bool = True  # If False, subtasks can be executed in any order
    priority: int = 5  # Method preference (lower = preferred)

    def is_applicable(self, state: Dict[str, Any]) -> bool:
        """Check if method is applicable in current state."""
        return all(c.evaluate(state) for c in self.preconditions)


@dataclass
class Plan:
    """Execution plan - sequence of primitive tasks."""
    plan_id: str
    tasks: List[Task]
    initial_state: Dict[str, Any]
    goal_state: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    estimated_duration: float = 0.0

    def __len__(self) -> int:
        return len(self.tasks)


class HTNPlanner:
    """
    Hierarchical Task Network Planner for manufacturing.

    Features:
    - Task decomposition for complex operations
    - State-based precondition checking
    - Multiple decomposition methods with priorities
    - Backtracking search for valid plans
    - Manufacturing-specific task templates

    Example manufacturing tasks:
    - print_batch -> {prepare_printer, load_material, execute_print, quality_check}
    - quality_check -> {visual_inspection, dimensional_check, clutch_test}
    """

    def __init__(self, max_depth: int = 20, max_iterations: int = 1000):
        self.max_depth = max_depth
        self.max_iterations = max_iterations
        self._methods: Dict[str, List[Method]] = {}
        self._primitive_tasks: Dict[str, Task] = {}

    def register_method(self, method: Method) -> None:
        """Register a decomposition method."""
        if method.task_name not in self._methods:
            self._methods[method.task_name] = []
        self._methods[method.task_name].append(method)
        # Sort by priority
        self._methods[method.task_name].sort(key=lambda m: m.priority)
        logger.debug(f"Registered method {method.name} for {method.task_name}")

    def register_primitive(self, task: Task) -> None:
        """Register a primitive task template."""
        if task.task_type != TaskType.PRIMITIVE:
            raise ValueError("Only primitive tasks can be registered")
        self._primitive_tasks[task.name] = task
        logger.debug(f"Registered primitive task {task.name}")

    def plan(self,
             initial_task: Task,
             initial_state: Dict[str, Any],
             goal_state: Optional[Dict[str, Any]] = None) -> Optional[Plan]:
        """
        Generate a plan by decomposing the initial task.

        Args:
            initial_task: Top-level task to plan
            initial_state: Current world state
            goal_state: Optional goal conditions

        Returns:
            Plan if found, None otherwise
        """
        plan_id = str(uuid.uuid4())
        iterations = 0

        # Use depth-first search with backtracking
        result = self._decompose(
            [initial_task],
            initial_state,
            goal_state or {},
            0,
            iterations
        )

        if result is None:
            logger.warning(f"No plan found for task {initial_task.name}")
            return None

        primitive_tasks, final_state = result

        # Calculate estimated duration
        duration = sum(t.duration_estimate for t in primitive_tasks)

        plan = Plan(
            plan_id=plan_id,
            tasks=primitive_tasks,
            initial_state=initial_state,
            goal_state=goal_state or final_state,
            estimated_duration=duration
        )

        logger.info(f"Plan {plan_id} generated with {len(plan)} steps")
        return plan

    def _decompose(self,
                   tasks: List[Task],
                   state: Dict[str, Any],
                   goal: Dict[str, Any],
                   depth: int,
                   iterations: int) -> Optional[Tuple[List[Task], Dict[str, Any]]]:
        """Recursive decomposition with backtracking."""
        if iterations > self.max_iterations:
            logger.warning("Max iterations exceeded")
            return None

        if depth > self.max_depth:
            logger.warning("Max depth exceeded")
            return None

        if not tasks:
            # All tasks decomposed - check goal
            if self._satisfies_goal(state, goal):
                return ([], state)
            return None

        current_task = tasks[0]
        remaining = tasks[1:]

        if current_task.task_type == TaskType.PRIMITIVE:
            # Check preconditions
            if not current_task.check_preconditions(state):
                return None

            # Apply effects
            new_state = current_task.apply_effects(state)

            # Continue with remaining tasks
            result = self._decompose(remaining, new_state, goal, depth, iterations + 1)
            if result is not None:
                result_tasks, final_state = result
                return ([current_task] + result_tasks, final_state)
            return None

        elif current_task.task_type == TaskType.COMPOUND:
            # Try each applicable method
            methods = self._methods.get(current_task.name, [])

            for method in methods:
                if not method.is_applicable(state):
                    continue

                # Substitute parameters
                subtasks = self._instantiate_subtasks(method, current_task)

                if method.ordered:
                    new_tasks = subtasks + remaining
                else:
                    # For unordered, try all permutations (simplified: just use as-is)
                    new_tasks = subtasks + remaining

                result = self._decompose(new_tasks, state, goal, depth + 1, iterations + 1)
                if result is not None:
                    return result

            return None  # No method worked

        elif current_task.task_type == TaskType.GOAL:
            # Goal task - find method that achieves it
            # This is simplified - full HTN would do goal regression
            methods = self._methods.get(current_task.name, [])

            for method in methods:
                if not method.is_applicable(state):
                    continue

                subtasks = self._instantiate_subtasks(method, current_task)
                new_tasks = subtasks + remaining

                result = self._decompose(new_tasks, state, goal, depth + 1, iterations + 1)
                if result is not None:
                    return result

            return None

        return None

    def _instantiate_subtasks(self, method: Method, task: Task) -> List[Task]:
        """Instantiate method subtasks with task parameters."""
        subtasks = []
        for subtask_template in method.subtasks:
            subtask = copy.deepcopy(subtask_template)
            # Substitute parameters from parent task
            for key, value in task.parameters.items():
                if key in subtask.parameters:
                    subtask.parameters[key] = value
            subtasks.append(subtask)
        return subtasks

    def _satisfies_goal(self, state: Dict[str, Any], goal: Dict[str, Any]) -> bool:
        """Check if state satisfies goal conditions."""
        if not goal:
            return True
        return all(state.get(k) == v for k, v in goal.items())


# Manufacturing-specific task templates
def create_manufacturing_domain() -> HTNPlanner:
    """Create HTN planner with manufacturing domain knowledge."""
    planner = HTNPlanner()

    # Primitive tasks
    planner.register_primitive(Task(
        name="preheat_bed",
        task_type=TaskType.PRIMITIVE,
        preconditions=[Condition("printer_available", ("printer",))],
        effects=[Condition("bed_heated", ("printer",))],
        duration_estimate=120
    ))

    planner.register_primitive(Task(
        name="preheat_nozzle",
        task_type=TaskType.PRIMITIVE,
        preconditions=[Condition("printer_available", ("printer",))],
        effects=[Condition("nozzle_heated", ("printer",))],
        duration_estimate=60
    ))

    planner.register_primitive(Task(
        name="load_filament",
        task_type=TaskType.PRIMITIVE,
        preconditions=[Condition("nozzle_heated", ("printer",))],
        effects=[Condition("filament_loaded", ("printer",))],
        duration_estimate=30
    ))

    planner.register_primitive(Task(
        name="execute_gcode",
        task_type=TaskType.PRIMITIVE,
        preconditions=[
            Condition("bed_heated", ("printer",)),
            Condition("nozzle_heated", ("printer",)),
            Condition("filament_loaded", ("printer",))
        ],
        effects=[Condition("print_complete", ("job",))],
        duration_estimate=3600
    ))

    planner.register_primitive(Task(
        name="visual_inspection",
        task_type=TaskType.PRIMITIVE,
        preconditions=[Condition("print_complete", ("job",))],
        effects=[Condition("visual_checked", ("job",))],
        duration_estimate=60
    ))

    planner.register_primitive(Task(
        name="dimensional_check",
        task_type=TaskType.PRIMITIVE,
        preconditions=[Condition("print_complete", ("job",))],
        effects=[Condition("dimensions_checked", ("job",))],
        duration_estimate=120
    ))

    planner.register_primitive(Task(
        name="clutch_test",
        task_type=TaskType.PRIMITIVE,
        preconditions=[Condition("print_complete", ("job",))],
        effects=[Condition("clutch_tested", ("job",))],
        duration_estimate=60
    ))

    # Compound task: prepare_printer
    planner.register_method(Method(
        name="prepare_printer_method",
        task_name="prepare_printer",
        subtasks=[
            Task(name="preheat_bed", task_type=TaskType.PRIMITIVE),
            Task(name="preheat_nozzle", task_type=TaskType.PRIMITIVE),
            Task(name="load_filament", task_type=TaskType.PRIMITIVE)
        ]
    ))

    # Compound task: quality_check
    planner.register_method(Method(
        name="full_quality_check",
        task_name="quality_check",
        subtasks=[
            Task(name="visual_inspection", task_type=TaskType.PRIMITIVE),
            Task(name="dimensional_check", task_type=TaskType.PRIMITIVE),
            Task(name="clutch_test", task_type=TaskType.PRIMITIVE)
        ],
        ordered=False  # Can be done in any order
    ))

    planner.register_method(Method(
        name="quick_quality_check",
        task_name="quality_check",
        preconditions=[Condition("quick_mode", ("config",))],
        subtasks=[
            Task(name="visual_inspection", task_type=TaskType.PRIMITIVE)
        ],
        priority=10  # Lower priority than full check
    ))

    # Compound task: print_lego_brick
    planner.register_method(Method(
        name="print_lego_brick_method",
        task_name="print_lego_brick",
        subtasks=[
            Task(name="prepare_printer", task_type=TaskType.COMPOUND),
            Task(name="execute_gcode", task_type=TaskType.PRIMITIVE),
            Task(name="quality_check", task_type=TaskType.COMPOUND)
        ]
    ))

    return planner
