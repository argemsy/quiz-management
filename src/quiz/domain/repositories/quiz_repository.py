import uuid
from abc import ABC, abstractmethod

from src.quiz.domain.entities.quiz_entity import QuizEntity


class QuizRepository(ABC):
    @abstractmethod
    async def create(self, quiz: QuizEntity) -> QuizEntity:
        pass

    @abstractmethod
    async def get_by_id(self, quiz_id: uuid.UUID) -> QuizEntity | None:
        pass

    @abstractmethod
    async def count_active_questions(self, quiz_id: uuid.UUID) -> int:
        """Count the quiz's questions that are active and not soft-deleted.

        The predicate matters: it is what `is_publishable` measures against
        `min_questions_allowed`, and it matches the condition every partial
        constraint in this app already uses.
        """

    @abstractmethod
    def save_sync(self, quiz: QuizEntity) -> QuizEntity:
        """Plain synchronous write, deliberately outside the async ABC
        convention: it exists so a caller can compose it into another
        transaction (e.g. `IdempotencyReservationRepository.reserve_and_run`)
        — `create` alone can't share a transaction with another
        independently `sync_to_async`-wrapped call. Not part of the async
        port surface `QuizService.create_quiz` uses for the ordinary path.
        """
