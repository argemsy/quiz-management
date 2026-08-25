from django.contrib import admin

from src.quiz.infrastructure.persistence.django.models import QuizFormModel


@admin.register(QuizFormModel)
class QuizFormAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "quiz", "status", "started_at", "expires_at")
    list_filter = ("status",)
    search_fields = ("user", "tenant_user")
    readonly_fields = (
        "id",
        "quiz_configuration_snapshot",
        "created_at",
        "updated_at",
    )
