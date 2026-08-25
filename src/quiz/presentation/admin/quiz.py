from django.contrib import admin
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _

from src.quiz.domain.composition import is_publishable
from src.quiz.domain.entities.quiz_entity import QuizEntity
from src.quiz.infrastructure.persistence.django.models import QuestionModel, QuizModel
from src.shared.presentation.admin import (
    CommonAdminActionsMixin,
    TenantScopedInlineAdminMixin,
)


class QuestionInline(admin.TabularInline):
    model = QuestionModel
    extra = 0
    fields = ("order", "text", "response_type", "is_active", "is_deleted")
    ordering = ("order", "created_at")
    show_change_link = True


@admin.register(QuizModel)
class QuizAdmin(
    TenantScopedInlineAdminMixin, CommonAdminActionsMixin, admin.ModelAdmin
):
    list_display = (
        "code",
        "tenant",
        "quiz_type",
        "active_question_count",
        "is_publishable",
        "is_active",
        "is_deleted",
    )
    list_filter = ("quiz_type", "is_active", "is_deleted")
    search_fields = ("code", "tenant")
    readonly_fields = ("id", "code", "created_at", "updated_at")
    inlines = (QuestionInline,)

    def get_queryset(self, request):
        """Annotate the question count rather than counting per row.

        `is_publishable` is derived from the count on every render, so a
        per-row query would be one COUNT per quiz across the whole
        changelist.
        """
        return (
            super()
            .get_queryset(request)
            .annotate(
                _active_question_count=Count(
                    "questions",
                    filter=Q(questions__is_active=True, questions__is_deleted=False),
                )
            )
        )

    @admin.display(description=_("Questions"), ordering="_active_question_count")
    def active_question_count(self, obj) -> int:
        return obj._active_question_count

    @admin.display(description=_("Publishable"), boolean=True)
    def is_publishable(self, obj) -> bool:
        return is_publishable(
            obj._active_question_count,
            QuizEntity.from_model(obj).configuration,
        )
