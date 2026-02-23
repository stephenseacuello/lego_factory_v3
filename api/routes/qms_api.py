"""
LEGO Factory v3 - QMS API
==========================
REST API endpoints for Quality Management System.

Provides endpoints for:
- Document control
- NCR (Non-Conformance Reports)
- CAPA (Corrective and Preventive Actions)
- E-signatures (21 CFR Part 11)
"""

import logging
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

logger = logging.getLogger(__name__)

qms_api_bp = Blueprint('qms_api', __name__, url_prefix='/api/qms')


# ─────────────────────────────────────────────────────────────────────────────
# Documents
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/documents', methods=['GET'])
@jwt_required()
def list_documents():
    """
    List controlled documents.

    Query params:
    - type: Filter by document type
    - status: Filter by status
    - category_id: Filter by category
    - search: Search in title/number
    - limit: Max results
    """
    try:
        from config.database import get_db_session
        from services.qms.document_service import DocumentService

        with get_db_session() as session:
            service = DocumentService(session)
            documents = service.get_documents(
                document_type=request.args.get('type'),
                status=request.args.get('status'),
                category_id=request.args.get('category_id'),
                search=request.args.get('search'),
                limit=int(request.args.get('limit', 100)),
            )

            return jsonify({
                'documents': documents,
                'count': len(documents),
            })
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_documents
            data = get_demo_documents()
            return jsonify({**data, 'demo': True})

        logger.error(f"QMS service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'QMS service unavailable',
            'message': 'The Quality Management System is not available. Please check system status.'
        }), 503


