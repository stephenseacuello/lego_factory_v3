"""
Inventory Models

ISA-95 compliant inventory management models:
- Part: Part master (EBOM/MBOM source)
- BOM: Bill of Materials relationships
- InventoryLocation: Storage locations
- InventoryTransaction: Movement history
- InventoryBalance: Current stock levels
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, Date, DateTime,
    ForeignKey, UniqueConstraint, Index, Numeric
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, backref

from .base import Base, IS_SQLITE

# Use JSON for SQLite, JSONB for PostgreSQL
JSON_TYPE = Text if IS_SQLITE else JSONB


class Part(Base):
    """
    Part Master - Central repository for all LEGO brick definitions.

    Represents both Engineering BOM (EBOM) and Manufacturing BOM (MBOM) items.
    Each part has specifications, routing, and cost information.
    """
    __tablename__ = 'parts'

    part_number = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # LEGO-specific attributes
    part_type = Column(String(50), nullable=False, default='standard')
    category = Column(String(100), index=True)
    studs_x = Column(Integer)
    studs_y = Column(Integer)
    height_plates = Column(Float)  # Height in plate units (1 brick = 3 plates)

    # Physical properties
    volume_mm3 = Column(Float)
    weight_grams = Column(Float)

    # Costing
    standard_cost = Column(Numeric(10, 4), default=0)

    # Status
    is_active = Column(Boolean, default=True)

    # Extended specifications (LEGO dimensions, tolerances, etc.)
    specifications = Column(JSON_TYPE)

    # File references
    cad_file_path = Column(String(500))
    thumbnail_path = Column(String(500))

    # Relationships
    bom_as_parent = relationship(
        'BOM',
        foreign_keys='BOM.parent_part_id',
        back_populates='parent_part',
        cascade='all, delete-orphan'
    )
    bom_as_child = relationship(
        'BOM',
        foreign_keys='BOM.child_part_id',
        back_populates='child_part'
    )
    routings = relationship('Routing', back_populates='part', cascade='all, delete-orphan')
    inventory_balances = relationship('InventoryBalance', back_populates='part')

    def __repr__(self):
        return f"<Part({self.part_number}: {self.name})>"

    @classmethod
    def get_by_part_number(cls, session, part_number: str) -> Optional['Part']:
        """Find part by part number."""
        return session.query(cls).filter(cls.part_number == part_number).first()

    @classmethod
    def search(cls, session, query: str, limit: int = 50) -> List['Part']:
        """Search parts by name or part number."""
        search_term = f"%{query}%"
        return session.query(cls).filter(
            (cls.name.ilike(search_term)) | (cls.part_number.ilike(search_term))
        ).limit(limit).all()

    @classmethod
    def get_by_category(cls, session, category: str) -> List['Part']:
        """Get all parts in a category."""
        return session.query(cls).filter(cls.category == category).all()

    def get_bom_components(self, session) -> List[Dict[str, Any]]:
        """Get all BOM components for this part."""
        return [
            {
                'child_part': bom.child_part.to_dict(),
                'quantity': bom.quantity,
                'unit': bom.unit,
                'sequence': bom.sequence
            }
            for bom in self.bom_as_parent
        ]


class BOM(Base):
    """
    Bill of Materials - Parent-child relationships between parts.

    Supports multiple BOM types:
    - EBOM: Engineering BOM (as-designed)
    - MBOM: Manufacturing BOM (as-built)
    - SBOM: Service BOM (spare parts)
    """
    __tablename__ = 'bom'

    parent_part_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                            ForeignKey('parts.id', ondelete='CASCADE'), nullable=False)
    child_part_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                           ForeignKey('parts.id', ondelete='RESTRICT'), nullable=False)

    quantity = Column(Float, nullable=False, default=1)
    unit = Column(String(10), default='EA')
    bom_type = Column(String(20), default='MBOM')  # EBOM, MBOM, SBOM
    sequence = Column(Integer)
    notes = Column(Text)

    effective_date = Column(Date)
    obsolete_date = Column(Date)

    # Relationships
    parent_part = relationship('Part', foreign_keys=[parent_part_id], back_populates='bom_as_parent')
    child_part = relationship('Part', foreign_keys=[child_part_id], back_populates='bom_as_child')

    __table_args__ = (
        UniqueConstraint('parent_part_id', 'child_part_id', 'bom_type', name='uq_bom_parent_child_type'),
        Index('idx_bom_parent', 'parent_part_id'),
        Index('idx_bom_child', 'child_part_id'),
    )

    def __repr__(self):
        return f"<BOM({self.parent_part_id} -> {self.child_part_id}, qty={self.quantity})>"


class InventoryLocation(Base):
    """
    Inventory Locations - Physical storage locations.

    Hierarchical structure supporting:
    - Zones, Aisles, Racks, Shelves, Bins
    - Location types: SHELF, BIN, FLOOR, WIP, FINISHED_GOODS
    """
    __tablename__ = 'inventory_locations'

    location_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    location_type = Column(String(50), default='SHELF')

    # Hierarchical location
    parent_location_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                                ForeignKey('inventory_locations.id'))
    zone = Column(String(50))
    aisle = Column(String(50))
    rack = Column(String(50))
    shelf = Column(String(50))
    bin = Column(String(50))

    capacity = Column(Integer)
    is_active = Column(Boolean, default=True)

    # Relationships
    parent_location = relationship('InventoryLocation', remote_side='InventoryLocation.id', backref='child_locations')
    inventory_balances = relationship('InventoryBalance', back_populates='location')

    def __repr__(self):
        return f"<InventoryLocation({self.location_code}: {self.name})>"

    @classmethod
    def get_by_code(cls, session, location_code: str) -> Optional['InventoryLocation']:
        """Find location by code."""
        return session.query(cls).filter(cls.location_code == location_code).first()


class InventoryTransaction(Base):
    """
    Inventory Transactions - Movement and adjustment history.

    Transaction types:
    - RECEIPT: Material received
    - ISSUE: Material issued to production
    - TRANSFER: Movement between locations
    - ADJUSTMENT: Inventory adjustment (count, damage)
    - SCRAP: Material scrapped
    """
    __tablename__ = 'inventory_transactions'

    transaction_type = Column(String(50), nullable=False, index=True)

    part_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                     ForeignKey('parts.id'), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    uom = Column(String(10), default='EA')

    from_location_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                              ForeignKey('inventory_locations.id'))
    to_location_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                            ForeignKey('inventory_locations.id'))

    work_order_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                           ForeignKey('work_orders.id'))

    lot_number = Column(String(100))
    serial_number = Column(String(100))

    unit_cost = Column(Numeric(10, 4))
    total_cost = Column(Numeric(12, 4))

    reason_code = Column(String(50))
    reference_doc = Column(String(100))

    transacted_at = Column(DateTime, default=datetime.utcnow, index=True)
    transacted_by = Column(String(100))

    # Relationships
    part = relationship('Part')
    from_location = relationship('InventoryLocation', foreign_keys=[from_location_id])
    to_location = relationship('InventoryLocation', foreign_keys=[to_location_id])
    work_order = relationship('WorkOrder')

    def __repr__(self):
        return f"<InventoryTransaction({self.transaction_type}, {self.part_id}, qty={self.quantity})>"


class InventoryBalance(Base):
    """
    Inventory Balances - Current stock levels by part and location.

    Tracks:
    - Quantity on hand
    - Quantity allocated (reserved for work orders)
    - Quantity available (on_hand - allocated)
    - Average cost
    """
    __tablename__ = 'inventory_balances'

    part_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                     ForeignKey('parts.id'), nullable=False, index=True)
    location_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                         ForeignKey('inventory_locations.id'), nullable=False, index=True)

    quantity_on_hand = Column(Float, default=0)
    quantity_allocated = Column(Float, default=0)
    # Note: quantity_available is calculated in PostgreSQL as a generated column
    # For Python, we provide a property

    last_count_date = Column(DateTime)
    average_cost = Column(Numeric(10, 4))
    last_receipt_date = Column(DateTime)
    last_issue_date = Column(DateTime)

    # Relationships
    part = relationship('Part', back_populates='inventory_balances')
    location = relationship('InventoryLocation', back_populates='inventory_balances')

    __table_args__ = (
        UniqueConstraint('part_id', 'location_id', name='uq_inv_balance_part_location'),
    )

    @property
    def quantity_available(self) -> float:
        """Calculate available quantity."""
        return (self.quantity_on_hand or 0) - (self.quantity_allocated or 0)

    def __repr__(self):
        return f"<InventoryBalance({self.part_id} @ {self.location_id}, qty={self.quantity_on_hand})>"

    @classmethod
    def get_balance(cls, session, part_id: str, location_id: str) -> Optional['InventoryBalance']:
        """Get balance for a specific part and location."""
        return session.query(cls).filter(
            cls.part_id == part_id,
            cls.location_id == location_id
        ).first()

    @classmethod
    def get_total_on_hand(cls, session, part_id: str) -> float:
        """Get total quantity on hand across all locations."""
        from sqlalchemy import func
        result = session.query(func.sum(cls.quantity_on_hand)).filter(
            cls.part_id == part_id
        ).scalar()
        return result or 0.0
