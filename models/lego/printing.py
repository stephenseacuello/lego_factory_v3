"""
LEGO Factory v3 - 3D Printing Models
====================================
Print profiles, filament inventory, and brick templates.
"""

from datetime import datetime, date
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index, LargeBinary
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel, VersionedModel


class FilamentType(str, Enum):
    """3D printing filament types."""
    PLA = 'pla'
    ABS = 'abs'
    PETG = 'petg'
    TPU = 'tpu'
    NYLON = 'nylon'
    ASA = 'asa'
    PC = 'pc'
    RESIN_STANDARD = 'resin_standard'
    RESIN_TOUGH = 'resin_tough'
    RESIN_FLEXIBLE = 'resin_flexible'


class PrintQuality(str, Enum):
    """Print quality presets."""
    DRAFT = 'draft'
    NORMAL = 'normal'
    QUALITY = 'quality'
    ULTRA = 'ultra'


class PrintProfile(VersionedModel):
    """
    3D print profile / slicing preset.

    Stores slicing settings for different printers and use cases.
    """

    __tablename__ = 'print_profiles'

    profile_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Printer compatibility
    printer_type = Column(String(100), nullable=False, index=True)
    printer_model = Column(String(100))
    nozzle_diameter = Column(Float, default=0.4)

    # Filament settings
    filament_type = Column(SQLEnum(FilamentType), default=FilamentType.PLA)
    filament_diameter = Column(Float, default=1.75)

    # Quality preset
    quality_preset = Column(SQLEnum(PrintQuality), default=PrintQuality.NORMAL)

    # Layer settings
    layer_height = Column(Float, nullable=False)  # mm
    first_layer_height = Column(Float)
    line_width = Column(Float)

    # Speed settings (mm/s)
    print_speed = Column(Float)
    travel_speed = Column(Float)
    first_layer_speed = Column(Float)
    infill_speed = Column(Float)
    wall_speed = Column(Float)

    # Temperature settings
    nozzle_temp = Column(Integer)
    bed_temp = Column(Integer)
    chamber_temp = Column(Integer)

    # Infill
    infill_percent = Column(Integer, default=20)
    infill_pattern = Column(String(50))  # grid, gyroid, honeycomb, etc.

    # Walls
    wall_count = Column(Integer, default=3)
    top_layers = Column(Integer, default=4)
    bottom_layers = Column(Integer, default=4)

    # Support
    supports_enabled = Column(Boolean, default=False)
    support_type = Column(String(50))  # normal, tree
    support_density = Column(Integer)
    support_angle = Column(Float)

    # Retraction
    retraction_enabled = Column(Boolean, default=True)
    retraction_distance = Column(Float)
    retraction_speed = Column(Float)

    # Cooling
    cooling_enabled = Column(Boolean, default=True)
    fan_speed_min = Column(Integer)
    fan_speed_max = Column(Integer)

    # Advanced settings as JSON
    advanced_settings = Column(JSON, default=dict)

    # For LEGO bricks specifically
    is_lego_optimized = Column(Boolean, default=False)
    stud_quality_mode = Column(Boolean, default=False)
    tight_tolerance_mode = Column(Boolean, default=False)

    # Usage
    is_public = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    times_used = Column(Integer, default=0)

    __table_args__ = (
        Index('ix_print_profiles_printer', 'printer_type', 'filament_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'profile_id': self.profile_id,
            'name': self.name,
            'printer_type': self.printer_type,
            'filament_type': self.filament_type.value if self.filament_type else None,
            'quality_preset': self.quality_preset.value if self.quality_preset else None,
            'layer_height': self.layer_height,
            'infill_percent': self.infill_percent,
            'supports_enabled': self.supports_enabled,
            'is_lego_optimized': self.is_lego_optimized,
        }


class FilamentInventory(AuditedModel):
    """
    Filament spool inventory tracking.

    Tracks filament spools and their usage.
    """

    __tablename__ = 'filament_inventory'

    spool_id = Column(String(50), unique=True, nullable=False, index=True)

    # Filament properties
    filament_type = Column(SQLEnum(FilamentType), nullable=False, index=True)
    material_name = Column(String(200), nullable=False)
    brand = Column(String(100))
    color_name = Column(String(100))
    color_hex = Column(String(7))

    # Physical properties
    diameter = Column(Float, default=1.75)  # mm
    density = Column(Float)  # g/cm³

    # Spool info
    spool_weight_grams = Column(Float)  # Total weight when new
    current_weight_grams = Column(Float)  # Current weight
    length_meters = Column(Float)  # Estimated length remaining

    # Usage tracking
    total_used_grams = Column(Float, default=0)
    total_used_meters = Column(Float, default=0)
    print_count = Column(Integer, default=0)

    # Temperature recommendations
    recommended_nozzle_temp_min = Column(Integer)
    recommended_nozzle_temp_max = Column(Integer)
    recommended_bed_temp_min = Column(Integer)
    recommended_bed_temp_max = Column(Integer)

    # Storage
    location = Column(String(100))
    opened_date = Column(Date)
    expiry_date = Column(Date)

    # Drying
    requires_drying = Column(Boolean, default=False)
    last_dried_date = Column(DateTime)
    drying_temp = Column(Integer)
    drying_hours = Column(Float)

    # Cost
    purchase_cost = Column(Float)
    cost_per_gram = Column(Float)

    # Status
    is_active = Column(Boolean, default=True)
    is_empty = Column(Boolean, default=False)

    # Vendor
    vendor = Column(String(200))
    purchase_date = Column(Date)
    lot_number = Column(String(100))

    __table_args__ = (
        Index('ix_filament_inventory_type_color', 'filament_type', 'color_name'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'spool_id': self.spool_id,
            'filament_type': self.filament_type.value if self.filament_type else None,
            'material_name': self.material_name,
            'brand': self.brand,
            'color_name': self.color_name,
            'current_weight_grams': self.current_weight_grams,
            'is_active': self.is_active,
            'is_empty': self.is_empty,
        }


class BrickTemplate(BaseModel):
    """
    Standard LEGO brick template.

    Pre-defined brick configurations from the official catalog.
    """

    __tablename__ = 'brick_templates'

    # LEGO identification
    part_number = Column(String(50), unique=True, nullable=False, index=True)
    ldraw_id = Column(String(50), index=True)
    bricklink_id = Column(String(50))

    # Basic info
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(100))  # Indexed via composite index in __table_args__
    subcategory = Column(String(100))

    # Dimensions (studs)
    studs_x = Column(Integer)
    studs_y = Column(Integer)
    height_plates = Column(Integer)  # In plate units

    # Physical dimensions (mm)
    width_mm = Column(Float)
    depth_mm = Column(Float)
    height_mm = Column(Float)
    weight_grams = Column(Float)

    # Stud configuration
    stud_count = Column(Integer)
    has_bottom_tubes = Column(Boolean, default=True)
    has_side_studs = Column(Boolean, default=False)
    has_technic_holes = Column(Boolean, default=False)

    # Type
    brick_type = Column(String(50))  # brick, plate, tile, slope, technic, etc.
    is_printed = Column(Boolean, default=False)
    is_transparent = Column(Boolean, default=False)

    # Geometry data
    geometry_stl = Column(LargeBinary)
    geometry_step = Column(LargeBinary)
    thumbnail = Column(LargeBinary)
    geometry_hash = Column(String(64))

    # Printability
    is_printable = Column(Boolean, default=True)
    print_difficulty = Column(Integer)  # 1-5
    requires_supports = Column(Boolean, default=False)
    recommended_orientation = Column(String(50))
    estimated_print_time_mins = Column(Float)
    estimated_filament_grams = Column(Float)

    # Availability
    year_from = Column(Integer)
    year_to = Column(Integer)
    is_current = Column(Boolean, default=True)

    # Popularity
    popularity_rank = Column(Integer)
    times_used = Column(Integer, default=0)

    __table_args__ = (
        Index('ix_brick_templates_category', 'category', 'subcategory'),
        Index('ix_brick_templates_studs', 'studs_x', 'studs_y'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'part_number': self.part_number,
            'name': self.name,
            'category': self.category,
            'studs_x': self.studs_x,
            'studs_y': self.studs_y,
            'height_plates': self.height_plates,
            'brick_type': self.brick_type,
            'is_printable': self.is_printable,
            'is_current': self.is_current,
        }


class PrintJob(AuditedModel):
    """
    3D print job record.

    Tracks individual print jobs for statistics and history.
    """

    __tablename__ = 'print_jobs'

    job_id = Column(String(50), unique=True, nullable=False, index=True)

    # What's being printed
    export_job_id = Column(UUID(as_uuid=True), ForeignKey('brick_export_jobs.id'))
    design_id = Column(UUID(as_uuid=True), ForeignKey('brick_designs.id'))
    template_id = Column(UUID(as_uuid=True), ForeignKey('brick_templates.id'))

    # Profile used
    profile_id = Column(UUID(as_uuid=True), ForeignKey('print_profiles.id'))

    # Printer
    printer_name = Column(String(200))
    printer_type = Column(String(100))

    # Filament used
    filament_id = Column(UUID(as_uuid=True), ForeignKey('filament_inventory.id'))
    filament_type = Column(String(50))
    filament_color = Column(String(50))

    # Job timing
    queued_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    print_duration_mins = Column(Float)

    # Estimates vs actuals
    estimated_time_mins = Column(Float)
    estimated_filament_grams = Column(Float)
    actual_filament_grams = Column(Float)

    # Results
    status = Column(String(50), default='queued')  # queued, printing, completed, failed, cancelled
    success = Column(Boolean)
    quality_rating = Column(Integer)  # 1-5 stars
    failure_reason = Column(Text)

    # G-code file
    gcode_file = Column(String(500))
    gcode_size_bytes = Column(Integer)
    layer_count = Column(Integer)

    # Notes
    notes = Column(Text)

    __table_args__ = (
        Index('ix_print_jobs_status', 'status'),
        Index('ix_print_jobs_started', 'started_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'job_id': self.job_id,
            'printer_name': self.printer_name,
            'filament_type': self.filament_type,
            'filament_color': self.filament_color,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'print_duration_mins': self.print_duration_mins,
            'status': self.status,
            'success': self.success,
            'quality_rating': self.quality_rating,
        }
