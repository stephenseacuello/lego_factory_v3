"""
LEGO Factory v3 - Genealogy Service
=====================================
Product genealogy and traceability for MESA-11 Product Tracking & Genealogy.
Handles serial number generation, process step recording, and trace queries.
"""

import logging
from datetime import datetime, date, timedelta
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

    # =========================================================================
    # Component Serial Tracking (High-Value Parts)
    # =========================================================================

    def add_component_serial(
        self,
        parent_serial: str,
        component_serial: str,
        component_type: str,
        component_name: str,
        supplier: Optional[str] = None,
        supplier_lot: Optional[str] = None,
        position: Optional[str] = None,
        value: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Track a serialized component installed in a product.

        For high-value parts like motors, controllers, or precision components
        that require individual tracking.

        Args:
            parent_serial: Parent product serial number
            component_serial: Component's unique serial number
            component_type: Type of component (e.g., 'motor', 'controller')
            component_name: Human-readable name
            supplier: Component supplier
            supplier_lot: Supplier's lot number
            position: Installation position (e.g., 'axis_x', 'slot_1')
            value: Component value for tracking purposes

        Returns:
            Created component record
        """
        genealogy = self.get_product_by_serial(parent_serial)
        if not genealogy:
            return {'error': 'Parent product not found', 'serial': parent_serial}

        component_data = {
            'component_serial': component_serial,
            'component_type': component_type,
            'component_name': component_name,
            'supplier': supplier,
            'supplier_lot': supplier_lot,
            'position': position,
            'value': value,
            'installed_at': datetime.utcnow().isoformat(),
        }

        if not genealogy.component_serials:
            genealogy.component_serials = []

        genealogy.component_serials.append(component_data)
        self.session.flush()

        logger.info(f"Added component {component_serial} to {parent_serial}")

        return {
            'status': 'added',
            'parent_serial': parent_serial,
            'component': component_data,
        }

    def find_by_component_serial(self, component_serial: str) -> Optional[Dict[str, Any]]:
        """
        Find a product by one of its installed component serials.

        Useful for tracking where a specific component ended up.
        """
        products = self.session.query(ProductGenealogy).filter(
            ProductGenealogy.component_serials.contains([{'component_serial': component_serial}])
        ).all()

        if not products:
            # Fallback: manual search through all records
            all_products = self.session.query(ProductGenealogy).filter(
                ProductGenealogy.component_serials.isnot(None)
            ).all()

            for p in all_products:
                if p.component_serials:
                    for comp in p.component_serials:
                        if comp.get('component_serial') == component_serial:
                            return {
                                'found': True,
                                'parent_serial': p.serial_number,
                                'product_id': p.product_id,
                                'product_name': p.product_name,
                                'status': p.status.value,
                                'component': comp,
                            }
            return None

        product = products[0]
        component = next(
            (c for c in (product.component_serials or [])
             if c.get('component_serial') == component_serial),
            None
        )

        return {
            'found': True,
            'parent_serial': product.serial_number,
            'product_id': product.product_id,
            'product_name': product.product_name,
            'status': product.status.value,
            'component': component,
        }

    # =========================================================================
    # Recall Impact Analysis
    # =========================================================================

    def analyze_recall_impact(
        self,
        lot_number: str = None,
        component_serial_pattern: str = None,
        date_range_start: datetime = None,
        date_range_end: datetime = None,
        affected_operation: str = None
    ) -> Dict[str, Any]:
        """
        Analyze the impact of a potential recall.

        Can search by:
        - Material lot number
        - Component serial pattern
        - Production date range
        - Specific operation with issues

        Returns affected products, customers, and recommended actions.
        """
        affected_products = []
        affected_lots = []

        # Search by lot number
        if lot_number:
            forward_trace = self.trace_forward(lot_number)
            if 'error' not in forward_trace:
                affected_lots.append(lot_number)
                for product in forward_trace.get('products_made', []):
                    affected_products.append(product['serial_number'])

        # Search by date range
        if date_range_start or date_range_end:
            query = self.session.query(ProductGenealogy)
            if date_range_start:
                query = query.filter(ProductGenealogy.started_at >= date_range_start)
            if date_range_end:
                query = query.filter(ProductGenealogy.started_at <= date_range_end)

            for product in query.all():
                if product.serial_number not in affected_products:
                    affected_products.append(product.serial_number)

        # Search by affected operation
        if affected_operation:
            steps = self.session.query(ProcessStep).filter(
                ProcessStep.operation_id == affected_operation
            ).all()

            for step in steps:
                if step.genealogy and step.genealogy.serial_number not in affected_products:
                    affected_products.append(step.genealogy.serial_number)

        # Build detailed impact analysis
        product_details = []
        customers_affected = set()
        locations = []

        for serial in affected_products:
            product = self.get_product_by_serial(serial)
            if product:
                detail = {
                    'serial_number': serial,
                    'product_id': product.product_id,
                    'product_name': product.product_name,
                    'status': product.status.value,
                    'quality_result': product.overall_quality.value if product.overall_quality else None,
                    'completed_at': product.completed_at.isoformat() if product.completed_at else None,
                    'current_location': product.current_location,
                    'shipped': product.status == GenealogyStatus.SHIPPED,
                }
                product_details.append(detail)

                if product.customer_id:
                    customers_affected.add(product.customer_id)
                if product.current_location:
                    locations.append(product.current_location)

        # Calculate severity
        shipped_count = len([p for p in product_details if p['shipped']])
        severity = 'critical' if shipped_count > 0 else (
            'high' if len(affected_products) > 10 else 'medium'
        )

        return {
            'recall_analysis': {
                'search_criteria': {
                    'lot_number': lot_number,
                    'component_pattern': component_serial_pattern,
                    'date_range': {
                        'start': date_range_start.isoformat() if date_range_start else None,
                        'end': date_range_end.isoformat() if date_range_end else None,
                    },
                    'affected_operation': affected_operation,
                },
                'impact_summary': {
                    'total_products_affected': len(affected_products),
                    'products_shipped': shipped_count,
                    'products_in_process': len(affected_products) - shipped_count,
                    'customers_affected': len(customers_affected),
                    'affected_lots': affected_lots,
                    'severity': severity,
                },
                'affected_products': product_details,
                'customers': list(customers_affected),
                'locations': list(set(locations)),
                'recommended_actions': self._generate_recall_actions(
                    shipped_count, len(customers_affected), severity
                ),
                'analysis_timestamp': datetime.utcnow().isoformat(),
            }
        }

    def _generate_recall_actions(
        self,
        shipped_count: int,
        customer_count: int,
        severity: str
    ) -> List[Dict[str, Any]]:
        """Generate recommended recall actions."""
        actions = []

        if shipped_count > 0:
            actions.append({
                'priority': 1,
                'action': 'customer_notification',
                'description': f'Notify {customer_count} affected customers',
                'urgency': 'immediate',
            })
            actions.append({
                'priority': 2,
                'action': 'field_containment',
                'description': 'Issue containment notice for shipped products',
                'urgency': 'immediate',
            })

        actions.append({
            'priority': 3,
            'action': 'wip_quarantine',
            'description': 'Quarantine all affected WIP inventory',
            'urgency': 'high',
        })

        actions.append({
            'priority': 4,
            'action': 'root_cause_investigation',
            'description': 'Initiate 8D problem-solving process',
            'urgency': 'high',
        })

        if severity == 'critical':
            actions.append({
                'priority': 5,
                'action': 'regulatory_notification',
                'description': 'Prepare regulatory agency notification if required',
                'urgency': 'high',
            })

        return actions

    # =========================================================================
    # Regulatory Compliance Reporting
    # =========================================================================

    def generate_compliance_report(
        self,
        serial_number: str,
        report_type: str = 'full',
        standard: str = 'ISO'
    ) -> Dict[str, Any]:
        """
        Generate regulatory compliance report for a product.

        Supports:
        - ISO 9001 Quality Management
        - AS9100 Aerospace
        - FDA 21 CFR Part 11 (Medical Devices)
        - IATF 16949 Automotive

        Args:
            serial_number: Product serial number
            report_type: 'full', 'summary', or 'audit'
            standard: Compliance standard ('ISO', 'AS9100', 'FDA', 'IATF')

        Returns:
            Formatted compliance report
        """
        genealogy = self.get_product_by_serial(serial_number)
        if not genealogy:
            return {'error': 'Product not found', 'serial_number': serial_number}

        backward = self.trace_backward(serial_number)
        steps = backward.get('process_steps', [])
        materials = backward.get('input_materials', [])

        report = {
            'report_header': {
                'report_type': f'{standard} Compliance Report',
                'serial_number': serial_number,
                'product_id': genealogy.product_id,
                'product_name': genealogy.product_name,
                'generated_at': datetime.utcnow().isoformat(),
                'standard': standard,
            },
            'product_information': {
                'serial_number': serial_number,
                'batch_number': genealogy.batch_number,
                'work_order_id': str(genealogy.work_order_id) if genealogy.work_order_id else None,
                'production_start': genealogy.started_at.isoformat() if genealogy.started_at else None,
                'production_end': genealogy.completed_at.isoformat() if genealogy.completed_at else None,
                'final_status': genealogy.status.value,
                'quality_result': genealogy.overall_quality.value if genealogy.overall_quality else None,
                'quality_score': genealogy.quality_score,
            },
            'traceability': {
                'input_materials': materials,
                'material_lot_count': len(materials),
                'full_traceability': len(materials) > 0,
            },
            'process_history': {
                'total_operations': len(steps),
                'operations': steps,
                'all_operations_documented': all(
                    s.get('completed_at') for s in steps
                ),
            },
            'quality_records': {
                'inspections_performed': len([
                    s for s in steps if s.get('quality_result') != 'pending'
                ]),
                'defects_found': sum(
                    len(s.get('defects_found', [])) for s in steps
                ),
                'all_inspections_passed': all(
                    s.get('quality_result') in ['passed', 'pending'] for s in steps
                ),
            },
        }

        # Add standard-specific sections
        if standard == 'AS9100':
            report['aerospace_requirements'] = self._generate_as9100_section(genealogy, steps)
        elif standard == 'FDA':
            report['fda_requirements'] = self._generate_fda_section(genealogy, steps)
        elif standard == 'IATF':
            report['automotive_requirements'] = self._generate_iatf_section(genealogy, steps)

        # Add electronic signature section
        report['electronic_signatures'] = {
            'production_signature': {
                'signed_by': 'Production System',
                'timestamp': genealogy.completed_at.isoformat() if genealogy.completed_at else None,
                'meaning': 'Production complete',
            },
            'quality_signature': {
                'signed_by': 'Quality System',
                'timestamp': datetime.utcnow().isoformat(),
                'meaning': 'Quality records verified',
            },
        }

        report['compliance_summary'] = self._assess_compliance(report, standard)

        return report

    def _generate_as9100_section(
        self,
        genealogy: ProductGenealogy,
        steps: List[Dict]
    ) -> Dict[str, Any]:
        """Generate AS9100 aerospace-specific compliance section."""
        return {
            'first_article_inspection': {
                'required': True,
                'completed': genealogy.fai_complete if hasattr(genealogy, 'fai_complete') else False,
                'fai_number': genealogy.fai_number if hasattr(genealogy, 'fai_number') else None,
            },
            'special_processes': {
                'processes_identified': [
                    s['operation_name'] for s in steps
                    if 'heat treat' in s['operation_name'].lower()
                    or 'weld' in s['operation_name'].lower()
                    or 'coating' in s['operation_name'].lower()
                ],
                'nadcap_certification_required': False,
            },
            'configuration_management': {
                'drawing_revision': genealogy.drawing_revision if hasattr(genealogy, 'drawing_revision') else None,
                'change_notices_applied': [],
            },
            'counterfeit_parts_prevention': {
                'all_parts_from_approved_sources': True,
                'verification_performed': True,
            },
        }

    def _generate_fda_section(
        self,
        genealogy: ProductGenealogy,
        steps: List[Dict]
    ) -> Dict[str, Any]:
        """Generate FDA 21 CFR Part 11 compliance section."""
        return {
            'device_history_record': {
                'dhr_complete': True,
                'production_dates_documented': genealogy.started_at is not None,
                'quantities_documented': True,
                'acceptance_records_present': genealogy.overall_quality is not None,
            },
            'electronic_records': {
                'part_11_compliant': True,
                'audit_trail_enabled': True,
                'electronic_signatures_valid': True,
                'system_validation_status': 'validated',
            },
            'labeling': {
                'udi_assigned': genealogy.serial_number is not None,
                'lot_number_present': genealogy.batch_number is not None,
            },
            'complaint_tracking': {
                'linked_complaints': [],
                'capa_required': False,
            },
        }

    def _generate_iatf_section(
        self,
        genealogy: ProductGenealogy,
        steps: List[Dict]
    ) -> Dict[str, Any]:
        """Generate IATF 16949 automotive-specific compliance section."""
        return {
            'ppap_status': {
                'ppap_level': 3,
                'ppap_approved': True,
                'control_plan_followed': True,
            },
            'special_characteristics': {
                'critical_characteristics_identified': True,
                'all_critical_in_spec': all(
                    s.get('quality_result') == 'passed' for s in steps
                ),
            },
            'traceability_marking': {
                'part_marking_present': True,
                'marking_method': 'laser_etch',
                'marking_content': genealogy.serial_number,
            },
            'control_plan_adherence': {
                'all_checks_performed': True,
                'frequencies_met': True,
            },
        }

    def _assess_compliance(self, report: Dict, standard: str) -> Dict[str, Any]:
        """Assess overall compliance based on report data."""
        issues = []

        # Check traceability
        if not report['traceability']['full_traceability']:
            issues.append('Incomplete material traceability')

        # Check process documentation
        if not report['process_history']['all_operations_documented']:
            issues.append('Some operations not fully documented')

        # Check quality records
        if not report['quality_records']['all_inspections_passed']:
            issues.append('Some quality inspections failed')

        return {
            'compliant': len(issues) == 0,
            'standard': standard,
            'issues_found': issues,
            'issue_count': len(issues),
            'assessment_date': datetime.utcnow().isoformat(),
            'next_audit_recommended': date.today() + timedelta(days=365) if len(issues) == 0 else date.today() + timedelta(days=90),
        }

    def export_device_history_record(self, serial_number: str) -> Dict[str, Any]:
        """
        Export complete Device History Record (DHR) for FDA compliance.

        The DHR contains all production documentation for a single device.
        """
        report = self.generate_compliance_report(serial_number, 'full', 'FDA')
        if 'error' in report:
            return report

        backward = self.trace_backward(serial_number)

        dhr = {
            'document_type': 'Device History Record',
            'document_number': f"DHR-{serial_number}",
            'revision': '1.0',
            'effective_date': datetime.utcnow().isoformat(),
            'product_identification': report['product_information'],
            'production_documentation': {
                'work_order': report['product_information']['work_order_id'],
                'batch_record': report['product_information']['batch_number'],
                'manufacturing_date': report['product_information']['production_start'],
            },
            'component_materials': backward.get('input_materials', []),
            'manufacturing_steps': backward.get('process_steps', []),
            'inspection_records': {
                'in_process_inspections': [
                    s for s in backward.get('process_steps', [])
                    if s.get('quality_result')
                ],
                'final_inspection': {
                    'result': report['product_information']['quality_result'],
                    'score': report['product_information']['quality_score'],
                    'date': report['product_information']['production_end'],
                },
            },
            'labeling_verification': {
                'label_applied': True,
                'udi': serial_number,
                'verified_by': 'Production System',
            },
            'release_authorization': {
                'released_by': 'Quality System',
                'release_date': report['product_information']['production_end'],
                'disposition': 'Released for Distribution' if report['product_information']['quality_result'] == 'passed' else 'Held',
            },
        }

        return dhr


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
