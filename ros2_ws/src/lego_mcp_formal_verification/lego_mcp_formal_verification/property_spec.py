"""
Temporal Logic Property Specifications

Defines LTL and CTL formulas for manufacturing safety properties.

Reference: Model Checking (Clarke et al.), Temporal Logic
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import re


class PropertyType(Enum):
    """Type of temporal property."""
    SAFETY = "safety"          # Something bad never happens
    LIVENESS = "liveness"      # Something good eventually happens
    FAIRNESS = "fairness"      # Fair scheduling
    RESPONSE = "response"      # Request leads to response
    PRECEDENCE = "precedence"  # Ordering constraint


class LTLOperator(Enum):
    """Linear Temporal Logic operators."""
    # Path operators
    ALWAYS = "G"       # Globally (always)
    EVENTUALLY = "F"   # Finally (eventually)
    NEXT = "X"         # Next state
    UNTIL = "U"        # Strong until
    WEAK_UNTIL = "W"   # Weak until
    RELEASE = "R"      # Release

    # Boolean operators
    AND = "&&"
    OR = "||"
    NOT = "!"
    IMPLIES = "->"
    IFF = "<->"

    # Atomic
    ATOM = "atom"


class CTLOperator(Enum):
    """Computation Tree Logic operators."""
    # Path quantifiers
    ALL = "A"       # All paths
    EXISTS = "E"    # Some path

    # Temporal operators (combined with path quantifier)
    AG = "AG"       # All paths, Globally
    AF = "AF"       # All paths, Finally
    AX = "AX"       # All paths, neXt
    AU = "AU"       # All paths, Until
    EG = "EG"       # Exists path, Globally
    EF = "EF"       # Exists path, Finally
    EX = "EX"       # Exists path, neXt
    EU = "EU"       # Exists path, Until


@dataclass
class AtomicProposition:
    """
    Atomic proposition in temporal logic.

    Represents a basic predicate that can be true or false.
    """
    name: str
    description: str = ""
    evaluator: Optional[Callable[[Dict[str, Any]], bool]] = None

    def evaluate(self, state: Dict[str, Any]) -> bool:
        """Evaluate proposition in given state."""
        if self.evaluator:
            return self.evaluator(state)
        return state.get(self.name, False)

    def __str__(self) -> str:
        return self.name


@dataclass
class LTLFormula:
    """
    Linear Temporal Logic formula.

    LTL formulas describe properties of individual execution paths.
    """
    operator: LTLOperator
    operands: List[Union['LTLFormula', AtomicProposition]] = field(default_factory=list)
    time_bound: Optional[float] = None  # Bounded temporal operator

    @classmethod
    def atom(cls, prop: Union[str, AtomicProposition]) -> 'LTLFormula':
        """Create atomic formula."""
        if isinstance(prop, str):
            prop = AtomicProposition(prop)
        return cls(operator=LTLOperator.ATOM, operands=[prop])

    @classmethod
    def always(cls, formula: 'LTLFormula', bound: Optional[float] = None) -> 'LTLFormula':
        """G(formula) - formula holds at all future states."""
        return cls(operator=LTLOperator.ALWAYS, operands=[formula], time_bound=bound)

    @classmethod
    def eventually(cls, formula: 'LTLFormula', bound: Optional[float] = None) -> 'LTLFormula':
        """F(formula) - formula holds at some future state."""
        return cls(operator=LTLOperator.EVENTUALLY, operands=[formula], time_bound=bound)

    @classmethod
    def next(cls, formula: 'LTLFormula') -> 'LTLFormula':
        """X(formula) - formula holds at next state."""
        return cls(operator=LTLOperator.NEXT, operands=[formula])

    @classmethod
    def until(cls, left: 'LTLFormula', right: 'LTLFormula') -> 'LTLFormula':
        """left U right - left holds until right becomes true."""
        return cls(operator=LTLOperator.UNTIL, operands=[left, right])

    @classmethod
    def implies(cls, left: 'LTLFormula', right: 'LTLFormula') -> 'LTLFormula':
        """left -> right - logical implication."""
        return cls(operator=LTLOperator.IMPLIES, operands=[left, right])

    @classmethod
    def and_(cls, *formulas: 'LTLFormula') -> 'LTLFormula':
        """Conjunction of formulas."""
        return cls(operator=LTLOperator.AND, operands=list(formulas))

    @classmethod
    def or_(cls, *formulas: 'LTLFormula') -> 'LTLFormula':
        """Disjunction of formulas."""
        return cls(operator=LTLOperator.OR, operands=list(formulas))

    @classmethod
    def not_(cls, formula: 'LTLFormula') -> 'LTLFormula':
        """Negation of formula."""
        return cls(operator=LTLOperator.NOT, operands=[formula])

    def to_promela(self) -> str:
        """Convert to Promela LTL syntax."""
        if self.operator == LTLOperator.ATOM:
            return str(self.operands[0])
        elif self.operator == LTLOperator.ALWAYS:
            return f"[] ({self.operands[0].to_promela()})"
        elif self.operator == LTLOperator.EVENTUALLY:
            return f"<> ({self.operands[0].to_promela()})"
        elif self.operator == LTLOperator.NEXT:
            return f"X ({self.operands[0].to_promela()})"
        elif self.operator == LTLOperator.UNTIL:
            return f"({self.operands[0].to_promela()}) U ({self.operands[1].to_promela()})"
        elif self.operator == LTLOperator.IMPLIES:
            return f"({self.operands[0].to_promela()}) -> ({self.operands[1].to_promela()})"
        elif self.operator == LTLOperator.AND:
            parts = [f"({o.to_promela()})" for o in self.operands]
            return " && ".join(parts)
        elif self.operator == LTLOperator.OR:
            parts = [f"({o.to_promela()})" for o in self.operands]
            return " || ".join(parts)
        elif self.operator == LTLOperator.NOT:
            return f"! ({self.operands[0].to_promela()})"
        return ""

    def __str__(self) -> str:
        return self.to_promela()


@dataclass
class CTLFormula:
    """
    Computation Tree Logic formula.

    CTL formulas describe properties over computation trees
    (branching-time logic).
    """
    operator: CTLOperator
    operands: List[Union['CTLFormula', AtomicProposition]] = field(default_factory=list)

    @classmethod
    def atom(cls, prop: Union[str, AtomicProposition]) -> 'CTLFormula':
        """Create atomic formula."""
        if isinstance(prop, str):
            prop = AtomicProposition(prop)
        return cls(operator=CTLOperator.AG, operands=[prop])  # Placeholder

    @classmethod
    def ag(cls, formula: 'CTLFormula') -> 'CTLFormula':
        """AG(formula) - on all paths, always."""
        return cls(operator=CTLOperator.AG, operands=[formula])

    @classmethod
    def af(cls, formula: 'CTLFormula') -> 'CTLFormula':
        """AF(formula) - on all paths, eventually."""
        return cls(operator=CTLOperator.AF, operands=[formula])

    @classmethod
    def ef(cls, formula: 'CTLFormula') -> 'CTLFormula':
        """EF(formula) - on some path, eventually."""
        return cls(operator=CTLOperator.EF, operands=[formula])

    @classmethod
    def eg(cls, formula: 'CTLFormula') -> 'CTLFormula':
        """EG(formula) - on some path, always."""
        return cls(operator=CTLOperator.EG, operands=[formula])

    def to_nusmv(self) -> str:
        """Convert to nuSMV/nuXmv syntax."""
        if self.operator == CTLOperator.AG:
            return f"AG ({self.operands[0].to_nusmv() if hasattr(self.operands[0], 'to_nusmv') else str(self.operands[0])})"
        elif self.operator == CTLOperator.AF:
            return f"AF ({self.operands[0].to_nusmv() if hasattr(self.operands[0], 'to_nusmv') else str(self.operands[0])})"
        elif self.operator == CTLOperator.EF:
            return f"EF ({self.operands[0].to_nusmv() if hasattr(self.operands[0], 'to_nusmv') else str(self.operands[0])})"
        elif self.operator == CTLOperator.EG:
            return f"EG ({self.operands[0].to_nusmv() if hasattr(self.operands[0], 'to_nusmv') else str(self.operands[0])})"
        return ""


@dataclass
class SafetyProperty:
    """
    Safety property specification.

    Safety properties state that "something bad never happens."
    Expressible as G(not bad_state).

    Reference: Alpern & Schneider, "Recognizing Safety and Liveness"
    """
    id: str
    name: str
    description: str
    formula: LTLFormula
    severity: int = 3  # 1-5, 5=critical
    asil_level: str = "B"  # ISO 26262 ASIL levels: QM, A, B, C, D
    sil_level: int = 2  # IEC 61508 SIL levels: 1-4

    def is_safety(self) -> bool:
        """Check if this is a valid safety property."""
        # Safety properties are of form G(p) or !F(!p)
        return self.formula.operator == LTLOperator.ALWAYS

    def to_promela_ltl(self) -> str:
        """Generate Promela LTL claim."""
        return f"ltl {self.id} {{ {self.formula.to_promela()} }}"


@dataclass
class LivenessProperty:
    """
    Liveness property specification.

    Liveness properties state that "something good eventually happens."
    Expressible as F(good_state).

    Reference: Alpern & Schneider, "Recognizing Safety and Liveness"
    """
    id: str
    name: str
    description: str
    formula: LTLFormula
    timeout_ms: Optional[float] = None  # Bounded liveness

    def is_liveness(self) -> bool:
        """Check if this is a valid liveness property."""
        # Liveness properties contain F (eventually)
        return self.formula.operator == LTLOperator.EVENTUALLY

    def to_promela_ltl(self) -> str:
        """Generate Promela LTL claim."""
        return f"ltl {self.id} {{ {self.formula.to_promela()} }}"


# Predefined Manufacturing Safety Properties
MANUFACTURING_SAFETY_PROPERTIES = {
    "SP-001": SafetyProperty(
        id="SP-001",
        name="NoCollision",
        description="Robots must never collide",
        formula=LTLFormula.always(
            LTLFormula.not_(LTLFormula.atom("collision"))
        ),
        severity=5,
        asil_level="D",
        sil_level=3
    ),
    "SP-002": SafetyProperty(
        id="SP-002",
        name="EmergencyStopEffective",
        description="Emergency stop must halt all motion within 100ms",
        formula=LTLFormula.always(
            LTLFormula.implies(
                LTLFormula.atom("e_stop_pressed"),
                LTLFormula.eventually(
                    LTLFormula.atom("all_motion_stopped"),
                    bound=0.1
                )
            )
        ),
        severity=5,
        asil_level="D",
        sil_level=4
    ),
    "SP-003": SafetyProperty(
        id="SP-003",
        name="TemperatureInRange",
        description="Process temperature must stay within safe limits",
        formula=LTLFormula.always(
            LTLFormula.atom("temperature_safe")
        ),
        severity=4,
        asil_level="C",
        sil_level=2
    ),
    "SP-004": SafetyProperty(
        id="SP-004",
        name="PressureInRange",
        description="System pressure must stay within safe limits",
        formula=LTLFormula.always(
            LTLFormula.atom("pressure_safe")
        ),
        severity=4,
        asil_level="C",
        sil_level=2
    ),
}

MANUFACTURING_LIVENESS_PROPERTIES = {
    "LP-001": LivenessProperty(
        id="LP-001",
        name="JobCompletion",
        description="Every started job must eventually complete or fail",
        formula=LTLFormula.always(
            LTLFormula.implies(
                LTLFormula.atom("job_started"),
                LTLFormula.eventually(
                    LTLFormula.or_(
                        LTLFormula.atom("job_completed"),
                        LTLFormula.atom("job_failed")
                    )
                )
            )
        ),
        timeout_ms=60000
    ),
    "LP-002": LivenessProperty(
        id="LP-002",
        name="RequestResponse",
        description="Every request receives a response",
        formula=LTLFormula.always(
            LTLFormula.implies(
                LTLFormula.atom("request"),
                LTLFormula.eventually(LTLFormula.atom("response"))
            )
        ),
        timeout_ms=5000
    ),
}
