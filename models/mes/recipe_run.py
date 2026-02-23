"""
LEGO Factory v3 - Recipe Run Tracking Models
=============================================
Links production lots/jobs to recipe versions used,
with audit trail and effectiveness metrics.
"""

from datetime import datetime
from typing import Dict, Any

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, JSON, Index
)

from models.base import AuditedModel


class RecipeRun(AuditedModel):
    """Links a production lot to the recipe version used."""

    __tablename__ = 'recipe_runs'

    lot_id = Column(String(100), nullable=False, index=True)
    recipe_id = Column(String(100), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    version_id = Column(String(100))
    job_id = Column(String(100))
    quantity = Column(Integer, default=0)
    parameters_snapshot = Column(JSON, default=dict)

    # Effectiveness tracking
    good_quantity = Column(Integer)
    reject_quantity = Column(Integer)
    cycle_time = Column(Float)
    quality_score = Column(Float)

    __table_args__ = (
        Index('ix_recipe_runs_recipe_version', 'recipe_id', 'version_number'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'lot_id': self.lot_id,
            'recipe_id': self.recipe_id,
            'version_number': self.version_number,
            'version_id': self.version_id,
            'job_id': self.job_id,
            'quantity': self.quantity,
            'parameters_snapshot': self.parameters_snapshot,
            'good_quantity': self.good_quantity,
            'reject_quantity': self.reject_quantity,
            'cycle_time': self.cycle_time,
            'quality_score': self.quality_score,
            'linked_at': self.created_at.isoformat() if self.created_at else None,
        }


class RecipeAuditEntry(AuditedModel):
    """Recipe change audit trail entry."""

    __tablename__ = 'recipe_audit_entries'

    recipe_id = Column(String(100), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    action = Column(String(100), nullable=False)
    actor = Column(String(100), nullable=False)
    details = Column(JSON, default=dict)
    lot_id = Column(String(100))
    job_id = Column(String(100))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'recipe_id': self.recipe_id,
            'version_number': self.version_number,
            'action': self.action,
            'actor': self.actor,
            'timestamp': self.created_at.isoformat() if self.created_at else None,
            'details': self.details,
            'lot_id': self.lot_id,
            'job_id': self.job_id,
        }
