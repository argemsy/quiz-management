import uuid

from django.db import models

from src.quiz.shared.quiz_enums import QuestionResponseTypeEnum
from src.shared.infrastructure.persistence.django.models import QuizTimeStampMixin


class QuizQuestionResponse(QuizTimeStampMixin):
    """Represent a user's response to a quiz question."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.UUIDField(
        db_column="user_id",
        editable=False,
        help_text="The user UUID that submitted this response.",
    )
    tenant_user = models.UUIDField(
        db_column="tenant_user_id",
        editable=False,
        null=True,
        blank=True,
        help_text="The optional tenant-user UUID associated with this form.",
    )
    quiz_form = models.ForeignKey(
        "QuizForm",
        on_delete=models.PROTECT,
        related_name="responses",
    )
    question = models.ForeignKey(
        "Question",
        on_delete=models.PROTECT,
        related_name="user_responses",
    )
    answer_choice = models.ForeignKey(
        "AnswerChoice",
        on_delete=models.PROTECT,
        related_name="user_responses",
        null=True,
        blank=True,
    )
    definition = models.TextField(
        null=True,
        blank=True,
    )
    response_type = models.CharField(
        max_length=20,
        choices=QuestionResponseTypeEnum.choices(),
        editable=False,
        help_text="Snapshot of Question.response_type when this response was recorded.",
    )

    class Meta:
        db_table = "quiz_question_response"
        verbose_name = "Quiz Question Response"
        verbose_name_plural = "Quiz Question Responses"
        constraints = [
            models.UniqueConstraint(
                fields=("quiz_form", "question"),
                condition=models.Q(response_type__in=["SINGLE", "DEFINITION"]),
                name="uq_response_single_definition_one_row",
            ),
            models.UniqueConstraint(
                fields=("quiz_form", "question", "answer_choice"),
                condition=models.Q(
                    response_type="MULTIPLE",
                    answer_choice__isnull=False,
                ),
                name="uq_response_multiple_per_choice",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(answer_choice__isnull=False, definition__isnull=True)
                    | models.Q(answer_choice__isnull=True, definition__isnull=False)
                ),
                name="ck_response_exactly_one_answer",
            ),
        ]
        indexes = [
            models.Index(
                fields=("quiz_form",),
                name="idx_question_response_form",
            ),
        ]
