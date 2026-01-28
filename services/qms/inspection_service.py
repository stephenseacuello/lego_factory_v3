"""
LEGO Factory v3 - Inspection Service
=====================================
Quality inspection service with auto-NCR functionality.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from models.qms.supplier_quality import (
    InspectionPlan,
    InspectionCharacteristic,
    InspectionRecord,
    InspectionMeasurement,
    InspectionType,
    InspectionResult,
    CharacteristicType,
)
from models.qms import (
    NonConformanceReport,
    NCRStatus,
    NCRType,
    Severity,
)
from services.websocket import emit_event


class InspectionStatus(str, Enum):
    """Inspection lifecycle status."""
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    PASSED = 'passed'
    FAILED = 'failed'
    CONDITIONALLY_ACCEPTED = 'conditionally_accepted'


class InspectionService:
    """Inspection management service with auto-NCR creation."""

    def __init__(self, session: Session):
        self.session = session

    def create_inspection(
        self,
        job_id: str,
        plan_id: UUID,
        serial_number: str = None,
        inspector_id: str = None,
        lot_number: str = None,
        quantity: int = None,
    ) -> InspectionRecord:
        """
        Create a new inspection record from a plan.

        Args:
            job_id: Associated job/work order ID
            plan_id: Inspection plan UUID
            serial_number: Product serial number
            inspector_id: Inspector worker ID
            lot_number: Lot number being inspected
            quantity: Quantity being inspected

        Returns:
            Created InspectionRecord
        """
        plan = self.session.query(InspectionPlan).filter_by(id=plan_id).first()
        if not plan:
            raise ValueError(f"Inspection plan {plan_id} not found")

        # Generate inspection number
        inspection_number = f"INS-{datetime.utcnow().strftime('%Y%m%d')}-{job_id[-4:]}"

        record = InspectionRecord(
            inspection_number=inspection_number,
            plan_id=plan_id,
            job_id=job_id,
            serial_number=serial_number,
            inspector_id=inspector_id,
            lot_number=lot_number,
            quantity_inspected=quantity,
            status='pending',
            inspection_date=datetime.utcnow(),
            measurements=[],
        )

        self.session.add(record)
        self.session.commit()

        # Emit event
        emit_event('inspection_created', {
            'inspection_number': inspection_number,
            'plan_id': str(plan_id),
            'job_id': job_id,
            'serial_number': serial_number,
        }, namespace='/qms')

        return record

    def record_measurement(
        self,
        inspection_id: UUID,
        characteristic_id: UUID,
        value: float,
        notes: str = None,
    ) -> Tuple[InspectionMeasurement, bool]:
        """
        Record a measurement for an inspection characteristic.

        Args:
            inspection_id: Inspection record UUID
            characteristic_id: Characteristic UUID
            value: Measured value
            notes: Measurement notes

        Returns:
            Tuple of (InspectionMeasurement, passed)
        """
        record = self.session.query(InspectionRecord).filter_by(id=inspection_id).first()
        if not record:
            raise ValueError(f"Inspection record {inspection_id} not found")

        characteristic = self.session.query(InspectionCharacteristic).filter_by(
            id=characteristic_id
        ).first()
        if not characteristic:
            raise ValueError(f"Characteristic {characteristic_id} not found")

        # Check if value is within tolerance
        passed = True
        deviation = None

        if characteristic.nominal is not None:
            if characteristic.upper_tolerance is not None and value > characteristic.nominal + characteristic.upper_tolerance:
                passed = False
                deviation = value - (characteristic.nominal + characteristic.upper_tolerance)
            elif characteristic.lower_tolerance is not None and value < characteristic.nominal - characteristic.lower_tolerance:
                passed = False
                deviation = value - (characteristic.nominal - characteristic.lower_tolerance)

        # Create measurement
        measurement = InspectionMeasurement(
            record_id=inspection_id,
            characteristic_id=characteristic_id,
            measured_value=value,
            deviation=deviation,
            result='pass' if passed else 'fail',
            measured_at=datetime.utcnow(),
            notes=notes,
        )

        self.session.add(measurement)

        # Update record status if this was the first measurement
        if record.status == 'pending':
            record.status = 'in_progress'

        self.session.commit()

        return measurement, passed

    def complete_inspection(
        self,
        inspection_id: UUID,
        notes: str = None,
        disposition: str = None,
    ) -> Tuple[InspectionRecord, Optional[NonConformanceReport]]:
        """
        Complete an inspection and optionally create NCR if failed.

        Args:
            inspection_id: Inspection record UUID
            notes: Completion notes
            disposition: Disposition decision (accept, reject, conditional, rework)

        Returns:
            Tuple of (InspectionRecord, NCR if created)
        """
        record = self.session.query(InspectionRecord).filter_by(id=inspection_id).first()
        if not record:
            raise ValueError(f"Inspection record {inspection_id} not found")

        # Get all measurements
        measurements = self.session.query(InspectionMeasurement).filter_by(
            record_id=inspection_id
        ).all()

        # Calculate results
        total_measurements = len(measurements)
        failed_measurements = [m for m in measurements if m.result == 'fail']
        failed_count = len(failed_measurements)

        # Get critical failures
        critical_failures = []
        for m in failed_measurements:
            char = self.session.query(InspectionCharacteristic).filter_by(
                id=m.characteristic_id
            ).first()
            if char and char.is_critical:
                critical_failures.append(m)

        # Determine overall result
        if failed_count == 0:
            record.status = 'passed'
            record.result = InspectionResult.ACCEPT
        elif critical_failures:
            record.status = 'failed'
            record.result = InspectionResult.REJECT
        elif disposition:
            record.status = disposition
            record.result = getattr(InspectionResult, disposition.upper(), InspectionResult.HOLD)
        else:
            record.status = 'failed'
            record.result = InspectionResult.REJECT

        record.completed_at = datetime.utcnow()
        record.notes = notes
        record.total_characteristics = total_measurements
        record.passed_count = total_measurements - failed_count
        record.failed_count = failed_count

        # Auto-create NCR if critical failure
        ncr = None
        if critical_failures or (failed_count > 0 and record.result == InspectionResult.REJECT):
            ncr = self._auto_ncr_on_fail(record, failed_measurements, critical_failures)

        self.session.commit()

        # Emit event
        emit_event('inspection_completed', {
            'inspection_id': str(inspection_id),
            'status': record.status,
            'result': record.result.value if record.result else None,
            'failed_count': failed_count,
            'critical_failures': len(critical_failures),
            'ncr_created': ncr.ncr_number if ncr else None,
        }, namespace='/qms')

        return record, ncr

    def _auto_ncr_on_fail(
        self,
        record: InspectionRecord,
        failed_measurements: List[InspectionMeasurement],
        critical_failures: List[InspectionMeasurement],
    ) -> NonConformanceReport:
        """
        Automatically create NCR for inspection failure.

        Args:
            record: Inspection record
            failed_measurements: All failed measurements
            critical_failures: Critical dimension failures

        Returns:
            Created NCR
        """
        # Determine severity based on failures
        if len(critical_failures) >= 2:
            severity = Severity.CRITICAL
        elif len(critical_failures) == 1:
            severity = Severity.MAJOR
        elif len(failed_measurements) >= 3:
            severity = Severity.MAJOR
        else:
            severity = Severity.MINOR

        # Generate NCR number
        ncr_number = f"NCR-{datetime.utcnow().strftime('%Y%m%d')}-{record.inspection_number[-4:]}"

        # Build description
        failed_details = []
        for m in failed_measurements:
            char = self.session.query(InspectionCharacteristic).filter_by(
                id=m.characteristic_id
            ).first()
            if char:
                failed_details.append(
                    f"- {char.name}: measured {m.measured_value}, "
                    f"nominal {char.nominal} ±{char.upper_tolerance}/{char.lower_tolerance}"
                )

        description = f"Inspection {record.inspection_number} failed with {len(failed_measurements)} dimension(s) out of tolerance.\n\n"
        description += "Failed dimensions:\n" + "\n".join(failed_details)

        ncr = NonConformanceReport(
            ncr_number=ncr_number,
            title=f"Inspection Failure - {record.serial_number or record.lot_number or record.job_id}",
            description=description,
            ncr_type=NCRType.PRODUCT,
            status=NCRStatus.OPEN,
            severity=severity,
            source='inspection',
            source_reference=record.inspection_number,
            detected_date=datetime.utcnow(),
            detected_by=record.inspector_id,
            product_id=record.serial_number,
            work_order_id=record.job_id,
            lot_number=record.lot_number,
            quantity_affected=record.quantity_inspected or 1,
        )

        self.session.add(ncr)
        self.session.flush()

        # Link NCR to inspection record
        record.ncr_id = ncr.id

        # Emit NCR created event
        emit_event('ncr_auto_created', {
            'ncr_number': ncr_number,
            'severity': severity.value,
            'inspection_number': record.inspection_number,
            'failed_count': len(failed_measurements),
        }, namespace='/qms')

        return ncr

    def get_first_article_status(
        self,
        product_id: str,
    ) -> Dict[str, Any]:
        """
        Check if first article inspection exists and passed.

        Args:
            product_id: Product ID to check

        Returns:
            Dict with FAI status information
        """
        # Find FAI plans for this product
        fai_plans = self.session.query(InspectionPlan).filter(
            and_(
                InspectionPlan.item_id == product_id,
                InspectionPlan.inspection_type == InspectionType.FIRST_ARTICLE,
            )
        ).all()

        if not fai_plans:
            return {
                'status': 'no_plan',
                'message': 'No first article inspection plan exists for this product',
                'fai_required': False,
            }

        # Find completed FAI records
        fai_records = []
        for plan in fai_plans:
            records = self.session.query(InspectionRecord).filter(
                and_(
                    InspectionRecord.plan_id == plan.id,
                    InspectionRecord.status.in_(['passed', 'failed', 'conditionally_accepted']),
                )
            ).order_by(desc(InspectionRecord.completed_at)).all()
            fai_records.extend(records)

        if not fai_records:
            return {
                'status': 'pending',
                'message': 'First article inspection required but not completed',
                'fai_required': True,
                'can_proceed': False,
            }

        # Check most recent FAI
        latest_fai = max(fai_records, key=lambda r: r.completed_at or datetime.min)

        if latest_fai.status == 'passed':
            return {
                'status': 'passed',
                'message': 'First article inspection passed',
                'fai_required': True,
                'can_proceed': True,
                'inspection_number': latest_fai.inspection_number,
                'completed_date': latest_fai.completed_at.isoformat() if latest_fai.completed_at else None,
            }
        elif latest_fai.status == 'conditionally_accepted':
            return {
                'status': 'conditional',
                'message': 'First article conditionally accepted',
                'fai_required': True,
                'can_proceed': True,
                'inspection_number': latest_fai.inspection_number,
                'notes': latest_fai.notes,
            }
        else:
            return {
                'status': 'failed',
                'message': 'First article inspection failed',
                'fai_required': True,
                'can_proceed': False,
                'inspection_number': latest_fai.inspection_number,
                'ncr_number': latest_fai.ncr_id,
            }

    def get_inspection(
        self,
        inspection_id: UUID,
    ) -> Dict[str, Any]:
        """Get detailed inspection record."""
        record = self.session.query(InspectionRecord).filter_by(id=inspection_id).first()
        if not record:
            raise ValueError(f"Inspection {inspection_id} not found")

        plan = self.session.query(InspectionPlan).filter_by(id=record.plan_id).first()
        measurements = self.session.query(InspectionMeasurement).filter_by(
            record_id=inspection_id
        ).all()

        # Get characteristics with measurements
        characteristics = []
        for m in measurements:
            char = self.session.query(InspectionCharacteristic).filter_by(
                id=m.characteristic_id
            ).first()
            if char:
                characteristics.append({
                    'characteristic': char.to_dict(),
                    'measurement': m.to_dict(),
                })

        return {
            'record': record.to_dict(),
            'plan': plan.to_dict() if plan else None,
            'measurements': characteristics,
            'summary': {
                'total': len(measurements),
                'passed': sum(1 for m in measurements if m.result == 'pass'),
                'failed': sum(1 for m in measurements if m.result == 'fail'),
            },
        }

    def get_pending_inspections(
        self,
        inspector_id: str = None,
        job_id: str = None,
    ) -> List[Dict[str, Any]]:
        """Get pending inspections."""
        query = self.session.query(InspectionRecord).filter(
            InspectionRecord.status.in_(['pending', 'in_progress'])
        )

        if inspector_id:
            query = query.filter_by(inspector_id=inspector_id)
        if job_id:
            query = query.filter_by(job_id=job_id)

        records = query.order_by(InspectionRecord.inspection_date).all()

        result = []
        for record in records:
            plan = self.session.query(InspectionPlan).filter_by(id=record.plan_id).first()
            result.append({
                'record': record.to_dict(),
                'plan_name': plan.name if plan else 'Unknown',
                'inspection_type': plan.inspection_type.value if plan else None,
            })

        return result

    def get_inspection_stats(
        self,
        days: int = 30,
        machine_id: str = None,
    ) -> Dict[str, Any]:
        """Get inspection statistics."""
        from_date = datetime.utcnow() - timedelta(days=days)

        query = self.session.query(InspectionRecord).filter(
            InspectionRecord.completed_at >= from_date
        )

        records = query.all()

        if not records:
            return {
                'total_inspections': 0,
                'pass_rate': 0,
                'fail_rate': 0,
                'ncr_count': 0,
            }

        total = len(records)
        passed = sum(1 for r in records if r.status == 'passed')
        failed = sum(1 for r in records if r.status == 'failed')
        conditional = sum(1 for r in records if r.status == 'conditionally_accepted')
        ncr_count = sum(1 for r in records if r.ncr_id is not None)

        return {
            'total_inspections': total,
            'passed': passed,
            'failed': failed,
            'conditional': conditional,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'fail_rate': (failed / total * 100) if total > 0 else 0,
            'ncr_count': ncr_count,
            'by_type': self._group_by_type(records),
        }

    def _group_by_type(
        self,
        records: List[InspectionRecord],
    ) -> Dict[str, Dict[str, int]]:
        """Group inspection results by type."""
        result = {}

        for record in records:
            plan = self.session.query(InspectionPlan).filter_by(id=record.plan_id).first()
            if not plan:
                continue

            inspection_type = plan.inspection_type.value
            if inspection_type not in result:
                result[inspection_type] = {'total': 0, 'passed': 0, 'failed': 0}

            result[inspection_type]['total'] += 1
            if record.status == 'passed':
                result[inspection_type]['passed'] += 1
            elif record.status == 'failed':
                result[inspection_type]['failed'] += 1

        return result


# Required import for timedelta
from datetime import timedelta


# Export convenience functions
def create_inspection_service(session: Session) -> InspectionService:
    """Create an inspection service instance."""
    return InspectionService(session)
