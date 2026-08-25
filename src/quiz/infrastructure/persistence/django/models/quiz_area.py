import uuid

from django.db import models

from src.shared.infrastructure.persistence.django.models import QuizTimeStampMixin


class QuizArea(QuizTimeStampMixin):
    """Relates a quiz to an area it covers.

    A separate model rather than a foreign key on `Quiz` because a quiz may
    cover several areas — an integrative exam spanning Ciencias and
    Matemática. `area` points at whichever level applies, root or child;
    because the hierarchy is one table, this stays a single foreign key
    instead of a polymorphic pair.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    quiz = models.ForeignKey(
        "Quiz",
        on_delete=models.PROTECT,
        related_name="quiz_areas",
    )
    area = models.ForeignKey(
        "Area",
        on_delete=models.PROTECT,
        related_name="quiz_areas",
    )
    tenant = models.UUIDField(
        db_column="tenant_id",
        editable=False,
        help_text="The tenant(uuid) this relation belongs to",
    )
    tenant_user = models.UUIDField(
        db_column="tenant_user_id",
        editable=False,
        help_text="The tenant_user(uuid) that established this relation",
    )

    class Meta:
        db_table = "quiz_area"
        verbose_name = "Quiz Area"
        verbose_name_plural = "Quiz Areas"
        constraints = [
            models.UniqueConstraint(
                fields=("quiz", "area"),
                name="uq_quiz_area_quiz_area",
            ),
        ]
        indexes = [
            models.Index(
                fields=("area",),
                name="idx_quiz_area_area",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quiz.code} → {self.area}"
