from django.contrib import admin

from src.quiz.infrastructure.persistence.django.models import AnswerChoiceModel
from src.shared.presentation.admin import CommonAdminActionsMixin


@admin.register(AnswerChoiceModel)
class AnswerChoiceAdmin(CommonAdminActionsMixin, admin.ModelAdmin):
    list_display = ("text", "question", "is_correct", "is_active", "is_deleted")
    list_filter = ("is_correct", "is_active", "is_deleted")
    search_fields = ("text",)
    readonly_fields = ("id", "created_at", "updated_at")
