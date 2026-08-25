from django.contrib import admin

from src.quiz.infrastructure.persistence.django.models import (
    AnswerChoiceModel,
    QuestionModel,
)
from src.shared.presentation.admin import (
    CommonAdminActionsMixin,
    TenantScopedInlineAdminMixin,
)


class AnswerChoiceInline(admin.TabularInline):
    model = AnswerChoiceModel
    extra = 0
    fields = ("order", "text", "is_correct", "is_active", "is_deleted")
    ordering = ("order", "created_at")


@admin.register(QuestionModel)
class QuestionAdmin(
    TenantScopedInlineAdminMixin, CommonAdminActionsMixin, admin.ModelAdmin
):
    list_display = ("text", "quiz", "order", "response_type", "is_active", "is_deleted")
    list_editable = ("order",)
    list_filter = ("response_type", "is_active", "is_deleted")
    search_fields = ("text",)
    ordering = ("quiz", "order", "created_at")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (AnswerChoiceInline,)
