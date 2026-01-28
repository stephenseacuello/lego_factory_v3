"""
LEGO Factory v3 - Document Control Service
==========================================
Document management with e-signatures (21 CFR Part 11 compliant).
"""

import logging
import hashlib
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import func

from config.database import get_db_session

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document control."""

    def __init__(self, session: Session):
        self.session = session

    def create_document(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new controlled document."""
        from models.qms.documents import Document, DocumentType, DocumentStatus

        document = Document(
            document_number=data.get('document_number', f"DOC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"),
            title=data['title'],
            description=data.get('description'),
            document_type=DocumentType(data.get('document_type', 'procedure')),
            category_id=data.get('category_id'),
            status=DocumentStatus.DRAFT,
            revision=data.get('revision', 'A'),
            author_id=data.get('author_id'),
            owner_id=data.get('owner_id'),
            department=data.get('department'),
            confidentiality=data.get('confidentiality', 'internal'),
            requires_training=data.get('requires_training', False),
            keywords=data.get('keywords', []),
            metadata=data.get('metadata', {}),
            created_by=data.get('created_by', 'system'),
        )

        self.session.add(document)
        self.session.flush()

        logger.info(f"Created document: {document.document_number}")
        return document.to_dict()

    def get_document(self, document_number: str) -> Optional[Dict[str, Any]]:
        """Get a document by number."""
        from models.qms.documents import Document

        doc = self.session.query(Document).filter(
            Document.document_number == document_number
        ).first()

        if not doc:
            return None

        result = doc.to_dict()
        result['files'] = [f.to_dict() for f in doc.files]
        result['revisions'] = [r.to_dict() for r in doc.revisions]
        result['approvals'] = [a.to_dict() for a in doc.approvals]
        return result

    def get_documents(
        self,
        document_type: str = None,
        status: str = None,
        category_id: str = None,
        search: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get documents with filtering."""
        from models.qms.documents import Document, DocumentType, DocumentStatus

        query = self.session.query(Document).filter(Document.is_deleted == False)

        if document_type:
            query = query.filter(Document.document_type == DocumentType(document_type))
        if status:
            query = query.filter(Document.status == DocumentStatus(status))
        if category_id:
            query = query.filter(Document.category_id == category_id)
        if search:
            query = query.filter(
                (Document.document_number.ilike(f'%{search}%')) |
                (Document.title.ilike(f'%{search}%'))
            )

        docs = query.order_by(Document.document_number).limit(limit).all()
        return [d.to_dict() for d in docs]

    def submit_for_review(self, document_number: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Submit document for review."""
        from models.qms.documents import Document, DocumentStatus

        doc = self.session.query(Document).filter(
            Document.document_number == document_number
        ).first()

        if not doc or doc.status != DocumentStatus.DRAFT:
            return None

        doc.status = DocumentStatus.PENDING_REVIEW
        doc.updated_at = datetime.utcnow()
        doc.updated_by = user_id
        self.session.flush()

        logger.info(f"Document {document_number} submitted for review")
        return doc.to_dict()

    def add_approval(
        self,
        document_number: str,
        approver_id: str,
        approval_type: str,
        due_date: datetime = None
    ) -> Optional[Dict[str, Any]]:
        """Add an approval requirement."""
        from models.qms.documents import Document, DocumentApproval

        doc = self.session.query(Document).filter(
            Document.document_number == document_number
        ).first()

        if not doc:
            return None

        sequence = len(doc.approvals) + 1

        approval = DocumentApproval(
            document_id=doc.id,
            approval_type=approval_type,
            sequence=sequence,
            approver_id=approver_id,
            due_date=due_date,
            created_by='system',
        )

        self.session.add(approval)
        self.session.flush()

        return approval.to_dict()

    def sign_approval(
        self,
        approval_id: str,
        user_id: str,
        user_name: str,
        meaning: str,
        password_hash: str,
        ip_address: str = None,
        comments: str = None
    ) -> Optional[Dict[str, Any]]:
        """Sign an approval (e-signature)."""
        from models.qms.documents import DocumentApproval, ApprovalStatus, ESignature

        approval = self.session.query(DocumentApproval).filter(
            DocumentApproval.id == approval_id
        ).first()

        if not approval or approval.status != ApprovalStatus.PENDING:
            return None

        if approval.approver_id != user_id:
            return None

        # Create signature hash (21 CFR Part 11 compliant)
        timestamp = datetime.utcnow()
        signature_data = f"{user_id}|{meaning}|{timestamp.isoformat()}|{password_hash}"
        signature_hash = hashlib.sha256(signature_data.encode()).hexdigest()

        # Record e-signature
        esig = ESignature(
            record_type='document_approval',
            record_id=approval.id,
            user_id=user_id,
            user_name=user_name,
            meaning=meaning,
            timestamp=timestamp,
            signature_hash=signature_hash,
            ip_address=ip_address,
            created_by=user_id,
        )

        self.session.add(esig)

        # Update approval
        approval.status = ApprovalStatus.APPROVED
        approval.completed_date = timestamp
        approval.signature_meaning = meaning
        approval.signature_timestamp = timestamp
        approval.signature_hash = signature_hash
        approval.ip_address = ip_address
        approval.comments = comments

        self.session.flush()

        # Check if all approvals complete
        self._check_approval_complete(approval.document_id)

        logger.info(f"Approval {approval_id} signed by {user_id}")
        return approval.to_dict()

    def reject_approval(
        self,
        approval_id: str,
        user_id: str,
        reason: str
    ) -> Optional[Dict[str, Any]]:
        """Reject an approval."""
        from models.qms.documents import DocumentApproval, Document, ApprovalStatus, DocumentStatus

        approval = self.session.query(DocumentApproval).filter(
            DocumentApproval.id == approval_id
        ).first()

        if not approval:
            return None

        approval.status = ApprovalStatus.REJECTED
        approval.completed_date = datetime.utcnow()
        approval.rejection_reason = reason

        # Return document to draft
        doc = self.session.query(Document).filter(Document.id == approval.document_id).first()
        if doc:
            doc.status = DocumentStatus.DRAFT

        self.session.flush()

        logger.info(f"Approval {approval_id} rejected by {user_id}")
        return approval.to_dict()

    def _check_approval_complete(self, document_id: str):
        """Check if all approvals are complete and update document status."""
        from models.qms.documents import Document, DocumentApproval, ApprovalStatus, DocumentStatus

        doc = self.session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return

        pending = self.session.query(DocumentApproval).filter(
            DocumentApproval.document_id == document_id,
            DocumentApproval.status == ApprovalStatus.PENDING
        ).count()

        if pending == 0:
            # All approvals complete
            doc.status = DocumentStatus.APPROVED
            doc.updated_at = datetime.utcnow()
            self.session.flush()
            logger.info(f"Document {doc.document_number} fully approved")

    def make_effective(
        self,
        document_number: str,
        effective_date: date,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Make an approved document effective."""
        from models.qms.documents import Document, DocumentStatus

        doc = self.session.query(Document).filter(
            Document.document_number == document_number
        ).first()

        if not doc or doc.status != DocumentStatus.APPROVED:
            return None

        # Supersede previous version
        if doc.previous_version_id:
            prev = self.session.query(Document).filter(
                Document.id == doc.previous_version_id
            ).first()
            if prev:
                prev.status = DocumentStatus.SUPERSEDED
                prev.updated_at = datetime.utcnow()

        doc.status = DocumentStatus.EFFECTIVE
        doc.effective_date = effective_date
        doc.revision_date = effective_date
        doc.updated_at = datetime.utcnow()
        doc.updated_by = user_id

        self.session.flush()

        logger.info(f"Document {document_number} made effective on {effective_date}")
        return doc.to_dict()

    def create_new_revision(
        self,
        document_number: str,
        user_id: str,
        change_summary: str
    ) -> Optional[Dict[str, Any]]:
        """Create a new revision of a document."""
        from models.qms.documents import Document, DocumentRevision, DocumentStatus

        current = self.session.query(Document).filter(
            Document.document_number == document_number
        ).first()

        if not current or current.status != DocumentStatus.EFFECTIVE:
            return None

        # Increment revision
        new_revision = chr(ord(current.revision[0]) + 1) if current.revision else 'B'

        new_doc = Document(
            document_number=document_number,
            title=current.title,
            description=current.description,
            document_type=current.document_type,
            category_id=current.category_id,
            status=DocumentStatus.DRAFT,
            revision=new_revision,
            previous_version_id=current.id,
            author_id=user_id,
            owner_id=current.owner_id,
            department=current.department,
            confidentiality=current.confidentiality,
            requires_training=current.requires_training,
            keywords=current.keywords,
            metadata=current.metadata,
            created_by=user_id,
        )

        self.session.add(new_doc)
        self.session.flush()

        # Record revision
        revision = DocumentRevision(
            document_id=new_doc.id,
            revision=new_revision,
            revision_date=date.today(),
            change_summary=change_summary,
            revised_by=user_id,
            created_by=user_id,
        )

        self.session.add(revision)
        self.session.flush()

        logger.info(f"Created new revision {new_revision} of document {document_number}")
        return new_doc.to_dict()


def get_document_service(session: Session = None) -> DocumentService:
    """Get document service instance."""
    if session:
        return DocumentService(session)
    with get_db_session() as session:
        return DocumentService(session)
