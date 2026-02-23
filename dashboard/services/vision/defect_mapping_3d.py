"""
3D Defect Mapping Service

LegoMCP World-Class Manufacturing Platform v2.0
ISO 23247 Compliant Digital Twin Implementation

Maps 2D defect detections from vision systems to 3D spatial coordinates
for visualization in Unity digital twins.

Features:
- Multi-camera triangulation for 3D localization
- Point cloud generation from defect regions
- Defect clustering and classification
- Temporal tracking across layers
- Integration with digital twin visualization

Research Value:
- Novel approach to 2D-to-3D defect mapping in additive manufacturing
- Real-time defect localization for in-situ correction
- Spatial defect density analysis for root cause investigation

References:
- ISO 23247 (2021). Digital Twin Framework for Manufacturing
- Hartley, R. & Zisserman, A. (2003). Multiple View Geometry

Author: LegoMCP Team
Version: 2.0.0
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any, Set
import numpy as np
import logging
import threading
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class DefectType(Enum):
    """Types of manufacturing defects."""
    SURFACE_SCRATCH = auto()
    VOID = auto()
    DELAMINATION = auto()
    WARPING = auto()
    STRINGING = auto()
    LAYER_SHIFT = auto()
    UNDER_EXTRUSION = auto()
    OVER_EXTRUSION = auto()
    BLOB = auto()
    ZITS = auto()
    BURN_MARK = auto()
    COLOR_VARIATION = auto()
    DIMENSIONAL_ERROR = auto()
    UNKNOWN = auto()


class DefectSeverity(Enum):
    """Severity levels for defects."""
    COSMETIC = 1  # Visual only, no functional impact
    MINOR = 2  # Slight deviation, acceptable
    MODERATE = 3  # Noticeable, may affect quality
    MAJOR = 4  # Significant, requires attention
    CRITICAL = 5  # Severe, part rejection required


class CameraModel(Enum):
    """Camera projection models."""
    PINHOLE = auto()
    FISHEYE = auto()
    ORTHOGRAPHIC = auto()


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Vector3D:
    """3D vector/point."""
    x: float
    y: float
    z: float

    def to_array(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> 'Vector3D':
        return cls(float(arr[0]), float(arr[1]), float(arr[2]))

    def distance_to(self, other: 'Vector3D') -> float:
        return np.linalg.norm(self.to_array() - other.to_array())

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass
class BoundingBox3D:
    """3D bounding box."""
    min_point: Vector3D
    max_point: Vector3D

    @property
    def center(self) -> Vector3D:
        return Vector3D(
            (self.min_point.x + self.max_point.x) / 2,
            (self.min_point.y + self.max_point.y) / 2,
            (self.min_point.z + self.max_point.z) / 2,
        )

    @property
    def dimensions(self) -> Vector3D:
        return Vector3D(
            self.max_point.x - self.min_point.x,
            self.max_point.y - self.min_point.y,
            self.max_point.z - self.min_point.z,
        )

    @property
    def volume(self) -> float:
        d = self.dimensions
        return d.x * d.y * d.z

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min": self.min_point.to_dict(),
            "max": self.max_point.to_dict(),
            "center": self.center.to_dict(),
            "dimensions": self.dimensions.to_dict(),
        }


@dataclass
class CameraCalibration:
    """Camera intrinsic and extrinsic calibration."""
    camera_id: str
    model: CameraModel = CameraModel.PINHOLE

    # Intrinsic parameters
    focal_length_x: float = 1000.0  # pixels
    focal_length_y: float = 1000.0  # pixels
    principal_point_x: float = 640.0  # pixels
    principal_point_y: float = 480.0  # pixels
    image_width: int = 1280
    image_height: int = 960
    distortion_coeffs: List[float] = field(default_factory=lambda: [0.0] * 5)

    # Extrinsic parameters (camera pose in world frame)
    position: Vector3D = field(default_factory=lambda: Vector3D(0, 0, 0.5))
    rotation_matrix: np.ndarray = field(default_factory=lambda: np.eye(3))

    def get_intrinsic_matrix(self) -> np.ndarray:
        """Get 3x3 camera intrinsic matrix."""
        return np.array([
            [self.focal_length_x, 0, self.principal_point_x],
            [0, self.focal_length_y, self.principal_point_y],
            [0, 0, 1],
        ])

    def get_projection_matrix(self) -> np.ndarray:
        """Get 3x4 projection matrix."""
        K = self.get_intrinsic_matrix()
        R = self.rotation_matrix
        t = -R @ self.position.to_array()

        Rt = np.hstack([R, t.reshape(3, 1)])
        return K @ Rt


@dataclass
class Defect2D:
    """2D defect detection from vision system."""
    detection_id: str
    camera_id: str
    defect_type: DefectType
    confidence: float
    bbox_x: float  # Normalized [0, 1]
    bbox_y: float
    bbox_width: float
    bbox_height: float
    mask_points: Optional[List[Tuple[float, float]]] = None
    layer_number: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Defect3D:
    """3D defect with spatial localization."""
    defect_id: str
    defect_type: DefectType
    severity: DefectSeverity
    position: Vector3D
    bounding_box: BoundingBox3D
    confidence: float
    point_cloud: np.ndarray  # Nx3 array of points
    source_detections: List[str]  # IDs of 2D detections used
    layer_range: Tuple[int, int]  # (start_layer, end_layer)
    volume_mm3: float
    surface_area_mm2: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "defect_id": self.defect_id,
            "defect_type": self.defect_type.name,
            "severity": self.severity.name,
            "position": self.position.to_dict(),
            "bounding_box": self.bounding_box.to_dict(),
            "confidence": self.confidence,
            "point_count": len(self.point_cloud),
            "source_detections": self.source_detections,
            "layer_range": list(self.layer_range),
            "volume_mm3": self.volume_mm3,
            "surface_area_mm2": self.surface_area_mm2,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class DefectCluster:
    """Cluster of related 3D defects."""
    cluster_id: str
    defects: List[Defect3D]
    center: Vector3D
    bounding_box: BoundingBox3D
    dominant_type: DefectType
    total_volume_mm3: float
    affected_layers: Set[int]
    root_cause_hypothesis: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "defect_count": len(self.defects),
            "center": self.center.to_dict(),
            "bounding_box": self.bounding_box.to_dict(),
            "dominant_type": self.dominant_type.name,
            "total_volume_mm3": self.total_volume_mm3,
            "affected_layers": list(self.affected_layers),
            "root_cause_hypothesis": self.root_cause_hypothesis,
        }


@dataclass
class QualityHeatmap:
    """Spatial quality heatmap."""
    heatmap_id: str
    grid_resolution: Tuple[int, int, int]  # (x, y, z) cells
    cell_size_mm: float
    origin: Vector3D
    values: np.ndarray  # 3D array of defect density
    defect_count_by_cell: np.ndarray
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_value_at(self, point: Vector3D) -> float:
        """Get heatmap value at a 3D point."""
        # Convert world point to grid indices
        offset = point.to_array() - self.origin.to_array()
        indices = (offset / self.cell_size_mm).astype(int)

        # Clamp to valid range
        indices = np.clip(indices, 0, np.array(self.grid_resolution) - 1)

        return float(self.values[indices[0], indices[1], indices[2]])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "heatmap_id": self.heatmap_id,
            "grid_resolution": list(self.grid_resolution),
            "cell_size_mm": self.cell_size_mm,
            "origin": self.origin.to_dict(),
            "max_value": float(np.max(self.values)),
            "mean_value": float(np.mean(self.values)),
            "total_defects": int(np.sum(self.defect_count_by_cell)),
        }


# =============================================================================
# 3D Defect Mapping Service
# =============================================================================

class DefectMapping3DService:
    """
    Service for mapping 2D defect detections to 3D spatial coordinates.

    Provides:
    - Multi-camera triangulation
    - Point cloud generation
    - Defect clustering
    - Quality heatmap generation
    - Temporal tracking
    """

    def __init__(
        self,
        build_volume: Tuple[float, float, float] = (200.0, 200.0, 200.0),
        layer_height: float = 0.2,
    ):
        """
        Initialize the 3D defect mapping service.

        Args:
            build_volume: Build volume in mm (x, y, z)
            layer_height: Layer height in mm
        """
        self.build_volume = build_volume
        self.layer_height = layer_height

        # Camera calibrations
        self._cameras: Dict[str, CameraCalibration] = {}

        # Defect storage
        self._detections_2d: Dict[str, List[Defect2D]] = defaultdict(list)  # by camera
        self._defects_3d: Dict[str, Defect3D] = {}  # by defect_id
        self._clusters: Dict[str, DefectCluster] = {}

        # Layer tracking
        self._current_layer: int = 0
        self._layer_defects: Dict[int, List[str]] = defaultdict(list)

        # Heatmap cache
        self._heatmap_cache: Optional[QualityHeatmap] = None
        self._heatmap_dirty: bool = True

        # Thread safety
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            "detections_processed": 0,
            "defects_mapped": 0,
            "clusters_formed": 0,
            "triangulation_failures": 0,
        }

    # =========================================================================
    # Camera Management
    # =========================================================================

    def register_camera(
        self,
        camera_id: str,
        calibration: CameraCalibration
    ) -> None:
        """Register a camera with its calibration."""
        with self._lock:
            calibration.camera_id = camera_id
            self._cameras[camera_id] = calibration
            logger.info(f"Registered camera: {camera_id}")

    def get_camera(self, camera_id: str) -> Optional[CameraCalibration]:
        """Get camera calibration."""
        return self._cameras.get(camera_id)

    def setup_default_cameras(self) -> None:
        """Set up default camera configuration for typical printer setup."""
        # Top-down camera
        top_cam = CameraCalibration(
            camera_id="top_camera",
            position=Vector3D(
                self.build_volume[0] / 2,
                self.build_volume[1] / 2,
                self.build_volume[2] + 100,
            ),
            rotation_matrix=np.array([
                [1, 0, 0],
                [0, -1, 0],
                [0, 0, -1],
            ]),  # Looking down
        )
        self.register_camera("top_camera", top_cam)

        # Side camera (front)
        front_cam = CameraCalibration(
            camera_id="front_camera",
            position=Vector3D(
                self.build_volume[0] / 2,
                -100,
                self.build_volume[2] / 2,
            ),
            rotation_matrix=np.array([
                [1, 0, 0],
                [0, 0, -1],
                [0, 1, 0],
            ]),  # Looking at print from front
        )
        self.register_camera("front_camera", front_cam)

        # Side camera (right)
        right_cam = CameraCalibration(
            camera_id="right_camera",
            position=Vector3D(
                self.build_volume[0] + 100,
                self.build_volume[1] / 2,
                self.build_volume[2] / 2,
            ),
            rotation_matrix=np.array([
                [0, 1, 0],
                [0, 0, -1],
                [-1, 0, 0],
            ]),  # Looking from right side
        )
        self.register_camera("right_camera", right_cam)

    # =========================================================================
    # 2D Detection Ingestion
    # =========================================================================

    def add_detection(self, detection: Defect2D) -> str:
        """
        Add a 2D defect detection from vision system.

        Returns:
            Detection ID
        """
        with self._lock:
            self._detections_2d[detection.camera_id].append(detection)
            self._stats["detections_processed"] += 1
            self._heatmap_dirty = True

            return detection.detection_id

    def add_detection_from_dict(
        self,
        camera_id: str,
        detection_data: Dict[str, Any]
    ) -> str:
        """
        Add detection from dictionary (e.g., from API).

        Args:
            camera_id: Camera identifier
            detection_data: Detection data with bbox and type info

        Returns:
            Detection ID
        """
        detection = Defect2D(
            detection_id=detection_data.get("id", str(uuid.uuid4())),
            camera_id=camera_id,
            defect_type=DefectType[detection_data.get("type", "UNKNOWN").upper()],
            confidence=detection_data.get("confidence", 0.5),
            bbox_x=detection_data.get("bbox", {}).get("x", 0.5),
            bbox_y=detection_data.get("bbox", {}).get("y", 0.5),
            bbox_width=detection_data.get("bbox", {}).get("width", 0.1),
            bbox_height=detection_data.get("bbox", {}).get("height", 0.1),
            layer_number=detection_data.get("layer", self._current_layer),
            metadata=detection_data.get("metadata", {}),
        )

        return self.add_detection(detection)

    # =========================================================================
    # 3D Triangulation
    # =========================================================================

    def triangulate_point(
        self,
        observations: List[Tuple[str, float, float]]
    ) -> Optional[Vector3D]:
        """
        Triangulate 3D point from multiple 2D observations.

        Args:
            observations: List of (camera_id, u, v) normalized coordinates

        Returns:
            3D point or None if triangulation failed
        """
        if len(observations) < 2:
            return None

        # Build linear system for DLT triangulation
        A = []

        for camera_id, u, v in observations:
            camera = self._cameras.get(camera_id)
            if not camera:
                continue

            P = camera.get_projection_matrix()

            # Two equations per observation
            A.append(u * P[2] - P[0])
            A.append(v * P[2] - P[1])

        if len(A) < 4:
            return None

        A = np.array(A)

        # SVD solution
        try:
            _, _, Vt = np.linalg.svd(A)
            X = Vt[-1]
            X = X[:3] / X[3]  # Dehomogenize

            # Validate point is within build volume
            if not self._is_in_build_volume(X):
                return None

            return Vector3D.from_array(X)

        except Exception as e:
            logger.warning(f"Triangulation failed: {e}")
            self._stats["triangulation_failures"] += 1
            return None

    def _is_in_build_volume(self, point: np.ndarray) -> bool:
        """Check if point is within build volume."""
        return (
            0 <= point[0] <= self.build_volume[0] and
            0 <= point[1] <= self.build_volume[1] and
            0 <= point[2] <= self.build_volume[2]
        )

    def map_detection_to_3d(
        self,
        detection: Defect2D,
        use_layer_height: bool = True
    ) -> Optional[Defect3D]:
        """
        Map a 2D detection to 3D using layer height constraint or triangulation.

        Args:
            detection: 2D defect detection
            use_layer_height: Use layer height as Z constraint if True

        Returns:
            3D defect or None if mapping failed
        """
        camera = self._cameras.get(detection.camera_id)
        if not camera:
            return None

        # Calculate 3D position
        if use_layer_height and detection.layer_number is not None:
            # Use layer height as Z constraint
            z = detection.layer_number * self.layer_height
            position = self._backproject_with_z(camera, detection, z)
        else:
            # Try triangulation with other cameras
            matching_detections = self._find_matching_detections(detection)
            if matching_detections:
                observations = [
                    (detection.camera_id, detection.bbox_x + detection.bbox_width/2,
                     detection.bbox_y + detection.bbox_height/2)
                ]
                for d in matching_detections:
                    observations.append((
                        d.camera_id,
                        d.bbox_x + d.bbox_width/2,
                        d.bbox_y + d.bbox_height/2,
                    ))
                position = self.triangulate_point(observations)
            else:
                # Fall back to layer height if available
                if detection.layer_number is not None:
                    z = detection.layer_number * self.layer_height
                    position = self._backproject_with_z(camera, detection, z)
                else:
                    return None

        if position is None:
            return None

        # Generate point cloud for defect region
        point_cloud = self._generate_defect_point_cloud(
            camera, detection, position
        )

        # Calculate bounding box
        if len(point_cloud) > 0:
            min_pt = Vector3D.from_array(point_cloud.min(axis=0))
            max_pt = Vector3D.from_array(point_cloud.max(axis=0))
        else:
            # Estimate from 2D bbox
            size = max(detection.bbox_width, detection.bbox_height) * self.build_volume[0]
            min_pt = Vector3D(position.x - size/2, position.y - size/2, position.z - self.layer_height)
            max_pt = Vector3D(position.x + size/2, position.y + size/2, position.z + self.layer_height)

        bbox = BoundingBox3D(min_pt, max_pt)

        # Estimate severity from defect type and size
        severity = self._estimate_severity(detection.defect_type, bbox.volume)

        # Create 3D defect
        defect_3d = Defect3D(
            defect_id=str(uuid.uuid4()),
            defect_type=detection.defect_type,
            severity=severity,
            position=position,
            bounding_box=bbox,
            confidence=detection.confidence,
            point_cloud=point_cloud,
            source_detections=[detection.detection_id],
            layer_range=(
                detection.layer_number or self._current_layer,
                detection.layer_number or self._current_layer,
            ),
            volume_mm3=bbox.volume,
            surface_area_mm2=self._estimate_surface_area(bbox),
            metadata=detection.metadata,
        )

        with self._lock:
            self._defects_3d[defect_3d.defect_id] = defect_3d
            self._layer_defects[detection.layer_number or self._current_layer].append(defect_3d.defect_id)
            self._stats["defects_mapped"] += 1
            self._heatmap_dirty = True

        return defect_3d

    def _backproject_with_z(
        self,
        camera: CameraCalibration,
        detection: Defect2D,
        z: float
    ) -> Optional[Vector3D]:
        """Backproject 2D detection to 3D plane at given Z."""
        # Get center of detection in pixel coordinates
        cx = (detection.bbox_x + detection.bbox_width/2) * camera.image_width
        cy = (detection.bbox_y + detection.bbox_height/2) * camera.image_height

        K_inv = np.linalg.inv(camera.get_intrinsic_matrix())

        # Ray direction in camera frame
        ray_cam = K_inv @ np.array([cx, cy, 1])
        ray_cam = ray_cam / np.linalg.norm(ray_cam)

        # Transform to world frame
        R_inv = camera.rotation_matrix.T
        ray_world = R_inv @ ray_cam

        # Camera position in world frame
        cam_pos = camera.position.to_array()

        # Intersect with Z plane
        if abs(ray_world[2]) < 1e-6:
            return None

        t = (z - cam_pos[2]) / ray_world[2]
        if t < 0:
            return None

        point = cam_pos + t * ray_world

        if not self._is_in_build_volume(point):
            return None

        return Vector3D.from_array(point)

    def _find_matching_detections(
        self,
        detection: Defect2D,
        time_window_ms: float = 1000.0
    ) -> List[Defect2D]:
        """Find matching detections from other cameras for triangulation."""
        matches = []

        for camera_id, detections in self._detections_2d.items():
            if camera_id == detection.camera_id:
                continue

            for d in detections:
                # Check temporal proximity
                time_diff = abs((d.timestamp - detection.timestamp).total_seconds() * 1000)
                if time_diff > time_window_ms:
                    continue

                # Check layer match
                if d.layer_number != detection.layer_number:
                    continue

                # Check defect type match
                if d.defect_type == detection.defect_type:
                    matches.append(d)

        return matches

    def _generate_defect_point_cloud(
        self,
        camera: CameraCalibration,
        detection: Defect2D,
        center: Vector3D,
        num_points: int = 50
    ) -> np.ndarray:
        """Generate a point cloud representing the defect region."""
        # Generate points based on 2D bbox
        width = detection.bbox_width * self.build_volume[0]
        height = detection.bbox_height * self.build_volume[1]

        # Random points in elliptical region
        angles = np.random.uniform(0, 2 * np.pi, num_points)
        radii = np.sqrt(np.random.uniform(0, 1, num_points))

        x = center.x + (width / 2) * radii * np.cos(angles)
        y = center.y + (height / 2) * radii * np.sin(angles)
        z = np.full(num_points, center.z) + np.random.uniform(
            -self.layer_height, self.layer_height, num_points
        )

        return np.column_stack([x, y, z])

    def _estimate_severity(self, defect_type: DefectType, volume: float) -> DefectSeverity:
        """Estimate defect severity based on type and size."""
        # Critical defect types
        if defect_type in [DefectType.DELAMINATION, DefectType.LAYER_SHIFT]:
            return DefectSeverity.CRITICAL

        # Size-based severity
        if volume > 1000:  # > 1 cm³
            return DefectSeverity.MAJOR
        elif volume > 100:  # > 0.1 cm³
            return DefectSeverity.MODERATE
        elif volume > 10:  # > 10 mm³
            return DefectSeverity.MINOR
        else:
            return DefectSeverity.COSMETIC

    def _estimate_surface_area(self, bbox: BoundingBox3D) -> float:
        """Estimate surface area of defect (simplified as bbox surface)."""
        d = bbox.dimensions
        return 2 * (d.x * d.y + d.y * d.z + d.z * d.x)

    # =========================================================================
    # Defect Clustering
    # =========================================================================

    def cluster_defects(
        self,
        distance_threshold: float = 10.0,
        min_cluster_size: int = 2
    ) -> List[DefectCluster]:
        """
        Cluster nearby defects for root cause analysis.

        Args:
            distance_threshold: Maximum distance between defects in a cluster (mm)
            min_cluster_size: Minimum defects to form a cluster

        Returns:
            List of defect clusters
        """
        with self._lock:
            defects = list(self._defects_3d.values())

            if len(defects) < min_cluster_size:
                return []

            # Simple agglomerative clustering
            clusters = []
            assigned = set()

            for i, defect in enumerate(defects):
                if defect.defect_id in assigned:
                    continue

                cluster_defects = [defect]
                assigned.add(defect.defect_id)

                # Find nearby defects
                for j, other in enumerate(defects):
                    if i == j or other.defect_id in assigned:
                        continue

                    if defect.position.distance_to(other.position) <= distance_threshold:
                        cluster_defects.append(other)
                        assigned.add(other.defect_id)

                if len(cluster_defects) >= min_cluster_size:
                    cluster = self._create_cluster(cluster_defects)
                    clusters.append(cluster)
                    self._clusters[cluster.cluster_id] = cluster

            self._stats["clusters_formed"] = len(clusters)
            return clusters

    def _create_cluster(self, defects: List[Defect3D]) -> DefectCluster:
        """Create a cluster from a list of defects."""
        # Calculate center
        positions = np.array([d.position.to_array() for d in defects])
        center = Vector3D.from_array(positions.mean(axis=0))

        # Calculate bounding box
        min_pt = Vector3D.from_array(positions.min(axis=0))
        max_pt = Vector3D.from_array(positions.max(axis=0))
        bbox = BoundingBox3D(min_pt, max_pt)

        # Find dominant defect type
        type_counts: Dict[DefectType, int] = defaultdict(int)
        for d in defects:
            type_counts[d.defect_type] += 1
        dominant_type = max(type_counts.items(), key=lambda x: x[1])[0]

        # Calculate total volume
        total_volume = sum(d.volume_mm3 for d in defects)

        # Collect affected layers
        affected_layers: Set[int] = set()
        for d in defects:
            for layer in range(d.layer_range[0], d.layer_range[1] + 1):
                affected_layers.add(layer)

        # Generate root cause hypothesis
        hypothesis = self._generate_root_cause_hypothesis(dominant_type, len(affected_layers))

        return DefectCluster(
            cluster_id=str(uuid.uuid4()),
            defects=defects,
            center=center,
            bounding_box=bbox,
            dominant_type=dominant_type,
            total_volume_mm3=total_volume,
            affected_layers=affected_layers,
            root_cause_hypothesis=hypothesis,
        )

    def _generate_root_cause_hypothesis(
        self,
        defect_type: DefectType,
        layer_span: int
    ) -> str:
        """Generate a hypothesis for the root cause of a defect cluster."""
        hypotheses = {
            DefectType.STRINGING: "Retraction settings may need adjustment",
            DefectType.LAYER_SHIFT: "Mechanical issue: belt tension or stepper motor",
            DefectType.WARPING: "Thermal management: bed temperature or enclosure",
            DefectType.UNDER_EXTRUSION: "Extrusion issue: clog, temperature, or filament",
            DefectType.OVER_EXTRUSION: "Flow rate calibration needed",
            DefectType.DELAMINATION: "Layer adhesion issue: temperature or speed",
            DefectType.VOID: "Moisture in filament or extrusion inconsistency",
            DefectType.BLOB: "Oozing during travel moves",
        }

        base = hypotheses.get(defect_type, "Further investigation required")

        if layer_span > 10:
            base += " (persistent across multiple layers)"

        return base

    # =========================================================================
    # Quality Heatmap
    # =========================================================================

    def generate_quality_heatmap(
        self,
        resolution: Tuple[int, int, int] = (20, 20, 20)
    ) -> QualityHeatmap:
        """
        Generate 3D quality heatmap from defect data.

        Args:
            resolution: Grid resolution (x, y, z cells)

        Returns:
            Quality heatmap
        """
        with self._lock:
            if not self._heatmap_dirty and self._heatmap_cache:
                return self._heatmap_cache

            # Calculate cell size
            cell_size = max(
                self.build_volume[0] / resolution[0],
                self.build_volume[1] / resolution[1],
                self.build_volume[2] / resolution[2],
            )

            origin = Vector3D(0, 0, 0)
            values = np.zeros(resolution)
            counts = np.zeros(resolution, dtype=int)

            # Accumulate defects into grid
            for defect in self._defects_3d.values():
                pos = defect.position.to_array()
                indices = (pos / cell_size).astype(int)
                indices = np.clip(indices, 0, np.array(resolution) - 1)

                # Weight by severity
                weight = defect.severity.value / 5.0
                values[indices[0], indices[1], indices[2]] += weight * defect.confidence
                counts[indices[0], indices[1], indices[2]] += 1

            # Normalize
            with np.errstate(divide='ignore', invalid='ignore'):
                values = np.where(counts > 0, values / counts, 0)

            heatmap = QualityHeatmap(
                heatmap_id=str(uuid.uuid4()),
                grid_resolution=resolution,
                cell_size_mm=cell_size,
                origin=origin,
                values=values,
                defect_count_by_cell=counts,
            )

            self._heatmap_cache = heatmap
            self._heatmap_dirty = False

            return heatmap

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_defects_in_region(
        self,
        min_point: Vector3D,
        max_point: Vector3D
    ) -> List[Defect3D]:
        """Get all defects within a 3D region."""
        results = []

        for defect in self._defects_3d.values():
            pos = defect.position
            if (min_point.x <= pos.x <= max_point.x and
                min_point.y <= pos.y <= max_point.y and
                min_point.z <= pos.z <= max_point.z):
                results.append(defect)

        return results

    def get_defects_by_layer(self, layer: int) -> List[Defect3D]:
        """Get all defects at a specific layer."""
        defect_ids = self._layer_defects.get(layer, [])
        return [self._defects_3d[d_id] for d_id in defect_ids if d_id in self._defects_3d]

    def get_defects_by_type(self, defect_type: DefectType) -> List[Defect3D]:
        """Get all defects of a specific type."""
        return [d for d in self._defects_3d.values() if d.defect_type == defect_type]

    def get_defects_by_severity(
        self,
        min_severity: DefectSeverity = DefectSeverity.MINOR
    ) -> List[Defect3D]:
        """Get defects at or above a severity level."""
        return [d for d in self._defects_3d.values() if d.severity.value >= min_severity.value]

    def get_all_defects(self) -> List[Defect3D]:
        """Get all mapped 3D defects."""
        return list(self._defects_3d.values())

    def get_defect_summary(self) -> Dict[str, Any]:
        """Get summary of all defects."""
        defects = list(self._defects_3d.values())

        if not defects:
            return {
                "total_defects": 0,
                "by_type": {},
                "by_severity": {},
                "total_volume_mm3": 0,
                "affected_layers": 0,
            }

        by_type = defaultdict(int)
        by_severity = defaultdict(int)
        total_volume = 0
        all_layers: Set[int] = set()

        for d in defects:
            by_type[d.defect_type.name] += 1
            by_severity[d.severity.name] += 1
            total_volume += d.volume_mm3
            for layer in range(d.layer_range[0], d.layer_range[1] + 1):
                all_layers.add(layer)

        return {
            "total_defects": len(defects),
            "by_type": dict(by_type),
            "by_severity": dict(by_severity),
            "total_volume_mm3": total_volume,
            "affected_layers": len(all_layers),
            "clusters": len(self._clusters),
        }

    # =========================================================================
    # Layer Management
    # =========================================================================

    def set_current_layer(self, layer: int) -> None:
        """Set the current layer number."""
        self._current_layer = layer

    def get_current_layer(self) -> int:
        """Get the current layer number."""
        return self._current_layer

    # =========================================================================
    # Export for Unity
    # =========================================================================

    def export_for_unity(self) -> Dict[str, Any]:
        """
        Export defect data in Unity-compatible format.

        Returns:
            Dictionary with defects, clusters, and heatmap for Unity visualization
        """
        heatmap = self.generate_quality_heatmap()

        return {
            "defects": [d.to_dict() for d in self._defects_3d.values()],
            "clusters": [c.to_dict() for c in self._clusters.values()],
            "heatmap": heatmap.to_dict(),
            "summary": self.get_defect_summary(),
            "build_volume": {
                "x": self.build_volume[0],
                "y": self.build_volume[1],
                "z": self.build_volume[2],
            },
            "current_layer": self._current_layer,
            "layer_height": self.layer_height,
        }

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            **self._stats,
            "cameras_registered": len(self._cameras),
            "defects_3d_count": len(self._defects_3d),
            "clusters_count": len(self._clusters),
            "current_layer": self._current_layer,
        }

    def clear(self) -> None:
        """Clear all defect data."""
        with self._lock:
            self._detections_2d.clear()
            self._defects_3d.clear()
            self._clusters.clear()
            self._layer_defects.clear()
            self._heatmap_cache = None
            self._heatmap_dirty = True
            self._current_layer = 0


# =============================================================================
# Singleton Instance
# =============================================================================

_defect_mapping_service: Optional[DefectMapping3DService] = None


def get_defect_mapping_service() -> DefectMapping3DService:
    """Get or create the defect mapping service instance."""
    global _defect_mapping_service
    if _defect_mapping_service is None:
        _defect_mapping_service = DefectMapping3DService()
        _defect_mapping_service.setup_default_cameras()
    return _defect_mapping_service


# =============================================================================
# Export Public API
# =============================================================================

__all__ = [
    # Service
    "DefectMapping3DService",
    "get_defect_mapping_service",
    # Data types
    "Defect2D",
    "Defect3D",
    "DefectCluster",
    "QualityHeatmap",
    "Vector3D",
    "BoundingBox3D",
    "CameraCalibration",
    # Enums
    "DefectType",
    "DefectSeverity",
    "CameraModel",
]
