"""
Digital Thread - Complete Product Traceability

LegoMCP World-Class Manufacturing System v5.0
Phase 15: Digital Thread & Genealogy (Enhanced for ISO 23247)

Complete traceability from order through delivery:
- Product genealogy with 3D visualization
- Material lot tracking
- Process parameter history
- Quality event linkage
- Root cause analysis
- Supply chain correlation
- Unity digital twin integration

Author: LegoMCP Team
Version: 2.0.0
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Set
from uuid import uuid4
from enum import Enum

logger = logging.getLogger(__name__)


class ThreadEventType(Enum):
    """Types of events in the digital thread."""
    CREATION = "creation"
    MATERIAL_ADDED = "material_added"
    PROCESS_RECORDED = "process_recorded"
    QUALITY_EVENT = "quality_event"
    STATUS_CHANGE = "status_change"
    DEFECT_DETECTED = "defect_detected"
    REWORK = "rework"
    INSPECTION = "inspection"
    SHIPMENT = "shipment"
    RETURN = "return"
    RECALL = "recall"


class ThreadVisualizationType(Enum):
    """Types of thread visualizations."""
    TIMELINE = "timeline"
    TREE = "tree"
    SANKEY = "sankey"
    NETWORK_GRAPH = "network_graph"
    SPATIAL_3D = "spatial_3d"


@dataclass
class SpatialPosition:
    """3D position for Unity visualization."""
    x: float
    y: float
    z: float

    def to_dict(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y, 'z': self.z}


@dataclass
class ThreadEvent:
    """Event in the digital thread."""
    event_id: str
    event_type: ThreadEventType
    timestamp: datetime
    description: str
    data: Dict[str, Any] = field(default_factory=dict)
    position: Optional[SpatialPosition] = None
    related_events: List[str] = field(default_factory=list)
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'description': self.description,
            'data': self.data,
            'position': self.position.to_dict() if self.position else None,
            'related_events': self.related_events,
            'user_id': self.user_id
        }


@dataclass
class MaterialConsumption:
    """Record of material consumed in production."""
    material_id: str
    part_id: str
    lot_number: str
    quantity_used: float
    unit_of_measure: str = "EA"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    supplier_id: Optional[str] = None
    supplier_lot: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'material_id': self.material_id,
            'part_id': self.part_id,
            'lot_number': self.lot_number,
            'quantity_used': self.quantity_used,
            'supplier_id': self.supplier_id,
            'supplier_lot': self.supplier_lot,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class ProcessSnapshot:
    """Snapshot of process parameters at production time."""
    snapshot_id: str
    timestamp: datetime

    # Temperature parameters
    nozzle_temp: Optional[float] = None
    bed_temp: Optional[float] = None
    ambient_temp: Optional[float] = None

    # Speed/motion
    print_speed: Optional[float] = None
    travel_speed: Optional[float] = None

    # Extrusion
    flow_rate: Optional[float] = None
    layer_height: Optional[float] = None

    # Environment
    humidity: Optional[float] = None

    # Machine state
    work_center_id: Optional[str] = None
    machine_runtime_hours: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'snapshot_id': self.snapshot_id,
            'timestamp': self.timestamp.isoformat(),
            'nozzle_temp': self.nozzle_temp,
            'bed_temp': self.bed_temp,
            'print_speed': self.print_speed,
            'flow_rate': self.flow_rate,
            'layer_height': self.layer_height,
            'work_center_id': self.work_center_id,
        }


@dataclass
class QualityEvent:
    """Quality event in the digital thread."""
    event_id: str
    event_type: str  # inspection, defect, spc_signal, etc.
    timestamp: datetime
    result: str  # pass, fail, warning
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'result': self.result,
            'details': self.details,
        }


@dataclass
class ProductGenealogy:
    """Complete genealogy of a produced item."""
    genealogy_id: str
    serial_number: str
    lot_number: str
    part_id: str
    part_name: str

    # Order linkage
    customer_order_id: Optional[str] = None
    work_order_id: Optional[str] = None

    # Version info
    bom_version: str = ""
    routing_version: str = ""

    # Production
    production_date: Optional[datetime] = None
    work_center_id: Optional[str] = None
    operator_id: Optional[str] = None

    # Materials
    materials_consumed: List[MaterialConsumption] = field(default_factory=list)

    # Process
    process_snapshots: List[ProcessSnapshot] = field(default_factory=list)

    # Quality
    quality_events: List[QualityEvent] = field(default_factory=list)
    final_quality_score: float = 100.0
    first_pass_yield: bool = True

    # SPC/FMEA state at production
    spc_state_snapshot: Dict[str, Any] = field(default_factory=dict)
    fmea_rpn_snapshot: Dict[str, float] = field(default_factory=dict)

    # Cost
    total_cost: float = 0.0
    energy_kwh: float = 0.0

    # Status
    status: str = "active"  # active, shipped, returned, recalled

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.genealogy_id:
            self.genealogy_id = str(uuid4())

    def add_material(self, material: MaterialConsumption) -> None:
        """Add material consumption record."""
        self.materials_consumed.append(material)

    def add_process_snapshot(self, snapshot: ProcessSnapshot) -> None:
        """Add process parameter snapshot."""
        self.process_snapshots.append(snapshot)

    def add_quality_event(self, event: QualityEvent) -> None:
        """Add quality event."""
        self.quality_events.append(event)
        if event.result == 'fail':
            self.first_pass_yield = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'genealogy_id': self.genealogy_id,
            'serial_number': self.serial_number,
            'lot_number': self.lot_number,
            'part_id': self.part_id,
            'part_name': self.part_name,
            'customer_order_id': self.customer_order_id,
            'work_order_id': self.work_order_id,
            'bom_version': self.bom_version,
            'routing_version': self.routing_version,
            'production_date': self.production_date.isoformat() if self.production_date else None,
            'work_center_id': self.work_center_id,
            'materials_consumed': [m.to_dict() for m in self.materials_consumed],
            'process_snapshots': [p.to_dict() for p in self.process_snapshots],
            'quality_events': [q.to_dict() for q in self.quality_events],
            'final_quality_score': self.final_quality_score,
            'first_pass_yield': self.first_pass_yield,
            'total_cost': self.total_cost,
            'energy_kwh': self.energy_kwh,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
        }


class DigitalThreadService:
    """
    Digital Thread Service.

    Builds and maintains complete product traceability.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # Storage
        self._genealogies: Dict[str, ProductGenealogy] = {}
        self._by_serial: Dict[str, str] = {}  # serial -> genealogy_id
        self._by_lot: Dict[str, List[str]] = {}  # lot -> [genealogy_ids]
        self._by_material_lot: Dict[str, List[str]] = {}  # material_lot -> [genealogy_ids]

    def create_genealogy(
        self,
        serial_number: str,
        lot_number: str,
        part_id: str,
        part_name: str,
        work_order_id: Optional[str] = None,
    ) -> ProductGenealogy:
        """Create a new product genealogy record."""
        genealogy = ProductGenealogy(
            genealogy_id=str(uuid4()),
            serial_number=serial_number,
            lot_number=lot_number,
            part_id=part_id,
            part_name=part_name,
            work_order_id=work_order_id,
        )

        self._genealogies[genealogy.genealogy_id] = genealogy
        self._by_serial[serial_number] = genealogy.genealogy_id

        if lot_number not in self._by_lot:
            self._by_lot[lot_number] = []
        self._by_lot[lot_number].append(genealogy.genealogy_id)

        logger.info(f"Created genealogy for {serial_number}")
        return genealogy

    def add_material_usage(
        self,
        serial_number: str,
        material_id: str,
        lot_number: str,
        quantity: float,
        supplier_id: Optional[str] = None,
    ) -> None:
        """Record material usage for a product."""
        genealogy_id = self._by_serial.get(serial_number)
        if not genealogy_id:
            return

        genealogy = self._genealogies.get(genealogy_id)
        if not genealogy:
            return

        material = MaterialConsumption(
            material_id=material_id,
            part_id=genealogy.part_id,
            lot_number=lot_number,
            quantity_used=quantity,
            supplier_id=supplier_id,
        )
        genealogy.add_material(material)

        # Index by material lot
        if lot_number not in self._by_material_lot:
            self._by_material_lot[lot_number] = []
        self._by_material_lot[lot_number].append(genealogy_id)

    def add_process_data(
        self,
        serial_number: str,
        process_data: Dict[str, Any],
    ) -> None:
        """Record process parameters for a product."""
        genealogy_id = self._by_serial.get(serial_number)
        if not genealogy_id:
            return

        genealogy = self._genealogies.get(genealogy_id)
        if not genealogy:
            return

        snapshot = ProcessSnapshot(
            snapshot_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            nozzle_temp=process_data.get('nozzle_temp'),
            bed_temp=process_data.get('bed_temp'),
            print_speed=process_data.get('print_speed'),
            flow_rate=process_data.get('flow_rate'),
            layer_height=process_data.get('layer_height'),
            work_center_id=process_data.get('work_center_id'),
        )
        genealogy.add_process_snapshot(snapshot)

    def add_quality_event(
        self,
        serial_number: str,
        event_type: str,
        result: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record quality event for a product."""
        genealogy_id = self._by_serial.get(serial_number)
        if not genealogy_id:
            return

        genealogy = self._genealogies.get(genealogy_id)
        if not genealogy:
            return

        event = QualityEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            result=result,
            details=details or {},
        )
        genealogy.add_quality_event(event)

    def get_genealogy(self, serial_number: str) -> Optional[ProductGenealogy]:
        """Get genealogy by serial number."""
        genealogy_id = self._by_serial.get(serial_number)
        if genealogy_id:
            return self._genealogies.get(genealogy_id)
        return None

    def trace_material_lot(self, material_lot: str) -> List[ProductGenealogy]:
        """Find all products that used a material lot."""
        genealogy_ids = self._by_material_lot.get(material_lot, [])
        return [
            self._genealogies[gid] for gid in genealogy_ids
            if gid in self._genealogies
        ]

    def simulate_recall(self, material_lot: str) -> Dict[str, Any]:
        """Simulate a recall based on material lot."""
        affected = self.trace_material_lot(material_lot)

        return {
            'material_lot': material_lot,
            'affected_count': len(affected),
            'affected_products': [
                {
                    'serial_number': g.serial_number,
                    'part_id': g.part_id,
                    'status': g.status,
                    'customer_order_id': g.customer_order_id,
                }
                for g in affected
            ],
        }

    def root_cause_analysis(
        self,
        serial_number: str,
    ) -> Dict[str, Any]:
        """Perform root cause analysis for a defective product."""
        genealogy = self.get_genealogy(serial_number)
        if not genealogy:
            return {'error': 'Product not found'}

        # Collect all relevant data
        failed_events = [
            e for e in genealogy.quality_events
            if e.result == 'fail'
        ]

        # Check process parameters against known good values
        process_issues = []
        for snapshot in genealogy.process_snapshots:
            if snapshot.nozzle_temp and snapshot.nozzle_temp < 200:
                process_issues.append('Low nozzle temperature')
            if snapshot.nozzle_temp and snapshot.nozzle_temp > 230:
                process_issues.append('High nozzle temperature')

        return {
            'serial_number': serial_number,
            'part_id': genealogy.part_id,
            'production_date': genealogy.production_date.isoformat() if genealogy.production_date else None,
            'work_center_id': genealogy.work_center_id,
            'materials_used': [
                {'lot': m.lot_number, 'supplier': m.supplier_id}
                for m in genealogy.materials_consumed
            ],
            'failed_events': [e.to_dict() for e in failed_events],
            'process_issues': process_issues,
            'recommendation': self._generate_recommendation(
                failed_events, process_issues, genealogy
            ),
        }

    def _generate_recommendation(
        self,
        failed_events: List[QualityEvent],
        process_issues: List[str],
        genealogy: ProductGenealogy,
    ) -> str:
        """Generate RCA recommendation."""
        if process_issues:
            return f"Check process parameters: {', '.join(process_issues)}"
        if genealogy.materials_consumed:
            return "Verify material quality from suppliers"
        return "Further investigation needed"

    def get_summary(self) -> Dict[str, Any]:
        """Get digital thread summary."""
        total = len(self._genealogies)
        fpy_count = sum(1 for g in self._genealogies.values() if g.first_pass_yield)

        return {
            'total_products': total,
            'tracked_lots': len(self._by_lot),
            'tracked_material_lots': len(self._by_material_lot),
            'first_pass_yield_percent': (fpy_count / total * 100) if total > 0 else 100,
        }

    # ========================================
    # 3D Visualization for Unity Digital Twin
    # ========================================

    def get_thread_visualization(
        self,
        serial_number: str,
        viz_type: ThreadVisualizationType = ThreadVisualizationType.TIMELINE
    ) -> Dict[str, Any]:
        """
        Get visualization data for digital thread.

        Supports multiple visualization types for Unity rendering.
        """
        genealogy = self.get_genealogy(serial_number)
        if not genealogy:
            return {'error': 'Product not found'}

        if viz_type == ThreadVisualizationType.TIMELINE:
            return self._build_timeline_viz(genealogy)
        elif viz_type == ThreadVisualizationType.TREE:
            return self._build_tree_viz(genealogy)
        elif viz_type == ThreadVisualizationType.NETWORK_GRAPH:
            return self._build_network_viz(genealogy)
        elif viz_type == ThreadVisualizationType.SPATIAL_3D:
            return self._build_spatial_3d_viz(genealogy)
        else:
            return self._build_timeline_viz(genealogy)

    def _build_timeline_viz(self, genealogy: ProductGenealogy) -> Dict[str, Any]:
        """Build timeline visualization data."""
        events = []

        # Creation event
        events.append({
            'id': f"create_{genealogy.genealogy_id[:8]}",
            'type': 'creation',
            'timestamp': genealogy.created_at.isoformat(),
            'label': f"Created: {genealogy.part_name}",
            'data': {'part_id': genealogy.part_id}
        })

        # Material events
        for mat in genealogy.materials_consumed:
            events.append({
                'id': f"mat_{mat.material_id[:8]}",
                'type': 'material',
                'timestamp': mat.timestamp.isoformat(),
                'label': f"Material: {mat.material_id}",
                'data': mat.to_dict()
            })

        # Process events
        for snap in genealogy.process_snapshots:
            events.append({
                'id': snap.snapshot_id,
                'type': 'process',
                'timestamp': snap.timestamp.isoformat(),
                'label': f"Process at {snap.work_center_id or 'unknown'}",
                'data': snap.to_dict()
            })

        # Quality events
        for qe in genealogy.quality_events:
            events.append({
                'id': qe.event_id,
                'type': 'quality',
                'timestamp': qe.timestamp.isoformat(),
                'label': f"Quality: {qe.event_type} - {qe.result}",
                'data': qe.to_dict(),
                'color': '#00FF00' if qe.result == 'pass' else '#FF0000'
            })

        # Sort by timestamp
        events.sort(key=lambda e: e['timestamp'])

        return {
            'visualization_type': 'timeline',
            'serial_number': genealogy.serial_number,
            'events': events,
            'summary': {
                'total_events': len(events),
                'first_pass_yield': genealogy.first_pass_yield,
                'quality_score': genealogy.final_quality_score
            }
        }

    def _build_tree_viz(self, genealogy: ProductGenealogy) -> Dict[str, Any]:
        """Build tree/hierarchy visualization data."""
        # Root node is the product
        root = {
            'id': genealogy.genealogy_id,
            'name': genealogy.part_name,
            'type': 'product',
            'children': []
        }

        # Materials branch
        materials_node = {
            'id': f"materials_{genealogy.genealogy_id[:8]}",
            'name': 'Materials',
            'type': 'category',
            'children': []
        }
        for mat in genealogy.materials_consumed:
            materials_node['children'].append({
                'id': f"mat_{mat.material_id}",
                'name': mat.material_id,
                'type': 'material',
                'data': mat.to_dict()
            })
        root['children'].append(materials_node)

        # Process branch
        process_node = {
            'id': f"process_{genealogy.genealogy_id[:8]}",
            'name': 'Process Steps',
            'type': 'category',
            'children': []
        }
        for snap in genealogy.process_snapshots:
            process_node['children'].append({
                'id': snap.snapshot_id,
                'name': f"Step at {snap.work_center_id or 'unknown'}",
                'type': 'process',
                'data': snap.to_dict()
            })
        root['children'].append(process_node)

        # Quality branch
        quality_node = {
            'id': f"quality_{genealogy.genealogy_id[:8]}",
            'name': 'Quality Events',
            'type': 'category',
            'children': []
        }
        for qe in genealogy.quality_events:
            quality_node['children'].append({
                'id': qe.event_id,
                'name': f"{qe.event_type}: {qe.result}",
                'type': 'quality',
                'status': qe.result,
                'data': qe.to_dict()
            })
        root['children'].append(quality_node)

        return {
            'visualization_type': 'tree',
            'serial_number': genealogy.serial_number,
            'tree': root
        }

    def _build_network_viz(self, genealogy: ProductGenealogy) -> Dict[str, Any]:
        """Build network graph visualization data."""
        nodes = []
        edges = []

        # Product node (center)
        nodes.append({
            'id': genealogy.genealogy_id,
            'label': genealogy.part_name,
            'type': 'product',
            'size': 30,
            'color': '#4CAF50'
        })

        # Supplier nodes
        suppliers: Set[str] = set()
        for mat in genealogy.materials_consumed:
            if mat.supplier_id and mat.supplier_id not in suppliers:
                suppliers.add(mat.supplier_id)
                nodes.append({
                    'id': f"supplier_{mat.supplier_id}",
                    'label': mat.supplier_id,
                    'type': 'supplier',
                    'size': 20,
                    'color': '#2196F3'
                })

            # Material node
            mat_id = f"mat_{mat.material_id}"
            nodes.append({
                'id': mat_id,
                'label': mat.material_id,
                'type': 'material',
                'size': 15,
                'color': '#FF9800'
            })

            # Edges
            if mat.supplier_id:
                edges.append({
                    'source': f"supplier_{mat.supplier_id}",
                    'target': mat_id,
                    'label': 'supplies'
                })
            edges.append({
                'source': mat_id,
                'target': genealogy.genealogy_id,
                'label': 'used_in'
            })

        # Work center nodes
        work_centers: Set[str] = set()
        for snap in genealogy.process_snapshots:
            if snap.work_center_id and snap.work_center_id not in work_centers:
                work_centers.add(snap.work_center_id)
                wc_id = f"wc_{snap.work_center_id}"
                nodes.append({
                    'id': wc_id,
                    'label': snap.work_center_id,
                    'type': 'work_center',
                    'size': 20,
                    'color': '#9C27B0'
                })
                edges.append({
                    'source': genealogy.genealogy_id,
                    'target': wc_id,
                    'label': 'processed_at'
                })

        return {
            'visualization_type': 'network_graph',
            'serial_number': genealogy.serial_number,
            'nodes': nodes,
            'edges': edges
        }

    def _build_spatial_3d_viz(self, genealogy: ProductGenealogy) -> Dict[str, Any]:
        """Build 3D spatial visualization for Unity."""
        # Create 3D layout with positions for Unity
        objects = []

        # Center: Product
        objects.append({
            'id': genealogy.genealogy_id,
            'type': 'product',
            'name': genealogy.part_name,
            'position': {'x': 0, 'y': 1, 'z': 0},
            'scale': {'x': 1, 'y': 1, 'z': 1},
            'color': '#4CAF50',
            'prefab': 'ProductNode'
        })

        # Arrange materials in a circle around product
        import math
        material_count = len(genealogy.materials_consumed)
        for i, mat in enumerate(genealogy.materials_consumed):
            angle = (2 * math.pi * i) / max(material_count, 1)
            radius = 3.0
            objects.append({
                'id': f"mat_{mat.material_id}",
                'type': 'material',
                'name': mat.material_id,
                'position': {
                    'x': radius * math.cos(angle),
                    'y': 0.5,
                    'z': radius * math.sin(angle)
                },
                'scale': {'x': 0.5, 'y': 0.5, 'z': 0.5},
                'color': '#FF9800',
                'prefab': 'MaterialNode',
                'connection_to': genealogy.genealogy_id
            })

        # Arrange work centers above
        wc_set: Set[str] = set()
        for snap in genealogy.process_snapshots:
            if snap.work_center_id and snap.work_center_id not in wc_set:
                wc_set.add(snap.work_center_id)

        wc_count = len(wc_set)
        for i, wc_id in enumerate(wc_set):
            angle = (2 * math.pi * i) / max(wc_count, 1) + math.pi / 4
            radius = 2.5
            objects.append({
                'id': f"wc_{wc_id}",
                'type': 'work_center',
                'name': wc_id,
                'position': {
                    'x': radius * math.cos(angle),
                    'y': 2.5,
                    'z': radius * math.sin(angle)
                },
                'scale': {'x': 0.7, 'y': 0.7, 'z': 0.7},
                'color': '#9C27B0',
                'prefab': 'WorkCenterNode',
                'connection_to': genealogy.genealogy_id
            })

        # Quality events as floating indicators
        for i, qe in enumerate(genealogy.quality_events):
            objects.append({
                'id': qe.event_id,
                'type': 'quality_event',
                'name': f"{qe.event_type}: {qe.result}",
                'position': {
                    'x': -3 + i * 0.5,
                    'y': 3,
                    'z': 0
                },
                'scale': {'x': 0.3, 'y': 0.3, 'z': 0.3},
                'color': '#00FF00' if qe.result == 'pass' else '#FF0000',
                'prefab': 'QualityMarker',
                'connection_to': genealogy.genealogy_id
            })

        return {
            'visualization_type': 'spatial_3d',
            'serial_number': genealogy.serial_number,
            'objects': objects,
            'camera_position': {'x': 5, 'y': 5, 'z': 5},
            'camera_target': {'x': 0, 'y': 1, 'z': 0}
        }

    def get_supply_chain_trace(
        self,
        serial_number: str
    ) -> Dict[str, Any]:
        """Get complete supply chain trace for a product."""
        genealogy = self.get_genealogy(serial_number)
        if not genealogy:
            return {'error': 'Product not found'}

        # Build supply chain path
        supply_chain = {
            'product': {
                'serial_number': genealogy.serial_number,
                'part_id': genealogy.part_id,
                'part_name': genealogy.part_name
            },
            'materials': [],
            'suppliers': {},
            'trace_depth': 0
        }

        suppliers_seen: Dict[str, Dict[str, Any]] = {}

        for mat in genealogy.materials_consumed:
            mat_trace = {
                'material_id': mat.material_id,
                'lot_number': mat.lot_number,
                'quantity': mat.quantity_used,
                'supplier_id': mat.supplier_id,
                'supplier_lot': mat.supplier_lot,
                'timestamp': mat.timestamp.isoformat()
            }
            supply_chain['materials'].append(mat_trace)

            if mat.supplier_id:
                if mat.supplier_id not in suppliers_seen:
                    suppliers_seen[mat.supplier_id] = {
                        'supplier_id': mat.supplier_id,
                        'materials_supplied': [],
                        'lots': set()
                    }
                suppliers_seen[mat.supplier_id]['materials_supplied'].append(mat.material_id)
                if mat.supplier_lot:
                    suppliers_seen[mat.supplier_id]['lots'].add(mat.supplier_lot)

        # Convert sets to lists for JSON
        for supplier_id, data in suppliers_seen.items():
            data['lots'] = list(data['lots'])
            supply_chain['suppliers'][supplier_id] = data

        supply_chain['trace_depth'] = len(suppliers_seen)

        return supply_chain

    def get_affected_by_supplier(
        self,
        supplier_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Find all products affected by a supplier."""
        affected = []

        for genealogy in self._genealogies.values():
            for mat in genealogy.materials_consumed:
                if mat.supplier_id == supplier_id:
                    # Check date range if specified
                    if start_date and mat.timestamp < start_date:
                        continue
                    if end_date and mat.timestamp > end_date:
                        continue

                    affected.append({
                        'serial_number': genealogy.serial_number,
                        'part_id': genealogy.part_id,
                        'material_id': mat.material_id,
                        'lot_number': mat.lot_number,
                        'timestamp': mat.timestamp.isoformat(),
                        'status': genealogy.status
                    })
                    break  # Only add once per product

        return affected

    def export_for_unity(
        self,
        serial_number: str
    ) -> Dict[str, Any]:
        """Export complete thread data for Unity visualization."""
        genealogy = self.get_genealogy(serial_number)
        if not genealogy:
            return {'error': 'Product not found'}

        return {
            'genealogy': genealogy.to_dict(),
            'visualizations': {
                'timeline': self._build_timeline_viz(genealogy),
                'tree': self._build_tree_viz(genealogy),
                'network': self._build_network_viz(genealogy),
                'spatial_3d': self._build_spatial_3d_viz(genealogy)
            },
            'supply_chain': self.get_supply_chain_trace(serial_number),
            'root_cause': self.root_cause_analysis(serial_number)
        }


# Singleton instance
_digital_thread_service: Optional[DigitalThreadService] = None


def get_digital_thread_service() -> DigitalThreadService:
    """Get or create digital thread service."""
    global _digital_thread_service
    if _digital_thread_service is None:
        _digital_thread_service = DigitalThreadService()
    return _digital_thread_service
