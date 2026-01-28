"""
Unity Scene Data Service
========================

Prepares and manages 3D scene data for Unity visualization.

Features:
- Factory floor layout management
- Equipment 3D model references
- Real-time state to visual mapping
- LOD (Level of Detail) management
- Spatial queries for frustum culling
- Animation state management
- Material and texture mapping

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid
import logging
import json
import math
from collections import defaultdict

logger = logging.getLogger(__name__)


class ModelFormat(Enum):
    """Supported 3D model formats."""
    GLTF = "gltf"
    GLB = "glb"
    FBX = "fbx"
    OBJ = "obj"
    USD = "usd"


class LODLevel(Enum):
    """Level of Detail settings."""
    ULTRA = 0       # Full detail, < 5m
    HIGH = 1        # High detail, 5-20m
    MEDIUM = 2      # Medium detail, 20-50m
    LOW = 3         # Low detail, 50-100m
    BILLBOARD = 4   # Sprite/billboard, > 100m


class AnimationType(Enum):
    """Types of equipment animations."""
    IDLE = "idle"
    RUNNING = "running"
    PRINTING = "printing"
    MILLING = "milling"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    LOADING = "loading"
    UNLOADING = "unloading"


class HighlightStyle(Enum):
    """Highlight styles for selection/attention."""
    NONE = "none"
    OUTLINE = "outline"
    GLOW = "glow"
    PULSE = "pulse"
    BLINK = "blink"
    ARROW = "arrow"
    RING = "ring"


@dataclass
class Vector3:
    """3D vector representation."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y, 'z': self.z}

    def to_unity(self) -> Dict[str, float]:
        """Convert to Unity coordinate system (Y-up, left-handed)."""
        return {'x': self.x, 'y': self.z, 'z': self.y}

    def distance_to(self, other: 'Vector3') -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'Vector3':
        return cls(
            x=data.get('x', 0.0),
            y=data.get('y', 0.0),
            z=data.get('z', 0.0)
        )


@dataclass
class Quaternion:
    """Quaternion for rotation."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0

    def to_dict(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y, 'z': self.z, 'w': self.w}

    @classmethod
    def from_euler(cls, euler_degrees: Dict[str, float]) -> 'Quaternion':
        """Create quaternion from euler angles (degrees)."""
        # Convert degrees to radians
        pitch = math.radians(euler_degrees.get('x', 0))
        yaw = math.radians(euler_degrees.get('y', 0))
        roll = math.radians(euler_degrees.get('z', 0))

        # Calculate quaternion
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)

        return cls(
            w=cr * cp * cy + sr * sp * sy,
            x=sr * cp * cy - cr * sp * sy,
            y=cr * sp * cy + sr * cp * sy,
            z=cr * cp * sy - sr * sp * cy
        )


@dataclass
class BoundingBox:
    """Axis-aligned bounding box."""
    min_point: Vector3 = field(default_factory=Vector3)
    max_point: Vector3 = field(default_factory=Vector3)

    @property
    def center(self) -> Vector3:
        return Vector3(
            x=(self.min_point.x + self.max_point.x) / 2,
            y=(self.min_point.y + self.max_point.y) / 2,
            z=(self.min_point.z + self.max_point.z) / 2
        )

    @property
    def size(self) -> Vector3:
        return Vector3(
            x=self.max_point.x - self.min_point.x,
            y=self.max_point.y - self.min_point.y,
            z=self.max_point.z - self.min_point.z
        )

    def contains(self, point: Vector3) -> bool:
        return (
            self.min_point.x <= point.x <= self.max_point.x and
            self.min_point.y <= point.y <= self.max_point.y and
            self.min_point.z <= point.z <= self.max_point.z
        )

    def intersects(self, other: 'BoundingBox') -> bool:
        return (
            self.min_point.x <= other.max_point.x and
            self.max_point.x >= other.min_point.x and
            self.min_point.y <= other.max_point.y and
            self.max_point.y >= other.min_point.y and
            self.min_point.z <= other.max_point.z and
            self.max_point.z >= other.min_point.z
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'min': self.min_point.to_dict(),
            'max': self.max_point.to_dict(),
            'center': self.center.to_dict(),
            'size': self.size.to_dict()
        }


@dataclass
class MaterialProperties:
    """Material properties for 3D rendering."""
    base_color: str = "#808080"
    metallic: float = 0.0
    roughness: float = 0.5
    emissive_color: str = "#000000"
    emissive_intensity: float = 0.0
    opacity: float = 1.0
    texture_url: Optional[str] = None
    normal_map_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'baseColor': self.base_color,
            'metallic': self.metallic,
            'roughness': self.roughness,
            'emissiveColor': self.emissive_color,
            'emissiveIntensity': self.emissive_intensity,
            'opacity': self.opacity,
            'textureUrl': self.texture_url,
            'normalMapUrl': self.normal_map_url
        }


@dataclass
class SceneObject:
    """Base class for scene objects."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    object_type: str = "generic"

    # Transform
    position: Vector3 = field(default_factory=Vector3)
    rotation: Quaternion = field(default_factory=Quaternion)
    scale: Vector3 = field(default_factory=lambda: Vector3(1, 1, 1))

    # Hierarchy
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)

    # Visibility
    visible: bool = True
    layer: str = "default"
    render_order: int = 0

    # Interaction
    interactive: bool = True
    selectable: bool = True
    tooltip: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.object_type,
            'transform': {
                'position': self.position.to_unity(),
                'rotation': self.rotation.to_dict(),
                'scale': self.scale.to_dict()
            },
            'parentId': self.parent_id,
            'childrenIds': self.children_ids,
            'visible': self.visible,
            'layer': self.layer,
            'interactive': self.interactive,
            'selectable': self.selectable,
            'tooltip': self.tooltip
        }


