from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ai_calling",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=False,
)

celery_app.conf.imports = ("app.tasks.voice_tasks",)
