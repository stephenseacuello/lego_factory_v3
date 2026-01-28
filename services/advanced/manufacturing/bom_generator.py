"""
BOM Generator - Bill of Materials from LEGO Model Specifications

Explodes LEGO model specs into manufacturable parts and operations.
Generates comprehensive BOMs for production planning.

LEGO MCP Manufacturing System v7.0
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class PartType(Enum):
    """Types of parts in a LEGO assembly."""
    BRICK = "brick"
    PLATE = "plate"
    TILE = "tile"
    SLOPE = "slope"
    TECHNIC = "technic"
    SPECIAL = "special"
    CUSTOM = "custom"


class ManufacturingProcess(Enum):
    """Manufacturing processes for parts."""
    SLA_PRINT = "sla_print"
    FDM_PRINT = "fdm_print"
    CNC_MILL = "cnc_mill"
    INJECTION_MOLD = "injection_mold"
    PURCHASED = "purchased"


@dataclass
class PartSpec:
    """Specification for a single part."""
    part_id: str
    part_type: PartType
    dimensions: Dict[str, float]  # studs_x, studs_y, height_plates
    color: str
    material: str = "ABS"
    quantity: int = 1
    manufacturing_process: ManufacturingProcess = ManufacturingProcess.SLA_PRINT
    print_time_minutes: float = 0.0
    material_grams: float = 0.0
    critical_dimensions: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""


@dataclass
class BOMItem:
    """Single item in the Bill of Materials."""
    item_number: int
    part_spec: PartSpec
    level: int  # BOM indentation level (1 = top level)
    parent_item: Optional[int] = None
    assembly_step: int = 0
    position: List[float] = field(default_factory=list)  # x, y, z in studs
    orientation: int = 0  # degrees rotation


@dataclass
class BillOfMaterials:
    """Complete Bill of Materials for a LEGO assembly."""
    bom_id: str
    model_name: str
    model_version: str
    created_at: datetime
    items: List[BOMItem]
    total_parts: int
    total_unique_parts: int
    total_print_time_hours: float
    total_material_grams: float
    assembly_steps: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert BOM to dictionary."""
        return {
            'bom_id': self.bom_id,
            'model_name': self.model_name,
            'model_version': self.model_version,
            'created_at': self.created_at.isoformat(),
            'items': [
                {
                    'item_number': item.item_number,
                    'part_id': item.part_spec.part_id,
                    'part_type': item.part_spec.part_type.value,
                    'dimensions': item.part_spec.dimensions,
                    'color': item.part_spec.color,
                    'quantity': item.part_spec.quantity,
                    'process': item.part_spec.manufacturing_process.value,
                    'level': item.level,
                    'assembly_step': item.assembly_step,
                    'position': item.position,
                }
                for item in self.items
            ],
            'summary': {
                'total_parts': self.total_parts,
                'total_unique_parts': self.total_unique_parts,
                'total_print_time_hours': self.total_print_time_hours,
                'total_material_grams': self.total_material_grams,
                'assembly_steps': self.assembly_steps,
            },
            'metadata': self.metadata,
        }


