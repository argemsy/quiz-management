## Why

An exam is a sequence with a size, and this system asserts neither.

**Ordering.** `QuestionModel` (`src/quiz/infrastructure/persistence/django/models/question.py`)
and `AnswerChoiceModel` (`.../answer_choice.py`) have no ordering column and no
`Meta.ordering`, so the sequence a taker would see is whatever Postgres happens to return —
unstable across queries, and silently different after any `UPDATE` that moves a row.
`QuestionRepositoryImpl.bulk_create` already receives the author's intended sequence (the
GraphQL input is a `list`, and `CreateQuestionsUseCase` iterates it in order) and then throws
that information away at the persistence boundary. The author cannot say "this question comes
third", and cannot fix it afterwards.

**Composition limits.** `QuizConfiguration` (`src/quiz/domain/entities/quiz_entity.py:11-30`)
declares `total_questions_allowed: int = 20`, but nothing reads it — nor
`time_limit_minutes`, `allow_review`, or `allowed_attempts`. The whole dataclass is dead
config: persisted into `Quiz.configuration` and never consulted. So today a quiz can be
created with 500 questions of 40 answer choices each and no rule objects, and conversely a
quiz with two questions is indistinguishable from a finished one — there is no notion of a
quiz being complete enough to put in front of a student.

Both gaps land in the same place (`CreateQuizUseCase._validate_questions`, whose docstring
already states its purpose is to fail the whole mutation up front rather than leave a Quiz
whose `QUESTIONS_REQUESTED` event is doomed), and both are about the author's control over
the shape of the exam. Hence one change.

## What Changes

### Authored order

- Add an `order` column (`PositiveIntegerField`) to `QuestionModel` and `AnswerChoiceModel`,
  with `Meta.ordering = ("order", "created_at")` and an index on `(quiz, order)` /
  `(question, order)` respectively. The `created_at` tie-break makes the ordering **total**
  even when two rows share an `order`, so no query is ever non-deterministic.
- **No unique constraint on `order`.** Django rejects `UniqueConstraint` combining
  `condition` with `deferrable` (`ValueError: UniqueConstraint with conditions cannot be
  deferred`), and every constraint in this app is partial over
  `is_active=True, is_deleted=False`. A non-deferrable partial unique would make any
  two-position swap fail mid-`UPDATE`. Density (`1..N`, no gaps) is instead an
  application-layer guarantee established at creation.
- Populate `order` from the input sequence: `CreateQuestionsUseCase` assigns
  `enumerate(..., start=1)` over `dto.questions` and over each question's `answer_choices`.
  **The GraphQL input surface does not change** — the list is already ordered, and an optional
  `order` input field would create a second source of truth for the same fact.
- Add `order: int` to `QuestionEntity` and `AnswerChoiceEntity`, persisted through the
  existing `bulk_create` calls — still one `bulk_create` per table, per mandatory pattern #1.
- Add `OrderStrategyEnum` (`AS_AUTHORED` | `RANDOM`) and two `QuizConfiguration` fields,
  `question_order` and `answer_order`, both defaulting to `AS_AUTHORED`.
- Add `src/quiz/domain/ordering.py`: pure, I/O-free resolution of a strategy plus a seed into
  a concrete sequence. `RANDOM` is **deterministic**, seeded from the `QuizForm` id (and, for
  answer choices, the question id) so a taker who reloads sees the same order and the sequence
  stays reproducible for later audit — without persisting a sequence anywhere.

### Composition limits

- `QuizConfiguration` gains `min_questions_allowed: int = 1` and
  `max_answers_allowed: int = 5`. **`total_questions_allowed` is deliberately left untouched
  and un-renamed** — it keeps its role as the upper bound on questions. Introducing a
  `max_questions_allowed` alongside it would create two fields that mean nearly the same
  thing and no way to tell which governs.
- `QuizConfiguration.__post_init__` validates its own coherence (pure, no I/O):
  `min_questions_allowed > 0`, `min_questions_allowed <= total_questions_allowed`,
  `max_answers_allowed > 0`, alongside the existing checks.
- Upper bounds are enforced **at quiz creation**, before any write:
  `len(dto.questions) <= total_questions_allowed`, and per question
  `len(answer_choices) <= max_answers_allowed`. New `DomainError` subclasses
  (`QuestionLimitExceededError`, `AnswerChoiceLimitExceededError`) so
  `@handle_mutations_exceptions` maps them to `ValidationErrorResponse` rather than the
  catch-all `InternalErrorResponse`.
- **`min_questions_allowed` is a publication gate, not a creation gate.** A quiz whose count
  of questions falls below it is not valid to expose to a student. Publishability is
  **derived**, not stored — no new status column, no lifecycle state machine.
