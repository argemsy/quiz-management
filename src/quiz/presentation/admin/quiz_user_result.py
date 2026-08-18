from django.contrib import admin

from src.quiz.infrastructure.persistence.django.models import (
    QuizUserResultHistoryModel,
    QuizUserResultModel,
)
from src.shared.presentation.admin import ActivableAdminMixin


@admin.register(QuizUserResultModel)
class QuizUserResultAdmin(ActivableAdminMixin, admin.ModelAdmin):
    list_display = ("user", "quiz", "attempt_number", "status", "is_active")
    list_filter = ("status", "is_active")
    search_fields = ("user", "tenant_user")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(QuizUserResultHistoryModel)
class QuizUserResultHistoryAdmin(ActivableAdminMixin, admin.ModelAdmin):
    list_display = ("user", "quiz", "attempt_number", "status", "is_active")
    list_filter = ("status", "is_active")
    search_fields = ("user", "tenant_user")
    readonly_fields = ("id", "created_at", "updated_at")
