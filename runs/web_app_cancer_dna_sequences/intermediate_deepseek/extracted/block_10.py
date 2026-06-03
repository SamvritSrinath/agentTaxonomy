from celery import Celery
from app.config import REDIS_URL

celery_app = Celery(
    "cancer_genomics",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"],
)

celery_app.conf.task_routes = {
    "app.tasks.process_upload": {"queue": "genomics"},
}
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
