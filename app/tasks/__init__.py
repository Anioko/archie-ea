"""
Celery task definitions for background processing.

This package contains Celery tasks for asynchronous operations including
batch import processing. Tasks are feature-flagged via CELERY_ENABLED
configuration and fall back to synchronous processing when Celery is
not available.
"""

import os

try:
    from celery import Celery as _Celery

    celery = _Celery(
        "flask_archie_tasks",
        broker=os.environ.get("CELERY_BROKER_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/0")),
        backend=os.environ.get("CELERY_RESULT_BACKEND", os.environ.get("REDIS_URL", "redis://localhost:6379/0")),
    )
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )

    class _ContextTask(celery.Task):
        """Push Flask app context for every task body."""

        def __call__(self, *args, **kwargs):
            from manage import app as _flask_app
            with _flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = _ContextTask

except ImportError:
    celery = None
