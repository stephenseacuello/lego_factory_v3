"""
LEGO Factory v3 - Genealogy Service
=====================================
Product genealogy and traceability for MESA-11 Product Tracking & Genealogy.
Handles serial number generation, process step recording, and trace queries.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models.mes.genealogy import (
    ProductGenealogy, ProcessStep, LotTrace,
    GenealogyStatus, QualityResult
)

logger = logging.getLogger(__name__)


class GenealogyService:
    """
    Service for managing product genealogy and traceability.

    Responsibilities:
    - Create product records with serial numbers
    - Record process steps
    - Track material consumption
    - Support forward/backward tracing
    """

    def __init__(self, session: Session):
        self.session = session

    # =========================================================================
    # Product Genealogy
    # =========================================================================

    def create_product_record(
        self,
        work_order_id: str,
        product_id: str,
        product_name: Optional[str] = None,
        batch_number: Optional[str] = None,
        serial_prefix: str = 'SN'
    ) -> ProductGenealogy:
        """
        Create a new product genealogy record.

        Args:
            work_order_id: Associated work order
            product_id: Product identifier
            product_name: Human-readable product name
            batch_number: Batch/lot number for this run
            serial_prefix: Prefix for serial number generation

        Returns:
            Created ProductGenealogy
        """
        # Generate unique serial number
        serial_number = self._generate_serial_number(serial_prefix, product_id)

        genealogy = ProductGenealogy(
            serial_number=serial_number,
            batch_number=batch_number,
            work_order_id=work_order_id if isinstance(work_order_id, uuid.UUID) else uuid.UUID(work_order_id),
            product_id=product_id,
            product_name=product_name,
            status=GenealogyStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
        )

        self.session.add(genealogy)
        self.session.flush()

        logger.info(f"Created genealogy record: {serial_number} for WO {work_order_id}")

        return genealogy

    def get_product_by_serial(self, serial_number: str) -> Optional[ProductGenealogy]:
        """Get product genealogy by serial number."""
        return self.session.query(ProductGenealogy).filter(
            ProductGenealogy.serial_number == serial_number
        ).first()

    def complete_product(
        self,
        serial_number: str,
        quality_result: str = 'passed',
        quality_score: Optional[float] = None,
        location: Optional[str] = None
    ) -> Optional[ProductGenealogy]:
        """
        Mark a product as completed.

        Args:
            serial_number: Product serial number
            quality_result: Final quality result
            quality_score: Overall quality score (0-100)
            location: Current location

        Returns:
            Updated ProductGenealogy or None if not found
        """
        genealogy = self.get_product_by_serial(serial_number)
        if not genealogy:
            return None

        genealogy.status = GenealogyStatus.COMPLETED
        genealogy.completed_at = datetime.utcnow()
        genealogy.overall_quality = QualityResult(quality_result)
        genealogy.quality_score = quality_score
        genealogy.current_location = location

        self.session.flush()

        logger.info(f"Completed product: {serial_number}")

        return genealogy

    # =========================================================================
    # Process Steps
    # =========================================================================

    def record_process_step(
        self,
        serial_number: str,
        operation_id: str,
        operation_name: str,
        sequence: int,
        machine_id: str,
        worker_id: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        parameters: Optional[Dict] = None,
        actuals: Optional[Dict] = None,
        quality_result: str = 'pending',
        defects: Optional[List[str]] = None,
    ) -> Optional[ProcessStep]:
        """
        Record a process step for a product.

        Args:
            serial_number: Product serial number
            operation_id: Operation identifier
            operation_name: Operation name
            sequence: Step sequence number
            machine_id: Machine used
            worker_id: Operator ID
            started_at: Step start time
            completed_at: Step completion time
            parameters: Recipe parameters used
            actuals: Actual measured values
            quality_result: Quality inspection result
            defects: List of defects found

        Returns:
            Created ProcessStep or None if product not found
        """
        genealogy = self.get_product_by_serial(serial_number)
        if not genealogy:
            logger.warning(f"Genealogy not found for serial: {serial_number}")
            return None

        # Calculate duration if both times provided
        actual_duration = None
        if started_at and completed_at:
            actual_duration = (completed_at - started_at).total_seconds() / 60

        step = ProcessStep(
            genealogy_id=genealogy.id,
            operation_id=operation_id,
            operation_name=operation_name,
            sequence=sequence,
            machine_id=machine_id,
            worker_id=worker_id,
            started_at=started_at or datetime.utcnow(),
            completed_at=completed_at,
            actual_duration_mins=actual_duration,
            parameters=parameters or {},
            actuals=actuals or {},
            quality_result=QualityResult(quality_result),
            defects_found=defects or [],
        )

        self.session.add(step)
        self.session.flush()

        logger.info(f"Recorded process step {sequence} for {serial_number}: {operation_name}")

        return step

    def get_process_steps(self, serial_number: str) -> List[Dict[str, Any]]:
        """Get all process steps for a product."""
        genealogy = self.get_product_by_serial(serial_number)
        if not genealogy:
            return []

        steps = self.session.query(ProcessStep).filter(
            ProcessStep.genealogy_id == genealogy.id
        ).order_by(ProcessStep.sequence).all()

        return [s.to_dict() for s in steps]

    # =========================================================================
    # Material Tracing
    # =========================================================================

    def record_material_consumption(
        self,
        serial_number: str,
        lot_id: str,
        job_id: str,
        quantity: float,
        unit: str = 'g',
        transformation_type: str = 'consumed'
    ) -> Optional[LotTrace]:
        """
        Record material lot consumption for a product.

        Args:
            serial_number: Output product serial number
            lot_id: Source material lot ID
            job_id: Job that consumed the material
            quantity: Quantity consumed
            unit: Unit of measure
            transformation_type: Type of transformation

        Returns:
            Created LotTrace or None
        """
        genealogy = self.get_product_by_serial(serial_number)
        if not genealogy:
            return None

        trace = LotTrace(
            lot_id=lot_id if isinstance(lot_id, uuid.UUID) else uuid.UUID(lot_id),
            consumed_by_job_id=job_id,
            work_order_id=str(genealogy.work_order_id),
            output_genealogy_id=genealogy.id,
            quantity_consumed=quantity,
            unit_of_measure=unit,
            transformation_type=transformation_type,
            consumed_at=datetime.utcnow(),
        )

        self.session.add(trace)
        self.session.flush()

        return trace

    # =========================================================================
    # Traceability Queries
    # =========================================================================

    def trace_forward(self, lot_number: str) -> Dict[str, Any]:
        """
        Forward trace: lot -> jobs -> products -> downstream.

        Shows what products were made from a given material lot.

        Args:
            lot_number: Material lot number to trace

        Returns:
            Trace tree dict
        """
        from models.mes.resources import MaterialLot

        # Find the lot
        lot = self.session.query(MaterialLot).filter(
            MaterialLot.lot_number == lot_number
        ).first()

        if not lot:
            return {'error': 'Lot not found', 'lot_number': lot_number}

        # Get all traces from this lot
        traces = self.session.query(LotTrace).filter(
            LotTrace.lot_id == lot.id
        ).all()

        # Build trace tree
        products = []
        for trace in traces:
            if trace.output_genealogy:
                products.append({
                    'serial_number': trace.output_genealogy.serial_number,
                    'product_id': trace.output_genealogy.product_id,
                    'product_name': trace.output_genealogy.product_name,
                    'status': trace.output_genealogy.status.value,
                    'quality': trace.output_genealogy.overall_quality.value if trace.output_genealogy.overall_quality else None,
                    'quantity_used': trace.quantity_consumed,
                    'job_id': trace.consumed_by_job_id,
                    'consumed_at': trace.consumed_at.isoformat() if trace.consumed_at else None,
                })

        return {
            'lot_number': lot_number,
            'material_type': lot.material_type,
            'supplier': lot.supplier,
            'quantity_received': lot.quantity_received,
            'quantity_consumed': lot.quantity_consumed,
            'products_made': products,
            'product_count': len(products),
        }

    def trace_backward(self, serial_number: str) -> Dict[str, Any]:
        """
        Backward trace: product -> process steps -> input lots -> suppliers.

        Shows all inputs and operations that went into a product.

        Args:
            serial_number: Product serial number

        Returns:
            Trace tree dict
        """
        genealogy = self.get_product_by_serial(serial_number)
        if not genealogy:
            return {'error': 'Product not found', 'serial_number': serial_number}

        # Get process steps
        steps = self.session.query(ProcessStep).filter(
            ProcessStep.genealogy_id == genealogy.id
        ).order_by(ProcessStep.sequence).all()

        # Get material traces
        traces = self.session.query(LotTrace).filter(
            LotTrace.output_genealogy_id == genealogy.id
        ).all()

        # Build input lots info
        input_lots = []
        for trace in traces:
            if trace.lot:
                input_lots.append({
                    'lot_number': trace.lot.lot_number,
                    'material_type': trace.lot.material_type,
                    'supplier': trace.lot.supplier,
                    'supplier_lot': trace.lot.supplier_lot,
                    'quantity_used': trace.quantity_consumed,
                    'received_date': trace.lot.received_date.isoformat() if trace.lot.received_date else None,
                })

        return {
            'serial_number': serial_number,
            'product_id': genealogy.product_id,
            'product_name': genealogy.product_name,
            'status': genealogy.status.value,
            'started_at': genealogy.started_at.isoformat() if genealogy.started_at else None,
            'completed_at': genealogy.completed_at.isoformat() if genealogy.completed_at else None,
            'quality': genealogy.overall_quality.value if genealogy.overall_quality else None,
            'process_steps': [s.to_dict() for s in steps],
            'input_materials': input_lots,
            'work_order_id': str(genealogy.work_order_id) if genealogy.work_order_id else None,
        }

    def get_genealogy_tree(self, serial_number: str) -> Dict[str, Any]:
        """
        Get full genealogy tree for D3.js visualization.

        Returns hierarchical structure suitable for tree diagram.
        """
        backward = self.trace_backward(serial_number)
        if 'error' in backward:
            return backward

        # Build tree structure
        nodes = []
        edges = []

        # Root node (the product)
        product_node = {
            'id': serial_number,
            'type': 'product',
            'label': backward['product_name'] or backward['product_id'],
            'status': backward['status'],
            'quality': backward.get('quality'),
        }
        nodes.append(product_node)

        # Process step nodes
        for step in backward.get('process_steps', []):
            step_id = f"step_{step['sequence']}"
            nodes.append({
                'id': step_id,
                'type': 'operation',
                'label': step['operation_name'],
                'machine': step['machine_id'],
                'quality': step.get('quality_result'),
            })
            edges.append({
                'source': step_id,
                'target': serial_number,
                'type': 'produces',
            })

        # Material lot nodes
        for lot in backward.get('input_materials', []):
            lot_id = f"lot_{lot['lot_number']}"
            nodes.append({
                'id': lot_id,
                'type': 'material',
                'label': f"{lot['material_type']} - {lot['lot_number']}",
                'supplier': lot['supplier'],
            })
            # Connect to first process step
            if backward.get('process_steps'):
                edges.append({
                    'source': lot_id,
                    'target': f"step_{backward['process_steps'][0]['sequence']}",
                    'type': 'consumed',
                    'quantity': lot['quantity_used'],
                })

        return {
            'serial_number': serial_number,
            'nodes': nodes,
            'edges': edges,
            'metadata': {
                'product_id': backward['product_id'],
                'work_order_id': backward.get('work_order_id'),
            }
        }

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _generate_serial_number(self, prefix: str, product_id: str) -> str:
        """Generate unique serial number."""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"{prefix}-{product_id[:10]}-{timestamp}-{unique_id}"


# =============================================================================
# Module-level convenience functions
# =============================================================================

def create_product_record(session: Session, work_order_id: str, product_id: str, **kwargs) -> ProductGenealogy:
    """Create a product genealogy record."""
    service = GenealogyService(session)
    return service.create_product_record(work_order_id, product_id, **kwargs)


def record_process_step(session: Session, serial_number: str, **kwargs) -> Optional[ProcessStep]:
    """Record a process step."""
    service = GenealogyService(session)
    return service.record_process_step(serial_number, **kwargs)


def trace_forward(session: Session, lot_number: str) -> Dict[str, Any]:
    """Forward trace from lot to products."""
    service = GenealogyService(session)
    return service.trace_forward(lot_number)


def trace_backward(session: Session, serial_number: str) -> Dict[str, Any]:
    """Backward trace from product to inputs."""
    service = GenealogyService(session)
    return service.trace_backward(serial_number)
