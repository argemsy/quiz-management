import uuid

from django.db import models

from src.quiz.shared.quiz_enums import QuizTypeEnum
from src.shared.infrastructure.persistence.django.models import (
    QuizActiveMixin,
    QuizSoftDeleteMixin,
    QuizTimeStampMixin,
    nanoid_generator,
)


class Quiz(QuizTimeStampMixin, QuizActiveMixin, QuizSoftDeleteMixin):
    """Represent a quiz assigned to a tenant."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    code = models.CharField(
        max_length=36,
        default=nanoid_generator,
        unique=True,
    )
    quiz_type = models.CharField(
        max_length=30,
        choices=QuizTypeEnum.choices(),
        default=QuizTypeEnum.PRACTICE.value,
    )
    configuration = models.JSONField(
        default=dict,
        help_text="Quiz configuration.",
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
        db_table = "quiz"
        verbose_name = "Quiz"
        verbose_name_plural = "Quizzes"
        indexes = [
            models.Index(
                fields=("tenant",),
                condition=models.Q(
                    is_active=True,
                    is_deleted=False,
                ),
                name="idx_quiz_tenant_active",
            ),
        ]
