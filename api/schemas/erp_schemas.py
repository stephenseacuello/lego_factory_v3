"""
LEGO Factory v3 - ERP Pydantic Schemas
=======================================
Validation schemas for Enterprise Resource Planning (ERP)
operations including sales orders, purchase orders, inventory,
items, partners, and financial transactions.

These schemas ensure data integrity for business transactions
with proper validation of monetary values, quantities, dates,
and business rules.
"""

import re
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from api.schemas.common_schemas import BaseSchema, AuditMixin, PaginationParams


# ============================================================================
# Enums
# ============================================================================

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


class ReceiptStatus(str, Enum):
    """Receipt status."""
    PENDING = 'pending'
    IN_INSPECTION = 'in_inspection'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    PARTIAL_ACCEPT = 'partial_accept'


class PartnerType(str, Enum):
    """Partner/business entity type."""
    CUSTOMER = 'customer'
    VENDOR = 'vendor'
    BOTH = 'both'


class ItemType(str, Enum):
    """Item/product type."""
    RAW_MATERIAL = 'raw_material'
    COMPONENT = 'component'
    SUBASSEMBLY = 'subassembly'
    FINISHED_GOOD = 'finished_good'
    SERVICE = 'service'
    CONSUMABLE = 'consumable'


class UnitOfMeasure(str, Enum):
    """Common units of measure."""
    EACH = 'EA'
    PIECE = 'PC'
    KILOGRAM = 'KG'
    GRAM = 'G'
    METER = 'M'
    LITER = 'L'
    HOUR = 'HR'
    BOX = 'BOX'
    PALLET = 'PLT'


class PaymentTerms(str, Enum):
    """Standard payment terms."""
    NET_30 = 'net_30'
    NET_60 = 'net_60'
    NET_90 = 'net_90'
    DUE_ON_RECEIPT = 'due_on_receipt'
    PREPAID = 'prepaid'
    COD = 'cod'


# ============================================================================
# Partner (Customer/Vendor) Schemas
# ============================================================================

class PartnerCreate(BaseSchema):
    """
    Schema for creating a business partner (customer or vendor).

    Attributes:
        partner_id: Optional custom partner ID
        name: Company or individual name
        partner_type: Customer, vendor, or both
        tax_id: Tax identification number
        email: Primary contact email
        phone: Primary phone number
        website: Company website
        payment_terms: Default payment terms
        credit_limit: Credit limit for customers
        currency: Preferred currency
    """
    partner_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Partner ID (auto-generated if not provided)"
    )
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Company or individual name"
    )
    partner_type: PartnerType = Field(
        default=PartnerType.CUSTOMER,
        description="Partner type"
    )
    tax_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Tax identification number"
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Primary email"
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=30,
        description="Primary phone"
    )
    website: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Website URL"
    )
    payment_terms: Optional[PaymentTerms] = Field(
        default=PaymentTerms.NET_30,
        description="Default payment terms"
    )
    credit_limit: Optional[float] = Field(
        default=None,
        ge=0,
        description="Credit limit"
    )
    currency: str = Field(
        default="USD",
        pattern="^[A-Z]{3}$",
        description="Preferred currency (ISO 4217)"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Notes"
    )
    is_active: bool = Field(
        default=True,
        description="Active status"
    )

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number format."""
        if v is not None:
            # Remove common formatting characters
            cleaned = re.sub(r'[\s\-\(\)\.]', '', v)
            if not re.match(r'^\+?[0-9]{7,15}$', cleaned):
                raise ValueError('Invalid phone number format')
        return v


class PartnerUpdate(BaseSchema):
    """Schema for updating a partner."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    partner_type: Optional[PartnerType] = Field(default=None)
    tax_id: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = Field(default=None)
    phone: Optional[str] = Field(default=None, max_length=30)
    website: Optional[str] = Field(default=None, max_length=200)
    payment_terms: Optional[PaymentTerms] = Field(default=None)
    credit_limit: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, pattern="^[A-Z]{3}$")
    notes: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = Field(default=None)


