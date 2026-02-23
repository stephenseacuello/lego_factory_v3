"""
LEGO Factory v3 - ERP Inventory Models
=======================================
Inventory locations, transactions, and lot tracking.
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


class LocationType(str, Enum):
    """Inventory location type."""
    WAREHOUSE = 'warehouse'
    PRODUCTION = 'production'
    STAGING = 'staging'
    SHIPPING = 'shipping'
    RECEIVING = 'receiving'
    QUALITY = 'quality'
    SCRAP = 'scrap'
    TRANSIT = 'transit'
    VIRTUAL = 'virtual'


class TransactionType(str, Enum):
    """Inventory transaction type."""
    RECEIPT = 'receipt'
    ISSUE = 'issue'
    TRANSFER = 'transfer'
    ADJUSTMENT = 'adjustment'
    SCRAP = 'scrap'
    PRODUCTION_ISSUE = 'production_issue'
    PRODUCTION_RECEIPT = 'production_receipt'
    RETURN = 'return'
    CYCLE_COUNT = 'cycle_count'
    PHYSICAL_COUNT = 'physical_count'


class LotStatus(str, Enum):
    """Lot/batch status."""
    AVAILABLE = 'available'
    QUARANTINE = 'quarantine'
    HOLD = 'hold'
    REJECTED = 'rejected'
    EXPIRED = 'expired'


class Location(AuditedModel):
    """Inventory storage location."""

    __tablename__ = 'locations'

    location_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Hierarchy
    parent_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))
    location_type = Column(SQLEnum(LocationType), default=LocationType.WAREHOUSE)

    # Physical address (for warehouses)
    address_line1 = Column(String(200))
    address_line2 = Column(String(200))
    city = Column(String(100))
    state = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(100))

    # Capacity
    capacity = Column(Float)
    capacity_uom = Column(String(20))

    # Status
    is_active = Column(Boolean, default=True)
    allows_negative = Column(Boolean, default=False)

    # Costing
    costing_enabled = Column(Boolean, default=True)

    # Relationships
    parent = relationship('Location', remote_side='Location.id', backref='children')
    bins = relationship('Bin', back_populates='location', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'location_id': self.location_id,
            'name': self.name,
            'location_type': self.location_type.value if self.location_type else None,
            'is_active': self.is_active,
        }


class Bin(AuditedModel):
    """Storage bin within a location."""

    __tablename__ = 'bins'

    bin_id = Column(String(50), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=False)
    name = Column(String(100))

    # Position
    aisle = Column(String(20))
    rack = Column(String(20))
    level = Column(String(20))
    position = Column(String(20))

    # Capacity
    capacity = Column(Float)
    capacity_uom = Column(String(20))

    is_active = Column(Boolean, default=True)

    # Relationships
    location = relationship('Location', back_populates='bins')

    __table_args__ = (
        UniqueConstraint('location_id', 'bin_id', name='uq_bin_location'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'bin_id': self.bin_id,
            'location_id': str(self.location_id),
            'aisle': self.aisle,
            'rack': self.rack,
            'level': self.level,
        }


class Lot(AuditedModel):
    """Lot/batch tracking."""

    __tablename__ = 'lots'

    lot_number = Column(String(50), nullable=False, index=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)

    status = Column(SQLEnum(LotStatus), default=LotStatus.AVAILABLE)

    # Dates
    manufacture_date = Column(Date)
    expiration_date = Column(Date)
    receipt_date = Column(Date)

    # Supplier
    vendor_id = Column(UUID(as_uuid=True))
    vendor_lot = Column(String(50))

    # Quality
    inspection_status = Column(String(50))
    inspection_date = Column(DateTime)
    certificate_of_analysis = Column(String(200))

    # Attributes
    attributes = Column(JSON, default=dict)

    # Relationships
    item = relationship('Item')

    __table_args__ = (
        UniqueConstraint('lot_number', 'item_id', name='uq_lot_item'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'lot_number': self.lot_number,
            'item_id': str(self.item_id),
            'status': self.status.value if self.status else None,
            'manufacture_date': self.manufacture_date.isoformat() if self.manufacture_date else None,
            'expiration_date': self.expiration_date.isoformat() if self.expiration_date else None,
        }


class SerialNumber(AuditedModel):
    """Serial number tracking."""

    __tablename__ = 'serial_numbers'

    serial_number = Column(String(100), nullable=False, index=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)
    lot_id = Column(UUID(as_uuid=True), ForeignKey('lots.id'))

    # Current location
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))
    bin_id = Column(UUID(as_uuid=True), ForeignKey('bins.id'))

    # Status
    status = Column(String(50), default='available')  # available, sold, scrapped, returned

    # Dates
    receipt_date = Column(Date)
    ship_date = Column(Date)

    # Customer (if sold)
    customer_id = Column(UUID(as_uuid=True))

    # Warranty
    warranty_start = Column(Date)
    warranty_end = Column(Date)

    # Relationships
    item = relationship('Item')
    lot = relationship('Lot')
    location = relationship('Location')

    __table_args__ = (
        UniqueConstraint('serial_number', 'item_id', name='uq_serial_item'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'serial_number': self.serial_number,
            'item_id': str(self.item_id),
            'status': self.status,
        }


class InventoryBalance(AuditedModel):
    """Current inventory balance by location/lot."""

    __tablename__ = 'inventory_balances'

    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=False)
    bin_id = Column(UUID(as_uuid=True), ForeignKey('bins.id'))
    lot_id = Column(UUID(as_uuid=True), ForeignKey('lots.id'))

    # Quantities
    quantity_on_hand = Column(Float, default=0)
    quantity_allocated = Column(Float, default=0)
    quantity_available = Column(Float, default=0)  # on_hand - allocated
    quantity_on_order = Column(Float, default=0)

    # Valuation
    unit_cost = Column(Float, default=0)
    total_value = Column(Float, default=0)

    # Last activity
    last_receipt_date = Column(DateTime)
    last_issue_date = Column(DateTime)
    last_count_date = Column(DateTime)

    # Relationships
    item = relationship('Item')
    location = relationship('Location')
    lot = relationship('Lot')

    __table_args__ = (
        Index('ix_inv_balance_item', 'item_id'),
        Index('ix_inv_balance_location', 'location_id'),
        UniqueConstraint('item_id', 'location_id', 'bin_id', 'lot_id', name='uq_inv_balance'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'item_id': str(self.item_id),
            'item_name': self.item.name if self.item else None,
            'item_number': self.item.item_id if self.item else None,
            'location_id': str(self.location_id),
            'location_name': self.location.name if self.location else None,
            'lot_id': str(self.lot_id) if self.lot_id else None,
            'quantity_on_hand': self.quantity_on_hand,
            'quantity_available': self.quantity_available,
            'quantity_allocated': self.quantity_allocated,
            'quantity_on_order': self.quantity_on_order,
            'unit_cost': self.unit_cost,
            'total_value': self.total_value,
        }


class InventoryTransaction(AuditedModel):
    """Inventory transaction history."""

    __tablename__ = 'inventory_transactions'

    transaction_id = Column(String(50), unique=True, nullable=False, index=True)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    transaction_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Item
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)
    lot_id = Column(UUID(as_uuid=True), ForeignKey('lots.id'))
    serial_number_id = Column(UUID(as_uuid=True), ForeignKey('serial_numbers.id'))

    # Locations
    from_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))
    to_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))
    from_bin_id = Column(UUID(as_uuid=True), ForeignKey('bins.id'))
    to_bin_id = Column(UUID(as_uuid=True), ForeignKey('bins.id'))

    # Quantity
    quantity = Column(Float, nullable=False)
    uom = Column(String(20))

    # Cost
    unit_cost = Column(Float)
    total_cost = Column(Float)

    # Reference documents
    reference_type = Column(String(50))  # 'purchase_order', 'sales_order', 'work_order', etc.
    reference_id = Column(String(50))
    reference_line = Column(Integer)

    # Reason
    reason_code = Column(String(50))
    notes = Column(Text)

    # Posted to GL
    gl_posted = Column(Boolean, default=False)
    gl_journal_id = Column(String(50))

    # Relationships
    item = relationship('Item')
    lot = relationship('Lot')
    from_location = relationship('Location', foreign_keys=[from_location_id])
    to_location = relationship('Location', foreign_keys=[to_location_id])

    __table_args__ = (
        Index('ix_inv_trans_item', 'item_id'),
        Index('ix_inv_trans_date', 'transaction_date'),
        Index('ix_inv_trans_type', 'transaction_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'transaction_id': self.transaction_id,
            'transaction_type': self.transaction_type.value if self.transaction_type else None,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'item_id': str(self.item_id),
            'quantity': self.quantity,
            'unit_cost': self.unit_cost,
            'reference_type': self.reference_type,
            'reference_id': self.reference_id,
        }
