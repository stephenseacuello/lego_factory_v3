"""
LEGO Factory v3 - LEGO Brick Design Models
===========================================
Models for custom brick designs and export jobs.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text,
    ForeignKey, Enum as SQLEnum, JSON, Index, LargeBinary
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel, VersionedModel


class BrickType(str, Enum):
    """Types of LEGO bricks."""
    STANDARD = 'standard'
    PLATE = 'plate'
    TILE = 'tile'
    SLOPE = 'slope'
    TECHNIC = 'technic'
    DUPLO = 'duplo'
    CUSTOM = 'custom'


class ExportFormat(str, Enum):
    """Export file formats."""
    STL = 'stl'
    STEP = 'step'
    OBJ = 'obj'
    THREEMF = '3mf'
    GCODE = 'gcode'


class ExportStatus(str, Enum):
    """Export job status."""
    PENDING = 'pending'
    PROCESSING = 'processing'
    SLICING = 'slicing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class PrinterType(str, Enum):
    """3D printer types for slicing."""
    PRUSA_MK4 = 'prusa_mk4'
    PRUSA_MINI = 'prusa_mini'
    BAMBU_X1 = 'bambu_x1'
    BAMBU_P1 = 'bambu_p1'
    ENDER3 = 'ender3'
    GENERIC_FDM = 'generic_fdm'
    GENERIC_SLA = 'generic_sla'


class BrickDesign(VersionedModel):
    """
    Custom LEGO brick design.

    Stores the design parameters and generated geometry
    for custom brick designs.
    """
    __tablename__ = 'brick_designs'

    # Identification
    design_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Brick specifications
    brick_type = Column(SQLEnum(BrickType), default=BrickType.STANDARD, nullable=False)
    studs_x = Column(Integer, nullable=False)  # Number of studs in X direction
    studs_y = Column(Integer, nullable=False)  # Number of studs in Y direction
    height_units = Column(Integer, default=1)  # Height in plate units (3 plates = 1 brick)

    # Color
    color_name = Column(String(50))
    color_hex = Column(String(7))  # #RRGGBB
    color_ldraw = Column(Integer)  # LDraw color code

    # Dimensions (calculated, in mm)
    width_mm = Column(Float)
    depth_mm = Column(Float)
    height_mm = Column(Float)
    volume_mm3 = Column(Float)
    weight_grams = Column(Float)

    # Design parameters
    wall_thickness = Column(Float, default=1.5)  # mm
    stud_height = Column(Float, default=1.8)  # mm
    stud_diameter = Column(Float, default=4.8)  # mm
    anti_stud_diameter = Column(Float, default=3.2)  # mm
    has_bottom_tubes = Column(Boolean, default=True)
    has_studs = Column(Boolean, default=True)
    is_hollow = Column(Boolean, default=True)

    # Custom modifications
    custom_parameters = Column(JSON, default=dict)  # Additional parameters

    # Geometry (stored binary)
    stl_data = Column(LargeBinary)  # STL file content
    step_data = Column(LargeBinary)  # STEP file content
    thumbnail = Column(LargeBinary)  # PNG thumbnail

    # Validation
    is_valid = Column(Boolean, default=False)
    validation_errors = Column(JSON)

    # Usage tracking
    times_exported = Column(Integer, default=0)
    times_printed = Column(Integer, default=0)
    total_print_time_mins = Column(Float, default=0)

    # Source
    source = Column(String(50))  # 'catalog', 'custom', 'fusion360', 'imported'
    source_file = Column(String(500))

    # Public/private
    is_public = Column(Boolean, default=False)
    owner_id = Column(String(50), index=True)

    # Relationships
    export_jobs = relationship('BrickExportJob', back_populates='design')

    __table_args__ = (
        Index('ix_brick_designs_type', 'brick_type'),
        Index('ix_brick_designs_studs', 'studs_x', 'studs_y'),
        Index('ix_brick_designs_owner', 'owner_id', 'is_public'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'design_id': self.design_id,
            'name': self.name,
            'description': self.description,
            'brick_type': self.brick_type.value if self.brick_type else None,
            'studs_x': self.studs_x,
            'studs_y': self.studs_y,
            'height_units': self.height_units,
            'dimensions': {
                'width_mm': self.width_mm,
                'depth_mm': self.depth_mm,
                'height_mm': self.height_mm,
                'volume_mm3': self.volume_mm3,
                'weight_grams': self.weight_grams,
            },
            'color': {
                'name': self.color_name,
                'hex': self.color_hex,
                'ldraw': self.color_ldraw,
            },
            'is_valid': self.is_valid,
            'is_public': self.is_public,
            'times_exported': self.times_exported,
            'times_printed': self.times_printed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class BrickExportJob(AuditedModel):
    """
    Export job for brick designs.

    Tracks the export/slicing process for a brick design.
    """
    __tablename__ = 'brick_export_jobs'

    # Identification
    job_id = Column(String(50), unique=True, nullable=False, index=True)

    # Reference to design
    design_id = Column(UUID(as_uuid=True), ForeignKey('brick_designs.id'), nullable=False)

    # Export settings
    export_format = Column(SQLEnum(ExportFormat), nullable=False)
    printer_type = Column(SQLEnum(PrinterType))

    # Slicing parameters
    layer_height = Column(Float)  # mm
    infill_percent = Column(Integer)  # 0-100
    supports_enabled = Column(Boolean, default=False)
    print_speed = Column(Float)  # mm/s
    nozzle_diameter = Column(Float, default=0.4)  # mm
    filament_type = Column(String(50))  # PLA, ABS, PETG, etc.
    filament_color = Column(String(50))

    # Custom slicing parameters
    slicer_config = Column(JSON, default=dict)

    # Status
    status = Column(SQLEnum(ExportStatus), default=ExportStatus.PENDING)
    progress = Column(Float, default=0)  # 0-100
    error_message = Column(Text)

    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Output
    output_file = Column(String(500))  # Path to output file
    output_size_bytes = Column(Integer)
    gcode_file = Column(String(500))  # Path to G-code if sliced

    # Print estimates (from slicer)
    estimated_print_time_mins = Column(Float)
    estimated_filament_grams = Column(Float)
    estimated_filament_meters = Column(Float)

    # Relationships
    design = relationship('BrickDesign', back_populates='export_jobs')

    __table_args__ = (
        Index('ix_export_jobs_status', 'status'),
        Index('ix_export_jobs_design', 'design_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'job_id': self.job_id,
            'design_id': str(self.design_id),
            'export_format': self.export_format.value if self.export_format else None,
            'printer_type': self.printer_type.value if self.printer_type else None,
            'status': self.status.value if self.status else None,
            'progress': self.progress,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'output_file': self.output_file,
            'print_estimates': {
                'time_mins': self.estimated_print_time_mins,
                'filament_grams': self.estimated_filament_grams,
                'filament_meters': self.estimated_filament_meters,
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class BrickColor(BaseModel):
    """
    Standard LEGO colors.

    Reference table of official LEGO colors.
    """
    __tablename__ = 'brick_colors'

    # Color identification
    color_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)

    # Color values
    hex_code = Column(String(7), nullable=False)  # #RRGGBB
    rgb_r = Column(Integer)
    rgb_g = Column(Integer)
    rgb_b = Column(Integer)

    # LDraw compatibility
    ldraw_id = Column(Integer)
    ldraw_name = Column(String(100))

    # BrickLink compatibility
    bricklink_id = Column(Integer)
    bricklink_name = Column(String(100))

    # Rebrickable compatibility
    rebrickable_id = Column(Integer)

    # Color properties
    is_transparent = Column(Boolean, default=False)
    is_metallic = Column(Boolean, default=False)
    is_pearl = Column(Boolean, default=False)

    # Availability
    is_current = Column(Boolean, default=True)  # Still in production
    year_from = Column(Integer)
    year_to = Column(Integer)

    __table_args__ = (
        Index('ix_brick_colors_name', 'name'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'color_id': self.color_id,
            'name': self.name,
            'hex': self.hex_code,
            'rgb': {'r': self.rgb_r, 'g': self.rgb_g, 'b': self.rgb_b},
            'ldraw_id': self.ldraw_id,
            'bricklink_id': self.bricklink_id,
            'is_transparent': self.is_transparent,
            'is_current': self.is_current,
        }
