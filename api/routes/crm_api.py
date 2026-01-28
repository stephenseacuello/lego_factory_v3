"""
LEGO Factory v3 - CRM API
==========================
REST API endpoints for Customer Relationship Management.

Provides endpoints for:
- Customer management (partners with is_customer=True)
- Contact management
- Activity logging
"""

import logging
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

logger = logging.getLogger(__name__)

crm_api_bp = Blueprint('crm_api', __name__, url_prefix='/api/crm')


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@crm_api_bp.route('/dashboard', methods=['GET'])
@jwt_required(optional=True)
def get_dashboard():
    """
    Get CRM dashboard summary data.

    Returns stats, recent activities, top customers, and upcoming follow-ups.
    """
    try:
        from config.database import get_db_session
        from models.erp.partners import Partner

        with get_db_session() as session:
            from models.erp.partners import PartnerType
            # Get customer count
            total_customers = session.query(Partner).filter(
                Partner.is_deleted == False,
                Partner.partner_type == PartnerType.CUSTOMER
            ).count()

            # Get contact count
            try:
                from sqlalchemy import text
                result = session.execute(text("SELECT COUNT(*) FROM contacts WHERE is_deleted = false"))
                total_contacts = result.scalar() or 0
            except Exception:
                total_contacts = 0

            # Get activity stats
            try:
                result = session.execute(text("""
                    SELECT
                        COUNT(*) FILTER (WHERE completed = false) as open_activities,
                        COUNT(*) FILTER (WHERE activity_date >= NOW() - INTERVAL '30 days') as monthly_activities
                    FROM crm_activities
                    WHERE is_deleted = false
                """))
                row = result.fetchone()
                open_activities = row[0] if row else 0
                monthly_activities = row[1] if row else 0
            except Exception:
                open_activities = 0
                monthly_activities = 0

            # Get recent activities
            recent_activities = []
            try:
                result = session.execute(text("""
                    SELECT a.id, a.activity_type, a.subject, a.activity_date, p.name as customer_name
                    FROM crm_activities a
                    LEFT JOIN partners p ON a.partner_id = p.id
                    WHERE a.is_deleted = false
                    ORDER BY a.activity_date DESC
                    LIMIT 5
                """))
                for row in result:
                    recent_activities.append({
                        'id': str(row[0]),
                        'activity_type': row[1],
                        'subject': row[2],
                        'activity_date': row[3].isoformat() if row[3] else None,
                        'customer_name': row[4] or 'Unknown'
                    })
            except Exception:
                pass

            # Get activity breakdown
            activity_breakdown = {'call': 0, 'email': 0, 'meeting': 0, 'note': 0}
            try:
                result = session.execute(text("""
                    SELECT activity_type, COUNT(*)
                    FROM crm_activities
                    WHERE is_deleted = false AND activity_date >= NOW() - INTERVAL '30 days'
                    GROUP BY activity_type
                """))
                for row in result:
                    if row[0] in activity_breakdown:
                        activity_breakdown[row[0]] = row[1]
            except Exception:
                pass

            # Get upcoming follow-ups
            upcoming_followups = []
            try:
                result = session.execute(text("""
                    SELECT a.subject, p.name as customer_name, a.due_date
                    FROM crm_activities a
                    LEFT JOIN partners p ON a.partner_id = p.id
                    WHERE a.is_deleted = false
                    AND a.completed = false
                    AND a.due_date IS NOT NULL
                    AND a.due_date >= CURRENT_DATE
                    ORDER BY a.due_date ASC
                    LIMIT 5
                """))
                for row in result:
                    upcoming_followups.append({
                        'subject': row[0],
                        'customer_name': row[1] or 'Unknown',
                        'due_date': row[2].isoformat() if row[2] else None
                    })
            except Exception:
                pass

            return jsonify({
                'stats': {
                    'total_customers': total_customers,
                    'total_contacts': total_contacts,
                    'open_activities': open_activities,
                    'monthly_activities': monthly_activities
                },
                'recent_activities': recent_activities,
                'top_customers': [],  # Would need sales data
                'upcoming_followups': upcoming_followups,
                'activity_breakdown': activity_breakdown
            })

    except Exception as e:
        logger.error(f"Error fetching CRM dashboard: {e}", exc_info=True)
        return jsonify({
            'stats': {'total_customers': 0, 'total_contacts': 0, 'open_activities': 0, 'monthly_activities': 0},
            'recent_activities': [],
            'top_customers': [],
            'upcoming_followups': [],
            'activity_breakdown': {},
            'error': 'Could not fetch dashboard data'
        })


