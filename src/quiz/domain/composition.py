from typing import Protocol, Sequence

from src.quiz.domain.entities.quiz_entity import QuizConfiguration
from src.quiz.domain.exceptions import (
    AnswerChoiceLimitExceededError,
    QuestionLimitExceededError,
)


class _HasAnswerChoices(Protocol):
    """Structural type covering both `QuestionEntity` and `QuestionDTO`.

    `validate_composition` runs against the DTOs the resolver built, before
    any entity exists, but must stay usable against entities too. A protocol
    keeps the domain from importing the application layer's DTOs.
    """

    text: str
    answer_choices: Sequence


def validate_composition(
    configuration: QuizConfiguration,
    questions: Sequence[_HasAnswerChoices],
) -> None:
    """Check a quiz's contents against the upper bounds it declares.

    Raises:
        QuestionLimitExceededError: More questions than
            `total_questions_allowed`.
        AnswerChoiceLimitExceededError: Some question offers more choices
            than `max_answers_allowed`.
    """
    if len(questions) > configuration.total_questions_allowed:
        raise QuestionLimitExceededError(
            submitted=len(questions),
            allowed=configuration.total_questions_allowed,
        )

    for question in questions:
        if len(question.answer_choices) > configuration.max_answers_allowed:
            raise AnswerChoiceLimitExceededError(
                question_text=question.text,
                submitted=len(question.answer_choices),
                allowed=configuration.max_answers_allowed,
            )


def is_publishable(
    active_question_count: int,
    configuration: QuizConfiguration,
) -> bool:
    """Whether a quiz holds enough questions to put in front of a student.

    Derived from the current count rather than stored, so it cannot drift
    out of sync with the quiz's contents — `SoftDeleteAdminMixin`'s bulk
    actions are plain `queryset.update()` calls that fire no model signals,
    which is exactly the case a stored flag would miss. The caller supplies
    a count of questions that are active and not soft-deleted.
    """
    return active_question_count >= configuration.min_questions_allowed
