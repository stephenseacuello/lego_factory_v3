"""
LEGO Factory v3 - QMS View Routes
==================================
Quality Management dashboard views.
"""

from flask import Blueprint, render_template, jsonify, request
import logging

logger = logging.getLogger(__name__)

qms_bp = Blueprint('qms', __name__, url_prefix='/qms')


@qms_bp.route('/documents')
def documents():
    """Document control dashboard."""
    return render_template('qms/documents.html')


@qms_bp.route('/ncr')
def ncr_list():
    """NCR list dashboard."""
    try:
        from config.database import get_db_session
        from services.qms.ncr_service import get_ncr_service

        with get_db_session() as session:
            service = get_ncr_service(session)
            ncrs = service.get_ncrs(limit=50)
    except Exception as e:
        logger.warning(f'Exception in qms_views.py: {e}')
        ncrs = []

    return render_template('qms/ncr_list.html', ncrs=ncrs)


@qms_bp.route('/ncr/<ncr_number>')
def ncr_detail(ncr_number):
    """NCR detail view."""
    try:
        from config.database import get_db_session
        from services.qms.ncr_service import get_ncr_service

        with get_db_session() as session:
            service = get_ncr_service(session)
            ncr = service.get_ncr(ncr_number)
    except Exception as e:
        logger.warning(f'Exception in qms_views.py: {e}')
        ncr = None

    if not ncr:
        return render_template('errors/404.html'), 404

    return render_template('qms/ncr_detail.html', ncr=ncr)


@qms_bp.route('/capa')
def capa_list():
    """CAPA list dashboard."""
    return render_template('qms/capa_list.html')


@qms_bp.route('/audits')
def audits():
    """Audit management dashboard."""
    return render_template('qms/audits.html')


@qms_bp.route('/training')
def training():
    """Training management dashboard."""
    return render_template('qms/training.html')


@qms_bp.route('/calibration')
def calibration():
    """Calibration management dashboard."""
    return render_template('qms/calibration.html')


@qms_bp.route('/spc')
def spc():
    """SPC charts dashboard."""
    return render_template('qms/spc.html')
