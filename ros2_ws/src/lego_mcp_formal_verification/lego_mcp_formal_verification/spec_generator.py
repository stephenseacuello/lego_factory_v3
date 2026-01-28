"""
Specification Generator for Formal Verification

Generates Promela (SPIN) and TLA+ specifications from
high-level manufacturing system models.

Reference: Holzmann "The SPIN Model Checker", Lamport "Specifying Systems"
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import textwrap


@dataclass
class StateVariable:
    """State variable in the model."""
    name: str
    var_type: str  # "int", "bool", "byte", "mtype"
    initial_value: Any
    description: str = ""


@dataclass
class Process:
    """Process/component in the model."""
    name: str
    states: List[str]
    initial_state: str
    transitions: List['Transition'] = field(default_factory=list)
    local_vars: List[StateVariable] = field(default_factory=list)


@dataclass
class Transition:
    """State transition."""
    from_state: str
    to_state: str
    guard: str  # Boolean condition
    action: str  # Assignment or channel operation
    label: str = ""


@dataclass
class SpecificationContext:
    """
    Context for generating specifications.

    Captures the manufacturing system model.
    """
    name: str
    description: str
    processes: List[Process] = field(default_factory=list)
    global_vars: List[StateVariable] = field(default_factory=list)
    ltl_properties: List[str] = field(default_factory=list)
    invariants: List[str] = field(default_factory=list)
    channels: Dict[str, int] = field(default_factory=dict)  # name -> capacity


class PromelaGenerator:
    """
    Generates Promela specifications for SPIN model checker.

    Reference: Holzmann, "The SPIN Model Checker"
    """

    def __init__(self, context: SpecificationContext):
        self.context = context

    def generate(self) -> str:
        """Generate complete Promela specification."""
        parts = [
            self._generate_header(),
            self._generate_mtypes(),
            self._generate_globals(),
            self._generate_channels(),
            self._generate_processes(),
            self._generate_init(),
            self._generate_ltl_properties(),
        ]
        return "\n\n".join(filter(None, parts))

    def _generate_header(self) -> str:
        """Generate file header."""
        return textwrap.dedent(f"""\
            /*
             * {self.context.name}
             * {self.context.description}
             *
             * Generated: {datetime.now().isoformat()}
             * Tool: LEGO MCP Formal Verification Framework
             */
        """)

    def _generate_mtypes(self) -> str:
        """Generate mtype declarations for states."""
        all_states: Set[str] = set()
        for proc in self.context.processes:
            all_states.update(proc.states)

        if not all_states:
            return ""

        states_str = ", ".join(sorted(all_states))
        return f"mtype = {{{states_str}}};"

    def _generate_globals(self) -> str:
        """Generate global variable declarations."""
        if not self.context.global_vars:
            return ""

        lines = ["/* Global variables */"]
        for var in self.context.global_vars:
            if var.description:
                lines.append(f"/* {var.description} */")
            lines.append(f"{var.var_type} {var.name} = {var.initial_value};")

        return "\n".join(lines)

    def _generate_channels(self) -> str:
        """Generate channel declarations."""
        if not self.context.channels:
            return ""

        lines = ["/* Channels */"]
        for name, capacity in self.context.channels.items():
            lines.append(f"chan {name} = [{capacity}] of {{ mtype, int }};")

        return "\n".join(lines)

    def _generate_processes(self) -> str:
        """Generate process definitions."""
        parts = []
        for proc in self.context.processes:
            parts.append(self._generate_process(proc))
        return "\n\n".join(parts)

    def _generate_process(self, proc: Process) -> str:
        """Generate single process definition."""
        lines = [f"proctype {proc.name}() {{"]

        # Local variables
        for var in proc.local_vars:
            lines.append(f"    {var.var_type} {var.name} = {var.initial_value};")

        lines.append(f"    mtype state = {proc.initial_state};")
        lines.append("")
        lines.append("    do")

        # Group transitions by source state
        by_state: Dict[str, List[Transition]] = {}
        for trans in proc.transitions:
            if trans.from_state not in by_state:
                by_state[trans.from_state] = []
            by_state[trans.from_state].append(trans)

        for state, transitions in by_state.items():
            lines.append(f"    :: state == {state} ->")
            lines.append("        if")
            for trans in transitions:
                guard = trans.guard if trans.guard else "true"
                lines.append(f"        :: {guard} ->")
                if trans.action:
                    lines.append(f"            {trans.action};")
                lines.append(f"            state = {trans.to_state}")
            lines.append("        fi")

        lines.append("    od")
        lines.append("}")

        return "\n".join(lines)

    def _generate_init(self) -> str:
        """Generate init process."""
        lines = ["init {"]
        lines.append("    atomic {")
        for proc in self.context.processes:
            lines.append(f"        run {proc.name}();")
        lines.append("    }")
        lines.append("}")
        return "\n".join(lines)

    def _generate_ltl_properties(self) -> str:
        """Generate LTL property claims."""
        if not self.context.ltl_properties:
            return ""

        lines = ["/* LTL Properties */"]
        for i, prop in enumerate(self.context.ltl_properties):
            lines.append(f"ltl prop{i} {{ {prop} }}")

        return "\n".join(lines)


class TLAGenerator:
    """
    Generates TLA+ specifications.

    Reference: Lamport, "Specifying Systems"
    """

    def __init__(self, context: SpecificationContext):
        self.context = context

    def generate(self) -> str:
        """Generate complete TLA+ specification."""
        parts = [
            self._generate_header(),
            self._generate_constants(),
            self._generate_variables(),
            self._generate_type_invariant(),
            self._generate_init(),
            self._generate_actions(),
            self._generate_next(),
            self._generate_spec(),
            self._generate_properties(),
            self._generate_footer(),
        ]
        return "\n\n".join(filter(None, parts))

    def _generate_header(self) -> str:
        """Generate module header."""
        module_name = self.context.name.replace(" ", "")
        return textwrap.dedent(f"""\
            ---- MODULE {module_name} ----
            (*
             * {self.context.description}
             *
             * Generated: {datetime.now().isoformat()}
             * Tool: LEGO MCP Formal Verification Framework
             *)

            EXTENDS Integers, Sequences, FiniteSets
        """)

    def _generate_constants(self) -> str:
        """Generate CONSTANTS section."""
        if not self.context.processes:
            return ""

        lines = ["CONSTANTS"]
        constants = set()
        for proc in self.context.processes:
            constants.add(f"    Num{proc.name}s")
        constants.add("    MaxQueueLen")

        return "CONSTANTS\n" + ",\n".join(sorted(constants))

    def _generate_variables(self) -> str:
        """Generate VARIABLES section."""
        lines = ["VARIABLES"]
        vars = []

        for var in self.context.global_vars:
            vars.append(f"    {var.name}")

        for proc in self.context.processes:
            vars.append(f"    {proc.name.lower()}State")

        if vars:
            return "VARIABLES\n" + ",\n".join(vars) + "\n\nvars == <<" + ", ".join([v.strip() for v in vars]) + ">>"

        return ""

    def _generate_type_invariant(self) -> str:
        """Generate TypeInvariant."""
        lines = ["TypeInvariant =="]
        conditions = []

        for var in self.context.global_vars:
            if var.var_type == "bool":
                conditions.append(f"    /\\ {var.name} \\in BOOLEAN")
            elif var.var_type == "int":
                conditions.append(f"    /\\ {var.name} \\in Int")

        for proc in self.context.processes:
            states_set = "{" + ", ".join(f'"{s}"' for s in proc.states) + "}"
            conditions.append(f"    /\\ {proc.name.lower()}State \\in {states_set}")

        return "\n".join(lines + conditions) if conditions else ""

    def _generate_init(self) -> str:
        """Generate Init predicate."""
        lines = ["Init =="]
        inits = []

        for var in self.context.global_vars:
            inits.append(f"    /\\ {var.name} = {self._convert_value(var.initial_value)}")

        for proc in self.context.processes:
            inits.append(f'    /\\ {proc.name.lower()}State = "{proc.initial_state}"')

        return "\n".join(lines + inits) if inits else "Init == TRUE"

    def _generate_actions(self) -> str:
        """Generate action definitions."""
        actions = []

        for proc in self.context.processes:
            for trans in proc.transitions:
                action_name = f"{proc.name}_{trans.from_state}_To_{trans.to_state}"
                action_lines = [f"{action_name} =="]
                state_var = f"{proc.name.lower()}State"

                action_lines.append(f'    /\\ {state_var} = "{trans.from_state}"')
                if trans.guard:
                    action_lines.append(f"    /\\ {trans.guard}")
                action_lines.append(f"    /\\ {state_var}' = \"{trans.to_state}\"")

                # UNCHANGED for other variables
                other_vars = [v.name for v in self.context.global_vars]
                if other_vars:
                    action_lines.append(f"    /\\ UNCHANGED <<{', '.join(other_vars)}>>")

                actions.append("\n".join(action_lines))

        return "\n\n".join(actions)

    def _generate_next(self) -> str:
        """Generate Next predicate."""
        action_refs = []
        for proc in self.context.processes:
            for trans in proc.transitions:
                action_name = f"{proc.name}_{trans.from_state}_To_{trans.to_state}"
                action_refs.append(action_name)

        if not action_refs:
            return "Next == TRUE"

        lines = ["Next =="]
        lines.append("    \\/ " + "\n    \\/ ".join(action_refs))
        return "\n".join(lines)

    def _generate_spec(self) -> str:
        """Generate Spec formula."""
        return textwrap.dedent("""\
            Spec == Init /\\ [][Next]_vars /\\ WF_vars(Next)
        """)

    def _generate_properties(self) -> str:
        """Generate property theorems."""
        lines = []

        for inv in self.context.invariants:
            lines.append(f"SafetyProperty == []{inv}")

        lines.append("")
        lines.append("THEOREM Spec => []TypeInvariant")
        for i, inv in enumerate(self.context.invariants):
            lines.append(f"THEOREM Spec => SafetyProperty")

        return "\n".join(lines)

    def _generate_footer(self) -> str:
        """Generate module footer."""
        return "===="

    def _convert_value(self, value: Any) -> str:
        """Convert Python value to TLA+ value."""
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, str):
            return f'"{value}"'
        return str(value)


# Convenience functions for common manufacturing patterns

def create_robot_cell_spec(
    num_robots: int = 3,
    num_positions: int = 5
) -> SpecificationContext:
    """Create specification for robot cell."""
    ctx = SpecificationContext(
        name="RobotCell",
        description="Multi-robot manufacturing cell with collision avoidance"
    )

    # Global variables
    ctx.global_vars = [
        StateVariable("emergencyStop", "bool", "false", "Emergency stop button"),
        StateVariable("totalJobs", "int", "0", "Total jobs completed"),
    ]

    # Robot process
    robot_states = ["Idle", "Moving", "Processing", "EStop"]
    transitions = [
        Transition("Idle", "Moving", "!emergencyStop", "", "Start moving"),
        Transition("Moving", "Processing", "!emergencyStop", "", "Arrived"),
        Transition("Processing", "Idle", "!emergencyStop", "totalJobs++", "Done"),
        Transition("Idle", "EStop", "emergencyStop", "", "Emergency"),
        Transition("Moving", "EStop", "emergencyStop", "", "Emergency"),
        Transition("Processing", "EStop", "emergencyStop", "", "Emergency"),
        Transition("EStop", "Idle", "!emergencyStop", "", "Reset"),
    ]

    ctx.processes = [
        Process(
            name="Robot",
            states=robot_states,
            initial_state="Idle",
            transitions=transitions
        )
    ]

    # Safety properties
    ctx.ltl_properties = [
        "[] (!emergencyStop || <> (state == EStop))",  # E-stop works
        "[] (state == Moving -> X (state == Processing || state == EStop))",
    ]

    ctx.invariants = [
        "emergencyStop => robotState = \"EStop\"",
    ]

    return ctx


def create_conveyor_spec(num_stations: int = 4) -> SpecificationContext:
    """Create specification for conveyor system."""
    ctx = SpecificationContext(
        name="ConveyorSystem",
        description="Multi-station conveyor with piece tracking"
    )

    ctx.global_vars = [
        StateVariable("pieceCount", "int", "0", "Pieces on conveyor"),
        StateVariable("running", "bool", "true", "Conveyor running"),
    ]

    conveyor_states = ["Empty", "Loading", "Moving", "Unloading", "Stopped"]
    transitions = [
        Transition("Empty", "Loading", "running", "pieceCount++", "Load piece"),
        Transition("Loading", "Moving", "true", "", "Start moving"),
        Transition("Moving", "Unloading", "true", "", "Arrived at station"),
        Transition("Unloading", "Empty", "true", "pieceCount--", "Piece removed"),
        Transition("Empty", "Stopped", "!running", "", "Stop conveyor"),
        Transition("Moving", "Stopped", "!running", "", "Stop conveyor"),
    ]

    ctx.processes = [
        Process(
            name="Conveyor",
            states=conveyor_states,
            initial_state="Empty",
            transitions=transitions
        )
    ]

    ctx.ltl_properties = [
        "[] (pieceCount >= 0)",  # No negative pieces
        "[] (state == Loading -> <> state == Unloading)",  # Loaded pieces get delivered
    ]

    return ctx
