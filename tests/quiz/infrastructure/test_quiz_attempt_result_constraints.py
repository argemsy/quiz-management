import uuid

import pytest
from django.db import IntegrityError, transaction

from src.quiz.infrastructure.persistence.django.models import (
    QuizUserResultHistoryModel,
    QuizUserResultModel,
)

pytestmark = pytest.mark.django_db


def test_unaffiliated_user_second_current_result_is_rejected(make_quiz, make_quiz_form):
    quiz = make_quiz()
    user = uuid.uuid4()
    form_a = make_quiz_form(quiz=quiz, user=user)
    form_b = make_quiz_form(quiz=quiz, user=user)
    QuizUserResultModel.objects.create(
        user=user, quiz=quiz, quiz_form=form_a, attempt_number=1
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            QuizUserResultModel.objects.create(
                user=user, quiz=quiz, quiz_form=form_b, attempt_number=2
            )


def test_affiliated_user_second_current_result_is_rejected(make_quiz, make_quiz_form):
    quiz = make_quiz()
    user = uuid.uuid4()
    tenant_user = uuid.uuid4()
    form_a = make_quiz_form(quiz=quiz, user=user, tenant_user=tenant_user)
    form_b = make_quiz_form(quiz=quiz, user=user, tenant_user=tenant_user)
    QuizUserResultModel.objects.create(
        user=user,
        tenant_user=tenant_user,
        quiz=quiz,
        quiz_form=form_a,
        attempt_number=1,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            QuizUserResultModel.objects.create(
                user=user,
                tenant_user=tenant_user,
                quiz=quiz,
                quiz_form=form_b,
                attempt_number=2,
            )


def test_distinct_quizzes_reuse_attempt_numbers_independently(
    make_quiz, make_quiz_form
):
    quiz_a = make_quiz()
    quiz_b = make_quiz()
    user = uuid.uuid4()
    form_a = make_quiz_form(quiz=quiz_a, user=user)
    form_b = make_quiz_form(quiz=quiz_b, user=user)

    QuizUserResultHistoryModel.objects.create(
        user=user, quiz=quiz_a, quiz_form=form_a, attempt_number=1
    )
    QuizUserResultHistoryModel.objects.create(
        user=user, quiz=quiz_b, quiz_form=form_b, attempt_number=1
    )

    assert (
        QuizUserResultHistoryModel.objects.filter(user=user, attempt_number=1).count()
        == 2
    )


def test_duplicate_attempt_for_same_quiz_is_rejected(make_quiz, make_quiz_form):
    quiz = make_quiz()
    user = uuid.uuid4()
    form_a = make_quiz_form(quiz=quiz, user=user)
    form_b = make_quiz_form(quiz=quiz, user=user)
    QuizUserResultHistoryModel.objects.create(
        user=user, quiz=quiz, quiz_form=form_a, attempt_number=1
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            QuizUserResultHistoryModel.objects.create(
                user=user, quiz=quiz, quiz_form=form_b, attempt_number=1
            )
