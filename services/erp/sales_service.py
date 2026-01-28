"""
LEGO Factory v3 - Sales Service
================================
Sales orders, quotes, and shipments.
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from decimal import Decimal
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db_session

logger = logging.getLogger(__name__)


class SalesService:
    """Service for managing sales."""

    def __init__(self, session: Session):
        self.session = session

    def create_quote(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a sales quote."""
        from models.erp.sales import SalesQuote, QuoteStatus
        from models.erp.partners import Partner

        customer = self.session.query(Partner).filter(
            Partner.partner_id == data['customer_id']
        ).first()
        if not customer:
            raise ValueError(f"Customer {data['customer_id']} not found")

        quote = SalesQuote(
            quote_number=data.get('quote_number', f"QT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"),
            customer_id=customer.id,
            status=QuoteStatus.DRAFT,
            quote_date=data.get('quote_date', date.today()),
            expiration_date=data.get('expiration_date'),
            requested_date=data.get('requested_date'),
            currency=data.get('currency', 'USD'),
            shipping_method=data.get('shipping_method'),
            payment_terms=data.get('payment_terms', customer.payment_terms.value if customer.payment_terms else 'net_30'),
            customer_po=data.get('customer_po'),
            salesperson_id=data.get('salesperson_id', customer.salesperson_id),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(quote)
        self.session.flush()

        # Add lines
        for line_data in data.get('lines', []):
            self.add_quote_line(quote.quote_number, line_data)

        self._recalculate_quote_totals(quote)

        logger.info(f"Created sales quote: {quote.quote_number}")
        return quote.to_dict()

    def add_quote_line(self, quote_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a line to a sales quote."""
        from models.erp.sales import SalesQuote, SalesQuoteLine
        from models.erp.items import Item

        quote = self.session.query(SalesQuote).filter(
            SalesQuote.quote_number == quote_number
        ).first()
        item = self.session.query(Item).filter(Item.item_id == data['item_id']).first()

        if not quote or not item:
            return None

        line_number = len(quote.lines) + 1

        line = SalesQuoteLine(
            quote_id=quote.id,
            line_number=line_number,
            item_id=item.id,
            description=data.get('description', item.name),
            quantity=data['quantity'],
            uom=data.get('uom', item.base_uom),
            unit_price=data.get('unit_price', item.list_price),
            discount_percent=data.get('discount_percent', 0),
            requested_date=data.get('requested_date'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        # Calculate line total
        line.line_total = line.quantity * line.unit_price * (Decimal(1) - line.discount_percent / Decimal(100))

        self.session.add(line)
        self.session.flush()

        self._recalculate_quote_totals(quote)

        return line.to_dict()

    def _recalculate_quote_totals(self, quote):
        """Recalculate quote totals from lines."""
        quote.subtotal = sum(line.line_total for line in quote.lines)
        quote.tax_amount = sum(line.tax_amount or 0 for line in quote.lines)
        quote.total = quote.subtotal - quote.discount_amount + quote.tax_amount + quote.freight_amount
        self.session.flush()

    def convert_quote_to_order(self, quote_number: str) -> Optional[Dict[str, Any]]:
        """Convert a quote to a sales order."""
        from models.erp.sales import SalesQuote, SalesOrder, SalesOrderLine, QuoteStatus, SalesOrderStatus

        quote = self.session.query(SalesQuote).filter(
            SalesQuote.quote_number == quote_number
        ).first()

        if not quote or quote.status != QuoteStatus.ACCEPTED:
            return None

        order = SalesOrder(
            order_number=f"SO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
            customer_id=quote.customer_id,
            status=SalesOrderStatus.DRAFT,
            quote_id=quote.id,
            order_date=date.today(),
            requested_date=quote.requested_date,
            price_list_id=quote.price_list_id,
            currency=quote.currency,
            exchange_rate=quote.exchange_rate,
            subtotal=quote.subtotal,
            discount_amount=quote.discount_amount,
            tax_amount=quote.tax_amount,
            freight_amount=quote.freight_amount,
            total=quote.total,
            ship_to_address_id=quote.ship_to_address_id,
            shipping_method=quote.shipping_method,
            payment_terms=quote.payment_terms,
            customer_po=quote.customer_po,
            salesperson_id=quote.salesperson_id,
            notes=quote.notes,
            created_by='system',
        )

        self.session.add(order)
        self.session.flush()

        # Copy lines
        for ql in quote.lines:
            sol = SalesOrderLine(
                order_id=order.id,
                line_number=ql.line_number,
                item_id=ql.item_id,
                description=ql.description,
                quantity_ordered=ql.quantity,
                uom=ql.uom,
                unit_price=ql.unit_price,
                discount_percent=ql.discount_percent,
                line_total=ql.line_total,
                tax_code=ql.tax_code,
                tax_amount=ql.tax_amount,
                requested_date=ql.requested_date,
                notes=ql.notes,
                created_by='system',
            )
            self.session.add(sol)

        quote.status = QuoteStatus.CONVERTED
        self.session.flush()

        logger.info(f"Converted quote {quote_number} to order {order.order_number}")
        return order.to_dict()

    def create_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a sales order directly."""
        from models.erp.sales import SalesOrder, SalesOrderStatus
        from models.erp.partners import Partner

        customer = self.session.query(Partner).filter(
            Partner.partner_id == data['customer_id']
        ).first()
        if not customer:
            raise ValueError(f"Customer {data['customer_id']} not found")

        order = SalesOrder(
            order_number=data.get('order_number', f"SO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"),
            customer_id=customer.id,
            status=SalesOrderStatus.DRAFT,
            order_date=data.get('order_date', date.today()),
            requested_date=data.get('requested_date'),
            promised_date=data.get('promised_date'),
            currency=data.get('currency', 'USD'),
            shipping_method=data.get('shipping_method'),
            payment_terms=data.get('payment_terms', customer.payment_terms.value if customer.payment_terms else 'net_30'),
            customer_po=data.get('customer_po'),
            salesperson_id=data.get('salesperson_id', customer.salesperson_id),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(order)
        self.session.flush()

        # Add lines
        for line_data in data.get('lines', []):
            self.add_order_line(order.order_number, line_data)

        self._recalculate_order_totals(order)

        logger.info(f"Created sales order: {order.order_number}")
        return order.to_dict()

    def add_order_line(self, order_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a line to a sales order."""
        from models.erp.sales import SalesOrder, SalesOrderLine
        from models.erp.items import Item

        order = self.session.query(SalesOrder).filter(
            SalesOrder.order_number == order_number
        ).first()
        item = self.session.query(Item).filter(Item.item_id == data['item_id']).first()

        if not order or not item:
            return None

        line_number = len(order.lines) + 1

        line = SalesOrderLine(
            order_id=order.id,
            line_number=line_number,
            item_id=item.id,
            description=data.get('description', item.name),
            quantity_ordered=data['quantity'],
            uom=data.get('uom', item.base_uom),
            unit_price=data.get('unit_price', item.list_price),
            unit_cost=item.standard_cost,
            discount_percent=data.get('discount_percent', 0),
            requested_date=data.get('requested_date'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        line.line_total = line.quantity_ordered * line.unit_price * (Decimal(1) - line.discount_percent / Decimal(100))

        self.session.add(line)
        self.session.flush()

        self._recalculate_order_totals(order)

        return line.to_dict()

    def _recalculate_order_totals(self, order):
        """Recalculate order totals from lines."""
        order.subtotal = sum(line.line_total for line in order.lines)
        order.tax_amount = sum(line.tax_amount or 0 for line in order.lines)
        order.total = order.subtotal - order.discount_amount + order.tax_amount + order.freight_amount
        self.session.flush()

    def get_order(self, order_number: str) -> Optional[Dict[str, Any]]:
        """Get a sales order."""
        from models.erp.sales import SalesOrder

        order = self.session.query(SalesOrder).filter(
            SalesOrder.order_number == order_number
        ).first()

        if not order:
            return None

        result = order.to_dict()
        result['lines'] = [l.to_dict() for l in order.lines]
        result['customer'] = order.customer.to_dict() if order.customer else None
        return result

    def get_orders(
        self,
        customer_id: str = None,
        status: str = None,
        start_date: date = None,
        end_date: date = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get sales orders with filtering."""
        from models.erp.sales import SalesOrder, SalesOrderStatus
        from models.erp.partners import Partner

        query = self.session.query(SalesOrder).filter(SalesOrder.is_deleted == False)

        if customer_id:
            customer = self.session.query(Partner).filter(Partner.partner_id == customer_id).first()
            if customer:
                query = query.filter(SalesOrder.customer_id == customer.id)
        if status:
            query = query.filter(SalesOrder.status == SalesOrderStatus(status))
        if start_date:
            query = query.filter(SalesOrder.order_date >= start_date)
        if end_date:
            query = query.filter(SalesOrder.order_date <= end_date)

        orders = query.order_by(SalesOrder.order_date.desc()).limit(limit).all()
        return [o.to_dict() for o in orders]

    def release_order(self, order_number: str, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Release a sales order for fulfillment."""
        from models.erp.sales import SalesOrder, SalesOrderStatus

        order = self.session.query(SalesOrder).filter(
            SalesOrder.order_number == order_number
        ).first()

        if not order or order.status != SalesOrderStatus.APPROVED:
            return None

        order.status = SalesOrderStatus.RELEASED
        order.updated_at = datetime.utcnow()
        order.updated_by = user_id
        self.session.flush()

        logger.info(f"Released sales order: {order_number}")
        return order.to_dict()

    def create_shipment(self, order_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a shipment for a sales order."""
        from models.erp.sales import SalesOrder, Shipment, ShipmentLine, ShipmentStatus

        order = self.session.query(SalesOrder).filter(
            SalesOrder.order_number == order_number
        ).first()

        if not order:
            return None

        shipment = Shipment(
            shipment_number=data.get('shipment_number', f"SHP-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"),
            sales_order_id=order.id,
            status=ShipmentStatus.PENDING,
            ship_date=data.get('ship_date'),
            expected_delivery=data.get('expected_delivery'),
            carrier=data.get('carrier'),
            service_level=data.get('service_level'),
            tracking_number=data.get('tracking_number'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(shipment)
        self.session.flush()

        # Add lines
        for line_data in data.get('lines', []):
            so_line = next((l for l in order.lines if l.line_number == line_data.get('line_number')), None)
            if so_line:
                ship_line = ShipmentLine(
                    shipment_id=shipment.id,
                    sales_order_line_id=so_line.id,
                    item_id=so_line.item_id,
                    lot_id=line_data.get('lot_id'),
                    quantity=line_data['quantity'],
                    uom=so_line.uom,
                    location_id=line_data.get('location_id'),
                    created_by=data.get('created_by', 'system'),
                )
                self.session.add(ship_line)

                # Update SO line shipped quantity
                so_line.quantity_shipped += line_data['quantity']

        self.session.flush()

        logger.info(f"Created shipment {shipment.shipment_number} for order {order_number}")
        return shipment.to_dict()

    def get_open_orders_report(self) -> Dict[str, Any]:
        """Get open orders summary."""
        from models.erp.sales import SalesOrder, SalesOrderStatus

        open_statuses = [
            SalesOrderStatus.APPROVED,
            SalesOrderStatus.RELEASED,
            SalesOrderStatus.PARTIALLY_SHIPPED,
        ]

        total_orders = self.session.query(func.count(SalesOrder.id)).filter(
            SalesOrder.status.in_(open_statuses),
            SalesOrder.is_deleted == False
        ).scalar()

        total_value = self.session.query(func.sum(SalesOrder.total)).filter(
            SalesOrder.status.in_(open_statuses),
            SalesOrder.is_deleted == False
        ).scalar()

        return {
            'open_orders': total_orders,
            'total_value': float(total_value or 0),
            'as_of_date': datetime.utcnow().isoformat(),
        }


def get_sales_service(session: Session = None) -> SalesService:
    """Get sales service instance."""
    if session:
        return SalesService(session)
    with get_db_session() as session:
        return SalesService(session)
