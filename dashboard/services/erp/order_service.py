"""
Order Service - Customer Order Management

LegoMCP World-Class Manufacturing System v5.0
Phase 8: Customer Orders & ATP/CTP

Manages customer order lifecycle:
- Order creation and validation
- Status transitions
- Priority management
- Order-to-production linkage
"""

import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class OrderCreateRequest:
    """Request to create a new order."""
    customer_id: str
    customer_name: str
    requested_delivery_date: Optional[date] = None
    priority_class: str = "B"
    shipping_method: str = "standard"
    notes: str = ""


@dataclass
class OrderLineRequest:
    """Request to add a line to an order."""
    part_id: str
    part_name: str
    quantity: int
    unit_price: float = 0.0
    quality_level: str = "standard"
    is_rush: bool = False


class OrderService:
    """
    Customer Order Service.

    Handles order lifecycle management from creation to delivery.
    """

    def __init__(
        self,
        atp_service: Optional[Any] = None,
        ctp_service: Optional[Any] = None,
        inventory_service: Optional[Any] = None,
        event_bus: Optional[Any] = None,
    ):
        self.atp_service = atp_service
        self.ctp_service = ctp_service
        self.inventory_service = inventory_service
        self.event_bus = event_bus

        # In-memory storage (would be database in production)
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._order_counter = 1000

    def _generate_order_number(self) -> str:
        """Generate unique order number."""
        self._order_counter += 1
        return f"SO-{self._order_counter:06d}"

    def create_order(self, request: OrderCreateRequest) -> Dict[str, Any]:
        """
        Create a new customer order.

        Returns the created order with ID.
        """
        order_id = str(uuid4())
        order_number = self._generate_order_number()

        order = {
            'order_id': order_id,
            'order_number': order_number,
            'customer_id': request.customer_id,
            'customer_name': request.customer_name,
            'order_date': datetime.utcnow().isoformat(),
            'requested_delivery_date': (
                request.requested_delivery_date.isoformat()
                if request.requested_delivery_date else None
            ),
            'promised_delivery_date': None,
            'priority_class': request.priority_class,
            'priority_score': self._calculate_priority_score(request),
            'status': 'draft',
            'lines': [],
            'subtotal': 0.0,
            'tax_amount': 0.0,
            'shipping_amount': 0.0,
            'total_amount': 0.0,
            'shipping_method': request.shipping_method,
            'notes': request.notes,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
        }

        self._orders[order_id] = order
        logger.info(f"Created order {order_number} for customer {request.customer_name}")

        return order

    def _calculate_priority_score(self, request: OrderCreateRequest) -> int:
        """Calculate priority score based on class and timing."""
        base_scores = {'A': 90, 'B': 50, 'C': 20}
        score = base_scores.get(request.priority_class, 50)

        # Adjust for requested date urgency
        if request.requested_delivery_date:
            days_until = (request.requested_delivery_date - date.today()).days
            if days_until <= 3:
                score += 10
            elif days_until <= 7:
                score += 5

        return min(100, max(1, score))

    def add_line(
        self,
        order_id: str,
        line_request: OrderLineRequest
    ) -> Optional[Dict[str, Any]]:
        """Add a line item to an order."""
        order = self._orders.get(order_id)
        if not order:
            return None

        if order['status'] not in ['draft', 'submitted']:
            logger.warning(f"Cannot add line to order {order_id} in status {order['status']}")
            return None

        line_id = str(uuid4())

        # Calculate line totals
        base_total = line_request.unit_price * line_request.quantity
        quality_premium = 0.0
        rush_premium = 0.0

        if line_request.quality_level == 'premium':
            quality_premium = base_total * 0.15
        elif line_request.quality_level == 'certified':
            quality_premium = base_total * 0.25

        if line_request.is_rush:
            rush_premium = base_total * 0.20

        line_total = base_total + quality_premium + rush_premium

        line = {
            'line_id': line_id,
            'part_id': line_request.part_id,
            'part_name': line_request.part_name,
            'quantity_ordered': line_request.quantity,
            'quantity_shipped': 0,
            'unit_price': line_request.unit_price,
            'line_total': line_total,
            'quality_level': line_request.quality_level,
            'quality_premium': quality_premium,
            'is_rush': line_request.is_rush,
            'rush_premium': rush_premium,
            'status': 'draft',
            'promise': None,
        }

        order['lines'].append(line)
        self._recalculate_totals(order)
        order['updated_at'] = datetime.utcnow().isoformat()

        return line

    def _recalculate_totals(self, order: Dict[str, Any]) -> None:
        """Recalculate order totals."""
        order['subtotal'] = sum(line['line_total'] for line in order['lines'])
        order['tax_amount'] = order['subtotal'] * 0.08  # 8% tax
        order['total_amount'] = order['subtotal'] + order['tax_amount'] + order['shipping_amount']

    def submit_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Submit order for processing."""
        order = self._orders.get(order_id)
        if not order:
            return None

        if order['status'] != 'draft':
            return order

        if not order['lines']:
            logger.warning(f"Cannot submit empty order {order_id}")
            return None

        order['status'] = 'submitted'
        order['updated_at'] = datetime.utcnow().isoformat()

        # Get delivery promises for each line
        if self.atp_service:
            for line in order['lines']:
                promise = self.atp_service.check_availability(
                    line['part_id'],
                    line['quantity_ordered'],
                    order.get('requested_delivery_date'),
                )
                line['promise'] = promise

        logger.info(f"Order {order['order_number']} submitted")

        # Emit event
        if self.event_bus:
            self.event_bus.publish({
                'event_type': 'order_submitted',
                'order_id': order_id,
                'order_number': order['order_number'],
            })

        return order

    def confirm_order(self, order_id: str, promised_date: date) -> Optional[Dict[str, Any]]:
        """Confirm order with promised delivery date."""
        order = self._orders.get(order_id)
        if not order:
            return None

        if order['status'] != 'submitted':
            return order

        order['status'] = 'confirmed'
        order['promised_delivery_date'] = promised_date.isoformat()
        order['updated_at'] = datetime.utcnow().isoformat()

        for line in order['lines']:
            line['status'] = 'confirmed'
            line['promised_date'] = promised_date.isoformat()

        logger.info(f"Order {order['order_number']} confirmed for {promised_date}")

        return order

    def release_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Release order for production."""
        order = self._orders.get(order_id)
        if not order:
            return None

        if order['status'] != 'confirmed':
            return order

        order['status'] = 'released'
        order['updated_at'] = datetime.utcnow().isoformat()

        for line in order['lines']:
            line['status'] = 'released'

        logger.info(f"Order {order['order_number']} released for production")

        # Emit event
        if self.event_bus:
            self.event_bus.publish({
                'event_type': 'order_released',
                'order_id': order_id,
                'order_number': order['order_number'],
                'lines': len(order['lines']),
            })

        return order

    def ship_line(
        self,
        order_id: str,
        line_id: str,
        quantity: int
    ) -> Optional[Dict[str, Any]]:
        """Record shipment of order line."""
        order = self._orders.get(order_id)
        if not order:
            return None

        for line in order['lines']:
            if line['line_id'] == line_id:
                line['quantity_shipped'] += quantity
                if line['quantity_shipped'] >= line['quantity_ordered']:
                    line['status'] = 'shipped'
                    line['ship_date'] = date.today().isoformat()
                break

        # Check if entire order is shipped
        all_shipped = all(
            line['quantity_shipped'] >= line['quantity_ordered']
            for line in order['lines']
        )

        if all_shipped:
            order['status'] = 'shipped'
            order['ship_date'] = date.today().isoformat()
            logger.info(f"Order {order['order_number']} fully shipped")

        order['updated_at'] = datetime.utcnow().isoformat()
        return order

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by ID."""
        return self._orders.get(order_id)

    def get_order_by_number(self, order_number: str) -> Optional[Dict[str, Any]]:
        """Get order by order number."""
        for order in self._orders.values():
            if order['order_number'] == order_number:
                return order
        return None

    def get_orders_by_customer(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all orders for a customer."""
        return [
            order for order in self._orders.values()
            if order['customer_id'] == customer_id
        ]

    def get_orders_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get orders by status."""
        return [
            order for order in self._orders.values()
            if order['status'] == status
        ]

    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all open orders."""
        closed_statuses = {'shipped', 'delivered', 'cancelled'}
        return [
            order for order in self._orders.values()
            if order['status'] not in closed_statuses
        ]

    def get_late_orders(self) -> List[Dict[str, Any]]:
        """Get orders past their promised date."""
        today = date.today()
        late = []

        for order in self._orders.values():
            if order['status'] in {'shipped', 'delivered', 'cancelled'}:
                continue
            if order.get('promised_delivery_date'):
                promised = date.fromisoformat(order['promised_delivery_date'])
                if today > promised:
                    late.append(order)

        return late

    def get_due_soon(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get orders due within specified days."""
        cutoff = date.today() + timedelta(days=days)
        due_soon = []

        for order in self.get_open_orders():
            if order.get('promised_delivery_date'):
                promised = date.fromisoformat(order['promised_delivery_date'])
                if promised <= cutoff:
                    due_soon.append(order)

        return due_soon

    def get_order_summary(self) -> Dict[str, Any]:
        """Get summary statistics of orders."""
        total = len(self._orders)
        by_status = {}

        for order in self._orders.values():
            status = order['status']
            by_status[status] = by_status.get(status, 0) + 1

        return {
            'total_orders': total,
            'by_status': by_status,
            'open_orders': len(self.get_open_orders()),
            'late_orders': len(self.get_late_orders()),
            'due_this_week': len(self.get_due_soon(7)),
        }

    def cancel_order(self, order_id: str, reason: str = "") -> Optional[Dict[str, Any]]:
        """Cancel an order."""
        order = self._orders.get(order_id)
        if not order:
            return None

        if order['status'] in {'shipped', 'delivered', 'cancelled'}:
            return order

        order['status'] = 'cancelled'
        order['cancellation_reason'] = reason
        order['cancelled_at'] = datetime.utcnow().isoformat()
        order['updated_at'] = datetime.utcnow().isoformat()

        for line in order['lines']:
            line['status'] = 'cancelled'

        logger.info(f"Order {order['order_number']} cancelled: {reason}")

        return order
