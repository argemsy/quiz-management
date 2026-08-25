import pytest

from src.quiz.infrastructure.persistence.django.models import (
    AnswerChoiceModel,
    QuestionModel,
)

pytestmark = pytest.mark.django_db


def test_questions_are_read_back_ordered_by_position(make_quiz):
    """`Meta.ordering` means an unqualified queryset already comes back in
    authored order — no caller has to remember to sort."""
    quiz = make_quiz()
    for position, text in ((3, "third"), (1, "first"), (2, "second")):
        QuestionModel.objects.create(
            text=text,
            quiz=quiz,
            order=position,
            tenant=quiz.tenant,
            tenant_user=quiz.tenant_user,
        )

    assert [q.text for q in QuestionModel.objects.filter(quiz=quiz)] == [
        "first",
        "second",
        "third",
    ]


def test_answer_choices_are_read_back_ordered_by_position(make_question):
    question = make_question()
    for position, text in ((2, "beta"), (1, "alpha")):
        AnswerChoiceModel.objects.create(
            text=text,
            question=question,
            order=position,
            tenant=question.tenant,
            tenant_user=question.tenant_user,
        )

    assert [c.text for c in question.answers.all()] == ["alpha", "beta"]


def test_equal_positions_are_broken_by_creation_time(make_quiz):
    """Nothing stops two rows sharing a position — there is deliberately no
    unique constraint on `order`, because Django cannot defer a conditional
    one and a non-deferrable partial unique would abort any two-position
    swap mid-UPDATE. The `created_at` tie-break is what keeps the read
    deterministic anyway."""
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
