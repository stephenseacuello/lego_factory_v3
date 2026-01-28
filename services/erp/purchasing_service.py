"""
LEGO Factory v3 - Purchasing Service
=====================================
Purchase orders, requisitions, and receiving.
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db_session

logger = logging.getLogger(__name__)


class PurchasingService:
    """Service for managing purchasing."""

    def __init__(self, session: Session):
        self.session = session

    def create_requisition(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a purchase requisition."""
        from models.erp.purchasing import PurchaseRequisition, RequisitionStatus

        requisition = PurchaseRequisition(
            requisition_number=data.get('requisition_number', f"REQ-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"),
            status=RequisitionStatus.DRAFT,
            requested_by=data['requested_by'],
            department=data.get('department'),
            request_date=data.get('request_date', date.today()),
            required_date=data.get('required_date'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(requisition)
        self.session.flush()

        # Add lines
        for line_data in data.get('lines', []):
            self.add_requisition_line(requisition.requisition_number, line_data)

        logger.info(f"Created requisition: {requisition.requisition_number}")
        return requisition.to_dict()

    def add_requisition_line(self, requisition_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a line to a requisition."""
        from models.erp.purchasing import PurchaseRequisition, PurchaseRequisitionLine
        from models.erp.items import Item

        requisition = self.session.query(PurchaseRequisition).filter(
            PurchaseRequisition.requisition_number == requisition_number
        ).first()
        item = self.session.query(Item).filter(Item.item_id == data['item_id']).first()

        if not requisition or not item:
            return None

        line_number = len(requisition.lines) + 1

        line = PurchaseRequisitionLine(
            requisition_id=requisition.id,
            line_number=line_number,
            item_id=item.id,
            description=data.get('description', item.name),
            quantity=data['quantity'],
            uom=data.get('uom', item.base_uom),
            estimated_unit_cost=data.get('estimated_unit_cost', item.standard_cost),
            required_date=data.get('required_date'),
            reference_type=data.get('reference_type'),
            reference_id=data.get('reference_id'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        line.estimated_total = line.quantity * (line.estimated_unit_cost or 0)

        self.session.add(line)
        self.session.flush()

        # Update requisition total
        requisition.estimated_total = sum(l.estimated_total or 0 for l in requisition.lines)
        self.session.flush()

        return line.to_dict()

    def create_purchase_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a purchase order."""
        from models.erp.purchasing import PurchaseOrder, PurchaseOrderStatus
        from models.erp.partners import Partner

        vendor = self.session.query(Partner).filter(
            Partner.partner_id == data['vendor_id']
        ).first()
        if not vendor:
            raise ValueError(f"Vendor {data['vendor_id']} not found")

        po = PurchaseOrder(
            po_number=data.get('po_number', f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"),
            vendor_id=vendor.id,
            status=PurchaseOrderStatus.DRAFT,
            order_date=data.get('order_date', date.today()),
            required_date=data.get('required_date'),
            currency=data.get('currency', 'USD'),
            shipping_method=data.get('shipping_method'),
            shipping_terms=data.get('shipping_terms'),
            payment_terms=data.get('payment_terms', vendor.payment_terms.value if vendor.payment_terms else 'net_30'),
            buyer_id=data.get('buyer_id'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(po)
        self.session.flush()

        # Add lines
        for line_data in data.get('lines', []):
            self.add_po_line(po.po_number, line_data)

        self._recalculate_po_totals(po)

        logger.info(f"Created purchase order: {po.po_number}")
        return po.to_dict()

    def add_po_line(self, po_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a line to a purchase order."""
        from models.erp.purchasing import PurchaseOrder, PurchaseOrderLine
        from models.erp.items import Item

        po = self.session.query(PurchaseOrder).filter(
            PurchaseOrder.po_number == po_number
        ).first()
        item = self.session.query(Item).filter(Item.item_id == data['item_id']).first()

        if not po or not item:
            return None

        line_number = len(po.lines) + 1

        line = PurchaseOrderLine(
            order_id=po.id,
            line_number=line_number,
            item_id=item.id,
            vendor_part_number=data.get('vendor_part_number'),
            description=data.get('description', item.name),
            quantity_ordered=data['quantity'],
            uom=data.get('uom', item.base_uom),
            unit_price=data.get('unit_price', item.standard_cost),
            discount_percent=data.get('discount_percent', 0),
            required_date=data.get('required_date'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        line.line_total = line.quantity_ordered * line.unit_price * (1 - line.discount_percent / 100)

        self.session.add(line)
        self.session.flush()

        self._recalculate_po_totals(po)

        return line.to_dict()

    def _recalculate_po_totals(self, po):
        """Recalculate PO totals from lines."""
        po.subtotal = sum(line.line_total for line in po.lines)
        po.tax_amount = sum(line.tax_amount or 0 for line in po.lines)
        po.total = po.subtotal - po.discount_amount + po.tax_amount + po.freight_amount
        self.session.flush()

    def get_purchase_order(self, po_number: str) -> Optional[Dict[str, Any]]:
        """Get a purchase order."""
        from models.erp.purchasing import PurchaseOrder

        po = self.session.query(PurchaseOrder).filter(
            PurchaseOrder.po_number == po_number
        ).first()

        if not po:
            return None

        result = po.to_dict()
        result['lines'] = [l.to_dict() for l in po.lines]
        result['vendor'] = po.vendor.to_dict() if po.vendor else None
        return result

    def get_purchase_orders(
        self,
        vendor_id: str = None,
        status: str = None,
        start_date: date = None,
        end_date: date = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get purchase orders with filtering."""
        from models.erp.purchasing import PurchaseOrder, PurchaseOrderStatus
        from models.erp.partners import Partner

        query = self.session.query(PurchaseOrder).filter(PurchaseOrder.is_deleted == False)

        if vendor_id:
            vendor = self.session.query(Partner).filter(Partner.partner_id == vendor_id).first()
            if vendor:
                query = query.filter(PurchaseOrder.vendor_id == vendor.id)
        if status:
            query = query.filter(PurchaseOrder.status == PurchaseOrderStatus(status))
        if start_date:
            query = query.filter(PurchaseOrder.order_date >= start_date)
        if end_date:
            query = query.filter(PurchaseOrder.order_date <= end_date)

        orders = query.order_by(PurchaseOrder.order_date.desc()).limit(limit).all()
        return [o.to_dict() for o in orders]

    def approve_po(self, po_number: str, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Approve a purchase order."""
        from models.erp.purchasing import PurchaseOrder, PurchaseOrderStatus

        po = self.session.query(PurchaseOrder).filter(
            PurchaseOrder.po_number == po_number
        ).first()

        if not po:
            return None

        po.status = PurchaseOrderStatus.APPROVED
        po.approved_by = user_id
        po.approved_date = datetime.utcnow()
        po.updated_at = datetime.utcnow()
        po.updated_by = user_id
        self.session.flush()

        logger.info(f"Approved PO: {po_number}")
        return po.to_dict()

    def send_po(self, po_number: str, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Mark PO as sent to vendor."""
        from models.erp.purchasing import PurchaseOrder, PurchaseOrderStatus

        po = self.session.query(PurchaseOrder).filter(
            PurchaseOrder.po_number == po_number
        ).first()

        if not po or po.status != PurchaseOrderStatus.APPROVED:
            return None

        po.status = PurchaseOrderStatus.SENT
        po.updated_at = datetime.utcnow()
        po.updated_by = user_id
        self.session.flush()

        return po.to_dict()

    def receive_goods(self, po_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a receipt for a PO."""
        from models.erp.purchasing import PurchaseOrder, PurchaseOrderStatus, Receipt, ReceiptLine, ReceiptStatus
        from models.erp.inventory import Lot

        po = self.session.query(PurchaseOrder).filter(
            PurchaseOrder.po_number == po_number
        ).first()

        if not po:
            return None

        receipt = Receipt(
            receipt_number=data.get('receipt_number', f"RCV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"),
            purchase_order_id=po.id,
            status=ReceiptStatus.PENDING,
            receipt_date=data.get('receipt_date', date.today()),
            carrier=data.get('carrier'),
            tracking_number=data.get('tracking_number'),
            packing_slip=data.get('packing_slip'),
            location_id=data.get('location_id'),
            inspection_required=data.get('inspection_required', False),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(receipt)
        self.session.flush()

        # Add lines
        for line_data in data.get('lines', []):
            po_line = next((l for l in po.lines if l.line_number == line_data.get('line_number')), None)
            if po_line:
                # Create lot if specified
                lot = None
                if line_data.get('lot_number'):
                    lot = Lot(
                        lot_number=line_data['lot_number'],
                        item_id=po_line.item_id,
                        receipt_date=receipt.receipt_date,
                        vendor_id=po.vendor_id,
                        vendor_lot=line_data.get('vendor_lot'),
                        created_by=data.get('created_by', 'system'),
                    )
                    self.session.add(lot)
                    self.session.flush()

                receipt_line = ReceiptLine(
                    receipt_id=receipt.id,
                    po_line_id=po_line.id,
                    item_id=po_line.item_id,
                    quantity_received=line_data['quantity_received'],
                    quantity_accepted=line_data.get('quantity_accepted', line_data['quantity_received']),
                    quantity_rejected=line_data.get('quantity_rejected', 0),
                    uom=po_line.uom,
                    lot_id=lot.id if lot else None,
                    vendor_lot=line_data.get('vendor_lot'),
                    location_id=line_data.get('location_id', data.get('location_id')),
                    unit_cost=po_line.unit_price,
                    rejection_reason=line_data.get('rejection_reason'),
                    notes=line_data.get('notes'),
                    created_by=data.get('created_by', 'system'),
                )
                receipt_line.total_cost = receipt_line.quantity_accepted * receipt_line.unit_cost

                self.session.add(receipt_line)

                # Update PO line received quantity
                po_line.quantity_received += line_data['quantity_received']
                po_line.quantity_rejected += line_data.get('quantity_rejected', 0)

        self.session.flush()

        # Update PO status
        total_ordered = sum(l.quantity_ordered for l in po.lines)
        total_received = sum(l.quantity_received for l in po.lines)

        if total_received >= total_ordered:
            po.status = PurchaseOrderStatus.RECEIVED
        else:
            po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED

        po.quantity_received = total_received
        self.session.flush()

        logger.info(f"Created receipt {receipt.receipt_number} for PO {po_number}")
        return receipt.to_dict()

    def get_open_po_report(self) -> Dict[str, Any]:
        """Get open PO summary."""
        from models.erp.purchasing import PurchaseOrder, PurchaseOrderStatus

        open_statuses = [
            PurchaseOrderStatus.APPROVED,
            PurchaseOrderStatus.SENT,
            PurchaseOrderStatus.ACKNOWLEDGED,
            PurchaseOrderStatus.PARTIALLY_RECEIVED,
        ]

        total_orders = self.session.query(func.count(PurchaseOrder.id)).filter(
            PurchaseOrder.status.in_(open_statuses),
            PurchaseOrder.is_deleted == False
        ).scalar()

        total_value = self.session.query(func.sum(PurchaseOrder.total)).filter(
            PurchaseOrder.status.in_(open_statuses),
            PurchaseOrder.is_deleted == False
        ).scalar()

        return {
            'open_pos': total_orders,
            'total_value': float(total_value or 0),
            'as_of_date': datetime.utcnow().isoformat(),
        }


def get_purchasing_service(session: Session = None) -> PurchasingService:
    """Get purchasing service instance."""
    if session:
        return PurchasingService(session)
    with get_db_session() as session:
        return PurchasingService(session)
