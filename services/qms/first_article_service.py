"""
LEGO Factory v3 - First Article Inspection (FAI) Service
=========================================================
Complete FAI workflow for new product/process qualification.

Features:
- FAI checklist generation from BOM/routing
- Measurement data capture with GD&T support
- Photo/document attachment for inspection records
- Approval workflow with electronic signatures
- AS9102 report generation
"""

import uuid
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal

from models.qms.first_article import FirstArticleInspection

logger = logging.getLogger(__name__)


class FAIStatus(str, Enum):
    """FAI workflow status."""
    DRAFT = 'draft'
    IN_PROGRESS = 'in_progress'
    PENDING_REVIEW = 'pending_review'
    PENDING_APPROVAL = 'pending_approval'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    ON_HOLD = 'on_hold'


class InspectionResult(str, Enum):
    """Inspection measurement result."""
    PASS = 'pass'
    FAIL = 'fail'
    DEVIATION = 'deviation'  # Out of spec but accepted
    NOT_INSPECTED = 'not_inspected'


class CharacteristicType(str, Enum):
    """Types of inspection characteristics."""
    DIMENSIONAL = 'dimensional'
    MATERIAL = 'material'
    VISUAL = 'visual'
    FUNCTIONAL = 'functional'
    PROCESS = 'process'
    DOCUMENTATION = 'documentation'


@dataclass
class InspectionCharacteristic:
    """Single inspection characteristic on FAI."""
    char_id: str
    char_number: int  # Balloon number on drawing
    description: str
    char_type: CharacteristicType
    specification: str
    nominal: Optional[float] = None
    upper_limit: Optional[float] = None
    lower_limit: Optional[float] = None
    unit_of_measure: str = ""
    gdt_symbol: str = ""  # GD&T symbol if applicable
    drawing_zone: str = ""  # Drawing zone reference
    is_critical: bool = False
    is_safety: bool = False

    # Measurement data
    measured_value: Optional[float] = None
    measurement_method: str = ""
    measurement_equipment: str = ""
    result: InspectionResult = InspectionResult.NOT_INSPECTED
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'char_id': self.char_id,
            'char_number': self.char_number,
            'description': self.description,
            'char_type': self.char_type.value,
            'specification': self.specification,
            'nominal': self.nominal,
            'upper_limit': self.upper_limit,
            'lower_limit': self.lower_limit,
            'unit_of_measure': self.unit_of_measure,
            'gdt_symbol': self.gdt_symbol,
            'drawing_zone': self.drawing_zone,
            'is_critical': self.is_critical,
            'is_safety': self.is_safety,
            'measured_value': self.measured_value,
            'measurement_method': self.measurement_method,
            'measurement_equipment': self.measurement_equipment,
            'result': self.result.value,
            'notes': self.notes,
        }


