"""
LEGO Factory v3 - ERP Tax Models
=================================
Tax jurisdictions, rates, and exemptions.
"""

from datetime import datetime, date
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, String, Float, Date, JSON, Index
)

from models.base import BaseModel


class TaxJurisdiction(BaseModel):
    """Tax jurisdiction definition."""

    __tablename__ = 'tax_jurisdictions'

    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    country = Column(String(100), nullable=False)
    state = Column(String(100), nullable=True)
    tax_types = Column(JSON, default=list)  # e.g. ['sales', 'use', 'vat']

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'code': self.code,
            'name': self.name,
            'country': self.country,
            'state': self.state,
            'tax_types': self.tax_types,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TaxRate(BaseModel):
    """Tax rate for a jurisdiction and tax type."""

    __tablename__ = 'tax_rates'

    jurisdiction_code = Column(String(50), nullable=False, index=True)
    tax_type = Column(String(50), nullable=False)
    rate = Column(Float, nullable=False)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    category = Column(String(100), nullable=True)  # product category override

    __table_args__ = (
        Index('ix_tax_rate_jurisdiction_type', 'jurisdiction_code', 'tax_type'),
        Index('ix_tax_rate_effective', 'effective_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'jurisdiction_code': self.jurisdiction_code,
            'tax_type': self.tax_type,
            'rate': self.rate,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TaxExemption(BaseModel):
    """Tax exemption certificate for an entity."""

    __tablename__ = 'tax_exemptions'

    entity_id = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)  # 'customer', 'vendor', 'organization'
    jurisdiction_code = Column(String(50), nullable=False)
    tax_type = Column(String(50), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    certificate_number = Column(String(100), nullable=True)

    __table_args__ = (
        Index('ix_tax_exempt_entity', 'entity_id', 'entity_type'),
        Index('ix_tax_exempt_jurisdiction', 'jurisdiction_code', 'tax_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'entity_id': self.entity_id,
            'entity_type': self.entity_type,
            'jurisdiction_code': self.jurisdiction_code,
            'tax_type': self.tax_type,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'certificate_number': self.certificate_number,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
