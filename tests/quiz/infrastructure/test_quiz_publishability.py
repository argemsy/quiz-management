import pytest
from asgiref.sync import sync_to_async

from src.quiz.domain.composition import is_publishable
from src.quiz.domain.entities.quiz_entity import QuizConfiguration
from src.quiz.infrastructure.repositories.quiz_repository_imp import QuizRepositoryImpl

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.asyncio
async def test_count_ignores_soft_deleted_and_inactive_questions(
    make_quiz, make_question
):
    """The count is what `min_questions_allowed` is measured against, so a
    question the schema already treats as non-existent must not prop a quiz
    up above its minimum."""

    def _setup():
        quiz = make_quiz()
        make_question(quiz=quiz, text="counted-1")
        make_question(quiz=quiz, text="counted-2")
        make_question(quiz=quiz, text="soft-deleted", is_deleted=True)
        make_question(quiz=quiz, text="inactive", is_active=False)
        return quiz

    quiz = await sync_to_async(_setup, thread_sensitive=True)()

    count = await QuizRepositoryImpl().count_active_questions(quiz.id)

    assert count == 2


@pytest.mark.asyncio
async def test_quiz_with_no_questions_counts_zero(make_quiz):
    quiz = await sync_to_async(make_quiz, thread_sensitive=True)()

    assert await QuizRepositoryImpl().count_active_questions(quiz.id) == 0


@pytest.mark.asyncio
async def test_soft_deleting_a_question_can_make_a_quiz_unpublishable(
    make_quiz, make_question
):
    """The end-to-end shape of the rule: publishability is derived, so it
    flips the moment the underlying rows change, with nothing to keep in
    sync."""
    configuration = QuizConfiguration(min_questions_allowed=2)

    def _setup():
        quiz = make_quiz()
        return quiz, [make_question(quiz=quiz, text=f"q{index}") for index in range(2)]

    quiz, questions = await sync_to_async(_setup, thread_sensitive=True)()
    repository = QuizRepositoryImpl()

    assert is_publishable(
        await repository.count_active_questions(quiz.id), configuration
    )

    def _soft_delete():
        questions[0].is_deleted = True
        questions[0].save(update_fields=["is_deleted"])

    await sync_to_async(_soft_delete, thread_sensitive=True)()

    assert not is_publishable(
        await repository.count_active_questions(quiz.id), configuration
    )