@qms_api_bp.route('/documents', methods=['POST'])
@jwt_required()
def create_document():
    """Create a new controlled document."""
    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify({'error': 'title required'}), 400

    try:
        from config.database import get_db_session
        from services.qms.document_service import DocumentService

        with get_db_session() as session:
            service = DocumentService(session)
            document = service.create_document(data)

            return jsonify(document), 201
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/documents/<document_number>', methods=['GET'])
@jwt_required()
def get_document(document_number: str):
    """Get a specific document with its history."""
    try:
        from config.database import get_db_session
        from services.qms.document_service import DocumentService

        with get_db_session() as session:
            service = DocumentService(session)
            document = service.get_document(document_number)

            if not document:
                return jsonify({'error': 'Document not found'}), 404

            return jsonify(document)
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_document_detail
            data = get_demo_document_detail(document_number)
            return jsonify({**data, 'demo': True})

        logger.error(f"Error getting document: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/documents/<document_number>/submit-review', methods=['POST'])
@jwt_required()
def submit_document_review(document_number: str):
    """Submit document for review."""
    data = request.get_json() or {}

    try:
        from config.database import get_db_session
        from services.qms.document_service import DocumentService

        with get_db_session() as session:
            service = DocumentService(session)
            document = service.submit_for_review(
                document_number,
                user_id=data.get('user_id', 'system')
            )

            if not document:
                return jsonify({'error': 'Document not found or not in draft status'}), 400

            return jsonify(document)
    except Exception as e:
        logger.error(f"Error submitting document for review: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/documents/<document_number>/approvals', methods=['POST'])
@jwt_required()
def add_document_approval(document_number: str):
    """Add an approval requirement to a document."""
    data = request.get_json()
    if not data or 'approver_id' not in data:
        return jsonify({'error': 'approver_id required'}), 400

    try:
        from config.database import get_db_session
        from services.qms.document_service import DocumentService

        with get_db_session() as session:
            due_date = None
            if data.get('due_date'):
                due_date = datetime.fromisoformat(data['due_date'])

            service = DocumentService(session)
            approval = service.add_approval(
                document_number,
                approver_id=data['approver_id'],
                approval_type=data.get('approval_type', 'approve'),
                due_date=due_date,
            )

            if not approval:
                return jsonify({'error': 'Document not found'}), 404

            return jsonify(approval), 201
    except Exception as e:
        logger.error(f"Error adding approval: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/approvals/<approval_id>/sign', methods=['POST'])
@jwt_required()
def sign_approval(approval_id: str):
    """
    Sign an approval with e-signature (21 CFR Part 11 compliant).

    JSON body:
    - user_id: User signing
    - user_name: Full name
    - meaning: Signature meaning (e.g., "I approve this document")
    - password_hash: Hash of user's password for verification
    - comments: Optional comments
    """
    data = request.get_json()
    required = ['user_id', 'user_name', 'meaning', 'password_hash']
    if not data or not all(k in data for k in required):
        return jsonify({'error': f'{required} required'}), 400

    try:
        from config.database import get_db_session
        from services.qms.document_service import DocumentService

        with get_db_session() as session:
            service = DocumentService(session)
            approval = service.sign_approval(
                approval_id=approval_id,
                user_id=data['user_id'],
                user_name=data['user_name'],
                meaning=data['meaning'],
                password_hash=data['password_hash'],
                ip_address=request.remote_addr,
                comments=data.get('comments'),
            )

            if not approval:
                return jsonify({'error': 'Approval not found or not pending'}), 400

            return jsonify(approval)
    except Exception as e:
        logger.error(f"Error signing approval: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/approvals/<approval_id>/reject', methods=['POST'])
@jwt_required()
def reject_approval(approval_id: str):
    """Reject an approval."""
    data = request.get_json()
    if not data or 'reason' not in data:
        return jsonify({'error': 'reason required'}), 400

    try:
        from config.database import get_db_session
        from services.qms.document_service import DocumentService

        with get_db_session() as session:
            service = DocumentService(session)
            approval = service.reject_approval(
                approval_id=approval_id,
                user_id=data.get('user_id', 'system'),
                reason=data['reason'],
            )

            if not approval:
                return jsonify({'error': 'Approval not found'}), 404

            return jsonify(approval)
    except Exception as e:
        logger.error(f"Error rejecting approval: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/documents/<document_number>/make-effective', methods=['POST'])
@jwt_required()
def make_document_effective(document_number: str):
    """Make an approved document effective."""
    data = request.get_json() or {}

    try:
        from config.database import get_db_session
        from services.qms.document_service import DocumentService

        with get_db_session() as session:
            effective_date = date.today()
            if data.get('effective_date'):
                effective_date = date.fromisoformat(data['effective_date'])

            service = DocumentService(session)
            document = service.make_effective(
                document_number,
                effective_date=effective_date,
                user_id=data.get('user_id', 'system'),
            )

            if not document:
                return jsonify({'error': 'Document not found or not approved'}), 400

            return jsonify(document)
    except Exception as e:
        logger.error(f"Error making document effective: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/documents/<document_number>/revise', methods=['POST'])
@jwt_required()
def create_document_revision(document_number: str):
    """Create a new revision of an effective document."""
    data = request.get_json()
    if not data or 'change_summary' not in data:
        return jsonify({'error': 'change_summary required'}), 400

    try:
        from config.database import get_db_session
        from services.qms.document_service import DocumentService

        with get_db_session() as session:
            service = DocumentService(session)
            document = service.create_new_revision(
                document_number,
                user_id=data.get('user_id', 'system'),
                change_summary=data['change_summary'],
            )

            if not document:
                return jsonify({'error': 'Document not found or not effective'}), 400

            return jsonify(document), 201
    except Exception as e:
        logger.error(f"Error creating revision: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# NCR (Non-Conformance Reports)
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/ncrs', methods=['GET'])
@jwt_required()
def list_ncrs():
    """List Non-Conformance Reports."""
    try:
        from config.database import get_db_session
        from services.qms.ncr_service import NCRService

        with get_db_session() as session:
            service = NCRService(session)
            ncrs = service.get_ncrs(
                status=request.args.get('status'),
                severity=request.args.get('severity'),
                limit=int(request.args.get('limit', 100)),
            )
            return jsonify({'ncrs': ncrs, 'count': len(ncrs)})
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_ncrs
            data = get_demo_ncrs()
            return jsonify({**data, 'demo': True})

        logger.error(f"QMS service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'QMS service unavailable',
            'message': 'The Quality Management System is not available. Please check system status.'
        }), 503


@qms_api_bp.route('/ncrs', methods=['POST'])
@jwt_required()
def create_ncr():
    """Create a new NCR."""
    data = request.get_json()
    if not data or 'description' not in data:
        return jsonify({'error': 'description required'}), 400

    try:
        from config.database import get_db_session
        from services.qms.ncr_service import NCRService

        ncr_data = {
            'title': data.get('title', data['description'][:200]),
            'description': data['description'],
            'ncr_type': data.get('ncr_type', data.get('source', 'product')),
            'severity': data.get('severity', 'minor'),
            'detected_by': data.get('detected_by', 'system'),
            'detection_location': data.get('detection_location'),
            'detection_stage': data.get('detection_stage'),
            'item_id': data.get('item_id'),
            'lot_number': data.get('lot_number'),
            'work_order_id': data.get('work_order_id'),
            'quantity_affected': data.get('quantity_affected'),
            'vendor_id': data.get('vendor_id'),
            'target_close_date': data.get('target_close_date'),
        }

        with get_db_session() as session:
            service = NCRService(session)
            result = service.create_ncr(ncr_data)
            session.commit()
            return jsonify(result), 201
    except Exception as e:
        logger.error(f"Failed to create NCR: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create NCR', 'message': str(e)}), 500


@qms_api_bp.route('/ncrs/<ncr_number>', methods=['GET'])
@jwt_required()
def get_ncr(ncr_number: str):
    """Get NCR details."""
    try:
        from config.database import get_db_session
        from services.qms.ncr_service import NCRService

        with get_db_session() as session:
            service = NCRService(session)
            result = service.get_ncr(ncr_number)
            if not result:
                return jsonify({'error': 'NCR not found'}), 404
            return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to get NCR {ncr_number}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get NCR', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# CAPA (Corrective and Preventive Actions)
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/capas', methods=['GET'])
@jwt_required()
def list_capas():
    """List CAPAs."""
    try:
        from config.database import get_db_session
        from models.qms.ncr_capa import CAPA, CAPAStatus, CAPAType

        with get_db_session() as session:
            query = session.query(CAPA).filter(CAPA.is_deleted == False)

            status = request.args.get('status')
            if status:
                query = query.filter(CAPA.status == CAPAStatus(status))
            capa_type = request.args.get('capa_type')
            if capa_type:
                query = query.filter(CAPA.capa_type == CAPAType(capa_type))

            limit = int(request.args.get('limit', 100))
            capas = query.order_by(CAPA.created_at.desc()).limit(limit).all()
            return jsonify({'capas': [c.to_dict() for c in capas], 'count': len(capas)})
    except Exception as e:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_capas
            data = get_demo_capas()
            return jsonify({**data, 'demo': True})

        logger.error(f"QMS service unavailable: {e}", exc_info=True)
        return jsonify({
            'error': 'QMS service unavailable',
            'message': 'The Quality Management System is not available. Please check system status.'
        }), 503


@qms_api_bp.route('/capas', methods=['POST'])
@jwt_required()
def create_capa():
    """Create a new CAPA."""
    data = request.get_json()
    if not data or 'description' not in data:
        return jsonify({'error': 'description required'}), 400

    try:
        from config.database import get_db_session
        from services.qms.ncr_service import NCRService

        capa_data = {
            'title': data.get('title', data['description'][:200]),
            'problem_statement': data['description'],
            'capa_type': data.get('capa_type', 'corrective'),
            'priority': data.get('priority', 'medium'),
            'ncr_number': data.get('source_ncr') or data.get('ncr_number'),
            'source_type': data.get('source_type', 'ncr'),
            'source_reference': data.get('source_reference'),
            'owner_id': data.get('owner_id', 'system'),
            'owner_department': data.get('owner_department'),
            'scope': data.get('scope'),
            'target_completion_date': data.get('target_completion_date') or data.get('due_date'),
        }

        with get_db_session() as session:
            service = NCRService(session)
            result = service.create_capa(capa_data)
            session.commit()
            return jsonify(result), 201
    except Exception as e:
        logger.error(f"Failed to create CAPA: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create CAPA', 'message': str(e)}), 500


@qms_api_bp.route('/capas/<capa_number>', methods=['GET'])
@jwt_required()
def get_capa(capa_number: str):
    """Get CAPA details."""
    try:
        from config.database import get_db_session
        from services.qms.ncr_service import NCRService

        with get_db_session() as session:
            service = NCRService(session)
            result = service.get_capa(capa_number)
            if not result:
                return jsonify({'error': 'CAPA not found'}), 404
            return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to get CAPA {capa_number}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get CAPA', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Pending Approvals
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/pending-approvals', methods=['GET'])
@jwt_required()
def get_pending_approvals():
    """Get pending approvals for a user."""
    try:
        from config.database import get_db_session
        from models.qms.documents import DocumentApproval

        with get_db_session() as session:
            approvals = session.query(DocumentApproval).filter(
                DocumentApproval.status == 'PENDING'
            ).order_by(DocumentApproval.requested_date.desc()).limit(50).all()

            return jsonify({
                'pending': [a.to_dict() for a in approvals],
                'count': len(approvals),
            })
    except Exception as e:
        logger.error(f"Failed to get pending approvals: {e}", exc_info=True)
        return jsonify({'pending': [], 'count': 0})


# ─────────────────────────────────────────────────────────────────────────────
# QMS Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_qms_dashboard():
    """Get QMS dashboard summary."""
    try:
        from config.database import get_db_session
        from models.qms.ncr_capa import NonConformanceReport, NCRStatus, CAPA, CAPAStatus
        from models.qms.documents import Document, DocumentStatus
        from models.qms.quality import TrainingRecord, TrainingStatus, Audit, AuditStatus
        from sqlalchemy import func

        with get_db_session() as session:
            # NCR stats
            ncr_open = session.query(func.count(NonConformanceReport.id)).filter(
                NonConformanceReport.status.notin_([NCRStatus.CLOSED, NCRStatus.VOIDED])
            ).scalar() or 0
            ncr_investigating = session.query(func.count(NonConformanceReport.id)).filter(
                NonConformanceReport.status == NCRStatus.UNDER_INVESTIGATION
            ).scalar() or 0
            ncr_closed_month = session.query(func.count(NonConformanceReport.id)).filter(
                NonConformanceReport.status == NCRStatus.CLOSED,
                NonConformanceReport.actual_close_date >= (date.today() - timedelta(days=30))
            ).scalar() or 0

            # CAPA stats
            capa_open = session.query(func.count(CAPA.id)).filter(
                CAPA.status.notin_([CAPAStatus.CLOSED, CAPAStatus.VOIDED])
            ).scalar() or 0
            capa_implementing = session.query(func.count(CAPA.id)).filter(
                CAPA.status == CAPAStatus.IN_IMPLEMENTATION
            ).scalar() or 0
            capa_overdue = session.query(func.count(CAPA.id)).filter(
                CAPA.status.notin_([CAPAStatus.CLOSED, CAPAStatus.VOIDED]),
                CAPA.target_completion_date < date.today()
            ).scalar() or 0

            # Document stats
            doc_total = session.query(func.count(Document.id)).scalar() or 0
            doc_effective = session.query(func.count(Document.id)).filter(
                Document.status == DocumentStatus.EFFECTIVE
            ).scalar() or 0
            doc_pending = session.query(func.count(Document.id)).filter(
                Document.status.in_([DocumentStatus.PENDING_REVIEW, DocumentStatus.UNDER_REVIEW, DocumentStatus.PENDING_APPROVAL])
            ).scalar() or 0
            doc_draft = session.query(func.count(Document.id)).filter(
                Document.status == DocumentStatus.DRAFT
            ).scalar() or 0

            # Training stats
            training_expired = session.query(func.count(TrainingRecord.id)).filter(
                TrainingRecord.status == TrainingStatus.EXPIRED
            ).scalar() or 0
            training_scheduled = session.query(func.count(TrainingRecord.id)).filter(
                TrainingRecord.status == TrainingStatus.SCHEDULED
            ).scalar() or 0
            training_total = session.query(func.count(TrainingRecord.id)).scalar() or 0
            training_completed = session.query(func.count(TrainingRecord.id)).filter(
                TrainingRecord.status == TrainingStatus.COMPLETED
            ).scalar() or 0
            completion_rate = (training_completed / training_total) if training_total > 0 else 0

            # Audit stats
            audits_quarter = session.query(func.count(Audit.id)).filter(
                Audit.planned_start >= (date.today() - timedelta(days=90))
            ).scalar() or 0

            return jsonify({
                'documents': {
                    'total': doc_total,
                    'effective': doc_effective,
                    'pending_approval': doc_pending,
                    'draft': doc_draft,
                },
                'ncrs': {
                    'open': ncr_open,
                    'under_investigation': ncr_investigating,
                    'closed_this_month': ncr_closed_month,
                },
                'capas': {
                    'open': capa_open,
                    'implementing': capa_implementing,
                    'overdue': capa_overdue,
                },
                'training': {
                    'pending_assignments': training_scheduled,
                    'overdue': training_expired,
                    'completion_rate': round(completion_rate, 2),
                },
                'pending_approvals': doc_pending,
                'audits_this_quarter': audits_quarter,
            })
    except Exception as e:
        logger.error(f"Failed to get QMS dashboard: {e}", exc_info=True)
        return jsonify({
            'documents': {'total': 0, 'effective': 0, 'pending_approval': 0, 'draft': 0},
            'ncrs': {'open': 0, 'under_investigation': 0, 'closed_this_month': 0},
            'capas': {'open': 0, 'implementing': 0, 'overdue': 0},
            'training': {'pending_assignments': 0, 'overdue': 0, 'completion_rate': 0},
            'pending_approvals': 0,
            'audits_this_quarter': 0,
        })


# Note: Demo data functions have been moved to api/routes/demo_data.py
# They are only used when DEMO_MODE environment variable is set to 'true'


# ─────────────────────────────────────────────────────────────────────────────
# DELETE Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id: str):
    """
    Soft delete a controlled document.

    Requires admin role. Returns 204 on success.
    Can only delete draft documents.
    """
    from datetime import datetime

    try:
        from flask_jwt_extended import jwt_required, get_jwt_identity
        from api.utils.auth import has_role

        @jwt_required()
        def _delete():
            current_user = get_jwt_identity()

            # Check permissions
            if not has_role(current_user, 'admin'):
                return jsonify({'error': 'Admin role required'}), 403

            try:
                from config.database import get_db_session
                from services.qms.document_service import DocumentService
                from models.qms.documents import Document

                with get_db_session() as session:
                    doc = session.query(Document).filter(
                        Document.document_number == doc_id
                    ).first()

                    if not doc:
                        return jsonify({'error': 'Document not found'}), 404

                    # Can only delete draft documents
                    if doc.status not in ('draft',):
                        return jsonify({'error': f"Cannot delete document with status '{doc.status}'. Only draft documents can be deleted."}), 409

                    # Soft delete
                    doc.deleted_at = datetime.utcnow()
                    doc.deleted_by = current_user
                    doc.status = 'deleted'

                    logger.info(f"Document {doc_id} soft deleted by {current_user}")
                    return '', 204

            except Exception as e:
                logger.error(f"Error deleting document: {e}")
                return jsonify({'error': 'Failed to delete document'}), 500

        return _delete()

    except ImportError:
        return jsonify({'error': 'Authentication required'}), 401


@qms_api_bp.route('/ncrs/<ncr_id>', methods=['DELETE'])
def delete_ncr(ncr_id: str):
    """
    Soft delete a Non-Conformance Report.

    Requires admin role. Returns 204 on success.
    Can only delete open NCRs.
    """
    from datetime import datetime

    try:
        from flask_jwt_extended import jwt_required, get_jwt_identity
        from api.utils.auth import has_role

        @jwt_required()
        def _delete():
            current_user = get_jwt_identity()

            # Check permissions
            if not has_role(current_user, 'admin'):
                return jsonify({'error': 'Admin role required'}), 403

            try:
                from config.database import get_db_session
                from models.qms.ncr import NCR

                with get_db_session() as session:
                    ncr = session.query(NCR).filter(NCR.ncr_number == ncr_id).first()

                    if not ncr:
                        return jsonify({'error': 'NCR not found'}), 404

                    # Can only delete open NCRs
                    if ncr.status not in ('open', 'draft'):
                        return jsonify({'error': f"Cannot delete NCR with status '{ncr.status}'. Only open NCRs can be deleted."}), 409

                    # Check for linked CAPAs
                    if hasattr(ncr, 'capas') and ncr.capas:
                        return jsonify({'error': 'Cannot delete NCR with linked CAPAs'}), 409

                    # Soft delete
                    ncr.deleted_at = datetime.utcnow()
                    ncr.deleted_by = current_user
                    ncr.status = 'deleted'

                    logger.info(f"NCR {ncr_id} soft deleted by {current_user}")
                    return '', 204

            except Exception as e:
                logger.error(f"Error deleting NCR: {e}")
                return jsonify({'error': 'Failed to delete NCR'}), 500

        return _delete()

    except ImportError:
        return jsonify({'error': 'Authentication required'}), 401


@qms_api_bp.route('/capas/<capa_id>', methods=['DELETE'])
def delete_capa(capa_id: str):
    """
    Soft delete a CAPA (Corrective and Preventive Action).

    Requires admin role. Returns 204 on success.
    Can only delete open CAPAs.
    """
    from datetime import datetime

    try:
        from flask_jwt_extended import jwt_required, get_jwt_identity
        from api.utils.auth import has_role

        @jwt_required()
        def _delete():
            current_user = get_jwt_identity()

            # Check permissions
            if not has_role(current_user, 'admin'):
                return jsonify({'error': 'Admin role required'}), 403

            try:
                from config.database import get_db_session
                from models.qms.capa import CAPA

                with get_db_session() as session:
                    capa = session.query(CAPA).filter(CAPA.capa_number == capa_id).first()

                    if not capa:
                        return jsonify({'error': 'CAPA not found'}), 404

                    # Can only delete open CAPAs
                    if capa.status not in ('open', 'draft'):
                        return jsonify({'error': f"Cannot delete CAPA with status '{capa.status}'. Only open CAPAs can be deleted."}), 409

                    # Soft delete
                    capa.deleted_at = datetime.utcnow()
                    capa.deleted_by = current_user
                    capa.status = 'deleted'

                    logger.info(f"CAPA {capa_id} soft deleted by {current_user}")
                    return '', 204

            except Exception as e:
                logger.error(f"Error deleting CAPA: {e}")
                return jsonify({'error': 'Failed to delete CAPA'}), 500

        return _delete()

    except ImportError:
        return jsonify({'error': 'Authentication required'}), 401


# =============================================================================
# SPC (Statistical Process Control) Endpoints
# =============================================================================

@qms_api_bp.route('/spc/charts', methods=['GET'])
def get_spc_charts():
    """Get all SPC control charts."""
    try:
        from services.qms.spc_service import create_spc_service
        from config.database import get_db_session
        with get_db_session() as session:
            spc_service = create_spc_service(session)
            charts = spc_service.get_all_charts()
            return jsonify({'charts': charts}), 200
    except Exception as e:
        logger.error(f"Error getting SPC charts: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/spc/charts', methods=['POST'])
def create_spc_chart():
    """Create a new SPC control chart."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        required_fields = ['parameter_name', 'machine_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        from services.qms.spc_service import create_spc_service
        from config.database import get_db_session
        with get_db_session() as session:
            spc_service = create_spc_service(session)
            chart = spc_service.create_control_chart(
                parameter_name=data['parameter_name'],
                machine_id=data['machine_id'],
                product_id=data.get('product_id'),
                chart_type=data.get('chart_type', 'xbar_r'),
                subgroup_size=data.get('subgroup_size', 5),
                initial_data=data.get('initial_data', []),
                specification_limits=data.get('specification_limits')
            )
            return jsonify({'chart': chart, 'message': 'SPC chart created successfully'}), 201
    except Exception as e:
        logger.error(f"Error creating SPC chart: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/spc/charts/<chart_id>', methods=['GET'])
def get_spc_chart(chart_id: str):
    """Get a specific SPC chart with all data."""
    try:
        from services.qms.spc_service import create_spc_service
        from config.database import get_db_session
        with get_db_session() as session:
            spc_service = create_spc_service(session)
            chart_data = spc_service.get_chart_data(chart_id)
            if not chart_data:
                return jsonify({'error': 'Chart not found'}), 404
            return jsonify(chart_data), 200
    except Exception as e:
        logger.error(f"Error getting SPC chart {chart_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/spc/charts/<chart_id>/readings', methods=['POST'])
def add_spc_reading(chart_id: str):
    """Add a reading to an SPC chart."""
    try:
        data = request.get_json()
        if not data or 'values' not in data:
            return jsonify({'error': 'Values array required'}), 400

        from services.qms.spc_service import create_spc_service
        from config.database import get_db_session
        with get_db_session() as session:
            spc_service = create_spc_service(session)
            result = spc_service.add_reading(chart_id, data['values'])
            return jsonify({
                'reading': result,
                'message': 'Reading added successfully',
                'in_control': result.get('in_control', True),
                'violations': result.get('violations', [])
            }), 201
    except Exception as e:
        logger.error(f"Error adding SPC reading: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/spc/charts/<chart_id>/recalculate', methods=['POST'])
def recalculate_spc_limits(chart_id: str):
    """Recalculate control limits from recent stable data."""
    try:
        data = request.get_json() or {}
        last_n = data.get('last_n_readings', 25)

        from services.qms.spc_service import create_spc_service
        from config.database import get_db_session
        with get_db_session() as session:
            spc_service = create_spc_service(session)
            result = spc_service.recalculate_limits(chart_id, last_n)
            return jsonify({
                'chart': result,
                'message': 'Control limits recalculated successfully'
            }), 200
    except Exception as e:
        logger.error(f"Error recalculating SPC limits: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# =============================================================================
# Inspection Endpoints
# =============================================================================

@qms_api_bp.route('/inspections', methods=['GET'])
def get_inspections():
    """Get all inspection results with optional filters."""
    try:
        status = request.args.get('status')
        job_id = request.args.get('job_id')
        plan_id = request.args.get('plan_id')

        from services.qms.inspection_service import create_inspection_service
        from config.database import get_db_session
        with get_db_session() as session:
            inspection_service = create_inspection_service(session)
            inspections = inspection_service.get_inspections(
                status=status,
                job_id=job_id,
                plan_id=plan_id
            )
            return jsonify({'inspections': inspections}), 200
    except Exception as e:
        logger.error(f"Error getting inspections: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/inspections/plans', methods=['GET'])
def get_inspection_plans():
    """Get all inspection plans."""
    try:
        from services.qms.inspection_service import create_inspection_service
        from config.database import get_db_session
        with get_db_session() as session:
            inspection_service = create_inspection_service(session)
            plans = inspection_service.get_inspection_plans()
            return jsonify({'plans': plans}), 200
    except Exception as e:
        logger.error(f"Error getting inspection plans: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/inspections', methods=['POST'])
def create_inspection():
    """Create a new inspection from a plan."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        required_fields = ['job_id', 'plan_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        from services.qms.inspection_service import create_inspection_service
        from config.database import get_db_session
        with get_db_session() as session:
            inspection_service = create_inspection_service(session)
            inspection = inspection_service.create_inspection(
                job_id=data['job_id'],
                plan_id=data['plan_id'],
                serial_number=data.get('serial_number'),
                inspector_id=data.get('inspector_id')
            )
            return jsonify({
                'inspection': inspection,
                'message': 'Inspection created successfully'
            }), 201
    except Exception as e:
        logger.error(f"Error creating inspection: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/inspections/<result_id>', methods=['GET'])
def get_inspection(result_id: str):
    """Get a specific inspection result with all measurements."""
    try:
        from services.qms.inspection_service import create_inspection_service
        from config.database import get_db_session
        with get_db_session() as session:
            inspection_service = create_inspection_service(session)
            inspection = inspection_service.get_inspection_detail(result_id)
            if not inspection:
                return jsonify({'error': 'Inspection not found'}), 404
            return jsonify(inspection), 200
    except Exception as e:
        logger.error(f"Error getting inspection {result_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/inspections/<result_id>/measurements', methods=['POST'])
def record_measurement(result_id: str):
    """Record a measurement for an inspection."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        required_fields = ['point_id', 'value']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        from services.qms.inspection_service import create_inspection_service
        from config.database import get_db_session
        with get_db_session() as session:
            inspection_service = create_inspection_service(session)
            result = inspection_service.record_measurement(
                result_id=result_id,
                point_id=data['point_id'],
                value=data['value']
            )
            return jsonify({
                'measurement': result,
                'message': 'Measurement recorded successfully'
            }), 200
    except Exception as e:
        logger.error(f"Error recording measurement: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/inspections/<result_id>/complete', methods=['POST'])
def complete_inspection(result_id: str):
    """Complete an inspection and calculate overall result."""
    try:
        from services.qms.inspection_service import create_inspection_service
        from config.database import get_db_session
        with get_db_session() as session:
            inspection_service = create_inspection_service(session)
            result = inspection_service.complete_inspection(result_id)
            return jsonify({
                'inspection': result,
                'message': 'Inspection completed',
                'passed': result.get('status') == 'passed',
                'ncr_created': result.get('ncr_id') is not None
            }), 200
    except Exception as e:
        logger.error(f"Error completing inspection: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/inspections/first-article/<product_id>', methods=['GET'])
def get_first_article_status(product_id: str):
    """Check if first article inspection exists and passed for a product."""
    try:
        from services.qms.inspection_service import create_inspection_service
        from config.database import get_db_session
        with get_db_session() as session:
            inspection_service = create_inspection_service(session)
            status = inspection_service.get_first_article_status(product_id)
            return jsonify(status), 200
    except Exception as e:
        logger.error(f"Error getting FAI status: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ---------------------------------------------------------------------------
# SPC Capability Endpoints
# ---------------------------------------------------------------------------

@qms_api_bp.route('/spc/capability/<chart_id>', methods=['GET'])
def get_spc_capability(chart_id: str):
    """Calculate process capability (Cp, Cpk) for an SPC chart."""
    try:
        from services.qms.spc_capability_service import SPCCapabilityService
        from config.database import get_db_session
        with get_db_session() as session:
            service = SPCCapabilityService(session)
            usl = request.args.get('usl', type=float)
            lsl = request.args.get('lsl', type=float)
            result = service.calculate_capability(chart_id, usl, lsl)
            return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error calculating capability for chart {chart_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/spc/capability/summary', methods=['GET'])
def get_spc_capability_summary():
    """Get a summary of process capability across all charts."""
    try:
        from services.qms.spc_capability_service import SPCCapabilityService
        from config.database import get_db_session
        with get_db_session() as session:
            from services.qms.spc_service import create_spc_service
            spc_service = create_spc_service(session)
            charts = spc_service.get_all_charts()
            service = SPCCapabilityService(session)
            summary = service.get_capability_summary(charts)
            return jsonify(summary), 200
    except Exception as e:
        logger.error(f"Error getting capability summary: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ---------------------------------------------------------------------------
# Supplier Quality Endpoints
# ---------------------------------------------------------------------------

@qms_api_bp.route('/suppliers/<supplier_id>/scorecard', methods=['GET'])
def get_supplier_scorecard(supplier_id: str):
    """Get quality scorecard for a supplier."""
    try:
        from services.qms.supplier_quality_service import SupplierQualityService
        from config.database import get_db_session
        with get_db_session() as session:
            service = SupplierQualityService(session)
            scorecard = service.calculate_supplier_score(supplier_id)
            return jsonify(scorecard), 200
    except Exception as e:
        logger.error(f"Error getting scorecard for supplier {supplier_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/suppliers/rankings', methods=['GET'])
def get_supplier_rankings():
    """Get supplier quality rankings."""
    try:
        from services.qms.supplier_quality_service import SupplierQualityService
        from config.database import get_db_session
        with get_db_session() as session:
            service = SupplierQualityService(session)
            rankings = service.get_supplier_rankings()
            return jsonify({'rankings': rankings}), 200
    except Exception as e:
        logger.error(f"Error getting supplier rankings: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/suppliers/at-risk', methods=['GET'])
def get_at_risk_suppliers():
    """Get suppliers flagged as at-risk based on quality metrics."""
    try:
        from services.qms.supplier_quality_service import SupplierQualityService
        from config.database import get_db_session
        with get_db_session() as session:
            service = SupplierQualityService(session)
            at_risk = service.flag_at_risk_suppliers()
            return jsonify({'at_risk_suppliers': at_risk}), 200
    except Exception as e:
        logger.error(f"Error getting at-risk suppliers: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@qms_api_bp.route('/suppliers/inspection', methods=['POST'])
def record_supplier_inspection():
    """Record a supplier incoming inspection result."""
    try:
        from services.qms.supplier_quality_service import SupplierQualityService
        from config.database import get_db_session
        with get_db_session() as session:
            service = SupplierQualityService(session)
            data = request.get_json()
            result = service.record_inspection(
                supplier_id=data.get('supplier_id'),
                lot_id=data.get('lot_id'),
                accepted_qty=data.get('accepted_qty'),
                rejected_qty=data.get('rejected_qty'),
                total_qty=data.get('total_qty')
            )
            return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error recording supplier inspection: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Audits
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/audits', methods=['GET'])
@jwt_required()
def list_audits():
    """List audits with optional filters."""
    try:
        from config.database import get_db_session
        from models.qms.quality import Audit, AuditStatus, AuditType

        status = request.args.get('status')
        audit_type = request.args.get('type')
        limit = min(int(request.args.get('limit', 50)), 200)

        with get_db_session() as session:
            query = session.query(Audit).filter(Audit.is_deleted == False)

            if status:
                try:
                    query = query.filter(Audit.status == AuditStatus(status))
                except ValueError:
                    pass
            if audit_type:
                try:
                    query = query.filter(Audit.audit_type == AuditType(audit_type))
                except ValueError:
                    pass

            audits = query.order_by(Audit.planned_start.desc().nullslast()).limit(limit).all()
            return jsonify({
                'audits': [a.to_dict() for a in audits],
                'count': len(audits),
            })
    except Exception as e:
        logger.error(f"Error listing audits: {e}", exc_info=True)
        return jsonify({'audits': [], 'count': 0})


# ─────────────────────────────────────────────────────────────────────────────
# Training
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/training/courses', methods=['GET'])
@jwt_required()
def list_training_courses():
    """List training courses."""
    try:
        from config.database import get_db_session
        from models.qms.quality import TrainingCourse

        with get_db_session() as session:
            courses = session.query(TrainingCourse).filter(
                TrainingCourse.is_deleted == False,
                TrainingCourse.is_active == True,
            ).order_by(TrainingCourse.title).all()
            return jsonify({
                'courses': [c.to_dict() for c in courses],
                'count': len(courses),
            })
    except Exception as e:
        logger.error(f"Error listing training courses: {e}", exc_info=True)
        return jsonify({'courses': [], 'count': 0})


@qms_api_bp.route('/training/records', methods=['GET'])
@jwt_required()
def list_training_records():
    """List training records with optional filters."""
    try:
        from config.database import get_db_session
        from models.qms.quality import TrainingRecord, TrainingStatus

        status = request.args.get('status')
        trainee = request.args.get('trainee')
        limit = min(int(request.args.get('limit', 100)), 500)

        with get_db_session() as session:
            query = session.query(TrainingRecord).filter(TrainingRecord.is_deleted == False)

            if status:
                try:
                    query = query.filter(TrainingRecord.status == TrainingStatus(status))
                except ValueError:
                    pass
            if trainee:
                query = query.filter(TrainingRecord.trainee_id == trainee)

            records = query.order_by(TrainingRecord.scheduled_date.desc().nullslast()).limit(limit).all()
            return jsonify({
                'records': [r.to_dict() for r in records],
                'count': len(records),
            })
    except Exception as e:
        logger.error(f"Error listing training records: {e}", exc_info=True)
        return jsonify({'records': [], 'count': 0})


# ─────────────────────────────────────────────────────────────────────────────
# Calibration
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/calibration/equipment', methods=['GET'])
@jwt_required()
def list_calibration_equipment():
    """List calibrated equipment with optional filters."""
    try:
        from config.database import get_db_session
        from models.qms.quality import CalibratedEquipment, CalibrationStatus

        status = request.args.get('status')
        limit = min(int(request.args.get('limit', 100)), 500)

        with get_db_session() as session:
            query = session.query(CalibratedEquipment).filter(
                CalibratedEquipment.is_deleted == False,
                CalibratedEquipment.is_active == True,
            )

            if status:
                try:
                    query = query.filter(CalibratedEquipment.status == CalibrationStatus(status))
                except ValueError:
                    pass

            equipment = query.order_by(CalibratedEquipment.next_calibration_due.asc().nullslast()).limit(limit).all()
            return jsonify({
                'equipment': [e.to_dict() for e in equipment],
                'count': len(equipment),
            })
    except Exception as e:
        logger.error(f"Error listing calibration equipment: {e}", exc_info=True)
        return jsonify({'equipment': [], 'count': 0})
