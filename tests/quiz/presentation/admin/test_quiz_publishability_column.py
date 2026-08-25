import pytest
from django.contrib import admin
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from src.account.infrastructure.persistence.django.models import MyUser
from src.quiz.domain.entities.quiz_entity import QuizConfiguration
from src.quiz.infrastructure.persistence.django.models import QuizModel
from src.quiz.presentation.admin.quiz import QuizAdmin

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_request():
    request = RequestFactory().get("/admin/")
    request.user = MyUser.objects.create_superuser(
        username="admin", email="admin@example.com", password="pw"
    )
    return request


def _quiz_admin() -> QuizAdmin:
    return QuizAdmin(QuizModel, admin.site)


def _annotated(admin_request, quiz) -> QuizModel:
    return _quiz_admin().get_queryset(admin_request).get(id=quiz.id)


def test_counts_only_active_undeleted_questions(
    admin_request, make_quiz, make_question
):
    quiz = make_quiz()
    make_question(quiz=quiz, text="counted")
    make_question(quiz=quiz, text="deleted", is_deleted=True)
    make_question(quiz=quiz, text="inactive", is_active=False)

    row = _annotated(admin_request, quiz)

    assert _quiz_admin().active_question_count(row) == 1


def test_publishable_flips_when_questions_drop_below_the_minimum(
    admin_request, make_quiz, make_question
):
    configuration = QuizConfiguration(min_questions_allowed=2).to_primitive()
    quiz = make_quiz(configuration=configuration)
    make_question(quiz=quiz, text="q1")
    second = make_question(quiz=quiz, text="q2")

    assert _quiz_admin().is_publishable(_annotated(admin_request, quiz)) is True

    second.is_deleted = True
    second.save(update_fields=["is_deleted"])

    assert _quiz_admin().is_publishable(_annotated(admin_request, quiz)) is False


def test_quiz_with_no_questions_is_not_publishable(admin_request, make_quiz):
    quiz = make_quiz(
        configuration=QuizConfiguration(min_questions_allowed=1).to_primitive()
    )

    assert _quiz_admin().is_publishable(_annotated(admin_request, quiz)) is False


def test_changelist_does_not_issue_a_count_per_quiz(
    admin_request, make_quiz, make_question
):
    """The whole point of annotating: a per-row count would grow with the
    number of quizzes on the page."""
    for index in range(5):
        quiz = make_quiz()
        make_question(quiz=quiz, text=f"q{index}")

    model_admin = _quiz_admin()
    with CaptureQueriesContext(connection) as captured:
        rows = list(model_admin.get_queryset(admin_request))
        for row in rows:
            model_admin.active_question_count(row)
            model_admin.is_publishable(row)

    assert len(rows) == 5
    assert len(captured.captured_queries) == 1
