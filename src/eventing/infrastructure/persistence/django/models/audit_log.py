import uuid

from django.db import models

from src.eventing.shared.eventing_enums import (
    AuditLogActionEnum,
    AuditLogContentTypeEnum,
    AuditLogSourceEnum,
)
from src.shared.infrastructure.persistence.django.models import QuizTimeStampMixin


def audit_log_metadata() -> dict:
    return {"previous_state": {}, "current_state": {}}


class AuditLog(QuizTimeStampMixin):
    """Immutable record of a change made to an entity anywhere in the system."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    object_id = models.UUIDField(
        db_index=True,
        help_text="The ID of the audited record.",
    )
    object_repr = models.TextField(
        blank=True,
        null=True,
        help_text="Human-readable snapshot of the audited record.",
    )
    user = models.UUIDField(
        db_column="user_id",
        null=True,
        blank=True,
        db_index=True,
        editable=False,
        help_text="The user UUID that performed the change, if any.",
    )
    tenant = models.UUIDField(
        db_column="tenant_id",
        null=True,
        blank=True,
        db_index=True,
        editable=False,
        help_text="The tenant UUID this change belongs to, if any.",
    )
    correlation_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        editable=False,
        help_text="Groups entries created by the same request or bulk operation.",
    )
    content_type = models.CharField(
        max_length=30,
        choices=AuditLogContentTypeEnum.choices(),
        db_index=True,
        editable=False,
        help_text="Which model was changed.",
    )
    source_type = models.CharField(
        max_length=20,
        choices=AuditLogSourceEnum.choices(),
        db_index=True,
        editable=False,
        help_text="Where the change originated.",
    )
    action_type = models.CharField(
        max_length=20,
        choices=AuditLogActionEnum.choices(),
        db_index=True,
        editable=False,
        help_text="What kind of change happened.",
    )
    metadata = models.JSONField(
        blank=True,
        null=True,
        default=audit_log_metadata,
        editable=False,
        help_text="previous_state / current_state snapshots and descriptive messages.",
    )

    def __str__(self):
        return self.object_repr

    class Meta:
        db_table = "audit_log"
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(
                fields=["tenant", "object_id", "content_type", "source_type"],
                name="idx_audit_tenant_object_source",
            ),
            models.Index(
                fields=[
                    "tenant",
                    "object_id",
                    "content_type",
                    "source_type",
                    "action_type",
                ],
                name="idx_audit_tenant_object_action",
            ),
            models.Index(
                fields=["correlation_id"],
                name="idx_audit_correlation_id",
            ),
        ]

    def __str__(self):
        return self.action_type
