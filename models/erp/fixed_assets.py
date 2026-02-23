"""
LEGO Factory v3 - ERP Fixed Asset Models
=========================================
Fixed assets, depreciation entries, and asset disposals.
"""

from datetime import datetime, date
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, Date,
    ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class FixedAsset(AuditedModel):
    """Fixed asset record for depreciation and tracking."""

    __tablename__ = 'fixed_assets'

    asset_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    acquisition_date = Column(Date)
    acquisition_cost = Column(Float, default=0)
    useful_life_months = Column(Integer)
    salvage_value = Column(Float, default=0)
    depreciation_method = Column(String(50))  # 'straight_line', 'declining_balance', etc.
    accumulated_depreciation = Column(Float, default=0)
    impairment_loss = Column(Float, default=0)
    net_book_value = Column(Float, default=0)
    status = Column(String(50), default='active')  # 'active', 'disposed', 'fully_depreciated'
    location_id = Column(String(100))
    department = Column(String(100))

    # Additional tracking fields
    serial_number = Column(String(100))
    vendor_id = Column(String(50))
    warranty_expiry = Column(Date)
    last_depreciation_date = Column(Date)

    # Units-of-production method fields
    total_units_capacity = Column(Integer)
    units_produced = Column(Integer, default=0)

    # Relationships
    depreciation_entries = relationship('DepreciationEntry', back_populates='asset', cascade='all, delete-orphan')
    disposals = relationship('AssetDisposal', back_populates='asset', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_fixed_asset_category', 'category'),
        Index('ix_fixed_asset_status', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'asset_id': self.asset_id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'acquisition_date': self.acquisition_date.isoformat() if self.acquisition_date else None,
            'acquisition_cost': self.acquisition_cost,
            'useful_life_months': self.useful_life_months,
            'salvage_value': self.salvage_value,
            'depreciation_method': self.depreciation_method,
            'accumulated_depreciation': self.accumulated_depreciation,
            'impairment_loss': self.impairment_loss,
            'net_book_value': self.net_book_value,
            'status': self.status,
            'location_id': self.location_id,
            'department': self.department,
            'serial_number': self.serial_number,
            'vendor_id': self.vendor_id,
            'warranty_expiry': self.warranty_expiry.isoformat() if self.warranty_expiry else None,
            'last_depreciation_date': self.last_depreciation_date.isoformat() if self.last_depreciation_date else None,
            'total_units_capacity': self.total_units_capacity,
            'units_produced': self.units_produced,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class DepreciationEntry(BaseModel):
    """Depreciation entry for a fixed asset."""

    __tablename__ = 'depreciation_entries'

    entry_id = Column(String(50), unique=True, nullable=False, index=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey('fixed_assets.id'), nullable=False, index=True)
    period_start = Column(Date)
    period_end = Column(Date, nullable=False)
    depreciation_amount = Column(Float, nullable=False)
    accumulated_total = Column(Float, nullable=False)
    net_book_value = Column(Float)
    method = Column(String(50))

    # Relationships
    asset = relationship('FixedAsset', back_populates='depreciation_entries')

    __table_args__ = (
        Index('ix_depreciation_asset_period', 'asset_id', 'period_end'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'entry_id': self.entry_id,
            'asset_id': str(self.asset_id),
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'depreciation_amount': self.depreciation_amount,
            'accumulated_total': self.accumulated_total,
            'net_book_value': self.net_book_value,
            'method': self.method,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AssetDisposal(BaseModel):
    """Disposal record for a fixed asset."""

    __tablename__ = 'asset_disposals'

    disposal_id = Column(String(50), unique=True, nullable=False, index=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey('fixed_assets.id'), nullable=False, index=True)
    disposal_date = Column(Date, nullable=False)
    disposal_method = Column(String(50))  # 'sale', 'scrap', 'donation', 'trade_in'
    sale_price = Column(Float, default=0)
    net_book_value_at_disposal = Column(Float, default=0)
    gain_loss = Column(Float, default=0)
    buyer_info = Column(Text)
    reason = Column(Text)

    # Relationships
    asset = relationship('FixedAsset', back_populates='disposals')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'disposal_id': self.disposal_id,
            'asset_id': str(self.asset_id),
            'disposal_date': self.disposal_date.isoformat() if self.disposal_date else None,
            'disposal_method': self.disposal_method,
            'sale_price': self.sale_price,
            'net_book_value_at_disposal': self.net_book_value_at_disposal,
            'gain_loss': self.gain_loss,
            'buyer_info': self.buyer_info,
            'reason': self.reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
