import uuid

import pytest
from asgiref.sync import sync_to_async

from src.quiz.application.create_questions_use_case.dto import CreateQuestionsDTO
from src.quiz.application.create_questions_use_case.question_service import (
    QuestionService,
)
from src.quiz.application.create_questions_use_case.use_case import (
    CreateQuestionsUseCase,
)
from src.quiz.infrastructure.persistence.django.models import QuestionModel
from src.quiz.infrastructure.repositories.question_repository_imp import (
    QuestionRepositoryImpl,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _question_payload(text: str, choice_texts: list[str]) -> dict:
    return {
        "text": text,
        "response_type": "SINGLE",
        "answer_choices": [
            {"text": choice_text, "is_correct": index == 0}
            for index, choice_text in enumerate(choice_texts)
        ],
    }


async def _create_questions(quiz, questions: list[dict]) -> None:
    use_case = CreateQuestionsUseCase(QuestionService(QuestionRepositoryImpl()))
    await use_case.execute(
        CreateQuestionsDTO(
            quiz_id=quiz.id,
            tenant=quiz.tenant,
            tenant_user=quiz.tenant_user,
            questions=questions,
            correlation_id=str(uuid.uuid4()),
        )
    )


@pytest.mark.asyncio
async def test_positions_follow_the_submitted_order(make_quiz):
    quiz = await sync_to_async(make_quiz, thread_sensitive=True)()

    await _create_questions(
        quiz,
        [
            _question_payload("third-submitted", ["a", "b"]),
            _question_payload("first-submitted", ["c", "d"]),
            _question_payload("second-submitted", ["e", "f"]),
        ],
    )

    stored = await sync_to_async(
        lambda: list(
            QuestionModel.objects.filter(quiz=quiz).values_list("text", "order")
        ),
        thread_sensitive=True,
    )()

    assert stored == [
        ("third-submitted", 1),
        ("first-submitted", 2),
        ("second-submitted", 3),
    ]


@pytest.mark.asyncio
async def test_answer_choices_are_numbered_within_their_question(make_quiz):
    quiz = await sync_to_async(make_quiz, thread_sensitive=True)()

    await _create_questions(
        quiz,
        [
            _question_payload("q1", ["alpha", "beta", "gamma"]),
            _question_payload("q2", ["delta", "epsilon"]),
        ],
    )

    def _choices_by_question():
        return {
            question.text: list(question.answers.values_list("text", "order"))
            for question in QuestionModel.objects.filter(quiz=quiz)
        }

    stored = await sync_to_async(_choices_by_question, thread_sensitive=True)()

    assert stored["q1"] == [("alpha", 1), ("beta", 2), ("gamma", 3)]
    assert stored["q2"] == [("delta", 1), ("epsilon", 2)]


@pytest.mark.asyncio
async def test_default_ordering_makes_reads_follow_position(make_quiz):
    """`Meta.ordering` means an unqualified queryset already comes back in
    authored order — no caller has to remember to sort."""
    quiz = await sync_to_async(make_quiz, thread_sensitive=True)()

    await _create_questions(
        quiz,
        [_question_payload(f"q{index}", ["x", "y"]) for index in range(5)],
    )

    ordered = await sync_to_async(
        lambda: [
            question.order for question in QuestionModel.objects.filter(quiz=quiz)
        ],
        thread_sensitive=True,
    )()

    assert ordered == [1, 2, 3, 4, 5]


def test_equal_positions_are_broken_by_creation_time(make_quiz):
    """Nothing stops two rows sharing a position — there is deliberately no
    unique constraint on `order`. The `created_at` tie-break is what keeps
    the read deterministic anyway."""
    quiz = make_quiz()
    for text in ("first", "second"):
        QuestionModel.objects.create(
            text=text,
            quiz=quiz,
            order=1,
            tenant=quiz.tenant,
            tenant_user=quiz.tenant_user,
        )

    reads = [
        [question.text for question in QuestionModel.objects.filter(quiz=quiz)]
        for _ in range(3)
    ]

    assert reads[0] == ["first", "second"]
    assert reads[0] == reads[1] == reads[2]
