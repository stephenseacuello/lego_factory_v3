"""
Printability Evaluator - 3D printing feasibility score.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 3: Generative Design System
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class PrintIssue(Enum):
    """Types of printability issues."""
    OVERHANG = "overhang"
    BRIDGING = "bridging"
    THIN_WALL = "thin_wall"
    SMALL_HOLE = "small_hole"
    SUPPORT_REQUIRED = "support_required"
    WARPING_RISK = "warping_risk"
    STRINGING_RISK = "stringing_risk"
    LAYER_ADHESION = "layer_adhesion"


@dataclass
class PrintabilityIssue:
    """Single printability issue."""
    issue_type: PrintIssue
    severity: float  # 0-1
    location: Tuple[int, int, int]
    description: str
    remediation: str


@dataclass
class PrintabilityResult:
    """Printability evaluation result."""
    printability_score: float  # 0-1
    issues: List[PrintabilityIssue]
    support_volume: float  # mm³
    estimated_print_time: float  # minutes
    estimated_material: float  # grams
    recommended_orientation: Tuple[float, float, float]
    slicer_settings: Dict[str, Any]
    fitness_score: float  # 0-1 for optimization
    passed: bool


class PrintabilityEvaluator:
    """
    3D printing feasibility evaluator.

    Features:
    - Overhang detection
    - Support volume estimation
    - Print time estimation
    - Optimal orientation finding
    - FDM-specific analysis
    """

    def __init__(self):
        self._printer_specs: Dict[str, Any] = {}
        self._default_settings: Dict[str, Any] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default printer specs and settings."""
        self._printer_specs = {
            'build_volume': (220, 220, 250),  # mm
            'nozzle_diameter': 0.4,  # mm
            'min_layer_height': 0.1,  # mm
            'max_layer_height': 0.3,  # mm
            'max_print_speed': 150,  # mm/s
            'heated_bed': True,
            'max_overhang_angle': 45,  # degrees
            'max_bridge_length': 10  # mm
        }

        self._default_settings = {
            'layer_height': 0.2,
            'infill_density': 20,
            'print_speed': 60,
            'nozzle_temp': 200,
            'bed_temp': 60,
            'support_enabled': True,
            'support_angle': 45
        }

    def evaluate(self,
                geometry: np.ndarray,
                voxel_size: float = 0.5,
                material: str = 'PLA') -> PrintabilityResult:
        """
        Evaluate printability of design.

        Args:
            geometry: 3D density field (0-1)
            voxel_size: Size of each voxel in mm
            material: Material type

        Returns:
            Printability evaluation result
        """
        issues = []

        # Check overhangs
        overhang_issues = self._check_overhangs(geometry, voxel_size)
        issues.extend(overhang_issues)

        # Check bridging
        bridge_issues = self._check_bridging(geometry, voxel_size)
        issues.extend(bridge_issues)

        # Check thin walls
        thin_wall_issues = self._check_thin_walls(geometry, voxel_size)
        issues.extend(thin_wall_issues)

        # Check small features
        small_feature_issues = self._check_small_features(geometry, voxel_size)
        issues.extend(small_feature_issues)

        # Calculate support volume
        support_volume = self._estimate_support_volume(geometry, voxel_size)

        # Estimate print time
        print_time = self._estimate_print_time(geometry, voxel_size)

        # Estimate material usage
        material_volume = np.sum(geometry) * (voxel_size ** 3)
        material_weight = material_volume * 1.24e-3  # PLA density in g/mm³

        # Find optimal orientation
        best_orientation = self._find_optimal_orientation(geometry)

        # Generate slicer settings
        slicer_settings = self._recommend_settings(geometry, issues, material)

        # Calculate overall score
        printability_score = self._calculate_score(issues, support_volume, geometry)

        # Fitness for optimization (0-1, higher is better)
        fitness_score = printability_score * (1 - min(1, support_volume / 1000))

        passed = printability_score >= 0.6 and len([i for i in issues if i.severity > 0.8]) == 0

        return PrintabilityResult(
            printability_score=printability_score,
            issues=issues,
            support_volume=support_volume,
            estimated_print_time=print_time,
            estimated_material=material_weight,
            recommended_orientation=best_orientation,
            slicer_settings=slicer_settings,
            fitness_score=fitness_score,
            passed=passed
        )

    def _check_overhangs(self,
                        geometry: np.ndarray,
                        voxel_size: float) -> List[PrintabilityIssue]:
        """Check for unsupported overhangs."""
        issues = []
        max_angle = self._printer_specs['max_overhang_angle']

        # Check each layer (assuming Z is up)
        for z in range(1, geometry.shape[2]):
            current_layer = geometry[:, :, z] > 0.5
            prev_layer = geometry[:, :, z-1] > 0.5

            # Find unsupported voxels
            unsupported = current_layer & ~prev_layer

            # Check neighbors in previous layer
            for i in range(geometry.shape[0]):
                for j in range(geometry.shape[1]):
                    if unsupported[i, j]:
                        # Check if supported by diagonal neighbor
                        has_diagonal_support = False
                        for di in [-1, 0, 1]:
                            for dj in [-1, 0, 1]:
                                ni, nj = i + di, j + dj
                                if 0 <= ni < geometry.shape[0] and 0 <= nj < geometry.shape[1]:
                                    if prev_layer[ni, nj]:
                                        has_diagonal_support = True
                                        break
                            if has_diagonal_support:
                                break

                        if not has_diagonal_support:
                            severity = 0.8
                            issues.append(PrintabilityIssue(
                                issue_type=PrintIssue.OVERHANG,
                                severity=severity,
                                location=(i, j, z),
                                description=f"Unsupported overhang at layer {z}",
                                remediation="Add support or redesign angle"
                            ))

        return issues[:20]  # Limit to top issues

    def _check_bridging(self,
                       geometry: np.ndarray,
                       voxel_size: float) -> List[PrintabilityIssue]:
        """Check for bridging issues."""
        issues = []
        max_bridge = self._printer_specs['max_bridge_length']

        for z in range(1, geometry.shape[2]):
            layer = geometry[:, :, z] > 0.5
            prev_layer = geometry[:, :, z-1] > 0.5

            # Find horizontal gaps in previous layer
            for i in range(geometry.shape[0]):
                in_bridge = False
                bridge_start = 0
                for j in range(geometry.shape[1]):
                    if layer[i, j] and not prev_layer[i, j]:
                        if not in_bridge:
                            in_bridge = True
                            bridge_start = j
                    else:
                        if in_bridge:
                            bridge_length = (j - bridge_start) * voxel_size
                            if bridge_length > max_bridge:
                                issues.append(PrintabilityIssue(
                                    issue_type=PrintIssue.BRIDGING,
                                    severity=min(1.0, bridge_length / (max_bridge * 2)),
                                    location=(i, bridge_start, z),
                                    description=f"Bridge of {bridge_length:.1f}mm",
                                    remediation="Reduce bridge length or add support"
                                ))
                            in_bridge = False

        return issues[:10]

    def _check_thin_walls(self,
                         geometry: np.ndarray,
                         voxel_size: float) -> List[PrintabilityIssue]:
        """Check for thin wall issues."""
        issues = []
        min_wall = self._printer_specs['nozzle_diameter'] * 2

        # Check wall thickness in each direction
        for z in range(geometry.shape[2]):
            layer = geometry[:, :, z] > 0.5

            # Check X direction walls
            for i in range(geometry.shape[0]):
                wall_start = None
                for j in range(geometry.shape[1]):
                    if layer[i, j]:
                        if wall_start is None:
                            wall_start = j
                    else:
                        if wall_start is not None:
                            wall_thickness = (j - wall_start) * voxel_size
                            if 0 < wall_thickness < min_wall:
                                issues.append(PrintabilityIssue(
                                    issue_type=PrintIssue.THIN_WALL,
                                    severity=1 - (wall_thickness / min_wall),
                                    location=(i, wall_start, z),
                                    description=f"Thin wall: {wall_thickness:.2f}mm",
                                    remediation=f"Increase to at least {min_wall:.1f}mm"
                                ))
                            wall_start = None

        return issues[:10]

    def _check_small_features(self,
                              geometry: np.ndarray,
                              voxel_size: float) -> List[PrintabilityIssue]:
        """Check for small holes and features."""
        issues = []
        min_hole = self._printer_specs['nozzle_diameter'] * 2

        # Check for small internal voids
        solid = geometry > 0.5

        for z in range(1, geometry.shape[2]-1):
            for i in range(1, geometry.shape[0]-1):
                for j in range(1, geometry.shape[1]-1):
                    if not solid[i, j, z]:
                        # Check if it's a small hole
                        neighbors_solid = (
                            solid[i-1, j, z] + solid[i+1, j, z] +
                            solid[i, j-1, z] + solid[i, j+1, z]
                        )
                        if neighbors_solid >= 3:  # Mostly surrounded
                            hole_size = voxel_size  # Minimum 1 voxel
                            if hole_size < min_hole:
                                issues.append(PrintabilityIssue(
                                    issue_type=PrintIssue.SMALL_HOLE,
                                    severity=0.5,
                                    location=(i, j, z),
                                    description=f"Small hole: {hole_size:.2f}mm",
                                    remediation="Enlarge or remove small features"
                                ))

        return issues[:10]

    def _estimate_support_volume(self,
                                geometry: np.ndarray,
                                voxel_size: float) -> float:
        """Estimate support material volume."""
        support_voxels = 0

        for z in range(1, geometry.shape[2]):
            current = geometry[:, :, z] > 0.5
            prev = geometry[:, :, z-1] > 0.5

            # Count unsupported voxels
            unsupported = current & ~prev
            support_voxels += np.sum(unsupported)

        return support_voxels * (voxel_size ** 3)

    def _estimate_print_time(self,
                            geometry: np.ndarray,
                            voxel_size: float) -> float:
        """Estimate print time in minutes."""
        layer_height = self._default_settings['layer_height']
        print_speed = self._default_settings['print_speed']

        n_layers = int(geometry.shape[2] * voxel_size / layer_height)

        # Estimate perimeter and infill per layer
        avg_voxels_per_layer = np.mean(np.sum(geometry > 0.5, axis=(0, 1)))
        perimeter_per_layer = np.sqrt(avg_voxels_per_layer) * 4 * voxel_size
        infill_per_layer = avg_voxels_per_layer * voxel_size * (self._default_settings['infill_density'] / 100)

        total_travel = (perimeter_per_layer + infill_per_layer) * n_layers
        print_time = total_travel / (print_speed * 60)  # Convert to minutes

        return print_time

    def _find_optimal_orientation(self, geometry: np.ndarray) -> Tuple[float, float, float]:
        """Find optimal print orientation."""
        # Simplified: check overhang counts for different orientations
        orientations = [
            (0, 0, 0),
            (90, 0, 0),
            (0, 90, 0),
            (0, 0, 90),
        ]

        best_orientation = (0, 0, 0)
        min_overhangs = float('inf')

        for orient in orientations:
            # Rotate geometry (simplified - just use current for demo)
            overhang_count = self._count_overhangs(geometry)
            if overhang_count < min_overhangs:
                min_overhangs = overhang_count
                best_orientation = orient

        return best_orientation

    def _count_overhangs(self, geometry: np.ndarray) -> int:
        """Count overhang voxels."""
        count = 0
        for z in range(1, geometry.shape[2]):
            current = geometry[:, :, z] > 0.5
            prev = geometry[:, :, z-1] > 0.5
            count += np.sum(current & ~prev)
        return count

    def _recommend_settings(self,
                           geometry: np.ndarray,
                           issues: List[PrintabilityIssue],
                           material: str) -> Dict[str, Any]:
        """Recommend slicer settings."""
        settings = self._default_settings.copy()

        # Adjust based on issues
        has_thin_walls = any(i.issue_type == PrintIssue.THIN_WALL for i in issues)
        has_bridging = any(i.issue_type == PrintIssue.BRIDGING for i in issues)
        has_overhangs = any(i.issue_type == PrintIssue.OVERHANG for i in issues)

        if has_thin_walls:
            settings['layer_height'] = 0.15  # Smaller layer for detail
            settings['print_speed'] = 40  # Slower for accuracy

        if has_bridging:
            settings['bridge_speed'] = 20
            settings['fan_speed_bridge'] = 100

        if has_overhangs:
            settings['support_enabled'] = True
            settings['support_angle'] = 40

        return settings

    def _calculate_score(self,
                        issues: List[PrintabilityIssue],
                        support_volume: float,
                        geometry: np.ndarray) -> float:
        """Calculate overall printability score."""
        # Base score
        score = 1.0

        # Penalty for issues
        for issue in issues:
            if issue.severity > 0.8:
                score -= 0.1
            elif issue.severity > 0.5:
                score -= 0.05
            else:
                score -= 0.02

        # Penalty for support
        part_volume = np.sum(geometry)
        support_ratio = support_volume / (part_volume + 1)
        score -= min(0.3, support_ratio * 0.5)

        return max(0, min(1, score))
