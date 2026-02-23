"""
Supply Chain Digital Twin Service
=================================

Digital twin of the supply chain network for visibility and simulation.

Features:
- Supplier node modeling and connectivity
- Material flow simulation
- Risk propagation analysis
- Inventory visualization
- Lead time prediction
- Disruption scenario simulation

ISO 23247 Compliance:
- Observable Manufacturing Element for supply chain nodes
- Real-time state synchronization
- Event-driven updates

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import threading
import logging
import json
import uuid
import heapq
import random

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Types of supply chain nodes."""
    SUPPLIER = "supplier"
    MANUFACTURER = "manufacturer"
    WAREHOUSE = "warehouse"
    DISTRIBUTION_CENTER = "distribution_center"
    RETAILER = "retailer"
    CUSTOMER = "customer"
    TRANSPORT_HUB = "transport_hub"


class NodeStatus(Enum):
    """Status of supply chain node."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISRUPTED = "disrupted"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class TransportMode(Enum):
    """Transportation modes."""
    TRUCK = "truck"
    RAIL = "rail"
    SHIP = "ship"
    AIR = "air"
    PIPELINE = "pipeline"
    MULTIMODAL = "multimodal"


class RiskCategory(Enum):
    """Risk categories for supply chain."""
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    GEOPOLITICAL = "geopolitical"
    NATURAL_DISASTER = "natural_disaster"
    CYBER = "cyber"
    QUALITY = "quality"
    CAPACITY = "capacity"
    LOGISTICS = "logistics"


class MaterialCategory(Enum):
    """Material categories."""
    RAW_MATERIAL = "raw_material"
    COMPONENT = "component"
    SUBASSEMBLY = "subassembly"
    FINISHED_GOOD = "finished_good"
    PACKAGING = "packaging"
    CONSUMABLE = "consumable"


@dataclass
class GeoLocation:
    """Geographic location."""
    latitude: float
    longitude: float
    country: str
    region: str = ""
    city: str = ""
    timezone: str = "UTC"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'country': self.country,
            'region': self.region,
            'city': self.city,
            'timezone': self.timezone
        }

    def distance_to(self, other: 'GeoLocation') -> float:
        """Calculate approximate distance in km using Haversine formula."""
        import math
        R = 6371  # Earth's radius in km

        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        return R * c


@dataclass
class Material:
    """Material or product in supply chain."""
    id: str
    name: str
    sku: str
    category: MaterialCategory
    unit_of_measure: str
    unit_cost: float
    unit_weight_kg: float
    lead_time_days: float
    minimum_order_qty: int = 1
    shelf_life_days: Optional[int] = None
    hazmat: bool = False
    temperature_sensitive: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'sku': self.sku,
            'category': self.category.value,
            'unit_of_measure': self.unit_of_measure,
            'unit_cost': self.unit_cost,
            'unit_weight_kg': self.unit_weight_kg,
            'lead_time_days': self.lead_time_days,
            'minimum_order_qty': self.minimum_order_qty,
            'shelf_life_days': self.shelf_life_days,
            'hazmat': self.hazmat
        }


@dataclass
class InventoryLevel:
    """Inventory level at a node."""
    material_id: str
    quantity: float
    reserved_quantity: float = 0
    incoming_quantity: float = 0
    reorder_point: float = 0
    max_level: float = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    @property
    def available_quantity(self) -> float:
        return self.quantity - self.reserved_quantity

    @property
    def needs_reorder(self) -> bool:
        return self.available_quantity <= self.reorder_point

    def to_dict(self) -> Dict[str, Any]:
        return {
            'material_id': self.material_id,
            'quantity': self.quantity,
            'reserved_quantity': self.reserved_quantity,
            'incoming_quantity': self.incoming_quantity,
            'available_quantity': self.available_quantity,
            'reorder_point': self.reorder_point,
            'max_level': self.max_level,
            'needs_reorder': self.needs_reorder,
            'last_updated': self.last_updated.isoformat()
        }


@dataclass
class RiskFactor:
    """Risk factor affecting supply chain."""
    id: str
    category: RiskCategory
    name: str
    description: str
    probability: float  # 0-1
    impact: float  # 0-1
    affected_node_ids: List[str] = field(default_factory=list)
    mitigation_strategies: List[str] = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    @property
    def risk_score(self) -> float:
        return self.probability * self.impact * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'category': self.category.value,
            'name': self.name,
            'description': self.description,
            'probability': self.probability,
            'impact': self.impact,
            'risk_score': self.risk_score,
            'affected_node_ids': self.affected_node_ids,
            'mitigation_strategies': self.mitigation_strategies,
            'detected_at': self.detected_at.isoformat()
        }


@dataclass
class SupplyChainNode:
    """Node in the supply chain network."""
    id: str
    name: str
    node_type: NodeType
    status: NodeStatus
    location: GeoLocation
    capacity: float  # Units per day
    current_utilization: float = 0.0  # 0-1
    reliability_score: float = 1.0  # 0-1
    inventory: Dict[str, InventoryLevel] = field(default_factory=dict)
    operating_hours: Dict[str, str] = field(default_factory=dict)
    contacts: List[Dict[str, str]] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)  # Risk IDs
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'node_type': self.node_type.value,
            'status': self.status.value,
            'location': self.location.to_dict(),
            'capacity': self.capacity,
            'current_utilization': self.current_utilization,
            'reliability_score': self.reliability_score,
            'inventory': {k: v.to_dict() for k, v in self.inventory.items()},
            'certifications': self.certifications,
            'risk_factors': self.risk_factors,
            'updated_at': self.updated_at.isoformat()
        }


@dataclass
class SupplyChainEdge:
    """Edge (connection) between supply chain nodes."""
    id: str
    source_node_id: str
    target_node_id: str
    transport_mode: TransportMode
    lead_time_days: float
    cost_per_unit: float
    capacity_per_day: float
    current_utilization: float = 0.0
    reliability_score: float = 1.0
    distance_km: float = 0.0
    active: bool = True
    schedule: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'source_node_id': self.source_node_id,
            'target_node_id': self.target_node_id,
            'transport_mode': self.transport_mode.value,
            'lead_time_days': self.lead_time_days,
            'cost_per_unit': self.cost_per_unit,
            'capacity_per_day': self.capacity_per_day,
            'current_utilization': self.current_utilization,
            'reliability_score': self.reliability_score,
            'distance_km': self.distance_km,
            'active': self.active
        }


@dataclass
class Shipment:
    """Active shipment in transit."""
    id: str
    edge_id: str
    material_id: str
    quantity: float
    departed_at: datetime
    expected_arrival: datetime
    actual_arrival: Optional[datetime] = None
    status: str = "in_transit"
    tracking_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'edge_id': self.edge_id,
            'material_id': self.material_id,
            'quantity': self.quantity,
            'departed_at': self.departed_at.isoformat(),
            'expected_arrival': self.expected_arrival.isoformat(),
            'actual_arrival': self.actual_arrival.isoformat() if self.actual_arrival else None,
            'status': self.status,
            'tracking_events': self.tracking_events
        }


@dataclass
class DisruptionScenario:
    """Simulated disruption scenario."""
    id: str
    name: str
    description: str
    affected_nodes: List[str]
    affected_edges: List[str]
    duration_days: float
    impact_factor: float  # 0-1, how much capacity is reduced
    risk_category: RiskCategory
    probability: float
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'affected_nodes': self.affected_nodes,
            'affected_edges': self.affected_edges,
            'duration_days': self.duration_days,
            'impact_factor': self.impact_factor,
            'risk_category': self.risk_category.value,
            'probability': self.probability
        }


class MaterialFlowSimulator:
    """Simulates material flow through supply chain."""

    def __init__(self, nodes: Dict[str, SupplyChainNode], edges: Dict[str, SupplyChainEdge]):
        self._nodes = nodes
        self._edges = edges
        self._shipments: Dict[str, Shipment] = {}

    def simulate_flow(
        self,
        material_id: str,
        source_node_id: str,
        target_node_id: str,
        quantity: float,
        start_time: datetime = None
    ) -> Optional[Shipment]:
        """Simulate material flow from source to target."""
        start_time = start_time or datetime.utcnow()

        # Find path
        path = self._find_path(source_node_id, target_node_id)
        if not path:
            logger.warning(f"No path from {source_node_id} to {target_node_id}")
            return None

        # Calculate total lead time
        total_lead_time = 0
        for edge_id in path:
            edge = self._edges.get(edge_id)
            if edge:
                total_lead_time += edge.lead_time_days

        expected_arrival = start_time + timedelta(days=total_lead_time)

        shipment = Shipment(
            id=str(uuid.uuid4()),
            edge_id=path[0] if path else "",
            material_id=material_id,
            quantity=quantity,
            departed_at=start_time,
            expected_arrival=expected_arrival,
            tracking_events=[{
                'event': 'departed',
                'timestamp': start_time.isoformat(),
                'location': source_node_id
            }]
        )

        self._shipments[shipment.id] = shipment
        return shipment

    def _find_path(self, source: str, target: str) -> List[str]:
        """Find shortest path using Dijkstra's algorithm."""
        distances: Dict[str, float] = {source: 0}
        previous: Dict[str, Tuple[str, str]] = {}
        pq = [(0, source)]
        visited: Set[str] = set()

        # Build adjacency
        adjacency: Dict[str, List[Tuple[str, str, float]]] = {}
        for edge_id, edge in self._edges.items():
            if edge.active:
                if edge.source_node_id not in adjacency:
                    adjacency[edge.source_node_id] = []
                adjacency[edge.source_node_id].append((
                    edge.target_node_id,
                    edge_id,
                    edge.lead_time_days
                ))

        while pq:
            current_dist, current = heapq.heappop(pq)

            if current in visited:
                continue
            visited.add(current)

            if current == target:
                # Reconstruct path
                path = []
                node = target
                while node in previous:
                    prev_node, edge_id = previous[node]
                    path.append(edge_id)
                    node = prev_node
                path.reverse()
                return path

            for neighbor, edge_id, weight in adjacency.get(current, []):
                distance = current_dist + weight
                if neighbor not in distances or distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous[neighbor] = (current, edge_id)
                    heapq.heappush(pq, (distance, neighbor))

        return []

    def get_active_shipments(self) -> List[Shipment]:
        """Get all active shipments."""
        return [s for s in self._shipments.values() if s.status == "in_transit"]


