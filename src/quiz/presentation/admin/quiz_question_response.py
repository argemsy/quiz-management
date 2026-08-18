from django.contrib import admin

from src.quiz.infrastructure.persistence.django.models import (
    QuizQuestionResponseModel,
)


@admin.register(QuizQuestionResponseModel)
class QuizQuestionResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "quiz_form", "question", "response_type", "answer_choice")
    list_filter = ("response_type",)
    search_fields = ("user", "tenant_user")
    readonly_fields = ("id", "response_type", "created_at", "updated_at")
