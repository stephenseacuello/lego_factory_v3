"""
LEGO Factory v3 - ERP Bank Reconciliation Models
=================================================
Bank transactions, reconciliation sessions, and outstanding checks.
"""

from datetime import datetime, date
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, String, Float, DateTime, Text, Date, JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class BankTransaction(BaseModel):
    """Bank transaction imported from bank statement."""

    __tablename__ = 'bank_transactions'

    bank_account_id = Column(String(100), nullable=False, index=True)
    transaction_date = Column(Date, nullable=False, index=True)
    post_date = Column(Date, nullable=True)
    transaction_type = Column(String(50), default='other')
    amount = Column(Float, nullable=False)
    description = Column(Text)
    reference = Column(String(200))
    check_number = Column(String(50), nullable=True)
    match_status = Column(String(50), default='unmatched')
    matched_gl_entry_id = Column(String(100), nullable=True)
    matched_at = Column(DateTime, nullable=True)
    imported_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('ix_bank_tx_account_date', 'bank_account_id', 'transaction_date'),
        Index('ix_bank_tx_match_status', 'match_status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'bank_account_id': self.bank_account_id,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'post_date': self.post_date.isoformat() if self.post_date else None,
            'transaction_type': self.transaction_type,
            'amount': self.amount,
            'description': self.description,
            'reference': self.reference,
            'check_number': self.check_number,
            'match_status': self.match_status,
            'matched_gl_entry_id': self.matched_gl_entry_id,
            'matched_at': self.matched_at.isoformat() if self.matched_at else None,
            'imported_at': self.imported_at.isoformat() if self.imported_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ReconciliationSession(AuditedModel):
    """Bank reconciliation session."""

    __tablename__ = 'reconciliation_sessions'

    bank_account_id = Column(String(100), nullable=False, index=True)
    statement_date = Column(Date, nullable=False)
    ending_balance = Column(Float, nullable=False)
    book_balance = Column(Float, nullable=True)
    status = Column(String(50), default='in_progress')
    completed_at = Column(DateTime, nullable=True)
    approved_by = Column(String(100), nullable=True)
    adjustments = Column(JSON, default=list)
    transactions_imported = Column(Float, default=0)
    transactions_matched = Column(Float, default=0)
    transactions_unmatched = Column(Float, default=0)

    __table_args__ = (
        Index('ix_recon_account_date', 'bank_account_id', 'statement_date'),
        Index('ix_recon_status', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'bank_account_id': self.bank_account_id,
            'statement_date': self.statement_date.isoformat() if self.statement_date else None,
            'ending_balance': self.ending_balance,
            'book_balance': self.book_balance,
            'status': self.status,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'approved_by': self.approved_by,
            'adjustments': self.adjustments,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class OutstandingCheck(BaseModel):
    """Outstanding check record for bank reconciliation."""

    __tablename__ = 'outstanding_checks'

    bank_account_id = Column(String(100), nullable=False, index=True)
    check_number = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    issued_date = Column(Date, nullable=False)
    payee = Column(String(200), nullable=False)
    gl_entry_id = Column(String(100), nullable=True)
    status = Column(String(50), default='outstanding')
    cleared_date = Column(Date, nullable=True)

    __table_args__ = (
        Index('ix_outstanding_check_account', 'bank_account_id', 'check_number'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'bank_account_id': self.bank_account_id,
            'check_number': self.check_number,
            'amount': self.amount,
            'issued_date': self.issued_date.isoformat() if self.issued_date else None,
            'payee': self.payee,
            'gl_entry_id': self.gl_entry_id,
            'status': self.status,
            'cleared_date': self.cleared_date.isoformat() if self.cleared_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
