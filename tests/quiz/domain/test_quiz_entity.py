import pytest

from src.quiz.domain.entities.quiz_entity import QuizConfiguration, QuizEntity
from src.quiz.domain.exceptions import InvalidQuizConfigurationError
from src.quiz.shared.quiz_enums import OrderStrategyEnum


def test_defaults_are_coherent():
    configuration = QuizConfiguration()

    assert configuration.min_questions_allowed <= configuration.total_questions_allowed
    assert configuration.question_order is OrderStrategyEnum.AS_AUTHORED
    assert configuration.answer_order is OrderStrategyEnum.AS_AUTHORED


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_questions_allowed": 0},
        {"min_questions_allowed": -1},
        {"min_questions_allowed": 21, "total_questions_allowed": 20},
        {"max_answers_allowed": 0},
        {"total_questions_allowed": 0},
        {"time_limit_minutes": 0},
    ],
)
def test_rejects_incoherent_configuration(kwargs):
    with pytest.raises(InvalidQuizConfigurationError):
        QuizConfiguration(**kwargs)


def test_incoherent_configuration_is_a_validation_error_not_an_internal_one():
    """`InvalidQuizConfigurationError` is a `DomainError`, so
    `@handle_mutations_exceptions` maps it to `ValidationErrorResponse`. A
    plain `ValueError` here would surface to the client as an internal
    error for what is really bad input."""
    from src.shared.domain.exceptions import DomainError

    assert issubclass(InvalidQuizConfigurationError, DomainError)


def test_ordering_strategies_are_coerced_from_strings():
    """`QuizEntity._build_configuration` hydrates this from raw JSON, so the
    strategies arrive as strings out of the database."""
    configuration = QuizConfiguration(question_order="RANDOM", answer_order="RANDOM")

    assert configuration.question_order is OrderStrategyEnum.RANDOM
    assert configuration.answer_order is OrderStrategyEnum.RANDOM


def test_round_trips_through_to_primitive():
    original = QuizConfiguration(
        total_questions_allowed=30,
        min_questions_allowed=5,
        max_answers_allowed=6,
        question_order=OrderStrategyEnum.RANDOM,
    )

    restored = QuizConfiguration(**original.to_primitive())

    assert restored == original


def test_to_primitive_serialises_strategies_as_plain_values():
    primitive = QuizConfiguration().to_primitive()

    assert primitive["question_order"] == "AS_AUTHORED"
    assert primitive["answer_order"] == "AS_AUTHORED"


def test_legacy_configuration_without_new_keys_falls_back_to_defaults():
    """Quizzes created before this change have none of the four new keys in
    their stored configuration; reading them must not fail."""
    legacy = {
        "total_questions_allowed": 20,
        "time_limit_minutes": 60,
        "allow_review": True,
        "allowed_attempts": None,
    }

    configuration = QuizConfiguration(**legacy)

    assert configuration.min_questions_allowed == 1
    assert configuration.max_answers_allowed == 5
    assert configuration.question_order is OrderStrategyEnum.AS_AUTHORED


def test_empty_stored_configuration_falls_back_to_defaults():
    class _FakeQuizModel:
        id = None
        code = "abc123"
        quiz_type = "PRACTICE"
        tenant = None
        tenant_user = None
        is_active = True
        configuration = {}

    entity = QuizEntity.from_model(_FakeQuizModel())

    assert entity.configuration == QuizConfiguration()
