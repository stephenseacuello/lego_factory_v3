"""
Celery Application Factory
============================
Configures Celery with Redis broker for async task processing.
"""
from celery import Celery


def create_celery_app(app=None):
    """Create and configure Celery application."""
    from config.settings import get_config
    config = get_config()

    celery = Celery(
        'lego_factory',
        broker=f'redis://{config.redis.host}:{config.redis.port}/{config.redis.db + 1}',
        backend=f'redis://{config.redis.host}:{config.redis.port}/{config.redis.db + 2}',
    )

    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=300,
        task_time_limit=600,
        beat_schedule={
            'calculate-daily-oee': {
                'task': 'services.tasks.reporting_tasks.calculate_daily_oee',
                'schedule': 3600.0,  # Every hour
            },
            'evaluate-cbm-conditions': {
                'task': 'services.tasks.maintenance_tasks.evaluate_all_machines_cbm',
                'schedule': 900.0,  # Every 15 minutes
            },
        },
    )

    if app:
        celery.conf.update(app.config)

        class ContextTask(celery.Task):
            abstract = True
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        celery.Task = ContextTask

    return celery


# Module-level celery instance
celery_app = create_celery_app()
