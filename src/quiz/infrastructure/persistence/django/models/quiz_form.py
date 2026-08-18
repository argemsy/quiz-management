import uuid

from django.db import models

from src.quiz.shared.quiz_enums import QuizFormStatusEnum
from src.shared.infrastructure.persistence.django.models import QuizTimeStampMixin


class QuizForm(QuizTimeStampMixin):
    """Represent a user's quiz form and its current response progress."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.UUIDField(
        db_column="user_id",
        editable=False,
        help_text="The user UUID that owns this quiz form.",
    )
    tenant_user = models.UUIDField(
        db_column="tenant_user_id",
        editable=False,
        null=True,
        blank=True,
        help_text="The optional tenant-user UUID associated with this form.",
    )
    quiz = models.ForeignKey(
        "Quiz",
        on_delete=models.PROTECT,
        related_name="forms",
    )
    correct_answers = models.PositiveIntegerField(
        default=0,
        help_text="Number of correct responses in this form.",
    )
    wrong_answers = models.PositiveIntegerField(
        default=0,
        help_text="Number of incorrect responses in this form.",
    )
    status = models.CharField(
        max_length=50,
        choices=QuizFormStatusEnum.choices(),
        default=QuizFormStatusEnum.NOT_STARTED.value,
    )
    started_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    quiz_configuration_snapshot = models.JSONField(
        editable=False,
        default=dict,
        help_text="Immutable quiz configuration captured when the form started.",
    )

    class Meta:
        db_table = "quiz_form"
        verbose_name = "Quiz Form"
        verbose_name_plural = "Quiz Forms"
        indexes = [
            models.Index(
                fields=("user", "quiz"),
                name="idx_quiz_form_user_quiz",
            ),
            models.Index(
                fields=("tenant_user", "quiz"),
                name="idx_quiz_form_tenant_user_quiz",
            ),
        ]
