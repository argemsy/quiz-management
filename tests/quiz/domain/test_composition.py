from dataclasses import dataclass, field

import pytest

from src.quiz.domain.composition import is_publishable, validate_composition
from src.quiz.domain.entities.quiz_entity import QuizConfiguration
from src.quiz.domain.exceptions import (
    AnswerChoiceLimitExceededError,
    QuestionLimitExceededError,
)


@dataclass(frozen=True)
class _Question:
    text: str = "What is dependency injection?"
    answer_choices: list = field(default_factory=list)


def _questions(count: int, choices_each: int = 1) -> list[_Question]:
    return [
        _Question(text=f"question-{index}", answer_choices=[None] * choices_each)
        for index in range(count)
    ]


def test_passes_at_exactly_the_question_limit():
    configuration = QuizConfiguration(total_questions_allowed=3)

    validate_composition(configuration, _questions(3))


def test_rejects_one_question_over_the_limit():
    configuration = QuizConfiguration(total_questions_allowed=3)

    with pytest.raises(QuestionLimitExceededError) as exc_info:
        validate_composition(configuration, _questions(4))

    assert exc_info.value.submitted == 4
    assert exc_info.value.allowed == 3


def test_passes_at_exactly_the_answer_choice_limit():
    configuration = QuizConfiguration(max_answers_allowed=4)

    validate_composition(configuration, _questions(2, choices_each=4))


def test_rejects_one_answer_choice_over_the_limit():
    configuration = QuizConfiguration(max_answers_allowed=4)

    with pytest.raises(AnswerChoiceLimitExceededError) as exc_info:
        validate_composition(configuration, _questions(2, choices_each=5))

    assert exc_info.value.submitted == 5
    assert exc_info.value.allowed == 4


def test_reports_which_question_exceeded_the_choice_limit():
    configuration = QuizConfiguration(max_answers_allowed=2)
    questions = [
        _Question(text="fine", answer_choices=[None, None]),
        _Question(text="too many", answer_choices=[None, None, None]),
    ]

    with pytest.raises(AnswerChoiceLimitExceededError) as exc_info:
        validate_composition(configuration, questions)

    assert exc_info.value.question_text == "too many"


def test_empty_quiz_passes_the_upper_bounds():
    """The minimum is a publication gate, not a creation gate — an empty
    submission violates no upper bound."""
    validate_composition(QuizConfiguration(), [])


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, False), (4, False), (5, True), (6, True)],
)
def test_publishable_at_and_around_the_minimum(count, expected):
    configuration = QuizConfiguration(min_questions_allowed=5)

    assert is_publishable(count, configuration) is expected
