"""
LEGO Factory v3 - LEGO View Routes
===================================
LEGO brick design and catalog dashboards.
"""

from flask import Blueprint, render_template, jsonify, request
import logging

logger = logging.getLogger(__name__)

lego_bp = Blueprint('lego', __name__, url_prefix='/lego')


@lego_bp.route('/catalog')
def catalog():
    """Brick catalog dashboard."""
    try:
        from services.lego.brick_catalog import BRICK_CATALOG
        bricks = [b.to_dict() for b in BRICK_CATALOG.values()]
    except Exception as e:
        logger.warning(f'Exception in lego_views.py: {e}')
        bricks = []

    return render_template('lego/catalog.html', bricks=bricks)


@lego_bp.route('/designer')
def designer():
    """Custom brick designer."""
    return render_template('lego/designer.html')


@lego_bp.route('/export-jobs')
def export_jobs():
    """Export jobs dashboard."""
    try:
        from config.database import get_db_session
        from models.lego.brick_designs import BrickExportJob

        with get_db_session() as session:
            jobs = session.query(BrickExportJob).order_by(BrickExportJob.created_at.desc()).limit(50).all()
            jobs_list = [j.to_dict() for j in jobs]
    except Exception as e:
        logger.warning(f'Exception in lego_views.py: {e}')
        jobs_list = []

    return render_template('lego/export_jobs.html', jobs=jobs_list)


@lego_bp.route('/brick/<part_id>')
def brick_detail(part_id):
    """Brick detail view."""
    try:
        from services.lego.brick_catalog import get_brick
        brick_def = get_brick(part_id)
        brick = brick_def.to_dict() if brick_def else None
    except Exception as e:
        logger.warning(f'Exception in lego_views.py: {e}')
        brick = None

    if not brick:
        return render_template('errors/404.html'), 404

    return render_template('lego/brick_detail.html', brick=brick)
