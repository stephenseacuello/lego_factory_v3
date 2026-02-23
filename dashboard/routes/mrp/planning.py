"""
MRP Planning API - Material requirements planning endpoints.
"""

from flask import Blueprint, jsonify, request

from models import get_db_session
from services.mrp import MRPEngine, LotSizingPolicy

planning_bp = Blueprint('planning', __name__, url_prefix='/planning')


@planning_bp.route('/run', methods=['POST'])
def run_mrp():
    """
    Run MRP planning.

    Request body:
    {
        "part_ids": ["uuid1", "uuid2"],  // Optional, null = all parts
        "horizon_weeks": 12,
        "lot_sizing": "lot_for_lot"
    }
    """
    data = request.get_json() or {}

    part_ids = data.get('part_ids')
    horizon_weeks = data.get('horizon_weeks', 12)
    lot_sizing_str = data.get('lot_sizing', 'lot_for_lot')

    try:
        lot_sizing = LotSizingPolicy(lot_sizing_str)
    except ValueError:
        return jsonify({'error': f'Invalid lot sizing policy: {lot_sizing_str}'}), 400

    with get_db_session() as session:
        engine = MRPEngine(session)

        result = engine.run_mrp(
            part_ids=part_ids,
            horizon_weeks=horizon_weeks,
            lot_sizing=lot_sizing
        )

        return jsonify(result)


@planning_bp.route('/planned-orders', methods=['GET'])
def get_planned_orders():
    """
    Get planned orders from last MRP run.

    Query params:
    - part_id: Filter by part
    - order_type: 'manufacturing' or 'purchase'
    """
    part_id = request.args.get('part_id')
    order_type = request.args.get('order_type')

    # Run quick MRP to get current planned orders
    with get_db_session() as session:
        engine = MRPEngine(session)

        result = engine.run_mrp(
            part_ids=[part_id] if part_id else None,
            horizon_weeks=8
        )

        orders = result['planned_orders']

        if order_type:
            orders = [o for o in orders if o['order_type'] == order_type]

        return jsonify({
            'planned_orders': orders,
            'total': len(orders)
        })


@planning_bp.route('/explode', methods=['POST'])
def explode_orders():
    """
    Explode planned orders through BOM.

    Request body:
    {
        "planned_orders": [
            {"part_id": "uuid", "quantity": 100, "due_date": "2024-02-01"}
        ]
    }
    """
    data = request.get_json()
    orders_data = data.get('planned_orders', [])

    if not orders_data:
        return jsonify({'error': 'planned_orders are required'}), 400

    from datetime import datetime
    from services.mrp.mrp_engine import PlannedOrder

    with get_db_session() as session:
        engine = MRPEngine(session)

        # Convert to PlannedOrder objects
        planned_orders = []
        for o in orders_data:
            due_date = datetime.fromisoformat(o['due_date'])
            po = PlannedOrder(
                part_id=o['part_id'],
                part_number=o.get('part_number', ''),
                part_name=o.get('part_name', ''),
                order_type='manufacturing',
                quantity=o['quantity'],
                due_date=due_date,
                start_date=due_date,
                level=0
            )
            planned_orders.append(po)

        # Explode through BOM
        exploded = engine.explode_planned_orders(planned_orders)

        return jsonify({
            'total_orders': len(exploded),
            'by_level': {
                level: len([o for o in exploded if o.level == level])
                for level in range(max(o.level for o in exploded) + 1)
            },
            'orders': [
                {
                    'part_id': o.part_id,
                    'part_number': o.part_number,
                    'order_type': o.order_type,
                    'quantity': o.quantity,
                    'due_date': o.due_date.isoformat(),
                    'start_date': o.start_date.isoformat(),
                    'level': o.level,
                    'parent': o.parent_order
                }
                for o in exploded
            ]
        })


@planning_bp.route('/action-messages', methods=['GET'])
def get_action_messages():
    """
    Get MRP action/exception messages.

    Query params:
    - part_id: Filter by part
    """
    part_id = request.args.get('part_id')

    with get_db_session() as session:
        engine = MRPEngine(session)
        messages = engine.get_action_messages(part_id=part_id)

        return jsonify({
            'messages': messages,
            'total': len(messages),
            'critical': sum(1 for m in messages if m.get('priority') == 'CRITICAL'),
            'warnings': sum(1 for m in messages if m.get('priority') == 'WARNING')
        })
