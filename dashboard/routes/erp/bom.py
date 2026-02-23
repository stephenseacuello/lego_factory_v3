"""
BOM API - Bill of Materials management.
"""

from flask import Blueprint, jsonify, request, render_template

from models import get_db_session
from services.erp import BOMService

bom_bp = Blueprint('bom', __name__, url_prefix='/bom')


# =============================================================================
# Dashboard Page Route
# =============================================================================

@bom_bp.route('/page', methods=['GET'])
def bom_dashboard():
    """Render the BOM dashboard page."""
    return render_template('pages/erp/bom_dashboard.html')


# =============================================================================
# API Routes
# =============================================================================

@bom_bp.route('/<part_id>', methods=['GET'])
def get_bom(part_id: str):
    """Get BOM for a part."""
    with get_db_session() as session:
        service = BOMService(session)
        bom = service.get_bom(part_id)

        return jsonify({
            'part_id': part_id,
            'bom_lines': bom
        })


@bom_bp.route('', methods=['POST'])
def create_bom_line():
    """
    Create a BOM line.

    Request body:
    {
        "parent_part_id": "uuid",
        "child_part_id": "uuid",
        "quantity": 4,
        "sequence": 10,
        "notes": "Optional"
    }
    """
    data = request.get_json()

    required = ['parent_part_id', 'child_part_id', 'quantity']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'error': f'Missing fields: {missing}'}), 400

    with get_db_session() as session:
        service = BOMService(session)

        try:
            bom_line = service.create_bom_line(
                parent_part_id=data['parent_part_id'],
                child_part_id=data['child_part_id'],
                quantity=data['quantity'],
                sequence=data.get('sequence', 10),
                bom_type=data.get('bom_type', 'manufacturing'),
                notes=data.get('notes')
            )

            return jsonify({
                'id': str(bom_line.id),
                'message': 'BOM line created'
            }), 201

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@bom_bp.route('/<part_id>/explode', methods=['GET'])
def explode_bom(part_id: str):
    """
    Multi-level BOM explosion.

    Query params:
    - quantity: Base quantity (default 1)
    """
    quantity = request.args.get('quantity', 1, type=int)

    with get_db_session() as session:
        service = BOMService(session)
        explosion = service.explode_bom(part_id, quantity=quantity)

        return jsonify({
            'part_id': part_id,
            'quantity': quantity,
            'explosion': explosion
        })


@bom_bp.route('/<part_id>/summarized', methods=['GET'])
def get_summarized_bom(part_id: str):
    """Get summarized (rolled up) BOM."""
    quantity = request.args.get('quantity', 1, type=int)

    with get_db_session() as session:
        service = BOMService(session)
        summary = service.get_summarized_bom(part_id, quantity=quantity)

        return jsonify({
            'part_id': part_id,
            'quantity': quantity,
            'summarized_bom': summary
        })


@bom_bp.route('/where-used/<part_id>', methods=['GET'])
def where_used(part_id: str):
    """Find all parents that use this part."""
    with get_db_session() as session:
        service = BOMService(session)
        parents = service.where_used(part_id)

        return jsonify({
            'part_id': part_id,
            'used_in': parents
        })


@bom_bp.route('/compare', methods=['POST'])
def compare_boms():
    """
    Compare two BOMs.

    Request body:
    {
        "part_id_1": "uuid",
        "part_id_2": "uuid"
    }
    """
    data = request.get_json()

    part_id_1 = data.get('part_id_1')
    part_id_2 = data.get('part_id_2')

    if not all([part_id_1, part_id_2]):
        return jsonify({'error': 'Both part_id_1 and part_id_2 are required'}), 400

    with get_db_session() as session:
        service = BOMService(session)
        comparison = service.compare_boms(part_id_1, part_id_2)

        return jsonify(comparison)
