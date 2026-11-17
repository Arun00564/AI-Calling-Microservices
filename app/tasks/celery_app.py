from celery import Celery
from datetime import timedelta

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

celery_app.conf.imports = (
    "app.tasks.voice_tasks",
    "app.tasks.voice_queue_tasks",
    "app.tasks.campaign_tasks",
)


celery_app.conf.beat_schedule = {
    "process-voice-call-queue": {
        "task": "app.tasks.voice_queue_tasks.process_voice_call_queue",
        "schedule": timedelta(seconds=2),
    },
    "process-campaign-queue-every-10-seconds": {
        "task": "app.tasks.campaign_tasks.process_campaign_queue",
        "schedule": timedelta(seconds=10),
    },
}
