"""
LEGO Factory v3 - ERP Item Models
==================================
Item master, BOM, and item specifications.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class ItemType(str, Enum):
    """Item classification type."""
    RAW_MATERIAL = 'raw_material'
    COMPONENT = 'component'
    SUBASSEMBLY = 'subassembly'
    FINISHED_GOOD = 'finished_good'
    PRODUCT = 'product'  # LEGO products (SKUs)
    SERVICE = 'service'
    MRO = 'mro'  # Maintenance, Repair, Operations
    CONSUMABLE = 'consumable'
    TOOL = 'tool'


class ItemStatus(str, Enum):
    """Item lifecycle status."""
    ACTIVE = 'active'
    PENDING = 'pending'
    OBSOLETE = 'obsolete'
    HOLD = 'hold'


class CostingMethod(str, Enum):
    """Inventory costing method."""
    STANDARD = 'standard'
    AVERAGE = 'average'
    FIFO = 'fifo'
    LIFO = 'lifo'
    SPECIFIC = 'specific'


class UnitOfMeasure(AuditedModel):
    """Unit of measure definition."""

    __tablename__ = 'units_of_measure'

    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    uom_type = Column(String(50))  # 'weight', 'length', 'volume', 'count', etc.

    # Conversion to base unit
    base_uom_code = Column(String(20))
    conversion_factor = Column(Float, default=1.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'code': self.code,
            'name': self.name,
            'uom_type': self.uom_type,
            'conversion_factor': self.conversion_factor,
        }


class ItemCategory(AuditedModel):
    """Item category hierarchy."""

    __tablename__ = 'item_categories'

    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('item_categories.id'))

    # GL Account mappings
    inventory_account = Column(String(50))
    cogs_account = Column(String(50))
    revenue_account = Column(String(50))

    # Relationships
    parent = relationship('ItemCategory', remote_side='ItemCategory.id', backref='children')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'code': self.code,
            'name': self.name,
            'parent_id': str(self.parent_id) if self.parent_id else None,
        }


class Item(AuditedModel):
    """Item master record."""

    __tablename__ = 'items'

    item_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Classification
    item_type = Column(SQLEnum(ItemType), default=ItemType.COMPONENT)
    status = Column(SQLEnum(ItemStatus), default=ItemStatus.ACTIVE)
    category_id = Column(UUID(as_uuid=True), ForeignKey('item_categories.id'))

    # Units
    base_uom = Column(String(20), default='EA')
    purchase_uom = Column(String(20))
    purchase_conversion = Column(Float, default=1.0)
    sales_uom = Column(String(20))
    sales_conversion = Column(Float, default=1.0)

    # Identification
    barcode = Column(String(100))
    manufacturer_part = Column(String(100))
    vendor_part = Column(String(100))

    # Costing
    costing_method = Column(SQLEnum(CostingMethod), default=CostingMethod.STANDARD)
    standard_cost = Column(Float, default=0)
    average_cost = Column(Float, default=0)
    last_cost = Column(Float, default=0)

    # Pricing
    list_price = Column(Float, default=0)
    min_price = Column(Float)

    # Planning
    lead_time_days = Column(Integer, default=0)
    safety_stock = Column(Float, default=0)
    reorder_point = Column(Float, default=0)
    reorder_quantity = Column(Float, default=0)
    min_order_qty = Column(Float, default=1)
    order_multiple = Column(Float, default=1)

    # Flags
    is_purchasable = Column(Boolean, default=True)
    is_salable = Column(Boolean, default=True)
    is_manufactured = Column(Boolean, default=False)
    is_lot_controlled = Column(Boolean, default=False)
    is_serial_controlled = Column(Boolean, default=False)
    track_inventory = Column(Boolean, default=True)

    # Weight/Dimensions
    weight = Column(Float)
    weight_uom = Column(String(10))
    length = Column(Float)
    width = Column(Float)
    height = Column(Float)
    dimension_uom = Column(String(10))

    # Default locations
    default_location_id = Column(String(50))
    default_bin = Column(String(50))

    # For manufactured items
    recipe_id = Column(String(50))  # Link to SCADA recipe

    # Custom attributes
    attributes = Column(JSON, default=dict)

    # Relationships
    category = relationship('ItemCategory')
    bom_lines = relationship('BOMLine', foreign_keys='BOMLine.parent_item_id', back_populates='parent_item')

    __table_args__ = (
        Index('ix_item_type', 'item_type'),
        Index('ix_item_category', 'category_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'item_id': self.item_id,
            'name': self.name,
            'description': self.description,
            'item_type': self.item_type.value if self.item_type else None,
            'status': self.status.value if self.status else None,
            'category': self.category.name if self.category else None,
            'base_uom': self.base_uom,
            'standard_cost': self.standard_cost,
            'average_cost': self.average_cost,
            'list_price': self.list_price,
            'is_purchasable': self.is_purchasable,
            'is_salable': self.is_salable,
            'is_manufactured': self.is_manufactured,
            'lead_time_days': self.lead_time_days,
            'safety_stock': self.safety_stock,
            'reorder_point': self.reorder_point,
            'reorder_quantity': self.reorder_quantity,
        }


class BOMLine(AuditedModel):
    """Bill of Materials line item."""

    __tablename__ = 'bom_lines'

    parent_item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)
    component_item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)

    sequence = Column(Integer, default=10)
    quantity = Column(Float, nullable=False)
    uom = Column(String(20), default='EA')

    # Effectivity
    effective_from = Column(Date)
    effective_to = Column(Date)

    # Options
    is_optional = Column(Boolean, default=False)
    scrap_factor = Column(Float, default=0)  # Percentage

    # Operation linkage (for routing)
    operation_sequence = Column(Integer)

    notes = Column(Text)

    # Relationships
    parent_item = relationship('Item', foreign_keys=[parent_item_id], back_populates='bom_lines')
    component_item = relationship('Item', foreign_keys=[component_item_id])

    __table_args__ = (
        Index('ix_bom_parent', 'parent_item_id'),
        UniqueConstraint('parent_item_id', 'component_item_id', 'sequence', name='uq_bom_line'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'parent_item_id': str(self.parent_item_id),
            'component_item_id': str(self.component_item_id),
            'sequence': self.sequence,
            'quantity': self.quantity,
            'uom': self.uom,
            'is_optional': self.is_optional,
            'scrap_factor': self.scrap_factor,
        }


class Routing(AuditedModel):
    """Manufacturing routing for an item."""

    __tablename__ = 'routings'

    routing_id = Column(String(50), unique=True, nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Status
    is_active = Column(Boolean, default=True)
    revision = Column(String(20))

    # Effectivity
    effective_from = Column(Date)
    effective_to = Column(Date)

    # Relationships
    item = relationship('Item')
    operations = relationship('RoutingOperation', back_populates='routing', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'routing_id': self.routing_id,
            'item_id': str(self.item_id),
            'name': self.name,
            'is_active': self.is_active,
            'revision': self.revision,
        }


class RoutingOperation(AuditedModel):
    """Operation step in a routing."""

    __tablename__ = 'routing_operations'

    routing_id = Column(UUID(as_uuid=True), ForeignKey('routings.id'), nullable=False)
    sequence = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Work center
    work_center_id = Column(String(50))
    machine_id = Column(String(50))

    # Times (in minutes)
    setup_time = Column(Float, default=0)
    run_time = Column(Float, default=0)  # Per unit
    teardown_time = Column(Float, default=0)
    queue_time = Column(Float, default=0)
    move_time = Column(Float, default=0)

    # Quantity
    run_quantity = Column(Float, default=1)  # Units produced per cycle

    # Costing
    labor_rate = Column(Float)
    overhead_rate = Column(Float)

    # Control
    is_subcontracted = Column(Boolean, default=False)
    vendor_id = Column(String(50))

    # Recipe linkage
    recipe_id = Column(String(50))

    # Relationships
    routing = relationship('Routing', back_populates='operations')

    __table_args__ = (
        UniqueConstraint('routing_id', 'sequence', name='uq_routing_operation'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'routing_id': str(self.routing_id),
            'sequence': self.sequence,
            'name': self.name,
            'work_center_id': self.work_center_id,
            'setup_time': self.setup_time,
            'run_time': self.run_time,
        }