@dataclass
class FAIForm:
    """First Article Inspection form (AS9102 compatible)."""
    fai_number: str
    part_number: str
    part_name: str
    revision: str

    # Identifiers
    serial_number: str = ""
    lot_number: str = ""
    work_order_id: str = ""

    # Drawing/Spec references
    drawing_number: str = ""
    drawing_revision: str = ""
    specification_refs: List[str] = field(default_factory=list)

    # Production info
    machine_id: str = ""
    operator_id: str = ""
    production_date: datetime = None
    quantity_inspected: int = 1

    # Characteristics
    characteristics: List[InspectionCharacteristic] = field(default_factory=list)

    # Attachments
    attachments: List[Dict[str, str]] = field(default_factory=list)  # {type, filename, url}

    # Status
    status: FAIStatus = FAIStatus.DRAFT

    # Workflow
    inspector_id: str = ""
    inspector_signature: str = ""
    inspection_date: datetime = None

    reviewer_id: str = ""
    reviewer_signature: str = ""
    review_date: datetime = None
    review_comments: str = ""

    approver_id: str = ""
    approver_signature: str = ""
    approval_date: datetime = None
    approval_comments: str = ""

    # Result
    overall_result: InspectionResult = InspectionResult.NOT_INSPECTED
    deviation_count: int = 0
    fail_count: int = 0

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'fai_number': self.fai_number,
            'part_number': self.part_number,
            'part_name': self.part_name,
            'revision': self.revision,
            'serial_number': self.serial_number,
            'lot_number': self.lot_number,
            'work_order_id': self.work_order_id,
            'drawing_number': self.drawing_number,
            'drawing_revision': self.drawing_revision,
            'machine_id': self.machine_id,
            'operator_id': self.operator_id,
            'production_date': self.production_date.isoformat() if self.production_date else None,
            'quantity_inspected': self.quantity_inspected,
            'characteristics': [c.to_dict() for c in self.characteristics],
            'attachments': self.attachments,
            'status': self.status.value,
            'inspector_id': self.inspector_id,
            'inspection_date': self.inspection_date.isoformat() if self.inspection_date else None,
            'reviewer_id': self.reviewer_id,
            'review_date': self.review_date.isoformat() if self.review_date else None,
            'approver_id': self.approver_id,
            'approval_date': self.approval_date.isoformat() if self.approval_date else None,
            'overall_result': self.overall_result.value,
            'deviation_count': self.deviation_count,
            'fail_count': self.fail_count,
            'created_at': self.created_at.isoformat(),
            'summary': self._get_summary(),
        }

    def _get_summary(self) -> Dict[str, Any]:
        total = len(self.characteristics)
        passed = len([c for c in self.characteristics if c.result == InspectionResult.PASS])
        failed = len([c for c in self.characteristics if c.result == InspectionResult.FAIL])
        deviation = len([c for c in self.characteristics if c.result == InspectionResult.DEVIATION])
        not_inspected = len([c for c in self.characteristics if c.result == InspectionResult.NOT_INSPECTED])

        return {
            'total_characteristics': total,
            'passed': passed,
            'failed': failed,
            'deviations': deviation,
            'not_inspected': not_inspected,
            'completion_pct': round((total - not_inspected) / total * 100, 1) if total > 0 else 0,
            'pass_rate': round(passed / (total - not_inspected) * 100, 1) if (total - not_inspected) > 0 else 0,
        }


