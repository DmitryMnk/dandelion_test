from celery import Celery

from core import settings

celery_app = Celery(
    "app_worker",
    broker=settings.REDIS.celery_backend_connection_url,
    backend=settings.REDIS.celery_backend_connection_url,
    include=["services.celery.tasks.events"],
)