- **Counting rule**: a question counts toward that threshold only if it is active and not
  soft-deleted (`is_active=True, is_deleted=False`) — the same predicate every partial
  constraint in this app already uses. Soft-deleting or deactivating a question therefore
  silently reduces the count and can render a quiz unpublishable; the Django admin surfaces
  this as a derived column so the author sees it, and nothing blocks the deletion.
- `QuizRepository` gains `count_active_questions(quiz_id) -> int` for that count.

### Data and admin

- Data migration renumbering pre-existing questions and answer choices to a dense `1..N` per
  group, ordered by `created_at`, accumulating and calling `bulk_update()` once.
- Django admin: `order` in `list_display` + `list_editable` on `QuestionAdmin` and
  `AnswerChoiceAdmin`; `AnswerChoiceInline` on `QuestionAdmin` and `QuestionInline` on
  `QuizAdmin` (reordering has no GraphQL path at all, so the admin is the only place an author
  can do it); a derived `is_publishable` column on `QuizAdmin`.

### Not in scope

`updateQuestion`/`reorderQuestions`/add-question mutations; reading a quiz back over GraphQL
(the root `Query` type is still empty — `src/shared/presentation/schema/schema.py:15`);
selecting *which* N questions a given attempt receives, and any replacement logic when one is
removed; `min_answers_allowed`; pinned answer choices; a stored draft/published lifecycle.

Known consequence, accepted and not resolved here: because no mutation can add questions to an
existing quiz, a quiz created below `min_questions_allowed` is permanently unpublishable. The
fix is an add-question mutation, which belongs to the editing change.

Latent bug noted but not fixed: `QuestionEntity.__post_init__` requires at least one answer
choice even for `DEFINITION` questions, which by definition should have none.

## Capabilities

### New Capabilities
- `quiz/question-ordering`: the authored-order guarantee for questions and answer choices —
  that a total, stable order exists and is derived from the author's input sequence — plus the
  per-quiz ordering strategy that turns it into a delivered sequence, including the
  determinism and per-attempt stability requirements for `RANDOM`.
- `quiz/quiz-composition`: the bounds a quiz's contents must satisfy — the upper limits on
  questions per quiz and answer choices per question enforced at creation, the minimum-question
  threshold below which a quiz may not be exposed to a student, and the active/not-soft-deleted
  rule that governs how contents are counted.

### Modified Capabilities
(none — `quiz/question-response`, `quiz/attempt-result`, and `quiz/tenant-scoping` cover
response cardinality, attempt bookkeeping, and tenant matching respectively; none of them makes
any claim about ordering or about how many questions a quiz may hold, so none of their
requirements change)

## Impact

- `src/quiz/shared/quiz_enums.py` (new `OrderStrategyEnum`)
- `src/quiz/domain/entities/question_entity.py` (`order` on both entities)
- `src/quiz/domain/entities/quiz_entity.py` (`QuizConfiguration`: two ordering fields, two
  limit fields, coherence checks in `__post_init__`, `.value` in `to_primitive()`, and
  `str → enum` coercion because `QuizEntity._build_configuration` calls
  `QuizConfiguration(**data)` on raw JSON)
- `src/quiz/domain/ordering.py`, `src/quiz/domain/composition.py` (new, pure)
- `src/quiz/domain/exceptions.py` (two new `DomainError` subclasses)
- `src/quiz/domain/repositories/quiz_repository.py` (`count_active_questions`)
- `src/quiz/infrastructure/persistence/django/models/{question,answer_choice}.py` + migration
  `0003_*` carrying the data renumbering
- `src/quiz/infrastructure/repositories/quiz_repository_imp.py` (count impl),
  `question_repository_imp.py` (persist `order`)
- `src/quiz/application/create_questions_use_case/use_case.py` (assign `order` from position)
- `src/quiz/application/create_quiz_use_case/use_case.py` (`_validate_questions` also runs the
  composition check)
- `src/quiz/presentation/schema/inputs/quiz_input.py`,
  `src/quiz/presentation/schema/quiz_enums.py` (four new `QuizConfigurationInput` fields —
  **additive with defaults, not breaking**: existing clients get `AS_AUTHORED` and the default
  limits)
- `src/quiz/presentation/admin/{question,answer_choice,quiz}.py` (ordering columns, inlines,
  derived publishability). The inlines must override `save_formset` to propagate
  `tenant`/`tenant_user` from the parent — both are `editable=False` and NOT NULL, so an insert
  from an inline would otherwise fail. The publishability column must be resolved with an
  annotated queryset, not a per-row count.
- `tests/fixtures/quiz_fixtures.py`, new domain tests, and the existing schema snapshot
  (`tests/quiz/presentation/schema/test_create_quiz_snapshot.py` — `QuizConfigurationInput`
  changes shape)
- No consumer of the ordering policy or the publishability rule exists yet: `QuizForm` /
  `QuizQuestionResponse` have models and constraints but no use cases. This change specifies
  and tests both rules as pure domain functions; the delivery flow wires them in.
