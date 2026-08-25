import uuid

from django.db import models

from src.quiz.shared.quiz_enums import QuestionResponseTypeEnum
from src.shared.infrastructure.persistence.django.models import (
    QuizActiveMixin,
    QuizSoftDeleteMixin,
    QuizTimeStampMixin,
)


class Question(QuizTimeStampMixin, QuizActiveMixin, QuizSoftDeleteMixin):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    text = models.CharField(max_length=200)
    response_type = models.CharField(
        max_length=20,
        choices=QuestionResponseTypeEnum.choices(),
        default=QuestionResponseTypeEnum.SINGLE.value,
    )
    quiz = models.ForeignKey("Quiz", on_delete=models.PROTECT, related_name="questions")
    order = models.PositiveIntegerField(
        default=0,
        help_text="Position of this question within its quiz, starting at 1.",
    )
    tenant = models.UUIDField(
        db_column="tenant_id",
        editable=False,
        help_text="The tenant(uuid) this quiz is assigned to",
    )
    tenant_user = models.UUIDField(
        db_column="tenant_user_id",
        editable=False,
        help_text="The tenant_user(uuid) that created this quiz",
    )

    class Meta:
        db_table = "question"
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        # `created_at` is not decoration: it makes the order total when two
        # questions share a position, so no read is ever non-deterministic.
        ordering = ("order", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "tenant",
                    "quiz",
                    "text",
                    "response_type",
                ),
                condition=models.Q(
                    is_active=True,
                    is_deleted=False,
                ),
                name="uq_question_tenant_quiz_text_response_type",
            ),
        ]
        indexes = [
            models.Index(
                fields=("quiz",),
                condition=models.Q(
                    is_active=True,
                    is_deleted=False,
                ),
                name="idx_question_quiz_active",
            ),
            models.Index(
                fields=("quiz", "order"),
                name="idx_question_quiz_order",
            ),
        ]
