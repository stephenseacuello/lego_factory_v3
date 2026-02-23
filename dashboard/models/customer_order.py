"""
Customer Order Model - Sales Orders and Demand Management

LegoMCP World-Class Manufacturing System v5.0
Phase 8: Customer Orders & ATP/CTP

Manages customer orders with:
- Priority classification (A/B/C)
- Delivery promises (ATP/CTP)
- Order lines with quantity and dates
- Quality and rush premiums
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class OrderStatus(str, Enum):
    """Order lifecycle status."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    IN_PRODUCTION = "in_production"
    READY_TO_SHIP = "ready_to_ship"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class OrderPriority(str, Enum):
    """Order priority classification."""
    A = "A"  # Critical - VIP customer or rush
    B = "B"  # Normal priority
    C = "C"  # Low priority - flexible delivery


class PromiseType(str, Enum):
    """Type of delivery promise."""
    ATP = "atp"  # Available-to-Promise (from inventory)
    CTP = "ctp"  # Capable-to-Promise (from production)
    CONFIRMED = "confirmed"  # Customer confirmed
    BEST_EFFORT = "best_effort"


@dataclass
class DeliveryPromise:
    """Delivery promise details."""
    promise_type: PromiseType
    promised_date: date
    confidence: float  # 0-1

    # ATP details
    available_from_inventory: int = 0
    inventory_location: Optional[str] = None

    # CTP details
    production_required: int = 0
    production_completion_date: Optional[date] = None

    # Capacity details
    capacity_available: bool = True
    bottleneck_resource: Optional[str] = None

    # Alternative promises
    alternative_date: Optional[date] = None
    partial_shipment_possible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'promise_type': self.promise_type.value,
            'promised_date': self.promised_date.isoformat(),
            'confidence': self.confidence,
            'available_from_inventory': self.available_from_inventory,
            'production_required': self.production_required,
            'production_completion_date': (
                self.production_completion_date.isoformat()
                if self.production_completion_date else None
            ),
            'capacity_available': self.capacity_available,
            'bottleneck_resource': self.bottleneck_resource,
            'alternative_date': (
                self.alternative_date.isoformat()
                if self.alternative_date else None
            ),
            'partial_shipment_possible': self.partial_shipment_possible,
        }


@dataclass
class OrderLine:
    """Individual line item in an order."""
    line_id: str
    part_id: str
    part_name: str
    quantity_ordered: int
    quantity_shipped: int = 0
    quantity_backordered: int = 0

    # Pricing
    unit_price: float = 0.0
    line_total: float = 0.0
    discount_percent: float = 0.0

    # Quality requirements
    quality_level: str = "standard"  # standard, premium, certified
    quality_premium_percent: float = 0.0

    # Rush handling
    is_rush: bool = False
    rush_premium_percent: float = 0.0

    # Dates
    requested_date: Optional[date] = None
    promised_date: Optional[date] = None
    ship_date: Optional[date] = None

    # Promise
    promise: Optional[DeliveryPromise] = None

    # Status
    status: OrderStatus = OrderStatus.DRAFT

    # Work order linkage
    work_order_id: Optional[str] = None

    def __post_init__(self):
        if not self.line_id:
            self.line_id = str(uuid4())
        self._calculate_totals()

    def _calculate_totals(self):
        """Calculate line totals with premiums."""
        base = self.unit_price * self.quantity_ordered
        discount = base * (self.discount_percent / 100)
        subtotal = base - discount

        quality_premium = subtotal * (self.quality_premium_percent / 100)
        rush_premium = subtotal * (self.rush_premium_percent / 100) if self.is_rush else 0

        self.line_total = subtotal + quality_premium + rush_premium

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'line_id': self.line_id,
            'part_id': self.part_id,
            'part_name': self.part_name,
            'quantity_ordered': self.quantity_ordered,
            'quantity_shipped': self.quantity_shipped,
            'quantity_backordered': self.quantity_backordered,
            'unit_price': self.unit_price,
            'line_total': self.line_total,
            'discount_percent': self.discount_percent,
            'quality_level': self.quality_level,
            'is_rush': self.is_rush,
            'requested_date': self.requested_date.isoformat() if self.requested_date else None,
            'promised_date': self.promised_date.isoformat() if self.promised_date else None,
            'status': self.status.value,
            'work_order_id': self.work_order_id,
            'promise': self.promise.to_dict() if self.promise else None,
        }


