"""
LEGO Factory v3 - Resource Service
===================================
Resource management for MESA-11 Resource Allocation & Status function.
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from models.mes.resources import (
    ResourceStatus, MachineStatus, ToolInventory, ToolStatus,
    MaterialLot, MaterialStatus, MaterialReservation
)

logger = logging.getLogger(__name__)


def _emit_resource_event(event_type: str, data: Dict[str, Any]):
    """
    Emit resource event to WebSocket clients.
    """
    try:
        from services.websocket.socket_service import emit_to_namespace
        emit_to_namespace(event_type, data, namespace='/dashboard')
        logger.debug(f"Emitted resource event: {event_type}")
    except ImportError:
        logger.debug("WebSocket service not available")
    except Exception as e:
        logger.warning(f"Failed to emit resource event: {e}")


class ResourceService:
    """Service for managing machine resources, tools, and materials."""

    def __init__(self, session: Session):
        self.session = session
        self._machines_config = None

    def _load_machines_config(self) -> List[Dict[str, Any]]:
        """Load machines configuration from JSON file."""
        if self._machines_config is not None:
            return self._machines_config

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'config', 'machines.json'
        )
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                self._machines_config = config.get('machines', [])
                return self._machines_config
        except Exception as e:
            logger.warning(f"Could not load machines config: {e}")
            return []

    # =========================================================================
    # Machine Status Management
    # =========================================================================

    def get_resource_dashboard(self) -> Dict[str, Any]:
        """
        Get aggregated resource dashboard data.
        Returns counts by status, all machine statuses, and material summary.
        """
        # Get all machine statuses
        statuses = self.session.query(ResourceStatus).all()
        status_map = {s.machine_id: s for s in statuses}

        # Load machine config to get all machines (including those without status records)
        machines_config = self._load_machines_config()
        physical_machines = [m for m in machines_config if m.get('machine_type') != 'virtual']

        # Build machine list with status
        machines = []
        counts = {
            'running': 0,
            'idle': 0,
            'down': 0,
            'setup': 0,
            'maintenance': 0,
            'offline': 0,
            'total': len(physical_machines),
        }

        for machine in physical_machines:
            machine_id = machine['machine_id']
            status_record = status_map.get(machine_id)

            if status_record:
                status = status_record.status.value if status_record.status else 'offline'
                counts[status] = counts.get(status, 0) + 1
                machines.append({
                    **status_record.to_dict(),
                    'machine_type': machine.get('machine_type'),
                    'area': machine.get('area'),
                    'cell': machine.get('cell'),
                    'capabilities': machine.get('capabilities', []),
                })
            else:
                counts['offline'] += 1
                machines.append({
                    'machine_id': machine_id,
                    'machine_name': machine.get('name'),
                    'status': 'offline',
                    'machine_type': machine.get('machine_type'),
                    'area': machine.get('area'),
                    'cell': machine.get('cell'),
                    'capabilities': machine.get('capabilities', []),
                    'is_connected': False,
                })

        # Get material summary
        material_summary = self._get_material_summary()

        # Get tool summary
        tool_summary = self._get_tool_summary()

        return {
            'counts': counts,
            'machines': machines,
            'materials': material_summary,
            'tools': tool_summary,
            'timestamp': datetime.utcnow().isoformat(),
        }

    def update_machine_status(
        self,
        machine_id: str,
        status: str,
        job_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
        operation_name: Optional[str] = None,
        material_type: Optional[str] = None,
        material_lot: Optional[str] = None,
        extra_data: Optional[Dict] = None,
    ) -> ResourceStatus:
        """
        Update machine status. Creates record if doesn't exist.
        Emits WebSocket event on status change.
        """
        # Get or create status record
        resource = self.session.query(ResourceStatus).filter(
            ResourceStatus.machine_id == machine_id
        ).first()

        if not resource:
            # Get machine name from config
            machines_config = self._load_machines_config()
            machine_config = next((m for m in machines_config if m['machine_id'] == machine_id), None)
            machine_name = machine_config.get('name', machine_id) if machine_config else machine_id

            resource = ResourceStatus(
                machine_id=machine_id,
                machine_name=machine_name,
                status=MachineStatus.OFFLINE,
            )
            self.session.add(resource)

        # Track status change
        old_status = resource.status
        new_status = MachineStatus(status) if isinstance(status, str) else status

        if old_status != new_status:
            resource.previous_status = old_status
            resource.status_changed_at = datetime.utcnow()

        # Update fields
        resource.status = new_status
        resource.is_connected = True
        resource.last_heartbeat = datetime.utcnow()

        if job_id is not None:
            resource.current_job_id = job_id
        if work_order_id is not None:
            resource.current_work_order_id = work_order_id
        if operation_name is not None:
            resource.current_operation_name = operation_name
        if material_type is not None:
            resource.current_material_type = material_type
        if material_lot is not None:
            resource.current_material_lot = material_lot
        if extra_data:
            resource.extra_data = {**(resource.extra_data or {}), **extra_data}

        self.session.flush()

        # Emit event if status changed
        if old_status != new_status:
            _emit_resource_event('resource_update', {
                'machine_id': machine_id,
                'old_status': old_status.value if old_status else None,
                'new_status': new_status.value,
                'resource': resource.to_dict(),
            })
            logger.info(f"Machine {machine_id} status: {old_status} -> {new_status}")

        return resource

    def update_machine_position(
        self,
        machine_id: str,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        spindle_rpm: Optional[float] = None,
        extruder_temp: Optional[float] = None,
        bed_temp: Optional[float] = None,
    ) -> Optional[ResourceStatus]:
        """Update machine position and sensor data."""
        resource = self.session.query(ResourceStatus).filter(
            ResourceStatus.machine_id == machine_id
        ).first()

        if not resource:
            return None

        if x is not None:
            resource.position_x = x
        if y is not None:
            resource.position_y = y
        if z is not None:
            resource.position_z = z
        if spindle_rpm is not None:
            resource.spindle_rpm = spindle_rpm
        if extruder_temp is not None:
            resource.extruder_temp = extruder_temp
        if bed_temp is not None:
            resource.bed_temp = bed_temp

        resource.last_heartbeat = datetime.utcnow()
        self.session.flush()

        return resource

    def update_job_progress(
        self,
        machine_id: str,
        progress_pct: float,
        estimated_completion: Optional[datetime] = None,
    ) -> Optional[ResourceStatus]:
        """Update job progress for a machine."""
        resource = self.session.query(ResourceStatus).filter(
            ResourceStatus.machine_id == machine_id
        ).first()

        if not resource:
            return None

        resource.job_progress_pct = progress_pct
        if estimated_completion:
            resource.estimated_completion = estimated_completion
        resource.last_heartbeat = datetime.utcnow()
        self.session.flush()

        return resource

    def set_machine_alarm(
        self,
        machine_id: str,
        alarm_code: str,
        alarm_message: str,
    ) -> Optional[ResourceStatus]:
        """Set alarm on a machine."""
        resource = self.session.query(ResourceStatus).filter(
            ResourceStatus.machine_id == machine_id
        ).first()

        if not resource:
            return None

        resource.has_alarm = True
        resource.alarm_code = alarm_code
        resource.alarm_message = alarm_message
        self.session.flush()

        _emit_resource_event('machine_alarm', {
            'machine_id': machine_id,
            'alarm_code': alarm_code,
            'alarm_message': alarm_message,
        })

        return resource

    def clear_machine_alarm(self, machine_id: str) -> Optional[ResourceStatus]:
        """Clear alarm on a machine."""
        resource = self.session.query(ResourceStatus).filter(
            ResourceStatus.machine_id == machine_id
        ).first()

        if not resource:
            return None

        resource.has_alarm = False
        resource.alarm_code = None
        resource.alarm_message = None
        self.session.flush()

        return resource

    def get_machine_status(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """Get status for a single machine with config data."""
        resource = self.session.query(ResourceStatus).filter(
            ResourceStatus.machine_id == machine_id
        ).first()

        machines_config = self._load_machines_config()
        machine_config = next((m for m in machines_config if m['machine_id'] == machine_id), None)

        if resource:
            result = resource.to_dict()
            if machine_config:
                result.update({
                    'machine_type': machine_config.get('machine_type'),
                    'area': machine_config.get('area'),
                    'cell': machine_config.get('cell'),
                    'capabilities': machine_config.get('capabilities', []),
                    'config': machine_config,
                })
            return result
        elif machine_config:
            return {
                'machine_id': machine_id,
                'machine_name': machine_config.get('name'),
                'status': 'offline',
                'is_connected': False,
                'machine_type': machine_config.get('machine_type'),
                'area': machine_config.get('area'),
                'cell': machine_config.get('cell'),
                'capabilities': machine_config.get('capabilities', []),
                'config': machine_config,
            }
        return None

    # =========================================================================
    # Material Management
    # =========================================================================

    def _get_material_summary(self) -> Dict[str, Any]:
        """Get material inventory summary."""
        # Count by status
        status_counts = self.session.query(
            MaterialLot.status,
            func.count(MaterialLot.id)
        ).filter(
            MaterialLot.is_deleted == False
        ).group_by(MaterialLot.status).all()

        counts = {s.value: c for s, c in status_counts}

        # Get low stock items
        low_stock = self.session.query(MaterialLot).filter(
            and_(
                MaterialLot.is_deleted == False,
                MaterialLot.status == MaterialStatus.AVAILABLE,
                MaterialLot.quantity_available < MaterialLot.quantity_received * 0.1
            )
        ).limit(10).all()

        # Get expiring soon (within 30 days)
        expiring = self.session.query(MaterialLot).filter(
            and_(
                MaterialLot.is_deleted == False,
                MaterialLot.expiry_date != None,
                MaterialLot.expiry_date < datetime.utcnow() + timedelta(days=30)
            )
        ).limit(10).all()

        return {
            'counts': counts,
            'low_stock': [m.to_dict() for m in low_stock],
            'expiring_soon': [m.to_dict() for m in expiring],
            'total_lots': sum(counts.values()),
        }

    def get_materials(
        self,
        material_type: Optional[str] = None,
        status: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get material lots with filtering."""
        query = self.session.query(MaterialLot).filter(MaterialLot.is_deleted == False)

        if material_type:
            query = query.filter(MaterialLot.material_type == material_type)
        if status:
            query = query.filter(MaterialLot.status == MaterialStatus(status))
        if location:
            query = query.filter(MaterialLot.location.ilike(f'%{location}%'))

        total = query.count()
        lots = query.order_by(MaterialLot.created_at.desc()).offset(offset).limit(limit).all()

        return {
            'lots': [lot.to_dict() for lot in lots],
            'total': total,
            'limit': limit,
            'offset': offset,
        }

    def get_material_lot(self, lot_id: str) -> Optional[Dict[str, Any]]:
        """Get a single material lot by ID or lot number."""
        lot = self.session.query(MaterialLot).filter(
            or_(
                MaterialLot.lot_number == lot_id,
                MaterialLot.id == lot_id if len(lot_id) == 36 else False
            )
        ).first()

        if lot:
            result = lot.to_dict()
            # Include reservations
            result['reservations'] = [r.to_dict() for r in lot.reservations if r.status == 'active']
            return result
        return None

    def check_material_availability(
        self,
        material_type: str,
        quantity: float,
    ) -> Dict[str, Any]:
        """
        Check if material is available in sufficient quantity.
        Returns available lots that can fulfill the request.
        """
        lots = self.session.query(MaterialLot).filter(
            and_(
                MaterialLot.is_deleted == False,
                MaterialLot.material_type == material_type,
                MaterialLot.status == MaterialStatus.AVAILABLE,
                MaterialLot.quantity_available > 0,
            )
        ).order_by(MaterialLot.expiry_date.asc().nullslast()).all()

        total_available = sum(lot.quantity_available - lot.quantity_reserved for lot in lots)
        is_available = total_available >= quantity

        # Find lots that can fulfill
        fulfillment_plan = []
        remaining = quantity
        for lot in lots:
            available = lot.quantity_available - lot.quantity_reserved
            if available > 0 and remaining > 0:
                use_qty = min(available, remaining)
                fulfillment_plan.append({
                    'lot_id': str(lot.id),
                    'lot_number': lot.lot_number,
                    'quantity': use_qty,
                    'expiry_date': lot.expiry_date.isoformat() if lot.expiry_date else None,
                })
                remaining -= use_qty

        return {
            'is_available': is_available,
            'total_available': total_available,
            'quantity_requested': quantity,
            'shortfall': max(0, quantity - total_available),
            'fulfillment_plan': fulfillment_plan if is_available else [],
            'material_type': material_type,
        }

    def reserve_material(
        self,
        lot_id: str,
        job_id: str,
        quantity: float,
        work_order_id: Optional[str] = None,
        reserved_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reserve material from a lot for a job.
        """
        lot = self.session.query(MaterialLot).filter(
            MaterialLot.id == lot_id
        ).first()

        if not lot:
            return {'success': False, 'error': 'Lot not found'}

        available = lot.quantity_available - lot.quantity_reserved
        if available < quantity:
            return {
                'success': False,
                'error': f'Insufficient quantity. Available: {available}, Requested: {quantity}'
            }

        # Create reservation
        reservation = MaterialReservation(
            lot_id=lot.id,
            job_id=job_id,
            work_order_id=work_order_id,
            quantity_reserved=quantity,
            unit_of_measure=lot.unit_of_measure,
            reserved_by=reserved_by,
        )
        self.session.add(reservation)

        # Update lot reserved quantity
        lot.quantity_reserved = (lot.quantity_reserved or 0) + quantity

        self.session.flush()

        logger.info(f"Reserved {quantity} {lot.unit_of_measure} from lot {lot.lot_number} for job {job_id}")

        return {
            'success': True,
            'reservation_id': str(reservation.id),
            'lot_number': lot.lot_number,
            'quantity_reserved': quantity,
        }

    def release_reservation(self, reservation_id: str) -> Dict[str, Any]:
        """Release a material reservation."""
        reservation = self.session.query(MaterialReservation).filter(
            MaterialReservation.id == reservation_id
        ).first()

        if not reservation:
            return {'success': False, 'error': 'Reservation not found'}

        if reservation.status != 'active':
            return {'success': False, 'error': f'Reservation already {reservation.status}'}

        # Update lot
        lot = reservation.lot
        lot.quantity_reserved = max(0, (lot.quantity_reserved or 0) - reservation.quantity_reserved)

        # Update reservation
        reservation.status = 'released'
        reservation.released_at = datetime.utcnow()

        self.session.flush()

        return {'success': True, 'lot_number': lot.lot_number}

    # Mapping from MES (material_type, color) to ERP item_id
    MATERIAL_TO_ERP_ITEM = {
        ('PLA', 'Red'):    'PLA-RED-1KG',
        ('PLA', 'Blue'):   'PLA-BLU-1KG',
        ('PLA', 'Yellow'): 'PLA-YLW-1KG',
        ('PLA', 'White'):  'PLA-WHT-1KG',
        ('Resin', 'Grey'): 'RESIN-GRY-1L',
        ('ABS', 'Green'):  'ABS-GRN-SHT',
        ('ABS', 'Grey'):   'ABS-GRY-SHT',
        ('Nylon', 'Black'): 'NYL-ROD-12',  # 12mm default
    }

    def consume_material(self, reservation_id: str, quantity: Optional[float] = None) -> Dict[str, Any]:
        """
        Mark material as consumed from a reservation.
        Also creates an ERP inventory issue transaction (MES→ERP integration).
        """
        reservation = self.session.query(MaterialReservation).filter(
            MaterialReservation.id == reservation_id
        ).first()

        if not reservation:
            return {'success': False, 'error': 'Reservation not found'}

        # Use full reserved quantity if not specified
        consume_qty = quantity or reservation.quantity_reserved

        # Update lot
        lot = reservation.lot
        lot.quantity_available = max(0, lot.quantity_available - consume_qty)
        lot.quantity_reserved = max(0, (lot.quantity_reserved or 0) - reservation.quantity_reserved)
        lot.quantity_consumed = (lot.quantity_consumed or 0) + consume_qty

        # Check if lot is now empty
        if lot.quantity_available <= 0:
            lot.status = MaterialStatus.CONSUMED

        # Update reservation
        reservation.quantity_consumed = consume_qty
        reservation.status = 'consumed'
        reservation.consumed_at = datetime.utcnow()

        self.session.flush()

        # MES→ERP: Create inventory issue transaction
        self._post_erp_material_issue(lot, consume_qty, reservation.job_id)

        return {
            'success': True,
            'lot_number': lot.lot_number,
            'quantity_consumed': consume_qty,
            'lot_remaining': lot.quantity_available,
        }

    def _post_erp_material_issue(self, lot, quantity: float, job_id=None):
        """Post an ERP inventory issue transaction for consumed material."""
        try:
            from services.erp.inventory_service import InventoryService

            erp_item_id = self.MATERIAL_TO_ERP_ITEM.get(
                (lot.material_type, lot.color)
            )
            if not erp_item_id:
                logger.debug(f"No ERP item mapping for ({lot.material_type}, {lot.color})")
                return

            # Determine the from_location based on material category
            location_map = {
                'filament': 'PROD-FDM',
                'resin': 'PROD-SLA',
                'sheet': 'PROD-CNC',
                'rod': 'PROD-CNC',
            }
            from_location = location_map.get(lot.material_category, 'WH-RAW')

            inv_service = InventoryService(self.session)
            inv_service.process_transaction({
                'transaction_type': 'issue',
                'item_id': erp_item_id,
                'from_location_id': from_location,
                'quantity': quantity,
                'reference_type': 'work_order',
                'reference_id': str(job_id) if job_id else None,
                'notes': f"MES material consumption from lot {lot.lot_number}",
                'created_by': 'mes_integration',
            })
            logger.info(f"Posted ERP issue: {erp_item_id} qty={quantity} from {from_location}")
        except Exception as e:
            logger.warning(f"Could not post ERP material issue: {e}")

    def create_material_lot(self, data: Dict[str, Any]) -> MaterialLot:
        """Create a new material lot."""
        lot = MaterialLot(
            lot_number=data.get('lot_number', f"LOT-{datetime.utcnow().strftime('%Y%m%d')}-{os.urandom(3).hex().upper()}"),
            material_type=data['material_type'],
            material_code=data.get('material_code'),
            material_name=data.get('material_name'),
            material_category=data.get('material_category'),
            color=data.get('color'),
            color_hex=data.get('color_hex'),
            quantity_received=data.get('quantity_received', data.get('quantity')),
            quantity_available=data.get('quantity_received', data.get('quantity')),
            unit_of_measure=data.get('unit_of_measure', 'g'),
            location=data.get('location'),
            supplier=data.get('supplier'),
            supplier_lot=data.get('supplier_lot'),
            expiry_date=data.get('expiry_date'),
            cost_per_unit=data.get('cost_per_unit'),
            notes=data.get('notes'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(lot)
        self.session.flush()

        logger.info(f"Created material lot: {lot.lot_number}")
        return lot

    # =========================================================================
    # Tool Management
    # =========================================================================

    def _get_tool_summary(self) -> Dict[str, Any]:
        """Get tool inventory summary."""
        # Count by status
        status_counts = self.session.query(
            ToolInventory.status,
            func.count(ToolInventory.id)
        ).filter(
            ToolInventory.is_deleted == False
        ).group_by(ToolInventory.status).all()

        counts = {s.value: c for s, c in status_counts}

        # Get worn tools (>80% wear)
        worn_tools = self.session.query(ToolInventory).filter(
            and_(
                ToolInventory.is_deleted == False,
                ToolInventory.wear_percent > 80
            )
        ).limit(10).all()

        return {
            'counts': counts,
            'worn_tools': [t.to_dict() for t in worn_tools],
            'total': sum(counts.values()),
        }

    def get_tools(
        self,
        machine_id: Optional[str] = None,
        tool_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get tool inventory with filtering."""
        query = self.session.query(ToolInventory).filter(ToolInventory.is_deleted == False)

        if machine_id:
            query = query.filter(ToolInventory.machine_id == machine_id)
        if tool_type:
            query = query.filter(ToolInventory.tool_type == tool_type)
        if status:
            query = query.filter(ToolInventory.status == ToolStatus(status))

        total = query.count()
        tools = query.order_by(ToolInventory.created_at.desc()).offset(offset).limit(limit).all()

        return {
            'tools': [tool.to_dict() for tool in tools],
            'total': total,
            'limit': limit,
            'offset': offset,
        }

    def update_tool_wear(
        self,
        tool_id: str,
        cutting_time_mins: float,
    ) -> Optional[ToolInventory]:
        """Update tool wear after use."""
        tool = self.session.query(ToolInventory).filter(
            ToolInventory.tool_id == tool_id
        ).first()

        if not tool:
            return None

        tool.total_cutting_time_mins = (tool.total_cutting_time_mins or 0) + cutting_time_mins
        tool.cut_count = (tool.cut_count or 0) + 1
        tool.last_used_at = datetime.utcnow()

        # Calculate wear percentage
        if tool.expected_life_mins and tool.expected_life_mins > 0:
            tool.wear_percent = min(100, (tool.total_cutting_time_mins / tool.expected_life_mins) * 100)
            tool.remaining_life_mins = max(0, tool.expected_life_mins - tool.total_cutting_time_mins)

            # Auto-update status if worn
            if tool.wear_percent >= 100:
                tool.status = ToolStatus.WORN

        self.session.flush()
        return tool


# Module-level convenience functions
def get_resource_dashboard(session: Session) -> Dict[str, Any]:
    """Get resource dashboard data."""
    service = ResourceService(session)
    return service.get_resource_dashboard()


def update_machine_status(session: Session, machine_id: str, status: str, **kwargs) -> ResourceStatus:
    """Update machine status."""
    service = ResourceService(session)
    return service.update_machine_status(machine_id, status, **kwargs)


def check_material_availability(session: Session, material_type: str, quantity: float) -> Dict[str, Any]:
    """Check material availability."""
    service = ResourceService(session)
    return service.check_material_availability(material_type, quantity)


def reserve_material(session: Session, lot_id: str, job_id: str, quantity: float, **kwargs) -> Dict[str, Any]:
    """Reserve material for a job."""
    service = ResourceService(session)
    return service.reserve_material(lot_id, job_id, quantity, **kwargs)
