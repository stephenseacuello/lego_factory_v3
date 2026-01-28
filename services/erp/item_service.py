"""
LEGO Factory v3 - Item Service
===============================
Item master and BOM management.
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db_session

logger = logging.getLogger(__name__)


class ItemService:
    """Service for managing items and BOMs."""

    def __init__(self, session: Session):
        self.session = session

    def create_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new item."""
        from models.erp.items import Item, ItemType, ItemStatus, CostingMethod

        item = Item(
            item_id=data.get('item_id', f"ITM-{uuid.uuid4().hex[:8].upper()}"),
            name=data['name'],
            description=data.get('description'),
            item_type=ItemType(data.get('item_type', 'component')),
            status=ItemStatus(data.get('status', 'active')),
            category_id=data.get('category_id'),
            base_uom=data.get('base_uom', 'EA'),
            costing_method=CostingMethod(data.get('costing_method', 'standard')),
            standard_cost=data.get('standard_cost', 0),
            list_price=data.get('list_price', 0),
            lead_time_days=data.get('lead_time_days', 0),
            safety_stock=data.get('safety_stock', 0),
            reorder_point=data.get('reorder_point', 0),
            reorder_quantity=data.get('reorder_quantity', 0),
            is_purchasable=data.get('is_purchasable', True),
            is_salable=data.get('is_salable', True),
            is_manufactured=data.get('is_manufactured', False),
            is_lot_controlled=data.get('is_lot_controlled', False),
            is_serial_controlled=data.get('is_serial_controlled', False),
            track_inventory=data.get('track_inventory', True),
            weight=data.get('weight'),
            weight_uom=data.get('weight_uom'),
            recipe_id=data.get('recipe_id'),
            attributes=data.get('attributes', {}),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(item)
        self.session.flush()

        logger.info(f"Created item: {item.item_id}")
        return item.to_dict()

    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get an item by ID."""
        from models.erp.items import Item

        item = self.session.query(Item).filter(Item.item_id == item_id).first()
        return item.to_dict() if item else None

    def get_items(
        self,
        item_type: str = None,
        status: str = None,
        category_id: str = None,
        search: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get items with filtering."""
        from models.erp.items import Item, ItemType, ItemStatus

        query = self.session.query(Item).filter(Item.is_deleted == False)

        if item_type:
            query = query.filter(Item.item_type == ItemType(item_type))
        if status:
            query = query.filter(Item.status == ItemStatus(status))
        if category_id:
            query = query.filter(Item.category_id == category_id)
        if search:
            query = query.filter(
                (Item.item_id.ilike(f'%{search}%')) |
                (Item.name.ilike(f'%{search}%'))
            )

        items = query.order_by(Item.item_id).offset(offset).limit(limit).all()
        return [i.to_dict() for i in items]

    def update_item(self, item_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an item."""
        from models.erp.items import Item, ItemType, ItemStatus, CostingMethod

        item = self.session.query(Item).filter(Item.item_id == item_id).first()
        if not item:
            return None

        for key, value in data.items():
            if hasattr(item, key) and key not in ('id', 'item_id', 'created_at'):
                if key == 'item_type' and isinstance(value, str):
                    value = ItemType(value)
                elif key == 'status' and isinstance(value, str):
                    value = ItemStatus(value)
                elif key == 'costing_method' and isinstance(value, str):
                    value = CostingMethod(value)
                setattr(item, key, value)

        item.updated_at = datetime.utcnow()
        item.updated_by = data.get('updated_by', 'system')
        self.session.flush()

        return item.to_dict()

    def add_bom_line(self, parent_item_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a BOM line to an item."""
        from models.erp.items import Item, BOMLine

        parent = self.session.query(Item).filter(Item.item_id == parent_item_id).first()
        component = self.session.query(Item).filter(Item.item_id == data['component_item_id']).first()

        if not parent or not component:
            return None

        bom_line = BOMLine(
            parent_item_id=parent.id,
            component_item_id=component.id,
            sequence=data.get('sequence', 10),
            quantity=data['quantity'],
            uom=data.get('uom', 'EA'),
            effective_from=data.get('effective_from'),
            effective_to=data.get('effective_to'),
            is_optional=data.get('is_optional', False),
            scrap_factor=data.get('scrap_factor', 0),
            operation_sequence=data.get('operation_sequence'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(bom_line)
        self.session.flush()

        return bom_line.to_dict()

    def get_bom(self, item_id: str, effective_date: date = None) -> List[Dict[str, Any]]:
        """Get BOM for an item."""
        from models.erp.items import Item, BOMLine

        item = self.session.query(Item).filter(Item.item_id == item_id).first()
        if not item:
            return []

        query = self.session.query(BOMLine).filter(
            BOMLine.parent_item_id == item.id,
            BOMLine.is_deleted == False
        )

        if effective_date:
            query = query.filter(
                (BOMLine.effective_from == None) | (BOMLine.effective_from <= effective_date),
                (BOMLine.effective_to == None) | (BOMLine.effective_to >= effective_date)
            )

        bom_lines = query.order_by(BOMLine.sequence).all()

        result = []
        for line in bom_lines:
            line_dict = line.to_dict()
            line_dict['component'] = line.component_item.to_dict() if line.component_item else None
            result.append(line_dict)

        return result

    def explode_bom(self, item_id: str, quantity: float = 1.0, level: int = 0, max_level: int = 10) -> List[Dict[str, Any]]:
        """Recursively explode BOM to get all components."""
        if level >= max_level:
            return []

        bom = self.get_bom(item_id)
        result = []

        for line in bom:
            component_id = line['component']['item_id'] if line.get('component') else None
            required_qty = line['quantity'] * quantity * (1 + line.get('scrap_factor', 0) / 100)

            result.append({
                'level': level,
                'item_id': component_id,
                'item_name': line['component']['name'] if line.get('component') else None,
                'quantity': required_qty,
                'uom': line['uom'],
                'is_optional': line['is_optional'],
            })

            # Recursively explode
            if component_id:
                sub_bom = self.explode_bom(component_id, required_qty, level + 1, max_level)
                result.extend(sub_bom)

        return result

    def create_category(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an item category."""
        from models.erp.items import ItemCategory

        category = ItemCategory(
            code=data['code'],
            name=data['name'],
            description=data.get('description'),
            parent_id=data.get('parent_id'),
            inventory_account=data.get('inventory_account'),
            cogs_account=data.get('cogs_account'),
            revenue_account=data.get('revenue_account'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(category)
        self.session.flush()

        return category.to_dict()

    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all item categories."""
        from models.erp.items import ItemCategory

        categories = self.session.query(ItemCategory).filter(
            ItemCategory.is_deleted == False
        ).order_by(ItemCategory.code).all()
        return [c.to_dict() for c in categories]

    def calculate_item_cost(self, item_id: str) -> float:
        """Calculate rolled-up cost from BOM."""
        from models.erp.items import Item

        item = self.session.query(Item).filter(Item.item_id == item_id).first()
        if not item:
            return 0

        if not item.is_manufactured:
            return item.standard_cost or 0

        bom = self.get_bom(item_id)
        total_cost = 0

        for line in bom:
            component_id = line['component']['item_id'] if line.get('component') else None
            if component_id:
                component_cost = self.calculate_item_cost(component_id)
                qty = line['quantity'] * (1 + line.get('scrap_factor', 0) / 100)
                total_cost += component_cost * qty

        return total_cost


def get_item_service(session: Session = None) -> ItemService:
    """Get item service instance."""
    if session:
        return ItemService(session)
    with get_db_session() as session:
        return ItemService(session)
