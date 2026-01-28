"""
Quality Heatmap Generator
=========================

Generates spatial quality heatmaps for manufacturing visualization.

Features:
- Defect density mapping across build volume
- Temporal trend overlays
- Root cause correlation analysis
- Export to Unity-compatible formats

ISO 23247 Compliance:
- Quality data visualization for digital twin
- Spatial analysis for process optimization

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading
import logging
import json
import math
import uuid

logger = logging.getLogger(__name__)


class HeatmapType(Enum):
    """Types of quality heatmaps."""
    DEFECT_DENSITY = "defect_density"
    SURFACE_ROUGHNESS = "surface_roughness"
    DIMENSIONAL_ACCURACY = "dimensional_accuracy"
    LAYER_ADHESION = "layer_adhesion"
    TEMPERATURE_DISTRIBUTION = "temperature_distribution"
    STRESS_CONCENTRATION = "stress_concentration"
    POROSITY = "porosity"
    COLOR_CONSISTENCY = "color_consistency"


class InterpolationMethod(Enum):
    """Interpolation methods for heatmap generation."""
    NEAREST = "nearest"
    LINEAR = "linear"
    BILINEAR = "bilinear"
    BICUBIC = "bicubic"
    IDW = "idw"  # Inverse Distance Weighting
    KRIGING = "kriging"


class ColorScale(Enum):
    """Color scales for heatmap visualization."""
    THERMAL = "thermal"       # Blue (good) -> Red (bad)
    VIRIDIS = "viridis"       # Purple -> Yellow
    PLASMA = "plasma"         # Purple -> Orange
    INFERNO = "inferno"       # Black -> Yellow
    GRAYSCALE = "grayscale"   # Black -> White
    DIVERGING = "diverging"   # Blue -> White -> Red
    QUALITY = "quality"       # Green (good) -> Red (bad)


@dataclass
class Vector3:
    """3D vector for spatial coordinates."""
    x: float
    y: float
    z: float

    def to_dict(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y, 'z': self.z}

    def distance_to(self, other: 'Vector3') -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )


@dataclass
class BoundingBox:
    """3D bounding box for build volume."""
    min_point: Vector3
    max_point: Vector3

    @property
    def size(self) -> Vector3:
        return Vector3(
            self.max_point.x - self.min_point.x,
            self.max_point.y - self.min_point.y,
            self.max_point.z - self.min_point.z
        )

    @property
    def center(self) -> Vector3:
        return Vector3(
            (self.min_point.x + self.max_point.x) / 2,
            (self.min_point.y + self.max_point.y) / 2,
            (self.min_point.z + self.max_point.z) / 2
        )

    def contains(self, point: Vector3) -> bool:
        return (
            self.min_point.x <= point.x <= self.max_point.x and
            self.min_point.y <= point.y <= self.max_point.y and
            self.min_point.z <= point.z <= self.max_point.z
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'min': self.min_point.to_dict(),
            'max': self.max_point.to_dict(),
            'size': self.size.to_dict(),
            'center': self.center.to_dict()
        }


@dataclass
class QualityDataPoint:
    """Single quality measurement point."""
    id: str
    position: Vector3
    value: float
    timestamp: datetime
    measurement_type: HeatmapType
    confidence: float = 1.0
    source: str = "sensor"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'position': self.position.to_dict(),
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'measurement_type': self.measurement_type.value,
            'confidence': self.confidence,
            'source': self.source,
            'metadata': self.metadata
        }


@dataclass
class HeatmapCell:
    """Single cell in the heatmap grid."""
    grid_x: int
    grid_y: int
    grid_z: int
    center: Vector3
    value: float
    sample_count: int
    confidence: float
    min_value: float
    max_value: float
    std_dev: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'grid': {'x': self.grid_x, 'y': self.grid_y, 'z': self.grid_z},
            'center': self.center.to_dict(),
            'value': self.value,
            'sample_count': self.sample_count,
            'confidence': self.confidence,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'std_dev': self.std_dev
        }


@dataclass
class HeatmapConfig:
    """Configuration for heatmap generation."""
    resolution: Tuple[int, int, int] = (50, 50, 50)  # Grid cells per axis
    interpolation: InterpolationMethod = InterpolationMethod.IDW
    color_scale: ColorScale = ColorScale.QUALITY
    min_samples_per_cell: int = 1
    idw_power: float = 2.0  # Power for IDW interpolation
    search_radius: float = 10.0  # mm
    normalize: bool = True
    clip_outliers: bool = True
    outlier_threshold: float = 3.0  # Standard deviations


@dataclass
class Heatmap:
    """Generated quality heatmap."""
    id: str
    heatmap_type: HeatmapType
    bounds: BoundingBox
    resolution: Tuple[int, int, int]
    cells: List[HeatmapCell]
    created_at: datetime
    config: HeatmapConfig
    statistics: Dict[str, float]
    color_scale: ColorScale
    value_range: Tuple[float, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'heatmap_type': self.heatmap_type.value,
            'bounds': self.bounds.to_dict(),
            'resolution': self.resolution,
            'cell_count': len(self.cells),
            'created_at': self.created_at.isoformat(),
            'statistics': self.statistics,
            'color_scale': self.color_scale.value,
            'value_range': self.value_range
        }

    def to_unity_format(self) -> Dict[str, Any]:
        """Export in Unity-compatible format."""
        # Flatten cells to 3D texture data
        nx, ny, nz = self.resolution
        data = [[[0.0 for _ in range(nz)] for _ in range(ny)] for _ in range(nx)]

        for cell in self.cells:
            if 0 <= cell.grid_x < nx and 0 <= cell.grid_y < ny and 0 <= cell.grid_z < nz:
                data[cell.grid_x][cell.grid_y][cell.grid_z] = cell.value

        return {
            'type': 'volume_texture',
            'heatmap_id': self.id,
            'heatmap_type': self.heatmap_type.value,
            'dimensions': {'x': nx, 'y': ny, 'z': nz},
            'bounds': self.bounds.to_dict(),
            'color_scale': self.color_scale.value,
            'value_range': {'min': self.value_range[0], 'max': self.value_range[1]},
            'data': data,
            'created_at': self.created_at.isoformat()
        }

    def to_slice(self, axis: str, position: float) -> Dict[str, Any]:
        """Get 2D slice at specified position along axis."""
        nx, ny, nz = self.resolution
        size = self.bounds.size

        slice_cells = []

        if axis == 'z':
            # Z-slice (XY plane)
            grid_z = int((position - self.bounds.min_point.z) / size.z * nz)
            grid_z = max(0, min(nz - 1, grid_z))

            for cell in self.cells:
                if cell.grid_z == grid_z:
                    slice_cells.append({
                        'x': cell.grid_x,
                        'y': cell.grid_y,
                        'value': cell.value,
                        'confidence': cell.confidence
                    })

        elif axis == 'y':
            # Y-slice (XZ plane)
            grid_y = int((position - self.bounds.min_point.y) / size.y * ny)
            grid_y = max(0, min(ny - 1, grid_y))

            for cell in self.cells:
                if cell.grid_y == grid_y:
                    slice_cells.append({
                        'x': cell.grid_x,
                        'z': cell.grid_z,
                        'value': cell.value,
                        'confidence': cell.confidence
                    })

        elif axis == 'x':
            # X-slice (YZ plane)
            grid_x = int((position - self.bounds.min_point.x) / size.x * nx)
            grid_x = max(0, min(nx - 1, grid_x))

            for cell in self.cells:
                if cell.grid_x == grid_x:
                    slice_cells.append({
                        'y': cell.grid_y,
                        'z': cell.grid_z,
                        'value': cell.value,
                        'confidence': cell.confidence
                    })

        return {
            'axis': axis,
            'position': position,
            'cells': slice_cells,
            'value_range': self.value_range
        }


class TemporalTrendAnalyzer:
    """Analyzes temporal trends in quality data."""

    def __init__(self):
        self._historical_data: Dict[str, List[QualityDataPoint]] = {}
        self._lock = threading.Lock()

    def add_data_point(self, point: QualityDataPoint):
        """Add data point for trend analysis."""
        key = f"{point.measurement_type.value}"
        with self._lock:
            if key not in self._historical_data:
                self._historical_data[key] = []
            self._historical_data[key].append(point)

            # Keep limited history (last 10000 points)
            if len(self._historical_data[key]) > 10000:
                self._historical_data[key].pop(0)

    def get_trend(
        self,
        measurement_type: HeatmapType,
        time_window: timedelta = timedelta(hours=24)
    ) -> Dict[str, Any]:
        """Calculate trend for measurement type."""
        key = measurement_type.value
        cutoff = datetime.utcnow() - time_window

        with self._lock:
            points = [
                p for p in self._historical_data.get(key, [])
                if p.timestamp > cutoff
            ]

        if len(points) < 2:
            return {'trend': 'insufficient_data', 'sample_count': len(points)}

        # Calculate trend using linear regression
        times = [(p.timestamp - cutoff).total_seconds() for p in points]
        values = [p.value for p in points]

        n = len(times)
        sum_t = sum(times)
        sum_v = sum(values)
        sum_tv = sum(t * v for t, v in zip(times, values))
        sum_t2 = sum(t * t for t in times)

        denom = n * sum_t2 - sum_t * sum_t
        if abs(denom) < 1e-10:
            slope = 0
        else:
            slope = (n * sum_tv - sum_t * sum_v) / denom

        mean_value = sum_v / n
        std_dev = math.sqrt(sum((v - mean_value) ** 2 for v in values) / n) if n > 0 else 0

        # Determine trend direction
        if abs(slope) < std_dev * 0.01:
            trend_direction = "stable"
        elif slope > 0:
            trend_direction = "increasing"
        else:
            trend_direction = "decreasing"

        return {
            'trend': trend_direction,
            'slope': slope,
            'slope_per_hour': slope * 3600,
            'mean_value': mean_value,
            'std_dev': std_dev,
            'min_value': min(values),
            'max_value': max(values),
            'sample_count': n,
            'time_window_hours': time_window.total_seconds() / 3600
        }

    def get_anomaly_correlation(
        self,
        measurement_type: HeatmapType,
        anomaly_positions: List[Vector3],
        radius: float = 20.0
    ) -> Dict[str, Any]:
        """Correlate quality data with anomaly positions."""
        key = measurement_type.value

        with self._lock:
            points = self._historical_data.get(key, [])

        correlations = []
        for anomaly_pos in anomaly_positions:
            nearby_points = [
                p for p in points
                if p.position.distance_to(anomaly_pos) <= radius
            ]

            if nearby_points:
                values = [p.value for p in nearby_points]
                correlations.append({
                    'position': anomaly_pos.to_dict(),
                    'nearby_count': len(nearby_points),
                    'avg_value': sum(values) / len(values),
                    'max_value': max(values),
                    'min_value': min(values)
                })

        return {
            'measurement_type': measurement_type.value,
            'anomaly_count': len(anomaly_positions),
            'correlations': correlations
        }


class RootCauseAnalyzer:
    """Analyzes root causes of quality issues."""

    def __init__(self):
        self._cause_patterns: Dict[str, Dict[str, Any]] = {}
        self._load_default_patterns()

    def _load_default_patterns(self):
        """Load default cause-effect patterns."""
        self._cause_patterns = {
            'high_defect_density_corner': {
                'pattern': 'high_values_at_corners',
                'likely_causes': [
                    'Poor bed adhesion',
                    'Uneven heating',
                    'Draft/cooling issues'
                ],
                'recommended_actions': [
                    'Check bed leveling',
                    'Increase bed temperature',
                    'Add enclosure or draft shield'
                ]
            },
            'high_defect_density_center': {
                'pattern': 'high_values_at_center',
                'likely_causes': [
                    'Overheating',
                    'Poor cooling',
                    'Too fast printing'
                ],
                'recommended_actions': [
                    'Improve cooling',
                    'Reduce print speed',
                    'Lower hotend temperature'
                ]
            },
            'layer_lines': {
                'pattern': 'horizontal_banding',
                'likely_causes': [
                    'Z-axis mechanical issues',
                    'Inconsistent extrusion',
                    'Temperature fluctuation'
                ],
                'recommended_actions': [
                    'Check Z-axis lead screw',
                    'Calibrate extruder',
                    'Stabilize temperature'
                ]
            },
            'surface_roughness_gradient': {
                'pattern': 'gradient_along_axis',
                'likely_causes': [
                    'Uneven cooling',
                    'Draft exposure',
                    'Temperature drop over time'
                ],
                'recommended_actions': [
                    'Add uniform cooling',
                    'Use enclosure',
                    'Check heater stability'
                ]
            }
        }

    def analyze(self, heatmap: Heatmap) -> Dict[str, Any]:
        """Analyze heatmap for root cause patterns."""
        patterns_found = []

        # Analyze spatial distribution
        corner_analysis = self._analyze_corners(heatmap)
        center_analysis = self._analyze_center(heatmap)
        gradient_analysis = self._analyze_gradients(heatmap)

        # Match patterns
        if corner_analysis['corner_avg'] > center_analysis['center_avg'] * 1.5:
            patterns_found.append({
                **self._cause_patterns['high_defect_density_corner'],
                'confidence': min(
                    corner_analysis['corner_avg'] / center_analysis['center_avg'] - 1,
                    1.0
                )
            })

        if center_analysis['center_avg'] > corner_analysis['corner_avg'] * 1.5:
            patterns_found.append({
                **self._cause_patterns['high_defect_density_center'],
                'confidence': min(
                    center_analysis['center_avg'] / corner_analysis['corner_avg'] - 1,
                    1.0
                )
            })

        if gradient_analysis['has_gradient']:
            patterns_found.append({
                **self._cause_patterns['surface_roughness_gradient'],
                'confidence': gradient_analysis['gradient_strength'],
                'gradient_axis': gradient_analysis['primary_axis']
            })

        return {
            'heatmap_id': heatmap.id,
            'heatmap_type': heatmap.heatmap_type.value,
            'patterns_found': patterns_found,
            'corner_analysis': corner_analysis,
            'center_analysis': center_analysis,
            'gradient_analysis': gradient_analysis,
            'overall_quality_score': self._calculate_quality_score(heatmap)
        }

    def _analyze_corners(self, heatmap: Heatmap) -> Dict[str, Any]:
        """Analyze corner regions of heatmap."""
        nx, ny, nz = heatmap.resolution
        corner_threshold = 0.2  # 20% of each dimension

        corner_cells = []
        for cell in heatmap.cells:
            is_corner_x = (
                cell.grid_x < nx * corner_threshold or
                cell.grid_x > nx * (1 - corner_threshold)
            )
            is_corner_y = (
                cell.grid_y < ny * corner_threshold or
                cell.grid_y > ny * (1 - corner_threshold)
            )
            if is_corner_x and is_corner_y:
                corner_cells.append(cell)

        if not corner_cells:
            return {'corner_avg': 0, 'corner_count': 0}

        values = [c.value for c in corner_cells]
        return {
            'corner_avg': sum(values) / len(values),
            'corner_max': max(values),
            'corner_min': min(values),
            'corner_count': len(corner_cells)
        }

    def _analyze_center(self, heatmap: Heatmap) -> Dict[str, Any]:
        """Analyze center region of heatmap."""
        nx, ny, nz = heatmap.resolution
        center_threshold = 0.3  # 30% from center

        center_cells = []
        cx, cy = nx / 2, ny / 2

        for cell in heatmap.cells:
            dist_x = abs(cell.grid_x - cx) / nx
            dist_y = abs(cell.grid_y - cy) / ny
            if dist_x < center_threshold and dist_y < center_threshold:
                center_cells.append(cell)

        if not center_cells:
            return {'center_avg': 0, 'center_count': 0}

        values = [c.value for c in center_cells]
        return {
            'center_avg': sum(values) / len(values),
            'center_max': max(values),
            'center_min': min(values),
            'center_count': len(center_cells)
        }

    def _analyze_gradients(self, heatmap: Heatmap) -> Dict[str, Any]:
        """Analyze spatial gradients in heatmap."""
        if not heatmap.cells:
            return {'has_gradient': False}

        # Calculate average values along each axis
        nx, ny, nz = heatmap.resolution

        x_values = [[] for _ in range(nx)]
        y_values = [[] for _ in range(ny)]
        z_values = [[] for _ in range(nz)]

        for cell in heatmap.cells:
            if 0 <= cell.grid_x < nx:
                x_values[cell.grid_x].append(cell.value)
            if 0 <= cell.grid_y < ny:
                y_values[cell.grid_y].append(cell.value)
            if 0 <= cell.grid_z < nz:
                z_values[cell.grid_z].append(cell.value)

        x_avgs = [sum(v) / len(v) if v else 0 for v in x_values]
        y_avgs = [sum(v) / len(v) if v else 0 for v in y_values]
        z_avgs = [sum(v) / len(v) if v else 0 for v in z_values]

        # Calculate gradient strength for each axis
        def gradient_strength(avgs):
            if len(avgs) < 2:
                return 0
            diffs = [avgs[i + 1] - avgs[i] for i in range(len(avgs) - 1)]
            if not diffs:
                return 0
            return abs(sum(diffs) / len(diffs))

        x_grad = gradient_strength(x_avgs)
        y_grad = gradient_strength(y_avgs)
        z_grad = gradient_strength(z_avgs)

        max_grad = max(x_grad, y_grad, z_grad)
        threshold = 0.1 * (heatmap.value_range[1] - heatmap.value_range[0])

        primary_axis = 'x' if x_grad == max_grad else ('y' if y_grad == max_grad else 'z')

        return {
            'has_gradient': max_grad > threshold,
            'gradient_strength': min(max_grad / threshold if threshold > 0 else 0, 1.0),
            'primary_axis': primary_axis,
            'x_gradient': x_grad,
            'y_gradient': y_grad,
            'z_gradient': z_grad
        }

    def _calculate_quality_score(self, heatmap: Heatmap) -> float:
        """Calculate overall quality score (0-100)."""
        if not heatmap.cells:
            return 0

        values = [c.value for c in heatmap.cells]
        avg_value = sum(values) / len(values)

        # Normalize to 0-100 (inverse for defect-based metrics)
        min_val, max_val = heatmap.value_range
        if max_val - min_val > 0:
            normalized = 1 - (avg_value - min_val) / (max_val - min_val)
        else:
            normalized = 1

        return max(0, min(100, normalized * 100))


class QualityHeatmapGenerator:
    """
    Main service for generating quality heatmaps.

    Provides:
    - 3D heatmap generation from quality data points
    - Multiple interpolation methods
    - Unity-compatible export
    - Temporal trend analysis
    - Root cause correlation
    """

    def __init__(self, config: HeatmapConfig = None):
        self.config = config or HeatmapConfig()
        self._data_points: Dict[str, List[QualityDataPoint]] = {}
        self._heatmaps: Dict[str, Heatmap] = {}
        self._trend_analyzer = TemporalTrendAnalyzer()
        self._root_cause_analyzer = RootCauseAnalyzer()
        self._lock = threading.RLock()

        logger.info("QualityHeatmapGenerator initialized")

    def add_data_point(self, point: QualityDataPoint):
        """Add a quality data point."""
        key = point.measurement_type.value
        with self._lock:
            if key not in self._data_points:
                self._data_points[key] = []
            self._data_points[key].append(point)

            # Also add to trend analyzer
            self._trend_analyzer.add_data_point(point)

    def add_data_points(self, points: List[QualityDataPoint]):
        """Add multiple quality data points."""
        for point in points:
            self.add_data_point(point)

    def generate_heatmap(
        self,
        heatmap_type: HeatmapType,
        bounds: BoundingBox,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        config: Optional[HeatmapConfig] = None
    ) -> Heatmap:
        """Generate a quality heatmap."""
        cfg = config or self.config
        key = heatmap_type.value

        with self._lock:
            # Get data points
            points = self._data_points.get(key, [])

            # Filter by time range if specified
            if time_range:
                start_time, end_time = time_range
                points = [
                    p for p in points
                    if start_time <= p.timestamp <= end_time
                ]

            # Filter by bounds
            points = [p for p in points if bounds.contains(p.position)]

        if not points:
            logger.warning(f"No data points for heatmap type: {heatmap_type.value}")

        # Generate grid
        nx, ny, nz = cfg.resolution
        cells = []

        cell_size = Vector3(
            bounds.size.x / nx,
            bounds.size.y / ny,
            bounds.size.z / nz
        )

        for gx in range(nx):
            for gy in range(ny):
                for gz in range(nz):
                    center = Vector3(
                        bounds.min_point.x + (gx + 0.5) * cell_size.x,
                        bounds.min_point.y + (gy + 0.5) * cell_size.y,
                        bounds.min_point.z + (gz + 0.5) * cell_size.z
                    )

                    # Interpolate value at this cell
                    cell_data = self._interpolate_cell(
                        center, points, cfg
                    )

                    if cell_data['sample_count'] >= cfg.min_samples_per_cell:
                        cells.append(HeatmapCell(
                            grid_x=gx,
                            grid_y=gy,
                            grid_z=gz,
                            center=center,
                            **cell_data
                        ))

        # Calculate statistics
        if cells:
            values = [c.value for c in cells]
            statistics = {
                'mean': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'std_dev': math.sqrt(sum((v - sum(values) / len(values)) ** 2 for v in values) / len(values)),
                'cell_count': len(cells),
                'coverage': len(cells) / (nx * ny * nz)
            }
            value_range = (min(values), max(values))
        else:
            statistics = {
                'mean': 0, 'min': 0, 'max': 0, 'std_dev': 0,
                'cell_count': 0, 'coverage': 0
            }
            value_range = (0, 1)

        # Normalize values if configured
        if cfg.normalize and cells and value_range[1] > value_range[0]:
            for cell in cells:
                cell.value = (cell.value - value_range[0]) / (value_range[1] - value_range[0])
            value_range = (0, 1)

        heatmap = Heatmap(
            id=str(uuid.uuid4()),
            heatmap_type=heatmap_type,
            bounds=bounds,
            resolution=cfg.resolution,
            cells=cells,
            created_at=datetime.utcnow(),
            config=cfg,
            statistics=statistics,
            color_scale=cfg.color_scale,
            value_range=value_range
        )

        # Store heatmap
        with self._lock:
            self._heatmaps[heatmap.id] = heatmap

        logger.info(
            f"Generated heatmap {heatmap.id}: {heatmap_type.value} "
            f"with {len(cells)} cells"
        )

        return heatmap

    def _interpolate_cell(
        self,
        center: Vector3,
        points: List[QualityDataPoint],
        config: HeatmapConfig
    ) -> Dict[str, Any]:
        """Interpolate value at cell center."""
        # Find nearby points
        nearby = [
            p for p in points
            if center.distance_to(p.position) <= config.search_radius
        ]

        if not nearby:
            return {
                'value': 0,
                'sample_count': 0,
                'confidence': 0,
                'min_value': 0,
                'max_value': 0,
                'std_dev': 0
            }

        values = [p.value for p in nearby]

        if config.interpolation == InterpolationMethod.NEAREST:
            # Use nearest point
            nearest = min(nearby, key=lambda p: center.distance_to(p.position))
            value = nearest.value

        elif config.interpolation == InterpolationMethod.IDW:
            # Inverse Distance Weighting
            weights = []
            for p in nearby:
                dist = center.distance_to(p.position)
                if dist < 0.001:  # Very close point
                    value = p.value
                    break
                weights.append(1.0 / (dist ** config.idw_power))
            else:
                total_weight = sum(weights)
                value = sum(w * p.value for w, p in zip(weights, nearby)) / total_weight

        else:
            # Default to simple average
            value = sum(values) / len(values)

        # Calculate statistics
        mean_val = sum(values) / len(values)
        std_dev = math.sqrt(sum((v - mean_val) ** 2 for v in values) / len(values)) if len(values) > 1 else 0

        # Clip outliers if configured
        if config.clip_outliers and std_dev > 0:
            threshold = config.outlier_threshold * std_dev
            value = max(mean_val - threshold, min(mean_val + threshold, value))

        # Calculate confidence based on sample count and spread
        confidence = min(len(nearby) / 10.0, 1.0) * (1 - min(std_dev / mean_val if mean_val > 0 else 0, 1))

        return {
            'value': value,
            'sample_count': len(nearby),
            'confidence': confidence,
            'min_value': min(values),
            'max_value': max(values),
            'std_dev': std_dev
        }

    def get_heatmap(self, heatmap_id: str) -> Optional[Heatmap]:
        """Get heatmap by ID."""
        with self._lock:
            return self._heatmaps.get(heatmap_id)

    def get_heatmap_slice(
        self,
        heatmap_id: str,
        axis: str,
        position: float
    ) -> Optional[Dict[str, Any]]:
        """Get 2D slice from heatmap."""
        heatmap = self.get_heatmap(heatmap_id)
        if heatmap:
            return heatmap.to_slice(axis, position)
        return None

    def export_for_unity(self, heatmap_id: str) -> Optional[Dict[str, Any]]:
        """Export heatmap in Unity-compatible format."""
        heatmap = self.get_heatmap(heatmap_id)
        if heatmap:
            return heatmap.to_unity_format()
        return None

    def get_trend(
        self,
        measurement_type: HeatmapType,
        time_window: timedelta = timedelta(hours=24)
    ) -> Dict[str, Any]:
        """Get temporal trend for measurement type."""
        return self._trend_analyzer.get_trend(measurement_type, time_window)

    def analyze_root_cause(self, heatmap_id: str) -> Optional[Dict[str, Any]]:
        """Analyze root cause patterns in heatmap."""
        heatmap = self.get_heatmap(heatmap_id)
        if heatmap:
            return self._root_cause_analyzer.analyze(heatmap)
        return None

    def correlate_with_anomalies(
        self,
        measurement_type: HeatmapType,
        anomaly_positions: List[Vector3],
        radius: float = 20.0
    ) -> Dict[str, Any]:
        """Correlate quality data with anomaly positions."""
        return self._trend_analyzer.get_anomaly_correlation(
            measurement_type, anomaly_positions, radius
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            return {
                'data_point_counts': {
                    k: len(v) for k, v in self._data_points.items()
                },
                'heatmap_count': len(self._heatmaps),
                'heatmap_types': list(self._data_points.keys())
            }

    def clear_data(self, measurement_type: Optional[HeatmapType] = None):
        """Clear stored data points."""
        with self._lock:
            if measurement_type:
                key = measurement_type.value
                if key in self._data_points:
                    self._data_points[key] = []
            else:
                self._data_points.clear()


# Singleton instance
_quality_heatmap_generator: Optional[QualityHeatmapGenerator] = None


def get_quality_heatmap_generator() -> QualityHeatmapGenerator:
    """Get or create quality heatmap generator."""
    global _quality_heatmap_generator
    if _quality_heatmap_generator is None:
        _quality_heatmap_generator = QualityHeatmapGenerator()
    return _quality_heatmap_generator
