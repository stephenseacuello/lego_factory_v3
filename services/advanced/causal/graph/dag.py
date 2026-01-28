"""
Causal DAG - Directed Acyclic Graph operations.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EdgeType(Enum):
    """Type of causal edge."""
    DIRECTED = "directed"      # X -> Y
    BIDIRECTED = "bidirected"  # X <-> Y (latent confounder)


@dataclass
class Node:
    """Node in causal graph."""
    name: str
    observed: bool = True
    node_type: str = "variable"  # variable, treatment, outcome, confounder
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """Edge in causal graph."""
    source: str
    target: str
    edge_type: EdgeType = EdgeType.DIRECTED
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class CausalDAG:
    """
    Causal Directed Acyclic Graph.

    Features:
    - Node and edge management
    - Path finding (d-separation)
    - Ancestor/descendant queries
    - Graph validation
    """

    def __init__(self):
        self._nodes: Dict[str, Node] = {}
        self._edges: List[Edge] = []
        self._adjacency: Dict[str, Set[str]] = {}
        self._reverse_adjacency: Dict[str, Set[str]] = {}

    def add_node(self,
                name: str,
                observed: bool = True,
                node_type: str = "variable",
                **metadata) -> Node:
        """Add node to graph."""
        node = Node(
            name=name,
            observed=observed,
            node_type=node_type,
            metadata=metadata
        )
        self._nodes[name] = node
        if name not in self._adjacency:
            self._adjacency[name] = set()
        if name not in self._reverse_adjacency:
            self._reverse_adjacency[name] = set()
        return node

    def add_edge(self,
                source: str,
                target: str,
                edge_type: EdgeType = EdgeType.DIRECTED,
                weight: float = 1.0,
                **metadata) -> Edge:
        """Add edge to graph."""
        # Auto-create nodes if needed
        if source not in self._nodes:
            self.add_node(source)
        if target not in self._nodes:
            self.add_node(target)

        edge = Edge(
            source=source,
            target=target,
            edge_type=edge_type,
            weight=weight,
            metadata=metadata
        )
        self._edges.append(edge)

        self._adjacency[source].add(target)
        self._reverse_adjacency[target].add(source)

        if edge_type == EdgeType.BIDIRECTED:
            # Bidirected edges go both ways
            self._adjacency[target].add(source)
            self._reverse_adjacency[source].add(target)

        return edge

    def get_node(self, name: str) -> Optional[Node]:
        """Get node by name."""
        return self._nodes.get(name)

    def get_nodes(self) -> List[Node]:
        """Get all nodes."""
        return list(self._nodes.values())

    def get_edges(self) -> List[Edge]:
        """Get all edges."""
        return self._edges

    def get_children(self, node: str) -> Set[str]:
        """Get direct children of node."""
        return self._adjacency.get(node, set()).copy()

    def get_parents(self, node: str) -> Set[str]:
        """Get direct parents of node."""
        return self._reverse_adjacency.get(node, set()).copy()

    def get_ancestors(self, node: str) -> Set[str]:
        """Get all ancestors of node."""
        ancestors = set()
        to_visit = list(self.get_parents(node))

        while to_visit:
            current = to_visit.pop()
            if current not in ancestors:
                ancestors.add(current)
                to_visit.extend(self.get_parents(current))

        return ancestors

    def get_descendants(self, node: str) -> Set[str]:
        """Get all descendants of node."""
        descendants = set()
        to_visit = list(self.get_children(node))

        while to_visit:
            current = to_visit.pop()
            if current not in descendants:
                descendants.add(current)
                to_visit.extend(self.get_children(current))

        return descendants

    def is_ancestor(self, node: str, potential_ancestor: str) -> bool:
        """Check if potential_ancestor is ancestor of node."""
        return potential_ancestor in self.get_ancestors(node)

    def is_descendant(self, node: str, potential_descendant: str) -> bool:
        """Check if potential_descendant is descendant of node."""
        return potential_descendant in self.get_descendants(node)

    def find_all_paths(self, source: str, target: str) -> List[List[str]]:
        """Find all directed paths from source to target."""
        paths = []

        def dfs(current: str, path: List[str]):
            if current == target:
                paths.append(path.copy())
                return

            for child in self.get_children(current):
                if child not in path:  # Avoid cycles
                    path.append(child)
                    dfs(child, path)
                    path.pop()

        dfs(source, [source])
        return paths

    def find_backdoor_paths(self, treatment: str, outcome: str) -> List[List[str]]:
        """Find all backdoor paths from treatment to outcome."""
        paths = []

        def dfs(current: str, path: List[str], direction: str):
            """
            direction: 'up' or 'down'
            Backdoor paths start going up (into treatment)
            """
            if current == outcome and len(path) > 1:
                paths.append(path.copy())
                return

            if current in path[:-1]:  # Already visited
                return

            if direction == 'up':
                # Can go up to parents
                for parent in self.get_parents(current):
                    if parent != treatment:  # Don't go back through treatment
                        path.append(parent)
                        dfs(parent, path, 'up')
                        path.pop()

                # Can switch to going down
                for child in self.get_children(current):
                    if child != treatment:
                        path.append(child)
                        dfs(child, path, 'down')
                        path.pop()
            else:  # going down
                for child in self.get_children(current):
                    path.append(child)
                    dfs(child, path, 'down')
                    path.pop()

        # Start from treatment, going up
        for parent in self.get_parents(treatment):
            dfs(parent, [treatment, parent], 'up')

        return paths

    def d_separated(self,
                   x: str,
                   y: str,
                   z: Set[str]) -> bool:
        """
        Check if X and Y are d-separated given Z.

        Uses the Bayes-Ball algorithm.
        """
        # Implementation of d-separation using path analysis
        # This is a simplified version

        # Find all paths between X and Y
        all_paths = self._find_all_undirected_paths(x, y)

        # Check if all paths are blocked by Z
        for path in all_paths:
            if not self._path_blocked(path, z):
                return False

        return True

    def _find_all_undirected_paths(self, source: str, target: str) -> List[List[str]]:
        """Find all paths (ignoring direction) between nodes."""
        paths = []

        def dfs(current: str, path: List[str]):
            if current == target:
                paths.append(path.copy())
                return

            # Get all neighbors (parents and children)
            neighbors = self.get_parents(current) | self.get_children(current)

            for neighbor in neighbors:
                if neighbor not in path:
                    path.append(neighbor)
                    dfs(neighbor, path)
                    path.pop()

        dfs(source, [source])
        return paths

    def _path_blocked(self, path: List[str], conditioning: Set[str]) -> bool:
        """Check if path is blocked by conditioning set."""
        if len(path) < 3:
            return False

        # Check each triple in the path
        for i in range(len(path) - 2):
            a, b, c = path[i], path[i+1], path[i+2]

            # Determine triple type
            a_to_b = b in self.get_children(a)
            b_to_c = c in self.get_children(b)

            if a_to_b and b_to_c:
                # Chain: A -> B -> C
                # Blocked if B in conditioning
                if b in conditioning:
                    return True
            elif not a_to_b and b_to_c:
                # Fork: A <- B -> C
                # Blocked if B in conditioning
                if b in conditioning:
                    return True
            elif a_to_b and not b_to_c:
                # Collider: A -> B <- C
                # Blocked if B NOT in conditioning and no descendant of B in conditioning
                b_descendants = self.get_descendants(b) | {b}
                if not (b_descendants & conditioning):
                    return True

        return False

    def is_valid_dag(self) -> bool:
        """Check if graph is a valid DAG (no cycles)."""
        # Topological sort to detect cycles
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for child in self.get_children(node):
                if child not in visited:
                    if has_cycle(child):
                        return True
                elif child in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in self._nodes:
            if node not in visited:
                if has_cycle(node):
                    return False

        return True

    def topological_sort(self) -> List[str]:
        """Get topological ordering of nodes."""
        visited = set()
        order = []

        def dfs(node: str):
            visited.add(node)
            for child in self.get_children(node):
                if child not in visited:
                    dfs(child)
            order.append(node)

        for node in self._nodes:
            if node not in visited:
                dfs(node)

        return list(reversed(order))

    def to_dict(self) -> Dict[str, Any]:
        """Export graph as dictionary."""
        return {
            'nodes': [
                {
                    'name': n.name,
                    'observed': n.observed,
                    'node_type': n.node_type,
                    'metadata': n.metadata
                }
                for n in self._nodes.values()
            ],
            'edges': [
                {
                    'source': e.source,
                    'target': e.target,
                    'edge_type': e.edge_type.value,
                    'weight': e.weight,
                    'metadata': e.metadata
                }
                for e in self._edges
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CausalDAG':
        """Import graph from dictionary."""
        dag = cls()

        for node_data in data.get('nodes', []):
            dag.add_node(
                name=node_data['name'],
                observed=node_data.get('observed', True),
                node_type=node_data.get('node_type', 'variable'),
                **node_data.get('metadata', {})
            )

        for edge_data in data.get('edges', []):
            dag.add_edge(
                source=edge_data['source'],
                target=edge_data['target'],
                edge_type=EdgeType(edge_data.get('edge_type', 'directed')),
                weight=edge_data.get('weight', 1.0),
                **edge_data.get('metadata', {})
            )

        return dag
