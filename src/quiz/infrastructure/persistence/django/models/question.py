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
        ]
