"""
Procurement Service - Purchase order and supplier management.

Handles:
- Purchase order creation and management
- Supplier management
- Receiving and inspection
- Lead time tracking
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Part
from models.inventory import InventoryTransaction, InventoryBalance, InventoryLocation

logger = logging.getLogger(__name__)


class PurchaseOrderStatus(Enum):
    """Purchase order status codes."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ORDERED = "ordered"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class ProcurementService:
    """Procurement and purchasing service."""

    def __init__(self, session: Session):
        self.session = session
        # In-memory PO storage (would be database table in production)
        self._purchase_orders: Dict[str, Dict] = {}
        self._suppliers: Dict[str, Dict] = {}
        self._po_counter = 1000

    def create_supplier(
        self,
        name: str,
        code: str,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
        lead_time_days: int = 7,
        min_order_value: float = 0,
        payment_terms: str = "NET30"
    ) -> Dict[str, Any]:
        """
        Create a new supplier.

        Args:
            name: Supplier name
            code: Unique supplier code
            contact_email: Contact email
            contact_phone: Contact phone
            lead_time_days: Standard lead time
            min_order_value: Minimum order value
            payment_terms: Payment terms

        Returns:
            Created supplier dict
        """
        if code in self._suppliers:
            raise ValueError(f"Supplier {code} already exists")

        supplier = {
            'id': code,
            'name': name,
            'code': code,
            'contact_email': contact_email,
            'contact_phone': contact_phone,
            'lead_time_days': lead_time_days,
            'min_order_value': min_order_value,
            'payment_terms': payment_terms,
            'active': True,
            'created_at': datetime.utcnow().isoformat()
        }

        self._suppliers[code] = supplier
        logger.info(f"Created supplier: {code}")
        return supplier

    def get_supplier(self, supplier_code: str) -> Optional[Dict[str, Any]]:
        """Get supplier by code."""
        return self._suppliers.get(supplier_code)

    def list_suppliers(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List all suppliers."""
        suppliers = list(self._suppliers.values())
        if active_only:
            suppliers = [s for s in suppliers if s.get('active', True)]
        return suppliers

    def create_purchase_order(
        self,
        supplier_code: str,
        lines: List[Dict[str, Any]],
        notes: Optional[str] = None,
        requested_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a new purchase order.

        Args:
            supplier_code: Supplier code
            lines: List of line items with part_id, quantity, unit_price
            notes: PO notes
            requested_date: Requested delivery date

        Returns:
            Created purchase order dict
        """
        supplier = self.get_supplier(supplier_code)
        if not supplier:
            raise ValueError(f"Supplier {supplier_code} not found")

        self._po_counter += 1
        po_number = f"PO-{self._po_counter:06d}"

        # Calculate totals
        total_amount = 0
        po_lines = []

        for i, line in enumerate(lines, 1):
            part = self.session.query(Part).filter(
                Part.id == line['part_id']
            ).first()

            line_total = line['quantity'] * line['unit_price']
            total_amount += line_total

            po_lines.append({
                'line_number': i,
                'part_id': line['part_id'],
                'part_number': part.part_number if part else None,
                'part_name': part.name if part else None,
                'quantity_ordered': line['quantity'],
                'quantity_received': 0,
                'unit_price': line['unit_price'],
                'line_total': line_total
            })

        # Calculate expected date
        if not requested_date:
            requested_date = datetime.utcnow() + timedelta(
                days=supplier['lead_time_days']
            )

        po = {
            'po_number': po_number,
            'supplier_code': supplier_code,
            'supplier_name': supplier['name'],
            'status': PurchaseOrderStatus.DRAFT.value,
            'lines': po_lines,
            'total_amount': total_amount,
            'notes': notes,
            'requested_date': requested_date.isoformat(),
            'created_at': datetime.utcnow().isoformat(),
            'approved_at': None,
            'ordered_at': None,
            'received_at': None
        }

        self._purchase_orders[po_number] = po
        logger.info(f"Created PO {po_number} for supplier {supplier_code}")
        return po

    def get_purchase_order(self, po_number: str) -> Optional[Dict[str, Any]]:
        """Get purchase order by number."""
        return self._purchase_orders.get(po_number)

    def approve_purchase_order(
        self,
        po_number: str,
        approved_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Approve a purchase order."""
        po = self.get_purchase_order(po_number)
        if not po:
            raise ValueError(f"PO {po_number} not found")

        if po['status'] != PurchaseOrderStatus.DRAFT.value:
            raise ValueError(f"PO {po_number} cannot be approved (status: {po['status']})")

        po['status'] = PurchaseOrderStatus.APPROVED.value
        po['approved_at'] = datetime.utcnow().isoformat()
        po['approved_by'] = approved_by

        logger.info(f"Approved PO {po_number}")
        return po

    def send_purchase_order(self, po_number: str) -> Dict[str, Any]:
        """Mark purchase order as sent to supplier."""
        po = self.get_purchase_order(po_number)
        if not po:
            raise ValueError(f"PO {po_number} not found")

        if po['status'] != PurchaseOrderStatus.APPROVED.value:
            raise ValueError(f"PO {po_number} must be approved before sending")

        po['status'] = PurchaseOrderStatus.ORDERED.value
        po['ordered_at'] = datetime.utcnow().isoformat()

        logger.info(f"Sent PO {po_number}")
        return po

    def receive_purchase_order(
        self,
        po_number: str,
        receipts: List[Dict[str, Any]],
        location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Receive items against a purchase order.

        Args:
            po_number: PO number
            receipts: List of receipts with line_number, quantity_received
            location_id: Inventory location for received items

        Returns:
            Updated purchase order
        """
        po = self.get_purchase_order(po_number)
        if not po:
            raise ValueError(f"PO {po_number} not found")

        if po['status'] not in [
            PurchaseOrderStatus.ORDERED.value,
            PurchaseOrderStatus.PARTIALLY_RECEIVED.value
        ]:
            raise ValueError(f"PO {po_number} cannot be received (status: {po['status']})")

        # Process receipts
        for receipt in receipts:
            line_num = receipt['line_number']
            qty = receipt['quantity_received']

            for line in po['lines']:
                if line['line_number'] == line_num:
                    line['quantity_received'] += qty

                    # Create inventory transaction
                    if location_id:
                        self._create_receipt_transaction(
                            part_id=line['part_id'],
                            quantity=qty,
                            location_id=location_id,
                            po_number=po_number
                        )
                    break

        # Update PO status
        all_received = all(
            line['quantity_received'] >= line['quantity_ordered']
            for line in po['lines']
        )
        any_received = any(
            line['quantity_received'] > 0
            for line in po['lines']
        )

        if all_received:
            po['status'] = PurchaseOrderStatus.RECEIVED.value
            po['received_at'] = datetime.utcnow().isoformat()
        elif any_received:
            po['status'] = PurchaseOrderStatus.PARTIALLY_RECEIVED.value

        logger.info(f"Received against PO {po_number}")
        return po

    def _create_receipt_transaction(
        self,
        part_id: str,
        quantity: int,
        location_id: str,
        po_number: str
    ):
        """Create inventory transaction for receipt."""
        transaction = InventoryTransaction(
            transaction_type='receipt',
            part_id=part_id,
            quantity=quantity,
            to_location_id=location_id,
            reference_number=po_number,
            notes=f"Receipt from PO {po_number}"
        )
        self.session.add(transaction)

        # Update balance
        balance = self.session.query(InventoryBalance).filter(
            InventoryBalance.part_id == part_id,
            InventoryBalance.location_id == location_id
        ).first()

        if balance:
            balance.quantity_on_hand += quantity
        else:
            balance = InventoryBalance(
                part_id=part_id,
                location_id=location_id,
                quantity_on_hand=quantity
            )
            self.session.add(balance)

        self.session.commit()

    def list_purchase_orders(
        self,
        supplier_code: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List purchase orders with filters."""
        orders = list(self._purchase_orders.values())

        if supplier_code:
            orders = [o for o in orders if o['supplier_code'] == supplier_code]
        if status:
            orders = [o for o in orders if o['status'] == status]

        # Sort by created date descending
        orders.sort(key=lambda x: x['created_at'], reverse=True)

        return orders[:limit]

    def get_open_orders_by_part(self, part_id: str) -> List[Dict[str, Any]]:
        """Get all open PO lines for a part."""
        open_statuses = [
            PurchaseOrderStatus.APPROVED.value,
            PurchaseOrderStatus.ORDERED.value,
            PurchaseOrderStatus.PARTIALLY_RECEIVED.value
        ]

        result = []
        for po in self._purchase_orders.values():
            if po['status'] not in open_statuses:
                continue

            for line in po['lines']:
                if line['part_id'] == part_id:
                    remaining = line['quantity_ordered'] - line['quantity_received']
                    if remaining > 0:
                        result.append({
                            'po_number': po['po_number'],
                            'supplier': po['supplier_name'],
                            'quantity_ordered': line['quantity_ordered'],
                            'quantity_received': line['quantity_received'],
                            'quantity_remaining': remaining,
                            'expected_date': po['requested_date']
                        })

        return result

    def calculate_reorder_point(
        self,
        part_id: str,
        lead_time_days: int = 7,
        safety_stock_days: int = 3,
        daily_usage: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate reorder point for a part.

        Reorder Point = (Lead Time × Daily Usage) + Safety Stock

        Args:
            part_id: Part ID
            lead_time_days: Supplier lead time
            safety_stock_days: Days of safety stock
            daily_usage: Average daily usage (calculated if not provided)

        Returns:
            Reorder point calculation
        """
        # Calculate daily usage from recent transactions if not provided
        if daily_usage is None:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            usage = self.session.query(
                func.sum(InventoryTransaction.quantity)
            ).filter(
                InventoryTransaction.part_id == part_id,
                InventoryTransaction.transaction_type.in_(['issue', 'production']),
                InventoryTransaction.created_at >= thirty_days_ago
            ).scalar() or 0

            daily_usage = usage / 30

        # Calculate reorder point
        lead_time_demand = lead_time_days * daily_usage
        safety_stock = safety_stock_days * daily_usage
        reorder_point = lead_time_demand + safety_stock

        return {
            'part_id': part_id,
            'daily_usage': round(daily_usage, 2),
            'lead_time_days': lead_time_days,
            'lead_time_demand': round(lead_time_demand, 2),
            'safety_stock_days': safety_stock_days,
            'safety_stock': round(safety_stock, 2),
            'reorder_point': round(reorder_point, 0),
            'calculated_at': datetime.utcnow().isoformat()
        }
