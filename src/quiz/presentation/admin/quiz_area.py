from django.contrib import admin

from src.quiz.infrastructure.persistence.django.models import QuizAreaModel


@admin.register(QuizAreaModel)
class QuizAreaAdmin(admin.ModelAdmin):
    list_display = ("quiz", "area", "tenant", "created_at")
    search_fields = ("quiz__code", "area__name")
    # Both sides grow without bound, so the change form must not render a
    # select holding every quiz and every area.
    raw_id_fields = ("quiz", "area")
    readonly_fields = ("id", "created_at", "updated_at")