class RiskPropagationEngine:
    """Analyzes risk propagation through supply chain."""

    def __init__(self, nodes: Dict[str, SupplyChainNode], edges: Dict[str, SupplyChainEdge]):
        self._nodes = nodes
        self._edges = edges

    def propagate_risk(
        self,
        risk: RiskFactor,
        propagation_factor: float = 0.5
    ) -> Dict[str, float]:
        """Propagate risk through connected nodes."""
        affected_scores: Dict[str, float] = {}

        # Direct impact
        for node_id in risk.affected_node_ids:
            affected_scores[node_id] = risk.risk_score

        # Propagate to connected nodes
        visited: Set[str] = set(risk.affected_node_ids)
        current_level = set(risk.affected_node_ids)
        current_factor = propagation_factor

        while current_level and current_factor > 0.1:
            next_level: Set[str] = set()

            for node_id in current_level:
                # Find connected nodes
                for edge in self._edges.values():
                    if edge.source_node_id == node_id and edge.target_node_id not in visited:
                        next_level.add(edge.target_node_id)
                        affected_scores[edge.target_node_id] = risk.risk_score * current_factor
                    elif edge.target_node_id == node_id and edge.source_node_id not in visited:
                        next_level.add(edge.source_node_id)
                        affected_scores[edge.source_node_id] = risk.risk_score * current_factor

            visited.update(next_level)
            current_level = next_level
            current_factor *= propagation_factor

        return affected_scores

    def analyze_single_point_failures(self) -> List[Dict[str, Any]]:
        """Identify single points of failure in supply chain."""
        failures = []

        for node_id, node in self._nodes.items():
            # Check if node is critical (only path for materials)
            incoming_edges = [e for e in self._edges.values() if e.target_node_id == node_id and e.active]
            outgoing_edges = [e for e in self._edges.values() if e.source_node_id == node_id and e.active]

            if len(incoming_edges) == 1 or len(outgoing_edges) == 1:
                failures.append({
                    'node_id': node_id,
                    'node_name': node.name,
                    'incoming_count': len(incoming_edges),
                    'outgoing_count': len(outgoing_edges),
                    'criticality': 'high' if len(incoming_edges) == 1 and len(outgoing_edges) == 1 else 'medium'
                })

        return failures

    def simulate_disruption(
        self,
        scenario: DisruptionScenario
    ) -> Dict[str, Any]:
        """Simulate disruption scenario and calculate impact."""
        impact = {
            'scenario_id': scenario.id,
            'affected_capacity': 0.0,
            'affected_inventory_value': 0.0,
            'recovery_time_days': scenario.duration_days,
            'node_impacts': {},
            'edge_impacts': {},
            'alternative_routes': []
        }

        # Calculate node impacts
        for node_id in scenario.affected_nodes:
            node = self._nodes.get(node_id)
            if node:
                capacity_loss = node.capacity * scenario.impact_factor
                impact['affected_capacity'] += capacity_loss
                impact['node_impacts'][node_id] = {
                    'capacity_loss': capacity_loss,
                    'original_capacity': node.capacity,
                    'utilization_before': node.current_utilization
                }

                # Calculate inventory at risk
                for inv in node.inventory.values():
                    impact['affected_inventory_value'] += inv.quantity * 10  # Simplified value

        # Calculate edge impacts
        for edge_id in scenario.affected_edges:
            edge = self._edges.get(edge_id)
            if edge:
                impact['edge_impacts'][edge_id] = {
                    'capacity_loss': edge.capacity_per_day * scenario.impact_factor,
                    'original_capacity': edge.capacity_per_day,
                    'lead_time_increase': edge.lead_time_days * 0.5
                }

        # Find alternative routes
        for edge_id in scenario.affected_edges:
            edge = self._edges.get(edge_id)
            if edge:
                alt_route = self._find_alternative_route(
                    edge.source_node_id,
                    edge.target_node_id,
                    {edge_id}
                )
                if alt_route:
                    impact['alternative_routes'].append({
                        'original_edge': edge_id,
                        'alternative_path': alt_route['path'],
                        'additional_lead_time': alt_route['lead_time'] - edge.lead_time_days
                    })

        return impact

    def _find_alternative_route(
        self,
        source: str,
        target: str,
        excluded_edges: Set[str]
    ) -> Optional[Dict[str, Any]]:
        """Find alternative route excluding specified edges."""
        # Use Dijkstra with excluded edges
        distances: Dict[str, float] = {source: 0}
        previous: Dict[str, str] = {}
        pq = [(0, source)]
        visited: Set[str] = set()

        # Build adjacency excluding edges
        adjacency: Dict[str, List[Tuple[str, float]]] = {}
        for edge_id, edge in self._edges.items():
            if edge.active and edge_id not in excluded_edges:
                if edge.source_node_id not in adjacency:
                    adjacency[edge.source_node_id] = []
                adjacency[edge.source_node_id].append((edge.target_node_id, edge.lead_time_days))

        while pq:
            current_dist, current = heapq.heappop(pq)

            if current in visited:
                continue
            visited.add(current)

            if current == target:
                # Reconstruct path
                path = [target]
                node = target
                while node in previous:
                    node = previous[node]
                    path.append(node)
                path.reverse()
                return {'path': path, 'lead_time': current_dist}

            for neighbor, weight in adjacency.get(current, []):
                distance = current_dist + weight
                if neighbor not in distances or distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous[neighbor] = current
                    heapq.heappush(pq, (distance, neighbor))

        return None


