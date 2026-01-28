"""
LEGO Factory v3 - ERP Purchasing Models
========================================
Purchase orders, requisitions, and receiving.
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


class RequisitionStatus(str, Enum):
    """Purchase requisition status."""
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    CONVERTED = 'converted'
    CANCELLED = 'cancelled'


class PurchaseOrderStatus(str, Enum):
    """Purchase order status."""
    DRAFT = 'draft'
    PENDING_APPROVAL = 'pending_approval'
    APPROVED = 'approved'
    SENT = 'sent'
    ACKNOWLEDGED = 'acknowledged'
    PARTIALLY_RECEIVED = 'partially_received'
    RECEIVED = 'received'
    INVOICED = 'invoiced'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class ReceiptStatus(str, Enum):
    """Receipt status."""
    PENDING = 'pending'
    IN_INSPECTION = 'in_inspection'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    PARTIAL_ACCEPT = 'partial_accept'


class PurchaseRequisition(AuditedModel):
    """Purchase requisition (internal request to purchase)."""

    __tablename__ = 'purchase_requisitions'

    requisition_number = Column(String(50), unique=True, nullable=False, index=True)

    # Status
    status = Column(SQLEnum(RequisitionStatus), default=RequisitionStatus.DRAFT)

    # Requester
    requested_by = Column(String(50), nullable=False)
    department = Column(String(100))

    # Dates
    request_date = Column(Date, default=date.today)
    required_date = Column(Date)

    # Suggested vendor
    suggested_vendor_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'))

    # Total
    estimated_total = Column(Float, default=0)

    # Approval
    approved_by = Column(String(50))
    approved_date = Column(DateTime)
    rejection_reason = Column(Text)

    notes = Column(Text)

    # Relationships
    suggested_vendor = relationship('Partner')
    lines = relationship('PurchaseRequisitionLine', back_populates='requisition', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'requisition_number': self.requisition_number,
            'status': self.status.value if self.status else None,
            'requested_by': self.requested_by,
            'request_date': self.request_date.isoformat() if self.request_date else None,
            'required_date': self.required_date.isoformat() if self.required_date else None,
            'estimated_total': self.estimated_total,
        }


class PurchaseRequisitionLine(AuditedModel):
    """Purchase requisition line item."""

    __tablename__ = 'purchase_requisition_lines'

    requisition_id = Column(UUID(as_uuid=True), ForeignKey('purchase_requisitions.id'), nullable=False)
    line_number = Column(Integer, nullable=False)

    # Item
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)
    description = Column(String(500))

    # Quantity
    quantity = Column(Float, nullable=False)
    uom = Column(String(20))

    # Estimated cost
    estimated_unit_cost = Column(Float)
    estimated_total = Column(Float)

    # Delivery
    required_date = Column(Date)
    delivery_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))

    # Reference
    reference_type = Column(String(50))  # 'work_order', 'project', etc.
    reference_id = Column(String(50))

    notes = Column(Text)

    # Relationships
    requisition = relationship('PurchaseRequisition', back_populates='lines')
    item = relationship('Item')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'requisition_id': str(self.requisition_id),
            'line_number': self.line_number,
            'item_id': str(self.item_id),
            'quantity': self.quantity,
            'estimated_unit_cost': self.estimated_unit_cost,
        }


class PurchaseOrder(AuditedModel):
    """Purchase order."""

    __tablename__ = 'purchase_orders'

    po_number = Column(String(50), unique=True, nullable=False, index=True)

    # Vendor
    vendor_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'), nullable=False)
    vendor_contact_id = Column(UUID(as_uuid=True), ForeignKey('contacts.id'))

    # Status
    status = Column(SQLEnum(PurchaseOrderStatus), default=PurchaseOrderStatus.DRAFT)

    # Source
    requisition_id = Column(UUID(as_uuid=True), ForeignKey('purchase_requisitions.id'))

    # Dates
    order_date = Column(Date, default=date.today)
    required_date = Column(Date)
    promised_date = Column(Date)

    # Pricing
    currency = Column(String(3), default='USD')
    exchange_rate = Column(Float, default=1.0)

    # Totals
    subtotal = Column(Float, default=0)
    discount_amount = Column(Float, default=0)
    tax_amount = Column(Float, default=0)
    freight_amount = Column(Float, default=0)
    total = Column(Float, default=0)

    # Shipping
    ship_to_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))
    shipping_method = Column(String(100))
    shipping_terms = Column(String(100))  # FOB, CIF, etc.

    # Payment
    payment_terms = Column(String(50))

    # References
    vendor_quote = Column(String(100))
    buyer_id = Column(String(50))

    # Fulfillment tracking
    quantity_received = Column(Float, default=0)
    quantity_invoiced = Column(Float, default=0)

    notes = Column(Text)
    vendor_notes = Column(Text)

    # Approval
    requires_approval = Column(Boolean, default=False)
    approval_limit = Column(Float)
    approved_by = Column(String(50))
    approved_date = Column(DateTime)

    # Acknowledgment
    acknowledged_date = Column(DateTime)

    # Relationships
    vendor = relationship('Partner')
    requisition = relationship('PurchaseRequisition')
    ship_to_location = relationship('Location')
    lines = relationship('PurchaseOrderLine', back_populates='order', cascade='all, delete-orphan')
    receipts = relationship('Receipt', back_populates='purchase_order')

    __table_args__ = (
        Index('ix_po_vendor', 'vendor_id'),
        Index('ix_po_status', 'status'),
        Index('ix_po_date', 'order_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'po_number': self.po_number,
            'vendor_id': str(self.vendor_id),
            'status': self.status.value if self.status else None,
            'order_date': self.order_date.isoformat() if self.order_date else None,
            'required_date': self.required_date.isoformat() if self.required_date else None,
            'subtotal': self.subtotal,
            'total': self.total,
            'quantity_received': self.quantity_received,
        }


class PurchaseOrderLine(AuditedModel):
    """Purchase order line item."""

    __tablename__ = 'purchase_order_lines'

    order_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'), nullable=False)
    line_number = Column(Integer, nullable=False)

    # Item
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)
    vendor_part_number = Column(String(100))
    description = Column(String(500))

    # Quantity and pricing
    quantity_ordered = Column(Float, nullable=False)
    quantity_received = Column(Float, default=0)
    quantity_invoiced = Column(Float, default=0)
    quantity_rejected = Column(Float, default=0)
    uom = Column(String(20))
    unit_price = Column(Float, nullable=False)
    discount_percent = Column(Float, default=0)
    line_total = Column(Float, default=0)

    # Tax
    tax_code = Column(String(50))
    tax_amount = Column(Float, default=0)

    # Delivery
    required_date = Column(Date)
    promised_date = Column(Date)
    delivery_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))

    # Source
    requisition_line_id = Column(UUID(as_uuid=True), ForeignKey('purchase_requisition_lines.id'))

    # Reference (what this is for)
    reference_type = Column(String(50))
    reference_id = Column(String(50))

    notes = Column(Text)

    # Relationships
    order = relationship('PurchaseOrder', back_populates='lines')
    item = relationship('Item')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'order_id': str(self.order_id),
            'line_number': self.line_number,
            'item_id': str(self.item_id),
            'quantity_ordered': self.quantity_ordered,
            'quantity_received': self.quantity_received,
            'unit_price': self.unit_price,
            'line_total': self.line_total,
        }


class Receipt(AuditedModel):
    """Purchase receipt (goods received)."""

    __tablename__ = 'receipts'

    receipt_number = Column(String(50), unique=True, nullable=False, index=True)

    # Purchase order
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey('purchase_orders.id'), nullable=False)

    # Status
    status = Column(SQLEnum(ReceiptStatus), default=ReceiptStatus.PENDING)

    # Dates
    receipt_date = Column(Date, default=date.today)

    # Shipping
    carrier = Column(String(100))
    tracking_number = Column(String(200))
    packing_slip = Column(String(100))

    # Receiving location
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))

    # Quality
    inspection_required = Column(Boolean, default=False)
    inspected_by = Column(String(50))
    inspection_date = Column(DateTime)

    notes = Column(Text)

    # Relationships
    purchase_order = relationship('PurchaseOrder', back_populates='receipts')
    location = relationship('Location')
    lines = relationship('ReceiptLine', back_populates='receipt', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'receipt_number': self.receipt_number,
            'purchase_order_id': str(self.purchase_order_id),
            'status': self.status.value if self.status else None,
            'receipt_date': self.receipt_date.isoformat() if self.receipt_date else None,
        }


class ReceiptLine(AuditedModel):
    """Receipt line item."""

    __tablename__ = 'receipt_lines'

    receipt_id = Column(UUID(as_uuid=True), ForeignKey('receipts.id'), nullable=False)
    po_line_id = Column(UUID(as_uuid=True), ForeignKey('purchase_order_lines.id'))

    # Item
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)

    # Quantities
    quantity_received = Column(Float, nullable=False)
    quantity_accepted = Column(Float, default=0)
    quantity_rejected = Column(Float, default=0)
    uom = Column(String(20))

    # Lot tracking
    lot_id = Column(UUID(as_uuid=True), ForeignKey('lots.id'))
    vendor_lot = Column(String(50))

    # Storage
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'))
    bin_id = Column(UUID(as_uuid=True), ForeignKey('bins.id'))

    # Costing
    unit_cost = Column(Float)
    total_cost = Column(Float)

    # Quality
    rejection_reason = Column(String(200))

    notes = Column(Text)

    # Relationships
    receipt = relationship('Receipt', back_populates='lines')
    item = relationship('Item')
    lot = relationship('Lot')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'receipt_id': str(self.receipt_id),
            'item_id': str(self.item_id),
            'quantity_received': self.quantity_received,
            'quantity_accepted': self.quantity_accepted,
            'quantity_rejected': self.quantity_rejected,
        }
