"""
LEGO Factory v3 - ERP Partner Models
=====================================
Customers, vendors, and contacts.
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


class PartnerType(str, Enum):
    """Partner classification."""
    CUSTOMER = 'customer'
    VENDOR = 'vendor'
    BOTH = 'both'


class PartnerStatus(str, Enum):
    """Partner lifecycle status."""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    HOLD = 'hold'
    PROSPECT = 'prospect'


class PaymentTerms(str, Enum):
    """Standard payment terms."""
    NET_30 = 'net_30'
    NET_60 = 'net_60'
    NET_90 = 'net_90'
    DUE_ON_RECEIPT = 'due_on_receipt'
    PREPAID = 'prepaid'
    COD = 'cod'
    CUSTOM = 'custom'


class Partner(AuditedModel):
    """Business partner (customer or vendor)."""

    __tablename__ = 'partners'

    partner_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    legal_name = Column(String(200))

    # Classification
    partner_type = Column(SQLEnum(PartnerType), default=PartnerType.CUSTOMER)
    status = Column(SQLEnum(PartnerStatus), default=PartnerStatus.ACTIVE)

    # Contact info
    email = Column(String(200))
    phone = Column(String(50))
    fax = Column(String(50))
    website = Column(String(200))

    # Primary address
    address_line1 = Column(String(200))
    address_line2 = Column(String(200))
    city = Column(String(100))
    state = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(100))

    # Tax/regulatory
    tax_id = Column(String(50))
    tax_exempt = Column(Boolean, default=False)
    tax_exempt_certificate = Column(String(100))

    # Financial
    payment_terms = Column(SQLEnum(PaymentTerms), default=PaymentTerms.NET_30)
    payment_terms_days = Column(Integer)
    credit_limit = Column(Float)
    currency = Column(String(3), default='USD')

    # Customer-specific
    salesperson_id = Column(String(50))
    territory = Column(String(100))
    customer_category = Column(String(50))
    price_list_id = Column(String(50))

    # Vendor-specific
    vendor_category = Column(String(50))
    lead_time_days = Column(Integer)
    min_order_amount = Column(Float)

    # Banking
    bank_name = Column(String(200))
    bank_account = Column(String(100))
    bank_routing = Column(String(50))

    # Accounting
    ar_account = Column(String(50))  # Accounts Receivable GL account
    ap_account = Column(String(50))  # Accounts Payable GL account

    # Notes
    notes = Column(Text)

    # Custom attributes
    attributes = Column(JSON, default=dict)

    # Relationships
    contacts = relationship('Contact', back_populates='partner', cascade='all, delete-orphan')
    addresses = relationship('PartnerAddress', back_populates='partner', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_partner_type', 'partner_type'),
        Index('ix_partner_status', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'partner_id': self.partner_id,
            'name': self.name,
            'partner_type': self.partner_type.value if self.partner_type else None,
            'status': self.status.value if self.status else None,
            'email': self.email,
            'phone': self.phone,
            'website': self.website,
            'address_line1': self.address_line1,
            'city': self.city,
            'state': self.state,
            'postal_code': self.postal_code,
            'country': self.country,
            'payment_terms': self.payment_terms.value if self.payment_terms else None,
            'credit_limit': self.credit_limit,
            'lead_time_days': self.lead_time_days,
            'currency': self.currency,
        }


class Contact(AuditedModel):
    """Contact person at a partner."""

    __tablename__ = 'contacts'

    partner_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'), nullable=False)

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100))
    title = Column(String(100))
    department = Column(String(100))

    # Contact info
    email = Column(String(200))
    phone = Column(String(50))
    mobile = Column(String(50))

    # Role
    is_primary = Column(Boolean, default=False)
    is_billing_contact = Column(Boolean, default=False)
    is_shipping_contact = Column(Boolean, default=False)

    notes = Column(Text)

    # Relationships
    partner = relationship('Partner', back_populates='contacts')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'partner_id': str(self.partner_id),
            'first_name': self.first_name,
            'last_name': self.last_name,
            'title': self.title,
            'email': self.email,
            'phone': self.phone,
            'is_primary': self.is_primary,
        }


class PartnerAddress(AuditedModel):
    """Additional addresses for a partner."""

    __tablename__ = 'partner_addresses'

    partner_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'), nullable=False)

    address_type = Column(String(50))  # 'billing', 'shipping', 'remit_to'
    name = Column(String(200))

    address_line1 = Column(String(200), nullable=False)
    address_line2 = Column(String(200))
    city = Column(String(100))
    state = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(100))

    is_default = Column(Boolean, default=False)

    # Relationships
    partner = relationship('Partner', back_populates='addresses')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'partner_id': str(self.partner_id),
            'address_type': self.address_type,
            'address_line1': self.address_line1,
            'city': self.city,
            'country': self.country,
            'is_default': self.is_default,
        }


class VendorItem(AuditedModel):
    """Vendor-specific item pricing and information."""

    __tablename__ = 'vendor_items'

    vendor_id = Column(UUID(as_uuid=True), ForeignKey('partners.id'), nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)

    vendor_part_number = Column(String(100))
    vendor_description = Column(String(200))

    # Pricing
    unit_price = Column(Float)
    price_uom = Column(String(20))
    min_order_qty = Column(Float)
    price_break_qty = Column(Float)
    price_break_price = Column(Float)

    # Lead time
    lead_time_days = Column(Integer)

    # Status
    is_preferred = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=True)

    # Effectivity
    effective_from = Column(Date)
    effective_to = Column(Date)

    # Relationships
    vendor = relationship('Partner')
    item = relationship('Item')

    __table_args__ = (
        Index('ix_vendor_item', 'vendor_id', 'item_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'vendor_id': str(self.vendor_id),
            'item_id': str(self.item_id),
            'vendor_part_number': self.vendor_part_number,
            'unit_price': self.unit_price,
            'lead_time_days': self.lead_time_days,
            'is_preferred': self.is_preferred,
        }


class PriceList(AuditedModel):
    """Customer price list."""

    __tablename__ = 'price_lists'

    price_list_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    currency = Column(String(3), default='USD')
    is_active = Column(Boolean, default=True)

    # Effectivity
    effective_from = Column(Date)
    effective_to = Column(Date)

    # Relationships
    items = relationship('PriceListItem', back_populates='price_list', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'price_list_id': self.price_list_id,
            'name': self.name,
            'currency': self.currency,
            'is_active': self.is_active,
        }


class PriceListItem(AuditedModel):
    """Item pricing in a price list."""

    __tablename__ = 'price_list_items'

    price_list_id = Column(UUID(as_uuid=True), ForeignKey('price_lists.id'), nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey('items.id'), nullable=False)

    unit_price = Column(Float, nullable=False)
    min_qty = Column(Float, default=1)

    # Discount
    discount_percent = Column(Float, default=0)

    # Relationships
    price_list = relationship('PriceList', back_populates='items')
    item = relationship('Item')

    __table_args__ = (
        Index('ix_price_list_item', 'price_list_id', 'item_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'price_list_id': str(self.price_list_id),
            'item_id': str(self.item_id),
            'unit_price': self.unit_price,
            'discount_percent': self.discount_percent,
        }
