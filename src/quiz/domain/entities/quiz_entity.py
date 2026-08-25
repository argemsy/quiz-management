import uuid
from dataclasses import dataclass, field
from typing import Any

from src.quiz.domain.exceptions import InvalidQuizConfigurationError
from src.quiz.shared.quiz_enums import OrderStrategyEnum, QuizTypeEnum
from src.shared.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class QuizConfiguration:
    total_questions_allowed: int = 20
    min_questions_allowed: int = 1
    max_answers_allowed: int = 5
    time_limit_minutes: int = 60
    allow_review: bool = True
    allowed_attempts: int | None = None
    question_order: OrderStrategyEnum = OrderStrategyEnum.AS_AUTHORED
    answer_order: OrderStrategyEnum = OrderStrategyEnum.AS_AUTHORED

    def __post_init__(self):
        # Hydrated from raw JSON by `QuizEntity._build_configuration`, so the
        # ordering fields arrive as plain strings from the database and as
        # enum members from Python callers. Normalising here keeps every
        # consumer free of that distinction. The dataclass is frozen, hence
        # `object.__setattr__`.
        for field_name in ("question_order", "answer_order"):
            value = getattr(self, field_name)
            if not isinstance(value, OrderStrategyEnum):
                object.__setattr__(self, field_name, OrderStrategyEnum(value))

        if self.total_questions_allowed <= 0:
            raise InvalidQuizConfigurationError(
                "total_questions_allowed must be greater than 0"
            )
        if self.time_limit_minutes <= 0:
            raise InvalidQuizConfigurationError(
                "time_limit_minutes must be greater than 0"
            )
        if self.min_questions_allowed <= 0:
            raise InvalidQuizConfigurationError(
                "min_questions_allowed must be greater than 0"
            )
        if self.min_questions_allowed > self.total_questions_allowed:
            raise InvalidQuizConfigurationError(
                "min_questions_allowed cannot exceed total_questions_allowed"
            )
        if self.max_answers_allowed <= 0:
            raise InvalidQuizConfigurationError(
                "max_answers_allowed must be greater than 0"
            )

    def to_primitive(self):
        return {
            "total_questions_allowed": self.total_questions_allowed,
            "min_questions_allowed": self.min_questions_allowed,
            "max_answers_allowed": self.max_answers_allowed,
            "time_limit_minutes": self.time_limit_minutes,
            "allow_review": self.allow_review,
            "allowed_attempts": self.allowed_attempts,
            "question_order": self.question_order.value,
            "answer_order": self.answer_order.value,
        }


@dataclass(frozen=True)
class QuizEntity:
    id: uuid.UUID | None = None
    code: str | None = None
    quiz_type: QuizTypeEnum | None = None
    tenant: uuid.UUID | None = None
    tenant_user: uuid.UUID | None = None
    is_active: bool = True
    configuration: QuizConfiguration = field(default_factory=QuizConfiguration)

    @staticmethod
    def _build_configuration(data: dict[str, Any]) -> QuizConfiguration:
        if not data:
            logger.warning("QuizEntity. No configuration provided", data=data)
            return QuizConfiguration()

        return QuizConfiguration(**data)

    @staticmethod
    def _get_quiz_type_enum(value: str) -> QuizTypeEnum:
        """Convert a persisted value into a quiz type enum."""
        try:
            return QuizTypeEnum(value)
        except ValueError as exc:
            logger.error(
                "QuizEntity. Invalid quiz type provided",
                value=value,
            )
            raise ValueError(f"Invalid quiz type: {value}") from exc

    def __post_init__(self) -> None:
        """Validate the entity invariants."""
        uuid_fields = (
            self.id,
            self.tenant,
            self.tenant_user,
        )

        if any(
            value is not None and not isinstance(value, uuid.UUID)
            for value in uuid_fields
        ):
            raise ValueError("QuizEntity UUID fields must contain valid UUID values")

    @classmethod
    def from_model(cls, instance: Any) -> "QuizEntity":
        return cls(
            id=instance.id,
            code=str(instance.code),
            quiz_type=cls._get_quiz_type_enum(instance.quiz_type),
            tenant=instance.tenant,
            tenant_user=instance.tenant_user,
            is_active=instance.is_active,
            configuration=cls._build_configuration(instance.configuration),
        )