class FirstArticleService:
    """
    First Article Inspection workflow service.

    Supports AS9102 FAI requirements for aerospace quality management.
    Uses database-backed storage via the FirstArticleInspection model.
    """

    def __init__(self, session=None):
        self.session = session

    def _get_fai(self, fai_number: str) -> Optional[FirstArticleInspection]:
        """Load an FAI record from the database by fai_number."""
        if not self.session:
            return None
        return self.session.query(FirstArticleInspection).filter(
            FirstArticleInspection.fai_number == fai_number
        ).first()

    def create_fai(
        self,
        part_number: str,
        part_name: str,
        revision: str,
        drawing_number: str = None,
        work_order_id: str = None
    ) -> Dict[str, Any]:
        """
        Create a new FAI form.

        Args:
            part_number: Part number
            part_name: Part description
            revision: Part revision
            drawing_number: Drawing reference
            work_order_id: Associated work order

        Returns:
            Created FAI as a dict
        """
        fai_number = f"FAI-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        fai = FirstArticleInspection(
            fai_number=fai_number,
            part_number=part_number,
            part_name=part_name,
            revision=revision,
            drawing_number=drawing_number or part_number,
            drawing_revision=revision,
            work_order_id=work_order_id or "",
            characteristics=[],
            attachments=[],
            status=FAIStatus.DRAFT.value,
            overall_result=InspectionResult.NOT_INSPECTED.value,
            deviation_count=0,
            fail_count=0,
        )

        self.session.add(fai)
        self.session.flush()
        logger.info(f"Created FAI: {fai_number} for {part_number} Rev {revision}")

        return fai.to_dict()

    def generate_checklist_from_bom(
        self,
        fai_number: str,
        bom_data: List[Dict[str, Any]],
        routing_data: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate FAI checklist from BOM and routing data.

        Args:
            fai_number: FAI form number
            bom_data: Bill of Materials with characteristics
            routing_data: Process routing with requirements

        Returns:
            Updated FAI with generated characteristics
        """
        fai = self._get_fai(fai_number)
        if not fai:
            return {'error': f'FAI {fai_number} not found'}

        characteristics = list(fai.characteristics or [])
        char_number = 1

        # Add material/component characteristics from BOM
        for item in bom_data:
            char = {
                'char_id': f"{fai_number}-{char_number:03d}",
                'char_number': char_number,
                'description': f"Material: {item.get('description', item.get('part_id', ''))}",
                'char_type': CharacteristicType.MATERIAL.value,
                'specification': item.get('specification', 'Per drawing'),
                'nominal': None,
                'upper_limit': None,
                'lower_limit': None,
                'unit_of_measure': '',
                'gdt_symbol': '',
                'drawing_zone': '',
                'is_critical': item.get('critical', False),
                'is_safety': False,
                'measured_value': None,
                'measurement_method': '',
                'measurement_equipment': '',
                'result': InspectionResult.NOT_INSPECTED.value,
                'notes': '',
            }
            characteristics.append(char)
            char_number += 1

        # Add process characteristics from routing
        if routing_data:
            for op in routing_data:
                # Add dimensional checks from routing
                for check in op.get('inspection_points', []):
                    char = {
                        'char_id': f"{fai_number}-{char_number:03d}",
                        'char_number': char_number,
                        'description': check.get('description', f"Op {op.get('operation', '')} check"),
                        'char_type': CharacteristicType.DIMENSIONAL.value if check.get('type') == 'dimensional' else CharacteristicType.PROCESS.value,
                        'specification': check.get('specification', ''),
                        'nominal': check.get('nominal'),
                        'upper_limit': check.get('upper_limit'),
                        'lower_limit': check.get('lower_limit'),
                        'unit_of_measure': check.get('unit', ''),
                        'gdt_symbol': '',
                        'drawing_zone': check.get('zone', ''),
                        'is_critical': check.get('critical', False),
                        'is_safety': False,
                        'measured_value': None,
                        'measurement_method': '',
                        'measurement_equipment': '',
                        'result': InspectionResult.NOT_INSPECTED.value,
                        'notes': '',
                    }
                    characteristics.append(char)
                    char_number += 1

        fai.characteristics = characteristics
        self.session.flush()

        return {
            'fai_number': fai_number,
            'characteristics_added': char_number - 1,
            'fai': fai.to_dict()
        }

    def add_characteristic(
        self,
        fai_number: str,
        description: str,
        char_type: CharacteristicType,
        specification: str,
        nominal: float = None,
        upper_limit: float = None,
        lower_limit: float = None,
        unit_of_measure: str = "",
        gdt_symbol: str = "",
        is_critical: bool = False,
        is_safety: bool = False
    ) -> Dict[str, Any]:
        """
        Add a single characteristic to FAI.

        Args:
            fai_number: FAI form number
            description: Characteristic description
            char_type: Type of characteristic
            specification: Specification/requirement
            nominal: Nominal value
            upper_limit: Upper tolerance limit
            lower_limit: Lower tolerance limit
            unit_of_measure: Unit (mm, in, etc.)
            gdt_symbol: GD&T symbol
            is_critical: Critical characteristic flag
            is_safety: Safety characteristic flag

        Returns:
            Added characteristic as a dict
        """
        fai = self._get_fai(fai_number)
        if not fai:
            return {'error': f'FAI {fai_number} not found'}

        characteristics = list(fai.characteristics or [])
        char_number = len(characteristics) + 1

        char = {
            'char_id': f"{fai_number}-{char_number:03d}",
            'char_number': char_number,
            'description': description,
            'char_type': char_type.value if isinstance(char_type, CharacteristicType) else char_type,
            'specification': specification,
            'nominal': nominal,
            'upper_limit': upper_limit,
            'lower_limit': lower_limit,
            'unit_of_measure': unit_of_measure,
            'gdt_symbol': gdt_symbol,
            'drawing_zone': '',
            'is_critical': is_critical,
            'is_safety': is_safety,
            'measured_value': None,
            'measurement_method': '',
            'measurement_equipment': '',
            'result': InspectionResult.NOT_INSPECTED.value,
            'notes': '',
        }

        characteristics.append(char)
        fai.characteristics = characteristics
        self.session.flush()

        return char

    def record_measurement(
        self,
        fai_number: str,
        char_id: str,
        measured_value: float,
        measurement_method: str = "",
        measurement_equipment: str = "",
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Record a measurement for a characteristic.

        Args:
            fai_number: FAI form number
            char_id: Characteristic ID
            measured_value: Measured value
            measurement_method: How measurement was taken
            measurement_equipment: Equipment used (with calibration status)
            notes: Additional notes

        Returns:
            Updated characteristic with result
        """
        fai = self._get_fai(fai_number)
        if not fai:
            return {'error': f'FAI {fai_number} not found'}

        characteristics = list(fai.characteristics or [])
        char = next((c for c in characteristics if c.get('char_id') == char_id), None)
        if not char:
            return {'error': f'Characteristic {char_id} not found'}

        char['measured_value'] = measured_value
        char['measurement_method'] = measurement_method
        char['measurement_equipment'] = measurement_equipment
        char['notes'] = notes

        # Determine result
        upper = char.get('upper_limit')
        lower = char.get('lower_limit')
        nominal = char.get('nominal')

        if upper is not None and lower is not None:
            if lower <= measured_value <= upper:
                char['result'] = InspectionResult.PASS.value
            else:
                char['result'] = InspectionResult.FAIL.value
        elif nominal is not None:
            # Simple pass/fail based on nominal
            tolerance = abs(nominal * 0.01)  # Default 1% tolerance
            if abs(measured_value - nominal) <= tolerance:
                char['result'] = InspectionResult.PASS.value
            else:
                char['result'] = InspectionResult.FAIL.value
        else:
            # Manual determination needed
            char['result'] = InspectionResult.PASS.value  # Default to pass if no limits

        fai.characteristics = characteristics
        self._update_fai_totals(fai)
        self.session.flush()

        return {
            'char_id': char_id,
            'measured_value': measured_value,
            'result': char['result'],
            'within_spec': char['result'] == InspectionResult.PASS.value
        }

    def _update_fai_totals(self, fai: FirstArticleInspection):
        """Update FAI pass/fail/deviation counts from characteristics JSON."""
        chars = fai.characteristics or []
        fai.fail_count = len([c for c in chars if c.get('result') == InspectionResult.FAIL.value])
        fai.deviation_count = len([c for c in chars if c.get('result') == InspectionResult.DEVIATION.value])

        # Determine overall result
        if fai.fail_count > 0:
            fai.overall_result = InspectionResult.FAIL.value
        elif fai.deviation_count > 0:
            fai.overall_result = InspectionResult.DEVIATION.value
        elif all(c.get('result') == InspectionResult.PASS.value for c in chars):
            fai.overall_result = InspectionResult.PASS.value
        else:
            fai.overall_result = InspectionResult.NOT_INSPECTED.value

    def add_attachment(
        self,
        fai_number: str,
        attachment_type: str,
        filename: str,
        url: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Add an attachment to FAI (photo, document, etc.).

        Args:
            fai_number: FAI form number
            attachment_type: Type (photo, document, certificate)
            filename: Original filename
            url: Storage URL/path
            description: Description

        Returns:
            Attachment record
        """
        fai = self._get_fai(fai_number)
        if not fai:
            return {'error': f'FAI {fai_number} not found'}

        attachment = {
            'id': f"ATT-{uuid.uuid4().hex[:8].upper()}",
            'type': attachment_type,
            'filename': filename,
            'url': url,
            'description': description,
            'uploaded_at': datetime.utcnow().isoformat()
        }

        attachments = list(fai.attachments or [])
        attachments.append(attachment)
        fai.attachments = attachments
        self.session.flush()

        return attachment

    # ==================== Workflow ====================

    def submit_for_review(
        self,
        fai_number: str,
        inspector_id: str,
        inspector_signature: str = None
    ) -> Dict[str, Any]:
        """
        Submit FAI for review (inspector sign-off).

        Args:
            fai_number: FAI form number
            inspector_id: Inspector user ID
            inspector_signature: Electronic signature

        Returns:
            Updated FAI status
        """
        fai = self._get_fai(fai_number)
        if not fai:
            return {'error': f'FAI {fai_number} not found'}

        # Validate all characteristics are inspected
        chars = fai.characteristics or []
        not_inspected = [c for c in chars if c.get('result', 'not_inspected') == InspectionResult.NOT_INSPECTED.value]
        if not_inspected:
            return {
                'error': 'Cannot submit - incomplete inspection',
                'not_inspected_count': len(not_inspected),
                'not_inspected': [c.get('char_id') for c in not_inspected]
            }

        fai.inspector_id = inspector_id
        fai.inspector_signature = inspector_signature or f"E-Signed by {inspector_id}"
        fai.inspection_date = datetime.utcnow()
        fai.status = FAIStatus.PENDING_REVIEW.value
        self.session.flush()

        logger.info(f"FAI {fai_number} submitted for review by {inspector_id}")

        return {
            'fai_number': fai_number,
            'status': fai.status,
            'inspector_id': inspector_id,
            'inspection_date': fai.inspection_date.isoformat()
        }

    def review_fai(
        self,
        fai_number: str,
        reviewer_id: str,
        approved: bool,
        comments: str = "",
        reviewer_signature: str = None
    ) -> Dict[str, Any]:
        """
        Review FAI (quality engineer review).

        Args:
            fai_number: FAI form number
            reviewer_id: Reviewer user ID
            approved: Review decision
            comments: Review comments
            reviewer_signature: Electronic signature

        Returns:
            Updated FAI status
        """
        fai = self._get_fai(fai_number)
        if not fai:
            return {'error': f'FAI {fai_number} not found'}

        if fai.status != FAIStatus.PENDING_REVIEW.value:
            return {'error': f'FAI not in review status (current: {fai.status})'}

        fai.reviewer_id = reviewer_id
        fai.reviewer_signature = reviewer_signature or f"E-Signed by {reviewer_id}"
        fai.review_date = datetime.utcnow()
        fai.review_comments = comments

        if approved:
            fai.status = FAIStatus.PENDING_APPROVAL.value
        else:
            fai.status = FAIStatus.REJECTED.value

        self.session.flush()

        logger.info(f"FAI {fai_number} reviewed by {reviewer_id}: {'approved' if approved else 'rejected'}")

        return {
            'fai_number': fai_number,
            'status': fai.status,
            'reviewer_id': reviewer_id,
            'review_date': fai.review_date.isoformat(),
            'approved': approved
        }

    def approve_fai(
        self,
        fai_number: str,
        approver_id: str,
        approved: bool,
        comments: str = "",
        approver_signature: str = None
    ) -> Dict[str, Any]:
        """
        Final approval of FAI.

        Args:
            fai_number: FAI form number
            approver_id: Approver user ID
            approved: Approval decision
            comments: Approval comments
            approver_signature: Electronic signature

        Returns:
            Final FAI status
        """
        fai = self._get_fai(fai_number)
        if not fai:
            return {'error': f'FAI {fai_number} not found'}

        if fai.status != FAIStatus.PENDING_APPROVAL.value:
            return {'error': f'FAI not pending approval (current: {fai.status})'}

        fai.approver_id = approver_id
        fai.approver_signature = approver_signature or f"E-Signed by {approver_id}"
        fai.approval_date = datetime.utcnow()
        fai.approval_comments = comments

        if approved:
            fai.status = FAIStatus.APPROVED.value
        else:
            fai.status = FAIStatus.REJECTED.value

        self.session.flush()

        logger.info(f"FAI {fai_number} {'approved' if approved else 'rejected'} by {approver_id}")

        return {
            'fai_number': fai_number,
            'status': fai.status,
            'approver_id': approver_id,
            'approval_date': fai.approval_date.isoformat(),
            'approved': approved,
            'overall_result': fai.overall_result
        }

    # ==================== Report Generation ====================

    def generate_as9102_report(self, fai_number: str) -> Dict[str, Any]:
        """
        Generate AS9102 First Article Inspection Report.

        AS9102 is the aerospace standard for FAI documentation.

        Args:
            fai_number: FAI form number

        Returns:
            AS9102 formatted report data
        """
        fai = self._get_fai(fai_number)
        if not fai:
            return {'error': f'FAI {fai_number} not found'}

        chars = fai.characteristics or []

        # Form 1: Part Number Accountability
        form1 = {
            'form_type': 'AS9102 Form 1',
            'title': 'Part Number Accountability',
            'part_number': fai.part_number,
            'part_name': fai.part_name,
            'part_revision': fai.revision,
            'drawing_number': fai.drawing_number,
            'drawing_revision': fai.drawing_revision,
            'organization': 'LEGO Factory v3',
            'fai_number': fai.fai_number,
            'serial_number': fai.serial_number,
            'fai_reason': 'New Part',  # Could be: New Part, Design Change, etc.
        }

        # Form 2: Product Accountability (Material/Process)
        material_chars = [c for c in chars if c.get('char_type') == CharacteristicType.MATERIAL.value]
        process_chars = [c for c in chars if c.get('char_type') == CharacteristicType.PROCESS.value]

        form2 = {
            'form_type': 'AS9102 Form 2',
            'title': 'Product Accountability - Material/Process',
            'part_number': fai.part_number,
            'fai_number': fai.fai_number,
            'materials': [
                {
                    'item': i + 1,
                    'description': c.get('description', ''),
                    'specification': c.get('specification', ''),
                    'result': c.get('result', 'not_inspected'),
                }
                for i, c in enumerate(material_chars)
            ],
            'special_processes': [
                {
                    'item': i + 1,
                    'description': c.get('description', ''),
                    'specification': c.get('specification', ''),
                    'result': c.get('result', 'not_inspected'),
                }
                for i, c in enumerate(process_chars)
            ],
        }

        # Form 3: Characteristic Accountability
        dimensional_chars = [c for c in chars if c.get('char_type') == CharacteristicType.DIMENSIONAL.value]

        form3 = {
            'form_type': 'AS9102 Form 3',
            'title': 'Characteristic Accountability',
            'part_number': fai.part_number,
            'fai_number': fai.fai_number,
            'characteristics': [
                {
                    'char_number': c.get('char_number'),
                    'char_designator': 'KC' if c.get('is_critical') else 'SC' if c.get('is_safety') else '',
                    'reference': c.get('drawing_zone', ''),
                    'requirement': c.get('specification', ''),
                    'results': c.get('measured_value'),
                    'designed_tooling': c.get('gdt_symbol', ''),
                    'conformance': 'C' if c.get('result') == InspectionResult.PASS.value else 'NC',
                }
                for c in dimensional_chars
            ],
        }

        # Signatures
        signatures = {
            'inspector': {
                'name': fai.inspector_id,
                'signature': fai.inspector_signature,
                'date': fai.inspection_date.isoformat() if fai.inspection_date else None,
            },
            'reviewer': {
                'name': fai.reviewer_id,
                'signature': fai.reviewer_signature,
                'date': fai.review_date.isoformat() if fai.review_date else None,
            },
            'approver': {
                'name': fai.approver_id,
                'signature': fai.approver_signature,
                'date': fai.approval_date.isoformat() if fai.approval_date else None,
            },
        }

        return {
            'fai_number': fai_number,
            'report_type': 'AS9102',
            'generated_at': datetime.utcnow().isoformat(),
            'status': fai.status,
            'overall_result': fai.overall_result,
            'form1': form1,
            'form2': form2,
            'form3': form3,
            'signatures': signatures,
            'attachments': fai.attachments or [],
            'summary': fai._get_summary(),
        }

    # ==================== Queries ====================

    def get_fai(self, fai_number: str) -> Optional[Dict[str, Any]]:
        """Get FAI form by number."""
        fai = self._get_fai(fai_number)
        return fai.to_dict() if fai else None

    def list_fais(
        self,
        status: FAIStatus = None,
        part_number: str = None,
        start_date: date = None,
        end_date: date = None
    ) -> List[Dict[str, Any]]:
        """List FAI forms with optional filtering."""
        if not self.session:
            return []

        query = self.session.query(FirstArticleInspection)

        if status:
            status_val = status.value if isinstance(status, FAIStatus) else status
            query = query.filter(FirstArticleInspection.status == status_val)
        if part_number:
            query = query.filter(FirstArticleInspection.part_number == part_number)
        if start_date:
            query = query.filter(FirstArticleInspection.created_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(FirstArticleInspection.created_at <= datetime.combine(end_date, datetime.max.time()))

        query = query.order_by(FirstArticleInspection.created_at.desc())
        fais = query.all()

        return [
            {
                'fai_number': fai.fai_number,
                'part_number': fai.part_number,
                'part_name': fai.part_name,
                'revision': fai.revision,
                'status': fai.status,
                'overall_result': fai.overall_result,
                'created_at': fai.created_at.isoformat() if fai.created_at else None,
                'summary': fai._get_summary(),
            }
            for fai in fais
        ]

    def get_pending_approvals(self, approver_id: str = None) -> List[Dict[str, Any]]:
        """Get FAIs pending approval."""
        if not self.session:
            return []

        query = self.session.query(FirstArticleInspection).filter(
            FirstArticleInspection.status.in_([
                FAIStatus.PENDING_REVIEW.value,
                FAIStatus.PENDING_APPROVAL.value,
            ])
        )

        fais = query.all()

        return [
            {
                'fai_number': fai.fai_number,
                'part_number': fai.part_number,
                'status': fai.status,
                'created_at': fai.created_at.isoformat() if fai.created_at else None,
                'waiting_for': 'review' if fai.status == FAIStatus.PENDING_REVIEW.value else 'approval',
            }
            for fai in fais
        ]
