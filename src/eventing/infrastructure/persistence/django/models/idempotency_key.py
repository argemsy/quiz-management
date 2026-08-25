import uuid

from django.db import models

from src.eventing.shared.eventing_enums import IdempotencyKeyStatus
from src.shared.infrastructure.persistence.django.models import QuizTimeStampMixin


class IdempotencyKey(QuizTimeStampMixin):
    """Postgres source of truth for mutation idempotency. The `operation_id`
    unique constraint here — not the Redis fast-path lock — is what actually
    prevents a duplicate record when a client resubmits a mutation attempt
    without having seen the original response; see
    `openspec/changes/mutation-idempotency-rate-limit/design.md` - Decisions.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    operation_id = models.UUIDField(unique=True, editable=False)
    status = models.CharField(
        max_length=20,
        choices=IdempotencyKeyStatus.choices(),
        default=IdempotencyKeyStatus.IN_PROGRESS.value,
    )
    response_payload = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "idempotency_key"
        verbose_name = "Idempotency key"
        verbose_name_plural = "Idempotency keys"
