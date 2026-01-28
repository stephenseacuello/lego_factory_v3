"""
LEGO Factory v3 - NCR/CAPA Service
===================================
Non-Conformance and Corrective Action management.
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db_session

logger = logging.getLogger(__name__)


class NCRService:
    """Service for managing NCRs and CAPAs."""

    def __init__(self, session: Session):
        self.session = session

    def create_ncr(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a non-conformance report."""
        from models.qms.ncr_capa import NonConformanceReport, NCRType, NCRStatus, Severity

        ncr = NonConformanceReport(
            ncr_number=data.get('ncr_number', f"NCR-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"),
            ncr_type=NCRType(data.get('ncr_type', 'product')),
            severity=Severity(data.get('severity', 'minor')),
            status=NCRStatus.DRAFT,
            title=data['title'],
            description=data['description'],
            detected_date=data.get('detected_date', date.today()),
            detected_by=data['detected_by'],
            detection_location=data.get('detection_location'),
            detection_stage=data.get('detection_stage'),
            item_id=data.get('item_id'),
            lot_number=data.get('lot_number'),
            work_order_id=data.get('work_order_id'),
            quantity_affected=data.get('quantity_affected'),
            vendor_id=data.get('vendor_id'),
            customer_id=data.get('customer_id'),
            target_close_date=data.get('target_close_date'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(ncr)
        self.session.flush()

        logger.info(f"Created NCR: {ncr.ncr_number}")
        return ncr.to_dict()

    def get_ncr(self, ncr_number: str) -> Optional[Dict[str, Any]]:
        """Get an NCR by number."""
        from models.qms.ncr_capa import NonConformanceReport

        ncr = self.session.query(NonConformanceReport).filter(
            NonConformanceReport.ncr_number == ncr_number
        ).first()
        return ncr.to_dict() if ncr else None

    def get_ncrs(
        self,
        status: str = None,
        ncr_type: str = None,
        severity: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get NCRs with filtering."""
        from models.qms.ncr_capa import NonConformanceReport, NCRStatus, NCRType, Severity

        query = self.session.query(NonConformanceReport).filter(
            NonConformanceReport.is_deleted == False
        )

        if status:
            query = query.filter(NonConformanceReport.status == NCRStatus(status))
        if ncr_type:
            query = query.filter(NonConformanceReport.ncr_type == NCRType(ncr_type))
        if severity:
            query = query.filter(NonConformanceReport.severity == Severity(severity))

        ncrs = query.order_by(NonConformanceReport.created_at.desc()).limit(limit).all()
        return [n.to_dict() for n in ncrs]

    def set_disposition(
        self,
        ncr_number: str,
        disposition: str,
        reason: str,
        approved_by: str
    ) -> Optional[Dict[str, Any]]:
        """Set NCR disposition."""
        from models.qms.ncr_capa import NonConformanceReport, NCRStatus, DispositionType

        ncr = self.session.query(NonConformanceReport).filter(
            NonConformanceReport.ncr_number == ncr_number
        ).first()

        if not ncr:
            return None

        ncr.disposition = DispositionType(disposition)
        ncr.disposition_reason = reason
        ncr.disposition_approved_by = approved_by
        ncr.disposition_date = datetime.utcnow()
        ncr.status = NCRStatus.DISPOSITION_APPROVED
        ncr.updated_at = datetime.utcnow()

        self.session.flush()

        logger.info(f"NCR {ncr_number} disposition set to {disposition}")
        return ncr.to_dict()

    def close_ncr(
        self,
        ncr_number: str,
        user_id: str,
        actual_cost: float = None
    ) -> Optional[Dict[str, Any]]:
        """Close an NCR."""
        from models.qms.ncr_capa import NonConformanceReport, NCRStatus

        ncr = self.session.query(NonConformanceReport).filter(
            NonConformanceReport.ncr_number == ncr_number
        ).first()

        if not ncr:
            return None

        ncr.status = NCRStatus.CLOSED
        ncr.actual_close_date = date.today()
        if actual_cost is not None:
            ncr.actual_cost = actual_cost
        ncr.updated_at = datetime.utcnow()
        ncr.updated_by = user_id

        self.session.flush()

        logger.info(f"NCR {ncr_number} closed")
        return ncr.to_dict()

    def create_capa(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a CAPA."""
        from models.qms.ncr_capa import CAPA, CAPAType, CAPAStatus, NonConformanceReport

        ncr_id = None
        if data.get('ncr_number'):
            ncr = self.session.query(NonConformanceReport).filter(
                NonConformanceReport.ncr_number == data['ncr_number']
            ).first()
            if ncr:
                ncr_id = ncr.id
                ncr.capa_required = True

        capa = CAPA(
            capa_number=data.get('capa_number', f"CAPA-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"),
            capa_type=CAPAType(data.get('capa_type', 'corrective')),
            status=CAPAStatus.DRAFT,
            priority=data.get('priority', 'medium'),
            ncr_id=ncr_id,
            source_type=data.get('source_type', 'ncr'),
            source_reference=data.get('source_reference'),
            title=data['title'],
            problem_statement=data['problem_statement'],
            scope=data.get('scope'),
            owner_id=data['owner_id'],
            owner_department=data.get('owner_department'),
            target_completion_date=data.get('target_completion_date'),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(capa)
        self.session.flush()

        logger.info(f"Created CAPA: {capa.capa_number}")
        return capa.to_dict()

    def get_capa(self, capa_number: str) -> Optional[Dict[str, Any]]:
        """Get a CAPA by number."""
        from models.qms.ncr_capa import CAPA

        capa = self.session.query(CAPA).filter(CAPA.capa_number == capa_number).first()
        if not capa:
            return None

        result = capa.to_dict()
        result['actions'] = [a.to_dict() for a in capa.actions]
        return result

    def add_capa_action(self, capa_number: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add an action to a CAPA."""
        from models.qms.ncr_capa import CAPA, CAPAAction

        capa = self.session.query(CAPA).filter(CAPA.capa_number == capa_number).first()
        if not capa:
            return None

        action_number = len(capa.actions) + 1

        action = CAPAAction(
            capa_id=capa.id,
            action_number=action_number,
            action_type=data.get('action_type', 'short_term'),
            description=data['description'],
            assigned_to=data['assigned_to'],
            assigned_department=data.get('assigned_department'),
            target_date=data.get('target_date'),
            verification_required=data.get('verification_required', True),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(action)
        self.session.flush()

        return action.to_dict()

    def complete_capa_action(
        self,
        action_id: str,
        user_id: str,
        completion_notes: str,
        evidence: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Complete a CAPA action."""
        from models.qms.ncr_capa import CAPAAction

        action = self.session.query(CAPAAction).filter(CAPAAction.id == action_id).first()
        if not action:
            return None

        action.status = 'completed'
        action.completed_date = date.today()
        action.completion_notes = completion_notes
        action.evidence = evidence or []
        action.updated_at = datetime.utcnow()
        action.updated_by = user_id

        self.session.flush()

        return action.to_dict()

    def verify_capa_effectiveness(
        self,
        capa_number: str,
        is_effective: bool,
        result: str,
        reviewed_by: str
    ) -> Optional[Dict[str, Any]]:
        """Record CAPA effectiveness verification."""
        from models.qms.ncr_capa import CAPA, CAPAStatus

        capa = self.session.query(CAPA).filter(CAPA.capa_number == capa_number).first()
        if not capa:
            return None

        capa.is_effective = is_effective
        capa.effectiveness_result = result
        capa.effectiveness_reviewed_by = reviewed_by
        capa.effectiveness_review_date = datetime.utcnow()
        capa.status = CAPAStatus.CLOSED if is_effective else CAPAStatus.ACTION_PLANNING
        capa.actual_completion_date = date.today() if is_effective else None
        capa.updated_at = datetime.utcnow()

        self.session.flush()

        logger.info(f"CAPA {capa_number} effectiveness: {is_effective}")
        return capa.to_dict()

    def get_ncr_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get NCR metrics."""
        from models.qms.ncr_capa import NonConformanceReport, NCRStatus, Severity
        from datetime import timedelta

        start_date = date.today() - timedelta(days=days)

        total = self.session.query(func.count(NonConformanceReport.id)).filter(
            NonConformanceReport.detected_date >= start_date
        ).scalar()

        by_severity = self.session.query(
            NonConformanceReport.severity, func.count(NonConformanceReport.id)
        ).filter(
            NonConformanceReport.detected_date >= start_date
        ).group_by(NonConformanceReport.severity).all()

        open_count = self.session.query(func.count(NonConformanceReport.id)).filter(
            NonConformanceReport.status.notin_([NCRStatus.CLOSED, NCRStatus.VOIDED])
        ).scalar()

        return {
            'period_days': days,
            'total_ncrs': total,
            'open_ncrs': open_count,
            'by_severity': {s.value if s else 'unknown': c for s, c in by_severity},
        }


def get_ncr_service(session: Session = None) -> NCRService:
    """Get NCR service instance."""
    if session:
        return NCRService(session)
    with get_db_session() as session:
        return NCRService(session)
