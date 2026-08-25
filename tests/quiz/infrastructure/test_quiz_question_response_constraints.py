import pytest
from django.db import IntegrityError, transaction

from src.quiz.infrastructure.persistence.django.models import QuizQuestionResponseModel

pytestmark = pytest.mark.django_db


def _respond(quiz_form, question, answer_choice=None, definition=None, **overrides):
    defaults = {
        "user": quiz_form.user,
        "quiz_form": quiz_form,
        "question": question,
        "response_type": question.response_type,
        "answer_choice": answer_choice,
        "definition": definition,
    }
    defaults.update(overrides)
    return QuizQuestionResponseModel.objects.create(**defaults)


def test_single_question_allows_one_response(
    make_quiz_form, make_question, make_answer_choice
):
    question = make_question(response_type="SINGLE")
    choice = make_answer_choice(question=question)
    quiz_form = make_quiz_form(quiz=question.quiz)

    response = _respond(quiz_form, question, answer_choice=choice)

    assert response.response_type == "SINGLE"


def test_single_question_second_response_is_rejected(
    make_quiz_form, make_question, make_answer_choice
):
    question = make_question(response_type="SINGLE")
    choice_a = make_answer_choice(question=question, text="A")
    choice_b = make_answer_choice(question=question, text="B")
    quiz_form = make_quiz_form(quiz=question.quiz)
    _respond(quiz_form, question, answer_choice=choice_a)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _respond(quiz_form, question, answer_choice=choice_b)


def test_definition_question_allows_one_response(make_quiz_form, make_question):
    question = make_question(response_type="DEFINITION")
    quiz_form = make_quiz_form(quiz=question.quiz)

    response = _respond(
        quiz_form, question, definition="Because it decouples dependencies"
    )

    assert response.definition == "Because it decouples dependencies"


def test_definition_question_second_response_is_rejected(make_quiz_form, make_question):
    question = make_question(response_type="DEFINITION")
    quiz_form = make_quiz_form(quiz=question.quiz)
    _respond(quiz_form, question, definition="First answer")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _respond(quiz_form, question, definition="Second answer")


def test_multiple_question_allows_one_response_per_choice(
    make_quiz_form, make_question, make_answer_choice
):
    question = make_question(response_type="MULTIPLE")
    choice_a = make_answer_choice(question=question, text="A")
    choice_b = make_answer_choice(question=question, text="B")
    quiz_form = make_quiz_form(quiz=question.quiz)

    _respond(quiz_form, question, answer_choice=choice_a)
    _respond(quiz_form, question, answer_choice=choice_b)

    assert (
        QuizQuestionResponseModel.objects.filter(
            quiz_form=quiz_form, question=question
        ).count()
        == 2
    )


def test_multiple_question_duplicate_choice_is_rejected(
    make_quiz_form, make_question, make_answer_choice
):
    question = make_question(response_type="MULTIPLE")
    choice = make_answer_choice(question=question)
    quiz_form = make_quiz_form(quiz=question.quiz)
    _respond(quiz_form, question, answer_choice=choice)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _respond(quiz_form, question, answer_choice=choice)
