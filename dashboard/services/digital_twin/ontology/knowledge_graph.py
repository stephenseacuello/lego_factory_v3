"""
Knowledge Graph Service - Neo4j Integration for Manufacturing Digital Twins.

This module provides a graph database layer for manufacturing knowledge:
- Neo4j graph database integration
- Entity relationship management
- Graph traversal queries
- Pattern matching for root cause analysis

Research Value:
- Graph-based manufacturing knowledge representation
- Relationship-aware queries for digital thread
- Pattern detection for quality analytics
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set, Tuple, Union, Generator
from enum import Enum
from datetime import datetime
import json
import logging
from abc import ABC, abstractmethod
import hashlib

from .manufacturing_ontology import (
    ManufacturingOntology,
    OntologyClass,
    OntologyProperty,
    OntologyIndividual,
    ISO23247EntityType
)

logger = logging.getLogger(__name__)


# =============================================================================
# Graph Node and Edge Types
# =============================================================================

class NodeType(Enum):
    """Types of nodes in the knowledge graph."""
    # Products
    PRODUCT = "Product"
    LEGO_BRICK = "LegoBrick"
    PLATE = "Plate"
    TILE = "Tile"
    TECHNIC_BRICK = "TechnicBrick"

    # Processes
    PROCESS = "Process"
    FDM_PRINTING = "FDMPrinting"
    CNC_MILLING = "CNCMilling"
    QUALITY_INSPECTION = "QualityInspection"

    # Resources
    EQUIPMENT = "Equipment"
    FDM_PRINTER = "FDMPrinter"
    CNC_MILL = "CNCMill"
    MATERIAL = "Material"
    FILAMENT = "Filament"

    # Quality
    DEFECT = "Defect"
    MEASUREMENT = "Measurement"
    INSPECTION = "Inspection"

    # Sustainability
    ENVIRONMENTAL_IMPACT = "EnvironmentalImpact"
    CARBON_FOOTPRINT = "CarbonFootprint"
    ENERGY_CONSUMPTION = "EnergyConsumption"

    # Digital Twin
    DIGITAL_TWIN = "DigitalTwin"
    SENSOR = "Sensor"
    STATE_SNAPSHOT = "StateSnapshot"

    # Work Management
    WORK_ORDER = "WorkOrder"
    OPERATION = "Operation"
    BATCH = "Batch"


class EdgeType(Enum):
    """Types of edges in the knowledge graph."""
    # Production relationships
    PRODUCED_BY = "PRODUCED_BY"
    USES_EQUIPMENT = "USES_EQUIPMENT"
    USES_MATERIAL = "USES_MATERIAL"
    PART_OF_BATCH = "PART_OF_BATCH"

    # Quality relationships
    HAS_DEFECT = "HAS_DEFECT"
    INSPECTED_BY = "INSPECTED_BY"
    HAS_MEASUREMENT = "HAS_MEASUREMENT"
    CAUSED_BY = "CAUSED_BY"

    # Digital twin relationships
    HAS_DIGITAL_TWIN = "HAS_DIGITAL_TWIN"
    HAS_SENSOR = "HAS_SENSOR"
    HAS_STATE = "HAS_STATE"
    DERIVED_FROM = "DERIVED_FROM"

    # Sustainability
    HAS_ENVIRONMENTAL_IMPACT = "HAS_ENVIRONMENTAL_IMPACT"

    # Temporal
    FOLLOWS = "FOLLOWS"
    PRECEDES = "PRECEDES"

    # Hierarchy
    IS_A = "IS_A"
    CONTAINS = "CONTAINS"

    # Traceability
    USES_COMPONENT = "USES_COMPONENT"
    MADE_FROM = "MADE_FROM"


# =============================================================================
# Graph Node and Edge Classes
# =============================================================================

@dataclass
class GraphNode:
    """
    Node in the knowledge graph.

    Represents an entity with:
    - Unique identifier
    - Type (from NodeType enum)
    - Properties (key-value pairs)
    - Labels (for categorization)
    """
    id: str
    node_type: NodeType
    properties: Dict[str, Any] = field(default_factory=dict)
    labels: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        # Always include node type as a label
        if self.node_type.value not in self.labels:
            self.labels.append(self.node_type.value)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, GraphNode):
            return self.id == other.id
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'type': self.node_type.value,
            'labels': self.labels,
            'properties': self.properties,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GraphNode':
        """Create from dictionary representation."""
        return cls(
            id=data['id'],
            node_type=NodeType(data['type']),
            properties=data.get('properties', {}),
            labels=data.get('labels', []),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data['updated_at']) if 'updated_at' in data else datetime.utcnow()
        )


@dataclass
class GraphEdge:
    """
    Edge in the knowledge graph.

    Represents a relationship between nodes:
    - Source node
    - Target node
    - Relationship type
    - Properties (weight, timestamp, etc.)
    """
    source_id: str
    target_id: str
    edge_type: EdgeType
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def id(self) -> str:
        """Generate unique edge ID."""
        return f"{self.source_id}-[{self.edge_type.value}]->{self.target_id}"

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, GraphEdge):
            return self.id == other.id
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'source_id': self.source_id,
            'target_id': self.target_id,
            'type': self.edge_type.value,
            'properties': self.properties,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GraphEdge':
        """Create from dictionary representation."""
        return cls(
            source_id=data['source_id'],
            target_id=data['target_id'],
            edge_type=EdgeType(data['type']),
            properties=data.get('properties', {}),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.utcnow()
        )


# =============================================================================
# Graph Path and Pattern Types
# =============================================================================

@dataclass
class GraphPath:
    """A path through the graph (sequence of nodes and edges)."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]

    @property
    def length(self) -> int:
        """Number of edges in the path."""
        return len(self.edges)

    @property
    def start_node(self) -> GraphNode:
        """First node in the path."""
        return self.nodes[0] if self.nodes else None

    @property
    def end_node(self) -> GraphNode:
        """Last node in the path."""
        return self.nodes[-1] if self.nodes else None


