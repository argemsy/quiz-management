import uuid
from dataclasses import dataclass

import pytest

from src.quiz.domain.ordering import resolve_answer_order, resolve_question_order
from src.quiz.shared.quiz_enums import OrderStrategyEnum

FORM_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_FORM_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
QUESTION_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


@dataclass(frozen=True)
class _Item:
    name: str
    order: int


def _items(count: int = 8) -> list[_Item]:
    return [_Item(name=f"item-{index}", order=index) for index in range(1, count + 1)]


def test_as_authored_returns_items_sorted_by_position():
    shuffled_input = [_Item("c", 3), _Item("a", 1), _Item("b", 2)]

    result = resolve_question_order(
        shuffled_input, OrderStrategyEnum.AS_AUTHORED, FORM_ID
    )

    assert [item.name for item in result] == ["a", "b", "c"]


def test_as_authored_breaks_ties_by_incoming_sequence():
    """Sort stability is what carries the `created_at` tie-break through:
    rows arrive ordered by ("order", "created_at") from the model layer."""
    tied = [_Item("first", 1), _Item("second", 1), _Item("third", 1)]

    result = resolve_question_order(tied, OrderStrategyEnum.AS_AUTHORED, FORM_ID)

    assert [item.name for item in result] == ["first", "second", "third"]


def test_random_is_stable_for_the_same_form():
    items = _items()

    first = resolve_question_order(items, OrderStrategyEnum.RANDOM, FORM_ID)
    second = resolve_question_order(items, OrderStrategyEnum.RANDOM, FORM_ID)

    assert first == second


def test_random_differs_between_forms():
    items = _items(12)

    first = resolve_question_order(items, OrderStrategyEnum.RANDOM, FORM_ID)
    second = resolve_question_order(items, OrderStrategyEnum.RANDOM, OTHER_FORM_ID)

    assert first != second


def test_random_does_not_mutate_its_input():
    items = _items()
    original = list(items)

    resolve_question_order(items, OrderStrategyEnum.RANDOM, FORM_ID)

    assert items == original


def test_random_is_a_permutation():
    items = _items()

    result = resolve_question_order(items, OrderStrategyEnum.RANDOM, FORM_ID)

    assert sorted(result, key=lambda item: item.order) == items


@pytest.mark.parametrize("strategy", list(OrderStrategyEnum))
def test_answer_order_is_stable_for_the_same_question(strategy):
    choices = _items(5)

    first = resolve_answer_order(choices, strategy, FORM_ID, QUESTION_ID)
    second = resolve_answer_order(choices, strategy, FORM_ID, QUESTION_ID)

    assert first == second


def test_answer_order_differs_between_questions_of_the_same_form():
    """The seed folds in the question id so each question shuffles
    independently — otherwise every question in a form would present its
    choices in the same permutation."""
    choices = _items(10)
    other_question = uuid.UUID("44444444-4444-4444-4444-444444444444")

    first = resolve_answer_order(
        choices, OrderStrategyEnum.RANDOM, FORM_ID, QUESTION_ID
    )
    second = resolve_answer_order(
        choices, OrderStrategyEnum.RANDOM, FORM_ID, other_question
    )

    assert first != second


def test_random_order_is_reproducible_across_processes():
    """Pinned to literal values on purpose.

    A seed derived from `hash()` would pass every other test in this file
    and still produce a different permutation in a process started with a
    different PYTHONHASHSEED, breaking the reload-stability and audit
    guarantees. Only a hardcoded expectation catches that regression.
    """
    items = _items(6)

    result = resolve_question_order(items, OrderStrategyEnum.RANDOM, FORM_ID)

    assert [item.order for item in result] == [5, 1, 6, 4, 2, 3]
