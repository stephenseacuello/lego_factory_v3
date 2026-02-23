"""
Maintenance Celery Tasks
==========================
Async tasks for condition-based maintenance evaluation.
"""
import logging

logger = logging.getLogger(__name__)

try:
    from app.celery_app import celery_app
except Exception:
    celery_app = None
    logger.warning("Celery app not available - maintenance tasks will run synchronously")


def _make_task(func):
    """Register function as a Celery task if celery_app is available."""
    if celery_app is not None:
        return celery_app.task(name=f'services.tasks.maintenance_tasks.{func.__name__}')(func)
    return func


@_make_task
def evaluate_all_machines_cbm():
    """Evaluate CBM conditions for all machines (runs every 15 min)."""
    logger.info("Evaluating CBM conditions for all machines...")
    try:
        from config.database import get_db_session
        from services.cmms.cbm_service import CBMService
        session = get_db_session()
        try:
            service = CBMService(session)
            results = service.evaluate_all_machines()
            if results:
                logger.warning(f"CBM: {len(results)} machines need maintenance attention")
            return {'machines_evaluated': True, 'alerts': len(results)}
        finally:
            session.close()
    except Exception as e:
        logger.error(f"CBM evaluation failed: {e}")
        return {'error': str(e)}
