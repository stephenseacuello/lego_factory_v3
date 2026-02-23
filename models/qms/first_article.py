"""
LEGO Factory v3 - First Article Inspection Models
==================================================
FAI forms with characteristics stored as JSON for AS9102 compliance.
"""

from datetime import datetime
from typing import Dict, Any

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, JSON, Index
)

from models.base import AuditedModel


class FirstArticleInspection(AuditedModel):
    """First Article Inspection form (AS9102 compatible)."""

    __tablename__ = 'first_article_inspections'

    fai_number = Column(String(100), unique=True, nullable=False, index=True)
    part_number = Column(String(100), nullable=False, index=True)
    part_name = Column(String(200), nullable=False)
    revision = Column(String(50), nullable=False)

    # Identifiers
    serial_number = Column(String(100), default='')
    lot_number = Column(String(100), default='')
    work_order_id = Column(String(100), default='')

    # Drawing/Spec references
    drawing_number = Column(String(100), default='')
    drawing_revision = Column(String(50), default='')
    specification_refs = Column(JSON, default=list)

    # Production info
    machine_id = Column(String(100), default='')
    operator_id = Column(String(100), default='')
    production_date = Column(DateTime)
    quantity_inspected = Column(Integer, default=1)

    # Characteristics stored as JSON array
    characteristics = Column(JSON, default=list)

    # Attachments
    attachments = Column(JSON, default=list)

    # Status
    status = Column(String(50), default='draft', index=True)

    # Workflow - Inspector
    inspector_id = Column(String(100), default='')
    inspector_signature = Column(String(200), default='')
    inspection_date = Column(DateTime)

    # Workflow - Reviewer
    reviewer_id = Column(String(100), default='')
    reviewer_signature = Column(String(200), default='')
    review_date = Column(DateTime)
    review_comments = Column(Text, default='')

    # Workflow - Approver
    approver_id = Column(String(100), default='')
    approver_signature = Column(String(200), default='')
    approval_date = Column(DateTime)
    approval_comments = Column(Text, default='')

    # Results
    overall_result = Column(String(50), default='not_inspected')
    deviation_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)

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
            'characteristics': self.characteristics or [],
            'attachments': self.attachments or [],
            'status': self.status,
            'inspector_id': self.inspector_id,
            'inspection_date': self.inspection_date.isoformat() if self.inspection_date else None,
            'reviewer_id': self.reviewer_id,
            'review_date': self.review_date.isoformat() if self.review_date else None,
            'approver_id': self.approver_id,
            'approval_date': self.approval_date.isoformat() if self.approval_date else None,
            'overall_result': self.overall_result,
            'deviation_count': self.deviation_count,
            'fail_count': self.fail_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'summary': self._get_summary(),
        }

    def _get_summary(self) -> Dict[str, Any]:
        chars = self.characteristics or []
        total = len(chars)
        passed = len([c for c in chars if c.get('result') == 'pass'])
        failed = len([c for c in chars if c.get('result') == 'fail'])
        deviation = len([c for c in chars if c.get('result') == 'deviation'])
        not_inspected = len([c for c in chars if c.get('result', 'not_inspected') == 'not_inspected'])

        return {
            'total_characteristics': total,
            'passed': passed,
            'failed': failed,
            'deviations': deviation,
            'not_inspected': not_inspected,
            'completion_pct': round((total - not_inspected) / total * 100, 1) if total > 0 else 0,
            'pass_rate': round(passed / (total - not_inspected) * 100, 1) if (total - not_inspected) > 0 else 0,
        }
