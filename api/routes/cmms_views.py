"""
LEGO Factory v3 - CMMS View Routes
===================================
Maintenance management dashboard views.
"""

from flask import Blueprint, render_template, jsonify, request
import logging

logger = logging.getLogger(__name__)

cmms_bp = Blueprint('cmms', __name__, url_prefix='/cmms')


@cmms_bp.route('/assets')
def assets():
    """Asset management dashboard."""
    try:
        from config.database import get_db_session
        from services.cmms.asset_service import get_asset_service

        with get_db_session() as session:
            service = get_asset_service(session)
            assets_list = service.get_assets(limit=100)
    except Exception as e:
        logger.warning(f'Exception in cmms_views.py: {e}')
        assets_list = []

    return render_template('cmms/assets.html', assets=assets_list)


@cmms_bp.route('/assets/<asset_number>')
def asset_detail(asset_number):
    """Asset detail view."""
    try:
        from config.database import get_db_session
        from services.cmms.asset_service import get_asset_service

        with get_db_session() as session:
            service = get_asset_service(session)
            asset = service.get_asset(asset_number)
    except Exception as e:
        logger.warning(f'Exception in cmms_views.py: {e}')
        asset = None

    if not asset:
        return render_template('errors/404.html'), 404

    return render_template('cmms/asset_detail.html', asset=asset)


@cmms_bp.route('/work-orders')
def work_orders():
    """Maintenance work orders dashboard."""
    try:
        from config.database import get_db_session
        from services.cmms.maintenance_service import get_maintenance_service

        with get_db_session() as session:
            service = get_maintenance_service(session)
            wos = service.get_work_orders(limit=50)
    except Exception as e:
        logger.warning(f'Exception in cmms_views.py: {e}')
        wos = []

    return render_template('cmms/work_orders.html', work_orders=wos)


@cmms_bp.route('/pm-schedules')
def pm_schedules():
    """PM schedules dashboard."""
    return render_template('cmms/pm_schedules.html')


@cmms_bp.route('/spare-parts')
def spare_parts():
    """Spare parts inventory dashboard."""
    return render_template('cmms/spare_parts.html')
