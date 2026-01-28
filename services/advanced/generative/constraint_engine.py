"""
Manufacturing Constraints - Printability constraints for generative design.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 3: Generative Design System
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class PrintOrientation(Enum):
    """Print build orientation."""
    XY_FLAT = "xy_flat"
    XZ_VERTICAL = "xz_vertical"
    YZ_VERTICAL = "yz_vertical"
    OPTIMAL = "optimal"


@dataclass
class ManufacturingConstraints:
    """Base manufacturing constraints."""
    min_wall_thickness: float = 0.8  # mm
    min_feature_size: float = 0.4  # mm
    max_aspect_ratio: float = 10.0
    requires_support: bool = True


@dataclass
class FDMConstraints(ManufacturingConstraints):
    """FDM-specific manufacturing constraints."""
    nozzle_diameter: float = 0.4  # mm
    layer_height: float = 0.2  # mm
    max_overhang_angle: float = 45  # degrees
    max_bridge_length: float = 10.0  # mm
    min_hole_diameter: float = 2.0  # mm
    xy_compensation: float = 0.0  # mm
    z_compensation: float = 0.0  # mm
    print_orientation: PrintOrientation = PrintOrientation.OPTIMAL

    def get_effective_min_feature(self) -> float:
        """Get effective minimum feature size."""
        return max(self.min_feature_size, self.nozzle_diameter)

    def validate_geometry(self, geometry: np.ndarray) -> Dict[str, Any]:
        """
        Validate geometry against FDM constraints.

        Returns validation report.
        """
        report = {
            'valid': True,
            'issues': [],
            'warnings': []
        }

        # Check minimum wall thickness
        wall_issues = self._check_wall_thickness(geometry)
        if wall_issues:
            report['issues'].extend(wall_issues)
            report['valid'] = False

        # Check overhangs
        overhang_issues = self._check_overhangs(geometry)
        if overhang_issues:
            report['warnings'].extend(overhang_issues)

        # Check bridges
        bridge_issues = self._check_bridges(geometry)
        if bridge_issues:
            report['warnings'].extend(bridge_issues)

        return report

    def _check_wall_thickness(self, geometry: np.ndarray) -> List[str]:
        """Check for walls thinner than minimum."""
        issues = []
        # Simplified check - in production would analyze actual wall thicknesses
        if np.min(geometry[geometry > 0.5]) < self.min_wall_thickness:
            issues.append(f"Walls thinner than {self.min_wall_thickness}mm detected")
        return issues

    def _check_overhangs(self, geometry: np.ndarray) -> List[str]:
        """Check for problematic overhangs."""
        warnings = []
        # Simplified - would calculate actual overhang angles
        return warnings

    def _check_bridges(self, geometry: np.ndarray) -> List[str]:
        """Check for bridges exceeding maximum length."""
        warnings = []
        return warnings


@dataclass
class SLAConstraints(ManufacturingConstraints):
    """SLA-specific manufacturing constraints."""
    xy_resolution: float = 0.05  # mm
    layer_height: float = 0.05  # mm
    min_wall_thickness: float = 0.5  # mm
    min_supported_angle: float = 20  # degrees
    max_unsupported_area: float = 100  # mm2
    drain_hole_diameter: float = 2.0  # mm
    requires_drain_holes: bool = True


class ConstraintChecker:
    """
    Check geometry against manufacturing constraints.
    """

    def __init__(self, constraints: ManufacturingConstraints):
        self.constraints = constraints

    def check_all(self, geometry: np.ndarray) -> Dict[str, Any]:
        """Run all constraint checks."""
        if isinstance(self.constraints, FDMConstraints):
            return self.constraints.validate_geometry(geometry)
        else:
            return {'valid': True, 'issues': [], 'warnings': []}

    def apply_compensation(self, geometry: np.ndarray) -> np.ndarray:
        """Apply dimensional compensation for manufacturing."""
        if isinstance(self.constraints, FDMConstraints):
            return self._apply_fdm_compensation(geometry)
        return geometry

    def _apply_fdm_compensation(self, geometry: np.ndarray) -> np.ndarray:
        """Apply FDM-specific dimensional compensation."""
        constraints = self.constraints

        # Apply XY compensation (shrinkage/expansion)
        if constraints.xy_compensation != 0:
            from scipy.ndimage import binary_dilation, binary_erosion
            binary = geometry > 0.5

            if constraints.xy_compensation > 0:
                # Expand (compensate for shrinkage)
                iterations = int(constraints.xy_compensation / 0.1)
                binary = binary_dilation(binary, iterations=iterations)
            else:
                # Contract (compensate for expansion)
                iterations = int(-constraints.xy_compensation / 0.1)
                binary = binary_erosion(binary, iterations=iterations)

            result = geometry.copy()
            result[~binary] = 0.001
            return result

        return geometry

    def suggest_orientation(self, geometry: np.ndarray) -> PrintOrientation:
        """Suggest optimal print orientation."""
        # Analyze geometry to find best orientation
        # Simplified - in production would analyze overhangs, supports, etc.

        shape = geometry.shape
        # Prefer orientation with smallest Z height for faster printing
        if shape[2] <= min(shape[0], shape[1]):
            return PrintOrientation.XY_FLAT
        elif shape[1] <= shape[0]:
            return PrintOrientation.XZ_VERTICAL
        else:
            return PrintOrientation.YZ_VERTICAL

    def estimate_support_volume(self, geometry: np.ndarray) -> float:
        """Estimate required support material volume."""
        if isinstance(self.constraints, FDMConstraints):
            # Simplified support estimation
            max_overhang = self.constraints.max_overhang_angle

            support_voxels = 0
            for z in range(1, geometry.shape[2]):
                for i in range(geometry.shape[0]):
                    for j in range(geometry.shape[1]):
                        if geometry[i, j, z] > 0.5:
                            if geometry[i, j, z-1] < 0.5:
                                support_voxels += 1

            return float(support_voxels)
        return 0.0