@dataclass
class EquipmentSceneObject(SceneObject):
    """Scene object representing manufacturing equipment."""
    ome_id: str = ""
    equipment_type: str = "generic"

    # 3D Model
    model_url: str = ""
    model_format: ModelFormat = ModelFormat.GLTF
    lod_models: Dict[LODLevel, str] = field(default_factory=dict)

    # Visual state
    material: MaterialProperties = field(default_factory=MaterialProperties)
    animation_state: AnimationType = AnimationType.IDLE
    highlight_style: HighlightStyle = HighlightStyle.NONE
    highlight_color: str = "#FFFF00"

    # Bounding
    bounds: BoundingBox = field(default_factory=BoundingBox)

    # Status indicators
    status_color: str = "#00FF00"  # Green = OK
    show_status_indicator: bool = True

    # Attachments (gauges, displays, etc.)
    attachments: List[Dict[str, Any]] = field(default_factory=list)

    # Real-time data displays
    data_displays: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        self.object_type = "equipment"

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'omeId': self.ome_id,
            'equipmentType': self.equipment_type,
            'model': {
                'url': self.model_url,
                'format': self.model_format.value,
                'lodModels': {k.value: v for k, v in self.lod_models.items()}
            },
            'material': self.material.to_dict(),
            'animation': self.animation_state.value,
            'highlight': {
                'style': self.highlight_style.value,
                'color': self.highlight_color
            },
            'bounds': self.bounds.to_dict(),
            'statusColor': self.status_color,
            'showStatusIndicator': self.show_status_indicator,
            'attachments': self.attachments,
            'dataDisplays': self.data_displays
        })
        return base


@dataclass
class SensorVisual:
    """Visual representation of sensor data."""
    sensor_id: str
    sensor_type: str
    position: Vector3
    value: float = 0.0
    unit: str = ""
    min_value: float = 0.0
    max_value: float = 100.0
    warning_threshold: float = 80.0
    critical_threshold: float = 95.0
    show_gauge: bool = True
    gauge_style: str = "radial"  # radial, linear, digital

    def to_dict(self) -> Dict[str, Any]:
        return {
            'sensorId': self.sensor_id,
            'sensorType': self.sensor_type,
            'position': self.position.to_unity(),
            'value': self.value,
            'unit': self.unit,
            'range': {'min': self.min_value, 'max': self.max_value},
            'thresholds': {
                'warning': self.warning_threshold,
                'critical': self.critical_threshold
            },
            'showGauge': self.show_gauge,
            'gaugeStyle': self.gauge_style
        }


