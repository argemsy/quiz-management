import uuid

from django.db import models

from src.eventing.shared.eventing_enums import FailedEventStatus
from src.shared.infrastructure.persistence.django.models import QuizTimeStampMixin


class FailedEventMessage(QuizTimeStampMixin):
    """
    Dead-letter record for an EventBusMessage a handler failed to process.

    Captures exactly what's needed to retry that single handler later
    (``channel_path`` / ``handler_path`` are dotted references resolved
    dynamically at retry time — see
    ``src.eventing.application.retry_failed_event_use_case.use_case``)
    without re-running every other handler already subscribed to the channel.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    channel_path = models.CharField(max_length=255)
    handler_path = models.CharField(max_length=255)
    resource_name = models.CharField(max_length=255)
    correlation_id = models.UUIDField(
        db_index=True,
        help_text=(
            "Identifier used to correlate all events and operations "
            "belonging to the same request or business transaction."
        ),
    )
    payload = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    error_type = models.CharField(max_length=255)
    error_message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=FailedEventStatus.choices(),
        default=FailedEventStatus.PENDING.value,
    )
    retry_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "failed_event_message"
        verbose_name = "Failed event message"
        verbose_name_plural = "Failed event messages"
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="idx_failed_event_retry",
            )
        ]
