import uuid

from django.db import models

from src.shared.infrastructure.persistence.django.models import (
    QuizActiveMixin,
    QuizTimeStampMixin,
)


class Area(QuizTimeStampMixin, QuizActiveMixin):
    """A tenant-defined classification for quizzes.

    The vocabulary belongs to the tenant, not to the system: a school's areas
    are subjects, a company's are departments. `parent` gives one optional
    level below that ("Ciencias" → "Ciencias I"), capped at two levels by
    `AreaEntity`'s invariants — which is what keeps cycles unrepresentable.

    Deliberately without `QuizSoftDeleteMixin`: deactivation is this model's
    whole lifecycle, and a second overlapping "gone" flag would only raise
    the question of which one the identity constraint should honour.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(max_length=150)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        help_text="The root area this one belongs under, or empty if it is a root.",
    )
    tenant = models.UUIDField(
        db_column="tenant_id",
        editable=False,
        help_text="The tenant(uuid) this area belongs to",
    )
    tenant_user = models.UUIDField(
        db_column="tenant_user_id",
        editable=False,
        help_text=(
            "The tenant_user(uuid) that created this area. Authorship only — "
            "an area belongs to its organization, not to its author, so this "
            "takes no part in the uniqueness constraint."
        ),
    )

    class Meta:
        db_table = "area"
        verbose_name = "Area"
        verbose_name_plural = "Areas"
        ordering = ("name",)
        constraints = [
            # `parent` is nullable and Postgres treats NULLs as distinct in a
            # unique index by default, which would silently permit two root
            # areas named "Ciencias" in one tenant — precisely the
            # duplication this constraint exists to prevent. NULLS NOT
            # DISTINCT is what makes the root case actually collide.
            models.UniqueConstraint(
                fields=("tenant", "parent", "name"),
                condition=models.Q(is_active=True),
                nulls_distinct=False,
                name="uq_area_tenant_parent_name_active",
            ),
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("id")),
                name="ck_area_not_its_own_parent",
            ),
        ]
        indexes = [
            models.Index(
                fields=("tenant",),
                condition=models.Q(is_active=True),
                name="idx_area_tenant_active",
            ),
            models.Index(
                fields=("parent",),
                name="idx_area_parent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.parent.name} / {self.name}" if self.parent_id else self.name
