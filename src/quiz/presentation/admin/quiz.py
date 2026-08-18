from django.contrib import admin

from src.quiz.infrastructure.persistence.django.models import QuizModel
from src.shared.presentation.admin import CommonAdminActionsMixin


@admin.register(QuizModel)
class QuizAdmin(CommonAdminActionsMixin, admin.ModelAdmin):
    list_display = ("code", "tenant", "quiz_type", "is_active", "is_deleted")
    list_filter = ("quiz_type", "is_active", "is_deleted")
    search_fields = ("code", "tenant")
    readonly_fields = ("id", "code", "created_at", "updated_at")
