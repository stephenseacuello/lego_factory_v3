"""
Material Usage Evaluator - Material efficiency metrics.

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


class MaterialType(Enum):
    """Types of 3D printing materials."""
    PLA = "pla"
    ABS = "abs"
    PETG = "petg"
    TPU = "tpu"
    NYLON = "nylon"
    ASA = "asa"


@dataclass
class MaterialCost:
    """Material cost data."""
    material: MaterialType
    cost_per_kg: float  # USD
    density: float  # g/cm³
    waste_factor: float  # Typical waste percentage


@dataclass
class MaterialUsageResult:
    """Material usage evaluation result."""
    volume_mm3: float
    weight_grams: float
    cost_usd: float
    efficiency_ratio: float  # Solid volume / bounding box
    waste_estimate: float  # grams
    co2_footprint: float  # kg CO2
    recyclability: float  # 0-1
    sustainability_score: float  # 0-1
    fitness_score: float  # 0-1 for optimization
    breakdown: Dict[str, float]


class MaterialUsageEvaluator:
    """
    Material efficiency evaluator for generative designs.

    Features:
    - Volume and weight calculation
    - Cost estimation
    - Sustainability metrics
    - Waste analysis
    """

    def __init__(self):
        self._materials: Dict[MaterialType, MaterialCost] = {}
        self._load_material_data()

    def _load_material_data(self) -> None:
        """Load material cost and properties data."""
        self._materials = {
            MaterialType.PLA: MaterialCost(
                material=MaterialType.PLA,
                cost_per_kg=25.0,
                density=1.24,
                waste_factor=0.10
            ),
            MaterialType.ABS: MaterialCost(
                material=MaterialType.ABS,
                cost_per_kg=22.0,
                density=1.05,
                waste_factor=0.12
            ),
            MaterialType.PETG: MaterialCost(
                material=MaterialType.PETG,
                cost_per_kg=28.0,
                density=1.27,
                waste_factor=0.08
            ),
            MaterialType.TPU: MaterialCost(
                material=MaterialType.TPU,
                cost_per_kg=45.0,
                density=1.20,
                waste_factor=0.15
            ),
            MaterialType.NYLON: MaterialCost(
                material=MaterialType.NYLON,
                cost_per_kg=55.0,
                density=1.15,
                waste_factor=0.12
            ),
            MaterialType.ASA: MaterialCost(
                material=MaterialType.ASA,
                cost_per_kg=35.0,
                density=1.07,
                waste_factor=0.10
            )
        }

        # CO2 footprint per kg of material (manufacturing + end of life)
        self._co2_per_kg = {
            MaterialType.PLA: 1.8,  # kg CO2 per kg material
            MaterialType.ABS: 3.5,
            MaterialType.PETG: 2.5,
            MaterialType.TPU: 4.0,
            MaterialType.NYLON: 6.5,
            MaterialType.ASA: 3.8
        }

        # Recyclability scores
        self._recyclability = {
            MaterialType.PLA: 0.9,  # Biodegradable
            MaterialType.ABS: 0.7,
            MaterialType.PETG: 0.8,
            MaterialType.TPU: 0.4,
            MaterialType.NYLON: 0.5,
            MaterialType.ASA: 0.6
        }

    def evaluate(self,
                geometry: np.ndarray,
                voxel_size: float = 0.5,
                material: MaterialType = MaterialType.PLA,
                infill_density: float = 0.2) -> MaterialUsageResult:
        """
        Evaluate material usage of design.

        Args:
            geometry: 3D density field (0-1)
            voxel_size: Size of each voxel in mm
            material: Material type
            infill_density: Internal infill density (0-1)

        Returns:
            Material usage evaluation result
        """
        mat_data = self._materials.get(material, self._materials[MaterialType.PLA])

        # Calculate volumes
        solid_voxels = np.sum(geometry > 0.5)
        partial_voxels = np.sum((geometry > 0) & (geometry <= 0.5))

        voxel_volume = voxel_size ** 3  # mm³

        # Estimate shell vs infill
        shell_fraction = self._estimate_shell_fraction(geometry)
        infill_fraction = 1 - shell_fraction

        # Total material volume
        solid_volume = solid_voxels * voxel_volume
        infill_volume = partial_voxels * voxel_volume * infill_density
        total_volume = solid_volume + infill_volume

        # Bounding box volume
        bbox_volume = np.prod(geometry.shape) * voxel_volume

        # Efficiency ratio
        efficiency = total_volume / bbox_volume if bbox_volume > 0 else 0

        # Weight calculation
        weight = total_volume * mat_data.density / 1000  # grams

        # Cost calculation
        cost = (weight / 1000) * mat_data.cost_per_kg  # USD

        # Waste estimate
        waste = weight * mat_data.waste_factor

        # CO2 footprint
        total_material = weight + waste
        co2 = (total_material / 1000) * self._co2_per_kg.get(material, 3.0)

        # Recyclability
        recyclability = self._recyclability.get(material, 0.5)

        # Sustainability score
        sustainability = self._calculate_sustainability(
            efficiency, recyclability, co2, weight
        )

        # Fitness score (for optimization - lower material = higher fitness)
        # Normalized to 0-1 where 1 is best
        fitness = self._calculate_fitness(efficiency, weight, cost)

        # Breakdown
        breakdown = {
            'shell_volume_mm3': solid_volume * shell_fraction,
            'infill_volume_mm3': solid_volume * infill_fraction * infill_density,
            'support_estimate_mm3': total_volume * 0.1,  # Rough estimate
            'shell_weight_g': weight * shell_fraction,
            'infill_weight_g': weight * infill_fraction,
            'waste_weight_g': waste
        }

        return MaterialUsageResult(
            volume_mm3=total_volume,
            weight_grams=weight,
            cost_usd=cost,
            efficiency_ratio=efficiency,
            waste_estimate=waste,
            co2_footprint=co2,
            recyclability=recyclability,
            sustainability_score=sustainability,
            fitness_score=fitness,
            breakdown=breakdown
        )

    def _estimate_shell_fraction(self, geometry: np.ndarray) -> float:
        """Estimate fraction of geometry that is shell (surface)."""
        solid = geometry > 0.5

        # Count surface voxels (have at least one non-solid neighbor)
        surface_count = 0
        total_count = np.sum(solid)

        for i in range(1, geometry.shape[0]-1):
            for j in range(1, geometry.shape[1]-1):
                for k in range(1, geometry.shape[2]-1):
                    if solid[i, j, k]:
                        # Check if any neighbor is not solid
                        neighbors = [
                            solid[i-1,j,k], solid[i+1,j,k],
                            solid[i,j-1,k], solid[i,j+1,k],
                            solid[i,j,k-1], solid[i,j,k+1]
                        ]
                        if not all(neighbors):
                            surface_count += 1

        return surface_count / total_count if total_count > 0 else 1.0

    def _calculate_sustainability(self,
                                 efficiency: float,
                                 recyclability: float,
                                 co2: float,
                                 weight: float) -> float:
        """Calculate sustainability score."""
        # Normalize CO2 (lower is better)
        co2_score = max(0, 1 - (co2 / 1.0))  # Assuming 1 kg CO2 as reference

        # Weight efficiency (less material is better)
        weight_score = max(0, 1 - (weight / 100))  # Assuming 100g as reference

        # Combined sustainability score
        sustainability = (
            0.3 * efficiency +
            0.3 * recyclability +
            0.2 * co2_score +
            0.2 * weight_score
        )

        return max(0, min(1, sustainability))

    def _calculate_fitness(self,
                          efficiency: float,
                          weight: float,
                          cost: float) -> float:
        """Calculate fitness score for optimization."""
        # Weight penalty (normalize to expected range)
        weight_score = 1 / (1 + weight / 50)  # 50g reference

        # Cost penalty
        cost_score = 1 / (1 + cost)

        # Efficiency bonus
        efficiency_score = efficiency

        # Combined fitness
        fitness = 0.4 * efficiency_score + 0.3 * weight_score + 0.3 * cost_score

        return max(0, min(1, fitness))

    def compare_materials(self,
                         geometry: np.ndarray,
                         voxel_size: float = 0.5,
                         materials: Optional[List[MaterialType]] = None) -> Dict[str, MaterialUsageResult]:
        """
        Compare material usage across different materials.

        Args:
            geometry: 3D density field
            voxel_size: Voxel size in mm
            materials: Materials to compare (default: all)

        Returns:
            Dictionary of results per material
        """
        if materials is None:
            materials = list(MaterialType)

        results = {}
        for material in materials:
            results[material.value] = self.evaluate(
                geometry, voxel_size, material
            )

        return results

    def optimize_infill(self,
                       geometry: np.ndarray,
                       voxel_size: float = 0.5,
                       material: MaterialType = MaterialType.PLA,
                       target_weight: Optional[float] = None,
                       target_cost: Optional[float] = None) -> Dict[str, Any]:
        """
        Find optimal infill density for targets.

        Args:
            geometry: 3D density field
            voxel_size: Voxel size in mm
            material: Material type
            target_weight: Target weight in grams
            target_cost: Target cost in USD

        Returns:
            Optimal infill settings
        """
        infill_options = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]

        results = []
        for infill in infill_options:
            result = self.evaluate(geometry, voxel_size, material, infill)
            score = result.fitness_score

            # Adjust score based on targets
            if target_weight and result.weight_grams > target_weight:
                score *= (target_weight / result.weight_grams)
            if target_cost and result.cost_usd > target_cost:
                score *= (target_cost / result.cost_usd)

            results.append({
                'infill': infill,
                'weight': result.weight_grams,
                'cost': result.cost_usd,
                'score': score
            })

        # Find best option
        best = max(results, key=lambda r: r['score'])

        return {
            'optimal_infill': best['infill'],
            'expected_weight': best['weight'],
            'expected_cost': best['cost'],
            'all_options': results
        }

    def estimate_batch_cost(self,
                           geometry: np.ndarray,
                           voxel_size: float,
                           material: MaterialType,
                           quantity: int,
                           include_setup: bool = True) -> Dict[str, float]:
        """
        Estimate cost for batch production.

        Args:
            geometry: 3D density field
            voxel_size: Voxel size in mm
            material: Material type
            quantity: Number of parts
            include_setup: Include setup costs

        Returns:
            Cost breakdown
        """
        single_result = self.evaluate(geometry, voxel_size, material)

        # Material cost
        material_cost = single_result.cost_usd * quantity

        # Waste cost (some waste per batch)
        waste_cost = material_cost * 0.1

        # Setup cost (per batch)
        setup_cost = 5.0 if include_setup else 0

        # Volume discount
        if quantity >= 100:
            discount = 0.15
        elif quantity >= 50:
            discount = 0.10
        elif quantity >= 20:
            discount = 0.05
        else:
            discount = 0

        subtotal = material_cost + waste_cost + setup_cost
        total = subtotal * (1 - discount)

        return {
            'material_cost': material_cost,
            'waste_cost': waste_cost,
            'setup_cost': setup_cost,
            'subtotal': subtotal,
            'discount_percent': discount * 100,
            'total': total,
            'cost_per_unit': total / quantity
        }

    def get_material_info(self, material: MaterialType) -> Dict[str, Any]:
        """Get material information."""
        mat_data = self._materials.get(material)
        if not mat_data:
            return {}

        return {
            'name': material.value.upper(),
            'cost_per_kg': mat_data.cost_per_kg,
            'density_g_cm3': mat_data.density,
            'waste_factor': mat_data.waste_factor,
            'co2_per_kg': self._co2_per_kg.get(material, 0),
            'recyclability': self._recyclability.get(material, 0)
        }
