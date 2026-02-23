"""
ISO 23247 Observable Manufacturing Element (OME) Registry
==========================================================

This module implements the Observable Manufacturing Element registry as defined
in ISO 23247 Digital Twin Framework for Manufacturing.

ISO 23247 Reference Architecture:
---------------------------------
- ISO 23247-1: Overview and general principles
- ISO 23247-2: Reference architecture (4 domains)
- ISO 23247-3: Digital representation of manufacturing elements
- ISO 23247-4: Information exchange

Key Concepts:
-------------
1. Observable Manufacturing Element (OME): Physical asset being monitored
2. Digital Twin Entity: Virtual representation of OME
3. Hierarchical relationships: Factory → Line → Cell → Equipment → Sensor
4. Lifecycle management: Design → Commissioning → Active → Maintenance → Retired

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid
import logging
import hashlib
import json
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class OMEType(Enum):
    """Types of Observable Manufacturing Elements per ISO 23247."""
    FACTORY = "factory"
    PRODUCTION_LINE = "production_line"
    WORK_CELL = "work_cell"
    EQUIPMENT = "equipment"
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    TOOL = "tool"
    FIXTURE = "fixture"
    MATERIAL = "material"
    PRODUCT = "product"
    OPERATOR = "operator"
    PROCESS = "process"
    # Robotic Elements (ISO 10218 / ISO/TS 15066)
    ROBOTIC_ARM = "robotic_arm"
    END_EFFECTOR = "end_effector"
    GRIPPER = "gripper"
    AMR = "amr"  # Autonomous Mobile Robot


class OMELifecycleState(Enum):
    """Lifecycle states for OME per ISO 23247."""
    DESIGN = "design"              # Being designed/planned
    COMMISSIONING = "commissioning"  # Being installed/configured
    ACTIVE = "active"              # In production use
    MAINTENANCE = "maintenance"    # Under maintenance
    DEGRADED = "degraded"          # Operating with reduced capability
    STANDBY = "standby"            # Ready but not in use
    OFFLINE = "offline"            # Temporarily offline
    RETIRED = "retired"            # Decommissioned


class CapabilityType(Enum):
    """Types of capabilities an OME can have."""
    PROCESSING = "processing"
    MEASUREMENT = "measurement"
    TRANSPORT = "transport"
    STORAGE = "storage"
    ASSEMBLY = "assembly"
    INSPECTION = "inspection"
    PRINTING = "printing"
    MILLING = "milling"
    LASER_CUTTING = "laser_cutting"
    QUALITY_CONTROL = "quality_control"
    # Robotic Capabilities (ISO 10218)
    PICK_AND_PLACE = "pick_and_place"
    MANIPULATION = "manipulation"
    PALLETIZING = "palletizing"
    WELDING = "welding"
    PAINTING = "painting"
    MATERIAL_HANDLING = "material_handling"
    COLLABORATIVE = "collaborative"  # ISO/TS 15066 cobot


class SensorType(Enum):
    """Types of sensors for data collection."""
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    VIBRATION = "vibration"
    CURRENT = "current"
    VOLTAGE = "voltage"
    POSITION = "position"
    SPEED = "speed"
    FORCE = "force"
    TORQUE = "torque"
    FLOW = "flow"
    HUMIDITY = "humidity"
    CAMERA = "camera"
    LIDAR = "lidar"
    PROXIMITY = "proximity"
    ACOUSTIC = "acoustic"


@dataclass
class Geometry3D:
    """3D geometry representation for Unity visualization."""
    model_url: Optional[str] = None  # URL to 3D model file (GLTF/FBX)
    bounding_box: Dict[str, float] = field(default_factory=lambda: {
        'x': 0.0, 'y': 0.0, 'z': 0.0,
        'width': 1.0, 'height': 1.0, 'depth': 1.0
    })
    position: Dict[str, float] = field(default_factory=lambda: {
        'x': 0.0, 'y': 0.0, 'z': 0.0
    })
    rotation: Dict[str, float] = field(default_factory=lambda: {
        'x': 0.0, 'y': 0.0, 'z': 0.0
    })
    scale: Dict[str, float] = field(default_factory=lambda: {
        'x': 1.0, 'y': 1.0, 'z': 1.0
    })
    color: str = "#808080"  # Default gray
    material: str = "standard"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_url': self.model_url,
            'bounding_box': self.bounding_box,
            'position': self.position,
            'rotation': self.rotation,
            'scale': self.scale,
            'color': self.color,
            'material': self.material
        }


@dataclass
class StaticAttributes:
    """
    Static attributes of an OME per ISO 23247-3.

    These attributes don't change during normal operation:
    - Physical properties
    - Specifications
    - Capabilities
    - Documentation references
    """
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    installation_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None

    # Physical specifications
    dimensions: Dict[str, float] = field(default_factory=dict)  # mm
    weight: Optional[float] = None  # kg
    power_rating: Optional[float] = None  # watts
    voltage: Optional[float] = None  # volts

    # Capabilities
    capabilities: List[CapabilityType] = field(default_factory=list)
    max_throughput: Optional[float] = None  # units/hour
    accuracy: Optional[float] = None  # +/- mm or percentage
    repeatability: Optional[float] = None  # +/- mm

    # Work envelope (for equipment)
    work_envelope: Dict[str, float] = field(default_factory=dict)  # x, y, z in mm

    # Documentation
    documentation_url: Optional[str] = None
    maintenance_manual_url: Optional[str] = None

    # 3D Visualization
    geometry: Geometry3D = field(default_factory=Geometry3D)

    # Certification
    certifications: List[str] = field(default_factory=list)  # e.g., CE, UL, ISO

    def to_dict(self) -> Dict[str, Any]:
        return {
            'manufacturer': self.manufacturer,
            'model': self.model,
            'serial_number': self.serial_number,
            'installation_date': self.installation_date.isoformat() if self.installation_date else None,
            'warranty_expiry': self.warranty_expiry.isoformat() if self.warranty_expiry else None,
            'dimensions': self.dimensions,
            'weight': self.weight,
            'power_rating': self.power_rating,
            'voltage': self.voltage,
            'capabilities': [c.value for c in self.capabilities],
            'max_throughput': self.max_throughput,
            'accuracy': self.accuracy,
            'repeatability': self.repeatability,
            'work_envelope': self.work_envelope,
            'documentation_url': self.documentation_url,
            'maintenance_manual_url': self.maintenance_manual_url,
            'geometry': self.geometry.to_dict(),
            'certifications': self.certifications
        }


@dataclass
class DynamicAttributes:
    """
    Dynamic attributes of an OME per ISO 23247-3.

    These attributes change during operation:
    - Current state
    - Sensor readings
    - Performance metrics
    - Health indicators
    """
    # Current state
    status: str = "unknown"
    operational_mode: str = "unknown"
    current_job_id: Optional[str] = None
    current_program: Optional[str] = None

    # Sensor readings (real-time)
    temperatures: Dict[str, float] = field(default_factory=dict)
    pressures: Dict[str, float] = field(default_factory=dict)
    positions: Dict[str, float] = field(default_factory=dict)
    speeds: Dict[str, float] = field(default_factory=dict)
    forces: Dict[str, float] = field(default_factory=dict)
    vibrations: Dict[str, float] = field(default_factory=dict)

    # Performance metrics
    current_throughput: float = 0.0
    cycle_time_seconds: float = 0.0
    oee: float = 0.0
    availability: float = 0.0
    performance: float = 0.0
    quality: float = 0.0

    # Health indicators
    health_score: float = 100.0  # 0-100
    remaining_useful_life_hours: Optional[float] = None
    anomaly_score: float = 0.0  # 0-1, higher = more anomalous

    # Counters
    parts_produced_total: int = 0
    parts_produced_shift: int = 0
    defects_total: int = 0
    cycles_total: int = 0

    # Energy
    power_consumption_watts: float = 0.0
    energy_consumed_kwh: float = 0.0

    # Timestamps
    last_update: datetime = field(default_factory=datetime.utcnow)
    last_maintenance: Optional[datetime] = None
    next_maintenance: Optional[datetime] = None

    # Alarms/Alerts
    active_alarms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status,
            'operational_mode': self.operational_mode,
            'current_job_id': self.current_job_id,
            'current_program': self.current_program,
            'temperatures': self.temperatures,
            'pressures': self.pressures,
            'positions': self.positions,
            'speeds': self.speeds,
            'forces': self.forces,
            'vibrations': self.vibrations,
            'current_throughput': self.current_throughput,
            'cycle_time_seconds': self.cycle_time_seconds,
            'oee': self.oee,
            'availability': self.availability,
            'performance': self.performance,
            'quality': self.quality,
            'health_score': self.health_score,
            'remaining_useful_life_hours': self.remaining_useful_life_hours,
            'anomaly_score': self.anomaly_score,
            'parts_produced_total': self.parts_produced_total,
            'parts_produced_shift': self.parts_produced_shift,
            'defects_total': self.defects_total,
            'cycles_total': self.cycles_total,
            'power_consumption_watts': self.power_consumption_watts,
            'energy_consumed_kwh': self.energy_consumed_kwh,
            'last_update': self.last_update.isoformat(),
            'last_maintenance': self.last_maintenance.isoformat() if self.last_maintenance else None,
            'next_maintenance': self.next_maintenance.isoformat() if self.next_maintenance else None,
            'active_alarms': self.active_alarms
        }


@dataclass
class BehaviorModel:
    """
    Behavior model definition for an OME.

    Defines how the OME behaves under various conditions:
    - Physics-based models
    - ML/AI models
    - Rule-based logic
    """
    model_type: str = "none"  # pinn, hybrid, rules, ml
    model_id: Optional[str] = None
    model_version: str = "1.0.0"

    # Physics constraints
    physics_constraints: List[str] = field(default_factory=list)

    # Model parameters
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Prediction capabilities
    can_predict_failure: bool = False
    can_predict_quality: bool = False
    can_predict_rul: bool = False
    can_simulate: bool = False

    # Accuracy metrics
    accuracy: Optional[float] = None
    last_trained: Optional[datetime] = None
    training_samples: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_type': self.model_type,
            'model_id': self.model_id,
            'model_version': self.model_version,
            'physics_constraints': self.physics_constraints,
            'parameters': self.parameters,
            'can_predict_failure': self.can_predict_failure,
            'can_predict_quality': self.can_predict_quality,
            'can_predict_rul': self.can_predict_rul,
            'can_simulate': self.can_simulate,
            'accuracy': self.accuracy,
            'last_trained': self.last_trained.isoformat() if self.last_trained else None,
            'training_samples': self.training_samples
        }


@dataclass
class OMERelationship:
    """Relationship between two OMEs."""
    source_id: str
    target_id: str
    relationship_type: str  # parent_of, contains, feeds, controls, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_id': self.source_id,
            'target_id': self.target_id,
            'relationship_type': self.relationship_type,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class ObservableManufacturingElement:
    """
    Observable Manufacturing Element (OME) per ISO 23247.

    This is the core entity representing any physical manufacturing asset
    that can be observed and digitally twinned.
    """
    # Identification (ISO 23247-3 Section 7.2)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ome_type: OMEType = OMEType.EQUIPMENT
    name: str = ""
    description: str = ""

    # Namespace for multi-tenant/multi-site
    namespace: str = "default"

    # Hierarchy
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)

    # Lifecycle
    lifecycle_state: OMELifecycleState = OMELifecycleState.DESIGN
    lifecycle_history: List[Dict[str, Any]] = field(default_factory=list)

    # Attributes (ISO 23247-3 Section 7.3)
    static_attributes: StaticAttributes = field(default_factory=StaticAttributes)
    dynamic_attributes: DynamicAttributes = field(default_factory=DynamicAttributes)

    # Behavior (ISO 23247-3 Section 7.4)
    behavior_model: BehaviorModel = field(default_factory=BehaviorModel)

    # Relationships
    relationships: List[OMERelationship] = field(default_factory=list)

    # Digital Twin instances
    twin_instance_ids: List[str] = field(default_factory=list)

    # Sensors attached to this OME
    sensor_ids: List[str] = field(default_factory=list)

    # Metadata
    tags: List[str] = field(default_factory=list)
    custom_attributes: Dict[str, Any] = field(default_factory=dict)

    # Versioning
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    # Sync status
    sync_status: str = "synced"  # synced, pending, conflict
    last_sync_at: Optional[datetime] = None

    def update_lifecycle(self, new_state: OMELifecycleState, reason: str = "", user: str = None):
        """Update lifecycle state with history tracking."""
        old_state = self.lifecycle_state
        self.lifecycle_state = new_state
        self.updated_at = datetime.utcnow()
        self.updated_by = user

        self.lifecycle_history.append({
            'from_state': old_state.value,
            'to_state': new_state.value,
            'reason': reason,
            'user': user,
            'timestamp': self.updated_at.isoformat()
        })

        logger.info(f"OME {self.id} lifecycle: {old_state.value} -> {new_state.value}")

    def add_relationship(self, target_id: str, relationship_type: str, metadata: Dict = None):
        """Add relationship to another OME."""
        rel = OMERelationship(
            source_id=self.id,
            target_id=target_id,
            relationship_type=relationship_type,
            metadata=metadata or {}
        )
        self.relationships.append(rel)
        self.updated_at = datetime.utcnow()
        return rel

    def get_checksum(self) -> str:
        """Generate checksum for integrity verification."""
        data = json.dumps({
            'id': self.id,
            'name': self.name,
            'ome_type': self.ome_type.value,
            'static': self.static_attributes.to_dict(),
            'version': self.version
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'ome_type': self.ome_type.value,
            'name': self.name,
            'description': self.description,
            'namespace': self.namespace,
            'parent_id': self.parent_id,
            'children_ids': self.children_ids,
            'lifecycle_state': self.lifecycle_state.value,
            'lifecycle_history': self.lifecycle_history,
            'static_attributes': self.static_attributes.to_dict(),
            'dynamic_attributes': self.dynamic_attributes.to_dict(),
            'behavior_model': self.behavior_model.to_dict(),
            'relationships': [r.to_dict() for r in self.relationships],
            'twin_instance_ids': self.twin_instance_ids,
            'sensor_ids': self.sensor_ids,
            'tags': self.tags,
            'custom_attributes': self.custom_attributes,
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'sync_status': self.sync_status,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'checksum': self.get_checksum()
        }

    def to_unity_dict(self) -> Dict[str, Any]:
        """Convert to Unity-optimized format for 3D visualization."""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.ome_type.value,
            'status': self.dynamic_attributes.status,
            'health_score': self.dynamic_attributes.health_score,
            'geometry': self.static_attributes.geometry.to_dict(),
            'current_job': self.dynamic_attributes.current_job_id,
            'oee': self.dynamic_attributes.oee,
            'temperatures': self.dynamic_attributes.temperatures,
            'alarms': self.dynamic_attributes.active_alarms,
            'parent_id': self.parent_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ObservableManufacturingElement':
        """Create OME from dictionary."""
        ome = cls(
            id=data.get('id', str(uuid.uuid4())),
            ome_type=OMEType(data.get('ome_type', 'equipment')),
            name=data.get('name', ''),
            description=data.get('description', ''),
            namespace=data.get('namespace', 'default'),
            parent_id=data.get('parent_id'),
            children_ids=data.get('children_ids', []),
            lifecycle_state=OMELifecycleState(data.get('lifecycle_state', 'design')),
            tags=data.get('tags', []),
            custom_attributes=data.get('custom_attributes', {})
        )

        # Parse static attributes
        if 'static_attributes' in data:
            static = data['static_attributes']
            ome.static_attributes = StaticAttributes(
                manufacturer=static.get('manufacturer'),
                model=static.get('model'),
                serial_number=static.get('serial_number'),
                capabilities=[CapabilityType(c) for c in static.get('capabilities', [])],
            )
            if 'geometry' in static:
                geom = static['geometry']
                ome.static_attributes.geometry = Geometry3D(
                    model_url=geom.get('model_url'),
                    position=geom.get('position', {'x': 0, 'y': 0, 'z': 0}),
                    rotation=geom.get('rotation', {'x': 0, 'y': 0, 'z': 0}),
                    scale=geom.get('scale', {'x': 1, 'y': 1, 'z': 1}),
                    color=geom.get('color', '#808080')
                )

        return ome


class OMERegistry:
    """
    Central registry for Observable Manufacturing Elements.

    Provides:
    - CRUD operations for OMEs
    - Hierarchical navigation
    - Query and filtering
    - Lifecycle management
    - Event emission for changes
    """

    def __init__(self):
        self._omes: Dict[str, ObservableManufacturingElement] = {}
        self._namespace_index: Dict[str, Set[str]] = {}  # namespace -> set of ome_ids
        self._type_index: Dict[OMEType, Set[str]] = {}  # ome_type -> set of ome_ids
        self._parent_index: Dict[str, Set[str]] = {}  # parent_id -> set of children_ids
        self._event_listeners: List[callable] = []

    def register(self, ome: ObservableManufacturingElement) -> ObservableManufacturingElement:
        """Register a new OME in the registry."""
        if ome.id in self._omes:
            raise ValueError(f"OME with id {ome.id} already exists")

        self._omes[ome.id] = ome

        # Update indexes
        self._add_to_index(self._namespace_index, ome.namespace, ome.id)
        self._add_to_index(self._type_index, ome.ome_type, ome.id)

        if ome.parent_id:
            self._add_to_index(self._parent_index, ome.parent_id, ome.id)
            # Update parent's children list
            if ome.parent_id in self._omes:
                self._omes[ome.parent_id].children_ids.append(ome.id)

        self._emit_event('ome_registered', ome)
        logger.info(f"Registered OME: {ome.id} ({ome.name})")

        return ome

    def update(self, ome_id: str, updates: Dict[str, Any], user: str = None) -> ObservableManufacturingElement:
        """Update an existing OME."""
        if ome_id not in self._omes:
            raise ValueError(f"OME with id {ome_id} not found")

        ome = self._omes[ome_id]
        old_version = ome.version

        # Apply updates
        for key, value in updates.items():
            if hasattr(ome, key):
                setattr(ome, key, value)

        ome.version = old_version + 1
        ome.updated_at = datetime.utcnow()
        ome.updated_by = user

        self._emit_event('ome_updated', ome)
        logger.info(f"Updated OME: {ome_id} (v{old_version} -> v{ome.version})")

        return ome

    def update_dynamic_attributes(
        self,
        ome_id: str,
        attributes: Dict[str, Any]
    ) -> ObservableManufacturingElement:
        """Update only dynamic attributes (high-frequency updates)."""
        if ome_id not in self._omes:
            raise ValueError(f"OME with id {ome_id} not found")

        ome = self._omes[ome_id]
        dynamic = ome.dynamic_attributes

        for key, value in attributes.items():
            if hasattr(dynamic, key):
                setattr(dynamic, key, value)

        dynamic.last_update = datetime.utcnow()

        # Don't increment version for dynamic updates (too frequent)
        self._emit_event('ome_dynamic_updated', ome)

        return ome

    def get(self, ome_id: str) -> Optional[ObservableManufacturingElement]:
        """Get OME by ID."""
        return self._omes.get(ome_id)

    def get_by_name(self, name: str, namespace: str = "default") -> Optional[ObservableManufacturingElement]:
        """Get OME by name within namespace."""
        for ome in self._omes.values():
            if ome.name == name and ome.namespace == namespace:
                return ome
        return None

    def get_all(self, namespace: str = None) -> List[ObservableManufacturingElement]:
        """Get all OMEs, optionally filtered by namespace."""
        if namespace:
            ome_ids = self._namespace_index.get(namespace, set())
            return [self._omes[oid] for oid in ome_ids]
        return list(self._omes.values())

    def get_by_type(self, ome_type: OMEType) -> List[ObservableManufacturingElement]:
        """Get all OMEs of a specific type."""
        ome_ids = self._type_index.get(ome_type, set())
        return [self._omes[oid] for oid in ome_ids]

    def get_children(self, parent_id: str) -> List[ObservableManufacturingElement]:
        """Get all children of an OME."""
        children_ids = self._parent_index.get(parent_id, set())
        return [self._omes[cid] for cid in children_ids if cid in self._omes]

    def get_hierarchy(self, root_id: str = None) -> Dict[str, Any]:
        """Get full hierarchy starting from root or all top-level OMEs."""
        if root_id:
            root = self.get(root_id)
            if not root:
                return {}
            return self._build_hierarchy_tree(root)

        # Get all top-level OMEs (no parent)
        roots = [ome for ome in self._omes.values() if ome.parent_id is None]
        return {
            'roots': [self._build_hierarchy_tree(r) for r in roots]
        }

    def _build_hierarchy_tree(self, ome: ObservableManufacturingElement) -> Dict[str, Any]:
        """Build hierarchy tree recursively."""
        children = self.get_children(ome.id)
        return {
            'id': ome.id,
            'name': ome.name,
            'type': ome.ome_type.value,
            'status': ome.dynamic_attributes.status,
            'lifecycle': ome.lifecycle_state.value,
            'children': [self._build_hierarchy_tree(c) for c in children]
        }

    def query(
        self,
        namespace: str = None,
        ome_type: OMEType = None,
        lifecycle_state: OMELifecycleState = None,
        status: str = None,
        tags: List[str] = None,
        parent_id: str = None,
        health_below: float = None,
        with_alarms: bool = None
    ) -> List[ObservableManufacturingElement]:
        """Query OMEs with multiple filters."""
        results = list(self._omes.values())

        if namespace:
            results = [o for o in results if o.namespace == namespace]

        if ome_type:
            results = [o for o in results if o.ome_type == ome_type]

        if lifecycle_state:
            results = [o for o in results if o.lifecycle_state == lifecycle_state]

        if status:
            results = [o for o in results if o.dynamic_attributes.status == status]

        if tags:
            results = [o for o in results if any(t in o.tags for t in tags)]

        if parent_id:
            results = [o for o in results if o.parent_id == parent_id]

        if health_below is not None:
            results = [o for o in results if o.dynamic_attributes.health_score < health_below]

        if with_alarms:
            results = [o for o in results if len(o.dynamic_attributes.active_alarms) > 0]

        return results

    def delete(self, ome_id: str) -> bool:
        """Delete an OME from registry."""
        if ome_id not in self._omes:
            return False

        ome = self._omes[ome_id]

        # Remove from indexes
        self._remove_from_index(self._namespace_index, ome.namespace, ome_id)
        self._remove_from_index(self._type_index, ome.ome_type, ome_id)

        if ome.parent_id:
            self._remove_from_index(self._parent_index, ome.parent_id, ome_id)
            if ome.parent_id in self._omes:
                parent = self._omes[ome.parent_id]
                if ome_id in parent.children_ids:
                    parent.children_ids.remove(ome_id)

        del self._omes[ome_id]

        self._emit_event('ome_deleted', {'id': ome_id})
        logger.info(f"Deleted OME: {ome_id}")

        return True

    def transition_lifecycle(
        self,
        ome_id: str,
        new_state: OMELifecycleState,
        reason: str = "",
        user: str = None
    ) -> ObservableManufacturingElement:
        """Transition OME to new lifecycle state with validation."""
        if ome_id not in self._omes:
            raise ValueError(f"OME with id {ome_id} not found")

        ome = self._omes[ome_id]
        current_state = ome.lifecycle_state

        # Validate transition
        valid_transitions = self._get_valid_transitions(current_state)
        if new_state not in valid_transitions:
            raise ValueError(
                f"Invalid transition: {current_state.value} -> {new_state.value}. "
                f"Valid: {[s.value for s in valid_transitions]}"
            )

        ome.update_lifecycle(new_state, reason, user)

        self._emit_event('ome_lifecycle_changed', {
            'ome_id': ome_id,
            'from_state': current_state.value,
            'to_state': new_state.value,
            'reason': reason
        })

        return ome

    def _get_valid_transitions(self, current_state: OMELifecycleState) -> Set[OMELifecycleState]:
        """Get valid state transitions based on current state."""
        transitions = {
            OMELifecycleState.DESIGN: {
                OMELifecycleState.COMMISSIONING,
            },
            OMELifecycleState.COMMISSIONING: {
                OMELifecycleState.ACTIVE,
                OMELifecycleState.DESIGN,  # Rollback
            },
            OMELifecycleState.ACTIVE: {
                OMELifecycleState.MAINTENANCE,
                OMELifecycleState.DEGRADED,
                OMELifecycleState.STANDBY,
                OMELifecycleState.OFFLINE,
            },
            OMELifecycleState.MAINTENANCE: {
                OMELifecycleState.ACTIVE,
                OMELifecycleState.DEGRADED,
                OMELifecycleState.RETIRED,
            },
            OMELifecycleState.DEGRADED: {
                OMELifecycleState.ACTIVE,
                OMELifecycleState.MAINTENANCE,
                OMELifecycleState.OFFLINE,
            },
            OMELifecycleState.STANDBY: {
                OMELifecycleState.ACTIVE,
                OMELifecycleState.MAINTENANCE,
                OMELifecycleState.OFFLINE,
            },
            OMELifecycleState.OFFLINE: {
                OMELifecycleState.ACTIVE,
                OMELifecycleState.MAINTENANCE,
                OMELifecycleState.STANDBY,
                OMELifecycleState.RETIRED,
            },
            OMELifecycleState.RETIRED: set(),  # Terminal state
        }
        return transitions.get(current_state, set())

    # Event system
    def add_event_listener(self, callback: callable):
        """Add event listener for registry changes."""
        self._event_listeners.append(callback)

    def remove_event_listener(self, callback: callable):
        """Remove event listener."""
        if callback in self._event_listeners:
            self._event_listeners.remove(callback)

    def _emit_event(self, event_type: str, data: Any):
        """Emit event to all listeners."""
        for listener in self._event_listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                logger.error(f"Event listener error: {e}")

    # Index helpers
    def _add_to_index(self, index: Dict, key: Any, value: str):
        if key not in index:
            index[key] = set()
        index[key].add(value)

    def _remove_from_index(self, index: Dict, key: Any, value: str):
        if key in index and value in index[key]:
            index[key].remove(value)

    # Bulk operations
    def get_unity_scene_data(self, namespace: str = "default") -> Dict[str, Any]:
        """Get all OMEs formatted for Unity 3D scene."""
        omes = self.get_all(namespace)

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'namespace': namespace,
            'equipment': [
                ome.to_unity_dict()
                for ome in omes
                if ome.ome_type in [OMEType.EQUIPMENT, OMEType.SENSOR]
            ],
            'hierarchy': self.get_hierarchy()
        }

    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary of all OMEs."""
        equipment = self.get_by_type(OMEType.EQUIPMENT)

        health_distribution = {
            'excellent': 0,  # 90-100
            'good': 0,       # 70-89
            'fair': 0,       # 50-69
            'poor': 0,       # 30-49
            'critical': 0    # 0-29
        }

        for eq in equipment:
            score = eq.dynamic_attributes.health_score
            if score >= 90:
                health_distribution['excellent'] += 1
            elif score >= 70:
                health_distribution['good'] += 1
            elif score >= 50:
                health_distribution['fair'] += 1
            elif score >= 30:
                health_distribution['poor'] += 1
            else:
                health_distribution['critical'] += 1

        total = len(equipment)
        average_health = sum(e.dynamic_attributes.health_score for e in equipment) / total if total > 0 else 0

        return {
            'total_equipment': total,
            'average_health': round(average_health, 1),
            'distribution': health_distribution,
            'equipment_with_alarms': len([e for e in equipment if e.dynamic_attributes.active_alarms]),
            'equipment_needing_maintenance': len([
                e for e in equipment
                if e.dynamic_attributes.next_maintenance
                and e.dynamic_attributes.next_maintenance <= datetime.utcnow() + timedelta(days=7)
            ])
        }

    def export_to_json(self) -> str:
        """Export all OMEs to JSON."""
        return json.dumps({
            'version': '2.0.0',
            'exported_at': datetime.utcnow().isoformat(),
            'omes': [ome.to_dict() for ome in self._omes.values()]
        }, indent=2)

    def import_from_json(self, json_str: str, overwrite: bool = False) -> int:
        """Import OMEs from JSON. Returns count of imported OMEs."""
        data = json.loads(json_str)
        count = 0

        for ome_data in data.get('omes', []):
            ome_id = ome_data.get('id')
            if ome_id in self._omes and not overwrite:
                continue

            ome = ObservableManufacturingElement.from_dict(ome_data)

            if ome_id in self._omes:
                self.delete(ome_id)

            self.register(ome)
            count += 1

        return count


