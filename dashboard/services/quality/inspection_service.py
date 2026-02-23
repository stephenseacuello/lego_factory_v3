"""
Inspection Service - Quality inspection management.

Handles:
- Inspection creation and workflow
- Inspection types (receiving, in-process, final, audit)
- Pass/fail disposition
- Non-conformance reporting
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

from sqlalchemy.orm import Session

from models import Part, WorkOrder, WorkOrderOperation
from models.quality import (
    QualityInspection, QualityMetric,
    InspectionType, InspectionResult, DispositionCode
)

logger = logging.getLogger(__name__)


class InspectionService:
    """Quality inspection management service."""

    def __init__(self, session: Session):
        self.session = session

    def create_inspection(
        self,
        work_order_id: str,
        inspection_type: str,
        inspector_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        sample_size: int = 1,
        notes: Optional[str] = None
    ) -> QualityInspection:
        """
        Create a new quality inspection.

        Args:
            work_order_id: Work order being inspected
            inspection_type: Type of inspection (receiving, in_process, final, audit)
            inspector_id: User performing inspection
            operation_id: Specific operation being inspected (optional)
            sample_size: Number of parts to inspect
            notes: Inspection notes

        Returns:
            Created QualityInspection
        """
        work_order = self.session.query(WorkOrder).filter(
            WorkOrder.id == work_order_id
        ).first()

        if not work_order:
            raise ValueError(f"Work order {work_order_id} not found")

        inspection = QualityInspection(
            work_order_id=work_order_id,
            operation_id=operation_id,
            inspection_type=inspection_type,
            inspector_id=inspector_id,
            sample_size=sample_size,
            result=InspectionResult.PENDING.value,
            notes=notes
        )

        self.session.add(inspection)
        self.session.commit()

        logger.info(f"Created inspection for WO {work_order.work_order_number}")
        return inspection

    def get_inspection(self, inspection_id: str) -> Optional[Dict[str, Any]]:
        """Get inspection with all metrics."""
        inspection = self.session.query(QualityInspection).filter(
            QualityInspection.id == inspection_id
        ).first()

        if not inspection:
            return None

        return {
            'id': str(inspection.id),
            'work_order_id': str(inspection.work_order_id),
            'work_order_number': inspection.work_order.work_order_number if inspection.work_order else None,
            'operation_id': str(inspection.operation_id) if inspection.operation_id else None,
            'inspection_type': inspection.inspection_type,
            'result': inspection.result,
            'disposition': inspection.disposition,
            'inspector_id': str(inspection.inspector_id) if inspection.inspector_id else None,
            'sample_size': inspection.sample_size,
            'defects_found': inspection.defects_found,
            'notes': inspection.notes,
            'inspection_date': inspection.inspection_date.isoformat() if inspection.inspection_date else None,
            'created_at': inspection.created_at.isoformat() if inspection.created_at else None,
            'metrics': [
                {
                    'id': str(m.id),
                    'metric_name': m.metric_name,
                    'target_value': m.target_value,
                    'actual_value': m.actual_value,
                    'tolerance_plus': m.tolerance_plus,
                    'tolerance_minus': m.tolerance_minus,
                    'unit': m.unit,
                    'passed': m.passed,
                    'notes': m.notes
                }
                for m in inspection.metrics
            ]
        }

    def record_measurement(
        self,
        inspection_id: str,
        metric_name: str,
        actual_value: float,
        target_value: Optional[float] = None,
        tolerance_plus: Optional[float] = None,
        tolerance_minus: Optional[float] = None,
        unit: str = "mm",
        notes: Optional[str] = None
    ) -> QualityMetric:
        """
        Record a measurement for an inspection.

        Args:
            inspection_id: Inspection ID
            metric_name: Name of metric being measured
            actual_value: Measured value
            target_value: Target/nominal value
            tolerance_plus: Upper tolerance
            tolerance_minus: Lower tolerance
            unit: Unit of measurement
            notes: Measurement notes

        Returns:
            Created QualityMetric
        """
        inspection = self.session.query(QualityInspection).filter(
            QualityInspection.id == inspection_id
        ).first()

        if not inspection:
            raise ValueError(f"Inspection {inspection_id} not found")

        # Determine if passed
        passed = True
        if target_value is not None:
            upper_limit = target_value + (tolerance_plus or 0)
            lower_limit = target_value - (tolerance_minus or tolerance_plus or 0)
            passed = lower_limit <= actual_value <= upper_limit

        metric = QualityMetric(
            inspection_id=inspection_id,
            metric_name=metric_name,
            target_value=target_value,
            actual_value=actual_value,
            tolerance_plus=tolerance_plus,
            tolerance_minus=tolerance_minus,
            unit=unit,
            passed=passed,
            notes=notes
        )

        self.session.add(metric)
        self.session.commit()

        return metric

    def complete_inspection(
        self,
        inspection_id: str,
        result: str,
        disposition: Optional[str] = None,
        defects_found: int = 0,
        notes: Optional[str] = None
    ) -> QualityInspection:
        """
        Complete an inspection with result and disposition.

        Args:
            inspection_id: Inspection ID
            result: pass, fail, conditional
            disposition: use_as_is, rework, scrap, return_to_vendor
            defects_found: Number of defects found
            notes: Completion notes

        Returns:
            Updated QualityInspection
        """
        inspection = self.session.query(QualityInspection).filter(
            QualityInspection.id == inspection_id
        ).first()

        if not inspection:
            raise ValueError(f"Inspection {inspection_id} not found")

        inspection.result = result
        inspection.disposition = disposition
        inspection.defects_found = defects_found
        inspection.inspection_date = datetime.utcnow()

        if notes:
            existing_notes = inspection.notes or ""
            inspection.notes = f"{existing_notes}\n[Completion] {notes}".strip()

        self.session.commit()

        logger.info(f"Completed inspection {inspection_id}: {result}")
        return inspection

    def get_pending_inspections(
        self,
        work_order_id: Optional[str] = None,
        inspection_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all pending inspections."""
        query = self.session.query(QualityInspection).filter(
            QualityInspection.result == InspectionResult.PENDING.value
        )

        if work_order_id:
            query = query.filter(QualityInspection.work_order_id == work_order_id)
        if inspection_type:
            query = query.filter(QualityInspection.inspection_type == inspection_type)

        inspections = query.order_by(QualityInspection.created_at).all()

        return [
            {
                'id': str(i.id),
                'work_order_number': i.work_order.work_order_number if i.work_order else None,
                'part_number': i.work_order.part.part_number if i.work_order and i.work_order.part else None,
                'inspection_type': i.inspection_type,
                'sample_size': i.sample_size,
                'created_at': i.created_at.isoformat() if i.created_at else None
            }
            for i in inspections
        ]

    def get_inspection_history(
        self,
        part_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get inspection history."""
        query = self.session.query(QualityInspection)

        if work_order_id:
            query = query.filter(QualityInspection.work_order_id == work_order_id)
        elif part_id:
            query = query.join(WorkOrder).filter(WorkOrder.part_id == part_id)

        inspections = query.order_by(
            QualityInspection.inspection_date.desc()
        ).limit(limit).all()

        return [
            {
                'id': str(i.id),
                'work_order_number': i.work_order.work_order_number if i.work_order else None,
                'part_number': i.work_order.part.part_number if i.work_order and i.work_order.part else None,
                'inspection_type': i.inspection_type,
                'result': i.result,
                'disposition': i.disposition,
                'defects_found': i.defects_found,
                'inspection_date': i.inspection_date.isoformat() if i.inspection_date else None
            }
            for i in inspections
        ]

    def calculate_first_pass_yield(
        self,
        part_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate First Pass Yield (FPY) for a part or overall.

        FPY = (Parts passing first inspection) / (Total parts inspected)
        """
        query = self.session.query(QualityInspection).filter(
            QualityInspection.result.in_([
                InspectionResult.PASS.value,
                InspectionResult.FAIL.value
            ])
        )

        if part_id:
            query = query.join(WorkOrder).filter(WorkOrder.part_id == part_id)
        if start_date:
            query = query.filter(QualityInspection.inspection_date >= start_date)
        if end_date:
            query = query.filter(QualityInspection.inspection_date <= end_date)

        inspections = query.all()

        total = len(inspections)
        passed = sum(1 for i in inspections if i.result == InspectionResult.PASS.value)
        failed = total - passed

        fpy = (passed / total * 100) if total > 0 else 0

        return {
            'total_inspections': total,
            'passed': passed,
            'failed': failed,
            'first_pass_yield': round(fpy, 2),
            'period': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None
            }
        }

    def create_ncr(
        self,
        inspection_id: str,
        description: str,
        root_cause: Optional[str] = None,
        corrective_action: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Non-Conformance Report (NCR) from a failed inspection.

        Returns dict with NCR details (would be stored in dedicated NCR table in production).
        """
        inspection = self.session.query(QualityInspection).filter(
            QualityInspection.id == inspection_id
        ).first()

        if not inspection:
            raise ValueError(f"Inspection {inspection_id} not found")

        # In a full implementation, this would create a dedicated NCR record
        # For now, we append to inspection notes
        ncr_number = f"NCR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        ncr_data = {
            'ncr_number': ncr_number,
            'inspection_id': str(inspection_id),
            'work_order_number': inspection.work_order.work_order_number if inspection.work_order else None,
            'description': description,
            'root_cause': root_cause,
            'corrective_action': corrective_action,
            'status': 'open',
            'created_at': datetime.utcnow().isoformat()
        }

        # Update inspection notes with NCR reference
        existing_notes = inspection.notes or ""
        inspection.notes = f"{existing_notes}\n[NCR] {ncr_number}: {description}".strip()
        self.session.commit()

        logger.info(f"Created NCR {ncr_number} for inspection {inspection_id}")
        return ncr_data
