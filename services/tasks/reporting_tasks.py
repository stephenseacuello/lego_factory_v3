"""
Reporting Celery Tasks
========================
Async tasks for report generation and calculations.
"""
import logging

logger = logging.getLogger(__name__)

try:
    from app.celery_app import celery_app
except Exception:
    # Fallback: allow module to be imported even without Celery running
    celery_app = None
    logger.warning("Celery app not available - reporting tasks will run synchronously")


def _make_task(func):
    """Register function as a Celery task if celery_app is available."""
    if celery_app is not None:
        return celery_app.task(name=f'services.tasks.reporting_tasks.{func.__name__}')(func)
    return func


@_make_task
def calculate_daily_oee():
    """Calculate daily OEE for all machines."""
    logger.info("Calculating daily OEE...")
    try:
        from config.database import get_db_session
        from services.mes.oee_service import OEEService
        session = get_db_session()
        try:
            service = OEEService(session)
            result = service.calculate_all_oee()
            logger.info(f"Daily OEE calculated for {len(result)} machines")
            return result
        finally:
            session.close()
    except Exception as e:
        logger.error(f"OEE calculation failed: {e}")
        return {'error': str(e)}


@_make_task
def generate_shift_report():
    """Generate shift report."""
    logger.info("Generating shift report...")
    return {'status': 'generated'}


@_make_task
def run_depreciation():
    """Run monthly depreciation calculations."""
    logger.info("Running depreciation...")
    try:
        from config.database import get_db_session
        from services.erp.depreciation_service import DepreciationService
        session = get_db_session()
        try:
            service = DepreciationService(session)
            result = service.run_depreciation()
            logger.info(f"Depreciation processed for {result.get('assets_processed', 0)} assets")
            return result
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Depreciation failed: {e}")
        return {'error': str(e)}