# ─────────────────────────────────────────────────────────────────────────────
# Customers (Partners with is_customer=True)
# ─────────────────────────────────────────────────────────────────────────────

@crm_api_bp.route('/customers', methods=['GET'])
@jwt_required(optional=True)
def list_customers():
    """
    List customers.

    Query params:
    - search: Filter by name or email
    - status: Filter by status (active, inactive, prospect)
    - limit: Max results (default 100)
    - offset: Pagination offset
    """
    try:
        from config.database import get_db_session
        from models.erp.partners import Partner, PartnerStatus, PartnerType

        with get_db_session() as session:
            query = session.query(Partner).filter(
                Partner.is_deleted == False,
                Partner.partner_type == PartnerType.CUSTOMER
            )

            search = request.args.get('search')
            if search:
                query = query.filter(
                    (Partner.name.ilike(f'%{search}%')) |
                    (Partner.email.ilike(f'%{search}%')) |
                    (Partner.partner_id.ilike(f'%{search}%'))
                )

            status = request.args.get('status')
            if status:
                query = query.filter(Partner.status == PartnerStatus(status))

            limit = int(request.args.get('limit', 100))
            offset = int(request.args.get('offset', 0))

            customers = query.order_by(Partner.name).offset(offset).limit(limit).all()

            return jsonify({
                'customers': [c.to_dict() for c in customers],
                'count': len(customers)
            })

    except Exception as e:
        logger.error(f"Error fetching customers: {e}", exc_info=True)
        return jsonify({'customers': [], 'count': 0, 'error': 'Could not fetch customers'})


