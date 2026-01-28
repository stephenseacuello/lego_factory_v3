"""
LEGO Factory v3 - ERP Sales Models
===================================
Sales orders, quotes, and shipments.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class SalesOrderStatus(str, Enum):
    """Sales order status."""
    DRAFT = 'draft'
    PENDING_APPROVAL = 'pending_approval'
    APPROVED = 'approved'
    RELEASED = 'released'
    PARTIALLY_SHIPPED = 'partially_shipped'
    SHIPPED = 'shipped'
    INVOICED = 'invoiced'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class QuoteStatus(str, Enum):
    """Quote status."""
    DRAFT = 'draft'
    SENT = 'sent'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    EXPIRED = 'expired'
    CONVERTED = 'converted'


class ShipmentStatus(str, Enum):
    """Shipment status."""
    PENDING = 'pending'
    PICKING = 'picking'
    PACKED = 'packed'
    SHIPPED = 'shipped'
    IN_TRANSIT = 'in_transit'
    DELIVERED = 'delivered'
    RETURNED = 'returned'


class SalesQuote(AuditedModel):
    """Sales quotation."""

    __tablename__ = 'sales_quotes'

    quote_number = Column(String(50), unique=True, nullable=False, index=True)

    # Customer
    customer_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'), nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey('contacts.id'))

    # Status
    status = Column(SQLEnum(QuoteStatus), default=QuoteStatus.DRAFT)

    # Dates
    quote_date = Column(Date, default=date.today)
    expiration_date = Column(Date)
    requested_date = Column(Date)

    # Pricing
    price_list_id = Column(UUID(as_uuid=True), ForeignKey('price_lists.id'))
    currency = Column(String(3), default='USD')
    exchange_rate = Column(Float, default=1.0)

    # Totals
    subtotal = Column(Float, default=0)
    discount_amount = Column(Float, default=0)
    tax_amount = Column(Float, default=0)
    total = Column(Float, default=0)

    # Shipping
    ship_to_address_id = Column(UUID(as_uuid=True), ForeignKey('partner_addresses.id'))
    shipping_method = Column(String(100))
    shipping_terms = Column(String(100))
    freight_amount = Column(Float, default=0)

    # Payment
    payment_terms = Column(String(50))

    # References
    customer_po = Column(String(100))
    salesperson_id = Column(String(50))

    notes = Column(Text)
    internal_notes = Column(Text)

    # Relationships
    customer = relationship('Partner')
    lines = relationship('SalesQuoteLine', back_populates='quote', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'quote_number': self.quote_number,
            'customer_id': str(self.customer_id),
            'status': self.status.value if self.status else None,
            'quote_date': self.quote_date.isoformat() if self.quote_date else None,
            'expiration_date': self.expiration_date.isoformat() if self.expiration_date else None,
            'subtotal': self.subtotal,
            'total': self.total,
        }


class SalesQuoteLine(AuditedModel):
    """Sales quote line item."""

    __tablename__ = 'sales_quote_lines'

    quote_id = Column(UUID(as_uuid=True), ForeignKey('sales_quotes.id'), nullable=False)
    line_number = Column(Integer, nullable=False)

    # Item
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)
    description = Column(String(500))

    # Quantity and pricing
    quantity = Column(Float, nullable=False)
    uom = Column(String(20))
    unit_price = Column(Float, nullable=False)
    discount_percent = Column(Float, default=0)
    line_total = Column(Float, default=0)

    # Tax
    tax_code = Column(String(50))
    tax_amount = Column(Float, default=0)

    # Delivery
    requested_date = Column(Date)

    notes = Column(Text)

    # Relationships
    quote = relationship('SalesQuote', back_populates='lines')
    item = relationship('Item')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'quote_id': str(self.quote_id),
            'line_number': self.line_number,
            'item_id': str(self.item_id),
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'line_total': self.line_total,
        }


class SalesOrder(AuditedModel):
    """Sales order."""

    __tablename__ = 'sales_orders'

    order_number = Column(String(50), unique=True, nullable=False, index=True)

    # Customer
    customer_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'), nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey('contacts.id'))

    # Status
    status = Column(SQLEnum(SalesOrderStatus), default=SalesOrderStatus.DRAFT)

    # Source
    quote_id = Column(UUID(as_uuid=True), ForeignKey('sales_quotes.id'))

    # Dates
    order_date = Column(Date, default=date.today)
    requested_date = Column(Date)
    promised_date = Column(Date)

    # Pricing
    price_list_id = Column(UUID(as_uuid=True), ForeignKey('price_lists.id'))
    currency = Column(String(3), default='USD')
    exchange_rate = Column(Float, default=1.0)

    # Totals
    subtotal = Column(Float, default=0)
    discount_amount = Column(Float, default=0)
    tax_amount = Column(Float, default=0)
    freight_amount = Column(Float, default=0)
    total = Column(Float, default=0)

    # Shipping
    ship_to_address_id = Column(UUID(as_uuid=True), ForeignKey('partner_addresses.id'))
    bill_to_address_id = Column(UUID(as_uuid=True), ForeignKey('partner_addresses.id'))
    shipping_method = Column(String(100))
    shipping_terms = Column(String(100))
    carrier = Column(String(100))

    # Payment
    payment_terms = Column(String(50))

    # References
    customer_po = Column(String(100))
    salesperson_id = Column(String(50))

    # Fulfillment tracking
    quantity_shipped = Column(Float, default=0)
    quantity_invoiced = Column(Float, default=0)

    notes = Column(Text)
    internal_notes = Column(Text)

    # Approval
    requires_approval = Column(Boolean, default=False)
    approved_by = Column(String(50))
    approved_date = Column(DateTime)

    # Relationships
    customer = relationship('Partner')
    quote = relationship('SalesQuote')
    lines = relationship('SalesOrderLine', back_populates='order', cascade='all, delete-orphan')
    shipments = relationship('Shipment', back_populates='sales_order')

    __table_args__ = (
        Index('ix_so_customer', 'customer_id'),
        Index('ix_so_status', 'status'),
        Index('ix_so_date', 'order_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'order_number': self.order_number,
            'customer_id': str(self.customer_id),
            'status': self.status.value if self.status else None,
            'order_date': self.order_date.isoformat() if self.order_date else None,
            'requested_date': self.requested_date.isoformat() if self.requested_date else None,
            'subtotal': self.subtotal,
            'total': self.total,
            'quantity_shipped': self.quantity_shipped,
        }


class SalesOrderLine(AuditedModel):
    """Sales order line item."""

    __tablename__ = 'sales_order_lines'

    order_id = Column(UUID(as_uuid=True), ForeignKey('sales_orders.id'), nullable=False)
    line_number = Column(Integer, nullable=False)

    # Item
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)
    description = Column(String(500))

    # Quantity and pricing
    quantity_ordered = Column(Float, nullable=False)
    quantity_shipped = Column(Float, default=0)
    quantity_invoiced = Column(Float, default=0)
    quantity_backordered = Column(Float, default=0)
    uom = Column(String(20))
    unit_price = Column(Float, nullable=False)
    discount_percent = Column(Float, default=0)
    line_total = Column(Float, default=0)

    # Cost
    unit_cost = Column(Float)

    # Tax
    tax_code = Column(String(50))
    tax_amount = Column(Float, default=0)

    # Delivery
    requested_date = Column(Date)
    promised_date = Column(Date)

    # Inventory allocation
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))

    # Manufacturing
    work_order_id = Column(String(50))

    notes = Column(Text)

    # Relationships
    order = relationship('SalesOrder', back_populates='lines')
    item = relationship('Item')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'order_id': str(self.order_id),
            'line_number': self.line_number,
            'item_id': str(self.item_id),
            'quantity_ordered': self.quantity_ordered,
            'quantity_shipped': self.quantity_shipped,
            'unit_price': self.unit_price,
            'line_total': self.line_total,
        }


class Shipment(AuditedModel):
    """Outbound shipment."""

    __tablename__ = 'shipments'

    shipment_number = Column(String(50), unique=True, nullable=False, index=True)

    # Sales order
    sales_order_id = Column(UUID(as_uuid=True), ForeignKey('sales_orders.id'), nullable=False)

    # Status
    status = Column(SQLEnum(ShipmentStatus), default=ShipmentStatus.PENDING)

    # Dates
    ship_date = Column(Date)
    expected_delivery = Column(Date)
    actual_delivery = Column(Date)

    # Carrier
    carrier = Column(String(100))
    service_level = Column(String(100))
    tracking_number = Column(String(200))

    # Weight/dimensions
    total_weight = Column(Float)
    weight_uom = Column(String(10))
    package_count = Column(Integer, default=1)

    # Cost
    freight_cost = Column(Float)

    # Shipping address
    ship_to_name = Column(String(200))
    ship_to_address1 = Column(String(200))
    ship_to_address2 = Column(String(200))
    ship_to_city = Column(String(100))
    ship_to_state = Column(String(100))
    ship_to_postal = Column(String(20))
    ship_to_country = Column(String(100))

    notes = Column(Text)

    # Relationships
    sales_order = relationship('SalesOrder', back_populates='shipments')
    lines = relationship('ShipmentLine', back_populates='shipment', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'shipment_number': self.shipment_number,
            'sales_order_id': str(self.sales_order_id),
            'status': self.status.value if self.status else None,
            'ship_date': self.ship_date.isoformat() if self.ship_date else None,
            'carrier': self.carrier,
            'tracking_number': self.tracking_number,
        }


class ShipmentLine(AuditedModel):
    """Shipment line item."""

    __tablename__ = 'shipment_lines'

    shipment_id = Column(UUID(as_uuid=True), ForeignKey('shipments.id'), nullable=False)
    sales_order_line_id = Column(UUID(as_uuid=True), ForeignKey('sales_order_lines.id'))

    # Item
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)
    lot_id = Column(UUID(as_uuid=True), ForeignKey('lots.id'))
    serial_number_id = Column(UUID(as_uuid=True), ForeignKey('serial_numbers.id'))

    # Quantity
    quantity = Column(Float, nullable=False)
    uom = Column(String(20))

    # From location
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))
    bin_id = Column(UUID(as_uuid=True), ForeignKey('bins.id'))

    # Relationships
    shipment = relationship('Shipment', back_populates='lines')
    item = relationship('Item')
    lot = relationship('Lot')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'shipment_id': str(self.shipment_id),
            'item_id': str(self.item_id),
            'quantity': self.quantity,
        }
