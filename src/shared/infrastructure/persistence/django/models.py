from functools import wraps

# Third-party Libraries
from asgiref.sync import sync_to_async
from django.db import close_old_connections, models, utils
from nanoid import generate

from src.shared.infrastructure.logging import get_logger

logger = get_logger(__name__)


class QuizTimeStampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        abstract = True


class QuizSoftDeleteMixin(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True, editable=False)

    class Meta:
        abstract = True


class QuizActiveMixin(models.Model):
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


def nanoid_generator(size: int = 10) -> str:
    return generate(size=size)


def async_database():
    def decorator(func):
        @sync_to_async(thread_sensitive=True)
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (utils.InterfaceError, utils.OperationalError):
                close_old_connections()
                logger.info(
                    "async_database", close_old_connections="close_old_connections()"
                )
                return func(*args, **kwargs)

        return wrapper

    return decorator