class AddressCreate(BaseSchema):
    """
    Schema for creating an address.

    Attributes:
        address_type: billing, shipping, or both
        address_line1: Primary address line
        address_line2: Secondary address line
        city: City
        state: State/province
        postal_code: ZIP/postal code
        country: Country (ISO 3166-1 alpha-2)
        is_default: Whether this is the default address
    """
    address_type: str = Field(
        default="shipping",
        pattern="^(billing|shipping|both)$",
        description="Address type"
    )
    address_line1: str = Field(
        min_length=1,
        max_length=200,
        description="Address line 1"
    )
    address_line2: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Address line 2"
    )
    city: str = Field(
        min_length=1,
        max_length=100,
        description="City"
    )
    state: Optional[str] = Field(
        default=None,
        max_length=100,
        description="State/province"
    )
    postal_code: str = Field(
        min_length=1,
        max_length=20,
        description="Postal code"
    )
    country: str = Field(
        default="US",
        pattern="^[A-Z]{2}$",
        description="Country code (ISO 3166-1 alpha-2)"
    )
    is_default: bool = Field(
        default=False,
        description="Default address flag"
    )


# ============================================================================
# Item/Product Schemas
# ============================================================================

class ItemCreate(BaseSchema):
    """
    Schema for creating an item (product, material, etc.).

    Attributes:
        item_number: Unique item/SKU number
        name: Item name
        description: Detailed description
        item_type: Type classification
        uom: Base unit of measure
        category: Item category
        standard_cost: Standard unit cost
        list_price: List/catalog price
        weight: Unit weight
        weight_uom: Weight unit
        is_active: Active status
        is_purchasable: Can be purchased
        is_saleable: Can be sold
        is_manufactured: Is manufactured in-house
        lead_time_days: Default lead time
        min_order_qty: Minimum order quantity
        reorder_point: Inventory reorder point
        safety_stock: Safety stock level
    """
    item_number: str = Field(
        min_length=1,
        max_length=50,
        description="Item/SKU number"
    )
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Item name"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Description"
    )
    item_type: ItemType = Field(
        default=ItemType.FINISHED_GOOD,
        description="Item type"
    )
    uom: str = Field(
        default="EA",
        max_length=10,
        description="Base unit of measure"
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Category"
    )
    standard_cost: Optional[float] = Field(
        default=None,
        ge=0,
        description="Standard cost"
    )
    list_price: Optional[float] = Field(
        default=None,
        ge=0,
        description="List price"
    )
    weight: Optional[float] = Field(
        default=None,
        ge=0,
        description="Unit weight"
    )
    weight_uom: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Weight unit"
    )
    is_active: bool = Field(default=True)
    is_purchasable: bool = Field(default=True)
    is_saleable: bool = Field(default=True)
    is_manufactured: bool = Field(default=False)
    lead_time_days: Optional[int] = Field(
        default=None,
        ge=0,
        le=365,
        description="Lead time in days"
    )
    min_order_qty: Optional[float] = Field(
        default=None,
        ge=0,
        description="Minimum order quantity"
    )
    reorder_point: Optional[float] = Field(
        default=None,
        ge=0,
        description="Reorder point"
    )
    safety_stock: Optional[float] = Field(
        default=None,
        ge=0,
        description="Safety stock level"
    )

    @field_validator('item_number')
    @classmethod
    def validate_item_number(cls, v: str) -> str:
        """Validate item number format."""
        if not re.match(r'^[A-Za-z0-9_-]+$', v):
            raise ValueError(
                'Item number must contain only letters, numbers, '
                'underscores, and hyphens'
            )
        return v.upper()


