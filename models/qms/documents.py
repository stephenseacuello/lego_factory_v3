"""
LEGO Factory v3 - QMS Document Models
======================================
Document control and e-signatures (21 CFR Part 11 compliant).
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index, LargeBinary
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from models.base import BaseModel, AuditedModel


class DocumentType(str, Enum):
    """Document types."""
    PROCEDURE = 'procedure'      # SOP, WI
    SPECIFICATION = 'specification'
    FORM = 'form'
    RECORD = 'record'
    DRAWING = 'drawing'
    REPORT = 'report'
    POLICY = 'policy'
    MANUAL = 'manual'
    EXTERNAL = 'external'


class DocumentStatus(str, Enum):
    """Document lifecycle status."""
    DRAFT = 'draft'
    PENDING_REVIEW = 'pending_review'
    UNDER_REVIEW = 'under_review'
    PENDING_APPROVAL = 'pending_approval'
    APPROVED = 'approved'
    EFFECTIVE = 'effective'
    SUPERSEDED = 'superseded'
    OBSOLETE = 'obsolete'


class ApprovalStatus(str, Enum):
    """Approval status."""
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    DELEGATED = 'delegated'


class DocumentCategory(AuditedModel):
    """Document category for organization."""

    __tablename__ = 'document_categories'

    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('document_categories.id'))

    # Retention
    retention_years = Column(Integer, default=7)

    # Default approvers
    default_approvers = Column(JSON, default=list)

    # Relationships
    parent = relationship('DocumentCategory', remote_side='DocumentCategory.id', backref='children')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'code': self.code,
            'name': self.name,
            'retention_years': self.retention_years,
        }


class Document(AuditedModel):
    """Controlled document."""

    __tablename__ = 'documents'

    document_number = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)

    # Classification
    document_type = Column(SQLEnum(DocumentType), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey('document_categories.id'))
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.DRAFT)

    # Version
    revision = Column(String(20), default='A')
    revision_date = Column(Date)
    effective_date = Column(Date)
    expiry_date = Column(Date)

    # Previous version
    previous_version_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'))

    # Ownership
    author_id = Column(String(50))
    owner_id = Column(String(50))
    department = Column(String(100))

    # Security
    confidentiality = Column(String(50), default='internal')  # public, internal, confidential, restricted

    # External references
    external_reference = Column(String(200))
    related_documents = Column(JSON, default=list)

    # Training
    requires_training = Column(Boolean, default=False)
    training_record_ids = Column(JSON, default=list)

    # Keywords for search
    keywords = Column(JSON, default=list)

    # Additional data (renamed from 'metadata' - reserved in SQLAlchemy)
    extra_data = Column(JSON, default=dict)

    # Relationships
    category = relationship('DocumentCategory')
    previous_version = relationship('Document', remote_side='Document.id')
    revisions = relationship('DocumentRevision', back_populates='document', cascade='all, delete-orphan')
    approvals = relationship('DocumentApproval', back_populates='document', cascade='all, delete-orphan')
    files = relationship('DocumentFile', back_populates='document', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_doc_status', 'status'),
        Index('ix_doc_type', 'document_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'document_number': self.document_number,
            'title': self.title,
            'document_type': self.document_type.value if self.document_type else None,
            'status': self.status.value if self.status else None,
            'revision': self.revision,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'author_id': self.author_id,
            'owner_id': self.owner_id,
        }


class DocumentRevision(AuditedModel):
    """Document revision history."""

    __tablename__ = 'document_revisions'

    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)
    revision = Column(String(20), nullable=False)
    revision_date = Column(Date, nullable=False)

    # Change description
    change_summary = Column(Text, nullable=False)
    change_details = Column(Text)

    # Who made the change
    revised_by = Column(String(50), nullable=False)

    # Approval reference
    approval_id = Column(UUID(as_uuid=True), ForeignKey('document_approvals.id'))

    # Relationships
    document = relationship('Document', back_populates='revisions')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'document_id': str(self.document_id),
            'revision': self.revision,
            'revision_date': self.revision_date.isoformat() if self.revision_date else None,
            'change_summary': self.change_summary,
            'revised_by': self.revised_by,
        }


class DocumentFile(AuditedModel):
    """File attachment for a document."""

    __tablename__ = 'document_files'

    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)

    filename = Column(String(500), nullable=False)
    file_type = Column(String(100))
    file_size = Column(Integer)

    # Storage
    storage_path = Column(String(1000))
    checksum = Column(String(64))  # SHA-256

    # File content (for small files)
    content = Column(LargeBinary)

    # Primary file flag
    is_primary = Column(Boolean, default=False)

    # Relationships
    document = relationship('Document', back_populates='files')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'document_id': str(self.document_id),
            'filename': self.filename,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'is_primary': self.is_primary,
        }


class DocumentApproval(AuditedModel):
    """Document approval record (e-signature)."""

    __tablename__ = 'document_approvals'

    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)

    # Approval workflow
    approval_type = Column(String(50), nullable=False)  # 'review', 'approve', 'release'
    sequence = Column(Integer, default=1)

    # Approver
    approver_id = Column(String(50), nullable=False)
    approver_name = Column(String(200))
    approver_role = Column(String(100))

    # Status
    status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING)

    # Timing
    requested_date = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime)
    completed_date = Column(DateTime)

    # E-Signature (21 CFR Part 11 compliant)
    signature_meaning = Column(String(200))  # e.g., "I approve this document"
    signature_timestamp = Column(DateTime)
    signature_hash = Column(String(256))  # Hash of user credentials + meaning + timestamp
    ip_address = Column(String(50))

    # Comments
    comments = Column(Text)
    rejection_reason = Column(Text)

    # Delegation
    delegated_to = Column(String(50))
    delegated_date = Column(DateTime)

    # Relationships
    document = relationship('Document', back_populates='approvals')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'document_id': str(self.document_id),
            'approval_type': self.approval_type,
            'approver_id': self.approver_id,
            'status': self.status.value if self.status else None,
            'completed_date': self.completed_date.isoformat() if self.completed_date else None,
            'comments': self.comments,
        }


class ESignature(AuditedModel):
    """E-Signature record (21 CFR Part 11 compliant)."""

    __tablename__ = 'e_signatures'

    # What was signed
    record_type = Column(String(100), nullable=False)
    record_id = Column(UUID(as_uuid=True), nullable=False)

    # Who signed
    user_id = Column(String(50), nullable=False)
    user_name = Column(String(200), nullable=False)
    user_title = Column(String(200))

    # Signature details
    meaning = Column(String(500), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Security
    signature_hash = Column(String(256), nullable=False)
    certificate_serial = Column(String(200))
    ip_address = Column(String(50))
    user_agent = Column(String(500))

    # Verification
    is_valid = Column(Boolean, default=True)
    invalidated_date = Column(DateTime)
    invalidated_reason = Column(Text)

    __table_args__ = (
        Index('ix_esig_record', 'record_type', 'record_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'record_type': self.record_type,
            'record_id': str(self.record_id),
            'user_id': self.user_id,
            'user_name': self.user_name,
            'meaning': self.meaning,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'is_valid': self.is_valid,
        }