class BOMGenerator:
    """
    Generates Bill of Materials from LEGO model specifications.

    Supports:
    - LDraw format parsing
    - LEGO Digital Designer (LDD) files
    - Custom JSON format
    - Standard brick library lookup
    """

    def __init__(self):
        self._brick_library = self._load_brick_library()
        self._print_time_estimator = PrintTimeEstimator()
        self._material_calculator = MaterialCalculator()

    def _load_brick_library(self) -> Dict[str, Dict[str, Any]]:
        """Load standard LEGO brick library."""
        # Standard brick definitions
        return {
            '3001': {  # 2x4 Brick
                'type': PartType.BRICK,
                'dimensions': {'studs_x': 4, 'studs_y': 2, 'height_plates': 3},
                'print_time_base': 12.0,  # minutes
                'material_base': 2.5,  # grams
            },
            '3003': {  # 2x2 Brick
                'type': PartType.BRICK,
                'dimensions': {'studs_x': 2, 'studs_y': 2, 'height_plates': 3},
                'print_time_base': 8.0,
                'material_base': 1.2,
            },
            '3010': {  # 1x4 Brick
                'type': PartType.BRICK,
                'dimensions': {'studs_x': 4, 'studs_y': 1, 'height_plates': 3},
                'print_time_base': 6.0,
                'material_base': 1.0,
            },
            '3004': {  # 1x2 Brick
                'type': PartType.BRICK,
                'dimensions': {'studs_x': 2, 'studs_y': 1, 'height_plates': 3},
                'print_time_base': 4.0,
                'material_base': 0.5,
            },
            '3005': {  # 1x1 Brick
                'type': PartType.BRICK,
                'dimensions': {'studs_x': 1, 'studs_y': 1, 'height_plates': 3},
                'print_time_base': 3.0,
                'material_base': 0.3,
            },
            '3020': {  # 2x4 Plate
                'type': PartType.PLATE,
                'dimensions': {'studs_x': 4, 'studs_y': 2, 'height_plates': 1},
                'print_time_base': 5.0,
                'material_base': 0.8,
            },
            '3021': {  # 2x3 Plate
                'type': PartType.PLATE,
                'dimensions': {'studs_x': 3, 'studs_y': 2, 'height_plates': 1},
                'print_time_base': 4.0,
                'material_base': 0.6,
            },
            '3022': {  # 2x2 Plate
                'type': PartType.PLATE,
                'dimensions': {'studs_x': 2, 'studs_y': 2, 'height_plates': 1},
                'print_time_base': 3.0,
                'material_base': 0.4,
            },
            '3023': {  # 1x2 Plate
                'type': PartType.PLATE,
                'dimensions': {'studs_x': 2, 'studs_y': 1, 'height_plates': 1},
                'print_time_base': 2.0,
                'material_base': 0.2,
            },
            '3024': {  # 1x1 Plate
                'type': PartType.PLATE,
                'dimensions': {'studs_x': 1, 'studs_y': 1, 'height_plates': 1},
                'print_time_base': 1.5,
                'material_base': 0.1,
            },
            '3070b': {  # 1x1 Tile
                'type': PartType.TILE,
                'dimensions': {'studs_x': 1, 'studs_y': 1, 'height_plates': 1},
                'print_time_base': 2.0,
                'material_base': 0.15,
            },
            '3069b': {  # 1x2 Tile
                'type': PartType.TILE,
                'dimensions': {'studs_x': 2, 'studs_y': 1, 'height_plates': 1},
                'print_time_base': 2.5,
                'material_base': 0.25,
            },
        }

    def generate_bom(
        self,
        model_spec: Dict[str, Any],
        model_name: str = "Custom Model",
        model_version: str = "1.0"
    ) -> BillOfMaterials:
        """
        Generate BOM from model specification.

        Args:
            model_spec: Model specification with parts list
            model_name: Name of the model
            model_version: Version string

        Returns:
            Complete Bill of Materials
        """
        bom_id = f"BOM-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        items: List[BOMItem] = []
        item_number = 0

        # Parse parts from spec
        parts = model_spec.get('parts', [])
        assembly_sequence = model_spec.get('assembly_sequence', [])

        for part_data in parts:
            item_number += 1
            part_spec = self._create_part_spec(part_data)

            # Determine assembly step
            assembly_step = self._find_assembly_step(
                part_data.get('id', ''),
                assembly_sequence
            )

            item = BOMItem(
                item_number=item_number,
                part_spec=part_spec,
                level=part_data.get('level', 1),
                parent_item=part_data.get('parent'),
                assembly_step=assembly_step,
                position=part_data.get('position', [0, 0, 0]),
                orientation=part_data.get('orientation', 0),
            )
            items.append(item)

        # Calculate totals
        total_parts = sum(item.part_spec.quantity for item in items)
        unique_parts = len(set(item.part_spec.part_id for item in items))
        total_print_time = sum(
            item.part_spec.print_time_minutes * item.part_spec.quantity
            for item in items
        ) / 60.0
        total_material = sum(
            item.part_spec.material_grams * item.part_spec.quantity
            for item in items
        )
        max_step = max((item.assembly_step for item in items), default=0)

        return BillOfMaterials(
            bom_id=bom_id,
            model_name=model_name,
            model_version=model_version,
            created_at=datetime.now(),
            items=items,
            total_parts=total_parts,
            total_unique_parts=unique_parts,
            total_print_time_hours=total_print_time,
            total_material_grams=total_material,
            assembly_steps=max_step,
            metadata={
                'source_format': model_spec.get('format', 'custom'),
                'generated_by': 'LEGO MCP BOM Generator v7.0',
            }
        )

    def _create_part_spec(self, part_data: Dict[str, Any]) -> PartSpec:
        """Create part specification from data."""
        part_id = part_data.get('part_id', 'unknown')

        # Look up in brick library
        library_data = self._brick_library.get(part_id, {})

        # Determine type and dimensions
        if library_data:
            part_type = library_data['type']
            dimensions = library_data['dimensions']
            print_time = library_data['print_time_base']
            material = library_data['material_base']
        else:
            # Custom part
            part_type = PartType(part_data.get('type', 'custom'))
            dimensions = part_data.get('dimensions', {'studs_x': 2, 'studs_y': 2, 'height_plates': 3})
            print_time = self._print_time_estimator.estimate(dimensions)
            material = self._material_calculator.calculate(dimensions)

        # Adjust for color/material
        color = part_data.get('color', 'red')
        mat = part_data.get('material', 'ABS')

        return PartSpec(
            part_id=part_id,
            part_type=part_type,
            dimensions=dimensions,
            color=color,
            material=mat,
            quantity=part_data.get('quantity', 1),
            manufacturing_process=ManufacturingProcess(
                part_data.get('process', 'sla_print')
            ),
            print_time_minutes=print_time,
            material_grams=material,
            critical_dimensions=self._get_critical_dimensions(dimensions),
        )

    def _find_assembly_step(
        self,
        part_id: str,
        sequence: List[Dict[str, Any]]
    ) -> int:
        """Find assembly step for a part."""
        for i, step in enumerate(sequence, 1):
            if part_id in step.get('parts', []):
                return i
        return 0

    def _get_critical_dimensions(
        self,
        dimensions: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Get critical dimensions for quality inspection."""
        critical = []

        # Stud diameter is always critical
        critical.append({
            'dimension': 'stud_diameter',
            'nominal': 4.8,
            'tolerance': 0.02,
            'unit': 'mm',
        })

        # Overall dimensions
        if 'studs_x' in dimensions:
            length = dimensions['studs_x'] * 8.0
            critical.append({
                'dimension': 'length',
                'nominal': length,
                'tolerance': 0.05,
                'unit': 'mm',
            })

        if 'studs_y' in dimensions:
            width = dimensions['studs_y'] * 8.0
            critical.append({
                'dimension': 'width',
                'nominal': width,
                'tolerance': 0.05,
                'unit': 'mm',
            })

        if 'height_plates' in dimensions:
            height = dimensions['height_plates'] * 3.2
            critical.append({
                'dimension': 'height',
                'nominal': height,
                'tolerance': 0.05,
                'unit': 'mm',
            })

        return critical

    def generate_from_ldraw(self, ldraw_content: str) -> BillOfMaterials:
        """Generate BOM from LDraw format."""
        parts = []
        lines = ldraw_content.strip().split('\n')

        for line in lines:
            if line.startswith('1 '):
                # Type 1 line: part reference
                tokens = line.split()
                if len(tokens) >= 15:
                    color_code = int(tokens[1])
                    part_id = tokens[14].replace('.dat', '')

                    parts.append({
                        'part_id': part_id,
                        'color': self._ldraw_color_to_name(color_code),
                        'position': [float(tokens[2]), float(tokens[3]), float(tokens[4])],
                    })

        return self.generate_bom({'parts': parts, 'format': 'ldraw'})

    def _ldraw_color_to_name(self, code: int) -> str:
        """Convert LDraw color code to name."""
        colors = {
            0: 'black',
            1: 'blue',
            2: 'green',
            3: 'dark_cyan',
            4: 'red',
            5: 'dark_pink',
            6: 'brown',
            7: 'light_gray',
            14: 'yellow',
            15: 'white',
            19: 'tan',
            25: 'orange',
        }
        return colors.get(code, f'color_{code}')

    def consolidate_bom(self, bom: BillOfMaterials) -> Dict[str, Any]:
        """
        Consolidate BOM by part type for procurement/production.

        Returns grouped parts with quantities.
        """
        consolidated = {}

        for item in bom.items:
            key = f"{item.part_spec.part_id}_{item.part_spec.color}"

            if key not in consolidated:
                consolidated[key] = {
                    'part_id': item.part_spec.part_id,
                    'part_type': item.part_spec.part_type.value,
                    'dimensions': item.part_spec.dimensions,
                    'color': item.part_spec.color,
                    'material': item.part_spec.material,
                    'process': item.part_spec.manufacturing_process.value,
                    'quantity': 0,
                    'total_print_time_minutes': 0,
                    'total_material_grams': 0,
                }

            consolidated[key]['quantity'] += item.part_spec.quantity
            consolidated[key]['total_print_time_minutes'] += (
                item.part_spec.print_time_minutes * item.part_spec.quantity
            )
            consolidated[key]['total_material_grams'] += (
                item.part_spec.material_grams * item.part_spec.quantity
            )

        return {
            'bom_id': bom.bom_id,
            'model_name': bom.model_name,
            'consolidated_items': list(consolidated.values()),
            'summary': {
                'total_unique_parts': len(consolidated),
                'total_parts': sum(c['quantity'] for c in consolidated.values()),
            }
        }


class PrintTimeEstimator:
    """Estimates print time based on part dimensions."""

    def estimate(self, dimensions: Dict[str, float]) -> float:
        """Estimate print time in minutes."""
        volume = (
            dimensions.get('studs_x', 1) *
            dimensions.get('studs_y', 1) *
            dimensions.get('height_plates', 1)
        )
        # Base time + volume-based time
        return 2.0 + volume * 0.8


class MaterialCalculator:
    """Calculates material usage for parts."""

    def calculate(self, dimensions: Dict[str, float]) -> float:
        """Calculate material in grams."""
        volume = (
            dimensions.get('studs_x', 1) *
            dimensions.get('studs_y', 1) *
            dimensions.get('height_plates', 1)
        )
        # ABS density ~1.04 g/cm³, convert stud units to volume
        stud_volume_cm3 = 0.064  # Approx volume per stud unit
        return volume * stud_volume_cm3 * 1.04


# Singleton instance
_bom_generator: Optional[BOMGenerator] = None


def get_bom_generator() -> BOMGenerator:
    """Get BOM generator singleton."""
    global _bom_generator
    if _bom_generator is None:
        _bom_generator = BOMGenerator()
    return _bom_generator
