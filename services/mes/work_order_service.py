"""
LEGO Factory v3 - Work Order Service
====================================
Work order management and execution tracking.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

from sqlalchemy.orm import Session

from config.database import get_db_session

logger = logging.getLogger(__name__)


def _emit_work_order_event(event_type: str, data: Dict[str, Any]):
    """
    Emit work order event to WebSocket clients.
    Gracefully handles case where SocketIO isn't initialized.
    """
    try:
        from services.websocket.socket_service import emit_to_namespace, emit_to_room

        # Emit to /dashboard namespace for dashboard subscribers
        emit_to_namespace(event_type, data, namespace='/dashboard')

        # Also notify MES users room
        emit_to_room(event_type, data, room='mes', namespace='/')

        logger.debug(f"Emitted work order event: {event_type}")
    except ImportError:
        logger.debug("WebSocket service not available, skipping work order emit")
    except Exception as e:
        logger.warning(f"Failed to emit work order event: {e}")


class WorkOrderService:
    """Service for managing work orders."""

    def __init__(self, session: Session):
        self.session = session

    def create_work_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new work order.

        If the product_id is a LEGO product SKU (e.g., 3001-ABS-RED),
        this will automatically:
        1. Look up the product and its routing
        2. Generate operations from the routing template
        3. Create a job for the scheduler
        """
        from models.mes.work_orders import WorkOrder, WorkOrderStatus, Operation, OperationType

        product_id = data.get('product_id')
        routing_id = data.get('routing_id')
        auto_generate_operations = data.get('auto_generate_operations', True)

        # Try to look up the LEGO product to get routing info
        product_info = None
        if product_id and auto_generate_operations:
            product_info = self._get_lego_product_info(product_id)
            if product_info:
                # Use product's routing if not explicitly specified
                if not routing_id and product_info.get('routing_id'):
                    routing_id = product_info['routing_id']
                # Auto-generate description if not provided
                if not data.get('description') and product_info.get('part_name'):
                    data['description'] = f"Manufacture {product_info['part_name']} ({product_id})"

        work_order = WorkOrder(
            work_order_id=data.get('work_order_id', f"WO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"),
            description=data.get('description'),
            product_id=product_id,
            recipe_id=data.get('recipe_id'),
            quantity_ordered=data.get('quantity_ordered', 1),
            status=WorkOrderStatus.DRAFT,
            priority=data.get('priority', 5),
            planned_start=data.get('planned_start'),
            planned_end=data.get('planned_end'),
            due_date=data.get('due_date'),
            customer_id=data.get('customer_id'),
            sales_order_id=data.get('sales_order_id'),
            notes=data.get('notes'),
            metadata=data.get('metadata', {}),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(work_order)
        self.session.flush()
        logger.info(f"Created work order: {work_order.work_order_id}")

        # Auto-generate operations from routing if available
        operations_created = 0
        if routing_id and auto_generate_operations:
            operations_created = self._generate_operations_from_routing(
                work_order=work_order,
                routing_id=routing_id,
                quantity=data.get('quantity_ordered', 1)
            )
            logger.info(f"Generated {operations_created} operations from routing {routing_id}")

        # Store product info in metadata
        if product_info:
            metadata = work_order.metadata or {}
            metadata['product_info'] = product_info
            metadata['routing_id'] = routing_id
            work_order.metadata = metadata
            self.session.flush()

        # Emit WebSocket event for work order creation
        work_order_data = work_order.to_dict()
        _emit_work_order_event('work_order_created', {
            'work_order_id': work_order.work_order_id,
            'created_at': datetime.utcnow().isoformat(),
            'created_by': data.get('created_by', 'system'),
            'work_order': work_order_data,
            'operations_created': operations_created,
        })

        return work_order_data

    def _get_lego_product_info(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Look up LEGO product info by SKU."""
        try:
            from models.lego.parts_catalog import LegoProduct
            product = self.session.query(LegoProduct).filter_by(sku=product_id).first()
            if product:
                return {
                    'sku': product.sku,
                    'part_number': product.part_number,
                    'material_code': product.material_code,
                    'color_code': product.color_code,
                    'routing_id': product.routing_id,
                    'part_name': product.part.name if product.part else None,
                    'material_name': product.material.name if product.material else None,
                    'color_name': product.color.name if product.color else None,
                    'weight_grams': product.weight_grams,
                }
        except Exception as e:
            logger.debug(f"Could not look up LEGO product {product_id}: {e}")
        return None

    def _generate_operations_from_routing(
        self,
        work_order,
        routing_id: str,
        quantity: int = 1
    ) -> int:
        """
        Generate work order operations from a routing template.

        Args:
            work_order: WorkOrder model instance
            routing_id: ID of the routing template to use
            quantity: Quantity to scale run times by

        Returns:
            Number of operations created
        """
        from models.mes.work_orders import Operation, OperationType

        try:
            from models.lego.parts_catalog import LegoRouting, LegoRoutingOperation

            routing = self.session.query(LegoRouting).filter_by(routing_id=routing_id).first()
            if not routing:
                logger.warning(f"Routing {routing_id} not found in database")
                return 0

            # Get routing operations ordered by sequence
            routing_ops = self.session.query(LegoRoutingOperation)\
                .filter_by(routing_id=routing_id)\
                .order_by(LegoRoutingOperation.sequence)\
                .all()

            if not routing_ops:
                logger.warning(f"No operations found for routing {routing_id}")
                return 0

            logger.info(f"Generating {len(routing_ops)} operations from routing {routing_id}")

            count = 0
            for rop in routing_ops:
                # Map operation_type string to OperationType enum
                op_type = self._map_operation_type(rop.operation_type)

                # Get eligible machines: prefer explicit list from routing, fallback to capability lookup
                eligible_machines = getattr(rop, 'eligible_machines', None) or []
                if not eligible_machines:
                    eligible_machines = self._get_eligible_machines_for_operation(rop.operation_type)

                # If machine_id is specified but not in eligible list, add it
                if rop.machine_id and rop.machine_id not in eligible_machines:
                    eligible_machines.append(rop.machine_id)

                operation = Operation(
                    work_order_id=work_order.id,
                    operation_id=f"OP-{work_order.work_order_id}-{rop.sequence:03d}",
                    sequence=rop.sequence,
                    operation_type=op_type,
                    name=rop.name,
                    description=rop.description or rop.instructions,
                    work_center_id=rop.work_center_id,
                    machine_id=rop.machine_id,
                    eligible_machines=eligible_machines,
                    setup_time=rop.setup_time_min or 0,
                    run_time=(rop.run_time_min or 0) * quantity,  # Scale by quantity
                    parameters={
                        'routing_id': routing_id,
                        'routing_sequence': rop.sequence,
                        'instructions': rop.instructions,
                        'gcode_template': rop.gcode_template,
                    },
                    metadata={
                        'source': 'auto_generated',
                        'routing_id': routing_id,
                    }
                )
                self.session.add(operation)
                count += 1
                logger.debug(f"Added operation {rop.sequence}: {rop.name} on machine {rop.machine_id}, eligible: {eligible_machines}")

            # Flush to ensure operations get IDs assigned
            self.session.flush()
            logger.info(f"Successfully generated {count} operations for work order {work_order.work_order_id}")
            return count

        except ImportError as e:
            logger.warning(f"LEGO parts catalog models not available: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error generating operations from routing {routing_id}: {e}", exc_info=True)
            return 0

    def _get_eligible_machines_for_operation(self, operation_type: str) -> List[str]:
        """
        Get list of eligible machine IDs for an operation type.

        Args:
            operation_type: Operation type string (e.g., 'fdm', 'cnc_milling')

        Returns:
            List of machine IDs that can perform this operation
        """
        machines = self._load_machines_config()

        # Map operation types to required capabilities
        op_to_caps = {
            'fdm': ['fdm_printing'],
            'printing_fdm': ['fdm_printing'],
            '3d_print': ['fdm_printing'],
            'print': ['fdm_printing'],
            'sla': ['sla_printing'],
            'printing_sla': ['sla_printing'],
            'resin': ['sla_printing'],
            'cnc': ['cnc_milling'],
            'cnc_milling': ['cnc_milling'],
            'milling': ['cnc_milling'],
            'machining': ['cnc_milling'],
            'roughing': ['cnc_milling'],
            'finishing': ['cnc_milling'],
            'lathe': ['cnc_turning'],
            'cnc_turning': ['cnc_turning'],
            'turning': ['cnc_turning'],
            'laser': ['laser_cutting', 'laser_engraving'],
            'laser_cut': ['laser_cutting'],
            'laser_engrave': ['laser_engraving'],
            'design': ['cad_design', 'cam_programming'],
            'cam_setup': ['cam_programming'],
            'slice': ['slicing'],
            'slicing': ['slicing'],
            'assembly': ['assembly', 'pick_and_place'],
            'robot': ['pick_and_place'],
            'load': ['pick_and_place'],
            'unload': ['pick_and_place'],
        }

        op_lower = (operation_type or '').lower()
        required_caps = op_to_caps.get(op_lower, [])

        if not required_caps:
            return []

        eligible = []
        for machine in machines:
            if not machine.get('enabled', True):
                continue
            machine_caps = set(machine.get('capabilities', []))
            # Machine is eligible if it has any of the required capabilities
            if machine_caps.intersection(required_caps):
                eligible.append(machine['machine_id'])

        return eligible

    def _map_operation_type(self, op_type_str: str) -> 'OperationType':
        """
        Map routing operation type string to OperationType enum.

        OperationType values: DESIGN, PRINTING_FDM, PRINTING_SLA, CNC_MILLING,
                              ASSEMBLY, INSPECTION, PACKAGING, CUSTOM
        """
        from models.mes.work_orders import OperationType

        if not op_type_str:
            return OperationType.CUSTOM

        op_lower = op_type_str.lower()

        mapping = {
            # Design/Setup operations
            'setup': OperationType.DESIGN,
            'design': OperationType.DESIGN,
            'cam_setup': OperationType.DESIGN,
            'slice': OperationType.DESIGN,
            'slicing': OperationType.DESIGN,
            # 3D Printing operations
            'fdm': OperationType.PRINTING_FDM,
            'printing_fdm': OperationType.PRINTING_FDM,
            '3d_print': OperationType.PRINTING_FDM,
            'print': OperationType.PRINTING_FDM,
            'sla': OperationType.PRINTING_SLA,
            'printing_sla': OperationType.PRINTING_SLA,
            'resin': OperationType.PRINTING_SLA,
            # CNC operations
            'machining': OperationType.CNC_MILLING,
            'cnc': OperationType.CNC_MILLING,
            'cnc_milling': OperationType.CNC_MILLING,
            'milling': OperationType.CNC_MILLING,
            'roughing': OperationType.CNC_MILLING,
            'finishing': OperationType.CNC_MILLING,
            # Assembly operations
            'assembly': OperationType.ASSEMBLY,
            'manual': OperationType.ASSEMBLY,
            'deburr': OperationType.ASSEMBLY,
            'clean': OperationType.ASSEMBLY,
            'load': OperationType.ASSEMBLY,
            'unload': OperationType.ASSEMBLY,
            'robot': OperationType.ASSEMBLY,
            # Inspection/QC operations
            'qc': OperationType.INSPECTION,
            'inspection': OperationType.INSPECTION,
            'quality_check': OperationType.INSPECTION,
            'test': OperationType.INSPECTION,
            'verify': OperationType.INSPECTION,
            # Packaging operations
            'package': OperationType.PACKAGING,
            'packaging': OperationType.PACKAGING,
            'pack': OperationType.PACKAGING,
            'ship': OperationType.PACKAGING,
        }
        return mapping.get(op_lower, OperationType.CUSTOM)

    def get_work_order(self, work_order_id: str) -> Optional[Dict[str, Any]]:
        """Get a work order by ID."""
        from models.mes.work_orders import WorkOrder

        wo = self.session.query(WorkOrder).filter(
            WorkOrder.work_order_id == work_order_id
        ).first()
        return wo.to_dict() if wo else None

    def get_work_orders(
        self,
        status: str = None,
        product_id: str = None,
        customer_id: str = None,
        due_before: datetime = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get work orders with filtering."""
        from models.mes.work_orders import WorkOrder, WorkOrderStatus

        query = self.session.query(WorkOrder).filter(WorkOrder.is_deleted == False)

        if status:
            query = query.filter(WorkOrder.status == WorkOrderStatus(status))
        if product_id:
            query = query.filter(WorkOrder.product_id == product_id)
        if customer_id:
            query = query.filter(WorkOrder.customer_id == customer_id)
        if due_before:
            query = query.filter(WorkOrder.due_date <= due_before)

        work_orders = query.order_by(WorkOrder.priority, WorkOrder.due_date)\
            .offset(offset).limit(limit).all()

        return [wo.to_dict() for wo in work_orders]

    def update_work_order(self, work_order_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a work order."""
        from models.mes.work_orders import WorkOrder, WorkOrderStatus

        wo = self.session.query(WorkOrder).filter(
            WorkOrder.work_order_id == work_order_id
        ).first()

        if not wo:
            return None

        # Track status change for WebSocket event
        old_status = wo.status.value if wo.status else None
        new_status = data.get('status')
        if isinstance(new_status, WorkOrderStatus):
            new_status = new_status.value

        for key, value in data.items():
            if hasattr(wo, key) and key not in ('id', 'work_order_id', 'created_at'):
                if key == 'status' and isinstance(value, str):
                    value = WorkOrderStatus(value)
                setattr(wo, key, value)

        wo.updated_at = datetime.utcnow()
        wo.updated_by = data.get('updated_by', 'system')
        self.session.flush()

        logger.info(f"Updated work order: {work_order_id}")

        # Emit WebSocket event for work order update
        work_order_data = wo.to_dict()
        event_data = {
            'work_order_id': work_order_id,
            'updated_at': datetime.utcnow().isoformat(),
            'updated_by': data.get('updated_by', 'system'),
            'work_order': work_order_data,
        }

        # Emit specific status change event if status changed
        if new_status and old_status != new_status:
            event_data['old_status'] = old_status
            event_data['new_status'] = new_status
            _emit_work_order_event('work_order_status_changed', event_data)
        else:
            _emit_work_order_event('work_order_updated', event_data)

        return work_order_data

    def release_work_order(self, work_order_id: str, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """
        Release a work order for production.

        This method:
        1. Generates operations from routing if none exist
        2. Creates a job for the scheduler with proper machine assignment
        3. Updates work order status to RELEASED
        """
        from models.mes.work_orders import WorkOrder, WorkOrderStatus, Job, Operation
        from datetime import timedelta

        wo = self.session.query(WorkOrder).filter(
            WorkOrder.work_order_id == work_order_id
        ).first()

        if not wo:
            return None

        # Check if operations exist, if not try to generate from routing
        existing_ops = self.session.query(Operation).filter(
            Operation.work_order_id == wo.id
        ).count()

        if existing_ops == 0 and wo.product_id:
            # Try to get routing from product
            product_info = self._get_lego_product_info(wo.product_id)
            if product_info and product_info.get('routing_id'):
                routing_id = product_info['routing_id']
                ops_created = self._generate_operations_from_routing(
                    work_order=wo,
                    routing_id=routing_id,
                    quantity=wo.quantity_ordered or 1
                )
                logger.info(f"Generated {ops_created} operations from routing {routing_id} for work order {work_order_id}")
                self.session.flush()  # Ensure operations are persisted

        # Update status to released
        result = self.update_work_order(work_order_id, {
            'status': WorkOrderStatus.RELEASED,
            'updated_by': user_id
        })

        if not result:
            return None

        # Check if jobs already exist for this work order
        existing_jobs = self.session.query(Job).filter(
            Job.work_order_id == wo.id
        ).count()

        if existing_jobs == 0:
            # Auto-create one job per physical-machine operation
            now = datetime.utcnow()
            cursor = now + timedelta(minutes=30)  # First job starts 30min from now

            # Get all operations ordered by sequence
            operations = self.session.query(Operation).filter(
                Operation.work_order_id == wo.id
            ).order_by(Operation.sequence).all()

            created_jobs = []
            for op in operations:
                # Skip software/virtual machine operations — add their time as a gap
                if op.machine_id == 'software':
                    gap_minutes = (op.setup_time or 0) + (op.run_time or 0)
                    cursor += timedelta(minutes=gap_minutes)
                    continue

                # Create a job for this physical-machine operation
                op_duration = (op.setup_time or 0) + (op.run_time or 0)
                scheduled_start = cursor
                scheduled_end = cursor + timedelta(minutes=max(op_duration, 1))

                job_data = {
                    'machine_id': op.machine_id,
                    'operation_id': op.id,
                    'scheduled_start': scheduled_start,
                    'scheduled_end': scheduled_end,
                    'quantity_planned': wo.quantity_ordered or 1,
                    'priority_score': wo.priority or 5,
                    'created_by': user_id,
                    'runtime_data': {
                        'eligible_machines': op.eligible_machines or [],
                        'operation_name': op.name,
                        'operation_type': op.operation_type.value if op.operation_type else None,
                        'operation_id': op.operation_id,
                    },
                }

                job = Job(
                    job_id=f"JOB-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
                    work_order_id=wo.id,
                    operation_id=op.id,
                    machine_id=job_data['machine_id'],
                    scheduled_start=job_data['scheduled_start'],
                    scheduled_end=job_data['scheduled_end'],
                    quantity_planned=job_data['quantity_planned'],
                    priority_score=job_data['priority_score'],
                    runtime_data=job_data['runtime_data'],
                    created_by=job_data['created_by'],
                )
                self.session.add(job)
                created_jobs.append(job)
                logger.info(f"Created job {job.job_id} for operation {op.name} on {op.machine_id}")

                # Next job starts when this one ends
                cursor = scheduled_end

            self.session.flush()

            if created_jobs:
                result['jobs'] = [j.to_dict() for j in created_jobs]
                logger.info(f"Auto-created {len(created_jobs)} jobs for released work order {work_order_id}")
            else:
                # Fallback: create a single job if no operations found
                machine_id = self._get_default_machine_for_product(wo.product_id) if wo.product_id else 'bambu-ps1'
                estimated_duration = self._estimate_work_order_duration(wo.id)
                job_data = {
                    'machine_id': machine_id,
                    'scheduled_start': cursor,
                    'scheduled_end': cursor + timedelta(hours=estimated_duration),
                    'quantity_planned': wo.quantity_ordered or 1,
                    'priority_score': wo.priority or 5,
                    'created_by': user_id,
                }
                job = self.create_job(work_order_id, job_data)
                if job:
                    result['job'] = job

        # Explicit commit to ensure all changes are persisted
        self.session.commit()

        return result

    def _estimate_work_order_duration(self, work_order_uuid) -> float:
        """Estimate total duration in hours for a work order based on operations."""
        from models.mes.work_orders import Operation

        operations = self.session.query(Operation).filter(
            Operation.work_order_id == work_order_uuid
        ).all()

        if not operations:
            return 2.0  # Default 2 hours

        total_minutes = sum(
            (op.setup_time or 0) + (op.run_time or 0) + (op.teardown_time or 0)
            for op in operations
        )

        return max(total_minutes / 60, 0.5)  # At least 30 minutes

    def _get_first_operation_machine(self, work_order_uuid) -> Optional[str]:
        """Get machine ID from the first operation of a work order."""
        from models.mes.work_orders import Operation

        first_op = self.session.query(Operation).filter(
            Operation.work_order_id == work_order_uuid
        ).order_by(Operation.sequence).first()

        return first_op.machine_id if first_op else None

    def _load_machines_config(self) -> List[Dict[str, Any]]:
        """Load machines configuration from JSON file."""
        import json
        import os

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'config', 'machines.json'
        )

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get('machines', [])
        except Exception as e:
            logger.warning(f"Could not load machines config: {e}")
            return []

    def _get_machines_by_capability(self, required_capabilities: List[str]) -> List[Dict[str, Any]]:
        """
        Get machines that have all required capabilities.

        Args:
            required_capabilities: List of capability strings to match

        Returns:
            List of machine configs that have all required capabilities
        """
        machines = self._load_machines_config()
        matching = []

        for machine in machines:
            if not machine.get('enabled', True):
                continue

            machine_caps = set(machine.get('capabilities', []))
            required_set = set(required_capabilities)

            # Check if machine has all required capabilities
            if required_set.issubset(machine_caps):
                matching.append(machine)

        return matching

    def _get_default_machine_for_product(self, product_id: str) -> str:
        """
        Get default machine based on product material type and capabilities.

        Returns:
            Machine ID string (e.g., 'bambu-ps1' for FDM, 'bantam-explorer' for CNC)
        """
        if not product_id:
            return 'bambu-ps1'  # Default to FDM printer

        product_info = self._get_lego_product_info(product_id)
        if product_info:
            material_code = product_info.get('material_code', '')

            # Determine required capabilities based on material
            required_capabilities = []

            # Metal materials need CNC milling
            if material_code in ('ALU', 'BRS', 'SST'):
                required_capabilities = ['cnc_milling']
                # Add material-specific capability
                material_map = {'ALU': 'aluminum', 'BRS': 'brass', 'SST': 'steel'}
                if material_code in material_map:
                    required_capabilities.append(material_map[material_code])
            # SLA resin
            elif material_code == 'RES':
                required_capabilities = ['sla_printing']
            # FDM plastics
            else:
                required_capabilities = ['fdm_printing']
                # Add material-specific capability
                material_map = {'ABS': 'abs', 'PLA': 'pla', 'PETG': 'petg', 'TPU': 'tpu', 'PA': 'pa'}
                if material_code in material_map:
                    required_capabilities.append(material_map[material_code])

            # Find matching machines
            if required_capabilities:
                matching_machines = self._get_machines_by_capability(required_capabilities)
                if matching_machines:
                    # Return first matching machine (could add priority/availability logic)
                    return matching_machines[0]['machine_id']

                # Fallback: try with just the process capability (not material specific)
                process_caps = [c for c in required_capabilities if c in ('cnc_milling', 'fdm_printing', 'sla_printing')]
                if process_caps:
                    matching_machines = self._get_machines_by_capability(process_caps)
                    if matching_machines:
                        return matching_machines[0]['machine_id']

            # Legacy fallback based on material
            if material_code in ('ALU', 'BRS', 'SST'):
                return 'bantam-explorer'
            elif material_code == 'RES':
                return 'formlabs-3'
            else:
                return 'bambu-ps1'

        return 'bambu-ps1'  # Default fallback

    def start_work_order(self, work_order_id: str, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Start a work order."""
        from models.mes.work_orders import WorkOrderStatus

        return self.update_work_order(work_order_id, {
            'status': WorkOrderStatus.IN_PROGRESS,
            'actual_start': datetime.utcnow(),
            'updated_by': user_id
        })

    def complete_work_order(self, work_order_id: str, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Complete a work order."""
        from models.mes.work_orders import WorkOrderStatus

        return self.update_work_order(work_order_id, {
            'status': WorkOrderStatus.COMPLETED,
            'actual_end': datetime.utcnow(),
            'updated_by': user_id
        })

    def hold_work_order(self, work_order_id: str, reason: str = None, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Put a work order on hold."""
        from models.mes.work_orders import WorkOrder, WorkOrderStatus

        wo = self.session.query(WorkOrder).filter(
            WorkOrder.work_order_id == work_order_id
        ).first()

        if not wo:
            return None

        # Can only hold released or in_progress work orders
        if wo.status not in (WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS):
            raise ValueError(f"Cannot hold work order with status '{wo.status.value}'")

        # Store the previous status so we can resume to it
        previous_status = wo.status.value

        # Update metadata with hold info
        metadata = wo.metadata or {}
        metadata['hold_reason'] = reason
        metadata['hold_timestamp'] = datetime.utcnow().isoformat()
        metadata['status_before_hold'] = previous_status

        return self.update_work_order(work_order_id, {
            'status': WorkOrderStatus.ON_HOLD,
            'metadata': metadata,
            'updated_by': user_id
        })

    def resume_work_order(self, work_order_id: str, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Resume a held work order."""
        from models.mes.work_orders import WorkOrder, WorkOrderStatus

        wo = self.session.query(WorkOrder).filter(
            WorkOrder.work_order_id == work_order_id
        ).first()

        if not wo:
            return None

        # Can only resume held work orders
        if wo.status != WorkOrderStatus.ON_HOLD:
            raise ValueError(f"Cannot resume work order with status '{wo.status.value}'")

        # Get the status before hold
        metadata = wo.metadata or {}
        previous_status = metadata.get('status_before_hold', 'in_progress')

        # Clear hold info from metadata
        metadata.pop('hold_reason', None)
        metadata.pop('hold_timestamp', None)
        metadata.pop('status_before_hold', None)

        return self.update_work_order(work_order_id, {
            'status': WorkOrderStatus(previous_status),
            'metadata': metadata,
            'updated_by': user_id
        })

    def cancel_work_order(self, work_order_id: str, reason: str = None, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Cancel a work order."""
        from models.mes.work_orders import WorkOrder, WorkOrderStatus

        wo = self.session.query(WorkOrder).filter(
            WorkOrder.work_order_id == work_order_id
        ).first()

        if not wo:
            return None

        # Cannot cancel completed work orders
        if wo.status == WorkOrderStatus.COMPLETED:
            raise ValueError("Cannot cancel a completed work order")

        # Update metadata with cancellation info
        metadata = wo.metadata or {}
        metadata['cancel_reason'] = reason
        metadata['cancel_timestamp'] = datetime.utcnow().isoformat()

        return self.update_work_order(work_order_id, {
            'status': WorkOrderStatus.CANCELLED,
            'metadata': metadata,
            'updated_by': user_id
        })

    def get_operations(self, work_order_id: str) -> List[Dict[str, Any]]:
        """Get operations for a work order."""
        from models.mes.work_orders import WorkOrder, Operation

        wo = self.session.query(WorkOrder).filter(
            WorkOrder.work_order_id == work_order_id
        ).first()

        if not wo:
            return []

        operations = self.session.query(Operation).filter(
            Operation.work_order_id == wo.id
        ).order_by(Operation.sequence).all()

        return [op.to_dict() for op in operations]

    def start_operation(self, operation_id: str, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Start an operation."""
        from models.mes.work_orders import Operation

        op = self.session.query(Operation).filter(
            Operation.operation_id == operation_id
        ).first()

        if not op:
            return None

        op.status = 'running'
        op.actual_start = datetime.utcnow()
        op.updated_at = datetime.utcnow()
        self.session.flush()

        logger.info(f"Started operation: {operation_id}")

        # Emit WebSocket event
        op_data = op.to_dict()
        _emit_work_order_event('operation_started', {
            'operation_id': operation_id,
            'started_at': datetime.utcnow().isoformat(),
            'started_by': user_id,
            'operation': op_data,
        })

        return op_data

    def complete_operation(self, operation_id: str, user_id: str = 'system', quantity_completed: int = None, quantity_defective: int = None) -> Optional[Dict[str, Any]]:
        """Complete an operation."""
        from models.mes.work_orders import Operation

        op = self.session.query(Operation).filter(
            Operation.operation_id == operation_id
        ).first()

        if not op:
            return None

        op.status = 'completed'
        op.actual_end = datetime.utcnow()
        op.updated_at = datetime.utcnow()

        if quantity_completed is not None:
            op.quantity_completed = quantity_completed
        if quantity_defective is not None:
            op.quantity_defective = quantity_defective

        self.session.flush()

        logger.info(f"Completed operation: {operation_id}")

        # Emit WebSocket event
        op_data = op.to_dict()
        _emit_work_order_event('operation_completed', {
            'operation_id': operation_id,
            'completed_at': datetime.utcnow().isoformat(),
            'completed_by': user_id,
            'operation': op_data,
        })

        return op_data

    def record_operation_time(self, operation_id: str, duration_minutes: int, user_id: str = 'system', notes: str = None) -> Optional[Dict[str, Any]]:
        """Record time spent on an operation."""
        from models.mes.work_orders import Operation

        op = self.session.query(Operation).filter(
            Operation.operation_id == operation_id
        ).first()

        if not op:
            return None

        # Update actual duration
        op.actual_duration = (op.actual_duration or 0) + duration_minutes
        op.updated_at = datetime.utcnow()

        # Add time entry to metadata
        metadata = op.metadata or {}
        time_entries = metadata.get('time_entries', [])
        time_entries.append({
            'duration_minutes': duration_minutes,
            'recorded_at': datetime.utcnow().isoformat(),
            'recorded_by': user_id,
            'notes': notes,
        })
        metadata['time_entries'] = time_entries
        op.metadata = metadata

        self.session.flush()

        logger.info(f"Recorded {duration_minutes} minutes for operation: {operation_id}")
        return op.to_dict()

    def add_operation(self, work_order_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add an operation to a work order."""
        from models.mes.work_orders import WorkOrder, Operation, OperationType

        wo = self.session.query(WorkOrder).filter(
            WorkOrder.work_order_id == work_order_id
        ).first()

        if not wo:
            return None

        operation = Operation(
            work_order_id=wo.id,
            operation_id=data.get('operation_id', f"OP-{uuid.uuid4().hex[:6].upper()}"),
            sequence=data.get('sequence', 10),
            operation_type=OperationType(data.get('operation_type', 'custom')),
            name=data['name'],
            description=data.get('description'),
            work_center_id=data.get('work_center_id'),
            machine_id=data.get('machine_id'),
            setup_time=data.get('setup_time', 0),
            run_time=data.get('run_time', 0),
            teardown_time=data.get('teardown_time', 0),
            parameters=data.get('parameters', {}),
        )

        self.session.add(operation)
        self.session.flush()
        return operation.to_dict()

    def create_job(self, work_order_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a job for a work order."""
        from models.mes.work_orders import WorkOrder, Job

        wo = self.session.query(WorkOrder).filter(
            WorkOrder.work_order_id == work_order_id
        ).first()

        if not wo:
            return None

        job = Job(
            job_id=data.get('job_id', f"JOB-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"),
            work_order_id=wo.id,
            machine_id=data.get('machine_id'),
            scheduled_start=data.get('scheduled_start'),
            scheduled_end=data.get('scheduled_end'),
            quantity_planned=data.get('quantity_planned', 1),
            priority_score=data.get('priority_score', 0),
            assigned_worker_id=data.get('assigned_worker_id'),
            gcode_file=data.get('gcode_file'),
            gcode_hash=data.get('gcode_hash'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(job)
        self.session.flush()

        logger.info(f"Created job: {job.job_id} for work order: {work_order_id}")
        return job.to_dict()

    def get_jobs(
        self,
        machine_id: str = None,
        status: str = None,
        work_order_id: str = None,
        limit: int = 100,
        scheduled_only: bool = False,
        date_from: datetime = None,
        date_to: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Get jobs with filtering.

        Args:
            machine_id: Filter by machine
            status: Filter by status
            work_order_id: Filter by work order
            limit: Maximum results to return
            scheduled_only: If True, only return jobs with valid scheduled_start
            date_from: Filter jobs scheduled on or after this date
            date_to: Filter jobs scheduled on or before this date
        """
        from models.mes.work_orders import Job, JobStatus, WorkOrder

        query = self.session.query(Job).filter(Job.is_deleted == False)

        if machine_id:
            query = query.filter(Job.machine_id == machine_id)
        if status:
            query = query.filter(Job.status == JobStatus(status))
        if work_order_id:
            wo = self.session.query(WorkOrder).filter(
                WorkOrder.work_order_id == work_order_id
            ).first()
            if wo:
                query = query.filter(Job.work_order_id == wo.id)

        # Filter for scheduled jobs (for Gantt chart)
        if scheduled_only:
            query = query.filter(Job.scheduled_start.isnot(None))
            query = query.filter(Job.scheduled_end.isnot(None))

        # Date range filters
        if date_from:
            query = query.filter(Job.scheduled_start >= date_from)
        if date_to:
            query = query.filter(Job.scheduled_start <= date_to)

        jobs = query.order_by(Job.scheduled_start).limit(limit).all()

        # Enrich job data with work order info for Gantt chart display
        result = []
        for j in jobs:
            job_dict = j.to_dict()
            # Add work order data for Gantt chart
            if j.work_order:
                # Build display name: operation name + product or just product
                op_name = job_dict.get('operation_name') or ''
                product_id = j.work_order.product_id or 'Unknown Product'
                job_dict['product'] = f"{op_name} - {product_id}" if op_name else product_id
                job_dict['qty'] = j.quantity_planned or j.work_order.quantity_ordered
                job_dict['due_date'] = j.work_order.due_date.isoformat() if j.work_order.due_date else None
                job_dict['priority'] = j.work_order.priority
                # Override work_order_id with human-readable version (JS expects this)
                job_dict['work_order_id'] = j.work_order.work_order_id
            else:
                job_dict['product'] = job_dict.get('operation_name') or 'Unknown Product'
                job_dict['qty'] = j.quantity_planned
                job_dict['due_date'] = None
                job_dict['priority'] = 5
            result.append(job_dict)

        return result

    def update_job_status(self, job_id: str, status: str, user_id: str = 'system') -> Optional[Dict[str, Any]]:
        """Update job status."""
        from models.mes.work_orders import Job, JobStatus

        job = self.session.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return None

        old_status = job.status.value if job.status else None
        job.status = JobStatus(status)
        job.updated_at = datetime.utcnow()
        job.updated_by = user_id

        if status == 'running' and not job.actual_start:
            job.actual_start = datetime.utcnow()
        elif status in ('completed', 'failed', 'cancelled'):
            job.actual_end = datetime.utcnow()

        self.session.flush()

        # Emit WebSocket event for job status change
        job_data = job.to_dict()
        event_data = {
            'job_id': job_id,
            'old_status': old_status,
            'new_status': status,
            'updated_at': datetime.utcnow().isoformat(),
            'updated_by': user_id,
            'job': job_data,
        }

        # Emit specific event for job completion
        if status == 'completed':
            _emit_work_order_event('job_completed', event_data)
        elif status == 'failed':
            _emit_work_order_event('job_failed', event_data)
        else:
            _emit_work_order_event('job_status_changed', event_data)

        return job_data


def get_work_order_service(session: Session = None) -> WorkOrderService:
    """Get work order service instance."""
    if session:
        return WorkOrderService(session)
    with get_db_session() as session:
        return WorkOrderService(session)
