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


def get_db_session():
    """Get database session."""
    try:
        from config.database import get_db_session as db_session
        return db_session()
    except Exception as e:
        logger.warning(f'Exception in qms_api.py: {e}')
        return None


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
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify({'error': 'title required'}), 400

    try:
        from services.qms.document_service import DocumentService

        service = DocumentService(session)
        document = service.create_document(data)
        session.commit()

        return jsonify(document), 201
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating document: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@qms_api_bp.route('/documents/<document_number>', methods=['GET'])
@jwt_required()
def get_document(document_number: str):
    """Get a specific document with its history."""
    session = get_db_session()
    if not session:
        # Check if demo mode is enabled
        from config.demo_mode import is_demo_mode_enabled
        if is_demo_mode_enabled():
            from api.routes.demo_data import get_demo_document_detail
            data = get_demo_document_detail(document_number)
            return jsonify({**data, 'demo': True})

        return jsonify({
            'error': 'QMS service unavailable',
            'message': 'The Quality Management System is not available. Please check system status.'
        }), 503

    try:
        from services.qms.document_service import DocumentService

        service = DocumentService(session)
        document = service.get_document(document_number)

        if not document:
            return jsonify({'error': 'Document not found'}), 404

        return jsonify(document)
    except Exception as e:
        logger.error(f"Error getting document: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@qms_api_bp.route('/documents/<document_number>/submit-review', methods=['POST'])
@jwt_required()
def submit_document_review(document_number: str):
    """Submit document for review."""
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json() or {}

    try:
        from services.qms.document_service import DocumentService

        service = DocumentService(session)
        document = service.submit_for_review(
            document_number,
            user_id=data.get('user_id', 'system')
        )
        session.commit()

        if not document:
            return jsonify({'error': 'Document not found or not in draft status'}), 400

        return jsonify(document)
    except Exception as e:
        session.rollback()
        logger.error(f"Error submitting document for review: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@qms_api_bp.route('/documents/<document_number>/approvals', methods=['POST'])
@jwt_required()
def add_document_approval(document_number: str):
    """Add an approval requirement to a document."""
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json()
    if not data or 'approver_id' not in data:
        return jsonify({'error': 'approver_id required'}), 400

    try:
        from services.qms.document_service import DocumentService

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
        session.commit()

        if not approval:
            return jsonify({'error': 'Document not found'}), 404

        return jsonify(approval), 201
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding approval: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


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
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json()
    required = ['user_id', 'user_name', 'meaning', 'password_hash']
    if not data or not all(k in data for k in required):
        return jsonify({'error': f'{required} required'}), 400

    try:
        from services.qms.document_service import DocumentService

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
        session.commit()

        if not approval:
            return jsonify({'error': 'Approval not found or not pending'}), 400

        return jsonify(approval)
    except Exception as e:
        session.rollback()
        logger.error(f"Error signing approval: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@qms_api_bp.route('/approvals/<approval_id>/reject', methods=['POST'])
@jwt_required()
def reject_approval(approval_id: str):
    """Reject an approval."""
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json()
    if not data or 'reason' not in data:
        return jsonify({'error': 'reason required'}), 400

    try:
        from services.qms.document_service import DocumentService

        service = DocumentService(session)
        approval = service.reject_approval(
            approval_id=approval_id,
            user_id=data.get('user_id', 'system'),
            reason=data['reason'],
        )
        session.commit()

        if not approval:
            return jsonify({'error': 'Approval not found'}), 404

        return jsonify(approval)
    except Exception as e:
        session.rollback()
        logger.error(f"Error rejecting approval: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@qms_api_bp.route('/documents/<document_number>/make-effective', methods=['POST'])
@jwt_required()
def make_document_effective(document_number: str):
    """Make an approved document effective."""
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json() or {}

    try:
        from services.qms.document_service import DocumentService

        effective_date = date.today()
        if data.get('effective_date'):
            effective_date = date.fromisoformat(data['effective_date'])

        service = DocumentService(session)
        document = service.make_effective(
            document_number,
            effective_date=effective_date,
            user_id=data.get('user_id', 'system'),
        )
        session.commit()

        if not document:
            return jsonify({'error': 'Document not found or not approved'}), 400

        return jsonify(document)
    except Exception as e:
        session.rollback()
        logger.error(f"Error making document effective: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@qms_api_bp.route('/documents/<document_number>/revise', methods=['POST'])
@jwt_required()
def create_document_revision(document_number: str):
    """Create a new revision of an effective document."""
    session = get_db_session()
    if not session:
        return jsonify({'error': 'Database not available'}), 503

    data = request.get_json()
    if not data or 'change_summary' not in data:
        return jsonify({'error': 'change_summary required'}), 400

    try:
        from services.qms.document_service import DocumentService

        service = DocumentService(session)
        document = service.create_new_revision(
            document_number,
            user_id=data.get('user_id', 'system'),
            change_summary=data['change_summary'],
        )
        session.commit()

        if not document:
            return jsonify({'error': 'Document not found or not effective'}), 400

        return jsonify(document), 201
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating revision: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


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

    return jsonify({
        'ncr_number': f"NCR-{datetime.utcnow().strftime('%Y%m%d')}-001",
        'description': data['description'],
        'severity': data.get('severity', 'minor'),
        'source': data.get('source'),
        'status': 'open',
        'created_at': datetime.utcnow().isoformat(),
    }), 201


@qms_api_bp.route('/ncrs/<ncr_number>', methods=['GET'])
@jwt_required()
def get_ncr(ncr_number: str):
    """Get NCR details."""
    return jsonify({
        'ncr_number': ncr_number,
        'description': 'Dimensional variation in brick studs',
        'severity': 'minor',
        'source': 'Production inspection',
        'product_id': 'brick_2x4_red',
        'work_order_id': 'WO-20240115-001',
        'status': 'under_investigation',
        'root_cause': None,
        'containment_action': 'Quarantined affected batch',
        'disposition': None,
        'created_at': (datetime.utcnow() - timedelta(days=2)).isoformat(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# CAPA (Corrective and Preventive Actions)
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/capas', methods=['GET'])
@jwt_required()
def list_capas():
    """List CAPAs."""
    try:
        from config.database import get_db_session
        from services.qms.capa_service import CAPAService

        with get_db_session() as session:
            service = CAPAService(session)
            capas = service.get_capas(
                status=request.args.get('status'),
                capa_type=request.args.get('capa_type'),
                limit=int(request.args.get('limit', 100)),
            )
            return jsonify({'capas': capas, 'count': len(capas)})
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

    return jsonify({
        'capa_number': f"CAPA-{datetime.utcnow().strftime('%Y%m%d')}-001",
        'capa_type': data.get('capa_type', 'corrective'),
        'description': data['description'],
        'source_ncr': data.get('source_ncr'),
        'status': 'open',
        'created_at': datetime.utcnow().isoformat(),
    }), 201


@qms_api_bp.route('/capas/<capa_number>', methods=['GET'])
@jwt_required()
def get_capa(capa_number: str):
    """Get CAPA details."""
    return jsonify({
        'capa_number': capa_number,
        'capa_type': 'corrective',
        'description': 'Improve printer calibration procedure',
        'source_ncr': 'NCR-20240113-001',
        'status': 'implementing',
        'root_cause_analysis': 'Printer Z-offset drift over time',
        'corrective_action': 'Add weekly calibration check to PM schedule',
        'preventive_action': 'Install automated calibration verification',
        'effectiveness_criteria': 'Zero calibration-related NCRs for 90 days',
        'due_date': (date.today() + timedelta(days=30)).isoformat(),
        'owner_id': 'W002',
        'created_at': (datetime.utcnow() - timedelta(days=5)).isoformat(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Pending Approvals
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/pending-approvals', methods=['GET'])
@jwt_required()
def get_pending_approvals():
    """Get pending approvals for a user."""
    user_id = request.args.get('user_id', 'current_user')
    return jsonify({
        'pending': [
            {
                'approval_id': 'APR001',
                'document_number': 'SOP-20240110-001',
                'document_title': 'Work Instruction: Printer Calibration',
                'approval_type': 'approve',
                'requested_date': (datetime.utcnow() - timedelta(days=1)).isoformat(),
                'due_date': (datetime.utcnow() + timedelta(days=3)).isoformat(),
            },
            {
                'approval_id': 'APR002',
                'document_number': 'SPEC-20240112-001',
                'document_title': 'Specification: LEGO Brick Tolerances',
                'approval_type': 'review',
                'requested_date': (datetime.utcnow() - timedelta(hours=4)).isoformat(),
                'due_date': (datetime.utcnow() + timedelta(days=5)).isoformat(),
            },
        ],
        'count': 2,
    })


# ─────────────────────────────────────────────────────────────────────────────
# QMS Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@qms_api_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_qms_dashboard():
    """Get QMS dashboard summary."""
    return jsonify({
        'documents': {
            'total': 45,
            'effective': 32,
            'pending_approval': 8,
            'draft': 5,
        },
        'ncrs': {
            'open': 3,
            'under_investigation': 2,
            'closed_this_month': 5,
        },
        'capas': {
            'open': 4,
            'implementing': 3,
            'overdue': 1,
        },
        'training': {
            'pending_assignments': 12,
            'overdue': 2,
            'completion_rate': 0.94,
        },
        'pending_approvals': 8,
        'audits_this_quarter': 2,
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

            session = get_db_session()
            if not session:
                return jsonify({'error': 'Database not available'}), 503

            try:
                from services.qms.document_service import DocumentService
                from models.qms.documents import Document

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
                session.commit()

                logger.info(f"Document {doc_id} soft deleted by {current_user}")
                return '', 204

            except Exception as e:
                session.rollback()
                logger.error(f"Error deleting document: {e}")
                return jsonify({'error': 'Failed to delete document'}), 500
            finally:
                session.close()

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

            session = get_db_session()
            if not session:
                return jsonify({'error': 'Database not available'}), 503

            try:
                from models.qms.ncr import NCR

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
                session.commit()

                logger.info(f"NCR {ncr_id} soft deleted by {current_user}")
                return '', 204

            except Exception as e:
                session.rollback()
                logger.error(f"Error deleting NCR: {e}")
                return jsonify({'error': 'Failed to delete NCR'}), 500
            finally:
                session.close()

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

            session = get_db_session()
            if not session:
                return jsonify({'error': 'Database not available'}), 503

            try:
                from models.qms.capa import CAPA

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
                session.commit()

                logger.info(f"CAPA {capa_id} soft deleted by {current_user}")
                return '', 204

            except Exception as e:
                session.rollback()
                logger.error(f"Error deleting CAPA: {e}")
                return jsonify({'error': 'Failed to delete CAPA'}), 500
            finally:
                session.close()

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
        spc_service = create_spc_service()
        charts = spc_service.get_all_charts()
        return jsonify({'charts': charts}), 200
    except Exception as e:
        logger.error(f"Error getting SPC charts: {e}")
        return jsonify({'error': str(e)}), 500


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
        spc_service = create_spc_service()

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
        return jsonify({'error': str(e)}), 500


@qms_api_bp.route('/spc/charts/<chart_id>', methods=['GET'])
def get_spc_chart(chart_id: str):
    """Get a specific SPC chart with all data."""
    try:
        from services.qms.spc_service import create_spc_service
        spc_service = create_spc_service()
        chart_data = spc_service.get_chart_data(chart_id)

        if not chart_data:
            return jsonify({'error': 'Chart not found'}), 404

        return jsonify(chart_data), 200
    except Exception as e:
        logger.error(f"Error getting SPC chart {chart_id}: {e}")
        return jsonify({'error': str(e)}), 500


@qms_api_bp.route('/spc/charts/<chart_id>/readings', methods=['POST'])
def add_spc_reading(chart_id: str):
    """Add a reading to an SPC chart."""
    try:
        data = request.get_json()
        if not data or 'values' not in data:
            return jsonify({'error': 'Values array required'}), 400

        from services.qms.spc_service import create_spc_service
        spc_service = create_spc_service()

        result = spc_service.add_reading(chart_id, data['values'])

        return jsonify({
            'reading': result,
            'message': 'Reading added successfully',
            'in_control': result.get('in_control', True),
            'violations': result.get('violations', [])
        }), 201
    except Exception as e:
        logger.error(f"Error adding SPC reading: {e}")
        return jsonify({'error': str(e)}), 500


@qms_api_bp.route('/spc/charts/<chart_id>/recalculate', methods=['POST'])
def recalculate_spc_limits(chart_id: str):
    """Recalculate control limits from recent stable data."""
    try:
        data = request.get_json() or {}
        last_n = data.get('last_n_readings', 25)

        from services.qms.spc_service import create_spc_service
        spc_service = create_spc_service()

        result = spc_service.recalculate_limits(chart_id, last_n)

        return jsonify({
            'chart': result,
            'message': 'Control limits recalculated successfully'
        }), 200
    except Exception as e:
        logger.error(f"Error recalculating SPC limits: {e}")
        return jsonify({'error': str(e)}), 500


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
        inspection_service = create_inspection_service()

        inspections = inspection_service.get_inspections(
            status=status,
            job_id=job_id,
            plan_id=plan_id
        )

        return jsonify({'inspections': inspections}), 200
    except Exception as e:
        logger.error(f"Error getting inspections: {e}")
        return jsonify({'error': str(e)}), 500


@qms_api_bp.route('/inspections/plans', methods=['GET'])
def get_inspection_plans():
    """Get all inspection plans."""
    try:
        from services.qms.inspection_service import create_inspection_service
        inspection_service = create_inspection_service()
        plans = inspection_service.get_inspection_plans()
        return jsonify({'plans': plans}), 200
    except Exception as e:
        logger.error(f"Error getting inspection plans: {e}")
        return jsonify({'error': str(e)}), 500


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
        inspection_service = create_inspection_service()

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
        return jsonify({'error': str(e)}), 500


@qms_api_bp.route('/inspections/<result_id>', methods=['GET'])
def get_inspection(result_id: str):
    """Get a specific inspection result with all measurements."""
    try:
        from services.qms.inspection_service import create_inspection_service
        inspection_service = create_inspection_service()

        inspection = inspection_service.get_inspection_detail(result_id)

        if not inspection:
            return jsonify({'error': 'Inspection not found'}), 404

        return jsonify(inspection), 200
    except Exception as e:
        logger.error(f"Error getting inspection {result_id}: {e}")
        return jsonify({'error': str(e)}), 500


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
        inspection_service = create_inspection_service()

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
        return jsonify({'error': str(e)}), 500


@qms_api_bp.route('/inspections/<result_id>/complete', methods=['POST'])
def complete_inspection(result_id: str):
    """Complete an inspection and calculate overall result."""
    try:
        from services.qms.inspection_service import create_inspection_service
        inspection_service = create_inspection_service()

        result = inspection_service.complete_inspection(result_id)

        return jsonify({
            'inspection': result,
            'message': 'Inspection completed',
            'passed': result.get('status') == 'passed',
            'ncr_created': result.get('ncr_id') is not None
        }), 200
    except Exception as e:
        logger.error(f"Error completing inspection: {e}")
        return jsonify({'error': str(e)}), 500


@qms_api_bp.route('/inspections/first-article/<product_id>', methods=['GET'])
def get_first_article_status(product_id: str):
    """Check if first article inspection exists and passed for a product."""
    try:
        from services.qms.inspection_service import create_inspection_service
        inspection_service = create_inspection_service()

        status = inspection_service.get_first_article_status(product_id)

        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Error getting FAI status: {e}")
        return jsonify({'error': str(e)}), 500
