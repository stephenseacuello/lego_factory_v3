"""
LEGO Factory v3 - MES View Routes
==================================
MES dashboard views for work orders, scheduling, OEE.
"""

from flask import Blueprint, render_template, jsonify, request
import logging

logger = logging.getLogger(__name__)

mes_bp = Blueprint('mes', __name__, url_prefix='/mes-data')


@mes_bp.route('/work-orders')
def work_orders():
    """Work orders dashboard."""
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import get_work_order_service

        with get_db_session() as session:
            service = get_work_order_service(session)
            wo_list = service.get_work_orders(limit=50)
            wo_counts = {
                'draft': len([w for w in wo_list if w.get('status') == 'draft']),
                'released': len([w for w in wo_list if w.get('status') == 'released']),
                'in_progress': len([w for w in wo_list if w.get('status') == 'in_progress']),
                'on_hold': len([w for w in wo_list if w.get('status') == 'on_hold']),
                'completed': len([w for w in wo_list if w.get('status') == 'completed']),
                'cancelled': len([w for w in wo_list if w.get('status') == 'cancelled']),
            }
    except Exception as e:
        logger.warning(f'Exception in mes_views.py: {e}')
        wo_list = []
        wo_counts = {'draft': 0, 'released': 0, 'in_progress': 0, 'on_hold': 0, 'completed': 0, 'cancelled': 0}

    return render_template('mes/work_orders.html', work_orders=wo_list, wo_counts=wo_counts)


@mes_bp.route('/work-orders/<wo_number>')
def work_order_detail(wo_number):
    """Work order detail view."""
    try:
        from config.database import get_db_session
        from services.mes.work_order_service import get_work_order_service

        with get_db_session() as session:
            service = get_work_order_service(session)
            wo = service.get_work_order(wo_number)
    except Exception as e:
        logger.warning(f'Exception in mes_views.py: {e}')
        wo = None

    if not wo:
        return render_template('errors/404.html'), 404

    return render_template('mes/work_order_detail.html', work_order=wo)


@mes_bp.route('/scheduling')
def scheduling():
    """Job scheduling dashboard."""
    return render_template('mes/scheduling.html')


@mes_bp.route('/oee')
def oee():
    """OEE dashboard."""
    try:
        from services.mes.oee_service import get_oee_dashboard
        oee_data = get_oee_dashboard()
    except Exception as e:
        logger.warning(f'Exception in mes_views.py: {e}')
        oee_data = {'overall': 85.0, 'availability': 90.0, 'performance': 95.0, 'quality': 99.0}

    return render_template('mes/oee.html', oee=oee_data)


@mes_bp.route('/downtime')
def downtime():
    """Downtime tracking dashboard."""
    return render_template('mes/downtime.html')


@mes_bp.route('/labor')
def labor():
    """Labor management dashboard."""
    return render_template('mes/labor.html')


@mes_bp.route('/resources')
def resources():
    """Resource dashboard - MESA-11 Resource Allocation & Status."""
    return render_template('mes/resources.html')


@mes_bp.route('/resources/<machine_id>')
def resource_detail(machine_id):
    """Machine resource detail view."""
    return render_template('mes/resource_detail.html', machine_id=machine_id)


@mes_bp.route('/materials')
def materials():
    """Material inventory dashboard."""
    return render_template('mes/materials.html')
