"""
LEGO Factory v3 - LEGO Parts Catalog Models
============================================
Master catalog of LEGO parts, materials, and manufactured products.

SKU Format: {LEGO_PART#}-{MATERIAL}-{COLOR}
Example: 3001-ABS-RED (2x4 Brick, ABS Plastic, Red)
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from decimal import Decimal

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text,
    ForeignKey, Enum as SQLEnum, JSON, Index, UniqueConstraint,
    Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class PartCategory(str, Enum):
    """LEGO part categories."""
    BRICK = 'brick'
    PLATE = 'plate'
    TILE = 'tile'
    SLOPE_45 = 'slope_45'
    SLOPE_33 = 'slope_33'
    SLOPE_INVERTED = 'slope_inverted'
    WEDGE = 'wedge'
    TECHNIC = 'technic'
    SPECIAL = 'special'


class MaterialType(str, Enum):
    """Manufacturing material types."""
    PLASTIC_FDM = 'plastic_fdm'    # 3D printed plastics
    PLASTIC_SLA = 'plastic_sla'    # Resin printing
    METAL_CNC = 'metal_cnc'        # CNC machined metals


class ProcessType(str, Enum):
    """Manufacturing process types."""
    FDM = 'fdm'           # Fused Deposition Modeling (3D print)
    SLA = 'sla'           # Stereolithography (resin)
    CNC_MILL = 'cnc_mill' # CNC Milling
    LASER = 'laser'       # Laser engraving/cutting


class LegoPart(AuditedModel):
    """
    Master catalog of LEGO part shapes.

    Uses official LEGO Design IDs (e.g., 3001 for 2x4 Brick).
    This represents the shape/mold, not material or color.
    """
    __tablename__ = 'lego_parts'

    # Official LEGO part number (Design ID)
    part_number = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)

    # Category
    category = Column(SQLEnum(PartCategory), nullable=False)
    subcategory = Column(String(50))  # Additional categorization

    # Dimensions in studs/plates
    studs_length = Column(Integer, nullable=False)  # X direction
    studs_width = Column(Integer, nullable=False)   # Y direction
    height_plates = Column(Integer, nullable=False)  # Height in plate units (3 plates = 1 brick)

    # Features
    has_studs = Column(Boolean, default=True)       # Top studs
    has_holes = Column(Boolean, default=False)      # Technic holes
    hole_count = Column(Integer, default=0)
    slope_angle = Column(Float)                      # For slopes: 45, 33, etc.
    is_inverted = Column(Boolean, default=False)
    side = Column(String(10))                        # For wedges: 'left', 'right'

    # Calculated dimensions (mm)
    width_mm = Column(Float)    # studs_width * 8.0 - 0.2
    length_mm = Column(Float)   # studs_length * 8.0 - 0.2
    height_mm = Column(Float)   # height_plates * 3.2
    volume_mm3 = Column(Float)  # Estimated solid volume

    # Reference weight in ABS (grams)
    reference_weight_g = Column(Float)

    # CAD file references
    fusion_design_id = Column(String(100))
    stl_file = Column(String(500))
    step_file = Column(String(500))
    thumbnail_url = Column(String(500))

    # Availability
    is_active = Column(Boolean, default=True)

    # Relationships
    products = relationship('LegoProduct', back_populates='part')

    __table_args__ = (
        Index('ix_lego_parts_category', 'category'),
        Index('ix_lego_parts_dims', 'studs_length', 'studs_width'),
    )

    @property
    def stud_count(self) -> int:
        """Total number of studs on top surface."""
        return self.studs_length * self.studs_width if self.has_studs else 0

    def calculate_dimensions(self):
        """Calculate metric dimensions from stud counts."""
        self.width_mm = self.studs_width * 8.0 - 0.2
        self.length_mm = self.studs_length * 8.0 - 0.2
        self.height_mm = self.height_plates * 3.2
        # Approximate volume (hollow bricks ~30% material)
        self.volume_mm3 = self.width_mm * self.length_mm * self.height_mm * 0.3

    def to_dict(self) -> Dict[str, Any]:
        return {
            'part_number': self.part_number,
            'name': self.name,
            'description': self.description,
            'category': self.category.value if self.category else None,
            'subcategory': self.subcategory,
            'studs': {
                'length': self.studs_length,
                'width': self.studs_width,
                'count': self.stud_count,
            },
            'height_plates': self.height_plates,
            'dimensions_mm': {
                'width': self.width_mm,
                'length': self.length_mm,
                'height': self.height_mm,
                'volume': self.volume_mm3,
            },
            'features': {
                'has_studs': self.has_studs,
                'has_holes': self.has_holes,
                'hole_count': self.hole_count,
                'slope_angle': self.slope_angle,
            },
            'reference_weight_g': self.reference_weight_g,
            'is_active': self.is_active,
            'thumbnail_url': self.thumbnail_url,
        }


class LegoMaterial(AuditedModel):
    """
    Manufacturing materials available.

    Includes plastics (for 3D printing) and metals (for CNC).
    """
    __tablename__ = 'lego_materials'

    code = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)

    # Type
    material_type = Column(SQLEnum(MaterialType), nullable=False)
    process_type = Column(SQLEnum(ProcessType), nullable=False)

    # Machine assignment
    default_machine_id = Column(String(50))

    # Physical properties
    density_g_cm3 = Column(Float, nullable=False)  # grams per cubic centimeter

    # Cost
    cost_per_gram = Column(Numeric(10, 4))
    cost_per_kg = Column(Numeric(10, 2))

    # Process parameters
    process_params = Column(JSON, default=dict)
    # For FDM: nozzle_temp, bed_temp, print_speed
    # For CNC: spindle_speed, feed_rate, depth_of_cut

    # Availability
    is_active = Column(Boolean, default=True)

    # Relationships
    products = relationship('LegoProduct', back_populates='material')

    def calculate_weight(self, volume_mm3: float) -> float:
        """Calculate weight from volume."""
        # Convert mm³ to cm³ (divide by 1000)
        volume_cm3 = volume_mm3 / 1000
        return volume_cm3 * self.density_g_cm3

    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'material_type': self.material_type.value if self.material_type else None,
            'process_type': self.process_type.value if self.process_type else None,
            'default_machine_id': self.default_machine_id,
            'density_g_cm3': self.density_g_cm3,
            'cost_per_gram': float(self.cost_per_gram) if self.cost_per_gram else None,
            'process_params': self.process_params,
            'is_active': self.is_active,
        }


class LegoColor(AuditedModel):
    """
    Available colors for products.

    Includes standard LEGO colors and metal finishes.
    """
    __tablename__ = 'lego_colors'

    code = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)

    # Color values (for plastics)
    hex_code = Column(String(7))  # #RRGGBB
    lego_id = Column(Integer)     # Official LEGO color ID

    # Type
    is_metal_finish = Column(Boolean, default=False)
    finish_type = Column(String(30))  # raw, anodized, polished, brushed

    # Material compatibility
    compatible_materials = Column(JSON, default=list)
    # e.g., ["ABS", "PLA", "PETG"] or ["ALU"]

    # Availability
    is_active = Column(Boolean, default=True)

    # Relationships
    products = relationship('LegoProduct', back_populates='color')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'name': self.name,
            'hex_code': self.hex_code,
            'lego_id': self.lego_id,
            'is_metal_finish': self.is_metal_finish,
            'finish_type': self.finish_type,
            'compatible_materials': self.compatible_materials,
            'is_active': self.is_active,
        }


class LegoProduct(AuditedModel):
    """
    Manufactured product variant.

    Combines Part + Material + Color = SKU
    Example: 3001-ABS-RED (2x4 Brick in Red ABS)
    """
    __tablename__ = 'lego_products'

    # SKU: {part_number}-{material_code}-{color_code}
    sku = Column(String(50), unique=True, nullable=False, index=True)

    # Components
    part_number = Column(String(20), ForeignKey('lego_parts.part_number'), nullable=False)
    material_code = Column(String(10), ForeignKey('lego_materials.code'), nullable=False)
    color_code = Column(String(10), ForeignKey('lego_colors.code'), nullable=False)

    # Calculated properties
    weight_grams = Column(Float)

    # Costing
    material_cost = Column(Numeric(10, 4))
    labor_cost = Column(Numeric(10, 4))
    overhead_cost = Column(Numeric(10, 4))
    total_cost = Column(Numeric(10, 4))
    list_price = Column(Numeric(10, 2))

    # Manufacturing
    routing_id = Column(String(50))  # Reference to manufacturing routing
    lead_time_days = Column(Integer, default=1)
    min_order_qty = Column(Integer, default=1)

    # Files
    gcode_file = Column(String(500))
    cam_file = Column(String(500))

    # Link to ERP Item (for inventory tracking)
    erp_item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'))

    # Status
    is_active = Column(Boolean, default=True)

    # Relationships
    part = relationship('LegoPart', back_populates='products')
    material = relationship('LegoMaterial', back_populates='products')
    color = relationship('LegoColor', back_populates='products')
    bom_items = relationship('LegoProductBOM', back_populates='product', cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('part_number', 'material_code', 'color_code', name='uq_lego_product'),
        Index('ix_lego_products_part', 'part_number'),
        Index('ix_lego_products_material', 'material_code'),
    )

    @staticmethod
    def generate_sku(part_number: str, material_code: str, color_code: str) -> str:
        """Generate SKU from components."""
        return f"{part_number}-{material_code}-{color_code}"

    def calculate_weight(self):
        """Calculate weight based on part volume and material density."""
        if self.part and self.material and self.part.volume_mm3:
            self.weight_grams = self.material.calculate_weight(self.part.volume_mm3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'sku': self.sku,
            'part_number': self.part_number,
            'material_code': self.material_code,
            'color_code': self.color_code,
            'part_name': self.part.name if self.part else None,
            'material_name': self.material.name if self.material else None,
            'color_name': self.color.name if self.color else None,
            'weight_grams': self.weight_grams,
            'costs': {
                'material': float(self.material_cost) if self.material_cost else None,
                'labor': float(self.labor_cost) if self.labor_cost else None,
                'overhead': float(self.overhead_cost) if self.overhead_cost else None,
                'total': float(self.total_cost) if self.total_cost else None,
            },
            'list_price': float(self.list_price) if self.list_price else None,
            'routing_id': self.routing_id,
            'lead_time_days': self.lead_time_days,
            'is_active': self.is_active,
        }


class LegoProductBOM(AuditedModel):
    """
    Bill of Materials for a LEGO product.

    Lists raw materials needed to manufacture one unit.
    """
    __tablename__ = 'lego_product_bom'

    product_sku = Column(String(50), ForeignKey('lego_products.sku'), nullable=False)

    # Material reference
    material_sku = Column(String(100), nullable=False)  # Raw material SKU
    material_name = Column(String(200))

    # Quantity
    quantity = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)  # grams, mm, ml, each

    # Sequence
    sequence = Column(Integer, default=10)

    notes = Column(Text)

    # Relationships
    product = relationship('LegoProduct', back_populates='bom_items')

    __table_args__ = (
        Index('ix_lego_bom_product', 'product_sku'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'product_sku': self.product_sku,
            'material_sku': self.material_sku,
            'material_name': self.material_name,
            'quantity': self.quantity,
            'unit': self.unit,
            'sequence': self.sequence,
            'notes': self.notes,
        }


class LegoRouting(AuditedModel):
    """
    Manufacturing routing template.

    Defines the sequence of operations to manufacture a product.
    """
    __tablename__ = 'lego_routings'

    routing_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Process type this routing is for
    process_type = Column(SQLEnum(ProcessType), nullable=False)

    # Estimated total time (minutes)
    estimated_time_min = Column(Integer)

    # Status
    is_active = Column(Boolean, default=True)
    revision = Column(String(20), default='1.0')

    # Relationships
    operations = relationship('LegoRoutingOperation', back_populates='routing',
                            cascade='all, delete-orphan', order_by='LegoRoutingOperation.sequence')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'routing_id': self.routing_id,
            'name': self.name,
            'description': self.description,
            'process_type': self.process_type.value if self.process_type else None,
            'estimated_time_min': self.estimated_time_min,
            'is_active': self.is_active,
            'revision': self.revision,
            'operations': [op.to_dict() for op in self.operations] if self.operations else [],
        }


class LegoRoutingOperation(AuditedModel):
    """
    Operation step in a routing.

    Defines what happens at each step of manufacturing.
    """
    __tablename__ = 'lego_routing_operations'

    routing_id = Column(String(50), ForeignKey('lego_routings.routing_id'), nullable=False)

    # Sequence (10, 20, 30...)
    sequence = Column(Integer, nullable=False)

    # Operation details
    name = Column(String(200), nullable=False)
    description = Column(Text)
    operation_type = Column(String(50))  # setup, machining, manual, qc, package

    # Work center / Machine
    work_center_id = Column(String(50))
    machine_id = Column(String(50))
    eligible_machines = Column(JSON, default=list)  # List of machine_ids that can perform this operation

    # Time estimates (minutes)
    setup_time_min = Column(Integer, default=0)
    run_time_min = Column(Integer, default=0)

    # Instructions
    instructions = Column(Text)
    gcode_template = Column(String(500))

    # Relationships
    routing = relationship('LegoRouting', back_populates='operations')

    __table_args__ = (
        UniqueConstraint('routing_id', 'sequence', name='uq_lego_routing_op'),
        Index('ix_lego_routing_ops_routing', 'routing_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'routing_id': self.routing_id,
            'sequence': self.sequence,
            'name': self.name,
            'description': self.description,
            'operation_type': self.operation_type,
            'work_center_id': self.work_center_id,
            'machine_id': self.machine_id,
            'eligible_machines': self.eligible_machines or [],
            'setup_time_min': self.setup_time_min,
            'run_time_min': self.run_time_min,
            'instructions': self.instructions,
        }
