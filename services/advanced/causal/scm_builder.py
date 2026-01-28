"""
SCM Builder - Structural Causal Model construction.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

Build causal graphs from domain knowledge and data.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger(__name__)


class VariableType(Enum):
    """Types of causal variables."""
    CONTINUOUS = "continuous"
    CATEGORICAL = "categorical"
    BINARY = "binary"
    ORDINAL = "ordinal"


class EdgeType(Enum):
    """Types of causal edges."""
    DIRECT = "direct"           # A -> B
    CONFOUNDED = "confounded"   # A <-> B (hidden confounder)
    SELECTION = "selection"     # Selection bias


@dataclass
class CausalVariable:
    """
    Variable in a causal model.

    Attributes:
        name: Variable name
        var_type: Variable type
        domain: Possible values or range
        description: Human-readable description
        structural_equation: Function computing value from parents + noise
    """
    name: str
    var_type: VariableType
    domain: Any = None
    description: str = ""
    structural_equation: Optional[Callable] = None
    noise_distribution: str = "gaussian"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CausalEdge:
    """Edge in causal graph."""
    source: str
    target: str
    edge_type: EdgeType = EdgeType.DIRECT
    coefficient: Optional[float] = None
    confidence: float = 1.0


class CausalGraph:
    """
    Directed Acyclic Graph for causal structure.

    Represents causal relationships between manufacturing variables.
    """

    def __init__(self):
        self._variables: Dict[str, CausalVariable] = {}
        self._edges: List[CausalEdge] = []
        self._adjacency: Dict[str, Set[str]] = {}  # parent -> children
        self._reverse_adj: Dict[str, Set[str]] = {}  # child -> parents

    def add_variable(self, variable: CausalVariable) -> None:
        """Add a variable to the graph."""
        self._variables[variable.name] = variable
        if variable.name not in self._adjacency:
            self._adjacency[variable.name] = set()
        if variable.name not in self._reverse_adj:
            self._reverse_adj[variable.name] = set()

    def add_edge(self, edge: CausalEdge) -> bool:
        """
        Add a causal edge.

        Returns False if edge would create a cycle.
        """
        if edge.source not in self._variables or edge.target not in self._variables:
            logger.warning(f"Variables not found for edge {edge.source} -> {edge.target}")
            return False

        # Check for cycle
        if self._would_create_cycle(edge.source, edge.target):
            logger.warning(f"Edge {edge.source} -> {edge.target} would create cycle")
            return False

        self._edges.append(edge)
        self._adjacency[edge.source].add(edge.target)
        self._reverse_adj[edge.target].add(edge.source)
        return True

    def _would_create_cycle(self, source: str, target: str) -> bool:
        """Check if adding edge would create a cycle."""
        # DFS from target to see if we can reach source
        visited = set()
        stack = [target]

        while stack:
            node = stack.pop()
            if node == source:
                return True
            if node in visited:
                continue
            visited.add(node)
            stack.extend(self._adjacency.get(node, set()))

        return False

    def get_parents(self, node: str) -> Set[str]:
        """Get parent nodes."""
        return self._reverse_adj.get(node, set())

    def get_children(self, node: str) -> Set[str]:
        """Get child nodes."""
        return self._adjacency.get(node, set())

    def get_ancestors(self, node: str) -> Set[str]:
        """Get all ancestors of a node."""
        ancestors = set()
        stack = list(self.get_parents(node))

        while stack:
            current = stack.pop()
            if current not in ancestors:
                ancestors.add(current)
                stack.extend(self.get_parents(current))

        return ancestors

    def get_descendants(self, node: str) -> Set[str]:
        """Get all descendants of a node."""
        descendants = set()
        stack = list(self.get_children(node))

        while stack:
            current = stack.pop()
            if current not in descendants:
                descendants.add(current)
                stack.extend(self.get_children(current))

        return descendants

    def topological_sort(self) -> List[str]:
        """Return nodes in topological order."""
        in_degree = {v: len(self._reverse_adj.get(v, set())) for v in self._variables}
        queue = [v for v, d in in_degree.items() if d == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for child in self._adjacency.get(node, set()):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return result

    def is_d_separated(self,
                       x: str,
                       y: str,
                       conditioning: Set[str]) -> bool:
        """
        Check if X and Y are d-separated given conditioning set.

        Uses the Bayes Ball algorithm.
        """
        # Simplified d-separation check
        # Full implementation would use proper Bayes Ball algorithm

        # If there's a direct path not blocked by conditioning, not separated
        visited = set()
        stack = [(x, 'down')]  # (node, direction)

        while stack:
            node, direction = stack.pop()
            if (node, direction) in visited:
                continue
            visited.add((node, direction))

            if node == y:
                return False

            is_conditioned = node in conditioning

            if direction == 'down':
                # Going down through node
                if not is_conditioned:
                    # Can continue down to children
                    for child in self.get_children(node):
                        stack.append((child, 'down'))
                    # Can also go up to parents
                    for parent in self.get_parents(node):
                        stack.append((parent, 'up'))

            else:  # direction == 'up'
                if is_conditioned:
                    # Collider - can continue up
                    for parent in self.get_parents(node):
                        stack.append((parent, 'up'))
                else:
                    # Chain/fork - can continue down
                    for child in self.get_children(node):
                        stack.append((child, 'down'))

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Export graph to dictionary."""
        return {
            'variables': [
                {
                    'name': v.name,
                    'type': v.var_type.value,
                    'description': v.description
                }
                for v in self._variables.values()
            ],
            'edges': [
                {
                    'source': e.source,
                    'target': e.target,
                    'type': e.edge_type.value,
                    'coefficient': e.coefficient
                }
                for e in self._edges
            ]
        }


