"""
LEGO Factory v3 - Inventory Service
====================================
Inventory transactions, balances, and lot tracking.
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db_session

logger = logging.getLogger(__name__)


class InventoryService:
    """Service for managing inventory."""

    def __init__(self, session: Session):
        self.session = session

    def create_location(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an inventory location."""
        from models.erp.inventory import Location, LocationType

        location = Location(
            location_id=data.get('location_id', f"LOC-{uuid.uuid4().hex[:6].upper()}"),
            name=data['name'],
            description=data.get('description'),
            parent_id=data.get('parent_id'),
            location_type=LocationType(data.get('location_type', 'warehouse')),
            address_line1=data.get('address_line1'),
            city=data.get('city'),
            state=data.get('state'),
            postal_code=data.get('postal_code'),
            country=data.get('country'),
            is_active=data.get('is_active', True),
            allows_negative=data.get('allows_negative', False),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(location)
        self.session.flush()

        return location.to_dict()

    def get_locations(self, location_type: str = None) -> List[Dict[str, Any]]:
        """Get all locations."""
        from models.erp.inventory import Location, LocationType

        query = self.session.query(Location).filter(
            Location.is_deleted == False,
            Location.is_active == True
        )

        if location_type:
            query = query.filter(Location.location_type == LocationType(location_type))

        locations = query.order_by(Location.location_id).all()
        return [l.to_dict() for l in locations]

    def get_balances(
        self,
        item_id: str = None,
        location_id: str = None,
        below_reorder: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List inventory balances with optional filters."""
        from sqlalchemy.orm import joinedload
        from models.erp.items import Item
        from models.erp.inventory import Location, InventoryBalance

        query = self.session.query(InventoryBalance).options(
            joinedload(InventoryBalance.item),
            joinedload(InventoryBalance.location),
        )

        if item_id:
            item = self.session.query(Item).filter(Item.item_id == item_id).first()
            if item:
                query = query.filter(InventoryBalance.item_id == item.id)

        if location_id:
            loc = self.session.query(Location).filter(Location.location_id == location_id).first()
            if loc:
                query = query.filter(InventoryBalance.location_id == loc.id)

        balances = query.limit(limit).all()

        if below_reorder:
            balances = [
                b for b in balances
                if b.item and b.quantity_on_hand <= (b.item.reorder_point or 0)
            ]

        return [b.to_dict() for b in balances]

    def get_balance(
        self,
        item_id: str,
        location_id: str = None,
        lot_id: str = None
    ) -> Dict[str, Any]:
        """Get inventory balance for an item."""
        from models.erp.items import Item
        from models.erp.inventory import Location, Lot, InventoryBalance

        item = self.session.query(Item).filter(Item.item_id == item_id).first()
        if not item:
            return {'item_id': item_id, 'error': 'Item not found'}

        query = self.session.query(InventoryBalance).filter(
            InventoryBalance.item_id == item.id
        )

        if location_id:
            location = self.session.query(Location).filter(Location.location_id == location_id).first()
            if location:
                query = query.filter(InventoryBalance.location_id == location.id)

        if lot_id:
            lot = self.session.query(Lot).filter(Lot.lot_number == lot_id).first()
            if lot:
                query = query.filter(InventoryBalance.lot_id == lot.id)

        balances = query.all()

        total_on_hand = sum(b.quantity_on_hand for b in balances)
        total_allocated = sum(b.quantity_allocated for b in balances)
        total_available = sum(b.quantity_available for b in balances)
        total_value = sum(b.total_value for b in balances)

        return {
            'item_id': item_id,
            'quantity_on_hand': total_on_hand,
            'quantity_allocated': total_allocated,
            'quantity_available': total_available,
            'total_value': total_value,
            'locations': [b.to_dict() for b in balances],
        }

    def process_transaction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an inventory transaction."""
        from models.erp.items import Item
        from models.erp.inventory import (
            Location, Lot, InventoryBalance, InventoryTransaction, TransactionType
        )

        item = self.session.query(Item).filter(Item.item_id == data['item_id']).first()
        if not item:
            raise ValueError(f"Item {data['item_id']} not found")

        from_location = None
        to_location = None
        lot = None

        if data.get('from_location_id'):
            from_location = self.session.query(Location).filter(
                Location.location_id == data['from_location_id']
            ).first()

        if data.get('to_location_id'):
            to_location = self.session.query(Location).filter(
                Location.location_id == data['to_location_id']
            ).first()

        if data.get('lot_number'):
            lot = self.session.query(Lot).filter(
                Lot.lot_number == data['lot_number'],
                Lot.item_id == item.id
            ).first()

        # Create transaction record
        transaction = InventoryTransaction(
            transaction_id=data.get('transaction_id', f"TXN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"),
            transaction_type=TransactionType(data['transaction_type']),
            transaction_date=data.get('transaction_date', datetime.utcnow()),
            item_id=item.id,
            lot_id=lot.id if lot else None,
            from_location_id=from_location.id if from_location else None,
            to_location_id=to_location.id if to_location else None,
            quantity=data['quantity'],
            uom=data.get('uom', item.base_uom),
            unit_cost=data.get('unit_cost', item.standard_cost),
            reference_type=data.get('reference_type'),
            reference_id=data.get('reference_id'),
            reason_code=data.get('reason_code'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        transaction.total_cost = transaction.quantity * (transaction.unit_cost or 0)

        self.session.add(transaction)

        # Update balances
        trans_type = TransactionType(data['transaction_type'])

        if trans_type in (TransactionType.RECEIPT, TransactionType.PRODUCTION_RECEIPT, TransactionType.RETURN):
            # Increase inventory at to_location
            if to_location:
                self._update_balance(item.id, to_location.id, lot.id if lot else None,
                                    data['quantity'], transaction.unit_cost)

        elif trans_type in (TransactionType.ISSUE, TransactionType.PRODUCTION_ISSUE, TransactionType.SCRAP):
            # Decrease inventory at from_location
            if from_location:
                self._update_balance(item.id, from_location.id, lot.id if lot else None,
                                    -data['quantity'], transaction.unit_cost)

        elif trans_type == TransactionType.TRANSFER:
            # Decrease from source, increase at destination
            if from_location:
                self._update_balance(item.id, from_location.id, lot.id if lot else None,
                                    -data['quantity'], transaction.unit_cost)
            if to_location:
                self._update_balance(item.id, to_location.id, lot.id if lot else None,
                                    data['quantity'], transaction.unit_cost)

        elif trans_type == TransactionType.ADJUSTMENT:
            # Adjustment can be positive or negative
            location = to_location or from_location
            if location:
                self._update_balance(item.id, location.id, lot.id if lot else None,
                                    data['quantity'], transaction.unit_cost)

        self.session.flush()

        logger.info(f"Processed inventory transaction: {transaction.transaction_id}")
        return transaction.to_dict()

    def _update_balance(
        self,
        item_id: str,
        location_id: str,
        lot_id: str,
        quantity_change: float,
        unit_cost: float
    ):
        """Update or create inventory balance."""
        from models.erp.inventory import InventoryBalance

        balance = self.session.query(InventoryBalance).filter(
            InventoryBalance.item_id == item_id,
            InventoryBalance.location_id == location_id,
            InventoryBalance.lot_id == lot_id
        ).first()

        if not balance:
            balance = InventoryBalance(
                item_id=item_id,
                location_id=location_id,
                lot_id=lot_id,
                quantity_on_hand=0,
                quantity_allocated=0,
                quantity_available=0,
                unit_cost=unit_cost or 0,
                total_value=0,
            )
            self.session.add(balance)

        balance.quantity_on_hand += quantity_change
        balance.quantity_available = balance.quantity_on_hand - balance.quantity_allocated

        if unit_cost:
            # Update average cost
            if balance.quantity_on_hand > 0:
                balance.unit_cost = (
                    (balance.unit_cost * (balance.quantity_on_hand - quantity_change) +
                     unit_cost * quantity_change) / balance.quantity_on_hand
                )
            balance.total_value = balance.quantity_on_hand * balance.unit_cost

        if quantity_change > 0:
            balance.last_receipt_date = datetime.utcnow()
        else:
            balance.last_issue_date = datetime.utcnow()

    def allocate_inventory(
        self,
        item_id: str,
        location_id: str,
        quantity: float,
        reference_type: str,
        reference_id: str,
        lot_id: str = None
    ) -> bool:
        """Allocate inventory for an order."""
        from models.erp.items import Item
        from models.erp.inventory import Location, InventoryBalance

        item = self.session.query(Item).filter(Item.item_id == item_id).first()
        location = self.session.query(Location).filter(Location.location_id == location_id).first()

        if not item or not location:
            return False

        balance = self.session.query(InventoryBalance).filter(
            InventoryBalance.item_id == item.id,
            InventoryBalance.location_id == location.id,
            InventoryBalance.lot_id == lot_id
        ).first()

        if not balance or balance.quantity_available < quantity:
            return False

        balance.quantity_allocated += quantity
        balance.quantity_available = balance.quantity_on_hand - balance.quantity_allocated
        self.session.flush()

        logger.info(f"Allocated {quantity} of {item_id} for {reference_type} {reference_id}")
        return True

    def deallocate_inventory(
        self,
        item_id: str,
        location_id: str,
        quantity: float,
        lot_id: str = None
    ) -> bool:
        """Release allocated inventory."""
        from models.erp.items import Item
        from models.erp.inventory import Location, InventoryBalance

        item = self.session.query(Item).filter(Item.item_id == item_id).first()
        location = self.session.query(Location).filter(Location.location_id == location_id).first()

        if not item or not location:
            return False

        balance = self.session.query(InventoryBalance).filter(
            InventoryBalance.item_id == item.id,
            InventoryBalance.location_id == location.id,
            InventoryBalance.lot_id == lot_id
        ).first()

        if not balance:
            return False

        balance.quantity_allocated = max(0, balance.quantity_allocated - quantity)
        balance.quantity_available = balance.quantity_on_hand - balance.quantity_allocated
        self.session.flush()

        return True

    def create_lot(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a lot/batch."""
        from models.erp.items import Item
        from models.erp.inventory import Lot, LotStatus

        item = self.session.query(Item).filter(Item.item_id == data['item_id']).first()
        if not item:
            raise ValueError(f"Item {data['item_id']} not found")

        lot = Lot(
            lot_number=data['lot_number'],
            item_id=item.id,
            status=LotStatus(data.get('status', 'available')),
            manufacture_date=data.get('manufacture_date'),
            expiration_date=data.get('expiration_date'),
            receipt_date=data.get('receipt_date', date.today()),
            vendor_id=data.get('vendor_id'),
            vendor_lot=data.get('vendor_lot'),
            attributes=data.get('attributes', {}),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(lot)
        self.session.flush()

        return lot.to_dict()

    def get_transaction_history(
        self,
        item_id: str = None,
        location_id: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get inventory transaction history."""
        from models.erp.items import Item
        from models.erp.inventory import Location, InventoryTransaction

        query = self.session.query(InventoryTransaction)

        if item_id:
            item = self.session.query(Item).filter(Item.item_id == item_id).first()
            if item:
                query = query.filter(InventoryTransaction.item_id == item.id)

        if location_id:
            location = self.session.query(Location).filter(Location.location_id == location_id).first()
            if location:
                query = query.filter(
                    (InventoryTransaction.from_location_id == location.id) |
                    (InventoryTransaction.to_location_id == location.id)
                )

        if start_date:
            query = query.filter(InventoryTransaction.transaction_date >= start_date)
        if end_date:
            query = query.filter(InventoryTransaction.transaction_date <= end_date)

        transactions = query.order_by(InventoryTransaction.transaction_date.desc()).limit(limit).all()
        return [t.to_dict() for t in transactions]

    def get_valuation_report(self, location_id: str = None) -> Dict[str, Any]:
        """Get inventory valuation report."""
        from models.erp.inventory import Location, InventoryBalance

        query = self.session.query(
            func.sum(InventoryBalance.quantity_on_hand).label('total_quantity'),
            func.sum(InventoryBalance.total_value).label('total_value')
        )

        if location_id:
            location = self.session.query(Location).filter(Location.location_id == location_id).first()
            if location:
                query = query.filter(InventoryBalance.location_id == location.id)

        result = query.first()

        return {
            'total_quantity': float(result.total_quantity or 0),
            'total_value': float(result.total_value or 0),
            'as_of_date': datetime.utcnow().isoformat(),
        }


def get_inventory_service(session: Session = None) -> InventoryService:
    """Get inventory service instance."""
    if session:
        return InventoryService(session)
    with get_db_session() as session:
        return InventoryService(session)