@dataclass
class CustomerOrder:
    """Customer sales order."""
    order_id: str
    order_number: str
    customer_id: str
    customer_name: str

    # Dates
    order_date: datetime
    requested_delivery_date: Optional[date] = None
    promised_delivery_date: Optional[date] = None
    committed_delivery_date: Optional[date] = None
    ship_date: Optional[date] = None

    # Priority
    priority_class: OrderPriority = OrderPriority.B
    priority_score: int = 50  # 1-100

    # Lines
    lines: List[OrderLine] = field(default_factory=list)

    # Status
    status: OrderStatus = OrderStatus.DRAFT

    # Pricing
    subtotal: float = 0.0
    tax_amount: float = 0.0
    shipping_amount: float = 0.0
    total_amount: float = 0.0
    target_margin_percent: float = 30.0

    # Shipping
    ship_to_address: Optional[str] = None
    shipping_method: str = "standard"

    # Notes
    notes: str = ""
    internal_notes: str = ""

    # Tracking
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None

    def __post_init__(self):
        if not self.order_id:
            self.order_id = str(uuid4())
        self._calculate_totals()

    def _calculate_totals(self):
        """Calculate order totals."""
        self.subtotal = sum(line.line_total for line in self.lines)
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_amount

    def add_line(self, line: OrderLine) -> None:
        """Add order line."""
        self.lines.append(line)
        self._calculate_totals()
        self.updated_at = datetime.utcnow()

    def remove_line(self, line_id: str) -> bool:
        """Remove order line by ID."""
        for i, line in enumerate(self.lines):
            if line.line_id == line_id:
                self.lines.pop(i)
                self._calculate_totals()
                self.updated_at = datetime.utcnow()
                return True
        return False

    def get_line(self, line_id: str) -> Optional[OrderLine]:
        """Get line by ID."""
        for line in self.lines:
            if line.line_id == line_id:
                return line
        return None

    def confirm(self) -> None:
        """Confirm the order."""
        if self.status == OrderStatus.SUBMITTED:
            self.status = OrderStatus.CONFIRMED
            self.updated_at = datetime.utcnow()

    def release(self) -> None:
        """Release order for production."""
        if self.status == OrderStatus.CONFIRMED:
            self.status = OrderStatus.RELEASED
            for line in self.lines:
                line.status = OrderStatus.RELEASED
            self.updated_at = datetime.utcnow()

    def set_promised_date(self, promised_date: date) -> None:
        """Set promised delivery date."""
        self.promised_delivery_date = promised_date
        for line in self.lines:
            line.promised_date = promised_date
        self.updated_at = datetime.utcnow()

    def is_late(self) -> bool:
        """Check if order is past due."""
        if self.promised_delivery_date and self.status not in [
            OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.CANCELLED
        ]:
            return date.today() > self.promised_delivery_date
        return False

    def days_until_due(self) -> Optional[int]:
        """Calculate days until due date."""
        if self.promised_delivery_date:
            delta = self.promised_delivery_date - date.today()
            return delta.days
        return None

    def get_total_quantity(self) -> int:
        """Get total quantity across all lines."""
        return sum(line.quantity_ordered for line in self.lines)

    def get_shipped_quantity(self) -> int:
        """Get total shipped quantity."""
        return sum(line.quantity_shipped for line in self.lines)

    def is_fully_shipped(self) -> bool:
        """Check if all items shipped."""
        return all(
            line.quantity_shipped >= line.quantity_ordered
            for line in self.lines
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'order_id': self.order_id,
            'order_number': self.order_number,
            'customer_id': self.customer_id,
            'customer_name': self.customer_name,
            'order_date': self.order_date.isoformat(),
            'requested_delivery_date': (
                self.requested_delivery_date.isoformat()
                if self.requested_delivery_date else None
            ),
            'promised_delivery_date': (
                self.promised_delivery_date.isoformat()
                if self.promised_delivery_date else None
            ),
            'priority_class': self.priority_class.value,
            'priority_score': self.priority_score,
            'status': self.status.value,
            'lines': [line.to_dict() for line in self.lines],
            'subtotal': self.subtotal,
            'tax_amount': self.tax_amount,
            'shipping_amount': self.shipping_amount,
            'total_amount': self.total_amount,
            'target_margin_percent': self.target_margin_percent,
            'is_late': self.is_late(),
            'days_until_due': self.days_until_due(),
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class CustomerOrderRepository:
    """Repository for customer order persistence."""

    def __init__(self):
        self._orders: Dict[str, CustomerOrder] = {}
        self._by_number: Dict[str, str] = {}  # order_number -> order_id
        self._by_customer: Dict[str, List[str]] = {}  # customer_id -> [order_ids]

    def save(self, order: CustomerOrder) -> None:
        """Save or update order."""
        self._orders[order.order_id] = order
        self._by_number[order.order_number] = order.order_id

        if order.customer_id not in self._by_customer:
            self._by_customer[order.customer_id] = []
        if order.order_id not in self._by_customer[order.customer_id]:
            self._by_customer[order.customer_id].append(order.order_id)

    def get(self, order_id: str) -> Optional[CustomerOrder]:
        """Get order by ID."""
        return self._orders.get(order_id)

    def get_by_number(self, order_number: str) -> Optional[CustomerOrder]:
        """Get order by order number."""
        order_id = self._by_number.get(order_number)
        return self._orders.get(order_id) if order_id else None

    def get_by_customer(self, customer_id: str) -> List[CustomerOrder]:
        """Get all orders for a customer."""
        order_ids = self._by_customer.get(customer_id, [])
        return [self._orders[oid] for oid in order_ids if oid in self._orders]

    def get_by_status(self, status: OrderStatus) -> List[CustomerOrder]:
        """Get orders by status."""
        return [o for o in self._orders.values() if o.status == status]

    def get_open_orders(self) -> List[CustomerOrder]:
        """Get all open (not shipped/delivered/cancelled) orders."""
        closed = {OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.CANCELLED}
        return [o for o in self._orders.values() if o.status not in closed]

    def get_late_orders(self) -> List[CustomerOrder]:
        """Get all late orders."""
        return [o for o in self._orders.values() if o.is_late()]

    def get_due_soon(self, days: int = 7) -> List[CustomerOrder]:
        """Get orders due within specified days."""
        cutoff = date.today() + timedelta(days=days)
        return [
            o for o in self.get_open_orders()
            if o.promised_delivery_date and o.promised_delivery_date <= cutoff
        ]

    def delete(self, order_id: str) -> bool:
        """Delete order."""
        if order_id in self._orders:
            order = self._orders.pop(order_id)
            if order.order_number in self._by_number:
                del self._by_number[order.order_number]
            if order.customer_id in self._by_customer:
                if order_id in self._by_customer[order.customer_id]:
                    self._by_customer[order.customer_id].remove(order_id)
            return True
        return False

    def count(self) -> int:
        """Get total order count."""
        return len(self._orders)