@dataclass
class ProductionQueueItem:
    """Visual representation of production queue item."""
    job_id: str
    work_order: str
    product_name: str
    quantity: int
    progress: float  # 0-100
    status: str
    assigned_equipment: str
    estimated_completion: Optional[datetime] = None
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'jobId': self.job_id,
            'workOrder': self.work_order,
            'productName': self.product_name,
            'quantity': self.quantity,
            'progress': self.progress,
            'status': self.status,
            'assignedEquipment': self.assigned_equipment,
            'estimatedCompletion': self.estimated_completion.isoformat() if self.estimated_completion else None,
            'priority': self.priority
        }


@dataclass
class FlowPath:
    """Visual representation of material/product flow."""
    id: str
    from_equipment: str
    to_equipment: str
    path_points: List[Vector3] = field(default_factory=list)
    color: str = "#0088FF"
    animated: bool = True
    flow_rate: float = 1.0  # Particles per second
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'from': self.from_equipment,
            'to': self.to_equipment,
            'path': [p.to_unity() for p in self.path_points],
            'color': self.color,
            'animated': self.animated,
            'flowRate': self.flow_rate,
            'active': self.active
        }


@dataclass
class Annotation3D:
    """3D annotation/label in scene."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    position: Vector3 = field(default_factory=Vector3)
    target_id: Optional[str] = None  # ID of object being annotated
    style: str = "label"  # label, callout, tooltip, warning
    color: str = "#FFFFFF"
    background_color: str = "#000000AA"
    font_size: int = 14
    always_visible: bool = False
    billboard: bool = True  # Always face camera

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'text': self.text,
            'position': self.position.to_unity(),
            'targetId': self.target_id,
            'style': self.style,
            'color': self.color,
            'backgroundColor': self.background_color,
            'fontSize': self.font_size,
            'alwaysVisible': self.always_visible,
            'billboard': self.billboard
        }


@dataclass
class CameraPreset:
    """Predefined camera position/view."""
    id: str
    name: str
    position: Vector3
    target: Vector3
    fov: float = 60.0
    near_clip: float = 0.1
    far_clip: float = 1000.0
    thumbnail_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'position': self.position.to_unity(),
            'target': self.target.to_unity(),
            'fov': self.fov,
            'nearClip': self.near_clip,
            'farClip': self.far_clip,
            'thumbnailUrl': self.thumbnail_url
        }


@dataclass
class SceneSettings:
    """Global scene settings."""
    # Lighting
    ambient_color: str = "#404040"
    ambient_intensity: float = 0.5
    sun_color: str = "#FFFFEE"
    sun_intensity: float = 1.0
    sun_direction: Vector3 = field(default_factory=lambda: Vector3(-0.5, -1, -0.5))

    # Environment
    sky_color: str = "#87CEEB"
    floor_color: str = "#808080"
    grid_visible: bool = True
    grid_size: float = 1000.0
    grid_divisions: int = 100

    # Post-processing
    bloom_enabled: bool = True
    bloom_intensity: float = 0.5
    ambient_occlusion: bool = True
    antialiasing: str = "msaa_4x"

    # Performance
    max_visible_objects: int = 1000
    lod_bias: float = 1.0
    shadow_distance: float = 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'lighting': {
                'ambientColor': self.ambient_color,
                'ambientIntensity': self.ambient_intensity,
                'sunColor': self.sun_color,
                'sunIntensity': self.sun_intensity,
                'sunDirection': self.sun_direction.to_unity()
            },
            'environment': {
                'skyColor': self.sky_color,
                'floorColor': self.floor_color,
                'gridVisible': self.grid_visible,
                'gridSize': self.grid_size,
                'gridDivisions': self.grid_divisions
            },
            'postProcessing': {
                'bloom': self.bloom_enabled,
                'bloomIntensity': self.bloom_intensity,
                'ambientOcclusion': self.ambient_occlusion,
                'antialiasing': self.antialiasing
            },
            'performance': {
                'maxVisibleObjects': self.max_visible_objects,
                'lodBias': self.lod_bias,
                'shadowDistance': self.shadow_distance
            }
        }


class SceneDataService:
    """
    Service for preparing and managing Unity scene data.

    Responsibilities:
    - Build complete scene graph
    - Map OME state to visual properties
    - Manage spatial indexing for efficient queries
    - Handle LOD calculations
    - Prepare delta updates
    """

    def __init__(self):
        # Scene objects
        self._equipment: Dict[str, EquipmentSceneObject] = {}
        self._sensors: Dict[str, SensorVisual] = {}
        self._annotations: Dict[str, Annotation3D] = {}
        self._flow_paths: Dict[str, FlowPath] = {}
        self._camera_presets: Dict[str, CameraPreset] = {}

        # Production data
        self._production_queue: List[ProductionQueueItem] = []

        # Scene settings
        self._settings: SceneSettings = SceneSettings()

        # Spatial index (simple grid-based)
        self._spatial_grid: Dict[Tuple[int, int], Set[str]] = defaultdict(set)
        self._grid_size: float = 10.0  # 10 meter grid cells

        # Change tracking
        self._last_update_time: datetime = datetime.utcnow()
        self._changed_objects: Set[str] = set()
        self._version: int = 0

        # Model library
        self._model_library: Dict[str, Dict[str, Any]] = self._init_model_library()

        logger.info("SceneDataService initialized")

    def _init_model_library(self) -> Dict[str, Dict[str, Any]]:
        """Initialize default 3D model references."""
        return {
            'prusa_mk3s': {
                'model_url': '/models/printers/prusa_mk3s.gltf',
                'thumbnail': '/thumbnails/prusa_mk3s.png',
                'bounds': {'width': 0.5, 'height': 0.6, 'depth': 0.5},
                'default_color': '#FF6600'
            },
            'prusa_mk4': {
                'model_url': '/models/printers/prusa_mk4.gltf',
                'thumbnail': '/thumbnails/prusa_mk4.png',
                'bounds': {'width': 0.5, 'height': 0.6, 'depth': 0.5},
                'default_color': '#FF6600'
            },
            'bambu_a1': {
                'model_url': '/models/printers/bambu_a1.gltf',
                'thumbnail': '/thumbnails/bambu_a1.png',
                'bounds': {'width': 0.4, 'height': 0.5, 'depth': 0.4},
                'default_color': '#00AA00'
            },
            'bambu_x1': {
                'model_url': '/models/printers/bambu_x1.gltf',
                'thumbnail': '/thumbnails/bambu_x1.png',
                'bounds': {'width': 0.5, 'height': 0.7, 'depth': 0.5},
                'default_color': '#333333'
            },
            'grbl_mill': {
                'model_url': '/models/mills/grbl_mill.gltf',
                'thumbnail': '/thumbnails/grbl_mill.png',
                'bounds': {'width': 0.8, 'height': 0.6, 'depth': 0.6},
                'default_color': '#0066CC'
            },
            'laser_engraver': {
                'model_url': '/models/lasers/laser_engraver.gltf',
                'thumbnail': '/thumbnails/laser_engraver.png',
                'bounds': {'width': 0.6, 'height': 0.3, 'depth': 0.5},
                'default_color': '#CC0000'
            },
            'inspection_station': {
                'model_url': '/models/stations/inspection.gltf',
                'thumbnail': '/thumbnails/inspection.png',
                'bounds': {'width': 1.0, 'height': 1.5, 'depth': 0.8},
                'default_color': '#AAAAAA'
            },
            'conveyor': {
                'model_url': '/models/transport/conveyor.gltf',
                'thumbnail': '/thumbnails/conveyor.png',
                'bounds': {'width': 2.0, 'height': 0.4, 'depth': 0.5},
                'default_color': '#666666'
            },
            'robot_arm': {
                'model_url': '/models/robots/arm_6dof.gltf',
                'thumbnail': '/thumbnails/robot_arm.png',
                'bounds': {'width': 0.5, 'height': 1.2, 'depth': 0.5},
                'default_color': '#FF8800'
            },
            'storage_rack': {
                'model_url': '/models/storage/rack.gltf',
                'thumbnail': '/thumbnails/storage_rack.png',
                'bounds': {'width': 2.0, 'height': 2.5, 'depth': 0.8},
                'default_color': '#4488AA'
            }
        }

    # ================== Equipment Management ==================

    def add_equipment(
        self,
        ome_id: str,
        name: str,
        equipment_type: str,
        position: Vector3,
        rotation: Quaternion = None
    ) -> EquipmentSceneObject:
        """Add equipment to scene."""
        # Get model info from library
        model_info = self._model_library.get(
            equipment_type.lower().replace(' ', '_'),
            self._model_library.get('prusa_mk3s')  # Default
        )

        equipment = EquipmentSceneObject(
            ome_id=ome_id,
            name=name,
            equipment_type=equipment_type,
            position=position,
            rotation=rotation or Quaternion(),
            model_url=model_info['model_url'],
            model_format=ModelFormat.GLTF
        )

        # Set bounds from model info
        bounds_info = model_info.get('bounds', {})
        half_w = bounds_info.get('width', 1.0) / 2
        half_h = bounds_info.get('height', 1.0) / 2
        half_d = bounds_info.get('depth', 1.0) / 2

        equipment.bounds = BoundingBox(
            min_point=Vector3(position.x - half_w, position.y, position.z - half_d),
            max_point=Vector3(position.x + half_w, position.y + bounds_info.get('height', 1.0), position.z + half_d)
        )

        # Set default color
        equipment.material.base_color = model_info.get('default_color', '#808080')

        # Add to scene
        self._equipment[ome_id] = equipment
        self._add_to_spatial_index(ome_id, position)
        self._mark_changed(ome_id)

        logger.info(f"Added equipment: {name} ({ome_id})")

        return equipment

    def update_equipment_state(
        self,
        ome_id: str,
        state_data: Dict[str, Any]
    ) -> bool:
        """Update equipment visual state from OME data."""
        if ome_id not in self._equipment:
            return False

        equipment = self._equipment[ome_id]

        # Map status to color
        status = state_data.get('status', 'unknown')
        equipment.status_color = self._status_to_color(status)

        # Map status to animation
        equipment.animation_state = self._status_to_animation(status)

        # Update material if overheating
        temps = state_data.get('temperatures', {})
        max_temp = max(temps.values()) if temps else 0
        if max_temp > 250:
            equipment.material.emissive_color = "#FF3300"
            equipment.material.emissive_intensity = min((max_temp - 250) / 50, 1.0)
        else:
            equipment.material.emissive_intensity = 0.0

        # Update data displays
        equipment.data_displays = [
            {
                'type': 'temperature',
                'values': temps,
                'position': {'x': 0.3, 'y': 0.5, 'z': 0}
            },
            {
                'type': 'oee',
                'value': state_data.get('oee', 0),
                'position': {'x': -0.3, 'y': 0.5, 'z': 0}
            }
        ]

        # Update tooltip
        equipment.tooltip = f"{equipment.name}\nStatus: {status}\nOEE: {state_data.get('oee', 0):.1f}%"

        self._mark_changed(ome_id)

        return True

    def set_equipment_highlight(
        self,
        ome_id: str,
        style: HighlightStyle,
        color: str = "#FFFF00"
    ):
        """Set highlight on equipment."""
        if ome_id in self._equipment:
            self._equipment[ome_id].highlight_style = style
            self._equipment[ome_id].highlight_color = color
            self._mark_changed(ome_id)

    def _status_to_color(self, status: str) -> str:
        """Map equipment status to indicator color."""
        color_map = {
            'running': '#00FF00',    # Green
            'printing': '#00FF00',
            'idle': '#00AAFF',       # Blue
            'standby': '#00AAFF',
            'warning': '#FFAA00',    # Orange
            'error': '#FF0000',      # Red
            'fault': '#FF0000',
            'maintenance': '#FFFF00',  # Yellow
            'offline': '#808080',    # Gray
            'unknown': '#808080'
        }
        return color_map.get(status.lower(), '#808080')

    def _status_to_animation(self, status: str) -> AnimationType:
        """Map equipment status to animation state."""
        animation_map = {
            'running': AnimationType.RUNNING,
            'printing': AnimationType.PRINTING,
            'milling': AnimationType.MILLING,
            'idle': AnimationType.IDLE,
            'standby': AnimationType.IDLE,
            'error': AnimationType.ERROR,
            'fault': AnimationType.ERROR,
            'maintenance': AnimationType.MAINTENANCE,
            'starting': AnimationType.STARTUP,
            'stopping': AnimationType.SHUTDOWN,
        }
        return animation_map.get(status.lower(), AnimationType.IDLE)

    # ================== Sensors ==================

    def add_sensor_visual(
        self,
        sensor_id: str,
        sensor_type: str,
        position: Vector3,
        **kwargs
    ) -> SensorVisual:
        """Add sensor gauge/display to scene."""
        sensor = SensorVisual(
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            position=position,
            **kwargs
        )
        self._sensors[sensor_id] = sensor
        self._mark_changed(sensor_id)
        return sensor

    def update_sensor_value(self, sensor_id: str, value: float):
        """Update sensor display value."""
        if sensor_id in self._sensors:
            self._sensors[sensor_id].value = value
            self._mark_changed(sensor_id)

    # ================== Annotations ==================

    def add_annotation(
        self,
        text: str,
        position: Vector3 = None,
        target_id: str = None,
        **kwargs
    ) -> Annotation3D:
        """Add 3D annotation to scene."""
        annotation = Annotation3D(
            text=text,
            position=position or Vector3(),
            target_id=target_id,
            **kwargs
        )
        self._annotations[annotation.id] = annotation
        self._mark_changed(annotation.id)
        return annotation

    def remove_annotation(self, annotation_id: str):
        """Remove annotation from scene."""
        if annotation_id in self._annotations:
            del self._annotations[annotation_id]
            self._mark_changed(annotation_id)

    # ================== Flow Paths ==================

    def add_flow_path(
        self,
        from_equipment: str,
        to_equipment: str,
        waypoints: List[Vector3] = None
    ) -> FlowPath:
        """Add material/product flow visualization."""
        path_id = f"flow_{from_equipment}_{to_equipment}"

        # Build path points
        if waypoints:
            path_points = waypoints
        else:
            # Auto-generate simple path
            from_eq = self._equipment.get(from_equipment)
            to_eq = self._equipment.get(to_equipment)

            if from_eq and to_eq:
                path_points = [
                    from_eq.position,
                    Vector3(
                        (from_eq.position.x + to_eq.position.x) / 2,
                        max(from_eq.position.y, to_eq.position.y) + 0.5,
                        (from_eq.position.z + to_eq.position.z) / 2
                    ),
                    to_eq.position
                ]
            else:
                path_points = []

        flow = FlowPath(
            id=path_id,
            from_equipment=from_equipment,
            to_equipment=to_equipment,
            path_points=path_points
        )

        self._flow_paths[path_id] = flow
        self._mark_changed(path_id)

        return flow

    # ================== Camera Presets ==================

    def add_camera_preset(
        self,
        name: str,
        position: Vector3,
        target: Vector3,
        **kwargs
    ) -> CameraPreset:
        """Add camera preset."""
        preset = CameraPreset(
            id=str(uuid.uuid4()),
            name=name,
            position=position,
            target=target,
            **kwargs
        )
        self._camera_presets[preset.id] = preset
        return preset

    def get_default_camera_presets(self) -> List[CameraPreset]:
        """Get default camera views for factory."""
        presets = [
            CameraPreset(
                id='overview',
                name='Factory Overview',
                position=Vector3(20, 15, 20),
                target=Vector3(0, 0, 0),
                fov=60
            ),
            CameraPreset(
                id='top_down',
                name='Top Down',
                position=Vector3(0, 30, 0),
                target=Vector3(0, 0, 0),
                fov=45
            ),
            CameraPreset(
                id='front',
                name='Front View',
                position=Vector3(0, 5, 20),
                target=Vector3(0, 2, 0),
                fov=50
            )
        ]

        for preset in presets:
            self._camera_presets[preset.id] = preset

        return presets

    # ================== Production Queue ==================

    def update_production_queue(self, jobs: List[Dict[str, Any]]):
        """Update production queue display."""
        self._production_queue = [
            ProductionQueueItem(
                job_id=j.get('job_id', ''),
                work_order=j.get('work_order', ''),
                product_name=j.get('product_name', ''),
                quantity=j.get('quantity', 0),
                progress=j.get('progress', 0),
                status=j.get('status', 'pending'),
                assigned_equipment=j.get('assigned_equipment', ''),
                estimated_completion=datetime.fromisoformat(j['estimated_completion']) if j.get('estimated_completion') else None,
                priority=j.get('priority', 0)
            )
            for j in jobs
        ]
        self._mark_changed('production_queue')

    # ================== Spatial Queries ==================

    def _add_to_spatial_index(self, object_id: str, position: Vector3):
        """Add object to spatial grid."""
        cell = self._get_grid_cell(position)
        self._spatial_grid[cell].add(object_id)

    def _get_grid_cell(self, position: Vector3) -> Tuple[int, int]:
        """Get grid cell for position."""
        return (
            int(position.x / self._grid_size),
            int(position.z / self._grid_size)
        )

    def get_objects_in_frustum(
        self,
        camera_position: Vector3,
        camera_forward: Vector3,
        fov: float,
        near: float,
        far: float
    ) -> List[str]:
        """Get objects visible in camera frustum (simplified)."""
        # Simplified: return all objects within distance
        visible = []

        for ome_id, equipment in self._equipment.items():
            distance = camera_position.distance_to(equipment.position)
            if near <= distance <= far:
                visible.append(ome_id)

        return visible

    def get_objects_near(
        self,
        position: Vector3,
        radius: float
    ) -> List[str]:
        """Get objects within radius of position."""
        nearby = []

        for ome_id, equipment in self._equipment.items():
            if position.distance_to(equipment.position) <= radius:
                nearby.append(ome_id)

        return nearby

    # ================== Scene Export ==================

    def get_full_scene(self) -> Dict[str, Any]:
        """Get complete scene data for initial load."""
        self._version += 1

        return {
            'version': self._version,
            'timestamp': datetime.utcnow().isoformat(),
            'settings': self._settings.to_dict(),
            'equipment': [eq.to_dict() for eq in self._equipment.values()],
            'sensors': [s.to_dict() for s in self._sensors.values()],
            'annotations': [a.to_dict() for a in self._annotations.values()],
            'flowPaths': [f.to_dict() for f in self._flow_paths.values()],
            'cameraPresets': [c.to_dict() for c in self._camera_presets.values()],
            'productionQueue': [p.to_dict() for p in self._production_queue],
            'modelLibrary': self._model_library
        }

    def get_delta_scene(self, since_version: int) -> Dict[str, Any]:
        """Get only changes since version."""
        changes = {
            'fromVersion': since_version,
            'toVersion': self._version,
            'timestamp': datetime.utcnow().isoformat(),
            'updates': [],
            'removes': []
        }

        for object_id in self._changed_objects:
            if object_id in self._equipment:
                changes['updates'].append({
                    'type': 'equipment',
                    'id': object_id,
                    'data': self._equipment[object_id].to_dict()
                })
            elif object_id in self._sensors:
                changes['updates'].append({
                    'type': 'sensor',
                    'id': object_id,
                    'data': self._sensors[object_id].to_dict()
                })
            elif object_id == 'production_queue':
                changes['updates'].append({
                    'type': 'productionQueue',
                    'data': [p.to_dict() for p in self._production_queue]
                })
            # Could be a removed object
            else:
                changes['removes'].append(object_id)

        # Clear change tracking
        self._changed_objects.clear()

        return changes

    def _mark_changed(self, object_id: str):
        """Mark object as changed for delta updates."""
        self._changed_objects.add(object_id)
        self._last_update_time = datetime.utcnow()
        self._version += 1

    # ================== Settings ==================

    def update_settings(self, settings: Dict[str, Any]):
        """Update scene settings."""
        if 'lighting' in settings:
            lighting = settings['lighting']
            if 'ambientColor' in lighting:
                self._settings.ambient_color = lighting['ambientColor']
            if 'ambientIntensity' in lighting:
                self._settings.ambient_intensity = lighting['ambientIntensity']
            if 'sunColor' in lighting:
                self._settings.sun_color = lighting['sunColor']
            if 'sunIntensity' in lighting:
                self._settings.sun_intensity = lighting['sunIntensity']

        if 'environment' in settings:
            env = settings['environment']
            if 'gridVisible' in env:
                self._settings.grid_visible = env['gridVisible']

        self._mark_changed('settings')


# Singleton instance
_scene_data_instance: Optional[SceneDataService] = None


def get_scene_data_service() -> SceneDataService:
    """Get the global SceneDataService instance."""
    global _scene_data_instance
    if _scene_data_instance is None:
        _scene_data_instance = SceneDataService()
    return _scene_data_instance
