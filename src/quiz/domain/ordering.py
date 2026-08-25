import random
import uuid
from typing import Protocol, Sequence, TypeVar

from src.quiz.shared.quiz_enums import OrderStrategyEnum


class _Ordered(Protocol):
    order: int


T = TypeVar("T", bound=_Ordered)


def _seeded_shuffle(items: Sequence[T], seed: str) -> list[T]:
    """Shuffle a copy of `items` reproducibly from `seed`.

    The seed is handed to `random.Random` as a string rather than through
    `hash()`: `PYTHONHASHSEED` randomises `str` hashing per process, so a
    hash-derived seed would yield a different order after every restart,
    breaking both the reload-stability and the audit-reproducibility
    guarantees. `random.Random` seeded with the same value is stable across
    processes and releases.

    Not cryptographic. The order is predictable to anyone holding the seed's
    inputs, so it must never be relied on to conceal anything.
    """
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    return shuffled


def resolve_question_order(
    questions: Sequence[T],
    strategy: OrderStrategyEnum,
    quiz_form_id: uuid.UUID,
) -> list[T]:
    """Order a quiz form's questions for presentation.

    `AS_AUTHORED` sorts on `order` alone and leans on `sorted` being stable:
    equal positions keep the sequence they arrived in, which for rows read
    through the models' `Meta.ordering = ("order", "created_at")` is already
    the creation-time tie-break the spec calls for. Re-sorting on
    `created_at` here would mean carrying a timestamp the entities have no
    other reason to hold.
    """
    if strategy is OrderStrategyEnum.RANDOM:
        return _seeded_shuffle(questions, f"questions:{quiz_form_id}")
    return sorted(questions, key=lambda question: question.order)


def resolve_answer_order(
    choices: Sequence[T],
    strategy: OrderStrategyEnum,
    quiz_form_id: uuid.UUID,
    question_id: uuid.UUID,
) -> list[T]:
    """Order one question's answer choices for presentation.

    The seed folds in `question_id` so each question's choices are shuffled
    independently and reproducibly, whatever order the caller happens to
    walk the questions in.
    """
    if strategy is OrderStrategyEnum.RANDOM:
        return _seeded_shuffle(choices, f"answers:{quiz_form_id}:{question_id}")
    return sorted(choices, key=lambda choice: choice.order)