@crm_api_bp.route('/customers', methods=['POST'])
@jwt_required()
def create_customer():
    """Create a new customer."""
    try:
        from config.database import get_db_session
        from models.erp.partners import Partner, PartnerType, PartnerStatus

        data = request.get_json()
        current_user = get_jwt_identity() or 'system'

        with get_db_session() as session:
            partner = Partner(
                partner_id=f"CUST-{uuid.uuid4().hex[:8].upper()}",
                name=data['name'],
                legal_name=data.get('legal_name'),
                partner_type=PartnerType.CUSTOMER,
                status=PartnerStatus(data.get('status', 'active')),
                email=data.get('email'),
                phone=data.get('phone'),
                website=data.get('website'),
                tax_id=data.get('tax_id'),
                address_line1=data.get('address_line1'),
                address_line2=data.get('address_line2'),
                city=data.get('city'),
                state=data.get('state'),
                postal_code=data.get('postal_code'),
                country=data.get('country', 'US'),
                territory=data.get('territory'),
                customer_category=data.get('customer_category'),
                payment_terms_days=data.get('payment_terms_days', 30),
                created_by=current_user
            )

            session.add(partner)
            session.flush()

            logger.info(f"Created customer: {partner.partner_id}")
            return jsonify(partner.to_dict()), 201

    except Exception as e:
        logger.error(f"Error creating customer: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create customer'}), 500


@crm_api_bp.route('/customers/<customer_id>', methods=['GET'])
@jwt_required(optional=True)
def get_customer(customer_id: str):
    """Get a specific customer."""
    try:
        from config.database import get_db_session
        from models.erp.partners import Partner

        with get_db_session() as session:
            partner = session.query(Partner).filter(
                (Partner.id == customer_id) | (Partner.partner_id == customer_id)
            ).first()

            if not partner:
                return jsonify({'error': 'Customer not found'}), 404

            return jsonify(partner.to_dict())

    except Exception as e:
        logger.error(f"Error fetching customer: {e}", exc_info=True)
        return jsonify({'error': 'Could not fetch customer'}), 500


@crm_api_bp.route('/customers/<customer_id>', methods=['PUT'])
@jwt_required()
def update_customer(customer_id: str):
    """Update a customer."""
    try:
        from config.database import get_db_session
        from models.erp.partners import Partner, PartnerStatus

        data = request.get_json()
        current_user = get_jwt_identity() or 'system'

        with get_db_session() as session:
            partner = session.query(Partner).filter(
                (Partner.id == customer_id) | (Partner.partner_id == customer_id)
            ).first()

            if not partner:
                return jsonify({'error': 'Customer not found'}), 404

            # Update allowed fields
            update_fields = [
                'name', 'legal_name', 'email', 'phone', 'website', 'tax_id',
                'address_line1', 'address_line2', 'city', 'state', 'postal_code',
                'country', 'territory', 'customer_category', 'payment_terms_days', 'notes'
            ]

            for field in update_fields:
                if field in data:
                    setattr(partner, field, data[field])

            if 'status' in data:
                partner.status = PartnerStatus(data['status'])

            partner.updated_at = datetime.utcnow()
            partner.updated_by = current_user

            logger.info(f"Updated customer: {partner.partner_id}")
            return jsonify(partner.to_dict())

    except Exception as e:
        logger.error(f"Error updating customer: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update customer'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Contacts
# ─────────────────────────────────────────────────────────────────────────────

@crm_api_bp.route('/contacts', methods=['GET'])
@jwt_required(optional=True)
def list_contacts():
    """List contacts with optional filtering."""
    try:
        from config.database import get_db_session
        from sqlalchemy import text

        with get_db_session() as session:
            partner_id = request.args.get('partner_id')
            search = request.args.get('search')
            limit = int(request.args.get('limit', 100))
            offset = int(request.args.get('offset', 0))

            query = """
                SELECT c.id, c.contact_id, c.partner_id, c.first_name, c.last_name,
                       c.title, c.department, c.email, c.phone, c.mobile, c.is_primary,
                       c.notes, p.name as customer_name
                FROM contacts c
                LEFT JOIN partners p ON c.partner_id = p.id
                WHERE c.is_deleted = false
            """
            params = {}

            if partner_id:
                query += " AND c.partner_id = :partner_id"
                params['partner_id'] = partner_id

            if search:
                query += """ AND (
                    c.first_name ILIKE :search OR
                    c.last_name ILIKE :search OR
                    c.email ILIKE :search
                )"""
                params['search'] = f'%{search}%'

            query += " ORDER BY c.last_name, c.first_name LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = offset

            result = session.execute(text(query), params)

            contacts = []
            for row in result:
                contacts.append({
                    'id': str(row[0]),
                    'contact_id': row[1],
                    'partner_id': str(row[2]) if row[2] else None,
                    'first_name': row[3],
                    'last_name': row[4],
                    'title': row[5],
                    'department': row[6],
                    'email': row[7],
                    'phone': row[8],
                    'mobile': row[9],
                    'is_primary': row[10],
                    'notes': row[11],
                    'customer_name': row[12]
                })

            return jsonify({'contacts': contacts, 'count': len(contacts)})

    except Exception as e:
        logger.error(f"Error fetching contacts: {e}", exc_info=True)
        return jsonify({'contacts': [], 'count': 0, 'error': 'Could not fetch contacts'})


@crm_api_bp.route('/contacts', methods=['POST'])
@jwt_required()
def create_contact():
    """Create a new contact."""
    try:
        from config.database import get_db_session
        from sqlalchemy import text

        data = request.get_json()
        current_user = get_jwt_identity() or 'system'
        contact_id = f"CON-{uuid.uuid4().hex[:8].upper()}"

        with get_db_session() as session:
            session.execute(text("""
                INSERT INTO contacts (
                    id, contact_id, partner_id, first_name, last_name, title, department,
                    email, phone, mobile, is_primary, notes, created_by, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), :contact_id, :partner_id, :first_name, :last_name,
                    :title, :department, :email, :phone, :mobile, :is_primary, :notes,
                    :created_by, NOW(), NOW()
                )
            """), {
                'contact_id': contact_id,
                'partner_id': data.get('partner_id'),
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'title': data.get('title'),
                'department': data.get('department'),
                'email': data.get('email'),
                'phone': data.get('phone'),
                'mobile': data.get('mobile'),
                'is_primary': data.get('is_primary', False),
                'notes': data.get('notes'),
                'created_by': current_user
            })

            logger.info(f"Created contact: {contact_id}")
            return jsonify({'contact_id': contact_id, 'message': 'Contact created'}), 201

    except Exception as e:
        logger.error(f"Error creating contact: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create contact'}), 500


@crm_api_bp.route('/contacts/<contact_id>', methods=['PUT'])
@jwt_required()
def update_contact(contact_id: str):
    """Update a contact."""
    try:
        from config.database import get_db_session
        from sqlalchemy import text

        data = request.get_json()
        current_user = get_jwt_identity() or 'system'

        with get_db_session() as session:
            # Build dynamic update query
            update_fields = []
            params = {'contact_id': contact_id, 'updated_by': current_user}

            field_mapping = {
                'partner_id': 'partner_id',
                'first_name': 'first_name',
                'last_name': 'last_name',
                'title': 'title',
                'department': 'department',
                'email': 'email',
                'phone': 'phone',
                'mobile': 'mobile',
                'is_primary': 'is_primary',
                'notes': 'notes'
            }

            for key, column in field_mapping.items():
                if key in data:
                    update_fields.append(f"{column} = :{key}")
                    params[key] = data[key]

            if not update_fields:
                return jsonify({'error': 'No fields to update'}), 400

            update_fields.append("updated_at = NOW()")
            update_fields.append("updated_by = :updated_by")

            query = f"""
                UPDATE contacts SET {', '.join(update_fields)}
                WHERE id::text = :contact_id OR contact_id = :contact_id
            """

            session.execute(text(query), params)

            logger.info(f"Updated contact: {contact_id}")
            return jsonify({'message': 'Contact updated'})

    except Exception as e:
        logger.error(f"Error updating contact: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update contact'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Activities
# ─────────────────────────────────────────────────────────────────────────────

@crm_api_bp.route('/activities', methods=['GET'])
@jwt_required(optional=True)
def list_activities():
    """List activities with optional filtering."""
    try:
        from config.database import get_db_session
        from sqlalchemy import text

        with get_db_session() as session:
            partner_id = request.args.get('partner_id')
            activity_type = request.args.get('activity_type')
            completed = request.args.get('completed')
            limit = int(request.args.get('limit', 100))
            offset = int(request.args.get('offset', 0))

            query = """
                SELECT a.id, a.activity_type, a.subject, a.description, a.activity_date,
                       a.due_date, a.completed, a.partner_id, a.contact_id, a.created_by,
                       p.name as customer_name
                FROM crm_activities a
                LEFT JOIN partners p ON a.partner_id = p.id
                WHERE a.is_deleted = false
            """
            params = {}

            if partner_id:
                query += " AND a.partner_id = :partner_id"
                params['partner_id'] = partner_id

            if activity_type:
                query += " AND a.activity_type = :activity_type"
                params['activity_type'] = activity_type

            if completed is not None:
                query += " AND a.completed = :completed"
                params['completed'] = completed.lower() == 'true'

            query += " ORDER BY a.activity_date DESC LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = offset

            result = session.execute(text(query), params)

            activities = []
            pending_followups = []

            for row in result:
                activity = {
                    'id': str(row[0]),
                    'activity_type': row[1],
                    'subject': row[2],
                    'description': row[3],
                    'activity_date': row[4].isoformat() if row[4] else None,
                    'due_date': row[5].isoformat() if row[5] else None,
                    'completed': row[6],
                    'partner_id': str(row[7]) if row[7] else None,
                    'contact_id': str(row[8]) if row[8] else None,
                    'created_by': row[9],
                    'customer_name': row[10]
                }
                activities.append(activity)

                # Track pending follow-ups
                if not activity['completed'] and activity['due_date']:
                    pending_followups.append({
                        'subject': activity['subject'],
                        'customer_name': activity['customer_name'],
                        'due_date': activity['due_date']
                    })

            return jsonify({
                'activities': activities,
                'count': len(activities),
                'pending_followups': pending_followups[:5]
            })

    except Exception as e:
        logger.error(f"Error fetching activities: {e}", exc_info=True)
        return jsonify({'activities': [], 'count': 0, 'error': 'Could not fetch activities'})


@crm_api_bp.route('/activities', methods=['POST'])
@jwt_required()
def create_activity():
    """Create a new activity."""
    try:
        from config.database import get_db_session
        from sqlalchemy import text

        data = request.get_json()
        current_user = get_jwt_identity() or 'system'

        with get_db_session() as session:
            activity_date = data.get('activity_date')
            if activity_date:
                activity_date = datetime.fromisoformat(activity_date.replace('Z', '+00:00'))
            else:
                activity_date = datetime.utcnow()

            due_date = data.get('due_date')
            if due_date:
                due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))

            session.execute(text("""
                INSERT INTO crm_activities (
                    id, activity_type, partner_id, contact_id, subject, description,
                    activity_date, due_date, completed, created_by, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), :activity_type, :partner_id, :contact_id, :subject,
                    :description, :activity_date, :due_date, :completed, :created_by, NOW(), NOW()
                )
            """), {
                'activity_type': data['activity_type'],
                'partner_id': data.get('partner_id'),
                'contact_id': data.get('contact_id'),
                'subject': data['subject'],
                'description': data.get('description'),
                'activity_date': activity_date,
                'due_date': due_date,
                'completed': data.get('completed', False),
                'created_by': current_user
            })

            logger.info(f"Created activity for partner {data.get('partner_id')}")
            return jsonify({'message': 'Activity created'}), 201

    except Exception as e:
        logger.error(f"Error creating activity: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create activity'}), 500


@crm_api_bp.route('/activities/<activity_id>', methods=['PUT'])
@jwt_required()
def update_activity(activity_id: str):
    """Update an activity."""
    try:
        from config.database import get_db_session
        from sqlalchemy import text

        data = request.get_json()
        current_user = get_jwt_identity() or 'system'

        with get_db_session() as session:
            update_fields = []
            params = {'activity_id': activity_id}

            if 'activity_type' in data:
                update_fields.append("activity_type = :activity_type")
                params['activity_type'] = data['activity_type']

            if 'subject' in data:
                update_fields.append("subject = :subject")
                params['subject'] = data['subject']

            if 'description' in data:
                update_fields.append("description = :description")
                params['description'] = data['description']

            if 'activity_date' in data:
                update_fields.append("activity_date = :activity_date")
                params['activity_date'] = datetime.fromisoformat(data['activity_date'].replace('Z', '+00:00')) if data['activity_date'] else None

            if 'due_date' in data:
                update_fields.append("due_date = :due_date")
                params['due_date'] = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00')) if data['due_date'] else None

            if 'completed' in data:
                update_fields.append("completed = :completed")
                params['completed'] = data['completed']

            if not update_fields:
                return jsonify({'error': 'No fields to update'}), 400

            update_fields.append("updated_at = NOW()")

            query = f"""
                UPDATE crm_activities SET {', '.join(update_fields)}
                WHERE id::text = :activity_id
            """

            session.execute(text(query), params)

            logger.info(f"Updated activity: {activity_id}")
            return jsonify({'message': 'Activity updated'})

    except Exception as e:
        logger.error(f"Error updating activity: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update activity'}), 500


@crm_api_bp.route('/activities/<activity_id>', methods=['DELETE'])
@jwt_required()
def delete_activity(activity_id: str):
    """Delete an activity (soft delete)."""
    try:
        from config.database import get_db_session
        from sqlalchemy import text

        with get_db_session() as session:
            session.execute(text("""
                UPDATE crm_activities
                SET is_deleted = true, updated_at = NOW()
                WHERE id::text = :activity_id
            """), {'activity_id': activity_id})

            logger.info(f"Deleted activity: {activity_id}")
            return '', 204

    except Exception as e:
        logger.error(f"Error deleting activity: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete activity'}), 500
