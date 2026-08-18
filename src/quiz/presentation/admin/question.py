from django.contrib import admin

from src.quiz.infrastructure.persistence.django.models import QuestionModel
from src.shared.presentation.admin import CommonAdminActionsMixin


@admin.register(QuestionModel)
class QuestionAdmin(CommonAdminActionsMixin, admin.ModelAdmin):
    list_display = ("text", "quiz", "response_type", "is_active", "is_deleted")
    list_filter = ("response_type", "is_active", "is_deleted")
    search_fields = ("text",)
    readonly_fields = ("id", "created_at", "updated_at")