# Singleton instance for global access
_registry_instance: Optional[OMERegistry] = None


def get_ome_registry() -> OMERegistry:
    """Get the global OME registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = OMERegistry()
    return _registry_instance


# Factory functions for common OME types
def create_printer_ome(
    name: str,
    manufacturer: str = "Prusa",
    model: str = "MK3S+",
    position: Dict[str, float] = None,
    namespace: str = "default"
) -> ObservableManufacturingElement:
    """Create a 3D printer OME with sensible defaults."""
    ome = ObservableManufacturingElement(
        ome_type=OMEType.EQUIPMENT,
        name=name,
        description=f"{manufacturer} {model} 3D Printer",
        namespace=namespace
    )

    ome.static_attributes = StaticAttributes(
        manufacturer=manufacturer,
        model=model,
        capabilities=[CapabilityType.PRINTING],
        work_envelope={'x': 250, 'y': 210, 'z': 210},
        power_rating=250,
        voltage=220,
        accuracy=0.05,
        repeatability=0.02
    )

    ome.static_attributes.geometry = Geometry3D(
        model_url=f"/models/printers/{model.lower().replace('+', '_')}.gltf",
        position=position or {'x': 0, 'y': 0, 'z': 0},
        color="#FF6600"  # Orange for printers
    )

    ome.dynamic_attributes = DynamicAttributes(
        status="idle",
        operational_mode="standby",
        temperatures={'hotend': 0, 'bed': 0},
        health_score=100.0
    )

    ome.behavior_model = BehaviorModel(
        model_type="pinn",
        can_predict_failure=True,
        can_predict_quality=True,
        can_predict_rul=True
    )

    ome.tags = ["3d_printer", "fdm", manufacturer.lower()]

    return ome


def create_sensor_ome(
    name: str,
    sensor_type: SensorType,
    parent_id: str,
    location: str = "",
    namespace: str = "default"
) -> ObservableManufacturingElement:
    """Create a sensor OME attached to equipment."""
    ome = ObservableManufacturingElement(
        ome_type=OMEType.SENSOR,
        name=name,
        description=f"{sensor_type.value.title()} sensor - {location}",
        namespace=namespace,
        parent_id=parent_id
    )

    ome.static_attributes = StaticAttributes(
        capabilities=[CapabilityType.MEASUREMENT]
    )

    ome.custom_attributes = {
        'sensor_type': sensor_type.value,
        'location': location
    }

    ome.tags = ["sensor", sensor_type.value]

    return ome


def create_work_cell_ome(
    name: str,
    cell_type: str = "manufacturing",
    position: Dict[str, float] = None,
    namespace: str = "default"
) -> ObservableManufacturingElement:
    """Create a work cell OME."""
    ome = ObservableManufacturingElement(
        ome_type=OMEType.WORK_CELL,
        name=name,
        description=f"{cell_type.title()} Work Cell",
        namespace=namespace
    )

    ome.static_attributes.geometry = Geometry3D(
        position=position or {'x': 0, 'y': 0, 'z': 0},
        bounding_box={'x': 0, 'y': 0, 'z': 0, 'width': 5000, 'height': 3000, 'depth': 5000},
        color="#404040"
    )

    ome.custom_attributes = {
        'cell_type': cell_type
    }

    ome.tags = ["work_cell", cell_type]

    return ome


def create_robotic_arm_ome(
    name: str,
    manufacturer: str,
    model: str,
    dof: int = 6,
    reach_mm: float = 440.0,
    payload_g: float = 300.0,
    repeatability_mm: float = 0.5,
    is_collaborative: bool = True,
    position: Dict[str, float] = None,
    urdf_url: Optional[str] = None,
    namespace: str = "default"
) -> ObservableManufacturingElement:
    """
    Create a robotic arm OME with ISO 10218/15066 compliance.

    Args:
        name: Human-readable name for the arm
        manufacturer: Manufacturer name (e.g., "Niryo", "UFactory")
        model: Model identifier (e.g., "Ned2", "xArm Lite 6")
        dof: Degrees of freedom (typically 6 for industrial arms)
        reach_mm: Maximum reach in millimeters
        payload_g: Maximum payload capacity in grams
        repeatability_mm: Position repeatability in mm
        is_collaborative: Whether the arm is ISO/TS 15066 compliant (cobot)
        position: 3D position in world coordinates
        urdf_url: URL to URDF description file
        namespace: Multi-tenant namespace

    Returns:
        Configured robotic arm OME
    """
    ome = ObservableManufacturingElement(
        ome_type=OMEType.ROBOTIC_ARM,
        name=name,
        description=f"{manufacturer} {model} {dof}-DOF {'Cobot' if is_collaborative else 'Robot'}",
        namespace=namespace
    )

    # Capabilities based on arm type
    capabilities = [
        CapabilityType.PICK_AND_PLACE,
        CapabilityType.MANIPULATION,
        CapabilityType.ASSEMBLY,
    ]
    if is_collaborative:
        capabilities.append(CapabilityType.COLLABORATIVE)

    ome.static_attributes = StaticAttributes(
        manufacturer=manufacturer,
        model=model,
        capabilities=capabilities,
        work_envelope={
            'radius_mm': reach_mm,
            'height_mm': reach_mm * 2,  # Approximate
        },
        accuracy=repeatability_mm,
        repeatability=repeatability_mm,
        certifications=["ISO 10218-1", "ISO 10218-2"]
    )

    if is_collaborative:
        ome.static_attributes.certifications.append("ISO/TS 15066")

    # 3D visualization geometry
    model_url = urdf_url or f"/models/arms/{manufacturer.lower()}_{model.lower().replace(' ', '_')}.gltf"
    ome.static_attributes.geometry = Geometry3D(
        model_url=model_url,
        position=position or {'x': 0, 'y': 0, 'z': 0},
        color="#2196F3" if is_collaborative else "#FF5722",  # Blue for cobot, orange for industrial
    )

    # Dynamic attributes for arm state
    ome.dynamic_attributes = DynamicAttributes(
        status="idle",
        operational_mode="standby",
        positions={
            'j1': 0.0, 'j2': 0.0, 'j3': 0.0,
            'j4': 0.0, 'j5': 0.0, 'j6': 0.0,
        },
        speeds={
            'j1': 0.0, 'j2': 0.0, 'j3': 0.0,
            'j4': 0.0, 'j5': 0.0, 'j6': 0.0,
        },
        forces={
            'j1': 0.0, 'j2': 0.0, 'j3': 0.0,
            'j4': 0.0, 'j5': 0.0, 'j6': 0.0,
        },
        health_score=100.0,
    )

    # Behavior model for simulation
    ome.behavior_model = BehaviorModel(
        model_type="kinematics",
        can_simulate=True,
        can_predict_failure=True,
        can_predict_rul=True,
        parameters={
            'dof': dof,
            'reach_mm': reach_mm,
            'payload_g': payload_g,
            'repeatability_mm': repeatability_mm,
            'is_collaborative': is_collaborative,
        }
    )

    ome.custom_attributes = {
        'dof': dof,
        'reach_mm': reach_mm,
        'payload_g': payload_g,
        'is_collaborative': is_collaborative,
        'urdf_url': urdf_url,
    }

    ome.tags = [
        "robotic_arm",
        f"{dof}_dof",
        manufacturer.lower(),
        "cobot" if is_collaborative else "industrial",
    ]

    return ome


def create_niryo_ned2_ome(
    name: str,
    position: Dict[str, float] = None,
    namespace: str = "default"
) -> ObservableManufacturingElement:
    """
    Create a Niryo Ned2 robotic arm OME with pre-configured specs.

    URDF Source: https://github.com/NiryoRobotics/ned_ros
    """
    ome = create_robotic_arm_ome(
        name=name,
        manufacturer="Niryo",
        model="Ned2",
        dof=6,
        reach_mm=440.0,
        payload_g=300.0,
        repeatability_mm=0.5,
        is_collaborative=True,
        position=position,
        urdf_url="https://github.com/NiryoRobotics/ned_ros/blob/master/niryo_robot_description/urdf/ned2.urdf.xacro",
        namespace=namespace
    )

    # Ned2-specific capabilities
    ome.custom_attributes.update({
        'gripper_types': ['standard', 'vacuum', 'electromagnetic'],
        'vision_capable': True,
        'conveyor_compatible': True,
        'max_velocity_deg_s': 180.0,
    })

    ome.tags.append("niryo_ned2")
    ome.tags.append("educational")

    return ome


def create_xarm_lite6_ome(
    name: str,
    position: Dict[str, float] = None,
    namespace: str = "default"
) -> ObservableManufacturingElement:
    """
    Create a UFactory xArm Lite 6 robotic arm OME with pre-configured specs.

    URDF Source: https://github.com/xArm-Developer/xarm_ros2
    """
    ome = create_robotic_arm_ome(
        name=name,
        manufacturer="UFactory",
        model="xArm Lite 6",
        dof=6,
        reach_mm=440.0,
        payload_g=500.0,  # Slightly higher payload than Ned2
        repeatability_mm=0.1,  # Better precision
        is_collaborative=True,
        position=position,
        urdf_url="https://github.com/xArm-Developer/xarm_ros2/blob/main/xarm_description/urdf/lite6.urdf.xacro",
        namespace=namespace
    )

    # xArm Lite 6-specific capabilities
    ome.custom_attributes.update({
        'gripper_types': ['xarm_gripper', 'bio_gripper', 'vacuum'],
        'external_tool_power': True,
        'max_velocity_deg_s': 240.0,
        'max_tcp_velocity_mm_s': 500.0,
    })

    ome.tags.append("xarm_lite6")
    ome.tags.append("high_precision")

    return ome


def create_end_effector_ome(
    name: str,
    effector_type: str,
    parent_arm_id: str,
    grip_force_n: float = 20.0,
    stroke_mm: float = 40.0,
    namespace: str = "default"
) -> ObservableManufacturingElement:
    """
    Create an end effector (gripper) OME attached to a robotic arm.

    Args:
        name: Effector name
        effector_type: Type of effector (gripper, vacuum, magnetic, tool)
        parent_arm_id: ID of the parent robotic arm OME
        grip_force_n: Maximum grip force in Newtons
        stroke_mm: Gripper stroke/opening in mm
        namespace: Multi-tenant namespace
    """
    ome = ObservableManufacturingElement(
        ome_type=OMEType.END_EFFECTOR,
        name=name,
        description=f"{effector_type.title()} End Effector",
        namespace=namespace,
        parent_id=parent_arm_id
    )

    ome.static_attributes = StaticAttributes(
        capabilities=[CapabilityType.MANIPULATION],
    )

    ome.dynamic_attributes = DynamicAttributes(
        status="closed",
        positions={'stroke': 0.0},
        forces={'grip': 0.0},
    )

    ome.custom_attributes = {
        'effector_type': effector_type,
        'grip_force_n': grip_force_n,
        'stroke_mm': stroke_mm,
    }

    ome.tags = ["end_effector", effector_type]

    return ome
