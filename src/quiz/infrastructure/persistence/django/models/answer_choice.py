import uuid

from django.db import models

from src.shared.infrastructure.persistence.django.models import (
    QuizActiveMixin,
    QuizSoftDeleteMixin,
    QuizTimeStampMixin,
)


class AnswerChoice(QuizTimeStampMixin, QuizActiveMixin, QuizSoftDeleteMixin):
    """Represent an answer option belonging to a question."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    text = models.CharField(max_length=500)
    question = models.ForeignKey(
        "Question",
        on_delete=models.PROTECT,
        related_name="answers",
    )
    is_correct = models.BooleanField(
        default=False,
    )
    tenant = models.UUIDField(
        db_column="tenant_id",
        editable=False,
        help_text="The tenant UUID this answer belongs to.",
    )
    tenant_user = models.UUIDField(
        db_column="tenant_user_id",
        editable=False,
        help_text="The tenant_user(uuid) that created this quiz",
    )

    class Meta:
        db_table = "answer_choice"
        verbose_name = "Answer Choice"
        verbose_name_plural = "Answer Choices"

        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "question", "text"),
                condition=models.Q(
                    is_active=True,
                    is_deleted=False,
                ),
                name="uq_answer_tenant_question_text",
            ),
        ]

        indexes = [
            models.Index(
                fields=("question",),
                condition=models.Q(
                    is_active=True,
                    is_deleted=False,
                ),
                name="idx_answer_question_active",
            ),
        ]
