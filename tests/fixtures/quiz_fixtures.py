import uuid

import pytest

from src.quiz.infrastructure.persistence.django.models import (
    AnswerChoiceModel,
    QuestionModel,
    QuizFormModel,
    QuizModel,
)


@pytest.fixture
def make_quiz(db):
    def _make(**overrides):
        defaults = {
            "tenant": uuid.uuid4(),
            "tenant_user": uuid.uuid4(),
        }
        defaults.update(overrides)
        return QuizModel.objects.create(**defaults)

    return _make


@pytest.fixture
def make_question(make_quiz):
    def _make(quiz=None, **overrides):
        quiz = quiz or make_quiz()
        defaults = {
            "text": "What is dependency injection?",
            "response_type": "SINGLE",
            "quiz": quiz,
            "order": QuestionModel.objects.filter(quiz=quiz).count() + 1,
            "tenant": quiz.tenant,
            "tenant_user": quiz.tenant_user,
        }
        defaults.update(overrides)
        return QuestionModel.objects.create(**defaults)

    return _make


@pytest.fixture
def make_answer_choice(make_question):
    def _make(question=None, **overrides):
        question = question or make_question()
        defaults = {
            "text": "Because it decouples dependencies",
            "question": question,
            "order": AnswerChoiceModel.objects.filter(question=question).count() + 1,
            "tenant": question.tenant,
            "tenant_user": question.tenant_user,
        }
        defaults.update(overrides)
        return AnswerChoiceModel.objects.create(**defaults)

    return _make


@pytest.fixture
def make_quiz_form(make_quiz):
    def _make(quiz=None, **overrides):
        quiz = quiz or make_quiz()
        defaults = {
            "user": uuid.uuid4(),
            "quiz": quiz,
        }
        defaults.update(overrides)
        return QuizFormModel.objects.create(**defaults)

    return _make
