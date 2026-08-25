import uuid

from django.db import models

from src.quiz.shared.quiz_enums import QuizResultStatusEnum
from src.shared.infrastructure.persistence.django.models import (
    QuizActiveMixin,
    QuizTimeStampMixin,
)


class QuizUserResult(QuizTimeStampMixin, QuizActiveMixin):
    """Represent the current result of a user for a quiz."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.UUIDField(
        db_column="user_id",
        editable=False,
        help_text="The user UUID associated with this result.",
    )
    tenant_user = models.UUIDField(
        db_column="tenant_user_id",
        editable=False,
        null=True,
        blank=True,
        help_text="The optional tenant-user UUID associated with this result.",
    )
    quiz = models.ForeignKey(
        "Quiz",
        on_delete=models.PROTECT,
        related_name="user_results",
    )
    quiz_form = models.OneToOneField(
        "QuizForm",
        on_delete=models.PROTECT,
        related_name="current_result",
    )
    attempt_number = models.PositiveIntegerField(
        help_text="The number of the latest attempt represented by this result.",
    )
    status = models.CharField(
        max_length=50,
        choices=QuizResultStatusEnum.choices(),
        default=QuizResultStatusEnum.REJECTED.value,
    )

    class Meta:
        db_table = "quiz_user_result"
        verbose_name = "Quiz User Result"
        verbose_name_plural = "Quiz User Results"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "tenant_user", "quiz"),
                condition=models.Q(tenant_user__isnull=False),
                name="uq_quiz_user_result_user_tenant_user_quiz",
            ),
            models.UniqueConstraint(
                fields=("user", "quiz"),
                condition=models.Q(tenant_user__isnull=True),
                name="uq_quiz_user_result_user_quiz_no_tenant",
            ),
        ]
        indexes = [
            models.Index(
                fields=("user", "quiz", "status"),
                name="idx_qur_user_quiz_status",
            ),
            models.Index(
                fields=("tenant_user", "quiz", "status"),
                name="idx_qur_tenant_quiz_status",
            ),
        ]


class QuizUserResultHistory(QuizTimeStampMixin, QuizActiveMixin):
    """Represent an immutable historical result of a quiz attempt."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.UUIDField(
        db_column="user_id",
        editable=False,
        help_text="The user UUID associated with this result.",
    )
    tenant_user = models.UUIDField(
        db_column="tenant_user_id",
        editable=False,
        null=True,
        blank=True,
        help_text="The optional tenant-user UUID associated with this result.",
    )
    quiz = models.ForeignKey(
        "Quiz",
        on_delete=models.PROTECT,
        related_name="result_history",
    )
    quiz_form = models.OneToOneField(
        "QuizForm",
        on_delete=models.PROTECT,
        related_name="result_history",
    )
    attempt_number = models.PositiveIntegerField(
        help_text="The sequential number of the historical attempt.",
    )
    status = models.CharField(
        max_length=50,
        choices=QuizResultStatusEnum.choices(),
        default=QuizResultStatusEnum.REJECTED.value,
    )

    class Meta:
        db_table = "quiz_user_result_history"
        verbose_name = "Quiz User Result History"
        verbose_name_plural = "Quiz User Result Histories"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "tenant_user", "quiz", "attempt_number"),
                condition=models.Q(tenant_user__isnull=False),
                name="uq_result_history_user_tenant_user_quiz_attempt",
            ),
            models.UniqueConstraint(
                fields=("user", "quiz", "attempt_number"),
                condition=models.Q(tenant_user__isnull=True),
                name="uq_result_history_user_quiz_attempt_no_tenant",
            ),
        ]
        indexes = [
            models.Index(
                fields=("user", "quiz", "attempt_number"),
                name="idx_urh_user_quiz_attempt",
            ),
            models.Index(
                fields=("tenant_user", "quiz", "attempt_number"),
                name="idx_urh_tenant_quiz_attempt",
            ),
        ]
