from django.apps import AppConfig


class QuizConfig(AppConfig):
    name = "src.quiz"
    label = "quiz"

    def ready(self):
        import src.quiz.presentation.admin  # type: ignore
        from src.quiz.infrastructure.event_handlers.quiz_event_handlers import (
            handle_questions_requested,
        )
        from src.quiz.shared.quiz_event_channels import QuizEventChannel
        from src.shared.infrastructure.event_bus import get_event_bus

        get_event_bus().subscribe(
            QuizEventChannel.QUESTIONS_REQUESTED, handle_questions_requested
        )
