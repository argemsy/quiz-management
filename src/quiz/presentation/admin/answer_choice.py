from django.contrib import admin

from src.quiz.infrastructure.persistence.django.models import AnswerChoiceModel
from src.shared.presentation.admin import CommonAdminActionsMixin


@admin.register(AnswerChoiceModel)
class AnswerChoiceAdmin(CommonAdminActionsMixin, admin.ModelAdmin):
    list_display = (
        "text",
        "question",
        "order",
        "is_correct",
        "is_active",
        "is_deleted",
    )
    list_editable = ("order",)
    list_filter = ("is_correct", "is_active", "is_deleted")
    search_fields = ("text",)
    ordering = ("question", "order", "created_at")
    readonly_fields = ("id", "created_at", "updated_at")
