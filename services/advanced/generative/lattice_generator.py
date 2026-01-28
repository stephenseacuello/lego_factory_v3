"""
Lattice Generator - Infill pattern optimization.

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


class LatticeType(Enum):
    """Types of lattice structures."""
    GRID = "grid"
    HONEYCOMB = "honeycomb"
    GYROID = "gyroid"
    OCTET = "octet"
    DIAMOND = "diamond"
    CUBIC = "cubic"
    SCHWARZ_P = "schwarz_p"
    KELVIN = "kelvin"
    CUSTOM = "custom"


class InfillPattern(Enum):
    """Standard infill patterns for 3D printing."""
    LINES = "lines"
    GRID = "grid"
    TRIANGLES = "triangles"
    TRI_HEXAGON = "tri_hexagon"
    CUBIC = "cubic"
    CUBIC_SUBDIVISION = "cubic_subdivision"
    OCTET = "octet"
    GYROID = "gyroid"
    CONCENTRIC = "concentric"
    ZIGZAG = "zigzag"
    CROSS = "cross"
    LIGHTNING = "lightning"


@dataclass
class LatticeCell:
    """Unit cell of lattice structure."""
    cell_type: LatticeType
    size: Tuple[float, float, float]  # x, y, z dimensions in mm
    strut_diameter: float  # Strut thickness in mm
    relative_density: float  # 0-1, how solid the cell is
    orientation: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # Rotation angles


@dataclass
class LatticeRegion:
    """Region with specific lattice properties."""
    region_id: str
    bounds: Tuple[Tuple[float, float, float], Tuple[float, float, float]]  # (min, max) corners
    cell: LatticeCell
    purpose: str = ""  # e.g., "stress concentration", "weight reduction"


@dataclass
class LatticeDesign:
    """Complete lattice design."""
    design_id: str
    regions: List[LatticeRegion]
    estimated_weight_reduction: float
    estimated_strength_retention: float
    print_time_factor: float
    material_volume: float
    created_at: datetime = field(default_factory=datetime.utcnow)


class LatticeGenerator:
    """
    Lattice/infill structure generator.

    Features:
    - Multiple lattice types (TPMS, strut-based)
    - Variable density gradients
    - Stress-adapted lattices
    - FDM-optimized patterns
    """

    def __init__(self):
        self._lattice_properties: Dict[LatticeType, Dict] = {}
        self._load_lattice_properties()

    def _load_lattice_properties(self) -> None:
        """Load properties for each lattice type."""
        self._lattice_properties = {
            LatticeType.GRID: {
                'min_strut': 0.4,
                'max_density': 0.5,
                'isotropy': 0.3,
                'printability': 0.9,
                'strength_efficiency': 0.6
            },
            LatticeType.HONEYCOMB: {
                'min_strut': 0.4,
                'max_density': 0.4,
                'isotropy': 0.7,
                'printability': 0.85,
                'strength_efficiency': 0.75
            },
            LatticeType.GYROID: {
                'min_strut': 0.5,
                'max_density': 0.5,
                'isotropy': 0.95,
                'printability': 0.7,
                'strength_efficiency': 0.85
            },
            LatticeType.OCTET: {
                'min_strut': 0.4,
                'max_density': 0.3,
                'isotropy': 0.9,
                'printability': 0.6,
                'strength_efficiency': 0.9
            },
            LatticeType.DIAMOND: {
                'min_strut': 0.4,
                'max_density': 0.35,
                'isotropy': 0.85,
                'printability': 0.65,
                'strength_efficiency': 0.8
            },
            LatticeType.CUBIC: {
                'min_strut': 0.3,
                'max_density': 0.6,
                'isotropy': 0.3,
                'printability': 0.95,
                'strength_efficiency': 0.5
            },
            LatticeType.SCHWARZ_P: {
                'min_strut': 0.6,
                'max_density': 0.5,
                'isotropy': 0.95,
                'printability': 0.6,
                'strength_efficiency': 0.8
            },
            LatticeType.KELVIN: {
                'min_strut': 0.4,
                'max_density': 0.3,
                'isotropy': 0.8,
                'printability': 0.5,
                'strength_efficiency': 0.7
            }
        }

    def generate_uniform_lattice(self,
                                volume_bounds: Tuple[Tuple[float, float, float],
                                                     Tuple[float, float, float]],
                                lattice_type: LatticeType,
                                target_density: float = 0.2,
                                cell_size: float = 2.0) -> LatticeDesign:
        """
        Generate uniform lattice structure.

        Args:
            volume_bounds: (min_corner, max_corner)
            lattice_type: Type of lattice
            target_density: Target relative density (0-1)
            cell_size: Unit cell size in mm

        Returns:
            Lattice design
        """
        props = self._lattice_properties.get(lattice_type, {})

        # Calculate strut diameter for target density
        strut_diameter = self._calculate_strut_for_density(
            lattice_type, target_density, cell_size
        )

        cell = LatticeCell(
            cell_type=lattice_type,
            size=(cell_size, cell_size, cell_size),
            strut_diameter=strut_diameter,
            relative_density=target_density
        )

        region = LatticeRegion(
            region_id="uniform",
            bounds=volume_bounds,
            cell=cell,
            purpose="uniform infill"
        )

        # Calculate metrics
        volume = self._calculate_volume(volume_bounds)
        material_volume = volume * target_density
        weight_reduction = 1 - target_density
        strength_retention = self._estimate_strength_retention(
            lattice_type, target_density
        )

        return LatticeDesign(
            design_id=f"lattice_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            regions=[region],
            estimated_weight_reduction=weight_reduction,
            estimated_strength_retention=strength_retention,
            print_time_factor=1 + (1 - target_density) * 0.3,  # Lower density = more travel
            material_volume=material_volume
        )

    def generate_gradient_lattice(self,
                                  volume_bounds: Tuple[Tuple[float, float, float],
                                                       Tuple[float, float, float]],
                                  lattice_type: LatticeType,
                                  density_function: str = 'linear',
                                  min_density: float = 0.1,
                                  max_density: float = 0.4,
                                  gradient_axis: str = 'z',
                                  n_regions: int = 5) -> LatticeDesign:
        """
        Generate gradient density lattice.

        Args:
            volume_bounds: (min_corner, max_corner)
            lattice_type: Type of lattice
            density_function: 'linear', 'parabolic', 'exponential'
            min_density: Minimum density
            max_density: Maximum density
            gradient_axis: Axis for gradient ('x', 'y', 'z')
            n_regions: Number of gradient regions

        Returns:
            Lattice design with gradient
        """
        min_corner, max_corner = volume_bounds
        axis_idx = {'x': 0, 'y': 1, 'z': 2}[gradient_axis]

        regions = []
        axis_min = min_corner[axis_idx]
        axis_max = max_corner[axis_idx]
        region_size = (axis_max - axis_min) / n_regions

        for i in range(n_regions):
            # Calculate density for this region
            t = i / (n_regions - 1) if n_regions > 1 else 0
            if density_function == 'linear':
                density = min_density + (max_density - min_density) * t
            elif density_function == 'parabolic':
                density = min_density + (max_density - min_density) * (t ** 2)
            elif density_function == 'exponential':
                density = min_density * np.exp(t * np.log(max_density / min_density))
            else:
                density = min_density

            # Create bounds for this region
            region_min = list(min_corner)
            region_max = list(max_corner)
            region_min[axis_idx] = axis_min + i * region_size
            region_max[axis_idx] = axis_min + (i + 1) * region_size

            strut_diameter = self._calculate_strut_for_density(
                lattice_type, density, 2.0
            )

            cell = LatticeCell(
                cell_type=lattice_type,
                size=(2.0, 2.0, 2.0),
                strut_diameter=strut_diameter,
                relative_density=density
            )

            regions.append(LatticeRegion(
                region_id=f"gradient_{i}",
                bounds=(tuple(region_min), tuple(region_max)),
                cell=cell,
                purpose=f"gradient layer {i+1}"
            ))

        # Calculate overall metrics
        avg_density = sum(r.cell.relative_density for r in regions) / len(regions)
        volume = self._calculate_volume(volume_bounds)

        return LatticeDesign(
            design_id=f"gradient_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            regions=regions,
            estimated_weight_reduction=1 - avg_density,
            estimated_strength_retention=self._estimate_strength_retention(
                lattice_type, avg_density
            ),
            print_time_factor=1.2,
            material_volume=volume * avg_density
        )

    def generate_stress_adapted(self,
                               volume_bounds: Tuple[Tuple[float, float, float],
                                                    Tuple[float, float, float]],
                               stress_field: np.ndarray,
                               lattice_type: LatticeType,
                               min_density: float = 0.1,
                               max_density: float = 0.5) -> LatticeDesign:
        """
        Generate stress-adapted lattice.

        Args:
            volume_bounds: (min_corner, max_corner)
            stress_field: 3D array of stress values
            lattice_type: Type of lattice
            min_density: Minimum density
            max_density: Maximum density

        Returns:
            Stress-adapted lattice design
        """
        # Normalize stress field
        stress_norm = (stress_field - stress_field.min()) / (stress_field.max() - stress_field.min() + 1e-10)

        # Map stress to density (higher stress = higher density)
        density_field = min_density + (max_density - min_density) * stress_norm

        # Create regions based on density thresholds
        regions = []
        n_levels = 5
        density_levels = np.linspace(min_density, max_density, n_levels + 1)

        for i in range(n_levels):
            mask = (density_field >= density_levels[i]) & (density_field < density_levels[i+1])
            if np.any(mask):
                avg_density = (density_levels[i] + density_levels[i+1]) / 2

                strut_diameter = self._calculate_strut_for_density(
                    lattice_type, avg_density, 2.0
                )

                cell = LatticeCell(
                    cell_type=lattice_type,
                    size=(2.0, 2.0, 2.0),
                    strut_diameter=strut_diameter,
                    relative_density=avg_density
                )

                regions.append(LatticeRegion(
                    region_id=f"stress_level_{i}",
                    bounds=volume_bounds,  # Would need refinement for actual regions
                    cell=cell,
                    purpose=f"stress-adapted level {i+1}"
                ))

        avg_density = np.mean(density_field)
        volume = self._calculate_volume(volume_bounds)

        return LatticeDesign(
            design_id=f"stress_adapted_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            regions=regions,
            estimated_weight_reduction=1 - avg_density,
            estimated_strength_retention=self._estimate_strength_retention(
                lattice_type, avg_density
            ) * 1.1,  # Bonus for stress-adaptation
            print_time_factor=1.3,
            material_volume=volume * avg_density
        )

    def _calculate_strut_for_density(self,
                                     lattice_type: LatticeType,
                                     target_density: float,
                                     cell_size: float) -> float:
        """Calculate strut diameter for target density."""
        # Simplified model: density ~ n * (d/L)^2 where n depends on lattice type
        n_factors = {
            LatticeType.GRID: 3.0,
            LatticeType.HONEYCOMB: 2.5,
            LatticeType.GYROID: 1.5,
            LatticeType.OCTET: 4.0,
            LatticeType.DIAMOND: 3.5,
            LatticeType.CUBIC: 3.0,
            LatticeType.SCHWARZ_P: 1.5,
            LatticeType.KELVIN: 3.0
        }

        n = n_factors.get(lattice_type, 3.0)
        strut_ratio = np.sqrt(target_density / n)
        strut_diameter = strut_ratio * cell_size

        # Enforce minimum printable strut
        min_strut = self._lattice_properties.get(lattice_type, {}).get('min_strut', 0.4)
        return max(min_strut, strut_diameter)

    def _calculate_volume(self,
                         bounds: Tuple[Tuple[float, float, float],
                                       Tuple[float, float, float]]) -> float:
        """Calculate volume from bounds."""
        min_corner, max_corner = bounds
        return ((max_corner[0] - min_corner[0]) *
                (max_corner[1] - min_corner[1]) *
                (max_corner[2] - min_corner[2]))

    def _estimate_strength_retention(self,
                                     lattice_type: LatticeType,
                                     density: float) -> float:
        """Estimate strength retention for lattice."""
        props = self._lattice_properties.get(lattice_type, {})
        efficiency = props.get('strength_efficiency', 0.7)

        # Gibson-Ashby relationship: strength ~ density^n where n ~ 1.5-2
        n = 1.5 if efficiency > 0.8 else 1.8
        return min(1.0, efficiency * (density ** n) / (1.0 ** n))

    def recommend_lattice(self,
                         requirements: Dict[str, float]) -> Dict[str, Any]:
        """
        Recommend best lattice type for requirements.

        Args:
            requirements: {
                'strength_priority': 0-1,
                'weight_priority': 0-1,
                'printability_priority': 0-1,
                'isotropy_priority': 0-1
            }

        Returns:
            Recommendation with scores
        """
        scores = {}

        for lattice_type, props in self._lattice_properties.items():
            score = 0
            score += requirements.get('strength_priority', 0) * props['strength_efficiency']
            score += requirements.get('weight_priority', 0) * (1 - props['max_density'])
            score += requirements.get('printability_priority', 0) * props['printability']
            score += requirements.get('isotropy_priority', 0) * props['isotropy']
            scores[lattice_type.value] = score

        best = max(scores.items(), key=lambda x: x[1])

        return {
            'recommended': best[0],
            'score': best[1],
            'all_scores': scores
        }

    def convert_to_infill_pattern(self, lattice_type: LatticeType) -> InfillPattern:
        """Convert lattice type to equivalent slicer infill pattern."""
        mapping = {
            LatticeType.GRID: InfillPattern.GRID,
            LatticeType.HONEYCOMB: InfillPattern.TRI_HEXAGON,
            LatticeType.GYROID: InfillPattern.GYROID,
            LatticeType.OCTET: InfillPattern.OCTET,
            LatticeType.CUBIC: InfillPattern.CUBIC,
        }
        return mapping.get(lattice_type, InfillPattern.GRID)