class SupplyChainTwinService:
    """
    Digital Twin service for supply chain visibility and simulation.

    Provides:
    - Real-time supply chain visibility
    - Material flow simulation
    - Risk analysis and propagation
    - Inventory optimization
    - Disruption scenario simulation
    """

    def __init__(self):
        self._nodes: Dict[str, SupplyChainNode] = {}
        self._edges: Dict[str, SupplyChainEdge] = {}
        self._materials: Dict[str, Material] = {}
        self._risks: Dict[str, RiskFactor] = {}
        self._scenarios: Dict[str, DisruptionScenario] = {}

        self._flow_simulator: Optional[MaterialFlowSimulator] = None
        self._risk_engine: Optional[RiskPropagationEngine] = None

        self._lock = threading.RLock()

        # Initialize demo data
        self._initialize_demo_network()

        logger.info("SupplyChainTwinService initialized")

    def _initialize_demo_network(self):
        """Initialize demo supply chain network."""
        # Create sample nodes
        nodes = [
            SupplyChainNode(
                id="supplier_pla",
                name="PLA Filament Supplier",
                node_type=NodeType.SUPPLIER,
                status=NodeStatus.ACTIVE,
                location=GeoLocation(
                    latitude=31.2304,
                    longitude=121.4737,
                    country="China",
                    region="Shanghai",
                    city="Shanghai"
                ),
                capacity=10000,
                current_utilization=0.75,
                reliability_score=0.92,
                certifications=["ISO 9001", "RoHS"]
            ),
            SupplyChainNode(
                id="supplier_petg",
                name="PETG Filament Supplier",
                node_type=NodeType.SUPPLIER,
                status=NodeStatus.ACTIVE,
                location=GeoLocation(
                    latitude=35.6762,
                    longitude=139.6503,
                    country="Japan",
                    region="Tokyo",
                    city="Tokyo"
                ),
                capacity=5000,
                current_utilization=0.60,
                reliability_score=0.95,
                certifications=["ISO 9001", "ISO 14001"]
            ),
            SupplyChainNode(
                id="warehouse_west",
                name="West Coast Warehouse",
                node_type=NodeType.WAREHOUSE,
                status=NodeStatus.ACTIVE,
                location=GeoLocation(
                    latitude=34.0522,
                    longitude=-118.2437,
                    country="USA",
                    region="California",
                    city="Los Angeles"
                ),
                capacity=50000,
                current_utilization=0.45,
                reliability_score=0.98
            ),
            SupplyChainNode(
                id="mfg_main",
                name="Main Manufacturing Facility",
                node_type=NodeType.MANUFACTURER,
                status=NodeStatus.ACTIVE,
                location=GeoLocation(
                    latitude=37.7749,
                    longitude=-122.4194,
                    country="USA",
                    region="California",
                    city="San Francisco"
                ),
                capacity=1000,
                current_utilization=0.80,
                reliability_score=0.95,
                certifications=["ISO 9001", "ISO 13485"]
            ),
            SupplyChainNode(
                id="dc_central",
                name="Central Distribution Center",
                node_type=NodeType.DISTRIBUTION_CENTER,
                status=NodeStatus.ACTIVE,
                location=GeoLocation(
                    latitude=39.7392,
                    longitude=-104.9903,
                    country="USA",
                    region="Colorado",
                    city="Denver"
                ),
                capacity=25000,
                current_utilization=0.55,
                reliability_score=0.97
            )
        ]

        for node in nodes:
            self._nodes[node.id] = node

        # Create edges
        edges = [
            SupplyChainEdge(
                id="edge_pla_warehouse",
                source_node_id="supplier_pla",
                target_node_id="warehouse_west",
                transport_mode=TransportMode.SHIP,
                lead_time_days=21,
                cost_per_unit=0.15,
                capacity_per_day=500,
                distance_km=10000,
                reliability_score=0.90
            ),
            SupplyChainEdge(
                id="edge_petg_warehouse",
                source_node_id="supplier_petg",
                target_node_id="warehouse_west",
                transport_mode=TransportMode.SHIP,
                lead_time_days=14,
                cost_per_unit=0.20,
                capacity_per_day=300,
                distance_km=8500,
                reliability_score=0.92
            ),
            SupplyChainEdge(
                id="edge_warehouse_mfg",
                source_node_id="warehouse_west",
                target_node_id="mfg_main",
                transport_mode=TransportMode.TRUCK,
                lead_time_days=2,
                cost_per_unit=0.05,
                capacity_per_day=200,
                distance_km=600,
                reliability_score=0.98
            ),
            SupplyChainEdge(
                id="edge_mfg_dc",
                source_node_id="mfg_main",
                target_node_id="dc_central",
                transport_mode=TransportMode.TRUCK,
                lead_time_days=3,
                cost_per_unit=0.08,
                capacity_per_day=150,
                distance_km=1500,
                reliability_score=0.96
            )
        ]

        for edge in edges:
            self._edges[edge.id] = edge

        # Create materials
        materials = [
            Material(
                id="pla_white",
                name="PLA Filament White",
                sku="FIL-PLA-WHT-1KG",
                category=MaterialCategory.RAW_MATERIAL,
                unit_of_measure="kg",
                unit_cost=20.0,
                unit_weight_kg=1.0,
                lead_time_days=21,
                minimum_order_qty=10
            ),
            Material(
                id="petg_clear",
                name="PETG Filament Clear",
                sku="FIL-PETG-CLR-1KG",
                category=MaterialCategory.RAW_MATERIAL,
                unit_of_measure="kg",
                unit_cost=25.0,
                unit_weight_kg=1.0,
                lead_time_days=14,
                minimum_order_qty=5
            ),
            Material(
                id="lego_brick_2x4",
                name="LEGO Brick 2x4",
                sku="BRICK-2X4-WHT",
                category=MaterialCategory.FINISHED_GOOD,
                unit_of_measure="piece",
                unit_cost=0.10,
                unit_weight_kg=0.002,
                lead_time_days=1
            )
        ]

        for material in materials:
            self._materials[material.id] = material

        # Initialize simulators
        self._flow_simulator = MaterialFlowSimulator(self._nodes, self._edges)
        self._risk_engine = RiskPropagationEngine(self._nodes, self._edges)

    def add_node(self, node: SupplyChainNode):
        """Add a supply chain node."""
        with self._lock:
            self._nodes[node.id] = node
            self._rebuild_simulators()
            logger.info(f"Added supply chain node: {node.name}")

    def update_node(self, node: SupplyChainNode):
        """Update an existing node."""
        with self._lock:
            if node.id in self._nodes:
                node.updated_at = datetime.utcnow()
                self._nodes[node.id] = node
                logger.info(f"Updated supply chain node: {node.name}")

    def get_node(self, node_id: str) -> Optional[SupplyChainNode]:
        """Get node by ID."""
        with self._lock:
            return self._nodes.get(node_id)

    def list_nodes(
        self,
        node_type: Optional[NodeType] = None,
        status: Optional[NodeStatus] = None
    ) -> List[SupplyChainNode]:
        """List nodes with optional filtering."""
        with self._lock:
            nodes = list(self._nodes.values())

            if node_type:
                nodes = [n for n in nodes if n.node_type == node_type]
            if status:
                nodes = [n for n in nodes if n.status == status]

            return nodes

    def add_edge(self, edge: SupplyChainEdge):
        """Add a supply chain edge."""
        with self._lock:
            self._edges[edge.id] = edge
            self._rebuild_simulators()
            logger.info(f"Added supply chain edge: {edge.id}")

    def get_edge(self, edge_id: str) -> Optional[SupplyChainEdge]:
        """Get edge by ID."""
        with self._lock:
            return self._edges.get(edge_id)

    def list_edges(self, node_id: Optional[str] = None) -> List[SupplyChainEdge]:
        """List edges, optionally filtered by connected node."""
        with self._lock:
            edges = list(self._edges.values())

            if node_id:
                edges = [
                    e for e in edges
                    if e.source_node_id == node_id or e.target_node_id == node_id
                ]

            return edges

    def _rebuild_simulators(self):
        """Rebuild simulators after topology change."""
        self._flow_simulator = MaterialFlowSimulator(self._nodes, self._edges)
        self._risk_engine = RiskPropagationEngine(self._nodes, self._edges)

    def update_inventory(
        self,
        node_id: str,
        material_id: str,
        quantity_change: float,
        operation: str = "adjustment"
    ) -> bool:
        """Update inventory at a node."""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False

            if material_id not in node.inventory:
                node.inventory[material_id] = InventoryLevel(
                    material_id=material_id,
                    quantity=0
                )

            inv = node.inventory[material_id]
            inv.quantity += quantity_change
            inv.quantity = max(0, inv.quantity)
            inv.last_updated = datetime.utcnow()

            logger.info(
                f"Inventory update at {node_id}: {material_id} "
                f"{'+' if quantity_change >= 0 else ''}{quantity_change} ({operation})"
            )
            return True

    def get_inventory_summary(self, node_id: str) -> Dict[str, Any]:
        """Get inventory summary for a node."""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return {'error': 'Node not found'}

            total_value = 0
            items_needing_reorder = []

            for material_id, inv in node.inventory.items():
                material = self._materials.get(material_id)
                if material:
                    total_value += inv.quantity * material.unit_cost
                if inv.needs_reorder:
                    items_needing_reorder.append(material_id)

            return {
                'node_id': node_id,
                'total_items': len(node.inventory),
                'total_value': total_value,
                'items_needing_reorder': items_needing_reorder,
                'inventory': {k: v.to_dict() for k, v in node.inventory.items()}
            }

    def simulate_material_flow(
        self,
        material_id: str,
        source_node_id: str,
        target_node_id: str,
        quantity: float
    ) -> Optional[Dict[str, Any]]:
        """Simulate material flow between nodes."""
        if not self._flow_simulator:
            return None

        shipment = self._flow_simulator.simulate_flow(
            material_id, source_node_id, target_node_id, quantity
        )

        if shipment:
            return shipment.to_dict()
        return None

    def get_active_shipments(self) -> List[Dict[str, Any]]:
        """Get all active shipments."""
        if not self._flow_simulator:
            return []
        return [s.to_dict() for s in self._flow_simulator.get_active_shipments()]

    def add_risk(self, risk: RiskFactor):
        """Add a risk factor."""
        with self._lock:
            self._risks[risk.id] = risk

            # Update affected nodes
            for node_id in risk.affected_node_ids:
                node = self._nodes.get(node_id)
                if node and risk.id not in node.risk_factors:
                    node.risk_factors.append(risk.id)

            logger.info(f"Added risk factor: {risk.name} (score: {risk.risk_score:.1f})")

    def get_risk(self, risk_id: str) -> Optional[RiskFactor]:
        """Get risk factor by ID."""
        with self._lock:
            return self._risks.get(risk_id)

    def list_risks(
        self,
        category: Optional[RiskCategory] = None,
        min_score: float = 0
    ) -> List[RiskFactor]:
        """List risk factors with optional filtering."""
        with self._lock:
            risks = list(self._risks.values())

            if category:
                risks = [r for r in risks if r.category == category]

            risks = [r for r in risks if r.risk_score >= min_score]

            return sorted(risks, key=lambda r: r.risk_score, reverse=True)

    def propagate_risk(self, risk_id: str) -> Dict[str, float]:
        """Propagate risk through network."""
        if not self._risk_engine:
            return {}

        risk = self.get_risk(risk_id)
        if not risk:
            return {}

        return self._risk_engine.propagate_risk(risk)

    def analyze_vulnerabilities(self) -> Dict[str, Any]:
        """Analyze supply chain vulnerabilities."""
        if not self._risk_engine:
            return {}

        single_points = self._risk_engine.analyze_single_point_failures()

        # Calculate overall risk score
        total_risk = sum(r.risk_score for r in self._risks.values())

        # Find highest risk nodes
        node_risk_scores: Dict[str, float] = {}
        for risk in self._risks.values():
            for node_id in risk.affected_node_ids:
                node_risk_scores[node_id] = node_risk_scores.get(node_id, 0) + risk.risk_score

        highest_risk_nodes = sorted(
            node_risk_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            'total_risk_score': total_risk,
            'risk_count': len(self._risks),
            'single_point_failures': single_points,
            'highest_risk_nodes': [
                {'node_id': n, 'risk_score': s}
                for n, s in highest_risk_nodes
            ]
        }

    def create_disruption_scenario(
        self,
        name: str,
        affected_nodes: List[str],
        affected_edges: List[str],
        duration_days: float,
        impact_factor: float,
        risk_category: RiskCategory
    ) -> DisruptionScenario:
        """Create a disruption scenario for simulation."""
        scenario = DisruptionScenario(
            id=str(uuid.uuid4()),
            name=name,
            description=f"Disruption affecting {len(affected_nodes)} nodes and {len(affected_edges)} edges",
            affected_nodes=affected_nodes,
            affected_edges=affected_edges,
            duration_days=duration_days,
            impact_factor=impact_factor,
            risk_category=risk_category,
            probability=0.1  # Default probability
        )

        with self._lock:
            self._scenarios[scenario.id] = scenario

        return scenario

    def simulate_disruption(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """Simulate a disruption scenario."""
        if not self._risk_engine:
            return None

        with self._lock:
            scenario = self._scenarios.get(scenario_id)

        if not scenario:
            return None

        return self._risk_engine.simulate_disruption(scenario)

    def get_network_visualization(self) -> Dict[str, Any]:
        """Get network data for visualization."""
        with self._lock:
            nodes_viz = []
            for node in self._nodes.values():
                nodes_viz.append({
                    'id': node.id,
                    'name': node.name,
                    'type': node.node_type.value,
                    'status': node.status.value,
                    'lat': node.location.latitude,
                    'lng': node.location.longitude,
                    'utilization': node.current_utilization,
                    'reliability': node.reliability_score,
                    'risk_count': len(node.risk_factors)
                })

            edges_viz = []
            for edge in self._edges.values():
                source = self._nodes.get(edge.source_node_id)
                target = self._nodes.get(edge.target_node_id)
                if source and target:
                    edges_viz.append({
                        'id': edge.id,
                        'source': edge.source_node_id,
                        'target': edge.target_node_id,
                        'mode': edge.transport_mode.value,
                        'lead_time': edge.lead_time_days,
                        'utilization': edge.current_utilization,
                        'active': edge.active
                    })

            return {
                'nodes': nodes_viz,
                'edges': edges_viz,
                'summary': {
                    'total_nodes': len(nodes_viz),
                    'total_edges': len(edges_viz),
                    'active_risks': len(self._risks)
                }
            }

    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            return {
                'total_nodes': len(self._nodes),
                'node_types': {
                    t.value: len([n for n in self._nodes.values() if n.node_type == t])
                    for t in NodeType
                },
                'total_edges': len(self._edges),
                'total_materials': len(self._materials),
                'active_risks': len(self._risks),
                'total_risk_score': sum(r.risk_score for r in self._risks.values()),
                'disruption_scenarios': len(self._scenarios)
            }


# Singleton instance
_supply_chain_twin_service: Optional[SupplyChainTwinService] = None


def get_supply_chain_twin_service() -> SupplyChainTwinService:
    """Get or create supply chain twin service."""
    global _supply_chain_twin_service
    if _supply_chain_twin_service is None:
        _supply_chain_twin_service = SupplyChainTwinService()
    return _supply_chain_twin_service
