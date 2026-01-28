"""
Unit tests for QMS Document Control Service.
Tests document lifecycle, e-signatures (21 CFR Part 11), and revision management.
"""

import pytest
from datetime import date
from unittest.mock import Mock, MagicMock, patch
import uuid

from services.qms.document_service import DocumentService, get_document_service


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return Mock(add=Mock(), flush=Mock(), query=Mock())


@pytest.fixture
def service(mock_session):
    """Create a DocumentService with mock session."""
    return DocumentService(mock_session)


class TestDocumentServiceBasics:
    """Tests for basic document operations."""

    def test_create_document_minimal(self, service, mock_session):
        """Test creating a document with minimal data."""
        with patch('models.qms.documents.Document') as MockDocument:
            mock_doc = Mock(document_number='DOC-20260121-ABCD')
            mock_doc.to_dict.return_value = {'title': 'Test Procedure', 'status': 'draft'}
            MockDocument.return_value = mock_doc
            result = service.create_document({'title': 'Test Procedure'})
        assert result['title'] == 'Test Procedure'
        assert result['status'] == 'draft'
        mock_session.add.assert_called_once()

    def test_get_document_existing(self, service, mock_session):
        """Test getting an existing document."""
        mock_doc = Mock(files=[], revisions=[], approvals=[])
        mock_doc.to_dict.return_value = {'document_number': 'DOC-001', 'status': 'draft'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_doc
        with patch('models.qms.documents.Document'):
            result = service.get_document('DOC-001')
        assert result is not None
        assert result['document_number'] == 'DOC-001'

    def test_get_document_nonexistent(self, service, mock_session):
        """Test getting a nonexistent document returns None."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        with patch('models.qms.documents.Document'):
            assert service.get_document('NONEXISTENT') is None

    def test_get_documents_with_filters(self, service, mock_session):
        """Test getting documents with filters."""
        mock_docs = [Mock(to_dict=Mock(return_value={'document_number': 'SOP-001'}))]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = mock_docs
        mock_session.query.return_value = mock_query
        with patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentType'), \
             patch('models.qms.documents.DocumentStatus'):
            result = service.get_documents(document_type='procedure', status='effective')
        assert len(result) == 1


class TestDocumentLifecycle:
    """Tests for document lifecycle transitions (draft -> review -> approved -> effective)."""

    def test_submit_for_review_success(self, service, mock_session):
        """Test submitting a draft document for review."""
        from models.qms.documents import DocumentStatus
        mock_doc = Mock(status=DocumentStatus.DRAFT)
        mock_doc.to_dict.return_value = {'status': 'pending_review'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_doc
        with patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentStatus', DocumentStatus):
            result = service.submit_for_review('DOC-001', 'user_001')
        assert result is not None
        assert mock_doc.status == DocumentStatus.PENDING_REVIEW

    def test_submit_for_review_wrong_status(self, service, mock_session):
        """Test submitting a non-draft document for review fails."""
        from models.qms.documents import DocumentStatus
        mock_doc = Mock(status=DocumentStatus.EFFECTIVE)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_doc
        with patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentStatus', DocumentStatus):
            assert service.submit_for_review('DOC-001', 'user_001') is None

    def test_make_effective_success(self, service, mock_session):
        """Test making an approved document effective."""
        from models.qms.documents import DocumentStatus
        mock_doc = Mock(status=DocumentStatus.APPROVED, previous_version_id=None)
        mock_doc.to_dict.return_value = {'status': 'effective'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_doc
        with patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentStatus', DocumentStatus):
            result = service.make_effective('DOC-001', date(2026, 1, 21), 'user_001')
        assert result is not None
        assert mock_doc.status == DocumentStatus.EFFECTIVE
        assert mock_doc.effective_date == date(2026, 1, 21)

    def test_make_effective_wrong_status(self, service, mock_session):
        """Test making a non-approved document effective fails."""
        from models.qms.documents import DocumentStatus
        mock_doc = Mock(status=DocumentStatus.DRAFT)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_doc
        with patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentStatus', DocumentStatus):
            assert service.make_effective('DOC-001', date(2026, 1, 21), 'user_001') is None


class TestApprovalWorkflow:
    """Tests for approval workflow."""

    def test_add_approval_success(self, service, mock_session):
        """Test adding an approval requirement."""
        mock_doc = Mock(id=str(uuid.uuid4()), approvals=[])
        mock_session.query.return_value.filter.return_value.first.return_value = mock_doc
        with patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentApproval') as MockApproval:
            mock_approval = Mock()
            mock_approval.to_dict.return_value = {'approval_type': 'review', 'sequence': 1}
            MockApproval.return_value = mock_approval
            result = service.add_approval('DOC-001', 'approver_001', 'review')
        assert result is not None
        assert result['approval_type'] == 'review'

    def test_add_approval_nonexistent_document(self, service, mock_session):
        """Test adding an approval to a nonexistent document fails."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        with patch('models.qms.documents.Document'):
            assert service.add_approval('NONEXISTENT', 'approver_001', 'review') is None

    def test_reject_approval_returns_document_to_draft(self, service, mock_session):
        """Test rejecting an approval returns the document to draft status."""
        from models.qms.documents import ApprovalStatus, DocumentStatus
        mock_approval = Mock(id=str(uuid.uuid4()), document_id=str(uuid.uuid4()))
        mock_approval.to_dict.return_value = {'status': 'rejected'}
        mock_doc = Mock(status=DocumentStatus.PENDING_REVIEW)
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value.first.side_effect = [mock_approval, mock_doc]
        with patch('models.qms.documents.DocumentApproval'), \
             patch('models.qms.documents.Document'), \
             patch('models.qms.documents.ApprovalStatus', ApprovalStatus), \
             patch('models.qms.documents.DocumentStatus', DocumentStatus):
            result = service.reject_approval(mock_approval.id, 'user_001', 'Missing sections')
        assert result is not None
        assert mock_approval.status == ApprovalStatus.REJECTED
        assert mock_approval.rejection_reason == 'Missing sections'


class TestESignatureWorkflow:
    """Tests for 21 CFR Part 11 compliant e-signature workflow."""

    def test_sign_approval_success(self, service, mock_session):
        """Test signing an approval with e-signature."""
        from models.qms.documents import ApprovalStatus
        mock_approval = Mock(
            id=str(uuid.uuid4()), status=ApprovalStatus.PENDING,
            approver_id='user_001', document_id=str(uuid.uuid4())
        )
        mock_document = Mock(id=mock_approval.document_id, document_number='DOC-001')
        mock_approval.to_dict.return_value = {'id': mock_approval.id, 'status': 'approved'}

        # Return different mocks for approval vs document queries
        def side_effect_query(model):
            mock_query = Mock()
            mock_filter = Mock()
            if hasattr(model, '__name__') and 'Document' in str(model.__name__):
                mock_filter.first.return_value = mock_document
            else:
                mock_filter.first.return_value = mock_approval
            mock_filter.count.return_value = 0  # No pending approvals
            mock_query.filter.return_value = mock_filter
            return mock_query

        mock_session.query.side_effect = side_effect_query
        with patch('models.qms.documents.DocumentApproval'), \
             patch('models.qms.documents.ApprovalStatus', ApprovalStatus), \
             patch('models.qms.documents.ESignature'), \
             patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentStatus'):
            result = service.sign_approval(
                mock_approval.id, 'user_001', 'John Doe',
                'I approve this document', 'hashed_password', '192.168.1.1'
            )
        assert result is not None
        assert mock_approval.signature_meaning == 'I approve this document'
        assert mock_approval.ip_address == '192.168.1.1'

    def test_sign_approval_wrong_user_fails(self, service, mock_session):
        """Test that only the assigned approver can sign."""
        from models.qms.documents import ApprovalStatus
        mock_approval = Mock(status=ApprovalStatus.PENDING, approver_id='user_001')
        mock_session.query.return_value.filter.return_value.first.return_value = mock_approval
        with patch('models.qms.documents.DocumentApproval'), \
             patch('models.qms.documents.ApprovalStatus', ApprovalStatus):
            result = service.sign_approval(
                str(uuid.uuid4()), 'user_002', 'Jane Doe', 'I approve', 'hash'
            )
        assert result is None

    def test_sign_approval_already_approved_fails(self, service, mock_session):
        """Test signing an already approved approval fails."""
        from models.qms.documents import ApprovalStatus
        mock_approval = Mock(status=ApprovalStatus.APPROVED)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_approval
        with patch('models.qms.documents.DocumentApproval'), \
             patch('models.qms.documents.ApprovalStatus', ApprovalStatus):
            result = service.sign_approval(
                str(uuid.uuid4()), 'user_001', 'John Doe', 'I approve', 'hash'
            )
        assert result is None


class TestRevisionManagement:
    """Tests for document revision management."""

    def test_create_new_revision_success(self, service, mock_session):
        """Test creating a new revision of an effective document."""
        from models.qms.documents import DocumentStatus
        mock_current = Mock(
            id=str(uuid.uuid4()), status=DocumentStatus.EFFECTIVE, revision='A',
            document_number='DOC-001', title='Test', description=None,
            document_type='procedure', category_id=None, owner_id='owner',
            department='QA', confidentiality='internal', requires_training=False,
            keywords=[], metadata={}
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_current
        with patch('models.qms.documents.Document') as MockDocument, \
             patch('models.qms.documents.DocumentRevision'), \
             patch('models.qms.documents.DocumentStatus', DocumentStatus):
            mock_new_doc = Mock(id=str(uuid.uuid4()))
            mock_new_doc.to_dict.return_value = {'revision': 'B', 'status': 'draft'}
            MockDocument.return_value = mock_new_doc
            result = service.create_new_revision('DOC-001', 'user_001', 'Updated procedures')
        assert result is not None
        assert result['revision'] == 'B'
        assert result['status'] == 'draft'
        assert mock_session.add.call_count == 2  # Document and Revision

    def test_create_new_revision_wrong_status_fails(self, service, mock_session):
        """Test creating a revision of a non-effective document fails."""
        from models.qms.documents import DocumentStatus
        mock_current = Mock(status=DocumentStatus.DRAFT)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_current
        with patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentStatus', DocumentStatus):
            assert service.create_new_revision('DOC-001', 'user_001', 'Changes') is None

    def test_create_new_revision_nonexistent_fails(self, service, mock_session):
        """Test creating a revision of a nonexistent document fails."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        with patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentStatus'):
            assert service.create_new_revision('NONEXISTENT', 'user_001', 'Changes') is None


class Test21CFRPart11Compliance:
    """Tests for 21 CFR Part 11 e-signature compliance requirements."""

    def test_signature_includes_timestamp_and_meaning(self, service, mock_session):
        """Test that e-signature includes timestamp and meaning per 21 CFR Part 11."""
        from models.qms.documents import ApprovalStatus
        mock_approval = Mock(
            id=str(uuid.uuid4()), status=ApprovalStatus.PENDING,
            approver_id='user_001', document_id=str(uuid.uuid4())
        )
        mock_approval.to_dict.return_value = {'id': mock_approval.id}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_approval
        mock_session.query.return_value.filter.return_value.count.return_value = 0
        with patch('models.qms.documents.DocumentApproval'), \
             patch('models.qms.documents.ApprovalStatus', ApprovalStatus), \
             patch('models.qms.documents.ESignature'), \
             patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentStatus'):
            service.sign_approval(mock_approval.id, 'user_001', 'John Doe', 'I approve', 'hash')
        assert mock_approval.signature_timestamp is not None
        assert mock_approval.signature_meaning == 'I approve'

    def test_signature_hash_is_sha256(self, service, mock_session):
        """Test that cryptographic signature hash is SHA-256 (64 hex characters)."""
        from models.qms.documents import ApprovalStatus
        mock_approval = Mock(
            id=str(uuid.uuid4()), status=ApprovalStatus.PENDING,
            approver_id='user_001', document_id=str(uuid.uuid4())
        )
        mock_approval.to_dict.return_value = {'id': mock_approval.id}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_approval
        mock_session.query.return_value.filter.return_value.count.return_value = 0
        with patch('models.qms.documents.DocumentApproval'), \
             patch('models.qms.documents.ApprovalStatus', ApprovalStatus), \
             patch('models.qms.documents.ESignature'), \
             patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentStatus'):
            service.sign_approval(mock_approval.id, 'user_001', 'John Doe', 'I approve', 'hash')
        assert mock_approval.signature_hash is not None
        assert len(mock_approval.signature_hash) == 64

    def test_esignature_record_created_for_audit(self, service, mock_session):
        """Test that a separate e-signature record is created for audit trail."""
        from models.qms.documents import ApprovalStatus
        mock_approval = Mock(
            id=str(uuid.uuid4()), status=ApprovalStatus.PENDING,
            approver_id='user_001', document_id=str(uuid.uuid4())
        )
        mock_approval.to_dict.return_value = {'id': mock_approval.id}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_approval
        mock_session.query.return_value.filter.return_value.count.return_value = 0
        with patch('models.qms.documents.DocumentApproval'), \
             patch('models.qms.documents.ApprovalStatus', ApprovalStatus), \
             patch('models.qms.documents.ESignature') as MockESignature, \
             patch('models.qms.documents.Document'), \
             patch('models.qms.documents.DocumentStatus'):
            service.sign_approval(
                mock_approval.id, 'user_001', 'John Doe', 'I approve', 'hash', '192.168.1.1'
            )
        MockESignature.assert_called_once()
        call_kwargs = MockESignature.call_args[1]
        assert call_kwargs['record_type'] == 'document_approval'
        assert call_kwargs['user_id'] == 'user_001'
        assert call_kwargs['ip_address'] == '192.168.1.1'


class TestGetDocumentService:
    """Tests for get_document_service factory function."""

    def test_with_provided_session(self):
        """Test getting service with provided session."""
        mock_session = Mock()
        service = get_document_service(mock_session)
        assert isinstance(service, DocumentService)
        assert service.session == mock_session

    def test_without_provided_session(self):
        """Test getting service creates new session."""
        with patch('services.qms.document_service.get_db_session') as mock_get_session:
            mock_context = MagicMock()
            mock_context.__enter__.return_value = Mock()
            mock_get_session.return_value = mock_context
            service = get_document_service()
            assert isinstance(service, DocumentService)
