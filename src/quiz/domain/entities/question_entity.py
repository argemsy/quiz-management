import uuid
from dataclasses import dataclass, field

from src.quiz.shared.quiz_enums import QuestionResponseTypeEnum


@dataclass(frozen=True)
class AnswerChoiceEntity:
    text: str
    is_correct: bool
    id: uuid.UUID | None = None


@dataclass(frozen=True)
class QuestionEntity:
    text: str
    response_type: QuestionResponseTypeEnum
    answer_choices: list[AnswerChoiceEntity] = field(default_factory=list)
    id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if not self.answer_choices:
            raise ValueError("A question must have at least one answer choice")
