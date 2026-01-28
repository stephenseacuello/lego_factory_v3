"""
CTP Service - Capable-to-Promise

LegoMCP World-Class Manufacturing System v5.0
Phase 8: Customer Orders & ATP/CTP

Determines production capability:
- Check production capacity
- Evaluate material availability
- Calculate earliest production date
- Promise based on manufacturing capability
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CapacitySlot:
    """Available capacity slot."""
    work_center_id: str
    work_center_name: str
    slot_date: date
    shift: str = "day"

    # Time in minutes
    total_capacity: int = 480  # 8 hours
    used_capacity: int = 0
    available_capacity: int = 480

    # Efficiency factor
    efficiency: float = 0.85

    def can_accommodate(self, minutes_required: int) -> bool:
        """Check if slot can accommodate work."""
        effective_capacity = int(self.available_capacity * self.efficiency)
        return effective_capacity >= minutes_required


@dataclass
class MaterialRequirement:
    """Material needed for production."""
    part_id: str
    part_name: str
    quantity_required: int
    quantity_available: int = 0
    quantity_short: int = 0
    available_date: Optional[date] = None
    is_satisfied: bool = False


@dataclass
class CTPResult:
    """Result of CTP check."""
    part_id: str
    quantity_requested: int
    check_date: date

    # Can produce?
    can_produce: bool = False
    production_start_date: Optional[date] = None
    production_end_date: Optional[date] = None
    delivery_date: Optional[date] = None

    # Production time
    production_time_hours: float = 0.0
    queue_time_hours: float = 0.0
    total_lead_time_days: int = 0

    # Resource assignment
    assigned_work_center: Optional[str] = None
    routing_id: Optional[str] = None

    # Material check
    materials_available: bool = False
    material_requirements: List[MaterialRequirement] = field(default_factory=list)
    material_ready_date: Optional[date] = None

    # Bottleneck
    bottleneck_resource: Optional[str] = None
    bottleneck_reason: Optional[str] = None

    # Confidence
    confidence: float = 0.0
    promise_type: str = "ctp"

    # Message
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'part_id': self.part_id,
            'quantity_requested': self.quantity_requested,
            'check_date': self.check_date.isoformat(),
            'can_produce': self.can_produce,
            'production_start_date': (
                self.production_start_date.isoformat()
                if self.production_start_date else None
            ),
            'production_end_date': (
                self.production_end_date.isoformat()
                if self.production_end_date else None
            ),
            'delivery_date': (
                self.delivery_date.isoformat()
                if self.delivery_date else None
            ),
            'production_time_hours': self.production_time_hours,
            'total_lead_time_days': self.total_lead_time_days,
            'assigned_work_center': self.assigned_work_center,
            'materials_available': self.materials_available,
            'material_ready_date': (
                self.material_ready_date.isoformat()
                if self.material_ready_date else None
            ),
            'bottleneck_resource': self.bottleneck_resource,
            'bottleneck_reason': self.bottleneck_reason,
            'confidence': self.confidence,
            'promise_type': self.promise_type,
            'message': self.message,
        }


class CTPService:
    """
    Capable-to-Promise Service.

    Determines when production can fulfill an order by checking:
    - Material availability
    - Production capacity
    - Routing requirements
    """

    def __init__(
        self,
        capacity_service: Optional[Any] = None,
        inventory_service: Optional[Any] = None,
        routing_service: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.capacity_service = capacity_service
        self.inventory_service = inventory_service
        self.routing_service = routing_service
        self.config = config or {}

        # Default production parameters
        self.shipping_lead_days = 2
        self.safety_buffer_days = 1

        # In-memory capacity slots (would query from capacity service)
        self._capacity: Dict[str, List[CapacitySlot]] = {}

        # Part production info
        self._part_info: Dict[str, Dict[str, Any]] = {}

    def set_part_info(
        self,
        part_id: str,
        setup_time_min: int,
        run_time_per_unit_min: float,
        eligible_work_centers: List[str],
        bom: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Set production info for a part."""
        self._part_info[part_id] = {
            'setup_time_min': setup_time_min,
            'run_time_per_unit_min': run_time_per_unit_min,
            'eligible_work_centers': eligible_work_centers,
            'bom': bom or [],
        }

    def add_capacity_slot(self, slot: CapacitySlot) -> None:
        """Add a capacity slot."""
        if slot.work_center_id not in self._capacity:
            self._capacity[slot.work_center_id] = []
        self._capacity[slot.work_center_id].append(slot)

    def check_production_capability(
        self,
        part_id: str,
        quantity: int,
        requested_date: Optional[date] = None,
        priority: str = "B"
    ) -> CTPResult:
        """
        Check production capability for a part/quantity.

        Args:
            part_id: Part to produce
            quantity: Quantity needed
            requested_date: Desired delivery date
            priority: Order priority (A/B/C)

        Returns:
            CTPResult with capability details
        """
        check_date = date.today()

        result = CTPResult(
            part_id=part_id,
            quantity_requested=quantity,
            check_date=check_date,
        )

        # Get part info
        info = self._part_info.get(part_id)
        if not info:
            result.message = "Part production information not found"
            return result

        # Calculate production time
        setup_time = info['setup_time_min']
        run_time = info['run_time_per_unit_min'] * quantity
        total_production_minutes = setup_time + run_time
        result.production_time_hours = total_production_minutes / 60

        # Check material availability
        material_result = self._check_materials(part_id, quantity, info.get('bom', []))
        result.materials_available = material_result['available']
        result.material_requirements = material_result['requirements']
        result.material_ready_date = material_result.get('ready_date')

        if not result.materials_available and not result.material_ready_date:
            result.message = "Materials not available and no expected receipt"
            result.bottleneck_reason = "material_shortage"
            return result

        # Determine earliest start date
        earliest_start = check_date + timedelta(days=1)  # Minimum 1 day lead
        if result.material_ready_date and result.material_ready_date > earliest_start:
            earliest_start = result.material_ready_date

        # Find capacity slot
        capacity_result = self._find_capacity(
            info['eligible_work_centers'],
            total_production_minutes,
            earliest_start,
            priority
        )

        if not capacity_result['found']:
            result.message = f"No capacity available. Bottleneck: {capacity_result.get('bottleneck')}"
            result.bottleneck_resource = capacity_result.get('bottleneck')
            result.bottleneck_reason = "capacity_constraint"
            return result

        # Success - calculate dates
        result.can_produce = True
        result.assigned_work_center = capacity_result['work_center']
        result.production_start_date = capacity_result['start_date']

        # Calculate production end (simplified - assumes single day)
        production_days = max(1, int(total_production_minutes / 480))  # 8 hour days
        result.production_end_date = result.production_start_date + timedelta(days=production_days)

        # Add shipping lead time
        result.delivery_date = result.production_end_date + timedelta(
            days=self.shipping_lead_days + self.safety_buffer_days
        )

        result.total_lead_time_days = (result.delivery_date - check_date).days

        # Calculate confidence
        result.confidence = self._calculate_confidence(
            result.materials_available,
            capacity_result.get('utilization', 0.5),
            priority
        )

        # Check against requested date
        if requested_date:
            if result.delivery_date <= requested_date:
                result.message = f"Can meet requested date of {requested_date}"
            else:
                result.message = (
                    f"Cannot meet {requested_date}. "
                    f"Earliest delivery: {result.delivery_date}"
                )

        return result

    def _check_materials(
        self,
        part_id: str,
        quantity: int,
        bom: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Check material availability for production."""
        if not bom:
            return {'available': True, 'requirements': []}

        requirements = []
        all_available = True
        latest_date = None

        for item in bom:
            req_qty = item.get('quantity', 1) * quantity
            avail_qty = item.get('available', 0)

            req = MaterialRequirement(
                part_id=item.get('part_id', ''),
                part_name=item.get('part_name', ''),
                quantity_required=req_qty,
                quantity_available=avail_qty,
                quantity_short=max(0, req_qty - avail_qty),
                is_satisfied=avail_qty >= req_qty,
            )

            if not req.is_satisfied:
                all_available = False
                # Check for expected receipt
                expected_date = item.get('expected_date')
                if expected_date:
                    req.available_date = expected_date
                    if latest_date is None or expected_date > latest_date:
                        latest_date = expected_date

            requirements.append(req)

        return {
            'available': all_available,
            'requirements': requirements,
            'ready_date': latest_date,
        }

    def _find_capacity(
        self,
        work_centers: List[str],
        minutes_required: int,
        earliest_date: date,
        priority: str
    ) -> Dict[str, Any]:
        """Find available capacity slot."""
        # Priority affects search range
        search_days = {'A': 5, 'B': 14, 'C': 30}.get(priority, 14)

        for wc_id in work_centers:
            slots = self._capacity.get(wc_id, [])

            for slot in slots:
                if slot.slot_date < earliest_date:
                    continue
                if slot.slot_date > earliest_date + timedelta(days=search_days):
                    continue

                if slot.can_accommodate(minutes_required):
                    utilization = slot.used_capacity / slot.total_capacity
                    return {
                        'found': True,
                        'work_center': wc_id,
                        'start_date': slot.slot_date,
                        'utilization': utilization,
                    }

        # No capacity found
        return {
            'found': False,
            'bottleneck': work_centers[0] if work_centers else 'unknown',
        }

    def _calculate_confidence(
        self,
        materials_available: bool,
        utilization: float,
        priority: str
    ) -> float:
        """Calculate confidence in the promise."""
        base_confidence = 0.85

        # Materials factor
        if materials_available:
            base_confidence += 0.05
        else:
            base_confidence -= 0.10

        # Utilization factor (lower utilization = higher confidence)
        if utilization < 0.5:
            base_confidence += 0.05
        elif utilization > 0.8:
            base_confidence -= 0.10

        # Priority factor (higher priority = more focus)
        if priority == 'A':
            base_confidence += 0.05

        return min(0.99, max(0.50, base_confidence))

    def reserve_capacity(
        self,
        work_center_id: str,
        slot_date: date,
        minutes: int,
        order_id: str
    ) -> bool:
        """Reserve capacity for an order."""
        slots = self._capacity.get(work_center_id, [])

        for slot in slots:
            if slot.slot_date == slot_date:
                if slot.available_capacity >= minutes:
                    slot.used_capacity += minutes
                    slot.available_capacity -= minutes
                    logger.info(
                        f"Reserved {minutes} min on {work_center_id} "
                        f"for {slot_date} (order {order_id})"
                    )
                    return True

        return False

    def release_capacity(
        self,
        work_center_id: str,
        slot_date: date,
        minutes: int,
        order_id: str
    ) -> None:
        """Release reserved capacity."""
        slots = self._capacity.get(work_center_id, [])

        for slot in slots:
            if slot.slot_date == slot_date:
                slot.used_capacity = max(0, slot.used_capacity - minutes)
                slot.available_capacity = slot.total_capacity - slot.used_capacity
                logger.info(
                    f"Released {minutes} min on {work_center_id} "
                    f"for {slot_date} (order {order_id})"
                )
                break

    def get_capacity_summary(
        self,
        work_center_id: Optional[str] = None,
        days_ahead: int = 14
    ) -> Dict[str, Any]:
        """Get capacity utilization summary."""
        cutoff = date.today() + timedelta(days=days_ahead)
        summary = {}

        work_centers = [work_center_id] if work_center_id else list(self._capacity.keys())

        for wc_id in work_centers:
            slots = self._capacity.get(wc_id, [])
            total_capacity = 0
            used_capacity = 0
            days_data = []

            for slot in slots:
                if slot.slot_date > cutoff:
                    continue
                total_capacity += slot.total_capacity
                used_capacity += slot.used_capacity
                days_data.append({
                    'date': slot.slot_date.isoformat(),
                    'utilization': slot.used_capacity / slot.total_capacity,
                })

            summary[wc_id] = {
                'total_capacity_min': total_capacity,
                'used_capacity_min': used_capacity,
                'available_capacity_min': total_capacity - used_capacity,
                'utilization_percent': (
                    (used_capacity / total_capacity * 100)
                    if total_capacity > 0 else 0
                ),
                'daily': days_data,
            }

        return summary

    def simulate_what_if(
        self,
        part_id: str,
        quantity: int,
        scenarios: List[Dict[str, Any]]
    ) -> List[CTPResult]:
        """
        Run what-if scenarios for CTP.

        Scenarios can vary priority, requested date, work centers, etc.
        """
        results = []

        for scenario in scenarios:
            result = self.check_production_capability(
                part_id,
                quantity,
                requested_date=scenario.get('requested_date'),
                priority=scenario.get('priority', 'B'),
            )
            result.message = f"Scenario: {scenario.get('name', 'unnamed')} - {result.message}"
            results.append(result)

        return results