class SCMBuilder:
    """
    Builder for Structural Causal Models.

    Creates causal graphs for manufacturing domains with:
    - Domain knowledge integration
    - Data-driven refinement
    - Structural equation specification
    """

    def __init__(self):
        self._graph = CausalGraph()
        self._equations: Dict[str, Callable] = {}

    def add_variable(self,
                    name: str,
                    var_type: VariableType = VariableType.CONTINUOUS,
                    domain: Any = None,
                    description: str = "") -> 'SCMBuilder':
        """Add a variable to the model."""
        variable = CausalVariable(
            name=name,
            var_type=var_type,
            domain=domain,
            description=description
        )
        self._graph.add_variable(variable)
        return self

    def add_cause(self,
                  cause: str,
                  effect: str,
                  coefficient: Optional[float] = None) -> 'SCMBuilder':
        """Add a causal relationship."""
        edge = CausalEdge(
            source=cause,
            target=effect,
            coefficient=coefficient
        )
        self._graph.add_edge(edge)
        return self

    def set_equation(self,
                    variable: str,
                    equation: Callable[[Dict[str, Any], float], Any]) -> 'SCMBuilder':
        """
        Set structural equation for a variable.

        Equation signature: f(parent_values: Dict, noise: float) -> value
        """
        self._equations[variable] = equation
        return self

    def build(self) -> Tuple[CausalGraph, Dict[str, Callable]]:
        """Build the SCM."""
        return self._graph, self._equations

    @staticmethod
    def create_lego_quality_scm() -> Tuple[CausalGraph, Dict[str, Callable]]:
        """
        Create SCM for LEGO brick quality.

        Causal structure:
        - print_temp -> stud_diameter, surface_quality
        - print_speed -> stud_diameter, layer_adhesion
        - material_moisture -> layer_adhesion, surface_quality
        - stud_diameter -> clutch_power
        - layer_adhesion -> structural_strength
        - surface_quality -> visual_grade
        - clutch_power, structural_strength, visual_grade -> overall_quality
        """
        builder = SCMBuilder()

        # Add variables
        builder.add_variable('print_temp', VariableType.CONTINUOUS,
                           domain=(180, 240), description='Nozzle temperature (C)')
        builder.add_variable('print_speed', VariableType.CONTINUOUS,
                           domain=(20, 100), description='Print speed (mm/s)')
        builder.add_variable('material_moisture', VariableType.CONTINUOUS,
                           domain=(0, 10), description='Material moisture (%)')
        builder.add_variable('stud_diameter', VariableType.CONTINUOUS,
                           domain=(4.7, 4.9), description='Stud diameter (mm)')
        builder.add_variable('layer_adhesion', VariableType.CONTINUOUS,
                           domain=(0, 100), description='Layer adhesion strength (%)')
        builder.add_variable('surface_quality', VariableType.CONTINUOUS,
                           domain=(0, 100), description='Surface quality score')
        builder.add_variable('clutch_power', VariableType.CONTINUOUS,
                           domain=(0, 5), description='Clutch force (N)')
        builder.add_variable('structural_strength', VariableType.CONTINUOUS,
                           domain=(0, 100), description='Structural integrity (%)')
        builder.add_variable('visual_grade', VariableType.CATEGORICAL,
                           domain=['A', 'B', 'C', 'D'], description='Visual quality grade')
        builder.add_variable('overall_quality', VariableType.CONTINUOUS,
                           domain=(0, 100), description='Overall quality score')

        # Add causal relationships
        builder.add_cause('print_temp', 'stud_diameter', 0.002)
        builder.add_cause('print_temp', 'surface_quality', 0.3)
        builder.add_cause('print_speed', 'stud_diameter', -0.001)
        builder.add_cause('print_speed', 'layer_adhesion', -0.5)
        builder.add_cause('material_moisture', 'layer_adhesion', -5.0)
        builder.add_cause('material_moisture', 'surface_quality', -3.0)
        builder.add_cause('stud_diameter', 'clutch_power', 10.0)
        builder.add_cause('layer_adhesion', 'structural_strength', 1.0)
        builder.add_cause('surface_quality', 'visual_grade')
        builder.add_cause('clutch_power', 'overall_quality', 10.0)
        builder.add_cause('structural_strength', 'overall_quality', 0.5)
        builder.add_cause('visual_grade', 'overall_quality', 5.0)

        # Set structural equations
        builder.set_equation('stud_diameter', lambda p, n:
            4.8 + 0.002 * (p.get('print_temp', 200) - 200) - 0.001 * (p.get('print_speed', 50) - 50) + n * 0.01
        )

        builder.set_equation('layer_adhesion', lambda p, n:
            80 - 0.5 * (p.get('print_speed', 50) - 50) - 5 * p.get('material_moisture', 0) + n * 5
        )

        builder.set_equation('clutch_power', lambda p, n:
            2.0 + 10 * (p.get('stud_diameter', 4.8) - 4.8) + n * 0.2
        )

        return builder.build()
