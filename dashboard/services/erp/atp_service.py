"""
ATP Service - Available-to-Promise

LegoMCP World-Class Manufacturing System v5.0
Phase 8: Customer Orders & ATP/CTP

Determines product availability from inventory:
- Check current inventory levels
- Consider allocated quantities
- Calculate available quantities
- Promise from stock
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class InventoryPosition:
    """Current inventory position for a part."""
    part_id: str
    quantity_on_hand: int = 0
    quantity_allocated: int = 0
    quantity_on_order: int = 0
    quantity_in_production: int = 0

    # Safety stock
    safety_stock: int = 0
    reorder_point: int = 0

    # Location breakdown
    by_location: Dict[str, int] = field(default_factory=dict)

    @property
    def quantity_available(self) -> int:
        """Quantity available for new orders."""
        return max(0, self.quantity_on_hand - self.quantity_allocated - self.safety_stock)

    @property
    def total_supply(self) -> int:
        """Total expected supply."""
        return self.quantity_on_hand + self.quantity_on_order + self.quantity_in_production

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'part_id': self.part_id,
            'quantity_on_hand': self.quantity_on_hand,
            'quantity_allocated': self.quantity_allocated,
            'quantity_available': self.quantity_available,
            'quantity_on_order': self.quantity_on_order,
            'quantity_in_production': self.quantity_in_production,
            'safety_stock': self.safety_stock,
            'total_supply': self.total_supply,
            'by_location': self.by_location,
        }


@dataclass
class ATPResult:
    """Result of ATP check."""
    part_id: str
    quantity_requested: int
    check_date: date

    # Available immediately
    quantity_available: int = 0
    available_date: Optional[date] = None
    available_location: Optional[str] = None

    # Partial availability
    partial_available: int = 0
    full_available_date: Optional[date] = None

    # Status
    can_fulfill: bool = False
    promise_type: str = "atp"  # atp, partial_atp, none

    # Details
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'part_id': self.part_id,
            'quantity_requested': self.quantity_requested,
            'check_date': self.check_date.isoformat(),
            'quantity_available': self.quantity_available,
            'available_date': self.available_date.isoformat() if self.available_date else None,
            'available_location': self.available_location,
            'partial_available': self.partial_available,
            'full_available_date': (
                self.full_available_date.isoformat()
                if self.full_available_date else None
            ),
            'can_fulfill': self.can_fulfill,
            'promise_type': self.promise_type,
            'message': self.message,
        }


class ATPService:
    """
    Available-to-Promise Service.

    Determines product availability from current and projected inventory.
    """

    def __init__(
        self,
        inventory_service: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.inventory_service = inventory_service
        self.config = config or {}

        # Default lead times for shipping
        self.shipping_lead_days = {
            'same_day': 0,
            'next_day': 1,
            'standard': 3,
            'economy': 7,
        }

        # In-memory inventory positions (would query from inventory service)
        self._inventory: Dict[str, InventoryPosition] = {}

        # Projected receipts (POs, production completions)
        self._projected_receipts: Dict[str, List[Dict[str, Any]]] = {}

    def set_inventory_position(self, position: InventoryPosition) -> None:
        """Set inventory position for a part."""
        self._inventory[position.part_id] = position

    def add_projected_receipt(
        self,
        part_id: str,
        quantity: int,
        expected_date: date,
        source: str = "production"
    ) -> None:
        """Add a projected inventory receipt."""
        if part_id not in self._projected_receipts:
            self._projected_receipts[part_id] = []

        self._projected_receipts[part_id].append({
            'quantity': quantity,
            'expected_date': expected_date,
            'source': source,
        })

        # Sort by date
        self._projected_receipts[part_id].sort(key=lambda x: x['expected_date'])

    def check_availability(
        self,
        part_id: str,
        quantity: int,
        requested_date: Optional[date] = None,
        shipping_method: str = "standard"
    ) -> ATPResult:
        """
        Check availability for a part/quantity.

        Args:
            part_id: Part to check
            quantity: Quantity needed
            requested_date: Requested delivery date
            shipping_method: Shipping speed

        Returns:
            ATPResult with availability details
        """
        check_date = date.today()
        shipping_days = self.shipping_lead_days.get(shipping_method, 3)

        result = ATPResult(
            part_id=part_id,
            quantity_requested=quantity,
            check_date=check_date,
        )

        # Get current position
        position = self._inventory.get(part_id)

        if not position:
            result.message = "Part not found in inventory"
            return result

        # Check immediate availability
        if position.quantity_available >= quantity:
            result.can_fulfill = True
            result.quantity_available = quantity
            result.available_date = check_date + timedelta(days=shipping_days)
            result.promise_type = "atp"
            result.message = f"Available from inventory at {list(position.by_location.keys())[0] if position.by_location else 'main warehouse'}"

            # Find best location
            for loc, qty in position.by_location.items():
                if qty >= quantity:
                    result.available_location = loc
                    break

            return result

        # Partial availability
        if position.quantity_available > 0:
            result.partial_available = position.quantity_available
            result.message = f"Partial availability: {position.quantity_available} of {quantity}"

        # Check projected receipts
        remaining_need = quantity - position.quantity_available
        projected = self._projected_receipts.get(part_id, [])

        cumulative = position.quantity_available
        for receipt in projected:
            cumulative += receipt['quantity']
            if cumulative >= quantity:
                result.full_available_date = receipt['expected_date'] + timedelta(days=shipping_days)
                result.message += f". Full quantity available by {result.full_available_date}"
                break

        # Determine if we can fulfill by requested date
        if requested_date:
            if result.can_fulfill and result.available_date and result.available_date <= requested_date:
                result.message = f"Can meet requested date of {requested_date}"
            elif result.full_available_date and result.full_available_date <= requested_date:
                result.can_fulfill = True
                result.available_date = result.full_available_date
                result.promise_type = "projected_atp"
                result.message = f"Can meet requested date with projected inventory"
            else:
                result.can_fulfill = False
                result.promise_type = "none"
                result.message = f"Cannot meet requested date. Consider CTP or later date."

        return result

    def check_multi_part_availability(
        self,
        parts: List[Dict[str, int]],
        requested_date: Optional[date] = None
    ) -> Dict[str, ATPResult]:
        """
        Check availability for multiple parts (e.g., BOM).

        Args:
            parts: List of {part_id, quantity} dicts
            requested_date: Requested delivery date

        Returns:
            Dict of part_id -> ATPResult
        """
        results = {}
        for part in parts:
            results[part['part_id']] = self.check_availability(
                part['part_id'],
                part['quantity'],
                requested_date
            )
        return results

    def get_available_inventory(self, part_id: str) -> int:
        """Get current available inventory for a part."""
        position = self._inventory.get(part_id)
        return position.quantity_available if position else 0

    def allocate_inventory(
        self,
        part_id: str,
        quantity: int,
        order_id: str
    ) -> bool:
        """
        Allocate inventory for an order.

        Returns True if allocation successful.
        """
        position = self._inventory.get(part_id)
        if not position:
            return False

        if position.quantity_available < quantity:
            return False

        position.quantity_allocated += quantity
        logger.info(f"Allocated {quantity} of {part_id} for order {order_id}")
        return True

    def release_allocation(
        self,
        part_id: str,
        quantity: int,
        order_id: str
    ) -> None:
        """Release previously allocated inventory."""
        position = self._inventory.get(part_id)
        if position:
            position.quantity_allocated = max(0, position.quantity_allocated - quantity)
            logger.info(f"Released allocation of {quantity} of {part_id} from order {order_id}")

    def get_inventory_summary(self) -> Dict[str, Any]:
        """Get summary of all inventory positions."""
        total_on_hand = 0
        total_available = 0
        total_allocated = 0
        parts_count = len(self._inventory)

        for position in self._inventory.values():
            total_on_hand += position.quantity_on_hand
            total_available += position.quantity_available
            total_allocated += position.quantity_allocated

        return {
            'parts_count': parts_count,
            'total_on_hand': total_on_hand,
            'total_available': total_available,
            'total_allocated': total_allocated,
            'utilization_percent': (
                (total_allocated / total_on_hand * 100) if total_on_hand > 0 else 0
            ),
        }

    def project_availability(
        self,
        part_id: str,
        days_ahead: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Project availability over time.

        Returns daily availability projection.
        """
        position = self._inventory.get(part_id)
        if not position:
            return []

        projections = []
        current = position.quantity_available

        for day in range(days_ahead + 1):
            proj_date = date.today() + timedelta(days=day)

            # Add any receipts for this date
            receipts = self._projected_receipts.get(part_id, [])
            for receipt in receipts:
                if receipt['expected_date'] == proj_date:
                    current += receipt['quantity']

            projections.append({
                'date': proj_date.isoformat(),
                'available': current,
            })

        return projections
