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
    def save_sync(self, quiz: QuizEntity) -> QuizEntity:
        """Plain synchronous write, deliberately outside the async ABC
        convention: it exists so a caller can compose it into another
        transaction (e.g. `IdempotencyReservationRepository.reserve_and_run`)
        — `create` alone can't share a transaction with another
        independently `sync_to_async`-wrapped call. Not part of the async
        port surface `QuizService.create_quiz` uses for the ordinary path.
        """