class ItemUpdate(BaseSchema):
    """Schema for updating an item."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    item_type: Optional[ItemType] = Field(default=None)
    uom: Optional[str] = Field(default=None, max_length=10)
    category: Optional[str] = Field(default=None, max_length=100)
    standard_cost: Optional[float] = Field(default=None, ge=0)
    list_price: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = Field(default=None)
    lead_time_days: Optional[int] = Field(default=None, ge=0, le=365)
    reorder_point: Optional[float] = Field(default=None, ge=0)
    safety_stock: Optional[float] = Field(default=None, ge=0)


# ============================================================================
# Sales Order Schemas
# ============================================================================

class SalesOrderCreate(BaseSchema):
    """
    Schema for creating a sales order.

    Attributes:
        order_number: Optional order number (auto-generated if not provided)
        customer_id: Customer partner ID
        order_date: Order date
        requested_date: Customer requested date
        promised_date: Promised delivery date
        currency: Order currency
        payment_terms: Payment terms
        shipping_method: Shipping method
        customer_po: Customer's PO number
        salesperson_id: Salesperson ID
        notes: Order notes
        lines: Order line items
    """
    order_number: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Order number"
    )
    customer_id: str = Field(
        min_length=1,
        description="Customer ID"
    )
    order_date: Optional[date] = Field(
        default=None,
        description="Order date"
    )
    requested_date: Optional[date] = Field(
        default=None,
        description="Requested delivery date"
    )
    promised_date: Optional[date] = Field(
        default=None,
        description="Promised delivery date"
    )
    currency: str = Field(
        default="USD",
        pattern="^[A-Z]{3}$",
        description="Currency code"
    )
    payment_terms: Optional[PaymentTerms] = Field(
        default=None,
        description="Payment terms"
    )
    shipping_method: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Shipping method"
    )
    ship_to_address_id: Optional[str] = Field(
        default=None,
        description="Ship-to address ID"
    )
    bill_to_address_id: Optional[str] = Field(
        default=None,
        description="Bill-to address ID"
    )
    customer_po: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Customer PO number"
    )
    salesperson_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Salesperson ID"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Order notes"
    )
    internal_notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Internal notes"
    )
    lines: List["SalesOrderLineCreate"] = Field(
        min_length=1,
        description="Order line items"
    )


class SalesOrderLineCreate(BaseSchema):
    """
    Schema for creating a sales order line.

    Attributes:
        item_id: Item/product ID
        quantity_ordered: Quantity ordered
        unit_price: Unit selling price
        discount_percent: Line discount percentage
        requested_date: Line-level requested date
        notes: Line notes
    """
    item_id: str = Field(
        min_length=1,
        description="Item ID"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Line description"
    )
    quantity_ordered: float = Field(
        gt=0,
        le=1000000,
        description="Quantity ordered"
    )
    uom: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Unit of measure"
    )
    unit_price: float = Field(
        ge=0,
        description="Unit price"
    )
    discount_percent: float = Field(
        default=0,
        ge=0,
        le=100,
        description="Discount percentage"
    )
    tax_code: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Tax code"
    )
    requested_date: Optional[date] = Field(
        default=None,
        description="Requested date"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Line notes"
    )


class SalesOrderUpdate(BaseSchema):
    """Schema for updating a sales order."""
    requested_date: Optional[date] = Field(default=None)
    promised_date: Optional[date] = Field(default=None)
    payment_terms: Optional[PaymentTerms] = Field(default=None)
    shipping_method: Optional[str] = Field(default=None, max_length=100)
    customer_po: Optional[str] = Field(default=None, max_length=100)
    salesperson_id: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=2000)
    internal_notes: Optional[str] = Field(default=None, max_length=2000)


class SalesOrderStatusChange(BaseSchema):
    """Schema for changing sales order status."""
    status: SalesOrderStatus = Field(description="New status")
    user_id: str = Field(default="system", min_length=1, max_length=100)
    reason: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def validate_cancellation_reason(self) -> 'SalesOrderStatusChange':
        """Validate reason is provided for cancellation."""
        if self.status == SalesOrderStatus.CANCELLED and not self.reason:
            raise ValueError('Reason is required when cancelling an order')
        return self


class SalesOrderListParams(PaginationParams):
    """Query parameters for listing sales orders."""
    customer_id: Optional[str] = Field(default=None)
    status: Optional[SalesOrderStatus] = Field(default=None)
    order_date_from: Optional[date] = Field(default=None)
    order_date_to: Optional[date] = Field(default=None)
    salesperson_id: Optional[str] = Field(default=None, max_length=50)


# ============================================================================
# Purchase Order Schemas
# ============================================================================

class PurchaseOrderCreate(BaseSchema):
    """
    Schema for creating a purchase order.

    Attributes:
        po_number: Optional PO number (auto-generated if not provided)
        vendor_id: Vendor partner ID
        order_date: Order date
        required_date: Required delivery date
        currency: Order currency
        payment_terms: Payment terms
        shipping_method: Shipping method
        ship_to_location_id: Receiving location
        buyer_id: Buyer/purchaser ID
        notes: Order notes
        lines: Order line items
    """
    po_number: Optional[str] = Field(
        default=None,
        max_length=50,
        description="PO number"
    )
    vendor_id: str = Field(
        min_length=1,
        description="Vendor ID"
    )
    order_date: Optional[date] = Field(
        default=None,
        description="Order date"
    )
    required_date: Optional[date] = Field(
        default=None,
        description="Required date"
    )
    currency: str = Field(
        default="USD",
        pattern="^[A-Z]{3}$",
        description="Currency code"
    )
    payment_terms: Optional[PaymentTerms] = Field(
        default=None,
        description="Payment terms"
    )
    shipping_method: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Shipping method"
    )
    shipping_terms: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Shipping terms (FOB, CIF, etc.)"
    )
    ship_to_location_id: Optional[str] = Field(
        default=None,
        description="Receiving location ID"
    )
    vendor_quote: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Vendor quote reference"
    )
    buyer_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Buyer ID"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Order notes"
    )
    vendor_notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Notes for vendor"
    )
    lines: List["PurchaseOrderLineCreate"] = Field(
        min_length=1,
        description="Order line items"
    )


class PurchaseOrderLineCreate(BaseSchema):
    """
    Schema for creating a purchase order line.

    Attributes:
        item_id: Item to purchase
        quantity_ordered: Quantity to order
        unit_price: Unit cost
        vendor_part_number: Vendor's part number
        required_date: Line-level required date
    """
    item_id: str = Field(
        min_length=1,
        description="Item ID"
    )
    vendor_part_number: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Vendor part number"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Line description"
    )
    quantity_ordered: float = Field(
        gt=0,
        le=1000000,
        description="Quantity ordered"
    )
    uom: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Unit of measure"
    )
    unit_price: float = Field(
        ge=0,
        description="Unit price"
    )
    discount_percent: float = Field(
        default=0,
        ge=0,
        le=100,
        description="Discount percentage"
    )
    tax_code: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Tax code"
    )
    required_date: Optional[date] = Field(
        default=None,
        description="Required date"
    )
    delivery_location_id: Optional[str] = Field(
        default=None,
        description="Delivery location"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Line notes"
    )


class PurchaseOrderUpdate(BaseSchema):
    """Schema for updating a purchase order."""
    required_date: Optional[date] = Field(default=None)
    payment_terms: Optional[PaymentTerms] = Field(default=None)
    shipping_method: Optional[str] = Field(default=None, max_length=100)
    ship_to_location_id: Optional[str] = Field(default=None)
    buyer_id: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=2000)
    vendor_notes: Optional[str] = Field(default=None, max_length=2000)


class PurchaseOrderStatusChange(BaseSchema):
    """Schema for changing purchase order status."""
    status: PurchaseOrderStatus = Field(description="New status")
    user_id: str = Field(default="system", min_length=1, max_length=100)
    reason: Optional[str] = Field(default=None, max_length=500)


class PurchaseOrderListParams(PaginationParams):
    """Query parameters for listing purchase orders."""
    vendor_id: Optional[str] = Field(default=None)
    status: Optional[PurchaseOrderStatus] = Field(default=None)
    order_date_from: Optional[date] = Field(default=None)
    order_date_to: Optional[date] = Field(default=None)
    buyer_id: Optional[str] = Field(default=None, max_length=50)


# ============================================================================
# Inventory Schemas
# ============================================================================

class InventoryAdjustment(BaseSchema):
    """
    Schema for inventory adjustment.

    Attributes:
        item_id: Item to adjust
        location_id: Storage location
        quantity: Adjustment quantity (positive or negative)
        adjustment_type: Type of adjustment
        reason: Reason for adjustment
        reference: Reference document
        lot_id: Lot/batch ID if applicable
    """
    item_id: str = Field(
        min_length=1,
        description="Item ID"
    )
    location_id: str = Field(
        min_length=1,
        description="Location ID"
    )
    quantity: float = Field(
        description="Adjustment quantity (+ or -)"
    )
    adjustment_type: str = Field(
        pattern="^(count|receipt|issue|scrap|transfer|correction)$",
        description="Adjustment type"
    )
    reason: str = Field(
        min_length=1,
        max_length=500,
        description="Adjustment reason"
    )
    reference: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Reference document"
    )
    lot_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Lot/batch ID"
    )
    serial_number: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Serial number"
    )
    cost: Optional[float] = Field(
        default=None,
        ge=0,
        description="Unit cost"
    )
    user_id: str = Field(
        default="system",
        min_length=1,
        max_length=100,
        description="User making adjustment"
    )


class InventoryTransfer(BaseSchema):
    """
    Schema for inventory transfer between locations.

    Attributes:
        item_id: Item to transfer
        from_location_id: Source location
        to_location_id: Destination location
        quantity: Transfer quantity
        lot_id: Lot ID if applicable
    """
    item_id: str = Field(
        min_length=1,
        description="Item ID"
    )
    from_location_id: str = Field(
        min_length=1,
        description="Source location"
    )
    to_location_id: str = Field(
        min_length=1,
        description="Destination location"
    )
    quantity: float = Field(
        gt=0,
        description="Transfer quantity"
    )
    lot_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Lot ID"
    )
    serial_number: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Serial number"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Transfer notes"
    )
    user_id: str = Field(
        default="system",
        min_length=1,
        max_length=100
    )

    @model_validator(mode='after')
    def validate_locations(self) -> 'InventoryTransfer':
        """Validate source and destination are different."""
        if self.from_location_id == self.to_location_id:
            raise ValueError('Source and destination locations must be different')
        return self


class InventoryCountRequest(BaseSchema):
    """
    Schema for physical inventory count.

    Attributes:
        item_id: Item counted
        location_id: Location counted
        counted_quantity: Physical count
        count_date: Date of count
        counter_id: Person who counted
    """
    item_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)
    counted_quantity: float = Field(ge=0)
    lot_id: Optional[str] = Field(default=None, max_length=50)
    count_date: Optional[datetime] = Field(default=None)
    counter_id: str = Field(min_length=1, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=500)


class InventoryQueryParams(PaginationParams):
    """Query parameters for inventory queries."""
    item_id: Optional[str] = Field(default=None)
    location_id: Optional[str] = Field(default=None)
    lot_id: Optional[str] = Field(default=None, max_length=50)
    below_reorder_point: Optional[bool] = Field(default=None)
    category: Optional[str] = Field(default=None, max_length=100)


# ============================================================================
# Receipt Schemas
# ============================================================================

class ReceiptCreate(BaseSchema):
    """
    Schema for creating a goods receipt.

    Attributes:
        receipt_number: Optional receipt number
        purchase_order_id: Related PO ID
        receipt_date: Date of receipt
        carrier: Carrier name
        tracking_number: Tracking number
        packing_slip: Packing slip number
        location_id: Receiving location
        lines: Receipt lines
    """
    receipt_number: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Receipt number"
    )
    purchase_order_id: str = Field(
        min_length=1,
        description="Purchase order ID"
    )
    receipt_date: Optional[date] = Field(
        default=None,
        description="Receipt date"
    )
    carrier: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Carrier"
    )
    tracking_number: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Tracking number"
    )
    packing_slip: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Packing slip number"
    )
    location_id: Optional[str] = Field(
        default=None,
        description="Receiving location"
    )
    inspection_required: bool = Field(
        default=False,
        description="Requires inspection"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Receipt notes"
    )
    lines: List["ReceiptLineCreate"] = Field(
        min_length=1,
        description="Receipt lines"
    )


class ReceiptLineCreate(BaseSchema):
    """Schema for receipt line."""
    item_id: str = Field(min_length=1)
    po_line_id: Optional[str] = Field(default=None)
    quantity_received: float = Field(gt=0)
    quantity_accepted: Optional[float] = Field(default=None, ge=0)
    quantity_rejected: Optional[float] = Field(default=None, ge=0)
    uom: Optional[str] = Field(default=None, max_length=20)
    lot_id: Optional[str] = Field(default=None, max_length=50)
    vendor_lot: Optional[str] = Field(default=None, max_length=50)
    location_id: Optional[str] = Field(default=None)
    unit_cost: Optional[float] = Field(default=None, ge=0)
    rejection_reason: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=500)


# ============================================================================
# Shipment Schemas
# ============================================================================

class ShipmentCreate(BaseSchema):
    """
    Schema for creating an outbound shipment.

    Attributes:
        shipment_number: Optional shipment number
        sales_order_id: Related sales order
        ship_date: Ship date
        carrier: Carrier name
        service_level: Service level
        tracking_number: Tracking number
        lines: Shipment lines
    """
    shipment_number: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Shipment number"
    )
    sales_order_id: str = Field(
        min_length=1,
        description="Sales order ID"
    )
    ship_date: Optional[date] = Field(
        default=None,
        description="Ship date"
    )
    expected_delivery: Optional[date] = Field(
        default=None,
        description="Expected delivery date"
    )
    carrier: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Carrier"
    )
    service_level: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Service level"
    )
    tracking_number: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Tracking number"
    )
    total_weight: Optional[float] = Field(
        default=None,
        ge=0,
        description="Total weight"
    )
    weight_uom: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Weight UOM"
    )
    package_count: int = Field(
        default=1,
        ge=1,
        description="Number of packages"
    )
    freight_cost: Optional[float] = Field(
        default=None,
        ge=0,
        description="Freight cost"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Shipment notes"
    )
    lines: List["ShipmentLineCreate"] = Field(
        min_length=1,
        description="Shipment lines"
    )


class ShipmentLineCreate(BaseSchema):
    """Schema for shipment line."""
    item_id: str = Field(min_length=1)
    sales_order_line_id: Optional[str] = Field(default=None)
    quantity: float = Field(gt=0)
    uom: Optional[str] = Field(default=None, max_length=20)
    lot_id: Optional[str] = Field(default=None, max_length=50)
    serial_number_id: Optional[str] = Field(default=None)
    location_id: Optional[str] = Field(default=None)


class ShipmentStatusUpdate(BaseSchema):
    """Schema for updating shipment status."""
    status: ShipmentStatus = Field(description="New status")
    tracking_number: Optional[str] = Field(default=None, max_length=200)
    actual_delivery: Optional[date] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=500)


# ============================================================================
# MRP Schemas
# ============================================================================

class MRPRunRequest(BaseSchema):
    """
    Schema for requesting an MRP run.

    Attributes:
        planning_horizon_days: Days to plan ahead
        include_safety_stock: Consider safety stock
        include_firm_orders: Consider firm orders
        item_ids: Specific items to plan (all if empty)
    """
    planning_horizon_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Planning horizon in days"
    )
    include_safety_stock: bool = Field(
        default=True,
        description="Include safety stock in calculations"
    )
    include_firm_orders: bool = Field(
        default=True,
        description="Include firm/released orders"
    )
    item_ids: Optional[List[str]] = Field(
        default=None,
        max_length=1000,
        description="Specific items to plan"
    )
    regenerative: bool = Field(
        default=False,
        description="Full regenerative run vs net change"
    )


class MRPPlannedOrder(BaseSchema):
    """Schema for MRP planned order."""
    item_id: str
    quantity: float = Field(ge=0)
    due_date: date
    release_date: date
    order_type: str = Field(pattern="^(purchase|work_order|transfer)$")
    source: Optional[str] = None
    notes: Optional[str] = None


# Resolve forward references
SalesOrderCreate.model_rebuild()
PurchaseOrderCreate.model_rebuild()
ReceiptCreate.model_rebuild()
ShipmentCreate.model_rebuild()