@dataclass
class GraphPattern:
    """
    Pattern for graph matching.

    Used for:
    - Root cause analysis
    - Quality pattern detection
    - Traceability queries
    """
    node_patterns: List[Tuple[str, NodeType, Dict[str, Any]]]  # (var_name, type, property_filters)
    edge_patterns: List[Tuple[str, str, EdgeType]]  # (from_var, to_var, edge_type)

    def to_cypher(self) -> str:
        """Convert to Cypher pattern match query."""
        node_clauses = []
        for var, node_type, filters in self.node_patterns:
            filter_str = ", ".join(f"{k}: {repr(v)}" for k, v in filters.items())
            if filter_str:
                node_clauses.append(f"({var}:{node_type.value} {{{filter_str}}})")
            else:
                node_clauses.append(f"({var}:{node_type.value})")

        edge_clauses = []
        for from_var, to_var, edge_type in self.edge_patterns:
            edge_clauses.append(f"({from_var})-[:{edge_type.value}]->({to_var})")

        return "MATCH " + ", ".join(node_clauses + edge_clauses)


# =============================================================================
# Knowledge Graph Implementation
# =============================================================================

class KnowledgeGraph:
    """
    Knowledge Graph for Manufacturing Digital Twins.

    Provides:
    - In-memory graph storage (with optional Neo4j backend)
    - Node and edge CRUD operations
    - Graph traversal algorithms
    - Pattern matching for analytics
    - Cypher query generation

    Research Features:
    - Root cause analysis via graph traversal
    - Digital thread traceability
    - Quality pattern detection
    - Sustainability impact propagation
    """

    def __init__(self, ontology: ManufacturingOntology = None, neo4j_uri: str = None):
        """
        Initialize knowledge graph.

        Args:
            ontology: Manufacturing ontology for semantic validation
            neo4j_uri: Optional Neo4j connection URI (bolt://host:port)
        """
        self.ontology = ontology or ManufacturingOntology()
        self.neo4j_uri = neo4j_uri

        # In-memory storage
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, GraphEdge] = {}

        # Indexes for efficient lookup
        self._nodes_by_type: Dict[NodeType, Set[str]] = {t: set() for t in NodeType}
        self._edges_by_type: Dict[EdgeType, Set[str]] = {t: set() for t in EdgeType}
        self._outgoing_edges: Dict[str, Set[str]] = {}  # node_id -> set of edge_ids
        self._incoming_edges: Dict[str, Set[str]] = {}  # node_id -> set of edge_ids

        # Neo4j driver (lazy initialization)
        self._neo4j_driver = None

    # -------------------------------------------------------------------------
    # Node Operations
    # -------------------------------------------------------------------------

    def add_node(self, node: GraphNode) -> GraphNode:
        """Add a node to the graph."""
        self._nodes[node.id] = node
        self._nodes_by_type[node.node_type].add(node.id)
        self._outgoing_edges.setdefault(node.id, set())
        self._incoming_edges.setdefault(node.id, set())

        logger.debug(f"Added node: {node.id} ({node.node_type.value})")
        return node

    def create_node(
        self,
        node_id: str,
        node_type: NodeType,
        properties: Dict[str, Any] = None,
        labels: List[str] = None
    ) -> GraphNode:
        """Create and add a new node."""
        node = GraphNode(
            id=node_id,
            node_type=node_type,
            properties=properties or {},
            labels=labels or []
        )
        return self.add_node(node)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def update_node(self, node_id: str, properties: Dict[str, Any]) -> Optional[GraphNode]:
        """Update node properties."""
        node = self._nodes.get(node_id)
        if node:
            node.properties.update(properties)
            node.updated_at = datetime.utcnow()
        return node

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and its edges."""
        if node_id not in self._nodes:
            return False

        node = self._nodes[node_id]

        # Remove associated edges
        for edge_id in list(self._outgoing_edges.get(node_id, set())):
            self.delete_edge(edge_id)
        for edge_id in list(self._incoming_edges.get(node_id, set())):
            self.delete_edge(edge_id)

        # Remove from indexes
        self._nodes_by_type[node.node_type].discard(node_id)
        del self._outgoing_edges[node_id]
        del self._incoming_edges[node_id]
        del self._nodes[node_id]

        logger.debug(f"Deleted node: {node_id}")
        return True

    def get_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        """Get all nodes of a specific type."""
        return [self._nodes[nid] for nid in self._nodes_by_type[node_type]]

    def find_nodes(
        self,
        node_type: NodeType = None,
        properties: Dict[str, Any] = None,
        labels: List[str] = None
    ) -> List[GraphNode]:
        """Find nodes matching criteria."""
        results = []

        candidates = (
            self._nodes_by_type[node_type] if node_type
            else set(self._nodes.keys())
        )

        for node_id in candidates:
            node = self._nodes[node_id]

            # Check type
            if node_type and node.node_type != node_type:
                continue

            # Check properties
            if properties:
                if not all(node.properties.get(k) == v for k, v in properties.items()):
                    continue

            # Check labels
            if labels:
                if not all(l in node.labels for l in labels):
                    continue

            results.append(node)

        return results

    # -------------------------------------------------------------------------
    # Edge Operations
    # -------------------------------------------------------------------------

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        """Add an edge to the graph."""
        # Verify nodes exist
        if edge.source_id not in self._nodes:
            raise ValueError(f"Source node not found: {edge.source_id}")
        if edge.target_id not in self._nodes:
            raise ValueError(f"Target node not found: {edge.target_id}")

        self._edges[edge.id] = edge
        self._edges_by_type[edge.edge_type].add(edge.id)
        self._outgoing_edges[edge.source_id].add(edge.id)
        self._incoming_edges[edge.target_id].add(edge.id)

        logger.debug(f"Added edge: {edge.id}")
        return edge

    def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        properties: Dict[str, Any] = None
    ) -> GraphEdge:
        """Create and add a new edge."""
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            properties=properties or {}
        )
        return self.add_edge(edge)

    def get_edge(self, edge_id: str) -> Optional[GraphEdge]:
        """Get an edge by ID."""
        return self._edges.get(edge_id)

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        if edge_id not in self._edges:
            return False

        edge = self._edges[edge_id]
        self._edges_by_type[edge.edge_type].discard(edge_id)
        self._outgoing_edges[edge.source_id].discard(edge_id)
        self._incoming_edges[edge.target_id].discard(edge_id)
        del self._edges[edge_id]

        logger.debug(f"Deleted edge: {edge_id}")
        return True

    def get_edges_between(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType = None
    ) -> List[GraphEdge]:
        """Get edges between two nodes."""
        results = []
        for edge_id in self._outgoing_edges.get(source_id, set()):
            edge = self._edges[edge_id]
            if edge.target_id == target_id:
                if edge_type is None or edge.edge_type == edge_type:
                    results.append(edge)
        return results

    def get_neighbors(
        self,
        node_id: str,
        edge_type: EdgeType = None,
        direction: str = 'outgoing'
    ) -> List[GraphNode]:
        """Get neighboring nodes."""
        edge_ids = (
            self._outgoing_edges.get(node_id, set()) if direction == 'outgoing'
            else self._incoming_edges.get(node_id, set()) if direction == 'incoming'
            else self._outgoing_edges.get(node_id, set()) | self._incoming_edges.get(node_id, set())
        )

        neighbors = []
        for edge_id in edge_ids:
            edge = self._edges[edge_id]
            if edge_type is None or edge.edge_type == edge_type:
                neighbor_id = edge.target_id if direction == 'outgoing' else edge.source_id
                if neighbor_id != node_id:  # Avoid self-loops in 'both' direction
                    neighbors.append(self._nodes[neighbor_id])

        return neighbors

    # -------------------------------------------------------------------------
    # Graph Traversal Algorithms
    # -------------------------------------------------------------------------

    def bfs(
        self,
        start_id: str,
        max_depth: int = None,
        edge_types: List[EdgeType] = None,
        node_types: List[NodeType] = None
    ) -> Generator[Tuple[GraphNode, int], None, None]:
        """
        Breadth-first search from a starting node.

        Yields:
            Tuple of (node, depth) for each visited node
        """
        if start_id not in self._nodes:
            return

        visited = {start_id}
        queue = [(start_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)
            current_node = self._nodes[current_id]

            # Check node type filter
            if node_types is None or current_node.node_type in node_types:
                yield (current_node, depth)

            # Check depth limit
            if max_depth is not None and depth >= max_depth:
                continue

            # Explore neighbors
            for edge_id in self._outgoing_edges.get(current_id, set()):
                edge = self._edges[edge_id]

                # Check edge type filter
                if edge_types is not None and edge.edge_type not in edge_types:
                    continue

                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append((edge.target_id, depth + 1))

    def dfs(
        self,
        start_id: str,
        max_depth: int = None,
        edge_types: List[EdgeType] = None
    ) -> Generator[GraphNode, None, None]:
        """
        Depth-first search from a starting node.

        Yields:
            Each visited node
        """
        if start_id not in self._nodes:
            return

        visited = set()
        stack = [(start_id, 0)]

        while stack:
            current_id, depth = stack.pop()

            if current_id in visited:
                continue

            visited.add(current_id)
            yield self._nodes[current_id]

            if max_depth is not None and depth >= max_depth:
                continue

            for edge_id in self._outgoing_edges.get(current_id, set()):
                edge = self._edges[edge_id]

                if edge_types is not None and edge.edge_type not in edge_types:
                    continue

                if edge.target_id not in visited:
                    stack.append((edge.target_id, depth + 1))

    def find_shortest_path(
        self,
        start_id: str,
        end_id: str,
        edge_types: List[EdgeType] = None
    ) -> Optional[GraphPath]:
        """
        Find shortest path between two nodes using BFS.

        Returns:
            GraphPath if path exists, None otherwise
        """
        if start_id not in self._nodes or end_id not in self._nodes:
            return None

        if start_id == end_id:
            return GraphPath(nodes=[self._nodes[start_id]], edges=[])

        visited = {start_id}
        queue = [(start_id, [start_id], [])]

        while queue:
            current_id, path_nodes, path_edges = queue.pop(0)

            for edge_id in self._outgoing_edges.get(current_id, set()):
                edge = self._edges[edge_id]

                if edge_types is not None and edge.edge_type not in edge_types:
                    continue

                if edge.target_id == end_id:
                    return GraphPath(
                        nodes=[self._nodes[nid] for nid in path_nodes + [end_id]],
                        edges=[self._edges[eid] for eid in path_edges + [edge_id]]
                    )

                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append((
                        edge.target_id,
                        path_nodes + [edge.target_id],
                        path_edges + [edge_id]
                    ))

        return None

    def find_all_paths(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 10,
        edge_types: List[EdgeType] = None
    ) -> List[GraphPath]:
        """
        Find all paths between two nodes (up to max depth).

        Returns:
            List of GraphPath objects
        """
        if start_id not in self._nodes or end_id not in self._nodes:
            return []

        paths = []
        stack = [(start_id, [start_id], [], set([start_id]))]

        while stack:
            current_id, path_nodes, path_edges, visited = stack.pop()

            if len(path_nodes) > max_depth + 1:
                continue

            for edge_id in self._outgoing_edges.get(current_id, set()):
                edge = self._edges[edge_id]

                if edge_types is not None and edge.edge_type not in edge_types:
                    continue

                if edge.target_id == end_id:
                    paths.append(GraphPath(
                        nodes=[self._nodes[nid] for nid in path_nodes + [end_id]],
                        edges=[self._edges[eid] for eid in path_edges + [edge_id]]
                    ))
                elif edge.target_id not in visited:
                    new_visited = visited | {edge.target_id}
                    stack.append((
                        edge.target_id,
                        path_nodes + [edge.target_id],
                        path_edges + [edge_id],
                        new_visited
                    ))

        return paths

    # -------------------------------------------------------------------------
    # Pattern Matching (Research Feature)
    # -------------------------------------------------------------------------

    def match_pattern(self, pattern: GraphPattern) -> List[Dict[str, GraphNode]]:
        """
        Match a graph pattern and return variable bindings.

        Research Application:
        - Detect quality issue patterns
        - Find root cause chains
        - Identify sustainability impact paths
        """
        results = []

        # Start with first node pattern
        if not pattern.node_patterns:
            return results

        first_var, first_type, first_filters = pattern.node_patterns[0]
        candidates = self.find_nodes(node_type=first_type, properties=first_filters)

        for candidate in candidates:
            bindings = {first_var: candidate}
            if self._extend_pattern_match(pattern, bindings, 1):
                results.append(bindings.copy())

        return results

    def _extend_pattern_match(
        self,
        pattern: GraphPattern,
        bindings: Dict[str, GraphNode],
        next_node_idx: int
    ) -> bool:
        """Recursively extend pattern match."""
        # Check all node patterns are bound
        if next_node_idx >= len(pattern.node_patterns):
            # Verify all edge patterns
            for from_var, to_var, edge_type in pattern.edge_patterns:
                if from_var not in bindings or to_var not in bindings:
                    return False
                edges = self.get_edges_between(
                    bindings[from_var].id,
                    bindings[to_var].id,
                    edge_type
                )
                if not edges:
                    return False
            return True

        # Try to bind next node
        var, node_type, filters = pattern.node_patterns[next_node_idx]

        # Check if constrained by edge patterns
        for from_var, to_var, edge_type in pattern.edge_patterns:
            if to_var == var and from_var in bindings:
                # Find via outgoing edge
                neighbors = self.get_neighbors(
                    bindings[from_var].id,
                    edge_type=edge_type,
                    direction='outgoing'
                )
                for neighbor in neighbors:
                    if neighbor.node_type == node_type:
                        if all(neighbor.properties.get(k) == v for k, v in filters.items()):
                            bindings[var] = neighbor
                            if self._extend_pattern_match(pattern, bindings, next_node_idx + 1):
                                return True
                            del bindings[var]
                return False

            if from_var == var and to_var in bindings:
                # Find via incoming edge
                neighbors = self.get_neighbors(
                    bindings[to_var].id,
                    edge_type=edge_type,
                    direction='incoming'
                )
                for neighbor in neighbors:
                    if neighbor.node_type == node_type:
                        if all(neighbor.properties.get(k) == v for k, v in filters.items()):
                            bindings[var] = neighbor
                            if self._extend_pattern_match(pattern, bindings, next_node_idx + 1):
                                return True
                            del bindings[var]
                return False

        # No edge constraint, try all nodes of type
        for node in self.find_nodes(node_type=node_type, properties=filters):
            bindings[var] = node
            if self._extend_pattern_match(pattern, bindings, next_node_idx + 1):
                return True
            del bindings[var]

        return False

    # -------------------------------------------------------------------------
    # Manufacturing-Specific Queries
    # -------------------------------------------------------------------------

    def trace_product_genealogy(self, product_id: str) -> Dict[str, Any]:
        """
        Trace the complete genealogy of a product.

        Returns:
        - Materials used
        - Processes involved
        - Equipment used
        - Quality inspections
        - Environmental impacts
        """
        genealogy = {
            'product_id': product_id,
            'materials': [],
            'processes': [],
            'equipment': [],
            'inspections': [],
            'defects': [],
            'environmental_impacts': []
        }

        product = self.get_node(product_id)
        if not product:
            return genealogy

        # Find all connected nodes via BFS
        for node, depth in self.bfs(product_id, max_depth=5):
            if node.node_type in [NodeType.MATERIAL, NodeType.FILAMENT]:
                genealogy['materials'].append(node.to_dict())
            elif node.node_type in [NodeType.PROCESS, NodeType.FDM_PRINTING, NodeType.CNC_MILLING]:
                genealogy['processes'].append(node.to_dict())
            elif node.node_type in [NodeType.EQUIPMENT, NodeType.FDM_PRINTER, NodeType.CNC_MILL]:
                genealogy['equipment'].append(node.to_dict())
            elif node.node_type == NodeType.INSPECTION:
                genealogy['inspections'].append(node.to_dict())
            elif node.node_type == NodeType.DEFECT:
                genealogy['defects'].append(node.to_dict())
            elif node.node_type in [NodeType.CARBON_FOOTPRINT, NodeType.ENERGY_CONSUMPTION]:
                genealogy['environmental_impacts'].append(node.to_dict())

        return genealogy

    def find_defect_root_causes(
        self,
        defect_id: str,
        max_depth: int = 5
    ) -> List[GraphPath]:
        """
        Find potential root causes for a defect by traversing CAUSED_BY edges.

        Research Application:
        - Root cause analysis for quality issues
        - Correlation of process parameters with defects
        """
        defect = self.get_node(defect_id)
        if not defect or defect.node_type != NodeType.DEFECT:
            return []

        root_causes = []

        # Traverse CAUSED_BY edges backwards
        for node, depth in self.bfs(defect_id, max_depth=max_depth, edge_types=[EdgeType.CAUSED_BY]):
            if node.id != defect_id:
                path = self.find_shortest_path(
                    defect_id, node.id,
                    edge_types=[EdgeType.CAUSED_BY]
                )
                if path:
                    root_causes.append(path)

        return root_causes

    def calculate_sustainability_impact(self, node_id: str) -> Dict[str, float]:
        """
        Calculate total sustainability impact for a node and its downstream.

        Returns:
        - total_carbon_kg: Total CO2 emissions
        - total_energy_kwh: Total energy consumption
        - total_waste_kg: Total material waste
        """
        totals = {
            'total_carbon_kg': 0.0,
            'total_energy_kwh': 0.0,
            'total_waste_kg': 0.0
        }

        for node, _ in self.bfs(node_id, edge_types=[EdgeType.HAS_ENVIRONMENTAL_IMPACT]):
            if node.node_type == NodeType.CARBON_FOOTPRINT:
                totals['total_carbon_kg'] += node.properties.get('value', 0.0)
            elif node.node_type == NodeType.ENERGY_CONSUMPTION:
                totals['total_energy_kwh'] += node.properties.get('value', 0.0)
            elif 'waste' in node.properties:
                totals['total_waste_kg'] += node.properties.get('waste', 0.0)

        return totals

    # -------------------------------------------------------------------------
    # Cypher Query Generation (for Neo4j)
    # -------------------------------------------------------------------------

    def to_cypher_create(self) -> str:
        """Generate Cypher CREATE statements for the graph."""
        statements = []

        # Create nodes
        for node in self._nodes.values():
            labels = ':'.join(node.labels)
            props = json.dumps(node.properties)
            statements.append(f"CREATE (n:{labels} {{id: '{node.id}', properties: {props}}})")

        # Create edges
        for edge in self._edges.values():
            statements.append(
                f"MATCH (a {{id: '{edge.source_id}'}}), (b {{id: '{edge.target_id}'}}) "
                f"CREATE (a)-[:{edge.edge_type.value}]->(b)"
            )

        return ';\n'.join(statements)

    def query_cypher(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query against Neo4j.

        Note: Requires Neo4j driver to be installed and configured.
        """
        if not self._neo4j_driver:
            logger.warning("Neo4j driver not initialized, using in-memory only")
            return []

        try:
            with self._neo4j_driver.session() as session:
                result = session.run(query)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Cypher query failed: {e}")
            return []

    # -------------------------------------------------------------------------
    # Import/Export
    # -------------------------------------------------------------------------

    def export_json(self) -> Dict[str, Any]:
        """Export graph to JSON format."""
        return {
            'nodes': [n.to_dict() for n in self._nodes.values()],
            'edges': [e.to_dict() for e in self._edges.values()]
        }

    def import_json(self, data: Dict[str, Any]):
        """Import graph from JSON format."""
        self.clear()

        for node_data in data.get('nodes', []):
            node = GraphNode.from_dict(node_data)
            self.add_node(node)

        for edge_data in data.get('edges', []):
            edge = GraphEdge.from_dict(edge_data)
            self.add_edge(edge)

    def clear(self):
        """Clear all nodes and edges."""
        self._nodes.clear()
        self._edges.clear()
        for node_type in NodeType:
            self._nodes_by_type[node_type].clear()
        for edge_type in EdgeType:
            self._edges_by_type[edge_type].clear()
        self._outgoing_edges.clear()
        self._incoming_edges.clear()

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        return {
            'total_nodes': len(self._nodes),
            'total_edges': len(self._edges),
            'nodes_by_type': {t.value: len(ids) for t, ids in self._nodes_by_type.items() if ids},
            'edges_by_type': {t.value: len(ids) for t, ids in self._edges_by_type.items() if ids},
            'avg_degree': sum(len(e) for e in self._outgoing_edges.values()) / max(1, len(self._nodes))
        }
